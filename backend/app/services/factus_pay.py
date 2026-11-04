"""Cliente para Factus Pay (Sandbox).

Endpoints:
- POST /auth        -> obtención y reuso de token Bearer
- POST /v1/collections -> creación de recaudo (QR / llave Bre-B)
- GET  /v1/collections/:referenceCode -> polling de estado

Manejo de errores HTTP:
- 401 -> re-autenticación y reintento una vez
- 422 -> error de validación de payload
- 404 -> recurso no encontrado
"""

from __future__ import annotations

from typing import Optional

import httpx
from pydantic import BaseModel, ConfigDict

from app.core.config import settings


class FactusPayAuthError(Exception):
    """Error de autenticación contra Factus Pay (401 persistente)."""


class FactusPayValidationError(Exception):
    """Payload inválido para Factus Pay (422)."""


class FactusPayNotFoundError(Exception):
    """Recurso no encontrado en Factus Pay (404)."""


class FactusPayService:
    """Servicio de Factus Pay con cliente HTTP asíncrono y reuso de token."""

    def __init__(self) -> None:
        self.base_url = settings.factus_pay_base_url.rstrip("/")
        self.client_id = settings.factus_pay_client_id
        self.client_secret = settings.factus_pay_client_secret
        self.webhook_secret = settings.factus_pay_webhook_secret
        self._access_token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def _auth(self) -> str:
        """POST /auth. Obtiene (o reusa) el token Bearer."""
        if self._access_token:
            return self._access_token

        client = await self._get_client()
        resp = await client.post(
            "/auth",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if resp.status_code == 401:
            raise FactusPayAuthError("Credenciales de Factus Pay inválidas (401).")
        if resp.status_code == 422:
            raise FactusPayValidationError("Payload de auth inválido (422).")
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token") or data.get("token", "")
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        token = self._access_token or ""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
        retry_auth: bool = True,
    ) -> httpx.Response:
        client = await self._get_client()
        await self._auth()
        headers = self._auth_headers()
        resp = await client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code == 401 and retry_auth:
            # Token expirado: forzar re-auth y reintentar una vez
            self._access_token = None
            await self._auth()
            headers = self._auth_headers()
            resp = await client.request(method, path, json=json, params=params, headers=headers)

        if resp.status_code == 422:
            raise FactusPayValidationError(
                f"Validación fallida en {method} {path} (422): {resp.text}"
            )
        if resp.status_code == 404:
            raise FactusPayNotFoundError(f"Recurso no encontrado en {method} {path} (404).")

        resp.raise_for_status()
        return resp

    async def crear_recaudo(
        self,
        *,
        reference_code: str,
        amount: float,
        expiration_minutes: int = 30,
        description: Optional[str] = None,
    ) -> dict:
        """POST /v1/collections. Crea un recaudo con QR y llave Bre-B.

        Retorna dict con al menos: referenceCode, amount, qrCode (base64),
        brebKey, status, expiresAt.
        """
        payload = {
            "referenceCode": reference_code,
            "amount": amount,
            "expiration": expiration_minutes,
        }
        if description:
            payload["description"] = description

        resp = await self._request("POST", "/v1/collections", json=payload)
        return resp.json()

    async def consultar_estado(self, reference_code: str) -> dict:
        """GET /v1/collections/{referenceCode}. Polling de estado del pago."""
        resp = await self._request("GET", f"/v1/collections/{reference_code}")
        return resp.json()

    def validar_webhook_key(self, key: str) -> bool:
        """Valida la llave constante del webhook de Factus Pay."""
        return bool(self.webhook_secret) and key == self.webhook_secret

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# Esquemas de respuesta tipados (Pydantic v2) para uso en la API


class RecaudoCreado(BaseModel):
    """Respuesta de creación de recaudo en Factus Pay."""

    reference_code: str
    amount: float
    qr_code: Optional[str] = None
    breb_key: Optional[str] = None
    status: str
    expires_at: Optional[str] = None
    payment_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
