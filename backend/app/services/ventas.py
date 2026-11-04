"""Confirmación de pagos: valida referencia e importe, descuenta stock y registra la venta."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Producto, Transaccion, Venta

# Referencias a las tareas de facturación en curso (evita que el recolector de basura las cancele)
_tareas_facturacion: set[asyncio.Task] = set()


def _programar_factura(transaccion_id) -> None:
    """Emite la factura en segundo plano para que el webhook responda a Factus en menos de 10 s."""
    from app.services.facturacion import emitir_factura

    tarea = asyncio.create_task(emitir_factura(transaccion_id))
    _tareas_facturacion.add(tarea)
    tarea.add_done_callback(_tareas_facturacion.discard)


async def confirmar_pago(db: AsyncSession, reference_code: str, amount: Decimal) -> str:
    """Resultado: pagada | not_found | amount_mismatch | not_pending | sin_stock.

    Idempotente: repetir el webhook de una venta ya pagada devuelve "pagada".
    El stock solo se descuenta aquí, con la fila de la transacción bloqueada.
    """
    tx = await db.scalar(
        select(Transaccion)
        .options(selectinload(Transaccion.items), selectinload(Transaccion.cliente))
        .where(Transaccion.reference_code == reference_code)
        .with_for_update()
    )
    if tx is None:
        return "not_found"
    if Decimal(tx.total) != amount:
        return "amount_mismatch"
    if tx.estado == "PAGADA":
        return "pagada"
    if tx.estado != "PENDIENTE_PAGO":
        return "not_pending"

    for item in tx.items:
        if item.producto_id is None:
            continue
        result = await db.execute(
            update(Producto)
            .where(Producto.id == item.producto_id, Producto.stock >= int(item.quantity))
            .values(stock=Producto.stock - int(item.quantity))
        )
        if result.rowcount != 1:
            await db.rollback()
            await db.execute(
                update(Transaccion)
                .where(Transaccion.reference_code == reference_code)
                .values(estado="SIN_STOCK")  # pago recibido sin inventario: requiere devolución
            )
            await db.commit()
            return "sin_stock"

    now = datetime.now(timezone.utc)
    tx.estado = "PAGADA"
    tx.pagado_en = now
    tx.completed_at = now
    db.add(
        Venta(
            transaccion_id=tx.id,
            cliente_id=tx.cliente_id,
            nit=f"{tx.cliente.identificacion}-{tx.cliente.dv}" if tx.cliente.dv else tx.cliente.identificacion,
            total=tx.total,
        )
    )
    await db.commit()
    # Solo aquí la venta pasa de PENDIENTE_PAGO a PAGADA, así que la factura se programa una sola vez
    _programar_factura(tx.id)
    return "pagada"
