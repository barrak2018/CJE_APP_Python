# CJE Perfumes — Flujo de datos y procesos

---

## Tabla de contenidos

1. [Arquitectura general](#1-arquitectura-general)
2. [Esquema de base de datos](#2-esquema-de-base-de-datos)
3. [Proceso de Fletes](#3-proceso-de-fletes)
4. [Proceso de Clientes](#4-proceso-de-clientes)
5. [Proceso de Catálogo](#5-proceso-de-católogo)
6. [Proceso de Inventario](#6-proceso-de-inventario)
7. [Proceso de Ventas](#7-proceso-de-ventas)
8. [Proceso de Abonos](#8-proceso-de-abonos)
9. [Relaciones entre entidades](#9-relaciones-entre-entidades)

---

## 1. Arquitectura general

```
┌─────────────┐       HTTP/JSON        ┌──────────────┐       SQL         ┌────────────┐
│  cje_gui/   │ ───────────────────▶   │   cje_api/   │ ─────────────▶   │ PostgreSQL │
│  (PySide6)  │ ◀───────────────────   │  (FastAPI)   │ ◀─────────────   │  (CJE DB)  │
│   Desktop   │     Respuestas JSON    │  SQLAlchemy  │   Resultados     │            │
└─────────────┘                        └──────────────┘                   └────────────┘
```

**Capas:**

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Presentación | PySide6 (Qt) | GUI de escritorio con 6 módulos CRUD (Fletes, Catálogo, Inventario, Clientes, Ventas, Abonos) |
| API | FastAPI + SQLAlchemy | Validación, lógica de negocio, cálculos |
| Persistencia | PostgreSQL 14+ | Almacenamiento, integridad referencial, columnas calculadas |

---

## 2. Esquema de base de datos

### Diagrama de entidades

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   CLIENTE    │       │    FLETE     │       │   CATALOGO   │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ CEDULA (PK)  │       │ ID_FLETE(PK) │       │ ID_CATALOGO  │
│ NOMBRE       │       │ PROVEEDOR    │       │    (PK)      │
│ CORREO       │       │ SHEPING      │       │ NOMBRE       │
│ TELEFONO     │       │ NOMBRE_CURR. │       │ MARCA        │
│ SALDO        │       │ VIA          │       │ PRESENTACION │
└──────┬───────┘       │ PRECIO_CURR. │       └──────┬───────┘
       │               │ CANTIDAD     │              │
       │               │ TOTAL_FLETE* │              │
       │               └──────┬───────┘              │
       │                      │                      │
       │                      │ FK                   │ FK
       │               ┌──────▼──────────────────────▼───────┐
       │               │            INVENTARIO               │
       │               ├─────────────────────────────────────┤
│               │ ID_INVENTARIO (PK)                  │
│               │ ID_CATALOGO  ──── FK → CATALOGO     │
│               │ ID_LOTE      ──── FK → FLETE        │
│               │ CANTIDA                              │
       │               │ PRECIO_UNITARIO                      │
       │               │ COSTO_UNITARIO (calculado*)          │
       │               │ GANACIA                              │
       │               │ PRECIO_VENTA   (calculado*)          │
       │               └─────────────────────────────────────┘
       │
       │ FK
┌──────▼────────┐       ┌──────────────────┐
│    VENTAS     │       │    ABONOS        │
├───────────────┤       ├──────────────────┤
│ ID_VENTA (PK) │       │ ID_ABONO (PK)    │
│ FECHA         │       │ FECHA            │
│ CEDULA ──FK──▶│       │ CEDULA ──FK──▶   │
│ PRECIO        │       │ CANTIDAD         │
│ TIPO_PAGO     │       └──────────────────┘
│ FORMA_DE_PAGO │
│ PAGO          │       ┌──────────────────┐
└───────┬───────┘       │ DETALLES_VENTAS  │
        │ FK            ├──────────────────┤
        └──────────────▶│ ID_DETALLE (PK)  │
                        │ ID_VENTA ──FK──▶ │
                        │ ID_INVENTARIO    │
                        │    ──FK──▶       │
                        │ CANTIDAD         │
                        │ PRECIO_UNITARIO* │
                        └──────────────────┘
```

### Campos calculados (no editables)

| Campo | Tabla | Fórmula |
|---|---|---|
| `TOTAL_FLETE` | FLETE | `(SHEPING + PRECIO_CURRIER) / NULLIF(CANTIDAD, 0)` (columna STORED, `real`) |
| `COSTO_UNITARIO` | INVENTARIO | `round(PRECIO_UNITARIO + TOTAL_FLETE_del_lote, 2)` |
| `PRECIO_VENTA` | INVENTARIO | `round(COSTO_UNITARIO / (1 - GANACIA/100), 2)` |

> **Precios en centavos:** `COSTO_UNITARIO` y `PRECIO_VENTA` los calcula la **API** (no la
> BD) y se **redondean a 2 decimales**. Así el precio mostrado ($30.00) coincide con el
> multiplicado en ventas ($30.00 × 2 = $60.00, nunca $59.99 por decimales largos).

> **`DETALLES_VENTAS.PRECIO_UNITARIO`** (marcado con `*`): es **opcional**. Si la línea trae un
> valor, ese es el precio unitario de la venta y el subtotal es `PRECIO_UNITARIO × CANTIDAD`.
> Si está en `NULL`, la API usa `INVENTARIO.PRECIO_VENTA` como respaldo. Permite fijar precios
> distintos por línea (ej. modificar el subtotal de cada elemento de un combo).

---

## 3. Proceso de Fletes

### Crear Flete

```
1. Cliente envía POST /fletes/ con JSON
2. FastAPI recibe y valida con FleteCreate (Pydantic)
   - VIA debe ser exactamente 'M' o 'A' (pattern ^[MA]$); otro valor → 422
   - CANTIDAD debe ser > 0
3. Se crea el objeto FleteModel con los campos recibidos
4. SQLAlchemy genera INSERT a PostgreSQL
5. PostgreSQL asigna ID_FLETE (auto-incremental)
6. PostgreSQL calcula TOTAL_FLETE automáticamente (columna STORED)
7. Se retorna el objeto completo con TOTAL_FLETE calculado
```

### Consultar Fletes

```
1. GET /fletes/  →  SELECT * FROM FLETE OFFSET skip LIMIT limit
2. GET /fletes/{id}  →  SELECT * FROM FLETE WHERE ID_FLETE = id
3. Se serializa con FleteResponse y se retorna
```

### Actualizar Flete

```
1. PUT /fletes/{id} con JSON completo (todos los campos requeridos)
2. Se busca el registro por ID_FLETE
3. Se actualizan todos los campos con los nuevos valores
4. PostgreSQL recalcula TOTAL_FLETE automáticamente al modificar SHEPING, PRECIO_CURRIER o CANTIDAD
5. Se retorna el objeto actualizado
```

### Eliminar Flete

```
1. DELETE /fletes/{id}
2. Se busca el registro por ID_FLETE
3. PostgreSQL intenta DELETE
4. Si existe FK constraint (INVENTARIO.ID_LOTE → FLETE.ID_FLETE), la eliminación falla
5. Se retorna 400 con mensaje de error referencial
```

---

## 4. Proceso de Clientes

### Crear Cliente

```
1. Cliente envía POST /clientes/ con JSON
2. FastAPI valida con ClienteCreate
3. Se verifica si ya existe un cliente con esa CEDULA
   - Si existe → retorna 400: "El cliente con cédula X ya se encuentra registrado."
   - Si no existe → continúa
4. Se ejecuta INSERT en tabla CLIENTE
5. Se retorna el objeto creado
```

### Consultar Clientes

```
1. GET /clientes/  →  SELECT * FROM CLIENTE OFFSET skip LIMIT limit
2. GET /clientes/{cedula}  →  SELECT * FROM CLIENTE WHERE CEDULA = cedula
```

### Actualizar Cliente

```
1. PUT /clientes/{cedula} con JSON (campos opcionales)
2. Se busca por CEDULA (PK)
3. Se aplican solo los campos enviados (model_dump(exclude_unset=True))
4. Los campos no enviados mantienen su valor actual
```

### Eliminar Cliente

```
1. DELETE /clientes/{cedula}
2. Se busca por CEDULA
3. Se ejecuta DELETE
4. Si tiene ventas o abonos asociados, falla por FK constraint → retorna 400
```

---

## 5. Proceso de Catálogo

### Crear Producto

```
1. POST /catalogo/ con JSON
2. Valida con CatalogoCreate
3. INSERT en tabla CATALOGO
4. PostgreSQL asigna ID_CATALOGO (auto-incremental)
5. Retorna objeto con ID asignado
```

### Consultar / Actualizar / Eliminar

Proceso estándar CRUD. El DELETE retorna `400` si el producto está referenciado en INVENTARIO.

---

## 6. Proceso de Inventario

Este es el módulo más complejo porque combina validación de FKs y cálculos automáticos.

### Crear Ítem de Inventario

```
1. Cliente envía POST /inventario/ con JSON
2. FastAPI valida con InventarioCreate
3. ┌─── VALIDACIÓN DE CATÁLOGO ───────────────────────────┐
   │ Se busca ID_CATALOGO en tabla CATALOGO                │
   │ Si no existe → 404: "El producto de catálogo          │
   │                     especificado no existe."          │
   └───────────────────────────────────────────────────────┘
4. ┌─── CÁLCULO DE PRECIOS ───────────────────────────────┐
   │                                                       │
   │  ID_LOTE es obligatorio (regla de negocio):           │
   │    a. Se busca el FLETE por ID_FLETE                  │
   │    b. Se obtiene TOTAL_FLETE del lote                 │
   │    c. Si el lote no existe → 404                      │
   │                                                       │
   │  COSTO_UNITARIO = round(PRECIO_UNITARIO + total_flete, 2) │
   │                                                       │
   │  Si GANACIA no está en el rango (0, 100) → 422         │
   │    (validación del schema, antes de la lógica)          │
   │                                                       │
   │  PRECIO_VENTA = round(COSTO_UNITARIO / (1 - GANACIA/100), 2) │
   │                                                       │
   └───────────────────────────────────────────────────────┘
5. Se crea el registro con COSTO_UNITARIO y PRECIO_VENTA pre-calculados
6. INSERT en tabla INVENTARIO
7. Retorna objeto completo con campos calculados
```

### Ejemplo numérico del cálculo

```
Datos de entrada:
  PRECIO_UNITARIO = 8.50
  ID_LOTE = 1  →  TOTAL_FLETE del lote = 4.60
  GANACIA = 33.3  (33.3%)

Cálculos (redondeados a 2 decimales):
  COSTO_UNITARIO = round(8.50 + 4.60, 2)   = 13.10
  PRECIO_VENTA   = round(13.10 / 0.667, 2) = 19.64
```

### Actualizar Ítem de Inventario

```
1. PUT /inventario/{id} con JSON (campos opcionales)
2. Se busca por ID_INVENTARIO
3. Si se envía "ID_LOTE": null → 400 (el lote es obligatorio, no puede quedar sin lote)
4. Se aplican los campos enviados
5. Se RECALCULAN automáticamente COSTO_UNITARIO y PRECIO_VENTA
   usando los valores actualizados (posiblemente mezclando
   valores nuevos con los que ya estaban en el registro)
6. Se ejecuta UPDATE
```

### Eliminar Ítem de Inventario

```
1. DELETE /inventario/{id}
2. Se busca por ID_INVENTARIO
3. DELETE directo
4. Si está referenciado en DETALLES_VENTAS, falla por FK → retorna 400
```

---

## 7. Proceso de Ventas

Módulo que combina validación de cliente, stock, cálculo de precios y ajuste de saldo en una **única transacción**.

### Crear Venta

```
1. POST /ventas/ con JSON (cliente, tipo/forma de pago, monto pagado y detalles)
2. Se valida que el cliente exista por CEDULA → si no → 404
3. ┌─── VALIDACIÓN DE DETALLES ─────────────────────────┐
   │ Para cada detalle:                                  │
   │   a. Se busca ID_INVENTARIO → si no existe → 404    │
   │   b. CANTIDAD > 0 (validación del schema → 422)     │
   │   c. CANTIDAD ≤ stock (CANTIDA) → si no → 400       │
   │   d. precio_unitario = PRECIO_UNITARIO de la línea   │
   │      si lo trae; si no, PRECIO_VENTA del inventario  │
   │   e. precio_calculado += precio_unitario × CANTIDAD  │
   └─────────────────────────────────────────────────────┘
4. PRECIO final:
   - Si se envió "PRECIO" → se usa ese valor (override manual)
   - Si se omitió → se usa el precio_calculado
5. Se inserta la VENTA (FECHA default hoy)
6. Por cada detalle: se inserta en DETALLES_VENTAS
   y se descuenta el stock: INVENTARIO.CANTIDA -= CANTIDAD
7. Se ajusta el saldo del cliente:
   CLIENTE.SALDO += (PRECIO − PAGO)
   - Pago exacto  → saldo sin cambios
   - Pago menor   → saldo positivo (cliente debe)
   - Pago mayor   → saldo negativo (crédito a favor del cliente)
   El PRECIO se registra completo; la deuda previa del cliente se refleja en el "PAGO"
   enviado por la interfaz: si el saldo es negativo (la empresa le debe) se descuenta
   ("monto a pagar = total − crédito"); si es positivo (el cliente debe) se suma
   ("monto a pagar = total + deuda"). La fórmula consume el crédito o cobra la deuda sin
   tocar el saldo por separado: ej. saldo −50 + (100 − 50) = 0, o saldo 75 + (100 − 175) = 0.
8. COMMIT → todo se guarda junto
   Si algo falla en cualquier paso → ROLLBACK (nada se guarda)
```

### Editar Venta (actualización atómica)

```
1. PUT /ventas/{id} con JSON (cliente, tipo/forma de pago, monto pagado, detalles,
   PRECIO opcional = override manual)
2. Se busca la venta por ID_VENTA → si no → 404
3. Se REVIERTE la venta original (como Eliminar):
   - Por cada detalle original: INVENTARIO.CANTIDA += CANTIDAD (devuelve stock)
   - CLIENTE.SALDO -= (PRECIO − PAGO) originales (revierte saldo)
4. Se valida el NUEVO cliente por CEDULA → si no → 404
5. ┌─── VALIDACIÓN DE DETALLES NUEVOS ────────────────────┐
   │ Para cada detalle:                                    │
   │   a. Se busca ID_INVENTARIO → si no existe → 404      │
   │   b. CANTIDAD > 0 (validación del schema → 422)       │
   │   c. CANTIDAD ≤ stock (CANTIDA) → si no → 400         │
   │   d. precio_unitario = PRECIO_UNITARIO de la línea     │
   │      si lo trae; si no, PRECIO_VENTA del inventario    │
   │   e. precio_calculado += precio_unitario × CANTIDAD    │
   └───────────────────────────────────────────────────────┘
6. PRECIO final:
   - Si se envió "PRECIO" → se usa ese valor (override manual)
   - Si se omitió → se usa el precio_calculado
7. Se actualiza la VENTA (cliente, fechas de pago, PRECIO)
8. Se borran los DETALLES_VENTAS originales y se insertan los nuevos,
   descontando el stock: INVENTARIO.CANTIDA -= CANTIDAD
9. Se ajusta el saldo del cliente (nuevo, que puede ser otro):
   CLIENTE.SALDO += (PRECIO − PAGO) nuevos
10. COMMIT → todo se guarda junto
    Si algo falla en cualquier paso → ROLLBACK (nada cambia)
```

### Consultar Ventas

```
1. GET /ventas/  →  SELECT * FROM VENTAS ORDER BY ID_VENTA DESC OFFSET skip LIMIT limit
2. GET /ventas/{id}  →  SELECT * FROM VENTAS WHERE ID_VENTA = id
3. Se enriquecen los detalles con el nombre del producto (CATALOGO)
   y el precio unitario (PRECIO_UNITARIO de la línea; si es NULL,
   se usa INVENTARIO.PRECIO_VENTA). El subtotal es precio_unitario × CANTIDAD
4. Se incluye NOMBRE_CLIENTE a partir de la tabla CLIENTE
```

### Eliminar Venta (reversión)

```
1. DELETE /ventas/{id}
2. Se busca la venta por ID_VENTA → si no → 404
3. Por cada detalle: se DEVUELVE el stock:
   INVENTARIO.CANTIDA += CANTIDAD
4. Se revierte el saldo del cliente:
   CLIENTE.SALDO -= (PRECIO − PAGO)
5. Se eliminan los DETALLES_VENTAS y la VENTA
6. COMMIT
```

---

## 8. Proceso de Abonos

Los **abonos** son pagos que el cliente hace sobre su cuenta. No están ligados a una
venta específica: se aplican al SALDO global del cliente.

### Crear Abono

```
1. POST /abonos/
2. Se valida CANTIDAD > 0 → si no → 422
3. Se busca el cliente por CEDULA → si no → 404
4. Se inserta en ABONOS (FECHA usa la fecha actual si no se envía)
5. Se reduce la deuda:  CLIENTE.SALDO -= CANTIDAD
6. COMMIT
```

Si `CANTIDAD` supera la deuda, `SALDO` puede quedar negativo (saldo a favor del cliente);
no se impide ese excedente.

### Consultar Abonos

```
1. GET /abonos/  →  SELECT * FROM ABONOS  (con filtro opcional ?cedula=)
2. GET /abonos/{id}  →  SELECT * FROM ABONOS WHERE ID_ABONO = id
3. Se incluye NOMBRE_CLIENTE a partir de la tabla CLIENTE
```

### Editar Abono (reversión + nueva aplicación)

```
1. PUT /abonos/{id}
2. Se busca el abono por ID_ABONO → si no → 404
3. Se revierte el efecto del abono original:
   CLIENTE.SALDO += CANTIDAD_original  (en la cédula original)
4. Se aplica el nuevo valor/cliente (si cambió la cédula, se aplica al nuevo cliente;
   si el cliente nuevo no existe → 404)
5. Se actualizan los campos enviados (FECHA, CEDULA, CANTIDAD parcial o completo)
   CLIENTE.SALDO -= CANTIDAD_nueva  (en la cédula final)
6. COMMIT
```

### Eliminar Abono (reversión)

```
1. DELETE /abonos/{id}
2. Se busca el abono por ID_ABONO → si no → 404
3. Se revierte el efecto:
   CLIENTE.SALDO += CANTIDAD
4. Se elimina el abono
5. COMMIT
```

---

## 9. Relaciones entre entidades

### Grafo de dependencias

```
FLETE ──────┬──▶ INVENTARIO ◀────── CATALOGO
            │        │
            │        ▼
            │    DETALLES_VENTAS ◀─── VENTAS ◀────── CLIENTE ────▶ ABONOS
            │
            └── (referenciado por INVENTARIO.ID_LOTE)
```

### Orden de creación recomendado

Para respetar las FK al cargar datos:

1. **CLIENTE** — Sin dependencias
2. **FLETE** — Sin dependencias
3. **CATALOGO** — Sin dependencias
4. **INVENTARIO** — Depende de CATALOGO y FLETE
5. **VENTAS** — Depende de CLIENTE
6. **DETALLES_VENTAS** — Depende de VENTAS e INVENTARIO
7. **ABONOS** — Depende de CLIENTE

> **Nota:** todo ítem de inventario requiere un `ID_LOTE` (flete) asociado.

### Restricciones de integridad

| FK | Tabla origen | Tabla destino | Acción |
|---|---|---|---|
| `FK_INVENTARIO_CATALOGO` | INVENTARIO | CATALOGO | RESTRICT (impide DELETE de CATALOGO si tiene inventario) |
| `FK_INVENTARIO_FLETE` | INVENTARIO | FLETE | RESTRICT (impide DELETE de FLETE si tiene inventario) |
| `FK_VENTAS_CLIENTE` | VENTAS | CLIENTE | RESTRICT |
| `FK_DETALLES_VENTA` | DETALLES_VENTAS | VENTAS | RESTRICT |
| `FK_DETALLES_INVENTARIO` | DETALLES_VENTAS | INVENTARIO | RESTRICT |
| `FK_ABONOS_CLIENTE` | ABONOS | CLIENTE | RESTRICT |
