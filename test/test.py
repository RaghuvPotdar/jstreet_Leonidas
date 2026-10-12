# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, Timer

CLKS_PER_BIT = 16
# LSB is 1, so the wire must go low for the start bit and then high for bit 0.
BYTE = 0b10110001


async def pins(dut):
    """Return (tx, busy) after the next rising edge has updated the flops."""
    await RisingEdge(dut.clk)
    await ReadOnly()
    value = int(dut.uo_out.value)
    await Timer(1, unit="ns")
    return value & 1, (value >> 1) & 1


async def expect_bit(dut, level, n, name):
    for i in range(n):
        tx, busy = await pins(dut)
        assert tx == level and busy == 1, (
            f"{name} cycle {i}: tx={tx} busy={busy}, expected tx={level} busy=1"
        )


@cocotb.test()
async def test_uart_tx(dut):
    """One byte leaves on uo_out[0]. LSB first, 16 clocks per bit, no queue."""
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.clk.value = 0
    dut.rst_n.value = 0
    await Timer(1, unit="ns")
    Clock(dut.clk, 10, unit="us").start()

    tx, busy = await pins(dut)
    assert tx == 1 and busy == 0, f"after reset tx={tx} busy={busy}"

    dut.rst_n.value = 1
    dut.ui_in.value = BYTE
    dut.uio_in.value = 1
    tx, busy = await pins(dut)
    assert tx == 1 and busy == 1, f"copy cycle tx={tx} busy={busy}"
    dut.uio_in.value = 0

    await expect_bit(dut, 0, CLKS_PER_BIT, "start")
    for bit in range(8):
        await expect_bit(dut, (BYTE >> bit) & 1, CLKS_PER_BIT, f"data[{bit}]")
    await expect_bit(dut, 1, CLKS_PER_BIT, "stop")

    tx, busy = await pins(dut)
    assert tx == 1 and busy == 0, f"after frame tx={tx} busy={busy}"
