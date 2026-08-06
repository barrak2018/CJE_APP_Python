from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QTabWidget, QMainWindow,
    QAbstractItemView, QCheckBox, QApplication, QDialog, QLabel, QGroupBox,
    QToolBar,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction

from dialogs import FormDialog, FieldDef
from api_client import ApiClient
from cliente_search import CatalogoSearchBox, ClienteSearchBox
from venta_dialog import VentaDialog
from gui_workers import run_async, push_busy, pop_busy


def _parse_error_text(e: Exception) -> str:
    try:
        body = e.response.json()
        return body.get("detail", str(e))
    except Exception:
        return str(e)


class ModuleWidget(QWidget):
    AUTO_REFRESH_INTERVAL_MS = 30000

    def __init__(self, api: ApiClient, columns: list[tuple[str, str]],
                 fields: list[FieldDef], pk_field: str,
                 api_list, api_create, api_update, api_delete,
                 parent=None):
        super().__init__(parent)
        self.api = api
        self.columns = columns
        self.fields = fields
        self.pk_field = pk_field
        self.api_list = api_list
        self.api_create = api_create
        self.api_update = api_update
        self.api_delete = api_delete
        self._records = []
        self._refreshing = False
        self._loaded = False
        self._build_ui()
        self._setup_auto_refresh()

    def _setup_auto_refresh(self):
        self.timer = QTimer(self)
        self.timer.setInterval(self.AUTO_REFRESH_INTERVAL_MS)
        self.timer.timeout.connect(self._auto_refresh)
        self.chk_auto.toggled.connect(self._on_auto_refresh_toggled)
        if self.chk_auto.isChecked():
            self.timer.start()

    def _on_auto_refresh_toggled(self, checked: bool):
        if checked:
            self.timer.start()
        else:
            self.timer.stop()

    def _auto_refresh(self):
        if not self.isVisible():
            return
        if QApplication.activeModalWidget() is not None:
            return
        self.refresh(silent=True)

    def _build_ui(self):
        self.root_layout = QVBoxLayout(self)

        self.toolbar = QHBoxLayout()
        self._btn_refresh = QPushButton("Refrescar")
        self._btn_refresh.clicked.connect(self.refresh)
        self.toolbar.addWidget(self._btn_refresh)
        self.chk_auto = QCheckBox("Auto-refresh")
        self.chk_auto.setChecked(True)
        self.toolbar.addWidget(self.chk_auto)
        self.toolbar.addStretch()
        btn_new = QPushButton("Nuevo")
        btn_new.clicked.connect(self._on_new)
        self.toolbar.addWidget(btn_new)
        btn_edit = QPushButton("Editar")
        btn_edit.clicked.connect(self._on_edit)
        self.toolbar.addWidget(btn_edit)
        btn_delete = QPushButton("Eliminar")
        btn_delete.clicked.connect(self._on_delete)
        self.toolbar.addWidget(btn_delete)
        self.root_layout.addLayout(self.toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels([h for h, _ in self.columns])
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.root_layout.addWidget(self.table)

    def ensure_loaded(self):
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def refresh(self, silent: bool = False):
        if self._refreshing:
            return
        self._refreshing = True
        push_busy()
        self._set_refresh_enabled(False)
        self._fetch_async(self._selected_pk(), silent)

    def _set_refresh_enabled(self, enabled: bool):
        btn = getattr(self, "_btn_refresh", None)
        if btn is not None:
            btn.setEnabled(enabled)

    def _fetch_async(self, selected_pk, silent: bool):
        api = self.api

        def on_result(records):
            pop_busy()
            self._set_refresh_enabled(True)
            self._refreshing = False
            self._records = records
            self._populate_table()
            self._restore_selection(selected_pk)

        def on_error(exc):
            pop_busy()
            self._set_refresh_enabled(True)
            self._refreshing = False
            if not silent:
                QMessageBox.critical(self, "Error",
                                     f"No se pudieron cargar los datos:\n{self._parse_error(exc)}")

        run_async(lambda: self.api_list(api), on_result, on_error)

    def _selected_pk(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        rec = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return rec.get(self.pk_field) if rec else None

    def _restore_selection(self, pk):
        if pk is None:
            return
        for row in range(self.table.rowCount()):
            rec = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if rec and rec.get(self.pk_field) == pk:
                self.table.selectRow(row)
                return

    def _populate_table(self):
        old_count = self.table.rowCount()
        new_count = len(self._records)
        self.table.setRowCount(new_count)
        for row_idx, rec in enumerate(self._records):
            for col_idx, (_, key) in enumerate(self.columns):
                val = rec.get(key)
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, rec)
                self.table.setItem(row_idx, col_idx, item)
        if new_count != old_count:
            self.table.resizeColumnsToContents()

    def _selected_record(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Seleccionar",
                                    "Seleccione un registro primero.")
            return None
        row = rows[0].row()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _pk_value(self, record: dict):
        return record[self.pk_field]

    def _prepare_fields(self, data: dict | None = None):
        pass

    def _prepare_async(self, after):
        self._prepare_fields()
        after()

    def _run_mutation(self, api_call, error_prefix="No se pudo guardar"):
        api = self.api
        push_busy()

        def on_result(_):
            pop_busy()
            self.refresh()

        def on_error(exc):
            pop_busy()
            QMessageBox.critical(self, "Error",
                                 f"{error_prefix}:\n{self._parse_error(exc)}")

        run_async(lambda: api_call(api), on_result, on_error)

    def _preview_callback(self):
        return None

    def _on_new(self):
        def open_dialog():
            dlg = FormDialog(f"Nuevo", self.fields, parent=self,
                             preview=self._preview_callback())
            if dlg.exec():
                data = dlg.get_data()
                self._run_mutation(lambda a: self.api_create(a, data),
                                   error_prefix="No se pudo crear")

        self._prepare_async(open_dialog)

    def _on_edit(self):
        rec = self._selected_record()
        if not rec:
            return

        def open_dialog():
            dlg = FormDialog(f"Editar", self.fields, data=rec, parent=self,
                             preview=self._preview_callback())
            if dlg.exec():
                data = dlg.get_data()
                self._run_mutation(
                    lambda a: self.api_update(a, self._pk_value(rec), data),
                    error_prefix="No se pudo actualizar")

        self._prepare_async(open_dialog)

    def _on_delete(self):
        rec = self._selected_record()
        if not rec:
            return
        pk = self._pk_value(rec)
        confirm = QMessageBox.question(
            self, "Confirmar",
            f"Eliminar registro con {self.pk_field}={pk}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._run_mutation(lambda a: self.api_delete(a, pk),
                               error_prefix="No se pudo eliminar")

    @staticmethod
    def _parse_error(e: Exception) -> str:
        return _parse_error_text(e)


class InventarioWidget(ModuleWidget):
    def __init__(self, api: ApiClient, parent=None):
        columns = [
            ("ID", "ID_INVENTARIO"), ("Catálogo", "ID_CATALOGO"),
            ("Producto", "NOMBRE"), ("Marca", "MARCA"),
            ("Presentación", "PRESENTACION"),
            ("Cantidad", "CANTIDA"), ("Lote", "ID_LOTE"),
            ("P. Unitario", "PRECIO_UNITARIO"),
            ("Costo Unit.", "COSTO_UNITARIO"),
            ("Ganancia %", "GANACIA"), ("P. Venta", "PRECIO_VENTA"),
        ]
        fields = [
            FieldDef("ID_CATALOGO", "Producto (Catálogo)", "search",
                     required=True, search_cls=CatalogoSearchBox,
                     search_key="ID_CATALOGO"),
            FieldDef("CANTIDA", "Cantidad", "int", required=True, minimum=1),
            FieldDef("ID_LOTE", "Lote (Flete)", "char", required=True,
                     options=[]),
            FieldDef("PRECIO_UNITARIO", "Precio Unitario", "float",
                     required=True, minimum=0.01),
            FieldDef("GANACIA", "Ganancia (%)", "float",
                     required=True, minimum=0.1, maximum=99.9),
        ]
        super().__init__(
            api=api, columns=columns, fields=fields,
            pk_field="ID_INVENTARIO",
            api_list=lambda a: a.get_inventario(),
            api_create=lambda a, d: a.create_inventario(d),
            api_update=lambda a, p, d: a.update_inventario(p, d),
            api_delete=lambda a, p: a.delete_inventario(p),
            parent=parent,
        )

    def _prepare_async(self, after):
        api = self.api
        push_busy()

        def fetch():
            catalogo = api.get_catalogo()
            fletes = api.get_fletes()
            return catalogo, fletes

        def on_result(data):
            pop_busy()
            catalogo_items, fletes = data
            self._flete_total = {
                f["ID_FLETE"]: float(f.get("TOTAL_FLETE") or 0.0)
                for f in fletes}
            fletes_ordenados = sorted(
                fletes, key=lambda f: str(f.get("FECHA") or ""), reverse=True)
            opts_flete = [
                (f["ID_FLETE"], f'{f["FECHA"]} {f["PROVEEDOR"]} ({f["VIA"]})')
                for f in fletes_ordenados]
            for f in self.fields:
                if f.name == "ID_CATALOGO":
                    f.search_items = catalogo_items
                elif f.name == "ID_LOTE":
                    f.options = opts_flete
            after()

        def on_error(exc):
            pop_busy()
            QMessageBox.warning(
                self, "Datos",
                f"No se pudieron cargar los datos de referencia:\n{self._parse_error(exc)}")

        run_async(fetch, on_result, on_error)

    def _fetch_async(self, selected_pk, silent: bool):
        api = self.api

        def fetch():
            catalogo = api.get_catalogo()
            inventario = api.get_inventario()
            return catalogo, inventario

        def on_result(data):
            pop_busy()
            self._set_refresh_enabled(True)
            self._refreshing = False
            catalogo, inventario = data
            self._catalogo = {c["ID_CATALOGO"]: c for c in catalogo}
            self._records = inventario
            self._populate_table()
            self._restore_selection(selected_pk)

        def on_error(exc):
            pop_busy()
            self._set_refresh_enabled(True)
            self._refreshing = False
            if not silent:
                QMessageBox.critical(self, "Error",
                                     f"No se pudieron cargar los datos:\n{self._parse_error(exc)}")

        run_async(fetch, on_result, on_error)

    def _populate_table(self):
        for rec in self._records:
            cat = self._catalogo.get(rec.get("ID_CATALOGO")) or {}
            rec["NOMBRE"] = cat.get("NOMBRE") or ""
            rec["MARCA"] = cat.get("MARCA") or ""
            rec["PRESENTACION"] = cat.get("PRESENTACION") or ""
        super()._populate_table()

    def _preview_callback(self):
        flete_total = self._flete_total

        def preview(data: dict):
            id_lote = data.get("ID_LOTE")
            pu = data.get("PRECIO_UNITARIO")
            ganancia = data.get("GANACIA")
            if id_lote is None:
                return "Seleccione el lote para calcular el precio de venta."
            if pu is None or ganancia is None or ganancia <= 0 or ganancia >= 100:
                return ""
            costo = pu + flete_total.get(id_lote, 0.0)
            pv = costo / (1 - ganancia / 100.0)
            return f"Precio de venta estimado: ${pv:,.2f}"
        return preview


class FleteWidget(ModuleWidget):
    def __init__(self, api: ApiClient, parent=None):
        columns = [
            ("ID", "ID_FLETE"), ("Fecha", "FECHA"),
            ("Proveedor", "PROVEEDOR"),
            ("Shipping", "SHEPING"), ("Courier", "NOMBRE_CURRIER"),
            ("Vía", "VIA"), ("P. Courier", "PRECIO_CURRIER"),
            ("Cantidad", "CANTIDAD"), ("Total Flete", "TOTAL_FLETE"),
        ]
        fields = [
            FieldDef("FECHA", "Fecha", "date", required=True),
            FieldDef("PROVEEDOR", "Proveedor", "str", required=True),
            FieldDef("SHEPING", "Shipping ($)", "float", minimum=0),
            FieldDef("NOMBRE_CURRIER", "Nombre del Courier", "str",
                     required=True),
            FieldDef("VIA", "Vía", "char", required=True,
                     options=[("M", "Marítimo"), ("A", "Aéreo")]),
            FieldDef("PRECIO_CURRIER", "Precio Courier ($)", "float",
                     minimum=0),
            FieldDef("CANTIDAD", "Cantidad", "int", required=True,
                     minimum=1),
        ]
        super().__init__(
            api=api, columns=columns, fields=fields,
            pk_field="ID_FLETE",
            api_list=lambda a: a.get_fletes(),
            api_create=lambda a, d: a.create_flete(d),
            api_update=lambda a, p, d: a.update_flete(p, d),
            api_delete=lambda a, p: a.delete_flete(p),
            parent=parent,
        )


CLIENTE_FIELDS = [
    FieldDef("CEDULA", "Cédula", "int", required=True, minimum=1),
    FieldDef("NOMBRE", "Nombre", "str", required=True),
    FieldDef("CORREO", "Correo", "str"),
    FieldDef("TELEFONO", "Teléfono", "str"),
    FieldDef("SALDO", "Saldo", "float", minimum=-999999999),
]


class ClienteDetalleDialog(QDialog):
    """Ventana de detalle del cliente: datos guardados, compras, abonos y resumen."""

    def __init__(self, api: ApiClient, cedula: int, parent=None):
        super().__init__(parent)
        self.api = api
        self.cedula = cedula
        self.setWindowTitle(f"Detalle del Cliente {cedula}")
        self.setMinimumSize(760, 520)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.lbl_info)

        tables_row = QHBoxLayout()
        self.table_compras = self._crear_tabla(
            ["ID", "Fecha", "Tipo", "Forma", "Precio", "Pagado"])
        self.table_abonos = self._crear_tabla(["ID", "Fecha", "Cantidad"])
        self.table_compras.cellDoubleClicked.connect(
            self._on_compras_double_click)
        tables_row.addWidget(self._agrupar("Compras", self.table_compras), 3)
        tables_row.addWidget(self._agrupar("Abonos", self.table_abonos), 2)
        lay.addLayout(tables_row, 1)

        self.lbl_resumen = QLabel()
        self.lbl_resumen.setWordWrap(True)
        lay.addWidget(self.lbl_resumen)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self._on_editar)
        buttons_row.addWidget(btn_editar)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        buttons_row.addWidget(btn_cerrar)
        lay.addLayout(buttons_row)

    @staticmethod
    def _crear_tabla(columnas):
        tbl = QTableWidget()
        tbl.setColumnCount(len(columnas))
        tbl.setHorizontalHeaderLabels(columnas)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setStretchLastSection(True)
        return tbl

    def _agrupar(self, titulo, tbl):
        group = QGroupBox(titulo)
        vbox = QVBoxLayout(group)
        vbox.addWidget(tbl)
        return group

    def _rellenar(self, tbl, filas):
        tbl.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for col, val in enumerate(fila):
                tbl.setItem(i, col, QTableWidgetItem(str(val)))
        tbl.resizeColumnsToContents()

    def _load(self):
        cedula = self.cedula
        api = self.api
        self.lbl_info.setText("Cargando datos…")
        self.table_compras.setRowCount(0)
        self.table_abonos.setRowCount(0)
        self.lbl_resumen.setText("")

        def fetch():
            cliente = api.get_cliente(cedula)
            compras, err_compras = [], None
            abonos, err_abonos = [], None
            try:
                compras = api.get_ventas(cedula)
            except Exception as e:
                err_compras = e
            try:
                abonos = api.get_abonos(cedula)
            except Exception as e:
                err_abonos = e
            return cliente, compras, abonos, err_compras, err_abonos

        def on_result(data):
            cliente, compras, abonos, err_compras, err_abonos = data
            if err_compras is not None:
                QMessageBox.warning(self, "Compras",
                                    f"No se pudieron cargar las compras:\n{self._parse_error(err_compras)}")
            if err_abonos is not None:
                QMessageBox.warning(self, "Abonos",
                                    f"No se pudieron cargar los abonos:\n{self._parse_error(err_abonos)}")
            self._render(cliente, compras, abonos)

        def on_error(exc):
            QMessageBox.critical(self, "Error",
                                 f"No se pudo cargar el cliente:\n{self._parse_error(exc)}")

        run_async(fetch, on_result, on_error)

    def _render(self, cliente, compras, abonos):
        nombre = cliente.get("NOMBRE") or ""
        correo = cliente.get("CORREO") or "-"
        telefono = cliente.get("TELEFONO") or "-"
        saldo = float(cliente.get("SALDO") or 0.0)
        self.lbl_info.setText(
            f"<b>{self.cedula} - {nombre}</b><br>"
            f"Correo: {correo} &nbsp;&nbsp; Teléfono: {telefono}")

        total_comprado = 0.0
        pagado_ventas = 0.0
        for v in compras:
            total_comprado += float(v.get("PRECIO") or 0.0)
            pagado_ventas += float(v.get("PAGO") or 0.0)

        self._rellenar(self.table_compras, [
            (v.get("ID_VENTA"), v.get("FECHA") or "-",
             v.get("TIPO_PAGO") or "-", v.get("FORMA_DE_PAGO") or "-",
             f"${v.get('PRECIO', 0):,.2f}", f"${v.get('PAGO', 0):,.2f}")
            for v in compras
        ])
        self._rellenar(self.table_abonos, [
            (a.get("ID_ABONO"), a.get("FECHA") or "-",
             f"${a.get('CANTIDAD', 0):,.2f}")
            for a in abonos
        ])

        total_abonado = sum(float(a.get("CANTIDAD") or 0.0) for a in abonos)
        dinero_pagado = pagado_ventas + total_abonado
        self.lbl_resumen.setText(
            f"Total comprado: <b>$ {total_comprado:,.2f}</b>   |   "
            f"Pagado en ventas: <b>$ {pagado_ventas:,.2f}</b>   |   "
            f"Total abonado: <b>$ {total_abonado:,.2f}</b>   |   "
            f"<b>Dinero pagado: $ {dinero_pagado:,.2f}</b>   |   "
            f"Saldo actual: <b>$ {saldo:,.2f}</b>")

    def _on_editar(self):
        api = self.api
        cedula = self.cedula

        def on_cliente(cliente):
            dlg = FormDialog("Editar Cliente", list(CLIENTE_FIELDS),
                             data=cliente, parent=self)
            if not dlg.exec():
                return
            data = dlg.get_data()
            push_busy()

            def on_save_result(_):
                pop_busy()
                if data.get("CEDULA") and data["CEDULA"] != cedula:
                    self.cedula = data["CEDULA"]
                    self.setWindowTitle(f"Detalle del Cliente {self.cedula}")
                self._load()

            def on_save_error(exc):
                pop_busy()
                err = self._parse_error(exc)
                QMessageBox.critical(self, "Error", f"No se pudo editar:\n{err}")

            run_async(lambda: api.update_cliente(cedula, data),
                      on_save_result, on_save_error)

        def on_error(exc):
            QMessageBox.critical(self, "Error",
                                 f"No se pudo cargar el cliente:\n{self._parse_error(exc)}")

        run_async(lambda: api.get_cliente(cedula), on_cliente, on_error)

    def _on_compras_double_click(self, row: int, col: int):
        item = self.table_compras.item(row, 0)
        if item is None:
            return
        try:
            id_venta = int(item.text())
        except ValueError:
            return
        _abrir_detalle_venta(self.api, id_venta, self)

    @staticmethod
    def _parse_error(e: Exception) -> str:
        return _parse_error_text(e)


