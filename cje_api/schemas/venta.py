from pydantic import BaseModel, Field, ConfigDict
from datetime import date
from typing import List, Optional


# Detalle de venta: referencia al inventario, cantidad y precio opcional por línea
class DetalleVentaCreate(BaseModel):
    ID_INVENTARIO: int
    CANTIDAD: int = Field(gt=0, description="Cantidad comprada debe ser mayor a cero")
    # Precio unitario propio de la línea; si se omite, se usa INVENTARIO.PRECIO_VENTA
    PRECIO_UNITARIO: Optional[float] = Field(default=None, ge=0.0)


# Crear una venta con sus detalles
class VentaCreate(BaseModel):
    CEDULA: int
    FECHA: Optional[date] = None
    TIPO_PAGO: str
    FORMA_DE_PAGO: str
    PAGO: float = Field(default=0.0, ge=0.0)
    # Si se omite, el precio se calcula automáticamente como suma de los detalles
    PRECIO: Optional[float] = Field(default=None, ge=0.0)
    detalles: List[DetalleVentaCreate] = Field(min_length=1)


# Respuesta de un detalle de venta (con datos del producto para mostrar en la GUI)
class DetalleVentaResponse(BaseModel):
    ID_DETALLE: int
    ID_INVENTARIO: int
    CANTIDAD: int
    NOMBRE_PRODUCTO: Optional[str] = None
    PRECIO_UNITARIO: Optional[float] = None
    SUBTOTAL: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# Respuesta de una venta
class VentaResponse(BaseModel):
    ID_VENTA: int
    FECHA: Optional[date] = None
    CEDULA: int
    PRECIO: float
    TIPO_PAGO: str
    FORMA_DE_PAGO: str
    PAGO: float
    NOMBRE_CLIENTE: Optional[str] = None
    detalles: List[DetalleVentaResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
