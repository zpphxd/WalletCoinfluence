#!/usr/bin/env python3
"""Add verified whale wallets from trusted sources (Nansen, Lookonchain).

These whales have been verified by reputable on-chain analytics platforms.
We're adding them based on their reported performance metrics.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import CustomWatchlistWallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Verified whales from Nansen's "Top 10 Memecoin Wallets to Track for 2025"
# Published: 2025, Source: https://www.nansen.ai/post/top-10-memecoin-wallets-to-track-for-2025
VERIFIED_WHALES = [
    # SOLANA WHALES - Nansen Top 10
    {
        "address": "4EtAJ1p8RjqccEVhEhaYnEgQ6kA4JHR8oYqyLFwARUj6",
        "chain_id": "solana",
        "label": "Trump Memecoin Whale",
        "notes": """✅ VERIFIED BY NANSEN (Top 10 Memecoin Wallets 2025)

Performance:
- 97% average ROI
- 2,345 total trades
- $260k profit on ARC
- $229k profit on MELANIA
- Combined: ~$489k+ in profits

Trading Style: High-volume political memecoin trader
Source: Nansen "Top 10 Memecoin Wallets to Track for 2025"
Added: {}""".format(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
    },
    {
        "address": "EdCNh8EzETJLFphW8yvdY7rDd8zBiyweiz8DU5gUUka",
        "chain_id": "solana",
        "label": "WIF Mega Holder",
        "notes": """✅ VERIFIED BY NANSEN (Top 10 Memecoin Wallets 2025)

Performance:
- Turned $6M into $23.4M
- 579% ROI
- Major Dogwifhat (WIF) position

Trading Style: Large position holder, swing trader
Source: Nansen "Top 10 Memecoin Wallets to Track for 2025"
Added: {}""".format(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
    },
    {
        "address": "8zFZHuSRuDpuAR7J6FzwyF3vKNx4CVW3DFHJerQhc7Zd",
        "chain_id": "solana",
        "label": "Active Smart Money Trader",
        "notes": """✅ VERIFIED BY NANSEN (Top 10 Memecoin Wallets 2025)

Performance:
- Turned $31.2M into $34.5M
- $14.8M in profits
- 75% ROI

Trading Style: High-capital active trader
Source: Nansen "Top 10 Memecoin Wallets to Track for 2025"
Added: {}""".format(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
    },
    {
        "address": "8mZYBV8aPvPCo34CyCmt6fWkZRFviAUoBZr1Bn993gro",
        "chain_id": "solana",
        "label": "POPCAT Insider",
        "notes": """✅ VERIFIED BY NANSEN (Top 10 Memecoin Wallets 2025)

Performance:
- $7.2M in profits
- 538% ROI on Dogwifhat (WIF)
- POPCAT insider position

Trading Style: Early-stage insider positions
Source: Nansen "Top 10 Memecoin Wallets to Track for 2025"
Added: {}""".format(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
    },
    {
        "address": "5CP6zv8a17mz91v6rMruVH6ziC5qAL8GFaJzwrX9Fvup",
        "chain_id": "solana",
        "label": "Sniper Trader",
        "notes": """✅ VERIFIED BY NANSEN (Top 10 Memecoin Wallets 2025)

Performance:
- $8M profit on SHROOM
- $3.9M profit on ENRON
- $1M profit on HAWK
- Combined: ~$12M+ in profits

Trading Style: Fast sniper, early entries
Source: Nansen "Top 10 Memecoin Wallets to Track for 2025"
Added: {}""".format(datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')),
    },
]


def add_verified_whales():
    """Add verified whales to custom watchlist."""
    db = SessionLocal()

    try:
        print("\n" + "=" * 80)
        print("🐋 ADDING VERIFIED WHALES FROM NANSEN")
        print("=" * 80)
        print()
        print("Source: Nansen 'Top 10 Memecoin Wallets to Track for 2025'")
        print("These whales have multi-million dollar verified track records.")
        print()

        added_count = 0
        skipped_count = 0

        for whale in VERIFIED_WHALES:
            # Check if already exists
            existing = (
                db.query(CustomWatchlistWallet)
                .filter(
                    CustomWatchlistWallet.address == whale["address"],
                    CustomWatchlistWallet.chain_id == whale["chain_id"],
                )
                .first()
            )

            if existing:
                logger.info(f"⏭️  {whale['address'][:16]}... already exists, skipping")
                skipped_count += 1
                continue

            # Add new whale
            new_whale = CustomWatchlistWallet(
                address=whale["address"],
                chain_id=whale["chain_id"],
                label=whale["label"],
                notes=whale["notes"],
                is_active=True,
                added_at=datetime.utcnow(),
            )

            db.add(new_whale)
            db.commit()

            logger.info(f"✅ ADDED: {whale['label']} ({whale['address'][:16]}...)")
            added_count += 1

        print()
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✅ Added: {added_count} new whales")
        print(f"⏭️  Skipped (already exist): {skipped_count}")
        print()

        # Show total watchlist
        total = db.query(CustomWatchlistWallet).count()
        print(f"🎯 TOTAL CUSTOM WATCHLIST WHALES: {total}")
        print()

        # Show all whales
        if total > 0:
            print("📋 CURRENT WATCHLIST:")
            print()
            whales = db.query(CustomWatchlistWallet).all()
            for w in whales:
                print(f"  • {w.label}")
                print(f"    {w.address[:20]}... ({w.chain_id})")
                print(f"    Added: {w.added_at.strftime('%Y-%m-%d %H:%M UTC')}")
                print()

    except Exception as e:
        logger.error(f"Error adding whales: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    add_verified_whales()
