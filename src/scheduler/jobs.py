"""Job definitions for scheduled tasks."""

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.db import SessionLocal
from src.ingest.runners import RunnerIngestion
from src.ingest.wallet_discovery import WalletDiscovery
from src.monitoring.wallet_monitor import WalletMonitor
from src.watchlist.rules import WatchlistManager

logger = logging.getLogger(__name__)


async def runner_seed_job() -> None:
    """Fetch trending tokens from all sources (every 15 min)."""
    logger.info("Starting runner seed job")
    db = SessionLocal()

    try:
        ingestion = RunnerIngestion(db)
        results = await ingestion.run_all_sources()
        await ingestion.cleanup()

        total = sum(results.values())
        logger.info(f"Runner seed complete: {total} tokens ingested")

    except Exception as e:
        logger.error(f"Runner seed job failed: {str(e)}")
    finally:
        db.close()


async def stats_rollup_job() -> None:
    """Calculate wallet stats (hourly)."""
    logger.info("Starting stats rollup job")
    db = SessionLocal()

    try:
        from src.analytics.pnl import FIFOPnLCalculator
        from src.analytics.early import EarlyScoreCalculator
        from src.db.models import Wallet, WalletStats30D

        pnl_calc = FIFOPnLCalculator(db)
        early_calc = EarlyScoreCalculator(db)

        # Get all non-bot wallets
        wallets = db.query(Wallet).filter(Wallet.is_bot_flag == False).all()

        for wallet in wallets:
            try:
                # Calculate PnL (async method)
                pnl_data = await pnl_calc.calculate_wallet_pnl(wallet.address, days=30)
                best_multiple = pnl_calc.get_best_trade_multiple(wallet.address, days=30)

                # Calculate median EarlyScore
                median_early = early_calc.calculate_median_score(wallet.address, days=30)

                # Get or create stats record
                stats = (
                    db.query(WalletStats30D)
                    .filter(
                        WalletStats30D.wallet_address == wallet.address,
                        WalletStats30D.chain_id == wallet.chain_id,
                    )
                    .first()
                )

                if stats:
                    from datetime import datetime

                    stats.realized_pnl_usd = pnl_data["realized_pnl"]
                    stats.unrealized_pnl_usd = pnl_data["unrealized_pnl"]
                    stats.best_trade_multiple = best_multiple
                    stats.earlyscore_median = median_early
                    stats.last_update = datetime.utcnow()
                else:
                    from src.db.models import Trade
                    from datetime import datetime, timedelta
                    from sqlalchemy import and_, func

                    # Count trades
                    since = datetime.utcnow() - timedelta(days=30)
                    trade_count = (
                        db.query(func.count(Trade.tx_hash))
                        .filter(
                            and_(
                                Trade.wallet_address == wallet.address,
                                Trade.ts >= since,
                            )
                        )
                        .scalar()
                        or 0
                    )

                    stats = WalletStats30D(
                        wallet_address=wallet.address,
                        chain_id=wallet.chain_id,
                        trades_count=trade_count,
                        realized_pnl_usd=pnl_data["realized_pnl"],
                        unrealized_pnl_usd=pnl_data["unrealized_pnl"],
                        best_trade_multiple=best_multiple,
                        earlyscore_median=median_early,
                    )
                    db.add(stats)

            except Exception as e:
                logger.error(f"Error processing wallet {wallet.address}: {str(e)}")
                continue

        db.commit()
        logger.info(f"Stats rollup complete for {len(wallets)} wallets")

    except Exception as e:
        logger.error(f"Stats rollup job failed: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def wallet_discovery_job() -> None:
    """Discover wallets from trending tokens (every hour)."""
    logger.info("Starting wallet discovery job")
    db = SessionLocal()

    try:
        discovery = WalletDiscovery(db)
        wallets_found = await discovery.discover_from_seed_tokens(hours_back=24)
        logger.info(f"Wallet discovery complete: {wallets_found} wallets found")

    except Exception as e:
        logger.error(f"Wallet discovery job failed: {str(e)}")
    finally:
        db.close()


async def whale_discovery_job() -> None:
    """Enhanced whale discovery - Find wallets making $10k+ trades (every 30 min)."""
    logger.info("Starting enhanced whale discovery job")
    db = SessionLocal()

    try:
        from src.db.models import SeedToken, Wallet, Trade
        from src.clients.alchemy import AlchemyClient
        from datetime import datetime

        # Get top trending tokens with high liquidity (INCREASED FOR MAX SPEED)
        trending_tokens = (
            db.query(SeedToken)
            .filter(SeedToken.liquidity_usd > 50000)  # Lowered to $50k for more coverage
            .order_by(SeedToken.volume_24h_usd.desc())
            .limit(30)  # Increased to top 30 tokens
            .all()
        )

        logger.info(f"Analyzing {len(trending_tokens)} high-liquidity tokens for whale trades")

        client = AlchemyClient()
        whale_wallets_found = 0
        large_trades_found = 0

        for token in trending_tokens:
            try:
                # Get all transfers for this token (INCREASED LIMIT FOR MAX SPEED)
                transfers = await client.get_token_transfers(
                    token.token_address,
                    token.chain_id,
                    limit=100  # Doubled to catch more whales
                )

                # Filter for LARGE transfers ($10k+)
                large_transfers = [
                    t for t in transfers
                    if t.get("value_usd", 0) >= 10000 and t.get("type") == "buy"
                ]

                for transfer in large_transfers:
                    wallet_address = transfer.get("from_address")
                    value_usd = transfer.get("value_usd", 0)

                    # Check if wallet already exists
                    existing = db.query(Wallet).filter(
                        Wallet.address == wallet_address
                    ).first()

                    if not existing:
                        # New whale discovered!
                        wallet = Wallet(
                            address=wallet_address,
                            chain_id=token.chain_id,
                            first_seen_at=datetime.utcnow(),
                        )
                        db.add(wallet)
                        db.flush()
                        whale_wallets_found += 1
                        logger.info(f"🐋 NEW WHALE: {wallet_address[:16]}... bought ${value_usd:,.0f}")

                    # Record the trade
                    tx_hash = transfer.get("tx_hash")
                    existing_trade = db.query(Trade).filter(Trade.tx_hash == tx_hash).first()

                    if not existing_trade:
                        trade = Trade(
                            tx_hash=tx_hash,
                            ts=transfer.get("timestamp", datetime.utcnow()),
                            chain_id=token.chain_id,
                            wallet_address=wallet_address,
                            token_address=token.token_address,
                            side="buy",
                            qty_token=float(transfer.get("amount", 0)),
                            price_usd=float(transfer.get("price_usd", 0)),
                            usd_value=float(value_usd),
                            venue=transfer.get("dex"),
                        )
                        db.add(trade)
                        db.flush()
                        large_trades_found += 1

                db.commit()
                await asyncio.sleep(0.1)  # Minimal rate limiting for max speed

            except Exception as e:
                logger.error(f"Error processing {token.symbol}: {str(e)}")
                db.rollback()
                continue

        logger.info(f"Enhanced whale discovery complete: {whale_wallets_found} new whales, {large_trades_found} large trades ($10k+ each)")

    except Exception as e:
        logger.error(f"Enhanced whale discovery job failed: {str(e)}")
    finally:
        db.close()


async def wallet_monitoring_job() -> None:
    """Monitor watchlist wallets for trades (every 5 min)."""
    logger.info("Starting wallet monitoring job")
    db = SessionLocal()

    try:
        monitor = WalletMonitor(db)
        alerts_sent = await monitor.monitor_watchlist_wallets()
        logger.info(f"Wallet monitoring complete: {alerts_sent} alerts sent")

    except Exception as e:
        logger.error(f"Wallet monitoring job failed: {str(e)}")
    finally:
        db.close()


async def watchlist_maintenance_job() -> None:
    """Nightly watchlist add/remove (daily at 2 AM UTC)."""
    logger.info("Starting watchlist maintenance job")
    db = SessionLocal()

    try:
        manager = WatchlistManager(db)
        stats = manager.run_nightly_maintenance()
        logger.info(f"Watchlist maintenance complete: {stats}")

    except Exception as e:
        logger.error(f"Watchlist maintenance job failed: {str(e)}")
    finally:
        db.close()


async def performance_evaluation_job() -> None:
    """Evaluate system performance and self-score (every hour)."""
    logger.info("Starting performance self-evaluation")
    db = SessionLocal()

    try:
        from src.analytics.performance_tracker import log_performance_summary

        log_performance_summary(db)
        logger.info("Performance evaluation complete - check logs for score")

    except Exception as e:
        logger.error(f"Performance evaluation job failed: {str(e)}")
    finally:
        db.close()


def setup_scheduler() -> AsyncIOScheduler:
    """Set up and configure the job scheduler.

    Returns:
        Configured scheduler
    """
    scheduler = AsyncIOScheduler()

    # Runner seed - every 5 minutes (max speed)
    scheduler.add_job(
        runner_seed_job,
        trigger=IntervalTrigger(minutes=5),
        id="runner_seed",
        name="Fetch trending tokens",
        replace_existing=True,
    )

    # Wallet discovery - every 10 minutes (max speed)
    scheduler.add_job(
        wallet_discovery_job,
        trigger=IntervalTrigger(minutes=10),
        id="wallet_discovery",
        name="Discover wallets from trending tokens",
        replace_existing=True,
    )

    # Enhanced whale discovery - every 5 minutes (max speed)
    scheduler.add_job(
        whale_discovery_job,
        trigger=IntervalTrigger(minutes=5),
        id="whale_discovery",
        name="Find whales making $10k+ trades",
        replace_existing=True,
    )

    # Wallet monitoring - every 2 minutes (max speed)
    scheduler.add_job(
        wallet_monitoring_job,
        trigger=IntervalTrigger(minutes=2),
        id="wallet_monitoring",
        name="Monitor watchlist wallets for trades",
        replace_existing=True,
    )

    # Stats rollup - every 15 minutes (frequent updates)
    scheduler.add_job(
        stats_rollup_job,
        trigger=IntervalTrigger(minutes=15),
        id="stats_rollup",
        name="Calculate wallet stats",
        replace_existing=True,
    )

    # Watchlist maintenance - daily at 2 AM UTC
    scheduler.add_job(
        watchlist_maintenance_job,
        trigger=CronTrigger(hour=2, minute=0),
        id="watchlist_maintenance",
        name="Nightly watchlist maintenance",
        replace_existing=True,
    )

    logger.info("Scheduler configured with jobs (MAX SPEED MODE):")
    logger.info("  - runner_seed: every 5 minutes")
    logger.info("  - wallet_discovery: every 10 minutes")
    logger.info("  - whale_discovery: every 5 minutes ($10k+ trades)")
    logger.info("  - wallet_monitoring: every 2 minutes")
    logger.info("  - stats_rollup: every 15 minutes")
    logger.info("  - watchlist_maintenance: daily at 2:00 AM UTC")

    return scheduler
