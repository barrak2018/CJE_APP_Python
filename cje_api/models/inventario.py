from sqlalchemy import Column, BigInteger, Integer, Float, ForeignKey
from database import Base

class Inventario(Base):
    __tablename__ = "INVENTARIO"

    ID_INVENTARIO = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    ID_CATALOGO = Column(BigInteger, ForeignKey("CATALOGO.ID_CATALOGO"), nullable=False)
    CANTIDA = Column(Integer, default=0, nullable=False)
    ID_LOTE = Column(BigInteger, ForeignKey("FLETE.ID_FLETE"), nullable=False)
    PRECIO_UNITARIO = Column(Float, nullable=True)
    COSTO_UNITARIO = Column(Float, nullable=True)
    GANACIA = Column(Float, nullable=True)
    PRECIO_VENTA = Column(Float, nullable=True)