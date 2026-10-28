# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asm"))
from assemble import assemble  # noqa: E402
from eth_tx import ETH_BIT, ETH_TX, WIRE, expect_runs, lsb_bits, recover_bits  # noqa: E402
from usb_tx import DUMMY_PACKETS, USB_DM, USB_DP, build_dummy_tx  # noqa: E402

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


def payload(dut):
    try:
        return dut.DUT.dmem
    except AttributeError:
        return None


async def load_dmem(dut, data):
    for byte in data:
        await byte_strobe(dut, 0b11, byte)


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
    mem = payload(dut)
    if mem is not None:
        assert int(mem.wptr.value) == 1
        assert int(mem.sram.mem[0].value) == 0x55

    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    uart = assemble((ASM / "uart.asm").read_text(encoding="utf-8"))
    await load_program(dut, uart)

    expect = [pin_byte(0)] * 16
    for bit in (1, 0, 0, 0, 1, 1, 0, 1):
        expect += [pin_byte(bit)] * 16
    expect += [pin_byte(1)] * 16

    got = [int(dut.uo_out.value)]
    for _ in range(4 + len(expect) + 16):
        await clock_edge(dut)
        got.append(int(dut.uo_out.value))
    while got and got[0] == pin_byte(1):
        got.pop(0)
    got = got[: len(expect)]
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

    # R1=SDA pin10, R2=SCL pin11, R3=4, R4=8, R5=1
    lines = [
        "LDI R1, 0xAA",
        "LDI R2, 0xBB",
        "LDI R3, 4",
        "LDI R4, 8",
        "LDI R5, 1",
        "PSET R1, 0, R4",
        "PSET R2, 0, R4",
    ]

    def add_byte(value, ok):
        for shift in range(7, -1, -1):
            if (value >> shift) & 1:
                lines.append("REL R1, R3")
            else:
                lines.append("PSET R1, 0, R3")
            lines.append("REL R2, R4")
            lines.append("PSET R2, 0, R4")
        lines.append("REL R1, R3")
        lines.append(f"stretch_{ok}:")
        lines.append("REL R2, R5")
        lines.append(f"JL R2, stretch_{ok}")
        lines.append(f"JL R1, {ok}")
        lines.append("PSET R2, 0, R3")
        lines.append("PSET R1, 0, R3")
        lines.append("REL R2, R4")
        lines.append("REL R1, R3")
        lines.append("HALT")

    add_byte(0xA0, "data")
    lines.append("data:")
    lines.append("PSET R2, 0, R4")
    add_byte(0xB1, "stop")
    lines.append("stop:")
    lines.append("PSET R2, 0, R4")
    lines.append("PSET R1, 0, R3")
    lines.append("REL R2, R4")
    lines.append("REL R1, R3")
    lines.append("HALT")

    await load_program(dut, assemble("\n".join(lines)))

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


def usb_dp_dm(uo):
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


async def reset_dut(dut):
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


async def run_usb_words(dut, label, words, expect, bit_time, se0_time):
    await load_program(dut, words)

    total_bits = sum(n for _, n in expect)
    n = total_bits + 64
    samples = [usb_dp_dm(dut.uo_out.value)]
    for _ in range(n - 1):
        await clock_edge(dut)
        samples.append(usb_dp_dm(dut.uo_out.value))

    while samples and samples[0] == (1, 1):
        samples.pop(0)
    assert samples, f"{label}: USB never left idle SE1"

    runs = usb_runs(samples)
    assert len(runs) >= len(expect), (
        f"{label}: too few runs\n got {runs}\n exp {expect}"
    )

    for i, ((got_s, got_n), (exp_s, exp_n)) in enumerate(
        zip(runs[: len(expect)], expect)
    ):
        assert got_s == exp_s, (
            f"{label}: state[{i}] {got_s}, want {exp_s}\n runs {runs}"
        )
        if i == len(expect) - 1:
            assert got_n >= exp_n, (
                f"{label}: idle J held {got_n}, want >= {exp_n}"
            )
        else:
            assert got_n == exp_n, (
                f"{label}: state[{i}] {got_s} held {got_n}, want {exp_n}"
            )

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0


@cocotb.test()
async def test_usb_ls_ack(dut):
    """Hand asm: USB LS ACK handshake on D+/D-."""
    await reset_dut(dut)
    words = assemble((ASM / "usb_ls_ack.asm").read_text(encoding="utf-8"))
    _, expect, bit_time, se0_time = build_dummy_tx("ack", fs=False)
    await run_usb_words(dut, "usb_ls_ack.asm", words, expect, bit_time, se0_time)


