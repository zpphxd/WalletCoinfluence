"""Multi-source price fetcher with fallbacks to avoid rate limiting."""

import logging
from typing import Optional
import asyncio

from src.clients.dexscreener import DexScreenerClient
from src.clients.birdeye import BirdeyeClient
from src.clients.coingecko import CoinGeckoClient

logger = logging.getLogger(__name__)


class MultiSourcePriceFetcher:
    """Fetches token prices from multiple sources with automatic fallbacks."""

    def __init__(self):
        """Initialize all price sources."""
        self.dexscreener = DexScreenerClient()
        self.birdeye = BirdeyeClient()
        self.coingecko = CoinGeckoClient()

        # Track failures to avoid hammering dead APIs
        self.failure_counts = {
            "dexscreener": 0,
            "birdeye": 0,
            "coingecko": 0,
        }

    async def get_token_price(
        self, token_address: str, chain_id: str = "ethereum"
    ) -> float:
        """Get current token price trying multiple sources with fallbacks.

        Tries in order:
        1. DexScreener (best for EVM chains, has liquidity data)
        2. Birdeye (good for all chains, more generous rate limits)
        3. CoinGecko (fallback, only for major tokens)

        Args:
            token_address: Token contract address
            chain_id: Chain identifier (ethereum, base, arbitrum, solana, etc.)

        Returns:
            Current price in USD (0.0 if all sources fail)
        """
        # Try DexScreener first (best data, but rate limited)
        if self.failure_counts["dexscreener"] < 5:  # Skip if failing too much
            price = await self._try_dexscreener(token_address)
            if price > 0:
                self.failure_counts["dexscreener"] = 0  # Reset on success
                logger.info(
                    f"💰 Price from DexScreener: {token_address[:10]}... = ${price:.8f}"
                )
                return price
            else:
                self.failure_counts["dexscreener"] += 1

        # Try Birdeye second (more generous rate limits)
        if self.failure_counts["birdeye"] < 5:
            price = await self._try_birdeye(token_address, chain_id)
            if price > 0:
                self.failure_counts["birdeye"] = 0
                logger.info(
                    f"💰 Price from Birdeye: {token_address[:10]}... = ${price:.8f}"
                )
                return price
            else:
                self.failure_counts["birdeye"] += 1

        # Try CoinGecko third (only works for major tokens)
        if self.failure_counts["coingecko"] < 5:
            price = await self._try_coingecko(token_address, chain_id)
            if price > 0:
                self.failure_counts["coingecko"] = 0
                logger.info(
                    f"💰 Price from CoinGecko: {token_address[:10]}... = ${price:.8f}"
                )
                return price
            else:
                self.failure_counts["coingecko"] += 1

        # All sources failed
        logger.error(
            f"❌ ALL PRICE SOURCES FAILED for {token_address[:10]}... on {chain_id}\n"
            f"   DexScreener failures: {self.failure_counts['dexscreener']}\n"
            f"   Birdeye failures: {self.failure_counts['birdeye']}\n"
            f"   CoinGecko failures: {self.failure_counts['coingecko']}"
        )
        return 0.0

    async def _try_dexscreener(self, token_address: str) -> float:
        """Try fetching price from DexScreener."""
        try:
            token_info = await self.dexscreener.get_token_info(token_address)
            return float(token_info.get("price_usd", 0.0))
        except Exception as e:
            logger.debug(f"DexScreener failed for {token_address[:10]}...: {str(e)}")
            return 0.0

    async def _try_birdeye(self, token_address: str, chain_id: str) -> float:
        """Try fetching price from Birdeye."""
        try:
            # Birdeye has get_token_overview for detailed data
            token_info = await self.birdeye.get_token_overview(token_address)
            return float(token_info.get("price_usd", 0.0))
        except Exception as e:
            logger.debug(f"Birdeye failed for {token_address[:10]}...: {str(e)}")
            return 0.0

    async def _try_coingecko(self, token_address: str, chain_id: str) -> float:
        """Try fetching price from CoinGecko (only major tokens)."""
        try:
            # CoinGecko needs platform mapping
            platform_map = {
                "ethereum": "ethereum",
                "base": "base",
                "arbitrum": "arbitrum-one",
                "polygon": "polygon-pos",
                "bsc": "binance-smart-chain",
            }

            platform = platform_map.get(chain_id, chain_id)

            # CoinGecko API: /simple/token_price/{platform}?contract_addresses=XXX
            response = await self.coingecko.get(
                f"simple/token_price/{platform}",
                params={
                    "contract_addresses": token_address,
                    "vs_currencies": "usd",
                },
                rate_limit_delay=2.0,  # CoinGecko is strict on rate limits
            )

            # Response format: {token_address: {usd: price}}
            price_data = response.get(token_address.lower(), {})
            return float(price_data.get("usd", 0.0))

        except Exception as e:
            logger.debug(f"CoinGecko failed for {token_address[:10]}...: {str(e)}")
            return 0.0

    def reset_failure_counts(self):
        """Reset failure counts (call periodically to give APIs another chance)."""
        self.failure_counts = {
            "dexscreener": 0,
            "birdeye": 0,
            "coingecko": 0,
        }
        logger.info("🔄 Price fetcher failure counts reset")
