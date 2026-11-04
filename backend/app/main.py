"""Punto de entrada de la API FastAPI.

Rutas:
- GET  /health   -> healthcheck (usado por Docker Compose)
- POST /api/ventas -> crear venta + cobro Factus Pay
- Endpoints de clientes, recaudos y administración
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clientes as clientes_router
from app.api import productos as productos_router
from app.api import recaudos as recaudos_router
from app.api.deps import get_db
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

# Importar modelos para registrarlos en Base.metadata antes de crear las tablas
import app.db.models.cliente  # noqa: F401
import app.db.models.producto  # noqa: F401
import app.db.models.transaccion  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Crea automáticamente las tablas en la base de datos al iniciar el contenedor."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Drogueria Caribe - POS",
    description="Punto de venta para droguería con Factus Pay y Facturación electrónica DIAN.",
    version="0.1.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

# CORS para el frontend en desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.vite_api_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clientes_router.router)
app.include_router(productos_router.router)
app.include_router(recaudos_router.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/", tags=["root"])
async def root():
    return {"service": "Drogueria Caribe POS", "version": "0.1.0"}