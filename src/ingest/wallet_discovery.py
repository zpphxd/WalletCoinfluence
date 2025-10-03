"""Wallet discovery from trending token buyers."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.db.models import Token, SeedToken, Wallet, Trade
from src.config import settings

logger = logging.getLogger(__name__)


class WalletDiscovery:
    """Discovers wallet addresses from token buyer data."""

    def __init__(self, db: Session):
        """Initialize wallet discovery.

        Args:
            db: Database session
        """
        self.db = db

    async def discover_from_seed_tokens(self, hours_back: int = 24) -> int:
        """Discover wallets from recent seed tokens.

        Args:
            hours_back: How many hours back to look for seed tokens

        Returns:
            Number of wallets discovered
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours_back)

            # Get recent seed tokens
            seed_tokens = (
                self.db.query(SeedToken)
                .filter(SeedToken.snapshot_ts >= since)
                .order_by(SeedToken.rank_24h)
                .limit(50)  # Top 50 trending tokens
                .all()
            )

            logger.info(f"Found {len(seed_tokens)} seed tokens from last {hours_back}h")

            total_wallets = 0

            for seed in seed_tokens:
                try:
                    # Fetch buyers for this token
                    wallets = await self._fetch_token_buyers(
                        seed.token_address, seed.chain_id
                    )

                    total_wallets += wallets
                    logger.info(
                        f"Discovered {wallets} wallets for {seed.token_address[:10]}..."
                    )

                except Exception as e:
                    logger.error(
                        f"Error discovering wallets for {seed.token_address}: {str(e)}"
                    )
                    continue

            logger.info(f"Wallet discovery complete: {total_wallets} wallets found")
            return total_wallets

        except Exception as e:
            logger.error(f"Wallet discovery failed: {str(e)}")
            return 0

    async def _fetch_token_buyers(
        self, token_address: str, chain_id: str, limit: int = 100
    ) -> int:
        """Fetch recent buyers for a token.

        Args:
            token_address: Token contract address
            chain_id: Chain identifier
            limit: Max number of buyers to fetch

        Returns:
            Number of wallets discovered
        """
        try:
            # Import chain-specific clients
            if chain_id == "solana":
                from src.clients.helius import HeliusClient

                client = HeliusClient()
                transactions = await client.get_token_transactions(
                    token_address, limit=limit
                )
            else:
                from src.clients.alchemy import AlchemyClient

                client = AlchemyClient()
                transactions = await client.get_token_transfers(
                    token_address, chain_id, limit=limit
                )

            wallets_found = 0

            for tx in transactions:
                try:
                    wallet_address = tx.get("from_address")
                    if not wallet_address:
                        continue

                    # Check if it's a buy transaction
                    if tx.get("type") != "buy":
                        continue

                    # Create or update wallet
                    wallet = (
                        self.db.query(Wallet)
                        .filter(Wallet.address == wallet_address)
                        .first()
                    )

                    if not wallet:
                        wallet = Wallet(
                            address=wallet_address,
                            chain_id=chain_id,
                            first_seen_at=datetime.utcnow(),
                        )
                        self.db.add(wallet)
                        self.db.flush()  # Flush to make wallet visible to subsequent queries
                        wallets_found += 1

                    # Update last active
                    wallet.last_active_at = datetime.utcnow()

                    # Create trade record (check for duplicates first)
                    tx_hash = tx.get("tx_hash")
                    existing_trade = (
                        self.db.query(Trade)
                        .filter(Trade.tx_hash == tx_hash)
                        .first()
                    )

                    if not existing_trade:
                        trade = Trade(
                            tx_hash=tx_hash,
                            ts=tx.get("timestamp", datetime.utcnow()),
                            chain_id=chain_id,
                            wallet_address=wallet_address,
                            token_address=token_address,
                            side="buy",
                            qty_token=float(tx.get("amount", 0)),
                            price_usd=float(tx.get("price_usd", 0)),
                            usd_value=float(tx.get("value_usd", 0)),
                            venue=tx.get("dex"),
                        )
                        self.db.add(trade)
                        self.db.flush()  # Flush to make trade visible to subsequent queries

                except Exception as e:
                    logger.error(f"Error processing transaction: {str(e)}")
                    continue

            self.db.commit()
            return wallets_found

        except Exception as e:
            logger.error(f"Error fetching token buyers: {str(e)}")
            self.db.rollback()
            return 0
