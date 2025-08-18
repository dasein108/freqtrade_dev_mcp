"""
Configuration for the Strategy Development Agent
"""
import os
from pathlib import Path
from typing import Optional
import dotenv

dotenv.load_dotenv()

class AgentConfig:
    """Configuration for the strategy development agent"""
    
    def __init__(self):
        # MCP Server (stdio-based, no URL needed)
        self.mcp_server_path = os.getenv("MCP_SERVER_PATH", "../src/server.py")
        
        # Paths
        self.cache_dir = Path(os.getenv("CACHE_DIR", "./cache"))
        self.freqtrade_user_data = Path(os.getenv("FREQTRADE_USER_DATA", "../../user_data"))
        
        # Strategy Development
        self.max_iterations = int(os.getenv("MAX_ITERATIONS", "3"))
        self.hyperopt_epochs = int(os.getenv("HYPEROPT_EPOCHS", "100"))
        self.min_profit_threshold = float(os.getenv("MIN_PROFIT_THRESHOLD", "5.0"))
        
        # LLM Configuration (supports multiple providers)
        self.llm_model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
        self.llm_api_key = os.getenv("LLM_API_KEY")
        # self.llm_code_model = os.getenv("LLM_CODE_MODEL", "openai/gpt-4o")
        self.llm_code_model = self.llm_model
        # self.llm_base_url = os.getenv("LLM_BASE_URL")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS")) if os.getenv("LLM_MAX_TOKENS") else None
        self.llm_timeout = int(os.getenv("LLM_TIMEOUT", "300"))
        
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
        if not self.llm_api_key:
            raise ValueError("LLM_API_KEY environment variable is required")
        
        if not self.llm_model:
            raise ValueError("LLM_MODEL environment variable is required")
        
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
    
    def get_llm_config(self) -> dict:
        """Get LLM configuration for the client factory"""
        config = {
            "model": self.llm_model,
            "api_key": self.llm_api_key,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
            "timeout": self.llm_timeout
        }
        # Only include base_url if it's set (not used by current LLMConfig)
        # if self.llm_base_url:
        #     config["base_url"] = self.llm_base_url
        return config
    
    def get_llm_code_config(self) -> dict:
        """Get LLM configuration for code generation"""
        config = self.get_llm_config()
        config["model"] = self.llm_code_model
        config["temperature"] = 0.1  # Lower temperature for code generation
        return config
    
    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "mcp_server_path": self.mcp_server_path,
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