class ClienteWidget(ModuleWidget):
    def __init__(self, api: ApiClient, parent=None):
        columns = [
            ("Cédula", "CEDULA"), ("Nombre", "NOMBRE"),
            ("Correo", "CORREO"), ("Teléfono", "TELEFONO"),
            ("Saldo", "SALDO"),
        ]
        fields = list(CLIENTE_FIELDS)
        super().__init__(
            api=api, columns=columns, fields=fields,
            pk_field="CEDULA",
            api_list=lambda a: a.get_clientes(),
            api_create=lambda a, d: a.create_cliente(d),
            api_update=lambda a, p, d: a.update_cliente(p, d),
            api_delete=lambda a, p: a.delete_cliente(p),
            parent=parent,
        )

    def _build_ui(self):
        super()._build_ui()

        self.search_cliente = ClienteSearchBox()
        search_row = QHBoxLayout()
        search_row.addWidget(self.search_cliente, 1)
        btn = QPushButton("Ver Detalle")
        btn.clicked.connect(self._on_ver_detalle)
        search_row.addWidget(btn)
        self.root_layout.insertLayout(0, search_row)

        btn_tool = QPushButton("Ver Detalle")
        btn_tool.clicked.connect(self._on_ver_detalle)
        self.toolbar.insertWidget(self.toolbar.count() - 1, btn_tool)

        self.search_cliente.clienteSeleccionado.connect(self._on_buscar_cliente)

    def _fetch_async(self, selected_pk, silent: bool):
        api = self.api

        def on_result(clientes):
            pop_busy()
            self._set_refresh_enabled(True)
            self._refreshing = False
            self._records = clientes
            self._populate_table()
            self._restore_selection(selected_pk)
            self.search_cliente.setClientes(clientes)

        def on_error(exc):
            pop_busy()
            self._set_refresh_enabled(True)
            self._refreshing = False
            if not silent:
                QMessageBox.critical(self, "Error",
                                     f"No se pudieron cargar los datos:\n{self._parse_error(exc)}")

        run_async(lambda: api.get_clientes(), on_result, on_error)

    def _on_buscar_cliente(self, cliente: dict):
        if not cliente:
            return
        self._ver_detalle(cliente)
        self.search_cliente.clear()

    def _on_ver_detalle(self):
        rec = self._selected_record()
        if rec:
            self._ver_detalle(rec)

    def _ver_detalle(self, cliente: dict):
        dlg = ClienteDetalleDialog(self.api, cliente["CEDULA"], parent=self)
        dlg.exec()


