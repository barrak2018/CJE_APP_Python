from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models.cliente as models
import schemas.cliente as schemas

router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"]
)

# 1. Crear Cliente
@router.post("/", response_model=schemas.ClienteResponse, status_code=status.HTTP_201_CREATED)
def crear_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db)):
    db_cliente = db.query(models.Cliente).filter(models.Cliente.CEDULA == cliente.CEDULA).first()
    if db_cliente:
        raise HTTPException(
            status_code=400, 
            detail=f"El cliente con cédula {cliente.CEDULA} ya se encuentra registrado."
        )
    
    nuevo_cliente = models.Cliente(**cliente.model_dump())
    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)
    return nuevo_cliente

# 2. Listar todos los Clientes
@router.get("/", response_model=List[schemas.ClienteResponse])
def listar_clientes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Cliente).offset(skip).limit(limit).all()

# 3. Obtener un Cliente por CÉDULA
@router.get("/{cedula}", response_model=schemas.ClienteResponse)
def obtener_cliente(cedula: int, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.CEDULA == cedula).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

# 4. Actualizar Cliente
@router.put("/{cedula}", response_model=schemas.ClienteResponse)
def actualizar_cliente(cedula: int, datos: schemas.ClienteUpdate, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.CEDULA == cedula).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = datos.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cliente, key, value)
    
    db.commit()
    db.refresh(cliente)
    return cliente

# 5. Eliminar Cliente
@router.delete("/{cedula}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cliente(cedula: int, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.CEDULA == cedula).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    try:
        db.delete(cliente)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el cliente porque está referenciado en ventas o abonos o hubo un error: {str(e)}"
        )