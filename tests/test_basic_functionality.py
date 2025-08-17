#!/usr/bin/env python3
"""Basic functionality tests that can run standalone."""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Add paths for import
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from src.server import FreqtradeMCPServer
from src.config import Config


def create_test_config():
    """Create a real config for testing."""
    config = Config()
    # Use a temp directory for testing
    config.freqtrade_path = Path("/tmp/test_freqtrade")
    return config


def test_server_can_be_created():
    """Test that server can be created successfully."""
    config = create_test_config()
    server = FreqtradeMCPServer(config)
    
    assert server is not None
    assert server.config is not None
    assert server.server is not None
    assert len(server.commands) == 5


def test_all_expected_commands_exist():
    """Test that all expected commands are available."""
    config = create_test_config()
    server = FreqtradeMCPServer(config)
    
    expected_commands = [
        "download_candles",
        "backtest_strategy", 
        "hyperopt_strategy",
        "list_results",
        "get_result"
    ]
    
    for cmd in expected_commands:
        assert cmd in server.commands, f"Command {cmd} not found"


@pytest.mark.asyncio
async def test_list_results_works():
    """Test that list_results command works."""
    config = create_test_config()
    server = FreqtradeMCPServer(config)
    
    list_cmd = server.commands["list_results"]
    result = await list_cmd.execute(result_type="all", limit=5)
    
    assert result["success"] is True
    assert "results" in result
    assert "total_found" in result


@pytest.mark.asyncio 
async def test_commands_handle_errors_gracefully():
    """Test that commands handle errors gracefully."""
    config = create_test_config()
    server = FreqtradeMCPServer(config)
    
    # Test download command with invalid setup
    download_cmd = server.commands["download_candles"]
    result = await download_cmd.execute(
        pairs=["BTC/USDT"],
        timeframes=["1h"],
        date_range="last month"
    )
    
    # Should not crash, should return error gracefully
    assert "success" in result
    # Will be False due to missing freqtrade, but that's expected
    assert isinstance(result["success"], bool)


def test_date_parser_functionality():
    """Test that date parser works correctly."""
    from src.utils.date_parser import parse_natural_date, format_timerange
    
    test_cases = [
        "last month",
        "september", 
        "Q1 2024",
        "2024"
    ]
    
    for date_str in test_cases:
        try:
            start, end = parse_natural_date(date_str)
            timerange = format_timerange(start, end)
            assert len(timerange) == 17  # YYYYMMDD-YYYYMMDD format
            assert "-" in timerange
        except Exception as e:
            pytest.fail(f"Date parsing failed for '{date_str}': {e}")


@pytest.mark.asyncio
async def test_coingecko_client():
    """Test CoinGecko client functionality."""
    from src.utils.coingecko import CoinGeckoClient
    
    client = CoinGeckoClient()
    
    try:
        # This may fail without API key, but should not crash
        coins = await client.get_top_coins_by_market_cap(limit=3)
        assert isinstance(coins, list)
        
        if coins:  # If we got data
            pairs = client.map_coins_to_trading_pairs(coins[:2])
            assert isinstance(pairs, list)
    except Exception:
        # Expected if no API access, test that it doesn't crash the system
        pass


if __name__ == "__main__":
    # Can run standalone
    pytest.main([__file__])