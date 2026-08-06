from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QMessageBox, QLabel,
    QDateEdit,
)
from PySide6.QtCore import QLocale, QDate


def parse_decimal(texto: str) -> float:
    """Convierte un texto decimal a float aceptando punto o coma como
    separador decimal (ej: '150,50', '150.50', '1,500.50', '$ 200')."""
    limpio = (texto or "").replace("$", "").replace(" ", "").strip()
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    return float(limpio)


class DecimalSpinBox(QDoubleSpinBox):
    """SpinBox de decimales que acepta punto o coma como separador decimal,
    sin depender del locale del sistema (siempre muestra y devuelve punto)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setGroupSeparatorShown(False)

    def validate(self, text, pos):
        if "," in text:
            text = text.replace(",", ".")
        return super().validate(text, pos)

    def valueFromText(self, text):
        if "," in text:
            text = text.replace(",", ".")
        return super().valueFromText(text)


class FieldDef:
    def __init__(self, name: str, label: str, field_type: str = "str",
                 required: bool = False, default=None, options: list[tuple] = None,
                 minimum=None, maximum=None, decimals: int = 2,
                 step: float = 0.01,
                 search_cls=None, search_key: str = None,
                 search_items: list[dict] = None,
                 search_info: callable = None):
        self.name = name
        self.label = label
        self.field_type = field_type
        self.required = required
        self.default = default
        self.options = options or []
        self.minimum = minimum
        self.maximum = maximum
        self.decimals = decimals
        self.step = step
        self.search_cls = search_cls
        self.search_key = search_key
        self.search_items = search_items or []
        self.search_info = search_info


class FormDialog(QDialog):
    def __init__(self, title: str, fields: list[FieldDef], data: dict = None,
                 parent=None, preview: callable = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.fields = fields
        self.inputs = {}
        self.preview = preview
        self.lbl_preview = None
        self._build_ui(data)

    def _build_ui(self, data: dict | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        for f in self.fields:
            widget = self._create_input(f, data.get(f.name) if data else None)
            self.inputs[f.name] = widget
            form.addRow(f.label + (" *" if f.required else ""), widget)
            if f.field_type == "search" and f.search_info is not None:
                info = QLabel()
                info.setWordWrap(True)
                info.setStyleSheet("color: #666;")
                form.addRow("", info)
                widget.itemSelected.connect(
                    lambda item, lbl=info, fd=f: self._update_search_info(
                        fd, item, lbl))
                self._update_search_info(f, widget.item(), info)

        if self.preview is not None:
            self.lbl_preview = QLabel()
            self.lbl_preview.setWordWrap(True)
            form.addRow("", self.lbl_preview)
            for f in self.fields:
                w = self.inputs[f.name]
                if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.valueChanged.connect(self._update_preview)
                elif isinstance(w, QComboBox):
                    w.currentIndexChanged.connect(self._update_preview)
                elif isinstance(w, QLineEdit):
                    w.textChanged.connect(self._update_preview)
                elif f.field_type == "search":
                    w.itemSelected.connect(self._update_preview)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.preview is not None:
            self._update_preview()

    def _update_preview(self):
        if self.preview is None or self.lbl_preview is None:
            return
        try:
            texto = self.preview(self.get_data())
        except Exception:
            texto = ""
        self.lbl_preview.setText(texto or "")

    def _update_search_info(self, f: FieldDef, item, lbl: QLabel):
        if item is None or f.search_info is None:
            lbl.clear()
            return
        try:
            texto = f.search_info(item)
        except Exception:
            texto = ""
        lbl.setText(texto or "")

    def _create_input(self, f: FieldDef, value):
        if f.field_type == "search":
            w = f.search_cls()
            w.setItems(f.search_items)
            if value is not None:
                for it in f.search_items:
                    if it.get(f.search_key) == value:
                        w.setItem(it)
                        break
            return w

        if f.field_type == "char" and f.options:
            w = QComboBox()
            for val, label in f.options:
                w.addItem(label, val)
            if value is not None:
                idx = w.findData(value)
                if idx >= 0:
                    w.setCurrentIndex(idx)
            elif f.default is not None:
                idx = w.findData(f.default)
                if idx >= 0:
                    w.setCurrentIndex(idx)
            return w

        if f.field_type == "int":
            w = QSpinBox()
            w.setRange(f.minimum or 0, f.maximum or 999999999)
            w.setValue(value if value is not None else (f.default or 0))
            return w

        if f.field_type == "float":
            w = DecimalSpinBox()
            w.setRange(f.minimum or 0.0, f.maximum or 999999999.0)
            w.setDecimals(f.decimals)
            w.setSingleStep(f.step)
            w.setValue(value if value is not None else (f.default or 0.0))
            return w

        if f.field_type == "date":
            w = QDateEdit()
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            valor = value if value is not None else f.default
            qd = None
            if valor:
                qd = QDate.fromString(str(valor), "yyyy-MM-dd")
                if not qd.isValid():
                    qd = None
            w.setDate(qd if qd is not None else QDate.currentDate())
            return w

        w = QLineEdit()
        if value is not None:
            w.setText(str(value))
        elif f.default is not None:
            w.setText(str(f.default))
        return w

    def _validate_and_accept(self):
        for f in self.fields:
            w = self.inputs[f.name]
            if f.required:
                if f.field_type == "search" and w.item() is None:
                    QMessageBox.warning(self, "Validación",
                                        f"{f.label} es obligatorio.")
                    w.setFocus()
                    return
                if isinstance(w, QLineEdit) and not w.text().strip():
                    QMessageBox.warning(self, "Validación", f"{f.label} es obligatorio.")
                    w.setFocus()
                    return
                if isinstance(w, QComboBox) and w.currentData() is None:
                    QMessageBox.warning(self, "Validación", f"{f.label} es obligatorio.")
                    w.setFocus()
                    return
        self.accept()

    def get_data(self) -> dict:
        result = {}
        for f in self.fields:
            w = self.inputs[f.name]
            if f.field_type == "search":
                item = w.item()
                result[f.name] = item[f.search_key] if item else None
            elif isinstance(w, QLineEdit):
                val = w.text().strip()
                if f.field_type == "int":
                    val = int(val) if val else None
                elif f.field_type == "float":
                    val = float(val) if val else None
                result[f.name] = val if val else None
            elif isinstance(w, QSpinBox):
                result[f.name] = w.value()
            elif isinstance(w, QDoubleSpinBox):
                result[f.name] = w.value()
            elif isinstance(w, QDateEdit):
                result[f.name] = w.date().toString("yyyy-MM-dd")
            elif isinstance(w, QComboBox):
                val = w.currentData()
                result[f.name] = val if val not in (None, "") else None
        return result
