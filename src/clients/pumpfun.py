"""Pump.fun API client for Solana memecoin launches (FREE)."""

import logging
from typing import List, Dict, Any
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class PumpFunClient(BaseAPIClient):
    """Client for Pump.fun - Solana memecoin launchpad."""

    def __init__(self):
        """Initialize Pump.fun client."""
        super().__init__(base_url="https://frontend-api.pump.fun")

    async def get_new_tokens(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get newly launched tokens on Pump.fun.

        Args:
            limit: Max number of tokens

        Returns:
            List of new token data
        """
        try:
            # Get new token listings
            response = await self.get(
                "coins/latest",
                params={"limit": limit, "offset": 0}
            )

            coins = response if isinstance(response, list) else response.get("coins", [])

            tokens = []
            for coin in coins[:limit]:
                tokens.append({
                    "token_address": coin.get("mint"),
                    "chain_id": "solana",
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "price_usd": float(coin.get("usd_market_cap", 0)) / max(float(coin.get("total_supply", 1)), 1),
                    "market_cap_usd": float(coin.get("usd_market_cap", 0)),
                    "liquidity_usd": float(coin.get("virtual_sol_reserves", 0)) * 100,  # Approx SOL price
                    "created_timestamp": coin.get("created_timestamp"),
                    "creator": coin.get("creator"),
                    "bonding_curve": coin.get("bonding_curve"),
                    "source": "pumpfun",
                })

            logger.info(f"Fetched {len(tokens)} new tokens from Pump.fun")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching Pump.fun tokens: {str(e)}")
            return []

    async def get_trending_tokens(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get trending tokens on Pump.fun.

        Args:
            limit: Max number of tokens

        Returns:
            List of trending token data
        """
        try:
            response = await self.get(
                "coins/trending",
                params={"limit": limit}
            )

            coins = response if isinstance(response, list) else response.get("coins", [])

            tokens = []
            for coin in coins[:limit]:
                tokens.append({
                    "token_address": coin.get("mint"),
                    "chain_id": "solana",
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "price_usd": float(coin.get("usd_market_cap", 0)) / max(float(coin.get("total_supply", 1)), 1),
                    "market_cap_usd": float(coin.get("usd_market_cap", 0)),
                    "volume_24h_usd": float(coin.get("volume_24h", 0)),
                    "price_change_24h": float(coin.get("price_change_percentage_24h", 0)),
                    "reply_count": coin.get("reply_count", 0),
                    "source": "pumpfun",
                })

            logger.info(f"Fetched {len(tokens)} trending tokens from Pump.fun")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching Pump.fun trending: {str(e)}")
            return []

    async def get_token_trades(self, mint_address: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades for a specific token.

        Args:
            mint_address: Token mint address
            limit: Max trades to fetch

        Returns:
            List of trade data
        """
        try:
            response = await self.get(
                f"coins/{mint_address}/trades",
                params={"limit": limit}
            )

            trades = response if isinstance(response, list) else response.get("trades", [])

            return [{
                "wallet": trade.get("user"),
                "side": "buy" if trade.get("is_buy") else "sell",
                "sol_amount": float(trade.get("sol_amount", 0)),
                "token_amount": float(trade.get("token_amount", 0)),
                "timestamp": trade.get("timestamp"),
                "tx_hash": trade.get("signature"),
            } for trade in trades]

        except Exception as e:
            logger.error(f"Error fetching Pump.fun trades for {mint_address}: {str(e)}")
            return []
