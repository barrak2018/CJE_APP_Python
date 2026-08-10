from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget, QLineEdit, QListView, QVBoxLayout, QFrame, QAbstractItemView,
    QApplication,
)


class _SearchLineEdit(QLineEdit):
    keyPressed = Signal(object)

    def keyPressEvent(self, event):
        self.keyPressed.emit(event)
        if not event.isAccepted():
            super().keyPressEvent(event)


class SearchBox(QWidget):
    """Barra de búsqueda genérica con desplegable filtrable.

    Widget autocontenido y reutilizable. No llama a la API: quien lo use debe
    cargar los ítems con setItems(lista). Emite itemSelected(dict|None) al
    elegir una opción del desplegable o al limpiar la selección.

    Las subclases definen placeholder(), tooltip_text() y los hooks
    _display/_tooltip/_haystack para personalizar la presentación y el filtro.
    """

    itemSelected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._resultados = []
        self._selected = None
        self._setting_text = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.edit = _SearchLineEdit()
        self.edit.setPlaceholderText(self.placeholder())
        self.edit.setClearButtonEnabled(True)
        self.edit.setMinimumHeight(30)
        self.edit.setToolTip(self.tooltip_text())
        layout.addWidget(self.edit)

        self.edit.textChanged.connect(self._on_text_changed)
        self.edit.keyPressed.connect(self._on_key_press)
        self._popup = QListView(self)
        self._popup.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self._popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._popup.setFrameShape(QFrame.Shape.StyledPanel)
        self._popup.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._popup.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._popup.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._model = QStandardItemModel(self._popup)
        self._popup.setModel(self._model)
        self._popup.clicked.connect(self._on_row_clicked)
        self.edit.editingFinished.connect(self._on_edit_finished)

    # ── Ganchos para subclases ────────────────────────────
    def placeholder(self):
        return ""

    def tooltip_text(self):
        return ""

    def _display(self, item):
        return ""

    def _tooltip(self, item):
        return ""

    def _haystack(self, item):
        return ""

    def _permite(self, item):
        """True si el ítem puede aparecer en el desplegable. Por defecto todos."""
        return True

    def _notify(self, item):
        self.itemSelected.emit(item)

    # ── Datos ─────────────────────────────────────────────
    def setItems(self, items):
        """Reemplaza la lista de ítems disponibles y limpia la selección."""
        self._items = list(items or [])
        self._selected = None
        self._resultados = []
        self._hide_popup()
        self.edit.clear()

    def items(self):
        return list(self._items)

    def clear(self):
        """Limpia la selección y el texto del buscador."""
        self._selected = None
        self._resultados = []
        self._hide_popup()
        self.edit.clear()
        self._notify(None)

    def item(self):
        return self._selected

    def setItem(self, item):
        """Selecciona programáticamente un ítem (para precargar ediciones)."""
        if not item:
            return
        self._setting_text = True
        try:
            self.edit.setText(self._display(item))
        finally:
            self._setting_text = False
        self._selected = item
        self._hide_popup()
        self._notify(item)

    def select_result(self, indice):
        """Selecciona el resultado en la posición indice de las coincidencias."""
        if 0 <= indice < len(self._resultados):
            self.setItem(self._resultados[indice])

    # ── Filtrado ──────────────────────────────────────────
    def _on_text_changed(self, texto):
        if self._setting_text:
            return
        if self._selected is not None:
            self._selected = None
            self._notify(None)
        self._refrescar_popup()

    def _coincidencias(self):
        q = self.edit.text().strip()
        if not q:
            return []
        tokens = [t.lower() for t in q.split()]
        coinciden = []
        for it in self._items:
            if not self._permite(it):
                continue
            haystack = self._haystack(it)
            if all(t in haystack for t in tokens):
                coinciden.append(it)
        return coinciden

    def _refrescar_popup(self):
        self._resultados = self._coincidencias()
        self._model.clear()
        if not self._resultados:
            self._hide_popup()
            return
        for it in self._resultados[:20]:
            item = QStandardItem(self._display(it))
            item.setData(it, Qt.ItemDataRole.UserRole)
            item.setToolTip(self._tooltip(it))
            self._model.appendRow(item)
        self._show_popup()

    def _mostrar_todos(self):
        self._resultados = [it for it in self._items
                            if self._permite(it)][:20]
        self._model.clear()
        if not self._resultados:
            self._hide_popup()
            return
        for it in self._resultados:
            item = QStandardItem(self._display(it))
            item.setData(it, Qt.ItemDataRole.UserRole)
            item.setToolTip(self._tooltip(it))
            self._model.appendRow(item)
        self._show_popup()

    def _show_popup(self):
        if self._model.rowCount() == 0:
            self._hide_popup()
            return
        tl = self.edit.rect().topLeft()
        bl = self.edit.rect().bottomLeft()
        x = self.edit.mapToGlobal(tl).x()
        y = self.edit.mapToGlobal(bl).y() + 1
        self._popup.setFixedWidth(self.edit.width())
        self._popup.setFixedHeight(self._popup_height())
        self._popup.move(x, y)
        self._popup.setCurrentIndex(self._model.index(0, 0))
        self._popup.show()

    def _popup_height(self):
        n = self._model.rowCount()
        if n == 0:
            return 20
        filas = min(n, 8)
        total = 0
        for r in range(filas):
            total += self._popup.sizeHintForIndex(
                self._model.index(r, 0)).height()
        return total + 4

    def _hide_popup(self):
        try:
            if self._popup.isVisible():
                self._popup.hide()
        except RuntimeError:
            pass

    def _on_edit_finished(self):
        """El QLineEdit pierde el foco. Se cierra el desplegable salvo que el
        foco haya ido al propio popup (clic sobre una opción), que debe poder
        completarse, o que se haya perdido por mostrar el popup."""
        fw = QApplication.focusWidget()
        if fw is None or self._popup.isAncestorOf(fw):
            return
        self._hide_popup()

    # ── Selección ─────────────────────────────────────────
    def _on_row_clicked(self, index):
        item = self._model.itemFromIndex(index)
        if item is not None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                self.setItem(data)

    def _seleccionar_actual(self):
        index = self._popup.currentIndex()
        if not index.isValid():
            return False
        item = self._model.itemFromIndex(index)
        if item is None:
            return False
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return False
        self.setItem(data)
        return True

    # ── Teclado ───────────────────────────────────────────
    def _on_key_press(self, event):
        key = event.key()
        if key == Qt.Key.Key_Down:
            if self._popup.isVisible():
                self._popup.setCurrentIndex(self._popup.currentIndex().sibling(
                    self._popup.currentIndex().row() + 1, 0))
            elif self.edit.text().strip():
                self._refrescar_popup()
            else:
                self._mostrar_todos()
            event.accept()
        elif key == Qt.Key.Key_Up:
            if self._popup.isVisible():
                self._popup.setCurrentIndex(self._popup.currentIndex().sibling(
                    self._popup.currentIndex().row() - 1, 0))
            event.accept()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._popup.isVisible():
                self._seleccionar_actual()
                event.accept()
            else:
                event.ignore()
        elif key == Qt.Key.Key_Escape:
            self._hide_popup()
            event.accept()
        else:
            event.ignore()

    def hideEvent(self, event):
        self._hide_popup()
        super().hideEvent(event)


