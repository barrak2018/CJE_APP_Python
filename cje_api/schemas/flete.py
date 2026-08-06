from pydantic import BaseModel, Field, ConfigDict
from datetime import date

# Esquema para recibir la solicitud de creación
class FleteCreate(BaseModel):
    FECHA: date = Field(..., description="Fecha del flete (obligatoria)")
    PROVEEDOR: str
    SHEPING: float = Field(default=0.0, ge=0.0)
    NOMBRE_CURRIER: str
    VIA: str = Field(..., pattern=r'^[MA]$', description="'M' para Marítimo, 'A' para Aéreo")
    PRECIO_CURRIER: float = Field(default=0.0, ge=0.0)
    CANTIDAD: int = Field(default=1, gt=0, description="Cantidad debe ser mayor a cero para evitar división por cero")

# Esquema de respuesta con todos los campos devueltos por la BD
class FleteResponse(BaseModel):
    ID_FLETE: int
    FECHA: date
    PROVEEDOR: str
    SHEPING: float
    NOMBRE_CURRIER: str
    VIA: str
    PRECIO_CURRIER: float
    CANTIDAD: int
    TOTAL_FLETE: float | None = None

    model_config = ConfigDict(from_attributes=True)