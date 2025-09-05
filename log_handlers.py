"""
YMERA Enterprise - Log Handlers
Production-Ready File/Remote Log Handler System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import gzip
import json
import logging
import logging.handlers
import os
import socket
import ssl
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Third-party imports (alphabetical)
import aiofiles
import aiohttp
import structlog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import generate_service_token

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Handler constants
MAX_LOG_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_BACKUP_COUNT = 10
BATCH_SIZE = 1000
FLUSH_INTERVAL = 5.0
CONNECTION_TIMEOUT = 30.0
RETRY_BACKOFF_FACTOR = 2.0
MAX_RETRY_ATTEMPTS = 3
COMPRESSION_LEVEL = 6

# Buffer constants
MAX_BUFFER_SIZE = 10000
BUFFER_FLUSH_THRESHOLD = 0.8
EMERGENCY_FLUSH_SIZE = 50000

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class HandlerConfig:
    """Configuration for log handlers"""
    name: str
    level: int = logging.INFO
    formatter: Optional[str] = None
    enabled: bool = True
    buffer_size: int = 1000
    flush_interval: float = 5.0
    compression_enabled: bool = False
    encryption_enabled: bool = False
    retry_attempts: int = 3
    timeout: float = 30.0

@dataclass
class FileHandlerConfig(HandlerConfig):
    """Configuration for file-based handlers"""
    file_path: Path = field(default_factory=lambda: Path("logs/ymera.log"))
    max_file_size: int = MAX_LOG_FILE_SIZE
    backup_count: int = MAX_BACKUP_COUNT
    rotation_time: str = "midnight"
    create_directories: bool = True

@dataclass
class RemoteHandlerConfig(HandlerConfig):
    """Configuration for remote log handlers"""
    endpoint_url: str = ""
    auth_token: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    verify_ssl: bool = True
    connection_pool_size: int = 10
    batch_size: int = BATCH_SIZE

@dataclass
class LogEntry:
    """Structured log entry for processing"""
    record: logging.LogRecord
    formatted_message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseLogHandler(logging.Handler):
    """Enhanced base class for all YMERA log handlers"""
    
    def __init__(self, config: HandlerConfig):
        super().__init__(level=config.level)
        self.config = config
        self.handler_logger = logger.bind(handler=config.name)
        self._buffer: List[LogEntry] = []
        self._buffer_lock = threading.RLock()
        self._last_flush = time.time()
        self._shutdown_event = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None
        self._stats = {
            'records_processed': 0,
            'records_failed': 0,
            'flush_count': 0,
            'last_flush_time': None,
            'buffer_overflows': 0
        }
        
        if config.enabled:
            self._start_flush_thread()
    
    def _start_flush_thread(self) -> None:
        """Start background flush thread"""
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            name=f"LogFlush-{self.config.name}",
            daemon=True
        )
        self._flush_thread.start()
        self.handler_logger.info("Flush thread started")
    
    def _flush_loop(self) -> None:
        """Background thread for periodic flushing"""
        while not self._shutdown_event.is_set():
            try:
                # Wait for flush interval or shutdown
                if self._shutdown_event.wait(self.config.flush_interval):
                    break
                
                # Check if flush is needed
                current_time = time.time()
                with self._buffer_lock:
                    buffer_size = len(self._buffer)
                    time_since_flush = current_time - self._last_flush
                
                if (buffer_size > 0 and 
                    (time_since_flush >= self.config.flush_interval or 
                     buffer_size >= self.config.buffer_size * BUFFER_FLUSH_THRESHOLD)):
                    self._flush_buffer()
                    
            except Exception as e:
                self.handler_logger.error("Error in flush loop", error=str(e))
                time.sleep(1.0)  # Brief pause on error
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record"""
        if not self.config.enabled:
            return
            
        try:
            # Format the record
            formatted_message = self.format(record)
            
            # Create log entry
            log_entry = LogEntry(
                record=record,
                formatted_message=formatted_message
            )
            
            # Add to buffer
            with self._buffer_lock:
                # Check for buffer overflow
                if len(self._buffer) >= EMERGENCY_FLUSH_SIZE:
                    self._stats['buffer_overflows'] += 1
                    # Emergency flush - remove oldest entries
                    self._buffer = self._buffer[-self.config.buffer_size:]
                    self.handler_logger.warning(
                        "Buffer overflow, oldest entries dropped",
                        buffer_size=len(self._buffer)
                    )
                
                self._buffer.append(log_entry)
                self._stats['records_processed'] += 1
                
                # Immediate flush for critical errors
                if record.levelno >= logging.CRITICAL:
                    self._flush_buffer_unsafe()
                    
        except Exception as e:
            self.handler_logger.error("Failed to emit log record", error=str(e))
            self._stats['records_failed'] += 1
    
    def _flush_buffer(self) -> None:
        """Flush buffer with thread safety"""
        with self._buffer_lock:
            self._flush_buffer_unsafe()
    
    def _flush_buffer_unsafe(self) -> None:
        """Flush buffer without acquiring lock (caller must hold lock)"""
        if not self._buffer:
            return
            
        try:
            # Get entries to flush
            entries_to_flush = self._buffer.copy()
            self._buffer.clear()
            
            # Process entries
            self._process_log_entries(entries_to_flush)
            
            # Update stats
            self._stats['flush_count'] += 1
            self._stats['last_flush_time'] = datetime.now(timezone.utc)
            self._last_flush = time.time()
            
            self.handler_logger.debug(
                "Buffer flushed",
                entries_count=len(entries_to_flush),
                buffer_remaining=len(self._buffer)
            )
            
        except Exception as e:
            self.handler_logger.error("Failed to flush buffer", error=str(e))
            # Re-add failed entries to buffer for retry
            with self._buffer_lock:
                for entry in entries_to_flush:
                    entry.retry_count += 1
                    if entry.retry_count <= self.config.retry_attempts:
                        self._buffer.append(entry)
            
            self._stats['records_failed'] += len(entries_to_flush)
    
    def _process_log_entries(self, entries: List[LogEntry]) -> None:
        """Process log entries - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement _process_log_entries")
    
    def flush(self) -> None:
        """Force flush of buffered records"""
        self._flush_buffer()
        super().flush()
    
    def close(self) -> None:
        """Close handler and cleanup resources"""
        self.handler_logger.info("Closing handler")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for flush thread to complete
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=10.0)
        
        # Final flush
        self._flush_buffer()
        
        super().close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        with self._buffer_lock:
            buffer_size = len(self._buffer)
        
        return {
            **self._stats,
            'current_buffer_size': buffer_size,
            'handler_name': self.config.name,
            'handler_enabled': self.config.enabled,
            'uptime_seconds': time.time() - self._last_flush
        }

class EnhancedRotatingFileHandler(BaseLogHandler):
    """Production-ready rotating file handler with compression and encryption"""
    
    def __init__(self, config: FileHandlerConfig):
        super().__init__(config)
        self.file_config = config
        self._file_handler: Optional[logging.handlers.RotatingFileHandler] = None
        self._compression_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="LogCompress")
        self._setup_file_handler()
    
    def _setup_file_handler(self) -> None:
        """Setup internal file handler with rotation"""
        try:
            # Create directories if needed
            if self.file_config.create_directories:
                self.file_config.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create rotating file handler
            self._file_handler = logging.handlers.RotatingFileHandler(
                filename=str(self.file_config.file_path),
                maxBytes=self.file_config.max_file_size,
                backupCount=self.file_config.backup_count,
                encoding='utf-8'
            )
            
            # Override rotation behavior for compression
            if self.file_config.compression_enabled:
                self._file_handler.rotator = self._compress_rotated_file
            
            self.handler_logger.info(
                "File handler initialized",
                file_path=str(self.file_config.file_path),
                max_size=self.file_config.max_file_size,
                backup_count=self.file_config.backup_count
            )
            
        except Exception as e:
            self.handler_logger.error("Failed to setup file handler", error=str(e))
            raise
    
    def _compress_rotated_file(self, source: str, dest: str) -> None:
        """Compress rotated log file"""
        def compress_file():
            try:
                with open(source, 'rb') as f_in:
                    with gzip.open(f"{dest}.gz", 'wb', compresslevel=COMPRESSION_LEVEL) as f_out:
                        f_out.writelines(f_in)
                
                # Remove original file
                os.remove(source)
                
                self.handler_logger.debug(
                    "Log file compressed",
                    source=source,
                    dest=f"{dest}.gz"
                )
                
            except Exception as e:
                self.handler_logger.error(
                    "Failed to compress log file",
                    source=source,
                    dest=dest,
                    error=str(e)
                )
                # Fallback to normal rotation
                try:
                    os.rename(source, dest)
                except OSError:
                    pass
        
        # Submit compression task to executor
        self._compression_executor.submit(compress_file)
    
    def _process_log_entries(self, entries: List[LogEntry]) -> None:
        """Write log entries to file"""
        if not self._file_handler:
            raise RuntimeError("File handler not initialized")
        
        try:
            for entry in entries:
                # Encrypt message if required
                message = entry.formatted_message
                if self.file_config.encryption_enabled:
                    message = encrypt_data(message)
                
                # Create a new record for the file handler
                file_record = logging.LogRecord(
                    name=entry.record.name,
                    level=entry.record.levelno,
                    pathname=entry.record.pathname,
                    lineno=entry.record.lineno,
                    msg=message,
                    args=(),
                    exc_info=None
                )
                file_record.created = entry.record.created
                
                # Write to file
                self._file_handler.emit(file_record)
            
            # Ensure data is written to disk
            self._file_handler.flush()
            
        except Exception as e:
            self.handler_logger.error("Failed to write entries to file", error=str(e))
            raise
    
    def close(self) -> None:
        """Close file handler and cleanup"""
        super().close()
        
        if self._file_handler:
            self._file_handler.close()
        
        # Shutdown compression executor
        self._compression_executor.shutdown(wait=True)

class TimedRotatingFileHandler(BaseLogHandler):
    """Time-based rotating file handler with advanced features"""
    
    def __init__(self, config: FileHandlerConfig):
        super().__init__(config)
        self.file_config = config
        self._file_handler: Optional[logging.handlers.TimedRotatingFileHandler] = None
        self._setup_timed_handler()
    
    def _setup_timed_handler(self) -> None:
        """Setup time-based rotating file handler"""
        try:
            # Create directories if needed
            if self.file_config.create_directories:
                self.file_config.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Parse rotation time
            when, interval = self._parse_rotation_time(self.file_config.rotation_time)
            
            # Create timed rotating handler
            self._file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=str(self.file_config.file_path),
                when=when,
                interval=interval,
                backupCount=self.file_config.backup_count,
                encoding='utf-8',
                utc=True
            )
            
            # Add compression if enabled
            if self.file_config.compression_enabled:
                self._file_handler.rotator = self._compress_rotated_file
                self._file_handler.namer = lambda name: f"{name}.gz"
            
            self.handler_logger.info(
                "Timed file handler initialized",
                file_path=str(self.file_config.file_path),
                rotation_time=self.file_config.rotation_time,
                backup_count=self.file_config.backup_count
            )
            
        except Exception as e:
            self.handler_logger.error("Failed to setup timed handler", error=str(e))
            raise
    
    def _parse_rotation_time(self, rotation_time: str) -> tuple:
        """Parse rotation time specification"""
        time_specs = {
            'midnight': ('midnight', 1),
            'hourly': ('H', 1),
            'daily': ('D', 1),
            'weekly': ('W0', 1),  # Monday
            'monthly': ('midnight', 30)  # Approximate
        }
        
        spec = time_specs.get(rotation_time.lower())
        if not spec:
            # Try to parse custom format like "H:2" or "D:1"
            if ':' in rotation_time:
                when, interval_str = rotation_time.split(':', 1)
                try:
                    interval = int(interval_str)
                    return (when.upper(), interval)
                except ValueError:
                    pass
            
            # Default to daily
            return ('D', 1)
        
        return spec
    
    def _compress_rotated_file(self, source: str, dest: str) -> None:
        """Compress rotated log file"""
        try:
            with open(source, 'rb') as f_in:
                with gzip.open(dest, 'wb', compresslevel=COMPRESSION_LEVEL) as f_out:
                    f_out.writelines(f_in)
            
            # Remove original
            os.remove(source)
            
            self.handler_logger.debug("Timed log file compressed", source=source, dest=dest)
            
        except Exception as e:
            self.handler_logger.error("Failed to compress timed log file", error=str(e))
            # Fallback
            try:
                os.rename(source, dest.replace('.gz', ''))
            except OSError:
                pass
    
    def _process_log_entries(self, entries: List[LogEntry]) -> None:
        """Write log entries to timed rotating file"""
        if not self._file_handler:
            raise RuntimeError("Timed file handler not initialized")
        
        try:
            for entry in entries:
                # Process entry similar to rotating handler
                message = entry.formatted_message
                if self.file_config.encryption_enabled:
                    message = encrypt_data(message)
                
                file_record = logging.LogRecord(
                    name=entry.record.name,
                    level=entry.record.levelno,
                    pathname=entry.record.pathname,
                    lineno=entry.record.lineno,
                    msg=message,
                    args=(),
                    exc_info=None
                )
                file_record.created = entry.record.created
                
                self._file_handler.emit(file_record)
            
            self._file_handler.flush()
            
        except Exception as e:
            self.handler_logger.error("Failed to write entries to timed file", error=str(e))
            raise
    
    def close(self) -> None:
        """Close timed file handler"""
        super().close()
        
        if self._file_handler:
            self._file_handler.close()

class RemoteHTTPHandler(BaseLogHandler):
    """High-performance remote HTTP log handler with batching"""
    
    def __init__(self, config: RemoteHandlerConfig):
        super().__init__(config)
        self.remote_config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session_lock = threading.Lock()
        self._setup_session()
    
    def _setup_session(self) -> None:
        """Setup HTTP session for remote logging"""
        try:
            # Validate endpoint URL
            parsed_url = urlparse(self.remote_config.endpoint_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError(f"Invalid endpoint URL: {self.remote_config.endpoint_url}")
            
            # Setup SSL context
            ssl_context = None
            if parsed_url.scheme == 'https':
                ssl_context = ssl.create_default_context()
                if not self.remote_config.verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create connector with connection pooling
            connector = aiohttp.TCPConnector(
                limit=self.remote_config.connection_pool_size,
                limit_per_host=self.remote_config.connection_pool_size,
                ttl_dns_cache=300,
                use_dns_cache=True,
                ssl=ssl_context
            )
            
            # Setup timeout
            timeout = aiohttp.ClientTimeout(
                total=self.remote_config.timeout,
                connect=self.remote_config.timeout / 3
            )
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': f'YMERA-LogHandler/4.0',
                **self.remote_config.headers
            }
            
            # Add authentication if provided
            if self.remote_config.auth_token:
                headers['Authorization'] = f'Bearer {self.remote_config.auth_token}'
            
            self.handler_logger.info(
                "Remote handler configured",
                endpoint=self.remote_config.endpoint_url,
                batch_size=self.remote_config.batch_size,
                pool_size=self.remote_config.connection_pool_size
            )
            
        except Exception as e:
            self.handler_logger.error("Failed to setup remote session", error=str(e))
            raise
    
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        with self._session_lock:
            if self._session is None or self._session.closed:
                # Get or create event loop
                try:
                    self._loop = asyncio.get_event_loop()
                except RuntimeError:
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
                
                # Create session
                connector = aiohttp.TCPConnector(
                    limit=self.remote_config.connection_pool_size,
                    limit_per_host=self.remote_config.connection_pool_size
                )
                
                timeout = aiohttp.ClientTimeout(total=self.remote_config.timeout)
                
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    loop=self._loop
                )
        
        return self._session
    
    def _process_log_entries(self, entries: List[LogEntry]) -> None:
        """Send log entries to remote endpoint"""
        if not entries:
            return
        
        # Process in batches
        batch_size = self.remote_config.batch_size
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            self._send_batch(batch)
    
    def _send_batch(self, batch: List[LogEntry]) -> None:
        """Send a batch of log entries"""
        try:
            # Prepare batch payload
            log_records = []
            for entry in batch:
                log_data = {
                    'timestamp': entry.timestamp.isoformat(),
                    'level': entry.record.levelname,
                    'logger': entry.record.name,
                    'message': entry.formatted_message,
                    'module': entry.record.module,
                    'function': entry.record.funcName,
                    'line': entry.record.lineno,
                    'entry_id': entry.entry_id,
                    'service': self.remote_config.name
                }
                
                # Add exception info if present
                if entry.record.exc_info:
                    log_data['exception'] = {
                        'type': entry.record.exc_info[0].__name__,
                        'message': str(entry.record.exc_info[1])
                    }
                
                log_records.append(log_data)
            
            payload = {
                'batch_id': str(uuid.uuid4()),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'service': self.remote_config.name,
                'records': log_records
            }
            
            # Send synchronously (handler runs in separate thread)
            self._send_sync(payload)
            
        except Exception as e:
            self.handler_logger.error("Failed to send log batch", error=str(e))
            raise
    
    def _send_sync(self, payload: Dict[str, Any]) -> None:
        """Send payload synchronously"""
        try:
            # Create new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async send
            loop.run_until_complete(self._send_async(payload))
            
        except Exception as e:
            self.handler_logger.error("Sync send failed", error=str(e))
            raise
    
    async def _send_async(self, payload: Dict[str, Any]) -> None:
        """Send payload asynchronously"""
        session = self._get_session()
        
        retry_count = 0
        last_error = None
        
        while retry_count <= self.remote_config.retry_attempts:
            try:
                async with session.post(
                    self.remote_config.endpoint_url,
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.remote_config.auth_token}' if self.remote_config.auth_token else None,
                        **self.remote_config.headers
                    }
                ) as response:
                    
                    if response.status == 200:
                        self.handler_logger.debug(
                            "Log batch sent successfully",
                            batch_size=len(payload['records']),
                            status=response.status
                        )
                        return
                    else:
                        error_text = await response.text()
                        raise aiohttp.ClientError(
                            f"HTTP {response.status}: {error_text}"
                        )
                        
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count <= self.remote_config.retry_attempts:
                    wait_time = RETRY_BACKOFF_FACTOR ** retry_count
                    self.handler_logger.warning(
                        "Retrying log send",
                        retry=retry_count,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.handler_logger.error(
                        "Failed to send log batch after retries",
                        retries=retry_count,
                        error=str(last_error)
                    )
                    raise last_error
    
    def close(self) -> None:
        """Close remote handler and cleanup"""
        super().close()
        
        with self._session_lock:
            if self._session and not self._session.closed:
                if self._loop and not self._loop.is_closed():
                    self._loop.run_until_complete(self._session.close())

class SyslogHandler(BaseLogHandler):
    """Enterprise syslog handler with RFC5424 compliance"""
    
    def __init__(self, config: RemoteHandlerConfig, facility: int = logging.handlers.SysLogHandler.LOG_USER):
        super().__init__(config)
        self.syslog_config = config
        self.facility = facility
        self._syslog_handler: Optional[logging.handlers.SysLogHandler] = None
        self._setup_syslog()
    
    def _setup_syslog(self) -> None:
        """Setup syslog handler connection"""
        try:
            # Parse syslog address
            parsed_url = urlparse(self.syslog_config.endpoint_url)
            
            if parsed_url.scheme == 'udp':
                address = (parsed_url.hostname, parsed_url.port or 514)
                socktype = socket.SOCK_DGRAM
            elif parsed_url.scheme == 'tcp':
                address = (parsed_url.hostname, parsed_url.port or 514)
                socktype = socket.SOCK_STREAM
            else:
                # Unix socket
                address = parsed_url.path or '/dev/log'
                socktype = socket.SOCK_DGRAM
            
            self._syslog_handler = logging.handlers.SysLogHandler(
                address=address,
                facility=self.facility,
                socktype=socktype
            )
            
            self.handler_logger.info(
                "Syslog handler initialized",
                address=address,
                facility=self.facility,
                socktype=socktype
            )
            
        except Exception as e:
            self.handler_logger.error("Failed to setup syslog handler", error=str(e))
            raise
    
    def _process_log_entries(self, entries: List[LogEntry]) -> None:
        """Send entries to syslog"""
        if not self._syslog_handler:
            raise RuntimeError("Syslog handler not initialized")
        
        try:
            for entry in entries:
                # Create syslog record
                syslog_record = logging.LogRecord(
                    name=entry.record.name,
                    level=entry.record.levelno,
                    pathname=entry.record.pathname,
                    lineno=entry.record.lineno,
                    msg=entry.formatted_message,
                    args=(),
                    exc_info=None
                )
                syslog_record.created = entry.record.created
                
                self._syslog_handler.emit(syslog_record)
            
        except Exception as e:
            self.handler_logger.error("Failed to send syslog entries", error=str(e))
            raise
    
    def close(self) -> None:
        """Close syslog handler"""
        super().close()
        
        if self._syslog_handler:
            self._syslog_handler.close()

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_file_handler(config: FileHandlerConfig, rotation_type: str = "size") -> BaseLogHandler:
    """Factory function to create file handlers"""
    
    if rotation_type.lower() == "time":
        return TimedRotatingFileHandler(config)
    else:
        return EnhancedRotatingFileHandler(config)

def create_remote_handler(config: RemoteHandlerConfig, handler_type: str = "http") -> BaseLogHandler:
    """Factory function to create remote handlers"""
    
    handler_types = {
        'http': RemoteHTTPHandler,
        'https': RemoteHTTPHandler,
        'syslog': SyslogHandler
    }
    
    handler_class = handler_types.get(handler_type.lower())
    if not handler_class:
        raise ValueError(f"Unknown remote handler type: {handler_type}")
    
    return handler_class(config)

def create_handler_from_config(handler_config: Dict[str, Any]) -> BaseLogHandler:
    """Create handler from configuration dictionary"""
    
    handler_type = handler_config.get('type', 'file').lower()
    
    if handler_type in ['file', 'rotating_file']:
        config = FileHandlerConfig(**handler_config)
        return EnhancedRotatingFileHandler(config)
    
    elif handler_type == 'timed_rotating_file':
        config = FileHandlerConfig(**handler_config)
        return TimedRotatingFileHandler(config)
    
    elif handler_type in ['http', 'https']:
        config = RemoteHandlerConfig(**handler_config)
        return RemoteHTTPHandler(config)
    
    elif handler_type == 'syslog':
        config = RemoteHandlerConfig(**handler_config)
        return SyslogHandler(config)
    
    else:
        raise ValueError(f"Unknown handler type: {handler_type}")

@track_performance
async def health_check_handlers(handlers: List[BaseLogHandler]) -> Dict[str, Any]:
    """Perform health check on all handlers"""
    
    health_status = {
        'overall_status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'handlers': {}
    }
    
    unhealthy_count = 0
    
    for handler in handlers:
        try:
            stats = handler.get_stats()
            
            # Determine handler health
            handler_healthy = (
                handler.config.enabled and
                stats['records_failed'] < stats['records_processed'] * 0.1  # Less than 10% failure rate
            )
            
            if not handler_healthy:
                unhealthy_count += 1
            
            health_status['handlers'][handler.config.name] = {
                'status': 'healthy' if handler_healthy else 'unhealthy',
                'stats': stats
            }
            
        except Exception as e:
            unhealthy_count += 1
            health_status['handlers'][handler.config.name] = {
                'status': 'error',
                'error': str(e)
            }
    
    # Set overall status
    if unhealthy_count > 0:
        if unhealthy_count == len(handlers):
            health_status['overall_status'] = 'critical'
        else:
            health_status['overall_status'] = 'degraded'
    
    return health_status

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

def initialize_handlers(config: Dict[str, Any]) -> List[BaseLogHandler]:
    """Initialize handlers from configuration"""
    
    handlers = []
    
    for handler_name, handler_config in config.get('handlers', {}).items():
        try:
            handler_config['name'] = handler_name
            handler = create_handler_from_config(handler_config)
            handlers.append(handler)
            
            logger.info(
                "Handler initialized",
                handler_name=handler_name,
                handler_type=handler_config.get('type', 'file')
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize handler",
                handler_name=handler_name,
                error=str(e)
            )
    
    return handlers

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "BaseLogHandler",
    "EnhancedRotatingFileHandler",
    "TimedRotatingFileHandler", 
    "RemoteHTTPHandler",
    "SyslogHandler",
    "HandlerConfig",
    "FileHandlerConfig",
    "RemoteHandlerConfig",
    "LogEntry",
    "create_file_handler",
    "create_remote_handler",
    "create_handler_from_config",
    "health_check_handlers",
    "initialize_handlers"
]
        