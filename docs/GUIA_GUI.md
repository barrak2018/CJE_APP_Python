# Guía: Normas para construir interfaces que consumen la API de CJE Perfumes

Este documento reúne las **normas obligatorias** que debe cumplir cualquier interfaz
(web, escritorio, móvil u otra tecnología) que muestre o edite los datos de la API de
CJE Perfumes (`cje_api/`).

Las normas son **independientes de la tecnología**. Tratan sobre cómo recibir, validar,
transformar y enviar los datos para que siempre exista un contrato claro entre la
interfaz y la API. La implementación de referencia actual vive en `cje_gui/` (PySide6),
pero estas reglas aplican igual a un SPA, una app móvil o un CLI.

---

## 1. Arquitectura y responsabilidades

- La interfaz **nunca** accede a la base de datos directamente. Toda lectura y escritura
  pasa por la API vía HTTP/JSON.
- La API es la **única fuente de verdad**: valida, calcula y persiste. La interfaz solo
  captura datos, los valida para mejorar la experiencia y muestra resultados.
- Los nombres de campo, códigos y formatos que se documentan aquí **no deben
  renombrarse ni traducirse** en la interfaz: se usan tal cual llegan del JSON.

```
Interfaz (web / escritorio / móvil) ──HTTP/JSON──► API (FastAPI) ──SQL──► PostgreSQL
```

> **Dirección de la API:** en la GUI de escritorio, `ApiClient` toma la URL del campo
> `api.url` del archivo `cje_api/config.json` (o de la variable `CJE_API_URL` si está
> definida). Ese valor puede apuntar a local, a una IP de la red o a un dominio, sin
> cambiar el código (ver `INSTALACION.md` §8 para los escenarios de despliegue).

---

## 1.1 Autenticación (tokens JWT) — obligatorio

La API protege el acceso a los datos con **tokens JWT**. Toda petición a los módulos de
datos debe llevar el header `Authorization: Bearer <token>`; sin token válido la API
responde `401`.

1. **Obtener el token**: `POST /token/` con el flujo OAuth2 estándar (form con `username`
   y `password`). Respuesta: `{"access_token": "...", "token_type": "bearer"}`.
   Credenciales por defecto de desarrollo: `admin` / `admin123` (configurables con
   `CJE_API_USER` y `CJE_API_PASSWORD`).
2. **Enviarlo en cada petición**: header `Authorization: Bearer <token>`.
3. **Expiración**: el token caduca (por defecto 1440 min = 24 h, configurable con
   `CJE_TOKEN_EXPIRE_MINUTES`). Ante un `401` con token expirado, volver a obtener el token
   y reintentar una vez. La GUI de referencia (`ApiClient.login`) lo hace automáticamente.
4. **Endpoints públicos** (no requieren token): `GET /`, `GET /db-check` y `POST /token/`.
   Todos los demás (fletes, catálogo, inventario, clientes, ventas, abonos) exigen token.

Ejemplo con `curl`:

```bash
# 1) Obtener token
curl -X POST http://127.0.0.1:8000/token/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin123"

# 2) Usar el token
curl http://127.0.0.1:8000/clientes -H "Authorization: Bearer <token>"
```

En la GUI de escritorio, `ApiClient.login()`/`logout()` gestionan el token y el re-login
automático; el diálogo de inicio de sesión puede recordar las credenciales y el botón
"Cerrar sesión" (barra superior) las olvida y cierra el programa.

---

## 2. Contrato de datos (formato JSON)

### 2.1 Claves

Las claves son las del JSON, en mayúsculas, exactamente como las devuelve la API.
Ejemplos por módulo:

