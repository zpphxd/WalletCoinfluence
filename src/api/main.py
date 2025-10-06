"""FastAPI backend for Alpha Wallet Scout web dashboard."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.session import SessionLocal
from src.db.models import (
    Wallet,
    Trade,
    Token,
    SeedToken,
    WalletStats30D,
    CustomWatchlistWallet,
    Alert,
)
from src.api.watchlist import CustomWatchlistManager
from src.analytics.paper_trading import PaperTradingTracker
from src.utils.price_fetcher import MultiSourcePriceFetcher

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Alpha Wallet Scout API",
    description="Whale tracking and paper trading API",
    version="1.0.0",
)

# Enable CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React/Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get database session
def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic models for request/response
class WatchlistWalletCreate(BaseModel):
    address: str
    chain_id: str = "ethereum"
    label: Optional[str] = None
    notes: Optional[str] = None


class WatchlistWalletUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None


class WatchlistWalletResponse(BaseModel):
    address: str
    chain_id: str
    label: Optional[str]
    notes: Optional[str]
    added_at: Optional[str]
    is_active: bool
    stats: Optional[Dict[str, Any]] = None


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================


@app.get("/")
async def root():
    """API status."""
    return {
        "status": "ok",
        "message": "Alpha Wallet Scout API",
        "version": "1.0.0",
    }


@app.get("/api/stats/overview")
async def get_overview_stats(db: Session = Depends(get_db)):
    """Get dashboard overview statistics."""
    try:
        # Count stats
        total_whales = db.query(Wallet).count()
        total_trades = db.query(Trade).count()
        total_tokens = db.query(Token).count()
        total_alerts = db.query(Alert).count()

        # Paper trading status
        try:
            paper_trader = PaperTradingTracker.load_from_file()
            if paper_trader:
                paper_stats = {
                    "balance": paper_trader.current_balance,
                    "starting_balance": paper_trader.starting_balance,
                    "total_profit": paper_trader.total_profit,
                    "total_loss": paper_trader.total_loss,
                    "win_count": paper_trader.win_count,
                    "loss_count": paper_trader.loss_count,
                    "open_positions": len(paper_trader.positions),
                }
            else:
                paper_stats = None
        except:
            paper_stats = None

        # Profitable whales count
        profitable_whales = (
            db.query(WalletStats30D)
            .filter(WalletStats30D.unrealized_pnl_usd > 500)
            .count()
        )

        # Recent confluence alerts (last 24h)
        since = datetime.utcnow() - timedelta(hours=24)
        recent_alerts = (
            db.query(Alert)
            .filter(Alert.ts >= since, Alert.type == "confluence")
            .count()
        )

        # Custom watchlist stats with tier classification
        custom_whales = db.query(CustomWatchlistWallet).filter(
            CustomWatchlistWallet.is_active == True
        ).all()

        custom_watchlist_stats = {
            "total": len(custom_whales),
            "tier1_mega": sum(1 for w in custom_whales if "10M+" in (w.notes or "") or "579%" in (w.notes or "") or "$14.8M" in (w.notes or "") or "$12M" in (w.notes or "")),
            "tier2_strong": sum(1 for w in custom_whales if "$7.2M" in (w.notes or "") or "$489k" in (w.notes or "")),
            "tier3_learning": sum(1 for w in custom_whales if "$29k" in (w.notes or "") or "$21k" in (w.notes or "") or "$14k" in (w.notes or "")),
            "ethereum": sum(1 for w in custom_whales if w.chain_id == "ethereum"),
            "solana": sum(1 for w in custom_whales if w.chain_id == "solana"),
        }

        return {
            "total_whales": total_whales,
            "profitable_whales": profitable_whales,
            "total_trades": total_trades,
            "total_tokens": total_tokens,
            "total_alerts": total_alerts,
            "recent_alerts_24h": recent_alerts,
            "paper_trading": paper_stats,
            "custom_watchlist": custom_watchlist_stats,
        }

    except Exception as e:
        logger.error(f"Error getting overview stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/whales/top")
async def get_top_whales(limit: int = 20, db: Session = Depends(get_db)):
    """Get top performing whales."""
    try:
        whales = (
            db.query(Wallet, WalletStats30D)
            .join(WalletStats30D, Wallet.address == WalletStats30D.wallet_address)
            .filter(WalletStats30D.unrealized_pnl_usd > 0)
            .order_by(WalletStats30D.unrealized_pnl_usd.desc())
            .limit(limit)
            .all()
        )

        results = []
        for wallet, stats in whales:
            results.append(
                {
                    "address": wallet.address,
                    "chain_id": wallet.chain_id,
                    "first_seen": wallet.first_seen_at.isoformat() if wallet.first_seen_at else None,
                    "trades_count": stats.trades_count,
                    "realized_pnl_usd": stats.realized_pnl_usd,
                    "unrealized_pnl_usd": stats.unrealized_pnl_usd,
                    "best_trade_multiple": stats.best_trade_multiple,
                    "earlyscore_median": stats.earlyscore_median,
                }
            )

        return {"whales": results}

    except Exception as e:
        logger.error(f"Error getting top whales: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades/recent")
async def get_recent_trades(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent trades from all whales."""
    try:
        trades = (
            db.query(Trade, Token)
            .join(Token, Trade.token_address == Token.token_address)
            .order_by(Trade.ts.desc())
            .limit(limit)
            .all()
        )

        results = []
        for trade, token in trades:
            results.append(
                {
                    "tx_hash": trade.tx_hash,
                    "timestamp": trade.ts.isoformat() if trade.ts else None,
                    "chain_id": trade.chain_id,
                    "wallet_address": trade.wallet_address,
                    "token_address": trade.token_address,
                    "token_symbol": token.symbol,
                    "side": trade.side,
                    "qty_token": trade.qty_token,
                    "price_usd": trade.price_usd,
                    "usd_value": trade.usd_value,
                    "venue": trade.venue,
                }
            )

        return {"trades": results}

    except Exception as e:
        logger.error(f"Error getting recent trades: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tokens/trending")
