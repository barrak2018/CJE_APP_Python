# CJE Perfumes — Referencia de la API

**Versión:** 1.0.0  
**URL Base:** `http://localhost:8000`  
**Documentación Swagger:** `http://localhost:8000/docs`

> **Documentación relacionada:**
> - [FLUJO_DATOS.md](FLUJO_DATOS.md) — procesos y flujos de datos.
> - [LOGICA_NEGOCIO.md](LOGICA_NEGOCIO.md) — reglas de negocio.
> - [GUIA_GUI.md](GUIA_GUI.md) — normas para interfaces que consuman esta API (cualquier tecnología: web, escritorio, móvil).
> - [INSTALACION.md](INSTALACION.md) — puesta en marcha del backend y la GUI.
> - [BUGS_Y_SOLUCIONES.md](BUGS_Y_SOLUCIONES.md) — bugs encontrados y cómo se resolvieron.

---

## Tabla de contenidos

1. [Estado del sistema](#1-estado-del-sistema)
2. [Fletes](#2-fletes)
3. [Clientes](#3-clientes)
4. [Catálogo](#4-catálogo)
5. [Inventario](#5-inventario)
6. [Ventas](#6-ventas)
7. [Abonos](#7-abonos)
8. [Códigos de error](#8-códigos-de-error)

---

## 1. Estado del sistema

### `GET /`

Verifica que la API esté operativa.

**Respuesta `200`:**
```json
{
  "sistema": "CJE Perfumes API",
  "estado": "Operativo"
}
```

### `GET /db-check`

Valida la conexión con PostgreSQL.

**Respuesta `200`:**
```json
{
  "database": "Conexión exitosa a PostgreSQL"
}
```

**Respuesta `500`:**
```json
{
  "detail": "Error al conectar con la base de datos: ..."
}
```

---

## 2. Fletes

Representa un lote de mercancía importada con datos del proveedor, courier y costos de envío.

### Campos del recurso

| Campo | Tipo | Descripción |
|---|---|---|
| `ID_FLETE` | `int` | Identificador único (auto-generado) |
| `PROVEEDOR` | `str` | Nombre del proveedor |
| `SHEPING` | `float` | Costo de shipping (≥ 0, default `0.0`) |
| `NOMBRE_CURRIER` | `str` | Nombre del courier |
| `VIA` | `str` | Vía de transporte: `"M"` (Marítimo) o `"A"` (Aéreo) |
| `PRECIO_CURRIER` | `float` | Precio cobrado por el courier (≥ 0, default `0.0`) |
| `CANTIDAD` | `int` | Cantidad de unidades en el lote (> 0, default `1`) |
| `TOTAL_FLETE` | `float \| null` | Calculado automáticamente por la BD |
| `CANTIDAD_ASIGNADA` | `int` | Suma de las cantidades asignadas de los ítems de inventario del flete (solo lectura) |
| `CANTIDAD_DISPONIBLE` | `int` | `max(0, CANTIDAD − CANTIDAD_ASIGNADA)`, cupo restante para asignar (solo lectura) |

---

### `POST /fletes/`

Registra un nuevo flete.

**Body:**
```json
{
  "PROVEEDOR": "Perfumes Asia",
  "SHEPING": 150.00,
  "NOMBRE_CURRIER": "DHL Express",
  "VIA": "M",
  "PRECIO_CURRIER": 80.00,
  "CANTIDAD": 50
}
```

| Campo | Tipo | Requerido | Validaciones |
|---|---|---|---|
| `PROVEEDOR` | `str` | Sí | — |
| `SHEPING` | `float` | No | ≥ 0, default `0.0` |
| `NOMBRE_CURRIER` | `str` | Sí | — |
| `VIA` | `str` | Sí | Solo `"M"` (Marítimo) o `"A"` (Aéreo); cualquier otro valor → `422` |
| `PRECIO_CURRIER` | `float` | No | ≥ 0, default `0.0` |
| `CANTIDAD` | `int` | No | > 0, default `1` |

**Respuesta `201`:**
```json
{
  "ID_FLETE": 1,
  "PROVEEDOR": "Perfumes Asia",
  "SHEPING": 150.0,
  "NOMBRE_CURRIER": "DHL Express",
  "VIA": "M",
  "PRECIO_CURRIER": 80.0,
  "CANTIDAD": 50,
  "TOTAL_FLETE": 4.6,
  "CANTIDAD_ASIGNADA": 0,
  "CANTIDAD_DISPONIBLE": 50
}
```

**Curl:**
```bash
curl -X POST http://localhost:8000/fletes/ ^
  -H "Content-Type: application/json" ^
  -d "{\"PROVEEDOR\":\"Perfumes Asia\",\"SHEPING\":150,\"NOMBRE_CURRIER\":\"DHL Express\",\"VIA\":\"M\",\"PRECIO_CURRIER\":80,\"CANTIDAD\":50}"
```

---

### `GET /fletes/`

Lista todos los fletes registrados.

**Parámetros de consulta:**

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `skip` | `int` | `0` | Registros a saltar |
| `limit` | `int` | `100` | Máximo de registros a retornar |

**Respuesta `200`:** Array de objetos Flete.

```bash
curl http://localhost:8000/fletes/
```

---

### `GET /fletes/{id_flete}`

Obtiene un flete específico por su ID.

**Respuesta `200`:** Objeto Flete.  
**Respuesta `404`:** `"Flete con ID {id} no encontrado"`

```bash
curl http://localhost:8000/fletes/1
```

---

### `PUT /fletes/{id_flete}`

Actualiza completamente un flete existente. Todos los campos son requeridos.

**Body:** Mismo formato que `POST /fletes/`.

> No se puede reducir `CANTIDAD` por debajo de la cantidad ya asignada en inventario
> (`CANTIDAD_ASIGNADA` del flete): la API responde `400` con el detalle.

**Respuesta `200`:** Objeto Flete actualizado.  
**Respuesta `404`:** `"Flete con ID {id} no encontrado"`  
**Respuesta `400`:** Error de actualización (incluye reducir `CANTIDAD` por debajo de lo asignado).

```bash
curl -X PUT http://localhost:8000/fletes/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"PROVEEDOR\":\"Perfumes Asia\",\"SHEPING\":200,\"NOMBRE_CURRIER\":\"FedEx\",\"VIA\":\"A\",\"PRECIO_CURRIER\":120,\"CANTIDAD\":50}"
```

---

### `DELETE /fletes/{id_flete}`

Elimina un flete.

**Respuesta `204`:** Sin contenido (éxito).  
**Respuesta `404`:** `"Flete con ID {id} no encontrado"`  
**Respuesta `400`:** Si el flete está referenciado por inventario.

```bash
curl -X DELETE http://localhost:8000/fletes/1
```

---

## 3. Clientes

Registra clientes de la perfumería. La **cédula** funciona como identificador primario.

### Campos del recurso

| Campo | Tipo | Descripción |
|---|---|---|
| `CEDULA` | `int` | Cédula de identidad (PK) |
| `NOMBRE` | `str` | Nombre completo |
| `CORREO` | `str \| null` | Correo electrónico |
| `TELEFONO` | `str \| null` | Número de teléfono |
| `SALDO` | `float` | Saldo del cliente. Positivo = debe la empresa; negativo = la empresa le debe a él (default `0.0`) |

---

### `POST /clientes/`

Registra un nuevo cliente. La cédula debe ser única.

**Body:**
```json
{
  "CEDULA": 12345678,
  "NOMBRE": "Juan Pérez",
  "CORREO": "juan@email.com",
  "TELEFONO": "+584121234567",
  "SALDO": 0.0
}
```

| Campo | Tipo | Requerido | Validaciones |
|---|---|---|---|
| `CEDULA` | `int` | Sí | Única (no duplicada) |
| `NOMBRE` | `str` | Sí | — |
| `CORREO` | `str` | No | — |
| `TELEFONO` | `str` | No | — |
| `SALDO` | `float` | No | Default `0.0`. Puede ser negativo. |

**Respuesta `201`:** Objeto Cliente.  
**Respuesta `400`:** `"El cliente con cédula {cedula} ya se encuentra registrado."`

```bash
curl -X POST http://localhost:8000/clientes/ ^
  -H "Content-Type: application/json" ^
  -d "{\"CEDULA\":12345678,\"NOMBRE\":\"Juan Pérez\",\"CORREO\":\"juan@email.com\",\"TELEFONO\":\"+584121234567\",\"SALDO\":0}"
```

---

### `GET /clientes/`

Lista todos los clientes.

**Parámetros de consulta:** `skip` (default `0`), `limit` (default `100`).

```bash
curl http://localhost:8000/clientes/
```

---

### `GET /clientes/{cedula}`

Obtiene un cliente por su cédula.

**Respuesta `200`:** Objeto Cliente.  
**Respuesta `404`:** `"Cliente no encontrado"`

```bash
curl http://localhost:8000/clientes/12345678
```

---

### `PUT /clientes/{cedula}`

Actualiza parcialmente un cliente. Solo se envían los campos a modificar.

**Body:**
```json
{
  "NOMBRE": "Juan Pérez García",
  "SALDO": 50.0
}
```

| Campo | Tipo | Requerido |
|---|---|---|
| `NOMBRE` | `str` | No |
| `CORREO` | `str` | No |
| `TELEFONO` | `str` | No |
| `SALDO` | `float` | No |

**Respuesta `200`:** Objeto Cliente actualizado.  
**Respuesta `404`:** `"Cliente no encontrado"`

```bash
curl -X PUT http://localhost:8000/clientes/12345678 ^
  -H "Content-Type: application/json" ^
  -d "{\"SALDO\":50.0}"
```

---

### `DELETE /clientes/{cedula}`

Elimina un cliente.

**Respuesta `204`:** Sin contenido.  
**Respuesta `404`:** `"Cliente no encontrado"`  
**Respuesta `400`:** Si el cliente está referenciado en ventas o abonos.

```bash
curl -X DELETE http://localhost:8000/clientes/12345678
```

---

## 4. Catálogo

Catálogo de productos de perfumería (nombre, marca, presentación).

### Campos del recurso

| Campo | Tipo | Descripción |
|---|---|---|
| `ID_CATALOGO` | `int` | Identificador único (auto-generado) |
| `NOMBRE` | `str` | Nombre del producto |
| `MARCA` | `str \| null` | Marca del producto |
| `PRESENTACION` | `str \| null` | Presentación (ej: "100ml", "50ml EDP") |

---

### `POST /catalogo/`

Registra un nuevo producto en el catálogo.

**Body:**
```json
{
  "NOMBRE": "Noir Elixir",
  "MARCA": "Armaf",
  "PRESENTACION": "100ml"
}
```

| Campo | Tipo | Requerido |
|---|---|---|
| `NOMBRE` | `str` | Sí |
| `MARCA` | `str` | No |
| `PRESENTACION` | `str` | No |

**Respuesta `201`:** Objeto Catálogo.

```bash
curl -X POST http://localhost:8000/catalogo/ ^
  -H "Content-Type: application/json" ^
  -d "{\"NOMBRE\":\"Noir Elixir\",\"MARCA\":\"Armaf\",\"PRESENTACION\":\"100ml\"}"
```

---

### `GET /catalogo/`

Lista todos los productos del catálogo.

**Parámetros de consulta:** `skip` (default `0`), `limit` (default `100`).

```bash
curl http://localhost:8000/catalogo/
```

---

### `GET /catalogo/{id_catalogo}`

Obtiene un producto por ID.

**Respuesta `200`:** Objeto Catálogo.  
**Respuesta `404`:** `"Producto de catálogo no encontrado"`

```bash
curl http://localhost:8000/catalogo/1
```

---

### `PUT /catalogo/{id_catalogo}`

Actualiza parcialmente un producto del catálogo.

**Body:**
```json
{
  "PRESENTACION": "100ml Eau de Parfum"
}
```

**Respuesta `200`:** Objeto Catálogo actualizado.  
**Respuesta `404`:** `"Producto de catálogo no encontrado"`

```bash
curl -X PUT http://localhost:8000/catalogo/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"PRESENTACION\":\"100ml Eau de Parfum\"}"
```

---

### `DELETE /catalogo/{id_catalogo}`

Elimina un producto del catálogo.

**Respuesta `204`:** Sin contenido.  
**Respuesta `404`:** `"Producto de catálogo no encontrado"`  
**Respuesta `400`:** Si el producto está referenciado en el inventario.

```bash
curl -X DELETE http://localhost:8000/catalogo/1
```

---

## 5. Inventario

Registra unidades de productos del catálogo en stock, con costos y precios calculados automáticamente.

### Campos del recurso

| Campo | Tipo | Descripción |
|---|---|---|
| `ID_INVENTARIO` | `int` | Identificador único (auto-generado) |
| `ID_CATALOGO` | `int` | FK → Catálogo (obligatorio) |
| `CANTIDA` | `int` | Cantidad de unidades en stock (default `0`). Las ventas la descuentan |
| `CANTIDAD_ASIGNADA` | `int` | Cantidad original comprada del flete para este producto. No cambia al vender; al crear, la API iguala `CANTIDA` a este valor |
| `ID_LOTE` | `int` | FK → Flete (obligatorio, todo producto debe tener un lote asociado) |
| `PRECIO_UNITARIO` | `float` | Precio de compra por unidad |
| `COSTO_UNITARIO` | `float \| null` | Calculado: `round(PRECIO_UNITARIO + TOTAL_FLETE, 2)` |
| `GANACIA` | `float` | Porcentaje de ganancia (ej: `33.3` para 33.3%) |
| `PRECIO_VENTA` | `float \| null` | Calculado: `round(COSTO_UNITARIO / (1 - GANACIA/100), 2)` |

---

### `POST /inventario/`

Registra un nuevo ítem en inventario. Se calculan automáticamente `COSTO_UNITARIO` y
`PRECIO_VENTA` (ambos **redondeados a 2 decimales**) y se valida el **cupo del flete**.

**Body:**
```json
{
  "ID_CATALOGO": 1,
  "CANTIDAD_ASIGNADA": 30,
  "ID_LOTE": 1,
  "PRECIO_UNITARIO": 8.50,
  "GANACIA": 33.3
}
```

| Campo | Tipo | Requerido | Validaciones |
|---|---|---|---|
| `ID_CATALOGO` | `int` | Sí | Debe existir en Catálogo |
| `CANTIDAD_ASIGNADA` | `int` | Sí (salvo que se envíe `CANTIDA`) | ≥ 0. Cantidad original comprada del flete. Si se omite, se usa `CANTIDA` (legado) como cantidad asignada |
| `CANTIDA` | `int` | No | ≥ 0, default `0`. **Legado**: solo se usa como cantidad asignada si no se envía `CANTIDAD_ASIGNADA` |
| `ID_LOTE` | `int` | Sí | Debe existir en Flete. Todo producto requiere un lote asociado |
| `PRECIO_UNITARIO` | `float` | Sí | Debe ser `> 0` |
| `GANACIA` | `float` | Sí | Debe ser `> 0` y `< 100` |

**Respuesta `201`:**
```json
{
  "ID_INVENTARIO": 1,
  "ID_CATALOGO": 1,
  "CANTIDA": 30,
  "CANTIDAD_ASIGNADA": 30,
  "ID_LOTE": 1,
  "PRECIO_UNITARIO": 8.5,
  "COSTO_UNITARIO": 13.1,
  "GANACIA": 33.3,
  "PRECIO_VENTA": 19.64
}
```

**Cálculos (con flete, redondeados a 2 decimales):**
```
COSTO_UNITARIO = round(8.50 + 4.60, 2) = 13.10
PRECIO_VENTA   = round(13.10 / (1 - 0.333), 2) = 19.64
```

**Respuesta `422`:** Si `GANACIA` no está en el rango `(0, 100)` o `PRECIO_UNITARIO <= 0`.  
**Respuesta `404`:** `"El producto de catálogo especificado no existe."`  
**Respuesta `404`:** `"El lote (FLETE) especificado no existe."`  
**Respuesta `400`:** Si la suma de `CANTIDAD_ASIGNADA` de los ítems del flete supera
`FLETE.CANTIDAD` (el `detail` indica cuánto trajo el flete, cuánto ya está asignado y
cuánto queda).

```bash
curl -X POST http://localhost:8000/inventario/ ^
  -H "Content-Type: application/json" ^
  -d "{\"ID_CATALOGO\":1,\"CANTIDAD_ASIGNADA\":30,\"ID_LOTE\":1,\"PRECIO_UNITARIO\":8.5,\"GANACIA\":33.3}"
```

---

### `GET /inventario/`

Lista todos los ítems del inventario.

**Parámetros de consulta:** `skip` (default `0`), `limit` (default `100`).

```bash
curl http://localhost:8000/inventario/
```

---

### `GET /inventario/{id_inventario}`

Obtiene un ítem del inventario por ID.

**Respuesta `200`:** Objeto Inventario.  
**Respuesta `404`:** `"Registro de inventario no encontrado."`

```bash
curl http://localhost:8000/inventario/1
```

---

### `PUT /inventario/{id_inventario}`

Actualiza un ítem del inventario. Los campos calculados (`COSTO_UNITARIO`, `PRECIO_VENTA`)
se recalculan automáticamente con los nuevos valores. `CANTIDAD_ASIGNADA` solo cambia si se
envía explícitamente (ediciones de stock no la alteran) y, en ese caso, se valida el cupo
del flete.

**Body:**
```json
{
  "PRECIO_UNITARIO": 10.00,
  "GANACIA": 40.0
}
```

| Campo | Tipo | Requerido |
|---|---|---|
| `ID_CATALOGO` | `int` | No |
| `CANTIDA` | `int` | No |
| `CANTIDAD_ASIGNADA` | `int` | No (si se envía, se valida el cupo del flete) |
| `ID_LOTE` | `int` | No |
| `PRECIO_UNITARIO` | `float` | No |
| `GANACIA` | `float` | No |

**Respuesta `200`:** Objeto Inventario recalculado.  
**Respuesta `404`:** `"Registro de inventario no encontrado."`  
**Respuesta `400`:** Si se intenta poner `ID_LOTE` como `null` (`"Todo producto de inventario debe tener un lote (FLETE) asociado."`) o si `CANTIDAD_ASIGNADA` excede el cupo del flete.

```bash
curl -X PUT http://localhost:8000/inventario/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"PRECIO_UNITARIO\":10.0,\"GANACIA\":40.0}"
```

---

### `DELETE /inventario/{id_inventario}`

Elimina un ítem del inventario.

**Respuesta `204`:** Sin contenido.  
**Respuesta `404`:** `"Registro de inventario no encontrado."`  
**Respuesta `400`:** Si el ítem está referenciado en detalles de ventas.

```bash
curl -X DELETE http://localhost:8000/inventario/1
```

---

## 6. Ventas

Registra ventas con sus detalles. El precio se calcula automáticamente y se ajusta el saldo y el stock del cliente en una sola transacción.

**Deuda previa del cliente en el monto a pagar:** el monto a pagar refleja la deuda
completa del cliente en ambos sentidos: si tiene `SALDO` negativo (la empresa le debe),
ese monto se descuenta automáticamente (`PAGO = total − crédito`, mínimo 0) y el `PRECIO`
se registra completo; si tiene `SALDO` positivo (el cliente debe), se suma la deuda
(`PAGO = total + deuda`), lo que en una venta de Contado liquida toda la deuda previa. La
API ajusta `SALDO += PRECIO − PAGO`, que consume el crédito o cobra la deuda sin lógica
adicional; el sobrante (si el crédito supera el total) sigue a favor del cliente.

Cada **detalle (línea) de la venta admite un `PRECIO_UNITARIO` propio**. Si se omite, la API usa el `PRECIO_VENTA` del inventario; si se envía, se guarda en la línea y se usa para calcular el subtotal de ese ítem. Esto permite, por ejemplo, modificar el subtotal de cada elemento de un combo por separado.

### Campos del recurso

| Campo | Tipo | Descripción |
|---|---|---|
| `ID_VENTA` | `int` | Identificador único (auto-generado) |
| `FECHA` | `date \| null` | Fecha de la venta (default: hoy) |
| `CEDULA` | `int` | FK → Cliente |
| `PRECIO` | `float` | Total de la venta (calculado o manual) |
| `TIPO_PAGO` | `str` | Ej: `CONTADO`, `CREDITO` |
| `FORMA_DE_PAGO` | `str` | Ej: `EFECTIVO`, `TRANSFERENCIA`, `TARJETA` |
| `PAGO` | `float` | Monto pagado por el cliente (≥ 0) |
| `NOMBRE_CLIENTE` | `str \| null` | Nombre del cliente (solo lectura, en respuesta) |
| `detalles` | `array` | Lista de productos vendidos |

### Detalle de venta

| Campo | Tipo | Descripción |
|---|---|---|
| `ID_DETALLE` | `int` | Identificador único |
| `ID_INVENTARIO` | `int` | FK → Inventario |
| `CANTIDAD` | `int` | Cantidad vendida (> 0) |
| `NOMBRE_PRODUCTO` | `str \| null` | Nombre del producto (respuesta) |
| `PRECIO_UNITARIO` | `float \| null` | Precio de venta de la línea. **En envío es opcional**: si se omite se usa `INVENTARIO.PRECIO_VENTA`; si se envía se guarda tal cual (respuesta) |
| `SUBTOTAL` | `float \| null` | `PRECIO_UNITARIO × CANTIDAD` (respuesta) |

---

### `POST /ventas/`

Registra una venta. Si se omite `PRECIO`, se calcula como la suma de los subtotales de los detalles. La operación es **atómica**: valida cliente, stock y precios; descuenta el stock; y ajusta `SALDO += PRECIO − PAGO`. Si algo falla, no queda nada guardado.

**Body:**
```json
{
  "CEDULA": 12345678,
  "FECHA": "2026-08-04",
  "TIPO_PAGO": "CREDITO",
  "FORMA_DE_PAGO": "EFECTIVO",
  "PAGO": 50.00,
  "detalles": [
    { "ID_INVENTARIO": 1, "CANTIDAD": 2, "PRECIO_UNITARIO": 19.64 },
    { "ID_INVENTARIO": 2, "CANTIDAD": 3 }
  ]
}
```

| Campo | Tipo | Requerido | Validaciones |
|---|---|---|---|
| `CEDULA` | `int` | Sí | Debe existir en Cliente |
| `FECHA` | `date` | No | Default: hoy |
| `TIPO_PAGO` | `str` | Sí | — |
| `FORMA_DE_PAGO` | `str` | Sí | — |
| `PAGO` | `float` | No | ≥ 0, default `0.0` |
| `PRECIO` | `float` | No | ≥ 0. Si se omite, se calcula automáticamente |
| `detalles` | `array` | Sí | Mínimo 1 ítem; cada `CANTIDAD` debe ser `> 0` y no superar el stock |

Cada elemento de `detalles` acepta:

| Campo | Tipo | Requerido | Validaciones |
|---|---|---|---|
| `ID_INVENTARIO` | `int` | Sí | Debe existir en Inventario |
| `CANTIDAD` | `int` | Sí | `> 0` y `≤` stock disponible |
| `PRECIO_UNITARIO` | `float` | No | `≥ 0`. Si se omite, se usa `INVENTARIO.PRECIO_VENTA` |

> El subtotal de cada línea se calcula como `PRECIO_UNITARIO × CANTIDAD`, permitiendo precios
> distintos por elemento (por ejemplo, en un combo). Si `PRECIO` no se envía, la API lo
> calcula sumando los subtotales de las líneas.

**Respuesta `201`:** Objeto Venta con detalles.

**Respuesta `404`:** `"El cliente especificado no existe."` o `"El inventario con ID {id} no existe."`  
**Respuesta `400`:** `"Stock insuficiente para el producto de inventario ID {id}. Disponible: X, solicitado: Y."` o error de la transacción.

```bash
curl -X POST http://localhost:8000/ventas/ ^
  -H "Content-Type: application/json" ^
  -d "{\"CEDULA\":12345678,\"TIPO_PAGO\":\"CREDITO\",\"FORMA_DE_PAGO\":\"EFECTIVO\",\"PAGO\":50,\"detalles\":[{\"ID_INVENTARIO\":1,\"CANTIDAD\":2}]}"
```

---

### `GET /ventas/`

Lista las ventas (de la más reciente a la más antigua).

**Parámetros de consulta:** `cedula` (opcional, filtra por cliente), `skip` (default `0`), `limit` (default `100`).

**Respuesta `200`:** Array de objetos Venta con sus detalles.

```bash
curl http://localhost:8000/ventas/
curl "http://localhost:8000/ventas/?cedula=12345678"
```

---

### `GET /ventas/{id_venta}`

Obtiene una venta por ID, con los detalles (nombre y precio del producto).

**Respuesta `200`:** Objeto Venta.  
**Respuesta `404`:** `"Venta no encontrada"`

```bash
curl http://localhost:8000/ventas/1
```

---

### `PUT /ventas/{id_venta}`

Edita una venta completa (encabezado **y** productos). La operación es **atómica**: revierte el stock y el saldo originales, valida y aplica los nuevos valores. Se permite cambiar el cliente.

**Body:** Mismo formato que `POST /ventas/` (actualización completa):

```json
{
  "CEDULA": 29845213,
  "FECHA": "2026-08-05",
  "TIPO_PAGO": "CONTADO",
  "FORMA_DE_PAGO": "TRANSFERENCIA",
  "PAGO": 100.00,
  "PRECIO": 106.84,
  "detalles": [
    { "ID_INVENTARIO": 5, "CANTIDAD": 1, "PRECIO_UNITARIO": 30.00 },
    { "ID_INVENTARIO": 6, "CANTIDAD": 1 }
  ]
}
```

- `PRECIO` es opcional: si se omite, se recalcula como la suma de los subtotales.
- Cada detalle acepta `PRECIO_UNITARIO` opcional (≥ 0); si se omite, se usa `INVENTARIO.PRECIO_VENTA`. El `SUBTOTAL` de la línea es `PRECIO_UNITARIO × CANTIDAD`, por lo que se puede modificar el subtotal de cada elemento de un combo por separado.
- Si se cambia el `CEDULA`, el saldo se revierte al cliente original y se aplica al nuevo.
- Si el stock es insuficiente para algún detalle, la operación falla con `400` y **no cambia nada** (rollback).

**Respuesta `200`:** Objeto Venta actualizado.  
**Respuesta `404`:** `"Venta no encontrada"` o `"El cliente especificado no existe."` / `"El inventario con ID X no existe."`  
**Respuesta `400`:** Stock insuficiente o error de la transacción.

```bash
curl -X PUT http://localhost:8000/ventas/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"CEDULA\":29845213,\"TIPO_PAGO\":\"CONTADO\",\"FORMA_DE_PAGO\":\"TRANSFERENCIA\",\"PAGO\":100,\"detalles\":[{\"ID_INVENTARIO\":5,\"CANTIDAD\":1}]}"
```

---

### `DELETE /ventas/{id_venta}`

Elimina una venta y sus detalles. **Revierte el stock** (devuelve las cantidades al inventario) y **revierte el saldo** del cliente.

**Respuesta `204`:** Sin contenido.  
**Respuesta `404`:** `"Venta no encontrada"`  
**Respuesta `400`:** Error al eliminar.

```bash
curl -X DELETE http://localhost:8000/ventas/1
```

---

## 7. Abonos

Los **abonos** registran los pagos que un cliente hace para saldar su deuda. Cada
abono **reduce el SALDO del cliente** (`SALDO -= CANTIDAD`): si supera la deuda,
el excedente queda como saldo a favor (SALDO negativo). Un abono no está ligado a
una venta específica; se aplica a la cuenta del cliente.

### Campos del recurso

| Campo | Tipo | Descripción |
|---|---|---|
| `ID_ABONO` | `int` | Identificador único (autoincremental) |
| `FECHA` | `date` | Fecha del abono (por defecto el día actual) |
| `CEDULA` | `int` | Cédula del cliente que realiza el pago |
| `CANTIDAD` | `float` | Monto del abono (debe ser mayor a cero) |
| `NOMBRE_CLIENTE` | `str \| null` | Nombre del cliente (solo lectura, resuelto por la API) |

### `POST /abonos/`

Registra un abono y reduce el saldo del cliente.

**Body:**

```json
{
  "FECHA": "2026-08-04",
  "CEDULA": 12345678,
  "CANTIDAD": 50.0
}
```

`FECHA` es opcional (si se omite se usa la fecha actual).

**Respuesta `201`:** El abono creado (con `NOMBRE_CLIENTE`).  
**Respuesta `422`:** `CANTIDAD` no es mayor a cero.  
**Respuesta `404`:** `"El cliente especificado no existe."`  
**Respuesta `400`:** Error al registrar.

```bash
curl -X POST http://localhost:8000/abonos/ ^
  -H "Content-Type: application/json" ^
  -d "{\"CEDULA\":12345678,\"CANTIDAD\":50.0}"
```

### `GET /abonos/`

Lista los abonos. Puede filtrarse por cliente con el parámetro de consulta `cedula`.

```bash
curl "http://localhost:8000/abonos/?cedula=12345678"
```

### `GET /abonos/{id_abono}`

Obtiene un abono por su ID.  
**Respuesta `404`:** `"Abono no encontrado"`.

### `PUT /abonos/{id_abono}`

Actualiza un abono (parcial o completo). **Revierte el efecto del abono original en
el SALDO** y aplica el nuevo valor (y/o nuevo cliente). Los campos `FECHA`, `CEDULA`
y `CANTIDAD` son opcionales; solo se actualizan los enviados.

**Respuesta `200`:** El abono actualizado.  
**Respuesta `404`:** Abono no encontrado, o cliente nuevo inexistente.

```bash
curl -X PUT http://localhost:8000/abonos/1 ^
  -H "Content-Type: application/json" ^
  -d "{\"CANTIDAD\":40.0}"
```

### `DELETE /abonos/{id_abono}`

Elimina un abono y **revierte su efecto en el SALDO** del cliente (`SALDO += CANTIDAD`).

**Respuesta `204`:** Sin contenido.  
**Respuesta `404`:** `"Abono no encontrado"`.

```bash
curl -X DELETE http://localhost:8000/abonos/1
```

---

## 8. Códigos de error

| Código | Significado |
|---|---|
| `200` | Operación exitosa |
| `201` | Recurso creado exitosamente |
| `204` | Eliminación exitosa (sin contenido) |
| `400` | Solicitud inválida (datos faltantes, formato incorrecto, violación de regla de negocio) |
| `404` | Recurso no encontrado |
| `500` | Error interno del servidor |

Todos los errores devuelven un JSON con la clave `detail`:
```json
{
  "detail": "Descripción del error"
}
```
