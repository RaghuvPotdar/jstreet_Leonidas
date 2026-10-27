# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asm"))
from assemble import assemble  # noqa: E402

ASM = Path(__file__).resolve().parents[1] / "asm" / "examples"


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


async def load_program(dut, words):
    for index, word in enumerate(words):
        last = index == len(words) - 1
        await byte_strobe(dut, 0b01, word & 0xFF)
        await byte_strobe(dut, 0b10 if last else 0b01, (word >> 8) & 0xFF)


def loader(dut):
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
    return 0xFF if level else 0xFD


def rf_at(dp, index):
    return int(dp.regs.mem[index].value)


@cocotb.test()
async def test_uart_program(dut):
    """UART, SPI, then I2C on the compressed ISA (R0-R7, PSET, OUT, …)."""
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

    await byte_strobe(dut, 0b01, 0xCD)
    await byte_strobe(dut, 0b01, 0xAB)
    await byte_strobe(dut, 0b01, 0x34)
    await byte_strobe(dut, 0b01, 0x12)
    assert int(dut.uo_out.value) == 0xFF
    if imem is not None:
        assert int(imem.running.value) == 0
        assert int(imem.wr_addr.value) == 2

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

    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    uart = assemble((ASM / "uart.asm").read_text(encoding="utf-8"))
    await load_program(dut, uart)

    expect = [pin_byte(1)] * 4
    expect += [pin_byte(0)] * 16
    for bit in (1, 0, 0, 0, 1, 1, 0, 1):
        expect += [pin_byte(bit)] * 16
    expect += [pin_byte(1)] * 16

    got = [int(dut.uo_out.value)]
    for _ in range(len(expect) - 1):
        await clock_edge(dut)
        got.append(int(dut.uo_out.value))
    assert got == expect, f"UART pin mismatch\n got {got}\n exp {expect}"

    for _ in range(4):
        await clock_edge(dut)
        assert int(dut.uo_out.value) == 0xFF

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0
        assert rf_at(dp, 1) == 0

    # SPI: LDI R0 with bit-reversed 0xB1; OUT is LSB-first.
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    spi = assemble((ASM / "spi.asm").read_text(encoding="utf-8"))
    await load_program(dut, spi)

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
    assert cs_low[-1] - cs_low[0] + 1 == len(cs_low), "CS rose mid-frame"
    assert cs_low[-1] < len(samples) - 1, "CS still low at end"

    frame = samples[cs_low[0] : cs_low[-1] + 1]
    assert bit(frame[0], 3) == 0, "SCK high when CS fell"

    bits = []
    for prev, cur in zip(frame, frame[1:]):
        mosi = bit(cur, 4)
        if bit(prev, 3) == 0 and bit(cur, 3) == 1:
            assert bit(prev, 4) == mosi, "MOSI changed on SCK rise"
            bits.append(mosi)
        if bit(cur, 3) == 1:
            assert mosi == bits[-1], "MOSI changed while SCK high"
    assert bits == [1, 0, 1, 1, 0, 0, 0, 1], f"MOSI bits {bits}"

    after = samples[cs_low[-1] + 1]
    assert bit(after, 2) == 1 and bit(after, 3) == 0

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0
        assert rf_at(dp, 1) == 0

    # I2C master write: PSET/REL/JL on uio[2]/uio[3].
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    sda_pin, scl_pin = 10, 11

    def enc(opcode, field, payload):
        word = (opcode << 12) | ((field & 0xF) << 8) | (payload & 0xFF)
        return word & 0xFF, (word >> 8) & 0xFF

    def pset_payload(level, dur):
        coded = 0 if dur == 128 else dur
        return ((level & 1) << 7) | (coded & 0x7F)

    def build_i2c(ops):
        labels = {}
        address = 0
        for op in ops:
            if op[0] == "label":
                labels[op[1]] = address
            else:
                address += 1
        program = []
        for op in ops:
            kind = op[0]
            if kind == "label":
                continue
            if kind == "pset":
                program.append(enc(0x1, op[1], pset_payload(op[2], op[3])))
            elif kind == "rel":
                program.append(enc(0x5, op[1], op[2]))
            elif kind == "jl":
                program.append(enc(0x6, op[1], labels[op[2]]))
            else:
                program.append(enc(0x4, 0, 0))
        return program

    def add_byte(ops, value, ok_label):
        for shift in range(7, -1, -1):
            b = (value >> shift) & 1
            if b:
                ops.append(("rel", sda_pin, 4))
            else:
                ops.append(("pset", sda_pin, 0, 4))
            ops.append(("rel", scl_pin, 8))
            ops.append(("pset", scl_pin, 0, 8))
        ops.append(("rel", sda_pin, 4))
        ops.append(("label", f"stretch_{ok_label}"))
        ops.append(("rel", scl_pin, 1))
        ops.append(("jl", scl_pin, f"stretch_{ok_label}"))
        ops.append(("jl", sda_pin, ok_label))
        ops.append(("pset", scl_pin, 0, 4))
        ops.append(("pset", sda_pin, 0, 4))
        ops.append(("rel", scl_pin, 8))
        ops.append(("rel", sda_pin, 4))
        ops.append(("halt",))

    listing = [("pset", sda_pin, 0, 8), ("pset", scl_pin, 0, 8)]
    add_byte(listing, 0xA0, "data")
    listing.append(("label", "data"))
    listing.append(("pset", scl_pin, 0, 8))
    add_byte(listing, 0xB1, "stop")
    listing.append(("label", "stop"))
    listing.append(("pset", scl_pin, 0, 8))
    listing.append(("pset", sda_pin, 0, 4))
    listing.append(("rel", scl_pin, 8))
    listing.append(("rel", sda_pin, 4))
    listing.append(("halt",))

    i2c_bytes = build_i2c(listing)
    i2c_words = [low | (high << 8) for low, high in i2c_bytes]
    await load_program(dut, i2c_words)

    dut.uio_in.value = 0b1100

    bits = []
    byte_bits = 0
    prev_sda, prev_scl = 1, 1
    saw_start = False
    saw_stop = False
    ack_phase = False
    bytes_done = 0
    stretch_left = 0
    stretched = 0
    for _ in range(4000):
        oe = int(dut.uio_oe.value)
        out = int(dut.uio_out.value)
        ina = int(dut.uio_in.value)
        oe_sda, oe_scl = (oe >> 2) & 1, (oe >> 3) & 1
        out_sda, out_scl = (out >> 2) & 1, (out >> 3) & 1
        in_sda, in_scl = (ina >> 2) & 1, (ina >> 3) & 1
        sda = out_sda if oe_sda else in_sda
        scl = out_scl if oe_scl else in_scl

        if prev_scl == 1 and prev_sda == 1 and scl == 1 and sda == 0:
            saw_start = True
        if saw_start and prev_scl == 1 and scl == 1 and prev_sda == 0 and sda == 1:
            saw_stop = True
        if (
            prev_scl == 0
            and scl == 1
            and saw_start
            and not saw_stop
            and not ack_phase
            and bytes_done < 2
        ):
            if byte_bits < 8:
                bits.append(sda)
                byte_bits += 1
                if byte_bits == 8 and bytes_done == 0:
                    stretch_left = 250
            elif oe_sda == 0:
                ack_phase = True
        if ack_phase and prev_scl == 1 and scl == 0:
            ack_phase = False
            byte_bits = 0
            bytes_done += 1
        if byte_bits == 8 and bytes_done == 0 and oe_scl == 0 and scl == 0:
            stretched += 1

        prev_sda, prev_scl = sda, scl
        drive_sda = 0 if ack_phase or byte_bits == 8 else 1
        drive_scl = 0 if stretch_left else 1
        if stretch_left:
            stretch_left -= 1
        dut.uio_in.value = (drive_sda << 2) | (drive_scl << 3)
        await clock_edge(dut)
        if saw_stop and bytes_done >= 2:
            break

    for _ in range(30):
        await clock_edge(dut)

    assert saw_start, "no START"
    assert bits == [1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1], f"I2C bits {bits}"
    assert stretched >= 5, f"SCL not stretched ({stretched})"
    assert saw_stop and bytes_done == 2, f"stop={saw_stop} acks={bytes_done}"

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1


