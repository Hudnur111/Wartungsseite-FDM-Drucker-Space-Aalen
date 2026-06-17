param(
  [string]$Email = "",
  [string]$Name = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$arguments = @(".\scripts\reset_admin_password.py")
if ($Email) {
  $arguments += @("--email", $Email)
}
if ($Name) {
  $arguments += @("--name", $Name)
}

python @arguments
