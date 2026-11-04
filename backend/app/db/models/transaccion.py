"""Modelo Transaccion (venta) y TransaccionItem."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaccion(Base):
    """Venta / transacción de punto de venta. Estado del cobro y facturación."""

    __tablename__ = "transacciones"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    reference_code: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )  # idempotencia vs Factus
    cliente_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estado: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="PENDIENTE_PAGO",
        index=True,
    )  # PENDIENTE_PAGO, PAGADA, FACTURADA, ERROR_FACTURACION, CANCELADA
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    qr_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qr_expires_at: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pagado_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cliente: Mapped["Cliente"] = relationship(back_populates="transacciones")
    items: Mapped[List["TransaccionItem"]] = relationship(
        back_populates="transaccion", cascade="all, delete-orphan"
    )
    venta: Mapped[Optional["Venta"]] = relationship(
        back_populates="transaccion", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Transaccion(id={self.id}, reference_code={self.reference_code}, "
            f"estado={self.estado})>"
        )


class TransaccionItem(Base):
    """Ítem de una transacción. Trazabilidad de producto, precio e impuestos DIAN."""

    __tablename__ = "transaccion_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    transaccion_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transacciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    producto_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("productos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=1)
    price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    unit_measure_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # DIAN 94
    standard_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # DIAN 999
    taxes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON impuestos
    withholding_taxes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    transaccion: Mapped["Transaccion"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TransaccionItem(id={self.id}, name={self.name})>"
