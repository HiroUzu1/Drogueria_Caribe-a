"""Cliente para Factus Pay: POST /auth y POST /v1/collections."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.services.http_client import FactusHttpClient


class FactusPayError(Exception):
    pass


class FactusPayClient:
    """Crea recaudos (QR de cobro). El token de Factus no expira por tiempo."""

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url
        self.email = email
        self.password = password
        self._token: str | None = None

    async def _authenticate(self) -> str:
        if not self.email or not self.password:
            raise FactusPayError("Configura FACTUS_PAY_EMAIL y FACTUS_PAY_PASSWORD.")
        async with FactusHttpClient(self.base_url, headers={"Accept": "application/json"}) as http:
            resp = await http.request_with_retry(
                "POST", "/auth", json={"email": self.email, "password": self.password}
            )
        if resp.is_error:
            raise FactusPayError(f"Factus Pay rechazó la autenticación ({resp.status_code}).")
        token = resp.json().get("token")
        if not isinstance(token, str) or not token:
            raise FactusPayError("Factus Pay no devolvió un token válido.")
        return token

    async def _post_collection(self, token: str, payload: dict):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        async with FactusHttpClient(self.base_url, headers=headers) as http:
            return await http.request_with_retry("POST", "/v1/collections", json=payload)

    async def get_collection(self, reference_code: str) -> dict:
        """Detalle de un recaudo (GET /v1/collections/{reference_code}); sirve de polling sin webhook."""
        if self._token is None:
            self._token = await self._authenticate()
        resp = await self._get_collection(self._token, reference_code)
        if resp.status_code == 401:
            self._token = await self._authenticate()
            resp = await self._get_collection(self._token, reference_code)
        if resp.is_error:
            raise FactusPayError(f"Factus Pay no devolvió el recaudo ({resp.status_code}).")
        data = resp.json().get("data")
        if not isinstance(data, dict) or data.get("reference_code") != reference_code:
            raise FactusPayError("La respuesta de Factus Pay no coincide con la referencia.")
        return data

    async def _get_collection(self, token: str, reference_code: str):
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with FactusHttpClient(self.base_url, headers=headers) as http:
            return await http.request_with_retry("GET", f"/v1/collections/{reference_code}")

    async def create_collection(
        self, *, reference_code: str, amount: Decimal, expiration_seconds: int
    ) -> dict:
        """Retorna `data` de Factus: reference_code, amount, status, qr, qr_expires_at..."""
        payload = {
            "reference_code": reference_code,
            "amount": str(amount),
            "expiration": expiration_seconds,
        }
        if self._token is None:
            self._token = await self._authenticate()
        resp = await self._post_collection(self._token, payload)
        if resp.status_code == 401:  # token rotado por otra autenticación
            self._token = await self._authenticate()
            resp = await self._post_collection(self._token, payload)
        if resp.is_error:
            raise FactusPayError(f"Factus Pay rechazó el recaudo ({resp.status_code}).")

        data = resp.json().get("data")
        if not isinstance(data, dict) or data.get("reference_code") != reference_code:
            raise FactusPayError("La respuesta de Factus Pay no coincide con la referencia.")
        if data.get("status") not in {"ready", "paid"} or not isinstance(data.get("qr"), str):
            raise FactusPayError("Factus Pay no devolvió un recaudo listo con QR.")
        try:
            returned = Decimal(str(data.get("amount")))
        except InvalidOperation as exc:
            raise FactusPayError("Factus Pay devolvió un importe inválido.") from exc
        if returned != amount:
            raise FactusPayError("El importe devuelto por Factus Pay no coincide.")
        return data
