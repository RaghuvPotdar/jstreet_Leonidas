/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Payload SRAM, 256 bytes. Host writes with strobe 11 (ui_in → dmem[wptr++])
// while !running. Datapath reads with raddr/ren; data is on dout the next clock.
module dmem (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       running,
    input  wire [7:0] byte_in,
    input  wire [1:0] strobe,
    input  wire [7:0] raddr,
    input  wire       ren,
    output wire [7:0] dout
);

  localparam logic [1:0] IDLE = 2'b00;
  localparam logic [1:0] DATA = 2'b11;

  logic [1:0] strobe_q;
  logic [7:0] wptr;

  wire take = (strobe_q == IDLE) && (strobe == DATA) && !running;

  logic       men;
  logic       wen;
  logic       sren;
  logic [7:0] addr;
  logic [7:0] din;

  assign men  = take || ren;
  assign wen  = take;
  assign sren = ren && !take;
  assign addr = take ? wptr : raddr;
  assign din  = byte_in;

  RM_IHPSG13_1P_256x8_c3_bm_bist sram (
      .A_CLK      (clk),
      .A_MEN      (men),
      .A_WEN      (wen),
      .A_REN      (sren),
      .A_ADDR     (addr),
      .A_DIN      (din),
      .A_DLY      (1'b1),
      .A_DOUT     (dout),
      .A_BM       (8'hFF),
      .A_BIST_CLK (1'b0),
      .A_BIST_EN  (1'b0),
      .A_BIST_MEN (1'b0),
      .A_BIST_WEN (1'b0),
      .A_BIST_REN (1'b0),
      .A_BIST_ADDR(8'h00),
      .A_BIST_DIN (8'h00),
      .A_BIST_BM  (8'h00)
  );

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      strobe_q <= IDLE;
      wptr     <= 8'h00;
    end else begin
      strobe_q <= strobe;
      if (take)
        wptr <= wptr + 8'd1;
    end
  end

endmodule
