"""Rutas de clientes (identificados por NIT)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.db.models import Cliente
from app.schemas.cliente import ClienteOut, ClienteUpdate
from app.services.nit import parse_nit

router = APIRouter(prefix="/api/clientes", tags=["clientes"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[ClienteOut])
async def listar_clientes(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Cliente).order_by(Cliente.created_at.desc()).limit(limit).offset(offset)
    )
    return result.all()


@router.get("/{nit}", response_model=ClienteOut)
async def obtener_cliente(nit: str, db: AsyncSession = Depends(get_db)):
    try:
        numero, _ = parse_nit(nit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cliente = await db.scalar(select(Cliente).where(Cliente.identificacion == numero))
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return cliente


@router.patch("/{nit}", response_model=ClienteOut)
async def actualizar_cliente(nit: str, payload: ClienteUpdate, db: AsyncSession = Depends(get_db)):
    try:
        numero, _ = parse_nit(nit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cliente = await db.scalar(select(Cliente).where(Cliente.identificacion == numero))
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    await db.commit()
    return cliente
