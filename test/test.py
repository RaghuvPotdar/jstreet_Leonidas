# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import functools
import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asm"))
from assemble import assemble  # noqa: E402
from eth_tx import ETH_TX, WIRE, expect_runs  # noqa: E402
from usb_tx import DUMMY_PACKETS, USB_DM, USB_DP, build_dummy_tx  # noqa: E402

ASM = Path(__file__).resolve().parents[1] / "asm" / "examples"
GOLDEN = Path(__file__).resolve().parent / "golden"
GL = os.environ.get("GATES") == "yes"


def _hex(sig):
    v = sig.value
    return format(int(v), "02x") if v.is_resolvable else str(v)


def golden(func):
    """Record pins (and pc/halted in RTL) every clock; diff against test/golden.

    Row i is the state at RisingEdge+ReadOnly of the test's i-th clock edge.
    GOLDEN_WRITE=1 rewrites the file and then fails the test (a write is never a pass).
    """
    @functools.wraps(func)
    async def wrapper(dut, **kwargs):
        name = func.__name__ + "".join(f"_{k}={v}" for k, v in sorted(kwargs.items()))
        rows = []

        async def record():
            while True:
                await RisingEdge(dut.clk)
                await ReadOnly()
                row = [_hex(s) for s in (dut.uo_out, dut.uio_out, dut.uio_oe, dut.ui_in, dut.uio_in)]
                dp = engine(dut)
                if dp is not None:
                    row += [_hex(dp.pc), str(dp.halted.value)]
                rows.append(" ".join(row))

        task = cocotb.start_soon(record())
        await func(dut, **kwargs)
        task.cancel()
        path = GOLDEN / f"{name}.txt"
        if os.environ.get("GOLDEN_WRITE"):
            GOLDEN.mkdir(exist_ok=True)
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            raise AssertionError(f"golden {name} written; rerun without GOLDEN_WRITE to check")
        want = path.read_text(encoding="utf-8").splitlines()
        width = 5 if GL else 7
        got = [" ".join(r.split()[:width]) for r in rows]
        want = [" ".join(r.split()[:width]) for r in want]
        for i, (g, w) in enumerate(zip(got, want)):
            assert g == w, f"golden {name}: cycle {i} got '{g}' want '{w}'"
        assert len(got) == len(want), f"golden {name}: {len(got)} cycles, want {len(want)}"

    return wrapper


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


async def bus_settle(dut):
    """The host bus is synchronized in leonidas.sv: a byte lands 3 clocks after its strobe."""
    for _ in range(3):
        await clock_edge(dut)


async def load_dmem(dut, data):
    for byte in data:
        await byte_strobe(dut, 0b11, byte)


def pin_byte(level):
    return 0xFF if level else 0xFD


def rf_at(dp, index):
    return int(dp.regs.mem[index].value)


@cocotb.test()
@golden
async def test_uart_program(dut):
    """UART and SPI on the compressed ISA (R0-R7, PSET, OUT, …)."""
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
    await bus_settle(dut)
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
    await bus_settle(dut)
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
    await bus_settle(dut)
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
    for _ in range(799):
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

    sck = [bit(s, 3) for s in frame]
    sck_runs = usb_runs(sck)
    # Idle-low setup, then 8 highs. Interior lows are HALF; MOSI OUT is
    # subtracted from the low PSET so visible high == visible low == 8.
    highs = [n for level, n in sck_runs if level == 1]
    lows = [n for level, n in sck_runs if level == 0]
    assert highs == [8] * 8, f"SCK high runs {highs}, want eight 8s"
    assert len(lows) >= 8, f"SCK low runs {lows}"
    assert lows[1:8] == [8] * 7, f"SCK interior lows {lows[1:8]}, want seven 8s"

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