class ClienteSearchBox(SearchBox):
    """Barra de búsqueda de clientes: filtra por cédula, nombre o correo.

    Conserva la API original (setClientes/clientes/cliente/cedula/setCliente)
    además de la genérica de SearchBox. Emite clienteSeleccionado(dict|None).
    """

    clienteSeleccionado = Signal(object)

    def placeholder(self):
        return "Buscar por cédula, nombre o correo…"

    def tooltip_text(self):
        return ("Escriba la cédula, el nombre o el correo del cliente y elija "
                "una opción del desplegable.")

    def setClientes(self, clientes):
        self.setItems(clientes)

    def clientes(self):
        return self.items()

    def cliente(self):
        return self.item()

    def cedula(self):
        c = self._selected
        return c["CEDULA"] if c else None

    def setCliente(self, cliente):
        self.setItem(cliente)

    @staticmethod
    def _display(cliente):
        cedula = cliente.get("CEDULA")
        nombre = cliente.get("NOMBRE") or ""
        return f"{cedula} - {nombre}"

    @staticmethod
    def _tooltip(cliente):
        partes = []
        for clave in ("CORREO", "TELEFONO", "SALDO"):
            valor = cliente.get(clave)
            if valor not in (None, ""):
                partes.append(f"{clave}: {valor}")
        return "\n".join(partes)

    def _haystack(self, cliente):
        return " ".join([
            str(cliente.get("CEDULA") or ""),
            cliente.get("NOMBRE") or "",
            cliente.get("CORREO") or "",
            cliente.get("TELEFONO") or "",
        ]).lower()

    def _notify(self, item):
        self.itemSelected.emit(item)
        self.clienteSeleccionado.emit(item)


