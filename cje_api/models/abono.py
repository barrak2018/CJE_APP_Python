from sqlalchemy import Column, BigInteger, Date, Float, ForeignKey
from database import Base


class Abono(Base):
    __tablename__ = "ABONOS"

    ID_ABONO = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    FECHA = Column(Date, nullable=False)
    CEDULA = Column(BigInteger, ForeignKey("CLIENTE.CEDULA"), nullable=False)
    CANTIDAD = Column(Float, default=0.0, nullable=False)