@cocotb.test()
async def test_usb_fs_ack(dut):
    """Hand asm: USB FS ACK handshake on D+/D-."""
    await reset_dut(dut)
    words = assemble((ASM / "usb_fs_ack.asm").read_text(encoding="utf-8"))
    _, expect, bit_time, se0_time = build_dummy_tx("ack", fs=True)
    await run_usb_words(dut, "usb_fs_ack.asm", words, expect, bit_time, se0_time)


@cocotb.test()
async def test_usb_dummy_packets(dut):
    """Dummy TOKEN/DATA/handshake/SOF packets, LS and FS (fake CRC, no stuffing)."""
    await reset_dut(dut)
    for fs in (False, True):
        speed = "fs" if fs else "ls"
        for name in DUMMY_PACKETS:
            dut.rst_n.value = 0
            dut.uio_in.value = 0
            await clock_edge(dut)
            dut.rst_n.value = 1
            await clock_edge(dut)

            words, expect, bit_time, se0_time = build_dummy_tx(name, fs=fs)
            await run_usb_words(
                dut, f"{speed}/{name}", words, expect, bit_time, se0_time
            )


@cocotb.test()
async def test_ldi_then_out(dut):
    """LDI R0 immediately before OUT must be visible (1-cycle write/read)."""
    from assemble import OP_HALT, OP_LDI, encode, encode_out, encode_pset, reg_field

    await reset_dut(dut)
    words = [
        encode(OP_LDI, reg_field(2), 0x11),
        encode(OP_LDI, reg_field(3), 4),
        encode(OP_LDI, reg_field(4), 8),
        encode_pset(2, 0, 3),
        encode(OP_LDI, reg_field(0), 0x01),
        encode_out(2, 0, 4),
        encode(OP_HALT, 0, 0),
    ]
    await load_program(dut, words)

    samples = [int(dut.uo_out.value)]
    for _ in range(32):
        await clock_edge(dut)
        samples.append(int(dut.uo_out.value))

    bits = [((s >> 1) & 1) for s in samples]
    # idle 1, PSET 0 for 4, then OUT of R0[0]=1 for 8, sticky 1
    while bits and bits[0] == 1:
        bits.pop(0)
    assert bits, "pin 1 never left idle high"
    lows = 0
    while bits and bits[0] == 0:
        lows += 1
        bits.pop(0)
    assert lows >= 4, f"PSET low held {lows}, want >= 4"
    highs = 0
    while bits and bits[0] == 1:
        highs += 1
        bits.pop(0)
    assert highs >= 8, f"OUT high from LDI R0=1 held {highs}, want >= 8"
    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0


@cocotb.test()
async def test_dmem_ld(dut):
    """Strobe 11 fills dmem; LD Rn, [Rm] reads it and post-increments Rm."""
    from assemble import OP_HALT, OP_LDI, encode, encode_ld, encode_out, reg_field

    await reset_dut(dut)
    await load_dmem(dut, [0x5A, 0x3C])
    mem = payload(dut)
    if mem is not None:
        assert int(mem.wptr.value) == 2
        assert int(mem.sram.mem[0].value) == 0x5A
        assert int(mem.sram.mem[1].value) == 0x3C

    words = [
        encode(OP_LDI, reg_field(2), 0x11),
        encode(OP_LDI, reg_field(3), 8),
        encode(OP_LDI, reg_field(5), 0),
        encode_ld(0, 5),
        encode_out(2, 0, 3),
        encode_ld(1, 5),
        encode(OP_HALT, 0, 0),
    ]
    await load_program(dut, words)

    samples = [int(dut.uo_out.value)]
    for _ in range(64):
        await clock_edge(dut)
        samples.append(int(dut.uo_out.value))

    bits = [((s >> 1) & 1) for s in samples]
    while bits and bits[0] == 1:
        bits.pop(0)
    assert bits, "pin 1 never left idle high"
    lows = 0
    while bits and bits[0] == 0:
        lows += 1
        bits.pop(0)
    # 0x5A LSB is 0; OUT holds it for 8, then sticky
    assert lows >= 8, f"OUT from dmem[0]=0x5A held {lows}, want >= 8"

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0x2D
        assert rf_at(dp, 1) == 0x3C
        assert rf_at(dp, 5) == 2


