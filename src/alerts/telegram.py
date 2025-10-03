"""Telegram alert delivery."""

import logging
from typing import Dict, Any, Optional
from telegram import Bot
from telegram.error import TelegramError

from src.config import settings
from src.utils.wallet_labels import wallet_labels

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """Sends formatted alerts to Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        """Initialize Telegram alerter.

        Args:
            bot_token: Telegram bot token (defaults to settings)
            chat_id: Chat ID to send to (defaults to settings)
        """
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        self.bot = Bot(token=self.bot_token) if self.bot_token else None

    async def send_single_wallet_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert for single wallet buy.

        Args:
            alert_data: Alert payload with wallet, token, stats

        Returns:
            True if sent successfully
        """
        if not self.bot or not self.chat_id:
            logger.warning("Telegram not configured, skipping alert")
            return False

        try:
            message = self._format_single_alert(alert_data)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            logger.info(f"Sent single wallet alert for {alert_data.get('token_symbol')}")
            return True

        except TelegramError as e:
            logger.error(f"Telegram error: {str(e)}")
            return False

    async def send_confluence_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Send alert for confluence (multiple wallets).

        Args:
            alert_data: Alert payload with multiple wallets, token

        Returns:
            True if sent successfully
        """
        if not self.bot or not self.chat_id:
            logger.warning("Telegram not configured, skipping alert")
            return False

        try:
            message = self._format_confluence_alert(alert_data)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            logger.info(
                f"Sent confluence alert: {len(alert_data.get('wallets', []))} wallets "
                f"for {alert_data.get('token_symbol')}"
            )
            return True

        except TelegramError as e:
            logger.error(f"Telegram error: {str(e)}")
            return False

    def _format_single_alert(self, data: Dict[str, Any]) -> str:
        """Format single wallet alert message.

        Args:
            data: Alert data

        Returns:
            Formatted message
        """
        token_symbol = data.get("token_symbol", "Unknown")
        token_address = data.get("token_address", "")
        wallet = data.get("wallet_address", "")
        chain = data.get("chain_id", "")
        price_usd = data.get("price_usd", 0)
        pnl_30d = data.get("pnl_30d_usd", 0)
        best_multiple = data.get("best_trade_multiple", 0)
        earlyscore = data.get("earlyscore", 0)
        tx_hash = data.get("tx_hash", "")
        pair_address = data.get("pair_address", "")
        dex = data.get("dex", "")

        # Check for wallet label
        wallet_label = wallet_labels.get_label(wallet, chain)
        wallet_display = f"`{wallet[:8]}...{wallet[-6:]}`"
        if wallet_label:
            wallet_name = wallet_label.get("name", "")
            verified = "✓" if wallet_label.get("verified") else ""
            wallet_display = f"*{wallet_name}* {verified}\n`{wallet[:8]}...{wallet[-6:]}`"

        # Generate explorer links based on chain
        explorer_links = self._get_explorer_links(chain, token_address, tx_hash)

        message = f"""🔔 *TOP WALLET BUY*

*Token:* {token_symbol} (${price_usd:.6f})
*Wallet:* {wallet_display}
*30D PnL:* ${pnl_30d:,.0f} | *Best:* {best_multiple:.1f}x
*EarlyScore:* {earlyscore:.0f}

*Chain:* {chain.title()}
*DEX:* {dex or 'Unknown'}

{explorer_links}
"""
        return message

    def _format_confluence_alert(self, data: Dict[str, Any]) -> str:
        """Format confluence alert message.

        Args:
            data: Alert data

        Returns:
            Formatted message
        """
        token_symbol = data.get("token_symbol", "Unknown")
        token_address = data.get("token_address", "")
        chain = data.get("chain_id", "")
        price_usd = data.get("price_usd", 0)
        liquidity_usd = data.get("liquidity_usd", 0)
        wallets = data.get("wallets", [])
        num_wallets = len(wallets)
        avg_pnl = data.get("avg_pnl_30d", 0)
        window_minutes = data.get("window_minutes", 0)

        wallet_list = "\n".join(
            [f"• `{w['address'][:8]}...` (${w.get('pnl_30d', 0):,.0f})" for w in wallets[:5]]
        )

        message = f"""🚨 *CONFLUENCE* ({num_wallets} wallets)

*Token:* {token_symbol} (${price_usd:.6f})
*Wallets:*
{wallet_list}

*Avg 30D PnL:* ${avg_pnl:,.0f}
*Window:* {window_minutes} minutes

*Chain:* {chain.title()}
*Liquidity:* ${liquidity_usd:,.0f}

[Token](https://dexscreener.com/{chain}/{token_address})
"""
        return message

    def _get_explorer_links(self, chain: str, token_address: str, tx_hash: str) -> str:
        """Generate explorer links for chain.

        Args:
            chain: Chain identifier
            token_address: Token address
            tx_hash: Transaction hash

        Returns:
            Formatted links string
        """
        explorers = {
            "ethereum": "etherscan.io",
            "bsc": "bscscan.com",
            "polygon": "polygonscan.com",
            "arbitrum": "arbiscan.io",
            "base": "basescan.org",
            "optimism": "optimistic.etherscan.io",
            "avalanche": "snowtrace.io",
            "solana": "solscan.io",
        }

        explorer = explorers.get(chain, "etherscan.io")

        if chain == "solana":
            return f"[View TX](https://{explorer}/tx/{tx_hash})\n[DEX Screener](https://dexscreener.com/solana/{token_address})\n[Birdeye](https://birdeye.so/token/{token_address})"
        else:
            return f"[View TX](https://{explorer}/tx/{tx_hash})\n[DEX Screener](https://dexscreener.com/{chain}/{token_address})\n[Dextools](https://www.dextools.io/app/en/{chain}/pair-explorer/{token_address})"
