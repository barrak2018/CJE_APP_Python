#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CJE Perfumes - Centro de control (TUI de terminal).

Reemplaza a los scripts PowerShell del proyecto:
  1. iniciar_servidor.ps1   -> opcion 1 (iniciar API) / 2 (detener)
  2. iniciar_gui.ps1        -> opcion 3
  3. iniciar_tunel.ps1      -> opcion 4
  4. detener_tunel.ps1      -> opcion 5
  5. iniciar_gui_tunel.ps1  -> opcion 6

Uso:  .\\cje_venv\\Scripts\\python.exe cje_tui.py

Sin dependencias externas: solo libreria estandar.
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMP = Path(os.environ.get("TEMP", str(ROOT)))
STATE_DIR = TEMP
SERVER_PID_FILE = STATE_DIR / "cje_server.pid"
URL_FILE = ROOT / "URL_TUNEL.txt"
TUNNEL_URL_PATTERN = r"https://[a-z0-9-]+\.trycloudflare\.com"

try:
    sys.path.insert(0, str(ROOT / "cje_api"))
    import config as api_config
except Exception as _e:  # pragma: no cover - solo si cje_api/config.py falla
    api_config = None
    _CFG_ERROR = _e


def _reconfigure_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# --------------------------------------------------------------------------
# Utilidades de proceso
# --------------------------------------------------------------------------
def _venv_python() -> str:
    venv = ROOT / "cje_venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    print(f"[AVISO] No se encontro cje_venv; usando el Python actual: {sys.executable}")
    return sys.executable


def _spawn_and_tee(cmd, cwd, log_path: Path, env=None):
    """Lanza un proceso en segundo plano y vuelca su salida a un log y a una lista."""
    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
              "text": True, "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, **kwargs)
    lines = []

    def _tee():
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                for linea in proc.stdout:
                    lines.append(linea.rstrip())
                    f.write(linea)
                    f.flush()
        except Exception:
            pass

    threading.Thread(target=_tee, daemon=True).start()
    return proc, lines


def _pid_alive(pid: int) -> bool:
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=10)
        return str(pid) in r.stdout
    except Exception:
        return False


def _kill_tree(pid: int) -> bool:
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True, timeout=15)
        return True
    except Exception:
        return False


def _pid_by_port(port: int):
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15)
        for linea in r.stdout.splitlines():
            partes = linea.split()
            if len(partes) >= 5 and "LISTENING" in linea and partes[1].endswith(f":{port}"):
                return int(partes[4])
    except Exception:
        pass
    return None


def _cloudflared():
    exe = Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe")
    if exe.exists():
        return str(exe)
    return shutil.which("cloudflared")


def _wait_for_pattern(lines, pattern, timeout):
    regex = re.compile(pattern)
    fin = time.time() + timeout
    while time.time() < fin:
        for linea in list(lines):
            m = regex.search(linea)
            if m:
                return m.group(0)
        time.sleep(0.5)
    return None


def _http_ok(url, timeout=4) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _base_url() -> str:
    if api_config is None:
        return "http://127.0.0.1:8000"
    host = api_config.get_setting("api", "host") or "127.0.0.1"
    port = api_config.get_setting("api", "port") or 8000
    check_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return f"http://{check_host}:{port}"


def _config_values():
    return {
        "host": api_config.get_setting("api", "host") or "127.0.0.1",
        "port": api_config.get_setting("api", "port") or 8000,
        "reload": bool(api_config.get_setting("api", "reload")),
        "url": api_config.get_setting("api", "url") or "http://127.0.0.1:8000",
    }


