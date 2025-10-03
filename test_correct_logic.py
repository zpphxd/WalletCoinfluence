#!/usr/bin/env python3
"""Test the CORRECT logic for finding DEX swaps."""

import asyncio
import aiohttp
import json

ALCHEMY_API_KEY = "zwJXJe7g8Aex01u_4Mxkv"
PEPE_TOKEN = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
BASE_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

# Known Uniswap V2 pools that hold PEPE
KNOWN_PEPE_POOLS = [
    "0xa43fe16908251ee70ef74718545e4fe6c5ccec9f",  # From our analysis
]

async def main():
    """Test correct DEX swap identification logic."""

    async with aiohttp.ClientSession() as session:
        print("=" * 80)
        print("CORRECT DEX SWAP IDENTIFICATION LOGIC")
        print("=" * 80)

        # Get current block
        block_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_blockNumber",
            "params": []
        }
        async with session.post(BASE_URL, json=block_payload) as resp:
            block_data = await resp.json()
            latest_block = int(block_data["result"], 16)
            from_block = latest_block - 1000

        print(f"\n📊 Block range: {from_block} to {latest_block}")

        # Get PEPE transfers
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": hex(from_block),
                "toBlock": "latest",
                "contractAddresses": [PEPE_TOKEN],
                "category": ["erc20"],
                "maxCount": "0x64",
                "order": "desc"
            }]
        }

        async with session.post(BASE_URL, json=payload) as resp:
            data = await resp.json()
            transfers = data.get("result", {}).get("transfers", [])

            print(f"Total PEPE transfers: {len(transfers)}")

            print("\n" + "=" * 80)
            print("THE CORRECT LOGIC:")
            print("=" * 80)
            print("When someone BUYS a token on a DEX:")
            print("  1. User sends ETH/WETH to the DEX router")
            print("  2. Router interacts with the liquidity pool")
            print("  3. Pool sends tokens FROM pool TO buyer")
            print("  4. So we look for transfers FROM known DEX pools!")
            print("\nNOT transfers TO DEX routers (that's backwards!)")

            # Count transfers FROM known pools vs TO buyers
            from_pool_count = 0
            buyer_wallets = set()

            print("\n" + "=" * 80)
            print("ANALYZING TRANSFER DIRECTIONS")
            print("=" * 80)

            for transfer in transfers:
                from_addr = transfer.get('from', '').lower()
                to_addr = transfer.get('to', '').lower()

                # Check if this transfer is FROM a DEX pool (indicating a buy)
                if from_addr in [p.lower() for p in KNOWN_PEPE_POOLS]:
                    from_pool_count += 1
                    buyer_wallets.add(to_addr)

                    if from_pool_count <= 5:
                        print(f"\n✅ BUY detected!")
                        print(f"   Pool: {from_addr[:10]}...")
                        print(f"   Buyer: {to_addr}")
                        print(f"   Amount: {transfer.get('value')} PEPE")
                        print(f"   TX: {transfer.get('hash')}")

            print("\n" + "=" * 80)
            print("RESULTS WITH CORRECT LOGIC:")
            print("=" * 80)
            print(f"Total buys detected: {from_pool_count}")
            print(f"Unique buyer wallets: {len(buyer_wallets)}")

            if from_pool_count > 0:
                print(f"\n✅ SUCCESS! Found {from_pool_count} real buyers!")
                print(f"\nSample buyer wallets:")
                for wallet in list(buyer_wallets)[:5]:
                    print(f"  - {wallet}")
            else:
                print("\n❌ Still no buys found. Need to identify more pools.")

            # Now let's try to identify ALL pool addresses automatically
            print("\n" + "=" * 80)
            print("IDENTIFYING ALL DEX POOLS AUTOMATICALLY")
            print("=" * 80)

            # Addresses that send PEPE multiple times are likely pools
            from_address_counts = {}
            for transfer in transfers:
                from_addr = transfer.get('from', '').lower()
                from_address_counts[from_addr] = from_address_counts.get(from_addr, 0) + 1

            print("\nAddresses that sent PEPE multiple times (likely pools):")
            potential_pools = []
            for addr, count in sorted(from_address_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                if count > 2:  # Likely a pool if it sends multiple times
                    potential_pools.append(addr)
                    print(f"  {addr}: {count} transfers")

            # Now recount with ALL potential pools
            total_buys = 0
            all_buyers = set()
            for transfer in transfers:
                from_addr = transfer.get('from', '').lower()
                to_addr = transfer.get('to', '').lower()

                if from_addr in potential_pools:
                    total_buys += 1
                    all_buyers.add(to_addr)

            print("\n" + "=" * 80)
            print("FINAL RESULTS WITH ALL POOLS:")
            print("=" * 80)
            print(f"Total potential pools identified: {len(potential_pools)}")
            print(f"Total buys detected: {total_buys}")
            print(f"Unique buyer wallets: {len(all_buyers)}")

            if len(all_buyers) > 0:
                print(f"\n🎉 SUCCESS! Found {len(all_buyers)} unique wallet addresses!")
                print(f"\nFirst 10 buyer wallets:")
                for wallet in list(all_buyers)[:10]:
                    print(f"  - {wallet}")
            else:
                print("\n❌ FAILED - Still no buyers found")

if __name__ == "__main__":
    asyncio.run(main())
