## How it works

Leonidas loads a program into a 256-word SRAM and then runs it. `ui_in` carries one byte. `uio_in[1:0]` is the strobe: `00` does nothing, `01` stores the byte, `10` stores the byte and starts execution once that word is complete, and `11` does nothing. The first byte of a word is bits 7 through 0. The second byte is bits 15 through 8. The host returns the strobe to `00` between bytes.

Bits 15 through 12 are the opcode. Eight registers `R0`–`R7`, 3R1W: timed ops read a pin descriptor, a shifter, and a duration in one cycle (`OUT Rp, Rs, Rd`). `LDI` / `DJNZ` / `PSET` / `REL` / `JL` / `HALT` as in [isa.md](isa.md). USB D+/D− is descriptor `0x54` (`uo_out[4]` / `uo_out[5]`). Pins 0 through 7 are `uo_out`, which idles high. `JL` samples `uio` two clocks late.

The fixed UART transmitter is still in the repository and is not connected to the pins.

## How to test

Hold `rst_n` low for one rising edge of `clk`. Drive a byte on `ui_in` and `01` on `uio_in[1:0]` for one rising edge, then return the strobe to `00`. The next byte with strobe `01` completes the word. Strobe `10` on the high byte of the last word starts the program. `uo_out` stays `FF` until an instruction drives a pin.

## External hardware

None. Clock and reset come from the Tiny Tapeout harness.
