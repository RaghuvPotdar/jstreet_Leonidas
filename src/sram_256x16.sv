/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// The IHP library has no 64x16 macro. This is the smallest single-port
// macro whose word is 16 bits: 256 words. Simulation uses the model below.
// Synthesis sees an empty black box so the real macro can be dropped in
// later. A read is presented on one rising edge and A_DOUT updates on the
// next. A write lands on the edge where A_MEN and A_WEN are high.
`ifdef SIM
module RM_IHPSG13_1P_256x16_c2_bm_bist (
    input  wire        A_CLK,
    input  wire        A_MEN,
    input  wire        A_WEN,
    input  wire        A_REN,
    input  wire [7:0]  A_ADDR,
    input  wire [15:0] A_DIN,
    input  wire        A_DLY,
    output wire [15:0] A_DOUT,
    input  wire [15:0] A_BM,
    input  wire        A_BIST_CLK,
    input  wire        A_BIST_EN,
    input  wire        A_BIST_MEN,
    input  wire        A_BIST_WEN,
    input  wire        A_BIST_REN,
    input  wire [7:0]  A_BIST_ADDR,
    input  wire [15:0] A_BIST_DIN,
    input  wire [15:0] A_BIST_BM
);

  logic [15:0] mem [0:255];
  logic [7:0]  rd_addr_q;
  logic        rd_pend;
  logic [15:0] dout_q;

  assign A_DOUT = dout_q;

  always_ff @(posedge A_CLK) begin
    if (A_MEN && A_WEN && A_BM == 16'hFFFF)
      mem[A_ADDR] <= A_DIN;
    rd_addr_q <= A_ADDR;
    rd_pend   <= A_MEN && A_REN && !A_WEN;
    if (rd_pend)
      dout_q <= mem[rd_addr_q];
  end

  wire _unused = &{1'b0, A_DLY, A_BIST_CLK, A_BIST_EN, A_BIST_MEN, A_BIST_WEN,
                   A_BIST_REN, A_BIST_ADDR, A_BIST_DIN, A_BIST_BM, 1'b0};

endmodule
`else
(* blackbox *)
module RM_IHPSG13_1P_256x16_c2_bm_bist (
    input  wire        A_CLK,
    input  wire        A_MEN,
    input  wire        A_WEN,
    input  wire        A_REN,
    input  wire [7:0]  A_ADDR,
    input  wire [15:0] A_DIN,
    input  wire        A_DLY,
    output wire [15:0] A_DOUT,
    input  wire [15:0] A_BM,
    input  wire        A_BIST_CLK,
    input  wire        A_BIST_EN,
    input  wire        A_BIST_MEN,
    input  wire        A_BIST_WEN,
    input  wire        A_BIST_REN,
    input  wire [7:0]  A_BIST_ADDR,
    input  wire [15:0] A_BIST_DIN,
    input  wire [15:0] A_BIST_BM
);
endmodule
`endif
