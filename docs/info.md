<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

Leonidas is an 8-bit free-running counter. On each rising edge of `clk`, if `rst_n` is low the count is set to 0. Otherwise the count increments by 1 and wraps from 255 to 0. The count is driven on `uo_out`, with bit 0 as the least significant bit.

`ui_in` and `ena` are unused. `uio_out` and `uio_oe` are tied to 0, so the bidirectional pads stay inputs.

## How to test

Hold `rst_n` low and clock `clk`. `uo_out` is 0 on the first rising edge and stays 0 while reset is held. Release `rst_n` between edges. The next rising edge makes `uo_out` equal 1, and each later rising edge adds 1. Nine edges after the first increment, `uo_out` is 10.

## External hardware

None. Clock and reset come from the Tiny Tapeout harness.
