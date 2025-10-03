"""Configuration management for Alpha Wallet Scout."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql://user:password@localhost:5432/wallet_scout"
    redis_url: str = "redis://localhost:6379/0"

    # API Keys
    alchemy_api_key: str = ""
    bitquery_api_key: str = ""
    helius_api_key: str = ""
    birdeye_api_key: str = ""
    tokensniffer_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # API
    api_auth_token: str = "dev_token_change_me"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Chain configuration
    chains: str = "ethereum,base,arbitrum,solana"

    @property
    def chain_list(self) -> List[str]:
        """Parse chains string into list."""
        return [c.strip() for c in self.chains.split(",")]

    # Thresholds
    min_unique_buyers_24h: int = 30
    max_tax_pct: float = 10.0
    add_min_trades_30d: int = 5
    add_min_realized_pnl_30d_usd: float = 50000.0
    add_min_best_trade_multiple: float = 3.0
    remove_if_realized_pnl_30d_lt: float = 0.0
    remove_if_max_drawdown_pct_gt: float = 50.0
    remove_if_trades_30d_lt: int = 2
    confluence_minutes: int = 30

    # Job scheduling
    runner_poll_minutes: int = 15
    trader_window_hours_for_seed: int = 48
    wallet_backfill_days: int = 30
    token_success_window_hours: int = 72

    # Logging
    log_level: str = "INFO"


# Global settings instance
settings = Settings()
