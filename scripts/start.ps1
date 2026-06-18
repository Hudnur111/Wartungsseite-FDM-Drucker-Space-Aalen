$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not $env:WARTUNG_HOST) { $env:WARTUNG_HOST = "127.0.0.1" }
if (-not $env:WARTUNG_PORT) { $env:WARTUNG_PORT = "8080" }
python .\run.py

