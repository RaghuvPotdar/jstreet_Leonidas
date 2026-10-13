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


@cocotb.test()
async def test_imem_load(dut):
    """Two words are stored. The last strobe starts a read of word 0."""
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
    assert int(dut.DUT.imem.running.value) == 0

    # 16'hABCD, then 16'h1234. 10 on the last byte starts execution.
    await byte_strobe(dut, 0b01, 0xCD)
    await byte_strobe(dut, 0b01, 0xAB)
    assert int(dut.DUT.imem.running.value) == 0
    assert int(dut.DUT.imem.wr_addr.value) == 1

    await byte_strobe(dut, 0b01, 0x34)
    await byte_strobe(dut, 0b10, 0x12)
    assert int(dut.DUT.imem.running.value) == 1
    assert int(dut.DUT.imem.wr_addr.value) == 2

    # byte_strobe already consumed the write edge and the following edge.
    # The read data is valid on the edge after that.
    await clock_edge(dut)
    assert int(dut.DUT.imem.fetch_valid.value) == 1
    assert int(dut.DUT.imem.dout.value) == 0xABCD
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
    assert int(dut.DUT.imem.half.value) == 1
    assert int(dut.DUT.imem.wr_addr.value) == 0

    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.uio_in.value = 0b11
    await clock_edge(dut)
    dut.uio_in.value = 0
    await clock_edge(dut)
    assert int(dut.DUT.imem.half.value) == 1
    assert int(dut.DUT.imem.wr_addr.value) == 0
    assert int(dut.DUT.imem.running.value) == 0
