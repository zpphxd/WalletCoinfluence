"""Dextools API client for trending tokens (FREE tier)."""

import logging
from typing import List, Dict, Any, Optional
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class DextoolsClient(BaseAPIClient):
    """Client for Dextools trending tokens (free public API)."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Dextools client.

        Args:
            api_key: Optional API key for higher limits
        """
        super().__init__(
            base_url="https://www.dextools.io/shared/data",
            api_key=api_key,
        )

    async def get_hot_pairs(self, chain: str = "ether") -> List[Dict[str, Any]]:
        """Get hot/trending pairs from Dextools.

        Args:
            chain: Chain name (ether, bsc, polygon, etc.)

        Returns:
            List of hot pair data
        """
        try:
            # Dextools public endpoint (no auth needed for basic data)
            response = await self.get(f"chain/hot/{chain}")

            pairs = response.get("data", [])

            tokens = []
            for pair in pairs[:50]:  # Top 50
                token_info = pair.get("token", {})
                metrics = pair.get("metrics", {})

                tokens.append({
                    "token_address": token_info.get("address"),
                    "chain_id": self._normalize_chain(chain),
                    "symbol": token_info.get("symbol"),
                    "price_usd": float(metrics.get("price", 0)),
                    "liquidity_usd": float(metrics.get("liquidity", 0)),
                    "volume_24h_usd": float(metrics.get("volume24h", 0)),
                    "price_change_24h": float(metrics.get("variation24h", 0)),
                    "pair_address": pair.get("address"),
                    "dex_id": pair.get("dex"),
                    "source": "dextools",
                })

            logger.info(f"Fetched {len(tokens)} hot pairs from Dextools for {chain}")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching Dextools hot pairs for {chain}: {str(e)}")
            return []

    def _normalize_chain(self, dextools_chain: str) -> str:
        """Normalize Dextools chain names to our standard.

        Args:
            dextools_chain: Dextools chain identifier

        Returns:
            Normalized chain name
        """
        mapping = {
            "ether": "ethereum",
            "bsc": "bsc",
            "polygon": "polygon",
            "arbitrum": "arbitrum",
            "base": "base",
            "avalanche": "avalanche",
            "optimism": "optimism",
        }
        return mapping.get(dextools_chain, dextools_chain)
