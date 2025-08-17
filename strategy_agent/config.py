"""
Configuration for the Strategy Development Agent
"""
import os
from pathlib import Path
from typing import Optional


class AgentConfig:
    """Configuration for the strategy development agent"""
    
    def __init__(self):
        # MCP Server
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        
        # Paths
        self.cache_dir = Path(os.getenv("CACHE_DIR", "./cache"))
        self.freqtrade_user_data = Path(os.getenv("FREQTRADE_USER_DATA", "../../user_data"))
        
        # Strategy Development
        self.max_iterations = int(os.getenv("MAX_ITERATIONS", "3"))
        self.hyperopt_epochs = int(os.getenv("HYPEROPT_EPOCHS", "100"))
        self.min_profit_threshold = float(os.getenv("MIN_PROFIT_THRESHOLD", "5.0"))
        
        # OpenAI API
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_code_model = os.getenv("OPENAI_CODE_MODEL", "gpt-4o")
        
        # Default Trading Pairs
        self.default_symbols = [
            "BTC/USDT:USDT",
            "ETH/USDT:USDT",
            "SOL/USDT:USDT"
        ]
        self.default_timeframes = ["1h", "4h"]
        
        # Hyperopt Configuration
        self.hyperopt_loss_function = "SharpeHyperOptLoss"
        self.hyperopt_spaces = ["buy", "sell", "roi", "stoploss"]
        
        # Backtest Configuration
        self.backtest_timerange = "20240101-20250101"
        self.max_open_trades = 3
        self.stake_amount = 100
        self.stake_currency = "USDT"
        
        # Performance Thresholds
        self.min_sharpe_ratio = 0.5
        self.max_drawdown_pct = 20.0
        self.min_win_rate_pct = 35.0
        self.min_trades = 50
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Create directories if they don't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def get_strategy_dir(self) -> Path:
        """Get the strategies directory path"""
        return self.freqtrade_user_data / "strategies"
    
    def get_backtest_results_dir(self) -> Path:
        """Get the backtest results directory path"""
        return self.freqtrade_user_data / "backtest_results"
    
    def get_hyperopt_results_dir(self) -> Path:
        """Get the hyperopt results directory path"""
        return self.freqtrade_user_data / "hyperopt_results"
    
    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "mcp_server_url": self.mcp_server_url,
            "cache_dir": str(self.cache_dir),
            "freqtrade_user_data": str(self.freqtrade_user_data),
            "max_iterations": self.max_iterations,
            "hyperopt_epochs": self.hyperopt_epochs,
            "min_profit_threshold": self.min_profit_threshold,
            "default_symbols": self.default_symbols,
            "default_timeframes": self.default_timeframes,
            "hyperopt_loss_function": self.hyperopt_loss_function,
            "backtest_timerange": self.backtest_timerange,
            "performance_thresholds": {
                "min_sharpe_ratio": self.min_sharpe_ratio,
                "max_drawdown_pct": self.max_drawdown_pct,
                "min_win_rate_pct": self.min_win_rate_pct,
                "min_trades": self.min_trades
            }
        }


# Global config instance
config = AgentConfig()