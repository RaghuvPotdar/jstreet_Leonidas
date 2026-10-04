#!/usr/bin/env python3
"""Turn IHP standard-cell Verilog into a model Icarus can simulate.

sg13g2_dfrbpq stores its bit in a UDP. The UDP does not read CLK, D, or
RESET_B. It reads delayed_CLK, delayed_D, and delayed_RESET_B. Those wires
have no assign. Their only drivers are the delayed-net arguments of the
$setuphold and $recrem checks inside the specify block.

Icarus does not implement every specify construct in this file (the gate-level
log says "ifnone with an edge-sensitive path is not supported"). When those
timing checks do not drive the delayed wires, the UDP never sees a clock or a
reset, and Q stays X.

This rewrite deletes the specify blocks and connects each delayed_<port> wire
to that port. Combo cells already compute their outputs with gate primitives,
so losing the timing annotation does not change their function. The result is
a zero-delay functional model of the same cells.
"""

import re
import sys
from pathlib import Path


def strip_specify(text: str) -> str:
    return re.sub(r"\bspecify\b.*?\bendspecify\b", "", text, flags=re.S)


def input_names(module_text: str) -> set[str]:
    names: set[str] = set()
    for declaration in re.findall(r"\binput\b([^;]*);", module_text):
        declaration = re.sub(r"\[.*?\]", "", declaration)
        for part in declaration.split(","):
            name = part.strip()
            if name:
                names.add(name)
    return names


def delayed_names(module_text: str) -> list[str]:
    # Preserve declaration order so the assigns are stable.
    seen: list[str] = []
    for name in re.findall(r"\bdelayed_([A-Za-z_][A-Za-z0-9_]*)\b", module_text):
        if name not in seen:
            seen.append(name)
    return seen


def connect_delayed_nets(module_text: str) -> str:
    inputs = input_names(module_text)
    delayed = delayed_names(module_text)
    if not delayed:
        return module_text

    missing = [name for name in delayed if name not in inputs]
    if missing:
        module = re.search(r"\bmodule\s+(\S+)", module_text)
        module_name = module.group(1) if module else "<unknown>"
        raise SystemExit(
            f"{module_name}: delayed nets with no matching input: {', '.join(missing)}"
        )

    assigns = "\n".join(f"  assign delayed_{name} = {name};" for name in delayed)
    wire_decl = re.search(r"^.*\bdelayed_[A-Za-z0-9_]+.*$", module_text, flags=re.M)
    if wire_decl is None:
        raise SystemExit("delayed net is used but never declared")

    insert_at = wire_decl.end()
    return module_text[:insert_at] + "\n" + assigns + module_text[insert_at:]


def transform(stdcell_text: str, udp_text: str | None) -> str:
    body = strip_specify(stdcell_text)
    parts = re.split(r"(?=^\s*module\s+)", body, flags=re.M)
    rewritten = "".join(connect_delayed_nets(part) for part in parts)

    header = (
        "// Generated functional model. Do not edit.\n"
        "// specify blocks removed; delayed_<port> assigned from <port>.\n"
    )
    if udp_text and "primitive ihp_dff_r" not in rewritten:
        return header + udp_text + "\n" + rewritten
    return header + rewritten


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit(
            "usage: make_functional_stdcells.py STDCELL_V OUTPUT [UDP_V]"
        )

    stdcell_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    udp_text = Path(sys.argv[3]).read_text() if len(sys.argv) == 4 else None
    output_path.write_text(transform(stdcell_path.read_text(), udp_text))


if __name__ == "__main__":
    main()
