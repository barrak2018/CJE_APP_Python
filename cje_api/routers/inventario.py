from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
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


def _suma_asignada_por_flete(db: Session, id_lote: int, excluir_id: int = None) -> int:
    """Suma de CANTIDAD_ASIGNADA de todas las filas de inventario del flete."""
    query = db.query(func.coalesce(func.sum(models_inv.Inventario.CANTIDAD_ASIGNADA), 0))
    query = query.filter(models_inv.Inventario.ID_LOTE == id_lote)
    if excluir_id is not None:
        query = query.filter(models_inv.Inventario.ID_INVENTARIO != excluir_id)
    return int(query.scalar() or 0)


def _validar_cupo_flete(db: Session, id_lote: int, cantidad_asignada: int,
                        excluir_id: int = None) -> None:
    """Valida que la asignación total del flete no exceda la cantidad traída."""
    flete = db.query(FleteModel).filter(FleteModel.ID_FLETE == id_lote).first()
    if not flete:
        raise HTTPException(status_code=404, detail="El lote (FLETE) especificado no existe.")

    ya_asignado = _suma_asignada_por_flete(db, id_lote, excluir_id=excluir_id)
    total = ya_asignado + cantidad_asignada
    if total > flete.CANTIDAD:
        disponible = flete.CANTIDAD - ya_asignado
        raise HTTPException(
            status_code=400,
            detail=(
                f"El flete trajo {flete.CANTIDAD} perfume(s). "
                f"Ya hay {ya_asignado} asignado(s) en inventario y "
                f"esta entrada asigna {cantidad_asignada} (total {total}), "
                f"por lo que excede el cupo. Quedan {disponible} perfume(s) por asignar."
            )
        )


@router.post("/", response_model=schemas.InventarioResponse, status_code=status.HTTP_201_CREATED)
def crear_inventario(item: schemas.InventarioCreate, db: Session = Depends(get_db)):
    catalogo = db.query(models_cat.Catalogo).filter(models_cat.Catalogo.ID_CATALOGO == item.ID_CATALOGO).first()
    if not catalogo:
        raise HTTPException(status_code=404, detail="El producto de catálogo especificado no existe.")

    # Cantidad original = CANTIDAD_ASIGNADA (o CANTIDA como legado); CANTIDA se iguala a ese valor.
    asignada = item.CANTIDAD_ASIGNADA if item.CANTIDAD_ASIGNADA is not None else item.CANTIDA
    if asignada is None:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar la cantidad asignada (original comprada del flete).",
        )

    _validar_cupo_flete(db, item.ID_LOTE, asignada)

    costo_u, precio_v = calcular_precios(db, item.ID_LOTE, item.PRECIO_UNITARIO, item.GANACIA)

    nuevo_item = models_inv.Inventario(
        ID_CATALOGO=item.ID_CATALOGO,
        ID_LOTE=item.ID_LOTE,
        PRECIO_UNITARIO=item.PRECIO_UNITARIO,
        GANACIA=item.GANACIA,
        CANTIDA=asignada,
        CANTIDAD_ASIGNADA=asignada,
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

    # La cantidad asignada no cambia por ediciones de stock (solo por corrección explícita).
    nueva_asignada = item.CANTIDAD_ASIGNADA
    if "CANTIDAD_ASIGNADA" in update_data:
        nueva_asignada = update_data["CANTIDAD_ASIGNADA"]
        _validar_cupo_flete(db, item.ID_LOTE, nueva_asignada, excluir_id=id_inventario)

    for key, value in update_data.items():
        if key == "CANTIDAD_ASIGNADA":
            continue
        setattr(item, key, value)
    item.CANTIDAD_ASIGNADA = nueva_asignada

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
