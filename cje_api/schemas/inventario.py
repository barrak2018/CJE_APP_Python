from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class InventarioBase(BaseModel):
    ID_CATALOGO: int
    # Cantidad original comprada del flete; CANTIDA se iguala a este valor al crear.
    CANTIDAD_ASIGNADA: int = Field(default=0, ge=0)
    ID_LOTE: int
    PRECIO_UNITARIO: float = Field(gt=0)
    GANACIA: float = Field(gt=0, lt=100)  # Se recibe como valor directo (ej: 33.3 para 33.3%)

class InventarioCreate(BaseModel):
    ID_CATALOGO: int
    CANTIDAD_ASIGNADA: Optional[int] = Field(default=None, ge=0)
    ID_LOTE: int
    PRECIO_UNITARIO: float = Field(gt=0)
    GANACIA: float = Field(gt=0, lt=100)
    # Campo legado: si no se envía CANTIDAD_ASIGNADA, se usa CANTIDA como cantidad original.
    CANTIDA: Optional[int] = Field(default=None, ge=0)

class InventarioUpdate(BaseModel):
    ID_CATALOGO: Optional[int] = None
    CANTIDA: Optional[int] = Field(default=None, ge=0)
    CANTIDAD_ASIGNADA: Optional[int] = Field(default=None, ge=0)
    ID_LOTE: Optional[int] = None
    PRECIO_UNITARIO: Optional[float] = None
    GANACIA: Optional[float] = None

class InventarioResponse(InventarioBase):
    ID_INVENTARIO: int
    CANTIDA: int
    COSTO_UNITARIO: Optional[float] = None
    PRECIO_VENTA: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