| Módulo | Claves principales |
|---|---|
| Fletes | `ID_FLETE`, `FECHA`, `PROVEEDOR`, `SHEPING`, `NOMBRE_CURRIER`, `VIA`, `PRECIO_CURRIER`, `CANTIDAD`, `TOTAL_FLETE` |
| Clientes | `CEDULA`, `NOMBRE`, `CORREO`, `TELEFONO`, `SALDO` |
| Catálogo | `ID_CATALOGO`, `NOMBRE`, `MARCA`, `PRESENTACION` |
| Inventario | `ID_INVENTARIO`, `ID_CATALOGO`, `CANTIDA`, `ID_LOTE`, `PRECIO_UNITARIO`, `COSTO_UNITARIO`, `GANACIA`, `PRECIO_VENTA` (+ lectura: `NOMBRE`, `MARCA`, `PRESENTACION` del catálogo) |
| Ventas | `ID_VENTA`, `FECHA`, `CEDULA`, `PRECIO`, `TIPO_PAGO`, `FORMA_DE_PAGO`, `PAGO`, `detalles` |
| Detalle de venta | `ID_DETALLE`, `ID_INVENTARIO`, `CANTIDAD`, `NOMBRE_PRODUCTO`, `PRECIO_UNITARIO`, `SUBTOTAL` |
| Abonos | `ID_ABONO`, `FECHA`, `CEDULA`, `CANTIDAD` (+ lectura: `NOMBRE_CLIENTE` del cliente) |

### 2.2 Tipos

- **Números** (importes, cantidades, IDs): siempre se envían como **número JSON**
  (`150.5`), nunca como cadena (`"150.5"`) ni con símbolos (`$`).
- **Fechas**: texto en formato `YYYY-MM-DD` (ej. `2026-08-04`).
- **Valores opcionales**: se envían como `null` o simplemente se omiten (según lo que
  admita cada endpoint). En las respuestas pueden llegar como `null`.
- **Enumeraciones**: se envían como **código** en mayúsculas, no como etiqueta visible:

  | Campo | Valores |
  |---|---|
  | `VIA` | `M` (Marítimo) o `A` (Aéreo) |
  | `TIPO_PAGO` | `CONTADO`, `CREDITO` |
  | `FORMA_DE_PAGO` | `EFECTIVO`, `TRANSFERENCIA`, `TARJETA`, `MOVIL`, `OTRO` |

  La interfaz puede mostrar una etiqueta legible ("Crédito") pero **debe enviar el
  código** ("CREDITO").

### 2.3 Identificadores

- Cada recurso identifica por su clave primaria: `ID_FLETE`, `ID_INVENTARIO`,
  `ID_CATALOGO`, `ID_VENTA`. En Clientes la PK es `CEDULA`.
- Los IDs de la API se usan tal cual (enteros), sin prefijos ni transformaciones.

---

## 3. Campos calculados: no editables

La API calcula y devuelve estos campos. **La interfaz no debe enviarlos ni permitir
editarlos**; se recalculan automáticamente en cada operación.

| Campo | Cálculo |
|---|---|
| `TOTAL_FLETE` | `(SHEPING + PRECIO_CURRIER) / CANTIDAD` (columna STORED de la BD, `real`) |
| `COSTO_UNITARIO` | `round(PRECIO_UNITARIO + TOTAL_FLETE, 2)` del lote |
| `PRECIO_VENTA` | `round(COSTO_UNITARIO / (1 - GANACIA/100), 2)` |
| `NOMBRE_CLIENTE` | Nombre resuelto desde Cliente (solo lectura) |
| `NOMBRE_PRODUCTO` | Nombre resuelto desde Catálogo (solo lectura) |

> **Precios en centavos:** los importes son monetarios y la API los **redondea a 2
> decimales** antes de guardarlos (`COSTO_UNITARIO` y `PRECIO_VENTA`). Así el precio que se
> muestra (`$30.00`) coincide con el usado en los cálculos (`$30.00 × 2 = $60.00`, nunca
> `$59.99` por decimales largos).

> **Excepción en ventas:** en cada línea del detalle, `PRECIO_UNITARIO` **es un campo de
> entrada opcional** (≥ 0). Si se envía, queda guardado en la línea; si se omite, la API usa
> `INVENTARIO.PRECIO_VENTA`. `SUBTOTAL` nunca se envía: siempre es `PRECIO_UNITARIO × CANTIDAD`
> y lo calcula la API. Esto permite a la interfaz mostrar/editar el **subtotal de cada
> elemento del combo por separado** (al editar el subtotal se deriva el precio unitario =
> `subtotal ÷ cantidad`).

Regla: si un campo no se puede escribir en la BD, **no se muestra como editable**.

---

## 4. Entrada de números (punto o coma) — norma obligatoria

Cualquier campo numérico que el usuario escriba debe aceptar **punto o coma** como
separador decimal, sin importar la configuración regional del dispositivo.

