from pydantic import BaseModel, Field, ConfigDict
from datetime import date
from typing import Optional


class AbonoCreate(BaseModel):
    # Si se omite, la fecha se asigna como el día actual
    FECHA: Optional[date] = None
    CEDULA: int
    CANTIDAD: float = Field(gt=0, description="El monto del abono debe ser mayor a cero")


class AbonoUpdate(BaseModel):
    FECHA: Optional[date] = None
    CEDULA: Optional[int] = None
    CANTIDAD: Optional[float] = Field(default=None, gt=0)


class AbonoResponse(BaseModel):
    ID_ABONO: int
    FECHA: date
    CEDULA: int
    CANTIDAD: float
    NOMBRE_CLIENTE: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
