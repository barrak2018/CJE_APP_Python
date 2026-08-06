import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from api_client import ApiClient
from login_dialog import LoginDialog
from main_window import MainWindow

SETTINGS_ORG = "CJE Perfumes"
SETTINGS_APP = "CJE Perfumes"
KEY_USUARIO = "auth/usuario"
KEY_PASSWORD = "auth/password"


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


def cerrar_sesion(api: ApiClient, settings: QSettings, app: QApplication):
    api.logout()
    borrar_credenciales(settings)
    app.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CJE Perfumes")

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    api = ApiClient()

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
