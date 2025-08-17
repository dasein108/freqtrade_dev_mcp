"""
Hyperopt execution node
"""
import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any
from datetime import datetime

from ..state import StrategyDevelopmentState

logger = logging.getLogger(__name__)


async def run_hyperopt(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Run hyperopt optimization on the strategy
    """
    logger.info("Starting hyperopt optimization")
    state["current_step"] = "run_hyperopt"
    
    if not state["strategy_name"]:
        state["errors"].append("No strategy available for hyperopt")
        return state
    
    try:
        # Prepare hyperopt configuration
        hyperopt_config = {
            "strategy": state["strategy_name"],
            "timeframe": state["strategy_config"].get("timeframe", "1h"),
            "timerange": "20240101-20250101",  # Last year
            "epochs": state["hyperopt_epochs"],
            "spaces": ["buy", "sell", "roi", "stoploss"],
            "loss_function": state["hyperopt_loss_function"],
            "random_state": 42,
            "jobs": -1,  # Use all CPU cores
            "print_all": False,
            "print_json": True
        }
        
        state["hyperopt_config"] = hyperopt_config
        
        # Call MCP hyperopt endpoint
        result = await execute_hyperopt_mcp(
            state["mcp_server_url"],
            hyperopt_config
        )
        
        if result and result.get("success"):
            # Store results
            state["hyperopt_results"] = result
            state["hyperopt_best_params"] = result.get("best_params", {})
            state["optimization_complete"] = True
            
            logger.info(f"Hyperopt completed successfully")
            logger.info(f"Best loss: {result.get('best_loss', 'N/A')}")
            logger.info(f"Total epochs: {result.get('total_epochs', 0)}")
            
            # Update strategy config with best params
            if state["hyperopt_best_params"]:
                state["strategy_config"].update(state["hyperopt_best_params"])
        else:
            error_msg = result.get("error", "Unknown hyperopt error") if result else "Hyperopt failed"
            state["errors"].append(error_msg)
            state["optimization_complete"] = False
            logger.error(f"Hyperopt failed: {error_msg}")
            
    except Exception as e:
        logger.error(f"Error running hyperopt: {str(e)}")
        state["errors"].append(f"Hyperopt execution error: {str(e)}")
        state["optimization_complete"] = False
    
    return state


async def execute_hyperopt_mcp(
    mcp_url: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute hyperopt via MCP server
    """
    try:
        payload = {
            "method": "hyperopt_strategy",
            "params": config
        }
        
        # Long timeout for hyperopt
        timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{mcp_url}/tools/hyperopt_strategy",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Parse hyperopt results
                    if result.get("success"):
                        return parse_hyperopt_results(result)
                    else:
                        logger.error(f"MCP hyperopt error: {result.get('error')}")
                        return result
                else:
                    logger.error(f"HTTP error {response.status} from MCP server")
                    return {
                        "success": False,
                        "error": f"HTTP error {response.status}"
                    }
                    
    except asyncio.TimeoutError:
        logger.error("Hyperopt timeout - process took too long")
        return {
            "success": False,
            "error": "Hyperopt timeout after 1 hour"
        }
    except Exception as e:
        logger.error(f"Error calling MCP hyperopt: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def parse_hyperopt_results(raw_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and structure hyperopt results
    """
    parsed = {
        "success": True,
        "best_loss": raw_results.get("best_loss"),
        "total_epochs": raw_results.get("total_epochs", 0),
        "best_epoch": raw_results.get("best_epoch"),
        "best_params": {},
        "optimization_time": raw_results.get("duration_minutes"),
        "results_file": raw_results.get("results_file")
    }
    
    # Extract best parameters
    if "best_params" in raw_results:
        params = raw_results["best_params"]
        
        # Organize parameters by space
        parsed["best_params"] = {
            "buy": params.get("buy", {}),
            "sell": params.get("sell", {}),
            "roi": params.get("roi", {}),
            "stoploss": params.get("stoploss", -0.1),
            "trailing": params.get("trailing", {})
        }
    
    # Add performance metrics from best result
    if "best_result" in raw_results:
        best = raw_results["best_result"]
        parsed["best_metrics"] = {
            "profit": best.get("profit_total", 0),
            "trades": best.get("trade_count", 0),
            "duration": best.get("duration", 0),
            "sharpe": best.get("sharpe", 0),
            "drawdown": best.get("max_drawdown", 0)
        }
    
    return parsed


async def run_backtest_with_params(
    state: StrategyDevelopmentState
) -> Dict[str, Any]:
    """
    Run backtest with optimized parameters
    """
    if not state["hyperopt_best_params"]:
        logger.warning("No optimized parameters available, using defaults")
        return None
    
    try:
        # Prepare backtest config with optimized params
        backtest_config = {
            "strategy": state["strategy_name"],
            "timeframe": state["strategy_config"]["timeframe"],
            "timerange": "20240101-20250101",
            "enable_protections": True,
            "max_open_trades": 3,
            **state["hyperopt_best_params"]  # Apply optimized parameters
        }
        
        # Call MCP backtest endpoint
        payload = {
            "method": "backtest_strategy",
            "params": backtest_config
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{state['mcp_server_url']}/tools/backtest_strategy",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=600)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        return result
                        
        logger.error("Failed to run backtest with optimized parameters")
        return None
        
    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        return None