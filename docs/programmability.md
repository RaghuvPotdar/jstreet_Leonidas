# Programmability

Leonidas is a dumb pin machine. True programmability means the silicon stays a small set of verbs; new protocols and protocol details appear as **programs** and as **compiler lowering**, not as new named engines in the chip.

## Split of responsibility

| In the chip (ISA / datapath) | In the compiler / host |
|---|---|
| Drive a pin high or low for N clocks | UART / SPI / I2C / USB packet layout |
| Release a `uio` pin (open-drain) | NRZI encode |
| Shift a byte out LSB first (`OUT`) | MSB-first bit-reverse before `LDI` |
| Count, jump, halt, jump-if-pin-low | USB bit stuffing, CRC5 / CRC16 |
| Hold counts and pin numbers in the word | Idle J/K polarity for LS vs FS |
| | Turning a protocol dict into `.asm` / `.hex` |

The opcode is a verb. The protocol is a program. An unused opcode stays unused until a listing **cannot** be written with the verbs that exist.

## Clock and timing

Hold counts are in chip clocks. Absolute bit rate is `CLOCK_HZ / hold`. STA / target clock: **60 MHz** (`CLOCK_PERIOD` 16.667 ns) → LS = 40 clocks/bit, FS = 5 clocks/bit. Other protocols keep the same verbs; only the numbers in the listing change.

Continuity on the wire comes from prefetch while a hold counts down, not from the chip understanding frames. If a hold is too short for the next word to be ready, the bit stretches; measure before trusting very small counts (FS at 5 is the tight case).

## Compiler pipeline (planned)

```
protocol dict  →  protocol lowering  →  ISA asm  →  assemble.py  →  hex
```

- `assemble.py` only knows the ISA.
- Protocol frontends (UART, SPI, I2C, USB, …) append as new lowering steps. Example: USB bit stuffing and NRZI run in Python when expanding a packet into `PSET` on D+/D−.
- Future ISA verbs get a mnemonic in `assemble.py`; future protocols get a new dict shape and lowering function, not a rewrite of the chip.

## What we do not do

- A `USB` / `I2C` / baud opcode or a strobed “FS mode” bit that names the protocol in silicon.
- Widening the instruction past 16 bits for protocol fields (PID, ADDR, ENDP live on the wire, as many pin instructions, not in one instruction word).
- Spending the remaining opcodes for foresight. Empty slots are for verbs that unblock a program that cannot be written today.

## Open (next)

- Multi-protocol / second SM (not lockstep dual-issue on one RF).
- ISA polish after more protocol listings (shared duration regs, PSETH vs PSET redundancy) — keep silicon dumb until a real program cannot be written.
