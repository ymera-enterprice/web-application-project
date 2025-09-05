"""
YMERA Enterprise - Cache Manager
Production-Ready Redis Cache Management System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import json
import logging
import pickle
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
from redis.exceptions import RedisError, ConnectionError, TimeoutError as RedisTimeoutError

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from utils.serialization import serialize_data, deserialize_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.cache_manager")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Cache-specific constants
DEFAULT_TTL = 3600  # 1 hour default TTL
MAX_RETRIES = 3
TIMEOUT_SECONDS = 5
COMPRESSION_THRESHOLD = 1024  # Compress data larger than 1KB
MAX_KEY_LENGTH = 250
MAX_VALUE_SIZE = 512 * 1024 * 1024  # 512MB max value size

# Serialization formats
class SerializationFormat(Enum):
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    PLAIN = "plain"

# Cache operation types
class CacheOperation(Enum):
    GET = "get"
    SET = "set"
    DELETE = "delete"
    EXISTS = "exists"
    EXPIRE = "expire"
    INCR = "incr"
    DECR = "decr"

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class CacheConfig:
    """Configuration dataclass for cache settings"""
    redis_url: str = "redis://localhost:6379/0"
    max_connections: int = 100
    timeout: int = 5
    retry_attempts: int = 3
    default_ttl: int = 3600
    compression_enabled: bool = True
    encryption_enabled: bool = False
    key_prefix: str = "ymera"
    pool_timeout: int = 20
    socket_keepalive: bool = True
    socket_keepalive_options: Dict[str, int] = field(default_factory=lambda: {
        "TCP_KEEPIDLE": 1,
        "TCP_KEEPINTVL": 3,
        "TCP_KEEPCNT": 5,
    })

@dataclass
class CacheEntry:
    """Cache entry metadata"""
    key: str
    value: Any
    ttl: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    size_bytes: int = 0
    compression_used: bool = False
    encryption_used: bool = False
    serialization_format: SerializationFormat = SerializationFormat.JSON

@dataclass
class CacheStats:
    """Cache statistics"""
    total_keys: int = 0
    hit_count: int = 0
    miss_count: int = 0
    set_count: int = 0
    delete_count: int = 0
    memory_usage: int = 0
    connection_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

class CacheRequest(BaseModel):
    """Pydantic schema for cache API requests"""
    key: str = Field(..., min_length=1, max_length=MAX_KEY_LENGTH)
    value: Optional[Any] = None
    ttl: Optional[int] = Field(None, ge=1, le=86400 * 7)  # Max 7 days
    namespace: Optional[str] = Field(None, max_length=50)
    compression: Optional[bool] = None
    encryption: Optional[bool] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class CacheResponse(BaseModel):
    """Pydantic schema for cache API responses"""
    success: bool
    key: str
    value: Optional[Any] = None
    ttl: Optional[int] = None
    cached_at: Optional[datetime] = None
    size_bytes: Optional[int] = None
    operation: str
    execution_time_ms: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

# ===============================================================================
# EXCEPTION CLASSES
# ===============================================================================

class CacheError(Exception):
    """Base cache exception"""
    pass

class CacheConnectionError(CacheError):
    """Cache connection error"""
    pass

class CacheTimeoutError(CacheError):
    """Cache operation timeout"""
    pass

class CacheSerializationError(CacheError):
    """Cache serialization error"""
    pass

class CacheKeyError(CacheError):
    """Invalid cache key error"""
    pass

class CacheValueError(CacheError):
    """Invalid cache value error"""
    pass

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseCacheManager(ABC):
    """Abstract base class for cache managers"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.logger = logger.bind(cache_manager=self.__class__.__name__)
        self._stats = CacheStats()
        self._connection_pool = None
        self._health_status = True
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize cache manager resources"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup cache manager resources"""
        pass
    
    @abstractmethod
    async def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """Set value in cache"""
        pass
    
    @abstractmethod
    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete value from cache"""
        pass

class RedisCacheManager(BaseCacheManager):
    """Production-ready Redis cache manager implementation"""
    
    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self._redis: Optional[aioredis.Redis] = None
        self._connection_semaphore = asyncio.Semaphore(config.max_connections)
        self._operation_locks: Dict[str, asyncio.Lock] = {}
        self._serializer = CacheSerializer()
        self._key_validator = CacheKeyValidator()
        self._performance_monitor = CachePerformanceMonitor()
    
    async def initialize(self) -> None:
        """Initialize Redis connection and resources"""
        try:
            # Create Redis connection pool
            self._redis = aioredis.from_url(
                self.config.redis_url,
                max_connections=self.config.max_connections,
                retry_on_timeout=True,
                retry_on_error=[ConnectionError, RedisTimeoutError],
                socket_keepalive=self.config.socket_keepalive,
                socket_keepalive_options=self.config.socket_keepalive_options,
                decode_responses=False  # We handle encoding/decoding ourselves
            )
            
            # Test connection
            await self._redis.ping()
            
            # Initialize performance monitoring
            await self._performance_monitor.initialize()
            
            self.logger.info(
                "Redis cache manager initialized successfully",
                redis_url=self.config.redis_url,
                max_connections=self.config.max_connections
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize Redis cache manager", error=str(e))
            raise CacheConnectionError(f"Failed to initialize Redis: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup Redis connections and resources"""
        try:
            if self._redis:
                await self._redis.close()
                await self._redis.connection_pool.disconnect()
            
            await self._performance_monitor.cleanup()
            
            self.logger.info("Redis cache manager cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during cache manager cleanup", error=str(e))
    
    @track_performance
    async def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Get value from Redis cache"""
        start_time = time.time()
        full_key = self._build_key(key, namespace)
        
        try:
            # Validate key
            self._key_validator.validate(full_key)
            
            async with self._connection_semaphore:
                # Get value from Redis
                raw_value = await self._redis.get(full_key)
                
                if raw_value is None:
                    self._stats.miss_count += 1
                    self.logger.debug("Cache miss", key=full_key)
                    return None
                
                # Deserialize value
                value = await self._serializer.deserialize(raw_value)
                
                # Update statistics
                self._stats.hit_count += 1
                self._stats.last_updated = datetime.utcnow()
                
                execution_time = (time.time() - start_time) * 1000
                await self._performance_monitor.record_operation(
                    CacheOperation.GET, execution_time, True
                )
                
                self.logger.debug(
                    "Cache hit",
                    key=full_key,
                    execution_time_ms=execution_time
                )
                
                return value
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            await self._performance_monitor.record_operation(
                CacheOperation.GET, execution_time, False
            )
            
            self.logger.error(
                "Cache get operation failed",
                key=full_key,
                error=str(e),
                execution_time_ms=execution_time
            )
            
            if isinstance(e, (ConnectionError, RedisTimeoutError)):
                raise CacheConnectionError(f"Redis connection error: {str(e)}")
            else:
                raise CacheError(f"Get operation failed: {str(e)}")
    
    @track_performance
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        compression: Optional[bool] = None,
        encryption: Optional[bool] = None
    ) -> bool:
        """Set value in Redis cache"""
        start_time = time.time()
        full_key = self._build_key(key, namespace)
        effective_ttl = ttl or self.config.default_ttl
        
        try:
            # Validate key and value
            self._key_validator.validate(full_key)
            await self._validate_value(value)
            
            # Serialize value
            serialized_value = await self._serializer.serialize(
                value,
                compression=compression or self.config.compression_enabled,
                encryption=encryption or self.config.encryption_enabled
            )
            
            async with self._connection_semaphore:
                # Set value in Redis
                success = await self._redis.setex(
                    full_key, 
                    effective_ttl, 
                    serialized_value
                )
                
                if success:
                    # Update statistics
                    self._stats.set_count += 1
                    self._stats.last_updated = datetime.utcnow()
                    
                    execution_time = (time.time() - start_time) * 1000
                    await self._performance_monitor.record_operation(
                        CacheOperation.SET, execution_time, True
                    )
                    
                    self.logger.debug(
                        "Cache set successful",
                        key=full_key,
                        ttl=effective_ttl,
                        size_bytes=len(serialized_value),
                        execution_time_ms=execution_time
                    )
                    
                    return True
                
                return False
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            await self._performance_monitor.record_operation(
                CacheOperation.SET, execution_time, False
            )
            
            self.logger.error(
                "Cache set operation failed",
                key=full_key,
                error=str(e),
                execution_time_ms=execution_time
            )
            
            if isinstance(e, (ConnectionError, RedisTimeoutError)):
                raise CacheConnectionError(f"Redis connection error: {str(e)}")
            else:
                raise CacheError(f"Set operation failed: {str(e)}")
    
    @track_performance
    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete value from Redis cache"""
        start_time = time.time()
        full_key = self._build_key(key, namespace)
        
        try:
            # Validate key
            self._key_validator.validate(full_key)
            
            async with self._connection_semaphore:
                # Delete from Redis
                deleted_count = await self._redis.delete(full_key)
                
                success = deleted_count > 0
                
                if success:
                    # Update statistics
                    self._stats.delete_count += 1
                    self._stats.last_updated = datetime.utcnow()
                
                execution_time = (time.time() - start_time) * 1000
                await self._performance_monitor.record_operation(
                    CacheOperation.DELETE, execution_time, success
                )
                
                self.logger.debug(
                    "Cache delete operation",
                    key=full_key,
                    success=success,
                    execution_time_ms=execution_time
                )
                
                return success
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            await self._performance_monitor.record_operation(
                CacheOperation.DELETE, execution_time, False
            )
            
            self.logger.error(
                "Cache delete operation failed",
                key=full_key,
                error=str(e),
                execution_time_ms=execution_time
            )
            
            if isinstance(e, (ConnectionError, RedisTimeoutError)):
                raise CacheConnectionError(f"Redis connection error: {str(e)}")
            else:
                raise CacheError(f"Delete operation failed: {str(e)}")
    
    async def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """Check if key exists in cache"""
        full_key = self._build_key(key, namespace)
        
        try:
            self._key_validator.validate(full_key)
            
            async with self._connection_semaphore:
                exists = await self._redis.exists(full_key)
                return exists > 0
                
        except Exception as e:
            self.logger.error("Cache exists check failed", key=full_key, error=str(e))
            raise CacheError(f"Exists check failed: {str(e)}")
    
    async def expire(self, key: str, ttl: int, namespace: Optional[str] = None) -> bool:
        """Set TTL for existing key"""
        full_key = self._build_key(key, namespace)
        
        try:
            self._key_validator.validate(full_key)
            
            async with self._connection_semaphore:
                success = await self._redis.expire(full_key, ttl)
                return success
                
        except Exception as e:
            self.logger.error("Cache expire operation failed", key=full_key, error=str(e))
            raise CacheError(f"Expire operation failed: {str(e)}")
    
    async def increment(self, key: str, amount: int = 1, namespace: Optional[str] = None) -> int:
        """Increment numeric value in cache"""
        full_key = self._build_key(key, namespace)
        
        try:
            self._key_validator.validate(full_key)
            
            async with self._connection_semaphore:
                new_value = await self._redis.incrby(full_key, amount)
                return new_value
                
        except Exception as e:
            self.logger.error("Cache increment operation failed", key=full_key, error=str(e))
            raise CacheError(f"Increment operation failed: {str(e)}")
    
    async def decrement(self, key: str, amount: int = 1, namespace: Optional[str] = None) -> int:
        """Decrement numeric value in cache"""
        return await self.increment(key, -amount, namespace)
    
    async def get_multi(self, keys: List[str], namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get multiple values from cache"""
        if not keys:
            return {}
        
        full_keys = [self._build_key(key, namespace) for key in keys]
        
        try:
            # Validate all keys
            for full_key in full_keys:
                self._key_validator.validate(full_key)
            
            async with self._connection_semaphore:
                raw_values = await self._redis.mget(full_keys)
                
                result = {}
                for i, (original_key, raw_value) in enumerate(zip(keys, raw_values)):
                    if raw_value is not None:
                        try:
                            result[original_key] = await self._serializer.deserialize(raw_value)
                            self._stats.hit_count += 1
                        except Exception as e:
                            self.logger.warning(
                                "Failed to deserialize cached value",
                                key=original_key,
                                error=str(e)
                            )
                    else:
                        self._stats.miss_count += 1
                
                return result
                
        except Exception as e:
            self.logger.error("Multi-get operation failed", keys=keys, error=str(e))
            raise CacheError(f"Multi-get operation failed: {str(e)}")
    
    async def set_multi(
        self, 
        data: Dict[str, Any], 
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> Dict[str, bool]:
        """Set multiple values in cache"""
        if not data:
            return {}
        
        effective_ttl = ttl or self.config.default_ttl
        results = {}
        
        # Process each key-value pair
        for key, value in data.items():
            try:
                success = await self.set(key, value, effective_ttl, namespace)
                results[key] = success
            except Exception as e:
                self.logger.warning(
                    "Failed to set cache value in multi-set",
                    key=key,
                    error=str(e)
                )
                results[key] = False
        
        return results
    
    async def delete_multi(self, keys: List[str], namespace: Optional[str] = None) -> Dict[str, bool]:
        """Delete multiple values from cache"""
        if not keys:
            return {}
        
        results = {}
        
        for key in keys:
            try:
                success = await self.delete(key, namespace)
                results[key] = success
            except Exception as e:
                self.logger.warning(
                    "Failed to delete cache value in multi-delete",
                    key=key,
                    error=str(e)
                )
                results[key] = False
        
        return results
    
    async def flush_namespace(self, namespace: str) -> int:
        """Flush all keys in a namespace"""
        pattern = self._build_key("*", namespace)
        
        try:
            async with self._connection_semaphore:
                # Get all keys matching pattern
                keys = await self._redis.keys(pattern)
                
                if not keys:
                    return 0
                
                # Delete all matching keys
                deleted_count = await self._redis.delete(*keys)
                
                self.logger.info(
                    "Namespace flushed",
                    namespace=namespace,
                    keys_deleted=deleted_count
                )
                
                return deleted_count
                
        except Exception as e:
            self.logger.error("Namespace flush failed", namespace=namespace, error=str(e))
            raise CacheError(f"Namespace flush failed: {str(e)}")
    
    async def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        try:
            async with self._connection_semaphore:
                # Get Redis info
                redis_info = await self._redis.info()
                
                # Update stats with Redis metrics
                self._stats.total_keys = redis_info.get('db0', {}).get('keys', 0)
                self._stats.memory_usage = redis_info.get('used_memory', 0)
                self._stats.connection_count = redis_info.get('connected_clients', 0)
                self._stats.last_updated = datetime.utcnow()
                
                return self._stats
                
        except Exception as e:
            self.logger.error("Failed to get cache stats", error=str(e))
            raise CacheError(f"Stats retrieval failed: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "component": "redis_cache_manager",
            "version": "4.0",
            "checks": {}
        }
        
        try:
            # Test Redis connection
            start_time = time.time()
            await self._redis.ping()
            ping_time = (time.time() - start_time) * 1000
            
            health_status["checks"]["redis_ping"] = {
                "status": "healthy",
                "response_time_ms": ping_time
            }
            
            # Test basic operations
            test_key = f"health_check_{uuid.uuid4().hex}"
            test_value = {"test": True, "timestamp": datetime.utcnow().isoformat()}
            
            # Test set operation
            await self.set(test_key, test_value, ttl=60)
            health_status["checks"]["set_operation"] = {"status": "healthy"}
            
            # Test get operation
            retrieved_value = await self.get(test_key)
            if retrieved_value == test_value:
                health_status["checks"]["get_operation"] = {"status": "healthy"}
            else:
                health_status["checks"]["get_operation"] = {"status": "unhealthy", "reason": "value mismatch"}
                health_status["status"] = "degraded"
            
            # Test delete operation
            await self.delete(test_key)
            health_status["checks"]["delete_operation"] = {"status": "healthy"}
            
            # Get performance metrics
            stats = await self.get_stats()
            health_status["metrics"] = {
                "total_keys": stats.total_keys,
                "hit_rate": stats.hit_count / max(stats.hit_count + stats.miss_count, 1),
                "memory_usage_bytes": stats.memory_usage,
                "connection_count": stats.connection_count
            }
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            self.logger.error("Health check failed", error=str(e))
        
        return health_status
    
    def _build_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Build full cache key with prefix and namespace"""
        parts = [self.config.key_prefix]
        
        if namespace:
            parts.append(namespace)
        
        parts.append(key)
        
        return ":".join(parts)
    
    async def _validate_value(self, value: Any) -> None:
        """Validate cache value"""
        if value is None:
            return
        
        # Check serialized size
        try:
            serialized = await self._serializer.serialize(value, compression=False)
            if len(serialized) > MAX_VALUE_SIZE:
                raise CacheValueError(f"Value too large: {len(serialized)} bytes (max: {MAX_VALUE_SIZE})")
        except Exception as e:
            raise CacheValueError(f"Value validation failed: {str(e)}")

# ===============================================================================
# UTILITY CLASSES
# ===============================================================================

class CacheKeyValidator:
    """Validates cache keys"""
    
    def validate(self, key: str) -> None:
        """Validate cache key format and constraints"""
        if not key:
            raise CacheKeyError("Key cannot be empty")
        
        if len(key) > MAX_KEY_LENGTH:
            raise CacheKeyError(f"Key too long: {len(key)} (max: {MAX_KEY_LENGTH})")
        
        # Check for invalid characters
        invalid_chars = [' ', '\n', '\r', '\t']
        for char in invalid_chars:
            if char in key:
                raise CacheKeyError(f"Key contains invalid character: '{char}'")

class CacheSerializer:
    """Handles cache value serialization/deserialization"""
    
    def __init__(self):
        self.logger = logger.bind(component="cache_serializer")
    
    async def serialize(
        self, 
        value: Any, 
        compression: bool = False,
        encryption: bool = False
    ) -> bytes:
        """Serialize value for caching"""
        try:
            # Determine serialization format
            if isinstance(value, (str, int, float, bool)):
                # Simple types - use JSON
                serialized = json.dumps(value).encode('utf-8')
                format_used = SerializationFormat.JSON
            else:
                # Complex types - use pickle
                serialized = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
                format_used = SerializationFormat.PICKLE
            
            # Apply compression if enabled and beneficial
            if compression and len(serialized) > COMPRESSION_THRESHOLD:
                import gzip
                compressed = gzip.compress(serialized)
                if len(compressed) < len(serialized):
                    serialized = compressed
                    # Add compression marker
                    serialized = b'GZIP:' + serialized
            
            # Apply encryption if enabled
            if encryption:
                serialized = await encrypt_data(serialized)
                # Add encryption marker
                serialized = b'ENC:' + serialized
            
            return serialized
            
        except Exception as e:
            self.logger.error("Serialization failed", error=str(e))
            raise CacheSerializationError(f"Serialization failed: {str(e)}")
    
    async def deserialize(self, data: bytes) -> Any:
        """Deserialize cached value"""
        try:
            # Check for encryption marker
            if data.startswith(b'ENC:'):
                data = data[4:]  # Remove marker
                data = await decrypt_data(data)
            
            # Check for compression marker
            if data.startswith(b'GZIP:'):
                import gzip
                data = data[5:]  # Remove marker
                data = gzip.decompress(data)
            
            # Try JSON first (for simple types)
            try:
                return json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to pickle
                return pickle.loads(data)
                
        except Exception as e:
            self.logger.error("Deserialization failed", error=str(e))
            raise CacheSerializationError(f"Deserialization failed: {str(e)}")

class CachePerformanceMonitor:
    """Monitors cache performance metrics"""
    
    def __init__(self):
        self.logger = logger.bind(component="cache_performance_monitor")
        self._operation_metrics: Dict[CacheOperation, List[float]] = {
            op: [] for op in CacheOperation
        }
        self._success_rates: Dict[CacheOperation, List[bool]] = {
            op: [] for op in CacheOperation
        }
    
    async def initialize(self) -> None:
        """Initialize performance monitoring"""
        self.logger.info("Cache performance monitor initialized")
    
    async def cleanup(self) -> None:
        """Cleanup performance monitoring"""
        self.logger.info("Cache performance monitor cleanup completed")
    
    async def record_operation(
        self, 
        operation: CacheOperation, 
        execution_time_ms: float,
        success: bool
    ) -> None:
        """Record operation performance metrics"""
        self._operation_metrics[operation].append(execution_time_ms)
        self._success_rates[operation].append(success)
        
        # Keep only recent metrics (last 1000 operations per type)
        if len(self._operation_metrics[operation]) > 1000:
            self._operation_metrics[operation] = self._operation_metrics[operation][-1000:]
            self._success_rates[operation] = self._success_rates[operation][-1000:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        metrics = {}
        
        for operation in CacheOperation:
            op_metrics = self._operation_metrics[operation]
            success_metrics = self._success_rates[operation]
            
            if op_metrics:
                metrics[operation.value] = {
                    "avg_execution_time_ms": sum(op_metrics) / len(op_metrics),
                    "min_execution_time_ms": min(op_metrics),
                    "max_execution_time_ms": max(op_metrics),
                    "total_operations": len(op_metrics),
                    "success_rate": sum(success_metrics) / len(success_metrics) if success_metrics else 0
                }
            else:
                metrics[operation.value] = {
                    "avg_execution_time_ms": 0,
                    "min_execution_time_ms": 0,
                    "max_execution_time_ms": 0,
                    "total_operations": 0,
                    "success_rate": 0
                }
        
        return metrics

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def validate_cache_configuration(config: Dict[str, Any]) -> bool:
    """Validate cache configuration"""
    required_fields = [
        "redis_url", "max_connections", "timeout", "retry_attempts", 
        "default_ttl", "key_prefix"
    ]
    
    # Check required fields
    for field in required_fields:
        if field not in config:
            logger.error(f"Missing required configuration field: {field}")
            return False
    
    # Validate field types and ranges
    try:
        if not isinstance(config["max_connections"], int) or config["max_connections"] <= 0:
            return False
        
        if not isinstance(config["timeout"], int) or config["timeout"] <= 0:
            return False
        
        if not isinstance(config["retry_attempts"], int) or config["retry_attempts"] < 0:
            return False
        
        if not isinstance(config["default_ttl"], int) or config["default_ttl"] <= 0:
            return False
        
        if not isinstance(config["key_prefix"], str) or not config["key_prefix"]:
            return False
        
        return True
        
    except (TypeError, ValueError) as e:
        logger.error(f"Configuration validation error: {str(e)}")
        return False

async def create_cache_key_hash(data: str) -> str:
    """Create consistent hash for cache keys"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]

async def estimate_cache_size(value: Any) -> int:
    """Estimate cache value size in bytes"""
    try:
        if isinstance(value, str):
            return len(value.encode('utf-8'))
        elif isinstance(value, (int, float, bool)):
            return 8  # Approximate size
        else:
            # Use pickle to estimate size
            return len(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:
        return 0

@asynccontextmanager
async def cache_transaction(cache_manager: RedisCacheManager):
    """Context manager for cache transactions"""
    transaction_id = uuid.uuid4().hex
    logger.debug("Starting cache transaction", transaction_id=transaction_id)
    
    try:
        yield cache_manager
        logger.debug("Cache transaction completed", transaction_id=transaction_id)
    except Exception as e:
        logger.error(
            "Cache transaction failed", 
            transaction_id=transaction_id, 
            error=str(e)
        )
        raise
    finally:
        logger.debug("Cache transaction cleanup", transaction_id=transaction_id)

# ===============================================================================
# CACHE DECORATORS
# ===============================================================================

def cache_result(
    ttl: int = DEFAULT_TTL,
    namespace: Optional[str] = None,
    key_generator: Optional[Callable] = None
):
    """Decorator to cache function results"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Get cache manager from context or create one
            cache_manager = kwargs.get('_cache_manager')
            if not cache_manager:
                config = CacheConfig()
                cache_manager = RedisCacheManager(config)
                await cache_manager.initialize()
            
            # Generate cache key
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend([str(arg) for arg in args])
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
                cache_key = await create_cache_key_hash(":".join(key_parts))
            
            # Try to get cached result
            try:
                cached_result = await cache_manager.get(cache_key, namespace)
                if cached_result is not None:
                    logger.debug(
                        "Cache hit for function result",
                        function=func.__name__,
                        cache_key=cache_key
                    )
                    return cached_result
            except Exception as e:
                logger.warning(
                    "Cache get failed, executing function",
                    function=func.__name__,
                    error=str(e)
                )
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            
            try:
                await cache_manager.set(cache_key, result, ttl, namespace)
                logger.debug(
                    "Function result cached",
                    function=func.__name__,
                    cache_key=cache_key,
                    ttl=ttl
                )
            except Exception as e:
                logger.warning(
                    "Failed to cache function result",
                    function=func.__name__,
                    error=str(e)
                )
            
            return result
        
        return wrapper
    return decorator

def invalidate_cache_on_change(
    cache_keys: List[str],
    namespace: Optional[str] = None
):
    """Decorator to invalidate cache keys when function is called"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Execute function first
            result = await func(*args, **kwargs)
            
            # Get cache manager
            cache_manager = kwargs.get('_cache_manager')
            if cache_manager:
                # Invalidate specified cache keys
                for key in cache_keys:
                    try:
                        await cache_manager.delete(key, namespace)
                        logger.debug(
                            "Cache key invalidated",
                            function=func.__name__,
                            cache_key=key
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to invalidate cache key",
                            function=func.__name__,
                            cache_key=key,
                            error=str(e)
                        )
            
            return result
        
        return wrapper
    return decorator

# ===============================================================================
# CACHE WARMING UTILITIES
# ===============================================================================

class CacheWarmer:
    """Utility for cache warming operations"""
    
    def __init__(self, cache_manager: RedisCacheManager):
        self.cache_manager = cache_manager
        self.logger = logger.bind(component="cache_warmer")
    
    async def warm_cache_batch(
        self,
        data_generator: AsyncGenerator[Tuple[str, Any, int], None],
        namespace: Optional[str] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Warm cache with batch of data"""
        stats = {
            "total_processed": 0,
            "successful_sets": 0,
            "failed_sets": 0,
            "start_time": datetime.utcnow(),
            "batch_size": batch_size
        }
        
        batch_data = {}
        
        try:
            async for key, value, ttl in data_generator:
                batch_data[key] = {"value": value, "ttl": ttl}
                
                # Process batch when it reaches batch_size
                if len(batch_data) >= batch_size:
                    batch_results = await self._process_warm_batch(batch_data, namespace)
                    self._update_warm_stats(stats, batch_results)
                    batch_data.clear()
            
            # Process remaining data
            if batch_data:
                batch_results = await self._process_warm_batch(batch_data, namespace)
                self._update_warm_stats(stats, batch_results)
            
            stats["end_time"] = datetime.utcnow()
            stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            self.logger.info(
                "Cache warming completed",
                total_processed=stats["total_processed"],
                successful_sets=stats["successful_sets"],
                failed_sets=stats["failed_sets"],
                duration_seconds=stats["duration_seconds"]
            )
            
            return stats
            
        except Exception as e:
            self.logger.error("Cache warming failed", error=str(e))
            stats["error"] = str(e)
            return stats
    
    async def _process_warm_batch(
        self,
        batch_data: Dict[str, Dict[str, Any]],
        namespace: Optional[str]
    ) -> Dict[str, bool]:
        """Process a batch of cache warming data"""
        results = {}
        
        for key, data in batch_data.items():
            try:
                success = await self.cache_manager.set(
                    key, 
                    data["value"], 
                    data["ttl"], 
                    namespace
                )
                results[key] = success
            except Exception as e:
                self.logger.warning(
                    "Failed to warm cache key",
                    key=key,
                    error=str(e)
                )
                results[key] = False
        
        return results
    
    def _update_warm_stats(self, stats: Dict[str, Any], results: Dict[str, bool]) -> None:
        """Update warming statistics"""
        stats["total_processed"] += len(results)
        stats["successful_sets"] += sum(1 for success in results.values() if success)
        stats["failed_sets"] += sum(1 for success in results.values() if not success)

# ===============================================================================
# CACHE MONITORING & MAINTENANCE
# ===============================================================================

class CacheMaintenanceManager:
    """Manages cache maintenance operations"""
    
    def __init__(self, cache_manager: RedisCacheManager):
        self.cache_manager = cache_manager
        self.logger = logger.bind(component="cache_maintenance")
        self._maintenance_running = False
    
    async def start_maintenance_scheduler(self, interval_minutes: int = 60) -> None:
        """Start background maintenance scheduler"""
        if self._maintenance_running:
            self.logger.warning("Maintenance scheduler already running")
            return
        
        self._maintenance_running = True
        self.logger.info(
            "Starting cache maintenance scheduler",
            interval_minutes=interval_minutes
        )
        
        asyncio.create_task(self._maintenance_loop(interval_minutes))
    
    async def stop_maintenance_scheduler(self) -> None:
        """Stop background maintenance scheduler"""
        self._maintenance_running = False
        self.logger.info("Cache maintenance scheduler stopped")
    
    async def _maintenance_loop(self, interval_minutes: int) -> None:
        """Background maintenance loop"""
        while self._maintenance_running:
            try:
                await self.run_maintenance_cycle()
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                self.logger.error("Maintenance cycle failed", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def run_maintenance_cycle(self) -> Dict[str, Any]:
        """Run complete maintenance cycle"""
        cycle_start = datetime.utcnow()
        maintenance_results = {
            "start_time": cycle_start,
            "operations": {},
            "errors": []
        }
        
        try:
            # Clean expired keys
            expired_cleanup = await self._cleanup_expired_keys()
            maintenance_results["operations"]["expired_cleanup"] = expired_cleanup
            
            # Memory optimization
            memory_optimization = await self._optimize_memory_usage()
            maintenance_results["operations"]["memory_optimization"] = memory_optimization
            
            # Performance metrics collection
            performance_metrics = await self._collect_performance_metrics()
            maintenance_results["operations"]["performance_metrics"] = performance_metrics
            
            # Health check
            health_status = await self.cache_manager.health_check()
            maintenance_results["operations"]["health_check"] = health_status
            
            maintenance_results["end_time"] = datetime.utcnow()
            maintenance_results["duration_seconds"] = (
                maintenance_results["end_time"] - cycle_start
            ).total_seconds()
            
            self.logger.info(
                "Maintenance cycle completed successfully",
                duration_seconds=maintenance_results["duration_seconds"]
            )
            
        except Exception as e:
            maintenance_results["errors"].append(str(e))
            self.logger.error("Maintenance cycle encountered errors", error=str(e))
        
        return maintenance_results
    
    async def _cleanup_expired_keys(self) -> Dict[str, Any]:
        """Clean up expired keys (Redis handles this automatically, but we track it)"""
        try:
            stats = await self.cache_manager.get_stats()
            return {
                "operation": "expired_cleanup",
                "status": "completed",
                "current_key_count": stats.total_keys,
                "memory_usage": stats.memory_usage
            }
        except Exception as e:
            return {
                "operation": "expired_cleanup",
                "status": "failed",
                "error": str(e)
            }
    
    async def _optimize_memory_usage(self) -> Dict[str, Any]:
        """Optimize cache memory usage"""
        try:
            # Redis MEMORY PURGE command to free up memory
            async with self.cache_manager._connection_semaphore:
                # Note: MEMORY PURGE is available in Redis 4.0+
                try:
                    await self.cache_manager._redis.execute_command("MEMORY", "PURGE")
                    status = "completed"
                except Exception:
                    # Command might not be available in older Redis versions
                    status = "skipped_unsupported"
            
            stats = await self.cache_manager.get_stats()
            
            return {
                "operation": "memory_optimization",
                "status": status,
                "memory_usage_after": stats.memory_usage
            }
            
        except Exception as e:
            return {
                "operation": "memory_optimization",
                "status": "failed",
                "error": str(e)
            }
    
    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect and log performance metrics"""
        try:
            stats = await self.cache_manager.get_stats()
            performance_metrics = self.cache_manager._performance_monitor.get_performance_metrics()
            
            # Calculate hit rate
            total_requests = stats.hit_count + stats.miss_count
            hit_rate = stats.hit_count / max(total_requests, 1)
            
            metrics = {
                "operation": "performance_metrics_collection",
                "status": "completed",
                "hit_rate": hit_rate,
                "total_keys": stats.total_keys,
                "memory_usage": stats.memory_usage,
                "connection_count": stats.connection_count,
                "operation_metrics": performance_metrics
            }
            
            # Log important metrics
            self.logger.info(
                "Cache performance metrics",
                hit_rate=hit_rate,
                total_keys=stats.total_keys,
                memory_usage_mb=stats.memory_usage / 1024 / 1024
            )
            
            return metrics
            
        except Exception as e:
            return {
                "operation": "performance_metrics_collection",
                "status": "failed",
                "error": str(e)
            }

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_cache_manager(config: Optional[CacheConfig] = None) -> RedisCacheManager:
    """Initialize Redis cache manager for production use"""
    if config is None:
        config = CacheConfig(
            redis_url=settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            timeout=settings.REDIS_TIMEOUT,
            retry_attempts=settings.REDIS_RETRY_ATTEMPTS,
            default_ttl=settings.CACHE_DEFAULT_TTL,
            compression_enabled=settings.CACHE_COMPRESSION_ENABLED,
            encryption_enabled=settings.CACHE_ENCRYPTION_ENABLED,
            key_prefix=settings.CACHE_KEY_PREFIX
        )
    
    # Validate configuration
    config_dict = {
        "redis_url": config.redis_url,
        "max_connections": config.max_connections,
        "timeout": config.timeout,
        "retry_attempts": config.retry_attempts,
        "default_ttl": config.default_ttl,
        "key_prefix": config.key_prefix
    }
    
    if not validate_cache_configuration(config_dict):
        raise ValueError("Invalid cache configuration")
    
    # Initialize cache manager
    cache_manager = RedisCacheManager(config)
    await cache_manager.initialize()
    
    # Initialize maintenance manager
    maintenance_manager = CacheMaintenanceManager(cache_manager)
    await maintenance_manager.start_maintenance_scheduler(
        interval_minutes=settings.CACHE_MAINTENANCE_INTERVAL_MINUTES
    )
    
    logger.info(
        "Cache manager initialized successfully",
        redis_url=config.redis_url,
        max_connections=config.max_connections,
        default_ttl=config.default_ttl
    )
    
    return cache_manager

async def health_check() -> Dict[str, Any]:
    """Cache manager health check endpoint"""
    try:
        # Create temporary cache manager for health check
        config = CacheConfig()
        cache_manager = RedisCacheManager(config)
        await cache_manager.initialize()
        
        health_status = await cache_manager.health_check()
        
        await cache_manager.cleanup()
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "component": "redis_cache_manager",
            "error": str(e)
        }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "RedisCacheManager",
    "CacheConfig",
    "CacheEntry",
    "CacheStats",
    "CacheRequest",
    "CacheResponse",
    "CacheError",
    "CacheConnectionError",
    "CacheTimeoutError",
    "CacheSerializationError",
    "CacheKeyError",
    "CacheValueError",
    "SerializationFormat",
    "CacheOperation",
    "CacheWarmer",
    "CacheMaintenanceManager",
    "cache_result",
    "invalidate_cache_on_change",
    "cache_transaction",
    "initialize_cache_manager",
    "health_check",
    "validate_cache_configuration",
    "create_cache_key_hash",
    "estimate_cache_size"
]