1. `"150,50"` y `"150.50"` son lo mismo: **150.5**.
2. El separador de miles no debe interferir: `"1,500.50"` = 1500.5, `"1500,50"` = 1500.5.
   Regla: si hay coma **y** punto, la coma es miles; si hay solo coma, es decimal.
3. Antes de enviar se **normaliza a número** (se eliminan símbolos `$`, espacios y
   separadores de miles) y se envía como JSON number.
4. Los importes se **redondean a 2 decimales** antes de enviarse.
5. La entrada inválida se rechaza de forma amable: no debe crashear la interfaz ni
   alterar valores previos ya cargados.
6. El signo negativo solo es válido donde el negocio lo permite (ver §6.3 SALDO).
7. La visualización de números debe ser consistente (punto como decimal) e
   independiente del idioma del sistema operativo.

---

## 5. Validación

- La interfaz valida para dar buen UX, pero la **API es la autoridad final**: cualquier
  cosa que rechace el servidor debe mostrarse y respetarse.
- Las reglas locales **nunca son más estrictas que las del backend** (rangos, requeridos,
  formatos). Ejemplo: si la API exige `PRECIO_UNITARIO > 0`, la interfaz usa al menos ese
  mismo límite; si el backend admite `SALDO` negativo, la interfaz también.
- Un campo marcado como **requerido** en la interfaz debe coincidir con lo que exige el
  schema de la API (ver tablas del README).
- Validaciones de negocio a nivel de interfaz (para ahorrar un viaje al servidor):
  - Texto requerido no vacío.
  - Cantidades enteras ≥ 1 (o el mínimo que exija el módulo).
  - Importes ≥ 0 donde corresponda.
  - Combo obligatorio: el usuario debe elegir una opción real (no un valor "en blanco").
- Ante un rechazo del servidor, mostrar el `detail` que devuelve la API; no inventar un
  mensaje genérico que oculte la causa real.

---

## 6. Reglas de negocio que toda interfaz debe respetar

### 6.1 Inventario

- **El lote (`ID_LOTE`) es obligatorio.** No se puede crear ni guardar inventario sin
  lote, ni quitarle el lote a un ítem existente.
- En los formularios, el campo lote **no debe ofrecer una opción "sin lote"/"ninguno"**.
  Si la lista de fletes está vacía, el campo no podrá completarse y no se debe permitir
  guardar.
- `ID_CATALOGO`, `PRECIO_UNITARIO` y `GANACIA` también son obligatorios. `GANACIA` debe
  estar entre 0 y 100 (sin incluir los extremos).
- **Selector de producto (catálogo) tipo buscador**: el campo `ID_CATALOGO` se elige con una
  barra de búsqueda (`CatalogoSearchBox`) que filtra por **nombre, marca o presentación**
  mientras se escribe. El desplegable muestra cada coincidencia en dos líneas:
  `ID - NOMBRE` y, debajo, `MARCA · PRESENTACIÓN` (la segunda línea se omite si el catálogo
  no define marca/presentación). El usuario debe **elegir una opción del desplegable** (clic o
  Enter con flechas): un texto tecleado sin seleccionar no cuenta como producto válido. Al
  editar un ítem, el campo se precarga con el catálogo del registro.
- La tabla del inventario muestra, además de los campos del ítem, las columnas de lectura
  **Producto** (`CATALOGO.NOMBRE`), **Marca** (`CATALOGO.MARCA`) y **Presentación**
  (`CATALOGO.PRESENTACION`), obtenidas del catálogo según `ID_CATALOGO` (vacías si el
  catálogo no las define).
- El formulario de inventario ofrece un **vista previa en vivo** del precio de venta
  estimado (`costo ÷ (1 − ganancia/100)`) que se actualiza al cambiar lote, precio unitario
  o ganancia; es solo orientativa y no altera el payload guardado (el valor real lo recalcula
  la API al guardar).

### 6.2 Ventas

El formulario de venta es el proceso más delicado; combina cliente, stock, precio y saldo.

