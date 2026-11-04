"""Esquemas Pydantic v2 para Transaccion (venta) y sus ítems.

Incluye respuesta de venta con código QR base64 y llave Bre-B de Factus Pay.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class TransaccionItemBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    producto_id: Optional[UUID] = None
    code_reference: Optional[str] = Field(None, max_length=100)
    name: str = Field(..., max_length=200)
    quantity: float = Field(1, gt=0)
    price: float = Field(0, ge=0)
    discount_rate: float = Field(0, ge=0, le=100)
    discount_amount: float = Field(0, ge=0)
    subtotal: float = Field(0, ge=0)
    tax_amount: float = Field(0, ge=0)
    total: float = Field(0, ge=0)
    unit_measure_code: Optional[str] = Field(None, max_length=10)
    standard_code: Optional[str] = Field(None, max_length=20)
    taxes: Optional[str] = None
    withholding_taxes: Optional[str] = None


class TransaccionItemCreate(TransaccionItemBase):
    pass


class TransaccionItemOut(TransaccionItemBase):
    id: UUID
    transaccion_id: UUID
    created_at: datetime
    updated_at: datetime


class TransaccionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference_code: str = Field(..., max_length=100)
    cliente_id: UUID
    estado: Optional[str] = Field("PENDIENTE_PAGO", max_length=40)
    observacion: Optional[str] = None


class TransaccionCreate(BaseModel):
    """Entrada de POST /api/ventas: cédula + ítems."""
    identificacion: str = Field(..., min_length=3, max_length=50)
    items: List[TransaccionItemCreate] = Field(..., min_length=1)
    observacion: Optional[str] = None


class TransaccionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_code: str
    cliente_id: UUID
    estado: str
    subtotal: float
    tax_amount: float
    total: float
    observacion: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    items: List[TransaccionItemOut] = []


class VentaResponse(BaseModel):
    """Respuesta de POST /api/ventas con link/QR de Factus Pay."""

    model_config = ConfigDict(from_attributes=True)

    venta_id: UUID
    reference_code: str
    estado: str
    payment_url: Optional[str] = None
    qr_code: Optional[str] = None
    breb_key: Optional[str] = None
    expires_at: Optional[str] = None
