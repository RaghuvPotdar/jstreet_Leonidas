onerror {resume}

echo ========== 2980ns .. 3400ns every clk (byte boundary) ==========
for {set ns 2980} {$ns <= 3400} {incr ns 20} {
  echo "t=$ns pc=[examine -time ${ns}ns /tb/DUT/datapath/pc] instr=[examine -time ${ns}ns /tb/DUT/datapath/instr] hold=[examine -time ${ns}ns /tb/DUT/datapath/hold] asked=[examine -time ${ns}ns /tb/DUT/datapath/asked] ld_pend=[examine -time ${ns}ns /tb/DUT/datapath/ld_pend] uo=[examine -time ${ns}ns /tb/uo_out]"
}

quit -f
