#!/usr/bin/env python3
"""Backfill Solana whale wallets using Solscan public API.

Since Helius requires API key configuration, we'll use Solscan's public API
which doesn't require authentication for basic queries.
"""

import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import Wallet, Trade, CustomWatchlistWallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SolscanClient:
    """Client for Solscan public API (no auth required)."""

    BASE_URL = "https://public-api.solscan.io"

    async def get_wallet_transfers(
        self, wallet_address: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get SPL token transfers for a wallet.

        Solscan Public API endpoint - no authentication needed.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/account/token/txs",
                    params={
                        "address": wallet_address,
                        "limit": min(limit, 100),
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.error(
                        f"Solscan API error {response.status_code}: {response.text}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error fetching Solscan data: {str(e)}")
            return []

    async def get_wallet_sol_transfers(
        self, wallet_address: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get SOL transfers for a wallet."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/account/transactions",
                    params={
                        "address": wallet_address,
                        "limit": min(limit, 50),
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.error(
                        f"Solscan SOL API error {response.status_code}: {response.text}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error fetching SOL transfers: {str(e)}")
            return []


async def backfill_solana_whale(
    db: Session, wallet_address: str, chain_id: str = "solana"
) -> int:
    """Backfill transaction data for a single Solana whale.

    Returns:
        Number of trades added
    """
    logger.info(f"🔍 Backfilling {wallet_address[:16]}...")

    client = SolscanClient()

    # Get SPL token transfers (memecoins, etc.)
    transfers = await client.get_wallet_transfers(wallet_address, limit=100)

    if not transfers:
        logger.warning(f"   No transfers found for {wallet_address[:16]}...")
        return 0

    # Create wallet record if doesn't exist
    existing_wallet = (
        db.query(Wallet)
        .filter(Wallet.address == wallet_address, Wallet.chain_id == chain_id)
        .first()
    )

    if not existing_wallet:
        new_wallet = Wallet(
            address=wallet_address,
            chain_id=chain_id,
            first_seen_at=datetime.utcnow(),
        )
        db.add(new_wallet)
        db.commit()
        logger.info(f"   ✅ Created wallet record for {wallet_address[:16]}...")

    # Process transfers into trades
    trades_added = 0

    for tx in transfers[:50]:  # Limit to recent 50 to avoid rate limits
        try:
            # Extract transfer data
            tx_hash = tx.get("txHash")
            if not tx_hash:
                continue

            # Check if trade already exists
            existing = db.query(Trade).filter(Trade.tx_hash == tx_hash).first()
            if existing:
                continue

            # Parse timestamp
            block_time = tx.get("blockTime")
            if not block_time:
                continue

            ts = datetime.fromtimestamp(block_time)

            # Get token address and amount
            token_address = tx.get("tokenAddress")
            if not token_address:
                continue

            # Determine if buy or sell based on change amount
            change_amount = float(tx.get("changeAmount", 0))
            if change_amount == 0:
                continue

            side = "buy" if change_amount > 0 else "sell"
            qty_token = abs(change_amount)

            # Create trade record (without price for now - would need DexScreener)
            trade = Trade(
                tx_hash=tx_hash,
                ts=ts,
                chain_id=chain_id,
                wallet_address=wallet_address,
                token_address=token_address,
                side=side,
                qty_token=qty_token,
                price_usd=0,  # TODO: Enrich with DexScreener later
                usd_value=0,
                venue="unknown",  # Solscan doesn't provide DEX info easily
            )

            db.add(trade)
            trades_added += 1

        except Exception as e:
            logger.error(f"   Error processing transfer: {str(e)}")
            continue

    db.commit()

    if trades_added > 0:
        logger.info(f"   ✅ Added {trades_added} trades for {wallet_address[:16]}...")
    else:
        logger.info(f"   ⏭️  No new trades for {wallet_address[:16]}... (all exist)")

    return trades_added


async def backfill_all_solana_whales():
    """Backfill all Solana whales from custom watchlist."""
    db = SessionLocal()

    try:
        print("\n" + "=" * 80)
        print("🐋 BACKFILLING SOLANA WHALE TRANSACTION DATA")
        print("=" * 80)
        print()
        print("Using: Solscan Public API (no authentication required)")
        print()

        # Get all Solana whales from custom watchlist
        solana_whales = (
            db.query(CustomWatchlistWallet)
            .filter(
                CustomWatchlistWallet.chain_id == "solana",
                CustomWatchlistWallet.is_active == True,
            )
            .all()
        )

        if not solana_whales:
            print("❌ No Solana whales found in custom watchlist")
            return

        print(f"📋 Found {len(solana_whales)} Solana whales to backfill")
        print()

        total_trades_added = 0

        for whale in solana_whales:
            trades_added = await backfill_solana_whale(
                db, whale.address, whale.chain_id
            )
            total_trades_added += trades_added

            # Rate limit - wait 2 seconds between requests
            await asyncio.sleep(2)

        print()
        print("=" * 80)
        print("📊 BACKFILL SUMMARY")
        print("=" * 80)
        print(f"Whales processed: {len(solana_whales)}")
        print(f"Total trades added: {total_trades_added}")
        print()

        # Check database totals
        total_solana_trades = (
            db.query(Trade).filter(Trade.chain_id == "solana").count()
        )
        print(f"🎯 Total Solana trades in database: {total_solana_trades}")
        print()

        if total_trades_added > 0:
            print(
                "✅ SUCCESS: Solana whale data backfilled (prices need DexScreener enrichment)"
            )
        else:
            print("ℹ️  No new trades added (may already exist or no recent activity)")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(backfill_all_solana_whales())
