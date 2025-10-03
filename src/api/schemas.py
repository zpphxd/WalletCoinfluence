"""Pydantic schemas for API responses."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    """Wallet response schema."""

    address: str
    chain_id: str
    is_bot: bool
    first_seen_at: datetime
    last_active_at: Optional[datetime]

    class Config:
        from_attributes = True


class WalletStatsResponse(BaseModel):
    """Wallet statistics response schema."""

    wallet: str
    chain_id: str
    trades_count: int
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    best_trade_multiple: Optional[float]
    earlyscore_median: Optional[float]
    max_drawdown: Optional[float]
    last_update: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    """Alert response schema."""

    id: int
    ts: datetime
    type: str
    token_address: str
    chain_id: str
    wallets: str  # JSON string
    rule_id: Optional[str]

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
