"""Telegram bot for interactive commands."""

import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.config import settings
from src.analytics.paper_trading import PaperTradingTracker

logger = logging.getLogger(__name__)


async def handle_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /update or 'update' message - show current paper trading status."""

    # Load paper trading state
    paper_trader = PaperTradingTracker.load_from_file("paper_trading_log.json")

    if not paper_trader:
        await update.message.reply_text("📊 No paper trading data yet. Waiting for first confluence signal...")
        return

    # Get current stats
    total_trades = len(paper_trader.closed_trades)
    wins = paper_trader.win_count
    losses = paper_trader.loss_count
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    roi = ((paper_trader.current_balance - paper_trader.starting_balance) / paper_trader.starting_balance) * 100

    # Build message
    message = f"""📊 PAPER TRADING UPDATE

💰 BALANCE: ${paper_trader.current_balance:,.2f}
   Started: ${paper_trader.starting_balance:,.2f}
   ROI: {roi:+.2f}%

📈 TRADES: {total_trades} total ({wins}W / {losses}L)
   Win Rate: {win_rate:.1f}%
   Total Profit: ${paper_trader.total_profit:,.2f}
   Total Loss: ${paper_trader.total_loss:,.2f}

📍 OPEN POSITIONS: {len(paper_trader.positions)}
"""

    # Show open positions
    if paper_trader.positions:
        message += "\n🔓 OPEN:\n"
        for token_addr, pos in list(paper_trader.positions.items())[:5]:
            token_display = f"{token_addr[:8]}...{token_addr[-6:]}"
            entry = pos['entry_price']
            cost = pos['cost_basis']
            message += f"  • {token_display}: ${cost:.2f} @ ${entry:.8f}\n"

    # Show recent closed trades
    if paper_trader.closed_trades:
        message += "\n🔒 RECENT CLOSED:\n"
        for trade in paper_trader.closed_trades[-3:]:
            token_display = f"{trade['token_address'][:8]}..."
            profit_pct = trade['profit_pct']
            profit_loss = trade['profit_loss']
            emoji = "✅" if profit_loss > 0 else "❌"
            message += f"  {emoji} {token_display}: {profit_pct:+.1f}% (${profit_loss:+.2f})\n"

    await update.message.reply_text(message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (check for 'update' keyword)."""
    text = update.message.text.lower().strip()

    if text == "update":
        await handle_update_command(update, context)


def start_telegram_bot():
    """Start the Telegram bot for interactive commands."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram bot token or chat ID not configured, skipping bot startup")
        return

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("update", handle_update_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Telegram bot started - send 'update' to get paper trading status")

    # Run the bot
    application.run_polling()
