# CJE Perfumes — Guía Maestra de Replicación de la GUI

> **Propósito:** permitir a una persona o IA replicar la interfaz de usuario completa de
> CJE Perfumes en cualquier plataforma (Android, Java, web, .NET, etc.) contra la **misma
> API**, respetando la lógica de negocio, el contrato de datos y las normas creadas durante
> el desarrollo.
>
> **Documentos que esta guía enlaza (no duplica):**
> - `../README.md` — referencia de la API por módulo (endpoints, payloads, respuestas).
> - `../FLUJO_DATOS.md` — arquitectura, esquema de BD, procesos por módulo.
> - `../LOGICA_NEGOCIO.md` — reglas de negocio.
> - `../GUIA_GUI.md` — normas obligatorias para toda interfaz (auth, validación, payloads).
> - `../INSTALACION.md` — despliegue del backend y la GUI por escenario.
> - `../BUGS_Y_SOLUCIONES.md` — problemas resueltos y sus causas.
>
> La implementación de referencia es `cje_gui/` (PySide6). En esta guía se cita su
> comportamiento con referencias `archivo:línea` para que sirva de contrato observable.

---

## Tabla de contenidos

1. [Objetivo y alcance](#1-objetivo-y-alcance)
2. [Arquitectura](#2-arquitectura)
3. [Contrato de API y autenticación](#3-contrato-de-api-y-autenticación)
4. [Lógica de negocio obligatoria](#4-lógica-de-negocio-obligatoria)
5. [Cómo mostrar los datos en la GUI](#5-cómo-mostrar-los-datos-en-la-gui)
6. [Patrón CRUD genérico](#6-patrón-crud-genérico)
7. [Flujo de la GUI de referencia por módulo](#7-flujo-de-la-gui-de-referencia-por-módulo)
8. [Login y sesión](#8-login-y-sesión)
9. [Carga asíncrona y estados de la interfaz](#9-carga-asíncrona-y-estados-de-la-interfaz)
10. [Buenas prácticas multi-plataforma](#10-buenas-prácticas-multi-plataforma)
11. [Glosario](#11-glosario)

---

## 1. Objetivo y alcance

Esta guía describe **qué** debe hacer una interfaz de CJE Perfumes y **cómo** presentar y
transformar los datos, de forma independiente de la tecnología. Cubre:

- Cómo conectarse y autenticarse contra la API.
- Qué reglas de negocio son innegociables (las aplica el servidor; la interfaz las respeta).
- Cómo mostrar cada módulo (tablas, columnas, formatos, diálogos).
- Cómo es el flujo de la GUI de referencia para que una réplica se comporte igual.
- Qué primitivas de cada plataforma (hilos, almacenamiento local, etc.) remplazan las de Qt.

No cubre el diseño visual (colores, espaciados) salvo cuando afecta el contrato de datos.

---

## 2. Arquitectura

```
Interfaz (web / móvil / escritorio) ──HTTP/JSON──► cje_api/ (FastAPI) ──SQL──► PostgreSQL
```

- La interfaz **nunca** accede a la BD; toda lectura/escritura pasa por la API.
- La API es la **única fuente de verdad**: valida, calcula (precios, saldos, totales) y
  persiste. La interfaz captura, valida para UX y muestra resultados.
- Los nombres de campo y códigos llegan **tal cual** del JSON, en mayúsculas, sin
  renombrar ni traducir (`GUIA_GUI.md` §1 y §2.1).
- Arquitectura completa, esquema BD y procesos: `FLUJO_DATOS.md`.

### Resolución de la URL de la API

Al arrancar, la GUI de referencia muestra un **diálogo de URL** (`url_dialog.py`) que se
rellena con la última URL usada (almacenada en `QSettings`, clave `conexion/url`) y, si no
hay ninguna, con la prioridad de `cje_gui/config.py`:

1. Variable de entorno `CJE_API_URL`.
2. Campo `api.url` del archivo `cje_api/config.json` (ruta junto al proyecto, o la de
   `CJE_CONFIG`).
3. Valor por defecto `http://127.0.0.1:8000`.

El usuario confirma/edita la URL; la GUI la guarda en `QSettings` (`conexion/url`) y la
recuerda en los siguientes arranques. El valor puede apuntar a local, a una IP de LAN o a
un dominio sin cambiar el código (`INSTALACION.md` §8). La GUI muestra "Conectado a <url>"
en la barra de estado (`main_window.py:990`). Una réplica debe ofrecer el equivalente: un
campo de configuración de la URL recordado en el almacén local, precargado con
`CJE_API_URL`/`api.url`.

---

## 3. Contrato de API y autenticación

La API protege los datos con **tokens JWT** (`GUIA_GUI.md` §1.1). Toda petición a módulos
de datos lleva el header:

```
Authorization: Bearer <token>
```

Sin token válido la API responde `401`. Flujo estándar:

1. `POST /token/` — form-urlencoded con `username` y `password`. Responde
   `{"access_token": "...", "token_type": "bearer"}`.
   - Las credenciales se definen en `config.json` (sección `auth`, o con `CJE_API_USER` y
     `CJE_API_PASSWORD`); **no hay credenciales por defecto hardcodeadas**.
2. Enviar el token en cada petición. Expiración por defecto: 1440 min (24 h,
   configurable con `CJE_TOKEN_EXPIRE_MINUTES`).
3. Ante un `401` con token expirado: **obtener un token nuevo y reintentar la petición una
   vez**. La GUI de referencia lo hace en `ApiClient._request` (`api_client.py:39-48`)
   usando credenciales memorizadas.
4. Endpoints **públicos** (sin token): `GET /`, `GET /db-check`, `POST /token/`. Todo lo
   demás exige token.

### Endpoints por módulo (resumen)

Detalle completo de payloads, respuestas y códigos de error en `../README.md`.

| Módulo | Lectura | Crear | Actualizar | Eliminar | PK |
|---|---|---|---|---|---|
| Fletes | `GET /fletes` | `POST /fletes/` | `PUT /fletes/{id}` | `DELETE /fletes/{id}` | `ID_FLETE` |
| Catálogo | `GET /catalogo` | `POST /catalogo/` | `PUT /catalogo/{id}` | `DELETE /catalogo/{id}` | `ID_CATALOGO` |
| Inventario | `GET /inventario` | `POST /inventario/` | `PUT /inventario/{id}` | `DELETE /inventario/{id}` | `ID_INVENTARIO` |
| Clientes | `GET /clientes` · `GET /clientes/{cedula}` | `POST /clientes/` | `PUT /clientes/{cedula}` | `DELETE /clientes/{cedula}` | `CEDULA` |
| Ventas | `GET /ventas` (`?cedula=`) · `GET /ventas/{id}` | `POST /ventas/` | `PUT /ventas/{id}` | `DELETE /ventas/{id}` | `ID_VENTA` |
| Abonos | `GET /abonos` (`?cedula=`) | `POST /abonos/` | `PUT /abonos/{id}` | `DELETE /abonos/{id}` | `ID_ABONO` |

Notas:
- Los `PUT` de Clientes, Catálogo e Inventario son **parciales** (solo se envían los campos
  a modificar). El `PUT` de Ventas es **completo** (encabezado + todos los detalles).
- `GET /ventas/?cedula=` y `GET /abonos/?cedula=` filtran por cliente; se usan para el
  detalle del cliente.
- Claves de respuesta (JSON, mayúsculas): ver tabla de `GUIA_GUI.md` §2.1.

### Tipos y códigos (resumen)

| Campo | Valores permitidos |
|---|---|
| `VIA` | `M` (Marítimo), `A` (Aéreo) |
| `TIPO_PAGO` | `CONTADO`, `CREDITO` |
| `FORMA_DE_PAGO` | `EFECTIVO`, `TRANSFERENCIA`, `TARJETA`, `MOVIL`, `OTRO` |

- Números se envían como **JSON number**, nunca como cadena ni con `$`.
- Fechas en formato `YYYY-MM-DD`.
- La interfaz puede mostrar etiquetas legibles, pero **envía los códigos** en mayúsculas.

---

## 4. Lógica de negocio obligatoria

Resumen ejecutivo. La regla completa, con ejemplos numéricos, está en
`../LOGICA_NEGOCIO.md` y `../GUIA_GUI.md` §6.

- **Lote obligatorio en inventario:** no se crea/edita inventario sin `ID_LOTE` (nunca
  `null`). El campo no ofrece opción "sin lote".
- **Cantidad asignada vs stock:** al crear inventario se pide `CANTIDAD_ASIGNADA`
  (cantidad original comprada del flete); la API iguala `CANTIDA` (stock) a ese valor. Las
  ventas descuentan `CANTIDA` **sin tocar** `CANTIDAD_ASIGNADA`.
- **Cupo del flete:** la suma de `CANTIDAD_ASIGNADA` de los ítems de un flete no puede
  superar `FLETE.CANTIDAD` (la API responde `400` si se excede). Al editar un flete, no se
  puede reducir `CANTIDAD` por debajo de lo asignado. Los fletes exponen
  `CANTIDAD_ASIGNADA` y `CANTIDAD_DISPONIBLE` (solo lectura).
- **Precios monetarios a 2 decimales:** `COSTO_UNITARIO = round(PRECIO_UNITARIO +
  TOTAL_FLETE, 2)`; `PRECIO_VENTA = round(COSTO_UNITARIO / (1 − GANACIA/100), 2)`. La
  API los recalcula al guardar; la interfaz **no los envía**.
- **`TOTAL_FLETE`** = `(SHEPING + PRECIO_CURRIER) / CANTIDAD` (lo calcula la BD; no editable).
- **Venta:** cliente obligatorio y existente; stock suficiente por línea; sin duplicados de
  producto; precio total = Σ subtotales (o manual opcional); cada línea usa el
  `PRECIO_UNITARIO` guardado o el `PRECIO_VENTA` del inventario; `SUBTOTAL` nunca se envía
  (= `PRECIO_UNITARIO × CANTIDAD`).
- **Subtotal de línea editable:** al editarlo se deriva `precio_unitario = subtotal ÷
  cantidad` (redondeado a 2) y se envía como `PRECIO_UNITARIO` de la línea.
- **Cantidad de línea editable:** entero ≥ 1, ≤ stock; al cambiarla recalcula el subtotal.
- **Saldo del cliente:** `SALDO += PRECIO − PAGO`. Puede ser **negativo** (la empresa le
  debe). Monto a pagar = `total + SALDO` (mínimo 0): saldo negativo descuenta (crédito),
  positivo carga (deuda previa). `PRECIO` registrado no cambia por el crédito.
- **Eliminar venta** revierte stock y saldo; la interfaz debe advertirlo antes de confirmar.
- **Abonos:** `SALDO -= CANTIDAD`; cantidad > 0; el excedente sobre la deuda queda como
  saldo a favor (no se impide).
- **Eliminaciones con dependencias:** la API responde `400` si hay FK; la interfaz pide
  confirmación y muestra el `detail`.

---

## 5. Cómo mostrar los datos en la GUI

Esta sección define el **contrato visual**: cómo se presentan las tablas, celdas,
formularios y búsquedas, de modo que una réplica muestre los datos de la misma manera.

### 5.1 Reglas generales de presentación

- **Punto decimal fijo en pantalla**, independiente del idioma del sistema
  (`LOGICA_NEGOCIO.md`, "Formato de números").
- **Moneda:** los importes se muestran con `$`, separador de miles y 2 decimales:
  `$1,234.50`. Formato de referencia en Qt: `f"{val:,.2f}"`.
- **Fechas:** se muestran como `YYYY-MM-DD` (igual que llegan del JSON).
- **Códigos:** se pueden mostrar como etiqueta legible (`Marítimo`, `Crédito`, `Efectivo`),
  pero el **valor almacenado/enviado siempre es el código**.
- **Nulos:** una celda vacía se muestra como cadena vacía o `-`, nunca `null`/`None`.
- **Celdas de tabla:** solo lectura (la edición ocurre en diálogos o celdas específicas
  con doble clic). La selección es de fila completa y única.
- **Identificadores:** los IDs se muestran tal cual (enteros), sin prefijos.

### 5.2 Tablas de módulos (columnas y formato)

Columnas exactas de la GUI de referencia (`main_window.py`):

#### Fletes (`main_window.py:436-444`)

| Cabecera | Clave JSON | Formato |
|---|---|---|
| ID | `ID_FLETE` | entero |
| Fecha | `FECHA` | `YYYY-MM-DD` |
| Proveedor | `PROVEEDOR` | texto |
| Shipping | `SHEPING` | moneda |
| Courier | `NOMBRE_CURRIER` | texto |
| Vía | `VIA` | etiqueta: `M`→Marítimo, `A`→Aéreo |
| P. Courier | `PRECIO_CURRIER` | moneda |
| Cantidad | `CANTIDAD` | entero |
| Asignado | `CANTIDAD_ASIGNADA` | entero (solo lectura; lo calcula la API) |
| Disponible | `CANTIDAD_DISPONIBLE` | entero (solo lectura; lo calcula la API) |
| Total Flete | `TOTAL_FLETE` | moneda (calculado por servidor) |

#### Catálogo (`main_window.py:742-745`)

| Cabecera | Clave JSON |
|---|---|
| ID | `ID_CATALOGO` |
| Nombre | `NOMBRE` |
| Marca | `MARCA` |
| Presentación | `PRESENTACION` |

#### Inventario (`main_window.py:255-265`)

| Cabecera | Clave JSON | Origen |
|---|---|---|
| ID | `ID_INVENTARIO` | ítem |
| Catálogo | `ID_CATALOGO` | ítem |
| Producto | `NOMBRE` | del catálogo (join en la GUI) |
| Marca | `MARCA` | del catálogo |
| Presentación | `PRESENTACION` | del catálogo |
| Inventario Final (Actual) | `CANTIDA` | ítem (stock actual; lo descuentan las ventas) |
| Inventario Inicial | `CANTIDAD_ASIGNADA` | ítem (cantidad original comprada del flete) |
| Lote | `ID_LOTE` | ítem (ID del flete) |
| P. Unitario | `PRECIO_UNITARIO` | ítem, moneda |
| Costo Unit. | `COSTO_UNITARIO` | ítem, moneda |
| Ganancia % | `GANACIA` | ítem, número (ej. `33.3`) |
| P. Venta | `PRECIO_VENTA` | ítem, moneda |

> Las columnas Producto/Marca/Presentación se resuelven en la GUI: `get_inventario()`
> devuelve el `ID_CATALOGO` y la interfaz lo cruza con `get_catalogo()` para mostrar el
> nombre (`main_window.py:358-365`). Una réplica puede hacer lo mismo o pedir un endpoint
> enriquecido; si usa el cruce, **una sola carga de catálogo** alimenta la tabla y los
> formularios (no dos peticiones).

#### Clientes (`main_window.py:669-673`)

| Cabecera | Clave JSON | Formato |
|---|---|---|
| Cédula | `CEDULA` | entero |
| Nombre | `NOMBRE` | texto |
| Correo | `CORREO` | texto |
| Teléfono | `TELEFONO` | texto |
| Saldo | `SALDO` | moneda (puede ser negativa) |

#### Ventas (`main_window.py:764-769`)

| Cabecera | Clave JSON | Formato |
|---|---|---|
| ID | `ID_VENTA` | entero |
| Fecha | `FECHA` | `YYYY-MM-DD` |
| Cédula | `CEDULA` | entero |
| Cliente | `NOMBRE_CLIENTE` | texto (resuelto por la API) |
| Precio | `PRECIO` | moneda |
| Tipo | `TIPO_PAGO` | etiqueta (`CONTADO`/`CREDITO`) |
| Forma | `FORMA_DE_PAGO` | etiqueta |
| Pago | `PAGO` | moneda |

#### Abonos (`main_window.py:890-894`)

| Cabecera | Clave JSON | Formato |
|---|---|---|
| ID | `ID_ABONO` | entero |
| Fecha | `FECHA` | `YYYY-MM-DD` |
| Cédula | `CEDULA` | entero |
| Cliente | `NOMBRE_CLIENTE` | texto (resuelto por la API) |
| Cantidad | `CANTIDAD` | moneda |

### 5.3 Búsquedas (SearchBox)

Tres buscadores autocompletados; todos comparten: filtrar mientras se escribe, popup con
**máx. 20 coincidencias**, navegación por teclado (↑/↓, Enter selecciona, Esc cierra),
tooltip en cada resultado, y la regla de que **elegir una opción del desplegable es
obligatorio** (texto tecleado sin seleccionar no es válido).

- **ClienteSearchBox** (`cliente_search.py:269-326`) — filtra por **cédula, nombre o
  correo**. Resultado: `Cédula - Nombre` con tooltip de correo, teléfono y saldo. Se usa en
  Clientes, Ventas y Abonos. Al elegir en la pestaña Clientes se abre el Detalle y la
  búsqueda se limpia (`main_window.py:728`).
- **CatalogoSearchBox** (`cliente_search.py:402-466`) — filtra por **nombre, marca o
  presentación**. Desplegable en dos líneas: `ID - NOMBRE` y debajo `MARCA · PRESENTACIÓN`
  (segunda línea solo si existen). Campo `ID_CATALOGO` del inventario.
- **ProductoVentaSearchBox** (`cliente_search.py:329-399`) — filtra por **nombre, marca o
  presentación**, solo ítems con `CANTIDA > 0`. Dos líneas: `NOMBRE` y
  `MARCA · PRESENTACIÓN · $precio · (stock N)` (**sin el ID**). Espera claves en minúscula
  (`nombre`, `precio`, `stock`) — la réplica debe decidir un contrato equivalente y
  documentarlo; la referencia las deriva del inventario+catálogo (`venta_dialog.py:248-256`).

### 5.4 Formularios (FormDialog)

Diálogo genérico con un campo por entrada (`dialogs.py`). Tipos de campo y su control:

| Tipo | Control | Comportamiento |
|---|---|---|
| `str` | campo de texto | requerido si se indica; no vacío |
| `int` | campo numérico entero | mínimo configurable (≥ 1 típico) |
| `float` | campo decimal (`DecimalSpinBox`) | acepta **punto o coma**; redondea a 2 |
| `date` | selector de fecha | formato `YYYY-MM-DD` |
| `char` | combo | pares `(código, etiqueta)`; se guarda `currentData()` = código |
| `search` | SearchBox + `search_items` | se guarda el `search_key` del ítem elegido (p. ej. `CEDULA`, `ID_CATALOGO`) |

- **Validación local** antes de enviar: requeridos no vacíos, rangos, combo con opción real
  (`dialogs.py:198-215`). La API es la autoridad final: ante rechazo se muestra su `detail`.
- **Vista previa en vivo** (opcional): texto bajo el formulario que se actualiza al cambiar
  los campos (ej. precio de venta estimado en Inventario).
- **Info de búsqueda** (opcional): texto bajo un campo `search` con datos del ítem
  seleccionado (ej. deuda actual del cliente en Abonos).
- Los **campos calculados por la API** (`TOTAL_FLETE`, `COSTO_UNITARIO`, `PRECIO_VENTA`)
  no aparecen como editables.

### 5.5 Diálogos de detalle

- **Detalle del Cliente** (`main_window.py:478-665`): encabezado con cédula-nombre,
  correo, teléfono; dos tablas laterales **Compras** (ID, Fecha, Tipo, Forma, Precio,
  Pagado) y **Abonos** (ID, Fecha, Cantidad); resumen inferior con Total comprado, Pagado
  en ventas, Total abonado, Dinero pagado y **Saldo actual**. Doble clic en una compra abre
  el detalle de la venta. Botón "Editar" abre el form de cliente y recarga.
- **Detalle de Venta** (`main_window.py:834-870`): info de la venta (fecha, cliente,
  tipo/forma, precio total, pagado) y tabla de líneas **Producto, P. Unitario, Cantidad,
  Subtotal** (moneda en precios y subtotales).

### 5.6 Entrada de números (norma obligatoria)

Reglas completas en `GUIA_GUI.md` §4 y `LOGICA_NEGOCIO.md` "Formato de números":

1. Aceptar **punto o coma** como separador decimal: `150,50` = `150.50`.
2. Separador de miles no interfiere: si hay coma y punto, la coma es miles; si solo coma,
   es decimal (`1,500.50` = 1500.5).
3. Normalizar a número antes de enviar (quitar `$`, espacios, miles), redondear importes a
   2 decimales, enviar como JSON number.
4. Negativo solo donde el negocio lo permite (`SALDO`).
5. Entrada inválida no crashea ni borra valores previos.
6. **Visualización siempre con punto decimal**, sin importar el idioma del sistema.

---

## 6. Patrón CRUD genérico

Todos los módulos (salvo Ventas) comparten el patrón `ModuleWidget` (`main_window.py:25-251`):

- **Toolbar:** botón "Refrescar", checkbox "Auto-refresh" (ON por defecto), y botones
  Nuevo / Editar / Eliminar (en Clientes y Ventas se agrega "Ver Detalle").
- **Tabla:** solo lectura, selección de fila única, colores alternados, última columna
  estirable, columnas ajustadas al contenido al cambiar el número de filas
  (`main_window.py:158-169`).
- **Nuevo:** abre FormDialog "Nuevo" con campos en blanco; al aceptar hace POST y refresca.
- **Editar:** toma la fila seleccionada, abre FormDialog "Editar" precargado con el registro;
  al aceptar hace PUT y refresca.
- **Eliminar:** pide confirmación `¿Eliminar registro con {PK}={valor}?`; al confirmar hace
  DELETE y refresca. En Ventas el mensaje advierte "Se revertirá el stock y el saldo del
  cliente".
- **Auto-refresh:** cada 30 s recarga la tabla si la pestaña está visible y no hay diálogo
  modal abierto; la recarga es silenciosa (los errores no se muestran).
- **Selección preservada:** tras refrescar se restaura la fila previamente seleccionada por
  su PK.
- **Carga diferida:** cada pestaña carga sus datos la primera vez que se muestra
  (`ensure_loaded`, `main_window.py:103-106`), no al abrir la app.

---

## 7. Flujo de la GUI de referencia por módulo

### 7.1 Fletes

- CRUD estándar. `FECHA` y `PROVEEDOR` obligatorios; `SHEPING`/`PRECIO_CURRIER` ≥ 0;
  `VIA` combo Marítimo/Aéreo; `CANTIDAD` entero ≥ 1.
- `TOTAL_FLETE` lo calcula el servidor; no se muestra como editable.
- La tabla muestra **Asignado** (`CANTIDAD_ASIGNADA`) y **Disponible**
  (`CANTIDAD_DISPONIBLE`), ambos de solo lectura (los calcula la API).
- Al editar no se puede reducir `CANTIDAD` por debajo de lo asignado (la API responde
  `400`); se muestra el `detail`.
- No se elimina un flete con inventario asociado (la API responde `400`).

### 7.2 Catálogo

- CRUD estándar: `NOMBRE` obligatorio; `MARCA`, `PRESENTACION` opcionales.
- Sin lógica especial en la GUI.

### 7.3 Inventario

- **Antes de abrir el formulario** (`_prepare_async`, `main_window.py:291-328`): carga en
  segundo plano el catálogo y los fletes.
- El **combo de lote** muestra `FECHA PROVEEDOR (VIA)` (ej. `2026-08-05 Perfumería París
  (A)`) ordenado por **FECHA descendente**; el valor guardado es el **`ID_FLETE`**
  (`currentData`), que se envía como `ID_LOTE` (`main_window.py:308-318`). Cuando la API
  lo soporta, se agrega "‑ queda N" con `CANTIDAD_DISPONIBLE`.
- **Selector de producto:** CatalogoSearchBox (nombre/marca/presentación, `ID - NOMBRE`).
- **Campos:** `CANTIDAD_ASIGNADA` (Cantidad asignada (original), entero ≥ 1, obligatorio)
  y, al editar, `CANTIDA` (stock actual, editable). Al crear, `CANTIDA` no se muestra (la
  API lo iguala a la asignada).
- **Vista previa en vivo** (`main_window.py:392-431`): muestra el **cupo del flete**
  ("Flete #N: trajo X, asignados Y, disponibles Z") con advertencia si la cantidad asignada
  lo excede, y el precio de venta estimado = `round(round(PRECIO_UNITARIO + TOTAL_FLETE, 2)
  / (1 − GANACIA/100), 2)`; pide seleccionar lote si falta. Es orientativa; el valor real lo
  fija la API.
- `GANACIA` entre 0.1 y 99.9; `PRECIO_UNITARIO` ≥ 0.01; `CANTIDAD_ASIGNADA` ≥ 1.
- Al guardar, la API valida el **cupo del flete**; si se excede responde `400` y la GUI
  muestra el `detail`.

### 7.4 Clientes

- Tabla con buscador superior + botón "Ver Detalle" (también en el toolbar).
- Elegir un cliente del buscador **abre el Detalle y limpia la búsqueda**.
- **Detalle del Cliente** (§5.5): compras (`GET /ventas/?cedula=`), abonos
  (`GET /abonos/?cedula=`), resumen y saldo; doble clic en una compra abre el detalle de la
  venta; "Editar" usa el mismo form y, si cambia la cédula, actualiza título y recarga.
- `CEDULA` y `NOMBRE` obligatorios; `SALDO` acepta negativos (mínimo −999999999).

### 7.5 Ventas

Es el módulo más complejo; la referencia vive en `venta_dialog.py`. Flujo de un alta:

1. **Referencias asíncronas** (`venta_dialog.py:182-230`): cargar clientes (mapa
   `CEDULA → SALDO`) e inventario+catálogo. Mientras cargan, el botón Guardar queda
   deshabilitado y el título indica "(cargando…)".
2. **Cabecera:** cliente (ClienteSearchBox), fecha (default hoy), `TIPO_PAGO`
   (Contado/Crédito), `FORMA_DE_PAGO` (Efectivo/Transferencia/Tarjeta/Pago Móvil/Otro).
3. **Productos:** ProductoVentaSearchBox con stock; solo ítems con stock > 0; sin
   duplicados; el stock mostrado en la línea es el del inventario.
4. **Líneas** (tabla Producto / Stock / Cantidad / Subtotal): agregar y quitar; **cantidad**
   y **subtotal** editables con doble clic (validados y revertidos si son inválidos).
   Al editar el subtotal se deriva `precio = round(subtotal/cantidad, 2)`.
5. **Total:** automático = Σ(precio × cantidad); el campo "Total de la venta" admite
   **precio manual** que lo sustituye (placeholder con el precio sugerido).
6. **Saldos** (solo lectura, se recalculan en vivo): Deuda Actual, Crédito a favor
   (`max(0, −deuda)`), Monto a pagar (`max(total + deuda, 0)`), Deuda Posterior
   (`deuda + total − PAGO`).
7. **Monto Pagado:** último campo; en **Contado** queda bloqueado y se auto-rellena con el
   monto a pagar; en **Crédito** es editable. Puede ser 0.
8. **Guardado:** payload con `CEDULA`, `FECHA`, `TIPO_PAGO`, `FORMA_DE_PAGO`, `PAGO`,
   `detalles: [{ID_INVENTARIO, CANTIDAD, PRECIO_UNITARIO(round 4)}]` y `PRECIO` manual
   opcional. Si el pago excede el monto a pagar (> 0.005), pide confirmación ("el excedente
   quedará como saldo a favor").

**Edición** (`main_window.py:796-815`): carga `GET /ventas/{id}`, precarga cliente, fecha,
tipo/forma, PAGO, ítems con cantidades y el `PRECIO_UNITARIO` guardado por línea (o el
`PRECIO_VENTA` si es NULL); el `PRECIO` guardado se precarga **solo si difiere** del
subtotal calculado (en caso contrario queda vacío = recálculo). El stock de cada línea
**suma la cantidad ya reservada por esa misma venta**.

**Detalle:** botón "Ver Detalle" abre el diálogo de §5.5.

**Eliminar:** confirmación con advertencia de reversión de stock y saldo.

### 7.6 Abonos

- Cliente obligatorio (ClienteSearchBox, precargado con los clientes).
- Al seleccionar el cliente, muestra orientativamente: "Deuda actual del cliente: $X" o
  "Sin deuda; el cliente tiene saldo a favor de $Y" (`main_window.py:931-942`).
- Fecha opcional (default hoy); `CANTIDAD` > 0 obligatorio.
- Al editar/eliminar, la API revierte el efecto sobre el SALDO; la GUI recarga tras guardar.

---

## 8. Login y sesión

Comportamiento de referencia (`main.py`, `login_dialog.py`, `api_client.py`):

1. Al arrancar se muestra el **diálogo de URL** de la API (§2): precargado con la última
   URL usada (`QSettings conexion/url`) o con `CJE_API_URL`/`api.url`; si se cancela, el
   programa termina. La URL elegida se guarda.
2. Si hay credenciales guardadas, se intenta **login automático**; cualquier fallo cae al
   diálogo manual (`main.py:46-53`).
3. **LoginDialog** (`login_dialog.py:9-78`): campos Usuario y Contraseña (enmascarada),
   checkbox "Recordar credenciales" **marcado por defecto**, botones "Iniciar sesión"
   (default) / "Cancelar", y un label de error en rojo. Enter en usuario pasa a la
   contraseña; Enter en contraseña inicia sesión.
4. Credenciales guardadas (solo si "Recordar") en el almacén persistente de la plataforma
   (en Qt: `QSettings`, claves `auth/usuario` y `auth/password`). **No guardar el token**;
   solo usuario/contraseña.
5. El token vive **solo en memoria** y se envía como header en cada petición.
6. **Re-login automático:** ante `401`, si hay credenciales en memoria, obtener token nuevo
   y reintentar una vez (`api_client.py:39-48`).
7. **Cerrar sesión** (toolbar "Cerrar sesión"): confirmación (default **No**) → borrar
   credenciales guardadas → limpiar token/header → cerrar la app. La referencia **no
   vuelve al login**: termina el proceso (`main.py:33-36`).
8. Barra de estado: "Conectado a <url>".

---

## 9. Carga asíncrona y estados de la interfaz

Norma obligatoria (`GUIA_GUI.md` §8): **la interfaz nunca bloquea su hilo de UI** esperando
a la API.

- Toda petición HTTP corre en **segundo plano** (hilo de trabajo / async / worker), nunca en
  el hilo de presentación.
- Al terminar, el resultado (o el error) vuelve al hilo de UI mediante **señal/callback**;
  ahí se actualiza la vista.
- La UI sigue respondiendo durante la operación y muestra un estado de carga
  (cursor de ocupado; título "(cargando…)"; botones deshabilitados).
- **Anti-doble-envío:** mientras corre una operación, se deshabilita el botón que la
  disparó o el guardado.
- **Evitar cargas redundantes:** los datos de referencia (catálogo, clientes) que alimentan
  varios controles se obtienen **una vez** y se comparten; los módulos no visibles no se
  refrescan (carga diferida por pestaña).
- **Errores:** extraer y mostrar el `detail` de la API (cadena legible); nunca el error
  crudo. Clasificar: red/servidor, validación/negocio (4xx), servidor (5xx).
- Tras guardar/eliminar, **recargar desde la API** para reflejar los valores recalculados
  por el servidor (PRECIO_VENTA, saldos, TOTAL_FLETE).
- Tablas con muchos registros: fijar el número de filas de una vez y asignar celdas, sin
  insertar fila por fila; redimensionar solo cuando cambia el contenido.

Implementación de referencia (`gui_workers.py`): `run_async(fn, on_result, on_error)`
despacha al pool de hilos y devuelve los callbacks al hilo de UI; `push_busy()/pop_busy()`
muestran el cursor de ocupado de forma anidada.

---

## 10. Buenas prácticas multi-plataforma

Equivalencias entre la referencia Qt (PySide6) y otras tecnologías:

| Necesidad | Qt (referencia) | Equivalente recomendado |
|---|---|---|
| Almacén de credenciales | `QSettings` (`main.py:10-13`) | `SharedPreferences` (Android), `UserDefaults` (iOS), `localStorage` (web), registry/`app.config` (.NET/Java) |
| Persistir solo usuario/contraseña; token en memoria | `ApiClient.access_token` | Variable/objeto de sesión en memoria; nunca persistir el token |
| Hilos de fondo | `QThreadPool`/`QRunnable` + señales (`gui_workers.py`) | `Coroutine`/`Worker`/`AsyncTask` (Android), `async/await` (web), `Task`/`BackgroundWorker` (.NET), `SwingWorker` (Java) |
| Devolver resultados al hilo UI | señales Qt en cola | callbacks en el hilo principal / `runOnUiThread` / `Dispatcher` |
| Diálogos modales | `FormDialog`, `QMessageBox` | `DialogFragment`/`AlertDialog` (Android), `Modal` (web), `JDialog` (Java) |
| Autocompletado | `SearchBox` custom (`cliente_search.py`) | `AutocompleteTextView`, `<input list>`, `ComboBox` editable |
| Guardado de config | `cje_gui/config.py` + `config.json`; URL recordada en `QSettings` (`conexion/url`) | Archivo de config propio + variable de entorno `CJE_API_URL`; URL persistida en el almacén local |
| Validación de campos | `dialogs.py` (required, min, max, DecimalSpinBox) | Validators de cada framework + misma lógica en el cliente |

Prácticas generales:

- Usar la **URL base** del diálogo de URL / `config.json` / `CJE_API_URL` (§2) para apuntar
  a local, LAN o producción sin recompilar; recordar la URL elegida en el almacén local.
- **Una sola implementación de "parsear número con punto o coma"** y **una sola de
  "formatear moneda"** reutilizada en toda la app (nunca duplicar lógica por pantalla).
- Mantener el patrón CRUD genérico: no duplicar código de listado/formulario por módulo.
- Documentar en el README de la réplica las decisiones de contrato propias (p. ej. claves
  en minúscula del `ProductoVentaSearchBox`).
- Antes de dar por terminada la réplica, pasar la lista de pruebas obligatorias de
  `GUIA_GUI.md` §10.

---

## 11. Glosario

| Término | Significado |
|---|---|
| Flete | Lote de mercancía importada (proveedor, courier, costos, cantidad). Es el "lote" del inventario. |
| Lote (`ID_LOTE`) | Referencia del flete asociado a cada ítem de inventario. Obligatorio. |
| `CANTIDAD_ASIGNADA` | Cantidad original comprada del flete para un ítem; no cambia al vender. En fletes, es la suma de las de sus ítems. |
| `CANTIDAD_DISPONIBLE` | `max(0, FLETE.CANTIDAD − CANTIDAD_ASIGNADA)`; cupo restante por asignar. |
| `TOTAL_FLETE` | Costo de envío unitario del flete, calculado por la BD. |
| `COSTO_UNITARIO` | `PRECIO_UNITARIO + TOTAL_FLETE`, redondeado a 2. |
| `PRECIO_VENTA` | `COSTO_UNITARIO / (1 − GANACIA/100)`, redondeado a 2. |
| Ganancia (`GANACIA`) | Margen en % aplicado sobre el costo (0.1–99.9). |
| Abono | Pago del cliente hacia su saldo global (`SALDO -= CANTIDAD`). |
| Saldo del cliente | `SALDO`; positivo = debe, negativo = saldo a favor (la empresa le debe). |
| Crédito a favor | `max(0, −SALDO)`; se aplica como parte del pago sin alterar `PRECIO`. |
| Monto a pagar | `total + SALDO` (mínimo 0): descuenta crédito o cobra deuda previa. |
| Contado | `TIPO_PAGO=CONTADO`; el monto pagado se fija al monto a pagar. |
| Crédito | `TIPO_PAGO=CREDITO`; monto pagado editable (puede ser 0). |
| Detalle de venta | Línea de producto en una venta: `ID_INVENTARIO`, `CANTIDAD`, `PRECIO_UNITARIO`. |
| `PRECIO_UNITARIO` (línea) | Precio por unidad del detalle; si es NULL, la API usa `PRECIO_VENTA`. |
