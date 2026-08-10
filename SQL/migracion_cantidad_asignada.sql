-- ====================================================================
-- MIGRACIÓN: CANTIDAD_ASIGNADA en INVENTARIO
-- ====================================================================
-- Propósito: congelar la cantidad original comprada del flete por fila de
-- inventario, de modo que la validación de sobre-asignación de un flete no
-- se rompa cuando las ventas descuentan CANTIDA.
--
--  * CANTIDAD_ASIGNADA = número original de perfumes de esa entrada que se
--    compraron en el flete (lo ingresa el usuario al crear la entrada).
--  * CANTIDA = stock actual (se descuenta con cada venta, como hasta ahora).
--
-- Para filas existentes se estima el original como: stock actual + vendido
-- (via DETALLES_VENTAS). Filas que hayan sido editadas manualmente pueden
-- quedar imprecisas y deben revisarse manualmente.
--
-- Aplicar con:  psql -U postgres -d CJE -f SQL/migracion_cantidad_asignada.sql

ALTER TABLE public."INVENTARIO"
    ADD COLUMN "CANTIDAD_ASIGNADA" integer NOT NULL DEFAULT 0;

UPDATE public."INVENTARIO" inv
SET "CANTIDAD_ASIGNADA" =
    inv."CANTIDA" + COALESCE((
        SELECT SUM(det."CANTIDAD")
        FROM public."DETALLES_VENTAS" det
        WHERE det."ID_INVENTARIO" = inv."ID_INVENTARIO"
    ), 0);

ALTER TABLE public."INVENTARIO"
    ADD CONSTRAINT "CK_INVENTARIO_ASIGNADA_POSITIVA"
    CHECK ("CANTIDAD_ASIGNADA" >= 0);
