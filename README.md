![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Leonidas

Leonidas is a programmable pin machine for the Jane Street protocol emulator ASIC competition. The host loads 16-bit instructions and optional payload bytes through the Tiny Tapeout pins. To change protocols, reset and load a different program.

Timed instructions set, release, shift to, or sample a pin. Branches and register operations can use the remaining clocks of a timed instruction. `INW` waits on a synchronized pin transition, which lets a Manchester receiver lock to each bit. Instruction and payload bytes live in separate SRAMs.

- [ISA and instruction timing](docs/isa.md)
- [Example programs](docs/listings.md), including I²C write with ACK and clock-stretch handling
- [Pinout and host loading](docs/info.md)
- [Simulation and gate-level commands](docs/sim.md)

The cocotb regressions exercise the host loading strobes, SRAM reads, protocol timing, and RX across input phase and clock skew. The Questa suite provides waveforms and checks UART and Manchester echo data, stop bits, and completion. Codex implemented the RX review fixes and the flow migration. Claude Code reviewed prefetch timing and helped identify SRAM power connectivity as a migration risk.

## Reproduce the demos

Run these commands from the repository root.

```bash
python asm/assemble.py asm/examples/i2c_write.asm -o i2c_write.hex
python -m pip install -r test/requirements.txt
python -m pytest -q asm
cd test
make
python -m cocotb_tools.check_results results.xml
```

The I²C regression models a target, including clock stretching and both an ACK and a NACK at the address phase. The UART and Manchester RX regressions check the echoed bytes at multiple input phases and clock rates.

## ASIC build

The [GDS workflow](.github/workflows/gds.yaml) targets the Tiny Tapeout 8×4 IHP CMOS5L template. It builds with a 16.667 ns clock constraint and runs Tiny Tapeout precheck and the functional gate-level suite on the resulting netlist.

The local routed baseline passed all 15 RTL and 15 functional gate-level tests. At the 60 MHz target, extracted worst setup slack was +2.84 ns at the slow corner and worst hold slack was +0.11 ns at the fast corner. Netgen LVS matched. The flow still reports maximum transition and capacitance warnings.

Both SRAMs connect to the tile power grid on Metal4. OpenROAD checks connectivity after the stripes are stitched across the macro boundaries. Magic's DEF/LEF extraction reports eight overlaps at the abstract obstructions crossed by the VDD stitches. The build retains these as warnings and Tiny Tapeout precheck checks the streamed GDS.
