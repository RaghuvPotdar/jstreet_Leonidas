# SPDX-License-Identifier: Apache-2.0
"""RX Stage 1 tests (contract v5). All checks are on pins unless noted."""

import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import First, ReadOnly, RisingEdge, Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "asm"))
from assemble import assemble  # noqa: E402

ASM = Path(__file__).resolve().parents[1] / "asm" / "examples"
GL = os.environ.get("GATES") == "yes"
WINDOW = 64  # every absence check


async def clock_edge(dut):
    await RisingEdge(dut.clk)
    await ReadOnly()
    await Timer(1, unit="ns")


def engine(dut):
    try:
        return dut.DUT.datapath
    except AttributeError:
        return None


def rtl(dut):
    """Internal-signal checks are RTL only; they must not pass silently in RTL."""
    dp = engine(dut)
    if not GL:
        assert dp is not None, "datapath not visible in RTL sim"
    return dp


class Pads:
    """Owns uio_in.

    Open-drain pads `od`: chip = oe ? out : 1, bus = chip & target, uio_in = bus.
    Host pads: TB drives `host_val` where `host_oe` is set.
    Other pads read back the chip value while the chip drives them, else 0.
    On every chip output change: no open-drain pad drives high, and no pad
    is driven by the chip and the TB at once.
    """

    def __init__(self, dut, od=0):
        self.dut = dut
        self.od = od
        self.target = 0xFF
        self.host_oe = 0
        self.host_val = 0
        self.apply()
        self.task = cocotb.start_soon(self._watch())

    def bus(self):
        oe, out = self.dut.uio_oe.value, self.dut.uio_out.value
        if not (oe.is_resolvable and out.is_resolvable):
            return self.target
        oe, out = int(oe), int(out)
        return ((out & oe) | (~oe & 0xFF)) & self.target

    def apply(self):
        oe, out = self.dut.uio_oe.value, self.dut.uio_out.value
        if oe.is_resolvable and out.is_resolvable:
            oe, out = int(oe), int(out)
            assert oe & out & self.od == 0, f"open-drain pad driven high oe={oe:#04x} out={out:#04x}"
            assert oe & self.host_oe == 0, f"contention oe={oe:#04x} host_oe={self.host_oe:#04x}"
            loop = out & oe & ~self.host_oe & ~self.od
        else:
            loop = 0
        self.dut.uio_in.value = (self.host_val & self.host_oe) | (self.bus() & self.od) | loop

    async def _watch(self):
        while True:
            await First(self.dut.uio_oe.value_change, self.dut.uio_out.value_change)
            self.apply()

    def drive(self, host_oe=None, host_val=None, target=None):
        if host_oe is not None:
            assert host_oe & self.od == 0, "fixture: host pad marked open-drain"
            self.host_oe = host_oe
        if host_val is not None:
            self.host_val = host_val
        if target is not None:
            self.target = target
        self.apply()

    def stop(self):
        self.task.cancel()


_clock = []


async def reset(dut):
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


async def load(dut, pads, words):
    """Loader on uio[1:0] through the fixture; other host pads keep their values."""
    keep, oe0 = pads.host_val, pads.host_oe & 3
    for index, word in enumerate(words):
        last = index == len(words) - 1
        for code, data in ((0b01, word & 0xFF), (0b10 if last else 0b01, word >> 8)):
            dut.ui_in.value = data
            pads.drive(host_oe=pads.host_oe | 0b11, host_val=(keep & ~3) | code)
            await clock_edge(dut)
            pads.drive(host_val=keep & ~3)
            await clock_edge(dut)
    # Give uio[1:0] back to whatever drove them before the load.
    pads.drive(host_oe=(pads.host_oe & ~3) | oe0, host_val=keep)


def bit(v, i):
    return (int(v) >> i) & 1


# ------------------------------------------------------------------ test 2

@cocotb.test()
async def test_i2c_write_wired(dut):
    """i2c_write.asm on the wired-AND fixture: no pad drives high, no contention."""
    await reset(dut)
    sda, scl = 2, 3
    pads = Pads(dut, od=(1 << sda) | (1 << scl))
    await load(dut, pads, assemble((ASM / "i2c_write.asm").read_text()))

    bits, byte_bits, bytes_done = [], 0, 0
    prev = (1, 1)
    saw_start = saw_stop = ack_phase = False
    sampled = None
    stretch = stretched = 0
    for _ in range(4000):
        bus = int(dut.uio_in.value)
        s, c = bit(bus, sda), bit(bus, scl)
        if prev == (1, 1) and (s, c) == (0, 1):
            saw_start = True
        if saw_start and prev == (0, 1) and (s, c) == (1, 1):
            saw_stop = True
        if prev[1] == 0 and c == 1 and saw_start and not saw_stop and not ack_phase:
            if byte_bits < 8:
                sampled = s
            else:
                ack_phase = True
        if prev[1] == 1 and c == 0:
            if ack_phase:
                ack_phase, byte_bits = False, 0
                bytes_done += 1
            elif sampled is not None:
                bits.append(sampled)
                sampled = None
                byte_bits += 1
                if byte_bits == 8 and bytes_done == 0:
                    stretch = 250
        if stretch and c == 0 and not bit(dut.uio_oe.value, scl):
            stretched += 1
        prev = (s, c)
        ack = ack_phase or byte_bits == 8
        pads.drive(target=0xFF & ~((ack << sda) | ((stretch > 0) << scl)))
        stretch = max(0, stretch - 1)
        await clock_edge(dut)
        if saw_stop and bytes_done >= 2:
            break
    pads.stop()
    want = [(b >> i) & 1 for b in (0xA0, 0xB1) for i in range(7, -1, -1)]
    assert saw_start and saw_stop, f"start={saw_start} stop={saw_stop}"
    assert bits == want, f"I2C bits {bits}"
    assert bytes_done == 2 and stretched >= 5, f"bytes={bytes_done} stretched={stretched}"


# ------------------------------------------------------------------ helpers

Z = 0x88  # JL on uio0: the loader leaves it low, so JL Z always jumps


def pads16(dut):
    """(value, oe) of the 16 pins: uo 0..7 = pin 0..7, uio 0..7 = pin 8..15."""
    return int(dut.uo_out.value) | (int(dut.uio_out.value) << 8), 0xFF | (int(dut.uio_oe.value) << 8)


def pin(dut, p):
    return bit(dut.uo_out.value, p) if p < 8 else bit(dut.uio_out.value, p - 8)


def cfg_lines(um, im, stb, req, rsvd=0):
    return f"""
    LDI  R1, {um}
    LDI  R2, {im}
    LDI  R3, {(stb << 4) | (rsvd << 3) | req}
    HCFG R1, R2, R3
"""