- **Cliente obligatorio**: no se puede vender sin seleccionar un cliente registrado.
- **Selector de cliente tipo buscador**: el cliente se elige con una barra de búsqueda
  (`ClienteSearchBox`, reutilizable en otros módulos) que filtra por **cédula, nombre o
  correo** mientras se escribe y muestra un desplegable con las coincidencias. El usuario
  debe **elegir una opción del desplegable** (clic o Enter con flechas): un texto tecleado
  sin seleccionar no cuenta como cliente válido. Al editar una venta, el campo se precarga
  con el cliente guardado (`Cédula - Nombre`).
- **Venta contra inventario**: el selector de productos es una **barra de búsqueda**
  (`ProductoVentaSearchBox`) que filtra por **nombre, marca o presentación** y solo muestra
  ítems con `CANTIDA > 0`. El desplegable muestra cada coincidencia en dos líneas: `NOMBRE`
  y `MARCA · PRESENTACIÓN · $precio · (stock N)` (marca/presentación solo si existen; **sin el
  ID**). El usuario debe **elegir una opción del desplegable** (clic o Enter con flechas): un
  texto tecleado sin seleccionar no cuenta como producto válido. Al agregarlo, la búsqueda se
  limpia para poder elegir otro.
- **Sin productos duplicados** en la misma venta (cada `ID_INVENTARIO` una sola línea).
- **Cantidad editable por línea**: la columna de **cantidad** de cada producto también es
  editable (doble clic), igual que el subtotal. Al modificarla, el subtotal de la línea se
  recalcula (`precio unitario × cantidad`), y con él el total y el monto a pagar/pago en
  CONTADO. La cantidad debe ser un entero ≥ 1 y nunca superar el stock disponible (en la
  edición de una venta, el tope incluye la cantidad ya reservada por esa misma venta); si se
  escribe un valor inválido, se revierte al anterior.
- **Subtotal editable por línea**: la columna de subtotal de cada producto (elemento del combo)
  es editable (doble clic). Al modificarla, la interfaz calcula el precio unitario de la línea
  (`subtotal ÷ cantidad`, redondeado a 2 decimales) y lo envía como `PRECIO_UNITARIO`; el
  subtotal nunca se envía. El `PRECIO_UNITARIO` de la línea es opcional en la API: si se omite,
  usa `INVENTARIO.PRECIO_VENTA`. La interfaz lo envía siempre (el del inventario si la línea no
  se modificó), para conservar lo editado. En la edición de una venta se precargan los precios
  guardados de cada línea.
- **Precio total**:
  - Se calcula como suma de los subtotales de las líneas (cada subtotal =
    `PRECIO_UNITARIO` de la línea × `CANTIDAD`).
  - El usuario puede dejar el campo vacío (= se usa el cálculo automático) o escribir un
    **precio manual** que lo sustituye. El precio manual debe ser ≥ 0.
- **Monto pagado** (`PAGO`) puede ser 0 (venta a crédito) y nunca negativo. Aparece
  **después** del total de la venta (último campo del formulario). Si el tipo de pago es
  `CONTADO`, el campo se **bloquea y se fija al monto a pagar** (total de la venta más la
  deuda previa del cliente, con mínimo 0); en `CREDITO` el usuario lo escribe libremente.
- **Crédito a favor del cliente** (solo lectura): si el cliente tiene `SALDO` negativo,
  muestra cuánto le debe la empresa (`−SALDO`). Ese crédito **se aplica automáticamente
  como parte del pago**, sin alterar el `PRECIO` registrado (se guarda el precio completo).
- **Monto a pagar** (solo lectura): `total de la venta + deuda previa del cliente`
  (mínimo 0). Refleja la deuda completa del cliente en ambos sentidos:
  - `SALDO` negativo (la empresa le debe) → **descuento**: total − crédito.
  - `SALDO` positivo (el cliente debe) → **cargo**: total + deuda. En `CONTADO` esto
    liquida toda la deuda previa en una sola operación.
  - Si el crédito supera el total, el monto a pagar es 0 y el sobrante sigue a favor del
    cliente.
- **Deuda actual y posterior** (orientativas, de solo lectura) entre el total y el monto
  pagado: la primera muestra el `SALDO` actual del cliente seleccionado; la segunda, el
  saldo resultante tras la venta = `deuda actual + total − PAGO`. Ambas se recalculan en
  vivo al cambiar cliente, productos, precio o monto pagado.
- En `CREDITO`, si el `PAGO` supera el **monto a pagar**, la interfaz advierte que el
  excedente quedará como saldo a favor del cliente antes de guardar (no lo bloquea).
