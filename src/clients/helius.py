"""Helius API client for Solana chain data."""

import logging
from typing import List, Dict, Any
from datetime import datetime
from src.clients.base import BaseAPIClient
from src.config import settings

logger = logging.getLogger(__name__)


class HeliusClient(BaseAPIClient):
    """Client for Helius Solana data."""

    def __init__(self) -> None:
        """Initialize Helius client."""
        self.api_key = settings.helius_api_key

        if not self.api_key:
            raise ValueError("HELIUS_API_KEY not set in .env file")

        super().__init__(base_url=f"https://api.helius.xyz/v0")
        logger.info("✅ Helius client initialized")

    async def get_token_transactions(
        self, token_address: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent token transactions."""
        try:
            response = await self.get(
                f"/addresses/{token_address}/transactions",
                params={"api-key": self.api_key, "limit": min(limit, 100)}
            )

            transactions = []
            for tx in response:
                transactions.append({
                    "tx_hash": tx.get("signature"),
                    "timestamp": datetime.fromtimestamp(tx.get("timestamp", 0)),
                    "from_address": tx.get("feePayer"),
                    "type": "buy",
                    "token_address": token_address,
                    "amount": 0,
                    "price_usd": 0,
                    "value_usd": 0,
                    "dex": "unknown",
                })

            logger.info(f"Fetched {len(transactions)} txs from Helius")
            return transactions

        except Exception as e:
            logger.error(f"Helius API error: {str(e)}")
            return []

    async def get_wallet_transactions(
        self, wallet_address: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent wallet transactions."""
        try:
            response = await self.get(
                f"/addresses/{wallet_address}/transactions",
                params={"api-key": self.api_key, "limit": min(limit, 100)}
            )

            transactions = []
            for tx in response:
                transactions.append({
                    "tx_hash": tx.get("signature"),
                    "timestamp": datetime.fromtimestamp(tx.get("timestamp", 0)),
                    "type": "buy",
                    "token_address": None,
                    "amount": 0,
                    "price_usd": 0,
                    "value_usd": 0,
                    "dex": "unknown",
                })

            logger.info(f"Fetched {len(transactions)} txs from Helius")
            return transactions

        except Exception as e:
            logger.error(f"Helius API error: {str(e)}")
            return []
