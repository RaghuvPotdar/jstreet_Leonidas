# ISA

A program is a list of 16-bit words in a 256-word memory. The address of a word is 8 bits. The opcode is bits 15 through 12. The other bits mean whatever that opcode says.

The first byte stored for a word is bits 7 through 0. The second byte is bits 15 through 8. How those bytes are strobed in is in [info.md](info.md).

```
15        12 11        8 7         0
+-----------+-----------+-----------+
| opcode    | payload, per opcode   |
+-----------+-----------+-----------+
```

| Opcode | Name | Bits 11–8 | Bits 7–0 |
|---|---|---|---|
| `0000` | `LDI` | `0` ‖ `Rn` (3 bits) | immediate byte |
| `0001` | `PSET` | pin | level + duration (see below) |
| `0010` | `OUT` | pin | duration |
| `0011` | `DJNZ` | `0` ‖ `Rn` (3 bits) | jump target |
| `0100` | `HALT` | ignored | ignored |
| `0101` | `REL` | pin | duration |
| `0110` | `JL` | pin | jump target |
| `0111` | `PSETH` | dual-pin snap + wait index (see below) |
| `1000`–`1111` | unused | ignored | ignored |

## Register file

Eight architectural registers, `R0`–`R7`, each 8 bits. There is no separate shifter or `X` outside this file.

| Regs | Conventional use |
|---|---|
| `R0`–`R3` | Prefer for data / loop counts. **`OUT` reads `R0`** as the shift register (bit 0 out, shift right, fill 0). |
| `R4`–`R7` | Prefer for **durations** consumed by `PSETH`. |

The compiler allocates and tracks free regs. `PSETH` can only name four wait sources (2-bit index); those map to **`R4`–`R7`** (`ridx 00` → `R4`, …, `11` → `R7`). No way around that with the current `PSETH` layout.

`LDI` only writes the register file. Loading the program into SRAM is still the host strobe path, not `LDI`.

## Pins and duration

A pin number is 4 bits. Pins 0 through 7 are `uo_out[0]` through `uo_out[7]`. Pins 8 through 15 are `uio[0]` through `uio[7]`. `ui_in` cannot be driven. `uo_out` resets high. `uio` resets to inputs.

Timed ops wait for a duration in chip clocks. The clock that starts the level is one of those clocks. When the wait ends, the pin **keeps its level** until a later instruction writes that same pin.

`PSET`, `OUT`, `REL`, and `PSETH` are timed (see each). Driving a `uio` pin with `PSET`, `OUT`, or `PSETH` turns that bit of `uio_oe` on. `REL` turns it off.

## LDI — `0000`

```
15    12 11 10     8 7          0
| 0000  | 0 |  Rn  | immediate |
```

Writes the immediate into `Rn` (`Rn` is bits 10–8). Bit 11 is reserved (`0`).

## PSET — `0001`

```
15    12 11    8 7 6          0
| 0001  |  pin  |L| duration  |
```

- **L (bit 7):** level (`0` or `1`).
- **duration (bits 6–0):** hold length. `0` means 128 clocks. (Compiler should
  prefer explicit counts; silicon still defines `0`.)

Single-pin set + wait. For one-pin protocols (UART/SPI edges) and for raising idle **J** after USB SE0.

## OUT — `0010`

Uses **`R0`** as the shift register. Drives the pin from `R0[0]`, then `R0 ← {0, R0[7:1]}`. Waits for the duration in bits 7–0 (`0` means 256 clocks).

MSB-first on the wire is a compiler bit-reverse before `LDI R0, …`.

## DJNZ — `0011`

```
15    12 11 10     8 7          0
| 0011  | 0 |  Rn  |   target  |
```

`Rn ← Rn - 1` (wraps). If the result is not 0, next instruction is `target`; else the next word. Bit 11 reserved (`0`). Nested loops use different `Rn`s.

## HALT — `0100`

Stops advancing the program. A level already in progress finishes its duration. Pins stay. **`halted`** stops new issue; `running` stays set.

## REL — `0101`

Releases a `uio` pin (`oe` off, driven bit 0), waits duration bits 7–0 (`0` ⇒ 256). Pull-up defines the line. On `uo_out`, drives 0.

## JL — `0110`

If the `uio` pin reads 0, jump to bits 7–0; else fall through. `uo_out` reads as 1.

## PSETH — `0111`

```
15    12 11    8 7     4 3 2 1 0
| 0111  |  pin1 |  pin2 |A|B|idx|
```

- **pin1, pin2:** two pads (each 4 bits).
- **A, B:** levels for pin1 and pin2.
- **idx (bits 1–0):** which duration reg → **`R4+idx`**.

In one instruction, drives both pins to A/B and waits `R[4+idx]` clocks. Used when two lines must change together (e.g. USB J/K/SE0). Sticky afterward; EOP can SE0 here, then `PSET` to idle J.

## Unused opcodes — `1000` through `1111`

Eight free opcodes. No-op: next word.
