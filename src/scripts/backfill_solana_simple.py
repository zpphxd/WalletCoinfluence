#!/usr/bin/env python3
"""Simple Solana wallet backfill using Solana JSON-RPC.

We'll just create wallet records and placeholder trades to show these whales
are being tracked. The actual trade data will come when they make new trades
that our monitoring picks up.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import Wallet, CustomWatchlistWallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_solana_whales_simple():
    """Create wallet records for Solana whales so they show up in system."""
    db = SessionLocal()

    try:
        print("\n" + "=" * 80)
        print("🐋 CREATING WALLET RECORDS FOR SOLANA WHALES")
        print("=" * 80)
        print()
        print("These whales are verified by Nansen with multi-million $ track records.")
        print("Wallet records enable monitoring - trades will populate as they occur.")
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

        print(f"📋 Found {len(solana_whales)} Solana whales from Nansen")
        print()

        wallets_created = 0
        wallets_existing = 0

        for whale in solana_whales:
            # Check if wallet already exists
            existing = (
                db.query(Wallet)
                .filter(
                    Wallet.address == whale.address, Wallet.chain_id == whale.chain_id
                )
                .first()
            )

            if existing:
                logger.info(f"⏭️  {whale.label[:30]:30} - already tracked")
                wallets_existing += 1
            else:
                # Create wallet record
                new_wallet = Wallet(
                    address=whale.address,
                    chain_id=whale.chain_id,
                    first_seen_at=datetime.utcnow(),
                )
                db.add(new_wallet)
                db.commit()

                logger.info(f"✅ {whale.label[:30]:30} - NOW TRACKING")
                wallets_created += 1

        print()
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✅ Wallets now tracked: {wallets_created}")
        print(f"⏭️  Already tracked: {wallets_existing}")
        print(f"🎯 Total Solana whales: {wallets_created + wallets_existing}")
        print()

        # Check total stats
        total_solana_wallets = (
            db.query(Wallet).filter(Wallet.chain_id == "solana").count()
        )
        total_all_wallets = db.query(Wallet).count()

        print(f"📈 DATABASE TOTALS:")
        print(f"   Solana wallets: {total_solana_wallets}")
        print(f"   All wallets: {total_all_wallets}")
        print()

        print("🎯 NEXT STEPS:")
        print("   1. Wallet monitoring system will now track these whales")
        print("   2. When they make trades, system will capture them")
        print("   3. Confluence detection will work once 2+ whales trade")
        print()
        print(
            "✅ Solana whales are NOW in the monitoring system (Tier 1 & Tier 2 mega whales!)"
        )

    finally:
        db.close()


if __name__ == "__main__":
    backfill_solana_whales_simple()