@cocotb.test()
@cocotb.parametrize(ack_address=[True, False])
@golden
async def test_i2c_write(dut, ack_address):
    """A target stretches SCL and either accepts or rejects the address."""
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    await Timer(1, unit="ns")
    Clock(dut.clk, 10, unit="us").start()
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)

    await load_program(dut, assemble((ASM / "i2c_write.asm").read_text()))

    dut.uio_in.value = 0b1100

    expected_bytes = [0xA0, 0xB1] if ack_address else [0xA0]
    bits = []
    byte_bits = 0
    prev_sda, prev_scl = 1, 1
    saw_start = False
    saw_stop = False
    ack_phase = False
    sampled_bit = None
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
                sampled_bit = sda
            elif oe_sda == 0:
                ack_phase = True
        if prev_scl == 1 and scl == 0:
            if ack_phase:
                ack_phase = False
                byte_bits = 0
                bytes_done += 1
            elif sampled_bit is not None:
                # Commit a bit only when its clock pulse finishes. A STOP
                # raises SCL with SDA held low, then releases SDA while high.
                bits.append(sampled_bit)
                sampled_bit = None
                byte_bits += 1
                if byte_bits == 8 and bytes_done == 0:
                    stretch_left = 250
        if byte_bits == 8 and bytes_done == 0 and oe_scl == 0 and scl == 0:
            stretched += 1

        prev_sda, prev_scl = sda, scl
        drive_sda = 0 if ack_address and (ack_phase or byte_bits == 8) else 1
        drive_scl = 0 if stretch_left else 1
        if stretch_left:
            stretch_left -= 1
        dut.uio_in.value = (drive_sda << 2) | (drive_scl << 3)
        await clock_edge(dut)
        if saw_stop and bytes_done >= len(expected_bytes):
            break

    for _ in range(30):
        await clock_edge(dut)

    assert saw_start, "no START"
    expected_bits = [(byte >> shift) & 1 for byte in expected_bytes for shift in range(7, -1, -1)]
    assert bits == expected_bits, f"I2C bits {bits}"
    assert stretched >= 5, f"SCL not stretched ({stretched})"
    assert saw_stop and bytes_done == len(expected_bytes), f"stop={saw_stop} bytes={bytes_done}"

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


_clock = []


async def reset_dut(dut):
    # One clock driver only: a second Clock on clk corrupts the period.
    while _clock:
        _clock.pop().stop()
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.clk.value = 0
    dut.rst_n.value = 0
    await Timer(1, unit="ns")
    _clock.append(Clock(dut.clk, 10, unit="us"))
    _clock[0].start()
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
@golden
async def test_usb_ls_ack(dut):
    """Hand asm: USB LS ACK handshake on D+/D-."""
    await reset_dut(dut)
    words = assemble((ASM / "usb_ls_ack.asm").read_text(encoding="utf-8"))
    _, expect, bit_time, se0_time = build_dummy_tx("ack", fs=False)
    await run_usb_words(dut, "usb_ls_ack.asm", words, expect, bit_time, se0_time)


@cocotb.test()
@golden
async def test_usb_fs_ack(dut):
    """Hand asm: USB FS ACK handshake on D+/D-."""
    await reset_dut(dut)
    words = assemble((ASM / "usb_fs_ack.asm").read_text(encoding="utf-8"))
    _, expect, bit_time, se0_time = build_dummy_tx("ack", fs=True)
    await run_usb_words(dut, "usb_fs_ack.asm", words, expect, bit_time, se0_time)


@cocotb.test()
@golden
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
@golden
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
@golden
async def test_pset_two_levels(dut):
    """PSET L1/L2: pin0=0, pin1=1 on descriptor 0x10."""
    from assemble import OP_HALT, OP_LDI, encode, encode_pset, reg_field

    await reset_dut(dut)
    words = [
        encode(OP_LDI, reg_field(1), 0x10),
        encode(OP_LDI, reg_field(3), 8),
        encode_pset(1, 0, 3, 1),
        encode(OP_HALT, 0, 0),
    ]
    await load_program(dut, words)
    for _ in range(24):
        await clock_edge(dut)
        if engine(dut) is not None and int(engine(dut).halted.value) == 1:
            break
    uo = int(dut.uo_out.value)
    assert (uo & 1) == 0, f"pin0 want 0, uo={uo:#04x}"
    assert (uo >> 1) & 1 == 1, f"pin1 want 1, uo={uo:#04x}"
    assert (uo & 0xFC) == 0xFC


