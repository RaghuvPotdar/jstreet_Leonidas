`default_nettype none
`timescale 1ns / 1ps

// Standalone Questasim testbench.
// +PROGRAM=foo.hex runs one listing. No plusarg runs the suite in order.
// +DMEM=foo.dmem strobes 11 after reset, before the imem 10 start.
// Without +DMEM the bench tries foo.dmem next to the hex (missing = skip).
// test_id / test_name are for the wave window (not DUT pins).
//   0 = host load (ui/uio strobes)
//   1 = uart        pin 1, 16 clocks/bit, 0xB1
//   2 = spi         pins 2/3/4 CS/SCK/MOSI
//   3 = usb_ls_ack  pins 4/5, 40 clocks/bit
//   4 = usb_fs_ack  pins 4/5, 5 clocks/bit
//   5 = eth_10t     pin 6, IEEE Manchester, 6 clocks/bit
// I2C / USB dummy / LD / OUTM unit tests live in cocotb (test/), not here.
module tb;

  localparam int CLK_NS     = 20;
  localparam int MAX_WORDS  = 256;
  localparam int RUN_LIMIT  = 20000;
  localparam int SUITE_N    = 5;

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
  int          clocks;
  string       hex_path;
  string       dmem_path;

  // Wave markers. Analog test_id; test_name is the listing.
  int          test_id;
  string       test_name;

  string suite_hex  [0:SUITE_N-1];
  string suite_name [0:SUITE_N-1];

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

  function automatic string dmem_beside(input string hex);
    int n;
    n = hex.len();
    if (n >= 4 && hex.substr(n - 4, n - 1) == ".hex")
      return {hex.substr(0, n - 5), ".dmem"};
    return {hex, ".dmem"};
  endfunction

  // Strobe 11, one byte per edge pair. Must run after rst_n, before imem 10.
  task automatic load_dmem_hex(input string path, input bit required);
    int fd;
    int code;
    int n;
    logic [7:0] b;
    fd = $fopen(path, "r");
    if (fd == 0) begin
      if (required)
        $fatal(1, "cannot open %s", path);
      return;
    end
    n = 0;
    while (!$feof(fd) && n < 256) begin
      code = $fscanf(fd, "%h", b);
      if (code == 1) begin
        byte_strobe(2'b11, b);
        n++;
      end else begin
        code = $fgetc(fd);
      end
    end
    $fclose(fd);
    $display("loaded %0d dmem bytes from %s", n, path);
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

  task automatic run_listing(input int id, input string name, input string path);
    test_id   = 0;
    test_name = "load";
    load_hex(path);

    ena    = 1;
    ui_in  = 0;
    uio_in = 0;
    rst_n  = 0;
    edge_clk();
    rst_n  = 1;
    edge_clk();

    if (dmem_path.len() != 0)
      load_dmem_hex(dmem_path, 1);
    else
      load_dmem_hex(dmem_beside(path), 0);

    begin
      int wi;
      for (wi = 0; wi < program_len; wi++) begin
        byte_strobe(2'b01, program_mem[wi][7:0]);
        if (wi == program_len - 1)
          byte_strobe(2'b10, program_mem[wi][15:8]);
        else
          byte_strobe(2'b01, program_mem[wi][15:8]);
      end
    end

    // Host bus idle. Do not leave the last opcode byte on ui_in.
    ui_in  = 8'h00;
    uio_in = 8'b0000_1100;

    test_id   = id;
    test_name = name;

    clocks = 0;
    while (clocks < RUN_LIMIT) begin
      edge_clk();
      clocks++;
      if (DUT.datapath.halted === 1'b1)
        break;
    end

    $display("test %0d %s: %0d clocks halted=%0b uo=%02h",
             id, name, clocks, DUT.datapath.halted, uo_out);
  endtask

  initial begin
    suite_name[0] = "uart";
    suite_hex[0]  = "suite/uart.hex";
    suite_name[1] = "spi";
    suite_hex[1]  = "suite/spi.hex";
    suite_name[2] = "usb_ls_ack";
    suite_hex[2]  = "suite/usb_ls_ack.hex";
    suite_name[3] = "usb_fs_ack";
    suite_hex[3]  = "suite/usb_fs_ack.hex";
    suite_name[4] = "eth_10t";
    suite_hex[4]  = "suite/eth_10t.hex";

    test_id   = 0;
    test_name = "idle";
    ena       = 1;
    ui_in     = 0;
    uio_in    = 0;
    rst_n     = 0;

    if (!$value$plusargs("DMEM=%s", dmem_path))
      dmem_path = "";

    if ($value$plusargs("PROGRAM=%s", hex_path)) begin
      if (!$value$plusargs("TESTNAME=%s", test_name))
        test_name = hex_path;
      run_listing(1, test_name, hex_path);
    end else begin
      begin
        int s;
        for (s = 0; s < SUITE_N; s++)
          run_listing(s + 1, suite_name[s], suite_hex[s]);
      end
    end

    test_id   = 0;
    test_name = "done";
    $finish;
  end

endmodule
