from pydantic import BaseModel, ConfigDict
from typing import Optional

class CatalogoBase(BaseModel):
    NOMBRE: str
    MARCA: Optional[str] = None
    PRESENTACION: Optional[str] = None

class CatalogoCreate(CatalogoBase):
    pass

class CatalogoUpdate(BaseModel):
    NOMBRE: Optional[str] = None
    MARCA: Optional[str] = None
    PRESENTACION: Optional[str] = None

class CatalogoResponse(CatalogoBase):
    ID_CATALOGO: int

    model_config = ConfigDict(from_attributes=True)