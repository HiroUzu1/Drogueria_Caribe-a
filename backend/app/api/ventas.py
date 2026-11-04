"""Rutas: inventario, ventas con cobro Factus Pay y webhook de pago."""

import secrets
import uuid
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_admin
from app.core.config import settings
from app.db.models import Cliente, Producto, Transaccion, TransaccionItem, Venta
from app.schemas.venta import (
    FactusWebhook,
    ProductoCreate,
    ProductoOut,
    ProductoUpdate,
    RegistroVentaOut,
    TransaccionPagoOut,
    VentaCreate,
)
from app.services.factus_pay import FactusPayClient, FactusPayError
from app.services.facturacion import emitir_factura, impuestos_linea
from app.services.nit import parse_nit
from app.services.ventas import confirmar_pago

router = APIRouter()

MIN_COBRO = Decimal("10000")  # mínimo real del sandbox de Factus Pay (la documentación dice 1000)
MAX_COBRO = Decimal("12100000")

factus_pay = FactusPayClient(
    settings.factus_pay_base_url, settings.factus_pay_email, settings.factus_pay_password
)


# ---------------------------------------------------------------- Inventario
@router.get("/api/productos", response_model=list[ProductoOut], tags=["inventario"])
async def listar_productos(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(Producto).where(Producto.activo.is_(True)).order_by(Producto.sku))
    return result.all()


@router.post(
    "/api/productos",
    response_model=ProductoOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    tags=["inventario"],
)
async def crear_producto(payload: ProductoCreate, db: AsyncSession = Depends(get_db)):
    producto = Producto(**payload.model_dump())
    db.add(producto)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="El SKU ya existe.") from exc
    return producto


@router.patch(
    "/api/productos/{sku}",
    response_model=ProductoOut,
    dependencies=[Depends(require_admin)],
    tags=["inventario"],
)
async def actualizar_producto(sku: str, payload: ProductoUpdate, db: AsyncSession = Depends(get_db)):
    producto = await db.scalar(select(Producto).where(Producto.sku == sku).with_for_update())
    if producto is None:
        raise HTTPException(status_code=404, detail="SKU no encontrado.")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(producto, campo, valor)
    await db.commit()
    return producto


# -------------------------------------------------------------------- Ventas
async def _cargar_transaccion(db: AsyncSession, **filtro) -> Transaccion | None:
    stmt = (
        select(Transaccion)
        .options(selectinload(Transaccion.items), selectinload(Transaccion.venta))
        .execution_options(populate_existing=True)
    )
    for campo, valor in filtro.items():
        stmt = stmt.where(getattr(Transaccion, campo) == valor)
    return await db.scalar(stmt)


