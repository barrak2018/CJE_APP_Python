from sqlalchemy import Column, BigInteger, Date, Float, Text, ForeignKey
from database import Base


class Venta(Base):
    __tablename__ = "VENTAS"

    ID_VENTA = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    FECHA = Column(Date, nullable=True)
    CEDULA = Column(BigInteger, ForeignKey("CLIENTE.CEDULA"), nullable=False)
    PRECIO = Column(Float, default=0.0, nullable=False)
    TIPO_PAGO = Column(Text, nullable=False)
    FORMA_DE_PAGO = Column(Text, nullable=False)
    PAGO = Column(Float, nullable=True)
