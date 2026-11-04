"""Cliente para Factus Pay (Sandbox). Endpoints por confirmar."""

from __future__ import annotations

from typing import Optional

from app.services.http_client import FactusHttpClient


class FactusPayClient:
    """Genera cobros (link/QR) y consulta estado de pago en Factus Pay."""

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret

    async def create_collection(
        self,
        *,
        amount: float,
        reference_code: str,
        description: str,
        currency: str = "COP",
        expiration_minutes: int = 30,
        redirect_url: Optional[str] = None,
    ) -> dict:
        """Crea un cobro y retorna {id, payment_url, qr_code, status, expires_at}.

        Nota: payload y endpoints de Factus Pay están marcados POR CONFIRMAR.
        """
        headers = {
            "Authorization": f"Bearer {self.client_secret}",
            "Content-Type": "application/json",
        }
        payload = {
            "amount": amount,
            "reference_code": reference_code,
            "description": description,
            "currency": currency,
            "expiration_minutes": expiration_minutes,
        }
        if redirect_url:
            payload["redirect_url"] = redirect_url

        async with FactusHttpClient(self.base_url, headers=headers) as http:
            resp = await http.request_with_retry("POST", "/collections", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_collection(self, collection_id: str) -> dict:
        """Consulta estado de un cobro (polling)."""
        async with FactusHttpClient(self.base_url) as http:
            resp = await http.request_with_retry("GET", f"/collections/{collection_id}")
            resp.raise_for_status()
            return resp.json()
