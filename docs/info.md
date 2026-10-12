<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

Leonidas is a fixed UART transmitter with room for one byte. `ui_in` is that byte. A high level on `uio_in[0]` while the transmitter is idle copies the byte into a shift register. `uo_out[0]` then sends a start bit, the eight data bits least-significant-bit first, and a stop bit. Each bit lasts 16 `clk` cycles. `uo_out[1]` is high for the whole frame.

`uio_oe` is 0, so the bidirectional pads are inputs. There is no receive path and no byte queue. The next `send` overwrites the shift register.

## How to test

Hold `rst_n` low for one rising edge of `clk`. `uo_out[0]` is high and `uo_out[1]` is low. Put a byte on `ui_in`, raise `uio_in[0]` for one rising edge, then lower it. The following 16 cycles are low. The next 128 cycles are the data bits, 16 cycles each, bit 0 first. The next 16 cycles are high. `uo_out[1]` is low again on the cycle after the stop bit.

## External hardware

None. Clock and reset come from the Tiny Tapeout harness.
