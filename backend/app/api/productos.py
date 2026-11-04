"""Endpoints de Productos (catálogo)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.producto import Producto
from app.schemas.producto import ProductoOut

router = APIRouter(prefix="/api/productos", tags=["productos"])


@router.get(
    "",
    response_model=List[ProductoOut],
    summary="Lista productos con stock mayor a 0",
)
async def listar_productos(db: AsyncSession = Depends(get_db)) -> List[ProductoOut]:
    """Devuelve todos los productos disponibles (stock > 0)."""
    result = await db.execute(select(Producto).where(Producto.stock > 0))
    return result.scalars().all()


@router.get(
    "/{code_reference}",
    response_model=ProductoOut,
    summary="Obtiene un producto por código de referencia",
)
async def obtener_producto(
    code_reference: str = Path(..., description="Código único del producto"),
    db: AsyncSession = Depends(get_db),
) -> ProductoOut:
    """Devuelve un producto específico por su code_reference."""
    result = await db.execute(
        select(Producto).where(Producto.code_reference == code_reference)
    )
    producto: Optional[Producto] = result.scalar_one_or_none()
    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )
    return producto
