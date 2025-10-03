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
                        side = trade.get("side", "buy")  # "buy" or "sell"

                        # Record trade in confluence tracker
                        self.confluence.record_trade(
                            trade["token_address"],
                            trade["chain_id"],
                            wallet.address,
                            side,
                            {
                                "price_usd": trade.get("price_usd", 0),
                                "value_usd": trade.get("value_usd", 0),
                                "tx_hash": trade.get("tx_hash"),
                            }
                        )

                        # Check if this creates confluence (≥2 whales)
                        confluence_events = self.confluence.check_confluence(
                            trade["token_address"],
                            trade["chain_id"],
                            side=side,
                            min_wallets=2
                        )

                        if confluence_events:
                            # SEND CONFLUENCE ALERT (≥2 whales trading same token)
                            await self._send_confluence_alert(
                                trade, confluence_events, side=side
                            )
                            alerts_sent += 1
                            action = "buying" if side == "buy" else "selling"
                            logger.info(
                                f"🚨 CONFLUENCE ALERT SENT: {len(confluence_events)} whales "
                                f"{action} {trade['token_address'][:10]}..."
                            )

                        # DO NOT send single wallet alerts - user only wants confluence

                except Exception as e:
                    logger.error(f"Error monitoring wallet {wallet.address}: {str(e)}")
                    continue

            logger.info(f"Monitoring complete: {alerts_sent} alerts sent")
            return alerts_sent

        except Exception as e:
            logger.error(f"Wallet monitoring failed: {str(e)}")
            return 0

    def _get_watchlist_wallets(self) -> List[Wallet]:
        """Get TOP 30 WHALES ONLY - best performers ranked by composite score.

        Returns:
            List of top 30 whale wallets
        """
        try:
            from sqlalchemy import func, case

            # Calculate composite score for each wallet:
            # - 30% weight: Unrealized PnL rank (current position value)
            # - 30% weight: Trade activity rank (more active = better)
            # - 40% weight: EarlyScore rank (timing ability)

            # Get all wallet stats with PnL > $0 (only profitable whales)
            profitable_wallets = (
                self.db.query(
                    Wallet,
                    WalletStats30D,
                    # Normalize unrealized_pnl_usd to 0-100 scale
                    (WalletStats30D.unrealized_pnl_usd).label('pnl_score'),
                    # Normalize trades_count to 0-100 scale
                    (WalletStats30D.trades_count * 10).label('activity_score'),
                    # EarlyScore is already 0-100
                    (WalletStats30D.earlyscore_median).label('early_score'),
                )
                .join(WalletStats30D, Wallet.address == WalletStats30D.wallet_address)
                .filter(
                    WalletStats30D.unrealized_pnl_usd > 0,  # MUST be profitable
                    WalletStats30D.trades_count >= 1,  # At least 1 trade
                )
                .all()
            )

            # Calculate composite score for each wallet
            scored_wallets = []
            for wallet, stats, pnl_score, activity_score, early_score in profitable_wallets:
                # Composite score (weighted average)
                composite = (
                    0.30 * (pnl_score or 0) +
                    0.30 * min(activity_score or 0, 100) +  # Cap at 100
                    0.40 * (early_score or 0)
                )

                scored_wallets.append((wallet, composite))

            # Sort by composite score (highest first)
            scored_wallets.sort(key=lambda x: x[1], reverse=True)

            # Return TOP 30 WHALES ONLY
            top_30 = [wallet for wallet, score in scored_wallets[:30]]

            logger.info(
                f"🐋 TOP 30 WHALES selected from {len(profitable_wallets)} profitable wallets "
                f"(composite scoring: 30% PnL + 30% activity + 40% timing)"
            )

            return top_30

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
                    wallet.address, limit=100
                )
            else:
                from src.clients.alchemy import AlchemyClient

                client = AlchemyClient()
                recent_txs = await client.get_wallet_transactions(
                    wallet.address, wallet.chain_id, limit=100
                )

            new_trades = []

            for tx in recent_txs:
                tx_hash = tx.get("tx_hash")

                # Skip if we've seen this transaction
                if tx_hash == last_seen_tx:
                    break

                # Track both buys and sells
                if tx.get("type") not in ["buy", "sell"]:
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
            # Send via Telegram
            alert_data = {
                "token_symbol": token.symbol if token else "Unknown",
                "token_address": trade["token_address"],
                "wallet_address": wallet.address,
                "chain_id": trade["chain_id"],
                "price_usd": trade.get("price_usd", 0),
                "pnl_30d_usd": (stats.realized_pnl_usd + stats.unrealized_pnl_usd) if stats else 0,
                "best_trade_multiple": stats.best_trade_multiple if stats else 0,
                "earlyscore": stats.earlyscore_median if stats else 0,
                "tx_hash": trade.get("tx_hash", ""),
                "dex": trade.get("dex", ""),
            }
            await self.telegram.send_single_wallet_alert(alert_data)

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
        self, trade: Dict[str, Any], confluence_events: List[Dict[str, Any]], side: str = "buy"
    ) -> None:
        """Send alert for confluence (multiple wallets buying or selling).

        Args:
            trade: Trade data
            confluence_events: List of event dicts from confluence detector
            side: "buy" or "sell"
        """
        try:
            # Get token data
            from src.db.models import Token

            token = (
                self.db.query(Token)
                .filter(Token.token_address == trade["token_address"])
                .first()
            )

            # Extract wallet addresses from events
            wallet_addrs = [event.get("wallet") for event in confluence_events]

            # Get stats for all wallets
            wallet_stats_list = []
            for wallet_addr in wallet_addrs:
                stats = (
                    self.db.query(WalletStats30D)
                    .filter(WalletStats30D.wallet_address == wallet_addr)
                    .first()
                )
                if stats:
                    wallet_stats_list.append({
                        "address": wallet_addr,
                        "pnl_30d": stats.realized_pnl_usd + stats.unrealized_pnl_usd,
                        "best_multiple": stats.best_trade_multiple,
                        "earlyscore": stats.earlyscore_median,
                    })

            avg_pnl = (
                sum(w["pnl_30d"] for w in wallet_stats_list) / len(wallet_stats_list)
                if wallet_stats_list
                else 0
            )

            # Send via Telegram
            alert_data = {
                "token_symbol": token.symbol if token else "Unknown",
                "token_address": trade["token_address"],
                "chain_id": trade["chain_id"],
                "price_usd": trade.get("price_usd", 0),
                "wallets": wallet_stats_list,
                "avg_pnl_30d": avg_pnl,
                "window_minutes": settings.confluence_minutes,
                "liquidity_usd": 0,  # TODO: fetch from DexScreener
                "side": side,  # "buy" or "sell"
            }
            await self.telegram.send_confluence_alert(alert_data)

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
