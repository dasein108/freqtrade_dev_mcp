"""Integration tests for the Freqtrade MCP server."""

import pytest
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestServerIntegration:
    """Test server integration and functionality."""

    def test_server_imports(self):
        """Test that all server components import correctly."""
        from server import FreqtradeMCPServer
        from config import Config
        from commands.base import BaseCommand
        assert FreqtradeMCPServer is not None
        assert Config is not None
        assert BaseCommand is not None

    def test_server_initialization(self):
        """Test server initialization."""
        from server import FreqtradeMCPServer
        
        server = FreqtradeMCPServer()
        assert server is not None
        assert len(server.commands) == 12
        assert "download_candles" in server.commands
        assert "backtest_strategy" in server.commands
        assert "hyperopt_strategy" in server.commands
        assert "list_results" in server.commands
        assert "get_result" in server.commands
        assert "create_userdir" in server.commands
        assert "create_config" in server.commands
        assert "create_strategy" in server.commands
        assert "create_strategy_wireframe" in server.commands
        assert "extract_backtest_data" in server.commands
        assert "extract_hyperopt_data" in server.commands
        assert "search_results" in server.commands

    def test_config_loading(self):
        """Test configuration loading."""
        from config import Config
        
        config = Config()
        assert config.freqtrade_path is not None
        assert config.default_exchange == "binance"
        assert config.default_stake_amount == 100.0

    def test_date_parser(self):
        """Test date parsing functionality."""
        from utils.date_parser import parse_and_format_date
        
        # Test various date formats
        result = parse_and_format_date("last month")
        assert result is not None
        assert len(result.split('-')) == 2  # Should be in format YYYYMMDD-YYYYMMDD

    def test_coingecko_client(self):
        """Test CoinGecko client initialization."""
        from utils.coingecko import CoinGeckoClient
        
        client = CoinGeckoClient()
        assert client is not None
        
    @pytest.mark.asyncio
    async def test_command_execution_structure(self):
        """Test that commands have proper execution structure."""
        from server import FreqtradeMCPServer
        
        server = FreqtradeMCPServer()
        
        # Test that all commands have execute method
        for name, command in server.commands.items():
            assert hasattr(command, 'execute'), f"Command {name} missing execute method"
            assert asyncio.iscoroutinefunction(command.execute), f"Command {name} execute is not async"


class TestToolsListGeneration:
    """Test MCP tools list generation."""

    def test_tools_list(self):
        """Test that server generates proper tools list."""
        from server import FreqtradeMCPServer
        
        server = FreqtradeMCPServer()
        tools = server.list_tools()
        
        assert len(tools) == 12
        tool_names = [tool.name for tool in tools]
        
        expected_tools = [
            "download_candles", 
            "backtest_strategy", 
            "hyperopt_strategy", 
            "list_results", 
            "get_result",
            "create_userdir",
            "create_config", 
            "create_strategy",
            "create_strategy_wireframe",
            "extract_backtest_data",
            "extract_hyperopt_data",
            "search_results"
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    def test_tool_descriptions(self):
        """Test that all tools have proper descriptions."""
        from server import FreqtradeMCPServer
        
        server = FreqtradeMCPServer()
        tools = server.list_tools()
        
        for tool in tools:
            assert tool.description is not None
            assert len(tool.description) > 10  # Should have meaningful description
            assert tool.inputSchema is not None