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
    logic [7:0]  dmem_addr;
    logic        dmem_ren;
    logic [7:0]  dmem_dout;

    // ui_in is one byte. uio_in[1:0]: 00 idle, 01 imem byte, 10 imem byte
    // and start, 11 dmem byte. After start, datapath fetches imem through
    // pc and reads dmem with LD.
    imem imem (
        .clk    (clk),
        .rst_n  (rst_n),
        .byte_in(ui_in),
        .strobe (uio_in[1:0]),
        .pc     (pc),
        .running(running),
        .dout   (dout)
    );

    dmem dmem (
        .clk    (clk),
        .rst_n  (rst_n),
        .running(running),
        .byte_in(ui_in),
        .strobe (uio_in[1:0]),
        .raddr  (dmem_addr),
        .ren    (dmem_ren),
        .dout   (dmem_dout)
    );

    datapath datapath (
        .clk       (clk),
        .rst_n     (rst_n),
        .running   (running),
        .instr     (dout),
        .uio_in    (uio_in),
        .pc        (pc),
        .uo_out    (uo_out),
        .uio_out   (uio_out),
        .uio_oe    (uio_oe),
        .dmem_addr (dmem_addr),
        .dmem_ren  (dmem_ren),
        .dmem_rdata(dmem_dout)
    );

    wire _unused = &{1'b0, ena, 1'b0};

endmodule
