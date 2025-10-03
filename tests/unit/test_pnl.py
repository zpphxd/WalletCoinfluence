"""Unit tests for FIFO PnL calculation."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.analytics.pnl import FIFOPnLCalculator
from src.db.models import Trade


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def calculator(mock_db):
    """PnL calculator with mocked DB."""
    return FIFOPnLCalculator(mock_db)


def test_fifo_simple_profit(calculator, mock_db):
    """Test simple buy-sell with profit."""
    wallet = "0xtest"
    token = "0xtoken"

    # Mock trades: Buy at $1, sell at $2
    trades = [
        Trade(
            tx_hash="0x1",
            ts=datetime.utcnow() - timedelta(days=5),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="buy",
            qty_token=100.0,
            price_usd=1.0,
            usd_value=100.0,
            fee_usd=1.0,
        ),
        Trade(
            tx_hash="0x2",
            ts=datetime.utcnow() - timedelta(days=2),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="sell",
            qty_token=100.0,
            price_usd=2.0,
            usd_value=200.0,
            fee_usd=2.0,
        ),
    ]

    realized, unrealized = calculator._calculate_token_pnl(wallet, token, trades)

    # Realized = 200 - 2 (sell fee) - 100 - 1 (buy cost) = 97
    assert realized == pytest.approx(97.0, rel=0.01)
    assert unrealized == 0.0  # All sold


def test_fifo_partial_sell(calculator, mock_db):
    """Test partial sell leaves unrealized PnL."""
    wallet = "0xtest"
    token = "0xtoken"

    trades = [
        Trade(
            tx_hash="0x1",
            ts=datetime.utcnow() - timedelta(days=5),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="buy",
            qty_token=100.0,
            price_usd=1.0,
            usd_value=100.0,
            fee_usd=0.0,
        ),
        Trade(
            tx_hash="0x2",
            ts=datetime.utcnow() - timedelta(days=2),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="sell",
            qty_token=50.0,
            price_usd=2.0,
            usd_value=100.0,
            fee_usd=0.0,
        ),
    ]

    realized, unrealized = calculator._calculate_token_pnl(wallet, token, trades)

    # Realized: 100 (proceeds) - 50 (cost basis for 50 tokens) = 50
    assert realized == pytest.approx(50.0, rel=0.01)

    # Unrealized: 50 tokens @ $2 = 100, cost basis 50 = 50 profit
    assert unrealized == pytest.approx(50.0, rel=0.01)


def test_fifo_multiple_buys(calculator, mock_db):
    """Test FIFO with multiple buy lots."""
    wallet = "0xtest"
    token = "0xtoken"

    trades = [
        Trade(
            tx_hash="0x1",
            ts=datetime.utcnow() - timedelta(days=10),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="buy",
            qty_token=100.0,
            price_usd=1.0,
            usd_value=100.0,
            fee_usd=0.0,
        ),
        Trade(
            tx_hash="0x2",
            ts=datetime.utcnow() - timedelta(days=8),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="buy",
            qty_token=100.0,
            price_usd=2.0,
            usd_value=200.0,
            fee_usd=0.0,
        ),
        Trade(
            tx_hash="0x3",
            ts=datetime.utcnow() - timedelta(days=2),
            chain_id="ethereum",
            wallet=wallet,
            token_address=token,
            side="sell",
            qty_token=150.0,  # Sells first buy + half of second
            price_usd=3.0,
            usd_value=450.0,
            fee_usd=0.0,
        ),
    ]

    realized, unrealized = calculator._calculate_token_pnl(wallet, token, trades)

    # FIFO: Sell 100 @ $3 (cost $100) + 50 @ $3 (cost $100) = 450 - 200 = 250
    assert realized == pytest.approx(250.0, rel=0.01)

    # Unrealized: 50 tokens @ $3 = 150, cost basis 100 = 50 profit
    assert unrealized == pytest.approx(50.0, rel=0.01)


def test_best_trade_multiple(calculator, mock_db):
    """Test best trade multiple calculation."""
    wallet = "0xtest"

    # Mock query results
    trades = [
        # Token 1: 2x
        Trade(
            tx_hash="0x1",
            ts=datetime.utcnow() - timedelta(days=5),
            chain_id="ethereum",
            wallet=wallet,
            token_address="0xtoken1",
            side="buy",
            qty_token=100.0,
            price_usd=1.0,
            usd_value=100.0,
            fee_usd=0.0,
        ),
        Trade(
            tx_hash="0x2",
            ts=datetime.utcnow() - timedelta(days=2),
            chain_id="ethereum",
            wallet=wallet,
            token_address="0xtoken1",
            side="sell",
            qty_token=100.0,
            price_usd=2.0,
            usd_value=200.0,
            fee_usd=0.0,
        ),
        # Token 2: 5x
        Trade(
            tx_hash="0x3",
            ts=datetime.utcnow() - timedelta(days=10),
            chain_id="ethereum",
            wallet=wallet,
            token_address="0xtoken2",
            side="buy",
            qty_token=50.0,
            price_usd=2.0,
            usd_value=100.0,
            fee_usd=0.0,
        ),
        Trade(
            tx_hash="0x4",
            ts=datetime.utcnow() - timedelta(days=3),
            chain_id="ethereum",
            wallet=wallet,
            token_address="0xtoken2",
            side="sell",
            qty_token=50.0,
            price_usd=10.0,
            usd_value=500.0,
            fee_usd=0.0,
        ),
    ]

    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = trades

    multiple = calculator.get_best_trade_multiple(wallet, days=30)

    # Best should be 5x from token2
    assert multiple == pytest.approx(5.0, rel=0.01)
