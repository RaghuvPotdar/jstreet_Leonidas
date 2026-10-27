/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Executes the program in the instruction SRAM.
//
// Fetch and decode are separate. The word is on `instr` two clocks after
// an address is issued. Decode writes the register file, pins, and hold.
//
// Register file: R0-R7, clocked write, combinational read. OUT uses R0 as
// the shifter. PSETH waits use R4-R7 via a 2-bit index.
//
// Timed pin ops (PSET, OUT, REL, PSETH): the start clock is one of the
// duration clocks. Prefetch while holding keeps OUT/DJNZ/OUT gapless when
// the hold is long enough. Pins stick after the hold until rewritten.
module datapath (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        running,
    input  wire [15:0] instr,
    input  wire [7:0]  uio_in,
    output logic [7:0] pc,
    output wire [7:0]  uo_out,
    output wire [7:0]  uio_out,
    output wire [7:0]  uio_oe
);

  localparam logic [3:0] OP_LDI   = 4'h0;
  localparam logic [3:0] OP_PSET  = 4'h1;
  localparam logic [3:0] OP_OUT   = 4'h2;
  localparam logic [3:0] OP_DJNZ  = 4'h3;
  localparam logic [3:0] OP_HALT  = 4'h4;
  localparam logic [3:0] OP_REL   = 4'h5;
  localparam logic [3:0] OP_JL    = 4'h6;
  localparam logic [3:0] OP_PSETH = 4'h7;

  logic [7:0]  shown;
  logic        issue_q;
  logic        asked;
  logic [7:0]  asked_addr;
  logic [7:0]  next_addr;

  logic        buf_v;
  logic [15:0] buf_word;
  logic [7:0]  buf_addr;
  logic [7:0]  hold;
  logic        defer_v;
  logic [15:0] defer_word;
  logic [7:0]  defer_addr;
  logic        halted;
  logic [7:0]  rf [0:7];
  logic [7:0]  uo_q;
  logic [7:0]  uio_q;
  logic [7:0]  oe_q;

  logic        issue;
  logic [7:0]  issue_addr;
  logic [7:0]  asked_addr_n;

  logic        buf_v_n;
  logic [15:0] buf_n;
  logic [7:0]  buf_addr_n;
  logic [7:0]  hold_n;
  logic        defer_v_n;
  logic [15:0] defer_n;
  logic [7:0]  defer_addr_n;
  logic        halted_n;
  logic [7:0]  next_addr_n;
  logic [7:0]  rf_n [0:7];
  logic [7:0]  uo_n;
  logic [7:0]  uio_n;
  logic [7:0]  oe_n;

  logic        do_start;
  logic        do_one;
  logic        do_defer;
  logic        fetched;
  logic [15:0] op_word;
  logic [7:0]  op_addr;
  logic [2:0]  rn;
  logic [7:0]  rn_dec;
  logic [7:0]  wait_r;
  logic [7:0]  dur;
  logic        level;
  logic        level2;
  logic [3:0]  pin_i;
  logic [3:0]  pin2_i;

  assign uo_out  = uo_q;
  assign uio_out = uio_q;
  assign uio_oe  = oe_q;

  function automatic logic is_pin(input logic [3:0] op);
    is_pin = (op == OP_PSET) || (op == OP_OUT) || (op == OP_REL) || (op == OP_PSETH);
  endfunction

  function automatic logic pin_low(input logic [3:0] pin);
    pin_low = pin[3] && !uio_in[pin[2:0]];
  endfunction

  function automatic logic [7:0] pset_dur(input logic [6:0] raw);
    pset_dur = (raw == 7'd0) ? 8'd128 : {1'b0, raw};
  endfunction

  always_comb begin
    asked_addr_n = asked_addr;
    buf_v_n      = buf_v;
    buf_n        = buf_word;
    buf_addr_n   = buf_addr;
    hold_n       = hold;
    defer_v_n    = defer_v;
    defer_n      = defer_word;
    defer_addr_n = defer_addr;
    halted_n     = halted;
    next_addr_n  = next_addr;
    for (int ri = 0; ri < 8; ri++)
      rf_n[ri] = rf[ri];
    uo_n         = uo_q;
    uio_n        = uio_q;
    oe_n         = oe_q;
    issue        = 1'b0;
    issue_addr   = next_addr;
    do_start     = 1'b0;
    do_one       = 1'b0;
    do_defer     = 1'b0;
    fetched      = 1'b0;
    op_word      = instr;
    op_addr      = asked_addr;
    rn           = instr[10:8];
    rn_dec       = rf[rn] - 8'd1;
    wait_r       = 8'h00;
    dur          = 8'h00;
    level        = 1'b0;
    level2       = 1'b0;
    pin_i        = instr[11:8];
    pin2_i       = instr[7:4];

    if (!running) begin
      asked_addr_n = 8'h00;
      buf_v_n      = 1'b0;
      buf_n        = 16'h0000;
      buf_addr_n   = 8'h00;
      hold_n       = 8'h00;
      defer_v_n    = 1'b0;
      defer_n      = 16'h0000;
      defer_addr_n = 8'h00;
      halted_n     = 1'b0;
      next_addr_n  = 8'h00;
      for (int ri = 0; ri < 8; ri++)
        rf_n[ri] = 8'h00;
      uo_n         = 8'hFF;
      uio_n        = 8'h00;
      oe_n         = 8'h00;
    end else if (halted) begin
    end else if (defer_v) begin
      do_start     = 1'b1;
      op_word      = defer_word;
      op_addr      = defer_addr;
      defer_v_n    = 1'b0;
    end else if (asked && hold == 8'h00 && !buf_v) begin
      op_word = instr;
      op_addr = asked_addr;
      if (is_pin(instr[15:12]))
        do_start = 1'b1;
      else
        do_one = 1'b1;
    end else if (hold != 8'h00) begin
      if (hold == 8'd1 && (asked || buf_v)) begin
        if (asked) begin
          op_word = instr;
          op_addr = asked_addr;
        end else begin
          op_word = buf_word;
          op_addr = buf_addr;
        end
        buf_v_n = 1'b0;
        hold_n  = 8'h00;
        if (!asked)
          fetched = 1'b1;
        if (is_pin(op_word[15:12]))
          do_defer = 1'b1;
        else
          do_one = 1'b1;
      end else if (asked) begin
        buf_v_n    = 1'b1;
        buf_n      = instr;
        buf_addr_n = asked_addr;
        hold_n     = hold - 8'd1;
      end else if (hold == 8'd2 && buf_v && !is_pin(buf_word[15:12])
                   && buf_word[15:12] != OP_HALT) begin
        hold_n = hold - 8'd1;
        rn     = buf_word[10:8];
        rn_dec = rf[rn] - 8'd1;
        if (buf_word[15:12] == OP_DJNZ && rn_dec != 8'h00)
          next_addr_n = buf_word[7:0];
        else if (buf_word[15:12] == OP_JL && pin_low(buf_word[11:8]))
          next_addr_n = buf_word[7:0];
        else
          next_addr_n = buf_addr + 8'd1;
        issue      = 1'b1;
        issue_addr = next_addr_n;
      end else begin
        hold_n = hold - 8'd1;
        if (!buf_v) begin
          issue      = 1'b1;
          issue_addr = next_addr;
        end
      end
    end else if (!(issue_q && !asked)) begin
      issue      = 1'b1;
      issue_addr = next_addr;
    end

    if (do_defer) begin
      defer_v_n    = 1'b1;
      defer_n      = op_word;
      defer_addr_n = op_addr;
      next_addr_n  = op_addr + 8'd1;
    end else if (do_one) begin
      rn     = op_word[10:8];
      rn_dec = rf[rn] - 8'd1;
      case (op_word[15:12])
        OP_LDI: begin
          rf_n[rn]    = op_word[7:0];
          next_addr_n = op_addr + 8'd1;
          issue       = !fetched;
        end
        OP_DJNZ: begin
          rf_n[rn] = rn_dec;
          if (rn_dec != 8'h00)
            next_addr_n = op_word[7:0];
          else
            next_addr_n = op_addr + 8'd1;
          issue = !fetched;
        end
        OP_JL: begin
          if (pin_low(op_word[11:8]))
            next_addr_n = op_word[7:0];
          else
            next_addr_n = op_addr + 8'd1;
          issue = !fetched;
        end
        OP_HALT: halted_n = 1'b1;
        default: begin
          next_addr_n = op_addr + 8'd1;
          issue       = !fetched;
        end
      endcase
      if (issue)
        issue_addr = next_addr_n;
    end else if (do_start) begin
      pin_i  = op_word[11:8];
      pin2_i = op_word[7:4];
      if (op_word[15:12] == OP_OUT) begin
        level     = rf[0][0];
        rf_n[0]   = {1'b0, rf[0][7:1]};
        dur       = op_word[7:0];
      end else if (op_word[15:12] == OP_PSET) begin
        level = op_word[7];
        dur   = pset_dur(op_word[6:0]);
      end else if (op_word[15:12] == OP_PSETH) begin
        level  = op_word[3];
        level2 = op_word[2];
        wait_r = rf[3'd4 + {1'b0, op_word[1:0]}];
        dur    = wait_r;
      end else if (op_word[15:12] == OP_REL) begin
        level = 1'b0;
        dur   = op_word[7:0];
      end else begin
        level = 1'b0;
        dur   = op_word[7:0];
      end

      if (op_word[15:12] == OP_REL && pin_i[3] == 1'b1) begin
        uio_n[pin_i[2:0]] = 1'b0;
        oe_n[pin_i[2:0]]  = 1'b0;
      end else if (op_word[15:12] == OP_PSETH) begin
        if (pin_i[3] == 1'b0)
          uo_n[pin_i[2:0]] = level;
        else begin
          uio_n[pin_i[2:0]] = level;
          oe_n[pin_i[2:0]]  = 1'b1;
        end
        if (pin2_i[3] == 1'b0)
          uo_n[pin2_i[2:0]] = level2;
        else begin
          uio_n[pin2_i[2:0]] = level2;
          oe_n[pin2_i[2:0]]  = 1'b1;
        end
      end else if (pin_i[3] == 1'b0) begin
        uo_n[pin_i[2:0]] = level;
      end else begin
        uio_n[pin_i[2:0]] = level;
        oe_n[pin_i[2:0]]  = 1'b1;
      end

      // First clock of the count. 8-bit 0 wraps to 255 left (256 total).
      hold_n      = dur - 8'd1;
      next_addr_n = op_addr + 8'd1;
      issue       = 1'b1;
      issue_addr  = next_addr_n;
    end

    if (issue)
      asked_addr_n = issue_addr;
  end

  always_comb begin
    if (!running)
      pc = 8'h00;
    else if (issue)
      pc = issue_addr;
    else
      pc = shown;
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      shown      <= 8'h00;
      issue_q    <= 1'b0;
      asked      <= 1'b0;
      asked_addr <= 8'h00;
    end else begin
      shown      <= pc;
      issue_q    <= issue;
      asked      <= issue_q;
      asked_addr <= asked_addr_n;
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      buf_v      <= 1'b0;
      buf_word   <= 16'h0000;
      buf_addr   <= 8'h00;
      hold       <= 8'h00;
      defer_v    <= 1'b0;
      defer_word <= 16'h0000;
      defer_addr <= 8'h00;
      halted     <= 1'b0;
      next_addr  <= 8'h00;
      for (int ri = 0; ri < 8; ri++)
        rf[ri] <= 8'h00;
      uo_q       <= 8'hFF;
      uio_q      <= 8'h00;
      oe_q       <= 8'h00;
    end else begin
      buf_v      <= buf_v_n;
      buf_word   <= buf_n;
      buf_addr   <= buf_addr_n;
      hold       <= hold_n;
      defer_v    <= defer_v_n;
      defer_word <= defer_n;
      defer_addr <= defer_addr_n;
      halted     <= halted_n;
      next_addr  <= next_addr_n;
      for (int ri = 0; ri < 8; ri++)
        rf[ri] <= rf_n[ri];
      uo_q       <= uo_n;
      uio_q      <= uio_n;
      oe_q       <= oe_n;
    end
  end

endmodule
