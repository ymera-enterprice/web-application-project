"""
YMERA Enterprise - Log Formatters
Production-Ready Custom Log Formatting System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import json
import logging
import os
import socket
import sys
import traceback
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Third-party imports (alphabetical)
import structlog
from pythonjsonlogger import jsonlogger

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import sanitize_sensitive_data
from monitoring.performance_tracker import get_performance_context

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Formatter constants
MAX_MESSAGE_LENGTH = 32768
MAX_STACK_TRACE_LINES = 50
SENSITIVE_FIELDS = {'password', 'token', 'api_key', 'secret', 'authorization', 'cookie'}

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class LogContext:
    """Enhanced logging context with enterprise metadata"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = field(default="ymera")
    service_version: str = field(default="4.0")
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "production"))
    hostname: str = field(default_factory=socket.gethostname)
    process_id: int = field(default_factory=os.getpid)
    thread_id: int = field(default=0)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

@dataclass
class PerformanceMetrics:
    """Performance metrics for log enrichment"""
    duration_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    database_queries: Optional[int] = None
    cache_hits: Optional[int] = None
    cache_misses: Optional[int] = None

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseLogFormatter(logging.Formatter):
    """Abstract base class for all YMERA log formatters"""
    
    def __init__(self, include_context: bool = True, sanitize_data: bool = True):
        super().__init__()
        self.include_context = include_context
        self.sanitize_data = sanitize_data
        self.sensitive_fields = SENSITIVE_FIELDS.copy()
        self.hostname = socket.gethostname()
        self.service_name = getattr(settings, 'SERVICE_NAME', 'ymera')
        
    def add_sensitive_field(self, field: str) -> None:
        """Add field to sensitive data filter list"""
        self.sensitive_fields.add(field.lower())
    
    def _sanitize_record_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data from log record"""
        if not self.sanitize_data:
            return data
            
        return sanitize_sensitive_data(data, self.sensitive_fields)
    
    def _extract_context_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract contextual information from log record"""
        context = {}
        
        # Standard context fields
        if hasattr(record, 'correlation_id'):
            context['correlation_id'] = record.correlation_id
        if hasattr(record, 'user_id'):
            context['user_id'] = record.user_id
        if hasattr(record, 'session_id'):
            context['session_id'] = record.session_id
        if hasattr(record, 'request_id'):
            context['request_id'] = record.request_id
        if hasattr(record, 'trace_id'):
            context['trace_id'] = record.trace_id
        if hasattr(record, 'span_id'):
            context['span_id'] = record.span_id
            
        # Performance metrics
        perf_context = get_performance_context()
        if perf_context:
            context['performance'] = asdict(perf_context)
            
        return context
    
    def _format_exception_info(self, record: logging.LogRecord) -> Optional[Dict[str, Any]]:
        """Format exception information with stack trace"""
        if not record.exc_info:
            return None
            
        exc_type, exc_value, exc_traceback = record.exc_info
        
        # Extract stack trace
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        # Limit stack trace length
        if len(stack_trace) > MAX_STACK_TRACE_LINES:
            stack_trace = stack_trace[:MAX_STACK_TRACE_LINES]
            stack_trace.append("... (truncated)")
        
        return {
            'exception_type': exc_type.__name__ if exc_type else None,
            'exception_message': str(exc_value) if exc_value else None,
            'stack_trace': ''.join(stack_trace),
            'exception_module': getattr(exc_type, '__module__', None) if exc_type else None
        }

