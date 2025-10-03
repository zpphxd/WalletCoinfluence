"""Bot detection heuristics."""

import logging
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from src.db.models import Trade, Wallet

logger = logging.getLogger(__name__)


class BotFilter:
    """Detect and flag bot wallets using heuristics."""

    def __init__(self, db: Session):
        """Initialize bot filter.

        Args:
            db: Database session
        """
        self.db = db

    def is_bot(self, wallet_address: str, chain_id: str) -> bool:
        """Check if wallet exhibits bot-like behavior.

        Heuristics:
        1. Extremely short average hold times (< 60 seconds)
        2. High same-block trade frequency
        3. Many tokens with single buy-sell pairs
        4. Known MEV addresses (future)

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier

        Returns:
            True if likely a bot
        """
        # Check wallet record
        wallet = (
            self.db.query(Wallet)
            .filter(Wallet.address == wallet_address)
            .first()
        )

        if wallet and wallet.is_contract:
            logger.debug(f"{wallet_address[:8]}... is a contract")
            return True

        # Analyze recent trades (last 30 days)
        since = datetime.utcnow() - timedelta(days=30)

        trades = (
            self.db.query(Trade)
            .filter(
                and_(
                    Trade.wallet_address == wallet_address,
                    Trade.chain_id == chain_id,
                    Trade.ts >= since,
                )
            )
            .order_by(Trade.ts.asc())
            .all()
        )

        if len(trades) < 10:
            # Not enough data
            return False

        # Heuristic 1: Average hold time
        avg_hold = self._calculate_avg_hold_time(trades)
        if avg_hold and avg_hold < 60:  # Less than 60 seconds
            logger.info(f"{wallet_address[:8]}... flagged: avg hold {avg_hold:.0f}s")
            return True

        # Heuristic 2: Same-block flip ratio
        same_block_ratio = self._calculate_same_block_ratio(trades)
        if same_block_ratio > 0.5:  # More than 50% same-block
            logger.info(
                f"{wallet_address[:8]}... flagged: {same_block_ratio:.1%} same-block trades"
            )
            return True

        # Heuristic 3: Single buy-sell token ratio
        single_flip_ratio = self._calculate_single_flip_ratio(trades)
        if single_flip_ratio > 0.7:  # More than 70% tokens are single flips
            logger.info(
                f"{wallet_address[:8]}... flagged: {single_flip_ratio:.1%} single flips"
            )
            return True

        return False

    def _calculate_avg_hold_time(self, trades: List[Trade]) -> float:
        """Calculate average hold time in seconds.

        Args:
            trades: List of trades

        Returns:
            Average hold time in seconds
        """
        # Group by token
        from collections import defaultdict

        trades_by_token = defaultdict(list)
        for trade in trades:
            trades_by_token[trade.token_address].append(trade)

        hold_times = []

        for token_trades in trades_by_token.values():
            buys = [t for t in token_trades if t.side == "buy"]
            sells = [t for t in token_trades if t.side == "sell"]

            # Match chronologically
            for buy in buys:
                # Find next sell after this buy
                for sell in sells:
                    if sell.ts > buy.ts:
                        hold_time = (sell.ts - buy.ts).total_seconds()
                        hold_times.append(hold_time)
                        break

        if not hold_times:
            return 0

        return sum(hold_times) / len(hold_times)

    def _calculate_same_block_ratio(self, trades: List[Trade]) -> float:
        """Calculate ratio of trades that are in same block (or within 15s).

        Args:
            trades: List of trades

        Returns:
            Ratio 0-1
        """
        if len(trades) < 2:
            return 0.0

        same_block_count = 0

        # Sort by time
        sorted_trades = sorted(trades, key=lambda t: t.ts)

        for i in range(len(sorted_trades) - 1):
            time_diff = (sorted_trades[i + 1].ts - sorted_trades[i].ts).total_seconds()
            if time_diff < 15:  # Within 15 seconds
                same_block_count += 1

        return same_block_count / (len(trades) - 1)

    def _calculate_single_flip_ratio(self, trades: List[Trade]) -> float:
        """Calculate ratio of tokens that were bought once and sold once.

        Args:
            trades: List of trades

        Returns:
            Ratio 0-1
        """
        from collections import defaultdict

        trades_by_token = defaultdict(list)
        for trade in trades:
            trades_by_token[trade.token_address].append(trade)

        single_flip_count = 0
        total_tokens = len(trades_by_token)

        for token_trades in trades_by_token.values():
            buys = [t for t in token_trades if t.side == "buy"]
            sells = [t for t in token_trades if t.side == "sell"]

            if len(buys) == 1 and len(sells) == 1:
                single_flip_count += 1

        if total_tokens == 0:
            return 0.0

        return single_flip_count / total_tokens

    def flag_bots(self, chain_id: str) -> int:
        """Flag bot wallets for a given chain.

        Args:
            chain_id: Chain identifier

        Returns:
            Number of wallets flagged
        """
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

        flagged = 0

        for wallet in wallets:
            if self.is_bot(wallet.address, chain_id):
                wallet.is_bot_flag = True
                flagged += 1

        self.db.commit()
        logger.info(f"Flagged {flagged} bots on {chain_id}")

        return flagged
