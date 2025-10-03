"""Honeypot.is API client for scam detection."""

import logging
from typing import Dict, Any, Optional
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class HoneypotClient(BaseAPIClient):
    """Client for Honeypot.is scam/tax detection."""

    def __init__(self) -> None:
        """Initialize Honeypot client."""
        super().__init__(base_url="https://api.honeypot.is/v2")

    async def check_token(
        self, token_address: str, chain_id: str = "ethereum"
    ) -> Dict[str, Any]:
        """Check if token is a honeypot or has high taxes.

        Args:
            token_address: Token address
            chain_id: Chain identifier

        Returns:
            Dict with is_honeypot, buy_tax, sell_tax
        """
        try:
            # Map chain names to Honeypot.is format
            chain_map = {
                "ethereum": "eth",
                "base": "base",
                "arbitrum": "arbitrum",
                "bsc": "bsc",
            }

            chain = chain_map.get(chain_id, chain_id)

            response = await self.get(f"IsHoneypot", params={"address": token_address, "chainID": chain})

            simulation = response.get("simulationResult", {})
            honeypot_result = response.get("honeypotResult", {})

            return {
                "is_honeypot": honeypot_result.get("isHoneypot", False),
                "buy_tax": simulation.get("buyTax", 0) * 100,  # Convert to percentage
                "sell_tax": simulation.get("sellTax", 0) * 100,
                "transfer_tax": simulation.get("transferTax", 0) * 100,
                "buy_gas": simulation.get("buyGas"),
                "sell_gas": simulation.get("sellGas"),
            }

        except Exception as e:
            logger.error(f"Error checking honeypot for {token_address}: {str(e)}")
            return {
                "is_honeypot": None,
                "buy_tax": None,
                "sell_tax": None,
                "transfer_tax": None,
            }
