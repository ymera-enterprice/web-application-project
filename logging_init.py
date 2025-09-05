"""
YMERA Enterprise - Logging Module
Production-Ready Structured Logging System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import logging
import os
import sys
from typing import Dict, Any, Optional

# Third-party imports (alphabetical)
import structlog

# Local imports (alphabetical)
from .structured_logger import StructuredLogger, configure_structlog
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

# Global logger instance
_logger_instance: Optional[StructuredLogger] = None

# ===============================================================================
# LOGGING INITIALIZATION
# ===============================================================================

def get_logger(name: str = "ymera") -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name, typically module name
        
    Returns:
        Configured structlog.BoundLogger instance
        
    Example:
        >>> logger = get_logger("ymera.agents")
        >>> logger.info("Agent started", agent_id="agent_001")
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = StructuredLogger()
        configure_structlog()
    
    return structlog.get_logger(name)

def configure_logging(
    level: str = "INFO",
    environment: str = "production",
    enable_file_logging: bool = True,
    enable_remote_logging: bool = False,
    enable_database_logging: bool = False,
    log_dir: str = "logs",
    **kwargs
) -> None:
    """
    Configure the logging system for the entire application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        environment: Environment type (development, production, testing)
        enable_file_logging: Enable file-based logging
        enable_remote_logging: Enable remote logging (e.g., Elasticsearch)
        enable_database_logging: Enable database logging
        log_dir: Directory for log files
        **kwargs: Additional configuration options
    """
    global _logger_instance
    
    # Create logs directory if it doesn't exist
    if enable_file_logging:
        os.makedirs(log_dir, exist_ok=True)
    
    # Initialize structured logger
    _logger_instance = StructuredLogger(
        level=level,
        environment=environment,
        log_dir=log_dir,
        enable_file_logging=enable_file_logging,
        enable_remote_logging=enable_remote_logging,
        enable_database_logging=enable_database_logging,
        **kwargs
    )
    
    # Configure structlog
    configure_structlog(environment=environment)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add configured handlers
    for handler in _logger_instance.get_handlers():
        root_logger.addHandler(handler)

def get_logger_config() -> Dict[str, Any]:
    """
    Get current logger configuration.
    
    Returns:
        Dictionary containing current logging configuration
    """
    global _logger_instance
    
    if _logger_instance is None:
        return {"status": "not_configured"}
    
    return _logger_instance.get_config()

def shutdown_logging() -> None:
    """
    Gracefully shutdown logging system and close all handlers.
    """
    global _logger_instance
    
    if _logger_instance is not None:
        _logger_instance.shutdown()
        _logger_instance = None
    
    # Shutdown standard logging
    logging.shutdown()

# ===============================================================================
# CONTEXT MANAGERS
# ===============================================================================

class LoggingContext:
    """Context manager for temporary logging configuration changes."""
    
    def __init__(self, **context_data):
        self.context_data = context_data
        self.original_context = {}
    
    def __enter__(self):
        # Store original context and apply new context
        self.logger = get_logger()
        return self.logger.bind(**self.context_data)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Context automatically cleaned up by structlog
        pass

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def log_exception(
    logger: structlog.BoundLogger,
    exception: Exception,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an exception with full context and traceback.
    
    Args:
        logger: Structured logger instance
        exception: Exception to log
        context: Additional context information
    """
    import traceback
    
    context = context or {}
    logger.error(
        "Exception occurred",
        exception_type=exception.__class__.__name__,
        exception_message=str(exception),
        traceback=traceback.format_exc(),
        **context
    )

def log_performance(
    logger: structlog.BoundLogger,
    operation: str,
    duration: float,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log performance metrics for an operation.
    
    Args:
        logger: Structured logger instance
        operation: Operation name
        duration: Operation duration in seconds
        context: Additional context information
    """
    context = context or {}
    logger.info(
        "Performance metric",
        operation=operation,
        duration_seconds=duration,
        **context
    )

def create_audit_logger(name: str = "audit") -> structlog.BoundLogger:
    """
    Create a specialized audit logger.
    
    Args:
        name: Audit logger name
        
    Returns:
        Configured audit logger
    """
    return get_logger(f"ymera.audit.{name}")

# ===============================================================================
# DECORATORS
# ===============================================================================

def log_function_call(logger_name: Optional[str] = None):
    """
    Decorator to log function calls with parameters and results.
    
    Args:
        logger_name: Optional logger name override
    """
    def decorator(func):
        import functools
        import time
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or f"ymera.{func.__module__}")
            start_time = time.time()
            
            logger.debug(
                "Function call started",
                function=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.debug(
                    "Function call completed",
                    function=func.__name__,
                    duration_seconds=duration,
                    success=True
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    "Function call failed",
                    function=func.__name__,
                    duration_seconds=duration,
                    error=str(e),
                    success=False
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or f"ymera.{func.__module__}")
            start_time = time.time()
            
            logger.debug(
                "Function call started",
                function=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.debug(
                    "Function call completed",
                    function=func.__name__,
                    duration_seconds=duration,
                    success=True
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    "Function call failed",
                    function=func.__name__,
                    duration_seconds=duration,
                    error=str(e),
                    success=False
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

# Initialize default logging configuration
def _initialize_default_logging():
    """Initialize default logging configuration if not already configured."""
    if _logger_instance is None:
        environment = os.getenv("YMERA_ENVIRONMENT", "production")
        log_level = os.getenv("YMERA_LOG_LEVEL", "INFO")
        
        configure_logging(
            level=log_level,
            environment=environment,
            enable_file_logging=True,
            enable_remote_logging=os.getenv("YMERA_ENABLE_REMOTE_LOGGING", "false").lower() == "true",
            enable_database_logging=os.getenv("YMERA_ENABLE_DATABASE_LOGGING", "false").lower() == "true"
        )

# Auto-initialize with environment variables
_initialize_default_logging()

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Main functions
    "get_logger",
    "configure_logging",
    "get_logger_config",
    "shutdown_logging",
    
    # Context managers
    "LoggingContext",
    
    # Utility functions
    "log_exception",
    "log_performance",
    "create_audit_logger",
    
    # Decorators
    "log_function_call",
    
    # Classes and handlers (re-exported for convenience)
    "StructuredLogger",
    "JSONFormatter",
    "ConsoleFormatter",
    "ProductionFormatter",
    "DevelopmentFormatter",
    "RotatingFileHandler",
    "RemoteLogHandler",
    "DatabaseLogHandler",
    "ElasticsearchHandler"
]