from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.flete import FleteModel
from schemas.flete import FleteCreate, FleteResponse

router = APIRouter(
    prefix="/fletes",
    tags=["Fletes"]
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
        return nuevo_flete
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar el flete: {str(e)}"
        )

# 2. OBTENER TODOS LOS FLETES
@router.get("/", response_model=List[FleteResponse])
def listar_fletes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(FleteModel).offset(skip).limit(limit).all()

# 3. OBTENER UN FLETE POR ID
@router.get("/{id_flete}", response_model=FleteResponse)
def obtener_flete(id_flete: int, db: Session = Depends(get_db)):
    flete = db.query(FleteModel).filter(FleteModel.ID_FLETE == id_flete).first()
    if not flete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flete con ID {id_flete} no encontrado"
        )
    return flete

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
        flete.FECHA = flete_in.FECHA
        flete.PROVEEDOR = flete_in.PROVEEDOR
        flete.SHEPING = flete_in.SHEPING
        flete.NOMBRE_CURRIER = flete_in.NOMBRE_CURRIER
        flete.VIA = flete_in.VIA.upper()
        flete.PRECIO_CURRIER = flete_in.PRECIO_CURRIER
        flete.CANTIDAD = flete_in.CANTIDAD
        
        db.commit()
        db.refresh(flete)
        return flete
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