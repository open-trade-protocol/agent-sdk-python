"""OpenTrade Agent SDK — Python client for the OpenTrade Protocol.

This SDK enables AI agents to search, negotiate, and complete transactions
across all federated OpenTrade nodes using a single unified API.

Usage:
    from opentrade import Client

    client = Client(api_key="your_api_key")

    # Search across all federated nodes
    results = client.search(
        query="Jones Flagship 158",
        filters={"category": "snowboard", "condition": ["good", "like_new"]},
        buyer_location={"lat": 55.75, "lon": 37.61}
    )

    for listing in results:
        print(f"{listing.product.brand} {listing.product.model} - {listing.total_landed_cost.total} RUB")
"""

from __future__ import annotations

import json
import time
import hashlib
import hmac
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin


class Condition(str, Enum):
    """Product condition grades."""
    NEW = "new"
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class SortOrder(str, Enum):
    """Sort options for search results."""
    RELEVANCE = "relevance_score"
    TOTAL_COST_ASC = "total_cost_asc"
    TOTAL_COST_DESC = "total_cost_desc"
    NEWEST = "newest"
    SELLER_RATING_DESC = "seller_rating_desc"


@dataclass
class Location:
    """Geographic location."""
    lat: float
    lon: float
    geohash: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


@dataclass
class SearchFilters:
    """Search filter parameters."""
    category: Optional[str] = None
    brand: Optional[list[str]] = None
    condition: Optional[list[Condition]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    seller_min_rating: Optional[float] = None
    seller_max_dispute_rate: Optional[float] = None
    ai_confidence_min: Optional[float] = None
    has_serial_verification: Optional[bool] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None


@dataclass
class SearchResult:
    """A single search result from the federated index."""
    listing_id: str
    node_id: str
    brand: str
    model: str
    condition: str
    ask_price: float
    currency: str
    total_landed_cost: float
    seller_did: str
    seller_trust_score: float
    ai_confidence: float
    shipping_cost: float = 0.0
    insurance_cost: float = 0.0
    platform_fee: float = 0.0

    @property
    def savings_vs_median(self) -> float:
        """Estimated savings vs market median (placeholder)."""
        return 0.0


@dataclass
class SearchResponse:
    """Response from the search endpoint."""
    results: list[SearchResult]
    total_estimated: int
    next_cursor: Optional[str] = None
    query_understood_as: Optional[str] = None
    semantic_fallback_used: bool = False
    execution_time_ms: int = 0


@dataclass
class ProductSpec:
    """Category-specific product specifications."""
    category: str
    brand: str
    model: str
    model_year: Optional[int] = None
    specifications: dict[str, Any] = field(default_factory=dict)
    condition: str = "good"
    condition_details: list[dict[str, Any]] = field(default_factory=list)
    serial_number: Optional[str] = None
    serial_verified: bool = False


@dataclass
class EscrowContract:
    """An escrow contract for a transaction."""
    escrow_id: str
    listing_id: str
    status: str
    amounts: dict[str, dict[str, Any]]
    payment_url: str
    payment_expires_at: str
    inspection_period_hours: int = 48
    dispute_window_hours: int = 72


@dataclass
class Offer:
    """A negotiated offer between buyer and seller."""
    offer_id: str
    listing_id: str
    offer_price: float
    currency: str
    message: str
    status: str = "pending"
    expires_at: Optional[str] = None
    buyer_did: Optional[str] = None
    seller_did: Optional[str] = None


@dataclass
class TrustScore:
    """Trust score for a participant."""
    overall: float
    identity_verification: float
    transaction_completion: float
    dispute_resolution: float
    description_accuracy: float
    shipping_speed: float
    total_transactions: int
    dispute_rate: float
    return_rate: float
    verified_identity: bool
    category_expertise: dict[str, dict[str, float]] = field(default_factory=dict)


class Client:
    """OpenTrade Protocol client for AI agents.

    Connects to the PEP Index to search listings, negotiate prices,
    and manage escrow contracts across all federated nodes.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        did_jwt: Optional[str] = None,
        base_url: str = "https://api.opentradeprotocol.com/v1",
    ):
        self.api_key = api_key
        self.did_jwt = did_jwt
        self.base_url = base_url.rstrip("/")

    def _headers(self, auth: Optional[str] = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.did_jwt:
            headers["Authorization"] = f"Bearer {self.did_jwt}"
        return headers

    def _post(self, path: str, body: dict[str, Any], auth: Optional[str] = None) -> dict[str, Any]:
        import urllib.request
        url = urljoin(self.base_url, path)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(auth), method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def _get(self, path: str, params: Optional[dict[str, Any]] = None, auth: Optional[str] = None) -> dict[str, Any]:
        import urllib.request
        import urllib.parse
        url = urljoin(self.base_url, path)
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers=self._headers(auth))
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def search(
        self,
        query: str,
        filters: Optional[dict[str, Any]] = None,
        buyer_location: Optional[dict[str, float]] = None,
        sort: str = "relevance_score",
        limit: int = 20,
        cursor: Optional[str] = None,
        include_logistics: bool = True,
        currency: Optional[str] = None,
    ) -> SearchResponse:
        """Search across all federated OpenTrade nodes.

        Args:
            query: Natural language or keyword search query.
            filters: Structured filter parameters.
            buyer_location: Dict with 'lat' and 'lon' for cost calculation.
            sort: Sort order for results.
            limit: Max results to return (max 100).
            cursor: Pagination cursor from previous response.
            include_logistics: Include shipping costs in results.
            currency: ISO 4217 currency code.

        Returns:
            SearchResponse with results and metadata.
        """
        body: dict[str, Any] = {"query": query}
        if filters:
            # Convert Condition enums to strings
            if "condition" in filters and filters["condition"]:
                filters = dict(filters)
                filters["condition"] = [c.value if isinstance(c, Condition) else c for c in filters["condition"]]
            body["filters"] = filters
        if buyer_location:
            body["buyer_location"] = buyer_location
        body["sort"] = sort
        body["limit"] = min(limit, 100)
        if cursor:
            body["cursor"] = cursor
        body["include_logistics"] = include_logistics
        if currency:
            body["currency"] = currency

        data = self._post("/search", body)
        return self._parse_search_response(data)

    def semantic_search(
        self,
        vector: list[float],
        filters: Optional[dict[str, Any]] = None,
        buyer_location: Optional[dict[str, float]] = None,
        limit: int = 20,
    ) -> SearchResponse:
        """Search using a vector embedding from an LLM.

        Args:
            vector: Embedding vector from the agent's LLM.
            filters: Optional structured filters.
            buyer_location: Buyer location for cost calculation.
            limit: Max results.

        Returns:
            SearchResponse with semantic search results.
        """
        body = {"vector": vector}
        if filters:
            body["filters"] = filters
        if buyer_location:
            body["buyer_location"] = buyer_location
        body["limit"] = min(limit, 100)

        data = self._post("/search/semantic", body)
        return self._parse_search_response(data)

    def get_listing(self, listing_id: str, buyer_location: Optional[dict[str, float]] = None) -> dict[str, Any]:
        """Get a single listing by ID.

        Args:
            listing_id: The listing identifier.
            buyer_location: Optional buyer location for cost calculation.

        Returns:
            Full listing data in JSON-LD format.
        """
        params = {}
        if buyer_location:
            params["buyer_lat"] = buyer_location.get("lat")
            params["buyer_lon"] = buyer_location.get("lon")
        return self._get(f"/listings/{listing_id}", params)

    def get_total_cost(self, listing_id: str, buyer_lat: float, buyer_lon: float, insurance: bool = True) -> dict[str, Any]:
        """Calculate total landed cost for a listing.

        Args:
            listing_id: The listing identifier.
            buyer_lat: Buyer's latitude.
            buyer_lon: Buyer's longitude.
            insurance: Include insurance cost.

        Returns:
            Cost breakdown with cheapest and recommended options.
        """
        return self._get(
            f"/listings/{listing_id}/total-cost",
            {"buyer_lat": buyer_lat, "buyer_lon": buyer_lon, "insurance": insurance},
        )

    def create_offer(
        self,
        listing_id: str,
        offer_price: float,
        currency: str,
        message: str,
        expires_in: str = "PT2H",
        payment_method: str = "escrow",
    ) -> Offer:
        """Create an offer on a listing.

        Args:
            listing_id: Target listing.
            offer_price: Offered price.
            currency: ISO 4217 currency code.
            message: AI reasoning for the offer.
            expires_in: ISO 8601 duration (default 2 hours).
            payment_method: Payment method (escrow, direct, crypto).

        Returns:
            Created Offer object.
        """
        data = self._post(
            f"/listings/{listing_id}/offers",
            {
                "offerPrice": offer_price,
                "currency": currency,
                "message": message,
                "expiresIn": expires_in,
                "paymentMethod": payment_method,
            },
            auth=self.did_jwt,
        )
        return Offer(
            offer_id=data.get("offerId", ""),
            listing_id=listing_id,
            offer_price=offer_price,
            currency=currency,
            message=message,
            status=data.get("status", "pending"),
            expires_at=data.get("expiresAt"),
            buyer_did=data.get("buyerDid"),
            seller_did=data.get("sellerDid"),
        )

    def respond_to_offer(
        self,
        listing_id: str,
        offer_id: str,
        action: str,
        counter_price: Optional[float] = None,
        counter_currency: Optional[str] = None,
        counter_expires_in: Optional[str] = None,
        counter_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """Accept, reject, or counter an offer.

        Args:
            listing_id: Target listing.
            offer_id: Offer to respond to.
            action: 'accept', 'reject', or 'counter'.
            counter_price: Required if action='counter'.
            counter_currency: Currency for counter-offer.
            counter_expires_in: TTL for counter-offer.
            counter_message: Reasoning for counter-offer.

        Returns:
            Response data.
        """
        body: dict[str, Any] = {"action": action}
        if action == "counter":
            body["counterOfferPrice"] = counter_price
            body["counterCurrency"] = counter_currency
            body["counterExpiresIn"] = counter_expires_in
            body["counterMessage"] = counter_message

        return self._post(
            f"/listings/{listing_id}/offers/{offer_id}/respond",
            body,
            auth=self.did_jwt,
        )

    def create_escrow(
        self,
        listing_id: str,
        buyer_did: str,
        seller_did: str,
        shipping_method: str = "standard",
        insurance: bool = True,
        payment_method: str = "card",
    ) -> EscrowContract:
        """Create an escrow contract for a transaction.

        Args:
            listing_id: Target listing.
            buyer_did: Buyer's DID.
            seller_did: Seller's DID.
            shipping_method: Shipping method.
            insurance: Include insurance.
            payment_method: Payment method.

        Returns:
            EscrowContract with payment URL and details.
        """
        data = self._post(
            "/escrow/create",
            {
                "listingId": listing_id,
                "buyerDid": buyer_did,
                "sellerDid": seller_did,
                "shippingMethod": shipping_method,
                "insurance": insurance,
                "paymentMethod": payment_method,
            },
            auth=self.did_jwt,
        )
        return EscrowContract(
            escrow_id=data.get("escrowId", ""),
            listing_id=listing_id,
            status=data.get("status", "created"),
            amounts=data.get("amounts", {}),
            payment_url=data.get("paymentUrl", ""),
            payment_expires_at=data.get("paymentExpiresAt", ""),
            inspection_period_hours=data.get("inspectionPeriodHours", 48),
            dispute_window_hours=data.get("disputeWindowHours", 72),
        )

    def confirm_escrow(self, escrow_id: str, pin_code: str, photo_evidence: Optional[list[dict]] = None) -> dict[str, Any]:
        """Confirm receipt of an escrowed item.

        Args:
            escrow_id: The escrow contract ID.
            pin_code: PIN code from SMS.
            photo_evidence: Optional photo evidence.

        Returns:
            Confirmation result.
        """
        body: dict[str, Any] = {"pinCode": pin_code}
        if photo_evidence:
            body["photoEvidence"] = photo_evidence
        return self._post(f"/escrow/{escrow_id}/confirm", body, auth=self.did_jwt)

    def dispute_escrow(
        self,
        escrow_id: str,
        reason: str,
        description: str,
        photo_evidence: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """File a dispute for an escrowed transaction.

        Args:
            escrow_id: The escrow contract ID.
            reason: Dispute reason.
            description: Detailed description.
            photo_evidence: Photo evidence.

        Returns:
            Dispute result.
        """
        body: dict[str, Any] = {"reason": reason, "description": description}
        if photo_evidence:
            body["photoEvidence"] = photo_evidence
        return self._post(f"/escrow/{escrow_id}/dispute", body, auth=self.did_jwt)

    def get_trust_score(self, did: str) -> TrustScore:
        """Get the trust score for a DID.

        Args:
            did: Decentralized identifier.

        Returns:
            TrustScore with components.
        """
        data = self._get(f"/trust/{did}")
        cs = data.get("trustScore", {})
        components = cs.get("components", {})
        return TrustScore(
            overall=cs.get("overall", 0.0),
            identity_verification=components.get("identity_verification", 0.0),
            transaction_completion=components.get("transaction_completion", 0.0),
            dispute_resolution=components.get("dispute_resolution", 0.0),
            description_accuracy=components.get("description_accuracy", 0.0),
            shipping_speed=components.get("shipping_speed", 0.0),
            total_transactions=cs.get("totalTransactions", 0),
            dispute_rate=cs.get("disputeRate", 0.0),
            return_rate=cs.get("returnRate", 0.0),
            verified_identity=cs.get("verifiedIdentity", False),
            category_expertise=cs.get("categoryExpertise", {}),
        )

    def calculate_logistics(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        length_cm: float,
        width_cm: float,
        height_cm: float,
        weight_kg: float,
        declared_value: float,
        insurance: bool = True,
    ) -> dict[str, Any]:
        """Calculate shipping options.

        Args:
            origin_lat/lon: Origin location.
            destination_lat/lon: Destination location.
            length_cm: Package length in cm.
            width_cm: Package width in cm.
            height_cm: Package height in cm.
            weight_kg: Package weight in kg.
            declared_value: Item value for insurance.
            insurance: Include insurance cost.

        Returns:
            Shipping options with costs and delivery estimates.
        """
        return self._post(
            "/logistics/calculate",
            {
                "origin": {"lat": origin_lat, "lon": origin_lon},
                "destination": {"lat": destination_lat, "lon": destination_lon},
                "dimensions": {
                    "l": length_cm,
                    "w": width_cm,
                    "h": height_cm,
                    "weight": weight_kg,
                },
                "declaredValue": declared_value,
                "insurance": insurance,
            },
        )

    def get_category_schema(self, category_id: str) -> dict[str, Any]:
        """Get JSON Schema for a product category.

        Args:
            category_id: Category identifier (e.g., 'winter_sports/snowboard').

        Returns:
            JSON Schema for the category.
        """
        return self._get(f"/categories/{category_id}/schema")

    def bulk_listings(
        self,
        updated_since: Optional[str] = None,
        categories: Optional[list[str]] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Bulk fetch listings for indexing.

        Args:
            updated_since: ISO 8601 timestamp for incremental sync.
            categories: Filter by categories.
            cursor: Pagination cursor.
            limit: Max results (max 1000).

        Returns:
            Bulk listing data with next cursor.
        """
        params = {}
        if updated_since:
            params["updated_since"] = updated_since
        if categories:
            params["categories"] = ",".join(categories)
        if cursor:
            params["cursor"] = cursor
        params["limit"] = min(limit, 1000)
        return self._get("/listings/bulk", params)

    def _parse_search_response(self, data: dict[str, Any]) -> SearchResponse:
        """Parse raw API response into SearchResponse."""
        results = []
        for r in data.get("results", []):
            pricing = r.get("pricing", {})
            ask = pricing.get("askPrice", {})
            cost = r.get("total_landed_cost", {})
            results.append(SearchResult(
                listing_id=r.get("listing_id", ""),
                node_id=r.get("node_id", ""),
                brand=r.get("product", {}).get("brand", ""),
                model=r.get("product", {}).get("model", ""),
                condition=r.get("product", {}).get("condition", {}).get("overall_grade", "good"),
                ask_price=ask.get("amount", 0.0),
                currency=ask.get("currency", "RUB"),
                total_landed_cost=cost.get("total", 0.0),
                seller_did=r.get("seller", {}).get("did", ""),
                seller_trust_score=r.get("seller", {}).get("trust_score", 0.0),
                ai_confidence=r.get("ai_confidence", 0.0),
                shipping_cost=cost.get("shipping", 0.0),
                insurance_cost=cost.get("insurance", 0.0),
                platform_fee=cost.get("platform_fee", 0.0),
            ))
        return SearchResponse(
            results=results,
            total_estimated=data.get("total_estimated", 0),
            next_cursor=data.get("next_cursor"),
            query_understood_as=data.get("search_metadata", {}).get("query_understood_as"),
            semantic_fallback_used=data.get("search_metadata", {}).get("semantic_fallback_used", False),
            execution_time_ms=data.get("search_metadata", {}).get("execution_time_ms", 0),
        )
