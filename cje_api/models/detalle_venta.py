from sqlalchemy import Column, BigInteger, Integer, Float, ForeignKey
from database import Base


class DetalleVenta(Base):
    __tablename__ = "DETALLES_VENTAS"

    ID_DETALLE = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    ID_VENTA = Column(BigInteger, ForeignKey("VENTAS.ID_VENTA"), nullable=True)
    ID_INVENTARIO = Column(BigInteger, ForeignKey("INVENTARIO.ID_INVENTARIO"), nullable=True)
    CANTIDAD = Column(Integer, nullable=True)
    # Precio unitario propio de la línea; NULL = usar INVENTARIO.PRECIO_VENTA
    PRECIO_UNITARIO = Column(Float, nullable=True)
