"""
Error Handler Module
Handles errors and exceptions with logging and recovery
"""

import asyncio
import json
import time
import traceback
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import sys

from .logger import Logger, LogLevel


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class ErrorType(Enum):
    """Error types"""
    EXCEPTION = auto()
    VALIDATION = auto()
    NETWORK = auto()
    IO = auto()
    TIMEOUT = auto()
    RESOURCE = auto()
    UNKNOWN = auto()


@dataclass
class ErrorRecord:
    """Record of an error"""
    error_id: str
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    module: str
    context: str
    timestamp: float = field(default_factory=time.time)
    stack_trace: str = ""
    metadata: Dict = field(default_factory=dict)
    resolved: bool = False
    resolution: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "error_id": self.error_id,
            "error_type": self.error_type.name,
            "severity": self.severity.name,
            "message": self.message,
            "module": self.module,
            "context": self.context,
            "timestamp": self.timestamp,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata,
            "resolved": self.resolved,
            "resolution": self.resolution
        }


class ErrorHandler:
    """
    Handles errors and exceptions throughout the system
    """
    
    def __init__(self, logger: Logger):
        """
        Initialize the error handler
        
        Args:
            logger: Logger instance for logging errors
        """
        self.logger = logger
        
        # Error history
        self._errors: Dict[str, ErrorRecord] = {}
        self._error_history: List[ErrorRecord] = []
        self._max_history = 1000
        
        # Callbacks
        self._on_error: List[Callable[[ErrorRecord], None]] = []
        self._on_critical_error: List[Callable[[ErrorRecord], None]] = []
        
        # Recovery actions
        self._recovery_actions: Dict[ErrorType, List[Callable]] = {}
        
        # Statistics
        self._stats = {
            "total_errors": 0,
            "by_type": {},
            "by_severity": {},
            "by_module": {},
            "unresolved": 0
        }
    
    def handle_error(self, error: Exception, context: str = "", 
                    module: str = None, metadata: Dict = None):
        """
        Handle an exception
        
        Args:
            error: The exception to handle
            context: Context where the error occurred
            module: Module where the error occurred
            metadata: Additional metadata
        """
        try:
            # Determine error type and severity
            error_type = self._determine_error_type(error)
            severity = self._determine_severity(error, context)
            
            # Create error record
            error_id = self._generate_error_id()
            stack_trace = traceback.format_exc()
            
            error_record = ErrorRecord(
                error_id=error_id,
                error_type=error_type,
                severity=severity,
                message=str(error),
                module=module or "unknown",
                context=context,
                stack_trace=stack_trace,
                metadata=metadata or {}
            )
            
            # Store error
            self._errors[error_id] = error_record
            self._error_history.append(error_record)
            
            # Trim history if needed
            if len(self._error_history) > self._max_history:
                self._error_history = self._error_history[-self._max_history:]
            
            # Update statistics
            self._stats["total_errors"] += 1
            self._stats["by_type"][error_type.name] = self._stats["by_type"].get(error_type.name, 0) + 1
            self._stats["by_severity"][severity.name] = self._stats["by_severity"].get(severity.name, 0) + 1
            self._stats["by_module"][error_record.module] = self._stats["by_module"].get(error_record.module, 0) + 1
            self._stats["unresolved"] += 1
            
            # Log the error
            self._log_error(error_record)
            
            # Notify callbacks
            self._notify_error(error_record)
            
            # Attempt recovery
            self._attempt_recovery(error_record)
            
            return error_id
            
        except Exception as e:
            # Fallback to basic logging if error handling fails
            print(f"ERROR in error handler: {e}")
            print(f"Original error: {error}")
            return None
    
    def handle_message(self, message: str, context: str = "", 
                      severity: ErrorSeverity = ErrorSeverity.ERROR,
                      module: str = None, metadata: Dict = None):
        """
        Handle an error message (not an exception)
        
        Args:
            message: The error message
            context: Context where the error occurred
            severity: Severity level
            module: Module where the error occurred
            metadata: Additional metadata
        """
        try:
            # Create error record
            error_id = self._generate_error_id()
            
            error_record = ErrorRecord(
                error_id=error_id,
                error_type=ErrorType.UNKNOWN,
                severity=severity,
                message=message,
                module=module or "unknown",
                context=context,
                stack_trace="",
                metadata=metadata or {}
            )
            
            # Store error
            self._errors[error_id] = error_record
            self._error_history.append(error_record)
            
            # Trim history if needed
            if len(self._error_history) > self._max_history:
                self._error_history = self._error_history[-self._max_history:]
            
            # Update statistics
            self._stats["total_errors"] += 1
            self._stats["by_type"]["UNKNOWN"] = self._stats["by_type"].get("UNKNOWN", 0) + 1
            self._stats["by_severity"][severity.name] = self._stats["by_severity"].get(severity.name, 0) + 1
            self._stats["by_module"][error_record.module] = self._stats["by_module"].get(error_record.module, 0) + 1
            self._stats["unresolved"] += 1
            
            # Log the error
            self._log_error(error_record)
            
            # Notify callbacks
            self._notify_error(error_record)
            
            return error_id
            
        except Exception as e:
            print(f"ERROR in error handler: {e}")
            print(f"Original message: {message}")
            return None
    
    def _generate_error_id(self) -> str:
        """Generate a unique error ID"""
        import uuid
        return f"err_{uuid.uuid4().hex[:12]}_{int(time.time())}"
    
    def _determine_error_type(self, error: Exception) -> ErrorType:
        """Determine the error type from the exception"""
        error_type_map = {
            "ValueError": ErrorType.VALIDATION,
            "TypeError": ErrorType.VALIDATION,
            "KeyError": ErrorType.VALIDATION,
            "AttributeError": ErrorType.VALIDATION,
            "IOError": ErrorType.IO,
            "OSError": ErrorType.IO,
            "FileNotFoundError": ErrorType.IO,
            "PermissionError": ErrorType.IO,
            "TimeoutError": ErrorType.TIMEOUT,
            "ConnectionError": ErrorType.NETWORK,
            "socket.error": ErrorType.NETWORK,
            "MemoryError": ErrorType.RESOURCE,
            "RuntimeError": ErrorType.RESOURCE
        }
        
        error_name = type(error).__name__
        return error_type_map.get(error_name, ErrorType.EXCEPTION)
    
    def _determine_severity(self, error: Exception, context: str) -> ErrorSeverity:
        """Determine severity based on error type and context"""
        # Check for critical errors
        critical_errors = [
            "MemoryError",
            "RuntimeError",
            "KeyboardInterrupt",
            "SystemExit"
        ]
        
        if type(error).__name__ in critical_errors:
            return ErrorSeverity.CRITICAL
        
        # Check for network errors
        network_errors = [
            "ConnectionError",
            "TimeoutError",
            "socket.error"
        ]
        
        if type(error).__name__ in network_errors:
            return ErrorSeverity.WARNING
        
        # Default to ERROR
        return ErrorSeverity.ERROR
    
    def _log_error(self, error_record: ErrorRecord):
        """Log the error using the appropriate log level"""
        if error_record.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(
                f"[{error_record.module}] {error_record.message}",
                {"error_id": error_record.error_id, "context": error_record.context}
            )
        elif error_record.severity == ErrorSeverity.ERROR:
            self.logger.error(
                f"[{error_record.module}] {error_record.message}",
                {"error_id": error_record.error_id, "context": error_record.context}
            )
        elif error_record.severity == ErrorSeverity.WARNING:
            self.logger.warning(
                f"[{error_record.module}] {error_record.message}",
                {"error_id": error_record.error_id, "context": error_record.context}
            )
        else:
            self.logger.info(
                f"[{error_record.module}] {error_record.message}",
                {"error_id": error_record.error_id, "context": error_record.context}
            )
    
    def _notify_error(self, error_record: ErrorRecord):
        """Notify error callbacks"""
        # Notify all error callbacks
        for callback in self._on_error:
            try:
                callback(error_record)
            except Exception as e:
                print(f"Error in error callback: {e}")
        
        # Notify critical error callbacks
        if error_record.severity == ErrorSeverity.CRITICAL:
            for callback in self._on_critical_error:
                try:
                    callback(error_record)
                except Exception as e:
                    print(f"Error in critical error callback: {e}")
    
    def _attempt_recovery(self, error_record: ErrorRecord):
        """Attempt to recover from the error"""
        # Get recovery actions for this error type
        actions = self._recovery_actions.get(error_record.error_type, [])
        
        for action in actions:
            try:
                action(error_record)
            except Exception as e:
                print(f"Recovery action failed: {e}")
    
    # Error Management
    
    def get_error(self, error_id: str) -> Optional[ErrorRecord]:
        """Get an error by ID"""
        return self._errors.get(error_id)
    
    def get_recent_errors(self, count: int = 10) -> List[ErrorRecord]:
        """Get recent errors"""
        return self._error_history[-count:]
    
    def get_errors_by_type(self, error_type: ErrorType) -> List[ErrorRecord]:
        """Get errors by type"""
        return [e for e in self._error_history if e.error_type == error_type]
    
    def get_errors_by_severity(self, severity: ErrorSeverity) -> List[ErrorRecord]:
        """Get errors by severity"""
        return [e for e in self._error_history if e.severity == severity]
    
    def get_errors_by_module(self, module: str) -> List[ErrorRecord]:
        """Get errors by module"""
        return [e for e in self._error_history if e.module == module]
    
    def get_unresolved_errors(self) -> List[ErrorRecord]:
        """Get all unresolved errors"""
        return [e for e in self._error_history if not e.resolved]
    
    def mark_resolved(self, error_id: str, resolution: str = "") -> bool:
        """Mark an error as resolved"""
        if error_id not in self._errors:
            return False
        
        error_record = self._errors[error_id]
        error_record.resolved = True
        error_record.resolution = resolution
        
        self._stats["unresolved"] -= 1
        
        return True
    
    def clear_errors(self) -> int:
        """Clear all errors"""
        count = len(self._errors)
        self._errors = {}
        self._error_history = []
        self._stats = {
            "total_errors": 0,
            "by_type": {},
            "by_severity": {},
            "by_module": {},
            "unresolved": 0
        }
        return count
    
    def clear_resolved_errors(self) -> int:
        """Clear all resolved errors"""
        count = 0
        
        # Remove resolved errors from history
        new_history = []
        for error_record in self._error_history:
            if not error_record.resolved:
                new_history.append(error_record)
            else:
                count += 1
        
        self._error_history = new_history
        
        # Update statistics
        self._stats["total_errors"] -= count
        self._stats["unresolved"] = 0
        
        return count
    
    # Recovery Actions
    
    def register_recovery_action(self, error_type: ErrorType, action: Callable):
        """
        Register a recovery action for a specific error type
        
        Args:
            error_type: The error type to handle
            action: Function to call when this error occurs
                  Parameters: (ErrorRecord)
        """
        if error_type not in self._recovery_actions:
            self._recovery_actions[error_type] = []
        
        self._recovery_actions[error_type].append(action)
    
    def unregister_recovery_action(self, error_type: ErrorType, action: Callable):
        """Unregister a recovery action"""
        if error_type in self._recovery_actions:
            if action in self._recovery_actions[error_type]:
                self._recovery_actions[error_type].remove(action)
    
    # Callbacks
    
    def on_error(self, callback: Callable[[ErrorRecord], None]):
        """
        Register callback for all errors
        
        Args:
            callback: Function to call when any error occurs
                   Parameters: (ErrorRecord)
        """
        self._on_error.append(callback)
    
    def on_critical_error(self, callback: Callable[[ErrorRecord], None]):
        """
        Register callback for critical errors only
        
        Args:
            callback: Function to call when a critical error occurs
                   Parameters: (ErrorRecord)
        """
        self._on_critical_error.append(callback)
    
    # Statistics
    
    def get_statistics(self) -> Dict:
        """Get error statistics"""
        return self._stats.copy()
    
    def get_error_summary(self) -> Dict:
        """Get a summary of recent errors"""
        summary = {
            "total": self._stats["total_errors"],
            "unresolved": self._stats["unresolved"],
            "by_type": self._stats["by_type"],
            "by_severity": self._stats["by_severity"],
            "recent": [e.to_dict() for e in self._error_history[-10:]]
        }
        
        return summary
    
    # Cleanup
    
    def cleanup(self):
        """Clean up resources"""
        self._errors = {}
        self._error_history = []
        self._on_error = []
        self._on_critical_error = []
        self._recovery_actions = {}
        self._stats = {
            "total_errors": 0,
            "by_type": {},
            "by_severity": {},
            "by_module": {},
            "unresolved": 0
        }
