# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = leonidas.sv

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate level simulation.
# The PDK cell models drive flip-flop UDPs from delayed_* wires that are
# created by specify-block timing checks. Icarus does not implement those
# checks, so the wires stay Z and Q stays X. make_functional_stdcells.py
# rewrites the models into zero-delay assigns before compilation.
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DSIM
STDCELL_SRC     := $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v
UDP_SRC         := $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_udp.v
FUNCTIONAL_STDCELLS := $(SIM_BUILD)/sg13g2_stdcell_functional.v

VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_io/verilog/sg13g2_io.v
VERILOG_SOURCES += $(FUNCTIONAL_STDCELLS)
CUSTOM_COMPILE_DEPS += $(FUNCTIONAL_STDCELLS)

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Icarus defaults to Verilog-2005. leonidas.sv uses logic and always_ff.
COMPILE_ARGS 		+= -g2012

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.sv
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

# This rule has to stay below the include. The first target in a Makefile is
# Make's default goal. Cocotb's default goal is "all", which runs the test.
# A rule above the include would become the default goal, so "GATES=yes make"
# would generate the functional cells and exit 0 without ever simulating.
ifeq ($(GATES),yes)
$(FUNCTIONAL_STDCELLS): $(STDCELL_SRC) make_functional_stdcells.py
	mkdir -p $(dir $@)
	$(PYTHON_BIN) make_functional_stdcells.py $(STDCELL_SRC) $@ $(wildcard $(UDP_SRC))
endif
