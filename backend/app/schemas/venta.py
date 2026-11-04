"""Esquemas para productos (inventario) y ventas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.nit import parse_nit


class ProductoCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    nombre: str = Field(min_length=1, max_length=200)
    precio_cop: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    stock: int = Field(ge=0)
    iva_excluido: bool = True
    iva_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100, max_digits=5, decimal_places=2)

    @field_validator("sku", "nombre")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El campo no puede estar vacío.")
        return v


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=200)
    precio_cop: Optional[Decimal] = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    stock: Optional[int] = Field(default=None, ge=0)
    activo: Optional[bool] = None
    iva_excluido: Optional[bool] = None
    iva_rate: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    nombre: str
    precio_cop: Decimal
    stock: int
    activo: bool
    iva_excluido: bool
    iva_rate: Decimal


class VentaItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    cantidad: int = Field(gt=0, le=10000)

    @field_validator("sku")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class VentaCreate(BaseModel):
    nit: str = Field(min_length=6, max_length=32)
    razon_social: str = Field(min_length=1, max_length=150)
    email: EmailStr
    items: List[VentaItemCreate] = Field(min_length=1, max_length=100)
    observacion: Optional[str] = Field(default=None, max_length=500)

    @field_validator("nit")
    @classmethod
    def _validate_nit(cls, v: str) -> str:
        number, dv = parse_nit(v)
        return f"{number}-{dv}"

    @field_validator("items")
    @classmethod
    def _unique_skus(cls, v: List[VentaItemCreate]) -> List[VentaItemCreate]:
        skus = [i.sku.casefold() for i in v]
        if len(skus) != len(set(skus)):
            raise ValueError("Cada SKU solo puede aparecer una vez.")
        return v


class VentaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code_reference: Optional[str]
    name: str
    quantity: Decimal
    price: Decimal
    total: Decimal


class TransaccionPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference_code: str
    estado: str
    total: Decimal
    qr_code: Optional[str]
    qr_expires_at: Optional[str]
    created_at: datetime
    pagado_en: Optional[datetime]
    items: List[VentaItemOut]


class RegistroVentaOut(BaseModel):
    id: UUID
    transaccion_id: UUID
    reference_code: str
    nit: str
    total: Decimal
    created_at: datetime
    factura_numero: Optional[str] = None
    cufe: Optional[str] = None
    factura_url: Optional[str] = None
    factura_error: Optional[str] = None
    items: List[VentaItemOut]


class FactusPaymentData(BaseModel):
    reference_code: str
    amount: Decimal
    status: str


class FactusWebhook(BaseModel):
    data: FactusPaymentData