- **Eliminar una venta revierte stock y saldo** del cliente. La interfaz **debe advertir
  esto** antes de confirmar la eliminación.

### 6.3 Clientes

- **El saldo puede ser negativo** (la empresa le debe al cliente). Los campos de saldo
  deben permitir valores menores que cero.
- **Buscador de clientes**: la pestaña Clientes incluye arriba un `ClienteSearchBox`
  (igual que el de ventas, filtra por cédula/nombre/correo). Al **elegir un cliente del
  desplegable**, se abre la ventana de **Detalle del Cliente** y la búsqueda se limpia.
- **Ventana de Detalle del Cliente** (se abre con el buscador o con el botón
  "Ver Detalle" sobre la fila seleccionada). Muestra:
  - Los **datos guardados** del cliente (cédula, nombre, correo, teléfono) y su **saldo actual**.
  - La **lista de compras** del cliente (vía `GET /ventas/?cedula=`): ID, fecha, tipo de
    pago, forma, precio y pagado. Al hacer **doble clic** sobre una fila se abre el
    **detalle de esa venta** (misma ventana que el botón "Ver Detalle" de la pestaña
    Ventas: datos de la venta y sus productos vía `GET /ventas/{id}`).
  - La **lista de abonos** del cliente (vía `GET /abonos/?cedula=`): ID, fecha y cantidad.
  - Un **resumen** con: total comprado (Σ `PRECIO`), pagado en ventas (Σ `PAGO`), total
    abonado (Σ `CANTIDAD`), **dinero pagado** (`Σ PAGO + Σ abonos`) y saldo actual.
  - Un botón **"Editar"** que abre el mismo formulario de edición de cliente (cédula,
    nombre, correo, teléfono, saldo). Al guardar se llama `PUT /clientes/{cedula}` y la
    ventana **se recarga** (cabecera y resumen actualizados). Si se cambia la cédula,
    la ventana pasa a mostrar el detalle del nuevo cédula.

### 6.4 Abonos

- Los **abonos** son pagos que el cliente hace hacia su deuda. Cada abono **reduce el
  SALDO** del cliente (`SALDO -= CANTIDAD`). Si el monto supera la deuda, el excedente
  queda como saldo a favor (SALDO negativo); no se impide ese excedente.
- El **cliente es obligatorio** y se elige con la barra de búsqueda (`ClienteSearchBox`),
  igual que en ventas. Al seleccionarlo, el formulario muestra **orientativamente la deuda
  actual** del cliente (su `SALDO`), como ayuda para decidir el monto del abono.
- **Fecha**: opcional; por defecto la fecha actual. Debe enviarse en formato `YYYY-MM-DD`.
- **Monto (`CANTIDAD`)**: obligatorio, mayor a cero.
- Al **editar o eliminar** un abono, la API revierte el efecto original sobre el SALDO y
  aplica el nuevo valor (o cliente). La interfaz debe recargar los datos tras guardar.

### 6.5 Eliminaciones en general

- Si eliminar un registro puede afectar a otros (flete con inventario, catálogo con
  inventario, cliente con ventas, inventario con detalles), la interfaz **debe pedir
  confirmación** y la API rechazará la operación con `400` si hay dependencias. Mostrar
  ese mensaje tal cual.

---

## 7. Manejo de errores y estado de la interfaz

- **Errores de la API**: extraer y mostrar `detail` (es una cadena legible). Nunca
  mostrar el error crudo/interno al usuario final.
- Clasificar para una mejor UX:
  - Error de **red/servidor** (no se pudo conectar): mensaje de conexión.
  - Error **4xx de validación/negocio**: mensaje del servidor (stock, duplicados, etc.).
  - Error **5xx**: problema del servidor; indicar que se intente más tarde.
- **Carga**: mientras se lee o se guarda, la interfaz debe impedir acciones duplicadas
  (guardar dos veces seguidas) y, si la operación falla, no cerrar el formulario ni
  perder lo que escribió el usuario.
- **Después de guardar/eliminar**, volver a cargar los datos desde la API para reflejar
  el estado real (el servidor puede recalcular valores como `PRECIO_VENTA`).

---

## 8. Norma de responsividad: las interfaces NUNCA bloquean

