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
        """Get wallet transactions (for monitoring whales)."""
        try:
            # Use Helius' enhanced getSignaturesForAddress via JSON-RPC
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [wallet_address, {"limit": min(limit, 1000)}]
            }

            response = await self.post(
                f"/?api-key={self.api_key}",
                json=payload
            )

            if "error" in response:
                logger.error(f"Helius API error: {response['error']}")
                return []

            # Return simplified format for wallet monitor
            transactions = []
            for sig_info in response.get("result", [])[:limit]:
                transactions.append({
                    "tx_hash": sig_info.get("signature"),
                    "timestamp": datetime.fromtimestamp(sig_info.get("blockTime", 0)) if sig_info.get("blockTime") else datetime.utcnow(),
                    "type": "buy",  # Simplified - we'd need to parse full tx to know buy/sell
                    "token_address": "",  # Would need full tx parse
                    "amount": 0,
                    "price_usd": 0,
                    "value_usd": 0,
                    "dex": "raydium",  # Most common on Solana
                })

            logger.info(f"Fetched {len(transactions)} Solana transactions for {wallet_address[:8]}...")
            return transactions

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

    async def get_wallet_transactions(
        self, wallet_address: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent wallet transactions."""
        try:
            response = await self.get(
                f"/addresses/{wallet_address}/transactions",
                params={"api-key": self.api_key, "limit": min(limit, 100)}
            )

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

                # Extract token info from balance changes
                token_addr = None
                amount = 0
                if "tokenBalanceChanges" in tx and tx["tokenBalanceChanges"]:
                    change = tx["tokenBalanceChanges"][0]  # Take first token change
                    token_addr = change.get("mint")
                    amount = abs(float(change.get("amount", 0)) / 10**9)  # Assume 9 decimals

                # Get price if we have a token
                price_usd = 0
                value_usd = 0
                if token_addr:
                    token_info = await self.dex_client.get_token_info(token_addr)
                    price_usd = token_info.get("price_usd", 0)
                    value_usd = amount * price_usd if price_usd > 0 else 0

                transactions.append({
                    "tx_hash": tx.get("signature"),
                    "timestamp": datetime.fromtimestamp(tx.get("timestamp", 0)),
                    "type": "buy",
                    "token_address": token_addr,
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": dex_name,
                })

            logger.info(f"Fetched {len(transactions)} txs from Helius")
            return transactions

        except Exception as e:
            logger.error(f"Helius API error: {str(e)}")
            return []
