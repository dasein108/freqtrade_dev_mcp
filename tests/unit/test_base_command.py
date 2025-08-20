"""Unit tests for base command functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import asyncio
from pathlib import Path

from src.commands.base import BaseCommand


class MockCommand(BaseCommand):
    """Mock command implementation for testing."""
    
    async def execute(self, **kwargs):
        """Mock execute method."""
        return {"test": "result"}


class TestBaseCommand:
    """Test BaseCommand class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.full_data_dir = Path("/tmp/test_data")
        config.default_exchange = "binance"
        config.freqtrade_config_dir = Path("/tmp/config")
        config.freqtrade_path = Path("/tmp/freqtrade")
        config.full_strategy_dir = Path("/tmp/strategies")
        return config
    
    @pytest.fixture
    def mock_server(self):
        """Mock MCP server."""
        server = MagicMock()
        server.log_info = AsyncMock()
        server.log_warning = AsyncMock()
        server.log_error = AsyncMock()
        return server
    
    @pytest.fixture
    def command(self, mock_config, mock_server):
        """Create command instance."""
        return MockCommand(mock_config, mock_server)
    
    def test_command_initialization(self, command, mock_config, mock_server):
        """Test command initialization."""
        assert command.config == mock_config
        assert command.server == mock_server
    
    @pytest.mark.asyncio
    async def test_mcp_log_with_server(self, command):
        """Test MCP logging when server is available."""
        await command.mcp_log("info", "Test message")
        
        # Verify server logging was called
        command.server.log_info.assert_called_once_with("Test message")
    
    @pytest.mark.asyncio
    async def test_mcp_log_without_server(self, mock_config):
        """Test MCP logging when server is not available."""
        command = MockCommand(mock_config, None)
        
        # Should not raise exception when server is None
        await command.mcp_log("info", "Test message")
        
        # No server to verify, just ensure it doesn't crash
        assert command.server is None
    
    @pytest.mark.asyncio
    async def test_mcp_log_invalid_level(self, command):
        """Test MCP logging with invalid log level."""
        # Should handle invalid log levels gracefully
        await command.mcp_log("invalid_level", "Test message")
        
        # Should not call any specific log method
        command.server.log_info.assert_not_called()
        command.server.log_warning.assert_not_called()
        command.server.log_error.assert_not_called()
    
    def test_get_freqtrade_config(self, command):
        """Test freqtrade config generation."""
        config = command.get_freqtrade_config()
        
        assert isinstance(config, dict)
        assert "datadir" in config
        assert "user_data_dir" in config
        assert "strategy_path" in config
        assert config["datadir"] == command.config.full_data_dir
    
    def test_get_freqtrade_config_basic_structure(self, command):
        """Test freqtrade config basic structure."""
        config = command.get_freqtrade_config()
        
        assert isinstance(config, dict)
        assert len(config) >= 3  # Should have at least 3 keys
        assert all(key in config for key in ["datadir", "user_data_dir", "strategy_path"])
    
    @pytest.mark.asyncio
    async def test_run_freqtrade_command_success(self, command):
        """Test running freqtrade command successfully."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"success output", b"")
        mock_process.returncode = 0
        
        with patch('src.commands.base.asyncio.create_subprocess_exec', return_value=mock_process):
            result = await command.run_freqtrade_command(["backtesting", "--help"])
            
            assert result["success"] is True
            assert result["returncode"] == 0
            assert result["stdout"] == "success output"
            assert result["stderr"] == ""
    
    @pytest.mark.asyncio
    async def test_run_freqtrade_command_failure(self, command):
        """Test running freqtrade command that fails."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"error output")
        mock_process.returncode = 1
        
        with patch('src.commands.base.asyncio.create_subprocess_exec', return_value=mock_process):
            result = await command.run_freqtrade_command(["invalid-command"])
            
            assert result["success"] is False
            assert result["returncode"] == 1
            assert result["stdout"] == ""
            assert result["stderr"] == "error output"
    
    @pytest.mark.asyncio
    async def test_run_freqtrade_command_timeout(self, command):
        """Test freqtrade command timeout."""
        mock_process = AsyncMock()
        
        with patch('src.commands.base.asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('src.commands.base.asyncio.wait_for', side_effect=asyncio.TimeoutError()):
                result = await command.run_freqtrade_command(["long-running"], timeout=1)
                
                assert result["success"] is False
                assert "timeout" in result["stderr"].lower()
    
    @pytest.mark.asyncio
    async def test_run_freqtrade_command_exception(self, command):
        """Test freqtrade command with exception."""
        with patch('src.commands.base.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Process creation failed")
            
            result = await command.run_freqtrade_command(["test"])
            
            assert result["success"] is False
            assert "Process creation failed" in result["stderr"]
    
    def test_abstract_execute_method(self, mock_config):
        """Test that base command is abstract."""
        # BaseCommand should not be instantiated directly due to abstract execute method
        with pytest.raises(TypeError, match="Can't instantiate abstract class BaseCommand"):
            BaseCommand(mock_config)
        
        # Our MockCommand implements execute, so it should work
        command = MockCommand(mock_config)
        assert command is not None
    
    @pytest.mark.asyncio
    async def test_execute_implementation(self, command):
        """Test that our test command's execute works."""
        result = await command.execute(test_param="value")
        
        assert result == {"test": "result"}
    
    def test_config_access(self, command, mock_config):
        """Test config property access."""
        assert command.config == mock_config
        assert command.config.full_data_dir == Path("/tmp/test_data")
        assert command.config.default_exchange == "binance"
    
    def test_server_access(self, command, mock_server):
        """Test server property access."""
        assert command.server == mock_server
        assert hasattr(command.server, 'send_log_message')