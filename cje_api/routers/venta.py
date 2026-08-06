from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.venta import Venta
from models.detalle_venta import DetalleVenta
from models.cliente import Cliente
import models.inventario as models_inv
import models.catalogo as models_cat
import schemas.venta as schemas

router = APIRouter(
    prefix="/ventas",
    tags=["Ventas"]
)


def _precio_linea(det, inventario):
    """Precio unitario del detalle: el guardado en la línea si existe, si no PRECIO_VENTA."""
    if det.PRECIO_UNITARIO is not None:
        return float(det.PRECIO_UNITARIO)
    return float(inventario.PRECIO_VENTA or 0.0)


def _construir_detalle(det: DetalleVenta, inventario, catalogo):
    precio_unitario = _precio_linea(det, inventario)
    return schemas.DetalleVentaResponse(
        ID_DETALLE=det.ID_DETALLE,
        ID_INVENTARIO=det.ID_INVENTARIO,
        CANTIDAD=det.CANTIDAD,
        NOMBRE_PRODUCTO=catalogo.NOMBRE if catalogo else None,
        PRECIO_UNITARIO=precio_unitario,
        SUBTOTAL=round(precio_unitario * det.CANTIDAD, 2),
    )


def _construir_respuesta(db: Session, venta: Venta,
                         nombre_cliente: Optional[str] = None,
                         detalles=None) -> schemas.VentaResponse:
    if nombre_cliente is None:
        cliente = db.query(Cliente).filter(Cliente.CEDULA == venta.CEDULA).first()
        nombre_cliente = cliente.NOMBRE if cliente else None
    if detalles is None:
        detalles_db = (
            db.query(DetalleVenta)
            .filter(DetalleVenta.ID_VENTA == venta.ID_VENTA)
            .all()
        )
        detalles = []
        for det in detalles_db:
            inv = (
                db.query(models_inv.Inventario)
                .filter(models_inv.Inventario.ID_INVENTARIO == det.ID_INVENTARIO)
                .first()
            )
            cat = None
            if inv:
                cat = (
                    db.query(models_cat.Catalogo)
                    .filter(models_cat.Catalogo.ID_CATALOGO == inv.ID_CATALOGO)
                    .first()
                )
            detalles.append(_construir_detalle(det, inv, cat))

    return schemas.VentaResponse(
        ID_VENTA=venta.ID_VENTA,
        FECHA=venta.FECHA,
        CEDULA=venta.CEDULA,
        PRECIO=venta.PRECIO,
        TIPO_PAGO=venta.TIPO_PAGO,
        FORMA_DE_PAGO=venta.FORMA_DE_PAGO,
        PAGO=venta.PAGO or 0.0,
        NOMBRE_CLIENTE=nombre_cliente,
        detalles=detalles,
    )


def _listar_respuestas(db: Session, ventas) -> List[schemas.VentaResponse]:
    """Construye las respuestas de una lista en lote (evita el patrón N+1)."""
    nombres = {}
    cedulas = {v.CEDULA for v in ventas}
    if cedulas:
        clientes = db.query(Cliente).filter(Cliente.CEDULA.in_(cedulas)).all()
        nombres = {c.CEDULA: c.NOMBRE for c in clientes}

    detalles_por_venta = {}
    inv_ids = set()
    ids = [v.ID_VENTA for v in ventas]
    if ids:
        for det in (
            db.query(DetalleVenta)
            .filter(DetalleVenta.ID_VENTA.in_(ids))
            .all()
        ):
            detalles_por_venta.setdefault(det.ID_VENTA, []).append(det)
            inv_ids.add(det.ID_INVENTARIO)

    inventarios = {}
    catalogo_por_inv = {}
    if inv_ids:
        inventarios = {
            i.ID_INVENTARIO: i
            for i in db.query(models_inv.Inventario)
            .filter(models_inv.Inventario.ID_INVENTARIO.in_(inv_ids)).all()
        }
        cat_ids = {i.ID_CATALOGO for i in inventarios.values()}
        if cat_ids:
            catalogos = {
                c.ID_CATALOGO: c
                for c in db.query(models_cat.Catalogo)
                .filter(models_cat.Catalogo.ID_CATALOGO.in_(cat_ids)).all()
            }
            catalogo_por_inv = {
                iid: catalogos.get(inv.ID_CATALOGO)
                for iid, inv in inventarios.items()
            }

    respuestas = []
    for v in ventas:
        detalles = [
            _construir_detalle(d, inventarios.get(d.ID_INVENTARIO),
                               catalogo_por_inv.get(d.ID_INVENTARIO))
            for d in detalles_por_venta.get(v.ID_VENTA, [])
        ]
        respuestas.append(_construir_respuesta(
            db, v, nombre_cliente=nombres.get(v.CEDULA), detalles=detalles))
    return respuestas


