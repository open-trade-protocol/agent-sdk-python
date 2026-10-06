"""Example: Create a listing and escrow contract.

This example demonstrates:
1. Creating a new listing
2. Creating an escrow contract for it
3. Checking escrow status

Usage:
    python examples/create_escrow.py
"""

import asyncio
import sys
import uuid
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
            print("ERROR: PEP Node is not reachable.")
            return

        # 2. Create a listing
        print("\n=== Creating a listing ===")
        listing_data = {
            "title": "Burton Custom X 2024",
            "description": "Premium all-mountain snowboard. Excellent condition, used for one season.",
            "price": 45000.00,
            "currency": "RUB",
            "category": "snowboards",
            "condition": "used_like_new",
            "seller_node_id": "node-demo-agent-01",
        }

        try:
            listing = await client.create_listing(listing_data)
            print(f"Listing created: {listing.get('id', 'unknown')}")
            print(f"  Title: {listing.get('title')}")
            print(f"  Price: {listing.get('price')} {listing.get('currency')}")
            print(f"  Category: {listing.get('category')}")
            listing_id = listing.get("id", "")
        except OpenTradeError as e:
            print(f"Failed to create listing: {e}")
            return

        # 3. Create an escrow contract
        print("\n=== Creating escrow contract ===")
        try:
            escrow = await client.escrow_create(
                listing_id=listing_id,
                terms={
                    "buyer_node_id": "node-buyer-01",
                    "seller_node_id": "node-demo-agent-01",
                    "amount": listing_data["price"],
                    "currency": listing_data["currency"],
                    "release_conditions": "buyer_confirmed_delivery",
                    "dispute_window_hours": 72,
                },
            )
            print(f"Escrow created: {escrow.get('id', 'unknown')}")
            print(f"  Status: {escrow.get('status', 'unknown')}")
            print(f"  Amount: {escrow.get('amount', 0)} {escrow.get('currency', '')}")
            escrow_id = escrow.get("id", "")
        except OpenTradeError as e:
            print(f"Escrow API not available (expected — escrow endpoint not yet implemented): {e}")
            escrow_id = None

        # 4. Check escrow status (if created)
        if escrow_id:
            print("\n=== Checking escrow status ===")
            try:
                status = await client.escrow_status(escrow_id)
                print(f"Status: {status}")
            except OpenTradeError as e:
                print(f"Escrow status check failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except OpenTradeError as e:
        print(f"OpenTrade error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
