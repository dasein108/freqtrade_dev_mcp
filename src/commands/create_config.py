"""Create config command implementation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE

logger = logging.getLogger(__name__)


class CreateConfigCommand(BaseCommand):
    """Command to create a new Freqtrade configuration file."""

    async def execute(
        self,
        config_path: str = "config.json",
        template: str = "default",
        exchange: Optional[str] = None,
        stake_currency: Optional[str] = None,
        stake_amount: Optional[float] = None,
        max_open_trades: Optional[int] = None,
        dry_run: Optional[bool] = None,
        trading_mode: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute create config command.
        
        Args:
            config_path: Path where to save the configuration file
            template: Configuration template to use (default, conservative, aggressive, advanced)
            exchange: Exchange name (e.g., 'binance', 'kraken')
            stake_currency: Stake currency (e.g., 'USDT', 'BTC') 
            stake_amount: Amount to stake per trade
            max_open_trades: Maximum number of concurrent trades
            dry_run: Enable dry run mode (paper trading)
            trading_mode: Trading mode ('spot', 'futures', 'margin')
            pairs: List of trading pairs
            
        Returns:
            Command execution result with created configuration
        """
        try:
            await self.mcp_log("info", f"Creating configuration file: {config_path}")
            
            config_file_path = Path(config_path).resolve()
            
            # Check if file already exists
            if config_file_path.exists():
                return {
                    "command": "create_config",
                    "success": False,
                    "error": f"Configuration file {config_file_path} already exists. Remove it first or use a different path.",
                    "config_path": str(config_file_path)
                }
            
            # Generate configuration based on template and inputs
            config = self._generate_config(
                template=template,
                exchange=exchange,
                stake_currency=stake_currency,
                stake_amount=stake_amount,
                max_open_trades=max_open_trades,
                dry_run=dry_run,
                trading_mode=trading_mode,
                pairs=pairs
            )
            
            # Create directory if it doesn't exist
            config_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write configuration to file
            with open(config_file_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            await self.mcp_log("info", f"Configuration file created successfully at {config_file_path}")
            
            # Validate the created configuration if possible
            validation_result = await self._validate_config(config)
            
            return {
                "command": "create_config",
                "success": True,
                "config_path": str(config_file_path),
                "template": template,
                "configuration": config,
                "validation": validation_result,
                "summary": {
                    "exchange": config.get("exchange", {}).get("name", "not specified"),
                    "stake_currency": config.get("stake_currency", "not specified"),
                    "stake_amount": config.get("stake_amount", "not specified"),
                    "max_open_trades": config.get("max_open_trades", "not specified"),
                    "dry_run": config.get("dry_run", True),
                    "trading_mode": config.get("trading_mode", "spot"),
                    "pairs_count": len(config.get("exchange", {}).get("pair_whitelist", []))
                }
            }
            
        except Exception as e:
            await self.mcp_log("error", f"Create config command failed: {e}")
            return {
                "command": "create_config",
                "success": False,
                "error": str(e),
                "config_path": config_path
            }

    def _generate_config(
        self,
        template: str,
        exchange: Optional[str] = None,
        stake_currency: Optional[str] = None,
        stake_amount: Optional[float] = None,
        max_open_trades: Optional[int] = None,
        dry_run: Optional[bool] = None,
        trading_mode: Optional[str] = None,
        pairs: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate configuration based on template and inputs."""
        
        # Start with base template
        config = self._get_template_config(template)
        
        # Override with provided inputs
        if exchange:
            config["exchange"]["name"] = exchange
            
        if stake_currency:
            config["stake_currency"] = stake_currency
            
        if stake_amount:
            config["stake_amount"] = stake_amount
            
        if max_open_trades:
            config["max_open_trades"] = max_open_trades
            
        if dry_run is not None:
            config["dry_run"] = dry_run
            
        if trading_mode:
            config["trading_mode"] = trading_mode
            
        if pairs:
            config["exchange"]["pair_whitelist"] = pairs
        elif not config["exchange"].get("pair_whitelist"):
            # Set default pairs based on exchange and stake currency
            config["exchange"]["pair_whitelist"] = self._get_default_pairs(
                exchange or config["exchange"]["name"],
                stake_currency or config["stake_currency"]
            )
        
        return config

    def _get_template_config(self, template: str) -> Dict[str, Any]:
        """Get configuration template."""
        
        base_config = {
            "max_open_trades": 3,
            "stake_currency": "USDT",
            "stake_amount": 100,
            "tradable_balance_ratio": 0.99,
            "fiat_display_currency": "USD",
            "dry_run": True,
            "dry_run_wallet": 1000,
            "cancel_open_orders_on_exit": False,
            "trading_mode": "spot",
            "unfilledtimeout": {
                "entry": 10,
                "exit": 10,
                "exit_timeout_count": 0,
                "unit": "minutes"
            },
            "entry_pricing": {
                "price_side": "same",
                "use_order_book": True,
                "order_book_top": 1,
                "price_last_balance": 0.0,
                "check_depth_of_market": {
                    "enabled": False,
                    "bids_to_ask_delta": 1
                }
            },
            "exit_pricing": {
                "price_side": "same",
                "use_order_book": True,
                "order_book_top": 1
            },
            "exchange": {
                "name": "binance",
                "key": "",
                "secret": "",
                "ccxt_config": {},
                "ccxt_async_config": {},
                "pair_whitelist": [],
                "pair_blacklist": []
            },
            "pairlists": [
                {"method": "StaticPairList"}
            ],
            "telegram": {
                "enabled": False,
                "token": "",
                "chat_id": ""
            },
            "api_server": {
                "enabled": False,
                "listen_ip_address": "127.0.0.1",
                "listen_port": 8080,
                "verbosity": "error",
                "enable_openapi": False,
                "jwt_secret_key": "",
                "CORS_origins": [],
                "username": "",
                "password": ""
            },
            "bot_name": "freqtrade",
            "initial_state": "running",
            "force_entry_enable": False,
            "internals": {
                "process_throttle_secs": 5
            }
        }
        
        if template == "conservative":
            base_config.update({
                "max_open_trades": 2,
                "stake_amount": 50,
                "tradable_balance_ratio": 0.95,
                "unfilledtimeout": {
                    "entry": 5,
                    "exit": 5,
                    "exit_timeout_count": 0,
                    "unit": "minutes"
                }
            })
            
        elif template == "aggressive":
            base_config.update({
                "max_open_trades": 5,
                "stake_amount": 200,
                "tradable_balance_ratio": 0.99,
                "unfilledtimeout": {
                    "entry": 30,
                    "exit": 30,
                    "exit_timeout_count": 0,
                    "unit": "minutes"
                }
            })
            
        elif template == "advanced":
            base_config.update({
                "max_open_trades": 10,
                "stake_amount": "unlimited",
                "tradable_balance_ratio": 0.99,
                "pairlists": [
                    {
                        "method": "VolumePairList",
                        "number_assets": 20,
                        "sort_key": "quoteVolume",
                        "min_value": 0,
                        "refresh_period": 1800
                    },
                    {"method": "AgeFilter", "min_days_listed": 10},
                    {"method": "PrecisionFilter"},
                    {"method": "PriceFilter", "low_price_ratio": 0.01},
                    {"method": "SpreadFilter", "max_spread_ratio": 0.005},
                    {"method": "RangeStabilityFilter", "lookback_days": 10, "min_rate_of_change": 0.02, "max_rate_of_change": 0.75}
                ],
                "edge": {
                    "enabled": True,
                    "process_throttle_secs": 3600,
                    "calculate_since_number_of_days": 7,
                    "allowed_risk": 0.01,
                    "stoploss_range_min": -0.01,
                    "stoploss_range_max": -0.1,
                    "stoploss_range_step": -0.01,
                    "minimum_winrate": 0.60,
                    "minimum_expectancy": 0.20,
                    "min_trade_number": 10,
                    "max_trade_duration_minute": 1440,
                    "remove_pumps": False
                }
            })
        
        return base_config

    def _get_default_pairs(self, exchange: str, stake_currency: str) -> List[str]:
        """Get default trading pairs for exchange and stake currency."""
        
        base_assets = ["BTC", "ETH", "BNB", "ADA", "DOT", "SOL", "MATIC", "AVAX", "ATOM", "LINK"]
        
        if stake_currency == "USDT":
            return [f"{asset}/USDT" for asset in base_assets if asset != "USDT"]
        elif stake_currency == "BTC":
            return [f"{asset}/BTC" for asset in base_assets if asset != "BTC"]
        elif stake_currency == "ETH":
            return [f"{asset}/ETH" for asset in base_assets if asset not in ["BTC", "ETH"]]
        else:
            # Default to USDT pairs
            return [f"{asset}/USDT" for asset in base_assets]

    async def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the created configuration."""
        
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        try:
            # Check required fields
            required_fields = ["stake_currency", "exchange", "max_open_trades"]
            for field in required_fields:
                if field not in config:
                    validation_result["errors"].append(f"Missing required field: {field}")
                    validation_result["valid"] = False
            
            # Check exchange configuration
            if "exchange" in config:
                exchange_config = config["exchange"]
                if not exchange_config.get("name"):
                    validation_result["errors"].append("Exchange name is required")
                    validation_result["valid"] = False
                
                if not exchange_config.get("pair_whitelist"):
                    validation_result["warnings"].append("No trading pairs specified")
                
                if not exchange_config.get("key") and not config.get("dry_run", True):
                    validation_result["warnings"].append("Exchange API key not set - required for live trading")
            
            # Check stake configuration
            if config.get("stake_amount", 0) <= 0 and config.get("stake_amount") != "unlimited":
                validation_result["warnings"].append("Stake amount should be greater than 0")
            
            # Check dry run vs live trading
            if not config.get("dry_run", True):
                validation_result["warnings"].append("Live trading mode enabled - make sure you have properly configured exchange credentials")
            
            # Suggestions
            if config.get("max_open_trades", 0) > 10:
                validation_result["suggestions"].append("High number of open trades - consider risk management")
            
            if not config.get("telegram", {}).get("enabled", False):
                validation_result["suggestions"].append("Consider enabling Telegram notifications for trade updates")
                
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")
            validation_result["valid"] = False
        
        return validation_result