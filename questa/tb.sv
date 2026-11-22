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
//   6 = uart_rx_echo     tb drives UART on uio[2] (B1, 5A, 0F at 0/+3/-3%),
//                        DUT echoes on uo[1]
//   7 = eth_10t_rx_echo  tb drives 64 Manchester bits on uio[6] (+3% skew),
//                        DUT echoes the last byte (A3) as UART on uo[1]
// rx_line / rx_byte = what the tb is sending; echo_byte = decoded uo[1].
// I2C / USB dummy / LD / OUTM unit tests live in cocotb (test/), not here.
module tb;

  localparam int CLK_NS     = 20;
  localparam int MAX_WORDS  = 256;
  localparam int RUN_LIMIT  = 20000;
  localparam int SUITE_N    = 7;
  localparam logic [7:0] UART_RX_BYTES [0:2] = '{8'hB1, 8'h5A, 8'h0F};
  localparam logic [7:0] ETH_RX_FRAME [0:7] =
      '{8'h55, 8'h55, 8'h55, 8'h55, 8'h55, 8'h55, 8'hD5, 8'hA3};

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

  // RX stimulus markers.
  logic [7:0]  rx_idle;
  logic        rx_line;
  logic [7:0]  rx_byte;
  logic [7:0]  echo_byte;

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
    uio_in = rx_idle | {6'b0, code};
    edge_clk();
    uio_in = rx_idle;
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

  // 8N1 on uio_in[idx], LSB first, async to clk.
  task automatic uart_send(input int idx, input logic [7:0] b, input realtime bit_ns);
    logic [9:0] f;
    f = {1'b1, b, 1'b0};
    rx_byte = b;
    for (int i = 0; i < 10; i++) begin
      uio_in[idx] = f[i];
      rx_line     = f[i];
      #(bit_ns);
    end
  endtask

  // IEEE 802.3 Manchester: 1 = low then high, 0 = high then low. LSB first.
  task automatic manchester_send(input int idx, input logic [7:0] b, input realtime half_ns);
    rx_byte = b;
    for (int i = 0; i < 8; i++) begin
      uio_in[idx] = ~b[i]; rx_line = ~b[i]; #(half_ns);
      uio_in[idx] =  b[i]; rx_line =  b[i]; #(half_ns);
    end
  endtask

  task automatic drive_rx(input string name);
    if (name == "uart_rx_echo") begin
      // byte, baud error, start phase (fraction of a clock)
      real        errs  [3] = '{0.0, 0.03, -0.03};
      real        phs   [3] = '{0.37, 0.81, 0.12};
      for (int k = 0; k < $size(UART_RX_BYTES); k++) begin
        repeat (40) @(posedge clk);
        #(phs[k] * CLK_NS);
        uart_send(2, UART_RX_BYTES[k], 16.0 * CLK_NS * (1.0 + errs[k]));
        repeat (200) @(posedge clk);   // echo is in flight
      end
    end else if (name == "eth_10t_rx_echo") begin
      repeat (20) @(posedge clk);
      #(0.2 * CLK_NS);
      foreach (ETH_RX_FRAME[k]) manchester_send(6, ETH_RX_FRAME[k], 3.0 * CLK_NS * 1.03);
      uio_in[6] = 0; rx_line = 0;
    end
  endtask

  // Decode 8N1 frames on uo_out[1] at 16 clocks/bit.
  task automatic echo_mon(input string name, input int expected_count, ref int echo_count);
    logic [7:0] expected_byte;
    forever begin
      @(negedge uo_out[1]);
      repeat (8) @(posedge clk);
      if (uo_out[1] == 1'b0) begin
        if (expected_count != 0 && echo_count >= expected_count)
          $fatal(1, "%s: unexpected extra echo", name);
        for (int i = 0; i < 8; i++) begin
          repeat (16) @(posedge clk);
          echo_byte[i] = uo_out[1];
        end
        repeat (16) @(posedge clk);
        if (expected_count != 0) begin
          expected_byte = (name == "uart_rx_echo") ? UART_RX_BYTES[echo_count] :
                          ETH_RX_FRAME[$high(ETH_RX_FRAME)];
          if (echo_byte !== expected_byte || uo_out[1] !== 1'b1)
            $fatal(1, "%s: echo %0d expected %02h and stop=1, got %02h and stop=%0b",
                   name, echo_count, expected_byte, echo_byte, uo_out[1]);
          echo_count++;
        end
        $display("  echo %02h  (sent %02h)  stop=%0b uio_oe=%02h",
                 echo_byte, rx_byte, uo_out[1], uio_oe);
      end
    end
  endtask

  task automatic run_listing(input int id, input string name, input string path);
    int expected_count;
    int echo_count;
    expected_count = 0;
    echo_count = 0;
    if (name == "uart_rx_echo")
      expected_count = $size(UART_RX_BYTES);
    else if (name == "eth_10t_rx_echo")
      expected_count = 1;
    test_id   = 0;
    test_name = "load";
    load_hex(path);

    rx_idle   = (name == "uart_rx_echo") ? 8'h04 : 8'h00;
    rx_line   = rx_idle[2];
    rx_byte   = 0;
    echo_byte = 0;
    ena    = 1;
    ui_in  = 0;
    uio_in = rx_idle;
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
    uio_in = (name == "uart_rx_echo" || name == "eth_10t_rx_echo")
             ? rx_idle : 8'b0000_1100;

    test_id   = id;
    test_name = name;

    fork
      drive_rx(name);
      echo_mon(name, expected_count, echo_count);
    join_none

    clocks = 0;
    while (clocks < RUN_LIMIT) begin
      edge_clk();
      clocks++;
      if (DUT.datapath.halted === 1'b1)
        break;
    end
    disable fork;

    if (expected_count != 0) begin
      if (DUT.datapath.halted !== 1'b1)
        $fatal(1, "%s: did not halt within %0d clocks", name, RUN_LIMIT);
      if (echo_count != expected_count)
        $fatal(1, "%s: expected %0d echoes, got %0d", name, expected_count, echo_count);
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
    suite_name[5] = "uart_rx_echo";
    suite_hex[5]  = "suite/uart_rx_echo.hex";
    suite_name[6] = "eth_10t_rx_echo";
    suite_hex[6]  = "suite/eth_10t_rx_echo.hex";

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
