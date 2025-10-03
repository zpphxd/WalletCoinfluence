"""Defined.fi GraphQL API client for new pools and pairs."""

import logging
from typing import List, Dict, Any, Optional
from src.clients.base import BaseAPIClient

logger = logging.getLogger(__name__)


class DefinedClient(BaseAPIClient):
    """Client for Defined.fi (formerly Defined) - free GraphQL API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Defined client.

        Args:
            api_key: Optional API key (free tier available)
        """
        super().__init__(
            base_url="https://graph.defined.fi",
            api_key=api_key,
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with API key if available."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    async def get_new_pools(
        self,
        network_filter: Optional[List[int]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get newly created pools across chains.

        Args:
            network_filter: List of network IDs (1=Ethereum, 56=BSC, etc.)
            limit: Max number of pools

        Returns:
            List of new pool data
        """
        try:
            query = """
            query GetNewPools($limit: Int, $networkFilter: [Int!]) {
              filterPairs(
                limit: $limit
                filters: {
                  network: $networkFilter
                }
                rankings: [
                  {
                    attribute: createdAt
                    direction: DESC
                  }
                ]
              ) {
                results {
                  pair {
                    address
                    token0 {
                      address
                      symbol
                    }
                    token1 {
                      address
                      symbol
                    }
                    createdAt
                    networkId
                    liquidity
                    volume24
                    priceUsd
                  }
                }
              }
            }
            """

            variables = {
                "limit": limit,
                "networkFilter": network_filter or [1, 56, 137, 8453, 42161],  # ETH, BSC, Polygon, Base, Arb
            }

            response = await self.post(
                "",
                data={"query": query, "variables": variables}
            )

            pools = response.get("data", {}).get("filterPairs", {}).get("results", [])

            tokens = []
            for item in pools:
                pair = item.get("pair", {})
                token0 = pair.get("token0", {})

                tokens.append({
                    "token_address": token0.get("address"),
                    "chain_id": self._network_id_to_chain(pair.get("networkId")),
                    "symbol": token0.get("symbol"),
                    "price_usd": float(pair.get("priceUsd", 0)),
                    "liquidity_usd": float(pair.get("liquidity", 0)),
                    "volume_24h_usd": float(pair.get("volume24", 0)),
                    "pair_address": pair.get("address"),
                    "created_at": pair.get("createdAt"),
                    "source": "defined",
                })

            logger.info(f"Fetched {len(tokens)} new pools from Defined.fi")
            return tokens

        except Exception as e:
            logger.error(f"Error fetching Defined.fi new pools: {str(e)}")
            return []

    def _network_id_to_chain(self, network_id: int) -> str:
        """Convert network ID to chain name.

        Args:
            network_id: Defined network ID

        Returns:
            Chain name
        """
        mapping = {
            1: "ethereum",
            56: "bsc",
            137: "polygon",
            8453: "base",
            42161: "arbitrum",
            10: "optimism",
            43114: "avalanche",
        }
        return mapping.get(network_id, f"chain_{network_id}")
