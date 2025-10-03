#!/usr/bin/env python3
"""Direct Alchemy API test script to debug wallet discovery."""

import asyncio
import aiohttp
import json
from datetime import datetime

ALCHEMY_API_KEY = "zwJXJe7g8Aex01u_4Mxkv"
PEPE_TOKEN = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
BASE_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

# Known DEX routers for testing
UNISWAP_V2_ROUTER = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"
UNISWAP_V3_ROUTER = "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45"

async def test_alchemy_api():
    """Test Alchemy API with different configurations."""

    async with aiohttp.ClientSession() as session:
        print("=" * 80)
        print("TESTING ALCHEMY API WITH PEPE TOKEN")
        print("=" * 80)

        # TEST 1: Current implementation (fromBlock: "latest")
        print("\n🔬 TEST 1: Current implementation (fromBlock: 'latest')")
        print("-" * 80)
        payload1 = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "latest",
                "contractAddresses": [PEPE_TOKEN],
                "category": ["erc20"],
                "maxCount": "0x64",  # 100 in hex
                "order": "desc"
            }]
        }

        async with session.post(BASE_URL, json=payload1) as resp:
            data1 = await resp.json()
            result1 = data1.get("result", {})
            transfers1 = result1.get("transfers", [])
            print(f"Response status: {resp.status}")
            print(f"Transfers found: {len(transfers1)}")
            print(f"Full response: {json.dumps(data1, indent=2)[:500]}...")

        # TEST 2: Block range (last 1000 blocks - ~3.3 hours)
        print("\n🔬 TEST 2: Block range (latest - 1000 blocks)")
        print("-" * 80)

        # First get current block
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
            print(f"Latest block: {latest_block}")
            print(f"From block: {from_block} (hex: {hex(from_block)})")

        payload2 = {
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

        async with session.post(BASE_URL, json=payload2) as resp:
            data2 = await resp.json()
            result2 = data2.get("result", {})
            transfers2 = result2.get("transfers", [])
            print(f"Response status: {resp.status}")
            print(f"Transfers found: {len(transfers2)}")

            if transfers2:
                print(f"\n✅ SUCCESS! Found {len(transfers2)} transfers")
                print("\nFirst 3 transfers (RAW DATA):")
                for i, transfer in enumerate(transfers2[:3]):
                    print(f"\n--- Transfer {i+1} ---")
                    print(f"Hash: {transfer.get('hash')}")
                    print(f"From: {transfer.get('from')}")
                    print(f"To: {transfer.get('to')}")
                    print(f"Value: {transfer.get('value')}")
                    print(f"Asset: {transfer.get('asset')}")
                    print(f"Block: {transfer.get('blockNum')}")

                # TEST 3: Check if any go to DEX routers
                print("\n🔬 TEST 3: Analyzing DEX router destinations")
                print("-" * 80)
                dex_transfers = []
                for transfer in transfers2:
                    to_addr = transfer.get('to', '').lower()
                    if to_addr in [UNISWAP_V2_ROUTER.lower(), UNISWAP_V3_ROUTER.lower()]:
                        dex_transfers.append(transfer)

                print(f"Transfers TO DEX routers: {len(dex_transfers)}")
                if dex_transfers:
                    print("\nDEX transfers found:")
                    for dt in dex_transfers[:3]:
                        print(f"  - {dt.get('hash')} -> {dt.get('to')}")
                else:
                    print("❌ NO transfers to DEX routers found!")
                    print("\nSample 'to' addresses:")
                    for transfer in transfers2[:5]:
                        print(f"  - {transfer.get('to')}")
            else:
                print(f"❌ Still no transfers found!")
                print(f"Response: {json.dumps(data2, indent=2)}")

        # TEST 4: Try without contract filter (get ALL transfers)
        print("\n🔬 TEST 4: Get recent transfers WITHOUT token filter")
        print("-" * 80)
        payload3 = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": hex(from_block),
                "toBlock": "latest",
                "category": ["erc20"],
                "maxCount": "0xa",  # Just 10 transfers
                "order": "desc"
            }]
        }

        async with session.post(BASE_URL, json=payload3) as resp:
            data3 = await resp.json()
            result3 = data3.get("result", {})
            transfers3 = result3.get("transfers", [])
            print(f"Response status: {resp.status}")
            print(f"Total ERC20 transfers (any token): {len(transfers3)}")

            if transfers3:
                print("\nSample transfers:")
                for t in transfers3[:3]:
                    print(f"  - Token: {t.get('rawContract', {}).get('address')}")
                    print(f"    From: {t.get('from')}")
                    print(f"    To: {t.get('to')}")
                    print(f"    Value: {t.get('value')}")

if __name__ == "__main__":
    asyncio.run(test_alchemy_api())