@cocotb.test()
@golden
async def test_dmem_ld(dut):
    """Strobe 11 fills dmem; LD Rn, [Rm] reads it and post-increments Rm."""
    from assemble import OP_HALT, OP_LDI, encode, encode_ld, encode_out, reg_field

    await reset_dut(dut)
    await load_dmem(dut, [0x5A, 0x3C])
    await bus_settle(dut)
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
@golden
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


def assert_eth_runs(samples, expect, name):
    """Idle-high strip, then exact IEEE run lengths (3 / 6). Last run may stick."""
    while samples and samples[0] == 1:
        samples.pop(0)
    assert samples, f"{name} never left idle"
    runs = usb_runs(samples)
    assert len(runs) >= len(expect), (
        f"{name}: too few runs\n got {runs}\n exp {expect}"
    )
    for i, ((got_s, got_n), (exp_s, exp_n)) in enumerate(
        zip(runs[: len(expect)], expect)
    ):
        assert got_s == exp_s, (
            f"{name}: state[{i}] {got_s}, want {exp_s}\n runs {runs}"
        )
        if i == len(expect) - 1:
            assert got_n >= exp_n, (
                f"{name}: last held {got_n}, want >= {exp_n}"
            )
        else:
            assert got_n == exp_n, (
                f"{name}: state[{i}] {got_s} held {got_n}, want {exp_n}"
            )


@cocotb.test()
@golden
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

    assert_eth_runs(samples, expect, "eth_10t")

    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 0) == 0


@cocotb.test()
@golden
async def test_eth_10t_loop(dut):
    """Same runt frame as eth_10t: first LD in idle, then OUTM+DJNZ bits."""
    await reset_dut(dut)
    await load_dmem(dut, list(WIRE))
    words = assemble((ASM / "eth_10t_loop.asm").read_text(encoding="utf-8"))
    expect = expect_runs(WIRE)
    await load_program(dut, words)

    total = sum(n for _, n in expect) + 64
    samples = [eth_tx(dut.uo_out.value)]
    for _ in range(total - 1):
        await clock_edge(dut)
        samples.append(eth_tx(dut.uo_out.value))

    assert_eth_runs(samples, expect, "eth_10t_loop")
    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1
        assert rf_at(dp, 4) == 0
        # Last OUTM prefetches one byte past the frame into R0 / R5.
        assert rf_at(dp, 5) == len(WIRE) + 1


# ---------------------------------------------------------------- IN / INW

CLK_NS = 10_000  # 10 us clock (matches reset_dut)


async def load_program_idle(dut, words, idle):
    """load_program, but keep `idle` on uio_in[7:2] so RX pins never glitch."""
    for index, word in enumerate(words):
        last = index == len(words) - 1
        for code, data in ((0b01, word & 0xFF),
                           (0b10 if last else 0b01, (word >> 8) & 0xFF)):
            dut.ui_in.value = data
            dut.uio_in.value = idle | code
            await clock_edge(dut)
            dut.uio_in.value = idle
            await clock_edge(dut)


async def uart_send(dut, bit_idx, byte, bit_ns, delay_ns):
    """Drive one 8N1 frame on uio_in[bit_idx], asynchronous to clk."""
    await Timer(delay_ns, unit="ns")
    for level in [0] + [(byte >> i) & 1 for i in range(8)] + [1]:
        dut.uio_in.value = level << bit_idx
        await Timer(bit_ns, unit="ns")


