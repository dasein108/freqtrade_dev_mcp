"""Unit tests for base Pydantic models."""

import pytest
from pydantic import ValidationError

import sys
from pathlib import Path
# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.base_models import (
    MCPBaseResponse,
    CacheFileInfo,
    DownloadCandlesResponse,
    PerformanceMetrics,
    BacktestResponse,
    HyperoptResponse,
    create_error_response,
    create_success_response
)


class TestMCPBaseResponse:
    """Test MCPBaseResponse model."""
    
    def test_valid_response(self):
        """Test valid response creation."""
        response = MCPBaseResponse(
            command="test_command",
            success=True,
            duration_seconds=1.5
        )
        
        assert response.command == "test_command"
        assert response.success is True
        assert response.error is None
        assert response.duration_seconds == 1.5
    
    def test_error_response(self):
        """Test error response creation."""
        response = MCPBaseResponse(
            command="test_command",
            success=False,
            error="Test error message"
        )
        
        assert response.command == "test_command"
        assert response.success is False
        assert response.error == "Test error message"
    
    def test_missing_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as excinfo:
            MCPBaseResponse()
        
        error = excinfo.value
        assert "command" in str(error)
        assert "success" in str(error)
    
    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValidationError) as excinfo:
            MCPBaseResponse(
                command="test",
                success=True,
                extra_field="should_fail"
            )
        
        assert "extra_field" in str(excinfo.value)


class TestCacheFileInfo:
    """Test CacheFileInfo model."""
    
    def test_valid_cache_file_info(self):
        """Test valid cache file info creation."""
        cache_info = CacheFileInfo(
            pair="BTC/USDT:USDT",
            filename="BTC_USDT_USDT-1h-20240101-20250101.json",
            full_path="/data/BTC_USDT_USDT-1h-20240101-20250101.json",
            candle_count=8760
        )
        
        assert cache_info.pair == "BTC/USDT:USDT"
        assert cache_info.filename == "BTC_USDT_USDT-1h-20240101-20250101.json"
        assert cache_info.candle_count == 8760
    
    def test_default_candle_count(self):
        """Test default candle count."""
        cache_info = CacheFileInfo(
            pair="BTC/USDT",
            filename="test.json",
            full_path="/test.json"
        )
        
        assert cache_info.candle_count == 0
    
    def test_missing_required_fields(self):
        """Test required field validation."""
        with pytest.raises(ValidationError):
            CacheFileInfo(filename="test.json")


class TestDownloadCandlesResponse:
    """Test DownloadCandlesResponse model."""
    
    def test_valid_download_response(self):
        """Test valid download response."""
        cache_file = CacheFileInfo(
            pair="BTC/USDT:USDT",
            filename="test.json",
            full_path="/test.json",
            candle_count=100
        )
        
        response = DownloadCandlesResponse(
            command="download_candles",
            success=True,
            pairs=["BTC/USDT:USDT"],
            timeframes=["1h"],
            cache_files=[cache_file],
            total_candles=100
        )
        
        assert response.command == "download_candles"
        assert response.success is True
        assert response.pairs == ["BTC/USDT:USDT"]
        assert response.timeframes == ["1h"]
        assert len(response.cache_files) == 1
        assert response.total_candles == 100
    
    def test_empty_cache_files(self):
        """Test with empty cache files list."""
        response = DownloadCandlesResponse(
            command="download_candles",
            success=False,
            pairs=["BTC/USDT:USDT"],
            timeframes=["1h"],
            error="Download failed"
        )
        
        assert len(response.cache_files) == 0
        assert response.total_candles == 0


class TestPerformanceMetrics:
    """Test PerformanceMetrics model."""
    
    def test_valid_metrics(self):
        """Test valid performance metrics."""
        metrics = PerformanceMetrics(
            total_profit_pct=15.5,
            total_trades=100,
            win_rate=0.65,
            max_drawdown_pct=8.2,
            sharpe_ratio=1.25
        )
        
        assert metrics.total_profit_pct == 15.5
        assert metrics.total_trades == 100
        assert metrics.win_rate == 0.65
        assert metrics.max_drawdown_pct == 8.2
        assert metrics.sharpe_ratio == 1.25
    
    def test_optional_fields(self):
        """Test that optional fields work."""
        metrics = PerformanceMetrics(
            total_profit_pct=10.0,
            total_trades=50,
            win_rate=0.6,
            max_drawdown_pct=5.0
        )
        
        assert metrics.sharpe_ratio is None


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_error_response(self):
        """Test error response creation."""
        response = create_error_response(
            command="test_command",
            error="Test error",
            duration=1.5
        )
        
        assert response.command == "test_command"
        assert response.success is False
        assert response.error == "Test error"
        assert response.duration_seconds == 1.5
    
    def test_create_success_response(self):
        """Test success response creation."""
        response = create_success_response(
            command="test_command",
            duration=2.0
        )
        
        assert response.command == "test_command"
        assert response.success is True
        assert response.error is None
        assert response.duration_seconds == 2.0