"""Endpoints de Recaudos / Ventas (Módulo A).

- POST  /api/ventas                    -> crear venta PENDIENTE_PAGO + recaudo Factus Pay
- POST  /webhook/factus-pay            -> confirmación de pago (status=paid)
- GET   /api/ventas/{reference_code}/estado -> polling de estado del pago
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.cliente import Cliente
from app.db.models.transaccion import Transaccion, TransaccionItem
from app.schemas.cliente import ClienteCreate
from app.schemas.transaccion import (
    TransaccionCreate,
    TransaccionItemCreate,
    TransaccionOut,
    VentaResponse,
)
from app.services.factus_pay import FactusPayService, FactusPayAuthError, FactusPayNotFoundError, FactusPayValidationError

router = APIRouter(prefix="/api", tags=["ventas", "recaudos"])


def _generar_reference_code() -> str:
    return f"VENTA-{uuid.uuid4().hex[:12].upper()}"


async def _obtener_o_crear_cliente(
    db: AsyncSession,
    identificacion: str,
    nombres: Optional[str],
    apellidos: Optional[str],
    email: Optional[str],
    telefono: Optional[str],
) -> Cliente:
    result = await db.execute(select(Cliente).where(Cliente.identificacion == identificacion))
    cliente: Optional[Cliente] = result.scalar_one_or_none()
    if cliente is not None:
        return cliente
    cliente = Cliente(
        identificacion=identificacion,
        nombres=nombres,
        apellidos=apellidos,
        email=email,
        telefono=telefono,
    )
    db.add(cliente)
    await db.flush()
    return cliente


@router.post(
    "/ventas",
    response_model=VentaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear venta y recaudo Factus Pay",
)
async def crear_venta(
    venta_in: TransaccionCreate,
    db: AsyncSession = Depends(get_db),
) -> VentaResponse:
    """Registra una venta en PENDIENTE_PAGO, crea el recaudo en Factus Pay y retorna QR + breb_key."""
    # Buscar o registrar cliente por cédula
    cliente = await _obtener_o_crear_cliente(
        db,
        identificacion=venta_in.identificacion,
        nombres=None,
        apellidos=None,
        email=None,
        telefono=None,
    )

    # Crear transacción en estado PENDIENTE_PAGO
    reference_code = _generar_reference_code()
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

    total = 0.0
    subtotal = 0.0
    tax_amount = 0.0
    for item_in in venta_in.items:
        item_total = (item_in.price * item_in.quantity) - item_in.discount_amount + item_in.tax_amount
        item = TransaccionItem(
            transaccion_id=transaccion.id,
            producto_id=item_in.producto_id,
            code_reference=item_in.code_reference,
            name=item_in.name,
            quantity=item_in.quantity,
            price=item_in.price,
            discount_rate=item_in.discount_rate,
            discount_amount=item_in.discount_amount,
            subtotal=item_in.subtotal,
            tax_amount=item_in.tax_amount,
            total=item_in.total,
            unit_measure_code=item_in.unit_measure_code,
            standard_code=item_in.standard_code,
            taxes=item_in.taxes,
            withholding_taxes=item_in.withholding_taxes,
        )
        db.add(item)
        subtotal += item_in.subtotal
        tax_amount += item_in.tax_amount
        total += item_in.total

    transaccion.subtotal = subtotal
    transaccion.tax_amount = tax_amount
    transaccion.total = total
    await db.commit()
    await db.refresh(transaccion)

    # Crear recaudo en Factus Pay
    service = FactusPayService()
    try:
        recaudo = await service.crear_recaudo(
            reference_code=reference_code,
            amount=float(total),
            expiration_minutes=30,
            description=f"Venta {reference_code} - Drogueria Caribe",
        )
    except FactusPayValidationError as exc:
        await db.delete(transaccion)
        await db.commit()
        await service.aclose()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except FactusPayAuthError as exc:
        await service.aclose()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except Exception as exc:  # red de seguridad para errores de red / API externa
        await service.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error comunicando con Factus Pay: {exc}",
        )
    finally:
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


@router.post(
    "/webhook/factus-pay",
    summary="Webhook de confirmación de pago de Factus Pay",
)
async def webhook_factus_pay(
    key: str = Query(..., description="Llave secreta del webhook"),
    reference_code: Optional[str] = Query(None, description="Código de referencia del recaudo"),
    status_pago: Optional[str] = Query(None, alias="status", description="Estado del pago"),
    db: AsyncSession = Depends(get_db),
):
    """Valida la llave del webhook y, si status=paid, actualiza la venta a PAGADA."""
    service = FactusPayService()
    if not service.validar_webhook_key(key):
        await service.aclose()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Llave de webhook inválida.")

    if not reference_code:
        await service.aclose()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Falta el parámetro reference_code.",
        )

    # Si el webhook trae el estado, lo usamos; si no, consultamos polling a Factus Pay
    estado_final = status_pago
    if estado_final is None or estado_final.lower() != "paid":
        try:
            recaudo = await service.consultar_estado(reference_code)
        except FactusPayNotFoundError:
            await service.aclose()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recaudo no encontrado en Factus Pay.")
        except Exception as exc:
            await service.aclose()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error consultando estado en Factus Pay: {exc}",
            )
        estado_final = recaudo.get("status") or recaudo.get("estado")

    if estado_final and str(estado_final).lower() == "paid":
        result = await db.execute(select(Transaccion).where(Transaccion.reference_code == reference_code))
        transaccion: Optional[Transaccion] = result.scalar_one_or_none()
        if transaccion is None:
            await service.aclose()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
        transaccion.estado = "PAGADA"
        transaccion.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await service.aclose()
        return {"reference_code": reference_code, "estado": "PAGADA"}

    await service.aclose()
    return {"reference_code": reference_code, "estado": str(estado_final or "desconocido")}


@router.get(
    "/ventas/{reference_code}/estado",
    response_model=TransaccionOut,
    summary="Consultar estado de una venta (polling local)",
)
async def consultar_estado_venta(
    reference_code: str,
    db: AsyncSession = Depends(get_db),
) -> TransaccionOut:
    """Devuelve el estado actual de la venta. Útil para polling desde el frontend."""
    result = await db.execute(select(Transaccion).where(Transaccion.reference_code == reference_code))
    transaccion: Optional[Transaccion] = result.scalar_one_or_none()
    if transaccion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
    return transaccion
