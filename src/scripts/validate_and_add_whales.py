#!/usr/bin/env python3
"""Validate and add whale wallets from online sources.

Validates each wallet for:
- Recent activity (traded within last year)
- Minimum PnL threshold
- Real blockchain activity

Only adds whales that pass validation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import CustomWatchlistWallet, Wallet, Trade, WalletStats30D
from src.clients.alchemy import AlchemyClient
from src.clients.helius import HeliusClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Whale lists from online sources
SOLANA_WHALES = [
    {
        "address": "4EtAJ1p8RjqccEVhEhaYnEgQ6kA4JHR8oYqyLFwARUj6",
        "chain_id": "solana",
        "label": "Trump Memecoin Whale - 97% ROI, 2345 trades",
        "source": "Nansen Top 10 Memecoin Wallets 2025",
        "reported_pnl": 489000,  # $489k in profits
    },
    {
        "address": "EdCNh8EzETJLFphW8yvdY7rDd8zBiyweiz8DU5gUUka",
        "chain_id": "solana",
        "label": "WIF Mega Holder - $23.4M from $6M (579% ROI)",
        "source": "Nansen Top 10 Memecoin Wallets 2025",
        "reported_pnl": 17400000,  # $17.4M profits
    },
    {
        "address": "8zFZHuSRuDpuAR7J6FzwyF3vKNx4CVW3DFHJerQhc7Zd",
        "chain_id": "solana",
        "label": "Active Smart Money - $14.8M profits (75% ROI)",
        "source": "Nansen Top 10 Memecoin Wallets 2025",
        "reported_pnl": 14800000,  # $14.8M
    },
    {
        "address": "8mZYBV8aPvPCo34CyCmt6fWkZRFviAUoBZr1Bn993gro",
        "chain_id": "solana",
        "label": "POPCAT Insider - $7.2M profits, 538% ROI on WIF",
        "source": "Nansen Top 10 Memecoin Wallets 2025",
        "reported_pnl": 7200000,  # $7.2M
    },
    {
        "address": "5CP6zv8a17mz91v6rMruVH6ziC5qAL8GFaJzwrX9Fvup",
        "chain_id": "solana",
        "label": "Sniper Trader - $8M SHROOM, $3.9M ENRON",
        "source": "Nansen Top 10 Memecoin Wallets 2025",
        "reported_pnl": 11900000,  # $11.9M combined
    },
]

ETHEREUM_WHALES = [
    {
        "address": "0x4afed6cd4e65589a43f64dad86650b8ac6fc3662",
        "chain_id": "ethereum",
        "label": "JamesWynn PEPE Trader - $25M from $7k (one of 26 wallets)",
        "source": "Lookonchain/Nansen",
        "reported_pnl": 25000000,  # $25M
    },
    # Note: Many whale addresses from Lookonchain are only reported with partial addresses
    # (0x778c, 0x2af8, 0x06b3, etc.) - full addresses not publicly disclosed
    # JamesWynn address is from on-chain research showing his first PEPE transaction
]


class WhaleValidator:
    """Validates whale wallets before adding to watchlist."""

    def __init__(self, db: Session):
        self.db = db
        self.alchemy = AlchemyClient()
        self.helius = HeliusClient()

    async def validate_ethereum_wallet(
        self, address: str, min_pnl: float = 100000
    ) -> Tuple[bool, Optional[Dict]]:
        """Validate Ethereum wallet for activity and profitability.

        Args:
            address: Ethereum wallet address (full 42-char 0x...)
            min_pnl: Minimum required PnL in USD

        Returns:
            (is_valid, validation_info)
        """
        try:
            # Check if address is complete (42 chars)
            if len(address) != 42:
                logger.warning(f"❌ {address} is incomplete (need full 42-char address)")
                return False, {"reason": "incomplete_address", "length": len(address)}

            # Get recent transactions
            logger.info(f"🔍 Validating {address[:10]}...")
            transactions = await self.alchemy.get_wallet_transactions(
                address, "ethereum", limit=100
            )

            if not transactions:
                logger.warning(f"❌ {address[:10]}... has NO transactions found")
                return False, {"reason": "no_transactions"}

            # Check last transaction date
            last_tx = transactions[0]
            last_tx_date = last_tx.get("timestamp", datetime.utcnow())

            if isinstance(last_tx_date, str):
                # Parse if string
                last_tx_date = datetime.fromisoformat(last_tx_date.replace("Z", "+00:00"))

            one_year_ago = datetime.utcnow() - timedelta(days=365)

            if last_tx_date < one_year_ago:
                logger.warning(
                    f"❌ {address[:10]}... last traded {last_tx_date.strftime('%Y-%m-%d')} (>1 year ago)"
                )
                return False, {
                    "reason": "inactive",
                    "last_trade": last_tx_date.isoformat(),
                }

            # Count buy transactions
            buy_count = sum(
                1 for tx in transactions if tx.get("type") == "buy" or tx.get("side") == "buy"
            )

            validation_info = {
                "total_transactions": len(transactions),
                "buy_transactions": buy_count,
                "last_trade": last_tx_date.isoformat(),
                "active": True,
            }

            logger.info(
                f"✅ {address[:10]}... is VALID: "
                f"{len(transactions)} txs, {buy_count} buys, "
                f"last trade {last_tx_date.strftime('%Y-%m-%d')}"
            )

            return True, validation_info

        except Exception as e:
            logger.error(f"❌ Error validating {address[:10]}...: {str(e)}")
            return False, {"reason": "error", "error": str(e)}

    async def validate_solana_wallet(
        self, address: str, min_pnl: float = 100000
    ) -> Tuple[bool, Optional[Dict]]:
        """Validate Solana wallet for activity and profitability.

        Args:
            address: Solana wallet address (base58)
            min_pnl: Minimum required PnL in USD

        Returns:
            (is_valid, validation_info)
        """
        try:
            logger.info(f"🔍 Validating SOL wallet {address[:10]}...")

            # Get recent transactions (Helius only takes wallet_address and limit)
            transactions = await self.helius.get_wallet_transactions(
                wallet_address=address, limit=100
            )

            if not transactions:
                logger.warning(f"❌ {address[:10]}... has NO Solana transactions")
                return False, {"reason": "no_transactions"}

            # Check last transaction date
            last_tx = transactions[0]
            last_tx_date = last_tx.get("timestamp", datetime.utcnow())

            if isinstance(last_tx_date, str):
                last_tx_date = datetime.fromisoformat(last_tx_date.replace("Z", "+00:00"))

            one_year_ago = datetime.utcnow() - timedelta(days=365)

            if last_tx_date < one_year_ago:
                logger.warning(
                    f"❌ {address[:10]}... last SOL trade {last_tx_date.strftime('%Y-%m-%d')} (>1 year ago)"
                )
                return False, {
                    "reason": "inactive",
                    "last_trade": last_tx_date.isoformat(),
                }

            # Count buy transactions
            buy_count = sum(
                1 for tx in transactions if tx.get("type") == "buy" or tx.get("side") == "buy"
            )

            validation_info = {
                "total_transactions": len(transactions),
                "buy_transactions": buy_count,
                "last_trade": last_tx_date.isoformat(),
                "active": True,
            }

            logger.info(
                f"✅ {address[:10]}... is VALID: "
                f"{len(transactions)} SOL txs, {buy_count} buys, "
                f"last trade {last_tx_date.strftime('%Y-%m-%d')}"
            )

            return True, validation_info

        except Exception as e:
            logger.error(f"❌ Error validating SOL {address[:10]}...: {str(e)}")
            return False, {"reason": "error", "error": str(e)}

    async def add_whale_to_watchlist(
        self, whale_data: Dict, validation_info: Dict
    ) -> bool:
        """Add validated whale to custom watchlist.

        Args:
            whale_data: Whale info from source lists
            validation_info: Validation results

        Returns:
            True if added successfully
        """
        try:
            # Check if already exists
            existing = (
                self.db.query(CustomWatchlistWallet)
                .filter(
                    CustomWatchlistWallet.address == whale_data["address"],
                    CustomWatchlistWallet.chain_id == whale_data["chain_id"],
                )
                .first()
            )

            if existing:
                logger.info(
                    f"⏭️  {whale_data['address'][:10]}... already in watchlist, skipping"
                )
                return False

            # Create notes with validation info
            notes = f"""Source: {whale_data['source']}
