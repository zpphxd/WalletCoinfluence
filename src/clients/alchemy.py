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
            # Use Alchemy's getAssetTransfers API
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": "latest",
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

            for transfer in response.get("result", {}).get("transfers", []):
                # Check if this is a DEX swap (filter out regular transfers)
                to_address = transfer.get("to", "").lower()
                if not is_dex_router(to_address, chain_id):
                    continue  # Skip non-DEX transfers

                amount = float(transfer.get("value", 0))
                value_usd = amount * current_price if current_price > 0 else 0
                dex_name = get_dex_name(to_address, chain_id)

                transfers.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "from_address": transfer.get("from"),
                    "type": "buy",
                    "token_address": token_address,
                    "amount": amount,
                    "price_usd": current_price,
                    "value_usd": value_usd,
                    "dex": dex_name,
                })

            logger.info(f"Fetched {len(transfers)} transfers for {token_address[:10]}... (price=${current_price:.6f})")
            return transfers

        except Exception as e:
            logger.error(f"Alchemy API error: {str(e)}")
            return []

    async def get_wallet_transactions(
        self, wallet_address: str, chain_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent wallet transactions.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier
            limit: Max number of transactions

        Returns:
            List of transaction data
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": "latest",
                    "fromAddress": wallet_address,
                    "category": ["erc20"],
                    "maxCount": f"0x{min(limit, 100):x}",
                    "order": "desc"
                }]
            }

            response = await self.post("", data=payload)
            transactions = []

            for transfer in response.get("result", {}).get("transfers", []):
                # Check if this is a DEX swap
                to_address = transfer.get("to", "").lower()
                if not is_dex_router(to_address, chain_id):
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

                dex_name = get_dex_name(to_address, chain_id)

                transactions.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "type": "buy",
                    "token_address": token_addr,
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": dex_name,
                })

            logger.info(f"Fetched {len(transactions)} txs for {wallet_address[:10]}...")
            return transactions

        except Exception as e:
            logger.error(f"Alchemy API error: {str(e)}")
            return []
