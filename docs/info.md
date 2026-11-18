## How it works

Leonidas is a programmable pin machine (top `tt_um_RaghuvPotdar_Leonidas`). The opcode is a verb. The protocol is the program. Target **60 MHz**. Full ISA: [isa.md](isa.md). Doc map: [README.md](README.md).

Two SRAMs: **imem** (`256x16` instructions) and **dmem** (`256x8` payload). `ui_in` carries one byte. `uio_in[1:0]` selects the destination: `00` idle, `01` store into imem, `10` store into imem and start once that word is complete, `11` store into dmem at `wptr` and increment. The first imem byte of a word is bits 7 through 0. The second is bits 15 through 8. Fill dmem before the `10` start. The host returns the strobe to `00` between bytes. The bus is synchronized on chip: keep `ui_in` stable until the next strobe (at least one clock after the strobe rises). Each byte lands 3 clocks after its strobe.

Bits 15 through 12 are the opcode. Eight registers `R0`–`R7`, 3R1W: timed ops read a pin descriptor, a shifter, and a duration in one cycle (`OUT Rp, Rs, Rd`). `OUTM` (`[2]`) is IEEE Manchester (10BASE-T TX, 6 clocks/bit). Long payloads: compiler writes addresses (`LDI Rn, addr`); bytes sit in dmem; `LD Rn, [Rm]` fetches one byte (2 clocks, post-inc `Rm`) and arms `OUTM` to refill `Rs` from dmem every 8 bits during leftover hold. `OUT` does not. `LDI` / `DJNZ` / `PSET` / `REL` / `JL` / `HALT` as in [isa.md](isa.md). `PSET` can set two pins to different levels (`L1`/`L2`). USB D+/D− is descriptor `0x54` (`uo_out[4]` / `uo_out[5]`). Pins 0 through 7 are `uo_out`, which idles high. `JL` samples `uio` two clocks late. RX is `IN` / `INW` (sample a `uio` pin into a shifter; see [isa.md](isa.md)).

## How to test

Hold `rst_n` low for one rising edge of `clk`. Drive a byte on `ui_in` and `01` on `uio_in[1:0]` for one rising edge, then return the strobe to `00`. The next byte with strobe `01` completes the imem word. Strobe `11` writes one dmem byte. Strobe `10` on the high byte of the last **imem** word starts the program. `uo_out` stays `FF` until an instruction drives a pin.

cocotb + Icarus: `test/` (WSL). Waves: Questa in `questa/`. Commands: [sim.md](sim.md). Listings: [listings.md](listings.md).

## External hardware

None. Clock and reset come from the Tiny Tapeout harness. Protocol PHYs (USB resistors, Ethernet magnetics, I2C pull-ups) are off-chip. The TB models I2C pull-ups on `uio[3:2]`.
