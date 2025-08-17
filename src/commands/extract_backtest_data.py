"""Extract backtest data command implementation."""

import json
import logging
import pandas as pd
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE

logger = logging.getLogger(__name__)


class ExtractBacktestDataCommand(BaseCommand):
    """Command to extract and analyze data from backtest result .zip files."""

    async def execute(
        self,
        result_path: str,
        include_trades: bool = True,
        include_performance: bool = True,
        include_strategy_code: bool = False,
        include_config: bool = False,
        include_market_data: bool = False,
        output_format: str = "summary",  # summary, detailed, raw
        **kwargs
    ) -> Dict[str, Any]:
        """Execute extract backtest data command.
        
        Args:
            result_path: Path to the backtest result .zip file
            include_trades: Include individual trade data
            include_performance: Include performance metrics
            include_strategy_code: Include strategy source code
            include_config: Include configuration used
            include_market_data: Include market change data
            output_format: Level of detail (summary, detailed, raw)
            
        Returns:
            Command execution result with extracted data
        """
        try:
            await self.mcp_log("info", f"Extracting backtest data from: {result_path}")
            
            result_file = Path(result_path).resolve()
            
            if not result_file.exists():
                return {
                    "command": "extract_backtest_data",
                    "success": False,
                    "error": f"Result file {result_file} does not exist",
                    "path": str(result_file)
                }
            
            if not result_file.suffix.lower() == '.zip':
                return {
                    "command": "extract_backtest_data",
                    "success": False,
                    "error": "Result file must be a .zip file",
                    "path": str(result_file)
                }
            
            # Extract data from zip file
            extracted_data = await self._extract_from_zip(result_file)
            
            # Process and format the data based on requirements
            processed_data = await self._process_extracted_data(
                extracted_data,
                include_trades=include_trades,
                include_performance=include_performance,
                include_strategy_code=include_strategy_code,
                include_config=include_config,
                include_market_data=include_market_data,
                output_format=output_format
            )
            
            await self.mcp_log("info", f"Successfully extracted data from {result_file.name}")
            
            return {
                "command": "extract_backtest_data",
                "success": True,
                "result_file": str(result_file),
                "result_id": result_file.stem,
                "extraction_summary": {
                    "total_trades": processed_data.get("total_trades", 0),
                    "strategy_name": processed_data.get("strategy_name", "unknown"),
                    "backtest_period": processed_data.get("backtest_period", {}),
                    "performance_summary": processed_data.get("performance_summary", {})
                },
                "data": processed_data
            }
            
        except Exception as e:
            await self.mcp_log("error", f"Extract backtest data command failed: {e}")
            return {
                "command": "extract_backtest_data",
                "success": False,
                "error": str(e),
                "path": result_path
            }

    async def _extract_from_zip(self, zip_path: Path) -> Dict[str, Any]:
        """Extract all files from the backtest result zip."""
        extracted_data = {}
        
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            # List all files in the zip
            file_list = zip_file.namelist()
            await self.mcp_log("info", f"Found files in zip: {file_list}")
            
            for file_name in file_list:
                try:
                    if file_name.endswith('.json'):
                        # Extract JSON files
                        with zip_file.open(file_name) as f:
                            content = json.loads(f.read().decode('utf-8'))
                            
                        if 'config' in file_name:
                            extracted_data['config'] = content
                        elif file_name.endswith('_AlligatorFractalV2_Improved.json') or any(strategy in file_name for strategy in ['AlligatorFractalV2', 'OLSPairsTrading']):
                            extracted_data['strategy_metadata'] = content
                        else:
                            extracted_data['backtest_results'] = content
                            
                    elif file_name.endswith('.py'):
                        # Extract Python strategy files
                        with zip_file.open(file_name) as f:
                            extracted_data['strategy_code'] = f.read().decode('utf-8')
                            
                    elif file_name.endswith('.feather'):
                        # Extract market data (feather format)
                        import tempfile
                        import os
                        
                        # Extract to temporary file to read with pandas
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.feather') as tmp_file:
                            tmp_file.write(zip_file.read(file_name))
                            tmp_path = tmp_file.name
                        
                        try:
                            market_data = pd.read_feather(tmp_path)
                            extracted_data['market_data'] = market_data.to_dict('records')
                        except Exception as e:
                            await self.mcp_log("warning", f"Failed to read feather file {file_name}: {e}")
                            extracted_data['market_data'] = None
                        finally:
                            os.unlink(tmp_path)
                            
                except Exception as e:
                    await self.mcp_log("warning", f"Failed to extract {file_name}: {e}")
                    continue
        
        return extracted_data

    async def _process_extracted_data(
        self,
        extracted_data: Dict[str, Any],
        include_trades: bool,
        include_performance: bool,
        include_strategy_code: bool,
        include_config: bool,
        include_market_data: bool,
        output_format: str
    ) -> Dict[str, Any]:
        """Process and format the extracted data."""
        
        processed_data = {}
        backtest_results = extracted_data.get('backtest_results', {})
        
        # Extract strategy data (assuming single strategy)
        strategy_data = None
        strategy_name = "unknown"
        
        if 'strategy' in backtest_results:
            strategy_name = list(backtest_results['strategy'].keys())[0]
            strategy_data = backtest_results['strategy'][strategy_name]
            processed_data['strategy_name'] = strategy_name
        
        if not strategy_data:
            return {"error": "No strategy data found in backtest results"}
        
        # Basic information
        processed_data['result_metadata'] = {
            "strategy_name": strategy_name,
            "backtest_start": strategy_data.get('backtest_start'),
            "backtest_end": strategy_data.get('backtest_end'),
            "backtest_days": strategy_data.get('backtest_days'),
            "timeframe": strategy_data.get('timeframe'),
            "timerange": strategy_data.get('timerange'),
            "stake_currency": strategy_data.get('stake_currency'),
            "starting_balance": strategy_data.get('starting_balance'),
            "final_balance": strategy_data.get('final_balance')
        }
        
        processed_data['backtest_period'] = {
            "start": strategy_data.get('backtest_start'),
            "end": strategy_data.get('backtest_end'),
            "days": strategy_data.get('backtest_days')
        }
        
        # Performance metrics
        if include_performance:
            processed_data['performance_metrics'] = self._extract_performance_metrics(strategy_data)
            processed_data['performance_summary'] = self._create_performance_summary(strategy_data)
        
        # Trade data
        if include_trades and 'trades' in strategy_data:
            trades = strategy_data['trades']
            processed_data['total_trades'] = len(trades)
            
            if output_format == "summary":
                processed_data['trades_summary'] = self._create_trades_summary(trades)
            elif output_format == "detailed":
                processed_data['trades_summary'] = self._create_trades_summary(trades)
                processed_data['trades_analysis'] = self._analyze_trades(trades)
            elif output_format == "raw":
                processed_data['trades'] = trades
                processed_data['trades_summary'] = self._create_trades_summary(trades)
                processed_data['trades_analysis'] = self._analyze_trades(trades)
        
        # Strategy code
        if include_strategy_code and 'strategy_code' in extracted_data:
            processed_data['strategy_code'] = extracted_data['strategy_code']
        
        # Configuration
        if include_config and 'config' in extracted_data:
            processed_data['config'] = extracted_data['config']
        
        # Market data
        if include_market_data and 'market_data' in extracted_data:
            market_data = extracted_data['market_data']
            if market_data:
                processed_data['market_data_summary'] = {
                    "total_records": len(market_data),
                    "columns": list(market_data[0].keys()) if market_data else [],
                    "sample_data": market_data[:5] if len(market_data) > 5 else market_data
                }
                if output_format == "raw":
                    processed_data['market_data'] = market_data
        
        return processed_data

    def _extract_performance_metrics(self, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key performance metrics."""
        return {
            "total_trades": strategy_data.get('total_trades', 0),
            "profit_total": strategy_data.get('profit_total', 0.0),
            "profit_total_abs": strategy_data.get('profit_total_abs', 0.0),
            "profit_mean": strategy_data.get('profit_mean', 0.0),
            "profit_median": strategy_data.get('profit_median', 0.0),
            "winrate": strategy_data.get('winrate', 0.0),
            "wins": strategy_data.get('wins', 0),
            "losses": strategy_data.get('losses', 0),
            "draws": strategy_data.get('draws', 0),
            "profit_factor": strategy_data.get('profit_factor', 0.0),
            "expectancy": strategy_data.get('expectancy', 0.0),
            "expectancy_ratio": strategy_data.get('expectancy_ratio', 0.0),
            "sharpe": strategy_data.get('sharpe', 0.0),
            "sortino": strategy_data.get('sortino', 0.0),
            "calmar": strategy_data.get('calmar', 0.0),
            "max_drawdown": strategy_data.get('max_drawdown_account', 0.0),
            "max_drawdown_abs": strategy_data.get('max_drawdown_abs', 0.0),
            "cagr": strategy_data.get('cagr', 0.0),
            "holding_avg": strategy_data.get('holding_avg', 0.0),
            "trades_per_day": strategy_data.get('trades_per_day', 0.0),
            "best_pair": strategy_data.get('best_pair', {}),
            "worst_pair": strategy_data.get('worst_pair', {})
        }

    def _create_performance_summary(self, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a concise performance summary."""
        total_trades = strategy_data.get('total_trades', 0)
        winrate = strategy_data.get('winrate', 0.0)
        profit_total = strategy_data.get('profit_total', 0.0)
        max_drawdown = strategy_data.get('max_drawdown_account', 0.0)
        sharpe = strategy_data.get('sharpe', 0.0)
        
        # Performance rating (simplified)
        performance_score = 0
        if winrate > 0.6: performance_score += 1
        if profit_total > 0.1: performance_score += 1
        if max_drawdown < 0.2: performance_score += 1
        if sharpe > 1.0: performance_score += 1
        if total_trades > 50: performance_score += 1
        
        performance_rating = {0: "Poor", 1: "Below Average", 2: "Average", 3: "Good", 4: "Very Good", 5: "Excellent"}
        
        return {
            "total_trades": total_trades,
            "winrate_pct": round(winrate * 100, 2),
            "profit_total_pct": round(profit_total * 100, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "performance_rating": performance_rating.get(performance_score, "Unknown"),
            "performance_score": f"{performance_score}/5"
        }

    def _create_trades_summary(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary statistics for trades."""
        if not trades:
            return {"error": "No trades to analyze"}
        
        # Basic stats
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('profit_ratio', 0) > 0]
        losing_trades = [t for t in trades if t.get('profit_ratio', 0) < 0]
        breakeven_trades = [t for t in trades if t.get('profit_ratio', 0) == 0]
        
        # Profit analysis
        profits = [t.get('profit_ratio', 0) for t in trades]
        profits_abs = [t.get('profit_abs', 0) for t in trades]
        
        # Duration analysis
        durations = [t.get('trade_duration', 0) for t in trades]
        
        # Pair analysis
        pairs = [t.get('pair', 'unknown') for t in trades]
        pair_counts = {}
        for pair in pairs:
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        
        # Exit reason analysis
        exit_reasons = [t.get('exit_reason', 'unknown') for t in trades]
        exit_reason_counts = {}
        for reason in exit_reasons:
            exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + 1
        
        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "breakeven_trades": len(breakeven_trades),
            "winrate": len(winning_trades) / total_trades if total_trades > 0 else 0,
            "profit_total": sum(profits),
            "profit_mean": sum(profits) / len(profits) if profits else 0,
            "profit_total_abs": sum(profits_abs),
            "best_trade": max(profits) if profits else 0,
            "worst_trade": min(profits) if profits else 0,
            "avg_duration_minutes": sum(durations) / len(durations) if durations else 0,
            "max_duration_minutes": max(durations) if durations else 0,
            "min_duration_minutes": min(durations) if durations else 0,
            "top_pairs": dict(sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "exit_reasons": dict(sorted(exit_reason_counts.items(), key=lambda x: x[1], reverse=True))
        }

    def _analyze_trades(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform deeper analysis of trades."""
        if not trades:
            return {"error": "No trades to analyze"}
        
        analysis = {}
        
        # Time-based analysis
        trade_times = []
        for trade in trades:
            if 'open_timestamp' in trade:
                dt = datetime.fromtimestamp(trade['open_timestamp'] / 1000)
                trade_times.append({
                    "hour": dt.hour,
                    "day_of_week": dt.weekday(),
                    "profit": trade.get('profit_ratio', 0)
                })
        
        if trade_times:
            # Hour analysis
            hour_profits = {}
            for t in trade_times:
                hour = t['hour']
                if hour not in hour_profits:
                    hour_profits[hour] = []
                hour_profits[hour].append(t['profit'])
            
            analysis['hourly_performance'] = {
                hour: {
                    "trades": len(profits),
                    "avg_profit": sum(profits) / len(profits),
                    "total_profit": sum(profits)
                }
                for hour, profits in hour_profits.items()
            }
            
            # Day of week analysis
            dow_profits = {}
            for t in trade_times:
                dow = t['day_of_week']
                if dow not in dow_profits:
                    dow_profits[dow] = []
                dow_profits[dow].append(t['profit'])
            
            analysis['daily_performance'] = {
                ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][dow]: {
                    "trades": len(profits),
                    "avg_profit": sum(profits) / len(profits),
                    "total_profit": sum(profits)
                }
                for dow, profits in dow_profits.items()
            }
        
        # Long vs Short analysis
        long_trades = [t for t in trades if not t.get('is_short', False)]
        short_trades = [t for t in trades if t.get('is_short', False)]
        
        analysis['direction_performance'] = {
            "long_trades": {
                "count": len(long_trades),
                "total_profit": sum(t.get('profit_ratio', 0) for t in long_trades),
                "avg_profit": sum(t.get('profit_ratio', 0) for t in long_trades) / len(long_trades) if long_trades else 0,
                "winrate": len([t for t in long_trades if t.get('profit_ratio', 0) > 0]) / len(long_trades) if long_trades else 0
            },
            "short_trades": {
                "count": len(short_trades),
                "total_profit": sum(t.get('profit_ratio', 0) for t in short_trades),
                "avg_profit": sum(t.get('profit_ratio', 0) for t in short_trades) / len(short_trades) if short_trades else 0,
                "winrate": len([t for t in short_trades if t.get('profit_ratio', 0) > 0]) / len(short_trades) if short_trades else 0
            }
        }
        
        # Pair performance analysis
        pair_performance = {}
        for trade in trades:
            pair = trade.get('pair', 'unknown')
            if pair not in pair_performance:
                pair_performance[pair] = {
                    "trades": 0,
                    "profits": [],
                    "durations": []
                }
            
            pair_performance[pair]['trades'] += 1
            pair_performance[pair]['profits'].append(trade.get('profit_ratio', 0))
            pair_performance[pair]['durations'].append(trade.get('trade_duration', 0))
        
        # Summarize pair performance
        for pair, data in pair_performance.items():
            profits = data['profits']
            durations = data['durations']
            data['total_profit'] = sum(profits)
            data['avg_profit'] = sum(profits) / len(profits) if profits else 0
            data['winrate'] = len([p for p in profits if p > 0]) / len(profits) if profits else 0
            data['avg_duration'] = sum(durations) / len(durations) if durations else 0
            del data['profits']  # Remove raw data to reduce size
            del data['durations']
        
        analysis['pair_performance'] = dict(sorted(
            pair_performance.items(), 
            key=lambda x: x[1]['total_profit'], 
            reverse=True
        ))
        
        return analysis