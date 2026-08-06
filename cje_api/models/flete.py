from sqlalchemy import Column, BigInteger, Text, Float, Integer, CHAR, Computed, Date
from database import Base

class FleteModel(Base):
    __tablename__ = "FLETE"

    ID_FLETE = Column("ID_FLETE", BigInteger, primary_key=True, index=True)
    FECHA = Column("FECHA", Date, nullable=False)
    PROVEEDOR = Column("PROVEEDOR", Text, nullable=False)
    SHEPING = Column("SHEPING", Float, nullable=False, default=0.0)
    NOMBRE_CURRIER = Column("NOMBRE_CURRIER", Text, nullable=False)
    VIA = Column("VIA", CHAR, nullable=False)
    PRECIO_CURRIER = Column("PRECIO_CURRIER", Float, nullable=False, default=0.0)
    CANTIDAD = Column("CANTIDAD", Integer, nullable=False, default=0)
    
    # Campo generado por la BD: Usamos Computed() para evitar escrituras
    TOTAL_FLETE = Column("TOTAL_FLETE", Float, Computed("((SHEPING + PRECIO_CURRIER) / CANTIDAD)"))

    