# 1. CREAR VENTA (transacción atómica)
@router.post("/", response_model=schemas.VentaResponse, status_code=status.HTTP_201_CREATED)
def crear_venta(venta_in: schemas.VentaCreate, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.CEDULA == venta_in.CEDULA).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="El cliente especificado no existe.")

    # Validar detalles y calcular el precio por producto
    detalles_validados = []
    precio_calculado = 0.0
    for det in venta_in.detalles:
        inv = (
            db.query(models_inv.Inventario)
            .filter(models_inv.Inventario.ID_INVENTARIO == det.ID_INVENTARIO)
            .first()
        )
        if not inv:
            raise HTTPException(
                status_code=404,
                detail=f"El inventario con ID {det.ID_INVENTARIO} no existe.",
            )
        if det.CANTIDAD > inv.CANTIDA:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para el producto de inventario "
                       f"ID {det.ID_INVENTARIO}. Disponible: {inv.CANTIDA}, "
                       f"solicitado: {det.CANTIDAD}.",
            )
        precio_unitario = _precio_linea(det, inv)
        precio_calculado += precio_unitario * det.CANTIDAD
        detalles_validados.append((det, inv, precio_unitario))

    # PRECIO final: override del usuario o cálculo automático
    precio_final = venta_in.PRECIO if venta_in.PRECIO is not None else round(precio_calculado, 2)

    # PAGO puede ser mayor, menor o igual al PRECIO
    pago = venta_in.PAGO or 0.0

    try:
        nueva_venta = Venta(
            FECHA=venta_in.FECHA or date.today(),
            CEDULA=venta_in.CEDULA,
            PRECIO=precio_final,
            TIPO_PAGO=venta_in.TIPO_PAGO,
            FORMA_DE_PAGO=venta_in.FORMA_DE_PAGO,
            PAGO=pago,
        )
        db.add(nueva_venta)
        db.flush()

        for det, inv, precio_unitario in detalles_validados:
            db.add(DetalleVenta(
                ID_VENTA=nueva_venta.ID_VENTA,
                ID_INVENTARIO=det.ID_INVENTARIO,
                CANTIDAD=det.CANTIDAD,
                PRECIO_UNITARIO=precio_unitario,
            ))
            # Descontar stock del inventario
            inv.CANTIDA -= det.CANTIDAD

        # SALDO del cliente: positivo = debe la empresa... lógica: SALDO += PRECIO - PAGO
        # 0 -> no debe nada | negativo -> empresa debe al cliente | positivo -> cliente debe a la empresa
        cliente.SALDO = (cliente.SALDO or 0.0) + (precio_final - pago)

        db.commit()
        db.refresh(nueva_venta)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar la venta: {str(e)}",
        )

    return _construir_respuesta(db, nueva_venta)


# 2. LISTAR VENTAS
@router.get("/", response_model=List[schemas.VentaResponse])
def listar_ventas(cedula: Optional[int] = None, skip: int = 0, limit: int = 100,
                  db: Session = Depends(get_db)):
    query = db.query(Venta)
    if cedula is not None:
        query = query.filter(Venta.CEDULA == cedula)
    ventas = query.order_by(Venta.ID_VENTA.desc()).offset(skip).limit(limit).all()
    return _listar_respuestas(db, ventas)


# 3. OBTENER VENTA POR ID
@router.get("/{id_venta}", response_model=schemas.VentaResponse)
def obtener_venta(id_venta: int, db: Session = Depends(get_db)):
    venta = db.query(Venta).filter(Venta.ID_VENTA == id_venta).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return _construir_respuesta(db, venta)


