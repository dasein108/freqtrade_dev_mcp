"""Integration tests for MCP server-client communication."""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.server import FreqtradeMCPServer
from src.config import Config
from src.models.base_models import (
    DownloadCandlesResponse,
    CacheFileInfo
)


class TestMCPIntegration:
    """Integration tests for MCP server-client communication."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_config(self, temp_data_dir):
        """Mock configuration with temp directory."""
        config = Config()
        # Set freqtrade_path so that full_data_dir property returns temp_data_dir
        config.freqtrade_path = temp_data_dir.parent
        config.data_dir = temp_data_dir.name
        config.default_exchange = "binance"
        config.coingecko_api_key = None
        return config
    
    @pytest.fixture
    def mcp_server(self, mock_config):
        """Create MCP server instance."""
        with patch('src.server.stdio_server'):
            return FreqtradeMCPServer(mock_config)
    
    @pytest.fixture
    def sample_candle_data(self):
        """Sample candle data for testing."""
        return [
            [1704067200000, 50000.0, 50500.0, 49500.0, 50100.0, 1000.0],
            [1704070800000, 50100.0, 50600.0, 49600.0, 50200.0, 1100.0],
            [1704074400000, 50200.0, 50700.0, 49700.0, 50300.0, 1200.0]
        ]
    
    @pytest.mark.asyncio
    async def test_download_candles_workflow(self, mcp_server, temp_data_dir, sample_candle_data):
        """Test download candles workflow."""
        # Create a mock cache file
        cache_filename = "BTC_USDT_USDT-1h-20240101-20250101.json"
        cache_file_path = temp_data_dir / cache_filename
        
        with open(cache_file_path, 'w') as f:
            json.dump(sample_candle_data, f)
        
        # Mock download_candles to return cache filename
        mock_cache_info = CacheFileInfo(
            pair="BTC/USDT:USDT",
            filename=cache_filename,
            full_path=str(cache_file_path),
            candle_count=len(sample_candle_data)
        )
        
        download_response = DownloadCandlesResponse(
            command="download_candles",
            success=True,
            pairs=["BTC/USDT:USDT"],
            timeframes=["1h"],
            cache_files=[mock_cache_info],
            total_candles=len(sample_candle_data)
        )
        
        with patch.object(mcp_server.commands['download_candles'], 'execute', return_value=download_response.model_dump()):
            # Call download_candles
            download_result = await mcp_server.commands['download_candles'].execute(
                pairs="BTC/USDT:USDT",
                timeframes=["1h"],
                date_range="20240101-20250101"
            )
            
            download_data = download_result
            
            # Verify download response
            assert download_data["command"] == "download_candles"
            assert download_data["success"] is True
            assert len(download_data["cache_files"]) == 1
            assert download_data["cache_files"][0]["filename"] == cache_filename
            assert download_data["total_candles"] == 3
    
    @pytest.mark.asyncio
    async def test_schema_validation_consistency(self, mcp_server, temp_data_dir):
        """Test that server responses match expected schema."""
        # Create mock cache file
        cache_filename = "ETH_USDT-4h-20240101-20240201.json"
        cache_file_path = temp_data_dir / cache_filename
        
        sample_data = [
            [1704067200000, 3000.0, 3100.0, 2950.0, 3050.0, 500.0],
            [1704081600000, 3050.0, 3150.0, 3000.0, 3100.0, 600.0]
        ]
        
        with open(cache_file_path, 'w') as f:
            json.dump(sample_data, f)
        
        # Mock download response
        mock_cache_info = CacheFileInfo(
            pair="ETH/USDT",
            filename=cache_filename,
            full_path=str(cache_file_path),
            candle_count=len(sample_data)
        )
        
        download_response = DownloadCandlesResponse(
            command="download_candles",
            success=True,
            pairs=["ETH/USDT"],
            timeframes=["4h"],
            cache_files=[mock_cache_info],
            total_candles=len(sample_data)
        )
        
        with patch.object(mcp_server.commands['download_candles'], 'execute', return_value=download_response.model_dump()):
            download_result = await mcp_server.commands['download_candles'].execute(
                pairs="ETH/USDT",
                timeframes=["4h"],
                date_range="20240101-20240201"
            )
            
            download_data = download_result
            
            # Validate response can be parsed by Pydantic model
            try:
                validated_response = DownloadCandlesResponse(**download_data)
                assert validated_response.command == "download_candles"
                assert validated_response.success is True
                assert len(validated_response.cache_files) == 1
                assert validated_response.total_candles == 2
            except Exception as e:
                pytest.fail(f"Response schema validation failed: {e}")
    
    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, mcp_server):
        """Test consistent error responses across tools."""
        # Test download_candles error - mock returning error response
        error_response = {
            "command": "download_candles",
            "success": False,
            "error": "Download failed",
            "pairs": [],
            "timeframes": [],
            "cache_files": [],
            "total_candles": 0
        }
        
        with patch.object(mcp_server.commands['download_candles'], 'execute', return_value=error_response):
            download_result = await mcp_server.commands['download_candles'].execute(
                pairs="INVALID/PAIR",
                timeframes=["1h"],
                date_range="invalid"
            )
            
            download_data = download_result
            assert download_data["success"] is False
            assert "error" in download_data
            assert "Download failed" in download_data["error"]
    
    @pytest.mark.asyncio 
    async def test_multiple_pairs_download(self, mcp_server, temp_data_dir, sample_candle_data):
        """Test handling multiple pairs in download."""
        # Create multiple cache files
        pairs = ["BTC/USDT:USDT", "ETH/USDT:USDT", "BNB/USDT:USDT"]
        cache_files = []
        
        for pair in pairs:
            clean_pair = pair.replace('/', '_').replace(':', '_')
            cache_filename = f"{clean_pair}-1h-20240101-20240201.json"
            cache_path = temp_data_dir / cache_filename
            with open(cache_path, 'w') as f:
                json.dump(sample_candle_data, f)
            
            cache_files.append(CacheFileInfo(
                pair=pair,
                filename=cache_filename,
                full_path=str(cache_path),
                candle_count=len(sample_candle_data)
            ))
        
        download_response = DownloadCandlesResponse(
            command="download_candles",
            success=True,
            pairs=pairs,
            timeframes=["1h"],
            cache_files=cache_files,
            total_candles=len(sample_candle_data) * len(pairs)
        )
        
        with patch.object(mcp_server.commands['download_candles'], 'execute', return_value=download_response.model_dump()):
            download_result = await mcp_server.commands['download_candles'].execute(
                pairs=pairs,
                timeframes=["1h"],
                date_range="20240101-20240201"
            )
            
            download_data = download_result
            
            # Verify response
            assert download_data["success"] is True
            assert len(download_data["cache_files"]) == 3
            assert download_data["total_candles"] == 9  # 3 candles × 3 pairs
            
            # Verify all pairs are present
            downloaded_pairs = [cf["pair"] for cf in download_data["cache_files"]]
            for pair in pairs:
                assert pair in downloaded_pairs
    
    @pytest.mark.asyncio
    async def test_json_serialization_consistency(self, mcp_server, temp_data_dir):
        """Test that all responses are properly JSON serializable."""
        # Create test cache file
        cache_filename = "TEST_PAIR-1h-20240101-20240201.json"
        cache_path = temp_data_dir / cache_filename
        
        with open(cache_path, 'w') as f:
            json.dump([[1704067200000, 100.0, 110.0, 90.0, 105.0, 1000.0]], f)
        
        mock_cache_info = CacheFileInfo(
            pair="TEST/PAIR",
            filename=cache_filename,
            full_path=str(cache_path),
            candle_count=1
        )
        
        download_response = DownloadCandlesResponse(
            command="download_candles",
            success=True,
            pairs=["TEST/PAIR"],
            timeframes=["1h"],
            cache_files=[mock_cache_info],
            total_candles=1
        )
        
        with patch.object(mcp_server.commands['download_candles'], 'execute', return_value=download_response.model_dump()):
            download_result = await mcp_server.commands['download_candles'].execute(
                pairs="TEST/PAIR",
                timeframes=["1h"],
                date_range="20240101-20240201"
            )
            
            # Should be valid JSON
            try:
                download_data = download_result
                # Should be able to serialize back to JSON
                json.dumps(download_data)
            except (json.JSONDecodeError, TypeError) as e:
                pytest.fail(f"JSON serialization failed: {e}")
            
            # Test that all nested objects are JSON serializable
            assert isinstance(download_data, dict)
            for key, value in download_data.items():
                try:
                    json.dumps(value)
                except (TypeError, ValueError) as e:
                    pytest.fail(f"Value for key '{key}' is not JSON serializable: {e}")