class CatalogoWidget(ModuleWidget):
    def __init__(self, api: ApiClient, parent=None):
        columns = [
            ("ID", "ID_CATALOGO"), ("Nombre", "NOMBRE"),
            ("Marca", "MARCA"), ("Presentación", "PRESENTACION"),
        ]
        fields = [
            FieldDef("NOMBRE", "Nombre", "str", required=True),
            FieldDef("MARCA", "Marca", "str"),
            FieldDef("PRESENTACION", "Presentación", "str"),
        ]
        super().__init__(
            api=api, columns=columns, fields=fields,
            pk_field="ID_CATALOGO",
            api_list=lambda a: a.get_catalogo(),
            api_create=lambda a, d: a.create_catalogo(d),
            api_update=lambda a, p, d: a.update_catalogo(p, d),
            api_delete=lambda a, p: a.delete_catalogo(p),
            parent=parent,
        )


class VentasWidget(ModuleWidget):
    def __init__(self, api: ApiClient, parent=None):
        columns = [
            ("ID", "ID_VENTA"), ("Fecha", "FECHA"),
            ("Cédula", "CEDULA"), ("Cliente", "NOMBRE_CLIENTE"),
            ("Precio", "PRECIO"), ("Tipo", "TIPO_PAGO"),
            ("Forma", "FORMA_DE_PAGO"), ("Pago", "PAGO"),
        ]
        super().__init__(
            api=api, columns=columns, fields=[],
            pk_field="ID_VENTA",
            api_list=lambda a: a.get_ventas(),
            api_create=None,
            api_update=None,
            api_delete=lambda a, p: a.delete_venta(p),
            parent=parent,
        )

    def _build_ui(self):
        super()._build_ui()
        btn_detail = QPushButton("Ver Detalle")
        btn_detail.clicked.connect(self._on_ver_detalle)
        self.toolbar.insertWidget(self.toolbar.count() - 2, btn_detail)

    def _on_new(self):
        dlg = VentaDialog(self.api, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_ver_detalle(self):
        rec = self._selected_record()
        if rec:
            self._ver_detalle(rec)

    def _on_editar(self):
        rec = self._selected_record()
        if not rec:
            return
        id_venta = rec["ID_VENTA"]
        push_busy()
        api = self.api

        def on_venta(venta):
            pop_busy()
            dlg = VentaDialog(self.api, venta=venta, parent=self)
            if dlg.exec():
                self.refresh()

        def on_error(exc):
            pop_busy()
            QMessageBox.critical(self, "Error",
                                 f"No se pudo cargar la venta:\n{self._parse_error(exc)}")

        run_async(lambda: api.get_venta(id_venta), on_venta, on_error)

    def _ver_detalle(self, rec: dict):
        _abrir_detalle_venta(self.api, rec["ID_VENTA"], self)

    def _on_delete(self):
        rec = self._selected_record()
        if not rec:
            return
        pk = rec[self.pk_field]
        confirm = QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar la venta #{pk}?\nSe revertirá el stock y el saldo del cliente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._run_mutation(lambda a: self.api_delete(a, pk),
                               error_prefix="No se pudo eliminar")


