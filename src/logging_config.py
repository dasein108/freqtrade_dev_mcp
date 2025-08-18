"""
Enhanced logging configuration for MCP Server
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
import json


class MCPFileHandler(logging.FileHandler):
    """File handler for MCP server logs"""
    
    def __init__(self, filename, mode='a', encoding='utf-8'):
        super().__init__(filename, mode, encoding, delay=False)
        # Write header
        self.stream.write(f"\n{'='*80}\n")
        self.stream.write(f"MCP Server Started: {datetime.now().isoformat()}\n")
        self.stream.write(f"{'='*80}\n\n")
        self.flush()


class MCPFormatter(logging.Formatter):
    """Custom formatter for MCP server logs"""
    
    def format(self, record):
        # Add tool name if present
        if hasattr(record, 'tool'):
            record.msg = f"[TOOL: {record.tool}] {record.msg}"
        
        # Add request ID if present  
        if hasattr(record, 'request_id'):
            record.msg = f"[REQ: {record.request_id}] {record.msg}"
            
        return super().format(record)


def setup_mcp_logging(log_level=logging.INFO, log_to_file=True):
    """
    Setup logging for MCP server
    
    Args:
        log_level: Logging level
        log_to_file: Whether to log to file
        
    Returns:
        Path to log file if logging to file, None otherwise
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler with custom format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = MCPFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    log_file = None
    if log_to_file:
        # File handler for detailed logs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f"mcp_server_{timestamp}.log"
        
        file_handler = MCPFileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = MCPFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Also create a JSON log for structured data
        json_log_file = log_dir / f"mcp_server_{timestamp}.json"
        json_handler = logging.FileHandler(json_log_file, encoding='utf-8')
        json_handler.setLevel(logging.DEBUG)
        
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    'timestamp': datetime.now().isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                
                # Add custom fields
                for field in ['tool', 'request_id', 'params', 'result', 'error']:
                    if hasattr(record, field):
                        log_obj[field] = getattr(record, field)
                
                return json.dumps(log_obj)
        
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    
    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info(f"MCP Server logging initialized")
    if log_file:
        logger.info(f"Log file: {log_file}")
    
    return log_file


class MCPLogger:
    """Helper class for MCP-specific logging"""
    
    def __init__(self, name="mcp_server"):
        self.logger = logging.getLogger(name)
        self.request_id = None
        
    def set_request(self, request_id):
        """Set current request ID for context"""
        self.request_id = request_id
        
    def log_tool_call(self, tool_name, params, level=logging.INFO):
        """Log a tool call with parameters"""
        extra = {
            'tool': tool_name,
            'params': params
        }
        if self.request_id:
            extra['request_id'] = self.request_id
            
        self.logger.log(level, f"Tool called: {tool_name}", extra=extra)
        
    def log_tool_result(self, tool_name, result, success=True):
        """Log tool execution result"""
        extra = {
            'tool': tool_name,
            'result': result if success else None,
            'error': result if not success else None
        }
        if self.request_id:
            extra['request_id'] = self.request_id
            
        level = logging.INFO if success else logging.ERROR
        msg = f"Tool completed: {tool_name}" if success else f"Tool failed: {tool_name}"
        self.logger.log(level, msg, extra=extra)
        
    def log_error(self, message, error=None):
        """Log an error with details"""
        extra = {}
        if self.request_id:
            extra['request_id'] = self.request_id
        if error:
            extra['error'] = str(error)
            
        self.logger.error(message, extra=extra, exc_info=error is not None)