# USB D+/D- on uo_out[5]/[6] (see info.yaml / usb_*_ack.asm).
USB_DP = 5
USB_DM = 6


def usb_pair(uo):
    return ((int(uo) >> USB_DP) & 1, (int(uo) >> USB_DM) & 1)


def usb_runs(samples):
    """Collapse consecutive identical (dp, dm) samples into (state, clocks)."""
    runs = []
    for state in samples:
        if runs and runs[-1][0] == state:
            runs[-1] = (state, runs[-1][1] + 1)
        else:
            runs.append((state, 1))
    return runs


def usb_ack_bit_states(j, k, se0):
    # establish J, SYNC KJKJKJKK, PID ACK JJKJJKKK, EOP SE0, idle J
    return (
        [j]
        + [k, j, k, j, k, j, k, k]
        + [j, j, k, j, j, k, k, k]
        + [se0, j]
    )


def usb_ack_expect_runs(j, k, se0, bit_time, se0_time):
    """Merge consecutive identical line states (PSETH KK → one 2× hold)."""
    raw = []
    for state in usb_ack_bit_states(j, k, se0):
        dur = se0_time if state == se0 else bit_time
        if raw and raw[-1][0] == state:
            raw[-1] = (state, raw[-1][1] + dur)
        else:
            raw.append((state, dur))
    return raw


