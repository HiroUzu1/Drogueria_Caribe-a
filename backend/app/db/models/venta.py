"""Modelo Venta: registro de ventas con pago confirmado."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Venta(Base):
    """Se crea una sola vez por transacción, cuando el pago queda validado."""

    __tablename__ = "ventas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    transaccion_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transacciones.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    cliente_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("clientes.id"), index=True, nullable=False
    )
    nit: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaccion: Mapped["Transaccion"] = relationship(back_populates="venta")
