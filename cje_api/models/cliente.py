from sqlalchemy import Column, BigInteger, Text, Float
from database import Base

class Cliente(Base):
    __tablename__ = "CLIENTE"

    CEDULA = Column(BigInteger, primary_key=True, index=True)
    NOMBRE = Column(Text, nullable=False)
    CORREO = Column(Text, nullable=True)
    TELEFONO = Column(Text, nullable=True)
    SALDO = Column(Float, default=0.0)