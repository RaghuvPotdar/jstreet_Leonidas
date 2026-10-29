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
| `0010` | `OUT` | `Rp`(3) ‖ `Rs`(3) ‖ `Rd`(3) ‖ `M` ‖ 0 |
| `0011` | `DJNZ` | `0` ‖ `Rn`(3) ‖ target(8) |
| `0100` | `HALT` | ignored |
| `0101` | `REL` | `Rp`(3) ‖ `Rd`(3) ‖ 0 |
| `0110` | `JL` | `Rp`(3) ‖ `0` ‖ target(8) |
| `0111` | `LD` | `Rn`(3) ‖ `Rm`(3) ‖ 0 |
| `1000`–`1111` | unused | ignored |

## Register file

Eight architectural registers, `R0`–`R7`, each 8 bits. The file is **3R1W**: combinational reads on ports **P** (descriptor), **S** (shifter / `DJNZ`), **D** (duration); one clocked write.

A timed op (`PSET` / `OUT` / `REL`) issues in **one cycle** and needs those three values at once. That is why there are three read ports, not one. Serializing the reads would add issue clocks and break 5-clock FS bits.

`LDI` writes a register (descriptors, counts, **dmem addresses**). Payload bytes do not live in the instruction stream. They live in a second SRAM (`256x8` dmem). The compiler emits `LDI Rn, addr`; `LD Rn, [Rm]` reads `dmem[Rm]` and post-increments `Rm`. Loading either SRAM is the host strobe path in [info.md](info.md).

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

Pin numbers are 4 bits. Pins 0–7 are `uo_out[0]`–`[7]`. Pins 8–15 are `uio[0]`–`[7]`. `ui_in` is not in the pin space. `uo_out` resets high. `uio` resets to inputs.

USB D+/D− is `0x54` (pins 5 and 4). One pin, e.g. D− only, is `0x55`.

## Duration

`Rd` is a register. That is the baud / bit-time. There is no baud generator. `LDI R3, N` then `OUT …, R3` / `PSET …, R3` holds the pin for `N` clocks (`N=0` means 256). The listing picks `N`; the chip does not.

On issue, `hold ← Rd−1` (a datapath flop, not dmem, not the shifter). `hold` counts down every clock. The start clock is one of the duration clocks, so leftover is `Rd−1`. After `hold` hits 0 the pin **keeps its level** until a later op writes that same pin.

Driving a `uio` pin turns `uio_oe` on. `REL` turns it off (`uo` is driven 0).

## Fetch / `pc` / `asked`

imem is 1-port SRAM: address this clock, word two clocks later. `issue` sends `issue_addr` into that SRAM. `asked` is `issue` delayed two flops: the word on `instr` belongs to `asked_addr`. `pc` is **the address being issued**, not the op that is executing. `shown` holds the last `pc` when `issue` is 0.

A timed op (`PSET` / `OUT` / `REL`) issues the next sequential address on its start clock, then keeps issuing that same address every leftover clock until the word arrives and is buffered (`!buf_v`). Two consecutive `issue`s of the same address → **`asked` high for two clocks** and `instr` repeats. Once `buf_v` is set, leftover clocks do not re-issue.

At `hold==2`, a buffered non-pin op (`DJNZ` / `LDI` / `JL`) may issue its **target** (or `addr+1`) so the next timed op is already in flight. At `hold==1` that op commits (RF write). Execute of a timed op is `do_start` (or `do_defer` at `hold==1` if the next op is also timed).

`next_addr` is written by execute: `op_addr+1`, or the `DJNZ`/`JL` target. That is what advances `pc`.

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
15    12 11  9 8   6 5   3 2 1 0
| 0010  |  Rp |  Rs |  Rd |M| 0 |
```

Low nibble ← `Rs[0]`; if the two pin fields differ, high nibble ← `~Rs[0]`; then `Rs ← {0, Rs[7:1]}`. Wait `Rd` clocks.

`M` (`[2]`) is IEEE 802.3 Manchester. Issue drives `~Rs[0]` (pin2 `Rs[0]`); after `Rd >> 1` clocks those pins XOR, so a `1` is low then high and a `0` is high then low. `Rd=0` is 256 clocks, flip at 128. `Rd=1` never flips. Assembler: `OUT` has `M=0`, `OUTM` has `M=1`. `[1:0]` stay 0.

UART / SPI duplicate one pin in both nibbles. USB puts D+ and D− in the two nibbles.

**UART** (`asm/examples/uart.asm`): idle high, `PSET` low = start, eight `OUT`s = data LSB first, `PSET` high = stop. The byte is `LDI R0, 0xB1` — **not dmem**. `R3` is clocks/bit (16 in that listing; change the immediate). `R1` is the bit count (`DJNZ`). `R0` is the shifter: `LDI` fills it; each `OUT` writes `{0, R0[7:1]}`. After eight `OUT`s `R0` is 0. Nothing auto-reloads on `OUT`. The bit loop stops because `DJNZ R1` hits 0, not because the shifter is empty.

Small immediates can stay `LDI R0, byte`. Long payloads use dmem:

```
LDI  R5, pkt        ; address in dmem, not the bytes
LDI  R4, nbytes
L:   LD   R0, [R5]  ; 2 clocks: REN+R5++ then R0 ← dout
     OUT  R1, R0, R3
     DJNZ R4, L
```

`LD` into `Rs` also arms an **OUTM stream**. After 8 `OUTM`s of that `Rs`, leftover hold loads `dmem[dptr]` into `Rs` and write-backs `Rm`. Count is 8 issues, not `Rs==0` (`0x01` is empty after one shift). `OUT` does not refill. `LDI` into `Rs` disarms. First byte is a software `LD` in idle (legal high). Last `OUTM` prefetches one extra dmem byte. Needs leftover hold ≥ 3 (`Rd` ≥ 4).

10BASE-T TX is `OUTM` with `R3=6` (one data bit per issue) and a bit-count `DJNZ`. RX is not in silicon.

NRZI and stuffing are compiler work (bytes in dmem are line levels). Manchester polarity is IEEE in the chip.

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

## LD — `0111`

```
15    12 11  9 8   6 5        0
| 0111  |  Rn |  Rm |    0     |
```

`Rn ← dmem[Rm]`, then `Rm ← Rm + 1`. Two clocks because the file is 1W: cycle 0 asserts REN and writes `Rm`; cycle 1 writes `Rn` from `A_DOUT`. Hide a software `LD` inside a hold of 3 or more, not on an FS bit boundary. The same `LD` arms `OUTM` to consume the rest of dmem during leftover hold (see `OUT`).

## Unused opcodes — `1000` through `1111`

Eight free opcodes. No-op: next word. Next spend is RX (`IN` / `JH`) if `JL` is not enough.

## Scope notes

- **FS TX** is in scope (5 clocks/bit). **FS RX is not** until a hardware sampler.
- No PID comparator, no protocol-select pin, no ALU. A PID check is a program of `JL`s.
- No `PSETH` / `OUTD`. Two pins live in the descriptor nibbles.
- No circular imem. Payload is dmem (`256x8`), 8-bit address in an `Rn`.
