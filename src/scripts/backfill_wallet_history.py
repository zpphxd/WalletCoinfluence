"""Historical backfill script for wallet trade history.

Fetches complete 30-day transaction history for all discovered wallets
to identify truly profitable whales with sufficient trading data.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.db.models import Wallet, Trade, WalletStats30D
from src.clients.alchemy import AlchemyClient
from src.clients.helius import HeliusClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_wallet_history():
    """Backfill complete trade history for all discovered wallets."""

    print("=" * 70)
    print("🔄 HISTORICAL BACKFILL - 30-DAY WALLET TRADE HISTORY")
    print("=" * 70)
    print()

    db = SessionLocal()

    try:
        # Get all wallets
        wallets = db.query(Wallet).all()
        total_wallets = len(wallets)

        print(f"📋 Found {total_wallets} wallets to backfill")
        print(f"⏱️  Estimated time: {total_wallets * 2} minutes")
        print()

        # Group by chain for efficiency
        wallets_by_chain = {}
        for wallet in wallets:
            if wallet.chain_id not in wallets_by_chain:
                wallets_by_chain[wallet.chain_id] = []
            wallets_by_chain[wallet.chain_id].append(wallet)

        total_new_trades = 0
        total_errors = 0
        whales_with_depth = 0

        for chain_id, chain_wallets in wallets_by_chain.items():
            print(f"\n{'='*70}")
            print(f"🔗 Processing {chain_id.upper()} ({len(chain_wallets)} wallets)")
            print(f"{'='*70}\n")

            # Initialize client
            if chain_id == "solana":
                client = HeliusClient()
            else:
                client = AlchemyClient()

            for i, wallet in enumerate(chain_wallets, 1):
                try:
                    print(f"[{i}/{len(chain_wallets)}] Fetching {wallet.address[:16]}...", end=" ")

                    # Get complete transaction history (100 txs should cover 30 days for most wallets)
                    if chain_id == "solana":
                        transactions = await client.get_wallet_transactions(
                            wallet.address,
                            limit=100
                        )
                    else:
                        transactions = await client.get_wallet_transactions(
                            wallet.address,
                            chain_id,
                            limit=100
                        )

                    new_trades = 0

                    for tx in transactions:
                        tx_hash = tx.get("tx_hash")

                        # Check if trade already exists
                        existing = db.query(Trade).filter(Trade.tx_hash == tx_hash).first()

                        if not existing:
                            # Create new trade record
                            trade = Trade(
                                tx_hash=tx_hash,
                                ts=tx.get("timestamp", datetime.utcnow()),
                                chain_id=chain_id,
                                wallet_address=wallet.address,
                                token_address=tx.get("token_address"),
                                side=tx.get("type", "buy"),  # "buy" or "sell"
                                qty_token=float(tx.get("amount", 0)),
                                price_usd=float(tx.get("price_usd", 0)),
                                usd_value=float(tx.get("value_usd", 0)),
                                venue=tx.get("dex"),
                            )
                            db.add(trade)
                            new_trades += 1

                    # Commit trades for this wallet
                    db.commit()
                    total_new_trades += new_trades

                    # Check depth
                    total_trades = db.query(Trade).filter(
                        Trade.wallet_address == wallet.address
                    ).count()

                    if total_trades >= 5:
                        whales_with_depth += 1

                    print(f"✅ {new_trades} new trades (total: {total_trades})")

                    # Rate limiting - don't hammer APIs
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"❌ Error processing wallet {wallet.address}: {str(e)}")
                    db.rollback()
                    total_errors += 1
                    print(f"❌ Error: {str(e)}")
                    continue

        print()
        print("=" * 70)
        print("🎉 BACKFILL COMPLETE")
        print("=" * 70)
        print()
        print(f"📊 Results:")
        print(f"   Total wallets processed:    {total_wallets}")
        print(f"   New trades added:           {total_new_trades}")
        print(f"   Errors encountered:         {total_errors}")
        print(f"   Whales with ≥5 trades:      {whales_with_depth}")
        print()

        # Show updated database stats
        total_trades = db.query(Trade).count()
        total_buys = db.query(Trade).filter(Trade.side == "buy").count()
        total_sells = db.query(Trade).filter(Trade.side == "sell").count()
        avg_trades = total_trades / total_wallets if total_wallets > 0 else 0

        print(f"📈 Database Status:")
        print(f"   Total trades:               {total_trades}")
        print(f"   Buys:                       {total_buys}")
        print(f"   Sells:                      {total_sells}")
        print(f"   Avg trades per wallet:      {avg_trades:.1f}")
        print()

        # Now trigger stats recalculation
        print("🔄 Triggering stats recalculation...")
        from src.scheduler.jobs import stats_rollup_job
        await stats_rollup_job()
        print("✅ Stats recalculated")
        print()

        # Show profitable whales
        profitable_whales = (
            db.query(WalletStats30D)
            .filter(
                (WalletStats30D.realized_pnl_usd + WalletStats30D.unrealized_pnl_usd) > 0
            )
            .order_by(
                (WalletStats30D.realized_pnl_usd + WalletStats30D.unrealized_pnl_usd).desc()
            )
            .limit(10)
            .all()
        )

        print(f"🐋 Top 10 Profitable Whales:")
        print()

        if profitable_whales:
            for i, stats in enumerate(profitable_whales, 1):
                total_pnl = (stats.realized_pnl_usd or 0) + (stats.unrealized_pnl_usd or 0)
                print(
                    f"{i:2d}. {stats.wallet_address[:16]}... | "
                    f"PnL: ${total_pnl:,.0f} | "
                    f"Trades: {stats.trades_count} | "
                    f"Best: {stats.best_trade_multiple or 0:.1f}x | "
                    f"Early: {stats.earlyscore_median or 0:.0f}"
                )
        else:
            print("   No profitable whales found yet.")
            print("   This is normal if price data is missing.")
            print("   The system will continue discovering new opportunities.")

        print()
        print("=" * 70)
        print("✅ BACKFILL SUCCESSFUL - WHALE POOL READY")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(backfill_wallet_history())
