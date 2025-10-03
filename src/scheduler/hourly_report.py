"""Hourly performance report via Telegram during learning phase."""

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.alerts.telegram import TelegramAlerter
from src.db.models import WalletStats30D, Trade

logger = logging.getLogger(__name__)


async def send_hourly_update():
    """Send hourly paper trading + whale pool update to Telegram."""
    db = SessionLocal()
    telegram = TelegramAlerter()

    try:
        # Load paper trading state
        import json
        import os

        paper_state = {
            "starting_balance": 1000.0,
            "current_balance": 1000.0,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "open_positions": 0,
        }

        if os.path.exists("paper_trading_log.json"):
            with open("paper_trading_log.json") as f:
                data = json.load(f)
                paper_state["current_balance"] = data.get("current_balance", 1000.0)
                paper_state["total_profit"] = data.get("total_profit", 0.0)
                paper_state["total_loss"] = data.get("total_loss", 0.0)
                paper_state["wins"] = data.get("win_count", 0)
                paper_state["losses"] = data.get("loss_count", 0)
                paper_state["total_trades"] = paper_state["wins"] + paper_state["losses"]
                paper_state["open_positions"] = len(data.get("positions", {}))

        # Calculate ROI
        roi = ((paper_state["current_balance"] - paper_state["starting_balance"]) /
               paper_state["starting_balance"]) * 100

        # Get whale pool stats
        total_whales = db.query(WalletStats30D).count()
        profitable_whales = (
            db.query(WalletStats30D)
            .filter(WalletStats30D.unrealized_pnl_usd > 0)
            .count()
        )

        avg_pnl = (
            db.query(WalletStats30D.unrealized_pnl_usd)
            .filter(WalletStats30D.unrealized_pnl_usd > 0)
            .all()
        )
        avg_pnl_value = sum(p[0] for p in avg_pnl) / len(avg_pnl) if avg_pnl else 0

        # Get top 3 whales
        top_whales = (
            db.query(WalletStats30D)
            .filter(WalletStats30D.unrealized_pnl_usd > 0)
            .order_by(
                (WalletStats30D.unrealized_pnl_usd * 0.3 +
                 WalletStats30D.trades_count * 3 +
                 WalletStats30D.earlyscore_median * 0.4).desc()
            )
            .limit(3)
            .all()
        )

        # Get recent activity
        from sqlalchemy import func
        from datetime import timedelta

        since = datetime.utcnow() - timedelta(hours=1)
        recent_trades = (
            db.query(func.count(Trade.tx_hash))
            .filter(Trade.ts >= since)
            .scalar() or 0
        )

        # Calculate win rate
        win_rate = (paper_state["wins"] / paper_state["total_trades"] * 100) if paper_state["total_trades"] > 0 else 0

        # Determine emoji based on performance
        if roi >= 10:
            status_emoji = "🚀"
        elif roi >= 5:
            status_emoji = "📈"
        elif roi >= 0:
            status_emoji = "💰"
        else:
            status_emoji = "📉"

        # Build message
        message = f"""{status_emoji} HOURLY LEARNING UPDATE

⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

💰 PAPER TRADING PERFORMANCE:
Balance: ${paper_state['current_balance']:,.2f} (started $1,000)
ROI: {roi:+.2f}%

Trades: {paper_state['total_trades']} ({paper_state['wins']}W / {paper_state['losses']}L)
Win Rate: {win_rate:.1f}%

Profit: +${paper_state['total_profit']:.2f}
Loss: -${paper_state['total_loss']:.2f}
Open: {paper_state['open_positions']} positions

🐋 WHALE POOL STATUS:
Total Discovered: {total_whales} wallets
Profitable: {profitable_whales} whales
Avg PnL: ${avg_pnl_value:,.0f}

Recent Activity: {recent_trades} trades (last hour)

🏆 TOP 3 WHALES:
"""

        for i, whale in enumerate(top_whales, 1):
            message += f"{i}. {whale.wallet_address[:10]}... ${whale.unrealized_pnl_usd:,.0f}\n"

        if paper_state['total_trades'] == 0:
            message += "\n⏳ No trades yet - waiting for first confluence signal..."
        elif win_rate >= 60:
            message += f"\n✅ WINNING! Keep learning..."
        elif win_rate < 40:
            message += f"\n⚠️ Needs improvement - adjusting strategy..."
        else:
            message += f"\n📊 Learning in progress..."

        message += f"\n\n🤖 System is autonomously trading and learning."

        # Send to Telegram
        await telegram.bot.send_message(
            chat_id=telegram.chat_id,
            text=message,
            parse_mode=None,
        )

        logger.info(f"📱 Hourly update sent - ROI: {roi:+.2f}%, Trades: {paper_state['total_trades']}")

    except Exception as e:
        logger.error(f"Failed to send hourly update: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