# 4. EDITAR VENTA (transacción atómica: revierte stock/saldo originales y aplica los nuevos)
@router.put("/{id_venta}", response_model=schemas.VentaResponse)
def editar_venta(id_venta: int, venta_in: schemas.VentaCreate, db: Session = Depends(get_db)):
    venta = db.query(Venta).filter(Venta.ID_VENTA == id_venta).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    cliente_original = db.query(Cliente).filter(Cliente.CEDULA == venta.CEDULA).first()
    cliente_nuevo = db.query(Cliente).filter(Cliente.CEDULA == venta_in.CEDULA).first()
    if not cliente_nuevo:
        raise HTTPException(status_code=404, detail="El cliente especificado no existe.")

    detalles_originales = (
        db.query(DetalleVenta)
        .filter(DetalleVenta.ID_VENTA == id_venta)
        .all()
    )

    try:
        # 1. Revertir stock de los detalles originales
        for det in detalles_originales:
            inv = (
                db.query(models_inv.Inventario)
                .filter(models_inv.Inventario.ID_INVENTARIO == det.ID_INVENTARIO)
                .first()
            )
            if inv:
                inv.CANTIDA += det.CANTIDAD

        # 2. Revertir saldo del cliente original
        if cliente_original:
            cliente_original.SALDO = (cliente_original.SALDO or 0.0) - (
                (venta.PRECIO or 0.0) - (venta.PAGO or 0.0)
            )

        # 3. Validar nuevos detalles y calcular el precio
        detalles_validados = []
        precio_calculado = 0.0
        for det in venta_in.detalles:
            inv = (
                db.query(models_inv.Inventario)
                .filter(models_inv.Inventario.ID_INVENTARIO == det.ID_INVENTARIO)
                .first()
            )
            if not inv:
                raise HTTPException(
                    status_code=404,
                    detail=f"El inventario con ID {det.ID_INVENTARIO} no existe.",
                )
            if det.CANTIDAD > inv.CANTIDA:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para el producto de inventario "
                           f"ID {det.ID_INVENTARIO}. Disponible: {inv.CANTIDA}, "
                           f"solicitado: {det.CANTIDAD}.",
                )
            precio_unitario = _precio_linea(det, inv)
            precio_calculado += precio_unitario * det.CANTIDAD
            detalles_validados.append((det, inv, precio_unitario))

        precio_final = venta_in.PRECIO if venta_in.PRECIO is not None else round(precio_calculado, 2)
        pago = venta_in.PAGO or 0.0

        # 4. Eliminar detalles antiguos e insertar los nuevos
        for det in detalles_originales:
            db.delete(det)
        db.flush()
        for det, inv, precio_unitario in detalles_validados:
            db.add(DetalleVenta(
                ID_VENTA=id_venta,
                ID_INVENTARIO=det.ID_INVENTARIO,
                CANTIDAD=det.CANTIDAD,
                PRECIO_UNITARIO=precio_unitario,
            ))
            inv.CANTIDA -= det.CANTIDAD

        # 5. Actualizar cabecera
        venta.FECHA = venta_in.FECHA or venta.FECHA
        venta.CEDULA = venta_in.CEDULA
        venta.PRECIO = precio_final
        venta.TIPO_PAGO = venta_in.TIPO_PAGO
        venta.FORMA_DE_PAGO = venta_in.FORMA_DE_PAGO
        venta.PAGO = pago

        # 6. Aplicar saldo al cliente final
        cliente_nuevo.SALDO = (cliente_nuevo.SALDO or 0.0) + (precio_final - pago)

        db.commit()
        db.refresh(venta)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al editar la venta: {str(e)}",
        )

    return _construir_respuesta(db, venta)


# 5. ELIMINAR VENTA (revierte stock y saldo)
@router.delete("/{id_venta}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_venta(id_venta: int, db: Session = Depends(get_db)):
    venta = db.query(Venta).filter(Venta.ID_VENTA == id_venta).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    try:
        cliente = db.query(Cliente).filter(Cliente.CEDULA == venta.CEDULA).first()

        detalles_db = (
            db.query(DetalleVenta)
            .filter(DetalleVenta.ID_VENTA == id_venta)
            .all()
        )

        # Revertir stock de cada detalle
        for det in detalles_db:
            inv = (
                db.query(models_inv.Inventario)
                .filter(models_inv.Inventario.ID_INVENTARIO == det.ID_INVENTARIO)
                .first()
            )
            if inv:
                inv.CANTIDA += det.CANTIDAD

        # Revertir saldo del cliente
        if cliente:
            cliente.SALDO = (cliente.SALDO or 0.0) - ((venta.PRECIO or 0.0) - (venta.PAGO or 0.0))

        # Eliminar detalles y la venta
        for det in detalles_db:
            db.delete(det)
        db.delete(venta)

        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar la venta: {str(e)}",
        )
