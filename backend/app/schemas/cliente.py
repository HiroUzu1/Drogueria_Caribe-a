"""Esquemas Pydantic para Cliente."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ClienteBase(BaseModel):
    identificacion: str = Field(..., min_length=3, max_length=50)
    tipo_doc: Optional[str] = Field(None, max_length=20)
    dv: Optional[str] = Field(None, max_length=2)
    nombres: Optional[str] = Field(None, max_length=100)
    apellidos: Optional[str] = Field(None, max_length=100)
    razon_social: Optional[str] = Field(None, max_length=150)
    direccion: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=30)
    municipio_code: Optional[str] = Field(None, max_length=10)
    org_type: Optional[str] = Field(None, max_length=20)
    tribute_code: Optional[str] = Field(None, max_length=20)
    responsibilities: Optional[str] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    razon_social: Optional[str] = None
    direccion: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None


class ClienteOut(ClienteBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
