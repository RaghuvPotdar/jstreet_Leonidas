"""10BASE-T TX: IEEE Manchester on TD+/TD- via OUTM.

Preamble/SFD + a runt MAC frame (not padded to 64). Line coding is in
the chip (OUTM). This module is the bytes and the expected pin levels.
"""

from __future__ import annotations

import zlib
from pathlib import Path

from assemble import pin_desc

# uo_out[6] = TD+, uo_out[7] = TD-
ETH_TP = 6
ETH_TN = 7
ETH_PINS = pin_desc(ETH_TP, ETH_TN)
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


def ieee_half(bit: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """IEEE 802.3: 1 = low→high on TD+, 0 = high→low. TD- is ~TD+."""
    if bit:
        return (0, 1), (1, 0)
    return (1, 0), (0, 1)


def expect_runs(data: bytes = WIRE, clocks: int = ETH_BIT) -> list[tuple[tuple[int, int], int]]:
    """Collapse expected (tdp, tdn) samples into (state, clocks) runs."""
    half = clocks // 2
    runs: list[tuple[tuple[int, int], int]] = []
    for bit in lsb_bits(data):
        first, second = ieee_half(bit)
        for state in (first, second):
            if runs and runs[-1][0] == state:
                runs[-1] = (state, runs[-1][1] + half)
            else:
                runs.append((state, half))
    return runs


def asm_text(data: bytes = WIRE) -> str:
    lines = [
        "# 10BASE-T TX. IEEE Manchester, OUTM, 6 clocks/bit at 60 MHz.",
        "# TD+=pin6, TD-=pin7 (descriptor 0x76). R0 shifter, R1 pins, R3 duration.",
        "# Preamble 7*0x55, SFD 0xD5, then runt frame (no 64-byte pad):",
        "#   dest ff:ff:ff:ff:ff:ff  src 02:00:00:00:00:01  type 88b5  data 42",
        "#   FCS little-endian (IEEE CRC32).",
        "# Unrolled LDI+OUTM so halves stay on the 3-clock grid. RX is not in silicon.",
        "",
        ".equ PINS, 0x76",
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
    path = Path(__file__).resolve().parent / "examples" / "eth_10t.asm"
    text = asm_text()
    path.write_text(text, encoding="utf-8")
    print(f"wrote {len(WIRE)} bytes -> {path}")