# --------------------------------------------------------------------------
# Acciones
# --------------------------------------------------------------------------
def iniciar_servidor():
    if api_config is None:
        print(f"[ERROR] No se pudo cargar cje_api/config: {_CFG_ERROR}")
        return
    cfg = _config_values()

    # Los secretos son obligatorios; la API no arranca sin ellos.
    try:
        for seccion, clave in api_config.REQUIRED_SECRETS:
            api_config.require_secret(seccion, clave)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return

    if _pid_by_port(cfg["port"]):
        print(f"[ERROR] Ya hay un proceso escuchando en el puerto {cfg['port']}.")
        print("        Si es un servidor CJE, usa la opcion 2 (Detener servidor) primero.")
        return

    python = _venv_python()
    cmd = [python, "-m", "uvicorn", "main:app",
           "--host", str(cfg["host"]), "--port", str(cfg["port"])]
    if cfg["reload"]:
        cmd.append("--reload")

    env = os.environ.copy()
    for var, seccion, clave in [("CJE_API_USER", "auth", "api_user"),
                                ("CJE_API_PASSWORD", "auth", "api_password"),
                                ("CJE_SECRET_KEY", "auth", "secret_key")]:
        if var not in env:
            valor = api_config.get_setting(seccion, clave)
            if valor:
                env[var] = str(valor)

    log = TEMP / "cje_api.log"
    print(f"Iniciando API en http://{cfg['host']}:{cfg['port']} (reload={'si' if cfg['reload'] else 'no'})...")
    proc, lines = _spawn_and_tee(cmd, ROOT / "cje_api", log, env)
    SERVER_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(f"PID: {proc.pid}  |  Log: {log}")

    base = _base_url()
    for _ in range(30):  # hasta ~15s
        if _http_ok(base + "/", timeout=2):
            print(f"[OK] API operativa en {base}  (Swagger: {base}/docs)")
            return
        time.sleep(0.5)
    print("[AVISO] La API aun no responde. Revisa el log.")
    print("        Ultimas lineas:")
    for linea in lines[-5:]:
        print("        " + linea)


def detener_servidor():
    port = api_config.get_setting("api", "port") or 8000 if api_config else 8000
    detenido = False
    if SERVER_PID_FILE.exists():
        try:
            pid = int(SERVER_PID_FILE.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                print(f"Deteniendo servidor (PID {pid})...")
                detenido = _kill_tree(pid)
        except ValueError:
            pass
        try:
            SERVER_PID_FILE.unlink()
        except OSError:
            pass
    if not detenido:
        pid = _pid_by_port(port)
        if pid:
            print(f"Deteniendo proceso del puerto {port} (PID {pid})...")
            detenido = _kill_tree(pid)
    if detenido:
        print("Servidor detenido.")
    else:
        print("No se encontro un servidor corriendo.")


def iniciar_gui(env_extra=None):
    python = _venv_python()
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    log = TEMP / "cje_gui.log"
    print("Iniciando GUI...")
    proc, _ = _spawn_and_tee([python, "main.py"], ROOT / "cje_gui", log, env)
    print(f"PID: {proc.pid}  |  Log: {log}")
    print("La GUI abre su propia ventana. Cierra la ventana para terminar.")


def iniciar_tunel():
    cloudflared = _cloudflared()
    if not cloudflared:
        print("[ERROR] No se encontro cloudflared.")
        print("        Instalalo con:  winget install --id Cloudflare.cloudflared")
        return

    cfg = _config_values()
    target = f"http://{cfg['host']}:{cfg['port']}"
    print(f"Verificando API en {target} ...")
    if not _http_ok(target + "/", timeout=5):
        print("[ADVERTENCIA] La API no responde en el objetivo. El tunel se creara igual, pero no habra servicio detras.")

    log = TEMP / "cloudflared_tunel.log"
    print("Iniciando tunel temporal de Cloudflare...")
    proc, lines = _spawn_and_tee([cloudflared, "tunnel", "--url", target, "--no-autoupdate"],
                                 ROOT, log)
    print(f"PID: {proc.pid}  |  Log: {log}")

    url = _wait_for_pattern(lines, TUNNEL_URL_PATTERN, timeout=90)
    if not url:
        print("[ERROR] No se obtuvo la URL del tunel en 90s.")
        print("        Ultimas lineas del log:")
        for linea in lines[-5:]:
            print("        " + linea)
        return
    fecha = time.strftime("%Y-%m-%d %H:%M:%S")
    URL_FILE.write_text(f"# URL del tunel temporal - generado el {fecha}\n{url}\n",
                        encoding="utf-8")
    print(f"[OK] TUNEL ACTIVO: {url}")
    print(f"     URL guardada en: {URL_FILE}")


def detener_tunel():
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=10)
        cantidad = sum(1 for l in r.stdout.splitlines() if "cloudflared" in l.lower())
    except Exception:
        cantidad = 0
    try:
        subprocess.run(["taskkill", "/IM", "cloudflared.exe", "/F"],
                       capture_output=True, text=True, timeout=15)
        print(f"Tuneles detenidos: {cantidad} proceso(s)." if cantidad else
              "No hay tuneles de cloudflared activos.")
    except Exception:
        print("[ERROR] No se pudieron detener los tuneles.")


