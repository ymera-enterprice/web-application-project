"""
YMERA Enterprise Multi-Agent System v3.0 - Additional Components
Supporting utilities for enterprise-grade multi-agent system
Production-ready components with advanced learning capabilities
"""

import asyncio
import aiohttp
import aiofiles
import json
import time
import hashlib
import uuid
import os
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from contextlib import asynccontextmanager
import logging
import structlog
from pathlib import Path
import pickle
import gzip
import base64
import secrets
from enum import Enum

# Security and Crypto
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from jose import jwt, JWTError
import bcrypt

# Database and Caching
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

# AI and ML
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import tiktoken

# Network and HTTP
import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator

# Code Analysis
import ast
import inspect
from typing import get_type_hints

logger = structlog.get_logger()

class ComponentStatus(Enum):
    """Component status enumeration"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    SHUTDOWN = "shutdown"

class Priority(Enum):
    """Task priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5

@dataclass
class PerformanceMetrics:
    """Performance metrics tracking"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, float] = None
    response_time: float = 0.0
    throughput: float = 0.0
    error_rate: float = 0.0
    
    def __post_init__(self):
        if self.network_io is None:
            self.network_io = {"bytes_sent": 0.0, "bytes_recv": 0.0}

class APIKeyManager:
    """Enterprise API Key Management System with rotation and load balancing"""
    
    def __init__(self):
        self.api_keys = {
            "openai": {
                "primary": [
                    os.getenv("OPENAI_KEY_1"),
                    os.getenv("OPENAI_KEY_2"),
                    os.getenv("OPENAI_KEY_3"),
                    os.getenv("OPENAI_KEY_4"),
                    os.getenv("OPENAI_KEY_5")
                ],
                "service": [
                    os.getenv("OPENAI_SERVICE_1"),
                    os.getenv("OPENAI_SERVICE_2"),
                    os.getenv("OPENAI_SERVICE_3")
                ]
            },
            "anthropic": [
                os.getenv("CLAUDE_KEY_1"),
                os.getenv("CLAUDE_KEY_2"),
                os.getenv("CLAUDE_KEY_3"),
                os.getenv("CLAUDE_KEY_4"),
                os.getenv("CLAUDE_KEY_5"),
                os.getenv("CLAUDE_KEY_6"),
                os.getenv("CLAUDE_KEY_7")
            ],
            "google": [
                os.getenv("GEMINI_KEY_1"),
                os.getenv("GEMINI_KEY_2"),
                os.getenv("GEMINI_KEY_3"),
                os.getenv("GEMINI_KEY_4"),
                os.getenv("GEMINI_KEY_5")
            ],
            "deepseek": [
                os.getenv("DEEPSEEK_KEY_1"),
                os.getenv("DEEPSEEK_KEY_2"),
                os.getenv("DEEPSEEK_KEY_3"),
                os.getenv("DEEPSEEK_KEY_4"),
                os.getenv("DEEPSEEK_KEY_5")
            ],
            "groq": [
                os.getenv("GROQ_KEY_1"),
                os.getenv("GROQ_KEY_2"),
                os.getenv("GROQ_KEY_3"),
                os.getenv("GROQ_KEY_4"),
                os.getenv("GROQ_KEY_5")
            ],
            "github": {
                "admin": os.getenv("GITHUB_ADMIN_TOKEN"),
                "secondary": [
                    os.getenv("GITHUB_TOKEN_1"),
                    os.getenv("GITHUB_TOKEN_2")
                ]
            },
            "pinecone": os.getenv("PINECONE_API_KEY")
        }
        
        self.key_usage = {}
        self.key_limits = {}
        self.current_key_index = {}
        self.rate_limiters = {}
        self._initialize_tracking()
        
    def _initialize_tracking(self):
        """Initialize key usage tracking"""
        for service, keys in self.api_keys.items():
            if isinstance(keys, list):
                self.current_key_index[service] = 0
                self.key_usage[service] = {i: 0 for i in range(len(keys))}
                self.rate_limiters[service] = {i: asyncio.Semaphore(100) for i in range(len(keys))}
            elif isinstance(keys, dict):
                for category, key_list in keys.items():
                    if isinstance(key_list, list):
                        service_cat = f"{service}_{category}"
                        self.current_key_index[service_cat] = 0
                        self.key_usage[service_cat] = {i: 0 for i in range(len(key_list))}
                        self.rate_limiters[service_cat] = {i: asyncio.Semaphore(100) for i in range(len(key_list))}
    
    async def get_api_key(self, service: str, category: str = "primary") -> str:
        """Get API key with load balancing and rate limiting"""
        try:
            service_key = f"{service}_{category}" if category != "primary" else service
            
            # Handle special cases
            if service == "github" and category == "admin":
                return self.api_keys["github"]["admin"]
            elif service == "pinecone":
                return self.api_keys["pinecone"]
            
            # Get keys list
            if service in self.api_keys and isinstance(self.api_keys[service], list):
                keys = self.api_keys[service]
                service_key = service
            elif service in self.api_keys and isinstance(self.api_keys[service], dict):
                keys = self.api_keys[service].get(category, [])
                service_key = f"{service}_{category}"
            else:
                raise ValueError(f"Unknown service or category: {service}_{category}")
            
            if not keys or not any(keys):
                raise ValueError(f"No API keys available for {service}_{category}")
            
            # Round-robin key selection
            current_index = self.current_key_index.get(service_key, 0)
            selected_key = keys[current_index]
            
            # Update usage tracking
            self.key_usage[service_key][current_index] += 1
            self.current_key_index[service_key] = (current_index + 1) % len(keys)
            
            # Apply rate limiting
            if service_key in self.rate_limiters:
                await self.rate_limiters[service_key][current_index].acquire()
                # Release after a delay to implement rate limiting
                asyncio.create_task(self._release_after_delay(service_key, current_index, 0.1))
            
            logger.info(f"Retrieved API key for {service}_{category}", 
                       index=current_index, 
                       usage_count=self.key_usage[service_key][current_index])
            
            return selected_key
            
        except Exception as e:
            logger.error(f"Error getting API key for {service}_{category}: {e}")
            raise
    
    async def _release_after_delay(self, service_key: str, index: int, delay: float):
        """Release rate limiter after delay"""
        await asyncio.sleep(delay)
        self.rate_limiters[service_key][index].release()
    
    def get_usage_stats(self) -> Dict:
        """Get API key usage statistics"""
        return {
            "usage": self.key_usage,
            "current_indices": self.current_key_index
        }
    
    async def rotate_keys(self, service: str):
        """Force key rotation for a service"""
        if service in self.current_key_index:
            keys_count = len(self.api_keys.get(service, []))
            self.current_key_index[service] = (self.current_key_index[service] + 1) % keys_count
            logger.info(f"Rotated keys for {service}", new_index=self.current_key_index[service])

class SecureVault:
    """Enterprise-grade secure storage for sensitive data"""
    
    def __init__(self, master_key: bytes = None):
        self.master_key = master_key or os.getenv("VAULT_MASTER_KEY", "").encode()
        if not self.master_key:
            self.master_key = Fernet.generate_key()
        
        self.fernet = Fernet(self.master_key)
        self.vault_data = {}
        self.access_log = []
        
    async def store(self, key: str, value: Any, metadata: Dict = None) -> str:
        """Securely store data"""
        try:
            # Serialize and encrypt data
            serialized_data = json.dumps(value).encode()
            encrypted_data = self.fernet.encrypt(serialized_data)
            
            # Create storage entry
            entry_id = str(uuid.uuid4())
            entry = {
                "id": entry_id,
                "key": key,
                "data": base64.b64encode(encrypted_data).decode(),
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
                "accessed_count": 0,
                "last_accessed": None
            }
            
            self.vault_data[entry_id] = entry
            
            # Log access
            self.access_log.append({
                "action": "store",
                "entry_id": entry_id,
                "key": key,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Stored data in vault", key=key, entry_id=entry_id)
            return entry_id
            
        except Exception as e:
            logger.error(f"Error storing data in vault: {e}")
            raise
    
    async def retrieve(self, entry_id: str) -> Any:
        """Securely retrieve data"""
        try:
            if entry_id not in self.vault_data:
                raise ValueError(f"Entry not found: {entry_id}")
            
            entry = self.vault_data[entry_id]
            
            # Decrypt data
            encrypted_data = base64.b64decode(entry["data"])
            decrypted_data = self.fernet.decrypt(encrypted_data)
            value = json.loads(decrypted_data.decode())
            
            # Update access tracking
            entry["accessed_count"] += 1
            entry["last_accessed"] = datetime.utcnow().isoformat()
            
            # Log access
            self.access_log.append({
                "action": "retrieve",
                "entry_id": entry_id,
                "key": entry["key"],
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return value
            
        except Exception as e:
            logger.error(f"Error retrieving data from vault: {e}")
            raise
    
    async def delete(self, entry_id: str) -> bool:
        """Securely delete data"""
        try:
            if entry_id in self.vault_data:
                entry = self.vault_data.pop(entry_id)
                
                # Log deletion
                self.access_log.append({
                    "action": "delete",
                    "entry_id": entry_id,
                    "key": entry["key"],
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                logger.info(f"Deleted data from vault", entry_id=entry_id)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting data from vault: {e}")
            raise
    
    def get_audit_log(self) -> List[Dict]:
        """Get access audit log"""
        return self.access_log.copy()

class AdvancedCacheManager:
    """Advanced caching system with TTL, LRU, and intelligent prefetching"""
    
    def __init__(self, redis_client: aioredis.Redis, max_memory_cache: int = 1000):
        self.redis = redis_client
        self.memory_cache = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
        self.max_memory_cache = max_memory_cache
        self.access_times = {}
        
    async def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get cached value with multi-level caching"""
        try:
            full_key = f"{namespace}:{key}"
            
            # Check memory cache first
            if full_key in self.memory_cache:
                self.cache_stats["hits"] += 1
                self.access_times[full_key] = time.time()
                return self.memory_cache[full_key]["data"]
            
            # Check Redis cache
            cached_data = await self.redis.get(full_key)
            if cached_data:
                self.cache_stats["hits"] += 1
                data = pickle.loads(gzip.decompress(cached_data))
                
                # Promote to memory cache if frequently accessed
                await self._promote_to_memory(full_key, data)
                return data
            
            self.cache_stats["misses"] += 1
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached value: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600, namespace: str = "default"):
        """Set cached value with compression and smart storage"""
        try:
            full_key = f"{namespace}:{key}"
            
            # Serialize and compress data
            serialized_data = gzip.compress(pickle.dumps(value))
            
            # Store in Redis
            await self.redis.setex(full_key, ttl, serialized_data)
            
            # Store in memory cache if small enough
            if len(serialized_data) < 1024 * 100:  # 100KB threshold
                await self._add_to_memory_cache(full_key, value, ttl)
            
            self.cache_stats["sets"] += 1
            logger.debug(f"Cached value", key=full_key, size=len(serialized_data))
            
        except Exception as e:
            logger.error(f"Error setting cached value: {e}")
            raise
    
    async def _add_to_memory_cache(self, key: str, data: Any, ttl: int):
        """Add to memory cache with LRU eviction"""
        if len(self.memory_cache) >= self.max_memory_cache:
            # Evict least recently used
            lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.memory_cache[lru_key]
            del self.access_times[lru_key]
        
        self.memory_cache[key] = {
            "data": data,
            "expires_at": time.time() + ttl
        }
        self.access_times[key] = time.time()
    
    async def _promote_to_memory(self, key: str, data: Any):
        """Promote frequently accessed data to memory cache"""
        # Simple promotion strategy - can be enhanced
        if len(self.memory_cache) < self.max_memory_cache:
            self.memory_cache[key] = {
                "data": data,
                "expires_at": time.time() + 3600  # 1 hour default
            }
            self.access_times[key] = time.time()
    
    async def delete(self, key: str, namespace: str = "default"):
        """Delete cached value"""
        try:
            full_key = f"{namespace}:{key}"
            
            # Delete from Redis
            await self.redis.delete(full_key)
            
            # Delete from memory cache
            if full_key in self.memory_cache:
                del self.memory_cache[full_key]
                del self.access_times[full_key]
            
            self.cache_stats["deletes"] += 1
            
        except Exception as e:
            logger.error(f"Error deleting cached value: {e}")
    
    async def get_stats(self) -> Dict:
        """Get cache statistics"""
        hit_rate = self.cache_stats["hits"] / (self.cache_stats["hits"] + self.cache_stats["misses"]) if (self.cache_stats["hits"] + self.cache_stats["misses"]) > 0 else 0
        
        return {
            **self.cache_stats,
            "hit_rate": hit_rate,
            "memory_cache_size": len(self.memory_cache),
            "redis_info": await self.redis.info()
        }
    
    async def clear_expired(self):
        """Clear expired entries from memory cache"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self.memory_cache.items()
            if value["expires_at"] < current_time
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
            del self.access_times[key]
        
        logger.info(f"Cleared {len(expired_keys)} expired cache entries")

class IntelligentTaskQueue:
    """Advanced task queue with priority, scheduling, and load balancing"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.queues = {
            Priority.CRITICAL: "ymera:queue:critical",
            Priority.HIGH: "ymera:queue:high", 
            Priority.MEDIUM: "ymera:queue:medium",
            Priority.LOW: "ymera:queue:low",
            Priority.BACKGROUND: "ymera:queue:background"
        }
        self.processing_stats = {}
        self.worker_pool = ThreadPoolExecutor(max_workers=10)
        
    async def enqueue_task(self, task_data: Dict, priority: Priority = Priority.MEDIUM, 
                          delay: int = 0, retry_count: int = 3) -> str:
        """Enqueue task with priority and scheduling"""
        try:
            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "data": task_data,
                "priority": priority.value,
                "created_at": datetime.utcnow().isoformat(),
                "retry_count": retry_count,
                "attempts": 0,
                "scheduled_for": (datetime.utcnow() + timedelta(seconds=delay)).isoformat() if delay > 0 else None
            }
            
            if delay > 0:
                # Schedule for later
                await self.redis.zadd("ymera:scheduled_tasks", {json.dumps(task): time.time() + delay})
            else:
                # Add to priority queue
                queue_name = self.queues[priority]
                await self.redis.lpush(queue_name, json.dumps(task))
            
            logger.info(f"Enqueued task", task_id=task_id, priority=priority.name, delay=delay)
            return task_id
            
        except Exception as e:
            logger.error(f"Error enqueuing task: {e}")
            raise
    
    async def dequeue_task(self, timeout: int = 10) -> Optional[Dict]:
        """Dequeue task with priority ordering"""
        try:
            # Check for scheduled tasks first
            await self._process_scheduled_tasks()
            
            # Try to dequeue from priority queues
            for priority in Priority:
                queue_name = self.queues[priority]
                result = await self.redis.brpop([queue_name], timeout=1)
                
                if result:
                    queue, task_data = result
                    task = json.loads(task_data)
                    
                    # Update processing stats
                    self.processing_stats[task["id"]] = {
                        "started_at": datetime.utcnow().isoformat(),
                        "priority": priority.name
                    }
                    
                    return task
            
            return None
            
        except Exception as e:
            logger.error(f"Error dequeuing task: {e}")
            return None
    
    async def _process_scheduled_tasks(self):
        """Move scheduled tasks to appropriate queues"""
        try:
            current_time = time.time()
            
            # Get tasks scheduled for now or earlier
            scheduled_tasks = await self.redis.zrangebyscore(
                "ymera:scheduled_tasks", 0, current_time, withscores=True
            )
            
            for task_data, score in scheduled_tasks:
                task = json.loads(task_data)
                priority = Priority(task["priority"])
                queue_name = self.queues[priority]
                
                # Move to priority queue
                await self.redis.lpush(queue_name, task_data)
                await self.redis.zrem("ymera:scheduled_tasks", task_data)
                
                logger.info(f"Moved scheduled task to queue", task_id=task["id"], priority=priority.name)
                
        except Exception as e:
            logger.error(f"Error processing scheduled tasks: {e}")
    
    async def complete_task(self, task_id: str, result: Dict = None):
        """Mark task as completed"""
        try:
            if task_id in self.processing_stats:
                stats = self.processing_stats[task_id]
                stats["completed_at"] = datetime.utcnow().isoformat()
                stats["result"] = result
                
                # Store completion record
                await self.redis.hset(
                    "ymera:completed_tasks",
                    task_id,
                    json.dumps(stats)
                )
                
                # Remove from processing
                del self.processing_stats[task_id]
                
                logger.info(f"Completed task", task_id=task_id)
                
        except Exception as e:
            logger.error(f"Error completing task: {e}")
    
    async def fail_task(self, task_id: str, error: str, retry: bool = True):
        """Handle task failure with retry logic"""
        try:
            if task_id in self.processing_stats:
                stats = self.processing_stats[task_id]
                stats["failed_at"] = datetime.utcnow().isoformat()
                stats["error"] = error
                
                # TODO: Implement retry logic based on task configuration
                logger.error(f"Task failed", task_id=task_id, error=error)
                
        except Exception as e:
            logger.error(f"Error handling task failure: {e}")
    
    async def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        try:
            stats = {}
            
            for priority, queue_name in self.queues.items():
                queue_length = await self.redis.llen(queue_name)
                stats[priority.name] = {
                    "pending": queue_length,
                    "queue_name": queue_name
                }
            
            scheduled_count = await self.redis.zcard("ymera:scheduled_tasks")
            processing_count = len(self.processing_stats)
            completed_count = await self.redis.hlen("ymera:completed_tasks")
            
            stats["summary"] = {
                "scheduled": scheduled_count,
                "processing": processing_count,
                "completed": completed_count
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}

