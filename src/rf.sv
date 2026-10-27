/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// 8 x 8-bit register file, 1 read port + 1 write port.
// Read is combinational on raddr. Write is clocked on we.
// clear zeros every register on the next rising edge (used when !running).
module rf (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       clear,
    input  wire       we,
    input  wire [2:0] waddr,
    input  wire [7:0] wdata,
    input  wire [2:0] raddr,
    output wire [7:0] rdata
);

  logic [7:0] mem [0:7];

  assign rdata = mem[raddr];

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
