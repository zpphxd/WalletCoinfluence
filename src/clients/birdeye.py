"""Birdeye API client for Solana trending tokens."""

import logging
from typing import List, Dict, Any, Optional
from src.clients.base import BaseAPIClient
from src.config import settings

logger = logging.getLogger(__name__)


class BirdeyeClient(BaseAPIClient):
    """Client for Birdeye Solana data."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize Birdeye client.

        Args:
            api_key: Birdeye API key (defaults to settings)
        """
        super().__init__(
            base_url="https://public-api.birdeye.so",
            api_key=api_key or settings.birdeye_api_key,
        )

    def _get_headers(self) -> Dict[str, str]:
        """Override to use X-API-KEY header."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        return headers

    async def get_trending_tokens(self) -> List[Dict[str, Any]]:
        """Fetch trending tokens on Solana.

        Returns:
            List of trending token data
        """
        try:
            response = await self.get("defi/trending_tokens", params={"sort_by": "rank", "sort_type": "asc"})

            tokens_data = response.get("data", {}).get("tokens", [])

            tokens = []
            for token in tokens_data:
                tokens.append({
                    "token_address": token.get("address"),
                    "chain_id": "solana",
                    "symbol": token.get("symbol"),
                    "price_usd": float(token.get("price", 0)),
                    "liquidity_usd": float(token.get("liquidity", 0)),
                    "volume_24h_usd": float(token.get("v24hUSD", 0)),
                    "price_change_24h": float(token.get("v24hChangePercent", 0)),
                    "rank": token.get("rank"),
                })

            logger.info(f"Fetched {len(tokens)} trending tokens from Birdeye")
            return tokens[:50]

        except Exception as e:
            logger.error(f"Error fetching Birdeye trending: {str(e)}")
            return []

    async def get_token_overview(self, token_address: str) -> Dict[str, Any]:
        """Get token overview data.

        Args:
            token_address: Token address

        Returns:
            Token overview
        """
        try:
            response = await self.get(f"defi/token_overview", params={"address": token_address})

            data = response.get("data", {})

            return {
                "token_address": token_address,
                "chain_id": "solana",
                "symbol": data.get("symbol"),
                "price_usd": float(data.get("price", 0)),
                "liquidity_usd": float(data.get("liquidity", 0)),
                "volume_24h_usd": float(data.get("v24hUSD", 0)),
                "price_change_24h": float(data.get("v24hChangePercent", 0)),
                "holder_count": data.get("holder"),
            }

        except Exception as e:
            logger.error(f"Error fetching token overview for {token_address}: {str(e)}")
            return {}

    async def get_token_security(self, token_address: str) -> Dict[str, Any]:
        """Get token security info (ownership, mint authority, etc).

        Args:
            token_address: Token address

        Returns:
            Security info
        """
        try:
            response = await self.get(f"defi/token_security", params={"address": token_address})

            data = response.get("data", {})

            return {
                "token_address": token_address,
                "is_mutable": data.get("isMutable"),
                "freeze_authority": data.get("freezeAuthority"),
                "mint_authority": data.get("mintAuthority"),
                "top_holders_concentration": data.get("top10HolderPercent"),
            }

        except Exception as e:
            logger.error(f"Error fetching token security for {token_address}: {str(e)}")
            return {}
