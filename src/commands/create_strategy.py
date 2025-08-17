"""Create strategy command implementation."""

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


class CreateStrategyCommand(BaseCommand):
    """Command to create a new Freqtrade strategy."""

    async def execute(
        self,
        strategy_name: str,
        strategy_path: Optional[str] = None,
        template: str = "basic",
        timeframe: str = "5m",
        indicators: Optional[List[str]] = None,
        can_short: bool = False,
        minimal_roi: Optional[Dict[str, float]] = None,
        stoploss: float = -0.10,
        trailing_stop: bool = False,
        description: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute create strategy command.
        
        Args:
            strategy_name: Name of the strategy class and file
            strategy_path: Custom path for strategy file (optional)
            template: Strategy template to use (basic, trend, mean_reversion, scalping, advanced)
            timeframe: Primary timeframe for the strategy
            indicators: List of technical indicators to include
            can_short: Whether the strategy can short sell
            minimal_roi: ROI table configuration
            stoploss: Stop loss percentage (negative value)
            trailing_stop: Enable trailing stop
            description: Strategy description
            
        Returns:
            Command execution result with created strategy details
        """
        try:
            await self.mcp_log("info", f"Creating strategy: {strategy_name}")
            
            # Determine strategy file path
            if strategy_path:
                strategy_file_path = Path(strategy_path).resolve()
            else:
                # Default to strategies directory in current working directory
                strategies_dir = Path.cwd() / "strategies"
                strategies_dir.mkdir(exist_ok=True)
                strategy_file_path = strategies_dir / f"{strategy_name}.py"
            
            # Check if file already exists
            if strategy_file_path.exists():
                return {
                    "command": "create_strategy",
                    "success": False,
                    "error": f"Strategy file {strategy_file_path} already exists. Remove it first or use a different name.",
                    "strategy_path": str(strategy_file_path)
                }
            
            # Generate strategy code
            strategy_code = self._generate_strategy_code(
                strategy_name=strategy_name,
                template=template,
                timeframe=timeframe,
                indicators=indicators or [],
                can_short=can_short,
                minimal_roi=minimal_roi,
                stoploss=stoploss,
                trailing_stop=trailing_stop,
                description=description
            )
            
            # Create directory if it doesn't exist
            strategy_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write strategy to file
            strategy_file_path.write_text(strategy_code)
            
            await self.mcp_log("info", f"Strategy created successfully at {strategy_file_path}")
            
            # Validate the created strategy
            validation_result = await self._validate_strategy(strategy_file_path)
            
            return {
                "command": "create_strategy",
                "success": True,
                "strategy_name": strategy_name,
                "strategy_path": str(strategy_file_path),
                "template": template,
                "validation": validation_result,
                "configuration": {
                    "timeframe": timeframe,
                    "can_short": can_short,
                    "stoploss": stoploss,
                    "trailing_stop": trailing_stop,
                    "indicators": indicators or [],
                    "minimal_roi": minimal_roi or self._get_default_roi(template)
                },
                "summary": {
                    "lines_of_code": len(strategy_code.split('\n')),
                    "indicators_count": len(indicators) if indicators else len(self._get_template_indicators(template)),
                    "template_used": template
                }
            }
            
        except Exception as e:
            await self.mcp_log("error", f"Create strategy command failed: {e}")
            return {
                "command": "create_strategy",
                "success": False,
                "error": str(e),
                "strategy_name": strategy_name
            }

    def _generate_strategy_code(
        self,
        strategy_name: str,
        template: str,
        timeframe: str,
        indicators: List[str],
        can_short: bool,
        minimal_roi: Optional[Dict[str, float]],
        stoploss: float,
        trailing_stop: bool,
        description: Optional[str]
    ) -> str:
        """Generate strategy code based on template and parameters."""
        
        # Get template-specific configurations
        template_config = self._get_template_config(template)
        template_indicators = indicators if indicators else self._get_template_indicators(template)
        template_roi = minimal_roi if minimal_roi else self._get_default_roi(template)
        
        # Generate imports
        imports = self._generate_imports(template_indicators)
        
        # Generate class docstring
        class_docstring = self._generate_class_docstring(strategy_name, template, description)
        
        # Generate strategy parameters
        parameters = self._generate_parameters(
            timeframe, can_short, template_roi, stoploss, trailing_stop, template_config
        )
        
        # Generate indicator calculations
        indicators_code = self._generate_indicators_code(template_indicators, template)
        
        # Generate entry/exit logic
        entry_logic = self._generate_entry_logic(template, template_indicators)
        exit_logic = self._generate_exit_logic(template, template_indicators)
        
        # Combine all parts
        strategy_code = f'''"""{class_docstring}"""

{imports}


class {strategy_name}(IStrategy):
    """{self._get_strategy_description(template)}"""
    
    # Strategy interface version
    INTERFACE_VERSION: int = 3
    
{parameters}
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add technical indicators to the dataframe.
        """
{indicators_code}
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate the entry signal for the given dataframe.
        """
{entry_logic}
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate the exit signal for the given dataframe.
        """
{exit_logic}
        
        return dataframe
'''
        
        return strategy_code

    def _generate_imports(self, indicators: List[str]) -> str:
        """Generate import statements based on indicators."""
        base_imports = [
            "from freqtrade.strategy.interface import IStrategy",
            "from pandas import DataFrame"
        ]
        
        # Add talib if any indicators are used
        if indicators:
            base_imports.append("import talib.abstract as ta")
        
        # Add numpy for advanced calculations
        if any(ind in ["STOCH", "MACD", "BBANDS", "CUSTOM"] for ind in indicators):
            base_imports.append("import numpy as np")
        
        return '\n'.join(base_imports)

    def _generate_class_docstring(self, strategy_name: str, template: str, description: Optional[str]) -> str:
        """Generate class-level docstring."""
        if description:
            return f"{strategy_name} Strategy\n\n{description}\n\nTemplate: {template}"
        else:
            template_descriptions = {
                "basic": "Basic strategy template with RSI and MACD indicators",
                "trend": "Trend following strategy using moving averages and momentum",
                "mean_reversion": "Mean reversion strategy using Bollinger Bands and RSI",
                "scalping": "High-frequency scalping strategy with quick entry/exit",
                "advanced": "Advanced strategy with multiple indicators and complex logic"
            }
            return f"{strategy_name} Strategy\n\n{template_descriptions.get(template, 'Custom strategy')}\n\nGenerated using {template} template"

    def _generate_parameters(
        self, 
        timeframe: str, 
        can_short: bool, 
        minimal_roi: Dict[str, float], 
        stoploss: float, 
        trailing_stop: bool,
        template_config: Dict[str, Any]
    ) -> str:
        """Generate strategy parameters section."""
        
        roi_lines = []
        for time_str, roi_value in minimal_roi.items():
            roi_lines.append(f'        "{time_str}": {roi_value}')
        roi_string = ',\n'.join(roi_lines)
        
        params = f'''    # Optimal timeframe for the strategy
    timeframe = '{timeframe}'
    
    # Can this strategy go short?
    can_short: bool = {can_short}
    
    # Minimal ROI designed for the strategy
    minimal_roi = {{
{roi_string}
    }}
    
    # Optimal stoploss
    stoploss = {stoploss}
    
    # Trailing stoploss
    trailing_stop = {trailing_stop}'''
    
        # Add template-specific parameters
        if template_config.get("additional_params"):
            params += f"\n    \n    # Strategy-specific parameters\n"
            for param, value in template_config["additional_params"].items():
                if isinstance(value, str):
                    params += f"    {param} = '{value}'\n"
                else:
                    params += f"    {param} = {value}\n"
        
        return params

    def _generate_indicators_code(self, indicators: List[str], template: str) -> str:
        """Generate indicators calculation code."""
        code_lines = []
        
        indicator_code_map = {
            "RSI": "        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)",
            "MACD": """        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']""",
            "BBANDS": """        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']""",
            "SMA": """        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=10)
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=30)""",
            "EMA": """        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)""",
            "STOCH": """        stoch = ta.STOCH(dataframe)
        dataframe['slowk'] = stoch['slowk']
        dataframe['slowd'] = stoch['slowd']""",
            "ADX": "        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)",
            "ATR": "        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)",
            "VOLUME": "        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)"
        }
        
        for indicator in indicators:
            if indicator in indicator_code_map:
                code_lines.append(indicator_code_map[indicator])
        
        if not code_lines:
            # Default indicators if none specified
            code_lines = [
                indicator_code_map["RSI"],
                indicator_code_map["MACD"]
            ]
        
        return '\n        \n'.join(code_lines)

    def _generate_entry_logic(self, template: str, indicators: List[str]) -> str:
        """Generate entry signal logic based on template."""
        
        template_logic = {
            "basic": """        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &  # RSI oversold
                (dataframe['macd'] > dataframe['macdsignal']) &  # MACD above signal
                (dataframe['volume'] > 0)  # Volume check
            ),
            'enter_long'] = 1""",
            
            "trend": """        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &  # Fast EMA above slow
                (dataframe['rsi'] > 50) &  # RSI above neutral
                (dataframe['adx'] > 25) &  # Strong trend
                (dataframe['volume'] > dataframe['volume_sma'])  # Volume above average
            ),
            'enter_long'] = 1""",
            
            "mean_reversion": """        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &  # RSI oversold
                (dataframe['close'] < dataframe['bb_lowerband']) &  # Price below lower BB
                (dataframe['macd'] > dataframe['macdsignal']) &  # MACD turning up
                (dataframe['volume'] > 0)  # Volume check
            ),
            'enter_long'] = 1""",
            
            "scalping": """        dataframe.loc[
            (
                (dataframe['rsi'] < 40) &  # Slight oversold
                (dataframe['ema_fast'] > dataframe['ema_slow']) &  # Uptrend
                (dataframe['volume'] > dataframe['volume_sma'] * 1.5) &  # High volume
                (dataframe['atr'] > dataframe['atr'].rolling(20).mean())  # Increased volatility
            ),
            'enter_long'] = 1""",
            
            "advanced": """        dataframe.loc[
            (
                (dataframe['rsi'] < 35) &  # RSI condition
                (dataframe['macd'] > dataframe['macdsignal']) &  # MACD bullish
                (dataframe['ema_fast'] > dataframe['ema_slow']) &  # Trend alignment
                (dataframe['adx'] > 20) &  # Trend strength
                (dataframe['close'] > dataframe['bb_middleband']) &  # Above BB middle
                (dataframe['volume'] > dataframe['volume_sma'])  # Volume confirmation
            ),
            'enter_long'] = 1"""
        }
        
        return template_logic.get(template, template_logic["basic"])

    def _generate_exit_logic(self, template: str, indicators: List[str]) -> str:
        """Generate exit signal logic based on template."""
        
        template_logic = {
            "basic": """        dataframe.loc[
            (
                (dataframe['rsi'] > 70) &  # RSI overbought
                (dataframe['macd'] < dataframe['macdsignal']) &  # MACD below signal
                (dataframe['volume'] > 0)  # Volume check
            ),
            'exit_long'] = 1""",
            
            "trend": """        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) |  # Trend reversal
                (dataframe['rsi'] > 75) |  # Overbought
                (dataframe['adx'] < 20)  # Trend weakening
            ),
            'exit_long'] = 1""",
            
            "mean_reversion": """        dataframe.loc[
            (
                (dataframe['rsi'] > 70) &  # RSI overbought
                (dataframe['close'] > dataframe['bb_upperband']) &  # Price above upper BB
                (dataframe['macd'] < dataframe['macdsignal'])  # MACD turning down
            ),
            'exit_long'] = 1""",
            
            "scalping": """        dataframe.loc[
            (
                (dataframe['rsi'] > 60) |  # Quick profit taking
                (dataframe['ema_fast'] < dataframe['ema_slow']) |  # Trend change
                (dataframe['volume'] < dataframe['volume_sma'] * 0.5)  # Volume decline
            ),
            'exit_long'] = 1""",
            
            "advanced": """        dataframe.loc[
            (
                (dataframe['rsi'] > 65) |  # Overbought
                (dataframe['macd'] < dataframe['macdsignal']) |  # MACD bearish
                (dataframe['ema_fast'] < dataframe['ema_slow']) |  # Trend reversal
                (dataframe['close'] < dataframe['bb_middleband'])  # Below BB middle
            ),
            'exit_long'] = 1"""
        }
        
        return template_logic.get(template, template_logic["basic"])

    def _get_template_config(self, template: str) -> Dict[str, Any]:
        """Get template-specific configuration."""
        
        configs = {
            "basic": {
                "additional_params": {}
            },
            "trend": {
                "additional_params": {
                    "startup_candle_count": 30
                }
            },
            "mean_reversion": {
                "additional_params": {
                    "startup_candle_count": 20
                }
            },
            "scalping": {
                "additional_params": {
                    "startup_candle_count": 15,
                    "process_only_new_candles": True
                }
            },
            "advanced": {
                "additional_params": {
                    "startup_candle_count": 50,
                    "use_exit_signal": True,
                    "exit_profit_only": False
                }
            }
        }
        
        return configs.get(template, configs["basic"])

    def _get_template_indicators(self, template: str) -> List[str]:
        """Get default indicators for template."""
        
        template_indicators = {
            "basic": ["RSI", "MACD"],
            "trend": ["EMA", "RSI", "ADX", "VOLUME"],
            "mean_reversion": ["RSI", "BBANDS", "MACD"],
            "scalping": ["RSI", "EMA", "VOLUME", "ATR"],
            "advanced": ["RSI", "MACD", "EMA", "ADX", "BBANDS", "VOLUME"]
        }
        
        return template_indicators.get(template, template_indicators["basic"])

    def _get_default_roi(self, template: str) -> Dict[str, float]:
        """Get default ROI table for template."""
        
        roi_tables = {
            "basic": {
                "60": 0.01,
                "30": 0.02,
                "0": 0.04
            },
            "trend": {
                "120": 0.01,
                "60": 0.03,
                "30": 0.06,
                "0": 0.10
            },
            "mean_reversion": {
                "40": 0.01,
                "20": 0.02,
                "0": 0.04
            },
            "scalping": {
                "15": 0.01,
                "5": 0.02,
                "0": 0.03
            },
            "advanced": {
                "240": 0.01,
                "120": 0.02,
                "60": 0.05,
                "0": 0.08
            }
        }
        
        return roi_tables.get(template, roi_tables["basic"])

    def _get_strategy_description(self, template: str) -> str:
        """Get strategy description based on template."""
        
        descriptions = {
            "basic": "Basic trading strategy with RSI and MACD indicators for entry/exit signals.",
            "trend": "Trend following strategy using moving averages, RSI, and ADX for trend confirmation.",
            "mean_reversion": "Mean reversion strategy using Bollinger Bands and RSI to identify oversold/overbought conditions.",
            "scalping": "High-frequency scalping strategy with quick entry/exit using momentum indicators.",
            "advanced": "Advanced multi-indicator strategy with complex logic and trend analysis."
        }
        
        return descriptions.get(template, "Custom trading strategy")

    async def _validate_strategy(self, strategy_path: Path) -> Dict[str, Any]:
        """Validate the created strategy file."""
        
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "suggestions": []
        }
        
        try:
            # Read and basic syntax validation
            content = strategy_path.read_text()
            
            # Check for required components
            required_components = [
                "class ", "IStrategy", "populate_indicators", 
                "populate_entry_trend", "populate_exit_trend"
            ]
            
            for component in required_components:
                if component not in content:
                    validation_result["errors"].append(f"Missing required component: {component}")
                    validation_result["valid"] = False
            
            # Check for common issues
            if "enter_long" not in content and "enter_short" not in content:
                validation_result["warnings"].append("No entry signals found")
            
            if "exit_long" not in content and "exit_short" not in content:
                validation_result["warnings"].append("No exit signals found")
            
            # Suggestions
            if "stoploss" not in content:
                validation_result["suggestions"].append("Consider adding a stoploss parameter")
            
            if "minimal_roi" not in content:
                validation_result["suggestions"].append("Consider adding a minimal_roi table")
                
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")
            validation_result["valid"] = False
        
        return validation_result