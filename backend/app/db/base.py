"""Base declarativa compartida por todos los modelos de dominio."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base para modelos SQLAlchemy 2.0."""

    pass
