"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.config import Config


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config(temp_data_dir):
    """Create a test configuration."""
    config = Config()
    config.full_data_dir = temp_data_dir
    config.default_exchange = "binance"
    config.coingecko_api_key = None
    config.freqtrade_config_dir = temp_data_dir / "config"
    config.freqtrade_config_dir.mkdir(exist_ok=True)
    return config


@pytest.fixture
def mock_mcp_server():
    """Create a mock MCP server for testing."""
    server = MagicMock()
    server.send_log_message = MagicMock()
    return server


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data in freqtrade format."""
    return [
        [1704067200000, 50000.0, 50500.0, 49500.0, 50100.0, 1000.0],  # [timestamp, o, h, l, c, v]
        [1704070800000, 50100.0, 50600.0, 49600.0, 50200.0, 1100.0],
        [1704074400000, 50200.0, 50700.0, 49700.0, 50300.0, 1200.0]
    ]


@pytest.fixture
def sample_cache_files():
    """Sample cache filenames for testing."""
    return [
        "BTC_USDT_USDT-1h-20240101-20250101.json",
        "ETH_USDT_USDT-1h-20240101-20250101.json",
        "BNB_USDT-5m-20240101-20240201.json"
    ]


@pytest.fixture
def sample_pairs():
    """Sample trading pairs for testing."""
    return [
        "BTC/USDT:USDT",  # Futures
        "ETH/USDT:USDT",  # Futures
        "BNB/USDT",       # Spot
        "ADA/USDT"        # Spot
    ]


# Configure asyncio for pytest-asyncio
pytestmark = pytest.mark.asyncio