"""Punto de entrada de la API FastAPI.

Rutas:
- GET  /health                -> healthcheck (usado por Docker Compose)
- /api/productos, /api/ventas -> inventario y ventas con cobro Factus Pay
- POST /webhooks, /webhook/factus-pay -> confirmación de pago (llave en query `key`)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.clientes import router as clientes_router
from app.api.ventas import router as ventas_router
from app.core.config import settings
from app.db import models  # noqa: F401  (registra los modelos en Base.metadata)
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
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

# CORS para el frontend en desarrollo (ajustar orígenes en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.vite_api_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)

app.include_router(ventas_router)
app.include_router(clientes_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/", tags=["root"])
async def root():
    return {"service": "Drogueria Caribe POS", "version": "0.1.0"}
