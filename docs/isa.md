# ISA

A program is a list of 16-bit words in a 256-word memory. The address of a word is 8 bits. The opcode is bits 15 through 12. The other bits mean whatever that opcode says.

The first byte stored for a word is bits 7 through 0. The second byte is bits 15 through 8. How those bytes are strobed in is in [info.md](info.md).

```
15        12 11        8 7         0
+-----------+-----------+-----------+
| opcode    | payload, per opcode   |
+-----------+-----------+-----------+
```

| Opcode | Name | Encoding |
|---|---|---|
| `0000` | `LDI` | `0` ‖ `Rn`(3) ‖ imm(8) |
| `0001` | `PSET` | `Rp`(3) ‖ `L` ‖ `Rd`(3) ‖ 0 |
| `0010` | `OUT` | `Rp`(3) ‖ `Rs`(3) ‖ `Rd`(3) ‖ 0 |
| `0011` | `DJNZ` | `0` ‖ `Rn`(3) ‖ target(8) |
| `0100` | `HALT` | ignored |
| `0101` | `REL` | `Rp`(3) ‖ `Rd`(3) ‖ 0 |
| `0110` | `JL` | `Rp`(3) ‖ `0` ‖ target(8) |
| `0111`–`1111` | unused | ignored |

## Register file

Eight architectural registers, `R0`–`R7`, each 8 bits. The file is **3R1W**: combinational reads on ports **P** (descriptor), **S** (shifter / `DJNZ`), **D** (duration); one clocked write.

A timed op (`PSET` / `OUT` / `REL`) issues in **one cycle** and needs those three values at once. That is why there are three read ports, not one. Serializing the reads would add issue clocks and break 5-clock FS bits.

`LDI` only writes the file. Loading SRAM is still the host strobe path.

A register is read only when an op **issues**. Pin levels live in `uo` / `uio` / `oe` flops after that. `LDI` into a register does not change a pin that already holds a level. Overwriting a descriptor does not release the old pin — `PSET` / `REL` that pin first.

## Pin descriptor

An 8-bit descriptor is two pin numbers:

```
7        4 3        0
|  pin    |  pin    |
```

Write the same pin in both nibbles for one pin. Write two different pins to touch both in one op. There is no pair type and no 2p/2p+1 index.

- `PSET`: both fields get `L` (a duplicated field is one write).
- `OUT`: low nibble ← `Rs[0]`; if the nibbles differ, high nibble ← `~Rs[0]`.
- `REL`: release every distinct pin in the descriptor.
- `JL`: tests the low nibble.

Pin numbers are 4 bits. Pins 0–7 are `uo_out[0]`–`[7]`. Pins 8–15 are `uio[0]`–`[7]`. **`ui_in` is not in the pin space**. `uo_out` resets high. `uio` resets to inputs.

USB D+/D− is `0x54` (pins 5 and 4). One pin, e.g. D− only, is `0x55`.

## Duration

`Rd` is a register. `0` means 256 clocks. The start clock is one of the duration clocks. After the hold, the pin **keeps its level** until a later op writes that same pin.

Driving a `uio` pin turns `uio_oe` on. `REL` turns it off (`uo` is driven 0).

## LDI — `0000`

```
15    12 11 10     8 7          0
| 0000  | 0 |  Rn  | immediate |
```

Writes the immediate into `Rn`.

## PSET — `0001`

```
15    12 11  9 8 7   5 4     0
| 0001  |  Rp |L|  Rd |  0    |
```

Drive every distinct pin in `Rp` to `L`. Wait `Rd` clocks.

## OUT — `0010`

```
15    12 11  9 8   6 5   3 2  0
| 0010  |  Rp |  Rs |  Rd | 0  |
```

Low nibble ← `Rs[0]`; if the two pin fields differ, high nibble ← `~Rs[0]`; then `Rs ← {0, Rs[7:1]}`. Wait `Rd` clocks.

UART / SPI duplicate one pin in both nibbles. USB puts D+ and D− in the two nibbles. Same loop:

```
LDI  R0, byte
LDI  R4, 8
L:   OUT  R1, R0, R3
     DJNZ R4, L
```

NRZI and stuffing are compiler work (bytes in `R0` are line levels).

## DJNZ — `0011`

```
15    12 11 10     8 7          0
| 0011  | 0 |  Rn  |   target  |
```

`Rn ← Rn - 1`. If not 0, jump to `target`.

## HALT — `0100`

Stops new issue. An in-progress hold finishes. Pins stay. `running` stays set.

## REL — `0101`

```
15    12 11  9 8   6 5        0
| 0101  |  Rp |  Rd |    0     |
```

Release every distinct pin in `Rp`. Wait `Rd` clocks.

## JL — `0110`

```
15    12 11  9 8 7          0
| 0110  |  Rp |0|   target   |
```

If `pin1` of `Rp` reads 0 on `uio`, jump; else fall through. `uo_out` reads as 1. Sample is **two flops** behind the pad.

## Unused opcodes — `0111` through `1111`

Nine free opcodes. No-op: next word. Next spend is RX (`IN` / `JH`) if `JL` is not enough.

## Scope notes

- **FS TX** is in scope (5 clocks/bit). **FS RX is not** until a hardware sampler.
- No PID comparator, no protocol-select pin, no ALU. A PID check is a program of `JL`s.
- No `PSETH` / `OUTD`. Two pins live in the descriptor nibbles.
