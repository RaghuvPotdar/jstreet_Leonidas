# Programmability

Leonidas is a dumb pin machine. The opcode is a verb. The protocol is the program. Load a different listing to change protocol.

Doc map: [README.md](README.md). Silicon ISA: [isa.md](isa.md). Listings: [listings.md](listings.md). Drafts, roadmap, rejected ideas: [future.md](future.md).

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

UART, SPI, and USB data differ in the descriptor, `R3`, and the dmem image, not the opcode. 10BASE-T TX is `OUTM` with `R3=6` on **one** pin (IEEE Manchester). Complement is off-chip. A `LD` into the shifter arms `OUTM` to refill from dmem every 8 bits during leftover hold, so the listing is `OUTM`+`DJNZ` on **bits** with the first `LD` in idle. `OUT` is unchanged (one bit from a register). `PSET Rp, 0, Rd` with two different pins is both lines low (USB SE0). `PSET Rp, L1, L2, Rd` sets the two pins independently. Sticky pins plus a later `PSET`/`OUT` restore idle J. `LDI` after a timed op does not move the old pin.

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

**TX** at 5 clocks/bit is required. **RX** at 5 is a limitation (not software-sampled).

## Compiler pipeline (planned)

```
protocol dict  →  protocol lowering  →  ISA asm + dmem image  →  assemble.py  →  hex
```

Two artifacts: instruction words and payload bytes. The listing contains addresses into dmem.

## What we do not do

- Protocol-named opcodes, XOR/MOV, PID hardware, auto detect.
- Spending `1000`–`1111` for foresight. Next slot is `IN` then `EXT` ([future.md](future.md)).

## Pin output — degrees of freedom

What a pin output already is (do not add a third grammar):

- Which pad(s): two nibbles in the descriptor.
- Level: `PSET` `L1`/`L2`, or `OUT` `Rs[0]` (and `~Rs[0]` on the other nibble).
- How long: `Rd`. Leftover is `Rd−1` (non-pin ops only).
- Halfway: `OUTM` XOR at `Rd>>1` (Manchester).
- Sticky: after hold, the level stays until that pin is written again.
- Release: `REL` (uio `oe` off).

Not committed: more than two pins in one op, combo (unflopped) pads, a third leftover meaning.

## Pin input — when you take a bit

Same idea as the output knobs. RX is not UART/SPI/eth. It is **when** a `uio` bit is allowed into the SR. Three strobes:

| Strobe | What | Who |
|---|---|---|
| **Change on the data pin** | wait until `pin1` flips (or to 0/1); that event is the start or the bit | UART start, first energy, async |
| **Level after `Rd` clocks** | wait `Rd`, then sample `pin1` | UART data, any baud grid |
| **Edge of another pin** | sample `pin1` when `pin2` rises (or falls) | SPI MISO, I2C SDA, JTAG TDO |

Descriptor already has two nibbles: data + clock. Rise vs fall is a mode bit, not a protocol bit. Halfway (`Rd>>1`) is a second sample on the duration strobe — Manchester, not a fourth family.

Not a UART opcode: start = change-to-0, bits = duration. SPI = other-pin rise. 10BASE-T = change (lock phase) then duration+halfway. No token match in the chip: capture as sampled, store as captured. SFD / SYNC / start-bit checks are the listing or the host.

I2C START is change-on-data **while** the clock pin is high. Two waits (level on `pin2`, then change on `pin1`) before adding a fourth strobe.

**Strobe 3 is not “SCK samples MOSI/MISO.”** The chip does not know those names. `IN` is listen-only. If we also drive the clock, `PSET` first (sticky), then `IN`. No waiter, no matched `pc`, no protocol. The listing picks the pin numbers.

Two cores are for **independent timebases** (two `Rd`s, two pads). Each core locks to **its** pins. Do not lock two `pc`s. Do not wait on the other core.

Idle “wait for start” on a receive-only listing is a pin lock, not inter-core sync. Clock-gate later if power matters. Not a barrier opcode.

**Two sources later.** One `IN` = one pin. Two pins on the same read is later.

Locked `IN` / RX SRAM / `EXT` encodings, RX-pending table, two-core rule, and the rejected list: **[future.md](future.md)**. Not silicon.

## Open (next)

- JTAG, SWD, PS/2, CAN TX listings on the verbs we have. JTAG TDO is a sample — do not pretend TDO can wait.
- Then RX (`IN` as drafted). Then details (NLP, real eth size). Then optimize.
- Compiler (protocol → asm + dmem).
- USB dummy packets via dmem + `LD` instead of unrolled `LDI`.
- Two cores (`core0` / `core1`) only for independent timebases.
