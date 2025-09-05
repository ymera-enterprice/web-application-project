"""
YMERA Enterprise - Helper Utilities
Production-Ready Common Utility Functions - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import json
import time
import uuid
import zlib
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps, lru_cache
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Tuple, TypeVar, Generic
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from itertools import islice, chain
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field

# Local imports (alphabetical)
from config.settings import get_settings

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.utils.helpers")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Time constants
SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 3600
SECONDS_IN_DAY = 86400

# Size constants
BYTES_IN_KB = 1024
BYTES_IN_MB = 1024 * 1024
BYTES_IN_GB = 1024 * 1024 * 1024

# Default values
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_COUNT = 3
DEFAULT_BATCH_SIZE = 100
DEFAULT_CHUNK_SIZE = 8192

# Configuration loading
settings = get_settings()

# Generic type variables
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class ExecutionResult(Generic[T]):
    """Result of an operation execution"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RetryConfig:
    """Configuration for retry operations"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True

@dataclass
class BatchConfig:
    """Configuration for batch processing"""
    batch_size: int = 100
    max_workers: int = 5
    timeout_per_batch: float = 30.0
    continue_on_error: bool = True

class TaskStatus(Enum):
    """Status of async tasks"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# ===============================================================================
# CORE UTILITY CLASSES
# ===============================================================================

