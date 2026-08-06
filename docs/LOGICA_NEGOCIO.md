# Lógica de Negocio

## Conceptos básicos

- **Venta**: un registro que indica qué vendiste, a quién, por cuánto y cuánto te pagaron.
- **Detalle de venta**: cada producto que compró el cliente dentro de una venta.
- **Saldo del cliente**: cuánto te debe el cliente a ti (o tú a él).

## Inventario

1. **Todo producto debe tener un lote (flete) asociado.** No se puede crear ni guardar inventario sin lote. Si ya existe un inventario y se intenta quitar su lote, la operación se rechaza.

## Reglas al registrar una venta

1. **El cliente debe existir.** No se puede vender a alguien que no esté registrado en Clientes.

2. **Se validan los productos y su stock.**
   - Cada producto debe existir en el inventario.
   - La cantidad vendida no puede superar el stock disponible.
   - Si falta stock, la venta se rechaza por completo (nada se guarda a medias).

3. **El precio se calcula solo.**
   - **Los precios y costos son monetarios: se redondean a 2 decimales (centavos).**
     `PRECIO_VENTA = round(costo / (1 − ganancia), 2)` y el costo incluye el flete
     redondeado a centavos. Así `$30.00 × 2 = $60.00` (nunca `$59.99` por decimales largos).
   - Cada línea del detalle tiene su propio precio: se usa el **precio unitario de la línea**
     si lo tiene, o el **precio de venta** del inventario si no.
   - Subtotal de la línea = precio unitario × cantidad. Esto permite **modificar el subtotal
     de cada elemento de un combo por separado** (al editarlo se recalcula el precio unitario
     de la línea: `subtotal ÷ cantidad`, redondeado a 2 decimales). La **cantidad de cada
     línea también es editable** (doble clic): al cambiarla se recalcula el subtotal
     (`precio unitario × cantidad`); debe ser un entero ≥ 1 y nunca superar el stock
     disponible.
   - Precio total = suma de los subtotales de las líneas.
   - Si lo deseas, puedes escribir un **precio manual** que sustituya al cálculo automático.

4. **El saldo se ajusta según lo pagado.**
   - Si el cliente paga **exactamente** el precio → no debe nada (saldo sin cambios).
   - Si paga **menos** → el saldo del cliente aumenta (te queda debiendo).
   - Si paga **más** → el saldo baja e incluso puede quedar en negativo (tú le debes a favor del cliente).

5. **La deuda previa del cliente se refleja en el monto a pagar.**
   - **monto a pagar = total de la venta + SALDO previo del cliente** (mínimo 0). Refleja
     la deuda completa en ambos sentidos:
   - `SALDO` negativo (la empresa le debe) → **descuento**: se aplica como parte del pago
     (`total − crédito`). El **PRECIO registrado no cambia** (se guarda el precio completo);
     el crédito actúa como pago del cliente.
   - `SALDO` positivo (el cliente debe) → **cargo**: se suma la deuda completa al monto a
     pagar (`total + deuda`). En una venta de Contado esto **liquida toda la deuda previa**
     en una sola operación.
   - Ejemplo (descuento): la empresa le debía $50 al cliente y compra un producto de $100 →
     paga $50 y su saldo queda en $0 (`−50 + (100 − 50) = 0`).
   - Ejemplo (cargo): el cliente debe $75 y compra un producto de $100 → paga $175 y su
     saldo queda en $0 (`75 + (100 − 175) = 0`).
   - Si el crédito supera el precio (ej. saldo −$200 y compra de $100) se aplica hasta
     $100 y el sobrante sigue a favor del cliente (`−200 + (100 − 100) = −100`).
   - La fórmula `SALDO += PRECIO − PAGO` consume el crédito o cobra la deuda
     automáticamente sin tocar el saldo por separado.

6. **Todo se guarda al mismo tiempo (transacción).** Si falla cualquier paso, no queda nada guardado.

7. **El stock se descuenta automáticamente** al vender.

## Al eliminar una venta

- Se borran la venta y sus detalles.
- El **stock se devuelve** al inventario (cada cantidad vuelve a sumarse).
- El **saldo se revierte** (se deshace el ajuste que hizo la venta).

## Abonos (pagos de deudas)

- Un **abono** es un pago que el cliente hace hacia su cuenta: `SALDO -= CANTIDAD`.
- No está ligado a una venta específica; se aplica al saldo global del cliente.
- La **cantidad debe ser mayor a cero**.
- Si el abono supera la deuda, el excedente queda como **saldo a favor** (`SALDO` negativo);
  no se impide el excedente.
- Al **editar** un abono, primero se revierte su efecto original y luego se aplica el nuevo
  valor (o cliente). Al **eliminarlo**, solo se revierte (`SALDO += CANTIDAD`).
- La fecha es opcional: si no se indica, se usa la fecha actual.

## Formulario de venta (GUI)

- Busca el **cliente** por cédula, nombre o correo en la barra de búsqueda y elige la
  opción del desplegable (debe seleccionarse un cliente registrado; no basta con escribir
  el texto). Luego la **fecha**.
- Elige **tipo de pago** (Contado o Crédito) y **forma de pago** (Efectivo, Transferencia, etc.).
- Escribe el **monto pagado** (puede ser 0 si es a crédito). La ventana muestra el
  **Crédito a favor** (si la empresa le debe al cliente) y el **Monto a pagar** =
  `total + deuda previa` (mínimo 0): **descuento** si el saldo es negativo, **cargo** si
  es positivo. En Contado el monto pagado se fija a ese valor automáticamente (una venta
  de contado liquida la deuda previa completa); en Crédito es solo una sugerencia (si
  pagas de más, el excedente queda a favor del cliente).
- Agrega los **productos** con su cantidad. La columna **Cantidad** de cada producto es
  editable (doble clic): al cambiarla se recalcula el subtotal de la línea (precio unitario
  × cantidad) y el total. Debe ser un entero ≥ 1 sin superar el stock (en edición, el tope
  incluye la cantidad ya reservada por esa misma venta); si es inválida, se revierte.
- La columna **Subtotal** de cada producto también es editable: al modificarla, el precio
  unitario de esa línea se ajusta (subtotal ÷ cantidad) y el total se recalcula. Así puedes
  fijar el subtotal de cada elemento de un combo por separado. El campo "Total de la venta"
  muestra el **precio sugerido** como texto de ayuda (placeholder).
- Deja el total **vacío** para usar el precio calculado automáticamente, o **escríbelo** para usarlo como precio manual.
- Guarda y la venta queda registrada con todo lo anterior.

## Formato de números en la GUI

1. **Los campos numéricos aceptan punto o coma como separador decimal.** Un valor escrito como `150,50` o `150.50` debe interpretarse igual (150.5).
2. **El separador de miles no debe interferir:** `1,500.50` significa 1500.5 (la coma entre dígitos es miles, la última coma es decimal cuando no hay punto).
3. **El signo negativo es válido** donde el negocio lo permite (p. ej. SALDO del cliente puede quedar en negativo).
4. **El saldo del cliente puede ser negativo** (el vendedor le debe al cliente). Los campos de saldo deben permitir valores menores que cero.
5. **Todos los campos numéricos de la GUI deben usar** `DecimalSpinBox` (para spinboxes) o `parse_decimal()` (para texto libre). Nunca depender del locale del sistema ni de `float()` directo sobre texto escrito por el usuario.
6. **La visualización usa siempre punto** como separador decimal (locale fijo en inglés), independientemente del idioma de Windows.
