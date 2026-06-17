$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $env:WARTUNG_SSL_CERT -or -not $env:WARTUNG_SSL_KEY) {
  Write-Host "Bitte WARTUNG_SSL_CERT und WARTUNG_SSL_KEY setzen."
  Write-Host "Beispiel:"
  Write-Host '$env:WARTUNG_SSL_CERT="C:\Pfad\cert.pem"'
  Write-Host '$env:WARTUNG_SSL_KEY="C:\Pfad\key.pem"'
  exit 1
}

python .\run.py

