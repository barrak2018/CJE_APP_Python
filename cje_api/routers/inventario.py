from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models.inventario as models_inv
import models.catalogo as models_cat
from models.flete import FleteModel
import schemas.inventario as schemas

router = APIRouter(
    prefix="/inventario",
    tags=["Inventario"]
)


def calcular_precios(db: Session, id_lote: int, precio_unitario: float, ganancia_porcentaje: float):
    total_flete = 0.0
    if id_lote is not None:
        # Se realiza la consulta utilizando la clase FleteModel
        lote = db.query(FleteModel).filter(FleteModel.ID_FLETE == id_lote).first()
        if not lote:
            raise HTTPException(status_code=404, detail="El lote (FLETE) especificado no existe.")
        total_flete = lote.TOTAL_FLETE or 0.0

    costo_unitario = round(precio_unitario + total_flete, 2)
    
    if ganancia_porcentaje >= 100.0:
        raise HTTPException(
            status_code=400, 
            detail="La ganancia debe ser un porcentaje menor a 100 (ejemplo: 33.3 para 33.3%)."
        )

    porcentaje_decimal = ganancia_porcentaje / 100.0
    precio_venta = round(costo_unitario / (1.0 - porcentaje_decimal), 2)
    
    return costo_unitario, precio_venta


@router.post("/", response_model=schemas.InventarioResponse, status_code=status.HTTP_201_CREATED)
def crear_inventario(item: schemas.InventarioCreate, db: Session = Depends(get_db)):
    catalogo = db.query(models_cat.Catalogo).filter(models_cat.Catalogo.ID_CATALOGO == item.ID_CATALOGO).first()
    if not catalogo:
        raise HTTPException(status_code=404, detail="El producto de catálogo especificado no existe.")

    costo_u, precio_v = calcular_precios(db, item.ID_LOTE, item.PRECIO_UNITARIO, item.GANACIA)

    nuevo_item = models_inv.Inventario(
        **item.model_dump(),
        COSTO_UNITARIO=costo_u,
        PRECIO_VENTA=precio_v
    )
    db.add(nuevo_item)
    db.commit()
    db.refresh(nuevo_item)
    return nuevo_item


@router.get("/", response_model=List[schemas.InventarioResponse])
def listar_inventario(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models_inv.Inventario).offset(skip).limit(limit).all()


@router.get("/{id_inventario}", response_model=schemas.InventarioResponse)
def obtener_inventario(id_inventario: int, db: Session = Depends(get_db)):
    item = db.query(models_inv.Inventario).filter(models_inv.Inventario.ID_INVENTARIO == id_inventario).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro de inventario no encontrado.")
    return item


@router.put("/{id_inventario}", response_model=schemas.InventarioResponse)
def actualizar_inventario(id_inventario: int, datos: schemas.InventarioUpdate, db: Session = Depends(get_db)):
    item = db.query(models_inv.Inventario).filter(models_inv.Inventario.ID_INVENTARIO == id_inventario).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro de inventario no encontrado.")

    update_data = datos.model_dump(exclude_unset=True)
    if "ID_LOTE" in update_data and update_data["ID_LOTE"] is None:
        raise HTTPException(
            status_code=400,
            detail="Todo producto de inventario debe tener un lote (FLETE) asociado.",
        )
    for key, value in update_data.items():
        setattr(item, key, value)

    item.COSTO_UNITARIO, item.PRECIO_VENTA = calcular_precios(
        db, item.ID_LOTE, item.PRECIO_UNITARIO, item.GANACIA
    )

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{id_inventario}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_inventario(id_inventario: int, db: Session = Depends(get_db)):
    item = db.query(models_inv.Inventario).filter(models_inv.Inventario.ID_INVENTARIO == id_inventario).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro de inventario no encontrado.")
    
    try:
        db.delete(item)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el inventario porque está referenciado en detalles de ventas o hubo un error: {str(e)}"
        )