def _abrir_detalle_venta(api, id_venta: int, parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Venta #{id_venta}")
    dlg.setMinimumSize(520, 360)
    lay = QVBoxLayout(dlg)

    lbl_info = QLabel("Cargando venta…")
    lbl_info.setWordWrap(True)
    lay.addWidget(lbl_info)

    tbl = QTableWidget()
    tbl.setColumnCount(4)
    tbl.setHorizontalHeaderLabels(
        ["Producto", "P. Unitario", "Cantidad", "Subtotal"])
    tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tbl.horizontalHeader().setStretchLastSection(True)
    lay.addWidget(tbl)

    btn = QPushButton("Cerrar")
    btn.clicked.connect(dlg.accept)
    lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignRight)

    def on_result(venta):
        info = (
            f"Fecha: {venta.get('FECHA') or '-'}\n"
            f"Cliente: {venta.get('CEDULA')} - {venta.get('NOMBRE_CLIENTE') or ''}\n"
            f"Tipo de pago: {venta.get('TIPO_PAGO')}   "
            f"Forma: {venta.get('FORMA_DE_PAGO')}\n"
            f"Precio total: ${venta.get('PRECIO', 0):,.2f}   "
            f"Pagado: ${venta.get('PAGO', 0):,.2f}"
        )
        lbl_info.setText(info)
        detalles = venta.get("detalles") or []
        tbl.setRowCount(len(detalles))
        for i, det in enumerate(detalles):
            vals = [
                det.get("NOMBRE_PRODUCTO") or f'Inventario #{det["ID_INVENTARIO"]}',
                f"${det.get('PRECIO_UNITARIO', 0):,.2f}",
                str(det.get("CANTIDAD", 0)),
                f"${det.get('SUBTOTAL', 0):,.2f}",
            ]
            for col, val in enumerate(vals):
                tbl.setItem(i, col, QTableWidgetItem(val))
        tbl.resizeColumnsToContents()

    def on_error(exc):
        lbl_info.setText(f"No se pudo cargar la venta:\n{_parse_error_text(exc)}")

    run_async(lambda: api.get_venta(id_venta), on_result, on_error)
    dlg.exec()


