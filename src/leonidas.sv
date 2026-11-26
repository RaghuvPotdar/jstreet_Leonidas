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

    // The host bus is asynchronous to clk. Strobe goes through 3 flops, the
    // byte through 2. A strobe that leaves 00 is reported as the OR of the two
    // oldest samples, so pin skew on 00->11 cannot show up as 01 or 10.
    // The byte is taken one sample after the strobe edge: hold ui_in until
    // the next strobe. shortcut: assumes strobe pin skew < 1 clock.
    logic [1:0] strobe_s1, strobe_s2, strobe_s3;
    logic [7:0] byte_s1, byte_s2;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            strobe_s1 <= 2'b00;
            strobe_s2 <= 2'b00;
            strobe_s3 <= 2'b00;
        end else begin
            strobe_s1 <= uio_in[1:0];
            strobe_s2 <= strobe_s1;
            strobe_s3 <= strobe_s2;
        end
        byte_s1 <= ui_in;
        byte_s2 <= byte_s1;
    end
    wire [1:0] strobe = (strobe_s3 == 2'b00) ? 2'b00 : (strobe_s3 | strobe_s2);

    // ui_in is one byte. uio_in[1:0]: 00 idle, 01 imem byte, 10 imem byte
    // and start, 11 dmem byte. After start, datapath fetches imem through
    // pc and reads dmem with LD.
    imem imem (
        .clk    (clk),
        .rst_n  (rst_n),
        .byte_in(byte_s2),
        .strobe (strobe),
        .pc     (pc),
        .running(running),
        .dout   (dout)
    );

    dmem dmem (
        .clk    (clk),
        .rst_n  (rst_n),
        .running(running),
        .byte_in(byte_s2),
        .strobe (strobe),
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
        .byte_s2   (byte_s2),
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
