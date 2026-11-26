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
// OUT[2]: after Rd>>1 clocks, XOR the driven pins (mid-hold invert).
// A LD into Rs arms an OUTM dmem stream: after 8 OUTMs of that Rs,
// leftover hold refills Rs from dmem[dptr] and write-backs Rm. OUT
// does not. LDI into Rs disarms. Rs==0 is not byte-done.
// IN (1000) listens on pin1 of Rp, never drives. Rs <= {bit, Rs[7:1]}.
// [1:0]=00: hold Rd, sample at Rd>>1. [1:0]=01 (INW): stall until pin1
// changes, shift in the new level, then hold Rd from that clock.
// RX Stage 1 (docs/isa.md): CAP/SMP/HCFG/LDH are non-timed (LDI path),
// ODO is timed. rxp holds one received byte. The host-read overlay acts
// on the next-state pin values that feed the pad flops pad_*.
module datapath (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        running,
    input  wire [15:0] instr,
    input  wire [7:0]  uio_in,
    input  wire [7:0]  byte_s2,
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
  localparam logic [3:0] OP_IN   = 4'h8;
  localparam logic [3:0] OP_CAP  = 4'h9;
  localparam logic [3:0] OP_SMP  = 4'hA;
  localparam logic [3:0] OP_HCFG = 4'hB;
  localparam logic [3:0] OP_LDH  = 4'hC;
  localparam logic [3:0] OP_ODO  = 4'hD;

  localparam logic [1:0] SMP_IDLE = 2'd0;  // wait level == idle
  localparam logic [1:0] SMP_EDGE = 2'd1;  // wait level != idle
  localparam logic [1:0] SMP_RUN  = 2'd2;  // half, then 8 samples

  // RX Stage 1 state. None of it writes the RF.
  logic [7:0]  rxp, rxp_n;
  logic        rxp_v, rxp_v_n;
  logic        rx_ovf, rx_ovf_n;
  logic        smp_on, smp_on_n;
  logic        smp_ui, smp_ui_n;
  logic [2:0]  smp_idx, smp_idx_n;
  logic [7:0]  smp_b, smp_b_n;
  logic        smp_idle, smp_idle_n;
  logic [1:0]  smp_st, smp_st_n;
  logic        smp_ph, smp_ph_n;
  logic [7:0]  smp_t, smp_t_n;
  logic [2:0]  smp_k, smp_k_n;
  logic [7:0]  smp_sh, smp_sh_n;
  logic [15:0] hm, hm_n;
  logic [3:0]  hr_stb, hr_stb_n;
  logic [2:0]  hr_req, hr_req_n;
  logic        hr_rsvd_bad, hr_rsvd_bad_n;
  logic        hr_valid, hr_valid_n;
  logic        hr_req_last, hr_req_last_n;
  logic [1:0]  hr_blank, hr_blank_n;
  logic        hr_stb_q, hr_stb_q_n;
  logic [2:0]  hr_chunk, hr_chunk_n;
  logic [7:0]  hr_dout, hr_dout_n;
  logic        serve_d, serve_d_n;
  logic        hold_tx, hold_tx_n;
  logic [7:0]  txr, txr_n;
  logic [7:0]  pad_uo, pad_uo_n;
  logic [7:0]  pad_uio, pad_uio_n;
  logic [7:0]  pad_oe, pad_oe_n;

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
  logic        stream_v;
  logic [2:0]  stream_rs;
  logic [2:0]  ptr_r;
  logic [7:0]  dptr;
  logic [2:0]  bitcnt;
  logic        refill_ren;
  logic        refill_pend;
  logic        refill_wb;
  logic        man_v;
  logic [7:0]  man_at;
  logic [7:0]  man_uo;
  logic [7:0]  man_uio;
  logic [7:0]  uo_q;
  logic [7:0]  uio_q;
  logic [7:0]  oe_q;
  logic [7:0]  uio_s0;
  logic [7:0]  uio_s1;
  logic        in_wait;
  logic        in_ref;
  logic [3:0]  in_pin;
  logic [2:0]  in_rs;
  logic [7:0]  in_val;
  logic [7:0]  in_dur;
  logic        in_samp_v;
  logic [7:0]  in_samp_at;
  logic        in_wr_v;
  logic [7:0]  in_wr_val;

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
  logic        stream_v_n;
  logic [2:0]  stream_rs_n;
  logic [2:0]  ptr_r_n;
  logic [7:0]  dptr_n;
  logic [2:0]  bitcnt_n;
  logic        refill_ren_n;
  logic        refill_pend_n;
  logic        refill_wb_n;
  logic        man_v_n;
  logic [7:0]  man_at_n;
  logic [7:0]  man_uo_n;
  logic [7:0]  man_uio_n;
  logic [7:0]  next_addr_n;
  logic [7:0]  uo_n;
  logic [7:0]  uio_n;
  logic [7:0]  oe_n;
  logic        in_wait_n;
  logic        in_ref_n;
  logic [3:0]  in_pin_n;
  logic [2:0]  in_rs_n;
  logic [7:0]  in_val_n;
  logic [7:0]  in_dur_n;
  logic        in_samp_v_n;
  logic [7:0]  in_samp_at_n;
  logic        in_wr_v_n;
  logic [7:0]  in_wr_val_n;
  logic        in_fire;
  logic [2:0]  in_fire_rs;
  logic [7:0]  in_fire_val;

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

  assign uo_out  = pad_uo;
  assign uio_out = pad_uio;
  assign uio_oe  = pad_oe;

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

  function automatic logic is_pin(input logic [15:0] word);
    logic [3:0] op;
    op = word[15:12];
    // Timed ops: issue through do_start/do_defer, own the hold.
    is_pin = (op == OP_PSET) || (op == OP_OUT) || (op == OP_REL)
              || (op == OP_IN && !word[1]) || (op == OP_ODO);
  endfunction

  function automatic logic [2:0] field_rp(input logic [15:0] w);
    field_rp = w[11:9];
  endfunction

  function automatic logic [2:0] field_rs(input logic [15:0] w);
    field_rs = (w[15:12] == OP_OUT || w[15:12] == OP_LD || w[15:12] == OP_IN
                || w[15:12] == OP_HCFG) ? w[8:6] : w[10:8];
  endfunction

  function automatic logic [2:0] field_rd(input logic [15:0] w);
    case (w[15:12])
      OP_OUT:  field_rd = w[5:3];
      OP_IN:   field_rd = w[5:3];
      OP_PSET: field_rd = w[7:5];
      OP_REL:  field_rd = w[8:6];
      OP_SMP:  field_rd = w[5:3];
      OP_HCFG: field_rd = w[5:3];
      OP_ODO:  field_rd = w[8:6];
      default: field_rd = 3'd0;
    endcase
  endfunction

  // Synced level of a pin. uo pins read 1 (same as JL), except the
  // status pins: 7 reads 0 while rxp holds a byte, 6 reads 0 after overflow.
  function automatic logic pin_lvl(input logic [3:0] pin);
    if (pin[3])
      pin_lvl = uio_s1[pin[2:0]];
    else if (pin[2:0] == 3'd7)
      pin_lvl = !rxp_v;
    else if (pin[2:0] == 3'd6)
      pin_lvl = !rx_ovf;
    else
      pin_lvl = 1'b1;
  endfunction

  function automatic logic pin_low(input logic [3:0] pin);
    pin_low = !pin_lvl(pin);
  endfunction

  function automatic logic [4:0] popcount16(input logic [15:0] m);
    popcount16 = 5'd0;
    for (int i = 0; i < 16; i++)
      popcount16 = popcount16 + {4'd0, m[i]};
  endfunction

  // §4.2: host-read config is legal. Pin-table rules that hardware cannot
  // see (open-drain pads, LDH ready, sampler ui_in bit) are program rules.
  function automatic logic hr_ok(input logic [15:0] m, input logic [3:0] stb,
                                 input logic [2:0] req, input logic rsvd,
                                 input logic son, input logic sui,
                                 input logic [2:0] sidx);
    logic [4:0] n;
    n = popcount16(m);
    hr_ok = (n == 5'd1 || n == 5'd2 || n == 5'd4 || n == 5'd8)
            && !m[stb] && !m[{1'b1, req}] && stb != {1'b1, req} && !rsvd
            && !(son && !sui && (m[{1'b1, sidx}] || stb == {1'b1, sidx}));
  endfunction

  // Read-port addresses. Separate from execute so rdata_* see this address
  // before the decode body uses them.
  always_comb begin
    rf_raddr_p = 3'd0;
    rf_raddr_s = 3'd0;
    rf_raddr_d = 3'd0;
    if (!running || halted || in_wait) begin
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
    end else if (hold == 8'd2 && buf_v && !is_pin(buf_word)
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
    stream_v_n   = stream_v;
    stream_rs_n  = stream_rs;
    ptr_r_n      = ptr_r;
    dptr_n       = dptr;
    bitcnt_n     = bitcnt;
    refill_ren_n = refill_ren;
    refill_pend_n = refill_pend;
    refill_wb_n  = refill_wb;
    man_v_n      = man_v;
    man_at_n     = man_at;
    man_uo_n     = man_uo;
    man_uio_n    = man_uio;
    next_addr_n  = next_addr;
    dmem_ren     = 1'b0;
    dmem_addr    = 8'h00;
    uo_n         = uo_q;
    uio_n        = uio_q;
    oe_n         = oe_q;
    in_wait_n    = in_wait;
    in_ref_n     = in_ref;
    in_pin_n     = in_pin;
    in_rs_n      = in_rs;
    in_val_n     = in_val;
    in_dur_n     = in_dur;
    in_samp_v_n  = in_samp_v;
    in_samp_at_n = in_samp_at;
    in_wr_v_n    = in_wr_v;
    in_wr_val_n  = in_wr_val;
    in_fire      = 1'b0;
    in_fire_rs   = in_rs;
    in_fire_val  = 8'h00;
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
      stream_v_n   = 1'b0;
      stream_rs_n  = 3'd0;
      ptr_r_n      = 3'd0;
      dptr_n       = 8'h00;
      bitcnt_n     = 3'd0;
      refill_ren_n = 1'b0;
      refill_pend_n = 1'b0;
      refill_wb_n  = 1'b0;
      man_v_n      = 1'b0;
      man_at_n     = 8'h00;
      man_uo_n     = 8'h00;
      man_uio_n    = 8'h00;
      next_addr_n  = 8'h00;
      rf_clear     = 1'b1;
      uo_n         = 8'hFF;
      uio_n        = 8'h00;
      oe_n         = 8'h00;
      in_wait_n    = 1'b0;
      in_ref_n     = 1'b0;
      in_pin_n     = 4'd0;
      in_rs_n      = 3'd0;
      in_val_n     = 8'h00;
      in_dur_n     = 8'h00;
      in_samp_v_n  = 1'b0;
      in_samp_at_n = 8'h00;
      in_wr_v_n    = 1'b0;
      in_wr_val_n  = 8'h00;
    end else if (ld_pend) begin
      rf_we       = 1'b1;
      rf_waddr    = ld_dest;
      rf_wdata    = dmem_rdata;
      ld_pend_n   = 1'b0;
      next_addr_n = ld_ret + 8'd1;
      issue       = 1'b1;
      issue_addr  = next_addr_n;
    end else if (halted) begin
    end else if (in_wait) begin
      // INW stall. Keep the prefetched word like a hold would.
      if (asked && !buf_v) begin
        buf_v_n    = 1'b1;
        buf_n      = instr;
        buf_addr_n = asked_addr;
      end
      if (pin_lvl(in_pin) != in_ref) begin
        in_wait_n   = 1'b0;
        // Rd=1 acts as 2 so a buffered word is consumed at hold==1.
        hold_n      = (in_dur == 8'd1) ? 8'd1 : in_dur - 8'd1;
        in_fire     = 1'b1;
        in_fire_rs  = in_rs;
        in_fire_val = {pin_lvl(in_pin), in_val[7:1]};
      end
    end else if (defer_v) begin
      do_start     = 1'b1;
      op_word      = defer_word;
      op_addr      = defer_addr;
      defer_v_n    = 1'b0;
    end else if (asked && hold == 8'h00 && !buf_v) begin
      op_word = instr;
      op_addr = asked_addr;
      if (is_pin(instr))
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
        if (is_pin(op_word))
          do_defer = 1'b1;
        else
          do_one = 1'b1;
      end else if (asked) begin
        buf_v_n    = 1'b1;
        buf_n      = instr;
        buf_addr_n = asked_addr;
        hold_n     = hold - 8'd1;
      end else if (hold == 8'd2 && buf_v && !is_pin(buf_word)
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
          if (stream_v && rn == stream_rs) begin
            stream_v_n = 1'b0;
            bitcnt_n   = 3'd0;
          end
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
          // Keep the decision made at hold==2 if its fetch is in flight.
          if (!(fetched && issue_q)) begin
            next_addr_n = pin_low(rf_rdata_p[3:0]) ? op_word[7:0] : op_addr + 8'd1;
            issue = !fetched;
          end
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
          stream_v_n  = 1'b1;
          stream_rs_n = op_word[11:9];
          ptr_r_n     = op_word[8:6];
          dptr_n      = rf_rdata_s + 8'd1;
          bitcnt_n    = 3'd0;
        end
        OP_HALT: halted_n = 1'b1;
        // Reserved IN modes use the same sequencing as other unused opcodes.
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
        // OUTM (bit 2): IEEE 802.3 Manchester. 1 = low then high, 0 = high then low.
        if (op_word[2]) begin
          level  = ~rf_rdata_s[0];
          level2 = rf_rdata_s[0];
        end else begin
          level  = rf_rdata_s[0];
          level2 = ~rf_rdata_s[0];
        end
        rf_we    = 1'b1;
        rf_waddr = op_word[8:6];
        rf_wdata = {1'b0, rf_rdata_s[7:1]};
        if (op_word[2] && stream_v && op_word[8:6] == stream_rs) begin
          if (bitcnt == 3'd7) begin
            refill_ren_n = 1'b1;
            bitcnt_n     = 3'd0;
          end else
            bitcnt_n = bitcnt + 3'd1;
        end
      end else if (op_word[15:12] == OP_PSET) begin
        // [8]=L1 → pin1; [4]=L2 → pin2. Same pin twice: L1 only.
        level  = op_word[8];
        level2 = two ? op_word[4] : op_word[8];
      end else begin
        level  = 1'b0;
        level2 = 1'b0;
      end

      if (op_word[15:12] == OP_IN) begin
        // Listen only. No uo/uio/oe change.
      end else if (op_word[15:12] == OP_ODO) begin
        // Open-drain txr[7] on pin1 (uio only): 1 releases, 0 drives low.
        if (pin_i[3]) begin
          uio_n[pin_i[2:0]] = 1'b0;
          oe_n[pin_i[2:0]]  = !txr[7];
        end
      end else if (op_word[15:12] == OP_REL) begin
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

      in_samp_v_n = 1'b0;
      if (op_word[15:12] == OP_IN) begin
        in_pin_n = pin_i;
        in_rs_n  = op_word[8:6];
        in_val_n = rf_rdata_s;
        if (op_word[1:0] == 2'b01) begin
          // INW: wait for pin1 to differ from its level now.
          in_wait_n = 1'b1;
          in_ref_n  = pin_lvl(pin_i);
          in_dur_n  = dur;
          hold_n    = 8'h00;
        end else if (dur == 8'd1) begin
          in_fire     = 1'b1;
          in_fire_rs  = op_word[8:6];
          in_fire_val = {pin_lvl(pin_i), rf_rdata_s[7:1]};
        end else begin
          in_samp_v_n  = 1'b1;
          in_samp_at_n = (dur == 8'h00) ? 8'd128 : {1'b0, dur[7:1]};
        end
      end

      man_v_n = 1'b0;
      if (op_word[15:12] == OP_OUT && op_word[2]) begin
        man_at_n = (dur == 8'h00) ? 8'd128 : {1'b0, dur[7:1]};
        if (man_at_n != 8'h00) begin
          man_v_n   = 1'b1;
          man_uo_n  = 8'h00;
          man_uio_n = 8'h00;
          if (pin_i[3] == 1'b0)
            man_uo_n[pin_i[2:0]] = 1'b1;
          else
            man_uio_n[pin_i[2:0]] = 1'b1;
          if (two) begin
            if (pin2_i[3] == 1'b0)
              man_uo_n[pin2_i[2:0]] = 1'b1;
            else
              man_uio_n[pin2_i[2:0]] = 1'b1;
          end
        end
      end
    end

    if (running && man_v && hold == man_at && !do_start) begin
      uo_n    = uo_q ^ man_uo;
      uio_n   = uio_q ^ man_uio;
      man_v_n = 1'b0;
    end

    // IN mid-hold sample. Same clock as the OUTM flip point.
    if (running && in_samp_v && hold == in_samp_at && !do_start) begin
      in_samp_v_n = 1'b0;
      in_fire     = 1'b1;
      in_fire_rs  = in_rs;
      in_fire_val = {pin_lvl(in_pin), in_val[7:1]};
    end
    // 1W: if execute already writes this clock, write the sample next clock.
    if (running && in_wr_v && !rf_we) begin
      rf_we     = 1'b1;
      rf_waddr  = in_rs;
      rf_wdata  = in_wr_val;
      in_wr_v_n = 1'b0;
    end
    if (running && in_fire) begin
      if (!rf_we) begin
        rf_we    = 1'b1;
        rf_waddr = in_fire_rs;
        rf_wdata = in_fire_val;
      end else begin
        in_wr_v_n   = 1'b1;
        in_wr_val_n = in_fire_val;
      end
    end

    // OUTM stream refill lives in leftover hold. 1W: shift already wrote
    // Rs on the start clock; REN, then Rs from dout, then Rm write-back.
    if (running && refill_ren && !ld_pend) begin
      dmem_ren     = 1'b1;
      dmem_addr    = dptr;
      refill_pend_n = 1'b1;
      refill_ren_n = 1'b0;
    end
    if (running && refill_pend && !ld_pend) begin
      rf_we         = 1'b1;
      rf_waddr      = stream_rs;
      rf_wdata      = dmem_rdata;
      refill_pend_n = 1'b0;
      dptr_n        = dptr + 8'd1;
      refill_wb_n   = 1'b1;
    end
    if (running && refill_wb && !ld_pend && !refill_pend) begin
      if (!rf_we) begin
        rf_we       = 1'b1;
        rf_waddr    = ptr_r;
        rf_wdata    = dptr;
        refill_wb_n = 1'b0;
      end
    end

    if (issue)
      asked_addr_n = issue_addr;
  end

  // ---------------------------------------------------------------- RX Stage 1
  // Runs every clock, outside the execute if-chain. Commits come from do_one.
  logic       cap_cmt, smp_cmt, hcfg_cmt, ldh_cmt;
  logic [7:0] cap_val;
  logic       smp_lvl, smp_new_lvl, smp_sample, smp_fire;
  logic [7:0] smp_half;
  logic [2:0] smp_kcur;
  logic [4:0] hr_n;
  logic       hr_pending, hr_serve, tx_busy;
  logic [7:0] hr_chunk_bits;
  logic       hr_last;
  logic [3:0] hr_j;

  always_comb begin
    cap_cmt  = do_one && op_word[15:12] == OP_CAP;
    smp_cmt  = do_one && op_word[15:12] == OP_SMP;
    hcfg_cmt = do_one && op_word[15:12] == OP_HCFG;
    ldh_cmt  = do_one && op_word[15:12] == OP_LDH;

    // CAP forwards a same-clock or pending write of Rs.
    if (in_fire && in_fire_rs == op_word[10:8])
      cap_val = in_fire_val;
    else if (in_wr_v && in_rs == op_word[10:8])
      cap_val = in_wr_val;
    else if (refill_pend && stream_rs == op_word[10:8])
      cap_val = dmem_rdata;
    else
      cap_val = rf_rdata_s;

    // TX ops (PSET, OUT/OUTM, ODO) block a serve while their hold runs.
    if (do_start)
      hold_tx_n = (op_word[15:12] == OP_PSET || op_word[15:12] == OP_OUT
                   || op_word[15:12] == OP_ODO) && hold_n != 8'h00;
    else
      hold_tx_n = (hold_n == 8'h00) ? 1'b0 : hold_tx;
    tx_busy = (hold != 8'h00) && hold_tx;

    txr_n = txr;
    if (ldh_cmt)
      txr_n = byte_s2;
    else if (do_start && op_word[15:12] == OP_ODO)
      txr_n = {txr[6:0], 1'b0};

    // Sampler. Sample k is in the clock that ends at edge E + half + B*(k+1).
    smp_on_n   = smp_on;
    smp_ui_n   = smp_ui;
    smp_idx_n  = smp_idx;
    smp_b_n    = smp_b;
    smp_idle_n = smp_idle;
    smp_st_n   = smp_st;
    smp_ph_n   = smp_ph;
    smp_t_n    = smp_t;
    smp_k_n    = smp_k;
    smp_sh_n   = smp_sh;
    smp_lvl    = smp_ui ? byte_s2[smp_idx] : uio_s1[smp_idx];
    smp_new_lvl = rf_rdata_p[7] ? byte_s2[rf_rdata_p[2:0]] : uio_s1[rf_rdata_p[2:0]];
    smp_half   = (smp_b == 8'h00) ? 8'd128 : {1'b0, smp_b[7:1]};
    smp_sample = 1'b0;
    smp_fire   = 1'b0;
    smp_kcur   = smp_k;
    if (smp_cmt) begin
      smp_on_n   = rf_rdata_p[7] || rf_rdata_p[3];
      smp_ui_n   = rf_rdata_p[7];
      smp_idx_n  = rf_rdata_p[2:0];
      smp_b_n    = rf_rdata_d;
      smp_idle_n = smp_new_lvl;
      smp_st_n   = SMP_EDGE;
      smp_k_n    = 3'd0;               // a re-arm mid-byte restarts at sample 0
    end else if (smp_on) begin
      case (smp_st)
        SMP_IDLE: if (smp_lvl == smp_idle) smp_st_n = SMP_EDGE;
        SMP_EDGE: if (smp_lvl != smp_idle) begin
          // This clock is the first one after E.
          smp_st_n = SMP_RUN;
          smp_kcur = 3'd0;
          smp_k_n  = 3'd0;
          if (smp_half == 8'd0)
            smp_sample = 1'b1;          // B=1: sample 0 is this clock
          else if (smp_half == 8'd1) begin
            smp_ph_n = 1'b1;
            smp_t_n  = smp_b - 8'd1;
          end else begin
            smp_ph_n = 1'b0;
            smp_t_n  = smp_half - 8'd2;
          end
        end
        SMP_RUN: begin
          if (smp_t != 8'h00)
            smp_t_n = smp_t - 8'd1;
          else if (!smp_ph) begin
            smp_ph_n = 1'b1;
            smp_t_n  = smp_b - 8'd1;    // B=0: 255 means 256 clocks
          end else
            smp_sample = 1'b1;
        end
        default: smp_st_n = SMP_IDLE;
      endcase
      if (smp_sample) begin
        smp_sh_n = {smp_lvl, smp_sh[7:1]};
        smp_ph_n = 1'b1;
        smp_t_n  = smp_b - 8'd1;
        smp_k_n  = smp_kcur + 3'd1;
        if (smp_kcur == 3'd7) begin
          smp_fire = 1'b1;
          smp_st_n = SMP_IDLE;
        end
      end
    end

    // Capture into rxp. Accept only while rxp is empty; sampler wins a tie.
    rxp_n    = rxp;
    rxp_v_n  = rxp_v;
    rx_ovf_n = rx_ovf;
    if (smp_fire) begin
      if (!rxp_v) begin
        rxp_n   = smp_sh_n;
        rxp_v_n = 1'b1;
      end else
        rx_ovf_n = 1'b1;
      if (cap_cmt)
        rx_ovf_n = 1'b1;
    end else if (cap_cmt) begin
      if (!rxp_v) begin
        rxp_n   = cap_val;
        rxp_v_n = 1'b1;
      end else
        rx_ovf_n = 1'b1;
    end

    // Host-read config and validity.
    hm_n          = hm;
    hr_stb_n      = hr_stb;
    hr_req_n      = hr_req;
    hr_rsvd_bad_n = hr_rsvd_bad;
    hr_valid_n    = hr_valid;
    if (hcfg_cmt) begin
      hm_n          = {rf_rdata_s, rf_rdata_p};
      hr_stb_n      = rf_rdata_d[7:4];
      hr_req_n      = rf_rdata_d[2:0];
      hr_rsvd_bad_n = rf_rdata_d[3];
    end
    if (hcfg_cmt || smp_cmt)
      hr_valid_n = hr_ok(hm_n, hr_stb_n, hr_req_n, hr_rsvd_bad_n,
                         smp_on_n, smp_ui_n, smp_idx_n);

    // Chunk handshake.
    hr_n = popcount16(hm);
    case (hr_n)
      5'd1:    begin hr_chunk_bits = {7'd0, rxp[hr_chunk]};                   hr_last = hr_chunk == 3'd7; end
      5'd2:    begin hr_chunk_bits = {6'd0, rxp[{hr_chunk[1:0], 1'b0} +: 2]}; hr_last = hr_chunk == 3'd3; end
      5'd4:    begin hr_chunk_bits = {4'd0, rxp[{hr_chunk[0], 2'b00} +: 4]};  hr_last = hr_chunk == 3'd1; end
      default: begin hr_chunk_bits = rxp;                                     hr_last = 1'b1; end
    endcase
    hr_pending = hr_valid && hr_blank == 2'd0 && uio_s1[hr_req] != hr_req_last;
    hr_serve   = hr_pending && rxp_v && !tx_busy && !serve_d && hr_valid_n;

    hr_req_last_n = hr_req_last;
    hr_blank_n    = hr_blank;
    hr_stb_q_n    = hr_stb_q;
    hr_chunk_n    = hr_chunk;
    hr_dout_n     = hr_dout;
    serve_d_n     = serve_d;
    if (hcfg_cmt || hr_valid_n != hr_valid) begin
      // HCFG commit or validity change. Wins over a pending E+1 serve:
      // the chunk is not consumed and rxp_v does not change.
      hr_chunk_n    = 3'd0;
      hr_dout_n     = 8'h00;
      hr_stb_q_n    = hr_stb_n[3] ? pad_uio[hr_stb_n[2:0]] : pad_uo[hr_stb_n[2:0]];
      hr_req_last_n = uio_s1[hr_req_n];
      hr_blank_n    = 2'd3;
      serve_d_n     = 1'b0;
    end else begin
      if (hr_blank != 2'd0) begin
        hr_blank_n    = hr_blank - 2'd1;
        hr_req_last_n = uio_s1[hr_req];
      end
      if (hr_serve) begin                // edge E: strobe
        hr_stb_q_n    = !hr_stb_q;
        hr_req_last_n = uio_s1[hr_req];
        serve_d_n     = 1'b1;
      end
      if (serve_d) begin                 // edge E+1: data
        hr_dout_n  = hr_chunk_bits;
        hr_chunk_n = hr_last ? 3'd0 : hr_chunk + 3'd1;
        if (hr_last)
          rxp_v_n = 1'b0;
        serve_d_n  = 1'b0;
      end
    end

    // Pad next state: core values, overlaid while the config is valid.
    pad_uo_n  = uo_n;
    pad_uio_n = uio_n;
    pad_oe_n  = oe_n;
    hr_j      = 4'd0;
    if (hr_valid_n) begin
      for (int p = 0; p < 8; p++)
        if (hm_n[p]) begin
          pad_uo_n[p] = hr_dout_n[hr_j[2:0]];
          hr_j = hr_j + 4'd1;
        end
      for (int p = 0; p < 8; p++)
        if (hm_n[8 + p]) begin
          pad_uio_n[p] = hr_dout_n[hr_j[2:0]];
          pad_oe_n[p]  = 1'b1;
          hr_j = hr_j + 4'd1;
        end
      if (hr_stb_n[3]) begin
        pad_uio_n[hr_stb_n[2:0]] = hr_stb_q_n;
        pad_oe_n[hr_stb_n[2:0]]  = 1'b1;
      end else
        pad_uo_n[hr_stb_n[2:0]] = hr_stb_q_n;
      pad_oe_n[hr_req_n] = 1'b0;
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      rxp         <= 8'h00;
      rxp_v       <= 1'b0;
      rx_ovf      <= 1'b0;
      smp_on      <= 1'b0;
      smp_ui      <= 1'b0;
      smp_idx     <= 3'd0;
      smp_b       <= 8'h00;
      smp_idle    <= 1'b0;
      smp_st      <= SMP_IDLE;
      smp_ph      <= 1'b0;
      smp_t       <= 8'h00;
      smp_k       <= 3'd0;
      smp_sh      <= 8'h00;
      hm          <= 16'h0000;
      hr_stb      <= 4'd0;
      hr_req      <= 3'd0;
      hr_rsvd_bad <= 1'b0;
      hr_valid    <= 1'b0;
      hr_req_last <= 1'b0;
      hr_blank    <= 2'd0;
      hr_stb_q    <= 1'b0;
      hr_chunk    <= 3'd0;
      hr_dout     <= 8'h00;
      serve_d     <= 1'b0;
      hold_tx     <= 1'b0;
      txr         <= 8'h00;
      pad_uo      <= 8'hFF;
      pad_uio     <= 8'h00;
      pad_oe      <= 8'h00;
    end else begin
      rxp         <= rxp_n;
      rxp_v       <= rxp_v_n;
      rx_ovf      <= rx_ovf_n;
      smp_on      <= smp_on_n;
      smp_ui      <= smp_ui_n;
      smp_idx     <= smp_idx_n;
      smp_b       <= smp_b_n;
      smp_idle    <= smp_idle_n;
      smp_st      <= smp_st_n;
      smp_ph      <= smp_ph_n;
      smp_t       <= smp_t_n;
      smp_k       <= smp_k_n;
      smp_sh      <= smp_sh_n;
      hm          <= hm_n;
      hr_stb      <= hr_stb_n;
      hr_req      <= hr_req_n;
      hr_rsvd_bad <= hr_rsvd_bad_n;
      hr_valid    <= hr_valid_n;
      hr_req_last <= hr_req_last_n;
      hr_blank    <= hr_blank_n;
      hr_stb_q    <= hr_stb_q_n;
      hr_chunk    <= hr_chunk_n;
      hr_dout     <= hr_dout_n;
      serve_d     <= serve_d_n;
      hold_tx     <= hold_tx_n;
      txr         <= txr_n;
      pad_uo      <= pad_uo_n;
      pad_uio     <= pad_uio_n;
      pad_oe      <= pad_oe_n;
    end
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
      stream_v   <= 1'b0;
      stream_rs  <= 3'd0;
      ptr_r      <= 3'd0;
      dptr       <= 8'h00;
      bitcnt     <= 3'd0;
      refill_ren <= 1'b0;
      refill_pend <= 1'b0;
      refill_wb  <= 1'b0;
      man_v      <= 1'b0;
      man_at     <= 8'h00;
      man_uo     <= 8'h00;
      man_uio    <= 8'h00;
      next_addr  <= 8'h00;
      uo_q       <= 8'hFF;
      uio_q      <= 8'h00;
      oe_q       <= 8'h00;
      in_wait    <= 1'b0;
      in_ref     <= 1'b0;
      in_pin     <= 4'd0;
      in_rs      <= 3'd0;
      in_val     <= 8'h00;
      in_dur     <= 8'h00;
      in_samp_v  <= 1'b0;
      in_samp_at <= 8'h00;
      in_wr_v    <= 1'b0;
      in_wr_val  <= 8'h00;
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
      stream_v   <= stream_v_n;
      stream_rs  <= stream_rs_n;
      ptr_r      <= ptr_r_n;
      dptr       <= dptr_n;
      bitcnt     <= bitcnt_n;
      refill_ren <= refill_ren_n;
      refill_pend <= refill_pend_n;
      refill_wb  <= refill_wb_n;
      man_v      <= man_v_n;
      man_at     <= man_at_n;
      man_uo     <= man_uo_n;
      man_uio    <= man_uio_n;
      next_addr  <= next_addr_n;
      uo_q       <= uo_n;
      uio_q      <= uio_n;
      oe_q       <= oe_n;
      in_wait    <= in_wait_n;
      in_ref     <= in_ref_n;
      in_pin     <= in_pin_n;
      in_rs      <= in_rs_n;
      in_val     <= in_val_n;
      in_dur     <= in_dur_n;
      in_samp_v  <= in_samp_v_n;
      in_samp_at <= in_samp_at_n;
      in_wr_v    <= in_wr_v_n;
      in_wr_val  <= in_wr_val_n;
    end
  end

endmodule
