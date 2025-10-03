"""Integration tests for AlchemyClient buy/sell detection.

These tests verify the complete flow of detecting both buy and sell trades
from blockchain data through the Alchemy API.
"""

import pytest
from unittest.mock import patch, AsyncMock
from src.clients.alchemy import AlchemyClient


@pytest.mark.asyncio
async def test_complete_buy_sell_cycle():
    """Integration test: Wallet buys token, then sells it."""
    wallet = "0xTRADER"

    with patch("src.clients.alchemy.settings") as mock_settings:
        mock_settings.alchemy_api_key = "test_key"

        client = AlchemyClient()

        # Mock DexScreener to return consistent price
        mock_dex_client = AsyncMock()
        mock_dex_client.get_token_info = AsyncMock(
            return_value={"price_usd": 2.0}
        )
        client.dex_client = mock_dex_client

        # Mock Alchemy API responses
        mock_block_response = {"result": "0x1000000"}

        # Simulate a buy: DEX pool sends tokens to wallet
        mock_buy_response = {
            "result": {
                "transfers": [
                    {
                        "from": "0xUNISWAP_POOL",
                        "to": wallet,
                        "hash": "0xBUY_HASH",
                        "value": 100.0,
                        "rawContract": {"address": "0xTOKEN_ABC"},
                    },
                    {
                        "from": "0xUNISWAP_POOL",
                        "to": "0xOTHER_BUYER",
                        "hash": "0xOTHER_BUY",
                        "value": 50.0,
                        "rawContract": {"address": "0xTOKEN_ABC"},
                    },
                ]
            }
        }

        # Simulate a sell: Wallet sends tokens to DEX pool
        mock_sell_response = {
            "result": {
                "transfers": [
                    {
                        "from": wallet,
                        "to": "0xUNISWAP_POOL",
                        "hash": "0xSELL_HASH",
                        "value": 100.0,
                        "rawContract": {"address": "0xTOKEN_ABC"},
                    },
                    {
                        "from": "0xOTHER_SELLER",
                        "to": "0xUNISWAP_POOL",
                        "hash": "0xOTHER_SELL",
                        "value": 75.0,
                        "rawContract": {"address": "0xTOKEN_ABC"},
                    },
                ]
            }
        }

        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            # Return: block number, buy transfers, sell transfers
            mock_post.side_effect = [
                mock_block_response,
                mock_buy_response,
                mock_sell_response,
            ]

            transactions = await client.get_wallet_transactions(wallet, "ethereum")

            # Verify we got both buy and sell
            assert len(transactions) == 2

            buy_tx = [tx for tx in transactions if tx["type"] == "buy"][0]
            sell_tx = [tx for tx in transactions if tx["type"] == "sell"][0]

            # Verify buy transaction
            assert buy_tx["tx_hash"] == "0xBUY_HASH"
            assert buy_tx["type"] == "buy"
            assert buy_tx["token_address"] == "0xTOKEN_ABC"
            assert buy_tx["amount"] == 100.0
            assert buy_tx["price_usd"] == 2.0
            assert buy_tx["value_usd"] == 200.0

            # Verify sell transaction
            assert sell_tx["tx_hash"] == "0xSELL_HASH"
            assert sell_tx["type"] == "sell"
            assert sell_tx["token_address"] == "0xTOKEN_ABC"
            assert sell_tx["amount"] == 100.0
            assert sell_tx["price_usd"] == 2.0
            assert sell_tx["value_usd"] == 200.0

            # Verify API was called correctly (3 times: block, buys, sells)
            assert mock_post.call_count == 3

            # Verify correct payload for buy query (toAddress)
            buy_call = mock_post.call_args_list[1]
            assert "toAddress" in str(buy_call)

            # Verify correct payload for sell query (fromAddress)
            sell_call = mock_post.call_args_list[2]
            assert "fromAddress" in str(sell_call)


@pytest.mark.asyncio
async def test_only_buys_no_sells():
    """Integration test: Wallet only buys, never sells."""
    wallet = "0xHODLER"

    with patch("src.clients.alchemy.settings") as mock_settings:
        mock_settings.alchemy_api_key = "test_key"

        client = AlchemyClient()

        mock_dex_client = AsyncMock()
        mock_dex_client.get_token_info = AsyncMock(
            return_value={"price_usd": 1.0}
        )
        client.dex_client = mock_dex_client

        mock_block_response = {"result": "0x1000000"}

        mock_buy_response = {
            "result": {
                "transfers": [
                    {
                        "from": "0xDEX_POOL",
                        "to": wallet,
                        "hash": "0xBUY1",
                        "value": 50.0,
                        "rawContract": {"address": "0xTOKEN1"},
                    },
                    {
                        "from": "0xDEX_POOL",
                        "to": "0xOTHER",
                        "hash": "0xBUY2",
                        "value": 50.0,
                        "rawContract": {"address": "0xTOKEN1"},
                    },
                ]
            }
        }

        # No sells
        mock_sell_response = {"result": {"transfers": []}}

        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                mock_block_response,
                mock_buy_response,
                mock_sell_response,
            ]

            transactions = await client.get_wallet_transactions(wallet, "ethereum")

            # Only 1 buy, no sells
            assert len(transactions) == 1
            assert transactions[0]["type"] == "buy"


