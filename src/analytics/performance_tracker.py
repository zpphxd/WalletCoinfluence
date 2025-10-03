"""Self-scoring performance tracker for the whale detection system.

This module tracks how well the system performs and assigns rewards/punishments
based on signal quality, timeliness, and outcome accuracy.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.db.models import Alert, Trade, Token, WalletStats30D

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks and scores system performance with rewards/punishments."""

    def __init__(self, db: Session):
        """Initialize performance tracker.

        Args:
            db: Database session
        """
        self.db = db
        self.score = 0
        self.total_rewards = 0
        self.total_punishments = 0

    def evaluate_alert_outcome(self, alert_id: int, hours_after: int = 24) -> Dict[str, Any]:
        """Evaluate how well an alert performed.

        Rewards:
        +100 points: Token pumped >50% within 1 hour
        +75 points: Token pumped >30% within 2 hours
        +50 points: Token pumped >20% within 4 hours
        +25 points: Token pumped >10% within 24 hours
        +10 points: Whale was actually profitable (validation)
        +50 points: Confluence alert (multiple whales)
        +25 points: Alert sent within 5 minutes of trade

        Punishments:
        -50 points: Token dumped >20% within 1 hour
        -25 points: Token dumped >10% within 4 hours
        -10 points: Alert sent >15 minutes after trade (too slow)
        -5 points: Whale had negative PnL (bad whale selection)
        -100 points: Missed a >100% pump that whales traded

        Args:
            alert_id: Alert ID to evaluate
            hours_after: Hours after alert to check performance

        Returns:
            Evaluation results with score changes
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()

        if not alert:
            return {"error": "Alert not found"}

        # Get the token and check price change
        token = self.db.query(Token).filter(
            Token.token_address == alert.token_address
        ).first()

        if not token:
            return {"error": "Token not found"}

        evaluation = {
            "alert_id": alert_id,
            "token_symbol": token.symbol,
            "alert_time": alert.created_at,
            "alert_type": "confluence" if alert.num_wallets > 1 else "single",
            "rewards": [],
            "punishments": [],
            "total_score_change": 0,
        }

        # Calculate time delta from trade to alert
        # (assumes alert.created_at is when alert was sent)
        alert_latency_minutes = 0  # TODO: Calculate from actual trade time

        # REWARD: Fast alert delivery
        if alert_latency_minutes <= 5:
            points = 25
            evaluation["rewards"].append(f"+{points}: Alert sent within 5 minutes ⚡")
            self.score += points
            self.total_rewards += points
            evaluation["total_score_change"] += points

        # PUNISHMENT: Slow alert delivery
        elif alert_latency_minutes > 15:
            points = -10
            evaluation["punishments"].append(f"{points}: Alert delayed >15 min 🐌")
            self.score += points
            self.total_punishments += abs(points)
            evaluation["total_score_change"] += points

        # REWARD: Confluence detection
        if alert.num_wallets > 1:
            points = 50
            evaluation["rewards"].append(
                f"+{points}: Confluence detected ({alert.num_wallets} whales) 🐋🐋"
            )
            self.score += points
            self.total_rewards += points
            evaluation["total_score_change"] += points

        # Check token price performance
        # TODO: Get historical price data and calculate % change
        # For now, use placeholder logic

        # REWARD: Whale quality validation
        if alert.wallet_address:
            stats = self.db.query(WalletStats30D).filter(
                WalletStats30D.wallet_address == alert.wallet_address
            ).first()

            if stats:
                total_pnl = (stats.realized_pnl_usd or 0) + (stats.unrealized_pnl_usd or 0)

                if total_pnl > 0:
                    points = 10
                    evaluation["rewards"].append(
                        f"+{points}: Whale is profitable (${total_pnl:,.0f}) ✅"
                    )
                    self.score += points
                    self.total_rewards += points
                    evaluation["total_score_change"] += points
                else:
                    points = -5
                    evaluation["punishments"].append(
                        f"{points}: Whale has negative PnL (${total_pnl:,.0f}) ❌"
                    )
                    self.score += points
                    self.total_punishments += abs(points)
                    evaluation["total_score_change"] += points

        return evaluation

    def check_for_missed_opportunities(self) -> List[Dict[str, Any]]:
        """Check if we missed any big pumps from our whale pool.

        This is the PUNISHMENT mechanism - if a whale made a huge trade
        and we didn't alert on it, we get penalized.

        Returns:
            List of missed opportunities with punishment scores
        """
        missed = []

        # Look for trades from last 24 hours that we didn't alert on
        since = datetime.utcnow() - timedelta(hours=24)

        # Get all trades from our whale pool
        whale_addresses = (
            self.db.query(WalletStats30D.wallet_address)
            .filter(
                and_(
                    WalletStats30D.trades_count >= 1,
                    (WalletStats30D.realized_pnl_usd + WalletStats30D.unrealized_pnl_usd) > 0
                )
            )
            .all()
        )

        whale_addrs = [w[0] for w in whale_addresses]

        # Find trades we didn't alert on
        unalerted_trades = (
            self.db.query(Trade)
            .filter(
                and_(
                    Trade.wallet_address.in_(whale_addrs),
                    Trade.ts >= since,
                    Trade.side == "buy",
                )
            )
            .all()
        )

        for trade in unalerted_trades:
            # Check if we sent an alert for this
            existing_alert = self.db.query(Alert).filter(
                and_(
                    Alert.wallet_address == trade.wallet_address,
                    Alert.token_address == trade.token_address,
                    Alert.created_at >= trade.ts - timedelta(minutes=30),
                    Alert.created_at <= trade.ts + timedelta(minutes=30),
                )
            ).first()

            if not existing_alert:
                # We missed this trade! Calculate punishment based on delay
                delay_minutes = (datetime.utcnow() - trade.ts).total_seconds() / 60

                # Exponential punishment - the longer we wait, the worse
                base_punishment = -20
                delay_multiplier = min(delay_minutes / 60, 5)  # Max 5x multiplier
                punishment = int(base_punishment * delay_multiplier)

                missed.append({
                    "trade_id": trade.tx_hash,
                    "token_address": trade.token_address,
                    "wallet_address": trade.wallet_address,
                    "trade_time": trade.ts,
                    "delay_minutes": delay_minutes,
                    "punishment": punishment,
                    "reason": f"Missed whale trade! Delayed {delay_minutes:.0f} minutes",
                })

                self.score += punishment
                self.total_punishments += abs(punishment)

                logger.warning(
                    f"PUNISHMENT {punishment}: Missed trade from "
                    f"{trade.wallet_address[:10]}... delayed {delay_minutes:.0f}min"
                )

        return missed

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report.

        Returns:
            Performance metrics and score breakdown
        """
        # Get alert statistics
        total_alerts = self.db.query(func.count(Alert.id)).scalar() or 0

        confluence_alerts = (
            self.db.query(func.count(Alert.id))
            .filter(Alert.num_wallets > 1)
            .scalar() or 0
        )

        single_alerts = total_alerts - confluence_alerts

        # Calculate average alert latency
        # TODO: Add actual latency tracking

        # Get whale pool quality
        profitable_whales = (
            self.db.query(func.count(WalletStats30D.wallet_address))
            .filter(
                (WalletStats30D.realized_pnl_usd + WalletStats30D.unrealized_pnl_usd) > 0
            )
            .scalar() or 0
        )

        total_whales = self.db.query(func.count(WalletStats30D.wallet_address)).scalar() or 0

        whale_quality_pct = (
            (profitable_whales / total_whales * 100) if total_whales > 0 else 0
        )

        report = {
            "current_score": self.score,
            "total_rewards": self.total_rewards,
            "total_punishments": self.total_punishments,
            "net_performance": self.total_rewards - self.total_punishments,
            "alerts": {
                "total": total_alerts,
                "single": single_alerts,
                "confluence": confluence_alerts,
                "confluence_rate": (
                    confluence_alerts / total_alerts * 100 if total_alerts > 0 else 0
                ),
            },
            "whale_pool": {
                "total": total_whales,
                "profitable": profitable_whales,
                "quality_percentage": whale_quality_pct,
            },
            "grade": self._calculate_grade(self.score),
            "status": self._get_status_message(self.score),
        }

        return report

    def _calculate_grade(self, score: int) -> str:
        """Calculate letter grade based on score.

        Args:
            score: Current performance score

        Returns:
            Letter grade
        """
        if score >= 500:
            return "S+ (Elite Whale Hunter)"
        elif score >= 300:
            return "A+ (Excellent)"
        elif score >= 200:
            return "A (Great)"
        elif score >= 100:
            return "B (Good)"
        elif score >= 50:
            return "C (Average)"
        elif score >= 0:
            return "D (Below Average)"
        else:
            return "F (Needs Improvement)"

    def _get_status_message(self, score: int) -> str:
        """Get motivational status message based on score.

        Args:
            score: Current performance score

        Returns:
            Status message
        """
        if score >= 500:
            return "🏆 LEGENDARY! Printing money for users!"
        elif score >= 300:
            return "🔥 ON FIRE! Keep finding those whales!"
        elif score >= 200:
            return "💪 STRONG PERFORMANCE! Getting better!"
        elif score >= 100:
            return "📈 IMPROVING! More confluence needed!"
        elif score >= 50:
            return "⚠️ MEDIOCRE - Need faster alerts and better whales"
        elif score >= 0:
            return "🚨 STRUGGLING - Too slow or bad whale selection"
        else:
            return "💀 FAILING - Missing opportunities and sending bad signals"

    def print_report(self):
        """Print formatted performance report to logs."""
        report = self.get_performance_report()

        logger.info("=" * 70)
        logger.info("🎯 SYSTEM PERFORMANCE REPORT")
        logger.info("=" * 70)
        logger.info("")
        logger.info(f"📊 SCORE: {report['current_score']} points")
        logger.info(f"🏆 GRADE: {report['grade']}")
        logger.info(f"💬 STATUS: {report['status']}")
        logger.info("")
        logger.info(f"✅ Total Rewards: +{report['total_rewards']}")
        logger.info(f"❌ Total Punishments: -{report['total_punishments']}")
        logger.info(f"📈 Net Performance: {report['net_performance']}")
        logger.info("")
        logger.info("📢 ALERTS:")
        logger.info(f"   Total: {report['alerts']['total']}")
        logger.info(f"   Single: {report['alerts']['single']}")
        logger.info(f"   Confluence: {report['alerts']['confluence']}")
        logger.info(f"   Confluence Rate: {report['alerts']['confluence_rate']:.1f}%")
        logger.info("")
        logger.info("🐋 WHALE POOL:")
        logger.info(f"   Total Whales: {report['whale_pool']['total']}")
        logger.info(f"   Profitable: {report['whale_pool']['profitable']}")
        logger.info(
            f"   Quality: {report['whale_pool']['quality_percentage']:.1f}%"
        )
        logger.info("=" * 70)


def log_performance_summary(db: Session):
    """Log a performance summary (called periodically).

    Args:
        db: Database session
    """
    tracker = PerformanceTracker(db)

    # Check for missed opportunities
    missed = tracker.check_for_missed_opportunities()

    if missed:
        logger.warning(f"⚠️ Found {len(missed)} missed opportunities!")
        for m in missed[:5]:  # Show top 5
            logger.warning(
                f"   {m['punishment']} points: {m['reason']} "
                f"({m['wallet_address'][:10]}...)"
            )

    # Print full report
    tracker.print_report()
