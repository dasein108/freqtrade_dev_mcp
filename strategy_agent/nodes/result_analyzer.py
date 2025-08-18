"""
Result analysis and finalization nodes
"""
import logging
import json
from typing import Dict, Any
from datetime import datetime

from ..state import (
    StrategyDevelopmentState,
    StrategyAnalysis,
    PerformanceMetrics,
    update_state_metrics
)
from ..prompts.analysis_prompts import STRATEGY_ANALYSIS_PROMPT
from ..llm_client import create_llm_client, LLMConfig
from ..config import config
from ..logging_config import get_logger

logger = logging.getLogger(__name__)
strategy_logger = get_logger()


def _get_analysis_client():
    """Get LLM client for result analysis"""
    try:
        llm_config_dict = config.get_llm_config()
        llm_config = LLMConfig(**llm_config_dict)
        return create_llm_client(llm_config)
    except Exception as e:
        logger.error(f"Failed to create LLM client for analysis: {e}")
        raise


async def analyze_results(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Analyze backtest and hyperopt results
    """
    logger.info("Analyzing strategy results")
    strategy_logger.set_phase("RESULTS ANALYSIS")
    strategy_logger.set_step("Performance Evaluation")
    state["current_step"] = "analyze_results"
    
    # First run backtest with optimized parameters
    from .hyperopt_runner import run_backtest_with_params
    
    # Get MCP client from state
    mcp_client = state.get("mcp_client")
    if mcp_client is None:
        state["errors"].append("No MCP client available for backtest")
        return state
    
    backtest_results = await run_backtest_with_params(state, mcp_client)
    
    if backtest_results and backtest_results.get("success"):
        state["backtest_results"] = backtest_results
        state["backtest_file_path"] = backtest_results.get("results_file")
        
        # Update metrics
        state = update_state_metrics(state, backtest_results)
    else:
        # Use hyperopt metrics as fallback
        if state["hyperopt_results"] and "best_metrics" in state["hyperopt_results"]:
            metrics_data = state["hyperopt_results"]["best_metrics"]
            state["performance_metrics"] = PerformanceMetrics(
                total_profit_pct=metrics_data.get("profit", 0) * 100,
                sharpe_ratio=metrics_data.get("sharpe", 0),
                max_drawdown_pct=abs(metrics_data.get("drawdown", 0)),
                win_rate_pct=50,  # Default estimate
                total_trades=metrics_data.get("trades", 0),
                avg_trade_duration="N/A",
                best_pair="N/A",
                worst_pair="N/A"
            )
            state["is_profitable"] = state["performance_metrics"].total_profit_pct > 5.0
    
    # Analyze with LLM
    try:
        if state["performance_metrics"]:
            llm_client = _get_analysis_client()
            analysis = await llm_client.create_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert trading strategy analyst."
                    },
                    {
                        "role": "user",
                        "content": STRATEGY_ANALYSIS_PROMPT.format(
                            strategy_name=state["strategy_name"],
                            metrics=json.dumps({
                                "profit": state["performance_metrics"].total_profit_pct,
                                "sharpe": state["performance_metrics"].sharpe_ratio,
                                "drawdown": state["performance_metrics"].max_drawdown_pct,
                                "trades": state["performance_metrics"].total_trades,
                                "win_rate": state["performance_metrics"].win_rate_pct
                            }, indent=2),
                            strategy_code=state["strategy_code"][:2000]  # First 2000 chars
                        )
                    }
                ],
                response_model=StrategyAnalysis,
                temperature=0.3
            )
            
            state["strategy_analysis"] = analysis
            state["analysis_summary"] = f"Performance: {analysis.performance_rating}. {analysis.risk_assessment}"
            
            logger.info(f"Analysis complete: {analysis.performance_rating}")
            logger.info(f"Profitable: {analysis.is_profitable}")
            
            # Override profitability based on analysis
            state["is_profitable"] = analysis.is_profitable
            
        else:
            state["errors"].append("No performance metrics available for analysis")
            state["is_profitable"] = False
            
    except Exception as e:
        logger.error(f"Error analyzing results: {str(e)}")
        state["errors"].append(f"Analysis error: {str(e)}")
        # Use metric-based profitability
        state["is_profitable"] = (
            state["performance_metrics"] and 
            state["performance_metrics"].total_profit_pct > 5.0
        )
    
    return state


async def finalize_strategy(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Finalize successful strategy
    """
    logger.info("Finalizing successful strategy")
    state["current_step"] = "finalize_strategy"
    
    # Prepare final result
    state["final_strategy"] = {
        "name": state["strategy_name"],
        "file_path": state["strategy_file_path"],
        "config": state["strategy_config"],
        "hyperopt_params": state["hyperopt_best_params"],
        "metrics": {
            "profit": state["performance_metrics"].total_profit_pct if state["performance_metrics"] else 0,
            "sharpe": state["performance_metrics"].sharpe_ratio if state["performance_metrics"] else 0,
            "drawdown": state["performance_metrics"].max_drawdown_pct if state["performance_metrics"] else 0,
            "trades": state["performance_metrics"].total_trades if state["performance_metrics"] else 0,
            "win_rate": state["performance_metrics"].win_rate_pct if state["performance_metrics"] else 0
        },
        "backtest_file": state["backtest_file_path"],
        "hyperopt_file": state["hyperopt_results"].get("results_file") if state["hyperopt_results"] else None
    }
    
    # Save strategy configuration
    await save_strategy_config(state)
    
    # Mark as successful
    state["success"] = True
    state["end_time"] = datetime.now()
    state["total_duration_minutes"] = (
        (state["end_time"] - state["start_time"]).total_seconds() / 60
    )
    
    logger.info(f"✅ Strategy finalized: {state['strategy_name']}")
    logger.info(f"Total profit: {state['final_strategy']['metrics']['profit']:.2f}%")
    logger.info(f"Duration: {state['total_duration_minutes']:.1f} minutes")
    
    return state


async def return_best_attempt(state: StrategyDevelopmentState) -> StrategyDevelopmentState:
    """
    Node: Return best attempt when max iterations reached
    """
    logger.info("Returning best attempt after max iterations")
    state["current_step"] = "return_best_attempt"
    
    # Find best iteration from history
    best_iteration = None
    best_profit = -100
    
    for iteration in state["iteration_history"]:
        if "metrics" in iteration and iteration["metrics"].get("profit", -100) > best_profit:
            best_profit = iteration["metrics"]["profit"]
            best_iteration = iteration
    
    # Use current state if no better iteration
    if not best_iteration and state["performance_metrics"]:
        best_iteration = {
            "strategy_name": state["strategy_name"],
            "metrics": {
                "profit": state["performance_metrics"].total_profit_pct,
                "sharpe": state["performance_metrics"].sharpe_ratio,
                "drawdown": state["performance_metrics"].max_drawdown_pct,
                "trades": state["performance_metrics"].total_trades
            }
        }
    
    state["best_iteration"] = best_iteration
    state["success"] = False  # Mark as unsuccessful but with results
    state["end_time"] = datetime.now()
    state["total_duration_minutes"] = (
        (state["end_time"] - state["start_time"]).total_seconds() / 60
    )
    
    if best_iteration:
        logger.info(f"Best attempt: {best_iteration['strategy_name']}")
        logger.info(f"Best profit: {best_iteration['metrics']['profit']:.2f}%")
    else:
        logger.warning("No successful iterations to return")
    
    return state


async def save_strategy_config(state: StrategyDevelopmentState):
    """
    Save strategy configuration file
    """
    try:
        from pathlib import Path
        
        # Save config next to strategy file
        if state["strategy_file_path"]:
            strategy_path = Path(state["strategy_file_path"])
            config_path = strategy_path.with_suffix(".json")
            
            config = {
                "strategy_name": state["strategy_name"],
                "created": state["start_time"].isoformat(),
                "timeframe": state["strategy_config"]["timeframe"],
                "hyperopt_params": state["hyperopt_best_params"],
                "performance": {
                    "profit": state["performance_metrics"].total_profit_pct if state["performance_metrics"] else 0,
                    "sharpe": state["performance_metrics"].sharpe_ratio if state["performance_metrics"] else 0,
                    "drawdown": state["performance_metrics"].max_drawdown_pct if state["performance_metrics"] else 0,
                    "trades": state["performance_metrics"].total_trades if state["performance_metrics"] else 0
                },
                "idea": {
                    "description": state["strategy_idea"].description if state["strategy_idea"] else "",
                    "indicators": state["strategy_idea"].indicators if state["strategy_idea"] else []
                }
            }
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Strategy config saved to {config_path}")
            
    except Exception as e:
        logger.error(f"Error saving strategy config: {str(e)}")
        state["warnings"].append(f"Could not save strategy config: {str(e)}")