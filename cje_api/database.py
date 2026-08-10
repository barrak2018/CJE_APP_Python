from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import get_setting, require_secret

# Configuración de base de datos (config.json, sobreescribible por variables de entorno)
usuario = get_setting("database", "user")
password = require_secret("database", "password")
host = get_setting("database", "host")
puerto = get_setting("database", "port")
bd = get_setting("database", "name")

DATABASE_URL = f"postgresql://{usuario}:{password}@{host}:{puerto}/{bd}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"client_encoding": "utf8"}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()