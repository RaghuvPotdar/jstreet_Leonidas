# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, Timer


async def clock_edge(dut):
    await RisingEdge(dut.clk)
    await ReadOnly()
    await Timer(1, unit="ns")


async def byte_strobe(dut, code, data):
    """Present one byte. The strobe returns to idle before the next byte."""
    dut.ui_in.value = data
    dut.uio_in.value = code
    await clock_edge(dut)
    dut.uio_in.value = 0
    await clock_edge(dut)


def loader(dut):
    """The RTL hierarchy. Synthesis flattens imem away, so gate-level has none."""
    try:
        return dut.DUT.imem
    except AttributeError:
        return None


@cocotb.test()
async def test_imem_load(dut):
    """Two words are stored. The last strobe starts a read of word 0.

    uo_out is the check both simulations can see: the low byte of word 0
    once the read comes back. running, wr_addr, and half exist only while
    imem is still a module, which is the RTL run.
    """
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.clk.value = 0
    dut.rst_n.value = 0
    await Timer(1, unit="ns")
    Clock(dut.clk, 10, unit="us").start()

    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)
    imem = loader(dut)
    if imem is not None:
        assert int(imem.running.value) == 0

    # 16'hABCD, then 16'h1234. 10 on the last byte starts execution.
    await byte_strobe(dut, 0b01, 0xCD)
    await byte_strobe(dut, 0b01, 0xAB)
    assert int(dut.uo_out.value) == 0x00
    if imem is not None:
        assert int(imem.running.value) == 0
        assert int(imem.wr_addr.value) == 1

    await byte_strobe(dut, 0b01, 0x34)
    await byte_strobe(dut, 0b10, 0x12)
    if imem is not None:
        assert int(imem.running.value) == 1
        assert int(imem.wr_addr.value) == 2

    # byte_strobe already consumed the write edge and the following edge.
    # The read data is valid on the edge after that.
    await clock_edge(dut)
    if imem is not None:
        assert int(imem.fetch_valid.value) == 1
        assert int(imem.dout.value) == 0xABCD
    assert int(dut.uo_out.value) == 0xCD

    # Holding 01 for several clocks must not store extra bytes. Reset and
    # check a single held strobe leaves the loader waiting for the high byte.
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    dut.ui_in.value = 0x55
    dut.uio_in.value = 0b01
    await clock_edge(dut)
    await clock_edge(dut)
    await clock_edge(dut)
    assert int(dut.uo_out.value) == 0x00
    if imem is not None:
        assert int(imem.half.value) == 1
        assert int(imem.wr_addr.value) == 0

    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.uio_in.value = 0b11
    await clock_edge(dut)
    dut.uio_in.value = 0
    await clock_edge(dut)
    assert int(dut.uo_out.value) == 0x00
    if imem is not None:
        assert int(imem.half.value) == 1
        assert int(imem.wr_addr.value) == 0
        assert int(imem.running.value) == 0