def iniciar_gui_tunel():
    if not URL_FILE.exists():
        print("[ERROR] No existe URL_TUNEL.txt.")
        print("        Primero ejecuta la opcion 4 (Iniciar tunel Cloudflare).")
        return
    url = None
    for linea in URL_FILE.read_text(encoding="utf-8").splitlines():
        m = re.search(TUNNEL_URL_PATTERN, linea)
        if m:
            url = m.group(0)
            break
    if not url:
        print("[ERROR] No hay una URL de tunel valida en URL_TUNEL.txt.")
        print("        Ejecuta la opcion 4 nuevamente.")
        return

    print(f"Apuntando la GUI al tunel: {url}")
    if not _http_ok(url + "/", timeout=10):
        print("[ADVERTENCIA] El tunel no responde. Verifica que la API y el tunel esten activos.")
    iniciar_gui({"CJE_API_URL": url})


def estado():
    print("\n--- Estado del sistema ---")

    python = _venv_python()
    print(f"Python (venv):  {'OK' if Path(python).exists() else 'FALTANTE'}  ({python})")

    cloudflared = _cloudflared()
    print(f"Cloudflared:    {'OK  (' + cloudflared + ')' if cloudflared else 'NO instalado'}")

    if api_config:
        cfg = _config_values()
        base = _base_url()
        print(f"API config:     {cfg['host']}:{cfg['port']}  (reload={'si' if cfg['reload'] else 'no'})")
        print(f"API responde:   {'SI' if _http_ok(base + '/', timeout=4) else 'NO'}   ({base})")
        pid = _pid_by_port(cfg["port"])
        if pid:
            print(f"Proceso API:    activo (PID {pid}, puerto {cfg['port']})")
        elif SERVER_PID_FILE.exists():
            print(f"Proceso API:    PID registrado pero no responde ({SERVER_PID_FILE})")
        else:
            print("Proceso API:    detenido")
    else:
        print("API config:     NO CARGADA")

    if URL_FILE.exists():
        for linea in URL_FILE.read_text(encoding="utf-8").splitlines():
            m = re.search(TUNNEL_URL_PATTERN, linea)
            if m:
                ok = "SI" if _http_ok(m.group(0) + "/", timeout=4) else "NO"
                print(f"Tunel activo:   {ok}  ({m.group(0)})")
                break
    else:
        print("Tunel:          sin URL_TUNEL.txt")

    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=10)
        n = sum(1 for l in r.stdout.splitlines() if "cloudflared" in l.lower())
        print(f"cloudflared:    {n} proceso(s) corriendo")
    except Exception:
        print("cloudflared:    no consultable")


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------
def _print_menu():
    print()
    print("=" * 45)
    print("  CJE Perfumes - Centro de control")
    print("=" * 45)
    print(" [1] Iniciar servidor API")
    print(" [2] Detener servidor API")
    print(" [3] Iniciar GUI (local)")
    print(" [4] Iniciar tunel Cloudflare")
    print(" [5] Detener tunel")
    print(" [6] Iniciar GUI por tunel")
    print(" [7] Estado del sistema")
    print(" [0] Salir")
    print("=" * 45)


def main():
    _reconfigure_stdout()
    print("Bienvenido al centro de control de CJE Perfumes.")
    while True:
        _print_menu()
        try:
            opcion = input("Opcion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdios.")
            break
        if opcion == "0":
            print("Adios.")
            break
        elif opcion == "1":
            iniciar_servidor()
        elif opcion == "2":
            detener_servidor()
        elif opcion == "3":
            iniciar_gui()
        elif opcion == "4":
            iniciar_tunel()
        elif opcion == "5":
            detener_tunel()
        elif opcion == "6":
            iniciar_gui_tunel()
        elif opcion == "7":
            estado()
        else:
            print("Opcion no valida.")
        try:
            input("\nPresiona Enter para continuar...")
        except (EOFError, KeyboardInterrupt):
            print("Adios.")
            break


if __name__ == "__main__":
    main()
