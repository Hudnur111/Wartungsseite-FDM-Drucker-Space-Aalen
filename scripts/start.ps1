$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
streamlit run .\streamlit_app.py --server.address 127.0.0.1 --server.port 8501