@router.post(
    "/api/ventas",
    response_model=TransaccionPagoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["ventas"],
)
async def crear_venta(
    payload: VentaCreate, background: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    """Crea la venta PENDIENTE_PAGO y el QR. No toca el stock hasta confirmar el pago."""
    skus = [i.sku for i in payload.items]
    productos = {
        p.sku: p
        for p in (
            await db.scalars(select(Producto).where(Producto.sku.in_(skus), Producto.activo.is_(True)))
        ).all()
    }
    if faltantes := sorted(set(skus) - productos.keys()):
        raise HTTPException(404, f"SKU no encontrado o inactivo: {', '.join(faltantes)}.")
    for linea in payload.items:
        if productos[linea.sku].stock < linea.cantidad:
            raise HTTPException(409, f"Stock insuficiente para el SKU {linea.sku}.")

    lineas = []
    subtotal = Decimal("0")
    iva_total = Decimal("0")
    for i in payload.items:
        p = productos[i.sku]
        iva, taxes_json = impuestos_linea(p.precio_cop, i.cantidad, p.iva_excluido, p.iva_rate)
        base = p.precio_cop * i.cantidad
        subtotal += base
        iva_total += iva
        lineas.append((i, p, base, iva, taxes_json))
    subtotal = subtotal.quantize(Decimal("0.01"))
    total = (subtotal + iva_total).quantize(Decimal("0.01"))
    if not MIN_COBRO <= total <= MAX_COBRO:
        raise HTTPException(422, f"El total debe estar entre {MIN_COBRO} y {MAX_COBRO} COP.")

    numero, dv = parse_nit(payload.nit)
    cliente = await db.scalar(select(Cliente).where(Cliente.identificacion == numero))
    if cliente is None:
        cliente = Cliente(identificacion=numero, tipo_doc="NIT", dv=dv)
        db.add(cliente)
    cliente.dv = dv
    cliente.razon_social = payload.razon_social.strip()
    cliente.email = str(payload.email)

    reference_code = f"DC-{uuid.uuid4().hex.upper()}"
    tx = Transaccion(
        reference_code=reference_code,
        cliente=cliente,
        estado="PENDIENTE_PAGO",
        subtotal=subtotal,
        tax_amount=iva_total,
        total=total,
        observacion=payload.observacion,
        items=[
            TransaccionItem(
                producto_id=p.id,
                code_reference=i.sku,
                name=p.nombre,
                quantity=i.cantidad,
                price=p.precio_cop,
                subtotal=base,
                tax_amount=iva,
                total=base + iva,
                unit_measure_code="94",
                standard_code="999",
                taxes=taxes_json,
            )
            for i, p, base, iva, taxes_json in lineas
        ],
    )
    db.add(tx)
    await db.commit()  # la referencia debe existir antes de que Factus pueda notificarla

    try:
        data = await factus_pay.create_collection(
            reference_code=reference_code,
            amount=total,
            expiration_seconds=settings.factus_pay_qr_expiration_seconds,
        )
    except (FactusPayError, httpx.HTTPError) as exc:
        await db.execute(
            Transaccion.__table__.update()
            .where(Transaccion.reference_code == reference_code)
            .values(estado="ERROR_PAGO")
        )
        await db.commit()
        detail = str(exc) if isinstance(exc, FactusPayError) else "No fue posible conectar con Factus Pay."
        raise HTTPException(status_code=502, detail=detail) from exc

    tx.qr_code = data["qr"]
    tx.qr_expires_at = data.get("qr_expires_at")
    await db.commit()
    if data["status"] == "paid" and await confirmar_pago(db, reference_code, total) == "pagada":
        background.add_task(emitir_factura, tx.id)
    return await _cargar_transaccion(db, reference_code=reference_code)


@router.get("/api/ventas/{venta_id}", response_model=TransaccionPagoOut, tags=["ventas"])
async def obtener_venta(
    venta_id: UUID, background: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    tx = await _cargar_transaccion(db, id=venta_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    if tx.estado == "PENDIENTE_PAGO" and settings.factus_pay_poll_enabled:
        # Alternativa al webhook (que requiere URL pública): consulta el recaudo en Factus.
        try:
            data = await factus_pay.get_collection(tx.reference_code)
            if data.get("status") == "paid":
                resultado = await confirmar_pago(
                    db, tx.reference_code, Decimal(str(data.get("amount")))
                )
                if resultado == "pagada":
                    background.add_task(emitir_factura, tx.id)
                tx = await _cargar_transaccion(db, id=venta_id)
        except (FactusPayError, httpx.HTTPError, ArithmeticError):
            pass  # el cliente volverá a consultar; no se rompe la lectura
    return tx


@router.get(
    "/api/ventas",
    response_model=list[RegistroVentaOut],
    dependencies=[Depends(require_admin)],
    tags=["ventas"],
)
async def registro_de_ventas(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    ventas = await db.scalars(
        select(Venta)
        .options(selectinload(Venta.transaccion).selectinload(Transaccion.items))
        .order_by(Venta.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        RegistroVentaOut(
            id=v.id,
            transaccion_id=v.transaccion_id,
            reference_code=v.transaccion.reference_code,
            nit=v.nit,
            total=v.total,
            created_at=v.created_at,
            factura_numero=v.factura_numero,
            cufe=v.cufe,
            factura_url=v.factura_url,
            factura_error=v.factura_error,
            items=v.transaccion.items,
        )
        for v in ventas.all()
    ]


@router.post(
    "/api/ventas/{venta_id}/retry-bill",
    dependencies=[Depends(require_admin)],
    tags=["ventas"],
)
async def reintentar_facturacion(venta_id: UUID):
    estado = await emitir_factura(venta_id)
    if estado == "not_found":
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    return {"venta_id": venta_id, "estado": estado}


# ------------------------------------------------------------------- Webhook
@router.post("/webhooks", tags=["webhooks"])
@router.post("/webhook/factus-pay", tags=["webhooks"])
async def webhook_factus_pay(
    payload: FactusWebhook,
    background: BackgroundTasks,
    key: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not settings.factus_pay_webhook_key:
        raise HTTPException(status_code=503, detail="FACTUS_PAY_WEBHOOK_KEY no está configurada.")
    if not secrets.compare_digest(key, settings.factus_pay_webhook_key):
        raise HTTPException(status_code=401, detail="Llave de webhook inválida.")
    if payload.data.status != "paid":
        return {"received": True, "processed": False}

    resultado = await confirmar_pago(
        db, payload.data.reference_code, payload.data.amount.quantize(Decimal("0.01"))
    )
    if resultado == "sin_stock":
        # Respondemos 2xx: reintentar no sirve y el caso queda en estado SIN_STOCK.
        return {"received": True, "processed": False, "status": resultado}
    if resultado != "pagada":
        raise HTTPException(status_code=409, detail=f"No se pudo validar el pago: {resultado}.")
    tx_id = await db.scalar(
        select(Transaccion.id).where(Transaccion.reference_code == payload.data.reference_code)
    )
    background.add_task(emitir_factura, tx_id)  # responde rápido (<10 s) y factura después
    return {"received": True, "processed": True}
