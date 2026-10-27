/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// IHP 256 x 8 single-port. Read: address+REN this edge, A_DOUT next edge.
// Simulation uses the model below. Synthesis sees the black box.
`ifdef SIM
module RM_IHPSG13_1P_256x8_c3_bm_bist (
    input  wire       A_CLK,
    input  wire       A_MEN,
    input  wire       A_WEN,
    input  wire       A_REN,
    input  wire [7:0] A_ADDR,
    input  wire [7:0] A_DIN,
    input  wire       A_DLY,
    output wire [7:0] A_DOUT,
    input  wire [7:0] A_BM,
    input  wire       A_BIST_CLK,
    input  wire       A_BIST_EN,
    input  wire       A_BIST_MEN,
    input  wire       A_BIST_WEN,
    input  wire       A_BIST_REN,
    input  wire [7:0] A_BIST_ADDR,
    input  wire [7:0] A_BIST_DIN,
    input  wire [7:0] A_BIST_BM
);

  logic [7:0] mem [0:255];
  logic [7:0] dout_q;

  assign A_DOUT = dout_q;

  always_ff @(posedge A_CLK) begin
    if (A_MEN && A_WEN && A_BM == 8'hFF)
      mem[A_ADDR] <= A_DIN;
    if (A_MEN && A_REN && !A_WEN)
      dout_q <= mem[A_ADDR];
  end

  wire _unused = &{1'b0, A_DLY, A_BIST_CLK, A_BIST_EN, A_BIST_MEN, A_BIST_WEN,
                   A_BIST_REN, A_BIST_ADDR, A_BIST_DIN, A_BIST_BM, 1'b0};

endmodule
`else
(* blackbox *)
module RM_IHPSG13_1P_256x8_c3_bm_bist (
    input  wire       A_CLK,
    input  wire       A_MEN,
    input  wire       A_WEN,
    input  wire       A_REN,
    input  wire [7:0] A_ADDR,
    input  wire [7:0] A_DIN,
    input  wire       A_DLY,
    output wire [7:0] A_DOUT,
    input  wire [7:0] A_BM,
    input  wire       A_BIST_CLK,
    input  wire       A_BIST_EN,
    input  wire       A_BIST_MEN,
    input  wire       A_BIST_WEN,
    input  wire       A_BIST_REN,
    input  wire [7:0] A_BIST_ADDR,
    input  wire [7:0] A_BIST_DIN,
    input  wire [7:0] A_BIST_BM
);
  assign A_DOUT = 8'h00;
  wire _unused = &{1'b0, A_CLK, A_MEN, A_WEN, A_REN, A_ADDR, A_DIN, A_DLY,
                   A_BM, A_BIST_CLK, A_BIST_EN, A_BIST_MEN, A_BIST_WEN,
                   A_BIST_REN, A_BIST_ADDR, A_BIST_DIN, A_BIST_BM, 1'b0};
endmodule
`endif
