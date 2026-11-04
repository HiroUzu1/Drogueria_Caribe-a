"""Endpoints de Clientes (Módulo A).

- GET  /api/clientes/{identificacion}  -> búsqueda rápida por cédula
- POST /api/clientes                   -> registro express
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.cliente import Cliente
from app.schemas.cliente import (
    ClienteBuscarOut,
    ClienteCreate,
    ClienteOut,
)

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.get(
    "/{identificacion}",
    response_model=ClienteBuscarOut,
    summary="Búsqueda rápida de cliente por cédula",
)
async def buscar_cliente(
    identificacion: str = Path(..., description="Cédula o NIT del cliente"),
    db: AsyncSession = Depends(get_db),
) -> ClienteBuscarOut:
    """Devuelve si existe el cliente y sus datos básicos, o existe=False si no hay registro."""
    result = await db.execute(select(Cliente).where(Cliente.identificacion == identificacion))
    cliente: Optional[Cliente] = result.scalar_one_or_none()
    if cliente is None:
        return ClienteBuscarOut(
            identificacion=identificacion,
            nombres=None,
            apellidos=None,
            email=None,
            telefono=None,
            existe=False,
        )
    return ClienteBuscarOut(
        identificacion=cliente.identificacion,
        nombres=cliente.nombres,
        apellidos=cliente.apellidos,
        email=cliente.email,
        telefono=cliente.telefono,
        existe=True,
    )


@router.post(
    "",
    response_model=ClienteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registro express de cliente por cédula",
)
async def registrar_cliente(
    cliente_in: ClienteCreate,
    db: AsyncSession = Depends(get_db),
) -> ClienteOut:
    """Crea un cliente si no existe, o retorna el existente (idempotente por identificacion)."""
    result = await db.execute(select(Cliente).where(Cliente.identificacion == cliente_in.identificacion))
    existente: Optional[Cliente] = result.scalar_one_or_none()
    if existente is not None:
        return existente

    cliente = Cliente(**cliente_in.model_dump())
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente
