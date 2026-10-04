# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, ReadOnly, Timer


async def cycles(dut, n):
    """Return uo_out after n rising edges.

    ReadOnly is the phase where the nonblocking update is visible. Deposits
    are illegal there, so step 1 ns forward before returning. The clock
    period is 10 us, so this still lands well before the next edge.
    """
    await ClockCycles(dut.clk, n)
    await ReadOnly()
    value = int(dut.uo_out.value)
    await Timer(1, unit="ns")
    return value


@cocotb.test()
async def test_counter(dut):
    """Reset holds the count at 0. After release, each rising edge adds 1.

    One test owns the clock for the whole run. Cocotb cancels tasks when a
    test returns, so a second test would resume with a dead clock.
    """
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0

    # clk powers up as X. Drive 0 before starting so the first edge is 0->1.
    # Clock.start() already schedules the driver, and its first action is to
    # drive 1. Do not wrap it in start_soon.
    #
    # The gate netlist ties the flip-flop RESET_B pin high and applies reset
    # through D. That D is X until rst_n has propagated through the gates.
    # Starting the clock in the same timestep captures X, and the pin stays X.
    # One nanosecond is enough for the zero-delay gates to settle, and it is
    # far from the next edge of this 10 us clock.
    dut.clk.value = 0
    dut.rst_n.value = 0
    await Timer(1, unit="ns")
    Clock(dut.clk, 10, unit="us").start()

    # count is X until a rising edge applies the synchronous reset.
    assert await cycles(dut, 1) == 0
    assert await cycles(dut, 5) == 0

    # The edge just sampled still saw rst_n low. Release reset now, and the
    # next edge is the first one that increments.
    dut.rst_n.value = 1
    assert await cycles(dut, 1) == 1
    assert await cycles(dut, 9) == 10
