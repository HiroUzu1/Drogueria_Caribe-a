"""Configuración de la aplicación basada en variables de entorno.

Usa pydantic-settings BaseSettings. Los valores reales se leen de `.env`
(que NO se commitea). `.env.example` contiene valores simulados de Sandbox.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno tipadas y validadas."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    app_debug: bool = True

    # --- Base de datos (asyncpg para FastAPI; psycopg2 para alembic/seed) ---
    database_url: str
    sync_database_url: str | None = None

    # --- Factus Facturación (Sandbox, API oficial v2) ---
    factus_bill_base_url: str = "https://api-sandbox.factus.com.co"
    factus_bill_client_id: str = ""
    factus_bill_client_secret: str = ""
    factus_bill_username: str = ""
    factus_bill_password: str = ""
    factus_numbering_range_id: str | int = 123
    factus_default_municipality_id: str = "980"  # id de municipio en Factus (Bogotá por defecto)

    # --- Factus Pay (Sandbox: https://pay-api-sandbox.factus.com.co) ---
    factus_pay_base_url: str = "https://pay-api-sandbox.factus.com.co"
    factus_pay_email: str = ""
    factus_pay_password: str = ""
    factus_pay_webhook_key: str = ""
    factus_pay_qr_expiration_seconds: int = 1800
    factus_pay_poll_enabled: bool = True

    # --- Administración (inventario y registro de ventas) ---
    admin_api_key: str = ""

    # --- Frontend ---
    vite_api_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cargada (cached para no leer .env cada vez)."""
    return Settings()


settings = get_settings()
