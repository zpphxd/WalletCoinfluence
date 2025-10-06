#!/usr/bin/env python3
"""Test Solana whale tracking with fixed Helius API."""

import asyncio
from src.clients.helius import HeliusClient


async def test():
    print("🧪 Testing fixed Helius API for Solana whale tracking...\n")
    client = HeliusClient()

    # Test with a known Solana whale
    whale = "AVAZvHLR2PcWpDf8BXY4rVxNHYRBytycHkcB5z5QNXYm"

    print(f"Fetching transactions for whale: {whale[:16]}...")
    txs = await client.get_wallet_transactions(whale, limit=10)

    print(f"\n✅ Fetched {len(txs)} transactions\n")

    if txs:
        print("📊 Sample transactions:")
        for i, tx in enumerate(txs[:3], 1):
            print(f"\n{i}. TX: {tx.get('tx_hash', '')[:16]}...")
            print(f"   Token: {tx.get('token_address', '')[:16]}...")
            print(f"   Amount: {tx.get('amount', 0):.2f}")
            print(f"   Value: ${tx.get('value_usd', 0):.2f}")
            print(f"   DEX: {tx.get('dex', 'unknown')}")
    else:
        print("⚠️  No transactions found (wallet may be inactive or API issue)")


if __name__ == "__main__":
    asyncio.run(test())
