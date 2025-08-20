"""Unit tests for download_candles command."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from pathlib import Path

from src.commands.download_candles import DownloadCandlesCommand
from src.models.base_models import CacheFileInfo


class TestDownloadCandlesCommand:
    """Test DownloadCandlesCommand."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.default_exchange = "binance"
        config.coingecko_api_key = None
        config.full_data_dir = Path("/tmp/test_data")
        return config
    
    @pytest.fixture
    def command(self, mock_config):
        """Create command instance."""
        with patch('src.commands.download_candles.CoinGeckoClient'):
            return DownloadCandlesCommand(mock_config)
    
    @pytest.mark.asyncio
    async def test_execute_success(self, command):
        """Test successful execution."""
        # Mock the download methods
        mock_result = {
            "success": True,
            "cache_files": [
                CacheFileInfo(
                    pair="BTC/USDT:USDT",
                    filename="BTC_USDT_USDT-1h-20240101-20250101.json",
                    full_path="/tmp/BTC_USDT_USDT-1h-20240101-20250101.json",
                    candle_count=8760
                )
            ],
            "candle_count": 8760
        }
        
        with patch.object(command, '_download_for_timeframe', return_value=mock_result):
            with patch('src.commands.download_candles.parse_and_format_date', return_value="20240101-20250101"):
                result = await command.execute(
                    pairs=["BTC/USDT:USDT"],
                    timeframes=["1h"],
                    date_range="last year"
                )
        
        assert result["command"] == "download_candles"
        assert result["success"] is True
        assert len(result["cache_files"]) == 1
        assert result["total_candles"] == 8760
    
    @pytest.mark.asyncio
    async def test_execute_error(self, command):
        """Test execution with error."""
        with patch.object(command, '_download_for_timeframe', side_effect=Exception("Test error")):
            result = await command.execute(
                pairs=["BTC/USDT:USDT"],
                timeframes=["1h"],
                date_range="last year"
            )
        
        assert result["command"] == "download_candles"
        assert result["success"] is False
        assert "Test error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_process_pairs_string(self, command):
        """Test processing pairs as string."""
        result = await command._process_pairs("BTC/USDT", "binance")
        assert result == ["BTC/USDT"]
    
    @pytest.mark.asyncio
    async def test_process_pairs_list(self, command):
        """Test processing pairs as list."""
        pairs = ["BTC/USDT", "ETH/USDT"]
        result = await command._process_pairs(pairs, "binance")
        assert result == pairs
    
    @pytest.mark.asyncio
    async def test_process_pairs_top15(self, command):
        """Test processing 'top15' pairs."""
        mock_pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
        
        with patch.object(command.coingecko_client, 'get_top_trading_pairs', new_callable=AsyncMock, return_value=mock_pairs):
            result = await command._process_pairs("top15", "binance")
            assert result == mock_pairs
    
    @pytest.mark.asyncio
    async def test_process_pairs_top15_fallback(self, command):
        """Test fallback when top15 fails."""
        with patch.object(command.coingecko_client, 'get_top_trading_pairs', side_effect=Exception("API error")):
            result = await command._process_pairs("top15", "binance")
            
            # Should return fallback pairs
            assert isinstance(result, list)
            assert len(result) == 15
            assert "BTC/USDT" in result
    
    def test_process_timeframes_string(self, command):
        """Test processing timeframes as string."""
        result = command._process_timeframes("1h")
        assert result == ["1h"]
    
    def test_process_timeframes_all(self, command):
        """Test processing 'all' timeframes."""
        result = command._process_timeframes("all")
        expected = ["5m", "15m", "30m", "1h", "4h", "1d"]
        assert result == expected
    
    def test_process_timeframes_list(self, command):
        """Test processing timeframes as list."""
        timeframes = ["1h", "4h"]
        result = command._process_timeframes(timeframes)
        assert result == timeframes
    
    def test_generate_cache_filename(self, command):
        """Test cache filename generation."""
        filename = command._generate_cache_filename(
            "BTC/USDT:USDT", 
            "1h", 
            "20240101-20250101"
        )
        assert filename == "BTC_USDT_USDT-1h-20240101-20250101.json"
    
    def test_generate_cache_filename_special_chars(self, command):
        """Test cache filename with special characters."""
        filename = command._generate_cache_filename(
            "BTC/USDT", 
            "5m", 
            "20240101-20240201"
        )
        assert filename == "BTC_USDT-5m-20240101-20240201.json"