async def run_usb_ack(dut, asm_name, bit_time, se0_time, j, k, se0):
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

    words = assemble((ASM / asm_name).read_text(encoding="utf-8"))
    await load_program(dut, words)

    # Enough room for two LDIs, the packet, and sticky idle after HALT.
    n = 2 * bit_time + 18 * bit_time + se0_time + bit_time + 64
    samples = [usb_pair(dut.uo_out.value)]
    for _ in range(n - 1):
        await clock_edge(dut)
        samples.append(usb_pair(dut.uo_out.value))

    # Drop leading SE1 / undriven idle (both high after reset).
    while samples and samples[0] == (1, 1):
        samples.pop(0)
    assert samples, "USB never left idle SE1"

    runs = usb_runs(samples)
    expect = usb_ack_expect_runs(j, k, se0, bit_time, se0_time)
    assert len(runs) >= len(expect), (
        f"{asm_name} too few runs\n got {runs}\n exp {expect}"
    )

    for i, ((got_s, got_n), (exp_s, exp_n)) in enumerate(
        zip(runs[: len(expect)], expect)
    ):
        assert got_s == exp_s, (
            f"{asm_name} state[{i}] {got_s}, want {exp_s}\n runs {runs}"
        )
        # Final idle J merges with post-HALT sticky drive → only a floor.
        if i == len(expect) - 1:
            assert got_n >= exp_n, (
                f"{asm_name} idle J held {got_n}, want >= {exp_n}"
            )
        else:
            assert got_n == exp_n, (
                f"{asm_name} state[{i}] {got_s} held {got_n}, want {exp_n} "
                f"(stretch or early cut)"
            )

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 4) == bit_time
        assert rf_at(dp, 5) == se0_time


@cocotb.test()
async def test_usb_ls_ack(dut):
    """USB Low-Speed ACK: PSETH J/K/SE0 at 40 / 80 clocks (60 MHz → 1.5 Mbit/s)."""
    # LS: J=D- high, K=D+ high
    await run_usb_ack(
        dut,
        "usb_ls_ack.asm",
        bit_time=40,
        se0_time=80,
        j=(0, 1),
        k=(1, 0),
        se0=(0, 0),
    )


@cocotb.test()
async def test_usb_fs_ack(dut):
    """USB Full-Speed ACK: same packet, flipped J/K, 5 / 10 clocks (60 MHz → 12 Mbit/s)."""
    # FS: J=D+ high, K=D- high
    await run_usb_ack(
        dut,
        "usb_fs_ack.asm",
        bit_time=5,
        se0_time=10,
        j=(1, 0),
        k=(0, 1),
        se0=(0, 0),
    )