> **Regla obligatoria:** ninguna interfaz puede detener su hilo de presentación (UI) para
> esperar a la API. El usuario nunca debe ver la ventana "congelada" mientras se leen o se
> guardan datos.

### 8.1 Qué está prohibido

- Llamadas HTTP **síncronas directamente en el hilo de la UI** (bloquean el repintado y la
  entrada del usuario hasta que responde el servidor).
- Actualizaciones periódicas (auto-refresh) que ejecuten la petición en el hilo principal.
- Abrir formularios o pantallas cuyo constructor haga peticiones de red sincrónicas.
- Hacer la misma petición **dos veces** para llenar dos controles (tabla y buscador).

### 8.2 Cómo debe ser

- **Toda petición HTTP corre en segundo plano** (hilo de trabajo, `QThreadPool`/`QRunnable`,
  tarea `async`, worker de la plataforma, etc.) y **nunca** en el hilo de la UI.
- Al terminar, el resultado vuelve al hilo de la UI mediante una **señal/callback** y ahí se
  actualiza la vista. Los errores también se entregan por ese mismo mecanismo y se muestran
  de forma amable (§7).
- La UI debe **seguir respondiendo** (repintar, aceptar clics, mostrar un estado de "cargando…")
  durante toda la operación.
- Evitar **cargas redundantes**: los datos de referencia (catálogo, clientes) que alimentan
  varios controles se obtienen una sola vez y se comparten. Los módulos que no están visibles
  no se refrescan en segundo plano (carga diferida por pestaña/pantalla).
- **Anti-doble-envío**: mientras una operación está en curso, deshabilitar el botón que la
  disparó (o bloquear el guardado) para impedir peticiones duplicadas.
- Tablas con muchos registros se llenan por lotes (fijar el número de filas de una vez y
  asignar las celdas), sin insertar fila por fila, y se redimensionan solo cuando cambia el
  contenido.

### 8.3 Implementación de referencia

En `cje_gui/` (PySide6) se usa `gui_workers.py`:

- `run_async(fn, on_result, on_error)` despacha `fn` al pool de hilos; los callbacks corren
  en el hilo de la UI.
- `push_busy()` / `pop_busy()` muestran el cursor de ocupado de forma anidada y segura.
- Los widgets (tablas, CRUD, `VentaDialog`, detalle de cliente/venta) lanzan sus lecturas y
  guardados con `run_async(...)` y solo tocan la interfaz dentro de los callbacks.

Cualquier interfaz nueva (web, móvil, escritorio) debe seguir el mismo principio con las
primitivas asíncronas de su tecnología. Ver también la prueba 11 de §10 (pruebas
obligatorias).

---

## 9. Contratos de envío (payloads)

### Crear flete — `POST /fletes/`

```json
{
  "FECHA": "2026-08-05",
  "PROVEEDOR": "Perfumes Asia",
  "SHEPING": 150.00,
  "NOMBRE_CURRIER": "DHL Express",
  "VIA": "M",
  "PRECIO_CURRIER": 80.00,
  "CANTIDAD": 50
}
```

> `FECHA` es **obligatoria** (formato `YYYY-MM-DD`) tanto al crear como al editar un flete.

### Crear cliente — `POST /clientes/`

```json
{
  "CEDULA": 12345678,
  "NOMBRE": "Juan Pérez",
  "CORREO": "juan@email.com",
  "TELEFONO": "+584121234567",
  "SALDO": 0.0
}
```

### Crear ítem de inventario — `POST /inventario/`

```json
{
  "ID_CATALOGO": 1,
  "CANTIDA": 30,
  "ID_LOTE": 1,
  "PRECIO_UNITARIO": 8.50,
  "GANACIA": 33.3
}
```

> `ID_LOTE` nunca va en `null`.

### Crear venta — `POST /ventas/`

```json
{
  "CEDULA": 12345678,
  "FECHA": "2026-08-04",
  "TIPO_PAGO": "CREDITO",
  "FORMA_DE_PAGO": "EFECTIVO",
  "PAGO": 50.00,
  "PRECIO": 150.00,
  "detalles": [
    { "ID_INVENTARIO": 1, "CANTIDAD": 2, "PRECIO_UNITARIO": 19.64 },
    { "ID_INVENTARIO": 2, "CANTIDAD": 3 }
  ]
}
```

