"""Script de seed masivo de productos (idempotente).

Puebla la tabla `productos` con un catálogo amplio de droguería colombiana.
Usa ON CONFLICT (code_reference) DO UPDATE para no duplicar registros.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.producto import Producto
from app.db.session import AsyncSessionLocal

PRODUCTOS: list[dict[str, Any]] = [
    # --- Analgésicos ---
    {"code_reference": "ACE-500", "name": "Acetaminofén 500mg", "price": 2500, "tax_rate": 5, "stock": 100, "category": "Analgésicos"},
    {"code_reference": "IBU-400", "name": "Ibuprofeno 400mg", "price": 3200, "tax_rate": 5, "stock": 100, "category": "Analgésicos"},
    {"code_reference": "DOLEX", "name": "Dolex", "price": 4500, "tax_rate": 5, "stock": 80, "category": "Analgésicos"},
    {"code_reference": "DICLO-50", "name": "Diclofenaco 50mg", "price": 8000, "tax_rate": 5, "stock": 90, "category": "Analgésicos"},
    {"code_reference": "BIOFEN", "name": "Naproxeno 250mg", "price": 9500, "tax_rate": 5, "stock": 85, "category": "Analgésicos"},
    # --- Hidratación ---
    {"code_reference": "PEDIALYTE", "name": "Pedialyte", "price": 12000, "tax_rate": 5, "stock": 50, "category": "Hidratación"},
    {"code_reference": "ELECTROLIT", "name": "Electrolit", "price": 9000, "tax_rate": 5, "stock": 60, "category": "Hidratación"},
    {"code_reference": "ORS", "name": "Suero Oral", "price": 5000, "tax_rate": 5, "stock": 120, "category": "Hidratación"},
    # --- Antisépticos ---
    {"code_reference": "ALCOHOL-70", "name": "Alcohol 70°", "price": 4500, "tax_rate": 5, "stock": 200, "category": "Antisépticos"},
    {"code_reference": "BETADINE", "name": "Povidona Yodada", "price": 11000, "tax_rate": 5, "stock": 60, "category": "Antisépticos"},
    # --- Vendajes ---
    {"code_reference": "CURITAS", "name": "Curitas", "price": 3500, "tax_rate": 5, "stock": 150, "category": "Vendajes"},
    # --- Cuidado del bebé ---
    {"code_reference": "WINNY", "name": "Pañales Winny", "price": 25000, "tax_rate": 5, "stock": 30, "category": "Cuidado del bebé"},
    {"code_reference": "PEQUENIN", "name": "Pañales Pequeñín", "price": 28000, "tax_rate": 5, "stock": 25, "category": "Cuidado del bebé"},
    # --- Vitaminas ---
    {"code_reference": "TARRITO-ROJO", "name": "Tarrito Rojo", "price": 18000, "tax_rate": 5, "stock": 40, "category": "Vitaminas"},
    {"code_reference": "REDOXON", "name": "Redoxon", "price": 15000, "tax_rate": 5, "stock": 60, "category": "Vitaminas"},
    # --- Higiene bucal ---
    {"code_reference": "COLGATE", "name": "Colgate", "price": 6500, "tax_rate": 5, "stock": 100, "category": "Higiene bucal"},
    # --- Antibióticos ---
    {"code_reference": "AMOX-500", "name": "Amoxicilina 500mg", "price": 18000, "tax_rate": 5, "stock": 70, "category": "Antibióticos"},
    # --- Gastrointestinal ---
    {"code_reference": "LOSEC", "name": "Omeprazol 20mg", "price": 22000, "tax_rate": 5, "stock": 50, "category": "Gastrointestinal"},
    {"code_reference": "GASTRO", "name": "Bismuto Subsalicilato", "price": 14000, "tax_rate": 5, "stock": 40, "category": "Gastrointestinal"},
    # --- Antialérgicos ---
    {"code_reference": "LORAT-10", "name": "Loratadina 10mg", "price": 12000, "tax_rate": 5, "stock": 80, "category": "Antialérgicos"},
    # --- Respiratorios ---
    {"code_reference": "VICKS", "name": "Jarabe para la tos", "price": 12000, "tax_rate": 5, "stock": 70, "category": "Respiratorios"},
    # --- Dermatología ---
    {"code_reference": "CETAPHIL", "name": "Crema Hidratante Cetaphil", "price": 35000, "tax_rate": 5, "stock": 30, "category": "Dermatología"},
    {"code_reference": "NEUTROGENA", "name": "Protector Solar Neutrogena", "price": 45000, "tax_rate": 5, "stock": 25, "category": "Dermatología"},
    {"code_reference": "SILCOPAN", "name": "Gel para contusión Silcopan", "price": 7000, "tax_rate": 5, "stock": 100, "category": "Dermatología"},
]


async def seed(db: AsyncSession) -> None:
    for data in PRODUCTOS:
        stmt = pg_insert(Producto).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Producto.code_reference],
            set_={
                "name": stmt.excluded.name,
                "price": stmt.excluded.price,
                "tax_rate": stmt.excluded.tax_rate,
                "stock": stmt.excluded.stock,
                "category": stmt.excluded.category,
                "unit_measure_code": stmt.excluded.unit_measure_code,
            },
        )
        await db.execute(stmt)
    await db.commit()
    print(f"Seed completado: {len(PRODUCTOS)} productos insertados/actualizados.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
