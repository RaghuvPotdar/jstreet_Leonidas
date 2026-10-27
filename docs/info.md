## How it works

Leonidas has two SRAMs: **imem** (`256x16` instructions) and **dmem** (`256x8` payload). `ui_in` carries one byte. `uio_in[1:0]` selects the destination: `00` idle, `01` store into imem, `10` store into imem and start once that word is complete, `11` store into dmem at `wptr` and increment. The first imem byte of a word is bits 7 through 0. The second is bits 15 through 8. Fill dmem before the `10` start. The host returns the strobe to `00` between bytes.

Bits 15 through 12 are the opcode. Eight registers `R0`–`R7`, 3R1W: timed ops read a pin descriptor, a shifter, and a duration in one cycle (`OUT Rp, Rs, Rd`). Long payloads: compiler writes addresses (`LDI Rn, addr`); bytes sit in dmem; `LD Rn, [Rm]` fetches one byte (2 clocks, post-inc `Rm`). `LDI` / `DJNZ` / `PSET` / `REL` / `JL` / `HALT` as in [isa.md](isa.md). USB D+/D− is descriptor `0x54` (`uo_out[4]` / `uo_out[5]`). Pins 0 through 7 are `uo_out`, which idles high. `JL` samples `uio` two clocks late.

## How to test

Hold `rst_n` low for one rising edge of `clk`. Drive a byte on `ui_in` and `01` on `uio_in[1:0]` for one rising edge, then return the strobe to `00`. The next byte with strobe `01` completes the imem word. Strobe `11` writes one dmem byte. Strobe `10` on the high byte of the last **imem** word starts the program. `uo_out` stays `FF` until an instruction drives a pin.

## External hardware

None. Clock and reset come from the Tiny Tapeout harness.
