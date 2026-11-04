"""Cliente HTTP compartido con reintentos y respeto a rate-limit de Factus."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class FactusHttpClient:
    """Wrapper sobre httpx.AsyncClient con reintentos simples y logs de auditoría."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: Optional[dict] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "FactusHttpClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._headers,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("FactusHttpClient no inicializado. Usar async with.")
        return self._client

    async def request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> httpx.Response:
        """Ejecuta una petición HTTP con reintento ante 5xx y 429."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self.client.request(
                    method, path, json=json, params=params, headers=headers
                )
                # Log de auditoría sin secrets
                logger.info(
                    "Factus HTTP %s %s -> %s (intento %d)",
                    method,
                    path,
                    resp.status_code,
                    attempt,
                )
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else 2 ** attempt
                    logger.warning(
                        "Factus %s reintento %d/%d tras %ss",
                        resp.status_code,
                        attempt,
                        self.max_retries,
                        wait,
                    )
                    await httpx.sleep(wait)
                    continue
                return resp
            except httpx.RequestError as exc:
                last_exc = exc
                logger.warning("Factus RequestError intento %d/%d: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    await httpx.sleep(2 ** attempt)
        if last_exc:
            raise last_exc
        raise RuntimeError("FactusHttpClient: se agotaron los reintentos sin respuesta")
