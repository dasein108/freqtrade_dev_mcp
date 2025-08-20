"""Simplified base models for MCP communication."""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class MCPBaseResponse(BaseModel):
    """Simplified base response for all MCP operations."""
    command: str = Field(..., description="The MCP command executed")
    success: bool = Field(..., description="Operation success status")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_seconds: Optional[float] = Field(None, description="Execution time")
    
    class Config:
        extra = "forbid"  # Strict schema - no extra fields allowed


class CacheFileInfo(BaseModel):
    """Cache file information."""
    pair: str = Field(..., description="Trading pair")
    filename: str = Field(..., description="Cache filename") 
    full_path: str = Field(..., description="Full file path")
    candle_count: int = Field(0, description="Number of candles")
    
    class Config:
        extra = "forbid"


class DownloadCandlesResponse(MCPBaseResponse):
    """Download candles response."""
    pairs: List[str] = Field(..., description="Requested pairs")
    timeframes: List[str] = Field(..., description="Requested timeframes")
    cache_files: List[CacheFileInfo] = Field(default_factory=list, description="Created cache files")
    total_candles: int = Field(0, description="Total candles downloaded")


class PerformanceMetrics(BaseModel):
    """Trading performance metrics."""
    total_profit_pct: float = Field(..., description="Total profit %")
    total_trades: int = Field(..., description="Total trades")
    win_rate: float = Field(..., description="Win rate (0-1)")
    max_drawdown_pct: float = Field(..., description="Max drawdown %")
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    
    class Config:
        extra = "forbid"


class BacktestResponse(MCPBaseResponse):
    """Backtest response."""
    strategy: str = Field(..., description="Strategy name")
    result_id: str = Field(..., description="Result identifier")
    performance: PerformanceMetrics = Field(..., description="Performance metrics")


class HyperoptResponse(MCPBaseResponse):
    """Hyperopt response."""
    strategy: str = Field(..., description="Strategy name")
    result_id: str = Field(..., description="Result identifier")
    best_result: PerformanceMetrics = Field(..., description="Best result")
    best_params: Dict[str, Any] = Field(..., description="Best parameters")


# Utility functions
def create_error_response(command: str, error: str, duration: Optional[float] = None) -> MCPBaseResponse:
    """Create standardized error response."""
    return MCPBaseResponse(
        command=command,
        success=False,
        error=error,
        duration_seconds=duration
    )


def create_success_response(command: str, duration: Optional[float] = None) -> MCPBaseResponse:
    """Create standardized success response."""
    return MCPBaseResponse(
        command=command,
        success=True,
        duration_seconds=duration
    )