from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class InventarioBase(BaseModel):
    ID_CATALOGO: int
    CANTIDA: int = Field(default=0, ge=0)
    ID_LOTE: int
    PRECIO_UNITARIO: float = Field(gt=0)
    GANACIA: float = Field(gt=0, lt=100)  # Se recibe como valor directo (ej: 33.3 para 33.3%)

class InventarioCreate(InventarioBase):
    pass

class InventarioUpdate(BaseModel):
    ID_CATALOGO: Optional[int] = None
    CANTIDA: Optional[int] = None
    ID_LOTE: Optional[int] = None
    PRECIO_UNITARIO: Optional[float] = None
    GANACIA: Optional[float] = None

class InventarioResponse(InventarioBase):
    ID_INVENTARIO: int
    COSTO_UNITARIO: Optional[float] = None
    PRECIO_VENTA: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)