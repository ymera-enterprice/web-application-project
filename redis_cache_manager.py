"""
YMERA Enterprise Redis Cache Manager
Production-Ready Distributed Caching Layer for Multi-Agent System

Features:
- Distributed caching with Redis Cluster support
- Agent-specific namespacing and isolation
- Learning data caching with intelligent eviction
- Circuit breaker pattern for resilience
- Advanced serialization with compression
- Cache warming and prefetching
- Real-time metrics and monitoring
- Security and encryption for sensitive data
"""

import asyncio
import json
import pickle
import gzip
import hashlib
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Set, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager
import weakref
import threading
from concurrent.futures import ThreadPoolExecutor

import redis.asyncio as aioredis
from redis.asyncio.cluster import RedisCluster
from redis.asyncio.sentinel import Sentinel
from redis.backoff import ExponentialBackoff
from redis.retry import Retry
from redis.exceptions import (
    RedisError, ConnectionError, TimeoutError, 
    RedisClusterException, ResponseError
)

import orjson
import msgpack
from cryptography.fernet import Fernet
import zstd
import xxhash

from ymera_core.exceptions import YMERAException
from ymera_core.monitoring.metrics_collector import MetricsCollector
from ymera_core.utils.async_utils import AsyncRateLimiter, AsyncCircuitBreaker
from ymera_core.security.encryption import DataEncryption


class CacheMode(Enum):
    """Cache deployment modes"""
    STANDALONE = "standalone"
    CLUSTER = "cluster" 
    SENTINEL = "sentinel"


class SerializationMethod(Enum):
    """Serialization methods for cached data"""
    JSON = "json"
    ORJSON = "orjson"
    PICKLE = "pickle"
    MSGPACK = "msgpack"


class CompressionMethod(Enum):
    """Compression methods for cached data"""
    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"


class CacheStrategy(Enum):
    """Cache strategies for different data types"""
    LRU = "lru"          # Least Recently Used
    LFU = "lfu"          # Least Frequently Used
    FIFO = "fifo"        # First In, First Out
    TTL = "ttl"          # Time To Live
    ADAPTIVE = "adaptive" # Adaptive based on access patterns


@dataclass
class CacheConfig:
    """Redis cache configuration"""
    # Connection settings
    redis_url: str = "redis://localhost:6379"
    mode: CacheMode = CacheMode.STANDALONE
    cluster_nodes: List[str] = None
    sentinel_hosts: List[Tuple[str, int]] = None
    sentinel_service_name: str = "mymaster"
    
    # Connection pool settings
    max_connections: int = 100
    retry_on_timeout: bool = True
    retry_attempts: int = 3
    retry_backoff: float = 1.0
    health_check_interval: int = 30
    
    # Cache behavior
    default_ttl: int = 3600  # 1 hour
    max_ttl: int = 86400     # 24 hours
    min_ttl: int = 60        # 1 minute
    
    # Performance settings
    serialization_method: SerializationMethod = SerializationMethod.ORJSON
    compression_method: CompressionMethod = CompressionMethod.ZSTD
    compression_threshold: int = 1024  # Compress if data > 1KB
    
    # Security
    encrypt_sensitive_data: bool = True
    encryption_key: Optional[str] = None
    
    # Agent system specific
    agent_namespace_prefix: str = "ymera:agent"
    learning_namespace_prefix: str = "ymera:learning"
    session_namespace_prefix: str = "ymera:session"
    
    # Cache warming
    enable_cache_warming: bool = True
    warm_cache_on_startup: bool = True
    prefetch_popular_keys: bool = True
    
    # Monitoring
    enable_metrics: bool = True
    metrics_interval: int = 60
    slow_query_threshold: float = 0.1  # 100ms


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int
    ttl: Optional[int]
    tags: Set[str]
    agent_id: Optional[str] = None
    learning_context: Optional[str] = None
    compressed: bool = False
    encrypted: bool = False
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if not self.ttl:
            return False
        return time.time() - self.created_at > self.ttl
    
    def update_access(self):
        """Update access statistics"""
        self.accessed_at = time.time()
        self.access_count += 1


