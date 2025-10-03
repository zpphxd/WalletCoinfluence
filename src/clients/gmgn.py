"""GMGN.ai API client for Solana trending tokens (FREE)."""

import logging
from typing import List, Dict, Any
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class GMGNClient(BaseAPIClient):
    """Client for GMGN.ai - Solana token analytics (free API)."""

    def __init__(self):
        """Initialize GMGN client."""
        super().__init__(base_url="https://gmgn.ai/api/v1")

    async def get_trending_tokens(
        self,
        order_by: str = "volume_24h",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get trending tokens on Solana.

        Args:
            order_by: Sort field (volume_24h, price_change_percent, created_at)
            limit: Max number of tokens

        Returns:
            List of trending token data
        """
        try:
            response = await self.get(
                "tokens/sol/trending",
                params={
                    "orderby": order_by,
                    "direction": "desc",
                    "limit": limit,
                }
            )

            tokens_data = response.get("data", {}).get("tokens", [])

            tokens = []
            for token in tokens_data:
                tokens.append({
                    "token_address": token.get("address"),
                    "chain_id": "solana",
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "price_usd": float(token.get("price", 0)),
                    "market_cap_usd": float(token.get("market_cap", 0)),
                    "liquidity_usd": float(token.get("liquidity", 0)),
                    "volume_24h_usd": float(token.get("volume_24h", 0)),
                    "price_change_24h": float(token.get("price_change_24h_percent", 0)),
                    "holder_count": token.get("holder_count", 0),
                    "created_timestamp": token.get("created_timestamp"),
                    "source": "gmgn",
                })

            logger.info(f"Fetched {len(tokens)} trending tokens from GMGN")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching GMGN trending: {str(e)}")
            return []

    async def get_new_tokens(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get newly created tokens on Solana.

        Args:
            limit: Max number of tokens

        Returns:
            List of new token data
        """
        try:
            response = await self.get(
                "tokens/sol/new",
                params={"limit": limit}
            )

            tokens_data = response.get("data", {}).get("tokens", [])

            tokens = []
            for token in tokens_data:
                tokens.append({
                    "token_address": token.get("address"),
                    "chain_id": "solana",
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "price_usd": float(token.get("price", 0)),
                    "liquidity_usd": float(token.get("liquidity", 0)),
                    "created_timestamp": token.get("created_timestamp"),
                    "initial_liquidity": float(token.get("initial_liquidity", 0)),
                    "source": "gmgn",
                })

            logger.info(f"Fetched {len(tokens)} new tokens from GMGN")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching GMGN new tokens: {str(e)}")
            return []

    async def get_token_holders(self, token_address: str) -> List[Dict[str, Any]]:
        """Get top holders for a token.

        Args:
            token_address: Token mint address

        Returns:
            List of holder data
        """
        try:
            response = await self.get(
                f"tokens/sol/{token_address}/holders",
                params={"limit": 100}
            )

            holders = response.get("data", {}).get("holders", [])

            return [{
                "wallet": holder.get("address"),
                "balance": float(holder.get("balance", 0)),
                "percentage": float(holder.get("percentage", 0)),
                "is_smart_money": holder.get("is_smart_money", False),
            } for holder in holders]

        except Exception as e:
            logger.error(f"Error fetching GMGN holders for {token_address}: {str(e)}")
            return []
