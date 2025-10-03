"""Unit tests for AlchemyClient sell detection."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from src.clients.alchemy import AlchemyClient


@pytest.fixture
def mock_dex_client():
    """Mock DexScreener client."""
    client = Mock()
    client.get_token_info = AsyncMock(return_value={"price_usd": 1.5})
    return client


@pytest.fixture
def alchemy_client(mock_dex_client):
    """Create AlchemyClient with mocked dependencies."""
    with patch("src.clients.alchemy.settings") as mock_settings:
        mock_settings.alchemy_api_key = "test_key"
        client = AlchemyClient()
        client.dex_client = mock_dex_client
        return client


@pytest.mark.asyncio
async def test_detect_buy_from_dex_pool(alchemy_client):
    """Test that transfers FROM DEX pool TO wallet are detected as BUY."""
    wallet = "0xBUYER123"

    # Mock responses
    mock_block_response = {"result": "0x1000000"}  # Block 16777216

    # Mock transfer: DEX pool -> wallet (BUY)
    mock_transfer_response = {
        "result": {
            "transfers": [
                {
                    "from": "0xDEXPOOL",  # Pool address
                    "to": wallet,
                    "hash": "0xBUY_TX",
                    "value": 100.0,
                    "rawContract": {"address": "0xTOKEN"},
                },
                {
                    "from": "0xDEXPOOL",  # Same pool (heuristic: multiple sends)
                    "to": "0xOTHER",
                    "hash": "0xOTHER_TX",
                    "value": 50.0,
                    "rawContract": {"address": "0xTOKEN"},
                }
            ]
        }
    }

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_block_response, mock_transfer_response]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        # Should detect 1 buy transaction
        assert len(transactions) == 1
        assert transactions[0]["type"] == "buy"
        assert transactions[0]["tx_hash"] == "0xBUY_TX"
        assert transactions[0]["token_address"] == "0xTOKEN"
        assert transactions[0]["amount"] == 100.0


@pytest.mark.asyncio
async def test_detect_sell_to_dex_pool(alchemy_client):
    """Test that transfers FROM wallet TO DEX pool are detected as SELL."""
    wallet = "0xSELLER123"

    mock_block_response = {"result": "0x1000000"}

    # Mock transfer: wallet -> DEX pool (SELL)
    mock_transfer_response = {
        "result": {
            "transfers": [
                {
                    "from": wallet,  # Wallet sends
                    "to": "0xDEXPOOL",  # To pool
                    "hash": "0xSELL_TX",
                    "value": 50.0,
                    "rawContract": {"address": "0xTOKEN"},
                },
                {
                    "from": "0xOTHER",
                    "to": "0xDEXPOOL",  # Same pool (heuristic: receives multiple times)
                    "hash": "0xOTHER_TX",
                    "value": 75.0,
                    "rawContract": {"address": "0xTOKEN"},
                }
            ]
        }
    }

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_block_response, mock_transfer_response]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        # Should detect 1 sell transaction
        assert len(transactions) == 1
        assert transactions[0]["type"] == "sell"
        assert transactions[0]["tx_hash"] == "0xSELL_TX"
        assert transactions[0]["token_address"] == "0xTOKEN"
        assert transactions[0]["amount"] == 50.0


@pytest.mark.asyncio
async def test_detect_both_buys_and_sells(alchemy_client):
    """Test detecting both buys and sells for the same wallet."""
    wallet = "0xTRADER123"

    mock_block_response = {"result": "0x1000000"}

    # Mock two separate queries: one for receives (buys), one for sends (sells)
    mock_buy_response = {
        "result": {
            "transfers": [
                {
                    "from": "0xDEXPOOL",
                    "to": wallet,
                    "hash": "0xBUY_TX",
                    "value": 100.0,
                    "rawContract": {"address": "0xTOKEN"},
                },
                {
                    "from": "0xDEXPOOL",
                    "to": "0xOTHER",
                    "hash": "0xOTHER_BUY",
                    "value": 50.0,
                    "rawContract": {"address": "0xTOKEN"},
                }
            ]
        }
    }

    mock_sell_response = {
        "result": {
            "transfers": [
                {
                    "from": wallet,
                    "to": "0xDEXPOOL2",
                    "hash": "0xSELL_TX",
                    "value": 50.0,
                    "rawContract": {"address": "0xTOKEN"},
                },
                {
                    "from": "0xOTHER",
                    "to": "0xDEXPOOL2",
                    "hash": "0xOTHER_SELL",
                    "value": 75.0,
                    "rawContract": {"address": "0xTOKEN"},
                }
            ]
        }
    }

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        # Block number, then buy query, then sell query
        mock_post.side_effect = [
            mock_block_response,
            mock_buy_response,
            mock_sell_response
        ]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        # Should detect both buy and sell
        assert len(transactions) == 2

        buy_txs = [tx for tx in transactions if tx["type"] == "buy"]
        sell_txs = [tx for tx in transactions if tx["type"] == "sell"]

        assert len(buy_txs) == 1
        assert len(sell_txs) == 1
        assert buy_txs[0]["tx_hash"] == "0xBUY_TX"
        assert sell_txs[0]["tx_hash"] == "0xSELL_TX"


@pytest.mark.asyncio
async def test_dex_pool_heuristic_threshold(alchemy_client):
    """Test that pool detection requires minimum transfer count."""
    wallet = "0xWALLET"

    mock_block_response = {"result": "0x1000000"}

    # Only ONE transfer from an address - should NOT be considered a pool
    mock_transfer_response = {
        "result": {
            "transfers": [
                {
                    "from": "0xNOTPOOL",
                    "to": wallet,
                    "hash": "0xSINGLE_TX",
                    "value": 100.0,
                    "rawContract": {"address": "0xTOKEN"},
                }
            ]
        }
    }

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_block_response, mock_transfer_response]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        # Should NOT detect this as a DEX trade (not enough occurrences)
        assert len(transactions) == 0


@pytest.mark.asyncio
async def test_price_calculation_for_sells(alchemy_client, mock_dex_client):
    """Test that sell transactions have correct price and USD value."""
    wallet = "0xSELLER"

    mock_block_response = {"result": "0x1000000"}

    mock_transfer_response = {
        "result": {
            "transfers": [
                {
                    "from": wallet,
                    "to": "0xDEXPOOL",
                    "hash": "0xSELL_TX",
                    "value": 100.0,
                    "rawContract": {"address": "0xTOKEN"},
                },
                {
                    "from": "0xOTHER",
                    "to": "0xDEXPOOL",
                    "hash": "0xOTHER_TX",
                    "value": 50.0,
                    "rawContract": {"address": "0xTOKEN"},
                }
            ]
        }
    }

    # Mock DexScreener returns $1.50 per token
    mock_dex_client.get_token_info.return_value = {"price_usd": 1.5}

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_block_response, mock_transfer_response]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        assert len(transactions) == 1
        assert transactions[0]["price_usd"] == 1.5
        assert transactions[0]["value_usd"] == 150.0  # 100 tokens * $1.50
        assert transactions[0]["amount"] == 100.0


@pytest.mark.asyncio
async def test_empty_transfers_returns_empty_list(alchemy_client):
    """Test handling of no transfers found."""
    wallet = "0xEMPTY"

    mock_block_response = {"result": "0x1000000"}
    mock_transfer_response = {"result": {"transfers": []}}

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_block_response, mock_transfer_response]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        assert transactions == []


@pytest.mark.asyncio
async def test_error_handling_returns_empty_list(alchemy_client):
    """Test that API errors return empty list instead of raising."""
    wallet = "0xERROR"

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = Exception("API Error")

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        assert transactions == []


@pytest.mark.asyncio
async def test_multiple_tokens_same_wallet(alchemy_client):
    """Test detecting trades across multiple tokens."""
    wallet = "0xMULTI"

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
                    "to": "0xOTHER",
                    "hash": "0xOTHER_A",
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
                    "hash": "0xOTHER_B",
                    "value": 75.0,
                    "rawContract": {"address": "0xTOKEN_B"},
                }
            ]
        }
    }

    with patch.object(alchemy_client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_block_response, mock_buy_response]

        transactions = await alchemy_client.get_wallet_transactions(wallet, "ethereum")

        # Should detect both token buys
        assert len(transactions) == 2
        token_addresses = {tx["token_address"] for tx in transactions}
        assert token_addresses == {"0xTOKEN_A", "0xTOKEN_B"}
