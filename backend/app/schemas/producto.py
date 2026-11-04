"""Esquemas Pydantic v2 para Producto."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductoBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code_reference: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    price: float = Field(0, ge=0)
    tax_rate: float = Field(0, ge=0, le=100)
    stock: int = Field(0, ge=0)
    unit_measure_code: str = Field("94", max_length=10)
    category: Optional[str] = Field(None, max_length=100)


class ProductoOut(ProductoBase):
    id: UUID
    created_at: datetime
