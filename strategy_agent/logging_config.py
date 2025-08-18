"""
Enhanced logging configuration for Strategy Development Agent
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import json


class ColoredConsoleHandler(logging.StreamHandler):
    """Console handler with colored output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def emit(self, record):
        try:
            msg = self.format(record)
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            
            # Add icons for different levels
            icons = {
                'DEBUG': '🔍',
                'INFO': '✅',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🚨'
            }
            icon = icons.get(record.levelname, '')
            
            # Format the message with color and icon
            formatted_msg = f"{color}{icon} {msg}{self.COLORS['RESET']}"
            
            stream = self.stream
            stream.write(formatted_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


class StructuredFileHandler(logging.FileHandler):
    """File handler that writes structured JSON logs"""
    
    def emit(self, record):
        try:
            # Create structured log entry
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add extra fields if present
            if hasattr(record, 'phase'):
                log_entry['phase'] = record.phase
            if hasattr(record, 'step'):
                log_entry['step'] = record.step
            if hasattr(record, 'data'):
                log_entry['data'] = record.data
            if hasattr(record, 'error_details'):
                log_entry['error_details'] = record.error_details
            
            # Write as JSON line
            self.stream.write(json.dumps(log_entry) + '\n')
            self.flush()
        except Exception:
            self.handleError(record)


class HumanReadableFileHandler(logging.FileHandler):
    """File handler that writes human-readable logs with clear formatting"""
    
    def emit(self, record):
        try:
            # Create section separator for important messages
            if record.levelname in ['ERROR', 'CRITICAL']:
                separator = "=" * 80
                self.stream.write(f"\n{separator}\n")
            elif hasattr(record, 'phase'):
                separator = "-" * 60
                self.stream.write(f"\n{separator}\n")
            
            # Write timestamp and level
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.stream.write(f"[{timestamp}] {record.levelname:8} ")
            
            # Add phase/step information if available
            if hasattr(record, 'phase'):
                self.stream.write(f"| PHASE: {record.phase} ")
            if hasattr(record, 'step'):
                self.stream.write(f"| STEP: {record.step} ")
            
            self.stream.write("\n")
            
            # Write the main message
            self.stream.write(f"  {record.getMessage()}\n")
            
            # Add additional data if present
            if hasattr(record, 'data'):
                self.stream.write("  DATA:\n")
                if isinstance(record.data, dict):
                    for key, value in record.data.items():
                        self.stream.write(f"    - {key}: {value}\n")
                else:
                    self.stream.write(f"    {record.data}\n")
            
            # Add error details if present
            if hasattr(record, 'error_details'):
                self.stream.write("  ERROR DETAILS:\n")
                self.stream.write(f"    {record.error_details}\n")
            
            # Add location information for debugging
            if record.levelname in ['ERROR', 'CRITICAL']:
                self.stream.write(f"  Location: {record.pathname}:{record.lineno} in {record.funcName}\n")
            
            self.flush()
        except Exception:
            self.handleError(record)


class StrategyLogger:
    """Enhanced logger for strategy development with multiple outputs"""
    
    def __init__(self, name: str, session_id: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.session_id = session_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.phase = None
        self.step = None
        
    def setup(self, console_level=logging.INFO, file_level=logging.DEBUG):
        """Setup logging with console and file handlers"""
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Console handler with colors
        console_handler = ColoredConsoleHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter('%(name)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Human-readable file handler
        human_log_file = log_dir / f"strategy_{self.session_id}.log"
        human_handler = HumanReadableFileHandler(human_log_file, encoding='utf-8')
        human_handler.setLevel(file_level)
        self.logger.addHandler(human_handler)
        
        # Structured JSON file handler
        json_log_file = log_dir / f"strategy_{self.session_id}.json"
        json_handler = StructuredFileHandler(json_log_file, encoding='utf-8')
        json_handler.setLevel(file_level)
        self.logger.addHandler(json_handler)
        
        # Log initialization
        self.logger.info(f"Logging initialized - Session: {self.session_id}")
        self.logger.info(f"Human-readable log: {human_log_file}")
        self.logger.info(f"Structured log: {json_log_file}")
        
        return human_log_file, json_log_file
    
    def set_phase(self, phase: str):
        """Set the current phase for contextual logging"""
        self.phase = phase
        self.logger.info(f"📋 PHASE: {phase}", extra={'phase': phase})
    
    def set_step(self, step: str):
        """Set the current step for contextual logging"""
        self.step = step
        self.logger.info(f"📍 STEP: {step}", extra={'step': step, 'phase': self.phase})
    
    def log_data(self, level: int, message: str, data: dict = None):
        """Log with additional data"""
        extra = {'phase': self.phase, 'step': self.step}
        if data:
            extra['data'] = data
        self.logger.log(level, message, extra=extra)
    
    def log_error(self, message: str, error: Exception = None, details: str = None):
        """Log error with details"""
        extra = {
            'phase': self.phase,
            'step': self.step,
            'error_details': str(error) if error else details
        }
        
        if error:
            import traceback
            extra['error_details'] = traceback.format_exc()
        
        self.logger.error(message, extra=extra)
    
    def log_success(self, message: str, data: dict = None):
        """Log success message"""
        self.log_data(logging.INFO, f"✨ SUCCESS: {message}", data)
    
    def log_progress(self, message: str, current: int = None, total: int = None):
        """Log progress update"""
        if current is not None and total is not None:
            progress_pct = (current / total * 100) if total > 0 else 0
            message = f"{message} [{current}/{total}] ({progress_pct:.1f}%)"
        self.logger.info(f"⏳ {message}", extra={'phase': self.phase, 'step': self.step})
    
    def log_metrics(self, metrics: dict):
        """Log performance metrics"""
        self.logger.info("📊 METRICS:", extra={'phase': self.phase, 'step': self.step})
        for key, value in metrics.items():
            self.logger.info(f"  • {key}: {value}", extra={'phase': self.phase, 'step': self.step, 'data': metrics})


def setup_logging(session_id: Optional[str] = None, verbose: bool = False) -> StrategyLogger:
    """
    Setup enhanced logging for strategy development
    
    Args:
        session_id: Optional session ID for log files
        verbose: Enable verbose (DEBUG) console output
        
    Returns:
        Configured StrategyLogger instance
    """
    logger = StrategyLogger("strategy_agent", session_id)
    console_level = logging.DEBUG if verbose else logging.INFO
    logger.setup(console_level=console_level)
    
    return logger


# Create a global logger instance
global_logger: Optional[StrategyLogger] = None

def get_logger() -> StrategyLogger:
    """Get or create the global logger instance"""
    global global_logger
    if global_logger is None:
        global_logger = setup_logging()
    return global_logger