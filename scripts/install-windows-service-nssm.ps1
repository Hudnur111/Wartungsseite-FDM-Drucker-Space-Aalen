$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
$app = Join-Path $root "run.py"
$nssm = Get-Command nssm -ErrorAction SilentlyContinue

if (-not $nssm) {
  Write-Host "NSSM wurde nicht gefunden. Installiere NSSM oder nutze scripts/install-scheduled-task.ps1 als Windows-Bordmittel."
  exit 1
}

nssm install "WartungFdmSpace" $python "`"$app`""
nssm set "WartungFdmSpace" AppDirectory $root
nssm set "WartungFdmSpace" AppEnvironmentExtra "WARTUNG_HOST=0.0.0.0" "WARTUNG_PORT=8080"
nssm set "WartungFdmSpace" DisplayName "Wartung FDM Space"
nssm set "WartungFdmSpace" Description "Wartungsverwaltung fuer FDM Space Drucker"
nssm set "WartungFdmSpace" Start SERVICE_AUTO_START
nssm start "WartungFdmSpace"
Write-Host "Service WartungFdmSpace wurde angelegt und gestartet."

