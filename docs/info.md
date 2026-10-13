## How it works

Leonidas loads 16-bit instructions into a 256-word SRAM. `ui_in` carries one byte. `uio_in[1:0]` is the strobe: `00` does nothing, `01` stores the byte, `10` stores the byte and starts execution once that word is complete, and `11` does nothing. The first byte of a word is bits 7 through 0. The second byte is bits 15 through 8. The host returns the strobe to `00` between bytes.

After start, word 0 is read. The SRAM presents the data on the following clock. `uo_out` is the low byte of that word. The fixed UART transmitter is still in the repository and is not connected to the pins.

## How to test

Hold `rst_n` low for one rising edge of `clk`. Drive a byte on `ui_in` and `01` on `uio_in[1:0]` for one rising edge, then return the strobe to `00`. The next byte with strobe `01` completes the first word. A later byte with strobe `10` completes the last word and starts the read of word 0. Two clocks after that start edge, `uo_out` is the low byte of word 0.

## External hardware

None. Clock and reset come from the Tiny Tapeout harness.
