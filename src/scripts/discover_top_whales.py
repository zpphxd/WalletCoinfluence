#!/usr/bin/env python3
"""
Discover top-performing whale wallets from on-chain data.

This script analyzes trending tokens to find wallets with:
- Large position sizes ($10k+ trades)
- Consistent winning patterns
- Early entry timing (high EarlyScore)
- Multiple profitable trades

It adds the best 20 whales to the custom watchlist.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.db.session import SessionLocal
from src.db.models import (
    Wallet,
    Trade,
    Token,
    SeedToken,
    WalletStats30D,
    CustomWatchlistWallet,
)
from src.clients.alchemy import AlchemyClient
from src.analytics.pnl import FIFOPnLCalculator
from src.analytics.early import EarlyScoreCalculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def discover_whale_wallets(db: Session, min_trade_size_usd: float = 10000, limit: int = 20):
    """
    Discover top whale wallets from trending tokens.

    Strategy:
    1. Get trending tokens from last 7 days
    2. For each token, find large buyers ($10k+ trades)
    3. Analyze their full trading history
    4. Rank by profitability and consistency
    5. Add top 20 to custom watchlist

    Args:
        db: Database session
        min_trade_size_usd: Minimum trade size to qualify as whale
        limit: Number of whales to add
    """
    logger.info("🔍 DISCOVERING TOP WHALE WALLETS\n")

    # Get trending tokens from last 7 days with good liquidity
    cutoff = datetime.utcnow() - timedelta(days=7)
    trending_tokens = (
        db.query(SeedToken, Token)
        .join(Token, SeedToken.token_address == Token.token_address)
        .filter(
            SeedToken.spotted_at >= cutoff,
            Token.liquidity_usd > 100000,  # $100k+ liquidity
        )
        .order_by(SeedToken.spotted_at.desc())
        .limit(100)  # Top 100 trending tokens
        .all()
    )

    logger.info(f"📊 Analyzing {len(trending_tokens)} trending tokens\n")

    # Track discovered whales
    whale_candidates = {}
    alchemy = AlchemyClient()
    pnl_calc = FIFOPnLCalculator(db)
    early_calc = EarlyScoreCalculator(db)

    # Analyze each trending token
    for seed_token, token in trending_tokens:
        try:
            logger.info(f"🔍 Analyzing {token.symbol} ({token.token_address[:10]}...)")

            # Get token transfers (buyers)
            transfers = await alchemy.get_token_transfers(
                token.token_address,
                seed_token.chain_id,
                limit=500,  # Deep scan
            )

            # Find large buyers
            for transfer in transfers:
                if transfer.get("type") != "buy":
                    continue

                wallet_address = transfer.get("wallet_address")
                value_usd = transfer.get("value_usd", 0)

                # Must be large trade ($10k+)
                if value_usd < min_trade_size_usd:
                    continue

                # Track this wallet
                if wallet_address not in whale_candidates:
                    whale_candidates[wallet_address] = {
                        "address": wallet_address,
                        "chain_id": seed_token.chain_id,
                        "large_trades": 0,
                        "total_volume": 0,
                        "first_seen": transfer.get("timestamp", datetime.utcnow()),
                        "tokens_traded": set(),
                    }

                whale_candidates[wallet_address]["large_trades"] += 1
                whale_candidates[wallet_address]["total_volume"] += value_usd
                whale_candidates[wallet_address]["tokens_traded"].add(token.token_address)

                logger.info(f"   🐋 Found whale: {wallet_address[:16]}... (${value_usd:,.0f} buy)")

            await asyncio.sleep(0.2)  # Rate limiting

        except Exception as e:
            logger.error(f"   ❌ Error analyzing {token.symbol}: {str(e)}")
            continue

    logger.info(f"\n\n📊 ANALYSIS COMPLETE\n")
    logger.info(f"   Total whale candidates: {len(whale_candidates)}\n")

    # Filter and rank whales
    qualified_whales = []
    for wallet_data in whale_candidates.values():
        # Must have multiple large trades
        if wallet_data["large_trades"] < 2:
            continue

        # Must trade multiple tokens (not one-hit wonder)
        if len(wallet_data["tokens_traded"]) < 2:
            continue

        # Check if wallet exists in database
        wallet = (
            db.query(Wallet)
            .filter(
                Wallet.address == wallet_data["address"],
                Wallet.chain_id == wallet_data["chain_id"],
            )
            .first()
        )

        # Create wallet if it doesn't exist
        if not wallet:
            wallet = Wallet(
                address=wallet_data["address"],
                chain_id=wallet_data["chain_id"],
                first_seen_at=wallet_data["first_seen"],
            )
            db.add(wallet)
            db.flush()

        # Calculate stats
        pnl_data = await pnl_calc.calculate_wallet_pnl(wallet.address, days=30)
        early_score = early_calc.calculate_median_score(wallet.address, days=30)

        # Calculate composite score
        # 40% PnL, 30% Volume, 20% Win Rate, 10% EarlyScore
        pnl_score = max(0, pnl_data["realized_pnl"] + pnl_data["unrealized_pnl"])
        volume_score = wallet_data["total_volume"]
        win_rate = (
            (pnl_data["winning_trades"] / pnl_data["total_trades"])
            if pnl_data["total_trades"] > 0
            else 0
        )
        early_score_normalized = (early_score or 0) / 100

        composite_score = (
            (pnl_score * 0.4)
            + (volume_score * 0.3)
            + (win_rate * 1000 * 0.2)
            + (early_score_normalized * 1000 * 0.1)
        )

        qualified_whales.append({
            **wallet_data,
            "pnl": pnl_score,
            "win_rate": win_rate,
            "early_score": early_score,
            "composite_score": composite_score,
        })

    # Sort by composite score
    qualified_whales.sort(key=lambda x: x["composite_score"], reverse=True)

    logger.info(f"\n🏆 TOP {limit} WHALES DISCOVERED:\n")
    logger.info("=" * 80)

    # Add top whales to custom watchlist
    added_count = 0
    for idx, whale in enumerate(qualified_whales[:limit], 1):
        # Check if already in custom watchlist
        existing = (
            db.query(CustomWatchlistWallet)
            .filter(
                CustomWatchlistWallet.address == whale["address"],
                CustomWatchlistWallet.chain_id == whale["chain_id"],
            )
            .first()
        )

        if existing:
            logger.info(f"{idx}. {whale['address'][:16]}... (Already in watchlist)")
            continue

        # Add to custom watchlist
        custom_whale = CustomWatchlistWallet(
            address=whale["address"],
            chain_id=whale["chain_id"],
            added_at=datetime.utcnow(),
            added_by="auto_discovery",
            label=f"Auto-Discovered Whale (Rank #{idx})",
            notes=(
                f"Large Trades: {whale['large_trades']} | "
                f"Volume: ${whale['total_volume']:,.0f} | "
                f"PnL: ${whale['pnl']:,.0f} | "
                f"Win Rate: {whale['win_rate']*100:.1f}% | "
                f"EarlyScore: {whale['early_score']:.1f} | "
                f"Tokens: {len(whale['tokens_traded'])}"
            ),
            is_active=True,
        )
        db.add(custom_whale)
        added_count += 1

        logger.info(
            f"{idx}. {whale['address'][:16]}... | "
            f"Volume: ${whale['total_volume']:,.0f} | "
            f"PnL: ${whale['pnl']:,.0f} | "
            f"Win: {whale['win_rate']*100:.1f}% | "
            f"Early: {whale['early_score']:.0f}"
        )

    db.commit()

    logger.info("\n" + "=" * 80)
    logger.info(f"\n✅ ADDED {added_count} NEW WHALES TO CUSTOM WATCHLIST\n")

    return added_count


async def main():
    """Main execution."""
    db = SessionLocal()
    try:
        added = await discover_whale_wallets(db, min_trade_size_usd=10000, limit=20)
        logger.info(f"\n🎉 Discovery complete! {added} whales added to tracking.\n")
    except Exception as e:
        logger.error(f"\n❌ Discovery failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
