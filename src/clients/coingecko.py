"""CoinGecko API client for trending coins (FREE)."""

import logging
from typing import List, Dict, Any
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class CoinGeckoClient(BaseAPIClient):
    """Client for CoinGecko trending coins (free public API)."""

    def __init__(self):
        """Initialize CoinGecko client."""
        super().__init__(base_url="https://api.coingecko.com/api/v3")

    async def get_trending_coins(self) -> List[Dict[str, Any]]:
        """Get trending coins from CoinGecko.

        Returns:
            List of trending coin data
        """
        try:
            response = await self.get("search/trending")

            coins = response.get("coins", [])

            tokens = []
            for item in coins:
                coin = item.get("item", {})

                # Get additional data for the coin
                coin_id = coin.get("id")
                coin_data = await self._get_coin_data(coin_id)

                if coin_data:
                    tokens.append(coin_data)

            logger.info(f"Fetched {len(tokens)} trending coins from CoinGecko")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching CoinGecko trending: {str(e)}")
            return []

    async def _get_coin_data(self, coin_id: str) -> Dict[str, Any]:
        """Get detailed data for a specific coin.

        Args:
            coin_id: CoinGecko coin ID

        Returns:
            Coin data dict
        """
        try:
            response = await self.get(f"coins/{coin_id}")

            platforms = response.get("platforms", {})
            market_data = response.get("market_data", {})

            # Try to find token address (prefer Ethereum)
            token_address = None
            chain_id = None

            for platform, address in platforms.items():
                if address and address != "":
                    if platform == "ethereum":
                        token_address = address
                        chain_id = "ethereum"
                        break
                    elif platform == "binance-smart-chain":
                        token_address = address
                        chain_id = "bsc"
                    elif platform == "base":
                        token_address = address
                        chain_id = "base"
                        break
                    elif not token_address:  # Use first available
                        token_address = address
                        chain_id = platform

            if not token_address:
                return {}

            return {
                "token_address": token_address,
                "chain_id": self._normalize_platform(chain_id),
                "symbol": response.get("symbol", "").upper(),
                "price_usd": float(market_data.get("current_price", {}).get("usd", 0)),
                "market_cap_usd": float(market_data.get("market_cap", {}).get("usd", 0)),
                "volume_24h_usd": float(market_data.get("total_volume", {}).get("usd", 0)),
                "price_change_24h": float(market_data.get("price_change_percentage_24h", 0)),
                "source": "coingecko",
            }

        except Exception as e:
            logger.error(f"Error fetching CoinGecko coin data for {coin_id}: {str(e)}")
            return {}

    def _normalize_platform(self, platform: str) -> str:
        """Normalize CoinGecko platform names.

        Args:
            platform: CoinGecko platform name

        Returns:
            Normalized chain name
        """
        mapping = {
            "ethereum": "ethereum",
            "binance-smart-chain": "bsc",
            "polygon-pos": "polygon",
            "arbitrum-one": "arbitrum",
            "base": "base",
            "optimistic-ethereum": "optimism",
            "avalanche": "avalanche",
        }
        return mapping.get(platform, platform)
