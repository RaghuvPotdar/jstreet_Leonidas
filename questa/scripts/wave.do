# Wave layout for Leonidas. Use with a live sim or: vsim -view vsim.wlf

onerror {resume}
quietly WaveActivateNextPane {} 0

add wave -noupdate -divider {tb}
add wave -noupdate /tb/clk
add wave -noupdate /tb/rst_n
add wave -noupdate /tb/ena
add wave -noupdate -radix hex /tb/ui_in
add wave -noupdate -radix hex /tb/uio_in
add wave -noupdate -radix hex /tb/uo_out
add wave -noupdate -radix hex /tb/uio_out
add wave -noupdate -radix hex /tb/uio_oe

add wave -noupdate -divider {UART pin}
add wave -noupdate /tb/uo_out(1)

add wave -noupdate -divider {SPI pins}
add wave -noupdate /tb/uo_out(2)
add wave -noupdate /tb/uo_out(3)
add wave -noupdate /tb/uo_out(4)

add wave -noupdate -divider {I2C pins}
add wave -noupdate /tb/uio_out(2)
add wave -noupdate /tb/uio_oe(2)
add wave -noupdate /tb/uio_in(2)
add wave -noupdate /tb/uio_out(3)
add wave -noupdate /tb/uio_oe(3)
add wave -noupdate /tb/uio_in(3)

add wave -noupdate -divider {datapath}
add wave -noupdate -radix hex /tb/DUT/datapath/pc
add wave -noupdate -radix hex /tb/DUT/datapath/instr
add wave -noupdate -radix hex /tb/DUT/datapath/shifter
add wave -noupdate -radix hex /tb/DUT/datapath/xreg
add wave -noupdate -radix hex /tb/DUT/datapath/hold
add wave -noupdate /tb/DUT/datapath/halted
add wave -noupdate /tb/DUT/datapath/asked
add wave -noupdate /tb/DUT/imem/running

TreeUpdate [SetDefaultTree]
WaveRestoreZoom {0 ns} {200 us}
configure wave -namecolwidth 220
configure wave -valuecolwidth 80
configure wave -justifyvalue left
configure wave -signalnamewidth 1
update