def chunks_of(byte, n):
    """Spec §4.4: chunk c holds bits c*n .. c*n+n-1, LSB-aligned."""
    return [(byte >> (c * n)) & ((1 << n) - 1) for c in range(8 // n)]


class Host:
    """Host side of the pull handshake (§4.4, §4.5)."""

    def __init__(self, dut, pads, mask, stb, req):
        self.dut, self.pads = dut, pads
        self.pins = [p for p in range(16) if (mask >> p) & 1]
        self.n = len(self.pins)
        self.stb, self.req = stb, req
        pads.drive(host_oe=pads.host_oe | (1 << req))

    async def wait_live(self, timeout=200):
        """Host rule: start after the uio strobe pad turns on, plus the 3-clock blank."""
        assert self.stb >= 8, "wait_live needs a uio strobe pad"
        for _ in range(timeout):
            await clock_edge(self.dut)
            if bit(self.dut.uio_oe.value, self.stb - 8):
                break
        else:
            raise AssertionError("strobe pad never turned on (config not valid)")
        for _ in range(3):
            await clock_edge(self.dut)

    def data(self):
        return sum(pin(self.dut, p) << i for i, p in enumerate(self.pins))

    def check_oe(self):
        oe = int(self.dut.uio_oe.value)
        for p in self.pins + [self.stb]:
            if p >= 8:
                assert bit(oe, p - 8), f"owned uio pad {p} not driven"
        assert not bit(oe, self.req), "request pad driven"

    def toggle(self):
        self.pads.drive(host_val=self.pads.host_val ^ (1 << self.req))

    async def chunk(self, timeout=1200, latency=None):
        """Toggle once, wait for the strobe, latch 2 clocks later.

        Returns (data, clocks from the toggle to the strobe edge)."""
        s0, d0 = pin(self.dut, self.stb), self.data()
        self.toggle()
        for k in range(1, timeout + 1):
            await clock_edge(self.dut)
            if pin(self.dut, self.stb) != s0:
                break
        else:
            raise AssertionError(f"no strobe within {timeout} clocks")
        if latency is not None:
            assert k == latency, f"strobe {k} clocks after request, want {latency}"
        assert self.data() == d0, "data changed with the strobe edge"
        await clock_edge(self.dut)
        new = self.data()
        self.check_oe()
        await clock_edge(self.dut)
        assert self.data() == new, "data did not hold"
        return new, k

    async def byte(self, timeout=1200, latency=None):
        got = 0
        for c in range(8 // self.n):
            d, _ = await self.chunk(timeout, latency)
            got |= d << (c * self.n)
        return got

    async def no_strobe(self, toggle=True, window=WINDOW):
        s0 = pin(self.dut, self.stb)
        if toggle:
            self.toggle()
        for _ in range(window):
            await clock_edge(self.dut)
            assert pin(self.dut, self.stb) == s0, "unexpected strobe edge"


async def start(dut, src, od=0, host_oe=0, host_val=0, extra=None, target=0xFF):
    """Reset, load `src` (asm text; `extra` may edit the words), return the fixture.

    host_oe/host_val/target are on the pads from reset, before and during the load."""
    await reset(dut)
    pads = Pads(dut, od=od)
    pads.drive(host_oe=host_oe, host_val=host_val, target=target)
    words = assemble(src) if extra is None else extra(assemble(src))
    await load(dut, pads, words)
    return pads


async def trace(dut, cycles):
    rows = []
    for _ in range(cycles):
        await clock_edge(dut)
        rows.append((int(dut.uo_out.value), int(dut.uio_out.value), int(dut.uio_oe.value)))
    return rows


# ------------------------------------------------------------------ test 3

UART = (ASM / "uart.asm").read_text(encoding="utf-8")
HIDDEN = ["CAP R7", "SMP R7, R7", "HCFG R7, R7, R7", "LDH"]


def uart_with(slot, op):
    if slot == "loop":
        return UART.replace("    DJNZ R1, loop", f"    {op}\n    DJNZ R1, loop")
    return UART.replace("    LDI  R1, 8", f"    {op}\n    LDI  R1, 8")


@cocotb.test()
async def test_hidden_op_equivalence(dut):
    """CAP/SMP/HCFG(masks 0)/LDH in an LDI slot give the same pins as LDI R7,0."""
    for slot in ("loop", "pset"):
        pads = await start(dut, uart_with(slot, "LDI R7, 0"))
        ref = await trace(dut, 400)
        pads.stop()
        assert any(r[0] != 0xFF for r in ref), "reference never transmitted"
        for op in HIDDEN:
            pads = await start(dut, uart_with(slot, op))
            got = await trace(dut, 400)
            pads.stop()
            for i, (g, r) in enumerate(zip(got, ref)):
                assert g == r, f"{slot}/{op}: cycle {i} pins {g} want {r}"


# ------------------------------------------------------------------ test 4

def store_prog(um, im, stb, req, data):
    src = cfg_lines(um, im, stb, req) + "    LDI R6, 0x77\n"
    for i, b in enumerate(data):
        src += f"    LDI R4, {b}\n    CAP R4\nw{i}:\n    JL R6, w{i}\n"
    return src + "    HALT\n"


HS_CASES = [
    # (name, n, mask, strobe pin, request uio index)
    ("uo1", 1, 0x0008, 14, 7),
    ("uo2", 2, 0x000C, 14, 7),
    ("uo4", 4, 0x000F, 14, 7),
    ("uo8", 8, 0x00FF, 14, 7),
    ("uio1", 1, 0x0800, 4, 7),
    ("uio2", 2, 0x0C00, 4, 7),
    ("uio4", 4, 0x3C00, 4, 7),
    ("mix2", 2, 0x1002, 0, 7),
    ("mix4", 4, 0x8421, 1, 3),
    ("mix8", 8, 0x3C0F, 7, 6),
]
VECTORS = {1: [0x55], 2: [0xCC], 4: [0xF0], 8: [0xA5, 0x5A]}


@cocotb.test()
async def test_handshake(dut):
    """n=1/2/4/8 on uo, uio and mixed pins; strobe 1 clock before data; latency 3."""
    for name, n, mask, stb, req in HS_CASES:
        data = VECTORS[n] + [0xB1]
        pads = await start(dut, store_prog(mask & 0xFF, mask >> 8, stb, req, data))
        host = Host(dut, pads, mask, stb, req)
        for _ in range(40):  # program reaches its first JL loop
            await clock_edge(dut)
        dp = rtl(dut)
        if dp is not None:
            assert int(dp.rxp_v.value) == 1 and int(dp.hr_blank.value) == 0, "byte not ready"
        for i, b in enumerate(data):
            got = []
            for c in range(8 // n):
                # The first chunk of a later byte may wait for the program's CAP.
                d, _ = await host.chunk(latency=None if (i and not c) else 3)
                got.append(d)
            assert got == chunks_of(b, n), f"{name}: byte {b:#04x} chunks {got}"
            if name == "mix4" and b == 0xB1:
                # Hand-derived: pins {0,5,10,15}: chunk0 = 1,0,0,0; chunk1 = 1,1,0,1.
                assert got == [0b0001, 0b1011], f"mix4 0xB1 chunks {got}"
        v, oe = pads16(dut)
        free = ~(mask | (1 << stb) | (1 << (8 + req))) & 0xFFFF
        assert v & free & 0xFF == 0xFF & free, f"{name}: core uo pins changed"
        assert (oe >> 8) & (free >> 8) == 0, f"{name}: free uio pad driven"
        pads.stop()


# ------------------------------------------------------------------ test 9

ODO_SRC = """
    LDI  R2, {pin}
    LDI  R3, 16
    LDI  R1, 8
    LDI  R5, 0x33
    LDI  R0, {byte}
    LDH
    PSET R5, 0, R3
l:
    {op}
    DJNZ R1, l
    PSET R5, 1, R3
    HALT
"""


async def odo_run(dut, op, pin_, byte, ui=0):
    od = 1 << (pin_ & 7) if pin_ & 8 and op.startswith("ODO") else 0
    pads = await start(dut, ODO_SRC.format(pin=pin_, byte=byte, op=op), od=od)
    dut.ui_in.value = ui  # stable well before LDH (6 words later)
    rows = await trace(dut, 260)
    pads.stop()
    s0 = next(i for i, r in enumerate(rows) if not bit(r[0], 3))
    return rows, s0


def marker_rise(rows, s0):
    return next(i for i in range(s0, len(rows)) if bit(rows[i][0], 3)) - s0


@cocotb.test()
async def test_odo(dut):
    """ODO: same hold as OUT, oe = ~txr[7] MSB first, out stays 0, uo pin no-op."""
    rows, s0 = await odo_run(dut, "ODO R2, R3", 0xCC, 0, ui=0xB1)
    want = [0, 1, 0, 0, 1, 1, 1, 0]  # 0xB1 MSB first, inverted (§11.11)
    # Rd=16 keeps the ODO/DJNZ loop gapless (same as uart.asm), so window = hold.
    for k in range(8):
        for c in range(16):
            _, out, oe = rows[s0 + 16 * (k + 1) + c]
            assert bit(oe, 4) == want[k], f"ODO window {k} cycle {c}: oe {bit(oe, 4)}"
            assert not bit(out, 4), "ODO drove high"
    assert marker_rise(rows, s0) == 144, f"ODO loop length {marker_rise(rows, s0)}"

    # ODO 0x55 (oe 1,0,1,0..) vs OUT 0x55 (out 1,0,1,0..): both toggle every op from idle.
    rows_o, so = await odo_run(dut, "ODO R2, R3", 0xCC, 0, ui=0x55)
    rows_t, st = await odo_run(dut, "OUT R2, R0, R3", 0xCC, 0x55)
    eo = [i - so for i in range(1, len(rows_o)) if bit(rows_o[i][2], 4) != bit(rows_o[i - 1][2], 4)]
    et = [i - st for i in range(1, len(rows_t)) if bit(rows_t[i][1], 4) != bit(rows_t[i - 1][1], 4)]
    assert eo == et, f"ODO edges {eo} OUT edges {et}"
    assert marker_rise(rows_o, so) == marker_rise(rows_t, st) == 144

    # ODO on a uo pin: no pin change, same hold.
    rows, s0 = await odo_run(dut, "ODO R2, R3", 0x22, 0, ui=0x00)
    assert all(bit(r[0], 2) for r in rows), "ODO changed a uo pin"
    assert all(r[2] == 0 for r in rows), "ODO on a uo pin touched uio oe"
    assert marker_rise(rows, s0) == 144

    # 1110 and 1111 are no-ops: same trace as two LDIs in their place.
    src = "LDI R5, 0x33\nLDI R3, 5\nPSET R5, 0, R3\nLDI R7, 1\nLDI R7, 1\nPSET R5, 1, R3\nHALT\n"

    def raw(words):
        return words[:3] + [0xE5A5, 0xFFFF] + words[5:]
    pads = await start(dut, src)
    ref = await trace(dut, 40)
    pads.stop()
    pads = await start(dut, src, extra=raw)
    got = await trace(dut, 40)
    pads.stop()
    assert got == ref, "1110/1111 changed the pin trace"


# ------------------------------------------------------------------ UART helpers

def set_host_bit(pads, i, level):
    pads.drive(host_val=(pads.host_val & ~(1 << i)) | (level << i))


async def uart_host_send(pads, i, data, bit_ns, delay_ns):
    """8N1 frames on uio[i], back to back, asynchronous to clk."""
    if delay_ns:
        await Timer(delay_ns, unit="ns")
    for b in data:
        for level in [0] + [(b >> k) & 1 for k in range(8)] + [1]:
            set_host_bit(pads, i, level)
            await Timer(bit_ns, unit="ns")


async def uart_pin_frames(dut, p, bclk, frames, timeout=4000):
    """Decode `frames` 8N1 frames on uo[p] (mid-bit sampling)."""
    got = []
    for _ in range(frames):
        for _ in range(timeout):
            await clock_edge(dut)
            if not bit(dut.uo_out.value, p):
                break
        else:
            raise AssertionError("TX start bit never came")
        for _ in range(bclk // 2):
            await clock_edge(dut)
        assert not bit(dut.uo_out.value, p), "TX start bit too short"
        b = 0
        for k in range(8):
            for _ in range(bclk):
                await clock_edge(dut)
            b |= bit(dut.uo_out.value, p) << k
        for _ in range(bclk):
            await clock_edge(dut)
        assert bit(dut.uo_out.value, p), "TX stop bit low"
        got.append(b)
    return got


UDX = (ASM / "uart_duplex.asm").read_text(encoding="utf-8")
UDX_STB, UDX_REQ, UDX_RX = 12, 5, 2


def udx_src(bclk, um, im):
    return (UDX.replace(".equ BIT, 16", f".equ BIT, {bclk}")
               .replace(".equ UMASK, 0xFD", f".equ UMASK, {um}")
               .replace(".equ IOMASK, 0x08", f".equ IOMASK, {im}"))


async def duplex(dut, bclk, um, im, rx, err=0.0, phase=0.37, host_on=True, record=0):
    """Run uart_duplex; return (host bytes, TX frames, unowned-pin trace)."""
    mask = um | (im << 8)
    pads = await start(dut, udx_src(bclk, um, im), host_oe=1 << UDX_RX, host_val=1 << UDX_RX)
    host = Host(dut, pads, mask, UDX_STB, UDX_REQ)
    owned_uo = (mask | (1 << UDX_STB)) & 0xFF
    owned_io = ((mask | (1 << UDX_STB)) >> 8) | (1 << UDX_REQ)
    rows = []

    async def recorder():
        for _ in range(record):
            await clock_edge(dut)
            rows.append((int(dut.uo_out.value) & ~owned_uo & 0xFF,
                         int(dut.uio_out.value) & ~owned_io & 0xFF,
                         int(dut.uio_oe.value) & ~owned_io & 0xFF))
    rec = cocotb.start_soon(recorder())
    await host.wait_live()
    bit_ns = round(bclk * CLK_NS * (1 + err))
    tx = cocotb.start_soon(uart_host_send(pads, UDX_RX, rx, bit_ns, round((40 + phase) * CLK_NS)))
    frames = cocotb.start_soon(uart_pin_frames(dut, 1, bclk, 3, timeout=40 * bclk))
    got = []
    if host_on:
        for _ in rx:
            got.append(await host.byte(timeout=30 * bclk))
    await tx
    tx_frames = await frames
    await rec
    pads.stop()
    return got, tx_frames, rows


CLK_NS = 10_000


# ------------------------------------------------------------------ test 10

def per_byte_clocks(n, op, t_host):
    """§11.10: per chunk = op * ceil((T_host + 4) / op); worst case adds one op."""
    return (8 // n) * op * -(-(t_host + 4) // op) + op


@cocotb.test()
async def test_uart_duplex(dut):
    """Simultaneous TX/RX, independent phases, 16/52/104 clk/bit, +/-3%, host T_host=2."""
    rx = [0x5A, 0xC3, 0x0F, 0xF0]
    cases = [  # (clk/bit, uo mask, uio mask, baud error, phase)
        (16, 0xFD, 0x08, 0.0, 0.37),
        (16, 0xFD, 0x08, +0.03, 0.81),
        (16, 0xFD, 0x08, -0.03, 0.12),
        (52, 0xFD, 0x08, 0.0, 0.55),
        (104, 0xFD, 0x08, +0.03, 0.2),
        (16, 0x01, 0x00, 0.0, 0.63),  # n=1
    ]
    for bclk, um, im, err, phase in cases:
        n = bin(um | (im << 8)).count("1")
        data = rx if bclk < 100 else rx[:2]
        got, frames, _ = await duplex(dut, bclk, um, im, data, err, phase)
        assert got == data, f"B={bclk} n={n} err={err:+}: host read {[hex(b) for b in got]}"
        assert frames == [0xB1] * 3, f"B={bclk}: TX frames {frames}"
        # T_host = 2 (Host.chunk latches 2 clocks after the strobe, then toggles).
        fits = per_byte_clocks(n, bclk, 2) <= 10 * bclk
        assert fits, f"B={bclk} n={n}: formula says overflow, test vector is wrong"
        dp = rtl(dut)
        if dp is not None:
            assert int(dp.rx_ovf.value) == 0, f"B={bclk} n={n}: rx_ovf set"


@cocotb.test()
async def test_duplex_two_run_diff(dut):
    """uart_duplex with and without host requests: unowned pins identical every cycle."""
    rx = [0x5A, 0xC3, 0x0F]
    cycles = 16 * 10 * len(rx) + 400
    _, _, with_host = await duplex(dut, 16, 0xFD, 0x08, rx, record=cycles)
    _, _, without = await duplex(dut, 16, 0xFD, 0x08, rx, host_on=False, record=cycles)
    assert len(with_host) == len(without) == cycles
    for i, (a, b) in enumerate(zip(with_host, without)):
        assert a == b, f"cycle {i}: with host {a} without {b}"


# ------------------------------------------------------------------ test 11

def bitrev(b):
    return int(f"{b:08b}"[::-1], 2)


@cocotb.test()
async def test_spi_duplex(dut):
    """SPI mode 0: 0xB1 out on MOSI and 0x4D in on MISO in the same frame."""
    miso_pin = 2
    pads = await start(dut, (ASM / "spi_duplex.asm").read_text(encoding="utf-8"),
                       host_oe=1 << miso_pin, host_val=0)
    host = Host(dut, pads, 0x0063, 7, 7)
    miso = 0x4D
    mosi_bits, k, prev_sck, cs_seen, rises = [], 0, 0, False, 0
    for _ in range(600):
        await clock_edge(dut)
        uo = int(dut.uo_out.value)
        cs, sck, mosi = bit(uo, 2), bit(uo, 3), bit(uo, 4)
        if not cs and not cs_seen:
            cs_seen = True
            assert not sck, "SCK high when CS fell"
            set_host_bit(pads, miso_pin, (miso >> 7) & 1)
        if cs_seen and not cs:
            if not prev_sck and sck:
                mosi_bits.append(mosi)
                rises += 1
            if prev_sck and not sck and k < 7:
                k += 1
                set_host_bit(pads, miso_pin, (miso >> (7 - k)) & 1)
        prev_sck = sck
        if cs_seen and cs:
            break
    assert cs_seen and rises == 8, f"cs={cs_seen} SCK rises {rises}"
    assert mosi_bits == [(0xB1 >> (7 - i)) & 1 for i in range(8)], f"MOSI {mosi_bits}"
    for _ in range(8):  # CS-high PSET hold ends, core halts
        await clock_edge(dut)
    got = await host.byte(latency=3)
    assert got == bitrev(miso), f"host read {got:#04x}, want bitrev(0x4D)={bitrev(miso):#04x}"
    pads.stop()


# ------------------------------------------------------------------ spies (RTL only)

class Spy:
    """Clock index of each cycle where cond(dp) holds. Inactive in GL."""

    def __init__(self, dut, **conds):
        self.dp = rtl(dut)
        self.hits = {k: [] for k in conds}
        self.dut = dut
        self.task = cocotb.start_soon(self._run(conds)) if self.dp is not None else None

    async def _run(self, conds):
        c = 0
        while True:
            await RisingEdge(self.dut.clk)
            await ReadOnly()
            c += 1
            for k, f in conds.items():
                if f(self.dp):
                    self.hits[k].append(c)

    def stop(self):
        if self.task:
            self.task.cancel()


def sig(dp, name):
    return int(getattr(dp, name).value)


async def load_dmem_pads(dut, pads, data):
    for b in data:
        dut.ui_in.value = b
        pads.drive(host_oe=pads.host_oe | 3, host_val=(pads.host_val & ~3) | 3)
        await clock_edge(dut)
        pads.drive(host_val=pads.host_val & ~3)
        await clock_edge(dut)
    pads.drive(host_oe=pads.host_oe & ~3)


async def wait_until(dut, cond, timeout, what):
    """Bounded wait: fail after `timeout` clocks."""
    for _ in range(timeout):
        if cond():
            return
        await clock_edge(dut)
    raise AssertionError(f"timeout ({timeout} clocks) waiting for {what}")


async def wait_pin(dut, p, level, timeout=2000):
    for k in range(timeout):
        if pin(dut, p) == level:
            return k
        await clock_edge(dut)
    raise AssertionError(f"pin {p} never reached {level}")


MIX8 = (0x3C0F, 7, 6)  # uo0..3 + uio2..5 (pins 10..13), strobe uo7, request uio6


# ------------------------------------------------------------------ test 7

STATUS_SRC = cfg_lines(0x00, 0x3C, 14, 7) + """
    LDI  R6, 0x77
    LDI  R7, 0x66
    LDI  R5, 0x00
    LDI  R3, 4
    LDI  R4, 0xB1
    CAP  R4
    JL   R6, full
    HALT
full:
    PSET R5, 0, R3
    LDI  R4, 0x4D
    CAP  R4
    JL   R7, ovf
    HALT
ovf:
    LDI  R5, 0x11
    PSET R5, 0, R3
    LDI  R0, 0
    LDI  R1, 7
    LDI  R2, 0x55
    IN   R6, R0, R3
sh:
    IN   R2, R0, R3
    DJNZ R1, sh
    LDI  R2, 0x22
    OUT  R2, R0, R3
    INW  R6, R0, R3
    LDI  R2, 0x33
    PSET R2, 0, R3
    HALT
"""


@cocotb.test()
async def test_status_and_overflow(dut):
    """Overflow keeps the first byte; status pins 7/6 via JL (right after CAP), IN, INW."""
    pads = await start(dut, STATUS_SRC)
    host = Host(dut, pads, 0x3C00, 14, 7)
    await host.wait_live()
    await wait_pin(dut, 2, 0, 400)  # OUT of the IN-sampled pin-7 level
    uo = int(dut.uo_out.value)
    assert not bit(uo, 0), "JL pin 7 right after CAP did not see the byte"
    assert not bit(uo, 1), "JL pin 6 did not see the overflow"
    assert not bit(uo, 2), "IN pin 7 did not read 0"
    for _ in range(WINDOW):  # INW on pin 7 waits while the byte is unread
        await clock_edge(dut)
        assert bit(dut.uo_out.value, 3), "INW pin 7 finished with the byte unread"
    got = await host.byte(latency=3)
    assert got == 0xB1, f"first byte {got:#04x}, want 0xb1 (0x4d must be dropped)"
    await wait_pin(dut, 3, 0, 100)  # INW saw pin 7 return to 1
    await host.no_strobe()  # the dropped byte never appears
    pads.stop()


CAPT_SRC = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R4, 0xA5
    CAP  R4
    LDI  R5, 0x44
    LDI  R6, 16
    LDI  R7, 0x66
    LDI  R4, 0x3C
    REL  R5, R6
    CAP  R4
    JL   R7, ovf
    HALT
ovf:
    LDI  R5, 0x55
    PSET R5, 0, R6
    HALT
"""


@cocotb.test()
async def test_cap_vs_serve(dut):
    """CAP committing at E-1, E, E+1 of a last-chunk serve is dropped; at E+2 accepted."""
    for delta in (-1, 0, 1, 2):
        pads = await start(dut, CAPT_SRC)
        host = Host(dut, pads, *MIX8)
        spy = Spy(dut, serve=lambda dp: sig(dp, "hr_serve"), cap=lambda dp: sig(dp, "cap_cmt"))
        await wait_pin(dut, 4, 0, 200)  # REL marker: S
        # REL Rd=16 commits the hidden CAP at S+15; a toggle at X+1ns serves at X+3.
        for _ in range(12 - delta):
            await clock_edge(dut)
        d, k = await host.chunk(latency=3)
        assert d == 0xA5, f"delta {delta}: data at E+1 {d:#04x}, want the old byte"
        spy.stop()
        if spy.dp is not None:
            got = spy.hits["cap"][-1] - spy.hits["serve"][-1]
            assert got == delta, f"CAP at E{got:+}, test wanted E{delta:+}"
        for _ in range(30):
            await clock_edge(dut)
        dropped = not bit(dut.uo_out.value, 5)
        assert dropped == (delta <= 1), f"delta {delta}: rx_ovf via JL pin 6 = {dropped}"
        if dropped:
            await host.no_strobe()
        else:
            d, _ = await host.chunk(latency=3)
            assert d == 0x3C, f"delta {delta}: second byte {d:#04x}"
        pads.stop()


TIE_SRC = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R1, 0x0F
    LDI  R2, 2
    SMP  R1, R2
    LDI  R5, 0x44
    LDI  R6, 40
    LDI  R7, 0x66
    LDI  R4, 0x3C
    REL  R5, R6
    CAP  R4
    JL   R7, ovf
    HALT
ovf:
    LDI  R5, 0x55
    PSET R5, 0, R6
    HALT
"""


@cocotb.test()
async def test_cap_sampler_tie(dut):
    """Sampler and CAP in the same clock: the sampler byte wins, CAP sets rx_ovf."""
    rx = 7
    pads = await start(dut, TIE_SRC, host_oe=1 << rx, host_val=1 << rx)
    host = Host(dut, pads, *MIX8)
    spy = Spy(dut, fire=lambda dp: sig(dp, "smp_fire"), cap=lambda dp: sig(dp, "cap_cmt"))
    await wait_pin(dut, 4, 0, 200)  # S; CAP commits at S+39
    # Start bit at X+1ns: E = X+2, 8th sample (B=2, half=1) at E+1+16 = X+19 -> X = S+20.
    for _ in range(20):
        await clock_edge(dut)
    byte = 0x96
    set_host_bit(pads, rx, 0)
    for k in range(8):
        for _ in range(2):
            await clock_edge(dut)
            set_host_bit(pads, rx, (byte >> k) & 1)
    await clock_edge(dut)
    set_host_bit(pads, rx, 1)
    for _ in range(80):  # the JL-ovf path holds a PSET of 40; let it end
        await clock_edge(dut)
    spy.stop()
    if spy.dp is not None:
        assert spy.hits["fire"] and spy.hits["fire"][0] in spy.hits["cap"], \
            f"no tie: fire {spy.hits['fire']} cap {spy.hits['cap']}"
    assert not bit(dut.uo_out.value, 5), "CAP in the tie did not set rx_ovf"
    got = await host.byte(latency=3)
    assert got == byte, f"tie kept {got:#04x}, want the sampler byte {byte:#04x}"
    pads.stop()


FWD_BODY = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R6, 0x66
    LDI  R4, 0x44
    LDI  R7, 4
    LDI  R0, 0
    LDI  R1, 7
    LDI  R2, 0xFF
    LDI  R3, 16
l:
    IN   R2, R0, R3
    DJNZ R1, l
    {rd}
    IN   R2, R0, R3
    {mid}
    CAP  R0
    JL   R6, bad
    HALT
bad:
    PSET R4, 0, R7
    HALT
"""
STREAM_SRC = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R2, 0x55
    LDI  R3, 3
    LDI  R5, 0
    LD   R0, [R5]
""" + "    OUTM R2, R0, R3\n" * 8 + """
    CAP  R0
    HALT
"""


@cocotb.test()
async def test_cap_forwarding(dut):
    """IN Rd=2/3 then CAP gets the full byte; each CAP forwarding branch fires."""
    branches = {"fire": 0, "wr": 0, "refill": 0}
    conds = dict(
        fire=lambda dp: sig(dp, "cap_cmt") and sig(dp, "in_fire")
        and sig(dp, "in_fire_rs") == (sig(dp, "op_word") >> 8) & 7,
        wr=lambda dp: sig(dp, "cap_cmt") and sig(dp, "in_wr_v")
        and sig(dp, "in_rs") == (sig(dp, "op_word") >> 8) & 7,
        refill=lambda dp: sig(dp, "cap_cmt") and sig(dp, "refill_pend")
        and sig(dp, "stream_rs") == (sig(dp, "op_word") >> 8) & 7,
        cap=lambda dp: sig(dp, "cap_cmt"),
    )
    branches["cap"] = 0
    rx = 7  # uio7 = pin 15, held high: 8 INs from R0=0 give 0xFF only with the last bit
    for rd in ("LDI R3, 2", "LDI R3, 3"):
        for mid in ("", "LDI R5, 0x11"):
            pads = await start(dut, FWD_BODY.format(rd=rd, mid=mid), host_oe=1 << rx, host_val=1 << rx)
            host = Host(dut, pads, *MIX8)
            spy = Spy(dut, **conds)
            for _ in range(300):
                await clock_edge(dut)
            spy.stop()
            for k in branches:
                branches[k] += len(spy.hits[k])
            # R27: one CAP word must commit once (a second commit overflows -> JL pin 6).
            assert bit(dut.uo_out.value, 4), f"{rd} mid='{mid}': CAP committed twice (rx_ovf)"
            if spy.dp is not None:
                assert len(spy.hits["cap"]) == 1, f"{rd} mid='{mid}': {len(spy.hits['cap'])} CAP commits"
            got = await host.byte(latency=3)
            assert got == 0xFF, f"{rd} mid='{mid}': CAP got {got:#04x}, want 0xff"
            pads.stop()

    # OUTM stream: CAP in the refill clock forwards the dmem byte.
    await reset(dut)
    pads = Pads(dut)
    await load_dmem_pads(dut, pads, [0x11, 0xC6])
    for _ in range(3):
        await clock_edge(dut)
    spy = Spy(dut, **conds)
    await load(dut, pads, assemble(STREAM_SRC))
    host = Host(dut, pads, *MIX8)
    for _ in range(80):
        await clock_edge(dut)
    spy.stop()
    for k in branches:
        branches[k] += len(spy.hits[k])
    got = await host.byte(latency=3)
    assert got == 0xC6, f"stream CAP got {got:#04x}, want dmem[1]=0xc6"
    pads.stop()
    if rtl(dut) is not None:
        assert all(v for k, v in branches.items() if k != "cap"), f"forwarding branch hits {branches}"


# ------------------------------------------------------------------ test 8

SMP_SRC = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R4, {src}
    LDI  R5, {b}
    SMP  R4, R5
    HALT
"""


def smp_expect(d, b):
    """§11.7: bit k is the level driven at clock X + half + B*(k+1) - 1 (X = start edge)."""
    B = 256 if b == 0 else b
    half = 128 if b == 0 else b >> 1
    return sum(d[half + B * (k + 1) - 1] << k for k in range(8))


@cocotb.test()
async def test_sampler(dut):
    """Sample clocks vs E for B=1,2,16,170,171,255,0; uio and ui_in sources."""
    import random
    rnd = random.Random(0x5A)
    for b, src in [(1, 0x0F), (2, 0x0F), (16, 0x0F), (170, 0x0F), (171, 0x0F),
                   (255, 0x0F), (0, 0x0F), (16, 0x85)]:
        ui = src & 0x80
        idx = src & 7
        B = 256 if b == 0 else b
        length = (128 if b == 0 else b >> 1) + 8 * B + 2
        while True:
            d = [0] + [rnd.randint(0, 1) for _ in range(length)]
            want = smp_expect(d, b)
            # The vector must tell a 1-clock sample shift apart.
            if all(smp_expect(d[s:] + [1] * 4, b) != want for s in (1,)) and \
               smp_expect([1] + d, b) != want:
                break
        if ui:
            pads = await start(dut, SMP_SRC.format(src=src, b=b))
            dut.ui_in.value = 1 << idx

            def drive(level):
                dut.ui_in.value = level << idx
        else:
            pads = await start(dut, SMP_SRC.format(src=src, b=b), host_oe=1 << idx, host_val=1 << idx)

            def drive(level):
                set_host_bit(pads, idx, level)
        host = Host(dut, pads, *MIX8)
        for _ in range(40):
            await clock_edge(dut)
        spy = Spy(dut, cap=lambda dp: sig(dp, "rxp_v"))
        for level in d:
            drive(level)
            await clock_edge(dut)
        drive(1)
        got = await host.byte(timeout=600)
        spy.stop()
        assert got == want, f"B={b} src={src:#x}: got {got:#04x}, want {want:#04x}"
        if spy.dp is not None:
            # Spy clock c is edge X+c. rxp_v is first 1 after the capture edge E+half+8B.
            half = 128 if b == 0 else b >> 1
            assert spy.hits["cap"][:1] == [2 + half + 8 * B], \
                f"B={b}: capture at clock {spy.hits['cap'][:1]}, want E+half+8B = {2 + half + 8 * B}"
        pads.stop()


@cocotb.test()
async def test_sampler_arm(dut):
    """Disarm, re-arm waits for idle, and the sampler runs during INW, hold and HALT."""
    rx = 7
    # Disarm: SMP R0 (R0=0) after arming.
    src = SMP_SRC.format(src=0x0F, b=16).replace("    HALT", "    SMP  R0, R5\n    HALT")
    pads = await start(dut, src, host_oe=1 << rx, host_val=1 << rx)
    host = Host(dut, pads, *MIX8)
    for _ in range(40):
        await clock_edge(dut)
    await uart_host_send(pads, rx, [0x00], 16 * CLK_NS, 0)
    await host.no_strobe()
    pads.stop()

    # Re-arm waits for idle: line stays low after frame 1 (no stop bit).
    pads = await start(dut, SMP_SRC.format(src=0x0F, b=16), host_oe=1 << rx, host_val=1 << rx)
    host = Host(dut, pads, *MIX8)
    for _ in range(40):
        await clock_edge(dut)
    reader = cocotb.start_soon(host.byte())
    for level in [0] + [(0x2C >> k) & 1 for k in range(7)] + [0]:  # bit 7 = 0
        set_host_bit(pads, rx, level)
        await Timer(16 * CLK_NS, unit="ns")
    await Timer(40 * CLK_NS, unit="ns")  # still low: no new frame may start
    set_host_bit(pads, rx, 1)
    assert await reader == 0x2C
    reader = cocotb.start_soon(host.byte())
    await Timer(20 * CLK_NS, unit="ns")
    await uart_host_send(pads, rx, [0xD3], 16 * CLK_NS, 0)
    assert await reader == 0xD3, "re-arm did not wait for idle"
    pads.stop()

    # Runs during INW (wait on pin 9), during a 256-clock PSET hold, and after HALT.
    src = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R4, 0x0F
    LDI  R5, 16
    SMP  R4, R5
    LDI  R1, 0x99
    LDI  R2, 1
    LDI  R6, 0x44
    LDI  R7, 0
    INW  R1, R0, R2
    PSET R6, 0, R7
    HALT
"""
    pads = await start(dut, src, host_oe=1 << rx, host_val=1 << rx)
    pads.drive(host_oe=pads.host_oe | 2, host_val=pads.host_val | 2)  # pin 9 high
    host = Host(dut, pads, *MIX8)
    for _ in range(40):
        await clock_edge(dut)
    await uart_host_send(pads, rx, [0x61], 16 * CLK_NS, 0)  # during INW
    assert bit(dut.uo_out.value, 4), "INW ended early"
    assert await host.byte() == 0x61
    set_host_bit(pads, 1, 0)  # end INW; PSET hold of 256 starts
    await wait_pin(dut, 4, 0, 20)
    await uart_host_send(pads, rx, [0x9E], 16 * CLK_NS, 0)
    assert not bit(dut.uo_out.value, 4), "hold ended before the frame"
    assert await host.byte() == 0x9E
    for _ in range(200):  # HALT
        await clock_edge(dut)
    await uart_host_send(pads, rx, [0x3B], 16 * CLK_NS, 0)
    assert await host.byte() == 0x3B
    pads.stop()


class Edges:
    """Edge index counter, plus the edge indices where uo[p] changed."""

    def __init__(self, dut, p):
        self.dut, self.p, self.c, self.tx = dut, p, 0, []
        self.task = cocotb.start_soon(self._run())

    async def _run(self):
        prev = bit(self.dut.uo_out.value, self.p)
        while True:
            await RisingEdge(self.dut.clk)
            await ReadOnly()
            self.c += 1
            v = bit(self.dut.uo_out.value, self.p)
            if v != prev:
                self.tx.append(self.c)
            prev = v

    async def until(self, c):
        while self.c < c:
            await clock_edge(self.dut)

    def stop(self):
        self.task.cancel()


# ------------------------------------------------------------------ test 5

TXB_SRC = cfg_lines(0x00, 0x10, 15, 6) + """
    LDI  R2, 0x11
    LDI  R3, 16
    LDI  R4, 0xC3
    CAP  R4
    LDI  R0, 0x55
    LDI  R4, 0x96
    LDI  R5, 8
    LDI  R6, 1
    LDI  R7, 0
    PSET R2, 0, R3
    LDI  R1, 8
bit:
    OUT  R2, R0, R3
    DJNZ R1, bit
    PSET R2, 1, R3
    CAP  R4
    PSET R2, 0, R7
r1:
    PSET R2, 1, R6
    PSET R2, 0, R6
    DJNZ R5, r1
    LDI  R2, 0xDD
    REL  R2, R7
    IN   R2, R0, R7
    INW  R2, R0, R7
    HALT
"""


@cocotb.test()
async def test_tx_busy(dut):
    """Serve only at TX op boundaries; Rd=1 ops, REL, IN, INW and HALT never block."""
    pads = await start(dut, TXB_SRC, host_oe=1 << 5, host_val=0)
    host = Host(dut, pads, 0x1000, 15, 6)
    ed = Edges(dut, 1)
    await host.wait_live()
    await wait_until(dut, lambda: ed.tx, 400, "the TX frame start")
    s0 = ed.tx[0]  # start bit of the 0x55 frame: ops start at s0 + 16*i
    data = []

    async def req(at, blocked_until=None):
        await ed.until(at)
        t = ed.c
        d, k = await host.chunk(timeout=600)
        data.append(d)
        s = t + k  # strobe edge index
        if blocked_until is None:
            assert k == 3, f"request at {t - s0}: strobe after {k}, want 3 (not blocked)"
        else:
            assert s == blocked_until, \
                f"request at {t - s0}: strobe at {s - s0}, want the next op start {blocked_until - s0}"
            assert blocked_until in ed.tx, f"{blocked_until - s0} is not a TX edge {ed.tx}"
        return s

    for i in range(1, 9):  # mid-hold of each OUT: served at the next op start
        await req(s0 + 16 * i + 5, blocked_until=s0 + 16 * (i + 1))
    await req(s0 + 160 + 20, blocked_until=s0 + 160 + 256)  # Rd=0 PSET
    await req(s0 + 416 + 2)  # inside the Rd=1 burst
    burst_end = s0 + 416
    await wait_until(dut, lambda: ed.c - ed.tx[-1] >= 10, 400, "the end of the Rd=1 burst")
    burst_end = ed.tx[-1]
    await req(burst_end + 20)  # REL Rd=0
    await req(burst_end + 300)  # IN Rd=0
    await req(burst_end + 600)  # INW waiting
    set_host_bit(pads, 5, 1)  # INW sees pin 13 change, then holds 256
    await req(ed.c + 20)
    await req(ed.c + 300)  # HALT
    await req(ed.c + 5)
    ed.stop()
    pads.stop()
    got = [sum(b << i for i, b in enumerate(data[j:j + 8])) for j in (0, 8)]
    assert got == [0xC3, 0x96], f"bytes {[hex(b) for b in got]}"


# ------------------------------------------------------------------ test 6

@cocotb.test()
async def test_hcfg_request_baseline(dut):
    """No false serve: request idling high; request pad core-driven before HCFG."""
    # Request pad held high by the host from reset; uo strobe.
    pads = await start(dut, store_prog(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2], [0x5A]),
                       host_oe=1 << MIX8[2], host_val=1 << MIX8[2])
    host = Host(dut, pads, *MIX8)
    for _ in range(40):  # program reaches HCFG and its JL loop
        await clock_edge(dut)
    await host.no_strobe(toggle=False)
    assert await host.byte(latency=3) == 0x5A
    pads.stop()

    # Core drives the request pad high before HCFG; the host drives it low once released.
    src = """
    LDI  R1, 0xEE
    LDI  R2, 30
    PSET R1, 1, R2
""" + store_prog(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2], [0xA7])
    pads = await start(dut, src)
    await wait_pin(dut, 14, 1, 100)
    assert bit(dut.uio_oe.value, 6), "core did not drive the request pad"
    await wait_until(dut, lambda: not bit(dut.uio_oe.value, 6), 200, "HCFG to release the request pad")
    pads.drive(host_oe=pads.host_oe | (1 << 6), host_val=pads.host_val & ~(1 << 6))
    host = Host(dut, pads, *MIX8)
    await host.no_strobe(toggle=False)
    assert await host.byte(latency=3) == 0xA7
    pads.stop()


GO = 0x99  # pin 9 (uio1): the host pulls it low to let the program go on


def go_wait(tag):
    return f"""
    LDI  R6, {GO}
    LDI  R7, {Z}
{tag}:
    JL   R6, {tag}_go
    JL   R7, {tag}
{tag}_go:
"""


@cocotb.test()
async def test_hcfg_mid_byte(dut):
    """HCFG n=1 -> n=4 after chunk 5: same byte again from chunk 0, next byte intact."""
    src = cfg_lines(0x01, 0x00, 15, 6) + """
    LDI  R4, 0xB1
    CAP  R4
""" + go_wait("g") + cfg_lines(0x0F, 0x00, 15, 6) + """
    LDI  R6, 0x77
w:
    JL   R6, w
    LDI  R4, 0x4D
    CAP  R4
    HALT
"""
    pads = await start(dut, src, host_oe=2, host_val=2)
    host = Host(dut, pads, 0x0001, 15, 6)
    await host.wait_live()
    got = [(await host.chunk(latency=3))[0] for _ in range(5)]
    assert got == chunks_of(0xB1, 1)[:5], f"n=1 chunks {got}"
    set_host_bit(pads, 1, 0)
    host = Host(dut, pads, 0x000F, 15, 6)
    await host.no_strobe(toggle=False)  # same strobe pin: no edge at HCFG
    assert await host.byte(latency=3) == 0xB1, "HCFG mid-byte did not restart at chunk 0"
    assert await host.byte() == 0x4D
    pads.stop()


INVALID = [
    # (name, smp source or None, uo mask, uio mask, strobe pin, request, rsvd)
    ("popcount3", None, 0x07, 0x00, 15, 6, 0),
    ("strobe_in_mask", None, 0x0F, 0x00, 3, 6, 0),
    ("request_in_mask", None, 0x01, 0x40, 15, 6, 0),
    ("strobe_is_request", None, 0x01, 0x00, 14, 6, 0),
    ("rsvd", None, 0x01, 0x00, 15, 6, 1),
    ("sampler_in_mask", 0x0D, 0x01, 0x20, 15, 6, 0),
    ("sampler_is_strobe", 0x0F, 0x01, 0x00, 15, 6, 0),
]


@cocotb.test()
async def test_hcfg_invalid(dut):
    """Invalid configs leave the path off; pins keep core values."""
    for name, smp, um, im, stb, req, rsvd in INVALID:
        src = ""
        if smp is not None:
            src += f"    LDI R4, {smp}\n    LDI R5, 16\n    SMP R4, R5\n"
        src += cfg_lines(um, im, stb, req, rsvd) + "    LDI R4, 0xFF\n    CAP R4\n    HALT\n"
        pads = await start(dut, src, host_oe=0xA0, host_val=0xA0)  # uio5, uio7 idle high
        host = Host(dut, pads, um | (im << 8), stb, req)
        for _ in range(40):
            await clock_edge(dut)
        await host.no_strobe()
        assert int(dut.uo_out.value) == 0xFF, f"{name}: uo pins left core values"
        assert int(dut.uio_oe.value) == 0, f"{name}: a uio pad is driven"
        pads.stop()

    # Valid, then SMP on a masked uio pad makes it invalid.
    src = cfg_lines(0x01, 0x04, 15, 6) + "    LDI R4, 0xFF\n    CAP R4\n" + go_wait("g") + \
        "    LDI R4, 0x0A\n    LDI R5, 16\n    SMP R4, R5\n    HALT\n"
    pads = await start(dut, src, host_oe=2, host_val=2)
    host = Host(dut, pads, 0x0401, 15, 6)
    await host.wait_live()
    assert (await host.chunk(latency=3))[0] == 0b11
    set_host_bit(pads, 1, 0)
    for _ in range(30):
        await clock_edge(dut)
    await host.no_strobe()
    assert int(dut.uo_out.value) == 0xFF and int(dut.uio_oe.value) == 0, "SMP did not turn the path off"
    pads.stop()


@cocotb.test()
async def test_hcfg_disable_and_restrobe(dut):
    """Disable restores core pins; owned-pin core writes reappear; strobe baselines."""
    src = cfg_lines(0x0F, 0x00, 15, 6) + """
    LDI  R4, 0xFF
    CAP  R4
    LDI  R5, 0x00
    LDI  R4, 1
    PSET R5, 0, R4
""" + go_wait("g1") + cfg_lines(0x00, 0x3C, 3, 6) + """
    LDI  R4, 0xA5
    CAP  R4
    LDI  R6, 0x99
g2:
    JL   R6, g2
""" + cfg_lines(0x00, 0x00, 0, 0) + "    HALT\n"
    pads = await start(dut, src, host_oe=2, host_val=2)
    host = Host(dut, pads, 0x000F, 15, 6)
    await host.wait_live()
    assert await host.byte(latency=3) == 0xFF
    assert pin(dut, 0) == 1, "owned pin shows the core write instead of data"
    # Valid -> valid: the new strobe uo3 was a mask pin at 1. No edge.
    set_host_bit(pads, 1, 0)
    for _ in range(WINDOW):
        await clock_edge(dut)
        assert pin(dut, 3) == 1, "new strobe pin moved at HCFG"
    host = Host(dut, pads, 0x3C00, 3, 6)
    got = [(await host.chunk(latency=3))[0] for _ in range(2)]
    assert got == chunks_of(0xA5, 4), f"second config chunks {got}"
    set_host_bit(pads, 1, 1)  # program leaves g2 and disables the path
    for _ in range(WINDOW):
        await clock_edge(dut)
    assert int(dut.uo_out.value) == 0xFE, f"uo {int(dut.uo_out.value):#04x}, want core 0xfe"
    assert int(dut.uio_oe.value) == 0, "uio pads still driven after disable"
    pads.stop()


@cocotb.test()
async def test_hcfg_vs_serve(dut):
    """HCFG committing on E+1 of a last-chunk serve: the byte is served again from chunk 0."""
    m, stb, req = MIX8
    src = cfg_lines(m & 0xFF, m >> 8, stb, req) + """
    LDI  R4, 0xA5
    CAP  R4
    LDI  R5, 0x44
    LDI  R6, 16
    REL  R5, R6
    HCFG R1, R2, R3
    HALT
"""
    pads = await start(dut, src)
    host = Host(dut, pads, *MIX8)
    spy = Spy(dut, serve=lambda dp: sig(dp, "hr_serve"), hcfg=lambda dp: sig(dp, "hcfg_cmt"))
    await wait_pin(dut, 4, 0, 200)  # S; HCFG commits at S+15 = E+1 -> toggle at S+11
    for _ in range(11):
        await clock_edge(dut)
    d, _ = await host.chunk(latency=3)
    assert d == 0x00, f"data after a colliding HCFG {d:#04x}, want 0 (hr_dout reset)"
    spy.stop()
    if spy.dp is not None:
        assert spy.hits["hcfg"][-1] - spy.hits["serve"][-1] == 1, "HCFG not on E+1"
    for _ in range(10):
        await clock_edge(dut)
    assert await host.byte(latency=3) == 0xA5, "byte not served again"
    pads.stop()


OUTM_HOLD_SRC = """
    LDI  R1, {m1}
    LDI  R2, {m2}
    LDI  R3, {sr}
    LDI  R4, 0x55
    LDI  R0, 0x5A
    LDI  R6, {rd}
    OUTM R4, R0, R6
    {op}
    OUTM R4, R0, R6
    OUTM R4, R0, R6
    HALT
"""
GOLDEN = Path(__file__).resolve().parent / "golden"


@cocotb.test()
async def test_hcfg_in_outm_hold(dut):
    """OUTM Rd 2/3 with HCFG at hold==1: unowned pins equal the 663dec1 LDI-version golden.

    GOLDEN_WRITE=1 (run on 663dec1 src) records only the LDI version, then fails."""
    m, stb, req = MIX8
    owned_uo = (m | (1 << stb)) & 0xFF
    owned_io = (m >> 8) | (1 << req)
    write = bool(os.environ.get("GOLDEN_WRITE"))

    def unowned(rows):
        return [(u & ~owned_uo & 0xFF, o & ~owned_io & 0xFF, e & ~owned_io & 0xFF) for u, o, e in rows]
    for rd in (2, 3):
        path = GOLDEN / f"outm_hold_rd{rd}.txt"
        fmt = dict(m1=m & 0xFF, m2=m >> 8, sr=(stb << 4) | req, rd=rd)
        pads = await start(dut, OUTM_HOLD_SRC.format(op="LDI  R7, 0", **fmt))
        ref = await trace(dut, 60)
        pads.stop()
        if write:
            path.write_text("".join(f"{u:02x} {o:02x} {e:02x}\n" for u, o, e in ref), encoding="utf-8")
            continue
        gold = [tuple(int(x, 16) for x in line.split()) for line in path.read_text(encoding="utf-8").splitlines()]
        assert ref == gold, f"Rd={rd}: LDI version differs from the 663dec1 golden"
        pads = await start(dut, OUTM_HOLD_SRC.format(op="HCFG R1, R2, R3", **fmt))
        spy = Spy(dut, h1=lambda dp: sig(dp, "hcfg_cmt") and sig(dp, "hold") == 1,
                  valid=lambda dp: sig(dp, "hr_valid"))
        got = await trace(dut, 60)
        spy.stop()
        pads.stop()
        if spy.dp is not None:
            assert spy.hits["valid"], f"Rd={rd}: HCFG config was not valid"
            if rd == 3:
                assert spy.hits["h1"], "HCFG did not commit at hold==1"
        assert unowned(got) == unowned(gold), f"Rd={rd}: HCFG changed unowned pins vs golden"
    assert not write, "outm_hold goldens written; rerun without GOLDEN_WRITE to check"


@cocotb.test()
async def test_request_on_loader_pins(dut):
    """Request on uio0 or uio1 is served and has no loader effect while running."""
    for req in (0, 1):
        src = cfg_lines(0x01, 0x00, 15, req) + """
    LDI  R4, 0x69
    CAP  R4
    LDI  R6, 0x77
    LDI  R5, 0x44
    LDI  R3, 4
w:
    JL   R6, w
    PSET R5, 0, R3
    HALT
"""
        pads = await start(dut, src)
        imem = dut.DUT.imem if not GL else None
        host = Host(dut, pads, 0x0001, 15, req)
        await host.wait_live()
        assert await host.byte(latency=None) == 0x69
        await wait_pin(dut, 4, 0, 50)  # program kept running after the byte drained
        if imem is not None:
            assert int(imem.wr_addr.value) == len(assemble(src)), "a request toggle wrote imem"
        pads.stop()


# ------------------------------------------------------------------ test 13

RST_SRC = """
    LDI  R6, 0x66
    LDI  R7, 0x77
    LDI  R5, 0x44
    LDI  R3, 4
    JL   R6, bad6
    JL   R7, bad7
""" + cfg_lines(0x0F, 0x00, 15, 6) + """
    LDI  R4, 0xB1
    CAP  R4
    CAP  R4
    HALT
bad6:
    PSET R5, 0, R3
    HALT
bad7:
    LDI  R5, 0x55
    PSET R5, 0, R3
    HALT
"""


@cocotb.test()
async def test_reset(dut):
    """Reset: pads to FF/inputs at the first low edge; no false serve; status reads 1."""
    pads = await start(dut, RST_SRC)
    host = Host(dut, pads, 0x000F, 15, 6)
    await host.wait_live()
    assert int(dut.uo_out.value) & 0x0F == 0, "mask pins should show hr_dout=0"
    d, _ = await host.chunk(latency=3)
    assert d == 0x1
    dp = rtl(dut)
    if dp is not None:
        assert int(dp.rx_ovf.value) == 1, "second CAP should overflow"
    # Reset mid-byte (chunk 1 of 2 read). Request pad keeps its toggled level.
    dut.rst_n.value = 0
    await clock_edge(dut)
    assert int(dut.uo_out.value) == 0xFF, "uo not FF at the first reset edge"
    assert int(dut.uio_oe.value) == 0, "uio driven at the first reset edge (strobe)"
    await clock_edge(dut)
    dut.rst_n.value = 1
    await clock_edge(dut)
    await load(dut, pads, assemble(RST_SRC))
    await host.wait_live()
    await host.no_strobe(toggle=False)  # no false serve from the old toggle
    for _ in range(10):
        await clock_edge(dut)
    assert pin(dut, 4) == 1 and pin(dut, 5) == 1, "status pin read 0 after reload"
    assert await host.byte(latency=3) == 0xB1, "byte after restart not from chunk 0"
    pads.stop()


# ------------------------------------------------------------------ test 12 (I2C)

SDA, SCL = 2, 3
I2C_OD = (1 << SDA) | (1 << SCL)


class SdaRule:
    """Every chip SDA drive change must see bus SCL low, except at START/Sr/STOP.

    Records (clock, scl, new oe) for changes made while SCL was high."""

    def __init__(self, dut):
        self.dut, self.high, self.c = dut, [], 0
        self.task = cocotb.start_soon(self._run())

    async def _run(self):
        prev = bit(self.dut.uio_oe.value, SDA)
        while True:
            await clock_edge(self.dut)
            self.c += 1
            oe = bit(self.dut.uio_oe.value, SDA)
            if oe != prev and bit(self.dut.uio_in.value, SCL):
                self.high.append((self.c, oe))
            prev = oe

    def stop(self):
        self.task.cancel()


class I2CTarget:
    """Bus-level target at 0x50 that answers reads with `data`, stretching SCL."""

    def __init__(self, dut, pads, data, stretch):
        self.dut, self.pads, self.data = dut, pads, list(data)
        self.stretch = dict(stretch)  # event name -> clocks to hold SCL low
        self.state, self.prev = "idle", (1, 1)
        self.starts = self.stops = 0
        self.addrs, self.acks = [], []
        self.sda_low = self.hold = 0
        self.held = 0  # clocks the target held SCL while the chip had released it
        self.task = cocotb.start_soon(self._run())

    def _drive(self):
        self.pads.drive(target=0xFF & ~((self.sda_low << SDA) | ((self.hold > 0) << SCL)))

    def _present(self):
        self.sda_low = 1 - ((self.byte >> self.tb) & 1)

    def _stretch(self, name):
        self.hold = self.stretch.pop(name, 0)

    async def _run(self):
        while True:
            await clock_edge(self.dut)
            bus = int(self.dut.uio_in.value)
            sda, scl = bit(bus, SDA), bit(bus, SCL)
            psda, pscl = self.prev
            if self.hold:
                self.hold -= 1
                if not bit(self.dut.uio_oe.value, SCL):
                    self.held += 1
            if pscl and scl and psda and not sda:
                self.starts += 1
                self.state, self.bits, self.sh, self.sda_low = "addr", 0, 0, 0
            elif pscl and scl and not psda and sda:
                self.stops += 1
                self.state, self.sda_low = "idle", 0
            elif not pscl and scl:  # SCL rise
                if self.state == "addr":
                    self.sh, self.bits = (self.sh << 1) | sda, self.bits + 1
                elif self.state == "rx_ack":
                    self.acks.append(sda)
            elif pscl and not scl:  # SCL fall
                if self.state == "addr" and self.bits == 8:
                    self.addrs.append(self.sh)
                    if self.sh >> 1 == 0x50:
                        self.sda_low, self.state = 1, "ack_addr"
                    else:
                        self.state = "idle"
                elif self.state == "ack_addr":
                    self.sda_low = 0
                    if self.addrs[-1] & 1:
                        self.byte, self.tb, self.state = self.data.pop(0), 7, "tx"
                        self._present()
                        self._stretch("first")
                    else:
                        self.state = "idle"
                elif self.state == "tx":
                    if self.tb == 0:
                        self.sda_low, self.state = 0, "rx_ack"
                    else:
                        self.tb -= 1
                        self._present()
                        if self.tb == 3:
                            self._stretch("mid")
                elif self.state == "rx_ack":
                    if self.acks[-1] == 0:
                        self.byte, self.tb, self.state = self.data.pop(0), 7, "tx"
                        self._present()
                    else:
                        self.state = "idle"
            self.prev = (sda, scl)
            self._drive()

    def stop(self):
        self.task.cancel()


@cocotb.test()
async def test_i2c_read(dut):
    """i2c_read.asm: ACK/NACK, repeated START, stretching, STOP; host reads each byte."""
    data = [0x3C, 0xE7, 0x81]
    pads = await start(dut, (ASM / "i2c_read.asm").read_text(encoding="utf-8"), od=I2C_OD)
    dut.ui_in.value = 0xA1  # address byte for LDH, stable long before it runs
    target = I2CTarget(dut, pads, data + [0x00], {"first": 40, "mid": 25})
    rule = SdaRule(dut)
    host = Host(dut, pads, 0x00FF, 15, 6)
    await host.wait_live()
    got = [await host.byte(timeout=1500) for _ in data]
    for _ in range(200):
        await clock_edge(dut)
    target.stop()
    rule.stop()
    pads.stop()
    assert got == [bitrev(b) for b in data], f"host read {[hex(b) for b in got]}"
    assert target.addrs == [0xA1, 0xA1], f"addresses {[hex(a) for a in target.addrs]}"
    assert target.acks == [0, 1, 1], f"controller ACK/NACK {target.acks}"
    assert target.starts == 2 and target.stops == 1, f"starts {target.starts} stops {target.stops}"
    assert target.held >= 40, f"controller did not wait for the stretch ({target.held})"
    # Chip SDA changes with SCL high: only START (drive), Sr (drive), STOP (release).
    assert [oe for _, oe in rule.high] == [1, 1, 0], f"SDA changed with SCL high: {rule.high}"


class I2CController:
    """Bus-level controller: SCL low L clocks, high H clocks, honours stretching."""

    def __init__(self, dut, pads, low, high):
        self.dut, self.pads, self.L, self.H = dut, pads, low, high
        self.sda_rel = self.scl_rel = 1
        self.stretched = 0

    def _set(self, sda=None, scl=None):
        if sda is not None:
            self.sda_rel = sda
        if scl is not None:
            self.scl_rel = scl
        self.pads.drive(target=0xFF & ~(((1 - self.sda_rel) << SDA) | ((1 - self.scl_rel) << SCL)))

    async def _wait(self, n):
        for _ in range(n):
            await clock_edge(self.dut)

    def sda(self):
        return bit(self.dut.uio_in.value, SDA)

    async def _scl_up(self, timeout=5000):
        self._set(scl=1)
        for _ in range(timeout):
            await clock_edge(self.dut)
            if bit(self.dut.uio_in.value, SCL):
                return
            self.stretched += 1
        raise AssertionError("SCL held low too long")

    async def start(self):
        self._set(sda=0)
        await self._wait(self.H)
        self._set(scl=0)

    async def write_bit(self, b):
        await self._wait(self.L // 2)
        self._set(sda=b)
        await self._wait(self.L - self.L // 2)
        await self._scl_up()
        await self._wait(self.H)
        self._set(scl=0)

    async def read_bit(self):
        self._set(sda=1)
        await self._wait(self.L)
        await self._scl_up()
        await self._wait(self.H // 2)
        v = self.sda()
        await self._wait(self.H - self.H // 2)
        self._set(scl=0)
        return v

    async def write_byte(self, b):
        for i in range(7, -1, -1):
            await self.write_bit((b >> i) & 1)
        return await self.read_bit()  # 0 = ACK

    async def read_byte(self, ack):
        v = 0
        for _ in range(8):
            v = (v << 1) | await self.read_bit()
        await self.write_bit(0 if ack else 1)
        return v

    async def rstart(self):
        await self._wait(self.L // 2)
        self._set(sda=1)
        await self._wait(self.L - self.L // 2)
        await self._scl_up()
        await self._wait(self.H // 2)
        self._set(sda=0)
        await self._wait(self.H - self.H // 2)
        self._set(scl=0)

    async def stop(self):
        await self._wait(self.L // 2)
        self._set(sda=0)
        await self._wait(self.L - self.L // 2)
        await self._scl_up()
        await self._wait(self.H)
        self._set(sda=1)


RT = (ASM / "i2c_target_rt.asm").read_text(encoding="utf-8")
READY = 5


def reply_of(d):
    return (d + 0x11) & 0xFF


async def rt_host(dut, pads, host):
    """Once the target holds SCL low, read D, put the reply on ui_in, pull READY low."""
    await wait_until(dut, lambda: bit(dut.uio_oe.value, SCL), 20000, "the target to hold SCL")
    d = bitrev(await host.byte(timeout=20000))
    dut.ui_in.value = reply_of(d)
    for _ in range(3):  # ui_in stable >= 2 clocks before READY
        await clock_edge(dut)
    set_host_bit(pads, READY, 0)
    return d


async def rt_round(dut, pads, host, d, low, high, pre=0, answer=True, addr=0x50):
    ctl = I2CController(dut, pads, low, high)
    await ctl._wait(30 + pre)  # bus free time; the target is back in its idle poll
    await ctl.start()
    ack = await ctl.write_byte(addr << 1)
    if addr != 0x50:
        await ctl.stop()
        return ack, None, None, ctl
    assert ack == 0, "address (write) not ACKed"
    assert await ctl.write_byte(d) == 0, "data byte not ACKed"
    hosted = cocotb.start_soon(rt_host(dut, pads, host)) if answer else None
    await ctl.rstart()
    assert await ctl.write_byte((addr << 1) | 1) == 0, "address (read) not ACKed"
    r = await ctl.read_byte(ack=False)
    await ctl.stop()
    seen = await hosted if answer else None
    set_host_bit(pads, READY, 1)
    return ack, r, seen, ctl


async def rt_start(dut):
    pads = await start(dut, RT, od=I2C_OD, host_oe=1 << READY, host_val=1 << READY)
    host = Host(dut, pads, 0x00FF, 15, 6)
    await host.wait_live()
    return pads, host


@cocotb.test()
async def test_i2c_target_round_trip(dut):
    """Target round trip: live host reply from the observed byte, before STOP."""
    pads, host = await rt_start(dut)
    rule = SdaRule(dut)
    for d in (0x5C, 0xA3):
        _, r, seen, ctl = await rt_round(dut, pads, host, d, 20, 20)
        assert seen == d, f"host saw {seen:#04x}, controller wrote {d:#04x}"
        assert r == reply_of(d), f"controller read {r:#04x}, want {reply_of(d):#04x}"
        assert ctl.stretched > 0, "target did not stretch SCL for the host reply"
    rule.stop()
    pads.stop()
    assert rule.high == [], f"chip changed SDA while SCL high: {rule.high}"


@cocotb.test()
async def test_i2c_target_cases(dut):
    """Address mismatch, DJNZ timeout reply 0xFF, JL-race START sweep, 100 kHz at 600 clk/bit."""
    # Address mismatch: NACK and the chip never drives SDA or SCL.
    pads, host = await rt_start(dut)
    rule = SdaRule(dut)
    driven = []

    async def watch():
        while True:
            await clock_edge(dut)
            driven.append(int(dut.uio_oe.value) & I2C_OD)
    w = cocotb.start_soon(watch())
    ack, *_ = await rt_round(dut, pads, host, 0, 20, 20, addr=0x51)
    w.cancel()
    assert ack == 1, "mismatched address was ACKed"
    assert not any(driven), "chip drove SDA/SCL on a mismatched address"
    # Then a matching round trip still works.
    _, r, _, _ = await rt_round(dut, pads, host, 0x42, 20, 20)
    assert r == reply_of(0x42)
    # Timeout: the host never answers -> 0xFF.
    _, r, _, _ = await rt_round(dut, pads, host, 0x17, 20, 20, answer=False)
    assert r == 0xFF, f"timeout reply {r:#04x}, want 0xff"
    await host.byte(timeout=200)  # drain the unanswered byte
    rule.stop()
    pads.stop()
    assert rule.high == [], f"chip changed SDA while SCL high: {rule.high}"

    # JL race: START at 8 phase steps across one idle poll loop.
    for k in range(8):
        pads, host = await rt_start(dut)
        _, r, seen, _ = await rt_round(dut, pads, host, 0x96, 20, 20, pre=k)
        assert (seen, r) == (0x96, reply_of(0x96)), f"phase {k}: seen {seen} reply {r}"
        pads.stop()

    # 100 kHz at 60 MHz: 600 clocks per bit.
    pads, host = await rt_start(dut)
    rule = SdaRule(dut)
    _, r, seen, _ = await rt_round(dut, pads, host, 0xC9, 300, 300)
    rule.stop()
    pads.stop()
    assert (seen, r) == (0xC9, reply_of(0xC9))
    assert rule.high == [], f"chip changed SDA while SCL high: {rule.high}"


# ------------------------------------------------------------------ R27

R27_SRC = """
    LDI  R2, 0x11
    LDI  R3, {rd}
    LDI  R1, 4
    LDI  R0, 0xAA
    LDI  R4, 0x44
    LDI  R5, 8
l:
    OUT  R2, R0, R3
    DJNZ R1, l
    PSET R4, 0, R5
    HALT
"""


@cocotb.test()
async def test_r27_timed_op_then_djnz(dut):
    """Baseline ops only: OUT Rd=2/3 + DJNZ R1 with R1=4 gives exactly 4 OUT windows."""
    for rd in (2, 3):
        pads = await start(dut, R27_SRC.format(rd=rd))
        spy = Spy(dut, djnz=lambda dp: sig(dp, "do_one") and (sig(dp, "op_word") >> 12) == 3,
                  out=lambda dp: sig(dp, "do_start") and (sig(dp, "op_word") >> 12) == 2)
        rows = await trace(dut, 120)
        spy.stop()
        pads.stop()
        # 0xAA LSB first = 0,1,0,1,...: every OUT window toggles uo1 from idle high.
        lv = [1] + [bit(r[0], 1) for r in rows]
        edges = sum(1 for x, y in zip(lv, lv[1:]) if x != y)
        assert not bit(rows[-1][0], 4), f"Rd={rd}: program did not reach the marker"
        if spy.dp is not None:
            assert len(spy.hits["out"]) == 4 and len(spy.hits["djnz"]) == 4,                 f"Rd={rd}: OUT starts {len(spy.hits['out'])}, DJNZ commits {len(spy.hits['djnz'])}"
        assert edges == 4, f"Rd={rd}: {edges} OUT windows on uo1, want 4"


# ------------------------------------------------------------------ R26

R26_SRC = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R4, 0x0F
    LDI  R5, 16
    SMP  R4, R5
""" + go_wait("g") + """
    {mid}
    SMP  R4, R5
    HALT
"""


async def uart_clocked(dut, pads, i, byte, bclk):
    """8N1 on uio[i], each level set right after a clock edge (start bit at the current edge)."""
    for level in [0] + [(byte >> k) & 1 for k in range(8)] + [1]:
        set_host_bit(pads, i, level)
        for _ in range(bclk):
            await clock_edge(dut)


@cocotb.test()
async def test_sampler_rearm_mid_byte(dut):
    """R26: SMP (disarm + re-arm, or re-SMP) mid-byte restarts at sample 0."""
    rx = 7
    for mid in ("SMP  R0, R5", ""):
        pads = await start(dut, R26_SRC.format(mid=mid), host_oe=(1 << rx) | 2, host_val=(1 << rx) | 2)
        host = Host(dut, pads, *MIX8)
        for _ in range(40):
            await clock_edge(dut)
        k_at_cmt = Spy(dut, k=lambda dp: sig(dp, "smp_cmt") and sig(dp, "smp_k") != 0)
        set_host_bit(pads, rx, 0)  # start bit, then data bits 1, 0, 1 ...
        for level in (1, 0, 1):
            for _ in range(16):
                await clock_edge(dut)
            set_host_bit(pads, rx, level)
        for _ in range(8):
            await clock_edge(dut)
        set_host_bit(pads, 1, 0)  # program aborts the byte with SMP
        for _ in range(30):
            await clock_edge(dut)
        set_host_bit(pads, rx, 1)
        for _ in range(40):
            await clock_edge(dut)
        k_at_cmt.stop()
        if k_at_cmt.dp is not None:
            assert k_at_cmt.hits["k"], f"mid='{mid}': no SMP commit with a partial byte"
        spy = Spy(dut, cap=lambda dp: sig(dp, "rxp_v"))
        await uart_clocked(dut, pads, rx, 0xB1, 16)
        got = await host.byte(timeout=400)
        spy.stop()
        assert got == 0xB1, f"mid='{mid}': got {got:#04x}, want 0xb1"
        if spy.dp is not None:
            assert spy.hits["cap"][:1] == [2 + 8 + 8 * 16], f"mid='{mid}': capture at {spy.hits['cap'][:1]}, want E+half+8B = 138"
        pads.stop()


# ------------------------------------------------------------------ R28

R28_SRC = cfg_lines(MIX8[0] & 0xFF, MIX8[0] >> 8, MIX8[1], MIX8[2]) + """
    LDI  R4, 0xA5
    CAP  R4
    LDI  R5, 0x44
    LDI  R6, 16
    LDI  R7, 0x0A
    REL  R5, R6
    SMP  R7, R6
""" + go_wait("g") + """
    SMP  R0, R0
    HCFG R1, R2, R3
    HALT
"""


@cocotb.test()
async def test_serve_vs_invalidating_smp(dut):
    """R28: a serve edge in the clock where SMP makes the config invalid is cancelled."""
    pads = await start(dut, R28_SRC, host_oe=2, host_val=2)
    host = Host(dut, pads, *MIX8)
    spy = Spy(dut, hit=lambda dp: sig(dp, "smp_cmt") and sig(dp, "hr_pending") and sig(dp, "rxp_v")
              and not sig(dp, "serve_d") and not sig(dp, "tx_busy"))
    await wait_pin(dut, 4, 0, 200)  # REL marker S; SMP commits at S+15
    for _ in range(12):  # toggle at S+12 -> serve edge E = S+15
        await clock_edge(dut)
    await host.no_strobe()
    spy.stop()
    if spy.dp is not None:
        assert spy.hits["hit"], "serve condition did not fall in the SMP commit clock"
    set_host_bit(pads, 1, 0)  # disarm the sampler, valid HCFG again
    for _ in range(20):
        await clock_edge(dut)
    d, _ = await host.chunk(timeout=200, latency=3)
    assert d == 0xA5, f"byte after re-enable {d:#04x}, want 0xa5 from chunk 0"
    pads.stop()


# ------------------------------------------------------------------ V29

STATUS6_SRC = cfg_lines(0x00, 0x3C, 14, 7) + """
    LDI  R4, 0x09
    LDI  R2, 16
    SMP  R4, R2
    LDI  R7, 0x66
    LDI  R5, 0x00
    LDI  R3, 4
    LDI  R4, 0xB1
    CAP  R4
    PSET R5, 0, R3
    INW  R7, R0, R3
    LDI  R5, 0x11
    PSET R5, 0, R3
    LDI  R1, 7
    LDI  R2, 0x55
    IN   R7, R0, R3
sh:
    IN   R2, R0, R3
    DJNZ R1, sh
    LDI  R2, 0x44
    OUT  R2, R0, R3
    HALT
"""


@cocotb.test()
async def test_status_pin6_in_inw(dut):
    """Status pin 6 through INW (waits for the overflow) and IN (reads 0 after it)."""
    rx = 1  # sampler on uio1 (pin 9), idle high
    pads = await start(dut, STATUS6_SRC, host_oe=1 << rx, host_val=1 << rx)
    host = Host(dut, pads, 0x3C00, 14, 7)
    await host.wait_live()
    await wait_pin(dut, 0, 0, 200)  # rxp is full; INW on pin 6 now waits
    for _ in range(WINDOW):
        await clock_edge(dut)
        assert bit(dut.uo_out.value, 1), "INW pin 6 finished before any overflow"
    await uart_clocked(dut, pads, rx, 0x5A, 16)  # sampler byte -> dropped, rx_ovf
    await wait_pin(dut, 1, 0, 100)  # INW saw pin 6 go to 0
    await wait_pin(dut, 4, 0, 200)  # IN of pin 6 read 0
    dp = rtl(dut)
    if dp is not None:
        assert int(dp.rx_ovf.value) == 1
    for _ in range(8):  # the OUT hold ends, the core halts
        await clock_edge(dut)
    assert await host.byte(latency=3) == 0xB1, "first byte not intact"
    pads.stop()
