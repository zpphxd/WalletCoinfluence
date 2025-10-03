"""Jupiter API client for Solana token data (FREE)."""

import logging
from typing import List, Dict, Any, Optional
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class JupiterClient(BaseAPIClient):
    """Client for Jupiter - Solana DEX aggregator (free API)."""

    def __init__(self):
        """Initialize Jupiter client."""
        super().__init__(base_url="https://api.jup.ag")

    async def get_token_price(self, mint_address: str) -> Optional[float]:
        """Get current price for a token.

        Args:
            mint_address: Token mint address

        Returns:
            Price in USD or None
        """
        try:
            response = await self.get(
                "price/v2",
                params={"ids": mint_address}
            )

            data = response.get("data", {}).get(mint_address, {})
            price = data.get("price")

            return float(price) if price else None

        except Exception as e:
            logger.error(f"Error fetching Jupiter price for {mint_address}: {str(e)}")
            return None

    async def get_token_list(self) -> List[Dict[str, Any]]:
        """Get all verified tokens on Jupiter.

        Returns:
            List of token metadata
        """
        try:
            response = await self.get("tokens/v1")

            tokens = response if isinstance(response, list) else []

            logger.info(f"Fetched {len(tokens)} tokens from Jupiter")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching Jupiter token list: {str(e)}")
            return []

    async def get_top_tokens(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top tokens by volume on Jupiter.

        Args:
            limit: Max number of tokens

        Returns:
            List of top token data
        """
        try:
            # Jupiter doesn't have a direct trending endpoint
            # We'll use the tokens endpoint and filter by strict list
            response = await self.get("tokens/v1/strict")

            tokens = response if isinstance(response, list) else []

            # Add price data
            enriched = []
            for token in tokens[:limit]:
                mint = token.get("address")
                price = await self.get_token_price(mint)

                enriched.append({
                    "token_address": mint,
                    "chain_id": "solana",
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "price_usd": price or 0,
                    "decimals": token.get("decimals"),
                    "logo_uri": token.get("logoURI"),
                    "source": "jupiter",
                })

            logger.info(f"Fetched {len(enriched)} top tokens from Jupiter")
            return enriched

        except Exception as e:
            logger.error(f"Error fetching Jupiter top tokens: {str(e)}")
            return []
