"""
LangGraph State Schema for Strategy Development Agent
"""
from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime
import pandas as pd
from pydantic import BaseModel, Field


class StrategyIdea(BaseModel):
    """Structured strategy idea from LLM"""
    name: str
    description: str
    indicators: List[str]
    entry_logic: str
    exit_logic: str
    risk_management: str
    timeframe_preference: str
    rationale: str


class PerformanceMetrics(BaseModel):
    """Performance metrics from backtest/hyperopt"""
    total_profit_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    avg_trade_duration: str
    best_pair: str
    worst_pair: str
    calmar_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None


class StrategyAnalysis(BaseModel):
    """Analysis results from strategy evaluation"""
    is_profitable: bool
    performance_rating: str  # "excellent", "good", "poor", "failure"
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[str]
    risk_assessment: str


class StrategyDevelopmentState(TypedDict):
    """
    Main state schema for the strategy development workflow
    """
    # Market Data
    symbols: List[str]  # ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    timeframes: List[str]  # ["1h", "4h"]
    candle_data: Dict[str, Dict[str, Any]]  # {symbol: {tf: dataframe_dict}}
    data_cached: bool
    data_fetch_timestamp: Optional[datetime]
    
    # Strategy Development
    strategy_idea: Optional[StrategyIdea]
    strategy_name: str
    strategy_code: str
    strategy_config: Dict[str, Any]
    strategy_file_path: Optional[str]
    
    # Optimization
    hyperopt_config: Dict[str, Any]
    hyperopt_results: Dict[str, Any]
    hyperopt_best_params: Dict[str, Any]
    optimization_complete: bool
    hyperopt_epochs: int
    hyperopt_loss_function: str
    
    # Backtest Results
    backtest_results: Dict[str, Any]
    backtest_file_path: Optional[str]
    
    # Analysis
    performance_metrics: Optional[PerformanceMetrics]
    strategy_analysis: Optional[StrategyAnalysis]
    is_profitable: bool
    analysis_summary: str
    
    # Iteration Control
    iteration_count: int
    max_iterations: int  # Default: 3
    iteration_history: List[Dict[str, Any]]  # Track all attempts
    best_iteration: Optional[Dict[str, Any]]
    
    # Final Results
    final_strategy: Optional[Dict[str, Any]]
    success: bool
    
    # Error Handling
    errors: List[str]
    warnings: List[str]
    current_step: str
    retry_count: int
    max_retries: int  # Default: 3
    
    # Critical Error Handling
    critical_error: bool  # Flag for critical errors that should halt execution
    halt_execution: bool  # Flag to halt the workflow
    
    # Metadata
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_minutes: Optional[float]


class CheckpointState(BaseModel):
    """State that can be saved and restored"""
    state: Dict[str, Any]
    timestamp: datetime
    step: str
    iteration: int
    session_id: str
    
    class Config:
        arbitrary_types_allowed = True


def create_initial_state(
    symbols: List[str],
    timeframes: List[str],
    max_iterations: int = 3,
    hyperopt_epochs: int = 100
) -> StrategyDevelopmentState:
    """Create initial state for the workflow"""
    from uuid import uuid4
    
    return StrategyDevelopmentState(
        # Market Data
        symbols=symbols,
        timeframes=timeframes,
        candle_data={},
        data_cached=False,
        data_fetch_timestamp=None,
        
        # Strategy Development
        strategy_idea=None,
        strategy_name="",
        strategy_code="",
        strategy_config={},
        strategy_file_path=None,
        
        # Optimization
        hyperopt_config={},
        hyperopt_results={},
        hyperopt_best_params={},
        optimization_complete=False,
        hyperopt_epochs=hyperopt_epochs,
        hyperopt_loss_function="SharpeHyperOptLoss",
        
        # Backtest Results
        backtest_results={},
        backtest_file_path=None,
        
        # Analysis
        performance_metrics=None,
        strategy_analysis=None,
        is_profitable=False,
        analysis_summary="",
        
        # Iteration Control
        iteration_count=0,
        max_iterations=max_iterations,
        iteration_history=[],
        best_iteration=None,
        
        # Final Results
        final_strategy=None,
        success=False,
        
        # Error Handling
        errors=[],
        warnings=[],
        current_step="initialization",
        retry_count=0,
        max_retries=3,
        
        # Critical Error Handling
        critical_error=False,
        halt_execution=False,
        
        # Metadata
        session_id=str(uuid4()),
        start_time=datetime.now(),
        end_time=None,
        total_duration_minutes=None
    )


def update_state_metrics(
    state: StrategyDevelopmentState,
    backtest_results: Dict[str, Any]
) -> StrategyDevelopmentState:
    """Update state with performance metrics from backtest results"""
    if not backtest_results or "strategy" not in backtest_results:
        return state
    
    strategy_stats = backtest_results["strategy"]
    
    metrics = PerformanceMetrics(
        total_profit_pct=strategy_stats.get("profit_total_pct", 0),
        sharpe_ratio=strategy_stats.get("sharpe", 0),
        max_drawdown_pct=abs(strategy_stats.get("max_drawdown_pct", 0)),
        win_rate_pct=strategy_stats.get("win_rate", 0) * 100,
        total_trades=strategy_stats.get("total_trades", 0),
        avg_trade_duration=strategy_stats.get("avg_duration", ""),
        best_pair=strategy_stats.get("best_pair", ""),
        worst_pair=strategy_stats.get("worst_pair", ""),
        calmar_ratio=strategy_stats.get("calmar", None),
        sortino_ratio=strategy_stats.get("sortino", None)
    )
    
    state["performance_metrics"] = metrics
    state["is_profitable"] = metrics.total_profit_pct > 5.0  # 5% threshold
    
    return state


def should_continue_optimization(state: StrategyDevelopmentState) -> str:
    """Determine next step based on performance and critical errors"""
    # Check for critical errors first - halt execution immediately
    if state.get("critical_error", False) or state.get("halt_execution", False):
        return "return_best_attempt"  # Exit with best attempt on critical errors
    
    if state["is_profitable"]:
        return "finalize_strategy"
    elif state["iteration_count"] >= state["max_iterations"]:
        return "return_best_attempt"
    else:
        return "rewrite_strategy"


def get_state_summary(state: StrategyDevelopmentState) -> Dict[str, Any]:
    """Get a summary of the current state for logging"""
    summary = {
        "session_id": state["session_id"],
        "current_step": state["current_step"],
        "iteration": state["iteration_count"],
        "strategy_name": state["strategy_name"],
        "is_profitable": state["is_profitable"],
        "errors": len(state["errors"]),
        "warnings": len(state["warnings"])
    }
    
    # Add critical error information if present
    if state.get("critical_error", False):
        summary["critical_error"] = True
    if state.get("halt_execution", False):
        summary["halt_execution"] = True
        
    return summary