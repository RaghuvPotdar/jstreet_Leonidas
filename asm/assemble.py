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
OP_PSETH = 0x7


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
    return parse_number(token, symbols)


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
    # bit11 reserved 0, bits10-8 = Rn
    return rn & 0x7


def encode_pset(pin: int, level: int, dur: int) -> int:
    if level not in (0, 1):
        raise ValueError(f"PSET level must be 0 or 1, got {level}")
    if dur < 0 or dur > 128:
        raise ValueError(f"PSET duration must be 0..128, got {dur}")
    coded = 0 if dur == 128 else dur
    if dur != 128 and dur > 127:
        raise ValueError(f"PSET duration must be 1..127 or 128, got {dur}")
    payload = ((level & 1) << 7) | (coded & 0x7F)
    return encode(OP_PSET, pin, payload)


def encode_pseth(pin1: int, pin2: int, level1: int, level2: int, ridx: int) -> int:
    if level1 not in (0, 1) or level2 not in (0, 1):
        raise ValueError("PSETH levels must be 0 or 1")
    if ridx < 0 or ridx > 3:
        raise ValueError(f"PSETH ridx must be 0..3 (R4..R7), got {ridx}")
    # [11:8]=pin1, [7:4]=pin2, [3]=A, [2]=B, [1:0]=idx
    mid = ((pin2 & 0xF) << 4) | ((level1 & 1) << 3) | ((level2 & 1) << 2) | (ridx & 3)
    return encode(OP_PSETH, pin1, mid)


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
                raise ValueError(f"PSET needs pin, level, duration: {raw}")
            words.append(
                encode_pset(
                    parse_number(args[0], symbols),
                    parse_number(args[1], symbols),
                    parse_number(args[2], symbols),
                )
            )
        elif mnemonic == "LOW":
            if len(args) != 2:
                raise ValueError(f"LOW needs pin, duration: {raw}")
            words.append(
                encode_pset(
                    parse_number(args[0], symbols),
                    0,
                    parse_number(args[1], symbols),
                )
            )
        elif mnemonic == "HIGH":
            if len(args) != 2:
                raise ValueError(f"HIGH needs pin, duration: {raw}")
            words.append(
                encode_pset(
                    parse_number(args[0], symbols),
                    1,
                    parse_number(args[1], symbols),
                )
            )
        elif mnemonic == "PSETH":
            # PSETH pin1, pin2, level1, level2, ridx
            # or PSETH pin1, pin2, level1, level2, R4..R7
            if len(args) != 5:
                raise ValueError(
                    f"PSETH needs pin1, pin2, level1, level2, ridx|R4..R7: {raw}"
                )
            pin1 = parse_number(args[0], symbols)
            pin2 = parse_number(args[1], symbols)
            level1 = parse_number(args[2], symbols)
            level2 = parse_number(args[3], symbols)
            last = args[4].upper()
            if re.fullmatch(r"R[4-7]", last):
                ridx = int(last[1]) - 4
            else:
                ridx = parse_number(args[4], symbols)
                if ridx >= 4 and ridx <= 7:
                    ridx = ridx - 4
            words.append(encode_pseth(pin1, pin2, level1, level2, ridx))
        elif mnemonic == "OUT":
            if len(args) != 2:
                raise ValueError(f"OUT needs pin, duration: {raw}")
            words.append(
                encode(
                    OP_OUT,
                    parse_number(args[0], symbols),
                    parse_number(args[1], symbols),
                )
            )
        elif mnemonic == "REL":
            if len(args) != 2:
                raise ValueError(f"REL needs pin, duration: {raw}")
            words.append(
                encode(
                    OP_REL,
                    parse_number(args[0], symbols),
                    parse_number(args[1], symbols),
                )
            )
        elif mnemonic == "DJNZ":
            if len(args) != 2:
                raise ValueError(f"DJNZ needs Rn, target: {raw}")
            rn = parse_reg(args[0], symbols)
            target = parse_number(args[1], symbols)
            words.append(encode(OP_DJNZ, reg_field(rn), target))
        elif mnemonic == "JL":
            if len(args) != 2:
                raise ValueError(f"JL needs pin, target: {raw}")
            words.append(
                encode(
                    OP_JL,
                    parse_number(args[0], symbols),
                    parse_number(args[1], symbols),
                )
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
