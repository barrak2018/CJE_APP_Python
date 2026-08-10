from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel,
)


class UrlDialog(QDialog):
    def __init__(self, url_inicial: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conexión - CJE Perfumes")
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        lbl = QLabel("Ingrese la URL del servidor de la API:")
        layout.addWidget(lbl)

        form = QFormLayout()
        self.edt_url = QLineEdit(url_inicial)
        self.edt_url.setPlaceholderText("http://127.0.0.1:8000")
        form.addRow("URL:", self.edt_url)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Continuar")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._aceptar)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        self.edt_url.returnPressed.connect(self._aceptar)
        self.edt_url.setFocus()
        self.edt_url.selectAll()

    def _aceptar(self):
        url = self.edt_url.text().strip().rstrip("/")
        if not url:
            url = "http://127.0.0.1:8000"
        self._url = url
        self.accept()

    def url(self) -> str:
        return self._url
