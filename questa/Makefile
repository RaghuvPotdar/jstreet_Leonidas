# Questasim RTL sim for Leonidas.
# Set QUESTASIM_HOME to the install that contains win64/vsim.exe (or
# linux_x86_64/vsim). Override on the command line if needed.

QUESTASIM_HOME ?=
SRC_DIR        := ../src
ASM_DIR        := ../asm
EXAMPLES       := $(ASM_DIR)/examples
WORK           := work
PROGRAM        := program.hex

# make sim eth_10t.asm  →  ../asm/examples/eth_10t.asm
# Bare name or path; examples/ is implied when the file is not here.
ASM_ARG := $(firstword $(filter %.asm,$(MAKECMDGOALS)))
ifeq ($(ASM_ARG),)
  ASM :=
else ifneq ($(wildcard $(ASM_ARG)),)
  ASM := $(ASM_ARG)
else
  ASM := $(EXAMPLES)/$(notdir $(ASM_ARG))
endif

ifneq ($(ASM_ARG),)
.PHONY: $(ASM_ARG)
$(ASM_ARG):
	@:
endif

PROJECT_SOURCES := \
	$(SRC_DIR)/sram_256x16.sv \
	$(SRC_DIR)/sram_256x8.sv \
	$(SRC_DIR)/imem.sv \
	$(SRC_DIR)/dmem.sv \
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

.PHONY: all check compile sim gui wave clean asm suite

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

# One listing → program.hex. This is not the cocotb suite.
#   make sim eth_10t.asm
#   make gui eth_10t.asm
SUITE_NAMES := uart spi usb_ls_ack usb_fs_ack eth_10t

suite:
	mkdir -p suite
	@for n in $(SUITE_NAMES); do \
		python $(ASM_DIR)/assemble.py $(EXAMPLES)/$$n.asm -o suite/$$n.hex; \
	done

DMEM := $(basename $(PROGRAM)).dmem

asm:
	@if [ -z "$(ASM)" ]; then $(MAKE) suite; else \
		python $(ASM_DIR)/assemble.py $(ASM) -o $(PROGRAM); \
		if [ -f "$(basename $(ASM)).dmem" ]; then cp "$(basename $(ASM)).dmem" "$(DMEM)"; fi; \
	fi

PLUS :=
ifneq ($(ASM),)
  PLUS += +PROGRAM=$(PROGRAM)
  ifneq ($(wildcard $(DMEM)),)
    PLUS += +DMEM=$(DMEM)
  endif
endif

sim: asm compile
ifeq ($(ASM),)
	"$(VSIM_BIN)" -c -do "do scripts/sim.do" -wlf vsim.wlf
else
	"$(VSIM_BIN)" -c -do "do scripts/sim.do" -wlf vsim.wlf $(PLUS)
endif

gui: asm compile
ifeq ($(ASM),)
	"$(VSIM_BIN)" -voptargs=+acc work.tb -do "onfinish stop; log -r /*; view wave; do wave.do; run -all"
else
	"$(VSIM_BIN)" -voptargs=+acc work.tb -do "onfinish stop; log -r /*; view wave; do wave.do; run -all" $(PLUS)
endif

wave: check
	"$(VSIM_BIN)" -view vsim.wlf -do "do scripts/wave.do"

clean:
	rm -rf $(WORK) transcript vsim.wlf wlft* *.vstf vsim.dbg
	rm -f dump.vcd dump.wlf
