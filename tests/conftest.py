"""
Pytest configuration and fixtures for Freqtrade MCP tests.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

@pytest.fixture
def mock_config():
    """Provide a mock configuration for testing."""
    from config import Config
    from pathlib import Path
    
    # Create a test config with temporary paths
    config = Config()
    config.freqtrade_path = Path("/tmp/test_freqtrade")
    config.data_dir = "test_data"
    config.strategy_dir = "test_strategies"
    config.backtest_results_dir = "test_backtest_results"
    config.hyperopt_results_dir = "test_hyperopt_results"
    
    return config

@pytest.fixture
def mock_server():
    """Provide a mock MCP server for testing."""
    from server import FreqtradeMCPServer
    
    # Create server with mock config
    return FreqtradeMCPServer()