class UtilityManager:
    """Main utility manager for coordinating helper functions"""
    
    def __init__(self):
        self.logger = logger.bind(component="UtilityManager")
        self._thread_pool = ThreadPoolExecutor(max_workers=10)
        self._task_registry: Dict[str, Dict[str, Any]] = {}
        self._performance_metrics: Dict[str, List[float]] = defaultdict(list)
    
    async def cleanup(self) -> None:
        """Cleanup utility manager resources"""
        try:
            self._thread_pool.shutdown(wait=True)
            self.logger.info("Utility manager cleaned up successfully")
        except Exception as e:
            self.logger.error("Failed to cleanup utility manager", error=str(e))
    
    def register_task(self, task_id: str, task_info: Dict[str, Any]) -> None:
        """Register a task for tracking"""
        self._task_registry[task_id] = {
            **task_info,
            'registered_at': datetime.utcnow(),
            'status': TaskStatus.PENDING.value
        }
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a registered task"""
        return self._task_registry.get(task_id)
    
    def record_performance(self, operation: str, duration: float) -> None:
        """Record performance metrics"""
        self._performance_metrics[operation].append(duration)
        
        # Keep only last 1000 measurements
        if len(self._performance_metrics[operation]) > 1000:
            self._performance_metrics[operation] = self._performance_metrics[operation][-1000:]
    
    def get_performance_stats(self, operation: str) -> Dict[str, float]:
        """Get performance statistics for an operation"""
        measurements = self._performance_metrics.get(operation, [])
        if not measurements:
            return {}
        
        return {
            'count': len(measurements),
            'average': sum(measurements) / len(measurements),
            'min': min(measurements),
            'max': max(measurements),
            'latest': measurements[-1] if measurements else 0.0
        }

class AsyncTaskManager:
    """Manager for handling async tasks with lifecycle tracking"""
    
    def __init__(self, max_concurrent_tasks: int = 100):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.logger = logger.bind(component="AsyncTaskManager")
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: deque = deque(maxlen=1000)
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
    
    async def submit_task(self, 
                         task_id: str,
                         coro: Callable[..., Any],
                         *args,
                         **kwargs) -> str:
        """Submit an async task for execution"""
        if task_id in self._active_tasks:
            raise ValueError(f"Task {task_id} is already active")
        
        async def _wrapped_task():
            async with self._semaphore:
                try:
                    start_time = time.time()
                    result = await coro(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    self._completed_tasks.append({
                        'task_id': task_id,
                        'status': TaskStatus.COMPLETED.value,
                        'result': result,
                        'execution_time': execution_time,
                        'completed_at': datetime.utcnow()
                    })
                    
                    return result
                    
                except asyncio.CancelledError:
                    self._completed_tasks.append({
                        'task_id': task_id,
                        'status': TaskStatus.CANCELLED.value,
                        'completed_at': datetime.utcnow()
                    })
                    raise
                    
                except Exception as e:
                    self._completed_tasks.append({
                        'task_id': task_id,
                        'status': TaskStatus.FAILED.value,
                        'error': str(e),
                        'completed_at': datetime.utcnow()
                    })
                    raise
                finally:
                    self._active_tasks.pop(task_id, None)
        
        task = asyncio.create_task(_wrapped_task())
        self._active_tasks[task_id] = task
        
        self.logger.debug("Task submitted", task_id=task_id)
        return task_id
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Wait for a specific task to complete"""
        if task_id not in self._active_tasks:
            # Check if task already completed
            for completed in self._completed_tasks:
                if completed['task_id'] == task_id:
                    if completed['status'] == TaskStatus.COMPLETED.value:
                        return completed['result']
                    elif completed['status'] == TaskStatus.FAILED.value:
                        raise RuntimeError(completed['error'])
            
            raise ValueError(f"Task {task_id} not found")
        
        task = self._active_tasks[task_id]
        return await asyncio.wait_for(task, timeout=timeout)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self._active_tasks:
            task = self._active_tasks[task_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        return False
    
    def get_active_tasks(self) -> List[str]:
        """Get list of active task IDs"""
        return list(self._active_tasks.keys())
    
    def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent task completion history"""
        return list(islice(reversed(self._completed_tasks), limit))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def generate_unique_id(prefix: str = "", length: int = 8) -> str:
    """
    Generate a unique identifier.
    
    Args:
        prefix: Optional prefix for the ID
        length: Length of the random portion
        
    Returns:
        Unique identifier string
    """
    unique_part = str(uuid.uuid4()).replace('-', '')[:length]
    timestamp = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
    
    if prefix:
        return f"{prefix}_{timestamp}_{unique_part}"
    return f"{timestamp}_{unique_part}"

def format_timestamp(dt: Optional[datetime] = None, 
                    format_type: str = "iso",
                    timezone_aware: bool = True) -> str:
    """
    Format timestamp in various formats.
    
    Args:
        dt: DateTime object (defaults to current time)
        format_type: Format type ('iso', 'human', 'compact', 'filename')
        timezone_aware: Whether to include timezone info
        
    Returns:
        Formatted timestamp string
    """
    if dt is None:
        dt = datetime.utcnow()
    
    if timezone_aware and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    formats = {
        'iso': lambda d: d.isoformat(),
        'human': lambda d: d.strftime('%Y-%m-%d %H:%M:%S'),
        'compact': lambda d: d.strftime('%Y%m%d_%H%M%S'),
        'filename': lambda d: d.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
    }
    
    formatter = formats.get(format_type, formats['iso'])
    return formatter(dt)

def calculate_hash(data: Union[str, bytes, Dict[str, Any]], 
                  algorithm: str = "sha256") -> str:
    """
    Calculate hash of data.
    
    Args:
        data: Data to hash
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256', 'sha512')
        
    Returns:
        Hexadecimal hash string
    """
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    hasher = hashlib.new(algorithm)
    
    if isinstance(data, dict):
        # Convert dict to stable string representation
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        hasher.update(data_str.encode('utf-8'))
    elif isinstance(data, str):
        hasher.update(data.encode('utf-8'))
    elif isinstance(data, bytes):
        hasher.update(data)
    else:
        # Convert other types to string
        hasher.update(str(data).encode('utf-8'))
    
    return hasher.hexdigest()

def deep_merge_dict(dict1: Dict[K, V], dict2: Dict[K, V]) -> Dict[K, V]:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: Base dictionary
        dict2: Dictionary to merge into dict1
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if (key in result and 
            isinstance(result[key], dict) and 
            isinstance(value, dict)):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result

def flatten_dict(data: Dict[str, Any], 
                separator: str = ".",
                prefix: str = "") -> Dict[str, Any]:
    """
    Flatten nested dictionary.
    
    Args:
        data: Dictionary to flatten
        separator: Separator for nested keys
        prefix: Prefix for keys
        
    Returns:
        Flattened dictionary
    """
    items = []
    
    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, separator, new_key).items())
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, separator, f"{new_key}[{i}]").items())
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, value))
    
    return dict(items)

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string.
    
    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed data or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("JSON parsing failed", error=str(e), json_str=json_str[:100])
        return default

def safe_json_dumps(data: Any, 
                   default: Optional[Callable] = None,
                   ensure_ascii: bool = False,
                   indent: Optional[int] = None) -> str:
    """
    Safely serialize data to JSON.
    
    Args:
        data: Data to serialize
        default: Function to handle non-serializable objects
        ensure_ascii: Whether to escape non-ASCII characters
        indent: Indentation for pretty printing
        
    Returns:
        JSON string or empty string on error
    """
    def json_serializer(obj):
        """Default serializer for non-standard types"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    serializer = default or json_serializer
    
    try:
        return json.dumps(
            data,
            default=serializer,
            ensure_ascii=ensure_ascii,
            indent=indent,
            separators=(',', ':') if indent is None else None
        )
    except (TypeError, ValueError) as e:
        logger.warning("JSON serialization failed", error=str(e))
        return ""

async def retry_async_operation(
    operation: Callable[..., Any],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> ExecutionResult[Any]:
    """
    Retry an async operation with exponential backoff.
    
    Args:
        operation: Async function to retry
        config: Retry configuration
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation
        
    Returns:
        ExecutionResult with operation outcome
    """
    if config is None:
        config = RetryConfig()
    
    start_time = time.time()
    last_error = None
    
    for attempt in range(config.max_attempts):
        try:
            result = await operation(*args, **kwargs)
            return ExecutionResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time,
                metadata={'attempts': attempt + 1}
            )
            
        except Exception as e:
            last_error = e
            
            if attempt < config.max_attempts - 1:
                # Calculate delay with exponential backoff
                delay = min(
                    config.base_delay * (config.backoff_factor ** attempt),
                    config.max_delay
                )
                
                # Add jitter to prevent thundering herd
                if config.jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)
                
                logger.debug(
                    "Operation failed, retrying",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e)
                )
                
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Operation failed after all retries",
                    attempts=config.max_attempts,
                    error=str(e)
                )
    
    return ExecutionResult(
        success=False,
        error=str(last_error),
        execution_time=time.time() - start_time,
        metadata={'attempts': config.max_attempts}
    )

