"""DEX Screener API client for trending tokens."""

import logging
from typing import List, Dict, Any
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class DexScreenerClient(BaseAPIClient):
    """Client for DEX Screener trending tokens."""

    def __init__(self) -> None:
        """Initialize DEX Screener client."""
        super().__init__(base_url="https://api.dexscreener.com/latest")

    async def get_trending_tokens(self, chain: str = "ethereum") -> List[Dict[str, Any]]:
        """Fetch trending tokens for a specific chain.

        Args:
            chain: Chain identifier (ethereum, bsc, arbitrum, base, solana, etc.)

        Returns:
            List of trending token data
        """
        try:
            # Map our chain names to DEX Screener chain IDs
            chain_map = {
                "ethereum": "ethereum",
                "base": "base",
                "arbitrum": "arbitrum",
                "solana": "solana",
            }

            dex_chain = chain_map.get(chain, chain)

            # Try chain-specific search endpoint instead of boosted
            response = await self.get(f"dex/search?q=chainId:{dex_chain}")

            pairs = response.get("pairs")

            # Handle null response
            if pairs is None:
                logger.warning(f"DEX Screener returned null pairs for {chain}, trying alternative endpoint")
                # Fallback: get latest pairs for the chain
                response = await self.get(f"dex/pairs/{dex_chain}")
                pairs = response.get("pairs", [])

            if not pairs:
                pairs = []

            # Filter by chain and normalize
            tokens = []
            for pair in pairs:
                if pair.get("chainId") == chain:
                    tokens.append({
                        "token_address": pair.get("baseToken", {}).get("address"),
                        "chain_id": chain,
                        "symbol": pair.get("baseToken", {}).get("symbol"),
                        "price_usd": float(pair.get("priceUsd", 0)),
                        "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0)),
                        "volume_24h_usd": float(pair.get("volume", {}).get("h24", 0)),
                        "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)),
                        "pair_address": pair.get("pairAddress"),
                        "dex_id": pair.get("dexId"),
                    })

            logger.info(f"Fetched {len(tokens)} trending tokens for {chain} from DEX Screener")
            return tokens[:50]  # Top 50

        except Exception as e:
            logger.error(f"Error fetching DEX Screener trending for {chain}: {str(e)}")
            return []

    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get detailed info for a specific token.

        Args:
            token_address: Token contract address

        Returns:
            Token info
        """
        try:
            response = await self.get(f"dex/tokens/{token_address}")
            pairs = response.get("pairs", [])

            if not pairs:
                return {}

            # Use the pair with highest liquidity
            best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))

            return {
                "token_address": token_address,
                "chain_id": best_pair.get("chainId"),
                "symbol": best_pair.get("baseToken", {}).get("symbol"),
                "price_usd": float(best_pair.get("priceUsd", 0)),
                "liquidity_usd": float(best_pair.get("liquidity", {}).get("usd", 0)),
                "volume_24h_usd": float(best_pair.get("volume", {}).get("h24", 0)),
                "price_change_24h": float(best_pair.get("priceChange", {}).get("h24", 0)),
            }

        except Exception as e:
            logger.error(f"Error fetching token info for {token_address}: {str(e)}")
            return {}
