"""Watchlist add/remove rules and maintenance."""

import logging
from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.db.models import Wallet, WalletStats30D
from src.config import settings

logger = logging.getLogger(__name__)


class WatchlistManager:
    """Manages watchlist wallet add/remove based on rules."""

    def __init__(self, db: Session):
        """Initialize watchlist manager.

        Args:
            db: Database session
        """
        self.db = db

    def evaluate_add_criteria(self, wallet_address: str, chain_id: str) -> bool:
        """Check if wallet meets criteria to be added to watchlist.

        Criteria:
        - Not flagged as bot
        - Min trades in last 30D
        - Min realized PnL in last 30D
        - Min best trade multiple

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier

        Returns:
            True if wallet should be added
        """
        # Check wallet exists and not bot
        wallet = (
            self.db.query(Wallet)
            .filter(Wallet.address == wallet_address)
            .first()
        )

        if not wallet or wallet.is_bot_flag:
            return False

        # Check stats
        stats = (
            self.db.query(WalletStats30D)
            .filter(
                and_(
                    WalletStats30D.wallet_address == wallet_address,
                    WalletStats30D.chain_id == chain_id,
                )
            )
            .first()
        )

        if not stats:
            return False

        # Apply thresholds
        meets_criteria = (
            stats.trades_count >= settings.add_min_trades_30d
            and stats.realized_pnl_usd >= settings.add_min_realized_pnl_30d_usd
            and (stats.best_trade_multiple or 0) >= settings.add_min_best_trade_multiple
        )

        logger.debug(
            f"Wallet {wallet_address[:8]}... evaluation: trades={stats.trades_count}, "
            f"pnl=${stats.realized_pnl_usd:.0f}, best={stats.best_trade_multiple:.1f}x, "
            f"meets_criteria={meets_criteria}"
        )

        return meets_criteria

    def evaluate_remove_criteria(self, wallet_address: str, chain_id: str) -> bool:
        """Check if wallet should be removed from watchlist.

        Removal criteria:
        - Negative 30D PnL
        - Max drawdown exceeds threshold
        - Too few trades (inactive)

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier

        Returns:
            True if wallet should be removed
        """
        stats = (
            self.db.query(WalletStats30D)
            .filter(
                and_(
                    WalletStats30D.wallet_address == wallet_address,
                    WalletStats30D.chain_id == chain_id,
                )
            )
            .first()
        )

        if not stats:
            return True  # Remove if no stats

        should_remove = (
            stats.realized_pnl_usd < settings.remove_if_realized_pnl_30d_lt
            or (stats.max_drawdown or 0) > settings.remove_if_max_drawdown_pct_gt
            or stats.trades_count < settings.remove_if_trades_30d_lt
        )

        if should_remove:
            logger.info(
                f"Removing wallet {wallet_address[:8]}...: "
                f"pnl=${stats.realized_pnl_usd:.0f}, "
                f"drawdown={stats.max_drawdown:.1f}%, "
                f"trades={stats.trades_count}"
            )

        return should_remove

    def add_wallets(self, candidate_wallets: List[Dict[str, str]]) -> int:
        """Evaluate and add qualifying wallets to watchlist.

        Args:
            candidate_wallets: List of dicts with 'address' and 'chain_id'

        Returns:
            Number of wallets added
        """
        added = 0

        for candidate in candidate_wallets:
            address = candidate["address"]
            chain = candidate["chain_id"]

            if self.evaluate_add_criteria(address, chain):
                # Wallet already exists in DB (from trade discovery)
                # Just log that it's now on watchlist
                logger.info(f"Added {address[:8]}... ({chain}) to watchlist")
                added += 1

        return added

    def remove_wallets(self, chain_id: str) -> int:
        """Remove wallets that no longer meet criteria.

        Args:
            chain_id: Chain to evaluate

        Returns:
            Number of wallets removed
        """
        # Get all wallets for chain
        wallets = (
            self.db.query(Wallet)
            .filter(
                and_(
                    Wallet.chain_id == chain_id,
                    Wallet.is_bot_flag == False,
                )
            )
            .all()
        )

        removed = 0

        for wallet in wallets:
            if self.evaluate_remove_criteria(wallet.address, chain_id):
                # Mark as removed (could add a watchlist table, but for MVP just flag)
                # For now, we won't actually delete, just log
                logger.info(f"Would remove {wallet.address[:8]}... from watchlist")
                removed += 1

        return removed

    def run_nightly_maintenance(self) -> Dict[str, int]:
        """Run nightly watchlist maintenance across all chains.

        Returns:
            Dict with stats
        """
        logger.info("Starting nightly watchlist maintenance")

        stats = {
            "total_added": 0,
            "total_removed": 0,
        }

        for chain in settings.chain_list:
            # For each chain, evaluate all wallets with stats
            wallet_stats = (
                self.db.query(WalletStats30D)
                .filter(WalletStats30D.chain_id == chain)
                .all()
            )

            candidates = [
                {"address": ws.wallet_address, "chain_id": chain}
                for ws in wallet_stats
            ]

            added = self.add_wallets(candidates)
            removed = self.remove_wallets(chain)

            stats["total_added"] += added
            stats["total_removed"] += removed

            logger.info(
                f"Chain {chain}: added={added}, removed={removed}"
            )

        logger.info(
            f"Nightly maintenance complete: "
            f"added={stats['total_added']}, removed={stats['total_removed']}"
        )

        return stats
