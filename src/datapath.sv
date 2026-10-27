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
// `rf` is 3R1W. A timed op issues in one cycle and reads:
//   P = pin descriptor, S = shifter (OUT), D = duration.
// Descriptor: [7:4] and [3:0] are pin numbers. Same value twice is one
// pin. Different values are two pins (OUT: pin1=bit, pin2=~bit).
//
// Timed pin ops (PSET, OUT, REL): the start clock is one of the duration
// clocks. Prefetch while holding keeps OUT/DJNZ/OUT gapless when the hold
// is long enough. Pins stick after the hold until rewritten.
// JL samples a 2-flop-synced copy of uio_in, using pin1 of Rp.
// LD is two cycles (1W): issue reads dmem[Rm] and writes Rm+1; next
// clock writes Rn. Do not prefetch past an LD the way DJNZ is handled.
module datapath (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        running,
    input  wire [15:0] instr,
    input  wire [7:0]  uio_in,
    output logic [7:0] pc,
    output wire [7:0]  uo_out,
    output wire [7:0]  uio_out,
    output wire [7:0]  uio_oe,
    output logic [7:0] dmem_addr,
    output logic       dmem_ren,
    input  wire [7:0]  dmem_rdata
);

  localparam logic [3:0] OP_LDI  = 4'h0;
  localparam logic [3:0] OP_PSET = 4'h1;
  localparam logic [3:0] OP_OUT  = 4'h2;
  localparam logic [3:0] OP_DJNZ = 4'h3;
  localparam logic [3:0] OP_HALT = 4'h4;
  localparam logic [3:0] OP_REL  = 4'h5;
  localparam logic [3:0] OP_JL   = 4'h6;
  localparam logic [3:0] OP_LD   = 4'h7;

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
  logic        ld_pend;
  logic [2:0]  ld_dest;
  logic [7:0]  ld_ret;
  logic [7:0]  uo_q;
  logic [7:0]  uio_q;
  logic [7:0]  oe_q;
  logic [7:0]  uio_s0;
  logic [7:0]  uio_s1;

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
  logic        ld_pend_n;
  logic [2:0]  ld_dest_n;
  logic [7:0]  ld_ret_n;
  logic [7:0]  next_addr_n;
  logic [7:0]  uo_n;
  logic [7:0]  uio_n;
  logic [7:0]  oe_n;

  logic        rf_clear;
  logic        rf_we;
  logic [2:0]  rf_waddr;
  logic [7:0]  rf_wdata;
  logic [2:0]  rf_raddr_p;
  logic [2:0]  rf_raddr_s;
  logic [2:0]  rf_raddr_d;
  wire  [7:0]  rf_rdata_p;
  wire  [7:0]  rf_rdata_s;
  wire  [7:0]  rf_rdata_d;

  logic        do_start;
  logic        do_one;
  logic        do_defer;
  logic        fetched;
  logic [15:0] op_word;
  logic [7:0]  op_addr;
  logic [2:0]  rn;
  logic [7:0]  rn_dec;
  logic [7:0]  dur;
  logic        level;
  logic        level2;
  logic [3:0]  pin_i;
  logic [3:0]  pin2_i;
  logic        two;

  assign uo_out  = uo_q;
  assign uio_out = uio_q;
  assign uio_oe  = oe_q;

  rf regs (
      .clk     (clk),
      .rst_n   (rst_n),
      .clear   (rf_clear),
      .we      (rf_we),
      .waddr   (rf_waddr),
      .wdata   (rf_wdata),
      .raddr_p (rf_raddr_p),
      .raddr_s (rf_raddr_s),
      .raddr_d (rf_raddr_d),
      .rdata_p (rf_rdata_p),
      .rdata_s (rf_rdata_s),
      .rdata_d (rf_rdata_d)
  );

  function automatic logic is_pin(input logic [3:0] op);
    is_pin = (op == OP_PSET) || (op == OP_OUT) || (op == OP_REL);
  endfunction

  function automatic logic [2:0] field_rp(input logic [15:0] w);
    field_rp = w[11:9];
  endfunction

  function automatic logic [2:0] field_rs(input logic [15:0] w);
    field_rs = (w[15:12] == OP_OUT || w[15:12] == OP_LD) ? w[8:6] : w[10:8];
  endfunction

  function automatic logic [2:0] field_rd(input logic [15:0] w);
    case (w[15:12])
      OP_OUT:  field_rd = w[5:3];
      OP_PSET: field_rd = w[7:5];
      OP_REL:  field_rd = w[8:6];
      default: field_rd = 3'd0;
    endcase
  endfunction

  function automatic logic pin_low(input logic [3:0] pin);
    pin_low = pin[3] && !uio_s1[pin[2:0]];
  endfunction

  // Read-port addresses. Separate from execute so rdata_* see this address
  // before the decode body uses them.
  always_comb begin
    rf_raddr_p = 3'd0;
    rf_raddr_s = 3'd0;
    rf_raddr_d = 3'd0;
    if (!running || halted) begin
    end else if (defer_v) begin
      rf_raddr_p = field_rp(defer_word);
      rf_raddr_s = field_rs(defer_word);
      rf_raddr_d = field_rd(defer_word);
    end else if (asked && hold == 8'h00 && !buf_v) begin
      rf_raddr_p = field_rp(instr);
      rf_raddr_s = field_rs(instr);
      rf_raddr_d = field_rd(instr);
    end else if (hold == 8'd1 && (asked || buf_v)) begin
      if (asked) begin
        rf_raddr_p = field_rp(instr);
        rf_raddr_s = field_rs(instr);
        rf_raddr_d = field_rd(instr);
      end else begin
        rf_raddr_p = field_rp(buf_word);
        rf_raddr_s = field_rs(buf_word);
        rf_raddr_d = field_rd(buf_word);
      end
    end else if (hold == 8'd2 && buf_v && !is_pin(buf_word[15:12])
                 && buf_word[15:12] != OP_HALT
                 && buf_word[15:12] != OP_LD) begin
      rf_raddr_p = field_rp(buf_word);
      rf_raddr_s = field_rs(buf_word);
      rf_raddr_d = field_rd(buf_word);
    end
  end

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
    ld_pend_n    = ld_pend;
    ld_dest_n    = ld_dest;
    ld_ret_n     = ld_ret;
    next_addr_n  = next_addr;
    dmem_ren     = 1'b0;
    dmem_addr    = 8'h00;
    uo_n         = uo_q;
    uio_n        = uio_q;
    oe_n         = oe_q;
    rf_clear     = 1'b0;
    rf_we        = 1'b0;
    rf_waddr     = 3'd0;
    rf_wdata     = 8'h00;
    issue        = 1'b0;
    issue_addr   = next_addr;
    do_start     = 1'b0;
    do_one       = 1'b0;
    do_defer     = 1'b0;
    fetched      = 1'b0;
    op_word      = instr;
    op_addr      = asked_addr;
    rn           = instr[10:8];
    rn_dec       = rf_rdata_s - 8'd1;
    dur          = 8'h00;
    level        = 1'b0;
    level2       = 1'b0;
    pin_i        = 4'd0;
    pin2_i       = 4'd0;
    two          = 1'b0;

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
      ld_pend_n    = 1'b0;
      ld_dest_n    = 3'd0;
      ld_ret_n     = 8'h00;
      next_addr_n  = 8'h00;
      rf_clear     = 1'b1;
      uo_n         = 8'hFF;
      uio_n        = 8'h00;
      oe_n         = 8'h00;
    end else if (ld_pend) begin
      rf_we       = 1'b1;
      rf_waddr    = ld_dest;
      rf_wdata    = dmem_rdata;
      ld_pend_n   = 1'b0;
      next_addr_n = ld_ret + 8'd1;
      issue       = 1'b1;
      issue_addr  = next_addr_n;
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
                   && buf_word[15:12] != OP_HALT
                   && buf_word[15:12] != OP_LD) begin
        hold_n = hold - 8'd1;
        rn     = buf_word[10:8];
        rn_dec = rf_rdata_s - 8'd1;
        if (buf_word[15:12] == OP_DJNZ && rn_dec != 8'h00)
          next_addr_n = buf_word[7:0];
        else if (buf_word[15:12] == OP_JL && pin_low(rf_rdata_p[3:0]))
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
      rn_dec = rf_rdata_s - 8'd1;
      case (op_word[15:12])
        OP_LDI: begin
          rf_we       = 1'b1;
          rf_waddr    = rn;
          rf_wdata    = op_word[7:0];
          next_addr_n = op_addr + 8'd1;
          issue       = !fetched;
        end
        OP_DJNZ: begin
          rf_we    = 1'b1;
          rf_waddr = rn;
          rf_wdata = rn_dec;
          if (rn_dec != 8'h00)
            next_addr_n = op_word[7:0];
          else
            next_addr_n = op_addr + 8'd1;
          issue = !fetched;
        end
        OP_JL: begin
          if (pin_low(rf_rdata_p[3:0]))
            next_addr_n = op_word[7:0];
          else
            next_addr_n = op_addr + 8'd1;
          issue = !fetched;
        end
        OP_LD: begin
          dmem_ren    = 1'b1;
          dmem_addr   = rf_rdata_s;
          rf_we       = 1'b1;
          rf_waddr    = op_word[8:6];
          rf_wdata    = rf_rdata_s + 8'd1;
          ld_pend_n   = 1'b1;
          ld_dest_n   = op_word[11:9];
          ld_ret_n    = op_addr;
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
      pin_i  = rf_rdata_p[3:0];
      pin2_i = rf_rdata_p[7:4];
      two    = (pin_i != pin2_i);
      dur    = rf_rdata_d;

      if (op_word[15:12] == OP_OUT) begin
        level    = rf_rdata_s[0];
        level2   = ~rf_rdata_s[0];
        rf_we    = 1'b1;
        rf_waddr = op_word[8:6];
        rf_wdata = {1'b0, rf_rdata_s[7:1]};
      end else if (op_word[15:12] == OP_PSET) begin
        level  = op_word[8];
        level2 = op_word[8];
      end else begin
        level  = 1'b0;
        level2 = 1'b0;
      end

      if (op_word[15:12] == OP_REL) begin
        if (pin_i[3] == 1'b1) begin
          uio_n[pin_i[2:0]] = 1'b0;
          oe_n[pin_i[2:0]]  = 1'b0;
        end else
          uo_n[pin_i[2:0]] = 1'b0;
        if (two) begin
          if (pin2_i[3] == 1'b1) begin
            uio_n[pin2_i[2:0]] = 1'b0;
            oe_n[pin2_i[2:0]]  = 1'b0;
          end else
            uo_n[pin2_i[2:0]] = 1'b0;
        end
      end else begin
        if (pin_i[3] == 1'b0)
          uo_n[pin_i[2:0]] = level;
        else begin
          uio_n[pin_i[2:0]] = level;
          oe_n[pin_i[2:0]]  = 1'b1;
        end
        if (two) begin
          if (pin2_i[3] == 1'b0)
            uo_n[pin2_i[2:0]] = level2;
          else begin
            uio_n[pin2_i[2:0]] = level2;
            oe_n[pin2_i[2:0]]  = 1'b1;
          end
        end
      end

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
      uio_s0     <= 8'h00;
      uio_s1     <= 8'h00;
    end else begin
      shown      <= pc;
      issue_q    <= issue;
      asked      <= issue_q;
      asked_addr <= asked_addr_n;
      uio_s0     <= uio_in;
      uio_s1     <= uio_s0;
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
      ld_pend    <= 1'b0;
      ld_dest    <= 3'd0;
      ld_ret     <= 8'h00;
      next_addr  <= 8'h00;
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
      ld_pend    <= ld_pend_n;
      ld_dest    <= ld_dest_n;
      ld_ret     <= ld_ret_n;
      next_addr  <= next_addr_n;
      uo_q       <= uo_n;
      uio_q      <= uio_n;
      oe_q       <= oe_n;
    end
  end

endmodule
