# Compile Leonidas RTL + Questasim testbench.
# Invoked from questa/ as: vsim -c -do "do scripts/compile.do"

if {[file exists work]} {
    vdel -lib work -all
}
vlib work
vmap work work

set SRC ../src
vlog -sv -work work +define+SIM +incdir+$SRC \
    $SRC/sram_256x16.sv \
    $SRC/sram_256x8.sv \
    $SRC/imem.sv \
    $SRC/dmem.sv \
    $SRC/rf.sv \
    $SRC/datapath.sv \
    $SRC/leonidas.sv \
    tb.sv

puts "compile done"
quit -f
