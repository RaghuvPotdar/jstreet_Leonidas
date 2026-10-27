# Questasim RTL sim for Leonidas.
# Set QUESTASIM_HOME to the install that contains win64/vsim.exe (or
# linux_x86_64/vsim). Override on the command line if needed.

QUESTASIM_HOME ?=
SRC_DIR        := ../src
ASM_DIR        := ../asm
WORK           := work
PROGRAM        := program.hex

PROJECT_SOURCES := \
	$(SRC_DIR)/uart.sv \
	$(SRC_DIR)/sram_256x16.sv \
	$(SRC_DIR)/imem.sv \
	$(SRC_DIR)/rf.sv \
	$(SRC_DIR)/datapath.sv \
	$(SRC_DIR)/leonidas.sv

ifeq ($(OS),Windows_NT)
  VSIM_BIN := $(QUESTASIM_HOME)/win64/vsim.exe
  VLOG_BIN := $(QUESTASIM_HOME)/win64/vlog.exe
  VLIB_BIN := $(QUESTASIM_HOME)/win64/vlib.exe
  VMAP_BIN := $(QUESTASIM_HOME)/win64/vmap.exe
else
  VSIM_BIN := $(QUESTASIM_HOME)/linux_x86_64/vsim
  VLOG_BIN := $(QUESTASIM_HOME)/linux_x86_64/vlog
  VLIB_BIN := $(QUESTASIM_HOME)/linux_x86_64/vlib
  VMAP_BIN := $(QUESTASIM_HOME)/linux_x86_64/vmap
endif

.PHONY: all check compile sim gui wave clean asm

all: sim

check:
	@if [ -z "$(QUESTASIM_HOME)" ]; then \
		echo "Set QUESTASIM_HOME to your Questasim install root."; \
		echo "Example: make QUESTASIM_HOME=/path/to/questa_2024.1"; \
		exit 1; \
	fi
	@test -x "$(VSIM_BIN)" || test -f "$(VSIM_BIN)" || \
		(echo "vsim not found at $(VSIM_BIN)"; exit 1)

$(WORK): check
	"$(VLIB_BIN)" $(WORK)
	"$(VMAP_BIN)" work $(WORK)

compile: $(WORK) tb.sv $(PROJECT_SOURCES)
	"$(VLOG_BIN)" -sv -work $(WORK) +define+SIM \
		+incdir+$(SRC_DIR) $(PROJECT_SOURCES) tb.sv

# Assemble the default program if asm/ exists and PROGRAM is missing.
asm:
	@if [ -f $(ASM_DIR)/assemble.py ]; then \
		python $(ASM_DIR)/assemble.py $(ASM_DIR)/examples/uart.asm -o $(PROGRAM); \
	fi

sim: compile
	@test -f $(PROGRAM) || (echo "Missing $(PROGRAM). Run the assembler first."; exit 1)
	"$(VSIM_BIN)" -c -do "do scripts/sim.do" -wlf vsim.wlf

gui: compile
	@test -f $(PROGRAM) || (echo "Missing $(PROGRAM). Run the assembler first."; exit 1)
	"$(VSIM_BIN)" -do "do scripts/sim.do; do scripts/wave.do"

wave: check
	"$(VSIM_BIN)" -view vsim.wlf -do "do scripts/wave.do"

clean:
	rm -rf $(WORK) transcript vsim.wlf wlft* *.vstf vsim.dbg
	rm -f dump.vcd dump.wlf
