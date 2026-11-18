# Leonidas docs

Leonidas is a dumb pin machine on Tiny Tapeout (IHP). Top module `tt_um_RaghuvPotdar_Leonidas`. The opcode is a verb. The protocol is the program. Load a different listing to change protocol.

Target clock **60 MHz** (STA period 16.667 ns). Questa TB uses 20 ns. Pins `uo_out` idle `8'hFF`. `ui_in` is the host byte, not a pin. Jane Street question we want: **what else can this chip do?** not a catalog of extra opcodes.

**Silicon now:** eight opcodes (`LDI` `PSET` `OUT`/`OUTM` `DJNZ` `HALT` `REL` `JL` `LD`), 3R1W RF, imem `256x16`, dmem `256x8`. TX listings for UART, SPI, I2C (inline test), USB LS/FS ACK, 10BASE-T. **No RX in silicon.** `IN` / RX SRAM / `EXT` are drafted, not built.

Consult before ISA, RTL, or listing changes. Do not spend opcodes `1000`–`1111` until RX. Do not revert unsolicited work without asking.

## Read in this order

| File | What |
|---|---|
| [info.md](info.md) | Tiny Tapeout page: load strobes, how to test |
| [isa.md](isa.md) | 16-bit ISA as implemented |
| [listings.md](listings.md) | Programs, pins, timings, USB/eth bytes |
| [programmability.md](programmability.md) | Why the chip looks like this |
| [future.md](future.md) | RX draft, roadmap, rejected ideas, every parking-lot note |
| [sim.md](sim.md) | Questa and cocotb commands |

Old UART-only notes in `notes/programmability.md` are **historical**. They do not describe this chip.

## What is in the tree

| Path | Role |
|---|---|
| `src/` | RTL (`leonidas.sv` top wrapper) |
| `asm/assemble.py` | Assembler → hex |
| `asm/examples/` | TX listings |
| `test/` | cocotb + Icarus (WSL) |
| `questa/` | RTL sim + WLF (Windows Questa) |
