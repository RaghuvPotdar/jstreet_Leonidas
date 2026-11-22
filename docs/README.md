# Leonidas docs

Leonidas is a dumb pin machine on Tiny Tapeout (IHP). Top module `tt_um_RaghuvPotdar_Leonidas`. The opcode is a verb. The protocol is the program. Load a different listing to change protocol.

Target clock **60 MHz** (STA period 16.667 ns). Questa TB uses 20 ns. Pins `uo_out` idle `8'hFF`. `ui_in` is the host byte, not a pin. Jane Street question we want: **what else can this chip do?** not a catalog of extra opcodes.

The RTL implements nine opcodes (`LDI` `PSET` `OUT`/`OUTM` `DJNZ` `HALT` `REL` `JL` `LD` `IN`/`INW`), a 3R1W register file, 256×16 instruction SRAM, and 256×8 data SRAM. Examples cover UART, SPI, I2C, USB LS/FS ACK transmission, and Manchester TX and RX. RX SRAM and `EXT` are future work.

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
| `asm/examples/` | Protocol programs |
| `test/` | cocotb + Icarus (WSL) |
| `questa/` | RTL sim + WLF (Windows Questa) |
