"""Alchemy API client for EVM chain data."""

import logging
from typing import List, Dict, Any
from datetime import datetime
from src.clients.base import BaseAPIClient
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

            for transfer in response.get("result", {}).get("transfers", []):
                transfers.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "from_address": transfer.get("from"),
                    "type": "buy",
                    "token_address": token_address,
                    "amount": float(transfer.get("value", 0)),
                    "price_usd": 0,
                    "value_usd": 0,
                    "dex": "unknown",
                })

            logger.info(f"Fetched {len(transfers)} transfers for {token_address[:10]}...")
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
                transactions.append({
                    "tx_hash": transfer.get("hash"),
                    "timestamp": datetime.now(),
                    "type": "buy",
                    "token_address": transfer.get("rawContract", {}).get("address"),
                    "amount": float(transfer.get("value", 0)),
                    "price_usd": 0,
                    "value_usd": 0,
                    "dex": "unknown",
                })

            logger.info(f"Fetched {len(transactions)} txs for {wallet_address[:10]}...")
            return transactions

        except Exception as e:
            logger.error(f"Alchemy API error: {str(e)}")
            return []
