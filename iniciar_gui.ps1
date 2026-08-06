$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

& "$ProjectRoot\cje_venv\Scripts\Activate.ps1"

Write-Host "Iniciando GUI de CJE Perfumes..." -ForegroundColor Green
Set-Location "$ProjectRoot\cje_gui"
python main.py
