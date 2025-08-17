"""Configuration management for Freqtrade MCP server."""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Server configuration."""
    
    freqtrade_path: Path = Field(
        default=Path.home() / "freqtrade",
        description="Path to Freqtrade installation"
    )
    strategy_dir: Path = Field(
        default=Path("user_data/strategies"),
        description="Relative path to strategies directory"
    )
    data_dir: Path = Field(
        default=Path("user_data/data"),
        description="Relative path to data directory"
    )
    backtest_results_dir: Path = Field(
        default=Path("user_data/backtest_results"),
        description="Relative path to backtest results directory"
    )
    hyperopt_results_dir: Path = Field(
        default=Path("user_data/hyperopt_results"),
        description="Relative path to hyperopt results directory"
    )
    default_exchange: str = Field(
        default="binance",
        description="Default exchange for data operations"
    )
    default_stake_amount: float = Field(
        default=100.0,
        description="Default stake amount for backtesting"
    )
    default_epochs: int = Field(
        default=100,
        description="Default number of epochs for hyperopt"
    )
    coingecko_api_key: Optional[str] = Field(
        default=None,
        description="CoinGecko API key (optional)"
    )
    cache_ttl: int = Field(
        default=900,
        description="Cache TTL in seconds (15 minutes)"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    max_concurrent_operations: int = Field(
        default=3,
        description="Maximum concurrent operations"
    )

    @property
    def full_strategy_dir(self) -> Path:
        """Get full path to strategy directory."""
        return self.freqtrade_path / self.strategy_dir

    @property
    def full_data_dir(self) -> Path:
        """Get full path to data directory."""
        return self.freqtrade_path / self.data_dir

    @property
    def full_backtest_results_dir(self) -> Path:
        """Get full path to backtest results directory."""
        return self.freqtrade_path / self.backtest_results_dir

    @property
    def full_hyperopt_results_dir(self) -> Path:
        """Get full path to hyperopt results directory."""
        return self.freqtrade_path / self.hyperopt_results_dir

    class Config:
        """Pydantic config."""
        env_prefix = "FREQTRADE_MCP_"


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file or environment."""
    if config_path is None:
        config_path = Path.home() / ".config" / "freqtrade-mcp" / "config.json"
    
    config_data = {}
    
    # Load from file if exists
    if config_path.exists():
        with open(config_path) as f:
            config_data = json.load(f)
    
    # Override with environment variables
    env_mapping = {
        "FREQTRADE_MCP_PATH": "freqtrade_path",
        "FREQTRADE_MCP_EXCHANGE": "default_exchange",
        "FREQTRADE_MCP_COINGECKO_KEY": "coingecko_api_key",
        "FREQTRADE_MCP_LOG_LEVEL": "log_level",
    }
    
    for env_var, config_key in env_mapping.items():
        if env_value := os.getenv(env_var):
            if config_key.endswith("_path"):
                config_data[config_key] = Path(env_value)
            else:
                config_data[config_key] = env_value
    
    # Handle freqtrade path from parent directory if not set
    if "freqtrade_path" not in config_data:
        current_dir = Path.cwd()
        if current_dir.name == "freqtrade_mcp" and current_dir.parent.name == "freqtrade":
            config_data["freqtrade_path"] = current_dir.parent
        elif current_dir.name == "freqtrade":
            config_data["freqtrade_path"] = current_dir
    
    return Config(**config_data)


def save_config(config: Config, config_path: Optional[Path] = None):
    """Save configuration to file."""
    if config_path is None:
        config_path = Path.home() / ".config" / "freqtrade-mcp" / "config.json"
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        json.dump(config.model_dump(mode="json"), f, indent=2, default=str)