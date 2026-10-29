"""10BASE-T TX: IEEE Manchester on one TX pin via OUTM.

Preamble/SFD + a runt MAC frame (not padded to 64). Complement, if any,
is magnetics / off-chip. The listing drives one pin.
"""

from __future__ import annotations

import zlib
from pathlib import Path

from assemble import pin_desc

# uo_out[6] = TX. One pin, same nibble twice. Not a USB-style pair.
ETH_TX = 6
ETH_PINS = pin_desc(ETH_TX)
ETH_BIT = 6

PREAMBLE = bytes([0x55] * 7)
SFD = bytes([0xD5])

# dest broadcast, local src, ethertype 0x88B5, one data byte.
MAC = bytes.fromhex("ffffffffffff 020000000001 88b5 42")
FCS = (zlib.crc32(MAC) & 0xFFFFFFFF).to_bytes(4, "little")
WIRE = PREAMBLE + SFD + MAC + FCS


def lsb_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(8):
            bits.append((byte >> i) & 1)
    return bits


def ieee_halves(bit: int) -> tuple[int, int]:
    """IEEE 802.3: 1 = low then high, 0 = high then low."""
    if bit:
        return 0, 1
    return 1, 0


def recover_bits(samples: list[int], half: int = ETH_BIT // 2) -> list[int]:
    """Turn pin samples into IEEE data bits. Remainder clocks and 00/11
    half-pairs are illegal Manchester; this helper still drops them, so
    do not use it as a pass/fail. Use expect_runs for wire timing.
    """
    runs: list[tuple[int, int]] = []
    for level in samples:
        if runs and runs[-1][0] == level:
            runs[-1] = (level, runs[-1][1] + 1)
        else:
            runs.append((level, 1))
    halves: list[int] = []
    for level, n in runs:
        for _ in range(n // half):
            halves.append(level)
    bits: list[int] = []
    for i in range(0, len(halves) - 1, 2):
        a, b = halves[i], halves[i + 1]
        if a == 0 and b == 1:
            bits.append(1)
        elif a == 1 and b == 0:
            bits.append(0)
    return bits


def expect_runs(data: bytes = WIRE, clocks: int = ETH_BIT) -> list[tuple[int, int]]:
    """Collapse expected TX levels into (level, clocks) runs."""
    half = clocks // 2
    runs: list[tuple[int, int]] = []
    for bit in lsb_bits(data):
        for level in ieee_halves(bit):
            if runs and runs[-1][0] == level:
                runs[-1] = (level, runs[-1][1] + half)
            else:
                runs.append((level, half))
    return runs


def dmem_text(data: bytes = WIRE) -> str:
    return "\n".join(f"{b:02X}" for b in data) + "\n"


def asm_text(data: bytes = WIRE) -> str:
    lines = [
        "# 10BASE-T TX. IEEE Manchester, OUTM, 6 clocks/bit at 60 MHz.",
        "# One pin: uo[6] (descriptor 0x66). Not D+/D-. Magnetics make the complement.",
        "# Preamble 7*0x55, SFD 0xD5, then runt frame (no 64-byte pad):",
        "#   dest ff:ff:ff:ff:ff:ff  src 02:00:00:00:00:01  type 88b5  data 42",
        "#   FCS little-endian (IEEE CRC32).",
        "# Unrolled LDI+OUTM so halves stay on the 3-clock grid. RX is not in silicon.",
        "",
        ".equ PINS, 0x66",
        ".equ BIT,  6",
        "",
        "    LDI   R1, PINS",
        "    LDI   R3, BIT",
    ]
    for byte in data:
        lines.append(f"    LDI   R0, 0x{byte:02X}")
        for _ in range(8):
            lines.append("    OUTM  R1, R0, R3")
    lines.append("    HALT")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    examples = Path(__file__).resolve().parent / "examples"
    path = examples / "eth_10t.asm"
    path.write_text(asm_text(), encoding="utf-8")
    dmem = examples / "eth_10t_loop.dmem"
    dmem.write_text(dmem_text(), encoding="utf-8")
    print(f"wrote {len(WIRE)} bytes -> {path}")
    print(f"wrote {len(WIRE)} dmem bytes -> {dmem}")
