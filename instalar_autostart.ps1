# =====================================================================
# instalar_autostart.ps1
# CJE Perfumes - Autoarranque de la API y del túnel de Cloudflare al
# iniciar sesion en Windows.
#
# Instala una tarea programada (disparador "Al iniciar sesion") que:
#   1) levanta la API (uvicorn) si no esta respondiendo, y
#   2) levanta el tunel temporal de Cloudflare y actualiza URL_TUNEL.txt
#      con la URL nueva de cada arranque.
#
# Modos (switch):
#   (sin switch)   -> instala o actualiza la tarea
#   -Uninstall     -> elimina la tarea
#   -Status        -> muestra el estado de la tarea, la API y el tunel
#   -Bootstrap     -> (uso interno de la tarea) arranca API + tunel
#
# Ejecutar con:  powershell -ExecutionPolicy Bypass -File .\instalar_autostart.ps1
# =====================================================================

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Bootstrap
)

$TaskName   = "CJE_Perfumes_API_Tunel"
$UrlPattern = 'https://[a-z0-9-]+\.trycloudflare\.com'
$ProjectRoot = $PSScriptRoot
$UrlFile    = Join-Path $ProjectRoot "URL_TUNEL.txt"
$ScriptPath = $MyInvocation.MyCommand.Path

function Test-IsElevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Start-Elevated([string]$Switches) {
    $argumentos = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" $Switches"
    try {
        Start-Process -FilePath "powershell.exe" -ArgumentList $argumentos -Verb RunAs -Wait
        return $true
    } catch {
        Write-Host "[ERROR] Elevacion cancelada o no disponible (UAC). La tarea NO fue registrada."
        return $false
    }
}

function Test-Url([string]$Url, [int]$TimeoutSec = 3) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-Port([int]$Port) {
    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    } catch {
        return $false
    }
}

function Get-ApiConfig {
    $host_ = "127.0.0.1"
    $port  = 8000
    $configPath = Join-Path $ProjectRoot "cje_api\config.json"
    if (Test-Path -LiteralPath $configPath) {
        try {
            $cfg = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
            if ($cfg.api.host) { $host_ = [string]$cfg.api.host }
            if ($cfg.api.port) { $port  = [int]$cfg.api.port }
        } catch {
            Write-Verbose "No se pudo leer config.json; se usan 127.0.0.1:8000"
        }
    }
    return @{ Host = $host_; Port = $port }
}

# ---------------------------------------------------------------------
# Bootstrap: arranca API + tunel y actualiza URL_TUNEL.txt
# ---------------------------------------------------------------------
function Start-Bootstrap {
    $logsDir     = Join-Path $ProjectRoot "logs"
    $venvPython  = Join-Path $ProjectRoot "cje_venv\Scripts\python.exe"
    $apiLog      = Join-Path $logsDir "api.log"
    $apiErr      = Join-Path $logsDir "api_err.log"
    $tunelLog    = Join-Path $logsDir "tunel.log"
    $tunelErr    = Join-Path $logsDir "tunel_err.log"
    $autostart   = Join-Path $logsDir "autostart.log"
    $cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

    function Log([string]$msg) {
        $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
        Add-Content -LiteralPath $autostart -Value $line -Encoding UTF8
    }

    $cfg = Get-ApiConfig
    $targetHost = "127.0.0.1"
    if ($cfg.Host -notin @("0.0.0.0", "::", "*")) { $targetHost = $cfg.Host }
    $baseUrl      = "http://127.0.0.1:$($cfg.Port)"
    $tunelTarget  = "http://${targetHost}:$($cfg.Port)"

    # --- 1) API ---
    if (Test-Url "$baseUrl/") {
        Log "API ya responde en $baseUrl; se omite el arranque."
    } else {
        Log "Iniciando API en $baseUrl ..."
        if (-not (Test-Path -LiteralPath $venvPython)) {
            Log "ERROR: no se encontro $venvPython"
        } else {
            Start-Process -FilePath $venvPython `
                -ArgumentList "-m", "uvicorn", "main:app", "--host", $cfg.Host, "--port", $cfg.Port `
                -WorkingDirectory (Join-Path $ProjectRoot "cje_api") `
                -RedirectStandardOutput $apiLog -RedirectStandardError $apiErr `
                -WindowStyle Hidden | Out-Null
            $ready = $false
            for ($i = 0; $i -lt 60; $i++) {
                Start-Sleep -Seconds 1
                if (Test-Url "$baseUrl/") { $ready = $true; break }
            }
            if ($ready) { Log "API operativa en $baseUrl." }
            else { Log "ERROR: la API no respondio tras 60 s. Revisa logs\api_err.log" }
        }
    }

    # --- 2) Tunel ---
    if (Get-Process cloudflared -ErrorAction SilentlyContinue) {
        Log "cloudflared ya esta corriendo; se omite el tunel."
    } elseif (-not (Test-Path -LiteralPath $cloudflared)) {
        Log "ERROR: no se encontro cloudflared en $cloudflared"
    } else {
        Log "Iniciando tunel de Cloudflare hacia $tunelTarget ..."
        Start-Process -FilePath $cloudflared `
            -ArgumentList "tunnel", "--url", $tunelTarget, "--no-autoupdate" `
            -RedirectStandardOutput $tunelLog -RedirectStandardError $tunelErr `
            -WindowStyle Hidden | Out-Null

        $url = $null
        for ($i = 0; $i -lt 180; $i++) {
            Start-Sleep -Seconds 1
            $texto = ""
            foreach ($f in @($tunelLog, $tunelErr)) {
                try { $texto += (Get-Content -LiteralPath $f -Raw -ErrorAction Stop) } catch { }
            }
            if ($texto -match $UrlPattern) { $url = $Matches[0]; break }
        }
        if ($url) {
            $fecha = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            "# URL del tunel temporal - generado el $fecha`n$url" |
                Set-Content -LiteralPath $UrlFile -Encoding UTF8
            Log "Tunel activo: $url  (guardado en URL_TUNEL.txt)"
        } else {
            Log "ERROR: no se obtuvo la URL del tunel en 180 s. Revisa logs\tunel_err.log"
        }
    }

    Log "Bootstrap terminado."
}

