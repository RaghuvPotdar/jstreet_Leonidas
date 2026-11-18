# Graph Report - jstreet_Leonidas  (2026-11-17)

## Corpus Check
- Corpus is ~35,774 words - fits in a single context window. You may not need a graph.

## Summary
- 375 nodes · 581 edges · 23 communities (14 shown, 9 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 53 edges (avg confidence: 0.85)
- Token cost: 294,905 input · 0 output

## Community Hubs (Navigation)
- Cocotb Test Suite
- Datapath RTL Core
- TinyTapeout Pinout
- Architecture & Roadmap
- RX Plans & IN Opcode
- Assembler
- GDS Workflow Config
- GDS CI Run (Failed)
- FPGA Workflow
- Ethernet TX Helpers
- Docs Workflow
- Workflow Step Keys
- IHP Stdcell Sim Model
- Test Workflow
- TT Support Script
- SWD & REL
- BADPIGGY Idea
- CAN Plan
- HALT Opcode
- LDI Opcode
- Test Requirements

## God Nodes (most connected - your core abstractions)
1. `assemble()` - 26 edges
2. `pinout` - 25 edges
3. `clock_edge()` - 16 edges
4. `test_uart_program()` - 16 edges
5. `test` - 15 edges
6. `test_dmem_ld()` - 14 edges
7. `reset_dut()` - 13 edges
8. `test_outm_mid_invert()` - 13 edges
9. `test_eth_10t_loop()` - 13 edges
10. `test_ldi_then_out()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Leonidas 16-bit ISA` --conceptually_related_to--> `assemble()`  [INFERRED]
  docs/isa.md → asm/assemble.py
- `Assembler usage (assemble.py -q / -o, .dmem sidecar)` --references--> `assemble()`  [EXTRACTED]
  docs/sim.md → asm/assemble.py
- `Leonidas 16-bit ISA` --conceptually_related_to--> `datapath`  [INFERRED]
  docs/isa.md → src/datapath.sv
- `I2C master write (inline in test.py)` --references--> `test_uart_program()`  [EXTRACTED]
  docs/listings.md → test/test.py
- `UART frame format programmability (clocks/bit, parity, width, stop)` --semantically_similar_to--> `Duration Rd / hold counter`  [INFERRED] [semantically similar]
  notes/programmability.md → docs/isa.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Silicon opcode set (verbs)** — docs_isa_ldi, docs_isa_pset, docs_isa_out, docs_isa_outm, docs_isa_djnz, docs_isa_halt, docs_isa_rel, docs_isa_jl, docs_isa_ld, docs_isa_in [EXTRACTED 1.00]
- **TX protocol listings on the same verbs** — docs_listings_uart_tx, docs_listings_spi_mode0_tx, docs_listings_i2c_master_write, docs_listings_usb_ls_ack, docs_listings_usb_fs_ack, docs_listings_10base_t_tx [EXTRACTED 1.00]
- **RX/extract design (IN, RX SRAM, EXT)** — docs_future_in_original_draft, docs_future_rx_sram, docs_future_ext_opcode, docs_programmability_pin_input_strobes [INFERRED 0.85]
- **GDS hardening pipeline up to lint failure** — test_results_logs_109904887355_3_gds_tt_gds_action, test_results_logs_109904887355_3_gds_tt_tool, test_results_logs_109904887355_3_gds_librelane, test_results_logs_109904887355_3_gds_verilator_lint, test_results_logs_109904887355_3_gds_lint_errors_checker [EXTRACTED 1.00]
- **Lint failure chain stopping GDS harden** — test_results_logs_109904887355_gds_3_build_gds_harden, test_results_logs_109904887355_gds_3_build_gds_librelane, test_results_logs_109904887355_gds_3_build_gds_verilator_lint, test_results_logs_109904887355_gds_3_build_gds_multidriven_error, test_results_logs_109904887355_gds_3_build_gds_lint_errors_checker, test_results_logs_109904887355_gds_3_build_gds_datapath_instance [EXTRACTED 1.00]
- **GDS CI job steps** — test_results_logs_109904887355_gds_1_set_up_job_set_up_job, test_results_logs_109904887355_gds_2_checkout_repo_checkout_repo, test_results_logs_109904887355_gds_3_build_gds_build_gds, test_results_logs_109904887355_gds_5_post_build_gds_post_build_gds, test_results_logs_109904887355_gds_6_post_checkout_repo_post_checkout_repo, test_results_logs_109904887355_gds_7_complete_job_complete_job [INFERRED 0.85]

## Communities (23 total, 9 thin omitted)

### Community 0 - "Cocotb Test Suite"
Cohesion: 0.09
Nodes (34): encode_out(), test, runs-on, assert_eth_runs(), byte_strobe(), clock_edge(), engine(), eth_tx() (+26 more)

### Community 1 - "Datapath RTL Core"
Cohesion: 0.05
Nodes (28): 60 MHz target clock, tt_um_RaghuvPotdar_Leonidas top module, datapath, dmem, imem, tt_um_RaghuvPotdar_Leonidas, rf, blackbox (+20 more)

### Community 2 - "TinyTapeout Pinout"
Cohesion: 0.05
Nodes (36): pinout, ui[0], ui[1], ui[2], ui[3], ui[4], ui[5], ui[6] (+28 more)

### Community 3 - "Architecture & Roadmap"
Cohesion: 0.06
Nodes (32): Compiler pipeline (protocol dict -> asm + dmem -> hex), Non-blocking IN (thought), Roadmap (TX listings -> RX -> details -> optimize), Two cores (core0/core1) for independent timebases, External hardware (off-chip PHYs, I2C pull-ups), Host load strobes (uio_in[1:0]), How to test (load and start procedure), Fetch pipeline (pc / issue / asked / buf_v) (+24 more)

### Community 4 - "RX Plans & IN Opcode"
Cohesion: 0.08
Nodes (30): EXT opcode (draft, likely 1001), IN original draft (superseded), JTAG (IEEE 1149.1) plan, PS/2 plan, RX pending per protocol, RX SRAM (third 256x8 macro), DJNZ (0011), dmem (256x8 payload SRAM) (+22 more)

### Community 5 - "Assembler"
Cohesion: 0.14
Nodes (23): assemble(), encode(), encode_in(), encode_jl(), encode_ld(), encode_pset(), encode_rel(), main() (+15 more)

### Community 6 - "GDS Workflow Config"
Cohesion: 0.08
Nodes (28): runs-on, steps, needs, runs-on, steps, jobs, gds, gl_test (+20 more)

### Community 7 - "GDS CI Run (Failed)"
Cohesion: 0.09
Nodes (29): actions/checkout@v6, Step 1: Set up job, TinyTapeout/tt-gds-action@ttihp26b, GitHub hosted runner ubuntu-24.04 (runner 2.338.0, Azure westus), Step 2: checkout repo (RaghuvPotdar/jstreet_Leonidas @618cb6b, submodules recursive), Step 3: Build GDS (FAILED, exit code 1), awalsh128/cache-apt-pkgs-action (ghdl-llvm, librsvg2-bin, pngquant), tt_tool.py --create-user-config (fetch verilog & build config) (+21 more)

### Community 8 - "FPGA Workflow"
Cohesion: 0.14
Nodes (13): runs-on, steps, jobs, fpga, name, on, push, workflow_dispatch (+5 more)

### Community 9 - "Ethernet TX Helpers"
Cohesion: 0.18
Nodes (4): expect_runs(), ieee_halves(), lsb_bits(), recover_bits()

### Community 10 - "Docs Workflow"
Cohesion: 0.15
Nodes (12): runs-on, steps, jobs, docs, name, on, push, workflow_dispatch (+4 more)

### Community 11 - "Workflow Step Keys"
Cohesion: 0.17
Nodes (12): if, name, run, shell, uses, with, steps, name (+4 more)

### Community 12 - "IHP Stdcell Sim Model"
Cohesion: 0.42
Nodes (6): connect_delayed_nets(), delayed_names(), input_names(), main(), strip_specify(), transform()

### Community 13 - "Test Workflow"
Cohesion: 0.50
Nodes (3): jobs, name, on

## Knowledge Gaps
- **35 isolated node(s):** `blackbox`, `blackbox`, `LibreLane ASIC build`, `60 MHz target clock`, `SWD plan` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 169 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `assemble()` connect `Assembler` to `Cocotb Test Suite`, `Architecture & Roadmap`, `IHP Stdcell Sim Model`?**
  _High betweenness centrality (0.269) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `assemble()` (e.g. with `Leonidas 16-bit ISA` and `test_eth_10t()`) actually correct?**
  _`assemble()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `blackbox`, `blackbox`, `LibreLane ASIC build` to the rest of the system?**
  _35 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Cocotb Test Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.08766803039158387 - nodes in this community are weakly interconnected._
- **Why does `Leonidas 16-bit ISA` connect `Architecture & Roadmap` to `Datapath RTL Core`, `RX Plans & IN Opcode`, `Assembler`?**
  _High betweenness centrality (0.245) - this node is a cross-community bridge._
- **Should `Datapath RTL Core` be split into smaller, more focused modules?**
  _Cohesion score 0.049494949494949494 - nodes in this community are weakly interconnected._
- **Why does `datapath` connect `Datapath RTL Core` to `Architecture & Roadmap`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._