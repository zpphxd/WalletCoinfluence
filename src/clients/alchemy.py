"""Alchemy API client for EVM chain data."""

import logging
from typing import List, Dict, Any
from datetime import datetime
from src.clients.base import BaseAPIClient
from src.clients.dexscreener import DexScreenerClient
from src.utils.dex_routers import is_dex_router, get_dex_name
from src.config import settings

logger = logging.getLogger(__name__)


class AlchemyClient(BaseAPIClient):
    """Client for Alchemy blockchain data."""

    def __init__(self) -> None:
        """Initialize Alchemy client."""
        self.api_key = settings.alchemy_api_key

        if not self.api_key:
            raise ValueError("ALCHEMY_API_KEY not set in .env file")

        super().__init__(base_url=f"https://eth-mainnet.g.alchemy.com/v2/{self.api_key}")
        self.dex_client = DexScreenerClient()
        logger.info("✅ Alchemy client initialized")

    async def get_token_transfers(
        self, token_address: str, chain_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent token transfers (buys).

        Args:
            token_address: Token contract address
            chain_id: Chain identifier
            limit: Max number of transfers

        Returns:
            List of transfer data
        """
        try:
            # First get current block number
            block_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_blockNumber",
                "params": []
            }
            block_response = await self.post("", data=block_payload)
            latest_block = int(block_response.get("result", "0x0"), 16)
            # Look back ~1000 blocks (about 3.3 hours on Ethereum)
            from_block = max(0, latest_block - 1000)

            # Use Alchemy's getAssetTransfers API with block range
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": hex(from_block),
                    "toBlock": "latest",
                    "contractAddresses": [token_address],
                    "category": ["erc20"],
                    "maxCount": f"0x{min(limit, 1000):x}",
                    "order": "desc"
                }]
            }

            response = await self.post("", data=payload)
            transfers = []

            # Get token price from DexScreener
            token_info = await self.dex_client.get_token_info(token_address)
            current_price = token_info.get("price_usd", 0)

            # Identify potential DEX pools (addresses that send tokens multiple times)
            from_address_counts = {}
            all_transfers = response.get("result", {}).get("transfers", [])
            for transfer in all_transfers:
                from_addr = transfer.get("from", "").lower()
                from_address_counts[from_addr] = from_address_counts.get(from_addr, 0) + 1

            # Addresses sending multiple times are likely DEX pools
            potential_pools = {addr for addr, count in from_address_counts.items() if count > 2}

            logger.info(f"Identified {len(potential_pools)} potential DEX pools for {token_address[:10]}...")

            for transfer in all_transfers:
                # CORRECT LOGIC: Check if transfer is FROM a DEX pool (not TO a router)
                # When users buy tokens, the pool sends tokens to the buyer
                from_address = transfer.get("from", "").lower()

                # Check if from a known DEX pool (heuristic: sends tokens multiple times)
                if from_address not in potential_pools:
                    continue  # Skip transfers not from DEX pools

                # The "to" address is the buyer's wallet
                buyer_address = transfer.get("to", "")

                amount = float(transfer.get("value", 0))
                value_usd = amount * current_price if current_price > 0 else 0

                transfers.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "from_address": buyer_address,  # The buyer, not the pool
                    "type": "buy",
                    "token_address": token_address,
                    "amount": amount,
                    "price_usd": current_price,
                    "value_usd": value_usd,
                    "dex": "dex_pool",  # Generic since we're using heuristic
                })

            logger.info(f"Fetched {len(transfers)} DEX buys for {token_address[:10]}... (price=${current_price:.6f})")
            return transfers

        except Exception as e:
            logger.error(f"Alchemy API error: {str(e)}")
            return []

    async def get_wallet_transactions(
        self, wallet_address: str, chain_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent wallet transactions (both buys and sells).

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier
            limit: Max number of transactions

        Returns:
            List of transaction data with both buys and sells
        """
        try:
            # First get current block number
            block_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_blockNumber",
                "params": []
            }
            block_response = await self.post("", data=block_payload)
            latest_block = int(block_response.get("result", "0x0"), 16)
            # Look back ~5000 blocks (about 16 hours on Ethereum) for wallet history
            from_block = max(0, latest_block - 5000)

            transactions = []

            # Query 1: Get transfers TO the wallet (receives tokens = buys)
            buy_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": hex(from_block),
                    "toBlock": "latest",
                    "toAddress": wallet_address,  # Get tokens received by wallet
                    "category": ["erc20"],
                    "maxCount": f"0x{min(limit, 100):x}",
                    "order": "desc"
                }]
            }

            buy_response = await self.post("", data=buy_payload)
            buy_transfers = buy_response.get("result", {}).get("transfers", [])

            # Identify potential DEX pools sending tokens (for buys)
            from_address_counts = {}
            for transfer in buy_transfers:
                from_addr = transfer.get("from", "").lower()
                from_address_counts[from_addr] = from_address_counts.get(from_addr, 0) + 1

            # Addresses sending multiple times are likely DEX pools
            buy_pools = {addr for addr, count in from_address_counts.items() if count > 1}

            for transfer in buy_transfers:
                # Check if transfer is FROM a DEX pool (indicating a buy)
                from_address = transfer.get("from", "").lower()
                if from_address not in buy_pools:
                    continue  # Skip non-DEX transfers

                token_addr = transfer.get("rawContract", {}).get("address")
                amount = float(transfer.get("value", 0))

                # Get token price from DexScreener
                price_usd = 0
                value_usd = 0
                if token_addr:
                    token_info = await self.dex_client.get_token_info(token_addr)
                    price_usd = token_info.get("price_usd", 0)
                    value_usd = amount * price_usd if price_usd > 0 else 0

                transactions.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "type": "buy",
                    "token_address": token_addr,
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": "dex_pool",
                })

            # Query 2: Get transfers FROM the wallet (sends tokens = sells)
            sell_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": hex(from_block),
                    "toBlock": "latest",
                    "fromAddress": wallet_address,  # Get tokens sent by wallet
                    "category": ["erc20"],
                    "maxCount": f"0x{min(limit, 100):x}",
                    "order": "desc"
                }]
            }

            sell_response = await self.post("", data=sell_payload)
            sell_transfers = sell_response.get("result", {}).get("transfers", [])

            # Identify potential DEX pools receiving tokens (for sells)
            to_address_counts = {}
            for transfer in sell_transfers:
                to_addr = transfer.get("to", "").lower()
                to_address_counts[to_addr] = to_address_counts.get(to_addr, 0) + 1

            # Addresses receiving multiple times are likely DEX pools
            sell_pools = {addr for addr, count in to_address_counts.items() if count > 1}

            for transfer in sell_transfers:
                # Check if transfer is TO a DEX pool (indicating a sell)
                to_address = transfer.get("to", "").lower()
                if to_address not in sell_pools:
                    continue  # Skip non-DEX transfers

                token_addr = transfer.get("rawContract", {}).get("address")
                amount = float(transfer.get("value", 0))

                # Get token price from DexScreener
                price_usd = 0
                value_usd = 0
                if token_addr:
                    token_info = await self.dex_client.get_token_info(token_addr)
                    price_usd = token_info.get("price_usd", 0)
                    value_usd = amount * price_usd if price_usd > 0 else 0

                transactions.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "type": "sell",
                    "token_address": token_addr,
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": "dex_pool",
                })

            logger.info(
                f"Fetched {len([t for t in transactions if t['type'] == 'buy'])} buys, "
                f"{len([t for t in transactions if t['type'] == 'sell'])} sells "
                f"for {wallet_address[:10]}..."
            )
            return transactions

        except Exception as e:
            logger.error(f"Alchemy API error: {str(e)}")
            return []
