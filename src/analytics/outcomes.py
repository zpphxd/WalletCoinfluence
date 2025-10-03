"""Track alert outcomes to measure system performance."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.db.models import Alert, Token

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """Tracks alert outcomes for performance measurement."""

    def __init__(self, db: Session):
        """Initialize outcome tracker.

        Args:
            db: Database session
        """
        self.db = db

    async def track_alert_outcome(
        self,
        alert_id: int,
        hours_after: int = 24
    ) -> Dict[str, Any]:
        """Track outcome of an alert after specified hours.

        Args:
            alert_id: Alert ID to track
            hours_after: Hours after alert to check price

        Returns:
            Outcome data dict
        """
        # Get alert
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()

        if not alert:
            return {}

        # Get token at time of alert
        token = (
            self.db.query(Token)
            .filter(Token.token_address == alert.token_address)
            .first()
        )

        if not token:
            return {}

        # Get current/later price (would need price history table)
        # For now, we'll use current price as proxy
        price_at_alert = token.last_price_usd or 0
        current_price = token.last_price_usd or 0

        if price_at_alert > 0:
            price_change_pct = ((current_price - price_at_alert) / price_at_alert) * 100
        else:
            price_change_pct = 0

        return {
            "alert_id": alert_id,
            "token_address": alert.token_address,
            "chain_id": alert.chain_id,
            "alert_type": alert.type,
            "alert_ts": alert.ts,
            "price_at_alert": price_at_alert,
            "price_after": current_price,
            "price_change_pct": price_change_pct,
            "hours_tracked": hours_after,
            "was_profitable": price_change_pct > 0,
        }

    async def get_alert_performance_summary(
        self,
        hours_back: int = 24,
        min_price_change: float = 10.0
    ) -> Dict[str, Any]:
        """Get summary of alert performance.

        Args:
            hours_back: Hours to look back
            min_price_change: Minimum price change % to count as "win"

        Returns:
            Performance summary
        """
        since = datetime.utcnow() - timedelta(hours=hours_back)

        # Get alerts from period
        alerts = (
            self.db.query(Alert)
            .filter(Alert.ts >= since)
            .all()
        )

        total_alerts = len(alerts)
        if total_alerts == 0:
            return {
                "total_alerts": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "avg_return": 0,
            }

        wins = 0
        losses = 0
        total_return = 0

        for alert in alerts:
            outcome = await self.track_alert_outcome(alert.id, hours_after=1)

            if outcome:
                price_change = outcome.get("price_change_pct", 0)
                total_return += price_change

                if price_change >= min_price_change:
                    wins += 1
                elif price_change < 0:
                    losses += 1

        return {
            "total_alerts": total_alerts,
            "wins": wins,
            "losses": losses,
            "neutral": total_alerts - wins - losses,
            "win_rate": (wins / total_alerts * 100) if total_alerts > 0 else 0,
            "avg_return": total_return / total_alerts if total_alerts > 0 else 0,
            "period_hours": hours_back,
        }

    async def generate_daily_summary(self) -> str:
        """Generate daily performance summary message.

        Returns:
            Formatted summary string
        """
        summary = await self.get_alert_performance_summary(hours_back=24)

        message = f"""
📊 *Daily Alert Performance Summary*

🔔 Total Alerts: {summary['total_alerts']}
✅ Wins: {summary['wins']} ({summary['win_rate']:.1f}%)
❌ Losses: {summary['losses']}
➖ Neutral: {summary['neutral']}

📈 Avg Return: {summary['avg_return']:.1f}%

_Tracked over last 24 hours_
        """

        return message.strip()