async def batch_process(
    items: List[T],
    processor: Callable[[T], Any],
    config: Optional[BatchConfig] = None
) -> List[ExecutionResult[Any]]:
    """
    Process items in batches with concurrent execution.
    
    Args:
        items: Items to process
        processor: Function to process each item
        config: Batch processing configuration
        
    Returns:
        List of ExecutionResult for each item
    """
    if config is None:
        config = BatchConfig()
    
    if not items:
        return []
    
    results = []
    semaphore = asyncio.Semaphore(config.max_workers)
    
    async def process_item(item: T, index: int) -> ExecutionResult[Any]:
        async with semaphore:
            start_time = time.time()
            try:
                if asyncio.iscoroutinefunction(processor):
                    result = await asyncio.wait_for(
                        processor(item),
                        timeout=config.timeout_per_batch
                    )
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, processor, item)
                
                return ExecutionResult(
                    success=True,
                    data=result,
                    execution_time=time.time() - start_time,
                    metadata={'item_index': index}
                )
                
            except Exception as e:
                logger.warning(
                    "Item processing failed",
                    item_index=index,
                    error=str(e)
                )
                
                return ExecutionResult(
                    success=False,
                    error=str(e),
                    execution_time=time.time() - start_time,
                    metadata={'item_index': index}
                )
    
    # Process all items concurrently
    tasks = [process_item(item, i) for i, item in enumerate(items)]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    
    # Log batch processing summary
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    
    logger.info(
        "Batch processing completed",
        total_items=len(items),
        successful=successful,
        failed=failed,
        success_rate=successful / len(items) if results else 0
    )
    
    return results

