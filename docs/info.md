## How it works

Leonidas loads a program into a 256-word SRAM and then runs it. `ui_in` carries one byte. `uio_in[1:0]` is the strobe: `00` does nothing, `01` stores the byte, `10` stores the byte and starts execution once that word is complete, and `11` does nothing. The first byte of a word is bits 7 through 0. The second byte is bits 15 through 8. The host returns the strobe to `00` between bytes.

Bits 15 through 12 are the opcode. `LDI` loads the shifter. `SETX` loads X. `LOW`, `HIGH`, and `OUT` drive one pin for the count in the instruction. `OUT` uses the low bit of the shifter and shifts right. `DJNZ` decrements X and jumps if the result is not zero. `HALT` leaves the pins where they are. Pins 0 through 7 are `uo_out`, which idles high. The example program transmits one UART byte on `uo_out[1]`.

The fixed UART transmitter is still in the repository and is not connected to the pins.

## How to test

Hold `rst_n` low for one rising edge of `clk`. Drive a byte on `ui_in` and `01` on `uio_in[1:0]` for one rising edge, then return the strobe to `00`. The next byte with strobe `01` completes the word. Strobe `10` on the high byte of the last word starts the program. `uo_out` stays `FF` until an instruction drives a pin.

## External hardware

None. Clock and reset come from the Tiny Tapeout harness.