@pytest.mark.asyncio
async def test_only_sells_no_buys():
    """Integration test: Wallet only sells (perhaps received airdrop)."""
    wallet = "0xSELLER"

    with patch("src.clients.alchemy.settings") as mock_settings:
        mock_settings.alchemy_api_key = "test_key"

        client = AlchemyClient()

        mock_dex_client = AsyncMock()
        mock_dex_client.get_token_info = AsyncMock(
            return_value={"price_usd": 5.0}
        )
        client.dex_client = mock_dex_client

        mock_block_response = {"result": "0x1000000"}

        # No buys
        mock_buy_response = {"result": {"transfers": []}}

        mock_sell_response = {
            "result": {
                "transfers": [
                    {
                        "from": wallet,
                        "to": "0xDEX_POOL",
                        "hash": "0xSELL1",
                        "value": 100.0,
                        "rawContract": {"address": "0xAIRDROP_TOKEN"},
                    },
                    {
                        "from": "0xOTHER",
                        "to": "0xDEX_POOL",
                        "hash": "0xSELL2",
                        "value": 50.0,
                        "rawContract": {"address": "0xAIRDROP_TOKEN"},
                    },
                ]
            }
        }

        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                mock_block_response,
                mock_buy_response,
                mock_sell_response,
            ]

            transactions = await client.get_wallet_transactions(wallet, "ethereum")

            # Only 1 sell, no buys
            assert len(transactions) == 1
            assert transactions[0]["type"] == "sell"
            assert transactions[0]["value_usd"] == 500.0  # 100 * $5


@pytest.mark.asyncio
async def test_multiple_tokens_mixed_trades():
    """Integration test: Wallet trades multiple tokens with buys and sells."""
    wallet = "0xACTIVE_TRADER"

    with patch("src.clients.alchemy.settings") as mock_settings:
        mock_settings.alchemy_api_key = "test_key"

        client = AlchemyClient()

        mock_dex_client = AsyncMock()
        mock_dex_client.get_token_info = AsyncMock(
            return_value={"price_usd": 1.0}
        )
        client.dex_client = mock_dex_client

        mock_block_response = {"result": "0x1000000"}

        mock_buy_response = {
            "result": {
                "transfers": [
                    # Token A buy
                    {
                        "from": "0xPOOL_A",
                        "to": wallet,
                        "hash": "0xBUY_A",
                        "value": 100.0,
                        "rawContract": {"address": "0xTOKEN_A"},
                    },
                    {
                        "from": "0xPOOL_A",
                        "to": "0xOTHER1",
                        "hash": "0xOTHER_A1",
                        "value": 50.0,
                        "rawContract": {"address": "0xTOKEN_A"},
                    },
                    # Token B buy
                    {
                        "from": "0xPOOL_B",
                        "to": wallet,
                        "hash": "0xBUY_B",
                        "value": 200.0,
                        "rawContract": {"address": "0xTOKEN_B"},
                    },
                    {
                        "from": "0xPOOL_B",
                        "to": "0xOTHER2",
                        "hash": "0xOTHER_B1",
                        "value": 75.0,
                        "rawContract": {"address": "0xTOKEN_B"},
                    },
                ]
            }
        }

        mock_sell_response = {
            "result": {
                "transfers": [
                    # Token A sell
                    {
                        "from": wallet,
                        "to": "0xPOOL_A",
                        "hash": "0xSELL_A",
                        "value": 50.0,
                        "rawContract": {"address": "0xTOKEN_A"},
                    },
                    {
                        "from": "0xOTHER3",
                        "to": "0xPOOL_A",
                        "hash": "0xOTHER_A2",
                        "value": 25.0,
                        "rawContract": {"address": "0xTOKEN_A"},
                    },
                ]
            }
        }

        with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                mock_block_response,
                mock_buy_response,
                mock_sell_response,
            ]

            transactions = await client.get_wallet_transactions(wallet, "ethereum")

            # 2 buys + 1 sell = 3 transactions
            assert len(transactions) == 3

            buys = [tx for tx in transactions if tx["type"] == "buy"]
            sells = [tx for tx in transactions if tx["type"] == "sell"]

            assert len(buys) == 2
            assert len(sells) == 1

            # Verify tokens
            buy_tokens = {tx["token_address"] for tx in buys}
            assert buy_tokens == {"0xTOKEN_A", "0xTOKEN_B"}

            sell_tokens = {tx["token_address"] for tx in sells}
            assert sell_tokens == {"0xTOKEN_A"}
