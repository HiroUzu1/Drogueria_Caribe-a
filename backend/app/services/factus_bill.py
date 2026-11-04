"""Cliente para Factus Facturación (Sandbox, API oficial v2)."""

from __future__ import annotations

from typing import Optional

from app.services.http_client import FactusHttpClient


class FactusBillClient:
    """Emite facturas electrónicas ante DIAN vía Factus v2."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        numbering_range_id: str | int,
    ) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.numbering_range_id = numbering_range_id
        self._access_token: Optional[str] = None

    async def _auth_headers(self) -> dict:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get_access_token(self) -> str:
        """Obtiene (o reusa) el access_token vía OAuth2 password grant."""
        if self._access_token:
            return self._access_token
        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
        }
        async with FactusHttpClient(self.base_url) as http:
            resp = await http.request_with_retry("POST", "/oauth/token", json=payload)
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data.get("access_token", "")
            return self._access_token

    async def validate_bill(self, bill_json: dict) -> dict:
        """Envía la factura a validación y retorna {cufe, number, links, ...}."""
        headers = await self._auth_headers()
        async with FactusHttpClient(self.base_url, headers=headers) as http:
            resp = await http.request_with_retry("POST", "/v2/bills/validate", json=bill_json)
            if resp.status_code == 409:
                # Factura pendiente: se debe eliminar por reference y reintentar (en el servicio)
                resp.raise_for_status()
            resp.raise_for_status()
            return resp.json()

    async def destroy_pending_by_reference(self, reference_code: str) -> None:
        """Elimina una factura pendiente para permitir reintento tras 409."""
        async with FactusHttpClient(self.base_url) as http:
            resp = await http.request_with_retry(
                "DELETE", f"/v2/bills/destroy/reference/{reference_code}"
            )
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()

    async def download_pdf(self, bill_number: str) -> bytes:
        async with FactusHttpClient(self.base_url) as http:
            resp = await http.request_with_retry(
                "GET", f"/v2/bills/{bill_number}/download-pdf"
            )
            resp.raise_for_status()
            return resp.content

    async def download_xml(self, bill_number: str) -> bytes:
        async with FactusHttpClient(self.base_url) as http:
            resp = await http.request_with_retry(
                "GET", f"/v2/bills/{bill_number}/download-xml/"
            )
            resp.raise_for_status()
            return resp.content
