$ErrorActionPreference = "Stop"
$certDir = Join-Path (Split-Path -Parent $PSScriptRoot) "certs"
New-Item -ItemType Directory -Force -Path $certDir | Out-Null
Write-Host "Hinweis: Python benoetigt PEM-Dateien. Dieses Skript ist ein Platzhalter fuer eine produktive Zertifikatsstrategie."
Write-Host "Empfehlung: Internes CA-Zertifikat oder Reverse Proxy mit HTTPS verwenden."
Write-Host "Zertifikatsordner: $certDir"
