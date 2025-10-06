"""SQLAlchemy database models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Token(Base):
    """Token metadata and risk indicators."""

    __tablename__ = "tokens"

    token_address = Column(String(100), primary_key=True)
    chain_id = Column(String(20), nullable=False)
    symbol = Column(String(20), nullable=True)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    first_liquidity_at = Column(DateTime, nullable=True)
    last_price_usd = Column(Float, nullable=True)
    liquidity_usd = Column(Float, nullable=True)
    holders_top10_share = Column(Float, nullable=True)
    is_honeypot = Column(Boolean, nullable=True)
    buy_tax_pct = Column(Float, nullable=True)
    sell_tax_pct = Column(Float, nullable=True)

    # Relationships
    seed_tokens = relationship("SeedToken", back_populates="token")
    trades = relationship("Trade", back_populates="token")

    __table_args__ = (Index("idx_tokens_chain", "chain_id"),)


class SeedToken(Base):
    """Trending/runner tokens from various sources."""

    __tablename__ = "seed_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_address = Column(String(100), ForeignKey("tokens.token_address"), nullable=False)
    chain_id = Column(String(20), nullable=False)
    snapshot_ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = Column(String(50), nullable=False)  # dexscreener, geckoterminal, birdeye
    rank_24h = Column(Integer, nullable=True)
    vol_24h_usd = Column(Float, nullable=True)
    pct_change_24h = Column(Float, nullable=True)

    # Relationships
    token = relationship("Token", back_populates="seed_tokens")

    __table_args__ = (
        Index("idx_seed_tokens_snapshot", "snapshot_ts"),
        Index("idx_seed_tokens_token_chain", "token_address", "chain_id"),
    )


class Wallet(Base):
    """Wallet metadata and flags."""

    __tablename__ = "wallets"

    address = Column(String(100), primary_key=True)
    chain_id = Column(String(20), nullable=False)
    is_contract = Column(Boolean, default=False)
    labels_json = Column(Text, nullable=True)  # JSON string with labels/tags
    is_bot_flag = Column(Boolean, default=False)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_active_at = Column(DateTime, nullable=True)

    # Relationships
    trades = relationship("Trade", back_populates="wallet")
    positions = relationship("Position", back_populates="wallet")
    stats = relationship("WalletStats30D", back_populates="wallet")

    __table_args__ = (Index("idx_wallets_chain", "chain_id"),)


class Trade(Base):
    """Individual DEX trades."""

    __tablename__ = "trades"

    tx_hash = Column(String(100), primary_key=True)
    ts = Column(DateTime, nullable=False)
    chain_id = Column(String(20), nullable=False)
    wallet_address = Column(String(100), ForeignKey("wallets.address"), nullable=False)
    token_address = Column(String(100), ForeignKey("tokens.token_address"), nullable=False)
    side = Column(String(4), nullable=False)  # buy or sell
    qty_token = Column(Float, nullable=False)
    price_usd = Column(Float, nullable=False)
    usd_value = Column(Float, nullable=False)
    fee_usd = Column(Float, nullable=True)
    venue = Column(String(50), nullable=True)  # uniswap, raydium, etc
    pair_address = Column(String(100), nullable=True)

    # Relationships
    wallet = relationship("Wallet", back_populates="trades")
    token = relationship("Token", back_populates="trades")

    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="check_trade_side"),
        Index("idx_trades_wallet_ts", "wallet_address", "ts"),
        Index("idx_trades_token_ts", "token_address", "ts"),
        Index("idx_trades_chain_ts", "chain_id", "ts"),
    )


class Position(Base):
    """Current positions per wallet-token pair."""

    __tablename__ = "positions"

    wallet_address = Column(String(100), ForeignKey("wallets.address"), primary_key=True)
    token_address = Column(String(100), ForeignKey("tokens.token_address"), primary_key=True)
    chain_id = Column(String(20), nullable=False)
    qty = Column(Float, nullable=False, default=0.0)
    cost_basis_usd = Column(Float, nullable=False, default=0.0)
    realized_pnl_usd = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_usd = Column(Float, nullable=False, default=0.0)
    last_price_usd = Column(Float, nullable=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    wallet = relationship("Wallet", back_populates="positions")

    __table_args__ = (Index("idx_positions_wallet", "wallet_address"),)


class WalletStats30D(Base):
    """Rolling 30-day stats per wallet."""

    __tablename__ = "wallet_stats_30d"

    wallet_address = Column(String(100), ForeignKey("wallets.address"), primary_key=True)
    chain_id = Column(String(20), primary_key=True)
    trades_count = Column(Integer, nullable=False, default=0)
    realized_pnl_usd = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_usd = Column(Float, nullable=False, default=0.0)
    best_trade_multiple = Column(Float, nullable=True)
    earlyscore_median = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    last_update = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    wallet = relationship("Wallet", back_populates="stats")

    __table_args__ = (
        Index("idx_wallet_stats_pnl", "realized_pnl_usd"),
        Index("idx_wallet_stats_trades", "trades_count"),
    )


class Alert(Base):
    """Alert log for sent notifications."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    type = Column(String(20), nullable=False)  # single or confluence
    token_address = Column(String(100), nullable=False)
    chain_id = Column(String(20), nullable=False)
    wallets_json = Column(Text, nullable=False)  # JSON array of wallet addresses
    rule_id = Column(String(50), nullable=True)
    payload_json = Column(Text, nullable=True)  # Full alert payload

    __table_args__ = (
        CheckConstraint("type IN ('single', 'confluence')", name="check_alert_type"),
        Index("idx_alerts_ts", "ts"),
        Index("idx_alerts_token", "token_address"),
    )


class CustomWatchlistWallet(Base):
    """User-submitted wallets to monitor for confluence (separate from auto-discovered whales)."""

    __tablename__ = "custom_watchlist_wallets"

    address = Column(String(100), primary_key=True)
    chain_id = Column(String(20), primary_key=True)
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    added_by = Column(String(100), nullable=True, default="user")  # For future multi-user support
    label = Column(String(200), nullable=True)  # Custom label/note for this wallet
    is_active = Column(Boolean, default=True)  # Can disable without deleting
    notes = Column(Text, nullable=True)  # Additional notes about this wallet

    __table_args__ = (
        Index("idx_custom_watchlist_active", "is_active"),
        Index("idx_custom_watchlist_added", "added_at"),
    )
