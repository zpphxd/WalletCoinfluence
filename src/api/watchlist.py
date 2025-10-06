"""API endpoints for custom watchlist management."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from src.db.models import CustomWatchlistWallet, Wallet, WalletStats30D
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


class CustomWatchlistManager:
    """Manage user-submitted custom watchlist wallets."""

    def __init__(self, db: Session):
        """Initialize watchlist manager.

        Args:
            db: Database session
        """
        self.db = db

    def add_wallet(
        self,
        address: str,
        chain_id: str = "ethereum",
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a wallet to custom watchlist.

        Args:
            address: Wallet address
            chain_id: Chain identifier (ethereum, base, arbitrum, solana)
            label: Optional custom label
            notes: Optional notes about this wallet

        Returns:
            Result dict with success status and wallet info
        """
        try:
            # Check if already exists
            existing = (
                self.db.query(CustomWatchlistWallet)
                .filter(
                    CustomWatchlistWallet.address == address,
                    CustomWatchlistWallet.chain_id == chain_id,
                )
                .first()
            )

            if existing:
                # Reactivate if was disabled
                if not existing.is_active:
                    existing.is_active = True
                    existing.label = label or existing.label
                    existing.notes = notes or existing.notes
                    self.db.commit()
                    logger.info(f"✅ Re-activated custom wallet: {address[:16]}... ({label})")
                    return {"success": True, "message": "Wallet re-activated", "wallet": self._wallet_to_dict(existing)}
                else:
                    return {"success": False, "message": "Wallet already in watchlist"}

            # Add new wallet
            custom_wallet = CustomWatchlistWallet(
                address=address,
                chain_id=chain_id,
                label=label,
                notes=notes,
                added_at=datetime.utcnow(),
                is_active=True,
            )

            self.db.add(custom_wallet)
            self.db.commit()

            logger.info(f"✅ Added custom wallet to watchlist: {address[:16]}... ({label})")

            return {
                "success": True,
                "message": "Wallet added to watchlist",
                "wallet": self._wallet_to_dict(custom_wallet),
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding wallet to watchlist: {str(e)}")
            return {"success": False, "message": str(e)}

    def remove_wallet(self, address: str, chain_id: str = "ethereum") -> Dict[str, Any]:
        """Remove a wallet from custom watchlist (soft delete).

        Args:
            address: Wallet address
            chain_id: Chain identifier

        Returns:
            Result dict with success status
        """
        try:
            wallet = (
                self.db.query(CustomWatchlistWallet)
                .filter(
                    CustomWatchlistWallet.address == address,
                    CustomWatchlistWallet.chain_id == chain_id,
                )
                .first()
            )

            if not wallet:
                return {"success": False, "message": "Wallet not found in watchlist"}

            # Soft delete
            wallet.is_active = False
            self.db.commit()

            logger.info(f"🗑️  Removed custom wallet: {address[:16]}...")

            return {"success": True, "message": "Wallet removed from watchlist"}

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error removing wallet: {str(e)}")
            return {"success": False, "message": str(e)}

    def get_all_wallets(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all custom watchlist wallets.

        Args:
            active_only: Only return active wallets (default True)

        Returns:
            List of wallet dicts with stats
        """
        query = self.db.query(CustomWatchlistWallet)

        if active_only:
            query = query.filter(CustomWatchlistWallet.is_active == True)

        wallets = query.order_by(CustomWatchlistWallet.added_at.desc()).all()

        results = []
        for wallet in wallets:
            wallet_dict = self._wallet_to_dict(wallet)

            # Enrich with stats if available
            stats = (
                self.db.query(WalletStats30D)
                .filter(
                    WalletStats30D.wallet_address == wallet.address,
                    WalletStats30D.chain_id == wallet.chain_id,
                )
                .first()
            )

            if stats:
                wallet_dict["stats"] = {
                    "trades_count": stats.trades_count,
                    "realized_pnl_usd": stats.realized_pnl_usd,
                    "unrealized_pnl_usd": stats.unrealized_pnl_usd,
                    "best_trade_multiple": stats.best_trade_multiple,
                    "earlyscore_median": stats.earlyscore_median,
                }
            else:
                wallet_dict["stats"] = None

            results.append(wallet_dict)

        return results

    def update_wallet(
        self,
        address: str,
        chain_id: str = "ethereum",
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update wallet label/notes.

        Args:
            address: Wallet address
            chain_id: Chain identifier
            label: New label (optional)
            notes: New notes (optional)

        Returns:
            Result dict
        """
        try:
            wallet = (
                self.db.query(CustomWatchlistWallet)
                .filter(
                    CustomWatchlistWallet.address == address,
                    CustomWatchlistWallet.chain_id == chain_id,
                )
                .first()
            )

            if not wallet:
                return {"success": False, "message": "Wallet not found"}

            if label is not None:
                wallet.label = label
            if notes is not None:
                wallet.notes = notes

            self.db.commit()

            logger.info(f"✏️  Updated custom wallet: {address[:16]}...")

            return {
                "success": True,
                "message": "Wallet updated",
                "wallet": self._wallet_to_dict(wallet),
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating wallet: {str(e)}")
            return {"success": False, "message": str(e)}

    def get_wallet_addresses(self, active_only: bool = True) -> List[str]:
        """Get list of wallet addresses (for confluence detection).

        Args:
            active_only: Only return active wallets

        Returns:
            List of wallet addresses
        """
        query = self.db.query(CustomWatchlistWallet.address)

        if active_only:
            query = query.filter(CustomWatchlistWallet.is_active == True)

        return [row[0] for row in query.all()]

    def _wallet_to_dict(self, wallet: CustomWatchlistWallet) -> Dict[str, Any]:
        """Convert wallet model to dict.

        Args:
            wallet: CustomWatchlistWallet model

        Returns:
            Wallet as dict
        """
        return {
            "address": wallet.address,
            "chain_id": wallet.chain_id,
            "label": wallet.label,
            "notes": wallet.notes,
            "added_at": wallet.added_at.isoformat() if wallet.added_at else None,
            "is_active": wallet.is_active,
        }


# CLI helper functions
def add_wallet_cli(address: str, chain_id: str = "ethereum", label: str = None):
    """CLI function to add a wallet."""
    db = SessionLocal()
    try:
        manager = CustomWatchlistManager(db)
        result = manager.add_wallet(address, chain_id, label)
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")
        if result['success']:
            print(f"   Address: {result['wallet']['address']}")
            print(f"   Chain: {result['wallet']['chain_id']}")
            print(f"   Label: {result['wallet']['label']}")
    finally:
        db.close()


def list_wallets_cli():
    """CLI function to list all custom wallets."""
    db = SessionLocal()
    try:
        manager = CustomWatchlistManager(db)
        wallets = manager.get_all_wallets()

        if not wallets:
            print("📭 No custom wallets in watchlist")
            return

        print(f"\n📋 CUSTOM WATCHLIST ({len(wallets)} wallets)\n")
        print("=" * 80)

        for w in wallets:
            print(f"\n🔍 {w['label'] or 'Unlabeled'}")
            print(f"   Address: {w['address']}")
            print(f"   Chain: {w['chain_id']}")
            print(f"   Added: {w['added_at']}")

            if w.get('stats'):
                s = w['stats']
                print(f"   Stats: {s['trades_count']} trades, ${s['unrealized_pnl_usd']:,.0f} PnL")
            else:
                print(f"   Stats: Not yet tracked")

            if w['notes']:
                print(f"   Notes: {w['notes']}")

        print("\n" + "=" * 80)

    finally:
        db.close()


def remove_wallet_cli(address: str, chain_id: str = "ethereum"):
    """CLI function to remove a wallet."""
    db = SessionLocal()
    try:
        manager = CustomWatchlistManager(db)
        result = manager.remove_wallet(address, chain_id)
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")
    finally:
        db.close()
