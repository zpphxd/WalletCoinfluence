#!/usr/bin/env python3
"""Analyze DEX swap patterns to understand the correct filtering logic."""

import asyncio
import aiohttp
import json

ALCHEMY_API_KEY = "zwJXJe7g8Aex01u_4Mxkv"
PEPE_TOKEN = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
BASE_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

# DEX routers
KNOWN_DEX_ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3 Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router 1",
    "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b": "Uniswap Universal",
}

async def analyze_swap_tx(session, tx_hash):
    """Get transaction details to understand swap pattern."""
    print(f"\n🔍 Analyzing transaction: {tx_hash}")

    # Get transaction receipt
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash]
    }

    async with session.post(BASE_URL, json=payload) as resp:
        data = await resp.json()
        receipt = data.get("result", {})

        print(f"From: {receipt.get('from')}")
        print(f"To: {receipt.get('to')}")
        print(f"Status: {receipt.get('status')}")

        # Get all internal transfers
        transfer_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": receipt.get('blockNumber'),
                "toBlock": receipt.get('blockNumber'),
                "category": ["erc20", "external"],
            }]
        }

        async with session.post(BASE_URL, json=transfer_payload) as resp2:
            transfer_data = await resp2.json()
            transfers = transfer_data.get("result", {}).get("transfers", [])

            # Filter transfers for this tx
            tx_transfers = [t for t in transfers if t.get('hash') == tx_hash]

            print(f"\nAll transfers in this transaction ({len(tx_transfers)}):")
            for i, t in enumerate(tx_transfers):
                asset = t.get('asset', t.get('rawContract', {}).get('address', 'UNKNOWN'))
                print(f"{i+1}. {t.get('from')[:10]}... -> {t.get('to')[:10]}... | {t.get('value')} {asset}")

async def main():
    """Main analysis function."""

    async with aiohttp.ClientSession() as session:
        print("=" * 80)
        print("UNDERSTANDING DEX SWAP FLOW")
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
            from_block = latest_block - 2000  # ~6.5 hours

        # Get PEPE transfers
        print(f"\n📊 Fetching PEPE transfers from block {from_block} to {latest_block}")
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

            # Group by transaction hash
            tx_groups = {}
            for transfer in transfers:
                tx_hash = transfer.get('hash')
                if tx_hash not in tx_groups:
                    tx_groups[tx_hash] = []
                tx_groups[tx_hash].append(transfer)

            print(f"Unique transactions: {len(tx_groups)}")

            # Analyze patterns
            print("\n" + "=" * 80)
            print("PATTERN ANALYSIS: How to identify a DEX swap/buy")
            print("=" * 80)

            # Check if FROM address is a DEX router or pool
            from_dex = 0
            to_dex = 0
            from_addresses = {}
            to_addresses = {}

            for transfer in transfers:
                from_addr = transfer.get('from', '').lower()
                to_addr = transfer.get('to', '').lower()

                from_addresses[from_addr] = from_addresses.get(from_addr, 0) + 1
                to_addresses[to_addr] = to_addresses.get(to_addr, 0) + 1

                if from_addr in [r.lower() for r in KNOWN_DEX_ROUTERS.keys()]:
                    from_dex += 1
                if to_addr in [r.lower() for r in KNOWN_DEX_ROUTERS.keys()]:
                    to_dex += 1

            print(f"\nTransfers FROM DEX routers: {from_dex}")
            print(f"Transfers TO DEX routers: {to_dex}")

            print(f"\nTop 5 FROM addresses:")
            for addr, count in sorted(from_addresses.items(), key=lambda x: x[1], reverse=True)[:5]:
                dex_name = KNOWN_DEX_ROUTERS.get(addr, "")
                print(f"  {addr}: {count} transfers {dex_name}")

            print(f"\nTop 5 TO addresses:")
            for addr, count in sorted(to_addresses.items(), key=lambda x: x[1], reverse=True)[:5]:
                dex_name = KNOWN_DEX_ROUTERS.get(addr, "")
                print(f"  {addr}: {count} transfers {dex_name}")

            # Analyze a few sample transactions
            print("\n" + "=" * 80)
            print("SAMPLE TRANSACTION ANALYSIS")
            print("=" * 80)

            sample_txs = list(tx_groups.keys())[:2]
            for tx_hash in sample_txs:
                await analyze_swap_tx(session, tx_hash)

if __name__ == "__main__":
    asyncio.run(main())
