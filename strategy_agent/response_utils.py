"""Utilities for working with MCP responses."""

from typing import Dict, Any, TypeVar, Type, Optional, Union
from pydantic import BaseModel, ValidationError
import logging

from .models import (
    DownloadCandlesResponse,
    BacktestResponse,
    HyperoptResponse,
    MCPResponse
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def validate_response(response_data: Dict[str, Any], model_class: Type[T]) -> Optional[T]:
    """
    Validate and convert response data to Pydantic model.
    
    Args:
        response_data: Raw response data from MCP server
        model_class: Pydantic model class to validate against
        
    Returns:
        Validated model instance or None if validation fails
    """
    try:
        return model_class(**response_data)
    except ValidationError as e:
        logger.warning(f"Response validation failed for {model_class.__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during validation for {model_class.__name__}: {e}")
        return None


def is_successful_response(response: Union[Dict[str, Any], BaseModel]) -> bool:
    """
    Check if MCP response indicates success.
    
    Args:
        response: MCP response data or model
        
    Returns:
        True if response indicates success
    """
    if isinstance(response, BaseModel):
        return getattr(response, 'success', False)
    elif isinstance(response, dict):
        return response.get('success', False)
    return False


def get_error_message(response: Union[Dict[str, Any], BaseModel]) -> Optional[str]:
    """
    Extract error message from MCP response.
    
    Args:
        response: MCP response data or model
        
    Returns:
        Error message if present, None otherwise
    """
    if isinstance(response, BaseModel):
        return getattr(response, 'error', None)
    elif isinstance(response, dict):
        return response.get('error')
    return None


def extract_cache_files(download_response: Union[Dict[str, Any], DownloadCandlesResponse]) -> list:
    """
    Extract cache file information from download_candles response.
    
    Args:
        download_response: Response from download_candles tool
        
    Returns:
        List of cache file info objects
    """
    cache_files = []
    
    try:
        # Handle both dict and Pydantic model formats
        if isinstance(download_response, dict):
            cache_file_infos = download_response.get('cache_files', [])
        else:
            cache_file_infos = download_response.cache_files
                
        return cache_file_infos
                    
    except Exception as e:
        logger.error(f"Error extracting cache files: {e}")
        
    return cache_files




# Type guards for response checking
def is_download_response(response: Any) -> bool:
    """Check if response is from download_candles tool."""
    if isinstance(response, dict):
        return response.get('command') == 'download_candles'
    return isinstance(response, DownloadCandlesResponse)




def is_backtest_response(response: Any) -> bool:
    """Check if response is from backtest_strategy tool."""
    if isinstance(response, dict):
        return response.get('command') == 'backtest_strategy'
    return isinstance(response, BacktestResponse)


def is_hyperopt_response(response: Any) -> bool:
    """Check if response is from hyperopt_strategy tool."""
    if isinstance(response, dict):
        return response.get('command') == 'hyperopt_strategy'
    return isinstance(response, HyperoptResponse)