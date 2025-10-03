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
                parse_mode=None,  # Disable Markdown to avoid parsing errors
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
                parse_mode=None,  # Disable Markdown to avoid parsing errors
                disable_web_page_preview=True,
            )
            logger.info(
                f"Sent confluence alert: {len(alert_data.get('wallet_stats_list', []))} wallets "
                f"for {alert_data.get('token_symbol')}"
            )
            return True

        except TelegramError as e:
            logger.error(f"Telegram error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending confluence alert: {str(e)}")
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

        # Actionable alert format with buy info
        wallet_display = f"{wallet[:10]}...{wallet[-8:]}"

        # Generate buy links based on chain
        buy_link = self._get_buy_link(chain, token_address)

        message = f"""🔔 WHALE BUY SIGNAL

💰 TOKEN: {token_symbol}
📍 Price: ${price_usd:.8f}

🔗 CONTRACT ADDRESS:
{token_address}

🐋 WHALE STATS:
Address: {wallet_display}
30D PnL: ${pnl_30d:,.0f}
Best Trade: {best_multiple:.1f}x
Early Score: {earlyscore:.0f}/100

⛓ Chain: {chain.title()}
🔄 DEX: {dex or 'Unknown'}

🚀 QUICK ACTIONS:
{buy_link}
📊 Chart: https://dexscreener.com/{chain}/{token_address}
🔍 TX: https://etherscan.io/tx/{tx_hash}

⚡ Copy contract address above to buy on Uniswap/your wallet
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
        wallet_stats_list = data.get("wallet_stats_list", [])
        num_wallets = len(wallet_stats_list)

        # Format wallet list
        wallet_lines = []
        total_pnl = 0
        for w in wallet_stats_list[:5]:
            addr = w.get('address', '')
            pnl = w.get('pnl_30d', 0)
            total_pnl += pnl
            wallet_lines.append(f"  {addr[:10]}...{addr[-8:]} (${pnl:,.0f})")

        wallet_list = "\n".join(wallet_lines)
        avg_pnl = total_pnl / num_wallets if num_wallets > 0 else 0

        # Generate buy link
        buy_link = self._get_buy_link(chain, token_address)

        message = f"""🚨 CONFLUENCE ALERT - {num_wallets} WHALES BUYING!

💰 TOKEN: {token_symbol}
📍 Price: ${price_usd:.8f}

🔗 CONTRACT ADDRESS:
{token_address}

🐋 WHALES DETECTED ({num_wallets}):
{wallet_list}

💵 Avg 30D PnL: ${avg_pnl:,.0f}
⛓ Chain: {chain.title()}

🚀 QUICK BUY:
{buy_link}
📊 Chart: https://dexscreener.com/{chain}/{token_address}

⚡ STRONG SIGNAL - Multiple profitable whales buying same token!
⚡ Copy contract address above to buy immediately
"""
        return message

    def _get_buy_link(self, chain: str, token_address: str) -> str:
        """Generate buy link for chain.

        Args:
            chain: Chain identifier
            token_address: Token contract address

        Returns:
            Buy link string
        """
        # Multiple buy options for Kraken wallet users
        if chain == "ethereum":
            return f"💎 Uniswap: https://app.uniswap.org/#/swap?outputCurrency={token_address}\n🔗 1inch: https://app.1inch.io/#/1/simple/swap/ETH/{token_address}"
        elif chain == "base":
            return f"💎 Uniswap: https://app.uniswap.org/#/swap?chain=base&outputCurrency={token_address}\n🔗 Aerodrome: https://aerodrome.finance/swap?from=eth&to={token_address}"
        elif chain == "arbitrum":
            return f"💎 Uniswap: https://app.uniswap.org/#/swap?chain=arbitrum&outputCurrency={token_address}\n🔗 Camelot: https://app.camelot.exchange/?token2={token_address}"
        elif chain == "bsc":
            return f"💎 PancakeSwap: https://pancakeswap.finance/swap?outputCurrency={token_address}\n🔗 1inch: https://app.1inch.io/#/56/simple/swap/BNB/{token_address}"
        elif chain == "polygon":
            return f"💎 Quickswap: https://quickswap.exchange/#/swap?outputCurrency={token_address}\n🔗 1inch: https://app.1inch.io/#/137/simple/swap/MATIC/{token_address}"
        elif chain == "solana":
            return f"💎 Jupiter: https://jup.ag/swap/SOL-{token_address}\n🔗 Raydium: https://raydium.io/swap/?inputCurrency=sol&outputCurrency={token_address}"
        else:
            return f"💎 DEX Screener: https://dexscreener.com/{chain}/{token_address}"

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
