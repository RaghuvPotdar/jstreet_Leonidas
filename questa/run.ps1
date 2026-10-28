# Questasim entry from PowerShell.
#   .\run.ps1 -QuestaHome "C:\Desktop\altera_pro\26.1.1\questa_fse" -Asm asm\examples\eth_10t.asm -Gui
param(
    [Parameter(Mandatory = $true)]
    [string]$QuestaHome,
    [string]$Asm = "",
    [string]$Program = "program.hex",
    [string]$TestName = "",
    [switch]$Suite,
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

$assemble = Join-Path (Split-Path $PSScriptRoot -Parent) "asm\assemble.py"
$examples = Join-Path (Split-Path $PSScriptRoot -Parent) "asm\examples"

if ($Suite -or -not $Asm) {
    New-Item -ItemType Directory -Force suite | Out-Null
    foreach ($n in @("uart", "spi", "usb_ls_ack", "usb_fs_ack", "eth_10t")) {
        & python $assemble (Join-Path $examples "$n.asm") -o (Join-Path $PSScriptRoot "suite\$n.hex")
        if ($LASTEXITCODE -ne 0) { throw "assemble $n failed" }
    }
    $Suite = $true
} else {
    $asmPath = $Asm
    if (-not [System.IO.Path]::IsPathRooted($asmPath)) {
        $asmPath = Join-Path (Split-Path $PSScriptRoot -Parent) $Asm
    }
    & python $assemble $asmPath -o $Program
    if ($LASTEXITCODE -ne 0) { throw "assemble failed" }
    if (-not $TestName) { $TestName = [System.IO.Path]::GetFileNameWithoutExtension($asmPath) }
    $sidecar = [System.IO.Path]::ChangeExtension($asmPath, ".dmem")
    $dmemOut = [System.IO.Path]::ChangeExtension($Program, ".dmem")
    if (Test-Path $sidecar) {
        Copy-Item $sidecar $dmemOut -Force
    }
}

if (-not $Suite -and -not (Test-Path $Program)) {
    throw "missing $Program"
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

$plus = @()
if (-not $Suite) {
    $plus = @("+PROGRAM=$Program")
    if ($TestName) { $plus += "+TESTNAME=$TestName" }
    $dmem = [System.IO.Path]::ChangeExtension($Program, ".dmem")
    if (Test-Path $dmem) { $plus += "+DMEM=$dmem" }
}
if ($Gui) {
    # File → Save Format writes wave.do in this directory, not scripts/.
    # onfinish stop: the tb $finish's; without this the GUI can exit first.
    & $vsim -voptargs="+acc" "work.tb" -do "onfinish stop; log -r /*; view wave; do wave.do; run -all" $plus
} else {
    & $vsim -c -voptargs="+acc" "work.tb" -wlf vsim.wlf -do "log -r /*; run -all; quit -f" $plus
    Write-Host "waves: vsim.wlf"
    Write-Host "open: & `"$vsim`" -view vsim.wlf -do `"view wave; do wave.do`""
}