# ---------------------------------------------------------------------
# Instalar / actualizar la tarea programada
# ---------------------------------------------------------------------
function Install-Task {
    $argumentos = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`" -Bootstrap"

    $action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentos
    $trigger   = New-ScheduledTaskTrigger -AtLogOn
    $settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

    try {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
            -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
        Write-Host "[OK] Tarea '$TaskName' registrada para $env:USERDOMAIN\$env:USERNAME."
        Write-Host "     Se ejecutara al iniciar sesion y arrancara la API + el tunel."
        Write-Host "     Ver estado con:  .\instalar_autostart.ps1 -Status"
    } catch {
        Write-Host "[ERROR] No se pudo registrar la tarea: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------------
# Eliminar la tarea
# ---------------------------------------------------------------------
function Uninstall-Task {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[OK] Tarea '$TaskName' eliminada."
    } else {
        Write-Host "La tarea '$TaskName' no existe."
    }
}

# ---------------------------------------------------------------------
# Estado del sistema
# ---------------------------------------------------------------------
function Show-Status {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        Write-Host "[TAREA] $TaskName -> $($t.State)"
        Write-Host "        Accion: $($t.Actions.Execute) $($t.Actions.Arguments)"
    } else {
        Write-Host "[TAREA] $TaskName -> NO REGISTRADA"
    }

    $cfg = Get-ApiConfig
    $base = "http://127.0.0.1:$($cfg.Port)"
    $apiOk = Test-Url "$base/"
    Write-Host "[API]   $base  -> $(if ($apiOk) {'RESPONDE'} else {'no responde'})"

    $tunelProc = Get-Process cloudflared -ErrorAction SilentlyContinue
    Write-Host "[TUNEL] cloudflared -> $(if ($tunelProc) {"corriendo ($($tunelProc.Count) proceso(s))"} else {'detenido'})"

    if (Test-Path -LiteralPath $UrlFile) {
        $contenido = Get-Content -LiteralPath $UrlFile -Raw
        if ($contenido -match $UrlPattern) {
            $ok = Test-Url $Matches[0]
            Write-Host "[TUNEL] URL: $($Matches[0])  ->  $(if ($ok) {'responde'} else {'no responde'})"
        } else {
            Write-Host "[TUNEL] URL_TUNEL.txt sin URL valida"
        }
    } else {
        Write-Host "[TUNEL] URL_TUNEL.txt no existe aun"
    }
}

# ---------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------
if ($Bootstrap) { Start-Bootstrap; exit 0 }
if ($Status)    { Show-Status;    exit 0 }

# Install / Uninstall tocan el Programador de tareas (requiere elevacion)
if (-not (Test-IsElevated)) {
    $switches = if ($Uninstall) { "-Uninstall" } else { "-Install" }
    Write-Host "La gestion de tareas requiere privilegios de administrador."
    Write-Host "Solicitando elevacion (acepta el aviso de UAC)..."
    if (Start-Elevated $switches) {
        Write-Host "Finalizado. Verificar con:  .\instalar_autostart.ps1 -Status"
    }
    exit 0
}

if ($Uninstall) { Uninstall-Task; exit 0 }
Install-Task
