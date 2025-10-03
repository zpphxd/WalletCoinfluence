"""Confluence detection using Redis sorted sets."""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import redis

from src.config import settings

logger = logging.getLogger(__name__)


class ConfluenceDetector:
    """Detects when multiple watchlist wallets buy the same token."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize confluence detector.

        Args:
            redis_client: Redis client (creates new if None)
        """
        self.redis = redis_client or redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self.window_minutes = settings.confluence_minutes

    def record_trade(
        self,
        token_address: str,
        chain_id: str,
        wallet_address: str,
        side: str,  # "buy" or "sell"
        metadata: Dict[str, Any],
    ) -> None:
        """Record a trade event (buy or sell) in the time window.

        Args:
            token_address: Token address
            chain_id: Chain identifier
            wallet_address: Wallet that traded
            side: "buy" or "sell"
            metadata: Additional data (price, tx_hash, etc)
        """
        # Separate keys for buys and sells
        key = f"confluence:{side}:{chain_id}:{token_address}"
        timestamp = datetime.utcnow().timestamp()

        # Store as sorted set with timestamp as score
        value = json.dumps({
            "wallet": wallet_address,
            "ts": timestamp,
            "side": side,
            **metadata,
        })

        self.redis.zadd(key, {value: timestamp})

        # Set expiry to window + buffer
        self.redis.expire(key, self.window_minutes * 60 + 300)

        logger.debug(f"Recorded {side} for {wallet_address[:8]}... on {token_address[:8]}...")

    # Keep old method for backwards compatibility
    def record_buy(
        self,
        token_address: str,
        chain_id: str,
        wallet_address: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Record a buy event (backwards compatible wrapper)."""
        self.record_trade(token_address, chain_id, wallet_address, "buy", metadata)

    def check_confluence(
        self, token_address: str, chain_id: str, side: str = "buy", min_wallets: int = 2
    ) -> Optional[List[Dict[str, Any]]]:
        """Check if confluence exists within the time window.

        Args:
            token_address: Token address
            chain_id: Chain identifier
            side: "buy" or "sell"
            min_wallets: Minimum number of wallets for confluence

        Returns:
            List of trade events if confluence detected, None otherwise
        """
        key = f"confluence:{side}:{chain_id}:{token_address}"

        # Get all events in the window
        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        cutoff_ts = cutoff.timestamp()

        # Remove old entries
        self.redis.zremrangebyscore(key, "-inf", cutoff_ts)

        # Get remaining entries
        entries = self.redis.zrange(key, 0, -1)

        if len(entries) < min_wallets:
            return None

        # Parse entries
        events = []
        seen_wallets = set()

        for entry in entries:
            data = json.loads(entry)
            wallet = data["wallet"]

            # Ensure unique wallets
            if wallet not in seen_wallets:
                seen_wallets.add(wallet)
                events.append(data)

        if len(events) >= min_wallets:
            action = "bought" if side == "buy" else "sold"
            logger.info(
                f"🚨 CONFLUENCE DETECTED: {len(events)} whales {action} "
                f"{token_address[:8]}... on {chain_id}"
            )
            return events

        return None

    def get_window_stats(
        self, token_address: str, chain_id: str
    ) -> Dict[str, Any]:
        """Get stats for current window.

        Args:
            token_address: Token address
            chain_id: Chain identifier

        Returns:
            Stats dict
        """
        key = f"confluence:{chain_id}:{token_address}"

        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        cutoff_ts = cutoff.timestamp()

        # Remove old
        self.redis.zremrangebyscore(key, "-inf", cutoff_ts)

        # Count
        count = self.redis.zcard(key)

        # Get unique wallets
        entries = self.redis.zrange(key, 0, -1)
        wallets = set()
        for entry in entries:
            data = json.loads(entry)
            wallets.add(data["wallet"])

        return {
            "total_buys": count,
            "unique_wallets": len(wallets),
            "window_minutes": self.window_minutes,
        }

    def clear_token(self, token_address: str, chain_id: str) -> None:
        """Clear confluence data for a token.

        Args:
            token_address: Token address
            chain_id: Chain identifier
        """
        key = f"confluence:{chain_id}:{token_address}"
        self.redis.delete(key)
        logger.debug(f"Cleared confluence for {token_address[:8]}...")