class MLModelManager:
    """Machine Learning model management with caching and optimization"""
    
    def __init__(self):
        self.models = {}
        self.model_cache = {}
        self.embeddings_cache = {}
        self.model_stats = {}
        
    async def load_model(self, model_name: str, model_type: str = "sentence_transformer") -> Any:
        """Load ML model with caching"""
        try:
            if model_name in self.model_cache:
                self.model_stats[model_name]["access_count"] += 1
                return self.model_cache[model_name]
            
            if model_type == "sentence_transformer":
                model = SentenceTransformer(model_name)
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            self.model_cache[model_name] = model
            self.model_stats[model_name] = {
                "loaded_at": datetime.utcnow().isoformat(),
                "access_count": 1,
                "model_type": model_type
            }
            
            logger.info(f"Loaded ML model", model_name=model_name, model_type=model_type)
            return model
            
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            raise
    
    async def get_embeddings(self, texts: List[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
        """Generate embeddings with caching"""
        try:
            # Create cache key
            cache_key = hashlib.sha256(f"{model_name}:{json.dumps(sorted(texts))}".encode()).hexdigest()
            
            if cache_key in self.embeddings_cache:
                return self.embeddings_cache[cache_key]
            
            # Load model and generate embeddings
            model = await self.load_model(model_name)
            embeddings = model.encode(texts, convert_to_numpy=True)
            
            # Cache embeddings
            self.embeddings_cache[cache_key] = embeddings
            
            logger.info(f"Generated embeddings", model=model_name, texts_count=len(texts))
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    async def compute_similarity(self, text1: str, text2: str, model_name: str = "all-MiniLM-L6-v2") -> float:
        """Compute semantic similarity between texts"""
        try:
            embeddings = await self.get_embeddings([text1, text2], model_name)
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    async def cluster_texts(self, texts: List[str], n_clusters: int = 5, model_name: str = "all-MiniLM-L6-v2") -> Dict:
        """Cluster texts using embeddings"""
        try:
            embeddings = await self.get_embeddings(texts, model_name)
            
            # Perform clustering
            kmeans = KMeans(n_clusters=min(n_clusters, len(texts)), random_state=42)
            cluster_labels = kmeans.fit_predict(embeddings)
            
            # Organize results
            clusters = {}
            for i, label in enumerate(cluster_labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append({
                    "text": texts[i],
                    "index": i,
                    "embedding": embeddings[i].tolist()
                })
            
            return {
                "clusters": clusters,
                "centroids": kmeans.cluster_centers_.tolist(),
                "inertia": kmeans.inertia_
            }
            
        except Exception as e:
            logger.error(f"Error clustering texts: {e}")
            raise
    
    def get_model_stats(self) -> Dict:
        """Get model usage statistics"""
        return self.model_stats.copy()
    
    async def cleanup_cache(self, max_cache_size: int = 100):
        """Cleanup embedding cache to manage memory"""
        if len(self.embeddings_cache) > max_cache_size:
            # Remove oldest entries (simple FIFO)
            keys_to_remove = list(self.embeddings_cache.keys())[:len(self.embeddings_cache) - max_cache_size]
            for key in keys_to_remove:
                del self.embeddings_cache[key]
            
            logger.info(f"Cleaned up embedding cache", removed_count=len(keys_to_remove))

class SystemHealthMonitor:
    """Comprehensive system health monitoring"""
    
    def __init__(self):
        self.metrics_history = []
        self.alerts = []
        self.thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 90.0,
            "response_time": 5.0,
            "error_rate": 0.05
        }
        self.monitoring_active = True
        
    async def collect_metrics(self) -> PerformanceMetrics:
        """Collect current system metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            metrics = PerformanceMetrics(
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_io={
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv
                },
                response_time=0.0,  # To be updated by application
                throughput=0.0,     # To be updated by application
                error_rate=0.0      # To be updated by application
            )
            
            # Store metrics history
            metrics_dict = asdict(metrics)
            metrics_dict["timestamp"] = datetime.utcnow().isoformat()
            self.metrics_history.append(metrics_dict)
            
            # Keep only last 1000 metrics
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]
            
            # Check thresholds
            await self._check_thresholds(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            raise
    
    async def _check_thresholds(self, metrics: PerformanceMetrics):
        """Check metrics against thresholds and generate alerts"""
        try:
            current_time = datetime.utcnow().isoformat()
            
            for metric_name, threshold in self.thresholds.items():
                metric_value = getattr(metrics, metric_name)
                
                if metric_value > threshold:
                    alert = {
                        "id": str(uuid.uuid4()),
                        "metric": metric_name,
                        "value": metric_value,
                        "threshold": threshold,
                        "severity": "warning" if metric_value < threshold * 1.2 else "critical",
                        "timestamp": current_time,
                        "message": f"{metric_name} is {metric_value:.2f}%, exceeding threshold of {threshold}%"
                    }
                    
                    self.alerts.append(alert)
                    logger.warning(f"Threshold exceeded", **alert)
                    
                    # Keep only last 100 alerts
                    if len(self.alerts) > 100:
                        self.alerts = self.alerts[-100:]
                        
        except Exception as e:
            logger.error(f"Error checking thresholds: {e}")
    
    def get_health_status(self) -> Dict:
        """Get overall system health status"""
        try:
            if not self.metrics_history:
                return {"status": "unknown", "message": "No metrics available"}
            
            latest_metrics = self.metrics_history[-1]
            critical_alerts = [a for a in self.alerts if a["severity"] == "critical"]
            warning_alerts = [a for a in self.alerts if a["severity"] == "warning"]
            
            # Determine overall health
            if critical_alerts:
                status = "critical"
                message = f"{len(critical_alerts)} critical issues detected"
            elif warning_alerts:
                status = "warning"
                message = f"{len(warning_alerts)} warnings detected"
            elif latest_metrics["cpu_usage"] < 50 and latest_metrics["memory_usage"] < 70:
                status = "healthy"
                message = "All systems operating normally"
            else:
                status = "moderate"
                message = "System under moderate load"
            
            return {
                "status": status,
                "message": message,
                "latest_metrics": latest_metrics,
                "alerts": {
                    "critical": len(critical_alerts),
                    "warning": len(warning_alerts)
                },
                "uptime": self._get_uptime()
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"status": "error", "message": f"Error: {e}"}
    
    def _get_uptime(self) -> str:
        """Get system uptime"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            return str(uptime).split('.')[0]  # Remove microseconds
        except:
            return "unknown"
    
    def get_metrics_history(self, limit: int = 100) -> List[Dict]:
        """Get historical metrics"""
        return self.metrics_history[-limit:] if limit else self.metrics_history.copy()
    
    def get_alerts(self, severity: str = None) -> List[Dict]:
        """Get alerts, optionally filtered by severity"""
        if severity:
            return [a for a in self.alerts if a["severity"] == severity]
        return self.alerts.copy()
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()
        logger.info("Cleared all alerts")

class EventBus:
    """Enterprise event bus for inter-agent communication"""
    
    def __init__(self):
        self.subscribers = {}
        self.event_history = []
        self.event_stats = {}
        
    def subscribe(self, event_type: str, handler: Callable, priority: int = 0):
        """Subscribe to events"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        self.subscribers[event_type].append({
            "handler": handler,
            "priority": priority,
            "id": str(uuid.uuid4())
        })
        
        # Sort by priority (higher priority first)
        self.subscribers[event_type].sort(key=lambda x: x["priority"], reverse=True)
        
        logger.info(f"Subscribed to event", event_type=event_type, priority=priority)
    
    async def publish(self, event_type: str, data: Dict, metadata: Dict = None) -> List[Any]:
        """Publish event to subscribers"""
        try:
            event = {
                "id": str(uuid.uuid4()),
                "type": event_type,
                "data": data,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat(),
                "source": "system"
            }
            
            # Store in history
            self.event_history.append(event)
            if len(self.event_history) > 1000:
                self.event_history = self.event_history[-1000:]
            
            # Update stats
            if event_type not in self.event_stats:
                self.event_stats[event_type] = {"published": 0, "processed": 0}
            self.event_stats[event_type]["published"] += 1
            
            # Notify subscribers
            results = []
            if event_type in self.subscribers:
                for subscriber in self.subscribers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(subscriber["handler"]):
                            result = await subscriber["handler"](event)
                        else:
                            result = subscriber["handler"](event)
                        results.append(result)
                        self.event_stats[event_type]["processed"] += 1
                    except Exception as e:
                        logger.error(f"Error in event handler", event_type=event_type, error=str(e))
                        results.append({"error": str(e)})
            
            logger.info(f"Published event", event_type=event_type, subscribers=len(results))
            return results
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            raise
    
    def unsubscribe(self, event_type: str, handler_id: str):
        """Unsubscribe from events"""
        if event_type in self.subscribers:
            self.subscribers[event_type] = [
                sub for sub in self.subscribers[event_type] 
                if sub["id"] != handler_id
            ]
            logger.info(f"Unsubscribed from event", event_type=event_type, handler_id=handler_id)
    
    def get_event_stats(self) -> Dict:
        """Get event statistics"""
        return {
            "stats": self.event_stats.copy(),
            "total_events": len(self.event_history),
            "active_subscriptions": {
                event_type: len(handlers) 
                for event_type, handlers in self.subscribers.items()
            }
        }
    
    def get_recent_events(self, event_type: str = None, limit: int = 50) -> List[Dict]:
        """Get recent events"""
        events = self.event_history[-limit:] if not event_type else [
            event for event in self.event_history[-limit:] 
            if event["type"] == event_type
        ]
        return events

class BrowserManager:
    """Manages browser access for agents with security and resource management"""
    
    def __init__(self):
        self.active_sessions = {}
        self.session_limits = {
            "max_concurrent": 5,
            "max_duration": 3600,  # 1 hour
            "max_requests_per_session": 100
        }
        self.session_stats = {}
        
    async def create_session(self, agent_id: str, purpose: str = "research") -> str:
        """Create a new browser session for an agent"""
        try:
            # Check limits
            if len(self.active_sessions) >= self.session_limits["max_concurrent"]:
                raise HTTPException(status_code=429, detail="Too many concurrent browser sessions")
            
            session_id = str(uuid.uuid4())
            session = {
                "id": session_id,
                "agent_id": agent_id,
                "purpose": purpose,
                "created_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "request_count": 0,
                "user_agent": "YMERA-Agent/3.0 (Enterprise Multi-Agent System)",
                "timeout": self.session_limits["max_duration"]
            }
            
            self.active_sessions[session_id] = session
            self.session_stats[session_id] = {
                "requests": [],
                "errors": [],
                "start_time": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Created browser session", session_id=session_id, agent_id=agent_id, purpose=purpose)
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating browser session: {e}")
            raise
    
    async def make_request(self, session_id: str, url: str, method: str = "GET", 
                          headers: Dict = None, data: Dict = None) -> Dict:
        """Make HTTP request through managed session"""
        try:
            if session_id not in self.active_sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            
            session = self.active_sessions[session_id]
            
            # Check session limits
            if session["request_count"] >= self.session_limits["max_requests_per_session"]:
                raise HTTPException(status_code=429, detail="Session request limit exceeded")
            
            if datetime.utcnow() - session["created_at"] > timedelta(seconds=session["timeout"]):
                await self.close_session(session_id)
                raise HTTPException(status_code=408, detail="Session expired")
            
            # Prepare request
            default_headers = {
                "User-Agent": session["user_agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            if headers:
                default_headers.update(headers)
            
            # Make request with timeout
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
                async with client.request(method, url, headers=default_headers, json=data) as response:
                    content = await response.text()
                    
                    result = {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "content": content,
                        "url": str(response.url),
                        "method": method,
                        "timestamp": datetime.utcnow().isoformat()
                    }
            
            # Update session
            session["request_count"] += 1
            session["last_activity"] = datetime.utcnow()
            
            # Track stats
            self.session_stats[session_id]["requests"].append({
                "url": url,
                "method": method,
                "status_code": response.status,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Browser request completed", session_id=session_id, url=url, status=response.status)
            return result
            
        except Exception as e:
            # Track error
            if session_id in self.session_stats:
                self.session_stats[session_id]["errors"].append({
                    "url": url,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            logger.error(f"Browser request failed", session_id=session_id, url=url, error=str(e))
            raise
    
    async def close_session(self, session_id: str):
        """Close browser session and cleanup"""
        try:
            if session_id in self.active_sessions:
                session = self.active_sessions.pop(session_id)
                
                # Finalize stats
                if session_id in self.session_stats:
                    self.session_stats[session_id]["end_time"] = datetime.utcnow().isoformat()
                    self.session_stats[session_id]["duration"] = (
                        datetime.utcnow() - session["created_at"]
                    ).total_seconds()
                
                logger.info(f"Closed browser session", session_id=session_id, 
                           duration=self.session_stats[session_id]["duration"])
                
        except Exception as e:
            logger.error(f"Error closing browser session: {e}")
    
    async def get_session_info(self, session_id: str) -> Dict:
        """Get session information"""
        if session_id not in self.active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = self.active_sessions[session_id]
        stats = self.session_stats.get(session_id, {})
        
        return {
            "session": {
                "id": session_id,
                "agent_id": session["agent_id"],
                "purpose": session["purpose"],
                "created_at": session["created_at"].isoformat(),
                "last_activity": session["last_activity"].isoformat(),
                "request_count": session["request_count"],
                "remaining_requests": self.session_limits["max_requests_per_session"] - session["request_count"]
            },
            "stats": stats
        }
    
    async def cleanup_expired_sessions(self):
        """Cleanup expired sessions"""
        current_time = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if current_time - session["created_at"] > timedelta(seconds=session["timeout"]):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self.close_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up expired sessions", count=len(expired_sessions))
    
    def get_all_sessions(self) -> Dict:
        """Get information about all active sessions"""
        return {
            "active_sessions": len(self.active_sessions),
            "session_limit": self.session_limits["max_concurrent"],
            "sessions": [
                {
                    "id": session_id,
                    "agent_id": session["agent_id"],
                    "purpose": session["purpose"],
                    "created_at": session["created_at"].isoformat(),
                    "request_count": session["request_count"]
                }
                for session_id, session in self.active_sessions.items()
            ]
        }

class ComponentRegistry:
    """Central registry for all system components"""
    
    def __init__(self):
        self.components = {}
        self.component_health = {}
        self.startup_order = []
        
    def register_component(self, name: str, component: Any, health_check: Callable = None):
        """Register a system component"""
        self.components[name] = {
            "instance": component,
            "health_check": health_check,
            "registered_at": datetime.utcnow(),
            "status": ComponentStatus.INITIALIZING
        }
        
        logger.info(f"Registered component", name=name, type=type(component).__name__)
    
    async def initialize_component(self, name: str) -> bool:
        """Initialize a specific component"""
        try:
            if name not in self.components:
                raise ValueError(f"Component not found: {name}")
            
            component = self.components[name]
            instance = component["instance"]
            
            # Call initialize method if it exists
            if hasattr(instance, "initialize") and callable(getattr(instance, "initialize")):
                if asyncio.iscoroutinefunction(instance.initialize):
                    await instance.initialize()
                else:
                    instance.initialize()
            
            component["status"] = ComponentStatus.ACTIVE
            component["initialized_at"] = datetime.utcnow()
            
            logger.info(f"Initialized component", name=name)
            return True
            
        except Exception as e:
            if name in self.components:
                self.components[name]["status"] = ComponentStatus.ERROR
                self.components[name]["error"] = str(e)
            
            logger.error(f"Failed to initialize component", name=name, error=str(e))
            return False
    
    async def check_component_health(self, name: str) -> Dict:
        """Check health of a specific component"""
        try:
            if name not in self.components:
                return {"status": "not_found", "message": f"Component {name} not registered"}
            
            component = self.components[name]
            health_check = component.get("health_check")
            
            if health_check:
                if asyncio.iscoroutinefunction(health_check):
                    result = await health_check()
                else:
                    result = health_check()
                
                self.component_health[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "last_check": datetime.utcnow().isoformat(),
                    "result": result
                }
            else:
                self.component_health[name] = {
                    "status": "unknown",
                    "last_check": datetime.utcnow().isoformat(),
                    "message": "No health check available"
                }
            
            return self.component_health[name]
            
        except Exception as e:
            self.component_health[name] = {
                "status": "error",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e)
            }
            return self.component_health[name]
    
    async def check_all_components_health(self) -> Dict:
        """Check health of all registered components"""
        health_results = {}
        
        for name in self.components.keys():
            health_results[name] = await self.check_component_health(name)
        
        return health_results
    
    def get_component(self, name: str) -> Any:
        """Get a component instance"""
        if name not in self.components:
            raise ValueError(f"Component not found: {name}")
        
        return self.components[name]["instance"]
    
    def get_component_status(self, name: str) -> ComponentStatus:
        """Get component status"""
        if name not in self.components:
            raise ValueError(f"Component not found: {name}")
        
        return self.components[name]["status"]
    
    def list_components(self) -> Dict:
        """List all registered components with their status"""
        return {
            name: {
                "type": type(component["instance"]).__name__,
                "status": component["status"].value,
                "registered_at": component["registered_at"].isoformat()
            }
            for name, component in self.components.items()
        }
    
    async def shutdown_component(self, name: str):
        """Shutdown a specific component"""
        try:
            if name not in self.components:
                return
            
            component = self.components[name]
            instance = component["instance"]
            
            # Call shutdown method if it exists
            if hasattr(instance, "shutdown") and callable(getattr(instance, "shutdown")):
                if asyncio.iscoroutinefunction(instance.shutdown):
                    await instance.shutdown()
                else:
                    instance.shutdown()
            
            component["status"] = ComponentStatus.SHUTDOWN
            logger.info(f"Shutdown component", name=name)
            
        except Exception as e:
            logger.error(f"Error shutting down component", name=name, error=str(e))
    
    async def shutdown_all_components(self):
        """Shutdown all components in reverse order"""
        shutdown_order = list(reversed(self.startup_order)) if self.startup_order else list(self.components.keys())
        
        for name in shutdown_order:
            await self.shutdown_component(name)

# Global component instances
api_key_manager = APIKeyManager()
secure_vault = SecureVault()
ml_model_manager = MLModelManager()
system_health_monitor = SystemHealthMonitor()
event_bus = EventBus()
browser_manager = BrowserManager()
component_registry = ComponentRegistry()

async def initialize_all_components(redis_client: aioredis.Redis = None):
    """Initialize all system components"""
    try:
        logger.info("Initializing YMERA system components")
        
        # Register components
        component_registry.register_component("api_key_manager", api_key_manager)
        component_registry.register_component("secure_vault", secure_vault)
        component_registry.register_component("ml_model_manager", ml_model_manager)
        component_registry.register_component("system_health_monitor", system_health_monitor)
        component_registry.register_component("event_bus", event_bus)
        component_registry.register_component("browser_manager", browser_manager)
        
        # Initialize cache manager if Redis is available
        if redis_client:
            cache_manager = AdvancedCacheManager(redis_client)
            task_queue = IntelligentTaskQueue(redis_client)
            
            component_registry.register_component("cache_manager", cache_manager)
            component_registry.register_component("task_queue", task_queue)
        
        # Initialize all components
        for name in component_registry.components.keys():
            await component_registry.initialize_component(name)
        
        logger.info("All YMERA system components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize system components: {e}")
        raise

async def get_system_status() -> Dict:
    """Get comprehensive system status"""
    try:
        # Get component health
        component_health = await component_registry.check_all_components_health()
        
        # Get system metrics
        metrics = await system_health_monitor.collect_metrics()
        health_status = system_health_monitor.get_health_status()
        
        # Get API key usage
        api_key_stats = api_key_manager.get_usage_stats()
        
        # Get browser session info
        browser_sessions = browser_manager.get_all_sessions()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": health_status["status"],
            "components": component_health,
            "system_metrics": asdict(metrics),
            "health_summary": health_status,
            "api_key_usage": api_key_stats,
            "browser_sessions": browser_sessions,
            "uptime": health_status.get("uptime", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "error",
            "error": str(e)
        }

# Export all components for use by agents
__all__ = [
    "APIKeyManager",
    "SecureVault", 
    "AdvancedCacheManager",
    "IntelligentTaskQueue",
    "MLModelManager",
    "SystemHealthMonitor",
    "EventBus",
    "BrowserManager",
    "ComponentRegistry",
    "api_key_manager",
    "secure_vault",
    "ml_model_manager",
    "system_health_monitor",
    "event_bus",
    "browser_manager",
    "component_registry",
    "initialize_all_components",
    "get_system_status",
    "ComponentStatus",
    "Priority",
    "PerformanceMetrics"
]