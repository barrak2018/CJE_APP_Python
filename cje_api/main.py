# main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from security import get_current_user

# Importación de enrutadores por cada módulo de la base de datos
from routers.auth import router as auth_router
from routers.flete import router as flete_router
from routers.cliente import router as cliente_router
from routers.catalogo import router as catalogo_router
from routers.inventario import router as inventario_router
from routers.venta import router as ventas_router
from routers.abono import router as abonos_router

app = FastAPI(
    title="CJE Perfumes - Backend API",
    description="API para la automatización de cálculos, inventario y ventas de CJ de Perfumes",
    version="1.0.0"
)

# -------------------------------------------------------------------
# Registro de Enrutadores (Endpoints)
# -------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(flete_router, dependencies=[Depends(get_current_user)])
app.include_router(cliente_router, dependencies=[Depends(get_current_user)])
app.include_router(catalogo_router, dependencies=[Depends(get_current_user)])
app.include_router(inventario_router, dependencies=[Depends(get_current_user)])
app.include_router(ventas_router, dependencies=[Depends(get_current_user)])
app.include_router(abonos_router, dependencies=[Depends(get_current_user)])


# -------------------------------------------------------------------
# Rutas de Monitoreo y Estado
# -------------------------------------------------------------------
@app.get("/", tags=["Estado"])
def read_root():
    return {
        "sistema": "CJE Perfumes API",
        "estado": "Operativo"
    }

@app.get("/db-check", tags=["Estado"])
def check_db_connection(db: Session = Depends(get_db)):
    """Enrutador de prueba para validar la conexión con PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
        return {"database": "Conexión exitosa a PostgreSQL"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al conectar con la base de datos: {str(e)}"
        )