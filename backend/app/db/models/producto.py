"""Modelo Producto: catálogo de medicamentos y productos de droguería."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Producto(Base):
    """Producto de la droguería (medicamento o artículo de cuidado personal)."""

    __tablename__ = "productos"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    code_reference: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    tax_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=0
    )
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_measure_code: Mapped[str] = mapped_column(
        String(10), nullable=False, default="94"
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Producto(id={self.id}, code_reference={self.code_reference}, "
            f"name={self.name})>"
        )
