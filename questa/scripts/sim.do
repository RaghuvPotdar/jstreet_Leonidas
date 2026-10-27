# Batch sim. Assumes work/ already compiled (run.ps1 or compile.do).
# Dumps vsim.wlf. Open with: vsim -view vsim.wlf -do "do scripts/wave.do"

vsim -voptargs=+acc work.tb
log -r /*
run -all
quit -f
