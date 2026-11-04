"""Modelo Cliente: identificador único (cédula/NIT) y datos fiscales."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Cliente(Base):
    """Cliente de la droguería. Identificación única (cédula/NIT)."""

    __tablename__ = "clientes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    identificacion: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # cédula / NIT
    tipo_doc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # CC, NIT, CE, PAS
    dv: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)  # dígito de verificación
    nombres: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    apellidos: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    razon_social: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    municipio_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # DANE
    org_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # régimen
    tribute_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    responsibilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    transacciones: Mapped[List["Transaccion"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cliente(id={self.id}, identificacion={self.identificacion})>"
