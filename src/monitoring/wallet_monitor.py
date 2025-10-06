"""Real-time wallet monitoring for trade detection."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.models import Wallet, Trade, WalletStats30D, Alert, CustomWatchlistWallet
from src.alerts.telegram import TelegramAlerter
from src.alerts.confluence import ConfluenceDetector
from src.analytics.paper_trading import PaperTradingTracker
from src.utils.price_fetcher import MultiSourcePriceFetcher
from src.monitoring.position_manager import PositionManager
from src.utils.meme_coin_detector import MemeCoinDetector
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

        # Load or create paper trader (OPPORTUNITY-DRIVEN)
        self.paper_trader = PaperTradingTracker.load_from_file() or PaperTradingTracker(db, starting_balance=1000.0)
        self.price_fetcher = MultiSourcePriceFetcher()
        self.position_manager = PositionManager(self.paper_trader)
        self.meme_detector = MemeCoinDetector(db)

    async def monitor_watchlist_wallets(self) -> int:
        """Monitor all watchlist wallets for new trades.

        Returns:
            Number of alerts sent
        """
        try:
            # 🎯 STEP 1: Check open positions for take-profit/stop-loss
            positions_closed = await self.position_manager.check_and_exit_positions()
            if positions_closed > 0:
                logger.info(f"💰 Position manager closed {positions_closed} positions")

            # 🐋 STEP 2: Monitor ALL profitable whales for new trades
            watchlist = self._get_watchlist_wallets()

            logger.info(f"Monitoring {len(watchlist)} watchlist wallets")

            alerts_sent = 0

            for wallet in watchlist:
                try:
                    # Check for new trades
                    new_trades = await self._check_wallet_for_new_trades(wallet)

                    for trade in new_trades:
                        side = trade.get("side", "buy")  # "buy" or "sell"

                        # 🚫 FILTER STABLECOINS & BASE TOKENS - CRITICAL FIX!
                        token_address = trade["token_address"].lower()
                        STABLECOINS_AND_WRAPPED = {
                            # Ethereum Mainnet
                            "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT (ETH)
                            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC (ETH)
                            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH (ETH)
                            "0x2260fac5e5542a774ae82da6db1b2159f876eff9",  # WBTC (ETH)
                            "0x6b175474e89094c44da98b954eedeac495271d0f",  # DAI (ETH)
                            # Base
                            "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # USDC (Base)
                            "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",  # WBTC (Base)
                            "0x4200000000000000000000000000000000000006",  # WETH (Base)
                            # Arbitrum
                            "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",  # USDT (Arbitrum)
                            "0xaf88d065e77c8cc2239327c5edb3a432268e5831",  # USDC (Arbitrum)
                            "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",  # WBTC (Arbitrum)
                            "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",  # WETH (Arbitrum)
                        }

                        if token_address in STABLECOINS_AND_WRAPPED:
                            logger.info(f"⏭️  SKIPPING STABLECOIN/WRAPPED: {token_address[:16]}... (not a memecoin)")
                            continue

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

                        # Check if this creates confluence (≥2 whales within 30 min)
                        confluence_events = self.confluence.check_confluence(
                            trade["token_address"],
                            trade["chain_id"],
                            side=side,
                            min_wallets=2  # 2+ whales buying same token = signal
                        )

                        if confluence_events:
                            # 🤖 EXECUTE PAPER TRADE ON CONFLUENCE (OPPORTUNITY-DRIVEN!)
                            if side == "buy":
                                await self._execute_paper_buy(trade, len(confluence_events))
                            elif side == "sell":
                                await self._execute_paper_sell(trade, len(confluence_events))

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
        """Get PROFITABLE WHALES + USER CUSTOM WALLETS for strong signals!

        Returns:
            List of whale wallets (auto-discovered + custom)
        """
        try:
            # Get auto-discovered whales with $500+ PnL (QUALITY over quantity!)
            profitable_whales = (
                self.db.query(Wallet)
                .join(WalletStats30D, Wallet.address == WalletStats30D.wallet_address)
                .filter(
                    WalletStats30D.unrealized_pnl_usd > 500,  # $500+ profit whales only
                    WalletStats30D.trades_count >= 2,  # At least 2 trades
                )
                .all()
            )

            # Get user's CUSTOM WATCHLIST wallets
            custom_wallet_addrs = (
                self.db.query(CustomWatchlistWallet.address, CustomWatchlistWallet.chain_id)
                .filter(CustomWatchlistWallet.is_active == True)
                .all()
            )

            # Fetch full Wallet objects for custom wallets
            custom_wallets = []
            for addr, chain in custom_wallet_addrs:
                wallet = self.db.query(Wallet).filter(Wallet.address == addr, Wallet.chain_id == chain).first()

                # If not in database yet, create it
                if not wallet:
                    wallet = Wallet(
                        address=addr,
                        chain_id=chain,
                        first_seen_at=datetime.utcnow(),
                    )
                    self.db.add(wallet)
                    self.db.commit()
                    logger.info(f"✨ Created wallet entry for custom watchlist: {addr[:16]}...")

                custom_wallets.append(wallet)

            # Combine both lists (remove duplicates)
            all_wallets = profitable_whales + custom_wallets
            unique_wallets = {w.address: w for w in all_wallets}.values()

            logger.info(
                f"🐋 MONITORING {len(profitable_whales)} AUTO-DISCOVERED WHALES + "
                f"{len(custom_wallets)} CUSTOM WALLETS = {len(unique_wallets)} TOTAL"
            )

            return list(unique_wallets)

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

            # Get recent trades from chain (1000 txs = ~24-48h of whale activity)
            if wallet.chain_id == "solana":
                from src.clients.solscan import SolscanClient

                client = SolscanClient()
                recent_txs = await client.get_wallet_transactions(
                    wallet.address, limit=1000
                )

                # Log that we're tracking this Solana whale
                logger.info(f"📍 Tracking Solana whale: {wallet.address[:16]}... via Solscan")
            else:
                from src.clients.alchemy import AlchemyClient

                client = AlchemyClient()
                recent_txs = await client.get_wallet_transactions(
                    wallet.address, wallet.chain_id, limit=1000
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
            # Send via Telegram (DISABLED - user requested to stop)
            # alert_data = {
            #     "token_symbol": token.symbol if token else "Unknown",
            #     "token_address": trade["token_address"],
            #     "wallet_address": wallet.address,
            #     "chain_id": trade["chain_id"],
            #     "price_usd": trade.get("price_usd", 0),
            #     "pnl_30d_usd": (stats.realized_pnl_usd + stats.unrealized_pnl_usd) if stats else 0,
            #     "best_trade_multiple": stats.best_trade_multiple if stats else 0,
            #     "earlyscore": stats.earlyscore_median if stats else 0,
            #     "tx_hash": trade.get("tx_hash", ""),
            #     "dex": trade.get("dex", ""),
            # }
            # await self.telegram.send_single_wallet_alert(alert_data)

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

    async def _execute_paper_buy(self, trade: Dict[str, Any], num_whales: int) -> None:
        """Execute paper buy on confluence detection (OPPORTUNITY-DRIVEN).

        Args:
            trade: Trade data
            num_whales: Number of whales in confluence
        """
        try:
            token_address = trade["token_address"]
            chain_id = trade["chain_id"]

            # 🎯 MEME COIN FILTER - ONLY trade meme coins!
            is_meme = self.meme_detector.is_meme_coin(
                token_address,
                chain_id,
                price_usd=trade.get("price_usd"),
                volume_24h=None,  # Will fetch from DB
                liquidity=None,   # Will fetch from DB
            )

            if not is_meme:
                logger.info(f"❌ SKIPPING NON-MEME TOKEN: {token_address[:16]}... (not a meme coin)")
                return

            logger.info(f"✅ MEME COIN CONFLUENCE DETECTED: {token_address[:16]}... with {num_whales} whales!")

            # 🛑 MAX POSITIONS LIMIT - don't overextend!
            if len(self.paper_trader.positions) >= 3:
                logger.warning(f"Max 3 positions reached, skipping paper buy for {token_address[:16]}...")
                return

            # Don't buy if we already have a position
            if token_address in self.paper_trader.positions:
                logger.debug(f"Already have position in {token_address[:16]}..., skipping paper buy")
                return

            # Get current price
            current_price = await self.price_fetcher.get_token_price(token_address, chain_id)
            if current_price == 0:
                logger.warning(f"Cannot get price for {token_address[:16]}..., skipping paper buy")
                return

            # 🚀 AGGRESSIVE POSITION SIZING - We only get 5+ whale signals now!
            # 5+ whales = MAX CONVICTION
            if num_whales >= 10:
                position_pct = 0.60  # 60% - INSANE signal (10+ whales)
                take_profit = 40.0   # Take profit at +40%
                stop_loss = -15.0    # Stop loss at -15%
            elif num_whales >= 7:
                position_pct = 0.50  # 50% - VERY STRONG signal (7-9 whales)
                take_profit = 35.0   # Take profit at +35%
                stop_loss = -15.0    # Stop loss at -15%
            else:  # 5-6 whales
                position_pct = 0.40  # 40% - Strong signal (5-6 whales)
                take_profit = 30.0   # Take profit at +30%
                stop_loss = -15.0    # Stop loss at -15%

            buy_amount = self.paper_trader.current_balance * position_pct

            if buy_amount < 10:  # Don't buy if less than $10
                logger.warning(f"Insufficient balance for paper buy (${buy_amount:.2f}), skipping")
                return

            # Execute paper buy with dynamic targets
            result = self.paper_trader.execute_buy(
                token_address=token_address,
                chain_id=chain_id,
                price_usd=current_price,
                amount_usd=buy_amount,
                reason=f"{num_whales} whale confluence",
                num_whales=num_whales,
            )

            if result["success"]:
                # Store take profit / stop loss targets in position
                self.paper_trader.positions[token_address]["take_profit_pct"] = take_profit
                self.paper_trader.positions[token_address]["stop_loss_pct"] = stop_loss
                self.paper_trader.save_to_file()

                logger.info(
                    f"💰 PAPER BUY EXECUTED\n"
                    f"   Token: {token_address[:16]}...\n"
                    f"   Whales: {num_whales} (confidence: {'VERY HIGH' if num_whales >= 4 else 'HIGH' if num_whales == 3 else 'GOOD'})\n"
                    f"   Price: ${current_price:.8f}\n"
                    f"   Amount: ${buy_amount:.2f} ({position_pct:.0%} of balance)\n"
                    f"   Take Profit: +{take_profit:.0f}% | Stop Loss: {stop_loss:.0f}%\n"
                    f"   Balance: ${self.paper_trader.current_balance:.2f}"
                )

        except Exception as e:
            logger.error(f"Error executing paper buy: {str(e)}")

    async def _execute_paper_sell(self, trade: Dict[str, Any], num_whales: int) -> None:
        """Execute paper sell on whale exit confluence (OPPORTUNITY-DRIVEN).

        Args:
            trade: Trade data
            num_whales: Number of whales selling
        """
        try:
            token_address = trade["token_address"]

            # Only sell if we have a position
            if token_address not in self.paper_trader.positions:
                return

            # Get current price
            current_price = await self.price_fetcher.get_token_price(
                token_address, trade["chain_id"]
            )
            if current_price == 0:
                logger.warning(f"Cannot get price for {token_address[:16]}..., skipping paper sell")
                return

            # Execute paper sell
            result = self.paper_trader.execute_sell(
                token_address, current_price, reason=f"WHALE EXIT ({num_whales} whales selling)"
            )

            if result:
                self.paper_trader.save_to_file()
                emoji = "✅" if result["profit_loss"] > 0 else "❌"
                logger.info(
                    f"{emoji} PAPER SELL EXECUTED\n"
                    f"   Token: {token_address[:16]}...\n"
                    f"   Whales: {num_whales}\n"
                    f"   P/L: ${result['profit_loss']:+.2f} ({result['profit_pct']:+.1f}%)\n"
                    f"   Balance: ${self.paper_trader.current_balance:.2f}"
                )

        except Exception as e:
            logger.error(f"Error executing paper sell: {str(e)}")

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

            # Send via Telegram (DISABLED - user requested to stop)
            # alert_data = {
            #     "token_symbol": token.symbol if token else "Unknown",
            #     "token_address": trade["token_address"],
            #     "chain_id": trade["chain_id"],
            #     "price_usd": trade.get("price_usd", 0),
            #     "wallets": wallet_stats_list,
            #     "avg_pnl_30d": avg_pnl,
            #     "window_minutes": settings.confluence_minutes,
            #     "liquidity_usd": 0,  # TODO: fetch from DexScreener
            #     "side": side,  # "buy" or "sell"
            # }
            # await self.telegram.send_confluence_alert(alert_data)

            # Log alert
            import json

            alert = Alert(
                ts=datetime.utcnow(),
                type="confluence",
                token_address=trade["token_address"],
                chain_id=trade["chain_id"],
                wallets_json=json.dumps(wallet_addrs),
                payload_json=str(trade),
            )
            self.db.add(alert)
            self.db.commit()

            logger.info(
                f"Sent confluence alert for {len(wallet_addrs)} wallets buying {token.symbol if token else trade['token_address'][:10]}"
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
