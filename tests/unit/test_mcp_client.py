"""Unit tests for MCP client functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from strategy_agent.mcp_client import FreqtradeMCPClient
from src.models.base_models import (
    DownloadCandlesResponse,
    CacheFileInfo
)


class TestFreqtradeMCPClient:
    """Test FreqtradeMCPClient class."""
    
    @pytest.fixture
    def mock_stdio_client(self):
        """Mock stdio client."""
        client = MagicMock()
        client.call_tool = AsyncMock()
        return client
    
    @pytest.fixture
    def mcp_client(self, mock_stdio_client):
        """Create MCP client instance."""
        with patch('strategy_agent.mcp_client.stdio_client', return_value=mock_stdio_client):
            client = FreqtradeMCPClient()
            client.session = mock_stdio_client
            client._connected = True  # Simulate connection
            return client
    
    @pytest.mark.asyncio
    async def test_download_candles_success(self, mcp_client, mock_stdio_client):
        """Test successful download_candles call."""
        # Mock server response
        mock_response = {
            "command": "download_candles",
            "success": True,
            "pairs": ["BTC/USDT:USDT"],
            "timeframes": ["1h"],
            "cache_files": [{
                "pair": "BTC/USDT:USDT",
                "filename": "BTC_USDT_USDT-1h-20240101-20250101.json",
                "full_path": "/data/BTC_USDT_USDT-1h-20240101-20250101.json",
                "candle_count": 8760
            }],
            "total_candles": 8760
        }
        
        mock_stdio_client.call_tool.return_value = MagicMock(content=[
            MagicMock(text=json.dumps(mock_response))
        ])
        
        result = await mcp_client.download_candles(
            pairs=["BTC/USDT:USDT"],
            timeframe="1h",
            days=365
        )
        
        # Verify call was made correctly
        mock_stdio_client.call_tool.assert_called_once_with(
            "download_candles",
            {
                "pairs": ["BTC/USDT:USDT"],
                "timeframes": ["1h"],
                "date_range": "last 365 days",
                "exchange": "binance",
                "trading_mode": "futures"
            }
        )
        
        # Verify response structure
        assert result["command"] == "download_candles"
        assert result["success"] is True
        assert len(result["cache_files"]) == 1
        assert result["total_candles"] == 8760
    
    @pytest.mark.asyncio
    async def test_download_candles_with_validation(self, mcp_client, mock_stdio_client):
        """Test download_candles with Pydantic validation."""
        # Mock server response
        mock_response = {
            "command": "download_candles",
            "success": True,
            "pairs": ["ETH/USDT"],
            "timeframes": ["4h"],
            "cache_files": [{
                "pair": "ETH/USDT",
                "filename": "ETH_USDT-4h-20240101-20240201.json",
                "full_path": "/data/ETH_USDT-4h-20240101-20240201.json",
                "candle_count": 744
            }],
            "total_candles": 744
        }
        
        mock_stdio_client.call_tool.return_value = MagicMock(content=[
            MagicMock(text=json.dumps(mock_response))
        ])
        
        result = await mcp_client.download_candles(
            pairs=["ETH/USDT"],
            timeframe="4h", 
            days=30,
        )
        
        # MCP client returns dict, parse to Pydantic model for validation
        assert isinstance(result, dict)
        validated_result = DownloadCandlesResponse(**result)
        assert validated_result.command == "download_candles"
        assert validated_result.success is True
        assert len(validated_result.cache_files) == 1
        assert isinstance(validated_result.cache_files[0], CacheFileInfo)
        assert validated_result.cache_files[0].pair == "ETH/USDT"
        assert validated_result.total_candles == 744
    
    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self, mcp_client, mock_stdio_client):
        """Test error handling in call_tool method."""
        # Mock connection error
        mock_stdio_client.call_tool.side_effect = Exception("Connection failed")
        
        result = await mcp_client.download_candles(
            pairs=["BTC/USDT"],
            timeframe="1h",
            days=7
        )
        
        # Should return error response
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_invalid_server_response(self, mcp_client, mock_stdio_client):
        """Test handling of invalid server responses."""
        # Mock invalid JSON response
        mock_stdio_client.call_tool.return_value = MagicMock(content=[
            MagicMock(text="invalid json response")
        ])
        
        result = await mcp_client.download_candles(
            pairs=["BTC/USDT"],
            timeframe="1h",
            days=1
        )
        
        # Should handle JSON parsing error gracefully
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_empty_server_response(self, mcp_client, mock_stdio_client):
        """Test handling of empty server responses."""
        # Mock empty response
        mock_stdio_client.call_tool.return_value = MagicMock(content=[])
        
        result = await mcp_client.download_candles(
            pairs=["BTC/USDT"],
            timeframe="1h",
            days=1
        )
        
        # Should handle empty response gracefully
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "No content in response" in result["error"]
    
    @pytest.mark.asyncio
    async def test_validation_failure(self, mcp_client, mock_stdio_client):
        """Test handling of Pydantic validation failures."""
        # Mock response with missing required fields
        mock_response = {
            "command": "download_candles",
            "success": True,
            # Missing required fields: pairs, timeframes, cache_files, total_candles
        }
        
        mock_stdio_client.call_tool.return_value = MagicMock(content=[
            MagicMock(text=json.dumps(mock_response))
        ])
        
        result = await mcp_client.download_candles(
            pairs=["BTC/USDT"],
            timeframe="1h",
            days=1,
        )
        
        # Should handle validation error gracefully  
        # When validation fails, the client falls back to returning the original dict response
        assert isinstance(result, dict)
        assert result["success"] is True  # Original response was successful
        # The validated response should have been None due to missing fields
    
    @pytest.mark.asyncio
    async def test_client_initialization_without_server(self):
        """Test client initialization when server is not available."""
        # Test error handling when calling tool without connection
        client = FreqtradeMCPClient()
        # Client not started, so should fail
        
        with pytest.raises(RuntimeError, match="MCP client not connected"):
            await client.download_candles(
                pairs=["BTC/USDT"],
                timeframe="1h",
                days=1
            )
    
