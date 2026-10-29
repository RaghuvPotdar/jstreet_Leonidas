onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate -divider tb
add wave -noupdate -radix unsigned /tb/test_id
add wave -noupdate /tb/test_name
add wave -noupdate /tb/clk
add wave -noupdate /tb/rst_n
add wave -noupdate /tb/ena
add wave -noupdate -radix hexadecimal /tb/ui_in
add wave -noupdate -radix hexadecimal -childformat {{{/tb/uio_in[7]} -radix hexadecimal} {{/tb/uio_in[6]} -radix hexadecimal} {{/tb/uio_in[5]} -radix hexadecimal} {{/tb/uio_in[4]} -radix hexadecimal} {{/tb/uio_in[3]} -radix hexadecimal} {{/tb/uio_in[2]} -radix hexadecimal} {{/tb/uio_in[1]} -radix hexadecimal} {{/tb/uio_in[0]} -radix hexadecimal}} -subitemconfig {{/tb/uio_in[7]} {-height 15 -radix hexadecimal} {/tb/uio_in[6]} {-height 15 -radix hexadecimal} {/tb/uio_in[5]} {-height 15 -radix hexadecimal} {/tb/uio_in[4]} {-height 15 -radix hexadecimal} {/tb/uio_in[3]} {-height 15 -radix hexadecimal} {/tb/uio_in[2]} {-height 15 -radix hexadecimal} {/tb/uio_in[1]} {-height 15 -radix hexadecimal} {/tb/uio_in[0]} {-height 15 -radix hexadecimal}} /tb/uio_in
add wave -noupdate -color Cyan -radix hexadecimal -childformat {{{/tb/uo_out[7]} -radix hexadecimal} {{/tb/uo_out[6]} -radix hexadecimal} {{/tb/uo_out[5]} -radix hexadecimal} {{/tb/uo_out[4]} -radix hexadecimal} {{/tb/uo_out[3]} -radix hexadecimal} {{/tb/uo_out[2]} -radix hexadecimal} {{/tb/uo_out[1]} -radix hexadecimal} {{/tb/uo_out[0]} -radix hexadecimal}} -expand -subitemconfig {{/tb/uo_out[7]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[6]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[5]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[4]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[3]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[2]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[1]} {-color Cyan -height 15 -radix hexadecimal} {/tb/uo_out[0]} {-color Cyan -height 15 -radix hexadecimal}} /tb/uo_out
add wave -noupdate -color Cyan -radix hexadecimal /tb/uio_out
add wave -noupdate -radix hexadecimal /tb/uio_oe
add wave -noupdate -divider datapath
add wave -noupdate -radix hexadecimal /tb/DUT/datapath/pc
add wave -noupdate -radix hexadecimal /tb/DUT/datapath/instr
add wave -noupdate -radix hexadecimal /tb/DUT/datapath/hold
add wave -noupdate /tb/DUT/datapath/halted
add wave -noupdate /tb/DUT/datapath/asked
add wave -noupdate /tb/DUT/imem/running
add wave -noupdate -divider memory
add wave -noupdate -label imem /tb/DUT/imem/sram/mem
add wave -noupdate -label dmem /tb/DUT/dmem/sram/mem
TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 1} {27934900 ps} 0}
quietly wave cursor active 1
configure wave -namecolwidth 120
configure wave -valuecolwidth 80
configure wave -justifyvalue left
configure wave -signalnamewidth 1
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits ps
update
WaveRestoreZoom {23957158 ps} {28140150 ps}
