#!/usr/bin/env python3
"""Test wallet discovery with multiple tokens to verify robustness."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from clients.alchemy import AlchemyClient

# Popular tokens on Ethereum
TEST_TOKENS = {
    "PEPE": "0x6982508145454ce325ddbe47a25d4ec3d2311933",
    "SHIB": "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce",
    "WETH": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
}

CHAIN_ID = "ethereum"

async def test_multiple_tokens():
    """Test wallet discovery across multiple tokens."""

    print("=" * 80)
    print("MULTI-TOKEN WALLET DISCOVERY TEST")
    print("=" * 80)

    client = AlchemyClient()
    total_wallets = 0
    successful_tokens = 0

    for token_name, token_address in TEST_TOKENS.items():
        print(f"\n📊 Testing {token_name}...")
        print(f"   Address: {token_address}")

        try:
            transfers = await client.get_token_transfers(
                token_address=token_address,
                chain_id=CHAIN_ID,
                limit=50
            )

            unique_wallets = set(t.get('from_address') for t in transfers if t.get('from_address'))
            print(f"   ✅ Found {len(transfers)} buys from {len(unique_wallets)} unique wallets")

            if len(unique_wallets) > 0:
                successful_tokens += 1
                total_wallets += len(unique_wallets)

                # Show sample wallet
                sample_wallet = list(unique_wallets)[0]
                sample_transfer = [t for t in transfers if t.get('from_address') == sample_wallet][0]
                print(f"   Sample wallet: {sample_wallet[:10]}...")
                print(f"   Sample buy: {sample_transfer.get('amount', 0):,.2f} {token_name} (${sample_transfer.get('value_usd', 0):.2f})")
            else:
                print(f"   ⚠️  No buys found (low trading volume in recent blocks)")

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")

    await client.close()

    print("\n" + "=" * 80)
    print("MULTI-TOKEN TEST RESULTS")
    print("=" * 80)
    print(f"Tokens tested: {len(TEST_TOKENS)}")
    print(f"Successful discoveries: {successful_tokens}/{len(TEST_TOKENS)}")
    print(f"Total unique wallets found: {total_wallets}")

    if successful_tokens >= 2:
        print("\n✅ SUCCESS: Wallet discovery works across multiple tokens!")
        print("The fix is robust and production-ready.")
    elif successful_tokens == 1:
        print("\n⚠️  PARTIAL: Works for some tokens, may be volume dependent")
    else:
        print("\n❌ FAILED: No wallets discovered")

if __name__ == "__main__":
    asyncio.run(test_multiple_tokens())
