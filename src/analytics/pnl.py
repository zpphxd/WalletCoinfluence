"""FIFO PnL calculation for wallet positions."""

import logging
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.db.models import Trade, Position

logger = logging.getLogger(__name__)


class FIFOPnLCalculator:
    """Calculate realized and unrealized PnL using FIFO method."""

    def __init__(self, db: Session):
        """Initialize PnL calculator.

        Args:
            db: Database session
        """
        self.db = db

    def calculate_wallet_pnl(
        self, wallet_address: str, days: int = 30
    ) -> Dict[str, float]:
        """Calculate total PnL for a wallet over specified period.

        Args:
            wallet_address: Wallet address
            days: Number of days to look back

        Returns:
            Dict with realized_pnl, unrealized_pnl, total_pnl
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Get all trades for this wallet in period
        trades = (
            self.db.query(Trade)
            .filter(and_(Trade.wallet_address == wallet_address, Trade.ts >= since))
            .order_by(Trade.ts.asc())
            .all()
        )

        # Group by token
        trades_by_token: Dict[str, List[Trade]] = {}
        for trade in trades:
            if trade.token_address not in trades_by_token:
                trades_by_token[trade.token_address] = []
            trades_by_token[trade.token_address].append(trade)

        total_realized = 0.0
        total_unrealized = 0.0

        # Calculate per token
        for token_address, token_trades in trades_by_token.items():
            realized, unrealized = self._calculate_token_pnl(
                wallet_address, token_address, token_trades
            )
            total_realized += realized
            total_unrealized += unrealized

        return {
            "realized_pnl": total_realized,
            "unrealized_pnl": total_unrealized,
            "total_pnl": total_realized + total_unrealized,
        }

    def _calculate_token_pnl(
        self, wallet_address: str, token_address: str, trades: List[Trade]
    ) -> Tuple[float, float]:
        """Calculate PnL for a specific token using FIFO.

        Args:
            wallet_address: Wallet address
            token_address: Token address
            trades: List of trades for this token

        Returns:
            Tuple of (realized_pnl, unrealized_pnl)
        """
        if not trades:
            return 0.0, 0.0

        # FIFO queue of buys: (qty, price, cost_basis)
        buy_queue: List[Tuple[float, float, float]] = []
        realized_pnl = 0.0

        for trade in trades:
            if trade.side == "buy":
                # Add to queue
                cost = trade.usd_value + (trade.fee_usd or 0)
                buy_queue.append((trade.qty_token, trade.price_usd, cost))

            elif trade.side == "sell":
                # Match with buys FIFO
                sell_qty = trade.qty_token
                sell_proceeds = trade.usd_value - (trade.fee_usd or 0)

                while sell_qty > 0 and buy_queue:
                    buy_qty, buy_price, buy_cost = buy_queue[0]

                    if sell_qty >= buy_qty:
                        # Consume entire buy
                        sell_qty -= buy_qty
                        # Realized = proceeds proportional to this buy - cost basis
                        proportion = buy_qty / trade.qty_token
                        realized_pnl += (sell_proceeds * proportion) - buy_cost
                        buy_queue.pop(0)
                    else:
                        # Partial buy
                        proportion = sell_qty / trade.qty_token
                        cost_proportion = (sell_qty / buy_qty) * buy_cost
                        realized_pnl += (sell_proceeds * proportion) - cost_proportion

                        # Update remaining buy
                        remaining_qty = buy_qty - sell_qty
                        remaining_cost = buy_cost - cost_proportion
                        buy_queue[0] = (remaining_qty, buy_price, remaining_cost)
                        sell_qty = 0

        # Calculate unrealized PnL from remaining positions
        unrealized_pnl = 0.0
        current_price = trades[-1].price_usd if trades else 0.0

        for qty, buy_price, cost_basis in buy_queue:
            current_value = qty * current_price
            unrealized_pnl += current_value - cost_basis

        # Update position in database
        self._update_position(
            wallet_address,
            token_address,
            buy_queue,
            realized_pnl,
            unrealized_pnl,
            current_price,
        )

        return realized_pnl, unrealized_pnl

    def _update_position(
        self,
        wallet_address: str,
        token_address: str,
        buy_queue: List[Tuple[float, float, float]],
        realized_pnl: float,
        unrealized_pnl: float,
        last_price: float,
    ) -> None:
        """Update position table.

        Args:
            wallet_address: Wallet address
            token_address: Token address
            buy_queue: Remaining FIFO queue
            realized_pnl: Realized PnL
            unrealized_pnl: Unrealized PnL
            last_price: Last trade price
        """
        # Get or create position
        position = (
            self.db.query(Position)
            .filter(
                and_(
                    Position.wallet_address == wallet_address,
                    Position.token_address == token_address,
                )
            )
            .first()
        )

        total_qty = sum(qty for qty, _, _ in buy_queue)
        total_cost = sum(cost for _, _, cost in buy_queue)

        if position:
            position.qty = total_qty
            position.cost_basis_usd = total_cost
            position.realized_pnl_usd = realized_pnl
            position.unrealized_pnl_usd = unrealized_pnl
            position.last_price_usd = last_price
            position.last_update = datetime.utcnow()
        else:
            # Infer chain from first trade
            chain_id = (
                self.db.query(Trade.chain_id)
                .filter(Trade.token_address == token_address)
                .first()[0]
            )

            position = Position(
                wallet_address=wallet_address,
                token_address=token_address,
                chain_id=chain_id,
                qty=total_qty,
                cost_basis_usd=total_cost,
                realized_pnl_usd=realized_pnl,
                unrealized_pnl_usd=unrealized_pnl,
                last_price_usd=last_price,
                last_update=datetime.utcnow(),
            )
            self.db.add(position)

        self.db.commit()

    def get_best_trade_multiple(self, wallet_address: str, days: int = 30) -> float:
        """Get best trade multiple for a wallet.

        Args:
            wallet_address: Wallet address
            days: Days to look back

        Returns:
            Best trade multiple (e.g., 5.2 for 5.2x)
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Get all closed positions (have both buys and sells)
        trades = (
            self.db.query(Trade)
            .filter(and_(Trade.wallet_address == wallet_address, Trade.ts >= since))
            .order_by(Trade.ts.asc())
            .all()
        )

        # Group by token
        trades_by_token: Dict[str, List[Trade]] = {}
        for trade in trades:
            if trade.token_address not in trades_by_token:
                trades_by_token[trade.token_address] = []
            trades_by_token[trade.token_address].append(trade)

        best_multiple = 1.0

        for token_trades in trades_by_token.values():
            buys = [t for t in token_trades if t.side == "buy"]
            sells = [t for t in token_trades if t.side == "sell"]

            if not buys or not sells:
                continue

            # Average buy price vs average sell price
            avg_buy_price = sum(t.price_usd for t in buys) / len(buys)
            avg_sell_price = sum(t.price_usd for t in sells) / len(sells)

            if avg_buy_price > 0:
                multiple = avg_sell_price / avg_buy_price
                best_multiple = max(best_multiple, multiple)

        return best_multiple
