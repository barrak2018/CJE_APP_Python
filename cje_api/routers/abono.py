from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.abono import Abono
from models.cliente import Cliente
import schemas.abono as schemas

router = APIRouter(
    prefix="/abonos",
    tags=["Abonos"]
)


def _construir_respuesta(db: Session, abono: Abono) -> schemas.AbonoResponse:
    cliente = db.query(Cliente).filter(Cliente.CEDULA == abono.CEDULA).first()
    return schemas.AbonoResponse(
        ID_ABONO=abono.ID_ABONO,
        FECHA=abono.FECHA,
        CEDULA=abono.CEDULA,
        CANTIDAD=abono.CANTIDAD,
        NOMBRE_CLIENTE=cliente.NOMBRE if cliente else None,
    )


def _listar_respuestas(db: Session, abonos: List[Abono]) -> List[schemas.AbonoResponse]:
    """Construye las respuestas de una lista en lote (evita el patrón N+1)."""
    nombres = {}
    cedulas = {a.CEDULA for a in abonos}
    if cedulas:
        clientes = db.query(Cliente).filter(Cliente.CEDULA.in_(cedulas)).all()
        nombres = {c.CEDULA: c.NOMBRE for c in clientes}
    return [
        schemas.AbonoResponse(
            ID_ABONO=a.ID_ABONO,
            FECHA=a.FECHA,
            CEDULA=a.CEDULA,
            CANTIDAD=a.CANTIDAD,
            NOMBRE_CLIENTE=nombres.get(a.CEDULA),
        )
        for a in abonos
    ]


# 1. CREAR ABONO: reduce la deuda (SALDO) del cliente
@router.post("/", response_model=schemas.AbonoResponse, status_code=status.HTTP_201_CREATED)
def crear_abono(abono_in: schemas.AbonoCreate, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.CEDULA == abono_in.CEDULA).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="El cliente especificado no existe.")

    try:
        abono = Abono(
            FECHA=abono_in.FECHA or date.today(),
            CEDULA=abono_in.CEDULA,
            CANTIDAD=abono_in.CANTIDAD,
        )
        db.add(abono)
        # SALDO positivo = deuda del cliente; el abono la reduce (puede dejar
        # saldo a favor si supera la deuda).
        cliente.SALDO = (cliente.SALDO or 0.0) - abono_in.CANTIDAD
        db.commit()
        db.refresh(abono)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar el abono: {str(e)}",
        )

    return _construir_respuesta(db, abono)


# 2. LISTAR ABONOS (opcional: filtrar por cédula)
@router.get("/", response_model=List[schemas.AbonoResponse])
def listar_abonos(cedula: Optional[int] = None, skip: int = 0, limit: int = 100,
                  db: Session = Depends(get_db)):
    query = db.query(Abono)
    if cedula is not None:
        query = query.filter(Abono.CEDULA == cedula)
    abonos = query.order_by(Abono.ID_ABONO.desc()).offset(skip).limit(limit).all()
    return _listar_respuestas(db, abonos)


# 3. OBTENER ABONO POR ID
@router.get("/{id_abono}", response_model=schemas.AbonoResponse)
def obtener_abono(id_abono: int, db: Session = Depends(get_db)):
    abono = db.query(Abono).filter(Abono.ID_ABONO == id_abono).first()
    if not abono:
        raise HTTPException(status_code=404, detail="Abono no encontrado")
    return _construir_respuesta(db, abono)


# 4. EDITAR ABONO: revierte el efecto en SALDO del valor original y aplica el nuevo
@router.put("/{id_abono}", response_model=schemas.AbonoResponse)
def editar_abono(id_abono: int, datos: schemas.AbonoUpdate, db: Session = Depends(get_db)):
    abono = db.query(Abono).filter(Abono.ID_ABONO == id_abono).first()
    if not abono:
        raise HTTPException(status_code=404, detail="Abono no encontrado")

    update_data = datos.model_dump(exclude_unset=True)
    cedula_original = abono.CEDULA
    cantidad_original = float(abono.CANTIDAD or 0.0)
    nueva_cedula = update_data.get("CEDULA", cedula_original)
    nueva_cantidad = update_data.get("CANTIDAD", cantidad_original)

    try:
        # Revertir el abono original
        cliente_original = (
            db.query(Cliente).filter(Cliente.CEDULA == cedula_original).first()
        )
        if cliente_original:
            cliente_original.SALDO = (cliente_original.SALDO or 0.0) + cantidad_original

        # Aplicar el nuevo abono
        cliente_nuevo = db.query(Cliente).filter(Cliente.CEDULA == nueva_cedula).first()
        if not cliente_nuevo:
            raise HTTPException(status_code=404,
                                detail="El cliente especificado no existe.")
        cliente_nuevo.SALDO = (cliente_nuevo.SALDO or 0.0) - nueva_cantidad

        for key, value in update_data.items():
            setattr(abono, key, value)

        db.commit()
        db.refresh(abono)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al editar el abono: {str(e)}",
        )

    return _construir_respuesta(db, abono)


# 5. ELIMINAR ABONO: revierte su efecto en el SALDO del cliente
@router.delete("/{id_abono}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_abono(id_abono: int, db: Session = Depends(get_db)):
    abono = db.query(Abono).filter(Abono.ID_ABONO == id_abono).first()
    if not abono:
        raise HTTPException(status_code=404, detail="Abono no encontrado")

    try:
        cliente = db.query(Cliente).filter(Cliente.CEDULA == abono.CEDULA).first()
        if cliente:
            cliente.SALDO = (cliente.SALDO or 0.0) + float(abono.CANTIDAD or 0.0)
        db.delete(abono)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el abono: {str(e)}",
        )
