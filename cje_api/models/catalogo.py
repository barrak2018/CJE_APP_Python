from sqlalchemy import Column, BigInteger, Text
from database import Base

class Catalogo(Base):
    __tablename__ = "CATALOGO"

    ID_CATALOGO = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    NOMBRE = Column(Text, nullable=False)
    MARCA = Column(Text, nullable=True)
    PRESENTACION = Column(Text, nullable=True)