/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Fixed UART transmitter. One byte, no queue.
//
// data is copied on the rising edge where send is high and the transmitter
// is idle. The wire then stays at the idle level for that one edge. The
// start bit occupies the next 16 edges, then eight data bits, LSB first,
// 16 edges each, then a stop bit for 16 edges. The next byte is whatever
// is on data the next time send is high in idle.
module ff_uart (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] data,
    input  wire       send,
    output wire       tx,
    output wire       busy
);

  localparam int CLKS_PER_BIT = 16;

  localparam logic [1:0] IDLE  = 2'd0;
  localparam logic [1:0] START = 2'd1;
  localparam logic [1:0] DATA  = 2'd2;
  localparam logic [1:0] STOP  = 2'd3;

  logic [1:0] state;
  logic [3:0] timer;
  logic [2:0] bit_idx;
  logic [7:0] shifter;
  logic       tx_q;
  // The edge that finishes the stop bit returns to IDLE. That edge is still
  // the 16th clock of the stop bit, so busy has to stay high through it.
  logic       stop_done;

  assign tx   = tx_q;
  assign busy = (state != IDLE) || stop_done;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      state   <= IDLE;
      timer   <= 4'd0;
      bit_idx <= 3'd0;
      shifter   <= 8'd0;
      tx_q      <= 1'b1;
      stop_done <= 1'b0;
    end else begin
      stop_done <= 1'b0;
      case (state)
        IDLE: begin
          tx_q <= 1'b1;
          if (send) begin
            shifter <= data;
            timer   <= 4'd0;
            bit_idx <= 3'd0;
            state   <= START;
          end
        end
        START: begin
          tx_q <= 1'b0;
          if (timer == CLKS_PER_BIT - 1) begin
            timer <= 4'd0;
            state <= DATA;
          end else begin
            timer <= timer + 4'd1;
          end
        end
        DATA: begin
          tx_q <= shifter[0];
          if (timer == CLKS_PER_BIT - 1) begin
            timer   <= 4'd0;
            shifter <= {1'b0, shifter[7:1]};
            if (bit_idx == 3'd7) begin
              bit_idx <= 3'd0;
              state   <= STOP;
            end else begin
              bit_idx <= bit_idx + 3'd1;
            end
          end else begin
            timer <= timer + 4'd1;
          end
        end
        STOP: begin
          tx_q <= 1'b1;
          if (timer == CLKS_PER_BIT - 1) begin
            timer     <= 4'd0;
            state     <= IDLE;
            stop_done <= 1'b1;
          end else begin
            timer <= timer + 4'd1;
          end
        end
        default: begin
          state <= IDLE;
          tx_q  <= 1'b1;
        end
      endcase
    end
  end

endmodule
