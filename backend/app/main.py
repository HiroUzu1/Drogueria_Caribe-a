"""Punto de entrada de la API FastAPI.

Rutas:
- GET  /health   -> healthcheck (usado por Docker Compose)
- POST /api/ventas -> crear venta + cobro Factus Pay (esqueleto)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_db
from app.core.config import settings

app = FastAPI(
    title="Drogueria Caribe - POS",
    description="Punto de venta para droguería con Factus Pay y Facturación electrónica DIAN.",
    version="0.1.0",
    debug=settings.app_debug,
)

# CORS para el frontend en desarrollo (ajustar orígenes en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.vite_api_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/", tags=["root"])
async def root():
    return {"service": "Drogueria Caribe POS", "version": "0.1.0"}
