"""Adaptive whale scoring system that learns from signal performance."""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from src.db.models import Wallet, WalletStats30D, Alert, Trade

logger = logging.getLogger(__name__)


class AdaptiveWhaleScorer:
    """Dynamically scores whales and adjusts criteria based on actual performance."""

    def __init__(self, db: Session):
        """Initialize adaptive scorer.

        Args:
            db: Database session
        """
        self.db = db

    def calculate_composite_score(
        self,
        wallet_address: str,
        chain_id: str,
        weights: Dict[str, float] = None
    ) -> float:
        """Calculate composite whale score with adaptive weights.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier
            weights: Optional custom weights (defaults to learned weights)

        Returns:
            Score from 0-100
        """
        if weights is None:
            weights = self._get_learned_weights()

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
            return 0.0

        # Get percentile ranks
        pnl_rank = self._get_percentile_rank(
            stats.realized_pnl_usd + stats.unrealized_pnl_usd,
            "total_pnl",
            chain_id
        )
        activity_rank = self._get_percentile_rank(
            stats.trades_count,
            "trades_count",
            chain_id
        )
        early_rank = self._get_percentile_rank(
            stats.earlyscore_median or 0,
            "earlyscore_median",
            chain_id
        )

        # Weighted composite score
        composite = (
            weights["pnl"] * pnl_rank +
            weights["activity"] * activity_rank +
            weights["early"] * early_rank
        )

        return composite

    def rank_all_whales(self, chain_id: str, top_n: int = 30) -> List[Dict]:
        """Rank all discovered wallets and return top N.

        Args:
            chain_id: Chain to rank
            top_n: Number of top wallets to return

        Returns:
            List of wallet dicts with scores
        """
        all_stats = (
            self.db.query(WalletStats30D)
            .filter(WalletStats30D.chain_id == chain_id)
            .all()
        )

        scored_wallets = []

        for stats in all_stats:
            score = self.calculate_composite_score(stats.wallet_address, chain_id)

            if score > 0:  # Only include wallets with valid scores
                scored_wallets.append({
                    "address": stats.wallet_address,
                    "chain_id": chain_id,
                    "composite_score": score,
                    "total_pnl": stats.realized_pnl_usd + stats.unrealized_pnl_usd,
                    "trades_count": stats.trades_count,
                    "earlyscore": stats.earlyscore_median,
                    "best_multiple": stats.best_trade_multiple,
                })

        # Sort by composite score descending
        scored_wallets.sort(key=lambda x: x["composite_score"], reverse=True)

        return scored_wallets[:top_n]

    def evaluate_signal_performance(self, days_back: int = 7) -> Dict[str, float]:
        """Measure actual performance of recent alerts to learn what works.

        Args:
            days_back: How many days of alerts to analyze

        Returns:
            Performance metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        # Get recent alerts
        alerts = (
            self.db.query(Alert)
            .filter(Alert.ts >= cutoff)
            .all()
        )

        if not alerts:
            return {
                "win_rate": 0.0,
                "avg_return": 0.0,
                "sample_size": 0,
            }

        wins = 0
        total_return = 0.0

        for alert in alerts:
            # Check if token pumped after alert
            # For now, simplified - in production would check actual price changes
            performance = self._measure_alert_outcome(alert)

            if performance["pumped"]:
                wins += 1
            total_return += performance["return_pct"]

        return {
            "win_rate": wins / len(alerts) if alerts else 0.0,
            "avg_return": total_return / len(alerts) if alerts else 0.0,
            "sample_size": len(alerts),
        }

    def adjust_weights_from_performance(self) -> Dict[str, float]:
        """Learn optimal weights from historical signal performance.

        Returns:
            Updated weight dict
        """
        # Get performance metrics
        perf = self.evaluate_signal_performance(days_back=7)

        # Default weights
        weights = {
            "pnl": 0.30,
            "activity": 0.30,
            "early": 0.40,
        }

        # Adaptive adjustments based on win rate
        if perf["sample_size"] >= 10:  # Need minimum sample
            if perf["win_rate"] < 0.5:
                # Low win rate - increase EarlyScore weight (timing matters more)
                weights["early"] = 0.50
                weights["pnl"] = 0.25
                weights["activity"] = 0.25
            elif perf["win_rate"] > 0.7:
                # High win rate - increase PnL weight (following proven winners)
                weights["pnl"] = 0.40
                weights["early"] = 0.35
                weights["activity"] = 0.25

        logger.info(
            f"Adjusted weights based on {perf['sample_size']} alerts: "
            f"win_rate={perf['win_rate']:.1%}, weights={weights}"
        )

        return weights

    def should_remove_whale(
        self,
        wallet_address: str,
        chain_id: str,
        lookback_days: int = 30
    ) -> Tuple[bool, str]:
        """Determine if whale should be removed based on recent performance.

        Args:
            wallet_address: Wallet to evaluate
            chain_id: Chain identifier
            lookback_days: Days to look back for performance

        Returns:
            (should_remove, reason)
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
            return True, "No stats available"

        # Removal criteria (adaptive thresholds)

        # 1. Negative PnL (losing money)
        total_pnl = stats.realized_pnl_usd + stats.unrealized_pnl_usd
        if total_pnl < -5000:
            return True, f"Negative PnL: ${total_pnl:,.0f}"

        # 2. Inactive (no trades recently)
        if stats.trades_count == 0:
            return True, "Inactive: 0 trades in 30d"

        # 3. Consistently bad timing (low EarlyScore)
        if stats.earlyscore_median and stats.earlyscore_median < 20:
            return True, f"Poor timing: EarlyScore {stats.earlyscore_median:.0f}"

        # 4. No big wins (best trade < 2x)
        if stats.best_trade_multiple and stats.best_trade_multiple < 2.0:
            return True, f"No big wins: best only {stats.best_trade_multiple:.1f}x"

        # 5. Declining performance (compare last 7d to full 30d)
        recent_performance = self._get_recent_performance(wallet_address, chain_id, days=7)
        if recent_performance["trend"] == "declining":
            return True, "Performance declining (last 7d worse than 30d avg)"

        return False, "Meets criteria"

    def _get_percentile_rank(
        self,
        value: float,
        metric: str,
        chain_id: str
    ) -> float:
        """Get percentile rank for a metric value.

        Args:
            value: Metric value
            metric: Metric name
            chain_id: Chain identifier

        Returns:
            Percentile rank (0-100)
        """
        # Get all values for this metric
        if metric == "total_pnl":
            all_stats = self.db.query(WalletStats30D).filter(
                WalletStats30D.chain_id == chain_id
            ).all()
            all_values = [
                s.realized_pnl_usd + s.unrealized_pnl_usd
                for s in all_stats
            ]
        elif metric == "trades_count":
            all_values = [
                s.trades_count
                for s in self.db.query(WalletStats30D).filter(
                    WalletStats30D.chain_id == chain_id
                ).all()
            ]
        elif metric == "earlyscore_median":
            all_values = [
                s.earlyscore_median or 0
                for s in self.db.query(WalletStats30D).filter(
                    WalletStats30D.chain_id == chain_id
                ).all()
            ]
        else:
            return 50.0  # Default to median

        if not all_values:
            return 50.0

        # Calculate percentile
        sorted_values = sorted(all_values)
        rank = sum(1 for v in sorted_values if v <= value)
        percentile = (rank / len(sorted_values)) * 100

        return percentile

    def _get_learned_weights(self) -> Dict[str, float]:
        """Get currently learned optimal weights.

        Returns:
            Weight dict
        """
        # In production, would load from database/cache
        # For now, use adaptive adjustment
        return self.adjust_weights_from_performance()

    def _measure_alert_outcome(self, alert: Alert) -> Dict[str, any]:
        """Measure what happened after an alert was sent.

        Args:
            alert: Alert record

        Returns:
            Outcome dict with pumped flag and return pct
        """
        # TODO: Integrate with price data to measure actual outcomes
        # For MVP, simplified logic:

        # Check if token had volume spike after alert
        # Check if price increased 10%+ within 24h
        # For now, return placeholder

        return {
            "pumped": False,  # Would check actual price data
            "return_pct": 0.0,  # Would calculate actual return
            "time_to_pump_minutes": 0,
        }

    def _get_recent_performance(
        self,
        wallet_address: str,
        chain_id: str,
        days: int = 7
    ) -> Dict[str, any]:
        """Get wallet's recent performance trend.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier
            days: Recent period to analyze

        Returns:
            Performance trend dict
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get recent trades
        recent_trades = (
            self.db.query(Trade)
            .filter(
                and_(
                    Trade.wallet_address == wallet_address,
                    Trade.chain_id == chain_id,
                    Trade.ts >= cutoff,
                )
            )
            .all()
        )

        if not recent_trades:
            return {"trend": "neutral", "recent_pnl": 0}

        # Calculate recent PnL (simplified)
        recent_buys = sum(
            t.usd_value for t in recent_trades if t.side == "buy"
        )
        recent_sells = sum(
            t.usd_value for t in recent_trades if t.side == "sell"
        )

        recent_pnl = recent_sells - recent_buys

        # Get 30d stats for comparison
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

        if stats:
            avg_pnl = stats.realized_pnl_usd / 30 * days  # Proportional

            if recent_pnl < avg_pnl * 0.5:
                trend = "declining"
            elif recent_pnl > avg_pnl * 1.5:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "neutral"

        return {
            "trend": trend,
            "recent_pnl": recent_pnl,
        }
