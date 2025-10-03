"""GeckoTerminal API client for trending tokens."""

import logging
from typing import List, Dict, Any
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


# Chain mapping for GeckoTerminal
CHAIN_MAPPING = {
    "ethereum": "eth",
    "base": "base",
    "arbitrum": "arbitrum",
    "solana": "solana",
    "bsc": "bsc",
}


class GeckoTerminalClient(BaseAPIClient):
    """Client for GeckoTerminal trending pools."""

    def __init__(self) -> None:
        """Initialize GeckoTerminal client."""
        super().__init__(base_url="https://api.geckoterminal.com/api/v2")

    async def get_trending_pools(self, chain: str = "ethereum") -> List[Dict[str, Any]]:
        """Fetch trending pools for a specific chain.

        Args:
            chain: Chain identifier

        Returns:
            List of trending token data from pools
        """
        try:
            network = CHAIN_MAPPING.get(chain, chain)
            response = await self.get(f"networks/{network}/trending_pools")

            pools = response.get("data", [])

            tokens = []
            for pool in pools:
                attributes = pool.get("attributes", {})
                relationships = pool.get("relationships", {})

                # Extract base token address from relationships
                base_token_data = relationships.get("base_token", {}).get("data", {})
                base_token_id = base_token_data.get("id", "")

                # ID format is "chain_address", extract address
                base_token_address = base_token_id.split("_", 1)[1] if "_" in base_token_id else None
                base_token_price = attributes.get("base_token_price_usd")

                # Must have both address and price
                if base_token_address and base_token_price:
                    # Get symbol from pool name (e.g., "PNKSTR / ETH" -> "PNKSTR")
                    pool_name = attributes.get("name", "")
                    symbol = pool_name.split("/")[0].strip() if "/" in pool_name else "UNKNOWN"

                    tokens.append({
                        "token_address": base_token_address,
                        "chain_id": chain,
                        "symbol": symbol,
                        "price_usd": float(base_token_price),
                        "liquidity_usd": float(attributes.get("reserve_in_usd", 0)),
                        "volume_24h_usd": float(attributes.get("volume_usd", {}).get("h24", 0)),
                        "price_change_24h": float(attributes.get("price_change_percentage", {}).get("h24", 0)),
                        "pool_address": attributes.get("address"),
                        "dex_id": relationships.get("dex", {}).get("data", {}).get("id"),
                    })

            logger.info(f"Fetched {len(tokens)} trending pools for {chain} from GeckoTerminal")
            return tokens[:50]

        except Exception as e:
            logger.error(f"Error fetching GeckoTerminal trending for {chain}: {str(e)}")
            return []

    async def get_pool_info(self, chain: str, pool_address: str) -> Dict[str, Any]:
        """Get detailed pool information.

        Args:
            chain: Chain identifier
            pool_address: Pool contract address

        Returns:
            Pool info
        """
        try:
            network = CHAIN_MAPPING.get(chain, chain)
            response = await self.get(f"networks/{network}/pools/{pool_address}")

            data = response.get("data", {})
            attributes = data.get("attributes", {})

            return {
                "pool_address": pool_address,
                "chain_id": chain,
                "token_address": attributes.get("base_token_address"),
                "symbol": attributes.get("base_token_symbol"),
                "price_usd": float(attributes.get("base_token_price_usd", 0)),
                "liquidity_usd": float(attributes.get("reserve_in_usd", 0)),
                "volume_24h_usd": float(attributes.get("volume_usd", {}).get("h24", 0)),
            }

        except Exception as e:
            logger.error(f"Error fetching pool info for {pool_address}: {str(e)}")
            return {}
