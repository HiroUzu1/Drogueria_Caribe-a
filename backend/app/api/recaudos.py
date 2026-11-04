"""Endpoints de Recaudos/Webhook de Factus Pay (Módulo A).

- POST  /webhook/factus-pay  -> confirmación de pago (status=paid)
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models.transaccion import Transaccion
from app.services.factus_pay import (
    FactusPayNotFoundError,
    FactusPayService,
)
from app.services.ventas import confirmar_pago

router = APIRouter(prefix="/api", tags=["recaudos"])


@router.post(
    "/webhook/factus-pay",
    summary="Webhook de confirmación de pago de Factus Pay",
)
async def webhook_factus_pay(
    key: str = Query(..., description="Llave secreta del webhook"),
    reference_code: Optional[str] = Query(None, description="Código de referencia del recaudo"),
    status_pago: Optional[str] = Query(None, alias="status", description="Estado del pago"),
    amount: Optional[float] = Query(None, description="Monto confirmado en Factus Pay"),
    payload: Optional[dict[str, Any]] = Body(None),
    db: AsyncSession = Depends(get_db),
):
    """Valida la llave del webhook y, si status=paid, confirma el pago, descuenta stock y crea la venta."""
    if payload:
        body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        reference_code = reference_code or body.get("reference_code") or body.get("referenceCode")
        status_pago = status_pago or body.get("status")
        amount = amount if amount is not None else body.get("amount")
        key = payload.get("key", key)

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

    estado_final = status_pago
    if estado_final is None or str(estado_final).lower() != "paid":
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
        if isinstance(recaudo, dict) and isinstance(recaudo.get("data"), dict):
            estado_final = recaudo["data"].get("status") or recaudo["data"].get("estado") or estado_final

    if estado_final and str(estado_final).lower() == "paid":
        result_tx = await db.execute(
            select(Transaccion).where(Transaccion.reference_code == reference_code)
        )
        transaccion = result_tx.scalar_one_or_none()
        if transaccion is None:
            await service.aclose()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")

        pay_amount = Decimal(str(amount)) if amount is not None else Decimal(str(transaccion.total))
        codigo = await confirmar_pago(db, reference_code, pay_amount)
        await service.aclose()

        if codigo == "pagada":
            return {"reference_code": reference_code, "estado": "PAGADA"}
        if codigo == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada.")
        if codigo == "amount_mismatch":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El monto confirmado no coincide.")
        if codigo == "sin_stock":
            return {"reference_code": reference_code, "estado": "PAGADA_SIN_STOCK"}
        return {"reference_code": reference_code, "estado": codigo}

    await service.aclose()
    return {"reference_code": reference_code, "estado": str(estado_final or "desconocido")}
