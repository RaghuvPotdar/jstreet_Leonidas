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
| `0001` | `PSET` | `Rp`(3) ‖ `L1` ‖ `Rd`(3) ‖ `L2` ‖ 0 |
| `0010` | `OUT` | `Rp`(3) ‖ `Rs`(3) ‖ `Rd`(3) ‖ `M` ‖ 0 |
| `0011` | `DJNZ` | `0` ‖ `Rn`(3) ‖ target(8) |
| `0100` | `HALT` | ignored |
| `0101` | `REL` | `Rp`(3) ‖ `Rd`(3) ‖ 0 |
| `0110` | `JL` | `Rp`(3) ‖ `0` ‖ target(8) |
| `0111` | `LD` | `Rn`(3) ‖ `Rm`(3) ‖ 0 |
| `1000` | `IN` | `Rp`(3) ‖ `Rs`(3) ‖ `Rd`(3) ‖ 0 ‖ `W` ‖ `M` |
| `1001` | `CAP` | `0` ‖ `Rs`(3) ‖ 0 |
| `1010` | `SMP` | `Rp`(3) ‖ 0(3) ‖ `Rd`(3) ‖ 0 |
| `1011` | `HCFG` | `Rp`(3) ‖ `Rs`(3) ‖ `Rd`(3) ‖ 0 |
| `1100` | `LDH` | ignored |
| `1101` | `ODO` | `Rp`(3) ‖ `Rd`(3) ‖ 0 |
| `1110`–`1111` | unused | ignored |

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

- `PSET`: low nibble ← `L1`; if the nibbles differ, high nibble ← `L2`. Same pin twice uses `L1` only.
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

