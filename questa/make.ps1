# PowerShell stand-in for the Makefile. GNU make is not on this machine.
# From questa\:
#   .\make sim eth_10t.asm
#   .\make gui eth_10t.asm
param(
    [Parameter(Position = 0)]
    [ValidateSet("asm", "sim", "gui", "wave", "clean", "help")]
    [string]$Target = "help",
    [Parameter(Position = 1)]
    [string]$AsmFile = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$QuestaHome = $env:QUESTASIM_HOME
if (-not $QuestaHome) {
    $QuestaHome = "C:\Desktop\altera_pro\26.1.1\questa_fse"
}

function Resolve-Asm([string]$name) {
    if ([string]::IsNullOrWhiteSpace($name)) { $name = "uart.asm" }
    if (-not $name.EndsWith(".asm")) { $name = "$name.asm" }
    if ([System.IO.Path]::IsPathRooted($name) -and (Test-Path $name)) { return $name }
    if (Test-Path $name) { return (Resolve-Path $name).Path }
    $inExamples = Join-Path (Split-Path $PSScriptRoot -Parent) "asm\examples\$name"
    if (Test-Path $inExamples) { return $inExamples }
    throw "no listing $name (looked in asm\examples)"
}

switch ($Target) {
    "help" {
        Write-Host ".\make gui              # all 5 listings, watch test_id"
        Write-Host ".\make sim eth_10t.asm"
        Write-Host ".\make gui eth_10t.asm"
        Write-Host ".\make asm uart.asm"
        Write-Host ".\make wave"
        Write-Host ".\make clean"
    }
    "clean" {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue work, transcript, vsim.wlf
        Get-ChildItem -Filter "wlft*" -ErrorAction SilentlyContinue | Remove-Item -Force
        Remove-Item -Force -ErrorAction SilentlyContinue *.vstf, vsim.dbg, dump.vcd, dump.wlf
    }
    "wave" {
        $vsim = Join-Path $QuestaHome "win64\vsim.exe"
        & $vsim -view vsim.wlf -do "view wave; do wave.do"
    }
    "asm" {
        $asm = Resolve-Asm $(if ($AsmFile) { $AsmFile } else { "uart.asm" })
        $assemble = Join-Path (Split-Path $PSScriptRoot -Parent) "asm\assemble.py"
        & python $assemble $asm -o "program.hex"
        if ($LASTEXITCODE -ne 0) { throw "assemble failed" }
        $sidecar = [System.IO.Path]::ChangeExtension($asm, ".dmem")
        if (Test-Path $sidecar) { Copy-Item $sidecar "program.dmem" -Force }
    }
    "sim" {
        if ($AsmFile) {
            & (Join-Path $PSScriptRoot "run.ps1") -QuestaHome $QuestaHome -Asm (Resolve-Asm $AsmFile)
        } else {
            & (Join-Path $PSScriptRoot "run.ps1") -QuestaHome $QuestaHome -Suite
        }
    }
    "gui" {
        if ($AsmFile) {
            & (Join-Path $PSScriptRoot "run.ps1") -QuestaHome $QuestaHome -Asm (Resolve-Asm $AsmFile) -Gui
        } else {
            & (Join-Path $PSScriptRoot "run.ps1") -QuestaHome $QuestaHome -Suite -Gui
        }
    }
}
