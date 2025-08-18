"""
Hyperopt execution node with enhanced logging
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import traceback
import json

from ..state import StrategyDevelopmentState
from ..mcp_client import FreqtradeMCPClient
from ..logging_config import get_logger

logger = logging.getLogger(__name__)
strategy_logger = get_logger()


async def run_hyperopt(
    state: StrategyDevelopmentState,
    mcp_client: Optional[FreqtradeMCPClient] = None
) -> StrategyDevelopmentState:
    """
    Node: Run hyperopt optimization on the strategy
    
    Args:
        state: Current workflow state
        mcp_client: Optional MCP client instance
    """
    logger.info("Starting hyperopt optimization")
    strategy_logger.set_phase("HYPEROPT OPTIMIZATION")
    strategy_logger.set_step("Initialization")
    
    state["current_step"] = "run_hyperopt"
    
    # Get MCP client from state if not provided
    if mcp_client is None:
        mcp_client = state.get("mcp_client")
        if mcp_client is None:
            error_msg = "No MCP client available for hyperopt"
            state["errors"].append(error_msg)
            strategy_logger.log_error(error_msg)
            return state
    
    if not state["strategy_name"]:
        error_msg = "No strategy available for hyperopt"
        state["errors"].append(error_msg)
        strategy_logger.log_error(error_msg)
        return state
    
    strategy_logger.log_progress(f"Starting hyperopt for strategy: {state['strategy_name']}")
    
    try:
        # Prepare hyperopt configuration
        strategy_logger.set_step("Configuration")
        
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
        
        strategy_logger.log_data(logging.INFO, "Hyperopt configuration prepared", {
            "strategy": state["strategy_name"],
            "epochs": state["hyperopt_epochs"],
            "spaces": hyperopt_config["spaces"],
            "loss_function": state["hyperopt_loss_function"],
            "timeframe": hyperopt_config["timeframe"],
            "timerange": hyperopt_config["timerange"]
        })
        
        # Call MCP hyperopt via stdio
        strategy_logger.set_step("Execution")
        strategy_logger.log_progress(f"Running hyperopt with {state['hyperopt_epochs']} epochs...")
        
        logger.info(f"Calling MCP hyperopt_strategy with params: {json.dumps(hyperopt_config, indent=2)}")
        
        result = await mcp_client.hyperopt_strategy(
            strategy=state["strategy_name"],
            epochs=state["hyperopt_epochs"],
            spaces=hyperopt_config["spaces"],
            loss_function=state["hyperopt_loss_function"],
            timerange=hyperopt_config["timerange"],
            pairs=state.get("symbols", [])  # Pass pairs for futures detection
        )
        
        logger.info(f"MCP hyperopt result: {json.dumps(result, indent=2) if result else 'None'}")
        
        if result and result.get("success"):
            # Store results
            strategy_logger.set_step("Results Processing")
            
            state["hyperopt_results"] = result
            state["hyperopt_best_params"] = result.get("best_params", {})
            state["optimization_complete"] = True
            
            strategy_logger.log_success("Hyperopt completed successfully", {
                "best_loss": result.get("best_loss", "N/A"),
                "total_epochs": result.get("total_epochs", 0),
                "best_epoch": result.get("best_epoch", "N/A"),
                "results_file": result.get("results_file", "N/A")
            })
            
            # Log best parameters
            if state["hyperopt_best_params"]:
                strategy_logger.log_metrics({
                    "best_params": state["hyperopt_best_params"],
                    "optimization_time": result.get("duration_minutes", "N/A")
                })
                state["strategy_config"].update(state["hyperopt_best_params"])
                
            logger.info(f"Hyperopt completed successfully")
            logger.info(f"Best loss: {result.get('best_loss', 'N/A')}")
            logger.info(f"Total epochs: {result.get('total_epochs', 0)}")
            
        else:
            # Enhanced error reporting
            error_msg = "Hyperopt failed"
            error_details = {}
            
            if result:
                error_msg = result.get("error", "Unknown hyperopt error")
                error_details = {
                    "error": error_msg,
                    "result": result,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", "")
                }
                
                # Check for critical MCP server errors that should halt execution
                critical_errors = [
                    "list index out of range",
                    "IndexError",
                    "AttributeError", 
                    "KeyError",
                    "TypeError",
                    "NameError"
                ]
                
                is_critical = any(critical_error in error_msg for critical_error in critical_errors)
                if is_critical:
                    strategy_logger.log_error("🚨 CRITICAL MCP SERVER ERROR DETECTED - HALTING EXECUTION", 
                                            details=f"Error: {error_msg}\nFull result: {json.dumps(result, indent=2)}")
                    state["critical_error"] = True
                    state["halt_execution"] = True
                    state["errors"].append(f"CRITICAL ERROR: {error_msg}")
                    logger.critical(f"🚨 CRITICAL MCP SERVER ERROR - HALTING: {error_msg}")
                    return state
                    
            else:
                error_msg = "No result returned from MCP server"
                error_details = {"error": "MCP server did not return any result"}
            
            state["errors"].append(error_msg)
            state["optimization_complete"] = False
            
            strategy_logger.log_error(f"Hyperopt failed: {error_msg}", details=json.dumps(error_details, indent=2))
            logger.error(f"Hyperopt failed with details: {json.dumps(error_details, indent=2)}")
            
    except Exception as e:
        error_msg = f"Hyperopt execution error: {str(e)}"
        error_trace = traceback.format_exc()
        
        logger.error(f"Error running hyperopt: {str(e)}")
        logger.error(f"Traceback: {error_trace}")
        
        state["errors"].append(error_msg)
        state["optimization_complete"] = False
        
        strategy_logger.log_error(error_msg, e, error_trace)
    
    return state




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
    state: StrategyDevelopmentState,
    mcp_client: FreqtradeMCPClient
) -> Dict[str, Any]:
    """
    Run backtest with optimized parameters
    
    Args:
        state: Current workflow state
        mcp_client: MCP client instance
    """
    if not state["hyperopt_best_params"]:
        logger.warning("No optimized parameters available, using defaults")
        return None
    
    try:
        # Prepare backtest config with optimized params
        backtest_config = {
            "timeframe": state["strategy_config"]["timeframe"],
            "timerange": "20240101-20250101",
            "enable_protections": True,
            "max_open_trades": 3,
            **state["hyperopt_best_params"]  # Apply optimized parameters
        }
        
        # Call MCP backtest via stdio
        result = await mcp_client.backtest_strategy(
            strategy=state["strategy_name"],
            **backtest_config
        )
        
        if result.get("success"):
            return result
                        
        logger.error("Failed to run backtest with optimized parameters")
        return None
        
    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        return None