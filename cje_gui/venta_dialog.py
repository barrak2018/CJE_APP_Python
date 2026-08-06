from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QDialogButtonBox,
    QLineEdit, QComboBox, QDateEdit, QTableWidget,
    QTableWidgetItem, QPushButton, QMessageBox,
    QAbstractItemView, QGroupBox, QSpinBox, QLabel,
)

from api_client import ApiClient
from dialogs import DecimalSpinBox, parse_decimal
from cliente_search import ClienteSearchBox, ProductoVentaSearchBox
from gui_workers import run_async


class VentaDialog(QDialog):
    TIPOS_PAGO = [("CONTADO", "Contado"), ("CREDITO", "Crédito")]
    FORMAS_PAGO = [
        ("EFECTIVO", "Efectivo"),
        ("TRANSFERENCIA", "Transferencia"),
        ("TARJETA", "Tarjeta"),
        ("MOVIL", "Pago Móvil"),
        ("OTRO", "Otro"),
    ]

    def __init__(self, api: ApiClient, venta: dict = None, parent=None):
        super().__init__(parent)
        self.api = api
        self.venta = venta
        self._base_title = "Editar Venta" if venta else "Nueva Venta"
        self.setWindowTitle(self._base_title)
        self.setMinimumSize(640, 560)
        self._items = []  # [{ID_INVENTARIO, nombre, precio, cantidad, stock}]
        self._saldos = {}
        self._productos = []
        self._updating = False
        self._pending_references = 0
        self._loading = False
        self._build_ui()
        self._load_reference_data()

    # ── Construcción de la UI ─────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.search_cliente = ClienteSearchBox()
        self.date_fecha = QDateEdit()
        self.date_fecha.setCalendarPopup(True)
        self.date_fecha.setDate(QDate.currentDate())
        self.date_fecha.setDisplayFormat("yyyy-MM-dd")
        self.cmb_tipo_pago = QComboBox()
        for val, label in self.TIPOS_PAGO:
            self.cmb_tipo_pago.addItem(label, val)
        self.cmb_forma_pago = QComboBox()
        for val, label in self.FORMAS_PAGO:
            self.cmb_forma_pago.addItem(label, val)
        self.spin_pago = DecimalSpinBox()
        self.spin_pago.setDecimals(2)
        self.spin_pago.setRange(0.0, 999999999.0)
        self.spin_pago.setPrefix("$ ")

        form.addRow("Cliente *", self.search_cliente)
        form.addRow("Fecha", self.date_fecha)
        form.addRow("Tipo de Pago *", self.cmb_tipo_pago)
        form.addRow("Forma de Pago *", self.cmb_forma_pago)
        layout.addLayout(form)
        self.cmb_tipo_pago.currentIndexChanged.connect(self._on_tipo_pago_changed)
        self.search_cliente.clienteSeleccionado.connect(self._on_cliente_changed)
        self.spin_pago.valueChanged.connect(self._refresh_saldos)

        # Sección de ítems
        group = QGroupBox("Productos")
        vbox = QVBoxLayout(group)

        add_row = QHBoxLayout()
        self.search_producto = ProductoVentaSearchBox()
        self.search_producto.setMinimumWidth(260)
        self.spin_cantidad = QSpinBox()
        self.spin_cantidad.setRange(1, 999999)
        self.spin_cantidad.setValue(1)
        btn_add = QPushButton("Agregar")
        btn_add.clicked.connect(self._on_add_item)
        add_row.addWidget(self.search_producto, 1)
        add_row.addWidget(self.spin_cantidad)
        add_row.addWidget(btn_add)
        vbox.addLayout(add_row)

        self.table_items = QTableWidget()
        self.table_items.setColumnCount(4)
        self.table_items.setHorizontalHeaderLabels(
            ["Producto", "Stock", "Cantidad", "Subtotal"])
        self.table_items.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_items.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table_items.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table_items.horizontalHeader().setStretchLastSection(True)
        self.table_items.itemChanged.connect(self._on_item_changed)
        vbox.addWidget(self.table_items)

        btn_remove = QPushButton("Quitar seleccionado")
        btn_remove.clicked.connect(self._on_remove_item)
        vbox.addWidget(btn_remove)

        total_row = QHBoxLayout()
        total_row.addStretch()
        total_row.addWidget(self._label("Total de la venta:"))
        self.edit_precio = QLineEdit()
        self.edit_precio.setPlaceholderText("$ 0.00")
        self.edit_precio.setToolTip(
            "Deje el campo vacío para usar el precio calculado automáticamente, "
            "o escriba un precio manual.")
        self.edit_precio.setMaximumWidth(200)
        total_row.addWidget(self.edit_precio)
        total_row.addWidget(self._label("(vacío = precio automático)"))
        vbox.addLayout(total_row)
        self.edit_precio.textChanged.connect(self._on_precio_changed)

        deuda_actual_row = QHBoxLayout()
        deuda_actual_row.addStretch()
        deuda_actual_row.addWidget(self._label("Deuda Actual (cliente):"))
        self.lbl_deuda_actual = self._label("$ 0.00")
        deuda_actual_row.addWidget(self.lbl_deuda_actual)
        vbox.addLayout(deuda_actual_row)

        deuda_posterior_row = QHBoxLayout()
        deuda_posterior_row.addStretch()
        deuda_posterior_row.addWidget(self._label("Deuda Posterior (tras la venta):"))
        self.lbl_deuda_posterior = self._label("$ 0.00")
        deuda_posterior_row.addWidget(self.lbl_deuda_posterior)
        vbox.addLayout(deuda_posterior_row)

        credito_row = QHBoxLayout()
        credito_row.addStretch()
        credito_row.addWidget(self._label("Crédito a favor (cliente):"))
        self.lbl_credito = self._label("$ 0.00")
        credito_row.addWidget(self.lbl_credito)
        vbox.addLayout(credito_row)

        monto_pagar_row = QHBoxLayout()
        monto_pagar_row.addStretch()
        monto_pagar_row.addWidget(self._label("Monto a pagar:"))
        self.lbl_monto_a_pagar = self._label("$ 0.00")
        monto_pagar_row.addWidget(self.lbl_monto_a_pagar)
        vbox.addLayout(monto_pagar_row)

        pago_row = QHBoxLayout()
        pago_row.addStretch()
        pago_row.addWidget(self._label("Monto Pagado:"))
        self.spin_pago.setMaximumWidth(200)
        pago_row.addWidget(self.spin_pago)
        vbox.addLayout(pago_row)

        layout.addWidget(group, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._buttons = buttons
        self._on_tipo_pago_changed()

    @staticmethod
    def _label(text: str):
        lbl = QLabel(text)
        return lbl

    # ── Carga de datos de referencia ──────────────────────
    def _set_loading(self, loading: bool):
        self._loading = loading
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(not loading)
        self.setWindowTitle(self._base_title + (" (cargando…)" if loading else ""))

    def _load_reference_data(self):
        self._set_loading(True)
        self._pending_references = 0
        api = self.api

        self._pending_references += 1

        def on_clientes(clientes):
            self._pending_references -= 1
            self._saldos = {c["CEDULA"]: float(c.get("SALDO") or 0.0)
                            for c in clientes}
            self.search_cliente.setClientes(clientes)
            self._check_references_loaded()

        def on_clientes_error(exc):
            self._pending_references -= 1
            QMessageBox.warning(self, "Clientes",
                                f"No se pudieron cargar los clientes:\n{self._parse_error(exc)}")
            self._check_references_loaded()

        run_async(lambda: api.get_clientes(), on_clientes, on_clientes_error)

        self._pending_references += 1

        def fetch_productos():
            inventario = api.get_inventario()
            catalogo = {c["ID_CATALOGO"]: c for c in api.get_catalogo()}
            return inventario, catalogo

        def on_productos(data):
            self._pending_references -= 1
            inventario, catalogo = data
            self._build_productos(inventario, catalogo)
            self._check_references_loaded()

        def on_productos_error(exc):
            self._pending_references -= 1
            QMessageBox.warning(self, "Productos",
                                f"No se pudieron cargar los productos:\n{self._parse_error(exc)}")
            self._check_references_loaded()

        run_async(fetch_productos, on_productos, on_productos_error)

    def _check_references_loaded(self):
        if self._pending_references <= 0:
            self._pending_references = 0
            self._set_loading(False)
            if self.venta:
                self._prefill_edit()

    def _build_productos(self, inventario, catalogo):
        reserved = {}
        if self.venta:
            for det in self.venta.get("detalles") or []:
                reserved[det["ID_INVENTARIO"]] = det.get("CANTIDAD") or 0

        self._productos = []
        for inv in inventario:
            # En edición, el stock disponible suma la cantidad ya reservada
            # por esta misma venta.
            stock_efectivo = (inv.get("CANTIDA") or 0) + reserved.get(
                inv["ID_INVENTARIO"], 0)
            if stock_efectivo <= 0:
                continue
            cat = catalogo.get(inv.get("ID_CATALOGO"))
            nombre = cat["NOMBRE"] if cat else f'Catálogo #{inv.get("ID_CATALOGO")}'
            precio = round(float(inv.get("PRECIO_VENTA") or 0.0), 2)
            rec = {
                "ID_INVENTARIO": inv["ID_INVENTARIO"],
                "nombre": nombre,
                "MARCA": (cat or {}).get("MARCA") or "",
                "PRESENTACION": (cat or {}).get("PRESENTACION") or "",
                "precio": float(precio),
                "stock": stock_efectivo,
            }
            self._productos.append(rec)

        self.search_producto.setProductos(self._productos)

    def _prefill_edit(self):
        v = self.venta
        cliente = next((c for c in self.search_cliente.clientes()
                        if c["CEDULA"] == v["CEDULA"]), None)
        if cliente:
            self.search_cliente.setCliente(cliente)

        fecha = v.get("FECHA")
        if fecha:
            qd = QDate.fromString(str(fecha), "yyyy-MM-dd")
            if qd.isValid():
                self.date_fecha.setDate(qd)

        idx = self.cmb_tipo_pago.findData(v.get("TIPO_PAGO"))
        if idx >= 0:
            self.cmb_tipo_pago.setCurrentIndex(idx)
        idx = self.cmb_forma_pago.findData(v.get("FORMA_DE_PAGO"))
        if idx >= 0:
            self.cmb_forma_pago.setCurrentIndex(idx)

        self.spin_pago.setValue(float(v.get("PAGO") or 0.0))

        subtotal = 0.0
        for det in v.get("detalles") or []:
            prod = next((p for p in self._productos
                         if p["ID_INVENTARIO"] == det["ID_INVENTARIO"]), None)
            if not prod:
                continue
            cant = det.get("CANTIDAD") or 0
            # Precio unitario guardado en la línea; si es NULL, el del inventario
            precio = round(float(det.get("PRECIO_UNITARIO")
                                if det.get("PRECIO_UNITARIO") is not None
                                else prod["precio"]), 2)
            subtotal += precio * cant
            self._items.append({**prod, "precio": precio, "cantidad": cant})
        self._refresh_items()

        precio_guardado = float(v.get("PRECIO") or 0.0)
        if abs(precio_guardado - subtotal) > 0.005:
            self.edit_precio.setText(f"{precio_guardado:.2f}")

        self._on_tipo_pago_changed()

    # ── Manejo de ítems ───────────────────────────────────
    def _current_producto(self):
        return self.search_producto.item()

    def _on_add_item(self):
        prod = self._current_producto()
        if not prod:
            QMessageBox.information(self, "Productos",
                                    "Seleccione un producto primero.")
            return
        cantidad = self.spin_cantidad.value()
        ya = next((i for i in self._items
                   if i["ID_INVENTARIO"] == prod["ID_INVENTARIO"]), None)
        if ya:
            QMessageBox.information(self, "Productos",
                                    "El producto ya está en la lista; "
                                    "quítelo y vuelva a agregarlo si desea otra cantidad.")
            return
        if cantidad > prod["stock"]:
            QMessageBox.warning(self, "Stock",
                                f"Stock insuficiente. Disponible: {prod['stock']}")
            return
        self._items.append({**prod, "cantidad": cantidad})
        self.search_producto.clear()
        self._refresh_items()

    def _on_remove_item(self):
        row = self.table_items.currentRow()
        if row < 0:
            QMessageBox.information(self, "Seleccionar",
                                    "Seleccione un producto de la lista.")
            return
        self._items.pop(row)
        self._refresh_items()

    def _refresh_items(self):
        self._updating = True
        try:
            subtotal_total = 0.0
            self.table_items.setRowCount(len(self._items))
            for idx, item in enumerate(self._items):
                subtotal = item["precio"] * item["cantidad"]
                subtotal_total += subtotal
                vals = [item["nombre"], item["stock"], item["cantidad"],
                        f"${subtotal:,.2f}"]
                for col, val in enumerate(vals):
                    it = QTableWidgetItem(str(val))
                    it.setData(Qt.ItemDataRole.UserRole, item)
                    if col not in (2, 3):  # cantidad y subtotal editables
                        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table_items.setItem(idx, col, it)
            self.table_items.resizeColumnsToContents()
        finally:
            self._updating = False
        self.edit_precio.setPlaceholderText(f"$ {subtotal_total:,.2f}")
        if self.cmb_tipo_pago.currentData() == "CONTADO":
            self.spin_pago.setValue(self._monto_a_pagar())
        self._refresh_saldos()

    def _on_item_changed(self, item):
        if self._updating or item.column() not in (2, 3):
            return
        row = item.row()
        if row < 0 or row >= len(self._items):
            return
        texto = item.text().strip()
        if item.column() == 2:
            self._set_cantidad(row, texto)
        else:
            self._set_subtotal(row, texto)

    def _set_cantidad(self, row, texto):
        try:
            cantidad = int(texto)
            if cantidad < 1:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "Cantidad",
                "La cantidad debe ser un número entero mayor o igual a 1.")
            self._refresh_items()
            return
        stock = self._items[row]["stock"]
        if cantidad > stock:
            QMessageBox.warning(
                self, "Stock",
                f"Stock insuficiente. Disponible: {stock}")
            self._refresh_items()
            return
        self._items[row]["cantidad"] = cantidad
        self._refresh_items()

    def _set_subtotal(self, row, texto):
        try:
            subtotal = parse_decimal(texto)
            if subtotal < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "Subtotal",
                "El subtotal debe ser un número válido mayor o igual a cero.")
            self._refresh_items()
            return
        cantidad = self._items[row]["cantidad"]
        if cantidad > 0:
            self._items[row]["precio"] = round(subtotal / cantidad, 2)
        self._refresh_items()

    # ── Monto Pagado: último campo, bloqueado en Contado ──
    def _total_venta(self):
        subtotal = sum(
            item["precio"] * item["cantidad"] for item in self._items)
        texto = self.edit_precio.text().strip()
        if texto:
            try:
                manual = parse_decimal(texto)
                if manual >= 0:
                    return round(manual, 2)
            except ValueError:
                pass
        return round(subtotal, 2)

    def _deuda_actual(self):
        return self._saldos.get(self.search_cliente.cedula(), 0.0)

    def _credito_disponible(self):
        return max(0.0, -self._deuda_actual())

    def _monto_a_pagar(self):
        return max(self._total_venta() + self._deuda_actual(), 0.0)

    def _on_cliente_changed(self):
        if self.cmb_tipo_pago.currentData() == "CONTADO":
            self.spin_pago.setValue(self._monto_a_pagar())
        self._refresh_saldos()

    def _refresh_saldos(self):
        deuda = self._deuda_actual()
        credito = self._credito_disponible()
        total = self._total_venta()
        monto_pagar = self._monto_a_pagar()
        posterior = deuda + total - self.spin_pago.value()
        self.lbl_deuda_actual.setText(f"$ {deuda:,.2f}")
        self.lbl_deuda_posterior.setText(f"$ {posterior:,.2f}")
        self.lbl_credito.setText(f"$ {credito:,.2f}")
        self.lbl_monto_a_pagar.setText(f"$ {monto_pagar:,.2f}")

    def _on_tipo_pago_changed(self):
        contado = self.cmb_tipo_pago.currentData() == "CONTADO"
        if contado:
            self.spin_pago.setValue(self._monto_a_pagar())
        self.spin_pago.setEnabled(not contado)
        self._refresh_saldos()

    def _on_precio_changed(self):
        if self.cmb_tipo_pago.currentData() == "CONTADO":
            self.spin_pago.setValue(self._monto_a_pagar())
        self._refresh_saldos()

    # ── Guardado ──────────────────────────────────────────
    def _on_save(self):
        if self.search_cliente.cedula() is None:
            QMessageBox.warning(self, "Validación",
                                "Seleccione un cliente.")
            return
        if not self._items:
            QMessageBox.warning(self, "Validación",
                                "Agregue al menos un producto.")
            return

        data = {
            "CEDULA": self.search_cliente.cedula(),
            "FECHA": self.date_fecha.date().toString("yyyy-MM-dd"),
            "TIPO_PAGO": self.cmb_tipo_pago.currentData(),
            "FORMA_DE_PAGO": self.cmb_forma_pago.currentData(),
            "PAGO": self.spin_pago.value(),
            "detalles": [
                {"ID_INVENTARIO": i["ID_INVENTARIO"],
                 "CANTIDAD": i["cantidad"],
                 "PRECIO_UNITARIO": round(i["precio"], 4)}
                for i in self._items
            ],
        }
        texto_precio = self.edit_precio.text().strip()
        if texto_precio:
            try:
                precio_manual = parse_decimal(texto_precio)
                if precio_manual < 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(
                    self, "Validación",
                    "El precio manual debe ser un número válido mayor o igual a cero.")
                self.edit_precio.setFocus()
                return
            data["PRECIO"] = round(precio_manual, 2)

        monto_pagar = self._monto_a_pagar()
        if self.spin_pago.value() > monto_pagar + 0.005:
            resp = QMessageBox.question(
                self, "Excedente de pago",
                f"El monto pagado supera el monto a pagar ({monto_pagar:,.2f}). "
                "El excedente quedará como saldo a favor del cliente. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return

        self._set_loading(True)
        api = self.api
        mensaje = ("Venta actualizada correctamente." if self.venta
                   else "Venta registrada correctamente.")
        if self.venta:
            id_venta = self.venta["ID_VENTA"]

            def do():
                api.update_venta(id_venta, data)
        else:
            def do():
                api.create_venta(data)

        def on_result(_):
            self._set_loading(False)
            QMessageBox.information(self, "Venta", mensaje)
            self.accept()

        def on_error(exc):
            self._set_loading(False)
            QMessageBox.critical(self, "Error",
                                 f"No se pudo guardar la venta:\n{self._parse_error(exc)}")

        run_async(do, on_result, on_error)

    @staticmethod
    def _parse_error(e: Exception) -> str:
        try:
            body = e.response.json()
            return body.get("detail", str(e))
        except Exception:
            return str(e)
