/*
 * Copyright (c) 2026 Raghuv Potdar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

// Executes the program in the instruction SRAM.
//
// The SRAM returns a word one clock after the address is shown. A pin
// level from LOW, HIGH, or OUT lasts for the count in that instruction,
// and this clock is one of them. The next word is requested as soon as
// the current one is accepted, so it is usually waiting in `buf` during
// the hold. A one-clock instruction (LDI, SETX, DJNZ, HALT) that arrives
// during a hold runs on the last clock of that hold, which keeps it off
// the pin. The instruction after it then starts on the following clock.
//
// Opcode is instr[15:12]. LOW, HIGH, and OUT use [11:8] as the pin and
// [7:0] as the hold count. Pin 0-7 is uo_out. Pin 8-15 is uio, and that
// bit of uio_oe is turned on. LDI writes [7:0] into the shifter. SETX
// writes [7:0] into X. DJNZ decrements X and, if the result is not zero,
// continues at address [7:0]. OUT drives shifter[0] and shifts right.
// A hold count of 0 lasts 256 clocks.
module datapath (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        running,
    input  wire [15:0] instr,
    output wire [7:0]  pc,
    output wire [7:0]  uo_out,
    output wire [7:0]  uio_out,
    output wire [7:0]  uio_oe
);

  localparam logic [3:0] OP_LDI  = 4'h0;
  localparam logic [3:0] OP_LOW  = 4'h1;
  localparam logic [3:0] OP_HIGH = 4'h2;
  localparam logic [3:0] OP_SETX = 4'h3;
  localparam logic [3:0] OP_OUT  = 4'h4;
  localparam logic [3:0] OP_DJNZ = 4'h5;
  localparam logic [3:0] OP_HALT = 4'h6;

  // Address shown to the SRAM on the previous clock. Repeated until the
  // next request, so an idle cycle does not read a different word.
  logic [7:0]  shown;
  // `issue_q` is the request from the previous clock. `asked` is one
  // clock later, which is when `instr` is that word. Decoding on
  // `issue_q` would see the previous word.
  logic        issue_q;
  logic        asked;
  logic [7:0]  asked_addr;
  // Next instruction already returned, waiting for the pin hold to finish.
  logic        buf_v;
  logic [15:0] buf_word;
  logic [7:0]  buf_addr;
  // Clocks of the current pin level still left after this clock.
  logic [7:0]  hold;
  // A pin instruction that arrived on the last clock of the previous
  // level. Starting it now would steal that last clock, so it waits
  // one clock.
  logic        defer_v;
  logic [15:0] defer_word;
  logic [7:0]  defer_addr;
  logic        halted;
  // Address of the instruction after the one most recently accepted.
  logic [7:0]  next_addr;
  logic [7:0]  shifter;
  logic [7:0]  xreg;
  logic [7:0]  uo_q;
  logic [7:0]  uio_q;
  logic [7:0]  oe_q;

  logic        issue;
  logic [7:0]  issue_addr;
  logic        asked_n;
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
  logic [7:0]  shifter_n;
  logic [7:0]  x_n;
  logic [7:0]  uo_n;
  logic [7:0]  uio_n;
  logic [7:0]  oe_n;

  logic        do_start;
  logic        do_one;
  logic        do_defer;
  // A one-clock op already in buf had its successor requested on the
  // previous clock, while two clocks of the pin level were still left.
  // Executing it must not request that word again.
  logic        fetched;
  logic [15:0] op_word;
  logic [7:0]  op_addr;
  logic [7:0]  x_dec;
  logic        level;
  logic [3:0]  pin_i;

  assign pc      = (!running) ? 8'h00 : (issue ? issue_addr : shown);
  assign uo_out  = uo_q;
  assign uio_out = uio_q;
  assign uio_oe  = oe_q;

  function automatic logic is_pin(input logic [3:0] op);
    is_pin = (op == OP_LOW) || (op == OP_HIGH) || (op == OP_OUT);
  endfunction

  always_comb begin
    asked_n      = 1'b0;
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
      // Pin and shifter stay as the last instruction left them.
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
        // The buffered op runs on the next clock. Ask for the word
        // after it now, so that word is decoded as this level ends.
        hold_n = hold - 8'd1;
        if (buf_word[15:12] == OP_DJNZ && x_dec != 8'h00)
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
      // First clock after the load, and any later clock where no read
      // is outstanding. Ask for next_addr (0 coming out of reset).
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
      if (op_word[15:12] == OP_OUT) begin
        level     = shifter[0];
        shifter_n = {1'b0, shifter[7:1]};
      end else if (op_word[15:12] == OP_HIGH) begin
        level = 1'b1;
      end else begin
        level = 1'b0;
      end
      if (pin_i[3] == 1'b0)
        uo_n[pin_i[2:0]] = level;
      else begin
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

    if (issue) begin
      asked_n      = 1'b1;
      asked_addr_n = issue_addr;
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      shown      <= 8'h00;
      issue_q    <= 1'b0;
      asked      <= 1'b0;
      asked_addr <= 8'h00;
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
      shown      <= pc;
      issue_q    <= issue;
      asked      <= issue_q;
      asked_addr <= asked_addr_n;
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
