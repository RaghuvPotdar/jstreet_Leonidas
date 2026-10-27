# Questasim entry from PowerShell.
#   .\run.ps1 -QuestaHome "C:\Desktop\altera_pro\26.1.1\questa_fse" [-Gui]
param(
    [Parameter(Mandatory = $true)]
    [string]$QuestaHome,
    [string]$Program = "program.hex",
    [switch]$Gui,
    [switch]$CompileOnly
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$win = Join-Path $QuestaHome "win64"
$vsim = Join-Path $win "vsim.exe"
$vlog = Join-Path $win "vlog.exe"
$vlib = Join-Path $win "vlib.exe"
$vmap = Join-Path $win "vmap.exe"

foreach ($bin in @($vsim, $vlog, $vlib, $vmap)) {
    if (-not (Test-Path $bin)) {
        throw "missing $bin - check -QuestaHome"
    }
}

if (-not (Test-Path $Program)) {
    throw "missing $Program - assemble a program into questa/ first"
}

if (Test-Path "work") {
    Remove-Item -Recurse -Force "work"
}
& $vlib work
& $vmap work work

$src = Join-Path (Split-Path $PSScriptRoot -Parent) "src"
& $vlog -sv -work work "+define+SIM" "+incdir+$src" `
    (Join-Path $src "sram_256x16.sv") `
    (Join-Path $src "sram_256x8.sv") `
    (Join-Path $src "imem.sv") `
    (Join-Path $src "dmem.sv") `
    (Join-Path $src "rf.sv") `
    (Join-Path $src "datapath.sv") `
    (Join-Path $src "leonidas.sv") `
    "tb.sv"
if ($LASTEXITCODE -ne 0) { throw "vlog failed" }
if ($CompileOnly) { return }

$plus = "+PROGRAM=$Program"
if ($Gui) {
    & $vsim -voptargs="+acc" "work.tb" -do "log -r /*; do scripts/wave.do; run -all" $plus
} else {
    & $vsim -c -voptargs="+acc" "work.tb" -wlf vsim.wlf -do "log -r /*; run -all; quit -f" $plus
    Write-Host "waves: vsim.wlf"
    Write-Host "open: & `"$vsim`" -view vsim.wlf -do `"do scripts/wave.do`""
}
