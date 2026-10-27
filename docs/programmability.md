# Programmability

Leonidas is a dumb pin machine. The opcode is a verb. The protocol is the program. Load a different listing to change protocol.

## Split of responsibility

| In the chip | In the compiler / host |
|---|---|
| Drive pin(s) named by a descriptor for `Rd` clocks | UART / SPI / I2C / USB packet layout |
| Release a descriptor (`REL`) | NRZI, bit stuffing, CRC |
| Shift `Rs` LSB first (`OUT`) | Line-level bytes in `R0` |
| Count, jump, halt, `JL` on `pin1` | LS vs FS polarity (which pin is high in J) |
| 3R1W so issue is one cycle | Fit non-timed ops inside the previous hold |

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
LDI  R0, byte
LDI  R4, 8
L:   OUT  R1, R0, R3
     DJNZ R4, L
```

UART, SPI, and USB data differ in the descriptor and `R3`, not the opcode. `PSET Rp, 0, Rd` with two different pins is both lines low (USB SE0). Sticky pins plus a later `PSET`/`OUT` restore idle J. `LDI` after a timed op does not move the old pin.

## Clock and timing

60 MHz target → LS = 40 clocks/bit, FS = 5. Pins are sticky: extra instructions between timed ops stretch the previous level. If the gap does not fit in the hold, shorten that hold (FS: last `OUT` before a mid-packet `LDI` uses 4 so the tail restores 5). LS 40 hides an `LDI`.

`JL` sees `uio` +2 clocks (2-flop sync).

## FS

**TX** at 5 clocks/bit is required. **RX** at 5 will not be software-sampled.

## Compiler pipeline (planned)

```
protocol dict  →  protocol lowering  →  ISA asm  →  assemble.py  →  hex
```

## What we do not do

- Protocol-named opcodes, XOR/MOV, PID hardware, auto detect.
- Spending `0111`–`1111` for foresight. Empty slots are for RX verbs that unblock a program.

## Open (next)

- Compiler (protocol → asm).
- RX: `IN` / `JH` if `JL` is not enough; FS RX sampler if we take that on.
- Multi-protocol / second SM (not lockstep dual-issue on one RF).