class AbonosWidget(ModuleWidget):
    """Abonos: pagos del cliente hacia su deuda (reduce el SALDO)."""

    def __init__(self, api: ApiClient, parent=None):
        columns = [
            ("ID", "ID_ABONO"), ("Fecha", "FECHA"),
            ("Cédula", "CEDULA"), ("Cliente", "NOMBRE_CLIENTE"),
            ("Cantidad", "CANTIDAD"),
        ]
        fields = [
            FieldDef("CEDULA", "Cliente", "search", required=True,
                     search_cls=ClienteSearchBox, search_key="CEDULA",
                     search_info=self._info_deuda_cliente),
            FieldDef("FECHA", "Fecha", "date"),
            FieldDef("CANTIDAD", "Monto del abono", "float", required=True,
                     minimum=0.01, maximum=999999999),
        ]
        super().__init__(
            api=api, columns=columns, fields=fields,
            pk_field="ID_ABONO",
            api_list=lambda a: a.get_abonos(),
            api_create=lambda a, d: a.create_abono(d),
            api_update=lambda a, p, d: a.update_abono(p, d),
            api_delete=lambda a, p: a.delete_abono(p),
            parent=parent,
        )

    def _prepare_async(self, after):
        api = self.api
        push_busy()

        def on_result(clientes):
            pop_busy()
            for f in self.fields:
                if f.name == "CEDULA":
                    f.search_items = clientes
            after()

        def on_error(exc):
            pop_busy()
            QMessageBox.warning(self, "Datos",
                                f"No se pudieron cargar los clientes:\n{self._parse_error(exc)}")

        run_async(lambda: api.get_clientes(), on_result, on_error)

    @staticmethod
    def _info_deuda_cliente(cliente: dict) -> str:
        """Texto orientativo con la deuda/saldo actual del cliente."""
        try:
            saldo = float(cliente.get("SALDO") or 0.0)
        except (TypeError, ValueError):
            saldo = 0.0
        if saldo > 0:
            return f"Deuda actual del cliente: $ {saldo:,.2f}"
        if saldo < 0:
            return f"Sin deuda; el cliente tiene saldo a favor de $ {abs(saldo):,.2f}"
        return "Deuda actual del cliente: $ 0.00"


class MainWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, api: ApiClient = None, api_url: str = None):
        super().__init__()
        self.api = api if api is not None else ApiClient(api_url)
        self.setWindowTitle("CJE Perfumes - Gestión")
        self.setMinimumSize(1000, 600)
        self._build_toolbar()
        self._build_ui()

    def _build_toolbar(self):
        self.toolbar = QToolBar("Principal")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.action_cerrar_sesion = QAction("Cerrar sesión", self)
        self.action_cerrar_sesion.setToolTip(
            "Olvidar credenciales guardadas y salir del programa")
        self.action_cerrar_sesion.triggered.connect(self._on_cerrar_sesion)
        self.toolbar.addAction(self.action_cerrar_sesion)
        self.toolbar.addSeparator()

    def _on_cerrar_sesion(self):
        respuesta = QMessageBox.question(
            self, "Cerrar sesión",
            "Se olvidarán las credenciales guardadas y el programa se cerrará.\n"
            "¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.tabs.addTab(FleteWidget(self.api), "Fletes")
        self.tabs.addTab(CatalogoWidget(self.api), "Catálogo")
        self.tabs.addTab(InventarioWidget(self.api), "Inventario")
        self.tabs.addTab(ClienteWidget(self.api), "Clientes")
        self.tabs.addTab(VentasWidget(self.api), "Ventas")
        self.tabs.addTab(AbonosWidget(self.api), "Abonos")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.statusBar().showMessage("Conectado a " + self.api.base_url)
        self._on_tab_changed(self.tabs.currentIndex())

    def _on_tab_changed(self, index: int):
        widget = self.tabs.widget(index)
        if widget is not None and hasattr(widget, "ensure_loaded"):
            widget.ensure_loaded()
