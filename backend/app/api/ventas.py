"""Endpoints de Ventas (Módulo A, carrito en caja).

- POST  /api/ventas                          -> crear venta + cobro Factus Pay
- GET   /api/ventas/{reference_code}/estado   -> polling de estado
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.cliente import Cliente
from app.db.models.transaccion import Transaccion, TransaccionItem
from app.schemas.transaccion import (
    TransaccionCreate,
    TransaccionOut,
    VentaResponse,
)
from app.services.factus_pay import (
    FactusPayService,
    FactusPayAuthError,
    FactusPayNotFoundError,
    FactusPayValidationError,
)

router = APIRouter(prefix="/api", tags=["ventas"])


async def _generar_reference_code(db: AsyncSession) -> str:
    """Genera código único con formato TRX-YYYYMMDD-XXXX."""
    hoy = datetime.now(timezone.utc).strftime("%Y%m%d")
    for _ in range(10):
        sufijo = f"{random.SystemRandom().randrange(1000, 10000)}"
        codigo = f"TRX-{hoy}-{sufijo}"
        result = await db.execute(
            select(Transaccion).where(Transaccion.reference_code == codigo)
        )
        if result.scalar_one_or_none() is None:
            return codigo
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo generar un reference_code único.",
    )


async def _resolver_cliente(db: AsyncSession, venta_in: TransaccionCreate) -> Cliente:
    """Busca por cédula; crea o actualiza (campos no nulos) el cliente."""
    result = await db.execute(
        select(Cliente).where(Cliente.identificacion == venta_in.identificacion)
    )
    cliente: Optional[Cliente] = result.scalar_one_or_none()

    if cliente is None:
        cliente = Cliente(
            identificacion=venta_in.identificacion,
            nombres=venta_in.nombres,
            apellidos=venta_in.apellidos,
            email=venta_in.email,
            telefono=venta_in.telefono,
        )
        db.add(cliente)
        await db.flush()
    else:
        if venta_in.nombres is not None:
            cliente.nombres = venta_in.nombres
        if venta_in.apellidos is not None:
            cliente.apellidos = venta_in.apellidos
        if venta_in.email is not None:
            cliente.email = venta_in.email
        if venta_in.telefono is not None:
            cliente.telefono = venta_in.telefono
        await db.flush()

    return cliente


@router.post(
    "/ventas",
    response_model=VentaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crea una venta PENDIENTE_PAGO y el recaudo en Factus Pay",
)
async def crear_venta(
    venta_in: TransaccionCreate,
    db: AsyncSession = Depends(get_db),
) -> VentaResponse:
    """Flujo express: resolver cliente, guardar venta + items, llamar a Factus Pay."""
    cliente = await _resolver_cliente(db, venta_in)

    reference_code = await _generar_reference_code(db)

    transaccion = Transaccion(
        reference_code=reference_code,
        cliente_id=cliente.id,
        estado="PENDIENTE_PAGO",
        observacion=venta_in.observacion,
        subtotal=0.0,
        tax_amount=0.0,
        total=0.0,
    )
    db.add(transaccion)
    await db.flush()

    subtotal_global = 0.0
    tax_global = 0.0
    total_global = 0.0

    for item_in in venta_in.items:
        item_subtotal = round(
            float(item_in.price) * float(item_in.quantity)
            - float(item_in.discount_amount or 0),
            2,
        )
        item_tax = round(float(item_in.tax_amount or 0), 2)
        item_total = round(item_subtotal + item_tax, 2)

        db.add(
            TransaccionItem(
                transaccion_id=transaccion.id,
                producto_id=item_in.producto_id,
                code_reference=item_in.code_reference,
                name=item_in.name,
                quantity=item_in.quantity,
                price=item_in.price,
                discount_rate=item_in.discount_rate,
                discount_amount=item_in.discount_amount,
                subtotal=item_subtotal,
                tax_amount=item_tax,
                total=item_total,
                unit_measure_code=item_in.unit_measure_code,
                standard_code=item_in.standard_code,
                taxes=item_in.taxes,
                withholding_taxes=item_in.withholding_taxes,
            )
        )

        subtotal_global += item_subtotal
        tax_global += item_tax
        total_global += item_total

    transaccion.subtotal = round(subtotal_global, 2)
    transaccion.tax_amount = round(tax_global, 2)
    transaccion.total = round(total_global, 2)
    await db.flush()
    await db.commit()
    await db.refresh(transaccion)

    # Integración con Factus Pay
    service = FactusPayService()
    try:
        recaudo = await service.crear_recaudo(
            reference_code=transaccion.reference_code,
            amount=float(transaccion.total),
            expiration_minutes=30,
            description=f"Venta {transaccion.reference_code} - Drogueria Caribe",
        )
    except FactusPayValidationError as exc:
        await service.aclose()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except FactusPayAuthError as exc:
        await service.aclose()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        )
    except FactusPayNotFoundError as exc:
        await service.aclose()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
    except Exception as exc:
        await service.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error comunicando con Factus Pay: {exc}",
        )
    finally:
        pass

    await service.aclose()

    return VentaResponse(
        venta_id=transaccion.id,
        reference_code=transaccion.reference_code,
        estado=transaccion.estado,
        payment_url=recaudo.get("payment_url"),
        qr_code=recaudo.get("qrCode") or recaudo.get("qr_code"),
        breb_key=recaudo.get("brebKey") or recaudo.get("breb_key"),
        expires_at=recaudo.get("expiresAt") or recaudo.get("expires_at"),
    )


@router.get(
    "/ventas/{reference_code}/estado",
    response_model=TransaccionOut,
    summary="Consultar estado de una venta (polling local)",
)
async def consultar_estado_venta(
    reference_code: str,
    db: AsyncSession = Depends(get_db),
) -> TransaccionOut:
    """Devuelve el estado actual de la venta."""
    result = await db.execute(
        select(Transaccion).where(Transaccion.reference_code == reference_code)
    )
    transaccion: Optional[Transaccion] = result.scalar_one_or_none()
    if transaccion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada."
        )
    return transaccion
