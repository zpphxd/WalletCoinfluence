"""Autonomous paper trader that executes trades based on confluence signals."""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.analytics.paper_trading import PaperTradingTracker
from src.analytics.performance_tracker import PerformanceTracker
from src.utils.price_fetcher import MultiSourcePriceFetcher
from src.db.session import SessionLocal
from src.db.models import Trade, WalletStats30D

logger = logging.getLogger(__name__)


class AutonomousPaperTrader:
    """Autonomous trader that learns from confluence signals and manages paper trades."""

    def __init__(self, starting_balance: float = 1000.0):
        """Initialize autonomous trader.

        Args:
            starting_balance: Starting paper trading balance
        """
        self.db = SessionLocal()
        self.paper_trader = PaperTradingTracker(self.db, starting_balance)
        self.performance_tracker = PerformanceTracker(self.db)
        self.price_fetcher = MultiSourcePriceFetcher()

        # Trading rules (will evolve based on performance)
        self.rules = {
            "buy_amount_pct": 0.20,  # Invest 20% of balance per trade
            "min_whales_for_buy": 2,  # Need at least 2 whales for confluence
            "take_profit_pct": 20.0,  # Sell at +20% profit
            "stop_loss_pct": -10.0,  # Sell at -10% loss
            "max_hold_hours": 24.0,  # Auto-sell after 24 hours
            "min_whale_pnl": 1000.0,  # Only follow whales with >$1k PnL
        }

        logger.info(
            f"🤖 Autonomous Paper Trader initialized with ${starting_balance:,.2f}\n"
            f"   Rules: {self.rules}"
        )

    async def check_for_confluence_buys(self) -> int:
        """Check for confluence signals and execute paper buys.

        Returns:
            Number of buys executed
        """
        buys_executed = 0

        # Get recent trades from TOP whales
        since = datetime.utcnow() - timedelta(minutes=30)

        # Find tokens where ≥2 whales bought within last 30 minutes
        from sqlalchemy import func

        confluence_tokens = (
            self.db.query(
                Trade.token_address,
                Trade.chain_id,
                func.count(func.distinct(Trade.wallet_address)).label("whale_count"),
                func.avg(Trade.price_usd).label("avg_price"),
                func.max(Trade.ts).label("last_trade_time"),
            )
            .join(
                WalletStats30D,
                Trade.wallet_address == WalletStats30D.wallet_address,
            )
            .filter(
                Trade.ts >= since,
                Trade.side == "buy",
                WalletStats30D.unrealized_pnl_usd >= self.rules["min_whale_pnl"],
            )
            .group_by(Trade.token_address, Trade.chain_id)
            .having(func.count(func.distinct(Trade.wallet_address)) >= self.rules["min_whales_for_buy"])
            .all()
        )

        for token_address, chain_id, whale_count, avg_price, last_trade_time in confluence_tokens:
            # Check if we already have a position
            if token_address in self.paper_trader.positions:
                logger.debug(f"Already have position in {token_address[:16]}..., skipping")
                continue

            # Get current price
            current_price = await self.price_fetcher.get_token_price(token_address, chain_id)
            if current_price == 0:
                logger.warning(f"Cannot get price for {token_address[:16]}..., skipping")
                continue

            # Calculate buy amount (20% of current balance)
            buy_amount = self.paper_trader.current_balance * self.rules["buy_amount_pct"]

            # Execute paper buy
            result = self.paper_trader.execute_buy(
                token_address=token_address,
                chain_id=chain_id,
                price_usd=current_price,
                amount_usd=buy_amount,
                reason=f"{whale_count} whale confluence",
                num_whales=whale_count,
            )

            if result["success"]:
                buys_executed += 1

                # REWARD for detecting confluence
                reward = self.performance_tracker.reward_confluence_detection(
                    token_address, whale_count, window_minutes=30
                )

                # Check if we were fast enough
                detection_time = datetime.utcnow()
                delay = (detection_time - last_trade_time).total_seconds() / 60

                if delay > 5:
                    # PUNISHMENT for being late
                    punishment = self.performance_tracker.punish_late_detection(
                        token_address, last_trade_time, detection_time
                    )

                logger.info(
                    f"🎯 CONFLUENCE BUY EXECUTED\n"
                    f"   Token: {token_address[:16]}...\n"
                    f"   Whales: {whale_count}\n"
                    f"   Price: ${current_price:.6f}\n"
                    f"   Amount: ${buy_amount:.2f}\n"
                    f"   Reward: +{reward} pts\n"
                    f"   Delay: {delay:.1f}min"
                )

        return buys_executed

    async def check_for_sells(self) -> int:
        """Check open positions and sell based on profit/loss/time rules.

        Returns:
            Number of sells executed
        """
        sells_executed = 0

        for token_address in list(self.paper_trader.positions.keys()):
            position = self.paper_trader.positions[token_address]

            # Get current price
            current_price = await self.price_fetcher.get_token_price(
                token_address, position["chain_id"]
            )

            if current_price == 0:
                logger.warning(f"Cannot get price for {token_address[:16]}..., skipping")
                continue

            # Calculate current P/L
            current_value = position["qty"] * current_price
            profit_loss = current_value - position["cost_basis"]
            profit_pct = (profit_loss / position["cost_basis"]) * 100

            # Calculate hold time
            hold_time_hours = (datetime.utcnow() - position["bought_at"]).total_seconds() / 3600

            # Sell decision logic
            sell_reason = None

            if profit_pct >= self.rules["take_profit_pct"]:
                sell_reason = f"TAKE PROFIT (+{profit_pct:.1f}%)"

            elif profit_pct <= self.rules["stop_loss_pct"]:
                sell_reason = f"STOP LOSS ({profit_pct:.1f}%)"

            elif hold_time_hours >= self.rules["max_hold_hours"]:
                sell_reason = f"MAX HOLD TIME ({hold_time_hours:.1f}h)"

            # Check if whales are selling (exit signal)
            since = datetime.utcnow() - timedelta(minutes=30)
            whale_sells = (
                self.db.query(func.count(func.distinct(Trade.wallet_address)))
                .join(
                    WalletStats30D,
                    Trade.wallet_address == WalletStats30D.wallet_address,
                )
                .filter(
                    Trade.token_address == token_address,
                    Trade.side == "sell",
                    Trade.ts >= since,
                    WalletStats30D.unrealized_pnl_usd >= self.rules["min_whale_pnl"],
                )
                .scalar()
            )

            if whale_sells >= 2:
                sell_reason = f"WHALE EXIT ({whale_sells} whales selling)"

            # Execute sell if we have a reason
            if sell_reason:
                result = self.paper_trader.execute_sell(
                    token_address, current_price, sell_reason
                )

                if result:
                    sells_executed += 1

                    # REWARD/PUNISHMENT based on outcome
                    if result["profit_loss"] > 0:
                        # Calculate reward based on profit %
                        if result["profit_pct"] >= 50:
                            reward = 100  # BIG win
                        elif result["profit_pct"] >= 20:
                            reward = 50  # Good win
                        else:
                            reward = 25  # Small win

                        self.performance_tracker.score += reward
                        self.performance_tracker.total_rewards += reward

                        logger.info(
                            f"💰 PROFITABLE SELL (+{result['profit_pct']:.1f}%)\n"
                            f"   Token: {token_address[:16]}...\n"
                            f"   Profit: ${result['profit_loss']:.2f}\n"
                            f"   Reward: +{reward} pts"
                        )
                    else:
                        # PUNISHMENT for losing trade
                        punishment = -abs(int(result["profit_pct"]))  # -10% = -10 pts
                        self.performance_tracker.score += punishment
                        self.performance_tracker.total_punishments += abs(punishment)

                        logger.warning(
                            f"📉 LOSING SELL ({result['profit_pct']:.1f}%)\n"
                            f"   Token: {token_address[:16]}...\n"
                            f"   Loss: ${result['profit_loss']:.2f}\n"
                            f"   Punishment: {punishment} pts"
                        )

        return sells_executed

    async def run_trading_cycle(self) -> Dict[str, any]:
        """Run one complete trading cycle (check buys, check sells, report).

        Returns:
            Cycle results
        """
        logger.info("🔄 Running autonomous trading cycle...")

        # Check for new confluence buy opportunities
        buys = await self.check_for_confluence_buys()

        # Check if we should sell any positions
        sells = await self.check_for_sells()

        # Get current portfolio value
        open_positions = self.paper_trader.check_open_positions(self.price_fetcher)
        total_open_value = sum(pos["current_value"] for pos in open_positions)
        total_portfolio = self.paper_trader.current_balance + total_open_value

        # Calculate ROI
        roi = ((total_portfolio - self.paper_trader.starting_balance) / self.paper_trader.starting_balance) * 100

        logger.info(
            f"✅ Trading cycle complete\n"
            f"   Buys: {buys} | Sells: {sells}\n"
            f"   Portfolio: ${total_portfolio:,.2f} (ROI: {roi:+.2f}%)\n"
            f"   Score: {self.performance_tracker.score} pts"
        )

        # Save state
        self.paper_trader.save_to_file()

        return {
            "buys": buys,
            "sells": sells,
            "portfolio_value": total_portfolio,
            "roi": roi,
            "score": self.performance_tracker.score,
        }

    def adjust_rules_based_on_performance(self):
        """Dynamically adjust trading rules based on performance.

        LEARNING: If winning → take more risk
                  If losing → be more conservative
        """
        total_trades = len(self.paper_trader.closed_trades)

        if total_trades < 5:
            return  # Not enough data yet

        win_rate = self.paper_trader.win_count / total_trades

        # ADJUST RULES BASED ON WIN RATE
        if win_rate >= 0.7:
            # We're winning a lot - take MORE risk
            self.rules["buy_amount_pct"] = min(0.30, self.rules["buy_amount_pct"] + 0.05)
            self.rules["take_profit_pct"] = max(15.0, self.rules["take_profit_pct"] - 5.0)
            logger.info(
                f"📈 HIGH WIN RATE ({win_rate:.1%}) → Increasing risk:\n"
                f"   Buy amount: {self.rules['buy_amount_pct']:.1%}\n"
                f"   Take profit: +{self.rules['take_profit_pct']:.0f}%"
            )

        elif win_rate <= 0.4:
            # We're losing too much - be MORE conservative
            self.rules["buy_amount_pct"] = max(0.10, self.rules["buy_amount_pct"] - 0.05)
            self.rules["take_profit_pct"] = min(30.0, self.rules["take_profit_pct"] + 5.0)
            self.rules["stop_loss_pct"] = max(-15.0, self.rules["stop_loss_pct"] - 2.0)
            logger.info(
                f"📉 LOW WIN RATE ({win_rate:.1%}) → Reducing risk:\n"
                f"   Buy amount: {self.rules['buy_amount_pct']:.1%}\n"
                f"   Take profit: +{self.rules['take_profit_pct']:.0f}%\n"
                f"   Stop loss: {self.rules['stop_loss_pct']:.0f}%"
            )

        # Save adjusted rules
        logger.info(f"🔧 Updated trading rules: {self.rules}")

    def get_performance_report(self) -> str:
        """Get combined performance report (paper trading + scoring).

        Returns:
            Formatted report
        """
        paper_report = self.paper_trader.get_performance_report()

        score_section = f"""
╔══════════════════════════════════════════════════════════════╗
║          SELF-SCORING PERFORMANCE                            ║
╚══════════════════════════════════════════════════════════════╝

🎯 CURRENT SCORE: {self.performance_tracker.score} pts

✅ Total Rewards:     +{self.performance_tracker.total_rewards} pts
❌ Total Punishments: -{self.performance_tracker.total_punishments} pts

📊 EVENT LOG (Last 10):
"""
        for event in self.performance_tracker.performance_log[-10:]:
            score_section += f"   {event['type']}: {event.get('reward', event.get('punishment', 0))} pts\n"

        return paper_report + "\n" + score_section


# Job function for scheduler
async def autonomous_trading_job():
    """Autonomous trading job that runs every 5 minutes."""
    trader = AutonomousPaperTrader(starting_balance=1000.0)

    try:
        # Run trading cycle
        results = await trader.run_trading_cycle()

        # Adjust rules based on performance every 10 trades
        if len(trader.paper_trader.closed_trades) % 10 == 0:
            trader.adjust_rules_based_on_performance()

        # Log report every hour (12 cycles)
        if len(trader.paper_trader.closed_trades) % 12 == 0:
            report = trader.get_performance_report()
            logger.info(f"\n{report}")

    except Exception as e:
        logger.error(f"Autonomous trading job failed: {str(e)}")
        import traceback
        traceback.print_exc()
