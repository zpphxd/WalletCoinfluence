"""API routes for watchlist, alerts, and stats."""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.db import get_db
from src.db.models import Wallet, WalletStats30D, Alert
from src.api.schemas import WalletResponse, WalletStatsResponse, AlertResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/watchlist", response_model=List[WalletResponse])
async def get_watchlist(
    chain: Optional[str] = Query(None, description="Filter by chain"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    db: Session = Depends(get_db),
) -> List[WalletResponse]:
    """Get current watchlist wallets.

    Args:
        chain: Optional chain filter
        limit: Max number of results
        db: Database session

    Returns:
        List of watchlist wallets
    """
    query = db.query(Wallet).filter(Wallet.is_bot_flag == False)

    if chain:
        query = query.filter(Wallet.chain_id == chain)

    wallets = query.order_by(desc(Wallet.last_active_at)).limit(limit).all()

    return [
        WalletResponse(
            address=w.address,
            chain_id=w.chain_id,
            is_bot=w.is_bot_flag,
            first_seen_at=w.first_seen_at,
            last_active_at=w.last_active_at,
        )
        for w in wallets
    ]


@router.get("/stats/top-wallets", response_model=List[WalletStatsResponse])
async def get_top_wallets(
    chain: Optional[str] = Query(None, description="Filter by chain"),
    min_pnl: Optional[float] = Query(None, description="Minimum 30D PnL"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    db: Session = Depends(get_db),
) -> List[WalletStatsResponse]:
    """Get top performing wallets by 30D PnL.

    Args:
        chain: Optional chain filter
        min_pnl: Minimum PnL filter
        limit: Max number of results
        db: Database session

    Returns:
        List of wallet stats
    """
    query = db.query(WalletStats30D, Wallet).join(
        Wallet, WalletStats30D.wallet == Wallet.address
    ).filter(Wallet.is_bot_flag == False)

    if chain:
        query = query.filter(WalletStats30D.chain_id == chain)

    if min_pnl is not None:
        query = query.filter(WalletStats30D.realized_pnl_usd >= min_pnl)

    results = query.order_by(desc(WalletStats30D.realized_pnl_usd)).limit(limit).all()

    return [
        WalletStatsResponse(
            wallet=stats.wallet,
            chain_id=stats.chain_id,
            trades_count=stats.trades_count,
            realized_pnl_usd=stats.realized_pnl_usd,
            unrealized_pnl_usd=stats.unrealized_pnl_usd,
            best_trade_multiple=stats.best_trade_multiple,
            earlyscore_median=stats.earlyscore_median,
            max_drawdown=stats.max_drawdown,
            last_update=stats.last_update,
        )
        for stats, wallet in results
    ]


@router.get("/alerts/recent", response_model=List[AlertResponse])
async def get_recent_alerts(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    alert_type: Optional[str] = Query(None, description="Filter by type (single/confluence)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    db: Session = Depends(get_db),
) -> List[AlertResponse]:
    """Get recent alerts.

    Args:
        hours: Hours to look back
        alert_type: Optional type filter
        limit: Max number of results
        db: Database session

    Returns:
        List of recent alerts
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(Alert).filter(Alert.ts >= since)

    if alert_type:
        query = query.filter(Alert.type == alert_type)

    alerts = query.order_by(desc(Alert.ts)).limit(limit).all()

    return [
        AlertResponse(
            id=a.id,
            ts=a.ts,
            type=a.type,
            token_address=a.token_address,
            chain_id=a.chain_id,
            wallets=a.wallets_json,
            rule_id=a.rule_id,
        )
        for a in alerts
    ]
