#!/usr/bin/env python3
"""Assemble a Leonidas listing into a hex file of 16-bit words.

See docs/isa.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OP_LDI = 0x0
OP_PSET = 0x1
OP_OUT = 0x2
OP_DJNZ = 0x3
OP_HALT = 0x4
OP_REL = 0x5
OP_JL = 0x6
OP_LD = 0x7


def parse_number(token: str, symbols: dict[str, int]) -> int:
    if token in symbols:
        return symbols[token]
    if token.lower().startswith("0x"):
        return int(token, 16)
    if token.lower().startswith("0b"):
        return int(token, 2)
    return int(token, 10)


def parse_reg(token: str, symbols: dict[str, int]) -> int:
    t = token.upper()
    if re.fullmatch(r"R[0-7]", t):
        return int(t[1])
    n = parse_number(token, symbols)
    if n < 0 or n > 7:
        raise ValueError(f"register must be R0..R7, got {token}")
    return n


def strip_comment(line: str) -> str:
    if "#" in line:
        line = line[: line.index("#")]
    if ";" in line:
        line = line[: line.index(";")]
    return line.strip()


def encode(opcode: int, field: int, payload: int) -> int:
    return ((opcode & 0xF) << 12) | ((field & 0xF) << 8) | (payload & 0xFF)


def reg_field(rn: int) -> int:
    if rn < 0 or rn > 7:
        raise ValueError(f"register must be R0..R7, got {rn}")
    return rn & 0x7


def pin_desc(pin1: int, pin2: int | None = None) -> int:
    """Descriptor byte: [7:4] and [3:0] are pin numbers. Omit pin2 to duplicate pin1."""
    if pin2 is None:
        pin2 = pin1
    if pin1 < 0 or pin1 > 15 or pin2 < 0 or pin2 > 15:
        raise ValueError(f"pin must be 0..15, got {pin1},{pin2}")
    return ((pin2 & 0xF) << 4) | (pin1 & 0xF)


def encode_pset(rp: int, level: int, rd: int) -> int:
    if level not in (0, 1):
        raise ValueError(f"PSET level must be 0 or 1, got {level}")
    # [11:9]=Rp, [8]=L, [7:5]=Rd
    field = ((rp & 7) << 1) | (level & 1)
    payload = (rd & 7) << 5
    return encode(OP_PSET, field, payload)


def encode_out(rp: int, rs: int, rd: int, invert: bool = False) -> int:
    # [11:9]=Rp, [8:6]=Rs, [5:3]=Rd, [2]=mid-hold invert
    word = (OP_OUT << 12) | ((rp & 7) << 9) | ((rs & 7) << 6) | ((rd & 7) << 3)
    if invert:
        word |= 1 << 2
    return word


def encode_rel(rp: int, rd: int) -> int:
    # [11:9]=Rp, [8:6]=Rd
    return (OP_REL << 12) | ((rp & 7) << 9) | ((rd & 7) << 6)


def encode_jl(rp: int, target: int) -> int:
    # [11:9]=Rp, [7:0]=target
    return (OP_JL << 12) | ((rp & 7) << 9) | (target & 0xFF)


def encode_ld(rn: int, rm: int) -> int:
    # [11:9]=Rn dest, [8:6]=Rm addr (post-inc)
    return (OP_LD << 12) | ((rn & 7) << 9) | ((rm & 7) << 6)


def parse_mem_reg(token: str, symbols: dict[str, int]) -> int:
    t = token.strip()
    if t.startswith("[") and t.endswith("]"):
        t = t[1:-1].strip()
    return parse_reg(t, symbols)


def assemble(text: str) -> list[int]:
    symbols: dict[str, int] = {}
    lines = [strip_comment(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    addr = 0
    for raw in lines:
        if raw.lower().startswith(".equ"):
            _, rest = raw.split(None, 1)
            name, value = [part.strip() for part in rest.split(",", 1)]
            symbols[name] = parse_number(value, symbols)
            continue
        if raw.endswith(":"):
            name = raw[:-1].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ValueError(f"bad label: {name}")
            symbols[name] = addr
            continue
        addr += 1

    words: list[int] = []
    for raw in lines:
        if raw.lower().startswith(".equ") or raw.endswith(":"):
            continue
        parts = re.split(r"[\s,]+", raw)
        mnemonic = parts[0].upper()
        args = parts[1:]

        if mnemonic == "HALT":
            words.append(encode(OP_HALT, 0, 0))
        elif mnemonic == "LDI":
            if len(args) != 2:
                raise ValueError(f"LDI needs Rn, imm: {raw}")
            rn = parse_reg(args[0], symbols)
            imm = parse_number(args[1], symbols)
            words.append(encode(OP_LDI, reg_field(rn), imm))
        elif mnemonic == "PSET":
            if len(args) != 3:
                raise ValueError(f"PSET needs Rp, level, Rd: {raw}")
            words.append(
                encode_pset(
                    parse_reg(args[0], symbols),
                    parse_number(args[1], symbols),
                    parse_reg(args[2], symbols),
                )
            )
        elif mnemonic == "LOW":
            if len(args) != 2:
                raise ValueError(f"LOW needs Rp, Rd: {raw}")
            words.append(
                encode_pset(parse_reg(args[0], symbols), 0, parse_reg(args[1], symbols))
            )
        elif mnemonic == "HIGH":
            if len(args) != 2:
                raise ValueError(f"HIGH needs Rp, Rd: {raw}")
            words.append(
                encode_pset(parse_reg(args[0], symbols), 1, parse_reg(args[1], symbols))
            )
        elif mnemonic in ("OUT", "OUTM"):
            if len(args) != 3:
                raise ValueError(f"{mnemonic} needs Rp, Rs, Rd: {raw}")
            words.append(
                encode_out(
                    parse_reg(args[0], symbols),
                    parse_reg(args[1], symbols),
                    parse_reg(args[2], symbols),
                    invert=(mnemonic == "OUTM"),
                )
            )
        elif mnemonic == "REL":
            if len(args) != 2:
                raise ValueError(f"REL needs Rp, Rd: {raw}")
            words.append(
                encode_rel(parse_reg(args[0], symbols), parse_reg(args[1], symbols))
            )
        elif mnemonic == "DJNZ":
            if len(args) != 2:
                raise ValueError(f"DJNZ needs Rn, target: {raw}")
            rn = parse_reg(args[0], symbols)
            target = parse_number(args[1], symbols)
            words.append(encode(OP_DJNZ, reg_field(rn), target))
        elif mnemonic == "JL":
            if len(args) != 2:
                raise ValueError(f"JL needs Rp, target: {raw}")
            words.append(
                encode_jl(parse_reg(args[0], symbols), parse_number(args[1], symbols))
            )
        elif mnemonic == "LD":
            if len(args) != 2:
                raise ValueError(f"LD needs Rn, [Rm]: {raw}")
            words.append(
                encode_ld(parse_reg(args[0], symbols), parse_mem_reg(args[1], symbols))
            )
        else:
            raise ValueError(f"unknown instruction: {mnemonic}")

    if len(words) > 256:
        raise ValueError(f"program has {len(words)} words; memory holds 256")
    return words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("-q", "--questa", action="store_true")
    args = parser.parse_args()

    words = assemble(args.source.read_text(encoding="utf-8"))
    text = "\n".join(f"{word:04X}" for word in words) + "\n"

    out = args.output
    if args.questa and out is None:
        out = Path(__file__).resolve().parent.parent / "questa" / "program.hex"
    if out is None:
        sys.stdout.write(text)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {len(words)} words to {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