@cocotb.test()
async def test_outm_mid_invert(dut):
    """OUTM IEEE: Rs[0]=1 → 3 clocks low then 3 high; two-pin stays complementary."""
    from assemble import OP_HALT, OP_LDI, encode, encode_out, pin_desc, reg_field

    await reset_dut(dut)
    words = [
        encode(OP_LDI, reg_field(2), pin_desc(1)),
        encode(OP_LDI, reg_field(3), 6),
        encode(OP_LDI, reg_field(0), 0x01),
        encode_out(2, 0, 3, invert=True),
        encode(OP_HALT, 0, 0),
    ]
    await load_program(dut, words)

    bits = []
    for _ in range(24):
        bits.append((int(dut.uo_out.value) >> 1) & 1)
        await clock_edge(dut)

    while bits and bits[0] == 1:
        bits.pop(0)
    assert bits, "pin 1 never left idle high"
    lows = 0
    while bits and bits[0] == 0:
        lows += 1
        bits.pop(0)
    assert lows == 3, f"OUTM first half held {lows}, want 3"
    highs = 0
    while bits and bits[0] == 1:
        highs += 1
        bits.pop(0)
    assert highs >= 3, f"OUTM second half held {highs}, want >= 3"

    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    words = [
        encode(OP_LDI, reg_field(2), pin_desc(USB_DP, USB_DM)),
        encode(OP_LDI, reg_field(3), 6),
        encode(OP_LDI, reg_field(0), 0x01),
        encode_out(2, 0, 3, invert=True),
        encode(OP_HALT, 0, 0),
    ]
    await load_program(dut, words)

    samples = []
    for _ in range(24):
        samples.append(usb_dp_dm(dut.uo_out.value))
        await clock_edge(dut)

    while samples and samples[0] == (1, 1):
        samples.pop(0)
    assert samples, "USB pair never left idle SE1"
    first = []
    while samples and samples[0] == (0, 1):
        first.append(samples.pop(0))
    second = []
    while samples and samples[0] == (1, 0):
        second.append(samples.pop(0))
    assert len(first) == 3, f"OUTM pair first half {len(first)}, want 3"
    assert len(second) >= 3, f"OUTM pair second half {len(second)}, want >= 3"
    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0


def eth_tx(uo):
    return (int(uo) >> ETH_TX) & 1


@cocotb.test()
async def test_eth_10t(dut):
    """Hand asm: 10BASE-T TX, IEEE Manchester on one pin."""
    await reset_dut(dut)
    words = assemble((ASM / "eth_10t.asm").read_text(encoding="utf-8"))
    expect = expect_runs(WIRE)

    await load_program(dut, words)
    total = sum(n for _, n in expect) + 64
    samples = [eth_tx(dut.uo_out.value)]
    for _ in range(total - 1):
        await clock_edge(dut)
        samples.append(eth_tx(dut.uo_out.value))

    while samples and samples[0] == 1:
        samples.pop(0)
    assert samples, "10BASE-T never left idle"

    runs = usb_runs(samples)
    assert len(runs) >= len(expect), (
        f"eth_10t: too few runs\n got {runs}\n exp {expect}"
    )
    for i, ((got_s, got_n), (exp_s, exp_n)) in enumerate(
        zip(runs[: len(expect)], expect)
    ):
        assert got_s == exp_s, (
            f"eth_10t: state[{i}] {got_s}, want {exp_s}\n runs {runs}"
        )
        if i == len(expect) - 1:
            assert got_n >= exp_n, (
                f"eth_10t: last held {got_n}, want >= {exp_n}"
            )
        else:
            assert got_n == exp_n, (
                f"eth_10t: state[{i}] {got_s} held {got_n}, want {exp_n}"
            )

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0


@cocotb.test()
async def test_eth_10t_loop(dut):
    """Same runt frame as eth_10t, but OUTM+DJNZ with payload in dmem."""
    await reset_dut(dut)
    await load_dmem(dut, list(WIRE))
    words = assemble((ASM / "eth_10t_loop.asm").read_text(encoding="utf-8"))
    await load_program(dut, words)

    nbits = len(WIRE) * 8
    samples = [eth_tx(dut.uo_out.value)]
    for _ in range(nbits * ETH_BIT + nbits * 4 + 64):
        await clock_edge(dut)
        samples.append(eth_tx(dut.uo_out.value))

    while samples and samples[0] == 1:
        samples.pop(0)
    assert samples, "10BASE-T loop never left idle"
    got = recover_bits(samples)
    want = lsb_bits(WIRE)
    assert got[: len(want)] == want, (
        f"eth_10t_loop bits\n got {got[: len(want)]}\n exp {want}"
    )
    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 5) == len(WIRE)
        assert rf_at(dp, 4) == 0
