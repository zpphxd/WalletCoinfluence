"""Runner token ingestion from trending sources."""

import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.clients.dexscreener import DexScreenerClient
from src.clients.geckoterminal import GeckoTerminalClient
from src.clients.birdeye import BirdeyeClient
from src.db.models import Token, SeedToken
from src.config import settings

logger = logging.getLogger(__name__)


class RunnerIngestion:
    """Manages ingestion of trending/runner tokens."""

    def __init__(self, db: Session):
        """Initialize runner ingestion.

        Args:
            db: Database session
        """
        self.db = db
        self.dex_screener = DexScreenerClient()
        self.gecko_terminal = GeckoTerminalClient()
        self.birdeye = BirdeyeClient()

    async def ingest_trending_tokens(self, chain: str, source: str) -> int:
        """Ingest trending tokens for a specific chain and source.

        Args:
            chain: Chain identifier
            source: Source name (dexscreener, geckoterminal, birdeye)

        Returns:
            Number of tokens ingested
        """
        try:
            # Fetch from appropriate source
            if source == "dexscreener":
                tokens = await self.dex_screener.get_trending_tokens(chain)
            elif source == "geckoterminal":
                tokens = await self.gecko_terminal.get_trending_pools(chain)
            elif source == "birdeye" and chain == "solana":
                tokens = await self.birdeye.get_trending_tokens()
            else:
                logger.warning(f"Unknown source {source} for chain {chain}")
                return 0

            count = 0
            snapshot_ts = datetime.utcnow()

            for idx, token_data in enumerate(tokens):
                if not token_data.get("token_address"):
                    continue

                try:
                    # Upsert token
                    token = self._upsert_token(token_data)

                    # Flush to catch any conflicts early
                    self.db.flush()

                    # Create seed entry
                    seed = SeedToken(
                        token_address=token.token_address,
                        chain_id=chain,
                        snapshot_ts=snapshot_ts,
                        source=source,
                        rank_24h=idx + 1,
                        vol_24h_usd=token_data.get("volume_24h_usd"),
                        pct_change_24h=token_data.get("price_change_24h"),
                    )
                    self.db.add(seed)
                    count += 1

                except Exception as e:
                    logger.warning(f"Error upserting token {token_data.get('token_address', 'unknown')[:10]}...: {str(e)}")
                    self.db.rollback()
                    continue

            self.db.commit()
            logger.info(f"Ingested {count} tokens from {source} for {chain}")
            return count

        except Exception as e:
            logger.error(f"Error ingesting tokens from {source} for {chain}: {str(e)}")
            self.db.rollback()
            return 0

    def _upsert_token(self, token_data: Dict[str, Any]) -> Token:
        """Upsert token into database.

        Args:
            token_data: Token data dict

        Returns:
            Token model instance
        """
        token_address = token_data["token_address"]
        chain_id = token_data["chain_id"]

        # Check if exists
        token = self.db.query(Token).filter(Token.token_address == token_address).first()

        if token:
            # Update existing
            token.symbol = token_data.get("symbol") or token.symbol
            token.last_price_usd = token_data.get("price_usd")
            token.liquidity_usd = token_data.get("liquidity_usd")
        else:
            # Create new
            token = Token(
                token_address=token_address,
                chain_id=chain_id,
                symbol=token_data.get("symbol"),
                first_seen_at=datetime.utcnow(),
                last_price_usd=token_data.get("price_usd"),
                liquidity_usd=token_data.get("liquidity_usd"),
            )
            self.db.add(token)

        return token

    async def run_all_sources(self) -> Dict[str, int]:
        """Run ingestion for all configured chains and sources.

        Returns:
            Dict mapping source to count of tokens ingested
        """
        results = {}

        for chain in settings.chain_list:
            # DEX Screener for all chains
            count = await self.ingest_trending_tokens(chain, "dexscreener")
            results[f"{chain}_dexscreener"] = count

            # GeckoTerminal for all chains
            count = await self.ingest_trending_tokens(chain, "geckoterminal")
            results[f"{chain}_geckoterminal"] = count

            # Birdeye only for Solana
            if chain == "solana":
                count = await self.ingest_trending_tokens(chain, "birdeye")
                results[f"{chain}_birdeye"] = count

        total = sum(results.values())
        logger.info(f"Total tokens ingested across all sources: {total}")
        return results

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.dex_screener.close()
        await self.gecko_terminal.close()
        await self.birdeye.close()
