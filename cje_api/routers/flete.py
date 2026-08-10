from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db
from models.flete import FleteModel
import models.inventario as models_inv
from schemas.flete import FleteCreate, FleteResponse

router = APIRouter(
    prefix="/fletes",
    tags=["Fletes"]
)


def _suma_asignada(db: Session, id_lote: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(models_inv.Inventario.CANTIDAD_ASIGNADA), 0))
        .filter(models_inv.Inventario.ID_LOTE == id_lote)
        .scalar()
    )
    return int(total or 0)


def _to_response(flete: FleteModel, asignada: int) -> FleteResponse:
    return FleteResponse(
        ID_FLETE=flete.ID_FLETE,
        FECHA=flete.FECHA,
        PROVEEDOR=flete.PROVEEDOR,
        SHEPING=flete.SHEPING,
        NOMBRE_CURRIER=flete.NOMBRE_CURRIER,
        VIA=flete.VIA,
        PRECIO_CURRIER=flete.PRECIO_CURRIER,
        CANTIDAD=flete.CANTIDAD,
        TOTAL_FLETE=flete.TOTAL_FLETE,
        CANTIDAD_ASIGNADA=asignada,
        CANTIDAD_DISPONIBLE=max(0, (flete.CANTIDAD or 0) - asignada),
    )


# 1. CREAR FLETE
@router.post("/", response_model=FleteResponse, status_code=status.HTTP_201_CREATED)
def crear_flete(flete_in: FleteCreate, db: Session = Depends(get_db)):
    try:
        nuevo_flete = FleteModel(
            FECHA=flete_in.FECHA,
            PROVEEDOR=flete_in.PROVEEDOR,
            SHEPING=flete_in.SHEPING,
            NOMBRE_CURRIER=flete_in.NOMBRE_CURRIER,
            VIA=flete_in.VIA.upper(),  # Aseguramos enviar una sola letra en mayúscula ('M' o 'A')
            PRECIO_CURRIER=flete_in.PRECIO_CURRIER,
            CANTIDAD=flete_in.CANTIDAD
        )
        db.add(nuevo_flete)
        db.commit()
        db.refresh(nuevo_flete)
        return _to_response(nuevo_flete, 0)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar el flete: {str(e)}"
        )

# 2. OBTENER TODOS LOS FLETES
@router.get("/", response_model=List[FleteResponse])
def listar_fletes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    fletes = db.query(FleteModel).offset(skip).limit(limit).all()
    if not fletes:
        return []
    asignados = dict(
        db.query(models_inv.Inventario.ID_LOTE,
                 func.sum(models_inv.Inventario.CANTIDAD_ASIGNADA))
        .filter(models_inv.Inventario.ID_LOTE.in_([f.ID_FLETE for f in fletes]))
        .group_by(models_inv.Inventario.ID_LOTE)
        .all()
    )
    return [_to_response(f, int(asignados.get(f.ID_FLETE, 0) or 0)) for f in fletes]

# 3. OBTENER UN FLETE POR ID
@router.get("/{id_flete}", response_model=FleteResponse)
def obtener_flete(id_flete: int, db: Session = Depends(get_db)):
    flete = db.query(FleteModel).filter(FleteModel.ID_FLETE == id_flete).first()
    if not flete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flete con ID {id_flete} no encontrado"
        )
    return _to_response(flete, _suma_asignada(db, id_flete))

# 4. ACTUALIZAR FLETE
@router.put("/{id_flete}", response_model=FleteResponse)
def actualizar_flete(id_flete: int, flete_in: FleteCreate, db: Session = Depends(get_db)):
    flete = db.query(FleteModel).filter(FleteModel.ID_FLETE == id_flete).first()
    if not flete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flete con ID {id_flete} no encontrado"
        )
    
    try:
        # No permitir bajar la cantidad por debajo de lo ya asignado en inventario.
        asignada = _suma_asignada(db, id_flete)
        if flete_in.CANTIDAD < asignada:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No se puede reducir la cantidad del flete a {flete_in.CANTIDAD} "
                    f"porque ya hay {asignada} perfume(s) asignados en inventario."
                )
            )

        flete.FECHA = flete_in.FECHA
        flete.PROVEEDOR = flete_in.PROVEEDOR
        flete.SHEPING = flete_in.SHEPING
        flete.NOMBRE_CURRIER = flete_in.NOMBRE_CURRIER
        flete.VIA = flete_in.VIA.upper()
        flete.PRECIO_CURRIER = flete_in.PRECIO_CURRIER
        flete.CANTIDAD = flete_in.CANTIDAD
        
        db.commit()
        db.refresh(flete)
        return _to_response(flete, asignada)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar el flete: {str(e)}"
        )

# 5. ELIMINAR FLETE
@router.delete("/{id_flete}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_flete(id_flete: int, db: Session = Depends(get_db)):
    flete = db.query(FleteModel).filter(FleteModel.ID_FLETE == id_flete).first()
    if not flete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flete con ID {id_flete} no encontrado"
        )
    try:
        db.delete(flete)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el flete porque está referenciado en el inventario o hubo un error: {str(e)}"
        )
