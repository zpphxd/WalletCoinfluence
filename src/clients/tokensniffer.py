"""TokenSniffer API client for additional scam checks."""

import logging
from typing import Dict, Any, Optional
from src.clients.base import BaseAPIClient
from src.config import settings

logger = logging.getLogger(__name__)


class TokenSnifferClient(BaseAPIClient):
    """Client for TokenSniffer scam detection."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize TokenSniffer client.

        Args:
            api_key: API key (defaults to settings)
        """
        super().__init__(
            base_url="https://tokensniffer.com/api/v2",
            api_key=api_key or settings.tokensniffer_api_key,
        )

    def _get_headers(self) -> Dict[str, str]:
        """Override to use apikey query param."""
        return {"Content-Type": "application/json"}

    async def check_token(
        self, token_address: str, chain_id: str = "ethereum"
    ) -> Dict[str, Any]:
        """Check token for scam indicators.

        Args:
            token_address: Token address
            chain_id: Chain identifier

        Returns:
            Dict with scam indicators
        """
        try:
            # Map chains
            chain_map = {
                "ethereum": "eth",
                "base": "base",
                "arbitrum": "arbitrum",
                "bsc": "bsc",
            }

            chain = chain_map.get(chain_id, chain_id)

            params = {
                "address": token_address,
                "chain": chain,
            }

            if self.api_key:
                params["apikey"] = self.api_key

            response = await self.get("tokens", params=params)

            # Parse response
            score = response.get("score", 0)
            risks = response.get("risks", [])

            return {
                "score": score,  # 0-100, higher is safer
                "is_scam": score < 30,
                "risks": risks,
                "owner_can_mint": "owner_can_mint" in [r.get("name") for r in risks],
                "owner_can_blacklist": "owner_can_blacklist" in [r.get("name") for r in risks],
            }

        except Exception as e:
            logger.error(f"Error checking TokenSniffer for {token_address}: {str(e)}")
            return {
                "score": None,
                "is_scam": None,
                "risks": [],
            }
