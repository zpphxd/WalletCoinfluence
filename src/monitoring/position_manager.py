"""Position manager for checking take-profit/stop-loss targets."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from src.analytics.paper_trading import PaperTradingTracker
from src.utils.price_fetcher import MultiSourcePriceFetcher

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages open positions and executes exits based on targets."""

    def __init__(self, paper_trader: PaperTradingTracker):
        """Initialize position manager.

        Args:
            paper_trader: Paper trading tracker instance
        """
        self.paper_trader = paper_trader
        self.price_fetcher = MultiSourcePriceFetcher()

    async def check_and_exit_positions(self) -> int:
        """Check all open positions and exit if targets are hit.

        Returns:
            Number of positions closed
        """
        positions_closed = 0

        for token_address in list(self.paper_trader.positions.keys()):
            try:
                position = self.paper_trader.positions[token_address]

                # Get current price
                current_price = await self.price_fetcher.get_token_price(
                    token_address, position.get("chain_id", "ethereum")
                )

                if current_price == 0:
                    logger.warning(f"Cannot get price for {token_address[:16]}..., skipping")
                    continue

                # Calculate current P/L
                current_value = position["qty"] * current_price
                profit_loss = current_value - position["cost_basis"]
                profit_pct = (profit_loss / position["cost_basis"]) * 100

                # Get targets (with defaults if not set)
                take_profit_pct = position.get("take_profit_pct", 20.0)
                stop_loss_pct = position.get("stop_loss_pct", -15.0)

                # Calculate hold time (handle both datetime and string formats)
                bought_at = position["bought_at"]
                if isinstance(bought_at, str):
                    # Parse ISO format string: "2025-10-06T15:02:15.123456"
                    bought_at = datetime.fromisoformat(bought_at.replace('Z', '+00:00'))
                hold_time_hours = (datetime.utcnow() - bought_at).total_seconds() / 3600

                # 🎯 EXIT LOGIC (aggressive for max gains)
                sell_reason = None

                # 1. TAKE PROFIT
                if profit_pct >= take_profit_pct:
                    sell_reason = f"TAKE PROFIT (+{profit_pct:.1f}% ≥ target +{take_profit_pct:.0f}%)"

                # 2. STOP LOSS
                elif profit_pct <= stop_loss_pct:
                    sell_reason = f"STOP LOSS ({profit_pct:.1f}% ≤ {stop_loss_pct:.0f}%)"

                # 3. MAX HOLD TIME (24 hours - force exit to free capital)
                elif hold_time_hours >= 24.0:
                    sell_reason = f"MAX HOLD TIME ({hold_time_hours:.1f}h, P/L: {profit_pct:+.1f}%)"

                # 4. TRAILING STOP for winning positions (lock in profits)
                elif profit_pct >= 15.0:  # If up 15%+, use trailing stop
                    # Get peak profit for this position
                    peak_profit = position.get("peak_profit_pct", profit_pct)

                    # Update peak if current is higher
                    if profit_pct > peak_profit:
                        self.paper_trader.positions[token_address]["peak_profit_pct"] = profit_pct
                        peak_profit = profit_pct

                    # If profit dropped 8% from peak, sell (lock in gains)
                    if profit_pct < peak_profit - 8.0:
                        sell_reason = f"TRAILING STOP (dropped to +{profit_pct:.1f}% from peak +{peak_profit:.1f}%)"

                # Execute sell if we have a reason
                if sell_reason:
                    result = self.paper_trader.execute_sell(
                        token_address, current_price, sell_reason
                    )

                    if result:
                        positions_closed += 1
                        self.paper_trader.save_to_file()

                        emoji = "✅" if result["profit_loss"] > 0 else "❌"
                        logger.info(
                            f"{emoji} AUTO-SELL EXECUTED\n"
                            f"   Token: {token_address[:16]}...\n"
                            f"   Reason: {sell_reason}\n"
                            f"   P/L: ${result['profit_loss']:+.2f} ({result['profit_pct']:+.1f}%)\n"
                            f"   Hold: {result['hold_time_hours']:.1f}h\n"
                            f"   Balance: ${self.paper_trader.current_balance:.2f}"
                        )

            except Exception as e:
                logger.error(f"Error checking position {token_address[:16]}...: {str(e)}")
                continue

        return positions_closed
