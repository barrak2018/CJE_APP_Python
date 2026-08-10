import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from api_client import ApiClient
from login_dialog import LoginDialog
from main_window import MainWindow
from url_dialog import UrlDialog

SETTINGS_ORG = "CJE Perfumes"
SETTINGS_APP = "CJE Perfumes"
KEY_USUARIO = "auth/usuario"
KEY_PASSWORD = "auth/password"
KEY_URL = "conexion/url"


def cargar_credenciales(settings: QSettings):
    return (settings.value(KEY_USUARIO, "") or "",
            settings.value(KEY_PASSWORD, "") or "")


def guardar_credenciales(settings: QSettings, usuario: str, password: str):
    settings.setValue(KEY_USUARIO, usuario)
    settings.setValue(KEY_PASSWORD, password)
    settings.sync()


def borrar_credenciales(settings: QSettings):
    settings.remove(KEY_USUARIO)
    settings.remove(KEY_PASSWORD)
    settings.sync()


def seleccionar_url(settings: QSettings) -> str:
    dlg = UrlDialog(settings.value(KEY_URL, ""))
    if not dlg.exec():
        sys.exit(0)
    url = dlg.url()
    settings.setValue(KEY_URL, url)
    settings.sync()
    return url


def cerrar_sesion(api: ApiClient, settings: QSettings, app: QApplication):
    api.logout()
    borrar_credenciales(settings)
    app.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CJE Perfumes")

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    url = seleccionar_url(settings)
    api = ApiClient(base_url=url)

    usuario, password = cargar_credenciales(settings)
    logueado = False
    if usuario and password:
        try:
            api.login(usuario, password)
            logueado = True
        except Exception:
            logueado = False

    if not logueado:
        dlg = LoginDialog(api)
        if not dlg.exec():
            sys.exit(0)
        if dlg.recordar_credenciales():
            guardar_credenciales(settings, dlg.usuario(), dlg.password())
        else:
            borrar_credenciales(settings)

    window = MainWindow(api)
    window.logout_requested.connect(
        lambda: cerrar_sesion(api, settings, app))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
