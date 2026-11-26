# Future, drafts, and rejected ideas

Nothing in this file is silicon unless [isa.md](isa.md) already has it. Drafts are locked enough to implement when we say start. Thoughts are not locked. Rejected means do not build it.

Roadmap: **remaining TX listings → RX → details (NLP, real eth size) → optimize.** Compiler is planned, not started. Multiple state machines last.

## IN (original draft — superseded)

Silicon `IN` is in [isa.md](isa.md): `OUT`-shaped, modes `00` mid-sample and `01` wait-for-change. The encoding below (immediate pin, indirect dest) was not built. Other-pin edge (`11`) is not built yet.

Listen-only. Never drives. Never sets `oe`. A program may be only `IN`s. USB FS RX is a **limitation**, not a sampler project.

```
15:12  opcode          (next spend: 1000)
11:8   pin we listen to
 7:5   register (dest + other pin)
 4:2   register that has Rd
 1:0   kind of read
```

The `[7:5]` register is two nibbles. Use the parts the mode needs:

```
 7        4 3        0
|   dest   | other pin |
```

Dest is which register the bit shifts into (use the low 3 of that nibble). Other pin is the edge pin. `[4:2]` names the register that holds the clock count, so dest and N are not the same byte.

| `[1:0]` | When | `[7:5]` / `[4:2]` |
|---|---|---|
| `01` | `[11:8]` changed | dest; count unused |
| `10` | after `Rd` clocks, sample at **end** | dest; `[4:2]` = duration |
| `11` | edge of other pin | dest + other pin; then sample `[11:8]` |
| `00` | after `Rd`, sample at **`Rd>>1`** | UART mid-bit. Manchester: both halves XOR into dest |

`IN` does not use `OUTM`. `OUTM` is a drive. Polarities (change to-0 / to-1 / any, rise / fall / either) are not in the word yet; they can live in spare nibble bits later. Hang vs timeout on a missing edge is later. Shift is `{bit, dest[7:1]}` (same LSB-first as `OUT`).

Clocked duplex is **sticky `PSET` then `IN`**, not a sample bit on `PSET`. TMS+TDI can share one `PSET` (`L1`/`L2`). TCK is a later `PSET`. When TCK is sitting high, TDO is valid for `IN`. One word cannot name three pins.

`[1:0] = 00` is the expansion joint. Spend it on a missing *when* (halfway), never on a protocol name.

## RX SRAM + EXT (draft, not silicon) — superseded

Superseded by RX Stage 1 in [isa.md](isa.md): `CAP`/`SMP` fill one receive byte, the host pulls it with `HCFG` over a program-chosen pin mask, a toggle strobe and a toggle request. The RX SRAM (256x8) is Stage 2. The text below is history.

TX already owns dmem (`LD` / `OUTM`). A 1-port cannot store incoming bytes and fetch payload at the same time. **Third SRAM**, same `256x8` IHP macro. After 8 bits, dest is written there (`rptr++` on the fill side).

**`EXT`** is a new opcode (likely `1001`), **same shape as `OUT`**: descriptor in a register (one or two pins the listing is not using), `Rd` is the dump baud, source is RX SRAM not `Rs` / dmem. Width 1 or 2. Hold/leftover is the same machine — hide `LDI`/`DJNZ` **under** `EXT`. One pin → 8 issues/byte. Two pins → 4.

The host watches those pins for `Rd` clocks. No extra `uio` frame strobe. `Rd` is the window.

Do **not** dump a whole byte on all of `uo_out` while a program is running (those pins are live → garbage). Do **not** wait for `HALT` unless no pin is free. After a dump, sticky levels are the last dump bits; the listing restores idle.

Tiny Tapeout cannot read SRAM. `ui_in` only goes in. Bytes leave on `uo_out` or `uio`. Serial on a chosen pin via `OUT` of dest is the protocol-forward path, 8× slower, not extract.

## RX pending (TX exists)

| Protocol | TX | RX |
|---|---|---|
| UART | `uart.asm` | change-to-0, then duration (mid-bit = `IN` `00`) |
| SPI | `spi.asm` | sample MOSI/MISO pin on SCK; sticky `PSET` then `IN`, or other-edge |
| I2C | `i2c_write.asm` (controller write and ACK) | Target START is change-on-data **while** clock high (two waits before a fourth strobe) |
| USB LS | `usb_ls_ack.asm` | same 40-clock grid |
| USB FS | `usb_fs_ack.asm` | **limitation** |
| 10BASE-T | `eth_10t*.asm` | change (lock phase) then duration + halfway; NLP is TX detail |

**No TX listing yet:** JTAG, SWD, PS/2, CAN. They still need RX to be the protocol (see buckets below).

Two buckets:

- **Drive-only is fine to stack.** UART, USB ACK, 10BASE-T frame, MOSI-only SPI.
- **The protocol is a sample.** I2C ACK, SPI MISO, JTAG TDO, SWD turnaround, PS/2 device clock, CAN ACK slot. Without the sample they are pin movies. Do not write JTAG as if TDO can wait for a big-bang RX.

## Remaining TX (before RX, except the sample-is-the-protocol line)

