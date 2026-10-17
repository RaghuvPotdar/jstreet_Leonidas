/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Executes the program in the instruction SRAM.
//
// Fetch and decode are separate blocks. Fetch asks the SRAM for an
// address. The word is on `instr` two clocks later: the SRAM updates its
// output one clock after the address is sampled, and the decode block
// sees that output on the clock after the update. Decode then writes the
// shifter, X, the pin, and the hold counter.
//
// A LOW, HIGH, OUT_L, or OUT_M level lasts for the count in the instruction, and
// the clock that starts it is one of those clocks. The next word is
// requested as that instruction starts, so it is waiting in `buf` while
// the pin holds. With two clocks of the level left after the current
// one, decode asks for the word that buffered instruction will need.
// For OUT_L then DJNZ then OUT_L, that ask is the branch target, and the
// next OUT_L starts on the clock after the current level's last clock.
//
// HALT runs in that same last-clock slot. The level still gets its full
// count. HALT then leaves the pin at that level.
//
// Opcode is instr[15:12]. LOW, HIGH, OUT_L, OUT_M, and REL use [11:8] as
// the pin and [7:0] as the hold count. Pin 0-7 is uo_out. Pin 8-15 is
// uio, and that bit of uio_oe is turned on. REL turns the uio driver off
// and leaves the driven bit at 0. LDI writes [7:0] into the shifter.
// SETX writes [7:0] into X. DJNZ decrements X and, if the result is not
// zero, continues at address [7:0]. JL continues at address [7:0] when
// that uio pin reads 0. OUT_L drives shifter[0] and shifts right. OUT_M
// drives shifter[7] and shifts left. A hold count of 0 lasts 256 clocks.
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

  localparam logic [3:0] OP_LDI  = 4'h0;
  localparam logic [3:0] OP_LOW  = 4'h1;
  localparam logic [3:0] OP_HIGH = 4'h2;
  localparam logic [3:0] OP_SETX = 4'h3;
  localparam logic [3:0] OP_OUT_L = 4'h4;
  localparam logic [3:0] OP_DJNZ  = 4'h5;
  localparam logic [3:0] OP_HALT  = 4'h6;
  localparam logic [3:0] OP_OUT_M = 4'h7;
  localparam logic [3:0] OP_REL   = 4'h8;
  localparam logic [3:0] OP_JL    = 4'h9;

  // Fetch registers. `shown` is the address presented last clock.
  // `issue_q` is the ask from last clock. `asked` is the ask from two
  // clocks ago, which is when `instr` is that word. `asked_addr` is the
  // address the word came from.
  logic [7:0]  shown;
  logic        issue_q;
  logic        asked;
  logic [7:0]  asked_addr;
  logic [7:0]  next_addr;

  // Execute registers.
  logic        buf_v;
  logic [15:0] buf_word;
  logic [7:0]  buf_addr;
  logic [7:0]  hold;
  logic        defer_v;
  logic [15:0] defer_word;
  logic [7:0]  defer_addr;
  logic        halted;
  logic [7:0]  shifter;
  logic [7:0]  xreg;
  logic [7:0]  uo_q;
  logic [7:0]  uio_q;
  logic [7:0]  oe_q;

  // Fetch combinational result: ask the SRAM to sample `issue_addr`.
  logic        issue;
  logic [7:0]  issue_addr;
  logic [7:0]  asked_addr_n;

  // Decode combinational result, loaded by the execute registers.
  logic        buf_v_n;
  logic [15:0] buf_n;
  logic [7:0]  buf_addr_n;
  logic [7:0]  hold_n;
  logic        defer_v_n;
  logic [15:0] defer_n;
  logic [7:0]  defer_addr_n;
  logic        halted_n;
  logic [7:0]  next_addr_n;
  logic [7:0]  shifter_n;
  logic [7:0]  x_n;
  logic [7:0]  uo_n;
  logic [7:0]  uio_n;
  logic [7:0]  oe_n;

  logic        do_start;
  logic        do_one;
  logic        do_defer;
  logic        fetched;
  logic [15:0] op_word;
  logic [7:0]  op_addr;
  logic [7:0]  x_dec;
  logic        level;
  logic [3:0]  pin_i;

  assign uo_out  = uo_q;
  assign uio_out = uio_q;
  assign uio_oe  = oe_q;

  function automatic logic is_pin(input logic [3:0] op);
    is_pin = (op == OP_LOW) || (op == OP_HIGH) || (op == OP_OUT_L)
          || (op == OP_OUT_M) || (op == OP_REL);
  endfunction

  // uio pins are 8-15. A uo pin has no input, so it never reads low.
  function automatic logic pin_low(input logic [3:0] pin);
    pin_low = pin[3] && !uio_in[pin[2:0]];
  endfunction

  // Decode. Chooses the instruction to execute and whether fetch should
  // ask for another word. Does not present the address itself.
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
    shifter_n    = shifter;
    x_n          = xreg;
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
    x_dec        = xreg - 8'd1;
    level        = 1'b0;
    pin_i        = instr[11:8];

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
      shifter_n    = 8'h00;
      x_n          = 8'h00;
      uo_n         = 8'hFF;
      uio_n        = 8'h00;
      oe_n         = 8'h00;
    end else if (halted) begin
      // The timed level already finished. The pin stays.
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
        // Two clocks of this level remain after this one. DJNZ or SETX
        // is already in buf, so the word it needs can be sampled now
        // and will be ready when this level ends.
        hold_n = hold - 8'd1;
        if (buf_word[15:12] == OP_DJNZ && x_dec != 8'h00)
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
      case (op_word[15:12])
        OP_LDI: begin
          shifter_n   = op_word[7:0];
          next_addr_n = op_addr + 8'd1;
          issue       = !fetched;
        end
        OP_SETX: begin
          x_n         = op_word[7:0];
          next_addr_n = op_addr + 8'd1;
          issue       = !fetched;
        end
        OP_DJNZ: begin
          x_n = x_dec;
          if (x_dec != 8'h00)
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
        // Last clock of the current level. The count still completes.
        // The pin is then left at this level.
        OP_HALT: halted_n = 1'b1;
        default: begin
          next_addr_n = op_addr + 8'd1;
          issue       = !fetched;
        end
      endcase
      if (issue)
        issue_addr = next_addr_n;
    end else if (do_start) begin
      pin_i = op_word[11:8];
      if (op_word[15:12] == OP_OUT_L) begin
        level     = shifter[0];
        shifter_n = {1'b0, shifter[7:1]};
      end else if (op_word[15:12] == OP_OUT_M) begin
        level     = shifter[7];
        shifter_n = {shifter[6:0], 1'b0};
      end else if (op_word[15:12] == OP_HIGH) begin
        level = 1'b1;
      end else begin
        level = 1'b0;
      end
      if (op_word[15:12] == OP_REL && pin_i[3] == 1'b1) begin
        uio_n[pin_i[2:0]] = 1'b0;
        oe_n[pin_i[2:0]]  = 1'b0;
      end else if (pin_i[3] == 1'b0) begin
        uo_n[pin_i[2:0]] = level;
      end else begin
        uio_n[pin_i[2:0]] = level;
        oe_n[pin_i[2:0]]  = 1'b1;
      end
      // This clock is the first of the count. 0 wraps to 255 left
      // afterwards, so the level lasts 256 clocks.
      hold_n      = op_word[7:0] - 8'd1;
      next_addr_n = op_addr + 8'd1;
      issue       = 1'b1;
      issue_addr  = next_addr_n;
    end

    if (issue)
      asked_addr_n = issue_addr;
  end

  // Fetch. Presents the address decode asked for, or repeats the last
  // address when decode did not ask.
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
      shifter    <= 8'h00;
      xreg       <= 8'h00;
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
      shifter    <= shifter_n;
      xreg       <= x_n;
      uo_q       <= uo_n;
      uio_q      <= uio_n;
      oe_q       <= oe_n;
    end
  end

endmodule
