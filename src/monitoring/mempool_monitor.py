"""Mempool monitoring for instant whale trade detection (0-confirmation)."""

import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime
from web3 import Web3
from src.db.models import Wallet
from src.analytics.paper_trading import PaperTradingTracker
from src.utils.price_fetcher import MultiSourcePriceFetcher
from src.config import settings

logger = logging.getLogger(__name__)


class MempoolMonitor:
    """Monitor Ethereum mempool for pending whale transactions."""

    def __init__(self, whale_addresses: List[str], paper_trader: PaperTradingTracker):
        """Initialize mempool monitor.

        Args:
            whale_addresses: List of whale wallet addresses to watch
            paper_trader: Paper trading tracker instance
        """
        self.whale_addresses = set([addr.lower() for addr in whale_addresses])
        self.paper_trader = paper_trader
        self.price_fetcher = MultiSourcePriceFetcher()

        # Connect to Alchemy WebSocket
        self.w3 = Web3(Web3.WebsocketProvider(
            f"wss://eth-mainnet.g.alchemy.com/v2/{settings.alchemy_api_key}"
        ))

        logger.info(f"🔍 Mempool monitor initialized - watching {len(self.whale_addresses)} whales")

    async def start_monitoring(self):
        """Start monitoring mempool for whale transactions (runs continuously)."""
        logger.info("🚀 Starting mempool monitoring (pending transactions)...")

        # Subscribe to pending transactions
        pending_filter = self.w3.eth.filter('pending')

        while True:
            try:
                # Get pending transaction hashes
                pending_txs = pending_filter.get_new_entries()

                for tx_hash in pending_txs:
                    try:
                        # Get transaction details
                        tx = self.w3.eth.get_transaction(tx_hash)

                        if tx is None:
                            continue

                        # Check if transaction is from a whale we're watching
                        from_address = tx['from'].lower() if tx.get('from') else None

                        if from_address in self.whale_addresses:
                            # WHALE TRANSACTION DETECTED IN MEMPOOL!
                            await self._handle_whale_pending_tx(tx, from_address)

                    except Exception as e:
                        # Transaction might have already been mined
                        continue

                # Sleep briefly to avoid hammering the API
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Mempool monitoring error: {str(e)}")
                await asyncio.sleep(5)

    async def _handle_whale_pending_tx(self, tx: Dict[str, Any], whale_address: str):
        """Handle a pending whale transaction detected in mempool.

        Args:
            tx: Pending transaction data
            whale_address: Whale wallet address
        """
        try:
            # Decode the transaction to identify DEX swap
            to_address = tx['to'].lower() if tx.get('to') else None

            # Check if it's a known DEX router
            from src.utils.dex_routers import KNOWN_DEX_ROUTERS

            if to_address not in KNOWN_DEX_ROUTERS:
                return  # Not a DEX swap

            dex_name = KNOWN_DEX_ROUTERS.get(to_address, "Unknown DEX")

            # Parse swap data from transaction input
            token_out = self._parse_token_from_swap(tx.get('input', ''))

            if not token_out:
                return

            # Get current price
            current_price = await self.price_fetcher.get_token_price(token_out, "ethereum")

            if current_price == 0:
                return

            # Check if we already have this position
            if token_out in self.paper_trader.positions:
                return

            # Check max positions limit
            if len(self.paper_trader.positions) >= 3:
                return

            # EXECUTE INSTANT BUY (front-run or ride with whale)
            buy_amount = self.paper_trader.current_balance * 0.30  # 30% position

            if buy_amount < 10:
                return

            result = self.paper_trader.execute_buy(
                token_address=token_out,
                chain_id="ethereum",
                price_usd=current_price,
                amount_usd=buy_amount,
                reason=f"MEMPOOL: Whale {whale_address[:10]}... buying via {dex_name}",
                num_whales=1,
            )

            if result["success"]:
                # Store targets
                self.paper_trader.positions[token_out]["take_profit_pct"] = 25.0
                self.paper_trader.positions[token_out]["stop_loss_pct"] = -15.0
                self.paper_trader.save_to_file()

                logger.info(
                    f"⚡ MEMPOOL BUY EXECUTED (0-CONFIRMATION!)\n"
                    f"   Whale: {whale_address[:16]}...\n"
                    f"   Token: {token_out[:16]}...\n"
                    f"   DEX: {dex_name}\n"
                    f"   Price: ${current_price:.8f}\n"
                    f"   Amount: ${buy_amount:.2f}\n"
                    f"   Status: PENDING (front-ran whale trade!)"
                )

        except Exception as e:
            logger.error(f"Error handling pending whale tx: {str(e)}")

    def _parse_token_from_swap(self, input_data: str) -> str:
        """Parse token address from DEX swap transaction input.

        Args:
            input_data: Transaction input data (hex)

        Returns:
            Token address or empty string
        """
        # This is a simplified parser - in production would use proper ABI decoding
        # For now, just extract addresses from input data
        try:
            if len(input_data) < 10:
                return ""

            # Method signature (first 10 chars including 0x)
            # Uniswap V2/V3 swap methods typically have token addresses in the calldata

            # Extract potential addresses (20 bytes = 40 hex chars)
            # This is a heuristic - proper implementation would decode the ABI
            input_hex = input_data[2:] if input_data.startswith('0x') else input_data

            # Look for address patterns (40 hex chars)
            for i in range(0, len(input_hex) - 64, 2):
                potential_addr = input_hex[i+24:i+64]  # Skip padding
                if len(potential_addr) == 40:
                    addr = "0x" + potential_addr
                    # Basic validation - check if it looks like an address
                    if addr.startswith("0x") and len(addr) == 42:
                        return addr.lower()

            return ""
        except Exception:
            return ""


# Background job function
async def mempool_monitoring_job():
    """Background job to monitor mempool for whale trades."""
    from src.db.session import SessionLocal
    from src.db.models import Wallet, WalletStats30D

    db = SessionLocal()

    try:
        # Get all profitable whale addresses
        profitable_whales = (
            db.query(Wallet.address)
            .join(WalletStats30D, Wallet.address == WalletStats30D.wallet_address)
            .filter(
                WalletStats30D.unrealized_pnl_usd > 0,
                WalletStats30D.trades_count >= 1,
            )
            .all()
        )

        whale_addresses = [w[0] for w in profitable_whales]

        if not whale_addresses:
            logger.warning("No whales to monitor in mempool")
            return

        # Load paper trader
        paper_trader = PaperTradingTracker.load_from_file() or PaperTradingTracker(db, starting_balance=1000.0)

        # Start mempool monitoring (runs indefinitely)
        monitor = MempoolMonitor(whale_addresses, paper_trader)
        await monitor.start_monitoring()

    except Exception as e:
        logger.error(f"Mempool monitoring job failed: {str(e)}")
    finally:
        db.close()
