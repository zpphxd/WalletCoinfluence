"""Unit tests for confluence detection."""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.alerts.confluence import ConfluenceDetector


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.zadd = Mock()
    redis_mock.expire = Mock()
    redis_mock.zrange = Mock(return_value=[])
    redis_mock.zremrangebyscore = Mock()
    redis_mock.zcard = Mock(return_value=0)
    redis_mock.delete = Mock()
    return redis_mock


@pytest.fixture
def detector(mock_redis):
    """Confluence detector with mocked Redis."""
    return ConfluenceDetector(redis_client=mock_redis)


def test_record_buy(detector, mock_redis):
    """Test recording a buy event."""
    detector.record_buy(
        token_address="0xtoken",
        chain_id="ethereum",
        wallet_address="0xwallet",
        metadata={"price": 1.23, "tx_hash": "0x123"},
    )

    # Verify zadd called with correct key
    mock_redis.zadd.assert_called_once()
    args = mock_redis.zadd.call_args

    key = args[0][0]
    assert key == "confluence:ethereum:0xtoken"

    # Verify expire set
    mock_redis.expire.assert_called_once()


def test_no_confluence_single_wallet(detector, mock_redis):
    """Test no confluence with only one wallet."""
    # Mock one entry
    entry = json.dumps({
        "wallet": "0xwallet1",
        "ts": datetime.utcnow().timestamp(),
    })

    mock_redis.zrange.return_value = [entry]

    result = detector.check_confluence("0xtoken", "ethereum", min_wallets=2)

    assert result is None


def test_confluence_detected(detector, mock_redis):
    """Test confluence with multiple wallets."""
    now = datetime.utcnow().timestamp()

    # Mock three different wallets
    entries = [
        json.dumps({"wallet": "0xwallet1", "ts": now - 60}),
        json.dumps({"wallet": "0xwallet2", "ts": now - 30}),
        json.dumps({"wallet": "0xwallet3", "ts": now}),
    ]

    mock_redis.zrange.return_value = entries

    result = detector.check_confluence("0xtoken", "ethereum", min_wallets=2)

    assert result is not None
    assert len(result) == 3
    assert result[0]["wallet"] == "0xwallet1"
    assert result[1]["wallet"] == "0xwallet2"


def test_confluence_duplicate_wallet(detector, mock_redis):
    """Test that duplicate wallets are filtered."""
    now = datetime.utcnow().timestamp()

    # Same wallet buying twice
    entries = [
        json.dumps({"wallet": "0xwallet1", "ts": now - 60}),
        json.dumps({"wallet": "0xwallet1", "ts": now - 30}),
        json.dumps({"wallet": "0xwallet2", "ts": now}),
    ]

    mock_redis.zrange.return_value = entries

    result = detector.check_confluence("0xtoken", "ethereum", min_wallets=3)

    # Should be None because only 2 unique wallets
    assert result is None


def test_window_stats(detector, mock_redis):
    """Test window statistics."""
    entries = [
        json.dumps({"wallet": "0xwallet1"}),
        json.dumps({"wallet": "0xwallet2"}),
        json.dumps({"wallet": "0xwallet1"}),  # Duplicate
    ]

    mock_redis.zcard.return_value = 3
    mock_redis.zrange.return_value = entries

    stats = detector.get_window_stats("0xtoken", "ethereum")

    assert stats["total_buys"] == 3
    assert stats["unique_wallets"] == 2  # wallet1 and wallet2
    assert stats["window_minutes"] == detector.window_minutes


def test_clear_token(detector, mock_redis):
    """Test clearing confluence data."""
    detector.clear_token("0xtoken", "ethereum")

    mock_redis.delete.assert_called_once_with("confluence:ethereum:0xtoken")
