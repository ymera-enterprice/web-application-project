"""
YMERA Enterprise - Structured Logger
Production-Ready Structured Logging Implementation - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path

# Third-party imports (alphabetical)
import structlog
from structlog.stdlib import LoggerFactory

# Local imports (alphabetical)
from .log_formatters import (
    JSONFormatter,
    ConsoleFormatter,
    ProductionFormatter,
    DevelopmentFormatter
)
from .log_handlers import (
    RotatingFileHandler,
    RemoteLogHandler,
    DatabaseLogHandler,
    ElasticsearchHandler
)

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(__name__)

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = "logs"
DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
DEFAULT_BACKUP_COUNT = 5
DEFAULT_LOG_FORMAT = "json"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class LoggerConfig:
    """Configuration dataclass for structured logger settings"""
    level: str = DEFAULT_LOG_LEVEL
    environment: str = "production"
    log_dir: str = DEFAULT_LOG_DIR
    enable_file_logging: bool = True
    enable_remote_logging: bool = False
    enable_database_logging: bool = False
    enable_console_logging: bool = True
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    backup_count: int = DEFAULT_BACKUP_COUNT
    log_format: str = DEFAULT_LOG_FORMAT
    include_caller_info: bool = True
    include_thread_info: bool = True
    include_process_info: bool = True
    correlation_id_header: str = "X-Correlation-ID"
    remote_log_endpoint: Optional[str] = None
    elasticsearch_url: Optional[str] = None
    database_connection_string: Optional[str] = None

@dataclass
class LogContext:
    """Context information for log entries"""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    environment: str = "production"
    service_name: str = "ymera"
    service_version: str = "4.0"

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class StructuredLogger:
    """
    Production-ready structured logging implementation with multiple handlers
    and comprehensive context management.
    """
    
    def __init__(self, **config_kwargs):
        """
        Initialize structured logger with configuration.
        
        Args:
            **config_kwargs: Configuration parameters
        """
        self.config = LoggerConfig(**config_kwargs)
        self._handlers = []
        self._processors = []
        self._context = LogContext(environment=self.config.environment)
        self._is_configured = False
        
        # Initialize logger
        self._initialize_logger()
    
    def _initialize_logger(self) -> None:
        """Initialize the structured logger with all components."""
        try:
            # Setup processors
            self._setup_processors()
            
            # Setup handlers
            self._setup_handlers()
            
            # Configure structlog
            self._configure_structlog()
            
            self._is_configured = True
            
            # Log successful initialization
            init_logger = structlog.get_logger("ymera.logging")
            init_logger.info(
                "Structured logger initialized successfully",
                config=self._get_safe_config(),
                handlers_count=len(self._handlers)
            )
            
        except Exception as e:
            # Fallback to basic logging for initialization errors
            fallback_logger = logging.getLogger("ymera.logging.fallback")
            fallback_logger.error(f"Failed to initialize structured logger: {str(e)}")
            raise
    
    def _setup_processors(self) -> None:
        """Setup structlog processors for log entry processing."""
        self._processors = [
            # Add correlation ID and context
            self._add_context_processor,
            
            # Add timestamp
            structlog.processors.TimeStamper(fmt="ISO"),
            
            # Add logger name
            structlog.stdlib.add_logger_name,
            
            # Add log level
            structlog.stdlib.add_log_level,
            
            # Add caller information if enabled
            self._add_caller_info if self.config.include_caller_info else None,
            
            # Add thread/process info if enabled
            self._add_thread_process_info if (
                self.config.include_thread_info or self.config.include_process_info
            ) else None,
            
            # Stack info processor for exceptions
            structlog.processors.StackInfoRenderer(),
            
            # Exception processor
            structlog.dev.set_exc_info,
            
            # Filter None values
            lambda _, __, event_dict: {k: v for k, v in event_dict.items() if v is not None}
        ]
        
        # Remove None processors
        self._processors = [p for p in self._processors if p is not None]
    
    def _setup_handlers(self) -> None:
        """Setup logging handlers based on configuration."""
        self._handlers = []
        
        # Console handler
        if self.config.enable_console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            if self.config.environment == "development":
                console_handler.setFormatter(DevelopmentFormatter())
            else:
                console_handler.setFormatter(ConsoleFormatter())
            
            console_handler.setLevel(getattr(logging, self.config.level.upper()))
            self._handlers.append(console_handler)
        
        # File handler
        if self.config.enable_file_logging:
            log_file_path = Path(self.config.log_dir) / "ymera.log"
            file_handler = RotatingFileHandler(
                filename=str(log_file_path),
                max_bytes=self.config.max_file_size,
                backup_count=self.config.backup_count
            )
            
            if self.config.log_format == "json":
                file_handler.setFormatter(JSONFormatter())
            else:
                file_handler.setFormatter(ProductionFormatter())
            
            file_handler.setLevel(getattr(logging, self.config.level.upper()))
            self._handlers.append(file_handler)
        
        # Remote handler
        if self.config.enable_remote_logging and self.config.remote_log_endpoint:
            remote_handler = RemoteLogHandler(
                endpoint=self.config.remote_log_endpoint,
                timeout=30,
                max_retries=3
            )
            remote_handler.setFormatter(JSONFormatter())
            remote_handler.setLevel(getattr(logging, self.config.level.upper()))
            self._handlers.append(remote_handler)
        
        # Elasticsearch handler
        if self.config.elasticsearch_url:
            es_handler = ElasticsearchHandler(
                elasticsearch_url=self.config.elasticsearch_url,
                index_prefix="ymera-logs"
            )
            es_handler.setFormatter(JSONFormatter())
            es_handler.setLevel(getattr(logging, self.config.level.upper()))
            self._handlers.append(es_handler)
        
        # Database handler
        if self.config.enable_database_logging and self.config.database_connection_string:
            db_handler = DatabaseLogHandler(
                connection_string=self.config.database_connection_string,
                table_name="log_entries"
            )
            db_handler.setFormatter(JSONFormatter())
            db_handler.setLevel(getattr(logging, self.config.level.upper()))
            self._handlers.append(db_handler)
    
    def _configure_structlog(self) -> None:
        """Configure structlog with processors and handlers."""
        structlog.configure(
            processors=self._processors + [
                # Final processor for stdlib compatibility
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def _add_context_processor(self, logger, method_name, event_dict):
        """Add context information to log entries."""
        event_dict.update({
            "correlation_id": self._context.correlation_id,
            "service_name": self._context.service_name,
            "service_version": self._context.service_version,
            "environment": self._context.environment,
        })
        
        # Add optional context
        if self._context.user_id:
            event_dict["user_id"] = self._context.user_id
        if self._context.session_id:
            event_dict["session_id"] = self._context.session_id
        if self._context.request_id:
            event_dict["request_id"] = self._context.request_id
        if self._context.operation:
            event_dict["operation"] = self._context.operation
        if self._context.component:
            event_dict["component"] = self._context.component
        
        return event_dict
    
    def _add_caller_info(self, logger, method_name, event_dict):
        """Add caller information to log entries."""
        import inspect
        
        # Get caller frame (skip logging framework frames)
        frame = inspect.currentframe()
        try:
            # Skip through logging framework frames
            for _ in range(10):  # Reasonable limit to prevent infinite loop
                frame = frame.f_back
                if frame is None:
                    break
                
                filename = frame.f_code.co_filename
                # Stop when we reach non-logging code
                if not any(logging_module in filename for logging_module in [
                    'logging', 'structlog', 'loguru'
                ]):
                    break
            
            if frame:
                event_dict.update({
                    "caller_module": frame.f_globals.get("__name__", "unknown"),
                    "caller_function": frame.f_code.co_name,
                    "caller_line": frame.f_lineno,
                    "caller_file": os.path.basename(frame.f_code.co_filename)
                })
        finally:
            del frame
        
        return event_dict
    
    def _add_thread_process_info(self, logger, method_name, event_dict):
        """Add thread and process information to log entries."""
        import threading
        
        if self.config.include_thread_info:
            event_dict.update({
                "thread_id": threading.get_ident(),
                "thread_name": threading.current_thread().name
            })
        
        if self.config.include_process_info:
            event_dict.update({
                "process_id": os.getpid(),
                "process_name": os.path.basename(sys.argv[0]) if sys.argv else "unknown"
            })
        
        return event_dict
    
    def get_handlers(self) -> List[logging.Handler]:
        """Get all configured logging handlers."""
        return self._handlers.copy()
    
    def get_config(self) -> Dict[str, Any]:
        """Get current logger configuration."""
        config_dict = {
            "level": self.config.level,
            "environment": self.config.environment,
            "log_dir": self.config.log_dir,
            "handlers_count": len(self._handlers),
            "processors_count": len(self._processors),
            "is_configured": self._is_configured,
            "context": {
                "correlation_id": self._context.correlation_id,
                "service_name": self._context.service_name,
                "service_version": self._context.service_version,
                "environment": self._context.environment
            }
        }
        
        return config_dict
    
    def _get_safe_config(self) -> Dict[str, Any]:
        """Get configuration with sensitive information removed."""
        safe_config = self.get_config()
        
        # Remove sensitive information
        sensitive_keys = [
            "database_connection_string",
            "remote_log_endpoint",
            "elasticsearch_url"
        ]
        
        for key in sensitive_keys:
            if key in safe_config:
                safe_config[key] = "***REDACTED***"
        
        return safe_config
    
    def set_context(self, **context_data) -> None:
        """
        Update logging context.
        
        Args:
            **context_data: Context data to update
        """
        for key, value in context_data.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
    
    def get_context(self) -> Dict[str, Any]:
        """Get current logging context."""
        return {
            "correlation_id": self._context.correlation_id,
            "user_id": self._context.user_id,
            "session_id": self._context.session_id,
            "request_id": self._context.request_id,
            "operation": self._context.operation,
            "component": self._context.component,
            "environment": self._context.environment,
            "service_name": self._context.service_name,
            "service_version": self._context.service_version
        }
    
    def clear_context(self) -> None:
        """Clear optional context information."""
        self._context.user_id = None
        self._context.session_id = None
        self._context.request_id = None
        self._context.operation = None
        self._context.component = None
        # Generate new correlation ID
        self._context.correlation_id = str(uuid.uuid4())
    
    def shutdown(self) -> None:
        """Gracefully shutdown logger and close all handlers."""
        try:
            # Close all handlers
            for handler in self._handlers:
                if hasattr(handler, 'close'):
                    handler.close()
            
            # Clear handlers list
            self._handlers.clear()
            
            # Reset configuration flag
            self._is_configured = False
            
            logger.info("Structured logger shutdown completed")
            
        except Exception as e:
            # Use fallback logging for shutdown errors
            fallback_logger = logging.getLogger("ymera.logging.fallback")
            fallback_logger.error(f"Error during logger shutdown: {str(e)}")

# ===============================================================================
# CONFIGURATION FUNCTIONS
# ===============================================================================

def configure_structlog(environment: str = "production") -> None:
    """
    Configure structlog with appropriate settings for the environment.
    
    Args:
        environment: Environment type (development, production, testing)
    """
    if environment == "development":
        # Development configuration with pretty output
        structlog.configure(
            processors=[
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.dev.ConsoleRenderer,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )
    else:
        # Production configuration handled by StructuredLogger
        pass

def create_performance_logger() -> structlog.BoundLogger:
    """Create a specialized performance logger."""
    perf_logger = structlog.get_logger("ymera.performance")
    return perf_logger

def create_security_logger() -> structlog.BoundLogger:
    """Create a specialized security logger."""
    security_logger = structlog.get_logger("ymera.security")
    return security_logger

def create_audit_logger() -> structlog.BoundLogger:
    """Create a specialized audit logger."""
    audit_logger = structlog.get_logger("ymera.audit")
    return audit_logger

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def async_log_with_context(
    logger: structlog.BoundLogger,
    level: str,
    message: str,
    **context
) -> None:
    """
    Asynchronously log a message with context.
    
    Args:
        logger: Structured logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        **context: Additional context information
    """
    log_method = getattr(logger, level.lower())
    
    # Add async context if available
    try:
        task = asyncio.current_task()
        if task:
            context["task_name"] = task.get_name()
            context["task_id"] = id(task)
    except RuntimeError:
        # No event loop running
        pass
    
    log_method(message, **context)

def sanitize_log_data(data: Any) -> Any:
    """
    Sanitize data for logging by removing sensitive information.
    
    Args:
        data: Data to sanitize
        
    Returns:
        Sanitized data safe for logging
    """
    if isinstance(data, dict):
        sanitized = {}
        sensitive_keys = {
            'password', 'token', 'secret', 'key', 'auth', 'credential',
            'authorization', 'x-api-key', 'cookie', 'session'
        }
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, (dict, list)):
                sanitized[key] = sanitize_log_data(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    
    else:
        return data

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "StructuredLogger",
    "LoggerConfig",
    "LogContext",
    "configure_structlog",
    "create_performance_logger",
    "create_security_logger",
    "create_audit_logger",
    "async_log_with_context",
    "sanitize_log_data"
]