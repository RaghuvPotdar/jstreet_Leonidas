# Simulation

Two simulators. **cocotb + Icarus** in WSL is the test suite. **Questa** on Windows is waves (`vsim.wlf`). The agent does not open the Questa GUI. Batch `vsim -c` and `vsim -view` on a WLF are fine.

Questa home is `questa_fse`, not the `26.1.1` parent.

```
C:\Desktop\altera_pro\26.1.1\questa_fse
```

License:

```
C:\licenses\flexlm\LR-204936_License.dat
```

## Questa (PowerShell)

```powershell
$env:SALT_LICENSE_SERVER = "C:\licenses\flexlm\LR-204936_License.dat"
$env:QUESTASIM_HOME      = "C:\Desktop\altera_pro\26.1.1\questa_fse"

cd C:\Desktop\jstreet_Leonidas\questa
.\run.ps1 -QuestaHome $env:QUESTASIM_HOME -Asm ..\asm\examples\uart.asm
.\run.ps1 -QuestaHome $env:QUESTASIM_HOME -Asm ..\asm\examples\eth_10t_loop.asm -Gui
.\make.ps1 sim eth_10t_loop.asm
.\make.ps1 gui usb_fs_ack.asm
.\make.ps1 wave
```

`run.ps1` / `make.ps1` run these binaries, in order:

```
vlib work
vmap work work
vlog -sv -work work +define+SIM +incdir+..\src  <rtl>  tb.sv
```

Batch (no GUI):

```
vsim -c -voptargs=+acc work.tb -wlf vsim.wlf -do "log -r /*; run -all; quit -f" +PROGRAM=program.hex +TESTNAME=... +DMEM=program.dmem
```

GUI:

```
vsim -voptargs=+acc work.tb -do "onfinish stop; log -r /*; view wave; do wave.do; run -all" +PROGRAM=... +TESTNAME=... +DMEM=...
```

Reopen a WLF / dump from it:

```
vsim -view vsim.wlf -do "view wave; do wave.do"
vsim -c -view vsim.wlf -do dump_gap.do
vsim -c -view vsim.wlf -do "do dump_cyc.do"
```

Tcl used inside `vsim`: `log -r /*`, `view wave`, `do wave.do`, `run -all`, `onfinish stop`, `quit -f`, `examine -time`.

Plusargs: `+PROGRAM=` hex, `+TESTNAME=` listing name, `+DMEM=` sidecar. No `+PROGRAM` runs the suite in `tb.sv`. Clock is 20 ns (`questa/tb.sv`).

License check:

```
lmutil.exe lmdiag -c C:\licenses\flexlm\LR-204936_License.dat
```

GNU make is not on this Windows machine. Use `make.ps1` or `run.ps1`. `questa/Makefile` is the Linux-shaped twin.

## Assembler

```powershell
python asm\assemble.py asm\examples\uart.asm -q
python asm\assemble.py asm\examples\eth_10t.asm -o questa\program.hex
```

`-q` writes `questa/program.hex`. A sidecar `*.dmem` next to the `.asm` is copied to `program.dmem` when present (`eth_10t_loop.dmem`).

## cocotb + Icarus (WSL)

`.venv` has cocotb. Icarus warns about constant selects in `always_*` (pre-existing).

```bash
wsl
source /mnt/c/Desktop/jstreet_Leonidas/.venv/bin/activate
cd /mnt/c/Desktop/jstreet_Leonidas/test
make
make -B
```

First-time setup (if the venv is missing):

```bash
sudo apt-get update
sudo apt-get install -y iverilog python3-venv python3-pip
cd /mnt/c/Desktop/jstreet_Leonidas
python3 -m venv .venv
source .venv/bin/activate
pip install -r test/requirements.txt
cd test
make clean
make
```

Gate-level: copy the GL netlist to `test/gate_level_netlist.v`, then `make -B GATES=yes` (needs `PDK_ROOT` for IHP cells). Functional stdcell rewrite is `test/make_functional_stdcells.py`.

Waves: `tb.fst` (GTKWave / Surfer). `make -B FST=` for VCD.

A green cocotb suite can still hide a bad Manchester wave if the checker drops remainder and `00`/`11`. Use exact run lengths (`expect_runs`) and/or a WLF dump. Tests passing ≠ waves good.
