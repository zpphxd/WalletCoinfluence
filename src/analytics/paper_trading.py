"""Paper trading system to track actual performance with $1,000 starting balance."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class PaperTradingTracker:
    """Tracks paper trades to measure REAL performance with $1,000 virtual balance."""

    def __init__(self, db: Session, starting_balance: float = 1000.0):
        """Initialize paper trading tracker.

        Args:
            db: Database session
            starting_balance: Starting virtual balance (default $1,000)
        """
        self.db = db
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.positions: Dict[str, Dict[str, Any]] = {}  # token_address -> position
        self.closed_trades: List[Dict[str, Any]] = []
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.win_count = 0
        self.loss_count = 0

    def execute_buy(
        self,
        token_address: str,
        chain_id: str,
        price_usd: float,
        amount_usd: float,
        reason: str,
        num_whales: int = 1,
    ) -> Dict[str, Any]:
        """Execute a paper buy trade.

        Args:
            token_address: Token to buy
            chain_id: Chain identifier
            price_usd: Current token price
            amount_usd: Dollar amount to invest
            reason: Why we're buying (e.g., "2 whale confluence")
            num_whales: Number of whales buying (for confluence)

        Returns:
            Trade result
        """
        if amount_usd > self.current_balance:
            logger.warning(
                f"❌ INSUFFICIENT BALANCE: Tried to buy ${amount_usd:,.2f} "
                f"but only have ${self.current_balance:,.2f}"
            )
            return {
                "success": False,
                "reason": "insufficient_balance",
            }

        # Calculate quantity
        qty = amount_usd / price_usd

        # Record position
        self.positions[token_address] = {
            "token_address": token_address,
            "chain_id": chain_id,
            "qty": qty,
            "entry_price": price_usd,
            "cost_basis": amount_usd,
            "bought_at": datetime.utcnow(),
            "reason": reason,
            "num_whales": num_whales,
        }

        # Update balance
        self.current_balance -= amount_usd

        logger.info(
            f"📈 PAPER BUY: {qty:.2f} tokens @ ${price_usd:.6f} = ${amount_usd:.2f}\n"
            f"   Reason: {reason}\n"
            f"   Balance: ${self.current_balance:,.2f} (${amount_usd:.2f} invested)"
        )

        return {
            "success": True,
            "qty": qty,
            "price": price_usd,
            "cost": amount_usd,
        }

    def execute_sell(
        self,
        token_address: str,
        current_price: float,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        """Execute a paper sell trade (close position).

        Args:
            token_address: Token to sell
            current_price: Current token price
            reason: Why we're selling (e.g., "whale exit signal", "stop loss", "take profit")

        Returns:
            Trade result with profit/loss
        """
        if token_address not in self.positions:
            logger.warning(f"❌ NO POSITION: Cannot sell {token_address[:16]}...")
            return None

        position = self.positions[token_address]

        # Calculate proceeds
        proceeds = position["qty"] * current_price
        profit_loss = proceeds - position["cost_basis"]
        profit_pct = (profit_loss / position["cost_basis"]) * 100

        # Update balance
        self.current_balance += proceeds

        # Track win/loss
        if profit_loss > 0:
            self.win_count += 1
            self.total_profit += profit_loss
        else:
            self.loss_count += 1
            self.total_loss += abs(profit_loss)

        # Record closed trade
        hold_time = datetime.utcnow() - position["bought_at"]
        closed_trade = {
            "token_address": token_address,
            "chain_id": position["chain_id"],
            "entry_price": position["entry_price"],
            "exit_price": current_price,
            "qty": position["qty"],
            "cost_basis": position["cost_basis"],
            "proceeds": proceeds,
            "profit_loss": profit_loss,
            "profit_pct": profit_pct,
            "hold_time_hours": hold_time.total_seconds() / 3600,
            "bought_at": position["bought_at"],
            "sold_at": datetime.utcnow(),
            "buy_reason": position["reason"],
            "sell_reason": reason,
            "num_whales": position["num_whales"],
        }
        self.closed_trades.append(closed_trade)

        # Remove from positions
        del self.positions[token_address]

        emoji = "💰" if profit_loss > 0 else "📉"
        logger.info(
            f"{emoji} PAPER SELL: {position['qty']:.2f} tokens @ ${current_price:.6f} = ${proceeds:.2f}\n"
            f"   Entry: ${position['entry_price']:.6f} | Exit: ${current_price:.6f}\n"
            f"   P/L: ${profit_loss:+.2f} ({profit_pct:+.1f}%)\n"
            f"   Hold: {hold_time.total_seconds() / 3600:.1f}h\n"
            f"   Reason: {reason}\n"
            f"   Balance: ${self.current_balance:,.2f}"
        )

        return closed_trade

    def check_open_positions(self, price_fetcher) -> List[Dict[str, Any]]:
        """Check all open positions and calculate current value.

        Args:
            price_fetcher: MultiSourcePriceFetcher to get current prices

        Returns:
            List of positions with current values
        """
        import asyncio

        results = []

        for token_address, position in self.positions.items():
            # Get current price
            try:
                current_price = asyncio.run(
                    price_fetcher.get_token_price(token_address, position["chain_id"])
                )
            except Exception as e:
                logger.error(f"Error fetching price for {token_address[:16]}...: {e}")
                current_price = position["entry_price"]  # Fallback

            current_value = position["qty"] * current_price
            unrealized_pnl = current_value - position["cost_basis"]
            unrealized_pct = (unrealized_pnl / position["cost_basis"]) * 100

            hold_time = datetime.utcnow() - position["bought_at"]

            results.append({
                "token_address": token_address,
                "qty": position["qty"],
                "entry_price": position["entry_price"],
                "current_price": current_price,
                "cost_basis": position["cost_basis"],
                "current_value": current_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pct": unrealized_pct,
                "hold_time_hours": hold_time.total_seconds() / 3600,
                "num_whales": position["num_whales"],
            })

        return results

    def get_performance_report(self) -> str:
        """Generate comprehensive performance report.

        Returns:
            Formatted report string
        """
        # Calculate metrics
        total_trades = len(self.closed_trades)
        win_rate = (self.win_count / total_trades * 100) if total_trades > 0 else 0
        net_profit = self.total_profit - self.total_loss
        roi = ((self.current_balance - self.starting_balance) / self.starting_balance) * 100

        # Open positions value
        open_positions_value = sum(
            pos["qty"] * pos["entry_price"] for pos in self.positions.values()
        )
        total_portfolio_value = self.current_balance + open_positions_value

        # Best and worst trades
        best_trade = max(self.closed_trades, key=lambda t: t["profit_pct"]) if self.closed_trades else None
        worst_trade = min(self.closed_trades, key=lambda t: t["profit_pct"]) if self.closed_trades else None

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║          PAPER TRADING PERFORMANCE REPORT                    ║
╚══════════════════════════════════════════════════════════════╝

💰 ACCOUNT SUMMARY:
   Starting Balance:  ${self.starting_balance:,.2f}
   Current Cash:      ${self.current_balance:,.2f}
   Open Positions:    ${open_positions_value:,.2f}
   Total Portfolio:   ${total_portfolio_value:,.2f}

   Net P/L:           ${net_profit:+,.2f}
   ROI:               {roi:+.2f}%

📊 TRADE STATISTICS:
   Total Trades:      {total_trades}
   Winners:           {self.win_count} ({win_rate:.1f}%)
   Losers:            {self.loss_count} ({100-win_rate:.1f}%)

   Total Profit:      ${self.total_profit:,.2f}
   Total Loss:        $({self.total_loss:,.2f})
   Win/Loss Ratio:    {self.total_profit / self.total_loss if self.total_loss > 0 else float('inf'):.2f}x

🏆 BEST TRADE:
"""
        if best_trade:
            report += f"""   Token: {best_trade['token_address'][:16]}...
   P/L: ${best_trade['profit_loss']:+.2f} ({best_trade['profit_pct']:+.1f}%)
   Hold: {best_trade['hold_time_hours']:.1f}h
   Whales: {best_trade['num_whales']}
"""
        else:
            report += "   No trades yet\n"

        report += "\n📉 WORST TRADE:\n"
        if worst_trade:
            report += f"""   Token: {worst_trade['token_address'][:16]}...
   P/L: ${worst_trade['profit_loss']:+.2f} ({worst_trade['profit_pct']:+.1f}%)
   Hold: {worst_trade['hold_time_hours']:.1f}h
   Reason: {worst_trade['sell_reason']}
"""
        else:
            report += "   No trades yet\n"

        report += f"\n📈 OPEN POSITIONS: {len(self.positions)}\n"
        for token_addr, pos in list(self.positions.items())[:5]:
            hold_time = datetime.utcnow() - pos["bought_at"]
            report += f"""   {token_addr[:16]}... | Entry: ${pos['entry_price']:.6f} |
   Hold: {hold_time.total_seconds() / 3600:.1f}h | Whales: {pos['num_whales']}
"""

        # Grade based on ROI
        if roi >= 50:
            grade = "S+ (LEGENDARY)"
        elif roi >= 25:
            grade = "A+ (EXCELLENT)"
        elif roi >= 10:
            grade = "A (VERY GOOD)"
        elif roi >= 5:
            grade = "B (GOOD)"
        elif roi >= 0:
            grade = "C (BREAK EVEN)"
        else:
            grade = "F (LOSING)"

        report += f"\n🎯 PERFORMANCE GRADE: {grade}\n"
        report += "═" * 64 + "\n"

        return report

    def save_to_file(self, filename: str = "paper_trading_log.json"):
        """Save paper trading state to JSON file.

        Args:
            filename: Filename to save to
        """
        import json

        data = {
            "starting_balance": self.starting_balance,
            "current_balance": self.current_balance,
            "positions": self.positions,
            "closed_trades": self.closed_trades,
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "last_updated": datetime.utcnow().isoformat(),
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"📁 Paper trading state saved to {filename}")
