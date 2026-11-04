"""Endpoints de Recaudos/Webhook de Factus Pay (Módulo A).

- POST  /webhook/factus-pay  -> confirmación de pago (status=paid)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.db.models.transaccion import Transaccion
from app.services.factus_pay import (
    FactusPayService,
    FactusPayAuthError,
    FactusPayNotFoundError,
    FactusPayValidationError,
)

router = APIRouter(prefix="/api", tags=["recaudos"])

# Reuse shared singleton for webhook secret validation
_FACTUS_PAY = None


def get_factus_pay_service() -> FactusPayService:
    global _FACTUS_PAY
    if _FACTUS_PAY is None:
        _FACTUS_PAY = FactusPayService()
    return _FACTUS_PAY


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

    if estado_final and str(estado_final).lower() == "paid":
        result = await db.execute(
            select(Transaccion).where(Transaccion.reference_code == reference_code)
        )
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
