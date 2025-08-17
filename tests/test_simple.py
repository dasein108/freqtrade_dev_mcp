#!/usr/bin/env python3
"""Simple test script to verify MCP server works."""

import sys
import os
sys.path.insert(0, '/Users/dasein/dev/freqtrade')
sys.path.insert(0, os.path.dirname(__file__))

from src.server import FreqtradeMCPServer
from src.config import Config

def test_basic_functionality():
    """Test basic server functionality."""
    # Test config creation
    config = Config()
    print(f"✅ Config created with freqtrade_path: {config.freqtrade_path}")
    
    # Test server creation
    server = FreqtradeMCPServer(config)
    print(f"✅ Server created with {len(server.commands)} commands")
    
    # Test commands are available
    expected_commands = ["download_candles", "backtest_strategy", "hyperopt_strategy", "list_results", "get_result"]
    for cmd in expected_commands:
        assert cmd in server.commands, f"Command {cmd} not found"
    print(f"✅ All expected commands available: {list(server.commands.keys())}")
    
    print("✅ All basic tests passed!")

if __name__ == "__main__":
    test_basic_functionality()