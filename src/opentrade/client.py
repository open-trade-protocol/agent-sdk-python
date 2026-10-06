"""OpenTrade Protocol client for AI agents.

Provides a unified async client for interacting with OpenTrade Protocol
nodes. Supports listing management, search, negotiation, and escrow
operations.
"""

from __future__ import annotations

import httpx
from typing import Any, Optional
from urllib.parse import urljoin


class OpenTradeError(Exception):
    """Base exception for OpenTrade client errors."""
    pass


class ListingNotFoundError(OpenTradeError):
    """Raised when a listing is not found."""
    pass


class APIError(OpenTradeError):
    """Raised when the API returns an error response."""
    def __init__(self, status_code: int, message: str, details: Optional[dict] = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"API error {status_code}: {message}")


class OpenTradeClient:
    """Unified client for the OpenTrade Protocol API.

    Enables AI agents to search listings, negotiate, and manage escrow
    contracts across all federated OpenTrade nodes.

    Usage:
        async with OpenTradeClient() as client:
            listings = await client.list_listings(category="snowboards")
            listing = await client.get_listing("urn:opentrade:listing:xxx")
            result = await client.create_listing({...})
            search = await client.search("snowboard", category="snowboards")
    """

    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the underlying httpx client."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._headers,
            )
        return self._http

    def _headers(self) -> dict[str, str]:
        """Default request headers."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry logic and error handling."""
        client = await self._get_client()
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.request(
                    method=method,
                    url=path,
                    json=json_data,
                    params=params,
                )

                if response.status_code == 404:
                    raise ListingNotFoundError(f"Resource not found: {path}")

                if 400 <= response.status_code < 500:
                    raise APIError(
                        status_code=response.status_code,
                        message=response.text[:500],
                    )

                if response.status_code >= 500:
                    # Server error — retry
                    last_error = APIError(
                        status_code=response.status_code,
                        message=response.text[:500],
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        import asyncio
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                        continue

                return response.json() if response.content else {}

            except httpx.TimeoutException as e:
                last_error = OpenTradeError(f"Timeout on {method} {path}: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
            except httpx.NetworkError as e:
                last_error = OpenTradeError(f"Network error on {method} {path}: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue

        raise last_error or OpenTradeError(f"Request failed: {method} {path}")

    # ------------------------------------------------------------------
    # Listing operations
    # ------------------------------------------------------------------

    async def list_listings(
        self,
        category: str = "all",
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        """List and filter listings.

        Args:
            category: Filter by category (snowboards, bindings, boots, etc.)
            limit: Max number of results (1-100)
            cursor: Pagination cursor from previous response

        Returns:
            Dict with 'total' and 'items' keys
        """
        return await self._request(
            method="GET",
            url="/v1/api/v1/listings",
            params={"category": category, "limit": min(limit, 100), "cursor": cursor},
        )

    async def get_listing(self, listing_id: str) -> dict[str, Any]:
        """Get a single listing by ID.

        Args:
            listing_id: The listing URN or ID

        Returns:
            Listing dict matching the OpenAPI Listing schema
        """
        return await self._request(
            method="GET",
            url=f"/v1/listings/{listing_id}",
        )

    async def create_listing(self, data: dict[str, Any]) -> dict[str, Any]:
        """Publish a new listing.

        Args:
            data: Listing data matching ListingCreate schema:
                - title (required)
                - price (required)
                - currency (default: RUB)
                - category (required)
                - seller_node_id (required)
                - description (optional)
                - condition (default: used_good)

        Returns:
            Created listing dict
        """
        return await self._request(
            method="POST",
            url="/v1/api/v1/listings",
            json_data=data,
        )

    async def update_listing(
        self,
        listing_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing listing.

        Args:
            listing_id: The listing URN or ID
            data: Fields to update

        Returns:
            Updated listing dict
        """
        return await self._request(
            method="PUT",
            url=f"/v1/listings/{listing_id}",
            json_data=data,
        )

    async def delete_listing(self, listing_id: str) -> dict[str, Any]:
        """Delete a listing.

        Args:
            listing_id: The listing URN or ID

        Returns:
            Confirmation dict
        """
        return await self._request(
            method="DELETE",
            url=f"/v1/listings/{listing_id}",
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        buyer_lat: Optional[float] = None,
        buyer_lon: Optional[float] = None,
        sort: str = "relevance",
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> dict[str, Any]:
        """Full-text search across all federated listings.

        Combines Meilisearch full-text search with PostgreSQL filters.

        Args:
            query: Search query string
            category: Filter by category
            condition: Filter by condition (new, used_good, etc.)
            price_min: Minimum price filter
            price_max: Maximum price filter
            buyer_lat: Buyer latitude for cost calculation
            buyer_lon: Buyer longitude for cost calculation
            sort: Sort order (relevance, price_asc, price_desc, newest)
            limit: Max results
            cursor: Pagination cursor

        Returns:
            Dict with 'results', 'total_estimated', 'next_cursor', 'search_metadata'
        """
        body: dict[str, Any] = {"query": query}
        if category and category != "all":
            body["category"] = category
        if condition:
            body["condition"] = condition
        if price_min is not None:
            body["price_min"] = price_min
        if price_max is not None:
            body["price_max"] = price_max
        if buyer_lat is not None:
            body["buyer_lat"] = buyer_lat
        if buyer_lon is not None:
            body["buyer_lon"] = buyer_lon
        if sort != "relevance":
            body["sort"] = sort
        body["limit"] = min(limit, 100)
        if cursor:
            body["cursor"] = cursor

        return await self._request(
            method="POST",
            url="/v1/api/v1/search",
            json_data=body,
        )

    # ------------------------------------------------------------------
    # Escrow operations
    # ------------------------------------------------------------------

    async def escrow_create(
        self,
        listing_id: str,
        terms: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new escrow contract.

        Args:
            listing_id: The listing to escrow
            terms: Escrow terms (buyer, seller, amount, release conditions, etc.)

        Returns:
            Created escrow contract dict
        """
        return await self._request(
            method="POST",
            url="/v1/escrow",
            json_data={"listing_id": listing_id, **terms},
        )

    async def escrow_status(self, escrow_id: str) -> dict[str, Any]:
        """Get the status of an escrow contract.

        Args:
            escrow_id: The escrow contract ID

        Returns:
            Escrow status dict
        """
        return await self._request(
            method="GET",
            url=f"/v1/escrow/{escrow_id}",
        )

    async def escrow_release(
        self,
        escrow_id: str,
        buyer_confirmation: Optional[str] = None,
    ) -> dict[str, Any]:
        """Release funds from an escrow contract.

        Args:
            escrow_id: The escrow contract ID
            buyer_confirmation: Optional buyer confirmation message

        Returns:
            Release confirmation dict
        """
        return await self._request(
            method="POST",
            url=f"/v1/escrow/{escrow_id}/release",
            json_data={"buyer_confirmation": buyer_confirmation} if buyer_confirmation else {},
        )

    async def escrow_dispute(
        self,
        escrow_id: str,
        reason: str,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Open a dispute on an escrow contract.

        Args:
            escrow_id: The escrow contract ID
            reason: Dispute reason category
            description: Detailed description

        Returns:
            Dispute creation confirmation
        """
        return await self._request(
            method="POST",
            url=f"/v1/escrow/{escrow_id}/dispute",
            json_data={"reason": reason, "description": description},
        )

    # ------------------------------------------------------------------
    # Negotiation
    # ------------------------------------------------------------------

    async def negotiate(self, offer: dict[str, Any]) -> dict[str, Any]:
        """Send a negotiation offer.

        Args:
            offer: Negotiation data including listing_id, price, terms

        Returns:
            Negotiation response (counter-offer or acceptance)
        """
        return await self._request(
            method="POST",
            url="/v1/negotiation",
            json_data=offer,
        )

    async def get_negotiation(self, negotiation_id: str) -> dict[str, Any]:
        """Get negotiation status.

        Args:
            negotiation_id: The negotiation ID

        Returns:
            Negotiation state dict
        """
        return await self._request(
            method="GET",
            url=f"/v1/negotiation/{negotiation_id}",
        )

    # ------------------------------------------------------------------
    # User/Registration
    # ------------------------------------------------------------------

    async def user_register(self, data: dict[str, Any]) -> dict[str, Any]:
        """Register a new user.

        Args:
            data: User registration data

        Returns:
            Created user dict with credentials
        """
        return await self._request(
            method="POST",
            url="/v1/users",
            json_data=data,
        )

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user by ID.

        Args:
            user_id: The user ID

        Returns:
            User dict
        """
        return await self._request(
            method="GET",
            url=f"/v1/users/{user_id}",
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check the health of the PEP Node.

        Returns:
            Health status dict with 'status', 'database', 'meilisearch', etc.
        """
        try:
            client = await self._get_client()
            response = await client.get("/v1/health")
            if response.status_code == 200:
                return response.json()
            return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self):
        """Async context manager entry."""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None
