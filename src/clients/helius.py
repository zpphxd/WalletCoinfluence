"""Helius API client for Solana chain data."""

import logging
import os
from typing import List, Dict, Any
from datetime import datetime
from src.clients.base import BaseAPIClient
from src.clients.dexscreener import DexScreenerClient
from src.utils.dex_routers import is_dex_router, get_dex_name
from src.config import settings

logger = logging.getLogger(__name__)


class HeliusClient(BaseAPIClient):
    """Client for Helius Solana data."""

    def __init__(self) -> None:
        """Initialize Helius client."""
        # Try settings first, fallback to direct os.getenv
        self.api_key = settings.helius_api_key or os.getenv("HELIUS_API_KEY", "")

        if not self.api_key:
            logger.warning("⚠️  HELIUS_API_KEY not set - Solana monitoring will not work")
            # Don't raise error, allow initialization but log warning
        else:
            logger.info(f"✅ Helius client initialized with API key: {self.api_key[:8]}...")

        # Helius uses mainnet RPC endpoint with API key as query param
        super().__init__(base_url=f"https://mainnet.helius-rpc.com")
        self.dex_client = DexScreenerClient()

    async def get_wallet_transactions(
        self, wallet_address: str, limit: int = 100
        ) -> List[Dict[str, Any]]:
        """Get wallet transactions using Helius enhanced transactions API."""
        try:
            if not self.api_key:
                logger.warning("Helius API key not configured - skipping Solana wallet")
                return []

            # Use Helius enhanced transactions endpoint (parse transactions for us!)
            # Endpoint: https://api.helius.xyz/v0/addresses/{address}/transactions
            url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions?api-key={self.api_key}"

            # Make request with httpx directly
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params={"limit": min(limit, 100)})
                response.raise_for_status()
                data = response.json()

            transactions = []
            for tx in data:
                # Helius gives us parsed transactions with type, source, and token info
                tx_type = tx.get("type", "").lower()

                # Only track DEX swaps
                if tx_type != "swap":
                    continue

                # Get token info from transaction
                token_transfers = tx.get("tokenTransfers", [])
                if not token_transfers:
                    continue

                # Find the token they're buying (destination token)
                bought_token = None
                sold_token = None
                for transfer in token_transfers:
                    if transfer.get("toUserAccount") == wallet_address:
                        bought_token = transfer
                    elif transfer.get("fromUserAccount") == wallet_address:
                        sold_token = transfer

                if not bought_token:
                    continue  # Not a buy for this wallet

                token_address = bought_token.get("mint", "")
                amount = float(bought_token.get("tokenAmount", 0))

                # Get price from DexScreener
                token_info = await self.dex_client.get_token_info(token_address)
                price_usd = token_info.get("price_usd", 0)
                value_usd = amount * price_usd if price_usd > 0 else 0

                transactions.append({
                    "tx_hash": tx.get("signature"),
                    "timestamp": datetime.fromtimestamp(tx.get("timestamp", 0)) if tx.get("timestamp") else datetime.utcnow(),
                    "type": "buy",
                    "token_address": token_address,
                    "wallet_address": wallet_address,
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": tx.get("source", "raydium").lower(),
                })

            logger.info(f"✅ Fetched {len(transactions)} Solana DEX buys for {wallet_address[:8]}...")
            return transactions

        except httpx.HTTPStatusError as e:
            logger.error(f"Helius API HTTP error {e.response.status_code}: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Helius API error: {str(e)}")
            return []

    async def get_token_transactions(
        self, token_address: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get token transactions (not wallet transactions)."""
        try:
            # For now, return empty - we primarily track wallet transactions
            return []

            # Old code that didn't work:

            # Get token price from DexScreener
            token_info = await self.dex_client.get_token_info(token_address)
            current_price = token_info.get("price_usd", 0)

            transactions = []
            for tx in response:
                # Check if this transaction involves a DEX program
                dex_program = None
                dex_name = "unknown"
                if "instructions" in tx:
                    for inst in tx.get("instructions", []):
                        program_id = inst.get("programId", "").lower()
                        if is_dex_router(program_id, "solana"):
                            dex_program = program_id
                            dex_name = get_dex_name(program_id, "solana")
                            break

                # Skip non-DEX transactions
                if not dex_program:
                    continue

                # Try to extract amount from token balance changes
                amount = 0
                if "tokenBalanceChanges" in tx:
                    for change in tx["tokenBalanceChanges"]:
                        if change.get("mint") == token_address:
                            amount = abs(float(change.get("amount", 0)) / 10**9)  # Assume 9 decimals for Solana
                            break

                value_usd = amount * current_price if current_price > 0 else 0

                transactions.append({
                    "tx_hash": tx.get("signature"),
                    "timestamp": datetime.fromtimestamp(tx.get("timestamp", 0)),
                    "from_address": tx.get("feePayer"),
                    "type": "buy",
                    "token_address": token_address,
                    "amount": amount,
                    "price_usd": current_price,
                    "value_usd": value_usd,
                    "dex": dex_name,
                })

            logger.info(f"Fetched {len(transactions)} txs from Helius (price=${current_price:.9f})")
            return transactions

        except Exception as e:
            logger.error(f"Helius API error: {str(e)}")
            return []

