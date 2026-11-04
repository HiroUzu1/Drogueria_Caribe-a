import asyncio
from app.db.session import engine
from app.db.base import Base

# Importar modelos para que SQLAlchemy los registre en Base.metadata
import app.db.models.cliente
import app.db.models.transaccion


async def init_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("¡Tablas creadas exitosamente en PostgreSQL!")


if __name__ == "__main__":
    asyncio.run(init_tables())