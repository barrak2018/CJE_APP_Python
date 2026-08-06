from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit,
    QCheckBox, QPushButton, QLabel,
)

from api_client import ApiClient, AuthenticationError


class LoginDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Iniciar sesión - CJE Perfumes")
        self.setModal(True)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #c0392b;")
        self.lbl_error.setVisible(False)
        layout.addWidget(self.lbl_error)

        form = QFormLayout()
        self.edt_usuario = QLineEdit()
        self.edt_password = QLineEdit()
        self.edt_password.setEchoMode(QLineEdit.Password)
        form.addRow("Usuario:", self.edt_usuario)
        form.addRow("Contraseña:", self.edt_password)
        layout.addLayout(form)

        self.chk_recordar = QCheckBox("Recordar credenciales")
        self.chk_recordar.setChecked(True)
        layout.addWidget(self.chk_recordar)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Iniciar sesión")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._intentar_login)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        self.edt_password.returnPressed.connect(self._intentar_login)
        self.edt_usuario.returnPressed.connect(self.edt_password.setFocus)
        self.edt_usuario.setFocus()

    def _intentar_login(self):
        usuario = self.edt_usuario.text().strip()
        password = self.edt_password.text()
        if not usuario or not password:
            self._mostrar_error("Ingrese usuario y contraseña")
            return
        try:
            self.api.login(usuario, password)
        except AuthenticationError as e:
            self._mostrar_error(str(e))
            return
        except Exception as e:
            self._mostrar_error(f"Error de conexión: {e}")
            return
        self.accept()

    def _mostrar_error(self, mensaje: str):
        self.lbl_error.setText(mensaje)
        self.lbl_error.setVisible(True)

    def recordar_credenciales(self) -> bool:
        return self.chk_recordar.isChecked()

    def usuario(self) -> str:
        return self.edt_usuario.text().strip()

    def password(self) -> str:
        return self.edt_password.text()
