/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Loads 16-bit words into the instruction SRAM, two bytes per word.
// uio strobe[1:0] is sampled on the rising edge, and only a change out of
// 00 is a byte:
//   00 idle
//   01 load the byte on ui_in
//   10 load the byte on ui_in and, once the word is complete, start
//   11 reserved, ignored
// The first byte of a word is instr[7:0]. The second is instr[15:8].
// After start, every clock is a read of `pc`. The word comes back on the
// next clock. `pc` is the datapath's address, not a pin.
module imem (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  byte_in,
    input  wire [1:0]  strobe,
    input  wire [7:0]  pc,
    output wire        running,
    output wire [15:0] dout
);

  localparam logic [1:0] IDLE  = 2'b00;
  localparam logic [1:0] LOAD  = 2'b01;
  localparam logic [1:0] FINAL = 2'b10;

  logic [1:0]  strobe_q;
  logic        half;
  logic [7:0]  low_byte;
  logic [7:0]  wr_addr;
  logic        running_q;
  logic        arm_run;

  wire take = (strobe_q == IDLE) && (strobe == LOAD || strobe == FINAL) && !running_q;
  wire write_word = take && half;

  logic        men;
  logic        wen;
  logic        ren;
  logic [7:0]  addr;
  logic [15:0] din;

  assign running = running_q;
  assign men     = write_word || running_q;
  assign wen     = write_word;
  assign ren     = running_q && !write_word;
  assign addr    = write_word ? wr_addr : pc;
  assign din         = {byte_in, low_byte};

  RM_IHPSG13_1P_256x16_c2_bm_bist sram (
      .A_CLK      (clk),
      .A_MEN      (men),
      .A_WEN      (wen),
      .A_REN      (ren),
      .A_ADDR     (addr),
      .A_DIN      (din),
      .A_DLY      (1'b1),
      .A_DOUT     (dout),
      .A_BM       (16'hFFFF),
      .A_BIST_CLK (1'b0),
      .A_BIST_EN  (1'b0),
      .A_BIST_MEN (1'b0),
      .A_BIST_WEN (1'b0),
      .A_BIST_REN (1'b0),
      .A_BIST_ADDR(8'h00),
      .A_BIST_DIN (16'h0000),
      .A_BIST_BM  (16'h0000)
  );

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      strobe_q  <= IDLE;
      half      <= 1'b0;
      low_byte  <= 8'h00;
      wr_addr   <= 8'h00;
      running_q <= 1'b0;
      arm_run   <= 1'b0;
    end else begin
      strobe_q <= strobe;

      if (take && !half) begin
        low_byte <= byte_in;
        half     <= 1'b1;
        if (strobe == FINAL)
          arm_run <= 1'b1;
      end else if (write_word) begin
        half    <= 1'b0;
        wr_addr <= wr_addr + 8'd1;
        if (strobe == FINAL || arm_run) begin
          running_q <= 1'b1;
          arm_run   <= 1'b0;
        end
      end
    end
  end

endmodule