async def uart_recv_uo(dut, pin, bit_clocks, timeout=4000):
    """Decode one 8N1 frame on uo_out[pin]. Checks IN never drives uio."""
    for _ in range(timeout):
        await clock_edge(dut)
        assert int(dut.uio_oe.value) == 0, "IN drove a uio pin"
        if not (int(dut.uo_out.value) >> pin) & 1:
            break
    else:
        raise AssertionError("echo start bit never came")
    for _ in range(bit_clocks // 2):
        await clock_edge(dut)
    assert not (int(dut.uo_out.value) >> pin) & 1, "start bit too short"
    byte = 0
    for i in range(8):
        for _ in range(bit_clocks):
            await clock_edge(dut)
        byte |= ((int(dut.uo_out.value) >> pin) & 1) << i
    for _ in range(bit_clocks):
        await clock_edge(dut)
    assert (int(dut.uo_out.value) >> pin) & 1, "stop bit not high"
    return byte


@cocotb.test()
@golden
async def test_in_uart_echo(dut):
    """IN/INW: UART RX at odd phases and +/-3% baud, echoed back on uo[1]."""
    await reset_dut(dut)
    rx = 2
    idle = 1 << rx
    dut.uio_in.value = idle
    words = assemble((ASM / "uart_rx_echo.asm").read_text(encoding="utf-8"))
    await load_program_idle(dut, words, idle)

    # (byte, baud error, start phase as a fraction of a clock)
    cases = [(0xB1, 0.0, 0.37), (0x5A, +0.03, 0.81), (0x0F, -0.03, 0.12)]
    for byte, err, phase in cases:
        for _ in range(40):
            await clock_edge(dut)
        bit_ns = round(16 * CLK_NS * (1 + err))
        tx = cocotb.start_soon(
            uart_send(dut, rx, byte, bit_ns, round(phase * CLK_NS)))
        got = await uart_recv_uo(dut, 1, 16)
        await tx
        assert got == byte, f"sent {byte:#04x} err {err:+} got {got:#04x}"

    for _ in range(40):
        await clock_edge(dut)
    dp = engine(dut)
    if dp is not None:
        assert int(dp.halted.value) == 1


async def manchester_send(dut, bit_idx, data, half_ns, delay_ns):
    """IEEE 802.3: 1 = low then high, 0 = high then low. LSB first."""
    await Timer(delay_ns, unit="ns")
    for byte in data:
        for i in range(8):
            b = (byte >> i) & 1
            for level in ((0, 1) if b else (1, 0)):
                dut.uio_in.value = level << bit_idx
                await Timer(half_ns, unit="ns")
    dut.uio_in.value = 0


@cocotb.test()
@golden
async def test_inw_manchester_relock(dut):
    """INW re-locks every bit: 64 Manchester bits at 6 clk/bit, +/-3% skew."""
    rx = 6
    # 6x preamble, SFD, then one payload byte the echo must match.
    frame = [0x55] * 6 + [0xD5, 0xA3]
    words = assemble((ASM / "eth_10t_rx_echo.asm").read_text(encoding="utf-8"))
    for err, phase in ((0.0, 0.5), (+0.03, 0.2), (-0.03, 0.9)):
        await reset_dut(dut)
        await load_program_idle(dut, words, 0)
        for _ in range(20):
            await clock_edge(dut)
        half_ns = round(3 * CLK_NS * (1 + err))
        tx = cocotb.start_soon(
            manchester_send(dut, rx, frame, half_ns, round(phase * CLK_NS)))
        got = await uart_recv_uo(dut, 1, 16)
        await tx
        # A missed or extra edge either hangs the 64-bit loop (no echo)
        # or shifts R0 off the payload byte.
        assert got == 0xA3, f"skew {err:+}: got {got:#04x}, want 0xa3"


@cocotb.test()
@golden
async def test_strobe_skew_goes_to_dmem(dut):
    """Pin skew on a 00->11 dmem strobe (one clock of 01) must not write imem."""
    await reset_dut(dut)
    dut.ui_in.value = 0x77
    dut.uio_in.value = 0b01
    await clock_edge(dut)
    dut.uio_in.value = 0b11
    await clock_edge(dut)
    dut.uio_in.value = 0
    await clock_edge(dut)
    await bus_settle(dut)
    imem, mem = loader(dut), payload(dut)
    if imem is not None:
        assert int(imem.half.value) == 0, "skewed dmem strobe was taken as an imem byte"
    if mem is not None:
        assert int(mem.wptr.value) == 1
        assert int(mem.sram.mem[0].value) == 0x77
