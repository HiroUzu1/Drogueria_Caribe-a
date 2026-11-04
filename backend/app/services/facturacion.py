"""Emisión de la factura electrónica (Factus v2) después de confirmar el pago."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Transaccion, Venta
from app.db.session import AsyncSessionLocal
from app.services.factus_bill import FactusBillClient

logger = logging.getLogger(__name__)

bill_client = FactusBillClient(
    settings.factus_bill_base_url,
    settings.factus_bill_client_id,
    settings.factus_bill_client_secret,
    settings.factus_bill_username,
    settings.factus_bill_password,
    settings.factus_numbering_range_id,
)


def construir_factura(tx: Transaccion) -> dict:
    """Arma el JSON de /v2/bills/validate (operación estándar, contado, transferencia)."""
    cliente = tx.cliente
    items = []
    for item in tx.items:
        items.append(
            {
                "code_reference": item.code_reference,
                "name": item.name,
                "quantity": int(item.quantity),
                "discount_rate": 0,
                "price": float(item.price),
                "unit_measure_code": item.unit_measure_code or "94",
                "standard_code": item.standard_code or "999",
                "taxes": json.loads(item.taxes) if item.taxes else [{"is_excluded": True}],
            }
        )
    return {
        "numbering_range_id": settings.factus_numbering_range_id,
        "operation_type": 10,
        "reference_code": tx.reference_code,
        "observation": tx.observacion or "",
        "payment_details": [
            {
                "payment_form": 1,
                "payment_method_code": 47,
                "reference_code": tx.reference_code,
                "amount": float(tx.total),
            }
        ],
        "customer": {
            "identification_document_code": "31",  # NIT
            "identification": cliente.identificacion,
            "dv": cliente.dv,
            "legal_organization_code": "1",  # persona jurídica
            "names": cliente.razon_social or cliente.identificacion,
            "company": cliente.razon_social or cliente.identificacion,
            "email": cliente.email,
            "municipality_id": cliente.municipio_code or settings.factus_default_municipality_id,
        },
        "items": items,
    }


def _resumen_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Factus {exc.response.status_code}: {exc.response.text[:500]}"
    return f"{type(exc).__name__}: {exc}"[:1000]


async def emitir_factura(transaccion_id: UUID) -> str:
    """Factura una transacción PAGADA (o con ERROR_FACTURACION). Devuelve el estado final.

    Corre en segundo plano con su propia sesión; es idempotente porque bloquea la fila
    y solo procesa estados PAGADA o ERROR_FACTURACION.
    """
    async with AsyncSessionLocal() as db:
        tx = await db.scalar(
            select(Transaccion)
            .options(selectinload(Transaccion.items), selectinload(Transaccion.cliente))
            .where(Transaccion.id == transaccion_id)
            .with_for_update()
        )
        if tx is None or tx.estado not in {"PAGADA", "ERROR_FACTURACION"}:
            return tx.estado if tx else "not_found"
        venta = await db.scalar(select(Venta).where(Venta.transaccion_id == tx.id))
        if venta is None:
            return tx.estado

        try:
            payload = construir_factura(tx)
            try:
                respuesta = await bill_client.validate_bill(payload)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 409:
                    raise
                # Factura pendiente con la misma referencia: se elimina y se reintenta una vez
                await bill_client.destroy_pending_by_reference(tx.reference_code)
                respuesta = await bill_client.validate_bill(payload)
            bill = (respuesta.get("data") or {}).get("bill") or respuesta.get("data") or {}
            if bill.get("is_validated") is False or not bill.get("cufe"):
                raise ValueError(f"Factus no validó la factura: {json.dumps(bill.get('errors'), ensure_ascii=False)[:500]}")
            links = (respuesta.get("data") or {}).get("links") or {}
            venta.factura_numero = bill.get("number")
            venta.cufe = bill.get("cufe")
            venta.factura_url = links.get("public_url") or bill.get("public_url")
            venta.factura_error = None
            tx.estado = "FACTURADA"
        except Exception as exc:  # noqa: BLE001 - el error se guarda para reintentar
            logger.exception("Falló la facturación de %s", tx.reference_code)
            venta.factura_error = _resumen_error(exc)
            tx.estado = "ERROR_FACTURACION"
        await db.commit()
        return tx.estado


def impuestos_linea(precio: Decimal, cantidad: int, excluido: bool, tasa: Decimal) -> tuple[Decimal, str]:
    """Devuelve (IVA de la línea, JSON de impuestos para la factura)."""
    if excluido or tasa == 0:
        return Decimal("0.00"), json.dumps([{"is_excluded": True}])
    iva = (precio * cantidad * tasa / Decimal(100)).quantize(Decimal("0.01"))
    return iva, json.dumps([{"code": "01", "rate": f"{tasa:.2f}"}])
