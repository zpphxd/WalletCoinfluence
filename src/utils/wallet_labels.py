"""Wallet label lookup and management."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class WalletLabels:
    """Manages wallet labels and lookups."""

    def __init__(self, labels_file: Optional[str] = None):
        """Initialize wallet labels.

        Args:
            labels_file: Path to labels JSON file
        """
        if labels_file is None:
            labels_file = Path(__file__).parent.parent / "data" / "wallet_labels.json"

        self.labels_file = Path(labels_file)
        self.labels: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.load_labels()

    def load_labels(self) -> None:
        """Load labels from JSON file."""
        try:
            if self.labels_file.exists():
                with open(self.labels_file, "r") as f:
                    self.labels = json.load(f)
                    # Remove metadata key from chains
                    self.labels.pop("_metadata", None)
                logger.info(f"Loaded wallet labels from {self.labels_file}")
            else:
                logger.warning(f"Labels file not found: {self.labels_file}")
                self.labels = {}
        except Exception as e:
            logger.error(f"Error loading wallet labels: {str(e)}")
            self.labels = {}

    def get_label(self, wallet_address: str, chain_id: str) -> Optional[Dict[str, Any]]:
        """Get label for a wallet address.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier

        Returns:
            Label dict or None
        """
        chain_labels = self.labels.get(chain_id, {})
        return chain_labels.get(wallet_address.lower())

    def is_labeled(self, wallet_address: str, chain_id: str) -> bool:
        """Check if wallet has a label.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier

        Returns:
            True if labeled
        """
        return self.get_label(wallet_address, chain_id) is not None

    def get_name(self, wallet_address: str, chain_id: str) -> Optional[str]:
        """Get wallet name if labeled.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier

        Returns:
            Wallet name or None
        """
        label = self.get_label(wallet_address, chain_id)
        return label.get("name") if label else None

    def add_label(
        self,
        wallet_address: str,
        chain_id: str,
        name: str,
        source: str,
        wallet_type: str = "unknown",
        verified: bool = False,
    ) -> None:
        """Add a new wallet label.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier
            name: Wallet name/label
            source: Source of label
            wallet_type: Type of wallet
            verified: Whether verified
        """
        if chain_id not in self.labels:
            self.labels[chain_id] = {}

        self.labels[chain_id][wallet_address.lower()] = {
            "name": name,
            "source": source,
            "type": wallet_type,
            "verified": verified,
        }

        logger.info(f"Added label for {wallet_address[:8]}... on {chain_id}: {name}")

    def save_labels(self) -> None:
        """Save labels to JSON file."""
        try:
            # Add metadata
            data = dict(self.labels)
            data["_metadata"] = {
                "version": "1.0",
                "total_labels": sum(len(chain) for chain in self.labels.values()),
            }

            with open(self.labels_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved wallet labels to {self.labels_file}")

        except Exception as e:
            logger.error(f"Error saving wallet labels: {str(e)}")


# Global instance
wallet_labels = WalletLabels()
