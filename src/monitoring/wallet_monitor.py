"""Real-time wallet monitoring for trade detection."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.models import Wallet, Trade, WalletStats30D, Alert
from src.alerts.telegram import TelegramAlerter
from src.alerts.confluence import ConfluenceDetector
from src.config import settings
import redis

logger = logging.getLogger(__name__)


class WalletMonitor:
    """Monitors watchlist wallets for new trades."""

    def __init__(self, db: Session):
        """Initialize wallet monitor.

        Args:
            db: Database session
        """
        self.db = db
        self.telegram = TelegramAlerter()
        self.confluence = ConfluenceDetector()
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    async def monitor_watchlist_wallets(self) -> int:
        """Monitor all watchlist wallets for new trades.

        Returns:
            Number of alerts sent
        """
        try:
            # Get watchlist wallets (those with good stats)
            watchlist = self._get_watchlist_wallets()

            logger.info(f"Monitoring {len(watchlist)} watchlist wallets")

            alerts_sent = 0

            for wallet in watchlist:
                try:
                    # Check for new trades
                    new_trades = await self._check_wallet_for_new_trades(wallet)

                    for trade in new_trades:
                        # Check confluence
                        is_confluence = await self.confluence.check_confluence(
                            trade["token_address"],
                            trade["chain_id"],
                            wallet.address,
                        )

                        if is_confluence:
                            # Get all wallets in confluence
                            confluence_wallets = (
                                await self.confluence.get_confluence_wallets(
                                    trade["token_address"], trade["chain_id"]
                                )
                            )

                            # Send confluence alert
                            await self._send_confluence_alert(
                                trade, confluence_wallets
                            )
                            alerts_sent += 1

                        else:
                            # Send single wallet alert
                            await self._send_single_alert(trade, wallet)
                            alerts_sent += 1

                except Exception as e:
                    logger.error(f"Error monitoring wallet {wallet.address}: {str(e)}")
                    continue

            logger.info(f"Monitoring complete: {alerts_sent} alerts sent")
            return alerts_sent

        except Exception as e:
            logger.error(f"Wallet monitoring failed: {str(e)}")
            return 0

    def _get_watchlist_wallets(self) -> List[Wallet]:
        """Get wallets that meet watchlist criteria.

        Returns:
            List of watchlist wallets
        """
        try:
            # Get wallets with good 30D stats
            watchlist = (
                self.db.query(Wallet)
                .join(WalletStats30D, Wallet.address == WalletStats30D.wallet_address)
                .filter(
                    WalletStats30D.realized_pnl_usd
                    >= settings.add_min_realized_pnl_30d_usd,
                    WalletStats30D.trades_count >= settings.add_min_trades_30d,
                    WalletStats30D.best_trade_multiple
                    >= settings.add_min_best_trade_multiple,
                )
                .all()
            )

            return watchlist

        except Exception as e:
            logger.error(f"Error getting watchlist: {str(e)}")
            return []

    async def _check_wallet_for_new_trades(
        self, wallet: Wallet, minutes_back: int = 5
    ) -> List[Dict[str, Any]]:
        """Check if wallet has made new trades.

        Args:
            wallet: Wallet to check
            minutes_back: How many minutes back to check

        Returns:
            List of new trade data
        """
        try:
            # Check Redis cache for last seen trade
            cache_key = f"wallet_monitor:last_trade:{wallet.address}"
            last_seen_tx = self.redis_client.get(cache_key)

            # Get recent trades from chain
            if wallet.chain_id == "solana":
                from src.clients.helius import HeliusClient

                client = HeliusClient()
                recent_txs = await client.get_wallet_transactions(
                    wallet.address, limit=10
                )
            else:
                from src.clients.alchemy import AlchemyClient

                client = AlchemyClient()
                recent_txs = await client.get_wallet_transactions(
                    wallet.address, wallet.chain_id, limit=10
                )

            new_trades = []

            for tx in recent_txs:
                tx_hash = tx.get("tx_hash")

                # Skip if we've seen this transaction
                if tx_hash == last_seen_tx:
                    break

                # Only interested in buys
                if tx.get("type") != "buy":
                    continue

                new_trades.append(
                    {
                        "tx_hash": tx_hash,
                        "token_address": tx.get("token_address"),
                        "chain_id": wallet.chain_id,
                        "wallet_address": wallet.address,
                        "timestamp": tx.get("timestamp", datetime.utcnow()),
                        "amount": float(tx.get("amount", 0)),
                        "price_usd": float(tx.get("price_usd", 0)),
                        "value_usd": float(tx.get("value_usd", 0)),
                        "dex": tx.get("dex"),
                    }
                )

            # Update cache with latest tx
            if recent_txs:
                latest_tx = recent_txs[0].get("tx_hash")
                self.redis_client.setex(cache_key, 3600, latest_tx)  # 1 hour TTL

            return new_trades

        except Exception as e:
            logger.error(f"Error checking wallet for new trades: {str(e)}")
            return []

    async def _send_single_alert(
        self, trade: Dict[str, Any], wallet: Wallet
    ) -> None:
        """Send alert for single wallet buy.

        Args:
            trade: Trade data
            wallet: Wallet that made the trade
        """
        try:
            # Get wallet stats
            stats = (
                self.db.query(WalletStats30D)
                .filter(
                    WalletStats30D.wallet_address == wallet.address,
                    WalletStats30D.chain_id == wallet.chain_id,
                )
                .first()
            )

            # Calculate preliminary score
            prelim_score = self._calculate_preliminary_score(trade, stats)

            # Get token data
            from src.db.models import Token

            token = (
                self.db.query(Token)
                .filter(Token.token_address == trade["token_address"])
                .first()
            )

            # Build alert message
            message = f"""🔔 TOP WALLET BUY

