# Bugs y Soluciones — CJE Perfumes

Registro de los problemas encontrados a lo largo del proyecto, su **causa raíz**
y la **solución aplicada**, con las referencias al código actual.

Cada entrada sigue el mismo formato:

1. **Síntoma** — lo que el usuario o las pruebas observaban.
2. **Causa raíz** — por qué ocurría realmente.
3. **Solución** — qué se hizo para corregirlo.
4. **Verificación** — cómo se comprobó que quedó resuelto.

> Las referencias `archivo:línea` apuntan al estado actual del código. Como el
> proyecto no tiene historial git, algunas fechas y detalles de las primeras fases
> se reconstruyen a partir de los comentarios del código y de la documentación.

---

## Índice

**Interfaz GUI (cje_gui)**
1. [Resultados perdidos en operaciones asíncronas](#1-resultados-perdidos-en-operaciones-asíncronas)
2. [Cursor de ocupado que nunca se restauraba](#2-cursor-de-ocupado-que-nunca-se-restauraba)
3. [Desplegable de búsqueda no clickeable en diálogos modales](#3-desplegable-de-búsqueda-no-clickeable-en-diálogos-modales)
4. [Desplegable que se cerraba apenas se abría](#4-desplegable-que-se-cerraba-apenas-se-abría)
5. [Error al ocultar el desplegable tras destruirse el widget](#5-error-al-ocultar-el-desplegable-tras-destruirse-el-widget)
6. [Decimales con coma/punto según el locale de Windows](#6-decimales-con-comapunto-según-el-locale-de-windows)
7. [Editar una venta rechazaba el stock de la propia venta](#7-editar-una-venta-rechazaba-el-stock-de-la-propia-venta)
8. [Refrescos asíncronos solapados o pisando la tabla](#8-refrescos-asíncronos-solapados-o-pisando-la-tabla)
9. [El detalle de cliente se vaciaba si fallaba un endpoint](#9-el-detalle-de-cliente-se-vaciaba-si-fallaba-un-endpoint)
10. [El buscador de cliente reabría el detalle tras seleccionar](#10-el-buscador-de-cliente-reabría-el-detalle-tras-seleccionar)

**API (cje_api)**
11. [Precios con decimales largos ($59.99)](#11-precios-con-decimales-largos-5999)
12. [Patrón N+1 en listados de ventas y abonos](#12-patrón-n1-en-listados-de-ventas-y-abonos)
13. [Editar una venta duplicaba stock o saldo](#13-editar-una-venta-duplicaba-stock-o-saldo)
14. [Editar/eliminar un abono no revertía el saldo](#14-editar-eliminar-un-abono-no-revertía-el-saldo)
15. [`VIA` en minúsculas fallaba la validación](#15-via-en-minúsculas-fallaba-la-validación)
16. [Ganancia ≥ 100 y división por cero en `TOTAL_FLETE`](#16-ganancia--100-y-división-por-cero-en-total_flete)
17. [`ID_LOTE` nulo rompía la integridad del inventario](#17-id_lote-nulo-rompía-la-integridad-del-inventario)
18. [`TOTAL_FLETE` no debe escribirse desde la app](#18-total_flete-no-debe-escribirse-desde-la-app)

**Base de datos / migración**
19. [Bases creadas antes del precio por línea](#19-bases-creadas-antes-del-precio-por-línea)

**Pruebas / infraestructura**
20. [Suite de pruebas GUI síncrona rota tras el refactor asíncrono](#20-suite-de-pruebas-gui-síncrona-rota-tras-el-refactor-asíncrono)

---

## Interfaz GUI (cje_gui)

### 1. Resultados perdidos en operaciones asíncronas

- **Síntoma:** las operaciones que corren en un hilo del pool (`run_async`) perdían
  su resultado de forma **intermitente**: refrescar tablas, guardar o cargar datos
  a veces simplemente no hacía nada. La prueba de regresión entregaba `{}` en la
  ruta de resultado (aunque la ruta de error sí funcionaba).
- **Causa raíz:** `run_async` no conservaba ninguna referencia al `ApiWorker`. El
  wrapper de Python (y sus señales) podía ser recolectado por el GC **antes** de
  que el hilo del pool ejecutara `run()`, perdiendo el resultado. Era un fallo de
  concurrencia difícil de reproducir (dependía del momento exacto del GC).
- **Solución:** se mantiene una referencia fuerte a cada worker mientras corre
  mediante el set global `_ACTIVE_WORKERS` y la función `_release()`; la referencia
  se libera cuando el worker emite `result` o `error`.
  `cje_gui/gui_workers.py:31-54`.
- **Verificación:** regresión en `tests/test_cje.py` (sección B.1: el resultado
  llega al hilo de la UI y el hilo principal sigue respondiendo durante un worker
  de 0.5 s; B.2: los errores llegan como excepción). Suite: 13/13 y 23/23.

### 2. Cursor de ocupado que nunca se restauraba

- **Síntoma:** el cursor quedaba atascado como `WaitCursor` (reloj) para siempre
  cuando una operación asíncrona anidaba `push_busy()` con `pop_busy()`.
- **Causa raíz:** el contador de cursor no estaba balanceado ante llamadas
  anidadas: un `pop_busy()` prematuro restauraba el cursor mientras aún había
  operaciones en curso.
- **Solución:** contador `_busy_count` que solo muestra el cursor en el primer
  `push` y solo lo restaura cuando llega a 0 (seguro ante anidación).
  `cje_gui/gui_workers.py:57-73`.
- **Verificación:** prueba B.3 de `tests/test_cje.py` ("sin cursor de ocupado
  colgado") con llamadas `push`/`pop` anidadas y desbalanceadas.

### 3. Desplegable de búsqueda no clickeable en diálogos modales

- **Síntoma:** en los diálogos modales (Nuevo, Editar, Nueva Venta) el desplegable
  de búsqueda de cliente/producto **se veía pero el clic no lo seleccionaba**.
  Con el teclado (flechas + Enter) sí funcionaba.
- **Causa raíz:** el popup era una ventana de nivel superior sin padre
  (`Qt.Tool` sin `QWidget` propietario). Un diálogo modal (`exec()`) **bloquea la
  entrada** (ratón/teclado) de todas las ventanas que no sean descendientes o
  owned de él; como el popup no era owned del diálogo, el clic nunca llegaba.
- **Solución (final):** el popup se crea con padre (`self._popup = QListView(self)`),
  con lo que pasa a ser una ventana **owned del diálogo** y queda exenta del
  bloqueo modal. Se conserva `Qt.Tool | FramelessWindowHint` + `WA_ShowWithoutActivating`
  (para que muestre sin quitar el foco de la caja de texto) y se añade la guarda de
  `editingFinished` (ver entrada 4). `cje_gui/cliente_search.py:50-64, 205-212`.
- **Verificación:** prueba offscreen (el popup aparece al escribir, el clic
  selecciona y el teclado selecciona) + confirmación manual del usuario ("ok ya
  funcionó") + suites 13/13 y 23/23.

### 4. Desplegable que se cerraba apenas se abría

- **Síntoma:** durante las pruebas de la solución anterior, el desplegable **no
  llegaba a mostrarse**: aparecía y desaparecía al instante (o nunca aparecía).
- **Causa raíz:** el manejo del cierre por pérdida de foco era demasiado
  agresivo. Mostrar el popup (o hacer clic sobre él) movía el foco del `QLineEdit`,
  disparaba `editingFinished` y `_hide_popup()` cerraba el desplegable antes de que
  el clic se registrara. También se probó con `Qt.Popup` (sin y con padre): ese
  tipo de ventana provoca el mismo problema de activación/foco y nunca mostró bien
  el desplegable.
- **Solución:** el handler `editingFinished` (`_on_edit_finished`) solo oculta el
  popup cuando el nuevo `QApplication.focusWidget()` existe **y no** es el popup ni
  un ancestro suyo; si el foco fue al propio popup (clic sobre una opción) o se
  perdió por mostrarlo, no oculta. `cje_gui/cliente_search.py:205-212`.
- **Verificación:** las mismas pruebas offscreen de la entrada 3 (popup estable
  mientras se escribe; clic y teclado seleccionan).

### 5. Error al ocultar el desplegable tras destruirse el widget

- **Síntoma:** en algunos cierres de ventana aparecía un `RuntimeError` al
  intentar ocultar el popup ("wrapped C/C++ object has been deleted").
- **Causa raíz:** al destruirse el widget padre se destruye el popup (ventana
  owned); si luego se invocaba `_hide_popup()`, `isVisible()`/`hide()` se llamaban
  sobre un objeto C++ ya eliminado.
- **Solución:** `_hide_popup()` envuelve el acceso en `try/except RuntimeError`.
  `cje_gui/cliente_search.py:198-203`.
- **Verificación:** abrir/cerrar repetidamente diálogos y ventanas sin excepciones
  en consola.

### 6. Decimales con coma/punto según el locale de Windows

- **Síntoma:** los `QDoubleSpinBox` mostraban y devolvían decimales según el
  locale del sistema: en Windows con locale que usa coma (ej. `150,50`) el valor
  no se parseaba bien, se perdía el separador o `float()` fallaba.
- **Causa raíz:** `QDoubleSpinBox` usa el locale del sistema por defecto y el
  código dependía de `float()` directo sobre texto del usuario.
- **Solución:** se centralizó la entrada numérica en `DecimalSpinBox`, que fuerza
  `QLocale.c()` y normaliza `,` → `.` en `validate()`/`valueFromText()`; y en
  `parse_decimal()`, que acepta punto o coma (si hay coma y punto, la coma es
  separador de miles; si solo hay coma, es decimal). `cje_gui/dialogs.py:9-17, 20-37`.
- **Verificación:** reglas obligatorias documentadas en `docs/LOGICA_NEGOCIO.md`
  y `docs/GUIA_GUI.md:101-117`; toda la GUI usa estos componentes (nunca `float()`
  directo sobre texto).

### 7. Editar una venta rechazaba el stock de la propia venta

- **Síntoma:** al editar una venta existente, la validación de stock rechazaba la
  cantidad de un producto que la **propia venta** ya tenía reservado: daba "stock
  insuficiente" sin que hubiera un problema real.
- **Causa raíz:** el stock disponible mostrado no incluía la cantidad reservada
  por la venta que se está editando (esa cantidad seguía descontada en el
  inventario).
- **Solución:** en modo edición, el stock disponible de cada ítem suma la cantidad
  ya reservada por esta misma venta. `cje_gui/venta_dialog.py:240-247`.
- **Verificación:** regla documentada en `docs/GUIA_GUI.md:409-411` y flujo
  manual de edición de ventas.

### 8. Refrescos asíncronos solapados o pisando la tabla

- **Síntoma:** con auto-refresh activo, varios refrescos asíncronos se lanzaban a
  la vez (respuestas fuera de orden), la tabla se refrescaba **detrás de un
  diálogo modal** abierto y, al terminar, la fila que el usuario tenía seleccionada
  se perdía.
- **Causa raíz:** no había guarda de re-entrancia en `refresh()`, el auto-refresh
  no comprobaba si había un diálogo modal abierto, y el refresco repoblaba la
  tabla sin restaurar la selección.
- **Solución:**
  - Guarda `_refreshing`: si ya hay un refresco en curso, se descarta el nuevo
    (`cje_gui/main_window.py:107-113`).
  - `_auto_refresh` se aborta si `QApplication.activeModalWidget()` no es `None`
    (`cje_gui/main_window.py:59-65`).
  - `_restore_selection()` vuelve a seleccionar la fila que tenía el PK elegido
    (`cje_gui/main_window.py:147-155`).
- **Verificación:** uso continuo con auto-refresh activo; suites 13/13 y 23/23.

### 9. El detalle de cliente se vaciaba si fallaba un endpoint

- **Síntoma:** si al abrir el detalle de un cliente fallaba la carga de compras o
  de abonos, el diálogo quedaba en blanco o se rompía por completo.
- **Causa raíz:** las tres llamadas (cliente, compras, abonos) se trataban como una
  sola unidad: el primer error abortaba el renderizado de todo.
- **Solución:** en `ClienteDetalleDialog._load` las compras y los abonos se cargan
  con `try/except` independientes y los errores se notifican por separado, de modo
  que un endpoint caído no vacía la vista completa.
  `cje_gui/main_window.py:477-514`.
- **Verificación:** simular fallo de un endpoint (API parcialmente caída) y abrir
  el detalle.

### 10. El buscador de cliente reabría el detalle tras seleccionar

- **Síntoma:** al elegir un cliente en el buscador se abría su detalle; al
  refrescarse la lista de clientes (auto-refresh), el texto seguía en el buscador
  y volvía a disparar la apertura del detalle sin que el usuario pidiera nada.
- **Causa raíz:** el texto del buscador no se limpiaba tras la selección, así que
  las notificaciones de cambio podían re-ejecutar el handler.
- **Solución:** tras mostrar el detalle, se limpia el buscador
  (`self.search_cliente.clear()`). `cje_gui/main_window.py:660-662`.
- **Verificación:** seleccionar un cliente y esperar un auto-refresh: el detalle
  no se reabre.

---

## API (cje_api)

### 11. Precios con decimales largos ($59.99)

- **Síntoma:** los precios y totales mostraban decimales largos de coma flotante;
  por ejemplo, `$30.00 × 2` podía dar `$59.99...` en lugar de `$60.00`.
- **Causa raíz:** se calculaban con `float` sin redondear, y la aritmética de
  punto flotante acumula errores.
- **Solución:** `COSTO_UNITARIO` y `PRECIO_VENTA` se calculan con `round(..., 2)`
  (`cje_api/routers/inventario.py:26, 35`) y el `PRECIO` de la venta también se
  redondea a 2 decimales cuando se calcula automáticamente
  (`cje_api/routers/venta.py:166, 289`).
- **Verificación:** reglas en `docs/LOGICA_NEGOCIO.md:23-25` y
  `docs/GUIA_GUI.md:85-88`; ejemplos en la documentación de la API
  (`$30.00 × 2 = $60.00`).

### 12. Patrón N+1 en listados de ventas y abonos

- **Síntoma:** listar ventas (o abonos) con muchas filas generaba decenas de
  consultas extra: por cada venta se consultaban cliente, detalles, inventario y
  catálogo individualmente.
- **Causa raíz:** el listado resolvía las referencias una por una (patrón N+1).
- **Solución:** `_listar_respuestas` construye las respuestas **en lote**: consulta
  clientes, detalles, inventarios y catálogos con `IN (...)` y los agrupa en
  diccionarios. `cje_api/routers/venta.py:81-130` y
  `cje_api/routers/abono.py:29-45`.
- **Verificación:** comentarios "(path batch sin N+1)" en `tests/test_cje.py` y
  verificación visual del `pgAdmin`/logs al listar.

### 13. Editar una venta duplicaba stock o saldo

- **Síntoma:** al editar una venta, el stock y el saldo del cliente se aplicaban
  de nuevo sin revertir los valores originales, **contando dos veces** el efecto.
- **Causa raíz:** la edición insertaba nuevos detalles y ajustaba saldo sobre el
  estado que ya incluía la venta original.
- **Solución:** `editar_venta` es una **transacción atómica** con patrón
  "revert-then-apply": revierte el stock de los detalles originales y el saldo del
  cliente original, valida y aplica los nuevos valores; ante cualquier error hay
  `rollback()` total (no queda nada a medias). `cje_api/routers/venta.py:229-328`.
  La eliminación revierte igualmente stock y saldo antes de borrar
  (`cje_api/routers/venta.py:331-373`).
- **Verificación:** pruebas PUT y DELETE de ventas (los totales de stock/saldo se
  recomponen exactamente tras editar o eliminar).

### 14. Editar/eliminar un abono no revertía el saldo

- **Síntoma:** editar o borrar un abono dejaba el saldo del cliente sin corregir
  (el efecto del abono original no se deshacía).
- **Causa raíz:** solo el `POST` ajustaba `SALDO -= CANTIDAD`; el `PUT`/`DELETE`
  no revertían la operación previa.
- **Solución:** `editar_abono` revierte el efecto del abono original en el saldo y
  aplica el nuevo (manejando también el cambio de `CEDULA`: revierte al cliente
  original y aplica al nuevo); `eliminar_abono` suma de vuelta la cantidad
  (`SALDO += CANTIDAD`). `cje_api/routers/abono.py:97-140, 143-162`.
- **Verificación:** pruebas PUT y DELETE de abonos verificando el saldo resultante.

### 15. `VIA` en minúsculas fallaba la validación

- **Síntoma:** enviar `"m"` o `"a"` (minúsculas) en `VIA` fallaba contra la columna
  `CHAR` o el `pattern` de Pydantic, aunque el usuario escribía en minúsculas.
- **Causa raíz:** no se normalizaba la entrada; la columna espera exactamente
  `'M'` o `'A'` y el esquema valida con `^[MA]$`.
- **Solución:** la API normaliza siempre a mayúscula con `VIA.upper()` antes de
  guardar. `cje_api/routers/flete.py:21, 66`.
- **Verificación:** crear/editar fletes con `via: "m"` y `"a"` → guardan como `"M"`/`"A"`.

### 16. Ganancia ≥ 100 y división por cero en `TOTAL_FLETE`

- **Síntoma:** un `GANACIA = 100` producía división por cero en el cálculo de
  `PRECIO_VENTA` (o precios absurdos); y `CANTIDAD = 0` rompía la fórmula del
  `TOTAL_FLETE`.
- **Causa raíz:** el esquema permitía valores fuera de rango y la fórmula de la
  BD dividía directamente por `CANTIDAD`.
- **Solución:**
  - La API rechaza `GANACIA >= 100` con un 400 explícito
    (`cje_api/routers/inventario.py:28-32`) y el esquema fuerza `CANTIDAD > 0`
    (`cje_api/schemas/flete.py:10`).
  - La columna `TOTAL_FLETE` usa `NULLIF("CANTIDAD", 0)` para devolver `NULL` en
    vez de error (`SQL/CJE.sql:23`).
- **Verificación:** intentar crear inventario con `GANACIA = 100` → 400; flete con
  `CANTIDAD = 0` → 422.

### 17. `ID_LOTE` nulo rompía la integridad del inventario

- **Síntoma:** se podía guardar un ítem de inventario sin lote asociado, dejando
  datos huérfanos y precios calculados sin flete.
- **Causa raíz:** la actualización (`PUT`) no validaba que `ID_LOTE` siguiera
  existiendo o no fuera nulo.
- **Solución:** el `PUT` rechaza explícitamente `ID_LOTE = null` con un 400
  ("Todo producto de inventario debe tener un lote (FLETE) asociado").
  `cje_api/routers/inventario.py:79-83`.
- **Verificación:** `PUT` con `"ID_LOTE": null` → 400; el resto de actualizaciones
  siguen funcionando.

### 18. `TOTAL_FLETE` no debe escribirse desde la app

- **Síntoma:** al crear o editar un flete, la app podía intentar escribir
  `TOTAL_FLETE`, que en realidad es una **columna generada por PostgreSQL**
  (`GENERATED ALWAYS AS (...) STORED`); escribirla provocaba error de la BD.
- **Causa raíz:** el modelo no marcaba el campo como calculado.
- **Solución:** el modelo usa `Computed()` de SQLAlchemy sobre `TOTAL_FLETE` para
  que la app jamás intente escribirlo. `cje_api/models/flete.py:15-16`.
- **Verificación:** crear y editar fletes sin errores de la columna generada.

---

## Base de datos / migración

### 19. Bases creadas antes del precio por línea

- **Síntoma:** en bases de datos creadas con versiones anteriores del script,
  el campo `DETALLES_VENTAS.PRECIO_UNITARIO` no existía y al crear una venta con
  precio por línea fallaba.
- **Causa raíz:** el precio por línea (`PRECIO_UNITARIO` en detalle) se añadió al
  esquema en una fase posterior; las BD existentes quedaban sin la columna.
- **Solución:** migración ad-hoc documentada en `docs/INSTALACION.md:58-65`:
  `ALTER TABLE public."DETALLES_VENTAS" ADD COLUMN IF NOT EXISTS "PRECIO_UNITARIO"
  double precision;`.
- **Verificación:** ejecutar la migración sobre una BD antigua y crear ventas con
  precio por línea.

---

## Pruebas / infraestructura

### 20. Suite de pruebas GUI síncrona rota tras el refactor asíncrono

- **Síntoma:** tras refactorizar la GUI a llamadas asíncronas (`run_async`), las
  pruebas que llamaban a los handlers de forma síncrona colgaban o fallaban
  (por ejemplo, `_on_editar` abría `VentaDialog(...).exec()` desde un callback
  asíncrono y el test nunca terminaba).
- **Causa raíz:** los handlers ya no devuelven datos de forma síncrona y abren
  diálogos modales con `exec()` dentro del flujo asíncrono.
- **Solución:** la suite `test_gui_async.py` se adaptó al refactor:
  - La sección de ventas usa `search_cliente.clientes()` (el atributo `cmb_cliente`
    ya no existe) y llama `setCliente(CLIENTE)` antes de `_on_save()`.
  - Se parchea `main_window.VentaDialog.exec` con un reemplazo no-bloqueante para
    no colgar el test.
- **Verificación:** suite `test_gui_async.py` 23/23 y `tests/test_cje.py` 13/13
  en verde.
