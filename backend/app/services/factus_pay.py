"""Cliente para Factus Pay (Sandbox).

Endpoints reales (docs https://pay-developers.factus.com.co):
- POST /auth                                   -> {email, password} -> {token}
- POST /v1/collections                         -> crear recaudo
- GET  /v1/collections/:referenceCode          -> ver estado
- POST webhook (factores externos a la API)

Respuestas vienen envueltas: {"data": {...}, "status": "success", "message": "..."}
"""

from __future__ import annotations

import hmac
from typing import Optional

import httpx

from app.core.config import settings


class FactusPayAuthError(Exception):
    """Error de autenticación contra Factus Pay (401 persistente)."""


class FactusPayValidationError(Exception):
    """Payload inválido para Factus Pay (422)."""


class FactusPayNotFoundError(Exception):
    """Recurso no encontrado en Factus Pay (404)."""


class FactusPayService:
    """Servicio de Factus Pay con httpx async y reuso de token."""

    def __init__(self) -> None:
        self.base_url = settings.factus_pay_base_url.rstrip("/")
        self.email = settings.factus_pay_email
        self.password = settings.factus_pay_password
        self.webhook_secret = settings.factus_pay_webhook_secret
        self._access_token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=False,
            )
        return self._client

    async def _auth(self) -> str:
        """POST /auth. Obtiene (o reusa) el token."""
        if self._access_token:
            return self._access_token

        client = await self._get_client()
        resp = await client.post(
            "/auth",
            json={"email": self.email, "password": self.password},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code == 401:
            raise FactusPayAuthError("Credenciales de Factus Pay inválidas (401).")
        if resp.status_code == 422:
            raise FactusPayValidationError("Payload de auth inválido (422).")
        if resp.status_code == 302:
            raise FactusPayAuthError("Factus Pay redirigió; ver SDK de auth.")
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("token") or data.get("access_token") or ""
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token or ''}",
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
        resp = await client.request(method, path, json=json, params=params, headers=self._auth_headers())

        if resp.status_code == 401 and retry_auth:
            self._access_token = None
            await self._auth()
            resp = await client.request(method, path, json=json, params=params, headers=self._auth_headers())

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
        expiration: int = 1800,
    ) -> dict:
        """POST /v1/collections. Retorna respuesta completa de la API."""
        resp = await self._request(
            "POST",
            "/v1/collections",
            json={
                "reference_code": reference_code,
                "amount": amount,
                "expiration": expiration,
            },
        )
        return resp.json()

    async def consultar_estado(self, reference_code: str) -> dict:
        """GET /v1/collections/{referenceCode}."""
        resp = await self._request("GET", f"/v1/collections/{reference_code}")
        return resp.json()

    def validar_webhook_key(self, key: str) -> bool:
        return hmac.compare_digest(str(key), str(self.webhook_secret))

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
