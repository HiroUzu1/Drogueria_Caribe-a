"""Carga productos de ejemplo (idempotente por SKU).

Uso (dentro del contenedor): python -m app.seed
"""

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Producto
from app.db.session import AsyncSessionLocal

PRODUCTOS = [
    ("DOLEX-500", "Dolex Forte 500mg x24", "14500", 50, True),
    ("AMOX-500", "Amoxicilina 500mg x30", "22000", 40, True),
    ("ISDIN-50", "Protector Solar ISDIN 50+ 50ml", "95000", 15, False),
    ("REDOXON-ZN", "Redoxon Total C + Zinc x10", "35000", 30, False),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for sku, nombre, precio, stock, excluido in PRODUCTOS:
            if await db.scalar(select(Producto).where(Producto.sku == sku)):
                continue
            db.add(
                Producto(
                    sku=sku,
                    nombre=nombre,
                    precio_cop=Decimal(precio),
                    stock=stock,
                    iva_excluido=excluido,
                    iva_rate=Decimal("19.00"),
                )
            )
        await db.commit()
    print("Productos de ejemplo cargados.")


if __name__ == "__main__":
    asyncio.run(main())