@asynccontextmanager
async def measure_execution_time(operation_name: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Context manager to measure execution time.
    
    Args:
        operation_name: Name of the operation being measured
        
    Yields:
        Dictionary with timing information
    """
    start_time = time.time()
    timing_info = {'operation': operation_name, 'start_time': start_time}
    
    try:
        yield timing_info
    finally:
        end_time = time.time()
        execution_time = end_time - start_time
        
        timing_info.update({
            'end_time': end_time,
            'execution_time': execution_time
        })
        
        logger.debug(
            "Operation timing",
            operation=operation_name,
            execution_time=execution_time
        )

def chunk_list(items: List[T], chunk_size: int) -> AsyncGenerator[List[T], None]:
    """
    Split list into chunks of specified size.
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
        
    Yields:
        Chunks of the original list
    """
    async def _chunk_generator():
        for i in range(0, len(items), chunk_size):
            yield items[i:i + chunk_size]
    
    return _chunk_generator()

def compress_data(data: Union[str, bytes], level: int = 6) -> bytes:
    """
    Compress data using zlib.
    
    Args:
        data: Data to compress
        level: Compression level (0-9, higher = better compression)
        
    Returns:
        Compressed data
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    return zlib.compress(data, level)

def decompress_data(compressed_data: bytes, encoding: str = 'utf-8') -> Union[str, bytes]:
    """
    Decompress data using zlib.
    
    Args:
        compressed_data: Compressed data
        encoding: Text encoding (None for bytes output)
        
    Returns:
        Decompressed data
    """
    decompressed = zlib.decompress(compressed_data)
    
    if encoding:
        return decompressed.decode(encoding)
    return decompressed

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"

def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"

def parse_duration(duration_str: str) -> float:
    """
    Parse duration string to seconds.
    
    Args:
        duration_str: Duration string (e.g., "1h30m", "45s")
        
    Returns:
        Duration in seconds
    """
    import re
    
    # Pattern to match duration components
    pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?'
    match = re.match(pattern, duration_str.strip())
    
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}")
    
    days, hours, minutes, seconds = match.groups()
    
    total_seconds = 0
    if days:
        total_seconds += int(days) * 86400
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += float(seconds)
    
    return total_seconds

@lru_cache(maxsize=1000)
def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two strings using Jaccard similarity.
    
    Args:
        text1: First string
        text2: Second string
        
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0
    
    # Convert to sets of words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Calculate Jaccard similarity
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def create_circular_buffer(maxsize: int) -> deque:
    """
    Create a circular buffer with maximum size.
    
    Args:
        maxsize: Maximum number of items in buffer
        
    Returns:
        Circular buffer (deque)
    """
    return deque(maxlen=maxsize)

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "UtilityManager",
    "AsyncTaskManager",
    "ExecutionResult",
    "RetryConfig",
    "BatchConfig",
    "TaskStatus",
    "generate_unique_id",
    "format_timestamp",
    "calculate_hash",
    "deep_merge_dict",
    "flatten_dict",
    "safe_json_loads",
    "safe_json_dumps",
    "retry_async_operation",
    "batch_process",
    "measure_execution_time",
    "chunk_list",
    "compress_data",
    "decompress_data",
    "format_file_size",
    "format_duration",
    "parse_duration",
    "calculate_similarity",
    "create_circular_buffer"
]