# Programmability

Leonidas is a dumb pin machine. The opcode is a verb. The protocol is the program. Load a different listing to change protocol.

## Split of responsibility

| In the chip | In the compiler / host |
|---|---|
| Drive pin(s) named by a descriptor for `Rd` clocks | UART / SPI / I2C / USB packet layout |
| Release a descriptor (`REL`) | NRZI, bit stuffing, CRC |
| Shift `Rs` LSB first (`OUT`); `OUTM` flips at `Rd>>1` | Line-level **bytes in dmem**; listing holds **addresses** |
| Count, jump, halt, `JL` on `pin1` | LS vs FS polarity (which pin is high in J) |
| 3R1W so issue is one cycle | Fit non-timed ops (and 2-cycle `LD`) inside the previous hold |
| Two SRAMs: imem `256x16`, dmem `256x8` | Strobe `01`/`10` → imem, `11` → dmem |

No USB opcode, no PID comparator, no protocol-select pin.

## Why three reads

`OUT Rp, Rs, Rd` (and `PSET` / `REL`) must, in the **same** issue cycle:

1. **P** — read the descriptor (which pad(s) to touch)
2. **S** — read the shifter bit (and write the shifted value back)
3. **D** — read the hold count

One read port would serialize those into extra clocks. FS is 5 clocks/bit; that serialization is the bit. 3R1W is still a register file with address inputs, not eight named `r0`–`r7` wires.

## One loop shape

```
LDI  R1, desc        ; two pin nibbles (same pin twice if one pad)
LDI  R3, clocks
LDI  R5, pkt         ; dmem address (compiler), not the payload
LDI  R4, nbytes
L:   LD   R0, [R5]   ; 2 clocks, post-inc R5
     OUT  R1, R0, R3
     DJNZ R4, L
```

UART, SPI, and USB data differ in the descriptor, `R3`, and the dmem image, not the opcode. 10BASE-T TX is `OUTM` with `R3=6` on **one** pin (IEEE Manchester). Complement is off-chip. A `LD` into the shifter arms `OUTM` to refill from dmem every 8 bits during leftover hold, so the listing is `OUTM`+`DJNZ` on **bits** with the first `LD` in idle. `OUT` is unchanged (one bit from a register). `PSET Rp, 0, Rd` with two different pins is both lines low (USB SE0). Sticky pins plus a later `PSET`/`OUT` restore idle J. `LDI` after a timed op does not move the old pin.

## Dmem

`RM_IHPSG13_1P_256x8_c3_bm_bist`. Byte address = one `Rn` (0–255). No shift.

Host: `ui_in` is the byte. `uio[1:0]`:

| Strobe | Goes to |
|---|---|
| `00` | idle |
| `01` | imem (low then high byte of a 16-bit word) |
| `10` | imem, then **start** once that word is complete |
| `11` | dmem[`wptr`], then `wptr++` (wraps) |

`11` is a write to dmem, not a sticky “mode bit.” `01`/`10` always mean imem.

Fill **dmem before** the `10` that starts the program. Both macros are 1-port: no host write to dmem while `pc` is fetching. `wptr` resets on `rst_n`.

`LD Rn, [Rm]` is two clocks (REN + `Rm++`, then `Rn ← dout`). Hide it in a hold ≥ 3. Current USB dummy listings still `LDI` a byte into `R0`.

## Clock and timing

60 MHz target → LS = 40 clocks/bit, FS = 5, 10BASE-T TX = 6 (`OUTM`). Pins are sticky: extra instructions between timed ops stretch the previous level. If the gap does not fit in the hold, shorten that hold (FS: last `OUT` before a mid-packet `LDI` uses 4 so the tail restores 5). LS 40 hides an `LDI`. 10BASE-T leftover hold is 5: `DJNZ` plus the armed `OUTM` dmem refill.

`JL` sees `uio` +2 clocks (2-flop sync).

## FS

**TX** at 5 clocks/bit is required. **RX** at 5 will not be software-sampled.

## Compiler pipeline (planned)

```
protocol dict  →  protocol lowering  →  ISA asm + dmem image  →  assemble.py  →  hex
```

Two artifacts: instruction words and payload bytes. The listing contains addresses into dmem.

## What we do not do

- Protocol-named opcodes, XOR/MOV, PID hardware, auto detect.
- Spending `1000`–`1111` for foresight. Next slot is RX verbs that unblock a program.

## Open (next)

- More protocol listings on the verbs we have. Refine the ISA after that.
- Compiler (protocol → asm + dmem).
- USB dummy packets via dmem + `LD` instead of unrolled `LDI`.
- 10BASE-T listing (NLP + frame via `OUTM`); RX later.
- RX: `IN` / `JH` if `JL` is not enough; FS RX sampler if we take that on.
- Multi-protocol / second SM (not lockstep dual-issue on one RF).
