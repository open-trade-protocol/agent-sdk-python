"""OpenTrade Protocol client for AI agents."""

from __future__ import annotations

import httpx
from typing import Any, Optional


class OpenTradeClient:
    """Unified client for the OpenTrade Protocol API.

    Enables AI agents to search listings, negotiate, and manage escrow
    contracts across all federated OpenTrade nodes.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8000",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def search(
        self,
        query: str,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search across all federated OpenTrade nodes."""
        body: dict[str, Any] = {"query": query}
        if filters:
            body["filters"] = filters
        body["limit"] = min(limit, 100)
        resp = await self._http.post("/search", json=body, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def get_listing(self, listing_id: str) -> dict[str, Any]:
        """Get a single listing by ID."""
        resp = await self._http.get(f"/listings/{listing_id}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def create_listing(self, data: dict[str, Any]) -> dict[str, Any]:
        """Publish a new listing."""
        resp = await self._http.post("/listings", json=data, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._http.aclose()
