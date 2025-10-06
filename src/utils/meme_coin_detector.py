"""Meme coin detection utility - identifies if a token exhibits meme coin characteristics."""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.db.models import Token, SeedToken

logger = logging.getLogger(__name__)


class MemeCoinDetector:
    """Detects if a token is a meme coin based on characteristics."""

    # AGGRESSIVE: Follow profitable whales regardless of price
    # Changed from restrictive meme-only to any token whales are buying
    MEME_PRICE_MIN = 0.00000001  # Very low price (8 decimal places)
    MEME_PRICE_MAX = 10.0        # CHANGED: Up to $10 (follow whales on ANY token)
    MEME_MIN_VOLUME_24H = 50000  # RAISED: Min $50k volume (avoid dead tokens)
    MEME_MIN_LIQUIDITY = 50000   # RAISED: Min $50k liquidity (avoid rugs)

    # Meme coin name/symbol patterns
    MEME_KEYWORDS = [
        "inu", "doge", "shib", "pepe", "floki", "elon", "moon", "safe",
        "baby", "rocket", "wojak", "chad", "bonk", "cat", "dog", "frog",
        "meme", "chad", "giga", "based", "turbo", "mog", "wif", "ponke",
        "popcat", "myro", "brett", "toshi", "degen", "wen", "pnut"
    ]

    def __init__(self, db: Session):
        """Initialize meme coin detector.

        Args:
            db: Database session
        """
        self.db = db

    def is_meme_coin(
        self,
        token_address: str,
        chain_id: str,
        price_usd: Optional[float] = None,
        symbol: Optional[str] = None,
        volume_24h: Optional[float] = None,
        liquidity: Optional[float] = None,
    ) -> bool:
        """Check if token is a meme coin.

        Args:
            token_address: Token contract address
            chain_id: Chain identifier
            price_usd: Current price (optional, will fetch from DB if None)
            symbol: Token symbol (optional, will fetch from DB if None)
            volume_24h: 24h volume (optional, will fetch from DB if None)
            liquidity: Liquidity (optional, will fetch from DB if None)

        Returns:
            True if token exhibits meme coin characteristics
        """
        # Fetch token data if not provided
        if any(x is None for x in [price_usd, symbol, volume_24h, liquidity]):
            token = (
                self.db.query(Token)
                .filter(Token.token_address == token_address, Token.chain_id == chain_id)
                .first()
            )

            if not token:
                logger.debug(f"Token {token_address[:10]}... not found in database")
                return False

            price_usd = price_usd or token.last_price_usd
            symbol = symbol or token.symbol
            liquidity = liquidity or token.liquidity_usd

            # Get volume from seed_tokens table (most recent snapshot)
            if volume_24h is None:
                seed = (
                    self.db.query(SeedToken)
                    .filter(SeedToken.token_address == token_address, SeedToken.chain_id == chain_id)
                    .order_by(SeedToken.snapshot_ts.desc())
                    .first()
                )
                volume_24h = seed.vol_24h_usd if seed else 0

        # 1. PRICE CHECK: Meme coins are very cheap
        if price_usd is None or price_usd <= 0:
            return False

        if not (self.MEME_PRICE_MIN <= price_usd <= self.MEME_PRICE_MAX):
            logger.debug(
                f"{symbol} price ${price_usd:.8f} outside meme range "
                f"(${self.MEME_PRICE_MIN:.8f} - ${self.MEME_PRICE_MAX:.8f})"
            )
            return False

        # 2. VOLUME CHECK: Meme coins have active trading
        if volume_24h is None or volume_24h < self.MEME_MIN_VOLUME_24H:
            logger.debug(f"{symbol} volume ${volume_24h:,.0f} below meme minimum ${self.MEME_MIN_VOLUME_24H:,.0f}")
            return False

        # 3. LIQUIDITY CHECK: Meme coins have some liquidity (not total rug)
        if liquidity is None or liquidity < self.MEME_MIN_LIQUIDITY:
            logger.debug(f"{symbol} liquidity ${liquidity:,.0f} below meme minimum ${self.MEME_MIN_LIQUIDITY:,.0f}")
            return False

        # 4. NAME/SYMBOL CHECK: Meme coins often have meme keywords
        symbol_lower = (symbol or "").lower()
        has_meme_keyword = any(keyword in symbol_lower for keyword in self.MEME_KEYWORDS)

        if has_meme_keyword:
            logger.info(
                f"✅ MEME COIN DETECTED: {symbol} at ${price_usd:.8f} "
                f"(vol: ${volume_24h:,.0f}, liq: ${liquidity:,.0f})"
            )
            return True

        # If no keyword but meets price/volume/liquidity criteria, still consider it
        # (catches new memes without classic keywords)
        logger.info(
            f"✅ POTENTIAL MEME: {symbol} at ${price_usd:.8f} "
            f"(vol: ${volume_24h:,.0f}, liq: ${liquidity:,.0f}) - no keyword but meets criteria"
        )
        return True

    def get_meme_score(
        self,
        token_address: str,
        chain_id: str,
        price_usd: Optional[float] = None,
        symbol: Optional[str] = None,
        volume_24h: Optional[float] = None,
        liquidity: Optional[float] = None,
    ) -> int:
        """Get meme coin score (0-100).

        Higher score = more meme-like characteristics

        Args:
            token_address: Token contract address
            chain_id: Chain identifier
            price_usd: Current price (optional)
            symbol: Token symbol (optional)
            volume_24h: 24h volume (optional)
            liquidity: Liquidity (optional)

        Returns:
            Score from 0-100
        """
        # Fetch token data if not provided
        if any(x is None for x in [price_usd, symbol, volume_24h, liquidity]):
            token = (
                self.db.query(Token)
                .filter(Token.token_address == token_address, Token.chain_id == chain_id)
                .first()
            )

            if not token:
                return 0

            price_usd = price_usd or token.last_price_usd
            symbol = symbol or token.symbol
            liquidity = liquidity or token.liquidity_usd

            # Get volume from seed_tokens table (most recent snapshot)
            if volume_24h is None:
                seed = (
                    self.db.query(SeedToken)
                    .filter(SeedToken.token_address == token_address, SeedToken.chain_id == chain_id)
                    .order_by(SeedToken.snapshot_ts.desc())
                    .first()
                )
                volume_24h = seed.vol_24h_usd if seed else 0

        score = 0

        # Price score (0-40 points)
        if price_usd and self.MEME_PRICE_MIN <= price_usd <= self.MEME_PRICE_MAX:
            # Lower price = higher score (more meme-like)
            if price_usd < 0.0001:
                score += 40
            elif price_usd < 0.001:
                score += 30
            elif price_usd < 0.01:
                score += 20

        # Volume score (0-30 points)
        if volume_24h:
            if volume_24h >= 1000000:  # $1M+
                score += 30
            elif volume_24h >= 100000:  # $100k+
                score += 20
            elif volume_24h >= 10000:  # $10k+
                score += 10

        # Keyword score (0-30 points)
        symbol_lower = (symbol or "").lower()
        keyword_matches = sum(1 for keyword in self.MEME_KEYWORDS if keyword in symbol_lower)
        if keyword_matches >= 2:
            score += 30
        elif keyword_matches == 1:
            score += 20

        return min(score, 100)
