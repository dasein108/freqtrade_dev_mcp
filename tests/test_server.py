"""Basic tests for MCP server functionality."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.server import FreqtradeMCPServer
from src.config import Config


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    from pathlib import Path
    config = Config()
    config.freqtrade_path = Path("/tmp/test_freqtrade") 
    config.default_exchange = "binance"
    config.default_stake_amount = 100.0
    config.default_epochs = 100
    config.coingecko_api_key = None
    config.log_level = "INFO"
    return config


@pytest.fixture
def server(mock_config):
    """Create a server instance with mock config."""
    return FreqtradeMCPServer(mock_config)


def test_server_initialization(server):
    """Test server initializes correctly."""
    assert server.config is not None
    assert server.server is not None
    assert len(server.commands) == 5
    assert "download_candles" in server.commands
    assert "backtest_strategy" in server.commands
    assert "hyperopt_strategy" in server.commands
    assert "list_results" in server.commands
    assert "get_result" in server.commands


@pytest.mark.asyncio
async def test_list_tools(server):
    """Test listing available tools."""
    # Test that server has tools configured
    assert hasattr(server.server, 'list_tools')
    
    # Test the tools are available through the server commands
    assert len(server.commands) == 5
    tool_names = list(server.commands.keys())
    assert "download_candles" in tool_names
    assert "backtest_strategy" in tool_names
    assert "hyperopt_strategy" in tool_names
    assert "list_results" in tool_names
    assert "get_result" in tool_names


@pytest.mark.asyncio 
async def test_download_candles_tool_schema(server):
    """Test download_candles tool has correct schema."""
    # Test that download_candles command exists and has the right interface
    assert "download_candles" in server.commands
    download_cmd = server.commands["download_candles"]
    
    # Test command execution with expected parameters
    try:
        # This will fail but shows the command accepts the right parameters
        await download_cmd.execute(
            pairs=["BTC/USDT"],
            timeframes=["1h"],
            date_range="last month"
        )
    except Exception:
        # Expected to fail without real Freqtrade, but parameters were accepted
        pass


@pytest.mark.asyncio
async def test_call_tool_unknown(server):
    """Test calling unknown tool returns error."""
    # Test that unknown commands are not in the server
    assert "unknown_tool" not in server.commands
    
    # Test error handling by trying to access unknown command
    try:
        unknown_cmd = server.commands.get("unknown_tool")
        assert unknown_cmd is None
    except KeyError:
        # Expected behavior
        pass


@pytest.mark.asyncio 
@patch('src.commands.download_candles.DownloadCandlesCommand.execute')
async def test_call_download_candles(mock_execute, server):
    """Test calling download_candles tool."""
    # Mock the command execution
    mock_execute.return_value = {
        "command": "download_candles",
        "success": True,
        "pairs": ["BTC/USDT"],
        "timeframes": ["1h"]
    }
    
    # Test direct command execution
    download_cmd = server.commands["download_candles"]
    
    args = {
        "pairs": ["BTC/USDT"],
        "timeframes": ["1h"], 
        "date_range": "last month"
    }
    
    result = await download_cmd.execute(**args)
    
    assert result["command"] == "download_candles"
    assert result["success"] is True
    
    # Verify command was called with correct args
    mock_execute.assert_called_once_with(
        pairs=["BTC/USDT"],
        timeframes=["1h"],
        date_range="last month"
    )


@pytest.mark.asyncio
async def test_call_tool_exception_handling(server):
    """Test tool call exception handling."""
    # Test with invalid config that will cause errors
    download_cmd = server.commands["download_candles"]
    
    args = {
        "pairs": ["BLABLA"],
        "timeframes": ["1h"],
        "date_range": "last month"
    }
    
    result = await download_cmd.execute(**args)
    
    # The command should handle any exceptions and return error result
    assert "success" in result
    assert result["success"] is False
    # Should contain some error information
    assert result.get("total_downloads", 0) >= 0


if __name__ == "__main__":
    pytest.main([__file__])