Token: {token.symbol if token else 'Unknown'} (${trade['price_usd']:.8f})
Wallet: {wallet.address[:10]}...

30D PnL: ${stats.realized_pnl_usd:,.0f} | Best: {stats.best_trade_multiple:.1f}x
EarlyScore: {stats.earlyscore_median or 0:.0f}
Trades: {stats.trades_count}

Amount: {trade['amount']:,.2f} tokens
Value: ${trade['value_usd']:,.2f}
DEX: {trade['dex']}

TX: {self._get_explorer_link(trade['chain_id'], trade['tx_hash'])}
"""

            # Send via Telegram
            await self.telegram.send_message(message)

            # Log alert
            alert = Alert(
                ts=datetime.utcnow(),
                type="single",
                token_address=trade["token_address"],
                chain_id=trade["chain_id"],
                wallets_json=f'["{wallet.address}"]',
                payload_json=str(trade),
            )
            self.db.add(alert)
            self.db.commit()

            logger.info(
                f"Sent single alert for {wallet.address[:10]} buying {token.symbol if token else trade['token_address'][:10]}"
            )

        except Exception as e:
            logger.error(f"Error sending single alert: {str(e)}")

    async def _send_confluence_alert(
        self, trade: Dict[str, Any], wallets: List[str]
    ) -> None:
        """Send alert for confluence (multiple wallets buying).

        Args:
            trade: Trade data
            wallets: List of wallet addresses in confluence
        """
        try:
            # Get token data
            from src.db.models import Token

            token = (
                self.db.query(Token)
                .filter(Token.token_address == trade["token_address"])
                .first()
            )

            # Get stats for all wallets
            wallet_stats = []
            for wallet_addr in wallets:
                stats = (
                    self.db.query(WalletStats30D)
                    .filter(WalletStats30D.wallet_address == wallet_addr)
                    .first()
                )
                if stats:
                    wallet_stats.append(stats)

            avg_pnl = (
                sum(s.realized_pnl_usd for s in wallet_stats) / len(wallet_stats)
                if wallet_stats
                else 0
            )

            # Build alert message
            message = f"""🚨 CONFLUENCE ({len(wallets)} wallets) 🚨

Token: {token.symbol if token else 'Unknown'} (${trade['price_usd']:.8f})

Wallets:
"""

            for i, wallet_addr in enumerate(wallets[:5]):  # Show max 5
                stats = next(
                    (s for s in wallet_stats if s.wallet_address == wallet_addr), None
                )
                if stats:
                    message += f"- {wallet_addr[:10]}... | 30D: ${stats.realized_pnl_usd:,.0f} | Best: {stats.best_trade_multiple:.1f}x\n"

            message += f"""
Avg 30D PnL: ${avg_pnl:,.0f}
Window: {settings.confluence_minutes} min

TX: {self._get_explorer_link(trade['chain_id'], trade['tx_hash'])}
"""

            # Send via Telegram
            await self.telegram.send_message(message)

            # Log alert
            import json

            alert = Alert(
                ts=datetime.utcnow(),
                type="confluence",
                token_address=trade["token_address"],
                chain_id=trade["chain_id"],
                wallets_json=json.dumps(wallets),
                payload_json=str(trade),
            )
            self.db.add(alert)
            self.db.commit()

            logger.info(
                f"Sent confluence alert for {len(wallets)} wallets buying {token.symbol if token else trade['token_address'][:10]}"
            )

        except Exception as e:
            logger.error(f"Error sending confluence alert: {str(e)}")

    def _calculate_preliminary_score(
        self, trade: Dict[str, Any], stats: Optional[WalletStats30D]
    ) -> float:
        """Calculate preliminary signal score.

        Args:
            trade: Trade data
            stats: Wallet stats

        Returns:
            Score from 0-100
        """
        if not stats:
            return 0.0

        score = 0.0

        # 30D PnL component (40%)
        if stats.realized_pnl_usd > 100000:
            score += 40
        elif stats.realized_pnl_usd > 50000:
            score += 30
        elif stats.realized_pnl_usd > 10000:
            score += 20
        else:
            score += 10

        # Best trade component (30%)
        if stats.best_trade_multiple and stats.best_trade_multiple > 10:
            score += 30
        elif stats.best_trade_multiple and stats.best_trade_multiple > 5:
            score += 20
        elif stats.best_trade_multiple and stats.best_trade_multiple > 3:
            score += 15
        else:
            score += 5

        # EarlyScore component (30%)
        if stats.earlyscore_median and stats.earlyscore_median > 80:
            score += 30
        elif stats.earlyscore_median and stats.earlyscore_median > 60:
            score += 20
        elif stats.earlyscore_median and stats.earlyscore_median > 40:
            score += 10
        else:
            score += 5

        return score

    def _get_explorer_link(self, chain_id: str, tx_hash: str) -> str:
        """Get blockchain explorer link.

        Args:
            chain_id: Chain identifier
            tx_hash: Transaction hash

        Returns:
            Explorer URL
        """
        explorers = {
            "ethereum": f"https://etherscan.io/tx/{tx_hash}",
            "base": f"https://basescan.org/tx/{tx_hash}",
            "arbitrum": f"https://arbiscan.io/tx/{tx_hash}",
            "solana": f"https://solscan.io/tx/{tx_hash}",
        }

        return explorers.get(chain_id, f"https://etherscan.io/tx/{tx_hash}")
