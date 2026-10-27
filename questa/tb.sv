`default_nettype none
`timescale 1ns / 1ps

// Standalone Questasim testbench.
// Loads program.hex (one 16-bit word per line, hex), strobes it into the
// DUT the same way the host does, then runs until HALT or a timeout.
// External pull-ups on uio[3:2] stand in for I2C SDA/SCL.
module tb;

  localparam int CLK_NS     = 20;
  localparam int MAX_WORDS  = 256;
  localparam int RUN_LIMIT  = 20000;

  logic        clk;
  logic        rst_n;
  logic        ena;
  logic [7:0]  ui_in;
  logic [7:0]  uio_in;
  wire  [7:0]  uo_out;
  wire  [7:0]  uio_out;
  wire  [7:0]  uio_oe;

  logic [15:0] program_mem [0:MAX_WORDS-1];
  int          program_len;
  int          i;
  int          clocks;
  string       hex_path;

  tt_um_RaghuvPotdar_Leonidas DUT (
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  // Open-drain view of I2C: pad is low only while oe is on and out is 0.
  wire sda_pad = uio_oe[2] ? uio_out[2] : uio_in[2];
  wire scl_pad = uio_oe[3] ? uio_out[3] : uio_in[3];

  initial clk = 0;
  always #(CLK_NS / 2) clk = ~clk;

  task automatic edge_clk;
    @(posedge clk);
    #1;
  endtask

  task automatic byte_strobe(input logic [1:0] code, input logic [7:0] data);
    ui_in  = data;
    uio_in = {6'b0, code};
    edge_clk();
    uio_in = 8'h00;
    edge_clk();
  endtask

  task automatic load_hex(input string path);
    int fd;
    int code;
    logic [15:0] word;
    program_len = 0;
    fd = $fopen(path, "r");
    if (fd == 0) begin
      $fatal(1, "cannot open %s", path);
    end
    while (!$feof(fd) && program_len < MAX_WORDS) begin
      code = $fscanf(fd, "%h", word);
      if (code == 1) begin
        program_mem[program_len] = word;
        program_len++;
      end else begin
        code = $fgetc(fd);
      end
    end
    $fclose(fd);
    $display("loaded %0d words from %s", program_len, path);
  endtask

  initial begin
    if (!$value$plusargs("PROGRAM=%s", hex_path))
      hex_path = "program.hex";
    load_hex(hex_path);

    ena    = 1;
    ui_in  = 0;
    uio_in = 0;
    rst_n  = 0;
    edge_clk();
    rst_n  = 1;
    edge_clk();

    for (i = 0; i < program_len; i++) begin
      byte_strobe(2'b01, program_mem[i][7:0]);
      if (i == program_len - 1)
        byte_strobe(2'b10, program_mem[i][15:8]);
      else
        byte_strobe(2'b01, program_mem[i][15:8]);
    end

    // Idle strobe. Pull-ups on SDA/SCL (uio[2]/uio[3]).
    uio_in = 8'b0000_1100;

    clocks = 0;
    while (clocks < RUN_LIMIT) begin
      edge_clk();
      clocks++;
      if (DUT.datapath.halted === 1'b1)
        break;
    end

    $display("done after %0d clocks, halted=%0b uo_out=%02h uio_oe=%02h",
             clocks, DUT.datapath.halted, uo_out, uio_oe);
    $finish;
  end

endmodule
