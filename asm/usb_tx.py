"""Dummy USB TX: packet bytes → NRZI line levels → descriptor OUT/PSET.

No bit stuffing, no real CRC. See docs/programmability.md.
"""

from __future__ import annotations

from assemble import (
    OP_HALT,
    OP_LDI,
    encode,
    encode_out,
    encode_pset,
    pin_desc,
    reg_field,
)

USB_DP = 4
USB_DM = 5
USB_PINS = pin_desc(USB_DP, USB_DM)

PID_OUT = 0x1
PID_ACK = 0x2
PID_DATA0 = 0x3
PID_SOF = 0x5
PID_IN = 0x9
PID_NAK = 0xA
PID_DATA1 = 0xB
PID_SETUP = 0xD
PID_STALL = 0xE

SYNC_BITS = [0, 0, 0, 0, 0, 0, 0, 1]


def pid_byte(nibble: int) -> int:
    n = nibble & 0xF
    return n | ((~n & 0xF) << 4)


def bytes_to_lsb_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(8):
            bits.append((byte >> i) & 1)
    return bits


def nrzi_states(bits: list[int], j, k, start):
    cur = start
    out = []
    for bit in bits:
        if bit == 0:
            cur = k if cur == j else j
        out.append(cur)
    return out


def polarity(fs: bool):
    se0 = (0, 0)
    if fs:
        return (1, 0), (0, 1), se0
    return (0, 1), (1, 0), se0


def bit_times(fs: bool) -> tuple[int, int]:
    bit = 5 if fs else 40
    return bit, 2 * bit


DUMMY_PACKETS: dict[str, bytes] = {
    "ack": bytes([pid_byte(PID_ACK)]),
    "nak": bytes([pid_byte(PID_NAK)]),
    "stall": bytes([pid_byte(PID_STALL)]),
    "out": bytes([pid_byte(PID_OUT), 0x28, 0x17]),
    "in": bytes([pid_byte(PID_IN), 0x51, 0x2A]),
    "setup": bytes([pid_byte(PID_SETUP), 0x00, 0x10]),
    "sof": bytes([pid_byte(PID_SOF), 0x34, 0x56]),
    "data0": bytes([pid_byte(PID_DATA0), 0xDE, 0xAD, 0xBE, 0xEF, 0x12, 0x34]),
    "data1": bytes([pid_byte(PID_DATA1), 0x01, 0x02, 0x03, 0xAB, 0xCD]),
}


def packet_line_states(payload: bytes, j, k, se0) -> list[tuple[int, int]]:
    bits = SYNC_BITS + bytes_to_lsb_bits(payload)
    body = nrzi_states(bits, j, k, start=j)
    return [j] + body + [se0, j]


def merge_runs(states, bit_time: int, se0_time: int, se0) -> list[tuple]:
    runs: list[tuple] = []
    for state in states:
        dur = se0_time if state == se0 else bit_time
        if runs and runs[-1][0] == state:
            runs[-1] = (state, runs[-1][1] + dur)
        else:
            runs.append((state, dur))
    return runs


def levels_to_bytes(body) -> list[int]:
    bits = [state[0] & 1 for state in body]
    if len(bits) % 8:
        raise ValueError(f"body length {len(bits)} is not a multiple of 8")
    out = []
    for i in range(0, len(bits), 8):
        byte = 0
        for n, bit in enumerate(bits[i : i + 8]):
            byte |= (bit & 1) << n
        out.append(byte)
    return out


def program_from_states(
    states, bit_time: int, se0_time: int, j, se0, pins: int = USB_PINS
) -> list[int]:
    if states[0] != j or states[-2] != se0 or states[-1] != j:
        raise ValueError("expected [J] + body + [SE0, J]")
    body = states[1:-2]
    bytes_ = levels_to_bytes(body)
    j_bit = j[0] & 1
    gap = bit_time - 1 if bit_time <= 5 else bit_time

    words = [
        encode(OP_LDI, reg_field(1), pins),
        encode(OP_LDI, reg_field(3), bit_time),
        encode(OP_LDI, reg_field(5), se0_time),
        encode(OP_LDI, reg_field(6), gap),
        encode(OP_LDI, reg_field(0), j_bit),
        encode_out(1, 0, 6 if bit_time <= 5 else 3),
    ]
    for i, byte in enumerate(bytes_):
        words.append(encode(OP_LDI, reg_field(0), byte))
        more = i + 1 < len(bytes_)
        for n in range(8):
            rd = 6 if (n == 7 and more and bit_time <= 5) else 3
            words.append(encode_out(1, 0, rd))
    words.append(encode_pset(1, 0, 5))
    words.append(encode(OP_LDI, reg_field(0), j_bit))
    words.append(encode_out(1, 0, 3))
    words.append(encode(OP_HALT, 0, 0))
    return words


def build_dummy_tx(name: str, *, fs: bool) -> tuple[list[int], list[tuple], int, int]:
    if name not in DUMMY_PACKETS:
        raise KeyError(f"unknown dummy packet {name!r}; have {sorted(DUMMY_PACKETS)}")
    j, k, se0 = polarity(fs)
    bit_time, se0_time = bit_times(fs)
    states = packet_line_states(DUMMY_PACKETS[name], j, k, se0)
    words = program_from_states(states, bit_time, se0_time, j, se0)
    expect = merge_runs(states, bit_time, se0_time, se0)
    if len(words) > 256:
        raise ValueError(f"{name} needs {len(words)} words; imem holds 256")
    return words, expect, bit_time, se0_time
