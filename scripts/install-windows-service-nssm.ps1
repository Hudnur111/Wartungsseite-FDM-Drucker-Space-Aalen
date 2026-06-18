$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$streamlit = (Get-Command streamlit).Source
$app = Join-Path $root "streamlit_app.py"
$nssm = Get-Command nssm -ErrorAction SilentlyContinue

if (-not $nssm) {
  Write-Host "NSSM wurde nicht gefunden. Installiere NSSM oder nutze scripts/install-scheduled-task.ps1 als Windows-Bordmittel."
  exit 1
}

nssm install "WartungFdmSpace" $streamlit "run `"$app`" --server.address 0.0.0.0 --server.port 8501"
nssm set "WartungFdmSpace" AppDirectory $root
nssm set "WartungFdmSpace" DisplayName "Wartung FDM Space"
nssm set "WartungFdmSpace" Description "Wartungsverwaltung fuer FDM Space Drucker"
nssm set "WartungFdmSpace" Start SERVICE_AUTO_START
nssm start "WartungFdmSpace"
Write-Host "Service WartungFdmSpace wurde angelegt und gestartet."

