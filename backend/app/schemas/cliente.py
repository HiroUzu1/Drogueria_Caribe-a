"""Esquemas Pydantic v2 para Cliente (Registro Express)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ClienteBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identificacion: str = Field(..., min_length=3, max_length=50, description="Cédula o NIT")
    nombres: Optional[str] = Field(None, max_length=100)
    apellidos: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None, description="Correo para envío de factura/comprobante")
    telefono: Optional[str] = Field(None, max_length=30)


class ClienteCreate(ClienteBase):
    """Esquema express para registro de cliente en ventas."""
    pass


class ClienteOut(ClienteBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ClienteBuscarOut(BaseModel):
    identificacion: str
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    existe: bool