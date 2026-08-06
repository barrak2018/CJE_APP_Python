$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

& "$ProjectRoot\cje_venv\Scripts\Activate.ps1"

$ApiHost = "127.0.0.1"
$ApiPort = 8000
$ApiReloadFlag = "--reload"

# Leer configuración desde cje_api/config.json (o el archivo indicado en CJE_CONFIG)
$ConfigPath = if ($env:CJE_CONFIG) { $env:CJE_CONFIG } else { Join-Path $ProjectRoot "cje_api\config.json" }
if (Test-Path $ConfigPath) {
    $Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    $ApiHost = $Config.api.host
    $ApiPort = $Config.api.port
    if (-not $Config.api.reload) { $ApiReloadFlag = "" }
    if (-not $env:CJE_API_USER) { $env:CJE_API_USER = $Config.auth.api_user }
    if (-not $env:CJE_API_PASSWORD) { $env:CJE_API_PASSWORD = $Config.auth.api_password }
    if (-not $env:CJE_SECRET_KEY) { $env:CJE_SECRET_KEY = $Config.auth.secret_key }
} else {
    Write-Host "No se encontró config.json; usando valores por defecto." -ForegroundColor Yellow
    if (-not $env:CJE_API_USER) { $env:CJE_API_USER = "admin" }
    if (-not $env:CJE_API_PASSWORD) { $env:CJE_API_PASSWORD = "admin123" }
    if (-not $env:CJE_SECRET_KEY) { $env:CJE_SECRET_KEY = "dev-secret-cambiar-en-produccion" }
}

Write-Host "Iniciando servidor CJE Perfumes..." -ForegroundColor Green
Write-Host "API: http://$ApiHost`:$ApiPort  (usuario API: $env:CJE_API_USER)" -ForegroundColor Yellow
Set-Location "$ProjectRoot\cje_api"
if ($ApiReloadFlag) {
    uvicorn main:app --host $ApiHost --port $ApiPort --reload
} else {
    uvicorn main:app --host $ApiHost --port $ApiPort
}
