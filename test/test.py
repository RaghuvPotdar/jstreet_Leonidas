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


def engine(dut):
    try:
        return dut.DUT.datapath
    except AttributeError:
        return None


def pin_byte(level):
    """uo_out when only bit 1 carries the UART level. Every pin idles at 1."""
    return 0xFF if level else 0xFD


@cocotb.test()
async def test_uart_program(dut):
    """Load the UART listing and check uo_out[1].

    The byte is 0b10110001, LSB first, 16 clocks per level: idle high, start
    low, eight data bits, stop high, then HALT holds the stop level.
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

    # Two words, no start strobe. Pins stay idle and nothing is fetched.
    await byte_strobe(dut, 0b01, 0xCD)
    await byte_strobe(dut, 0b01, 0xAB)
    await byte_strobe(dut, 0b01, 0x34)
    await byte_strobe(dut, 0b01, 0x12)
    assert int(dut.uo_out.value) == 0xFF
    if imem is not None:
        assert int(imem.running.value) == 0
        assert int(imem.wr_addr.value) == 2

    # A held 01 stores one byte. 11 stores nothing.
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
    assert int(dut.uo_out.value) == 0xFF
    if imem is not None:
        assert int(imem.half.value) == 1
        assert int(imem.wr_addr.value) == 0

    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.uio_in.value = 0b11
    await clock_edge(dut)
    dut.uio_in.value = 0
    await clock_edge(dut)
    assert int(dut.uo_out.value) == 0xFF
    if imem is not None:
        assert int(imem.half.value) == 1
        assert int(imem.running.value) == 0

    # Reset again and load the real program. Low byte, then high byte.
    # 10 belongs on the high byte of HALT.
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    program = [
        (0xB1, 0x00),  # LDI  10110001
        (0x10, 0x11),  # LOW  pin 1 for 16
        (0x08, 0x30),  # SETX 8
        (0x10, 0x41),  # OUT  pin 1 for 16
        (0x03, 0x50),  # DJNZ address 3
        (0x10, 0x21),  # HIGH pin 1 for 16
        (0x00, 0x60),  # HALT
    ]
    for index, (low, high) in enumerate(program):
        last = index == len(program) - 1
        await byte_strobe(dut, 0b01, low)
        await byte_strobe(dut, 0b10 if last else 0b01, high)

    # After the strobe returns, four clocks are still idle: the read of
    # address 0, LDI, and the two clocks the SRAM needs before LOW drives
    # the pin. Then 16 clocks per level. 10110001 leaves LSB first.
    expect = [pin_byte(1)] * 4
    expect += [pin_byte(0)] * 16
    for bit in (1, 0, 0, 0, 1, 1, 0, 1):
        expect += [pin_byte(bit)] * 16
    expect += [pin_byte(1)] * 16

    got = [int(dut.uo_out.value)]
    for _ in range(len(expect) - 1):
        await clock_edge(dut)
        got.append(int(dut.uo_out.value))
    assert got == expect, f"pin mismatch\n got {got}\n exp {expect}"

    for _ in range(4):
        await clock_edge(dut)
        assert int(dut.uo_out.value) == 0xFF

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert int(dp.xreg.value) == 0
        assert int(dp.shifter.value) == 0
