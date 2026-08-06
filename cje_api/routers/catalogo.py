from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models.catalogo as models
import schemas.catalogo as schemas

router = APIRouter(
    prefix="/catalogo",
    tags=["Catálogo"]
)

@router.post("/", response_model=schemas.CatalogoResponse, status_code=status.HTTP_201_CREATED)
def crear_producto(producto: schemas.CatalogoCreate, db: Session = Depends(get_db)):
    nuevo_producto = models.Catalogo(**producto.model_dump())
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    return nuevo_producto

@router.get("/", response_model=List[schemas.CatalogoResponse])
def listar_catalogo(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Catalogo).offset(skip).limit(limit).all()

@router.get("/{id_catalogo}", response_model=schemas.CatalogoResponse)
def obtener_producto(id_catalogo: int, db: Session = Depends(get_db)):
    producto = db.query(models.Catalogo).filter(models.Catalogo.ID_CATALOGO == id_catalogo).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto de catálogo no encontrado")
    return producto

@router.put("/{id_catalogo}", response_model=schemas.CatalogoResponse)
def actualizar_producto(id_catalogo: int, datos: schemas.CatalogoUpdate, db: Session = Depends(get_db)):
    producto = db.query(models.Catalogo).filter(models.Catalogo.ID_CATALOGO == id_catalogo).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto de catálogo no encontrado")
    
    update_data = datos.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(producto, key, value)
    
    db.commit()
    db.refresh(producto)
    return producto

@router.delete("/{id_catalogo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(id_catalogo: int, db: Session = Depends(get_db)):
    producto = db.query(models.Catalogo).filter(models.Catalogo.ID_CATALOGO == id_catalogo).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto de catálogo no encontrado")
    
    try:
        db.delete(producto)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el catálogo porque está referenciado en el inventario o hubo un error: {str(e)}"
        )