async def get_trending_tokens(limit: int = 20, db: Session = Depends(get_db)):
    """Get trending tokens being bought by whales."""
    try:
        # Get tokens with most whale buys in last 24h
        since = datetime.utcnow() - timedelta(hours=24)

        trending = (
            db.query(
                Trade.token_address,
                Token.symbol,
                Token.last_price_usd,
                func.count(func.distinct(Trade.wallet_address)).label("whale_count"),
                func.sum(Trade.usd_value).label("total_volume"),
            )
            .join(Token, Trade.token_address == Token.token_address)
            .filter(Trade.ts >= since, Trade.side == "buy")
            .group_by(Trade.token_address, Token.symbol, Token.last_price_usd)
            .order_by(func.count(func.distinct(Trade.wallet_address)).desc())
            .limit(limit)
            .all()
        )

        results = []
        for token_addr, symbol, price, whale_count, volume in trending:
            results.append(
                {
                    "token_address": token_addr,
                    "symbol": symbol,
                    "price_usd": price,
                    "whale_count": whale_count,
                    "total_volume_24h": volume,
                }
            )

        return {"trending_tokens": results}

    except Exception as e:
        logger.error(f"Error getting trending tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts/recent")
async def get_recent_alerts(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent confluence alerts with enriched data."""
    try:
        alerts = (
            db.query(Alert, Token)
            .outerjoin(Token, Alert.token_address == Token.token_address)
            .filter(Alert.type == "confluence")
            .order_by(Alert.ts.desc())
            .limit(limit)
            .all()
        )

        results = []
        for alert, token in alerts:
            # Parse wallet addresses and payload from JSON
            import json
            try:
                wallet_addresses = json.loads(alert.wallets_json) if alert.wallets_json else []
            except:
                wallet_addresses = []

            # Parse payload for detailed trade info
            try:
                payload = json.loads(alert.payload_json) if alert.payload_json else {}
            except:
                payload = {}

            # Use wallet_details from payload if available, otherwise get from stats
            whale_stats = payload.get("wallet_details", [])
            if not whale_stats:
                # Fallback: Get wallet stats for confluence participants
                whale_stats = []
                for wallet_addr in wallet_addresses:
                    stats = (
                        db.query(WalletStats30D)
                        .filter(
                            WalletStats30D.wallet_address == wallet_addr,
                            WalletStats30D.chain_id == alert.chain_id,
                        )
                        .first()
                    )
                    if stats:
                        whale_stats.append({
                            "address": wallet_addr[:10] + "...",
                            "pnl_30d": stats.realized_pnl_usd + stats.unrealized_pnl_usd,
                            "best_trade": stats.best_trade_multiple,
                            "early_score": stats.earlyscore_median,
                            "purchase_amount_usd": 0,
                        })
            else:
                # Format addresses in whale_stats
                for whale in whale_stats:
                    whale["address"] = whale.get("address", "")[:10] + "..."

            # Get current token price (already cached with 60s TTL, minimal API impact)
            current_price = token.last_price_usd if token else 0

            results.append(
                {
                    "id": alert.id,
                    "timestamp": alert.ts.isoformat() if alert.ts else None,
                    "type": alert.type,
                    "token_address": alert.token_address,
                    "token_symbol": payload.get("token_symbol") or (token.symbol if token else "Unknown"),
                    "token_price": current_price,
                    "token_price_at_alert": payload.get("token_price", 0),
                    "chain_id": alert.chain_id,
                    "whale_count": len(wallet_addresses),
                    "whales": whale_stats,
                    "side": payload.get("side", "buy"),
                }
            )

        return {"alerts": results}

    except Exception as e:
        logger.error(f"Error getting recent alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/status")
async def get_paper_trading_status():
    """Get current paper trading status and positions."""
    try:
        paper_trader = PaperTradingTracker.load_from_file()

        if not paper_trader:
            return {
                "active": False,
                "message": "No paper trading data available",
            }

        # Get current position values
        price_fetcher = MultiSourcePriceFetcher()
        positions_with_current = []

        for token_addr, pos in paper_trader.positions.items():
            try:
                current_price = await price_fetcher.get_token_price(
                    token_addr, pos["chain_id"]
                )
                current_value = pos["qty"] * current_price
                profit_loss = current_value - pos["cost_basis"]
                profit_pct = (profit_loss / pos["cost_basis"]) * 100

                positions_with_current.append(
                    {
                        "token_address": token_addr,
                        "chain_id": pos["chain_id"],
                        "entry_price": pos["entry_price"],
                        "current_price": current_price,
                        "qty": pos["qty"],
                        "cost_basis": pos["cost_basis"],
                        "current_value": current_value,
                        "profit_loss": profit_loss,
                        "profit_pct": profit_pct,
                        "bought_at": pos["bought_at"].isoformat() if pos.get("bought_at") else None,
                    }
                )
            except:
                pass

        total_open_value = sum(p["current_value"] for p in positions_with_current)
        total_portfolio = paper_trader.current_balance + total_open_value
        roi = (
            (total_portfolio - paper_trader.starting_balance)
            / paper_trader.starting_balance
        ) * 100

        return {
            "active": True,
            "balance": paper_trader.current_balance,
            "starting_balance": paper_trader.starting_balance,
            "total_portfolio": total_portfolio,
            "roi": roi,
            "open_positions": positions_with_current,
            "closed_trades": paper_trader.closed_trades[-20:],  # Last 20
            "win_count": paper_trader.win_count,
            "loss_count": paper_trader.loss_count,
            "total_profit": paper_trader.total_profit,
            "total_loss": paper_trader.total_loss,
        }

    except Exception as e:
        logger.error(f"Error getting paper trading status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CUSTOM WATCHLIST ENDPOINTS
# =============================================================================


@app.get("/api/watchlist", response_model=List[WatchlistWalletResponse])
async def get_watchlist(db: Session = Depends(get_db)):
    """Get all custom watchlist wallets."""
    try:
        manager = CustomWatchlistManager(db)
        wallets = manager.get_all_wallets(active_only=True)
        return wallets
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watchlist")
async def add_to_watchlist(
    wallet: WatchlistWalletCreate, db: Session = Depends(get_db)
):
    """Add a wallet to custom watchlist."""
    try:
        manager = CustomWatchlistManager(db)
        result = manager.add_wallet(
            address=wallet.address,
            chain_id=wallet.chain_id,
            label=wallet.label,
            notes=wallet.notes,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/watchlist/{address}")
async def update_watchlist_wallet(
    address: str,
    wallet: WatchlistWalletUpdate,
    chain_id: str = "ethereum",
    db: Session = Depends(get_db),
):
    """Update a watchlist wallet's label/notes."""
    try:
        manager = CustomWatchlistManager(db)
        result = manager.update_wallet(
            address=address, chain_id=chain_id, label=wallet.label, notes=wallet.notes
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlist/{address}")
async def remove_from_watchlist(
    address: str, chain_id: str = "ethereum", db: Session = Depends(get_db)
):
    """Remove a wallet from custom watchlist."""
    try:
        manager = CustomWatchlistManager(db)
        result = manager.remove_wallet(address, chain_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