- `PRECIO` es opcional: si se omite, la API lo calcula como suma de subtotales.
- `FECHA` es opcional: si se omite, la API usa la fecha actual.
- `detalles` exige mínimo 1 ítem y `CANTIDAD > 0`.
- `PRECIO_UNITARIO` es opcional por línea (≥ 0): si se omite, se usa `INVENTARIO.PRECIO_VENTA`.
  Si la interfaz permitió editar el subtotal del elemento, envía `PRECIO_UNITARIO` calculado
  como `subtotal ÷ cantidad`.

### Editar venta — `PUT /ventas/{id}`

Mismo contrato que `POST /ventas/` (actualización **completa**: encabezado + productos).
La API revierte el stock y el saldo originales y aplica los nuevos en una sola transacción.

- Se permite cambiar el `CEDULA` del cliente.
- `PRECIO` es opcional: si se omite, se recalcula como suma de subtotales.
- Al editar, la interfaz debe precargar: cliente, fecha, tipo/forma de pago, PAGO,
  ítems con sus cantidades, el `PRECIO_UNITARIO` guardado en cada línea (si es `NULL`, el
  `PRECIO_VENTA` del inventario) y el PRECIO guardado **solo si difiere** del subtotal
  calculado (en caso contrario el campo queda vacío = recálculo automático).
- En el selector de productos, el stock disponible debe **sumar la cantidad reservada
  por la propia venta** que se está editando.

### Actualizaciones parciales — `PUT`

Los `PUT` de Clientes, Catálogo e Inventario son parciales: se envía **solo lo que se va
a modificar** (ej. `{"SALDO": 50.0}`). Los campos no enviados conservan su valor.

---

## 10. Pruebas obligatorias de la interfaz

Antes de dar por terminada una interfaz, comprobar al menos:

1. **Números con punto y coma**: `"150,50"` y `"150.50"` producen el mismo valor;
   `"1,500.50"` se envía como 1500.5. Sin símbolos `$` ni espacios en el payload.
2. **Valores negativos** donde aplique (SALDO de cliente) y rechazo donde no aplique
   (PAGO, cantidades, precio manual < 0).
3. **Entrada inválida** no crashea ni borra valores ya cargados.
4. **Payload exacto**: las claves, tipos y códigos coinciden con el §2 y el §9.
5. **Errores del servidor** se muestran al usuario con el `detail` correspondiente
   (duplicado de cédula, stock insuficiente, lote inexistente, etc.).
6. **Campos calculados** (PRECIO_VENTA, COSTO_UNITARIO, TOTAL_FLETE, saldo) se refrescan
   desde la API tras guardar, no se calculan a ciegas en la interfaz.
7. **Regla de negocio clave por módulo**: lote obligatorio en inventario; en ventas,
   stock y sin duplicados; advertencia al eliminar ventas.
8. **Edición de ventas**: al abrir el diálogo se precargan todos los valores; tras
   guardar, el stock y el saldo reflejan el estado final (stock + saldo original
   revertidos y nuevos aplicados).
9. **Subtotal por línea**: modificar el subtotal de un producto (elemento de combo) guarda
   el `PRECIO_UNITARIO` derivado; al reabrir la venta se precarga ese precio y el subtotal
   coincide. En las líneas no modificadas la interfaz envía igualmente `PRECIO_UNITARIO`
   (el de `PRECIO_VENTA`), que el backend guarda sin cambios de valor.
10. **Cantidad por línea**: modificar la cantidad (doble clic) recalcula el subtotal
    (`precio unitario × cantidad`), el total y el pago en CONTADO; se guarda como
    `CANTIDAD` del detalle y el stock se ajusta en el backend. Límite: entero ≥ 1 y no
    mayor al stock disponible (en edición, incluye la cantidad ya reservada).
11. **La interfaz no bloquea (norma §8)**: durante un refresco manual, el auto-refresh, la
    apertura de un formulario (`VentaDialog`, detalle de cliente/venta) o un guardado, la
    ventana **sigue respondiendo** (se puede mover, repintar y no muestra el "No responde"
    del sistema). Verificar que los botones que disparan la operación se deshabilitan
    mientras esta corre y que los datos se actualizan al llegar la respuesta.
