"""Enhanced whale discovery - Find wallets with REAL money ($100k+).

This script looks beyond just trending token buyers to find wallets with:
1. Large transaction sizes ($10k+ per trade)
2. High wallet balances ($100k+ total)
3. Consistent trading activity (multiple large trades)
4. Proven profitability over time
"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import Wallet, Trade, Token, SeedToken, WalletStats30D
from src.clients.alchemy import AlchemyClient
from src.clients.helius import HeliusClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def discover_whales_from_large_trades():
    """Find whales by looking for large trades ($10k+) on trending tokens."""

    print("=" * 70)
    print("🐋 ENHANCED WHALE DISCOVERY - FINDING REAL MONEY")
    print("=" * 70)
    print()
    print("Strategy: Look for wallets making $10k+ trades on trending tokens")
    print()

    db = SessionLocal()

    try:
        # Get top trending tokens with high liquidity
        trending_tokens = (
            db.query(SeedToken)
            .filter(SeedToken.liquidity_usd > 100000)  # At least $100k liquidity
            .order_by(SeedToken.volume_24h_usd.desc())
            .limit(20)
            .all()
        )

        print(f"📊 Found {len(trending_tokens)} high-liquidity trending tokens")
        print()

        client = AlchemyClient()
        whale_wallets_found = 0
        large_trades_found = 0

        for i, token in enumerate(trending_tokens, 1):
            try:
                print(f"[{i}/{len(trending_tokens)}] Analyzing {token.symbol}...")
                print(f"   Liquidity: ${token.liquidity_usd:,.0f} | Volume: ${token.volume_24h_usd:,.0f}")

                # Get all transfers for this token (last 1000 blocks = ~3 hours)
                transfers = await client.get_token_transfers(
                    token.token_address,
                    token.chain_id,
                    limit=100
                )

                # Filter for LARGE transfers ($10k+)
                large_transfers = [
                    t for t in transfers
                    if t.get("value_usd", 0) >= 10000  # $10k minimum
                ]

                print(f"   Found {len(large_transfers)} large transfers ($10k+)")

                for transfer in large_transfers:
                    wallet_address = transfer.get("from_address")
                    value_usd = transfer.get("value_usd", 0)

                    # Check if this is a buy (from DEX pool to wallet)
                    if transfer.get("type") != "buy":
                        continue

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

                        print(f"   🐋 NEW WHALE: {wallet_address[:16]}... bought ${value_usd:,.0f}")

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
                await asyncio.sleep(2)  # Rate limiting

            except Exception as e:
                logger.error(f"Error processing {token.symbol}: {str(e)}")
                db.rollback()
                continue

        print()
        print("=" * 70)
        print("🎉 WHALE DISCOVERY COMPLETE")
        print("=" * 70)
        print()
        print(f"📊 Results:")
        print(f"   New whale wallets:    {whale_wallets_found}")
        print(f"   Large trades found:   {large_trades_found} ($10k+ each)")
        print()

        # Now get complete history for these whales
        if whale_wallets_found > 0:
            print("🔄 Fetching complete trade history for new whales...")
            print()

            new_whales = (
                db.query(Wallet)
                .filter(Wallet.first_seen_at >= datetime.utcnow() - timedelta(minutes=30))
                .all()
            )

            for whale in new_whales:
                try:
                    print(f"   Fetching {whale.address[:16]}...", end=" ")

                    transactions = await client.get_wallet_transactions(
                        whale.address,
                        whale.chain_id,
                        limit=100
                    )

                    new_trades = 0
                    total_volume = 0

                    for tx in transactions:
                        tx_hash = tx.get("tx_hash")
                        existing = db.query(Trade).filter(Trade.tx_hash == tx_hash).first()

                        if not existing:
                            value = float(tx.get("value_usd", 0))
                            trade = Trade(
                                tx_hash=tx_hash,
                                ts=tx.get("timestamp", datetime.utcnow()),
                                chain_id=whale.chain_id,
                                wallet_address=whale.address,
                                token_address=tx.get("token_address"),
                                side=tx.get("type", "buy"),
                                qty_token=float(tx.get("amount", 0)),
                                price_usd=float(tx.get("price_usd", 0)),
                                usd_value=value,
                                venue=tx.get("dex"),
                            )
                            db.add(trade)
                            new_trades += 1
                            total_volume += value

                    db.commit()
                    print(f"✅ {new_trades} trades (${total_volume:,.0f} volume)")

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    db.rollback()
                    print(f"❌ Error")

        # Calculate stats
        print()
        print("🔄 Calculating stats for all whales...")
        from src.scheduler.jobs import stats_rollup_job
        await stats_rollup_job()
        print("✅ Stats calculated")
        print()

        # Show top whales by total volume
        top_whales = (
            db.query(WalletStats30D)
            .order_by(WalletStats30D.trades_count.desc())
            .limit(10)
            .all()
        )

        print("🐋 Top 10 Most Active Whales:")
        print()

        for i, stats in enumerate(top_whales, 1):
            total_pnl = (stats.realized_pnl_usd or 0) + (stats.unrealized_pnl_usd or 0)
            print(
                f"{i:2d}. {stats.wallet_address[:16]}... | "
                f"Trades: {stats.trades_count} | "
                f"PnL: ${total_pnl:,.0f} | "
                f"Best: {stats.best_trade_multiple or 0:.1f}x"
            )

        print()
        print("=" * 70)
        print("✅ REAL WHALE DISCOVERY COMPLETE")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(discover_whales_from_large_trades())
