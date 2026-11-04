"""Dependencias compartidas de la API."""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, get_db as _get_db


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión de base de datos asíncrona por request."""
    async for session in _get_db():
        yield session


__all__ = ["get_db"]