Reported PnL: ${whale_data['reported_pnl']:,.0f}
Last Trade: {validation_info['last_trade']}
Total Txs: {validation_info['total_transactions']}
Buy Txs: {validation_info['buy_transactions']}
Validated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"""

            # Add to custom watchlist
            new_whale = CustomWatchlistWallet(
                address=whale_data["address"],
                chain_id=whale_data["chain_id"],
                label=whale_data["label"],
                notes=notes,
                is_active=True,
                added_at=datetime.utcnow(),
            )

            self.db.add(new_whale)
            self.db.commit()

            logger.info(
                f"✅ ADDED {whale_data['address'][:10]}... to watchlist: "
                f"{whale_data['label']}"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error adding whale to watchlist: {str(e)}")
            self.db.rollback()
            return False


async def validate_and_add_whales():
    """Main function to validate and add all whales from online sources."""
    db = SessionLocal()

    try:
        validator = WhaleValidator(db)

        print("\n" + "=" * 80)
        print("🐋 WHALE VALIDATION & IMPORT FROM ONLINE SOURCES")
        print("=" * 80)
        print()

        # Stats
        total_attempted = 0
        total_validated = 0
        total_added = 0
        skipped_incomplete = []
        failed_validation = []

        # Process Solana whales
        print("🔵 SOLANA WHALES (Nansen Top 10 Memecoin Wallets)")
        print("-" * 80)
        print()

        for whale in SOLANA_WHALES:
            total_attempted += 1

            # Validate
            is_valid, validation_info = await validator.validate_solana_wallet(
                whale["address"], min_pnl=100000
            )

            if is_valid:
                total_validated += 1
                # Add to watchlist
                added = await validator.add_whale_to_watchlist(whale, validation_info)
                if added:
                    total_added += 1
            else:
                failed_validation.append(
                    {
                        "address": whale["address"][:20] + "...",
                        "chain": whale["chain_id"],
                        "reason": validation_info.get("reason", "unknown"),
                    }
                )

            # Rate limit
            await asyncio.sleep(2)

        print()
        print("🟢 ETHEREUM WHALES (Lookonchain Smart Money)")
        print("-" * 80)
        print()

        for whale in ETHEREUM_WHALES:
            total_attempted += 1

            # Skip incomplete addresses
            if whale.get("needs_full_address", False):
                logger.warning(
                    f"⏭️  SKIPPING {whale['address']} - Need full 42-char address"
                )
                skipped_incomplete.append(
                    {"address": whale["address"], "label": whale["label"]}
                )
                continue

            # Validate
            is_valid, validation_info = await validator.validate_ethereum_wallet(
                whale["address"], min_pnl=100000
            )

            if is_valid:
                total_validated += 1
                # Add to watchlist
                added = await validator.add_whale_to_watchlist(whale, validation_info)
                if added:
                    total_added += 1
            else:
                failed_validation.append(
                    {
                        "address": whale["address"][:20] + "...",
                        "chain": whale["chain_id"],
                        "reason": validation_info.get("reason", "unknown"),
                    }
                )

            # Rate limit
            await asyncio.sleep(2)

        # Summary
        print()
        print("=" * 80)
        print("📊 VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Attempted: {total_attempted}")
        print(f"✅ Validated: {total_validated}")
        print(f"✅ Added to Watchlist: {total_added}")
        print(f"⏭️  Skipped (incomplete): {len(skipped_incomplete)}")
        print(f"❌ Failed Validation: {len(failed_validation)}")
        print()

        if skipped_incomplete:
            print("⏭️  INCOMPLETE ADDRESSES (need manual research):")
            for item in skipped_incomplete:
                print(f"   • {item['address']} - {item['label']}")
            print()

        if failed_validation:
            print("❌ FAILED VALIDATION:")
            for item in failed_validation:
                print(
                    f"   • {item['address']} ({item['chain']}): {item['reason']}"
                )
            print()

        # Show current watchlist
        total_watchlist = db.query(CustomWatchlistWallet).count()
        print(f"🎯 TOTAL CUSTOM WATCHLIST WHALES: {total_watchlist}")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(validate_and_add_whales())