class JSONLogFormatter(BaseLogFormatter):
    """Production-ready JSON log formatter with comprehensive metadata"""
    
    def __init__(self, include_context: bool = True, sanitize_data: bool = True, 
                 pretty_print: bool = False):
        super().__init__(include_context, sanitize_data)
        self.pretty_print = pretty_print
        self.json_encoder = self._create_json_encoder()
    
    def _create_json_encoder(self) -> json.JSONEncoder:
        """Create custom JSON encoder for log serialization"""
        
        class LogJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, uuid.UUID):
                    return str(obj)
                elif isinstance(obj, Exception):
                    return {
                        'type': obj.__class__.__name__,
                        'message': str(obj),
                        'module': obj.__class__.__module__
                    }
                elif hasattr(obj, '__dict__'):
                    return obj.__dict__
                return super().default(obj)
        
        return LogJSONEncoder()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        try:
            # Base log data
            log_data = {
                'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage()[:MAX_MESSAGE_LENGTH],
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread': record.thread,
                'thread_name': record.threadName,
                'process': record.process,
                'service': {
                    'name': self.service_name,
                    'version': getattr(settings, 'SERVICE_VERSION', '4.0'),
                    'environment': getattr(settings, 'ENVIRONMENT', 'production'),
                    'hostname': self.hostname
                }
            }
            
            # Add contextual information
            if self.include_context:
                context_data = self._extract_context_data(record)
                if context_data:
                    log_data['context'] = context_data
            
            # Add exception information
            exception_info = self._format_exception_info(record)
            if exception_info:
                log_data['exception'] = exception_info
            
            # Add custom fields from record
            custom_fields = {}
            for key, value in record.__dict__.items():
                if key not in {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                             'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                             'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                             'exc_info', 'exc_text', 'stack_info', 'getMessage'}:
                    custom_fields[key] = value
            
            if custom_fields:
                log_data['fields'] = self._sanitize_record_data(custom_fields)
            
            # Serialize to JSON
            if self.pretty_print:
                return json.dumps(log_data, cls=self.json_encoder, indent=2, ensure_ascii=False)
            else:
                return json.dumps(log_data, cls=self.json_encoder, ensure_ascii=False, separators=(',', ':'))
                
        except Exception as e:
            # Fallback formatting if JSON serialization fails
            fallback_msg = f"LOG_FORMAT_ERROR: {str(e)} | Original: {record.getMessage()}"
            return json.dumps({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': 'ERROR',
                'logger': 'ymera.logging',
                'message': fallback_msg,
                'service': {'name': self.service_name, 'hostname': self.hostname}
            })

class StructuredTextFormatter(BaseLogFormatter):
    """Human-readable structured text formatter for development and debugging"""
    
    def __init__(self, include_context: bool = True, sanitize_data: bool = True,
                 use_colors: bool = True, max_width: int = 120):
        super().__init__(include_context, sanitize_data)
        self.use_colors = use_colors and self._supports_color()
        self.max_width = max_width
        self.colors = self._setup_colors()
    
    def _supports_color(self) -> bool:
        """Check if terminal supports color output"""
        return (
            hasattr(sys.stderr, "isatty") and 
            sys.stderr.isatty() and 
            os.environ.get("TERM") != "dumb"
        )
    
    def _setup_colors(self) -> Dict[str, str]:
        """Setup color codes for different log levels"""
        if not self.use_colors:
            return {level: '' for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'RESET']}
        
        return {
            'DEBUG': '\033[36m',      # Cyan
            'INFO': '\033[32m',       # Green
            'WARNING': '\033[33m',    # Yellow
            'ERROR': '\033[31m',      # Red
            'CRITICAL': '\033[35m',   # Magenta
            'RESET': '\033[0m'        # Reset
        }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as human-readable structured text"""
        try:
            # Color for log level
            level_color = self.colors.get(record.levelname, '')
            reset_color = self.colors['RESET']
            
            # Timestamp formatting
            timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Basic log line
            log_parts = [
                f"{timestamp_str}",
                f"{level_color}{record.levelname:8}{reset_color}",
                f"{record.name}:{record.lineno}",
                f"{record.getMessage()[:MAX_MESSAGE_LENGTH]}"
            ]
            
            base_line = " | ".join(log_parts)
            
            # Additional information sections
            sections = []
            
            # Context information
            if self.include_context:
                context_data = self._extract_context_data(record)
                if context_data:
                    context_str = self._format_context_section(context_data)
                    sections.append(f"Context: {context_str}")
            
            # Custom fields
            custom_fields = self._extract_custom_fields(record)
            if custom_fields:
                sanitized_fields = self._sanitize_record_data(custom_fields)
                fields_str = self._format_fields_section(sanitized_fields)
                sections.append(f"Fields: {fields_str}")
            
            # Exception information
            if record.exc_info:
                exception_info = self._format_exception_info(record)
                if exception_info:
                    sections.append(f"Exception: {exception_info['exception_type']}: {exception_info['exception_message']}")
                    if exception_info['stack_trace']:
                        sections.append(f"Stack Trace:\n{exception_info['stack_trace']}")
            
            # Combine all sections
            result_lines = [base_line]
            for section in sections:
                # Wrap long sections
                if len(section) > self.max_width:
                    wrapped_lines = self._wrap_text(section, self.max_width)
                    result_lines.extend(f"  {line}" for line in wrapped_lines)
                else:
                    result_lines.append(f"  {section}")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            # Fallback formatting
            return f"LOG_FORMAT_ERROR: {str(e)} | Original: {record.getMessage()}"
    
    def _extract_custom_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract custom fields from log record"""
        excluded_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'exc_info', 'exc_text',
            'stack_info', 'getMessage', 'correlation_id', 'user_id', 'session_id',
            'request_id', 'trace_id', 'span_id'
        }
        
        return {
            key: value for key, value in record.__dict__.items()
            if key not in excluded_fields
        }
    
    def _format_context_section(self, context: Dict[str, Any]) -> str:
        """Format context data for display"""
        context_parts = []
        
        for key, value in context.items():
            if isinstance(value, dict):
                # Nested context (like performance metrics)
                nested_parts = [f"{k}={v}" for k, v in value.items()]
                context_parts.append(f"{key}({', '.join(nested_parts)})")
            else:
                context_parts.append(f"{key}={value}")
        
        return ", ".join(context_parts)
    
    def _format_fields_section(self, fields: Dict[str, Any]) -> str:
        """Format custom fields for display"""
        field_parts = []
        
        for key, value in fields.items():
            if isinstance(value, (dict, list)):
                # Complex objects - show type and length
                if isinstance(value, dict):
                    field_parts.append(f"{key}=dict({len(value)} items)")
                else:
                    field_parts.append(f"{key}=list({len(value)} items)")
            else:
                # Simple values
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                field_parts.append(f"{key}={value_str}")
        
        return ", ".join(field_parts)
    
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to specified width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines

