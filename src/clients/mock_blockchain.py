"""Mock blockchain data for testing without API keys."""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class MockBlockchainClient:
    """Generates realistic mock blockchain data for testing."""

    # Sample known trader addresses (real addresses from crypto Twitter)
    KNOWN_WALLETS = [
        "0x8f94c56caa3d6c09e4cec61c2c814deb4f4bf1a3",  # Ansem
        "0x3d2c479070e54b918e88e3419b028194f3e6bfd4",  # Tetranode
        "0xb8c2c29ee19d8307cb7255e1cd9cbde883a267d5",  # DCF GOD
        "0x1111111111111111111111111111111111111111",  # Test whale 1
        "0x2222222222222222222222222222222222222222",  # Test whale 2
    ]

    def __init__(self):
        """Initialize mock client."""
        self.mock_data_enabled = True
        logger.info("🧪 Mock blockchain client initialized (no API key required)")

    async def get_token_transfers(
        self, token_address: str, chain_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Generate mock token transfer data.

        Args:
            token_address: Token contract address
            chain_id: Chain identifier
            limit: Max number of transfers

        Returns:
            List of mock transfer data
        """
        if not self.mock_data_enabled:
            return []

        # Generate 5-15 random buyers
        num_buyers = random.randint(5, 15)
        transfers = []

        for i in range(num_buyers):
            # Mix of known wallets and random addresses
            if i < 2 and random.random() > 0.5:
                wallet = random.choice(self.KNOWN_WALLETS)
            else:
                wallet = f"0x{random.randbytes(20).hex()}"

            # Generate realistic transaction
            timestamp = datetime.utcnow() - timedelta(
                minutes=random.randint(10, 1440)  # Last 24h
            )

            amount = random.uniform(1000, 1000000)  # Token amount
            price_usd = random.uniform(0.000001, 10.0)  # Price per token
            value_usd = amount * price_usd

            transfers.append(
                {
                    "tx_hash": f"0x{random.randbytes(32).hex()}",
                    "timestamp": timestamp,
                    "from_address": wallet,
                    "type": "buy",
                    "token_address": token_address,
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": random.choice(
                        ["uniswap-v3", "uniswap-v2", "sushiswap", "curve"]
                    ),
                }
            )

        logger.info(f"🧪 Generated {len(transfers)} mock token transfers")
        return transfers

    async def get_wallet_transactions(
        self, wallet_address: str, chain_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate mock wallet transaction data.

        Args:
            wallet_address: Wallet address
            chain_id: Chain identifier
            limit: Max number of transactions

        Returns:
            List of mock transaction data
        """
        if not self.mock_data_enabled:
            return []

        # 20% chance of having new trades
        if random.random() > 0.2:
            return []

        # Generate 1-3 new trades
        num_trades = random.randint(1, 3)
        transactions = []

        for _ in range(num_trades):
            timestamp = datetime.utcnow() - timedelta(minutes=random.randint(1, 30))

            amount = random.uniform(10000, 500000)
            price_usd = random.uniform(0.00001, 1.0)
            value_usd = amount * price_usd

            transactions.append(
                {
                    "tx_hash": f"0x{random.randbytes(32).hex()}",
                    "timestamp": timestamp,
                    "type": "buy",
                    "token_address": f"0x{random.randbytes(20).hex()}",
                    "amount": amount,
                    "price_usd": price_usd,
                    "value_usd": value_usd,
                    "dex": random.choice(
                        ["uniswap-v3", "pancakeswap", "sushiswap"]
                    ),
                }
            )

        logger.info(
            f"🧪 Generated {len(transactions)} mock wallet transactions for {wallet_address[:10]}..."
        )
        return transactions
