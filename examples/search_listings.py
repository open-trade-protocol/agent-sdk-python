"""Example: Search listings using the OpenTrade SDK.

This example demonstrates:
1. Creating a client
2. Searching for listings
3. Filtering by category and price
4. Displaying results

Usage:
    python examples/search_listings.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opentrade.client import OpenTradeClient, OpenTradeError


async def main():
    base_url = "http://localhost:8000"

    async with OpenTradeClient(base_url=base_url) as client:
        # 1. Health check
        health = await client.health_check()
        print(f"PEP Node health: {health}")
        if health.get("status") == "unreachable":
            print("ERROR: PEP Node is not reachable. Start it with: cd ../pep-node && python -m app.main")
            return

        # 2. Search for snowboards
        print("\n=== Searching for 'snowboard' ===")
        search_result = await client.search(
            query="snowboard",
            category="snowboards",
            limit=10,
        )
        print(f"Found {search_result.get('total_estimated', 0)} results")

        for i, listing in enumerate(search_result.get("results", [])[:5], 1):
            print(f"\n  {i}. {listing.get('title', 'N/A')}")
            print(f"     Price: {listing.get('price', 0)} {listing.get('currency', 'RUB')}")
            print(f"     Condition: {listing.get('condition', 'N/A')}")
            print(f"     Seller: {listing.get('seller_node_id', 'N/A')}")

        # 3. Filter by price range
        print("\n=== Filtering: price 10000 - 50000 ===")
        filtered = await client.search(
            query="",
            price_min=10000,
            price_max=50000,
            sort="price_asc",
        )
        print(f"Found {filtered.get('total_estimated', 0)} results in price range")

        for i, listing in enumerate(filtered.get("results", [])[:5], 1):
            print(f"  {i}. {listing.get('title', 'N/A')} — {listing.get('price', 0)} RUB")

        # 4. List all listings (no search query)
        print("\n=== All listings (first 5) ===")
        listings = await client.list_listings(category="all", limit=5)
        print(f"Total listings: {listings.get('total', 0)}")

        for i, item in enumerate(listings.get("items", [])[:5], 1):
            print(f"  {i}. {item.get('title', 'N/A')} — {item.get('price', 0)} {item.get('currency', 'RUB')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except OpenTradeError as e:
        print(f"OpenTrade error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