class MetricsLogFormatter(BaseLogFormatter):
    """Specialized formatter for metrics and performance logs"""
    
    def __init__(self, include_context: bool = True, sanitize_data: bool = True):
        super().__init__(include_context, sanitize_data)
        
    def format(self, record: logging.LogRecord) -> str:
        """Format metrics-focused log record"""
        try:
            # Extract performance metrics
            performance_data = {}
            
            # Check for performance context
            perf_context = get_performance_context()
            if perf_context:
                performance_data.update(asdict(perf_context))
            
            # Extract metrics from record
            metrics_fields = {}
            for key, value in record.__dict__.items():
                if key.endswith(('_count', '_duration', '_size', '_rate', '_percent', '_ms', '_mb')):
                    metrics_fields[key] = value
            
            # Base metrics log structure
            metrics_log = {
                'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                'event_type': 'metrics',
                'service': self.service_name,
                'logger': record.name,
                'level': record.levelname,
                'message': record.getMessage(),
                'metrics': {
                    **performance_data,
                    **metrics_fields
                }
            }
            
            # Add context if available
            if self.include_context:
                context_data = self._extract_context_data(record)
                if context_data:
                    metrics_log['context'] = context_data
            
            return json.dumps(metrics_log, ensure_ascii=False, separators=(',', ':'))
            
        except Exception as e:
            # Fallback
            return f"METRICS_FORMAT_ERROR: {str(e)} | Original: {record.getMessage()}"

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_formatter(formatter_type: str, **kwargs) -> logging.Formatter:
    """Factory function to create log formatters"""
    
    formatter_classes = {
        'json': JSONLogFormatter,
        'structured': StructuredTextFormatter,
        'metrics': MetricsLogFormatter
    }
    
    formatter_class = formatter_classes.get(formatter_type.lower())
    if not formatter_class:
        raise ValueError(f"Unknown formatter type: {formatter_type}")
    
    return formatter_class(**kwargs)

def get_default_formatter() -> logging.Formatter:
    """Get default formatter based on environment"""
    environment = getattr(settings, 'ENVIRONMENT', 'production').lower()
    
    if environment == 'development':
        return StructuredTextFormatter(use_colors=True)
    else:
        return JSONLogFormatter(pretty_print=False)

def configure_structlog_processors() -> List[Callable]:
    """Configure structlog processors for consistent formatting"""
    
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add JSON processor for production
    environment = getattr(settings, 'ENVIRONMENT', 'production').lower()
    if environment == 'production':
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    return processors

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

def initialize_formatters() -> Dict[str, logging.Formatter]:
    """Initialize all available formatters"""
    return {
        'json': JSONLogFormatter(),
        'json_pretty': JSONLogFormatter(pretty_print=True),
        'structured': StructuredTextFormatter(),
        'structured_no_color': StructuredTextFormatter(use_colors=False),
        'metrics': MetricsLogFormatter(),
        'default': get_default_formatter()
    }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "BaseLogFormatter",
    "JSONLogFormatter", 
    "StructuredTextFormatter",
    "MetricsLogFormatter",
    "LogContext",
    "PerformanceMetrics",
    "create_formatter",
    "get_default_formatter",
    "configure_structlog_processors",
    "initialize_formatters"
]