**JTAG** (IEEE 1149.1): TCK, TMS, TDI, TDO, optional nTRST. No standard frequency (DC to the other chip’s `fmax`). TAP samples TMS+TDI on TCK rise; TDO updates on fall. TMS+TDI in one `PSET L1/L2` while TCK is low, then `PSET` TCK. TDO is `uio`, needs `IN`. nTRST is a fifth pin if we bother.

**SWD:** one data pin + clock. Turnaround is `REL` then `IN`. Clock we drive → sticky `PSET` then `IN`.

**PS/2:** the device clocks. `IN` other-edge on their clock, sample data. We do not make that edge.

**CAN:** recessive/dominant on one wire. ACK slot **is** RX. TX without sampling ACK is a movie.

## Two cores

Named `core0` / `core1` in the assembly. For **independent timebases** (two `Rd`s, two pads), e.g. full-duplex UART or eth. Do not match `pc`s. Do not WAIT on the other core. Each core locks to its pins.

One core send **xor** receive when the timebases are independent. Clocked duplex on **one** core is drive pin2 (sticky) and `IN` pin1, not two cores.

## Compiler (planned)

```
protocol dict  →  protocol lowering  →  ISA asm + dmem image  →  assemble.py  →  hex
```

Two artifacts: instruction words and payload bytes. Listing holds **addresses** into dmem. NRZI, bit stuffing, CRC, LS vs FS polarity are compiler work. Fit non-timed ops (and 2-cycle `LD`) inside the previous hold. SPI: 8 means 8/8 after the MOSI tax. Do not have the compiler always insert `IN`.

## Thoughts (not now)

- **Non-blocking `IN`:** issue starts a listen; a side shifter eats bits while other ops run; dest (or RX SRAM) written at 8 bits. One in-flight. A second `IN` needs a read-in-flight flag (stall or illegal). 1-bit protocols (ACK, one TDO) cannot wait for 8. Dest write at bit 8 collides with 1W RF. Build blocking one-bit `IN` first.
- **Host SR write:** strobe tells the side shifter when to write. Byte on `ui_in`, strobe on some `uio_in`. `uio[1:0]` is already full (load). A new bit fights protocol pins if used while running. Fine as a load-time path, same family as strobe `11`.
- **Two sources:** one `IN` = one pin. Two pins on the same strobe later. Do not spend `[1:0]=00` on it.
- **I2C START** as a fourth strobe only after two waits in a listing prove they are not enough.
- **Change/edge polarity, timeout vs hang, shift the other way, `uo` loopback vs `uio` only.**
- **Clock-gate** idle wait-for-start if power matters. Not a barrier opcode.
- **Coherence opcodes** between two cores: maybe. Not lockstep.
- **dmem from the back** as RX buffer: superseded by a third SRAM.
- **`LD` dump to `uio_out`, N=5:** sketch, not silicon.
- **Store into dmem from address 255:** sketch.
- **Valid as a window** (level until the next OUT writes the other V), snapshot-per-TX-OUT: dropped.
- **Pin output leftover knobs** not committed beyond what `OUT`/`OUTM`/`PSET` already do (two nibbles, halfway XOR on `OUTM`, leftover hold).
- **`OUT[1]`** was reserved for RX. Current extract plan is a **new opcode**, not an `OUT` overload. Keep `[1:0]` of `OUT` as 0 until we spend them on purpose.
- **10BASE-T details:** NLP listing; real min/max frame; preamble is not 1500.
- **USB dummy packets** via dmem + `LD` instead of unrolled `LDI`.
- **Optimize** last (including SPI loop leftover).
- **Multiple SMs** last, and only if a listing cannot.
- **BADPIGGY protocol - a protocol that uses 8 bits to paint a picture. top to bottom, one line per strobe. the number of bits used is configurable.

## Rejected

- Protocol-named opcodes, XOR/MOV, PID hardware, auto-detect, SFD/SYNC match in silicon.
- Extra RF write ports (3R2W). OUTM auto-refill instead.
- Combo `uo_out` (must stay flopped).
- `Rs==0` as the refill condition (count 8 issues).
- `WAIT` on another core / pin-lock as coherence. Burns power, duplicates the FSM, invents a barrier.
- Sample fused onto `PSET` (`PSET S`) as the main RX. Listen must stand alone.
- Leftover `IN` after every `OUT`. TX OUT is not the RX bit. RX bit is `uio_in[k]`.
- Lockstep cores / matched `pc`s.
- Dump all of `uo_out` as the extract path while the program is running. **Superseded** by RX Stage 1: `HCFG` lets the program pick the host pins (n=8 allowed), and unmasked pins keep core values.
- Packed 3-immediate-pin extract with no `Rd` and a `uio` valid strobe. Last-minute. `EXT` looks like `OUT`. **Superseded** by RX Stage 1: a program-chosen strobe pin and a host request toggle (pull model), see [isa.md](isa.md).
- Illegal / malformed packets as a “wow” feature. True programmability is the wow.
- Spending `1000`–`1111` for foresight.
- Hardware NRZI. Listings store levels.
- Circular imem. `OUTD`. ALU. Protocol-select pin.

## Process

Consult before ISA / RTL / listing changes. Do not unroll unless asked. Agent does not drive the Questa GUI.
