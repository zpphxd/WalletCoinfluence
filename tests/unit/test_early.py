"""Unit tests for Being-Early score calculation."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.analytics.early import EarlyScoreCalculator


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def calculator(mock_db):
    """EarlyScore calculator with mocked DB."""
    return EarlyScoreCalculator(mock_db)


def test_rank_score_first_buyer(calculator, mock_db):
    """Test rank score for first buyer."""
    # Mock: 0 buyers before, 10 total
    mock_db.query.return_value.filter.return_value.scalar.side_effect = [0, 10]

    score = calculator._calculate_rank_score("0xtoken", datetime.utcnow())

    # rank_percentile = 0/10 = 0
    # score = 40 * (1 - 0) = 40
    assert score == pytest.approx(40.0, rel=0.01)


def test_rank_score_mid_buyer(calculator, mock_db):
    """Test rank score for mid-range buyer."""
    # Mock: 50 buyers before, 100 total
    mock_db.query.return_value.filter.return_value.scalar.side_effect = [50, 100]

    score = calculator._calculate_rank_score("0xtoken", datetime.utcnow())

    # rank_percentile = 50/100 = 0.5
    # score = 40 * (1 - 0.5) = 20
    assert score == pytest.approx(20.0, rel=0.01)


def test_rank_score_last_buyer(calculator, mock_db):
    """Test rank score for last buyer."""
    # Mock: 99 buyers before, 100 total
    mock_db.query.return_value.filter.return_value.scalar.side_effect = [99, 100]

    score = calculator._calculate_rank_score("0xtoken", datetime.utcnow())

    # rank_percentile = 99/100 = 0.99
    # score = 40 * (1 - 0.99) = 0.4
    assert score == pytest.approx(0.4, rel=0.1)


def test_mc_score_very_low_mc(calculator, mock_db):
    """Test MC score when buying at very low market cap."""
    # Mock token with low liquidity ($10k → ~$30k MC)
    from src.db.models import Token

    mock_token = Token(
        token_address="0xtoken",
        chain_id="ethereum",
        liquidity_usd=10000.0,
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_token

    score = calculator._calculate_mc_score("0xtoken", datetime.utcnow())

    # estimated_mc = 10000 * 3 = 30000
    # proportion = (1000000 - 30000) / 1000000 = 0.97
    # score = 40 * 0.97 = 38.8
    assert score == pytest.approx(38.8, rel=0.1)


def test_mc_score_high_mc(calculator, mock_db):
    """Test MC score when buying at high market cap."""
    from src.db.models import Token

    mock_token = Token(
        token_address="0xtoken",
        chain_id="ethereum",
        liquidity_usd=500000.0,  # ~$1.5M MC
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_token

    score = calculator._calculate_mc_score("0xtoken", datetime.utcnow())

    # estimated_mc = 500000 * 3 = 1500000 > 1000000
    # score = 0
    assert score == pytest.approx(0.0, rel=0.01)


def test_volume_score_large_buy(calculator, mock_db):
    """Test volume score for large buy."""
    from src.db.models import Trade

    # Mock wallet buy: $1000
    mock_buy = Trade(
        wallet="0xwallet",
        token_address="0xtoken",
        usd_value=1000.0,
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_buy

    # Mock total volume: $5000
    mock_db.query.return_value.filter.return_value.scalar.return_value = 5000.0

    score = calculator._calculate_volume_score(
        "0xwallet", "0xtoken", datetime.utcnow()
    )

    # participation = 1000 / 5000 = 0.2 (20%)
    # capped = 0.2
    # score = 20 * (0.2 / 0.5) = 8
    assert score == pytest.approx(8.0, rel=0.1)


def test_volume_score_whale(calculator, mock_db):
    """Test volume score for whale (capped at 50%)."""
    from src.db.models import Trade

    # Mock wallet buy: $6000 (60% of volume)
    mock_buy = Trade(
        wallet="0xwallet",
        token_address="0xtoken",
        usd_value=6000.0,
    )

    mock_db.query.return_value.filter.return_value.first.return_value = mock_buy

    # Mock total volume: $10000
    mock_db.query.return_value.filter.return_value.scalar.return_value = 10000.0

    score = calculator._calculate_volume_score(
        "0xwallet", "0xtoken", datetime.utcnow()
    )

    # participation = 0.6, capped at 0.5
    # score = 20 * (0.5 / 0.5) = 20 (max)
    assert score == pytest.approx(20.0, rel=0.1)


def test_complete_score_early_buyer(calculator, mock_db):
    """Test complete score for very early buyer."""
    from src.db.models import Token, Trade

    # Rank: 1st buyer (0 before, 100 total)
    # MC: Very low ($30k)
    # Volume: 10% participation

    mock_token = Token(token_address="0xtoken", chain_id="ethereum", liquidity_usd=10000.0)
    mock_buy = Trade(wallet="0xwallet", token_address="0xtoken", usd_value=1000.0)

    def query_side_effect(*args, **kwargs):
        mock_query = Mock()
        mock_query.filter.return_value.scalar.side_effect = [0, 100, 10000.0]
        mock_query.filter.return_value.first.side_effect = [mock_token, mock_buy]
        return mock_query

    mock_db.query.side_effect = query_side_effect

    # This is a simplified test; full integration would test calculate_score
    # Here we just verify components work

    rank_score = calculator._calculate_rank_score("0xtoken", datetime.utcnow())
    assert rank_score == pytest.approx(40.0, rel=0.1)
