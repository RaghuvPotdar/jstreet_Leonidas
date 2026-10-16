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
    """Load the UART listing, then the SPI listing.

    UART sends 0b10110001 LSB first on uo_out[1], 16 clocks per level.
    SPI then sends 0xB1 MSB first, mode 0, on CS, SCK, and MOSI.
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
        (0x10, 0x41),  # OUT_L pin 1 for 16
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

    # SPI mode 0, one byte, MSB first. Pins stay where an instruction left
    # them, so a hold is the wait before the next pin write, not the width
    # of the level. SCK is driven low before CS falls because uo_out idles
    # high. The byte in LDI is the byte on MOSI: OUT_M emits bit 7 first.
    #
    #   pin 2  CS    active low
    #   pin 3  SCK   idle low, high for 8, low for 8
    #   pin 4  MOSI  OUT_M for 4 clocks of setup
    #
    # 0  LDI   0xB1
    # 1  LOW   SCK  for 1
    # 2  LOW   CS   for 1
    # 3  SETX  8
    # 4  OUT_M MOSI for 4
    # 5  HIGH  SCK  for 8
    # 6  LOW   SCK  for 8
    # 7  DJNZ  4
    # 8  HIGH  CS   for 1
    # 9  HALT
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    spi = [
        (0xB1, 0x00),  # LDI  0xB1
        (0x01, 0x13),  # LOW  pin 3 for 1
        (0x01, 0x12),  # LOW  pin 2 for 1
        (0x08, 0x30),  # SETX 8
        (0x04, 0x74),  # OUT_M pin 4 for 4
        (0x08, 0x23),  # HIGH pin 3 for 8
        (0x08, 0x13),  # LOW  pin 3 for 8
        (0x04, 0x50),  # DJNZ address 4
        (0x01, 0x22),  # HIGH pin 2 for 1
        (0x00, 0x60),  # HALT
    ]
    for index, (low, high) in enumerate(spi):
        last = index == len(spi) - 1
        await byte_strobe(dut, 0b01, low)
        await byte_strobe(dut, 0b10 if last else 0b01, high)

    samples = [int(dut.uo_out.value)]
    for _ in range(499):
        await clock_edge(dut)
        samples.append(int(dut.uo_out.value))

    for sample in samples:
        assert sample & 0b11100011 == 0b11100011, f"unexpected pin {sample:#04x}"

    def bit(sample, index):
        return (sample >> index) & 1

    cs_low = [i for i, sample in enumerate(samples) if bit(sample, 2) == 0]
    assert cs_low, "CS never fell"
    assert cs_low[-1] - cs_low[0] + 1 == len(cs_low), "CS rose in the middle of the frame"
    assert cs_low[-1] < len(samples) - 1, "CS was still low at the end of the trace"

    frame = samples[cs_low[0]:cs_low[-1] + 1]
    assert bit(frame[0], 3) == 0, "SCK was high when CS fell"

    bits = []
    for prev, cur in zip(frame, frame[1:]):
        mosi = bit(cur, 4)
        if bit(prev, 3) == 0 and bit(cur, 3) == 1:
            assert bit(prev, 4) == mosi, "MOSI changed on the SCK rising edge"
            bits.append(mosi)
        if bit(cur, 3) == 1:
            assert mosi == bits[-1], "MOSI changed while SCK was high"
    assert bits == [1, 0, 1, 1, 0, 0, 0, 1], f"MOSI bits {bits}"

    after = samples[cs_low[-1] + 1]
    assert bit(after, 2) == 1 and bit(after, 3) == 0, "SCK was not low after CS rose"

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert int(dp.xreg.value) == 0
        assert int(dp.shifter.value) == 0
