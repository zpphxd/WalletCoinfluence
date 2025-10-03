"""Being-Early score calculation."""

import logging
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from src.db.models import Trade, Token

logger = logging.getLogger(__name__)


class EarlyScoreCalculator:
    """Calculate Being-Early score for wallet-token pairs."""

    def __init__(self, db: Session):
        """Initialize calculator.

        Args:
            db: Database session
        """
        self.db = db

    def calculate_score(
        self, wallet_address: str, token_address: str, trade_ts: datetime
    ) -> float:
        """Calculate Being-Early score (0-100) for a specific trade.

        EarlyScore = 40 × (1 - rank_percentile)           # Earlier rank = higher
                   + 40 × clip((1M - mc_at_buy) / 1M)    # Lower MC = higher
                   + 20 × volume_participation            # Larger buy = higher

        Args:
            wallet_address: Wallet address
            token_address: Token address
            trade_ts: Timestamp of the buy trade

        Returns:
            Score between 0-100
        """
        # Component 1: Buy rank percentile (40 points)
        rank_score = self._calculate_rank_score(token_address, trade_ts)

        # Component 2: Market cap at buy (40 points)
        mc_score = self._calculate_mc_score(token_address, trade_ts)

        # Component 3: Volume participation (20 points)
        vol_score = self._calculate_volume_score(wallet_address, token_address, trade_ts)

        total_score = rank_score + mc_score + vol_score

        logger.debug(
            f"EarlyScore for {wallet_address[:8]}.../{token_address[:8]}...: "
            f"rank={rank_score:.1f}, mc={mc_score:.1f}, vol={vol_score:.1f}, "
            f"total={total_score:.1f}"
        )

        return max(0.0, min(100.0, total_score))

    def _calculate_rank_score(self, token_address: str, trade_ts: datetime) -> float:
        """Calculate rank-based score.

        Args:
            token_address: Token address
            trade_ts: Trade timestamp

        Returns:
            Score 0-40 based on buyer rank
        """
        # Count how many unique buyers bought before this trade
        buyers_before = (
            self.db.query(func.count(func.distinct(Trade.wallet_address)))
            .filter(
                and_(
                    Trade.token_address == token_address,
                    Trade.side == "buy",
                    Trade.ts < trade_ts,
                )
            )
            .scalar()
            or 0
        )

        # Total unique buyers
        total_buyers = (
            self.db.query(func.count(func.distinct(Trade.wallet_address)))
            .filter(and_(Trade.token_address == token_address, Trade.side == "buy"))
            .scalar()
            or 1
        )

        # Rank percentile (0 = first, 1 = last)
        rank_percentile = buyers_before / max(total_buyers, 1)

        # Invert so earlier = higher score
        score = 40.0 * (1.0 - rank_percentile)

        return score

    def _calculate_mc_score(self, token_address: str, trade_ts: datetime) -> float:
        """Calculate market cap score.

        Uses liquidity as proxy for market cap.
        Assumption: MC ≈ liquidity × 3 for most DEX tokens.

        Args:
            token_address: Token address
            trade_ts: Trade timestamp

        Returns:
            Score 0-40 based on market cap at buy
        """
        # Get liquidity at time of trade (or closest available)
        token = self.db.query(Token).filter(Token.token_address == token_address).first()

        if not token or not token.liquidity_usd:
            # No data, assume neutral score
            return 20.0

        # Estimate market cap (liquidity × 3)
        estimated_mc = token.liquidity_usd * 3

        # Target: $1M market cap
        target_mc = 1_000_000

        if estimated_mc >= target_mc:
            # Already above target, low score
            return 0.0

        # Linear scale: lower MC = higher score
        proportion = max(0.0, (target_mc - estimated_mc) / target_mc)
        score = 40.0 * proportion

        return score

    def _calculate_volume_score(
        self, wallet_address: str, token_address: str, trade_ts: datetime
    ) -> float:
        """Calculate volume participation score.

        Args:
            wallet_address: Wallet address
            token_address: Token address
            trade_ts: Trade timestamp

        Returns:
            Score 0-20 based on buy size relative to token volume
        """
        # Get this wallet's buy
        wallet_buy = (
            self.db.query(Trade)
            .filter(
                and_(
                    Trade.wallet_address == wallet_address,
                    Trade.token_address == token_address,
                    Trade.ts == trade_ts,
                    Trade.side == "buy",
                )
            )
            .first()
        )

        if not wallet_buy:
            return 0.0

        # Get total volume around this time (±1 hour window)
        from datetime import timedelta

        window_start = trade_ts - timedelta(hours=1)
        window_end = trade_ts + timedelta(hours=1)

        total_volume = (
            self.db.query(func.sum(Trade.usd_value))
            .filter(
                and_(
                    Trade.token_address == token_address,
                    Trade.ts >= window_start,
                    Trade.ts <= window_end,
                )
            )
            .scalar()
            or 0.0
        )

        if total_volume == 0:
            return 0.0

        # Participation percentage
        participation = wallet_buy.usd_value / total_volume

        # Cap at 50% participation (whales get max 10 points from this component)
        capped_participation = min(participation, 0.5)

        # Scale to 0-20
        score = 20.0 * (capped_participation / 0.5)

        return score

    def calculate_median_score(self, wallet_address: str, days: int = 30) -> Optional[float]:
        """Calculate median Being-Early score for a wallet.

        Args:
            wallet_address: Wallet address
            days: Days to look back

        Returns:
            Median EarlyScore or None if no trades
        """
        from datetime import timedelta
        import statistics

        since = datetime.utcnow() - timedelta(days=days)

        # Get all buy trades
        buy_trades = (
            self.db.query(Trade)
            .filter(
                and_(
                    Trade.wallet_address == wallet_address,
                    Trade.side == "buy",
                    Trade.ts >= since,
                )
            )
            .all()
        )

        if not buy_trades:
            return None

        # Calculate score for each trade
        scores = []
        for trade in buy_trades:
            score = self.calculate_score(
                wallet_address, trade.token_address, trade.ts
            )
            scores.append(score)

        return statistics.median(scores) if scores else None
