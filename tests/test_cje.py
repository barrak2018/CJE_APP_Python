"""Prueba automatizada rápida del sistema CJE (herramientas dejadas por el compañero).

Parte A - Backend en vivo: valida el contrato JSON de cada módulo (endpoints
batch /ventas y /abonos incluidos) contra la API local.
Parte B - GUI no bloqueante: ejercita gui_workers.run_async / push_busy /
pop_busy en Qt sin ventana (offscreen), verificando que la UI no se congela
mientras corre una petición en segundo plano.

Ejecutar:  .\\cje_venv\\Scripts\\python.exe tests\\test_cje.py
Salida:    0 = todo OK, 1 = hay fallos.
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cje_gui"))
sys.path.insert(0, os.path.join(ROOT, "cje_api"))

try:
    import config as _config
    _DEFAULT_URL = _config.get_setting("api", "url")
except Exception:
    _DEFAULT_URL = "http://127.0.0.1:8000"

BASE_URL = os.environ.get("CJE_API_URL", _DEFAULT_URL)
API_USER = os.environ.get("CJE_API_USER", "admin")
API_PASSWORD = os.environ.get("CJE_API_PASSWORD", "admin123")

HEADERS = {}

RESULTS = []


def check(nombre, condicion, detalle=""):
    estado = "PASS" if condicion else "FAIL"
    RESULTS.append(condicion)
    print(f"[{estado}] {nombre}" + (f"  -- {detalle}" if detalle else ""))


# ── Parte A: API en vivo ────────────────────────────────────────────────
def test_api():
    import requests

    print("\n=== PARTE A: API en vivo (read-only) ===")
    try:
        r = requests.get(f"{BASE_URL}/db-check", timeout=10)
        check("GET /db-check -> 200", r.status_code == 200, r.text)
    except Exception as e:
        check("GET /db-check -> 200", False, str(e))
        print("  (se omite el resto de la parte A: la API no responde)")
        return

    # Autenticación: POST /token -> access_token para el resto de peticiones
    try:
        r = requests.post(
            f"{BASE_URL}/token/",
            data={"username": API_USER, "password": API_PASSWORD},
            timeout=10,
        )
        check("POST /token -> 200", r.status_code == 200, r.text)
        if r.status_code == 200:
            HEADERS["Authorization"] = f"Bearer {r.json()['access_token']}"
        else:
            print("  (se omite el resto de la parte A: autenticación falló)")
            return
    except Exception as e:
        check("POST /token -> 200", False, str(e))
        print("  (se omite el resto de la parte A: la API no responde)")
        return

    # Estructura esperada de cada módulo
    esquemas = {
        "/fletes": {"ID_FLETE", "PROVEEDOR", "TOTAL_FLETE"},
        "/catalogo": {"ID_CATALOGO", "NOMBRE"},
        "/inventario": {"ID_INVENTARIO", "CANTIDA", "PRECIO_VENTA"},
        "/clientes": {"CEDULA", "NOMBRE", "SALDO"},
    }
    for path, campos in esquemas.items():
        try:
            inicio = time.perf_counter()
            r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=15)
            datos = r.json()
            delta = (time.perf_counter() - inicio) * 1000
            ok = r.status_code == 200 and isinstance(datos, list)
            if ok and datos:
                ok = campos.issubset(set(datos[0].keys()))
            check(f"GET {path} -> 200 + schema", ok,
                  f"{len(datos)} filas en {delta:.0f} ms")
        except Exception as e:
            check(f"GET {path}", False, str(e))

    # /ventas -> lista con detalles (path batch sin N+1)
    try:
        inicio = time.perf_counter()
        r = requests.get(f"{BASE_URL}/ventas", headers=HEADERS, timeout=30)
        ventas = r.json()
        delta = (time.perf_counter() - inicio) * 1000
        ok = r.status_code == 200 and isinstance(ventas, list)
        if ok and ventas:
            v = ventas[0]
            ok = {"ID_VENTA", "CEDULA", "PRECIO", "PAGO",
                  "NOMBRE_CLIENTE", "detalles"}.issubset(set(v.keys()))
            if v.get("detalles"):
                det = v["detalles"][0]
                ok = ok and {"ID_INVENTARIO", "CANTIDAD",
                             "PRECIO_UNITARIO", "SUBTOTAL"}.issubset(set(det.keys()))
        check("GET /ventas -> 200 + schema", ok,
              f"{len(ventas)} ventas en {delta:.0f} ms")
    except Exception as e:
        check("GET /ventas", False, str(e))

    # /abonos -> lista con NOMBRE_CLIENTE (path batch sin N+1)
    try:
        inicio = time.perf_counter()
        r = requests.get(f"{BASE_URL}/abonos", headers=HEADERS, timeout=30)
        abonos = r.json()
        delta = (time.perf_counter() - inicio) * 1000
        ok = r.status_code == 200 and isinstance(abonos, list)
        if ok and abonos:
            ok = {"ID_ABONO", "CEDULA", "CANTIDAD",
                  "NOMBRE_CLIENTE"}.issubset(set(abonos[0].keys()))
        check("GET /abonos -> 200 + schema", ok,
              f"{len(abonos)} abonos en {delta:.0f} ms")
    except Exception as e:
        check("GET /abonos", False, str(e))


# ── Parte B: GUI no bloqueante (offscreen) ──────────────────────────────
def test_gui_workers():
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from gui_workers import run_async, push_busy, pop_busy

    print("\n=== PARTE B: GUI no bloqueante (gui_workers.py) ===")
    app = QApplication.instance() or QApplication([])

    def esperar(hasta, timeout_ms=3000):
        loop = QEventLoop()
        check_timer = QTimer()
        check_timer.setInterval(20)
        check_timer.timeout.connect(lambda: loop.quit() if hasta() else None)
        check_timer.start()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        check_timer.stop()

    # B.1 - run_async no bloquea el hilo principal
    resultado = {}
    ticks = {"n": 0}
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
    timer.start()

    def lento():
        time.sleep(0.5)
        return 42

    def on_result(v):
        resultado["v"] = v

    run_async(lento, on_result, lambda e: resultado.setdefault("err", e))
    esperar(lambda: "v" in resultado)
    timer.stop()
    check("B.1 resultado entregado al hilo principal",
          resultado.get("v") == 42, f"valor={resultado.get('v')}")
    check("B.1 hilo principal responsive mientras el worker corre",
          ticks["n"] >= 2, f"ticks={ticks['n']} durante 0.5s de trabajo en 2do plano")
    check("B.1 sin error", "err" not in resultado)

    # B.2 - los errores del worker llegan como excepción
    error = {}

    def boom():
        raise ValueError("boom de prueba")

    run_async(boom, lambda v: None, lambda e: error.__setitem__("e", e))
    esperar(lambda: "e" in error)
    check("B.2 error entregado al hilo principal",
          isinstance(error.get("e"), ValueError),
          str(error.get("e")))

    # B.3 - push_busy/pop_busy balanceados (sin cursor de ocupado colgado)
    push_busy()
    push_busy()
    pop_busy()
    check("B.3 cursor ocupado activo con push sin pop",
          app.overrideCursor() is not None)
    pop_busy()
    check("B.3 cursor restaurado tras balancear push/pop",
          app.overrideCursor() is None)


# ── Ejecución ───────────────────────────────────────────────────────────
def main():
    test_api()
    test_gui_workers()
    ok = sum(1 for r in RESULTS if r)
    print(f"\nResultado: {ok}/{len(RESULTS)} pruebas OK")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
