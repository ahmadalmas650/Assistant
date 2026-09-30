"""
Logger Module
Provides logging functionality with different levels and outputs
"""

import json
import time
import os
import sys
from typing import Dict, List, Optional, Any, TextIO
from dataclasses import dataclass, field
from enum import Enum, auto
import threading


class LogLevel(Enum):
    """Logging levels"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class LogOutput(Enum):
    """Log output destinations"""
    CONSOLE = auto()
    FILE = auto()
    BOTH = auto()


@dataclass
class LogEntry:
    """A single log entry"""
    level: LogLevel
    message: str
    module: str
    timestamp: float = field(default_factory=time.time)
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.name,
            "message": self.message,
            "module": self.module,
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "metadata": self.metadata
        }
    
    def to_string(self) -> str:
        """Convert to formatted string"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        return f"[{timestamp}] [{self.level.name}] [{self.module}] {self.message}"


class Logger:
    """
    Logger for the JARVIS system
    
    Supports multiple output destinations and log levels
    """
    
    def __init__(self, module: str, 
                 level: LogLevel = LogLevel.INFO,
                 output: LogOutput = LogOutput.CONSOLE,
                 log_file: str = None,
                 debug: bool = False):
        """
        Initialize the logger
        
        Args:
            module: Name of the module using this logger
            level: Minimum log level to output
            output: Output destination(s)
            log_file: Path to log file (if output includes FILE)
            debug: Enable debug mode
        """
        self.module = module
        self.level = level
        self.output = output
        self.log_file = log_file
        self.debug = debug
        
        # Log history
        self._history: List[LogEntry] = []
        self._max_history = 1000
        
        # File handle
        self._file_handle: Optional[TextIO] = None
        
        # Initialize file output if needed
        if output in [LogOutput.FILE, LogOutput.BOTH] and log_file:
            self._open_log_file()
    
    def _open_log_file(self):
        """Open the log file"""
        try:
            # Ensure directory exists
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Open file in append mode
            self._file_handle = open(self.log_file, 'a', encoding='utf-8')
        except Exception as e:
            print(f"Failed to open log file: {e}")
            self._file_handle = None
    
    def _close_log_file(self):
        """Close the log file"""
        if self._file_handle:
            try:
                self._file_handle.close()
            except:
                pass
            self._file_handle = None
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if a message should be logged based on level"""
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4
        }
        
        return level_order[level] >= level_order[self.level]
    
    def _log(self, level: LogLevel, message: str, metadata: Dict = None):
        """
        Internal log method
        
        Args:
            level: Log level
            message: Message to log
            metadata: Additional metadata
        """
        if not self._should_log(level):
            return
        
        # Create log entry
        entry = LogEntry(
            level=level,
            message=message,
            module=self.module,
            metadata=metadata or {}
        )
        
        # Add to history
        self._add_to_history(entry)
        
        # Format message
        formatted_message = entry.to_string()
        
        # Output to console
        if self.output in [LogOutput.CONSOLE, LogOutput.BOTH]:
            self._output_to_console(level, formatted_message)
        
        # Output to file
        if self.output in [LogOutput.FILE, LogOutput.BOTH]:
            self._output_to_file(formatted_message)
    
    def _add_to_history(self, entry: LogEntry):
        """Add entry to history"""
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def _output_to_console(self, level: LogLevel, message: str):
        """Output to console"""
        # Color codes for different levels
        colors = {
            LogLevel.DEBUG: '\033[94m',    # Blue
            LogLevel.INFO: '\033[92m',     # Green
            LogLevel.WARNING: '\033[93m',  # Yellow
            LogLevel.ERROR: '\033[91m',    # Red
            LogLevel.CRITICAL: '\033[95m'  # Magenta
        }
        reset_color = '\033[0m'
        
        # Use colors if terminal supports it
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = colors.get(level, '')
            print(f"{color}{message}{reset_color}")
        else:
            print(message)
    
    def _output_to_file(self, message: str):
        """Output to file"""
        if self._file_handle:
            try:
                self._file_handle.write(message + '\n')
                self._file_handle.flush()
            except:
                pass
    
    # Public logging methods
    
    def debug(self, message: str, metadata: Dict = None):
        """Log a debug message"""
        if self.debug:
            self._log(LogLevel.DEBUG, message, metadata)
    
    def info(self, message: str, metadata: Dict = None):
        """Log an info message"""
        self._log(LogLevel.INFO, message, metadata)
    
    def warning(self, message: str, metadata: Dict = None):
        """Log a warning message"""
        self._log(LogLevel.WARNING, message, metadata)
    
    def error(self, message: str, metadata: Dict = None):
        """Log an error message"""
        self._log(LogLevel.ERROR, message, metadata)
    
    def critical(self, message: str, metadata: Dict = None):
        """Log a critical message"""
        self._log(LogLevel.CRITICAL, message, metadata)
    
    # Exception logging
    
    def exception(self, message: str, exception: Exception, 
                 metadata: Dict = None):
        """Log an exception"""
        import traceback
        
        # Format exception info
        exc_info = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc()
        }
        
        # Add to metadata
        if metadata is None:
            metadata = {}
        metadata["exception"] = exc_info
        
        # Log as error
        self.error(f"{message}: {exc_info['type']} - {exc_info['message']}", metadata)
    
    # History methods
    
    def get_history(self, count: int = 100) -> List[LogEntry]:
        """Get recent log history"""
        return self._history[-count:] if count > 0 else self._history
    
    def get_history_by_level(self, level: LogLevel, count: int = 100) -> List[LogEntry]:
        """Get log history filtered by level"""
        return [entry for entry in self._history if entry.level == level][-count:]
    
    def get_history_by_module(self, module: str, count: int = 100) -> List[LogEntry]:
        """Get log history filtered by module"""
        return [entry for entry in self._history if entry.module == module][-count:]
    
    def clear_history(self):
        """Clear log history"""
        self._history = []
    
    # Configuration methods
    
    def set_level(self, level: LogLevel):
        """Set minimum log level"""
        self.level = level
    
    def set_output(self, output: LogOutput):
        """Set output destination"""
        self.output = output
        
        # Reopen file if needed
        if output in [LogOutput.FILE, LogOutput.BOTH] and self.log_file:
            self._open_log_file()
        else:
            self._close_log_file()
    
    def set_log_file(self, log_file: str):
        """Set log file path"""
        self.log_file = log_file
        
        # Reopen file if needed
        if self.output in [LogOutput.FILE, LogOutput.BOTH] and log_file:
            self._open_log_file()
        else:
            self._close_log_file()
    
    def enable_debug(self):
        """Enable debug mode"""
        self.debug = True
    
    def disable_debug(self):
        """Disable debug mode"""
        self.debug = False
    
    # Utility methods
    
    def get_statistics(self) -> Dict:
        """Get logging statistics"""
        stats = {
            "total_entries": len(self._history),
            "by_level": {},
            "by_module": {}
        }
        
        for entry in self._history:
            # Count by level
            level_name = entry.level.name
            stats["by_level"][level_name] = stats["by_level"].get(level_name, 0) + 1
            
            # Count by module
            stats["by_module"][entry.module] = stats["by_module"].get(entry.module, 0) + 1
        
        return stats
    
    # Cleanup
    
    def cleanup(self):
        """Clean up resources"""
        self._close_log_file()
        self._history = []
