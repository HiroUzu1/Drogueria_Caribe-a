"""Cliente HTTP asíncrono con reintentos para las APIs de Factus."""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

_RETRY_STATUS = {429, 502, 503, 504}


class FactusHttpClient:
    def __init__(
        self,
        base_url: str,
        headers: Optional[dict] = None,
        timeout: float = 15.0,
        retries: int = 2,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout
        )
        self._retries = retries

    async def __aenter__(self) -> "FactusHttpClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._client.aclose()

    async def request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.TransportError:
                if attempt == self._retries:
                    raise
            else:
                if response.status_code not in _RETRY_STATUS or attempt == self._retries:
                    return response
            await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError("unreachable")