class ProductoVentaSearchBox(SearchBox):
    """Barra de búsqueda de productos para el formulario de venta.

    Filtra por nombre, marca o presentación. El desplegable muestra en dos
    líneas `NOMBRE` y `MARCA · PRESENTACIÓN · $precio · (stock N)`, sin el ID.
    Emite productoSeleccionado(dict|None).
    """

    productoSeleccionado = Signal(object)

    def placeholder(self):
        return "Buscar por nombre, marca o presentación…"

    def tooltip_text(self):
        return ("Escriba el nombre, la marca o la presentación del producto "
                "y elija una opción del desplegable.")

    def setProductos(self, productos):
        self.setItems(productos)

    def productos(self):
        return self.items()

    def producto(self):
        return self.item()

    def setProducto(self, producto):
        self.setItem(producto)

    def id_inventario(self):
        p = self._selected
        return p["ID_INVENTARIO"] if p else None

    @staticmethod
    def _permite(producto):
        stock = producto.get("stock")
        if stock is None:
            return True
        try:
            return float(stock) > 0
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _display(producto):
        nombre = producto.get("nombre") or ""
        linea1 = nombre
        marca = (producto.get("MARCA") or "").strip()
        presentacion = (producto.get("PRESENTACION") or "").strip()
        precio = producto.get("precio")
        stock = producto.get("stock")
        partes = [p for p in (marca, presentacion) if p]
        if precio is not None:
            partes.append(f"${float(precio):,.2f}")
        if stock is not None:
            partes.append(f"(stock {int(stock)})")
        if partes:
            return f"{linea1}\n" + " · ".join(partes)
        return linea1

    @staticmethod
    def _tooltip(producto):
        partes = []
        for clave, etiqueta in (("nombre", "Producto"), ("MARCA", "Marca"),
                                ("PRESENTACION", "Presentación"),
                                ("precio", "Precio"), ("stock", "Stock")):
            valor = producto.get(clave)
            if valor not in (None, ""):
                partes.append(f"{etiqueta}: {valor}")
        return "\n".join(partes)

    def _haystack(self, producto):
        return " ".join([
            producto.get("nombre") or "",
            producto.get("MARCA") or "",
            producto.get("PRESENTACION") or "",
        ]).lower()

    def _notify(self, item):
        self.itemSelected.emit(item)
        self.productoSeleccionado.emit(item)


class CatalogoSearchBox(SearchBox):
    """Barra de búsqueda de productos del catálogo.

    Filtra por nombre, marca o presentación. El desplegable muestra en dos
    líneas `ID - NOMBRE` y `MARCA · PRESENTACIÓN`. Emite
    catalogoSeleccionado(dict|None).
    """

    catalogoSeleccionado = Signal(object)

    def placeholder(self):
        return "Buscar por nombre, marca o presentación…"

    def tooltip_text(self):
        return ("Escriba el nombre, la marca o la presentación del producto "
                "y elija una opción del desplegable.")

    def setCatalogos(self, catalogos):
        self.setItems(catalogos)

    def catalogos(self):
        return self.items()

    def catalogo(self):
        return self.item()

    def setCatalogo(self, catalogo):
        self.setItem(catalogo)

    def id_catalogo(self):
        c = self._selected
        return c["ID_CATALOGO"] if c else None

    @staticmethod
    def _display(catalogo):
        pid = catalogo.get("ID_CATALOGO")
        nombre = catalogo.get("NOMBRE") or ""
        linea1 = f"{pid} - {nombre}"
        marca = (catalogo.get("MARCA") or "").strip()
        presentacion = (catalogo.get("PRESENTACION") or "").strip()
        if marca or presentacion:
            linea2 = " · ".join(p for p in (marca, presentacion) if p)
            return f"{linea1}\n{linea2}"
        return linea1

    @staticmethod
    def _tooltip(catalogo):
        partes = []
        for clave in ("ID_CATALOGO", "NOMBRE", "MARCA", "PRESENTACION"):
            valor = catalogo.get(clave)
            if valor not in (None, ""):
                partes.append(f"{clave}: {valor}")
        return "\n".join(partes)

    def _haystack(self, catalogo):
        return " ".join([
            str(catalogo.get("ID_CATALOGO") or ""),
            catalogo.get("NOMBRE") or "",
            catalogo.get("MARCA") or "",
            catalogo.get("PRESENTACION") or "",
        ]).lower()

    def _notify(self, item):
        self.itemSelected.emit(item)
        self.catalogoSeleccionado.emit(item)