class CacheMetrics:
    """Cache performance metrics"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0
        self.errors = 0
        self.total_size = 0
        self.avg_response_time = 0.0
        self.slow_queries = 0
        self.last_reset = time.time()
        self._lock = threading.Lock()
    
    def record_hit(self, response_time: float = 0):
        with self._lock:
            self.hits += 1
            self._update_response_time(response_time)
    
    def record_miss(self, response_time: float = 0):
        with self._lock:
            self.misses += 1
            self._update_response_time(response_time)
    
    def record_set(self):
        with self._lock:
            self.sets += 1
    
    def record_delete(self):
        with self._lock:
            self.deletes += 1
    
    def record_eviction(self):
        with self._lock:
            self.evictions += 1
    
    def record_error(self):
        with self._lock:
            self.errors += 1
    
    def record_slow_query(self):
        with self._lock:
            self.slow_queries += 1
    
    def _update_response_time(self, response_time: float):
        if response_time > 0:
            total_operations = self.hits + self.misses
            if total_operations == 1:
                self.avg_response_time = response_time
            else:
                self.avg_response_time = (
                    (self.avg_response_time * (total_operations - 1) + response_time) 
                    / total_operations
                )
    
    def get_hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def reset(self):
        with self._lock:
            self.__init__()


class RedisCacheManager:
    """Enterprise-grade Redis cache manager for YMERA multi-agent system"""
    
    def __init__(self, config: CacheConfig = None, logger: logging.Logger = None):
        self.config = config or CacheConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Redis connections
        self.redis_client: Optional[Union[aioredis.Redis, RedisCluster]] = None
        self.sentinel: Optional[Sentinel] = None
        
        # Circuit breaker for resilience
        self.circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
            expected_exception=RedisError
        )
        
        # Rate limiter for request control
        self.rate_limiter = AsyncRateLimiter(
            max_requests=1000,
            time_window=60
        )
        
        # Metrics and monitoring
        self.metrics = CacheMetrics()
        self.metrics_collector: Optional[MetricsCollector] = None
        
        # Encryption for sensitive data
        self.encryption = DataEncryption() if self.config.encrypt_sensitive_data else None
        
        # Thread pool for CPU-intensive operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Cache warming and prefetching
        self.cache_warmer_task: Optional[asyncio.Task] = None
        self.prefetch_queue: asyncio.Queue = asyncio.Queue()
        
        # Agent-specific cache namespaces
        self.agent_namespaces: Set[str] = set()
        self.learning_cache_keys: Set[str] = set()
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
        
        # Key patterns for different data types
        self.key_patterns = {
            'agent_state': f"{self.config.agent_namespace_prefix}:{{agent_id}}:state",
            'agent_memory': f"{self.config.agent_namespace_prefix}:{{agent_id}}:memory:{{key}}",
            'learning_data': f"{self.config.learning_namespace_prefix}:{{context}}:{{key}}",
            'session_data': f"{self.config.session_namespace_prefix}:{{session_id}}:{{key}}",
            'analysis_cache': "ymera:analysis:{hash}",
            'code_cache': "ymera:code:{repo}:{branch}:{hash}",
            'embedding_cache': "ymera:embeddings:{model}:{hash}",
            'llm_response': "ymera:llm:{provider}:{model}:{hash}",
            'vulnerability_scan': "ymera:security:vulns:{repo}:{hash}",
            'deployment_cache': "ymera:deploy:{pipeline}:{stage}:{hash}"
        }
        
        self.logger.info("RedisCacheManager initialized with configuration", 
                        extra={"config": asdict(self.config)})
    
    async def initialize(self) -> None:
        """Initialize Redis connection and start background tasks"""
        try:
            self.logger.info("Initializing Redis cache manager...")
            
            # Initialize Redis connection based on mode
            await self._initialize_redis_connection()
            
            # Verify connection
            await self._verify_connection()
            
            # Initialize encryption if enabled
            if self.config.encrypt_sensitive_data:
                await self._initialize_encryption()
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Warm cache if enabled
            if self.config.warm_cache_on_startup:
                await self._warm_cache()
            
            self.logger.info("Redis cache manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis cache manager: {str(e)}")
            raise YMERAException(f"Cache initialization failed: {str(e)}")
    
    async def _initialize_redis_connection(self) -> None:
        """Initialize Redis connection based on configuration mode"""
        retry_policy = Retry(
            backoff=ExponentialBackoff(),
            retries=self.config.retry_attempts
        )
        
        if self.config.mode == CacheMode.CLUSTER:
            if not self.config.cluster_nodes:
                raise ValueError("Cluster nodes must be specified for cluster mode")
            
            self.redis_client = RedisCluster(
                startup_nodes=[
                    {"host": node.split(":")[0], "port": int(node.split(":")[1])}
                    for node in self.config.cluster_nodes
                ],
                decode_responses=False,
                retry=retry_policy,
                retry_on_timeout=self.config.retry_on_timeout,
                health_check_interval=self.config.health_check_interval,
                max_connections_per_node=self.config.max_connections
            )
            
        elif self.config.mode == CacheMode.SENTINEL:
            if not self.config.sentinel_hosts:
                raise ValueError("Sentinel hosts must be specified for sentinel mode")
            
            self.sentinel = Sentinel(
                self.config.sentinel_hosts,
                decode_responses=False,
                retry=retry_policy
            )
            self.redis_client = self.sentinel.master_for(
                self.config.sentinel_service_name,
                retry=retry_policy,
                retry_on_timeout=self.config.retry_on_timeout
            )
            
        else:  # STANDALONE mode
            self.redis_client = aioredis.from_url(
                self.config.redis_url,
                decode_responses=False,
                retry=retry_policy,
                retry_on_timeout=self.config.retry_on_timeout,
                health_check_interval=self.config.health_check_interval,
                max_connections=self.config.max_connections
            )
    
    async def _verify_connection(self) -> None:
        """Verify Redis connection is working"""
        try:
            await self.redis_client.ping()
            self.logger.info("Redis connection verified successfully")
        except Exception as e:
            self.logger.error(f"Redis connection verification failed: {str(e)}")
            raise
    
    async def _initialize_encryption(self) -> None:
        """Initialize encryption for sensitive data"""
        if not self.config.encryption_key:
            # Generate a new encryption key (in production, this should be from secure storage)
            self.config.encryption_key = Fernet.generate_key().decode()
            self.logger.warning("Generated new encryption key - store securely in production")
        
        self.encryption = DataEncryption(self.config.encryption_key)
    
    async def _start_background_tasks(self) -> None:
        """Start background tasks for maintenance and monitoring"""
        # Metrics collection task
        if self.config.enable_metrics:
            self.background_tasks.append(
                asyncio.create_task(self._metrics_collection_loop())
            )
        
        # Cache warming task
        if self.config.enable_cache_warming:
            self.background_tasks.append(
                asyncio.create_task(self._cache_warming_loop())
            )
        
        # Cleanup expired keys task
        self.background_tasks.append(
            asyncio.create_task(self._cleanup_expired_keys_loop())
        )
        
        # Health monitoring task
        self.background_tasks.append(
            asyncio.create_task(self._health_monitoring_loop())
        )
    
    async def _warm_cache(self) -> None:
        """Warm cache with frequently accessed data"""
        try:
            self.logger.info("Starting cache warming...")
            
            # Warm agent state data
            await self._warm_agent_caches()
            
            # Warm learning data
            await self._warm_learning_caches()
            
            # Warm frequently accessed configurations
            await self._warm_system_caches()
            
            self.logger.info("Cache warming completed")
            
        except Exception as e:
            self.logger.error(f"Cache warming failed: {str(e)}")
    
    async def _warm_agent_caches(self) -> None:
        """Warm cache with agent-specific data"""
        # This would typically load from database or other persistent storage
        # For now, we'll prepare the namespaces
        for agent_type in ['project_management', 'analysis', 'enhancement', 
                          'validation', 'documentation', 'security', 'deployment',
                          'monitoring', 'learning', 'communication', 'examination']:
            namespace = f"{self.config.agent_namespace_prefix}:{agent_type}"
            self.agent_namespaces.add(namespace)
    
    async def _warm_learning_caches(self) -> None:
        """Warm cache with learning engine data"""
        # Prepare learning data namespaces
        for context in ['patterns', 'feedback', 'models', 'knowledge', 'insights']:
            namespace = f"{self.config.learning_namespace_prefix}:{context}"
            await self.redis_client.sadd("ymera:learning:contexts", namespace)
    
    async def _warm_system_caches(self) -> None:
        """Warm cache with system configuration and metadata"""
        system_config = {
            "agents_count": len(self.agent_namespaces),
            "cache_initialized": datetime.utcnow().isoformat(),
            "features_enabled": [
                "multi_agent_support",
                "learning_engine", 
                "vector_search",
                "security_scanning"
            ]
        }
        await self.set("ymera:system:config", system_config, ttl=self.config.max_ttl)
    
    # Core cache operations
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache with comprehensive error handling"""
        start_time = time.time()
        
        try:
            async with self.rate_limiter:
                async with self.circuit_breaker:
                    result = await self._get_internal(key)
                    
                    response_time = time.time() - start_time
                    
                    if result is not None:
                        self.metrics.record_hit(response_time)
                        
                        # Track slow queries
                        if response_time > self.config.slow_query_threshold:
                            self.metrics.record_slow_query()
                            self.logger.warning(f"Slow cache get operation", 
                                              extra={"key": key, "response_time": response_time})
                        
                        return result
                    else:
                        self.metrics.record_miss(response_time)
                        return default
                        
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Batch get operation failed", 
                            extra={"keys": keys, "error": str(e)})
            return [None] * len(keys)
    
    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple key-value pairs at once"""
        try:
            async with self.circuit_breaker:
                # Serialize all values
                serialized_mapping = {}
                for key, value in mapping.items():
                    entry = CacheEntry(
                        key=key,
                        value=value,
                        created_at=time.time(),
                        accessed_at=time.time(),
                        access_count=1,
                        ttl=ttl or self.config.default_ttl,
                        tags=set()
                    )
                    serialized_mapping[key] = await self._serialize(entry)
                
                # Set all keys
                result = await self.redis_client.mset(serialized_mapping)
                
                # Set TTL for all keys if specified
                if ttl:
                    pipeline = self.redis_client.pipeline()
                    for key in mapping.keys():
                        pipeline.expire(key, ttl)
                    await pipeline.execute()
                
                if result:
                    self.metrics.sets += len(mapping)
                
                return result
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Batch set operation failed", 
                            extra={"keys": list(mapping.keys()), "error": str(e)})
            return False
    
    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys at once"""
        try:
            async with self.circuit_breaker:
                if not keys:
                    return 0
                
                deleted_count = await self.redis_client.delete(*keys)
                
                # Clean up metadata for deleted keys
                for key in keys:
                    await self._cleanup_key_metadata(key)
                
                self.metrics.deletes += deleted_count
                return deleted_count
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Batch delete operation failed", 
                            extra={"keys": keys, "error": str(e)})
            return 0
    
    # Advanced operations
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment a counter in cache"""
        try:
            async with self.circuit_breaker:
                result = await self.redis_client.incrby(key, amount)
                
                # Set TTL if this is a new key
                if result == amount and ttl:
                    await self.redis_client.expire(key, ttl)
                
                return result
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Increment operation failed", 
                            extra={"key": key, "amount": amount, "error": str(e)})
            return 0
    
    async def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement a counter in cache"""
        try:
            async with self.circuit_breaker:
                return await self.redis_client.decrby(key, amount)
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Decrement operation failed", 
                            extra={"key": key, "amount": amount, "error": str(e)})
            return 0
    
    async def push_list(self, key: str, values: List[Any], max_length: Optional[int] = None, ttl: Optional[int] = None) -> int:
        """Push values to a list in cache"""
        try:
            async with self.circuit_breaker:
                # Serialize values
                serialized_values = []
                for value in values:
                    entry = CacheEntry(
                        key=f"{key}:item",
                        value=value,
                        created_at=time.time(),
                        accessed_at=time.time(),
                        access_count=1,
                        ttl=ttl,
                        tags=set()
                    )
                    serialized_values.append(await self._serialize(entry))
                
                # Use pipeline for atomic operations
                pipeline = self.redis_client.pipeline()
                
                # Push values
                pipeline.lpush(key, *serialized_values)
                
                # Trim list if max_length specified
                if max_length:
                    pipeline.ltrim(key, 0, max_length - 1)
                
                # Set TTL if specified
                if ttl:
                    pipeline.expire(key, ttl)
                
                results = await pipeline.execute()
                return results[0]  # Length after push
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"List push operation failed", 
                            extra={"key": key, "error": str(e)})
            return 0
    
    async def pop_list(self, key: str, count: int = 1) -> List[Any]:
        """Pop values from a list in cache"""
        try:
            async with self.circuit_breaker:
                results = []
                
                for _ in range(count):
                    raw_data = await self.redis_client.lpop(key)
                    if raw_data is None:
                        break
                    
                    try:
                        deserialized = await self._deserialize(raw_data)
                        results.append(deserialized)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize list item: {str(e)}")
                        break
                
                return results
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"List pop operation failed", 
                            extra={"key": key, "count": count, "error": str(e)})
            return []
    
    async def get_list_range(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get a range of values from a list"""
        try:
            async with self.circuit_breaker:
                raw_items = await self.redis_client.lrange(key, start, end)
                results = []
                
                for raw_data in raw_items:
                    try:
                        deserialized = await self._deserialize(raw_data)
                        results.append(deserialized)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize list item: {str(e)}")
                
                return results
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"List range operation failed", 
                            extra={"key": key, "start": start, "end": end, "error": str(e)})
            return []
    
    # Set operations for tags and collections
    async def add_to_set(self, key: str, values: Union[Any, List[Any]], ttl: Optional[int] = None) -> int:
        """Add values to a set in cache"""
        try:
            async with self.circuit_breaker:
                if not isinstance(values, list):
                    values = [values]
                
                # Serialize values
                serialized_values = []
                for value in values:
                    entry = CacheEntry(
                        key=f"{key}:member",
                        value=value,
                        created_at=time.time(),
                        accessed_at=time.time(),
                        access_count=1,
                        ttl=ttl,
                        tags=set()
                    )
                    serialized_values.append(await self._serialize(entry))
                
                # Add to set
                result = await self.redis_client.sadd(key, *serialized_values)
                
                # Set TTL if specified
                if ttl:
                    await self.redis_client.expire(key, ttl)
                
                return result
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Set add operation failed", 
                            extra={"key": key, "error": str(e)})
            return 0
    
    async def get_set_members(self, key: str) -> Set[Any]:
        """Get all members of a set"""
        try:
            async with self.circuit_breaker:
                raw_members = await self.redis_client.smembers(key)
                members = set()
                
                for raw_data in raw_members:
                    try:
                        deserialized = await self._deserialize(raw_data)
                        members.add(deserialized)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize set member: {str(e)}")
                
                return members
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Set members operation failed", 
                            extra={"key": key, "error": str(e)})
            return set()
    
    async def remove_from_set(self, key: str, values: Union[Any, List[Any]]) -> int:
        """Remove values from a set"""
        try:
            async with self.circuit_breaker:
                if not isinstance(values, list):
                    values = [values]
                
                # Serialize values to match stored format
                serialized_values = []
                for value in values:
                    entry = CacheEntry(
                        key=f"{key}:member",
                        value=value,
                        created_at=time.time(),
                        accessed_at=time.time(),
                        access_count=1,
                        ttl=None,
                        tags=set()
                    )
                    serialized_values.append(await self._serialize(entry))
                
                return await self.redis_client.srem(key, *serialized_values)
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Set remove operation failed", 
                            extra={"key": key, "error": str(e)})
            return 0
    
    # Hash operations for structured data
    async def set_hash_field(self, key: str, field: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a field in a hash"""
        try:
            async with self.circuit_breaker:
                entry = CacheEntry(
                    key=f"{key}:{field}",
                    value=value,
                    created_at=time.time(),
                    accessed_at=time.time(),
                    access_count=1,
                    ttl=ttl,
                    tags=set()
                )
                serialized_value = await self._serialize(entry)
                
                result = await self.redis_client.hset(key, field, serialized_value)
                
                # Set TTL for the entire hash
                if ttl:
                    await self.redis_client.expire(key, ttl)
                
                return bool(result)
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Hash set operation failed", 
                            extra={"key": key, "field": field, "error": str(e)})
            return False
    
    async def get_hash_field(self, key: str, field: str) -> Any:
        """Get a field from a hash"""
        try:
            async with self.circuit_breaker:
                raw_data = await self.redis_client.hget(key, field)
                
                if raw_data is None:
                    return None
                
                return await self._deserialize(raw_data)
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Hash get operation failed", 
                            extra={"key": key, "field": field, "error": str(e)})
            return None
    
    async def get_hash_all(self, key: str) -> Dict[str, Any]:
        """Get all fields from a hash"""
        try:
            async with self.circuit_breaker:
                raw_hash = await self.redis_client.hgetall(key)
                result = {}
                
                for field, raw_data in raw_hash.items():
                    try:
                        if isinstance(field, bytes):
                            field = field.decode('utf-8')
                        result[field] = await self._deserialize(raw_data)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize hash field {field}: {str(e)}")
                
                return result
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Hash get all operation failed", 
                            extra={"key": key, "error": str(e)})
            return {}
    
    async def delete_hash_field(self, key: str, field: str) -> bool:
        """Delete a field from a hash"""
        try:
            async with self.circuit_breaker:
                return bool(await self.redis_client.hdel(key, field))
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Hash delete operation failed", 
                            extra={"key": key, "field": field, "error": str(e)})
            return False
    
    # Search and pattern operations
    async def get_keys_by_pattern(self, pattern: str, count: int = 1000) -> List[str]:
        """Get keys matching a pattern"""
        return await self._get_keys_by_pattern(pattern, count)
    
    async def _get_keys_by_pattern(self, pattern: str, count: int = 1000) -> List[str]:
        """Internal method to get keys by pattern"""
        try:
            async with self.circuit_breaker:
                keys = []
                
                if hasattr(self.redis_client, 'scan_iter'):
                    # Use scan for memory efficiency
                    async for key in self.redis_client.scan_iter(match=pattern, count=count):
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        keys.append(key)
                else:
                    # Fallback to keys (less memory efficient)
                    raw_keys = await self.redis_client.keys(pattern)
                    keys = [key.decode('utf-8') if isinstance(key, bytes) else key for key in raw_keys]
                
                return keys
                
        except Exception as e:
            self.logger.error(f"Pattern search failed", 
                            extra={"pattern": pattern, "error": str(e)})
            return []
    
    async def _delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern"""
        try:
            keys = await self._get_keys_by_pattern(pattern)
            if keys:
                return await self.delete_many(keys)
            return 0
        except Exception as e:
            self.logger.error(f"Pattern delete failed", 
                            extra={"pattern": pattern, "error": str(e)})
            return 0
    
    # Tag-based operations
    async def _update_tags(self, key: str, tags: Set[str]) -> None:
        """Update tag associations for a key"""
        for tag in tags:
            tag_key = f"ymera:tags:{tag}"
            await self.redis_client.sadd(tag_key, key)
    
    async def get_keys_by_tag(self, tag: str) -> List[str]:
        """Get all keys associated with a tag"""
        try:
            tag_key = f"ymera:tags:{tag}"
            raw_keys = await self.redis_client.smembers(tag_key)
            return [key.decode('utf-8') if isinstance(key, bytes) else key for key in raw_keys]
        except Exception as e:
            self.logger.error(f"Tag search failed", 
                            extra={"tag": tag, "error": str(e)})
            return []
    
    async def delete_by_tag(self, tag: str) -> int:
        """Delete all keys associated with a tag"""
        keys = await self.get_keys_by_tag(tag)
        if keys:
            deleted = await self.delete_many(keys)
            # Clean up the tag set
            await self.redis_client.delete(f"ymera:tags:{tag}")
            return deleted
        return 0
    
    # Agent tracking
    async def _track_agent_key(self, agent_id: str, key: str) -> None:
        """Track a key for an agent"""
        agent_keys_set = f"ymera:agent_keys:{agent_id}"
        await self.redis_client.sadd(agent_keys_set, key)
    
    async def _track_learning_key(self, context: str, key: str) -> None:
        """Track a key for learning context"""
        learning_keys_set = f"ymera:learning_keys:{context}"
        await self.redis_client.sadd(learning_keys_set, key)
        self.learning_cache_keys.add(key)
    
    async def _cleanup_key_metadata(self, key: str) -> None:
        """Clean up metadata when a key is deleted"""
        # Remove from tag associations
        tag_keys = await self._get_keys_by_pattern("ymera:tags:*")
        for tag_key in tag_keys:
            await self.redis_client.srem(tag_key, key)
        
        # Remove from agent tracking
        agent_key_sets = await self._get_keys_by_pattern("ymera:agent_keys:*")
        for agent_key_set in agent_key_sets:
            await self.redis_client.srem(agent_key_set, key)
        
        # Remove from learning tracking
        learning_key_sets = await self._get_keys_by_pattern("ymera:learning_keys:*")
        for learning_key_set in learning_key_sets:
            await self.redis_client.srem(learning_key_set, key)
        
        self.learning_cache_keys.discard(key)
    
    # Serialization and compression
    async def _serialize(self, entry: CacheEntry, encrypt: bool = False) -> bytes:
        """Serialize cache entry with optional compression and encryption"""
        try:
            # Serialize based on configuration
            if self.config.serialization_method == SerializationMethod.ORJSON:
                data = orjson.dumps(asdict(entry))
            elif self.config.serialization_method == SerializationMethod.MSGPACK:
                data = msgpack.packb(asdict(entry))
            elif self.config.serialization_method == SerializationMethod.PICKLE:
                data = pickle.dumps(entry)
            else:  # JSON fallback
                data = json.dumps(asdict(entry)).encode('utf-8')
            
            # Compress if data is large enough
            if (len(data) > self.config.compression_threshold and 
                self.config.compression_method != CompressionMethod.NONE):
                
                if self.config.compression_method == CompressionMethod.ZSTD:
                    data = zstd.compress(data)
                    entry.compressed = True
                elif self.config.compression_method == CompressionMethod.GZIP:
                    data = gzip.compress(data)
                    entry.compressed = True
            
            # Encrypt sensitive data
            if encrypt and self.encryption:
                data = self.encryption.encrypt(data)
                entry.encrypted = True
            
            return data
            
        except Exception as e:
            self.logger.error(f"Serialization failed: {str(e)}")
            raise
    
    async def _deserialize(self, data: bytes) -> Any:
        """Deserialize cache entry with decompression and decryption"""
        try:
            # Check if data is encrypted (basic heuristic)
            if self.encryption and len(data) > 100 and data.startswith(b'gAAAAA'):
                try:
                    data = self.encryption.decrypt(data)
                except Exception:
                    pass  # Not encrypted or different encryption
            
            # Check if data is compressed (basic heuristics)
            is_zstd = data.startswith(b'(\xb5/\xfd')
            is_gzip = data.startswith(b'\x1f\x8b')
            
            if is_zstd:
                data = zstd.decompress(data)
            elif is_gzip:
                data = gzip.decompress(data)
            
            # Deserialize based on data format detection
            try:
                # Try orjson first (fastest)
                entry_dict = orjson.loads(data)
                if isinstance(entry_dict, dict) and 'key' in entry_dict:
                    return entry_dict['value']
            except:
                pass
            
            try:
                # Try msgpack
                entry_dict = msgpack.unpackb(data, raw=False)
                if isinstance(entry_dict, dict) and 'key' in entry_dict:
                    return entry_dict['value']
            except:
                pass
            
            try:
                # Try pickle
                entry = pickle.loads(data)
                if isinstance(entry, CacheEntry):
                    return entry.value
            except:
                pass
            
            # Fallback to JSON
            entry_dict = json.loads(data.decode('utf-8'))
            if isinstance(entry_dict, dict) and 'key' in entry_dict:
                return entry_dict['value']
            
            return entry_dict
            
        except Exception as e:
            self.logger.error(f"Deserialization failed: {str(e)}")
            raise
    
    # Background tasks
    async def _metrics_collection_loop(self) -> None:
        """Background task for metrics collection"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.metrics_interval)
                await self._collect_redis_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {str(e)}")
    
    async def _collect_redis_metrics(self) -> None:
        """Collect Redis-specific metrics"""
        try:
            info = await self.redis_client.info()
            
            # Memory usage
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            
            # Connection stats
            connected_clients = info.get('connected_clients', 0)
            
            # Operation stats
            total_commands_processed = info.get('total_commands_processed', 0)
            
            # Key space stats
            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            
            # Log metrics
            self.logger.info("Redis metrics collected", extra={
                'used_memory': used_memory,
                'max_memory': max_memory,
                'connected_clients': connected_clients,
                'total_commands': total_commands_processed,
                'keyspace_hits': keyspace_hits,
                'keyspace_misses': keyspace_misses,
                'cache_hit_ratio': self.metrics.get_hit_ratio(),
                'cache_operations': {
                    'hits': self.metrics.hits,
                    'misses': self.metrics.misses,
                    'sets': self.metrics.sets,
                    'deletes': self.metrics.deletes,
                    'errors': self.metrics.errors
                }
            })
            
        except Exception as e:
            self.logger.error(f"Failed to collect Redis metrics: {str(e)}")
    
    async def _cache_warming_loop(self) -> None:
        """Background task for cache warming"""
        while not self.shutdown_event.is_set():
            try:
                # Process prefetch queue
                try:
                    key_to_prefetch = await asyncio.wait_for(
                        self.prefetch_queue.get(), 
                        timeout=10.0
                    )
                    await self._prefetch_key(key_to_prefetch)
                except asyncio.TimeoutError:
                    # No items to prefetch, continue
                    pass
                
                # Periodic cache warming
                await asyncio.sleep(300)  # Every 5 minutes
                await self._warm_popular_keys()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cache warming error: {str(e)}")
    
    async def _prefetch_key(self, key: str) -> None:
        """Prefetch a specific key"""
        # This would typically load from database or compute
        # For now, just log the prefetch request
        self.logger.debug(f"Prefetching key: {key}")
    
    async def _warm_popular_keys(self) -> None:
        """Warm cache with popular keys"""
        if self.config.prefetch_popular_keys:
            # Get popular keys from access patterns
            popular_patterns = [
                "ymera:system:*",
                "ymera:agent:*/state",
                "ymera:learning:patterns:*"
            ]
            
            for pattern in popular_patterns:
                keys = await self._get_keys_by_pattern(pattern, count=100)
                for key in keys[:10]:  # Warm top 10 keys per pattern
                    if not await self.exists(key):
                        await self.prefetch_queue.put(key)
    
    async def _cleanup_expired_keys_loop(self) -> None:
        """Background task for cleaning up expired keys"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(3600)  # Every hour
                await self._cleanup_expired_keys()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Expired keys cleanup error: {str(e)}")
    
    async def _cleanup_expired_keys(self) -> None:
        """Clean up expired keys and metadata"""
        try:
            # Clean up agent tracking sets
            agent_key_patterns = await self._get_keys_by_pattern("ymera:agent_keys:*")
            for agent_set_key in agent_key_patterns:
                await self._cleanup_expired_from_set(agent_set_key)
            
            # Clean up learning tracking sets
            learning_key_patterns = await self._get_keys_by_pattern("ymera:learning_keys:*")
            for learning_set_key in learning_key_patterns:
                await self._cleanup_expired_from_set(learning_set_key)
            
            # Clean up tag sets
            tag_key_patterns = await self._get_keys_by_pattern("ymera:tags:*")
            for tag_set_key in tag_key_patterns:
                await self._cleanup_expired_from_set(tag_set_key)
            
            self.logger.info("Expired keys cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Expired keys cleanup failed: {str(e)}")
    
    async def _cleanup_expired_from_set(self, set_key: str) -> None:
        """Clean up expired keys from a tracking set"""
        try:
            members = await self.redis_client.smembers(set_key)
            expired_keys = []
            
            for member in members:
                if isinstance(member, bytes):
                    member = member.decode('utf-8')
                
                ttl = await self.redis_client.ttl(member)
                if ttl == -2:  # Key doesn't exist
                    expired_keys.append(member)
            
            if expired_keys:
                await self.redis_client.srem(set_key, *expired_keys)
                self.logger.debug(f"Cleaned {len(expired_keys)} expired keys from {set_key}")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired keys from {set_key}: {str(e)}")
    
    async def _health_monitoring_loop(self) -> None:
        """Background task for health monitoring"""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error: {str(e)}")
    
    async def _perform_health_check(self) -> None:
        """Perform health check on Redis connection"""
        try:
            start_time = time.time()
            await self.redis_client.ping()
            response_time = time.time() - start_time
            
            if response_time > self.config.slow_query_threshold:
                self.logger.warning(f"Redis health check slow", 
                                  extra={"response_time": response_time})
            else:
                self.logger.debug(f"Redis health check passed", 
                                extra={"response_time": response_time})
                
        except Exception as e:
            self.logger.error(f"Redis health check failed: {str(e)}")
            self.metrics.record_error()
    
    # Public utility methods
    async def get_cache_size(self) -> Dict[str, Any]:
        """Get cache size information"""
        try:
            info = await self.redis_client.info('memory')
            keyspace_info = await self.redis_client.info('keyspace')
            
            total_keys = 0
            for db_key, db_info in keyspace_info.items():
                if db_key.startswith('db'):
                    # Parse "keys=X,expires=Y,avg_ttl=Z"
                    keys_count = int(db_info.split(',')[0].split('=')[1])
                    total_keys += keys_count
            
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'used_memory_peak': info.get('used_memory_peak', 0),
                'total_keys': total_keys,
                'fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                'cache_hit_ratio': self.metrics.get_hit_ratio(),
                'operations': {
                    'hits': self.metrics.hits,
                    'misses': self.metrics.misses,
                    'sets': self.metrics.sets,
                    'deletes': self.metrics.deletes
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get cache size: {str(e)}")
            return {}
    
    async def flush_cache(self, pattern: Optional[str] = None) -> bool:
        """Flush cache entries matching pattern or all if no pattern"""
        try:
            if pattern:
                deleted = await self._delete_pattern(pattern)
                self.logger.info(f"Flushed {deleted} keys matching pattern: {pattern}")
                return deleted > 0
            else:
                await self.redis_client.flushdb()
                self.logger.info("Flushed entire cache database")
                self.metrics.reset()
                return True
        except Exception as e:
            self.logger.error(f"Cache flush failed: {str(e)}")
            return False
            self.logger.error(f"Cache get operation failed", 
                            extra={"key": key, "error": str(e)})
            return default
    
    async def _get_internal(self, key: str) -> Any:
        """Internal get operation with deserialization"""
        raw_data = await self.redis_client.get(key)
        
        if raw_data is None:
            return None
        
        # Deserialize data
        try:
            return await self._deserialize(raw_data)
        except Exception as e:
            self.logger.error(f"Failed to deserialize cached data", 
                            extra={"key": key, "error": str(e)})
            # Remove corrupted data
            await self.redis_client.delete(key)
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        agent_id: Optional[str] = None,
        learning_context: Optional[str] = None,
        encrypt: bool = False
    ) -> bool:
        """Set value in cache with advanced options"""
        start_time = time.time()
        
        try:
            async with self.rate_limiter:
                async with self.circuit_breaker:
                    success = await self._set_internal(
                        key, value, ttl, tags, agent_id, learning_context, encrypt
                    )
                    
                    if success:
                        self.metrics.record_set()
                        
                        # Track slow operations
                        response_time = time.time() - start_time
                        if response_time > self.config.slow_query_threshold:
                            self.metrics.record_slow_query()
                            self.logger.warning(f"Slow cache set operation", 
                                              extra={"key": key, "response_time": response_time})
                    
                    return success
                    
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Cache set operation failed", 
                            extra={"key": key, "error": str(e)})
            return False
    
    async def _set_internal(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        agent_id: Optional[str] = None,
        learning_context: Optional[str] = None,
        encrypt: bool = False
    ) -> bool:
        """Internal set operation with serialization"""
        # Determine TTL
        if ttl is None:
            ttl = self.config.default_ttl
        ttl = max(self.config.min_ttl, min(ttl, self.config.max_ttl))
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            accessed_at=time.time(),
            access_count=1,
            ttl=ttl,
            tags=tags or set(),
            agent_id=agent_id,
            learning_context=learning_context
        )
        
        # Serialize data
        serialized_data = await self._serialize(entry, encrypt)
        
        # Store in Redis
        result = await self.redis_client.setex(key, ttl, serialized_data)
        
        # Update metadata if using tags or agent tracking
        if tags:
            await self._update_tags(key, tags)
        
        if agent_id:
            await self._track_agent_key(agent_id, key)
        
        if learning_context:
            await self._track_learning_key(learning_context, key)
        
        return result
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            async with self.circuit_breaker:
                result = await self.redis_client.delete(key)
                
                if result:
                    self.metrics.record_delete()
                    
                    # Clean up metadata
                    await self._cleanup_key_metadata(key)
                
                return bool(result)
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Cache delete operation failed", 
                            extra={"key": key, "error": str(e)})
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            async with self.circuit_breaker:
                return bool(await self.redis_client.exists(key))
        except Exception as e:
            self.logger.error(f"Cache exists check failed", 
                            extra={"key": key, "error": str(e)})
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key"""
        try:
            async with self.circuit_breaker:
                return bool(await self.redis_client.expire(key, ttl))
        except Exception as e:
            self.logger.error(f"Cache expire operation failed", 
                            extra={"key": key, "ttl": ttl, "error": str(e)})
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for key"""
        try:
            async with self.circuit_breaker:
                return await self.redis_client.ttl(key)
        except Exception as e:
            self.logger.error(f"Cache TTL check failed", 
                            extra={"key": key, "error": str(e)})
            return -1
    
    # Agent-specific operations
    async def set_agent_state(self, agent_id: str, state_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set agent state in cache"""
        key = self.key_patterns['agent_state'].format(agent_id=agent_id)
        return await self.set(key, state_data, ttl=ttl, agent_id=agent_id, tags={'agent_state'})
    
    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent state from cache"""
        key = self.key_patterns['agent_state'].format(agent_id=agent_id)
        return await self.get(key)
    
    async def set_agent_memory(self, agent_id: str, memory_key: str, memory_data: Any, ttl: Optional[int] = None) -> bool:
        """Set agent memory in cache"""
        key = self.key_patterns['agent_memory'].format(agent_id=agent_id, key=memory_key)
        return await self.set(key, memory_data, ttl=ttl, agent_id=agent_id, tags={'agent_memory'})
    
    async def get_agent_memory(self, agent_id: str, memory_key: str) -> Any:
        """Get agent memory from cache"""
        key = self.key_patterns['agent_memory'].format(agent_id=agent_id, key=memory_key)
        return await self.get(key)
    
    async def clear_agent_cache(self, agent_id: str) -> int:
        """Clear all cache entries for an agent"""
        pattern = f"{self.config.agent_namespace_prefix}:{agent_id}:*"
        return await self._delete_pattern(pattern)
    
    # Learning engine operations
    async def set_learning_data(self, context: str, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Set learning data in cache"""
        cache_key = self.key_patterns['learning_data'].format(context=context, key=key)
        return await self.set(cache_key, data, ttl=ttl, learning_context=context, tags={'learning_data'})
    
    async def get_learning_data(self, context: str, key: str) -> Any:
        """Get learning data from cache"""
        cache_key = self.key_patterns['learning_data'].format(context=context, key=key)
        return await self.get(cache_key)
    
    async def get_learning_keys(self, context: str) -> List[str]:
        """Get all learning keys for a context"""
        pattern = self.key_patterns['learning_data'].format(context=context, key="*")
        return await self._get_keys_by_pattern(pattern)
    
    async def clear_learning_context(self, context: str) -> int:
        """Clear all learning data for a context"""
        pattern = f"{self.config.learning_namespace_prefix}:{context}:*"
        return await self._delete_pattern(pattern)
    
    # Specialized cache operations for different data types
    async def cache_analysis_result(self, content_hash: str, analysis_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache code analysis result"""
        key = self.key_patterns['analysis_cache'].format(hash=content_hash)
        return await self.set(key, analysis_data, ttl=ttl, tags={'analysis'})
    
    async def get_cached_analysis(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis result"""
        key = self.key_patterns['analysis_cache'].format(hash=content_hash)
        return await self.get(key)
    
    async def cache_code_content(self, repo: str, branch: str, content_hash: str, code_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache code content and metadata"""
        key = self.key_patterns['code_cache'].format(repo=repo, branch=branch, hash=content_hash)
        return await self.set(key, code_data, ttl=ttl, tags={'code_content'})
    
    async def get_cached_code(self, repo: str, branch: str, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached code content"""
        key = self.key_patterns['code_cache'].format(repo=repo, branch=branch, hash=content_hash)
        return await self.get(key)
    
    async def cache_embedding(self, model: str, content_hash: str, embedding: List[float], ttl: Optional[int] = None) -> bool:
        """Cache text embedding"""
        key = self.key_patterns['embedding_cache'].format(model=model, hash=content_hash)
        return await self.set(key, embedding, ttl=ttl, tags={'embeddings'})
    
    async def get_cached_embedding(self, model: str, content_hash: str) -> Optional[List[float]]:
        """Get cached embedding"""
        key = self.key_patterns['embedding_cache'].format(model=model, hash=content_hash)
        return await self.get(key)
    
    async def cache_llm_response(self, provider: str, model: str, request_hash: str, response_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache LLM response"""
        key = self.key_patterns['llm_response'].format(provider=provider, model=model, hash=request_hash)
        return await self.set(key, response_data, ttl=ttl, tags={'llm_responses'})
    
    async def get_cached_llm_response(self, provider: str, model: str, request_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached LLM response"""
        key = self.key_patterns['llm_response'].format(provider=provider, model=model, hash=request_hash)
        return await self.get(key)
    
    async def cache_vulnerability_scan(self, repo: str, scan_hash: str, scan_results: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Cache vulnerability scan results"""
        key = self.key_patterns['vulnerability_scan'].format(repo=repo, hash=scan_hash)
        return await self.set(key, scan_results, ttl=ttl, tags={'security', 'vulnerability_scans'})
    
    async def get_cached_vulnerability_scan(self, repo: str, scan_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached vulnerability scan results"""
        key = self.key_patterns['vulnerability_scan'].format(repo=repo, hash=scan_hash)
        return await self.get(key)
    
    # Batch operations
    async def mget(self, keys: List[str]) -> List[Any]:
        """Get multiple keys at once"""
        try:
            async with self.circuit_breaker:
                raw_results = await self.redis_client.mget(keys)
                results = []
                
                for i, raw_data in enumerate(raw_results):
                    if raw_data is not None:
                        try:
                            deserialized = await self._deserialize(raw_data)
                            results.append(deserialized)
                            self.metrics.record_hit()
                        except Exception as e:
                            self.logger.error(f"Failed to deserialize data for key {keys[i]}: {str(e)}")
                            results.append(None)
                            self.metrics.record_error()
                    else:
                        results.append(None)
                        self.metrics.record_miss()
                
                return results
                
        except Exception as e:
            self.metrics.record_error() self.metrics.record_error()
            self.logger.error(f"Batch get operation failed", extra={"keys": keys, "error": str(e)})
            return [None] * len(keys)
    
    async def mset(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple keys at once"""
        try:
            async with self.circuit_breaker:
                # Prepare data for batch operation
                pipe = self.redis_client.pipeline()
                
                for key, value in data.items():
                    entry = CacheEntry(
                        key=key,
                        value=value,
                        created_at=time.time(),
                        accessed_at=time.time(),
                        access_count=1,
                        ttl=ttl or self.config.default_ttl,
                        tags=set(),
                        agent_id=None,
                        learning_context=None
                    )
                    
                    serialized_data = await self._serialize(entry, False)
                    pipe.setex(key, ttl or self.config.default_ttl, serialized_data)
                
                results = await pipe.execute()
                success = all(results)
                
                if success:
                    self.metrics.sets += len(data)
                
                return success
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Batch set operation failed", extra={"keys": list(data.keys()), "error": str(e)})
            return False
    
    async def mdel(self, keys: List[str]) -> int:
        """Delete multiple keys at once"""
        try:
            async with self.circuit_breaker:
                deleted = await self.redis_client.delete(*keys)
                
                if deleted > 0:
                    self.metrics.deletes += deleted
                    
                    # Clean up metadata for deleted keys
                    for key in keys:
                        await self._cleanup_key_metadata(key)
                
                return deleted
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Batch delete operation failed", extra={"keys": keys, "error": str(e)})
            return 0
    
    # Tag-based operations
    async def get_keys_by_tag(self, tag: str, count: int = 100) -> List[str]:
        """Get keys associated with a specific tag"""
        try:
            tag_key = f"ymera:tags:{tag}"
            members = await self.redis_client.smembers(tag_key)
            
            # Convert bytes to strings and limit count
            keys = []
            for member in members:
                if isinstance(member, bytes):
                    keys.append(member.decode('utf-8'))
                else:
                    keys.append(member)
                
                if len(keys) >= count:
                    break
            
            return keys
            
        except Exception as e:
            self.logger.error(f"Failed to get keys by tag {tag}: {str(e)}")
            return []
    
    async def clear_by_tag(self, tag: str) -> int:
        """Clear all cache entries with a specific tag"""
        try:
            keys = await self.get_keys_by_tag(tag, count=10000)  # Get more keys for clearing
            
            if keys:
                deleted = await self.mdel(keys)
                
                # Remove the tag set itself
                tag_key = f"ymera:tags:{tag}"
                await self.redis_client.delete(tag_key)
                
                self.logger.info(f"Cleared {deleted} keys with tag: {tag}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to clear keys by tag {tag}: {str(e)}")
            return 0
    
    # Atomic operations
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomically increment a numeric value"""
        try:
            async with self.circuit_breaker:
                pipe = self.redis_client.pipeline()
                pipe.incrby(key, amount)
                
                if ttl:
                    pipe.expire(key, ttl)
                
                results = await pipe.execute()
                return results[0]
                
        except Exception as e:
            self.logger.error(f"Increment operation failed", extra={"key": key, "amount": amount, "error": str(e)})
            return 0
    
    async def decrement(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomically decrement a numeric value"""
        return await self.increment(key, -amount, ttl)
    
    async def append_to_list(self, key: str, value: Any, max_length: Optional[int] = None, ttl: Optional[int] = None) -> bool:
        """Append value to a cached list"""
        try:
            async with self.circuit_breaker:
                pipe = self.redis_client.pipeline()
                serialized_value = await self._serialize_value(value)
                
                pipe.rpush(key, serialized_value)
                
                if max_length:
                    pipe.ltrim(key, -max_length, -1)
                
                if ttl:
                    pipe.expire(key, ttl)
                
                await pipe.execute()
                return True
                
        except Exception as e:
            self.logger.error(f"List append operation failed", extra={"key": key, "error": str(e)})
            return False
    
    async def get_list(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get list from cache with optional range"""
        try:
            async with self.circuit_breaker:
                raw_values = await self.redis_client.lrange(key, start, end)
                
                if not raw_values:
                    self.metrics.record_miss()
                    return []
                
                self.metrics.record_hit()
                values = []
                
                for raw_value in raw_values:
                    try:
                        deserialized = await self._deserialize_value(raw_value)
                        values.append(deserialized)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize list item: {str(e)}")
                        continue
                
                return values
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"List get operation failed", extra={"key": key, "error": str(e)})
            return []
    
    async def add_to_set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Add value to a cached set"""
        try:
            async with self.circuit_breaker:
                serialized_value = await self._serialize_value(value)
                
                pipe = self.redis_client.pipeline()
                pipe.sadd(key, serialized_value)
                
                if ttl:
                    pipe.expire(key, ttl)
                
                results = await pipe.execute()
                return bool(results[0])
                
        except Exception as e:
            self.logger.error(f"Set add operation failed", extra={"key": key, "error": str(e)})
            return False
    
    async def get_set(self, key: str) -> Set[Any]:
        """Get set from cache"""
        try:
            async with self.circuit_breaker:
                raw_values = await self.redis_client.smembers(key)
                
                if not raw_values:
                    self.metrics.record_miss()
                    return set()
                
                self.metrics.record_hit()
                values = set()
                
                for raw_value in raw_values:
                    try:
                        deserialized = await self._deserialize_value(raw_value)
                        values.add(deserialized)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize set item: {str(e)}")
                        continue
                
                return values
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Set get operation failed", extra={"key": key, "error": str(e)})
            return set()
    
    # Hash operations for structured data
    async def hset(self, key: str, field: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set field in hash"""
        try:
            async with self.circuit_breaker:
                serialized_value = await self._serialize_value(value)
                
                pipe = self.redis_client.pipeline()
                pipe.hset(key, field, serialized_value)
                
                if ttl:
                    pipe.expire(key, ttl)
                
                results = await pipe.execute()
                return bool(results[0])
                
        except Exception as e:
            self.logger.error(f"Hash set operation failed", extra={"key": key, "field": field, "error": str(e)})
            return False
    
    async def hget(self, key: str, field: str) -> Any:
        """Get field from hash"""
        try:
            async with self.circuit_breaker:
                raw_value = await self.redis_client.hget(key, field)
                
                if raw_value is None:
                    self.metrics.record_miss()
                    return None
                
                self.metrics.record_hit()
                return await self._deserialize_value(raw_value)
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Hash get operation failed", extra={"key": key, "field": field, "error": str(e)})
            return None
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all fields from hash"""
        try:
            async with self.circuit_breaker:
                raw_data = await self.redis_client.hgetall(key)
                
                if not raw_data:
                    self.metrics.record_miss()
                    return {}
                
                self.metrics.record_hit()
                result = {}
                
                for field, raw_value in raw_data.items():
                    if isinstance(field, bytes):
                        field = field.decode('utf-8')
                    
                    try:
                        result[field] = await self._deserialize_value(raw_value)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize hash field {field}: {str(e)}")
                        continue
                
                return result
                
        except Exception as e:
            self.metrics.record_error()
            self.logger.error(f"Hash getall operation failed", extra={"key": key, "error": str(e)})
            return {}
    
    # Search and pattern matching
    async def search_keys(self, pattern: str, count: int = 100) -> List[str]:
        """Search for keys matching pattern"""
        try:
            if self.config.mode == CacheMode.CLUSTER:
                # For cluster mode, we need to search across all nodes
                keys = []
                async for key_batch in self.redis_client.scan_iter(match=pattern, count=count):
                    keys.extend(key_batch)
                    if len(keys) >= count:
                        break
                return keys[:count]
            else:
                # For standalone/sentinel mode
                cursor = 0
                keys = []
                
                while len(keys) < count:
                    cursor, batch_keys = await self.redis_client.scan(cursor, match=pattern, count=min(100, count - len(keys)))
                    keys.extend(batch_keys)
                    
                    if cursor == 0:  # Scan completed
                        break
                
                return [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys[:count]]
                
        except Exception as e:
            self.logger.error(f"Key search failed", extra={"pattern": pattern, "error": str(e)})
            return []
    
    # Cache statistics and monitoring
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            cache_size = await self.get_cache_size()
            
            # Get Redis info
            info = await self.redis_client.info()
            
            # Calculate derived metrics
            uptime = info.get('uptime_in_seconds', 0)
            connected_clients = info.get('connected_clients', 0)
            
            stats = {
                'cache_metrics': {
                    'hit_ratio': self.metrics.get_hit_ratio(),
                    'operations': {
                        'hits': self.metrics.hits,
                        'misses': self.metrics.misses,
                        'sets': self.metrics.sets,
                        'deletes': self.metrics.deletes,
                        'errors': self.metrics.errors,
                        'slow_queries': self.metrics.slow_queries
                    },
                    'average_response_time': self.metrics.get_avg_response_time()
                },
                'memory_usage': cache_size,
                'redis_info': {
                    'version': info.get('redis_version', 'unknown'),
                    'uptime_seconds': uptime,
                    'uptime_days': uptime // 86400,
                    'connected_clients': connected_clients,
                    'total_commands_processed': info.get('total_commands_processed', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'evicted_keys': info.get('evicted_keys', 0),
                    'expired_keys': info.get('expired_keys', 0)
                },
                'configuration': {
                    'mode': self.config.mode.value,
                    'default_ttl': self.config.default_ttl,
                    'max_connections': self.config.max_connections,
                    'retry_attempts': self.config.retry_attempts,
                    'serialization_method': self.config.serialization_method.value,
                    'compression_method': self.config.compression_method.value,
                    'encryption_enabled': self.config.encryption_enabled
                },
                'background_tasks': {
                    'prefetch_queue_size': self.prefetch_queue.qsize(),
                    'background_tasks_running': len([task for task in self.background_tasks if not task.done()])
                }
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {str(e)}")
            return {}
    
    async def reset_stats(self) -> bool:
        """Reset cache statistics"""
        try:
            self.metrics.reset()
            self.logger.info("Cache statistics reset")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset stats: {str(e)}")
            return False
    
    # Administrative operations
    async def backup_keys(self, pattern: str, file_path: str) -> bool:
        """Backup keys matching pattern to file"""
        try:
            keys = await self.search_keys(pattern, count=10000)
            
            if not keys:
                self.logger.warning(f"No keys found matching pattern: {pattern}")
                return False
            
            backup_data = {}
            
            # Get all matching keys with their data
            for key in keys:
                try:
                    value = await self.get(key)
                    ttl_remaining = await self.ttl(key)
                    
                    backup_data[key] = {
                        'value': value,
                        'ttl': ttl_remaining if ttl_remaining > 0 else None,
                        'backed_up_at': time.time()
                    }
                except Exception as e:
                    self.logger.error(f"Failed to backup key {key}: {str(e)}")
                    continue
            
            # Write to file
            with open(file_path, 'wb') as f:
                # Use compression for backup files
                compressed_data = gzip.compress(orjson.dumps(backup_data))
                f.write(compressed_data)
            
            self.logger.info(f"Backed up {len(backup_data)} keys to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup operation failed: {str(e)}")
            return False
    
    async def restore_keys(self, file_path: str, overwrite: bool = False) -> int:
        """Restore keys from backup file"""
        try:
            with open(file_path, 'rb') as f:
                compressed_data = f.read()
                backup_data = orjson.loads(gzip.decompress(compressed_data))
            
            restored_count = 0
            
            for key, data in backup_data.items():
                try:
                    # Check if key exists and handle overwrite policy
                    if not overwrite and await self.exists(key):
                        self.logger.debug(f"Skipping existing key: {key}")
                        continue
                    
                    value = data['value']
                    ttl = data.get('ttl')
                    
                    success = await self.set(key, value, ttl=ttl)
                    if success:
                        restored_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Failed to restore key {key}: {str(e)}")
                    continue
            
            self.logger.info(f"Restored {restored_count} keys from {file_path}")
            return restored_count
            
        except Exception as e:
            self.logger.error(f"Restore operation failed: {str(e)}")
            return 0
    
    # Context managers for batch operations
    @asynccontextmanager
    async def batch_operation(self):
        """Context manager for efficient batch operations"""
        pipe = self.redis_client.pipeline()
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            self.logger.error(f"Batch operation failed: {str(e)}")
            raise
    
    @asynccontextmanager
    async def transaction(self, *watch_keys):
        """Context manager for Redis transactions"""
        async with self.redis_client.pipeline(transaction=True) as pipe:
            if watch_keys:
                await pipe.watch(*watch_keys)
            try:
                yield pipe
                await pipe.execute()
            except Exception as e:
                self.logger.error(f"Transaction failed: {str(e)}")
                raise
    
    # Helper methods for internal operations
    async def _serialize(self, entry: CacheEntry, encrypt: bool = False) -> bytes:
        """Serialize cache entry"""
        # Convert entry to dict for serialization
        entry_dict = asdict(entry)
        
        # Handle set serialization
        if entry_dict['tags']:
            entry_dict['tags'] = list(entry_dict['tags'])
        
        # Serialize based on method
        if self.config.serialization_method == SerializationMethod.ORJSON:
            data = orjson.dumps(entry_dict)
        elif self.config.serialization_method == SerializationMethod.MSGPACK:
            data = msgpack.packb(entry_dict)
        elif self.config.serialization_method == SerializationMethod.PICKLE:
            data = pickle.dumps(entry_dict)
        else:  # JSON fallback
            data = json.dumps(entry_dict).encode('utf-8')
        
        # Apply compression
        if self.config.compression_method == CompressionMethod.GZIP:
            data = gzip.compress(data)
        elif self.config.compression_method == CompressionMethod.ZSTD:
            data = zstd.compress(data)
        
        # Apply encryption if requested
        if encrypt and self.encryption:
            data = self.encryption.encrypt(data)
        
        return data
    
    async def _deserialize(self, data: bytes) -> Any:
        """Deserialize cache entry"""
        try:
            # Decrypt if encrypted
            if self.encryption and self.config.encryption_enabled:
                try:
                    data = self.encryption.decrypt(data)
                except Exception:
                    # Data might not be encrypted, continue
                    pass
            
            # Decompress
            if self.config.compression_method == CompressionMethod.GZIP:
                try:
                    data = gzip.decompress(data)
                except Exception:
                    # Data might not be compressed, continue
                    pass
            elif self.config.compression_method == CompressionMethod.ZSTD:
                try:
                    data = zstd.decompress(data)
                except Exception:
                    # Data might not be compressed, continue
                    pass
            
            # Deserialize based on method
            if self.config.serialization_method == SerializationMethod.ORJSON:
                entry_dict = orjson.loads(data)
            elif self.config.serialization_method == SerializationMethod.MSGPACK:
                entry_dict = msgpack.unpackb(data, raw=False)
            elif self.config.serialization_method == SerializationMethod.PICKLE:
                entry_dict = pickle.loads(data)
            else:  # JSON fallback
                entry_dict = json.loads(data.decode('utf-8'))
            
            # Convert back to set if needed
            if entry_dict.get('tags'):
                entry_dict['tags'] = set(entry_dict['tags'])
            
            # Create CacheEntry object
            cache_entry = CacheEntry(**entry_dict)
            
            # Update access statistics
            cache_entry.accessed_at = time.time()
            cache_entry.access_count += 1
            
            return cache_entry.value
            
        except Exception as e:
            self.logger.error(f"Deserialization failed: {str(e)}")
            raise
    
    async def _serialize_value(self, value: Any) -> bytes:
        """Serialize a single value (for list/set operations)"""
        if self.config.serialization_method == SerializationMethod.ORJSON:
            return orjson.dumps(value)
        elif self.config.serialization_method == SerializationMethod.MSGPACK:
            return msgpack.packb(value)
        elif self.config.serialization_method == SerializationMethod.PICKLE:
            return pickle.dumps(value)
        else:  # JSON fallback
            return json.dumps(value).encode('utf-8')
    
    async def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize a single value (for list/set operations)"""
        if self.config.serialization_method == SerializationMethod.ORJSON:
            return orjson.loads(data)
        elif self.config.serialization_method == SerializationMethod.MSGPACK:
            return msgpack.unpackb(data, raw=False)
        elif self.config.serialization_method == SerializationMethod.PICKLE:
            return pickle.loads(data)
        else:  # JSON fallback
            return json.loads(data.decode('utf-8'))
    
    async def _get_keys_by_pattern(self, pattern: str, count: int = 1000) -> List[str]:
        """Get keys matching pattern efficiently"""
        return await self.search_keys(pattern, count)
    
    async def _delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = await self._get_keys_by_pattern(pattern, count=10000)
            
            if not keys:
                return 0
            
            # Delete in batches to avoid memory issues
            batch_size = 1000
            total_deleted = 0
            
            for i in range(0, len(keys), batch_size):
                batch = keys[i:i + batch_size]
                deleted = await self.mdel(batch)
                total_deleted += deleted
            
            return total_deleted
            
        except Exception as e:
            self.logger.error(f"Pattern delete failed: {str(e)}")
            return 0
    
    async def _update_tags(self, key: str, tags: Set[str]) -> None:
        """Update tag associations for a key"""
        try:
            pipe = self.redis_client.pipeline()
            
            for tag in tags:
                tag_key = f"ymera:tags:{tag}"
                pipe.sadd(tag_key, key)
                pipe.expire(tag_key, self.config.default_ttl * 2)  # Tags live longer than data
            
            await pipe.execute()
            
        except Exception as e:
            self.logger.error(f"Failed to update tags for key {key}: {str(e)}")
    
    async def _track_agent_key(self, agent_id: str, key: str) -> None:
        """Track key for agent-specific operations"""
        try:
            agent_set_key = f"ymera:agent_keys:{agent_id}"
            pipe = self.redis_client.pipeline()
            pipe.sadd(agent_set_key, key)
            pipe.expire(agent_set_key, self.config.default_ttl * 2)
            await pipe.execute()
        except Exception as e:
            self.logger.error(f"Failed to track agent key {key} for {agent_id}: {str(e)}")
    
    async def _track_learning_key(self, context: str, key: str) -> None:
        """Track key for learning context operations"""
        try:
            learning_set_key = f"ymera:learning_keys:{context}"
            pipe = self.redis_client.pipeline()
            pipe.sadd(learning_set_key, key)
            pipe.expire(learning_set_key, self.config.default_ttl * 2)
            await pipe.execute()
        except Exception as e:
            self.logger.error(f"Failed to track learning key {key} for {context}: {str(e)}")
    
    async def _cleanup_key_metadata(self, key: str) -> None:
        """Clean up metadata when a key is deleted"""
        try:
            # Remove from all tag sets
            tag_patterns = await self._get_keys_by_pattern("ymera:tags:*")
            
            if tag_patterns:
                pipe = self.redis_client.pipeline()
                for tag_key in tag_patterns:
                    pipe.srem(tag_key, key)
                await pipe.execute()
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup metadata for key {key}: {str(e)}")


# Factory function for creating cache instances
async def create_cache_manager(config: CacheConfig) -> YMERARedisCache:
    """Factory function to create and initialize cache manager"""
    cache = YMERARedisCache(config)
    await cache.initialize()
    return cache


# Example usage and configuration
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Example configuration
        config = CacheConfig(
            redis_url="redis://localhost:6379/0",
            mode=CacheMode.STANDALONE,
            default_ttl=3600,
            max_connections=20,
            serialization_method=SerializationMethod.ORJSON,
            compression_method=CompressionMethod.ZSTD,
            enable_metrics=True,
            enable_cache_warming=True,
            encryption_enabled=False
        )
        
        # Create cache manager
        cache = await create_cache_manager(config)
        
        try:
            # Example operations
            await cache.set("test_key", {"data": "example"}, ttl=300)
            value = await cache.get("test_key")
            print(f"Retrieved: {value}")
            
            # Agent-specific operations
            await cache.set_agent_state("agent_001", {"status": "active"})
            agent_state = await cache.get_agent_state("agent_001")
            print(f"Agent state: {agent_state}")
            
            # Get statistics
            stats = await cache.get_stats()
            print(f"Cache stats: {stats}")
            
        finally:
            await cache.close()
    
    asyncio.run(main())