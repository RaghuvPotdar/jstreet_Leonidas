/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// 8 x 8-bit register file, 3 read ports + 1 write port.
// Reads are combinational on raddr_p / raddr_s / raddr_d.
// Write is clocked on we. clear zeros every register (used when !running).
//
// Three reads exist so a timed op can issue in one cycle:
//   P = pin descriptor, S = shifter / DJNZ count, D = duration.
module rf (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       clear,
    input  wire       we,
    input  wire [2:0] waddr,
    input  wire [7:0] wdata,
    input  wire [2:0] raddr_p,
    input  wire [2:0] raddr_s,
    input  wire [2:0] raddr_d,
    output wire [7:0] rdata_p,
    output wire [7:0] rdata_s,
    output wire [7:0] rdata_d
);

  logic [7:0] mem [0:7];

  assign rdata_p = mem[raddr_p];
  assign rdata_s = mem[raddr_s];
  assign rdata_d = mem[raddr_d];

  always_ff @(posedge clk) begin
    if (!rst_n || clear) begin
      mem[0] <= 8'h00;
      mem[1] <= 8'h00;
      mem[2] <= 8'h00;
      mem[3] <= 8'h00;
      mem[4] <= 8'h00;
      mem[5] <= 8'h00;
      mem[6] <= 8'h00;
      mem[7] <= 8'h00;
    end else if (we) begin
      mem[waddr] <= wdata;
    end
  end

endmodule
