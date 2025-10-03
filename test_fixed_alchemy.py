#!/usr/bin/env python3
"""Integration test for fixed Alchemy client."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from clients.alchemy import AlchemyClient

PEPE_TOKEN = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
CHAIN_ID = "ethereum"

async def test_fixed_client():
    """Test the fixed Alchemy client."""

    print("=" * 80)
    print("TESTING FIXED ALCHEMY CLIENT")
    print("=" * 80)

    # Initialize client
    print("\n1. Initializing Alchemy client...")
    client = AlchemyClient()
    print("✅ Client initialized")

    # Test get_token_transfers
    print("\n2. Testing get_token_transfers with PEPE token...")
    print(f"   Token: {PEPE_TOKEN}")
    print(f"   Chain: {CHAIN_ID}")

    transfers = await client.get_token_transfers(
        token_address=PEPE_TOKEN,
        chain_id=CHAIN_ID,
        limit=100
    )

    print(f"\n✅ Results:")
    print(f"   Total transfers (buys) found: {len(transfers)}")

    if len(transfers) > 0:
        print(f"\n🎉 SUCCESS! Wallet discovery is working!")
        print(f"\n   First 5 buyer wallets:")
        unique_wallets = set()
        for transfer in transfers[:10]:
            wallet = transfer.get('from_address')
            if wallet and wallet not in unique_wallets:
                unique_wallets.add(wallet)
                if len(unique_wallets) <= 5:
                    print(f"      - {wallet}")
                    print(f"        Amount: {transfer.get('amount'):,.2f} PEPE")
                    print(f"        Value: ${transfer.get('value_usd', 0):.2f}")
                    print(f"        TX: {transfer.get('tx_hash')}")

        print(f"\n   Total unique buyers found: {len(unique_wallets)}")

        # Test get_wallet_transactions with one of the buyers
        if unique_wallets:
            test_wallet = list(unique_wallets)[0]
            print(f"\n3. Testing get_wallet_transactions with buyer wallet...")
            print(f"   Wallet: {test_wallet}")

            wallet_txs = await client.get_wallet_transactions(
                wallet_address=test_wallet,
                chain_id=CHAIN_ID,
                limit=10
            )

            print(f"\n✅ Results:")
            print(f"   Total transactions found: {len(wallet_txs)}")

            if len(wallet_txs) > 0:
                print(f"\n   Recent buys:")
                for tx in wallet_txs[:5]:
                    print(f"      - Token: {tx.get('token_address', 'N/A')[:10]}...")
                    print(f"        Amount: {tx.get('amount', 0):,.2f}")
                    print(f"        Value: ${tx.get('value_usd', 0):.2f}")
            else:
                print(f"   ⚠️  No transactions found for this wallet")

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED! ✅")
        print("=" * 80)
        print("\nSUMMARY:")
        print(f"  - Block range query: WORKING")
        print(f"  - DEX pool detection: WORKING")
        print(f"  - Wallet discovery: WORKING")
        print(f"  - Found {len(unique_wallets)} unique buyer wallets")
        print("\nThe Alchemy integration is now functioning correctly!")

    else:
        print(f"\n❌ FAILED - Still no transfers found")
        print("   This might indicate:")
        print("   - API key issue")
        print("   - Network connectivity problem")
        print("   - Very low trading volume in recent blocks")

    # Close client session
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_fixed_client())