A timed op (`PSET` / `OUT` / `REL`) issues the next sequential address on its start clock, then keeps issuing that same address every leftover clock until the word arrives and is buffered (`!buf_v`). Two consecutive `issue`s of the same address → `asked` **high for two clocks** and `instr` repeats. Once `buf_v` is set, leftover clocks do not re-issue.

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
15    12 11  9 8  7   5  4  3    0
| 0001  |  Rp |L1| Rd  |L2|  0   |
```

Drive `pin1` to `L1`. If the descriptor has two pins, drive `pin2` to `L2`. One pin: `L2` is ignored. Wait `Rd` clocks.

Assembler: `PSET Rp, L, Rd` writes `L1=L2=L`. `PSET Rp, L1, L2, Rd` sets them separately.

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

10BASE-T TX is `OUTM` with `R3=6` (one data bit per issue) and a bit-count `DJNZ`. RX is `INW` (see `IN`).

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

If `pin1` of `Rp` reads 0 on `uio`, jump; else fall through. `uo_out` reads as 1, except the status pins 6 and 7 (RX Stage 1). Sample is **two flops** behind the pad.
When a buffered `JL` prefetches its destination at `hold == 2`, that sample determines the branch.

## LD — `0111`

```
15    12 11  9 8   6 5        0
| 0111  |  Rn |  Rm |    0     |
```

`Rn ← dmem[Rm]`, then `Rm ← Rm + 1`. Two clocks because the file is 1W: cycle 0 asserts REN and writes `Rm`; cycle 1 writes `Rn` from `A_DOUT`. Hide a software `LD` inside a hold of 3 or more, not on an FS bit boundary. The same `LD` arms `OUTM` to consume the rest of dmem during leftover hold (see `OUT`).

## IN — `1000`

```
15    12 11  9 8   6 5   3 2 1 0
| 1000  |  Rp |  Rs |  Rd |0|mode|
```

Listen on `pin1` of `Rp`. Never drives, never sets `oe`. Shift `Rs ← {bit, Rs[7:1]}` (LSB first, same as `OUT`). `uo` pins read 1, except the status pins 6 and 7 (RX Stage 1). Sample is the 2-flop synced `uio`, same as `JL`.

| `[1:0]` | Asm | Behaviour |
|---|---|---|
| `00` | `IN Rp, Rs, Rd` | Timed op, hold `Rd`. Sample at the `Rd>>1` point (same clock as the `OUTM` flip). `Rd=1` samples on issue. |
| `01` | `INW Rp, Rs, Rd` | Stall until `pin1` differs from its level at issue. Shift in the **new** level. Then hold `Rd` from that clock, like a timed op issued at the edge. `Rd=1` acts as 2. Waits forever. |
| `1x` | — | Reserved. Executes as a no-op. |

`Rs` is read at issue and written at the sample. Do not write `Rs` with a hidden op between. If a hidden op writes the RF on the sample clock, the sample lands one clock later (`IN` with `Rd` 2–3 and a hidden op after it).

UART RX: `INW` on the start edge with `Rd = bit`, then eight `IN …, bit` (`asm/examples/uart_rx_echo.asm`). Manchester RX: `INW` with `Rd` ≈ ¾ bit, looped. Each mid-bit edge re-locks, so sender clock error does not accumulate (`asm/examples/eth_10t_rx_echo.asm`).

## RX Stage 1 — receive byte and host read

One receive byte `rxp` with a valid flag and a sticky overflow flag `rx_ovf`. `CAP` or the sampler (`SMP`) fills `rxp`. The host pulls `rxp` in chunks over a program-chosen set of pins (`HCFG`). `LDH` and `ODO` send a live host byte open-drain. None of these ops writes the RF. TX encodings and timing do not change.

### CAP — `1001`

```
15    12 11 10   8 7          0
| 1001  | 0 |  Rs |     0      |
```

Non-timed (same path as `LDI`, can hide in a hold). If `rxp` is empty: `rxp ← Rs`, valid ← 1. Else the new byte is dropped and `rx_ovf ← 1` (sticky until reset). `CAP` forwards a write of `Rs` in the same clock or still pending (`IN` sample, deferred `IN` write, `OUTM` refill), so `IN` then a hidden `CAP` captures the full byte. If the sampler captures in the same clock, the sampler wins and the `CAP` counts as overflow. A capture in the clock before `rxp` empties (data edge of the last chunk) is dropped.

### SMP — `1010`

```
15    12 11  9 8   6 5   3 2  0
| 1010  |  Rp |  0  |  Rd | 0  |
```

Non-timed. Arms the 8-bit sampler. `Rp[7]=1`: source `ui_in[Rp[2:0]]`. `Rp[7]=0`, `Rp[3]=1`: source `uio[Rp[2:0]]`. Else (also `Rp=0`): disarm. Both sources are 2-flop synced. `Rd` = period `B` in clocks, 0 = 256.

Arm latches the current level as idle, then waits for an edge. `E` = the edge where the synced level first differs from idle. An input change at `e0`+1 ns gives `E = e0+2`. Sample `k` (0..7) reads the synced level just before edge `E + half + B·(k+1)`, with `half = B>>1` (128 for `B=0`). Shift is LSB first. After sample 7: capture (same rules as `CAP`), wait for idle, wait for the next edge. The sampler runs every clock, also during holds, `INW`, `LD` and `HALT`. `B=1` has `half=0`: sample 0 reads the clock after `E`, which is the start level. UART reception needs `B ≥ 2`.

### HCFG — `1011`

```
15    12 11  9 8   6 5   3 2  0
| 1011  |  Rp |  Rs |  Rd | 0  |
```

Non-timed. Mask = `{Rs, Rp}`: `Rp` = uo pins 0–7, `Rs` = uio pins 8–15. `Rd[7:4]` = strobe pin (0–15). `Rd[2:0]` = request uio index. `Rd[3]` is reserved and must be 0. `n` = number of mask pins.

The config is valid only if all are true: `n` is 1, 2, 4 or 8; the strobe pin is not in the mask; the request pad is not in the mask; strobe pin ≠ request pad; `Rd[3]=0`; if the sampler is armed on a uio pad, that pad is not in the mask and is not the strobe pin. Validity is computed again at each `HCFG` and `SMP`. Invalid or mask 0: the path is off and every pin shows its core value.

On each `HCFG` and each change to valid: chunk ← 0, data ← 0, strobe level ← the pad value of the strobe pin now (so no strobe edge), request reference ← request pad now, then 3 clocks with no request detection (the reference follows the pad).

While valid: mask uio pads and a uio strobe pad have `oe=1`, the request pad has `oe=0`. Chunk bit `i` drives the `i`-th mask pin in ascending pin number. Core writes to owned pins still update the core state and show again when the path is off. Outputs stay flopped: the overlay feeds the pad flops.

### Handshake

1. The host toggles the request pad once.
2. Pending = valid, no blank, synced request ≠ reference. A pending request is served at edge `E` if `rxp` is valid, no TX op holds the pins (`tx_busy=0`), and the previous serve is complete.
3. At `E`: the strobe pin toggles. At `E+1`: the data pins show the next chunk, `rxp[chunk·n +: n]`. After the last chunk (`8/n` chunks), `rxp` is empty.

Idle core: a toggle at `E0`+1 ns gives the strobe after `E3` and the data after `E4`. A request while `rxp` is empty waits. When a byte lands at edge `Ec`, the strobe comes after `Ec+1` and the data after `Ec+2`. An `HCFG` commit on the data edge of a serve wins: that chunk is not used, and the byte starts again at chunk 0. A validity change (for example by `SMP`) acts the same way, and no serve occurs in the clock where the config turns invalid.

`tx_busy` = a `PSET`, `OUT`/`OUTM` or `ODO` hold is running (`hold ≠ 0`). `REL`, `IN`, `INW`, `LD`, `HALT` and `Rd=1` ops never block. Every timed op starts in a clock with `hold = 0`, so gapless TX leaves a serve window at each op start. Worst-case wait = longest TX op (`Rd=0`: 256) + 2 sync + 1.

### LDH — `1100`

Non-timed, no operand. `txr ← ui_in` (2-flop synced). Host rule: hold `ui_in` stable at least 2 clocks before the ready signal that the program polls.

### ODO — `1101`

```
15    12 11  9 8   6 5        0
| 1101  |  Rp |  Rd |    0     |
```

Timed, same hold path and length as `OUT` with the same `Rd`. Acts on `pin1` of `Rp` only (uio pins only). `txr[7]=1`: release (`oe=0`). `txr[7]=0`: drive low (`oe=1`). The pin output is always 0, so `ODO` never drives high. Then `txr ← {txr[6:0], 0}` (MSB first). On a uo pin: no pin change, but the hold and the shift still occur.

### Status pins

In `JL`, `IN` and `INW`, pin number 7 reads 0 while `rxp` is valid, and pin number 6 reads 0 after an overflow. The other uo pins read 1.

### Pin roles

| Role | Allowed pins | Direction while active | Before HCFG / reset | Must not overlap |
|---|---|---|---|---|
| Mask (n=1,2,4,8) | 0..15 | out; uio oe=1 | core values | strobe, request, sampler pad, open-drain pads, uio[1:0] unless host tri-states |
| Strobe (toggle) | 0..15 | out; uio oe=1 | core value, loaded at HCFG | mask, request, sampler pad |
| Request (toggle) | uio 0..7 | oe forced 0; 2-flop synced | input | mask, strobe, LDH ready |
| LDH ready | uio, program-chosen | input (JL) | input | request, mask |
| LDH byte | ui_in[7:0] | input | loader byte before run | sampler ui_in bit |
| Sampler source | uio or ui_in[k] | input | — | mask, strobe |
| Loader strobes | uio[1:0] | host until start, ignored while running | input | mask/strobe unless host tri-states |
| Status (virtual) | pin numbers 6, 7 in JL/IN/INW | internal | reads 1 | none |

Hardware checks only the rules in `HCFG`. The other rules in this table are program rules.

### Host rules

- Toggle the request once for each chunk. Do not toggle again until the strobe answers (a second toggle cancels the first).
- Latch the data 2 or more clocks after the strobe toggle.
- Do not drive mask or strobe uio pads while the config is valid. If `uio[0]`/`uio[1]` are mask or strobe pads, tri-state them after the start strobe.
- After reset or `HCFG`, count chunks from chunk 0. Toggles in the first 3 clocks after `HCFG` are lost. Start after the config is live.
- Stage 1 has no host-visible empty or overflow flag. Use a timeout.
- Turning the path off returns the strobe and mask pins to core values. This can make a strobe edge that the host must ignore.
- Throughput: per chunk = `op · ceil((T_host + 4) / op)`, worst case plus one `op`. `T_host` starts at the strobe toggle and includes the 2-clock latch rule. No overflow if `(8/n) · per chunk ≤` RX byte time. Example: `n=1`, 16 clk/bit, `T_host=2`: 128 clocks per byte ≤ 160.

Listings: `uart_duplex.asm`, `spi_duplex.asm`, `i2c_read.asm`, `i2c_target_rt.asm` in `asm/examples`.

## Unused opcodes — `1110` and `1111`

Two free opcodes. No-op: next word. RX Stage 1 spent `1001`–`1101`; the `EXT` draft in [future.md](future.md) is superseded. Do not spend these for foresight. `JL` stays until a listing proves it is not enough.

## Scope notes

- **FS TX** is in scope (5 clocks/bit). **FS RX is a limitation** (not software-sampled).
- No PID comparator, no protocol-select pin, no ALU. A PID check is a program of `JL`s.
- No `OUTD`. Two pins live in the descriptor nibbles. `PSET` has `L1`/`L2`.
- No circular imem. Payload is dmem (`256x8`), 8-bit address in an `Rn`.
- `OUT[1:0]` stay 0. RX is its own opcode (`IN`), not an `OUT` overload.
- Programs, pins, and timings: [listings.md](listings.md). Drafts and ideas: [future.md](future.md). How to run sim: [sim.md](sim.md).
