/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_RaghuvPotdar_Leonidas (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    logic        running;
    logic [15:0] dout;
    logic [7:0]  pc;

    // ui_in is one byte of an instruction. uio_in[1:0] says what to do with
    // it: 00 idle, 01 store the byte, 10 store the byte and start once the
    // word is complete, 11 ignored. After start, datapath reads the SRAM
    // through pc and drives the pins.
    imem imem (
        .clk    (clk),
        .rst_n  (rst_n),
        .byte_in(ui_in),
        .strobe (uio_in[1:0]),
        .pc     (pc),
        .running(running),
        .dout   (dout)
    );

    datapath datapath (
        .clk    (clk),
        .rst_n  (rst_n),
        .running(running),
        .instr  (dout),
        .pc     (pc),
        .uo_out (uo_out),
        .uio_out(uio_out),
        .uio_oe (uio_oe)
    );

    wire _unused = &{1'b0, ena, 1'b0};

endmodule
