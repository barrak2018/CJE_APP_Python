from pydantic import BaseModel, ConfigDict
from typing import Optional

# Esquema base con campos comunes
class ClienteBase(BaseModel):
    NOMBRE: str
    CORREO: Optional[str] = None
    TELEFONO: Optional[str] = None
    SALDO: Optional[float] = 0.0

# Para crear cliente requiere la CÉDULA
class ClienteCreate(ClienteBase):
    CEDULA: int

# Para actualizar campos (opcionales)
class ClienteUpdate(BaseModel):
    NOMBRE: Optional[str] = None
    CORREO: Optional[str] = None
    TELEFONO: Optional[str] = None
    SALDO: Optional[float] = None

# Respuesta de la API
class ClienteResponse(ClienteBase):
    CEDULA: int

    model_config = ConfigDict(from_attributes=True)