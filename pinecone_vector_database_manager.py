"""
YMERA Enterprise Pinecone Vector Database Manager
Production-Ready Vector Database with Multi-Agent Learning Support
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, Set
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import logging
from contextlib import asynccontextmanager

import pinecone
from pinecone import Pinecone, Index, PodSpec, ServerlessSpec
import numpy as np
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aioredis
from prometheus_client import Counter, Histogram, Gauge

from ymera_core.exceptions import YMERAException
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.monitoring.base_monitor import BaseMonitor


class VectorOperationType(Enum):
    """Vector operation types for monitoring"""
    UPSERT = "upsert"
    QUERY = "query"
    DELETE = "delete"
    UPDATE = "update"
    FETCH = "fetch"
    LIST = "list"
    STATS = "stats"


class VectorNamespace(Enum):
    """Vector namespaces for multi-agent organization"""
    AGENT_KNOWLEDGE = "agent-knowledge"
    PROJECT_CONTEXT = "project-context"
    CODE_SEMANTICS = "code-semantics"
    LEARNING_PATTERNS = "learning-patterns"
    USER_INTERACTIONS = "user-interactions"
    SECURITY_INSIGHTS = "security-insights"
    DEPLOYMENT_CONFIGS = "deployment-configs"
    ERROR_PATTERNS = "error-patterns"
    PERFORMANCE_METRICS = "performance-metrics"
    CONVERSATION_MEMORY = "conversation-memory"


@dataclass
class VectorMetadata:
    """Enhanced metadata structure for vector entries"""
    id: str
    source_type: str  # agent, user, system, external
    source_id: str
    content_type: str  # text, code, config, pattern, etc.
    timestamp: str
    project_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tags: List[str] = None
    importance_score: float = 0.5
    confidence_score: float = 1.0
    learning_context: Dict[str, Any] = None
    version: str = "1.0"
    ttl_hours: Optional[int] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.learning_context is None:
            self.learning_context = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Pinecone metadata"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class QueryResult:
    """Enhanced query result with relevance scoring"""
    id: str
    score: float
    metadata: VectorMetadata
    content: Optional[str] = None
    namespace: str = VectorNamespace.AGENT_KNOWLEDGE.value
    
    @classmethod
    def from_pinecone_match(cls, match: Dict, namespace: str = None) -> 'QueryResult':
        """Create QueryResult from Pinecone match"""
        metadata_dict = match.get('metadata', {})
        metadata = VectorMetadata(**metadata_dict)
        
        return cls(
            id=match['id'],
            score=match['score'],
            metadata=metadata,
            content=metadata_dict.get('content'),
            namespace=namespace or VectorNamespace.AGENT_KNOWLEDGE.value
        )


class VectorSearchConfig:
    """Configuration for vector search operations"""
    
    def __init__(self,
                 top_k: int = 10,
                 min_score: float = 0.7,
                 include_metadata: bool = True,
                 include_values: bool = False,
                 namespace: str = None,
                 filter_dict: Dict[str, Any] = None,
                 hybrid_search: bool = False,
                 rerank: bool = False):
        self.top_k = top_k
        self.min_score = min_score
        self.include_metadata = include_metadata
        self.include_values = include_values
        self.namespace = namespace
        self.filter_dict = filter_dict or {}
        self.hybrid_search = hybrid_search
        self.rerank = rerank


class PineconeMetrics:
    """Prometheus metrics for Pinecone operations"""
    
    def __init__(self):
        self.operations_total = Counter(
            'pinecone_operations_total',
            'Total Pinecone operations',
            ['operation_type', 'namespace', 'status']
        )
        
        self.operation_duration = Histogram(
            'pinecone_operation_duration_seconds',
            'Duration of Pinecone operations',
            ['operation_type', 'namespace']
        )
        
        self.vector_count = Gauge(
            'pinecone_vectors_total',
            'Total number of vectors',
            ['namespace']
        )
        
        self.query_relevance = Histogram(
            'pinecone_query_relevance_score',
            'Query relevance scores',
            ['namespace']
        )


class PineconeManager(BaseMonitor):
    """
    Enterprise-grade Pinecone vector database manager with multi-agent support,
    continuous learning integration, and production monitoring.
    """
    
    def __init__(self,
                 api_key: str,
                 environment: str,
                 index_name: str,
                 dimension: int = 1536,
                 metric: str = "cosine",
                 pod_type: str = "p1.x1",
                 replicas: int = 1,
                 shards: int = 1,
                 metadata_config: Dict[str, str] = None,
                 timeout: int = 30,
                 max_retries: int = 3,
                 batch_size: int = 100,
                 cache_ttl: int = 300,
                 redis_url: str = None,
                 enable_serverless: bool = False,
                 cloud: str = "aws",
                 region: str = "us-east-1"):
        
        super().__init__(component_name="pinecone_manager")
        
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        self.dimension = dimension
        self.metric = metric
        self.pod_type = pod_type
        self.replicas = replicas
        self.shards = shards
        self.metadata_config = metadata_config or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.cache_ttl = cache_ttl
        self.enable_serverless = enable_serverless
        self.cloud = cloud
        self.region = region
        
        # Core components
        self.client: Optional[Pinecone] = None
        self.index: Optional[Index] = None
        self.logger = StructuredLogger("pinecone_manager")
        self.metrics = PineconeMetrics()
        self.redis_client: Optional[aioredis.Redis] = None
        
        # State management
        self.is_initialized = False
        self.connection_pool_size = 10
        self.active_connections = 0
        self.last_health_check = None
        self.index_stats_cache = {}
        self.namespace_stats = {}
        
        # Learning integration
        self.learning_metadata_keys = {
            'learning_phase', 'feedback_score', 'usage_count',
            'last_accessed', 'relevance_decay', 'update_frequency'
        }
        
        # Performance optimization
        self.query_cache = {}
        self.embedding_cache = {}
        self.batch_operations = []
        self.batch_timer = None
        
        # Initialize Redis if URL provided
        if redis_url:
            self._setup_redis_cache(redis_url)
    
    async def initialize(self) -> None:
        """Initialize Pinecone client and index with comprehensive setup"""
        try:
            await self.logger.initialize()
            self.logger.info("Initializing Pinecone manager...")
            
            # Initialize Pinecone client
            self.client = Pinecone(api_key=self.api_key)
            
            # Ensure index exists
            await self._ensure_index_exists()
            
            # Get index reference
            self.index = self.client.Index(self.index_name)
            
            # Initialize namespaces
            await self._initialize_namespaces()
            
            # Setup monitoring
            await self._setup_monitoring()
            
            # Start background tasks
            await self._start_background_tasks()
            
            self.is_initialized = True
            self.logger.info(
                "Pinecone manager initialized successfully",
                extra={
                    "index_name": self.index_name,
                    "dimension": self.dimension,
                    "metric": self.metric,
                    "namespaces_count": len(VectorNamespace)
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Pinecone manager: {str(e)}")
            raise YMERAException(f"Pinecone initialization failed: {str(e)}")
    
    def _setup_redis_cache(self, redis_url: str):
        """Setup Redis caching for query optimization"""
        try:
            self.redis_client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            self.logger.info("Redis cache initialized for Pinecone")
        except Exception as e:
            self.logger.warning(f"Redis cache setup failed: {str(e)}")
    
    async def _ensure_index_exists(self) -> None:
        """Ensure Pinecone index exists with proper configuration"""
        try:
            existing_indexes = [idx.name for idx in self.client.list_indexes()]
            
            if self.index_name not in existing_indexes:
                self.logger.info(f"Creating Pinecone index: {self.index_name}")
                
                # Choose spec based on configuration
                if self.enable_serverless:
                    spec = ServerlessSpec(
                        cloud=self.cloud,
                        region=self.region
                    )
                else:
                    spec = PodSpec(
                        environment=self.environment,
                        pod_type=self.pod_type,
                        pods=self.replicas,
                        replicas=self.replicas,
                        shards=self.shards,
                        metadata_config=self.metadata_config
                    )
                
                self.client.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=spec,
                    timeout=self.timeout
                )
                
                # Wait for index to be ready
                await self._wait_for_index_ready()
                
                self.logger.info(f"Pinecone index created: {self.index_name}")
            else:
                self.logger.info(f"Using existing Pinecone index: {self.index_name}")
                
        except Exception as e:
            raise YMERAException(f"Failed to ensure index exists: {str(e)}")
    
    async def _wait_for_index_ready(self, max_wait: int = 300) -> None:
        """Wait for index to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                index_desc = self.client.describe_index(self.index_name)
                if index_desc.status.ready:
                    return
                
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.warning(f"Error checking index status: {str(e)}")
                await asyncio.sleep(10)
        
        raise YMERAException(f"Index {self.index_name} not ready after {max_wait}s")
    
    async def _initialize_namespaces(self) -> None:
        """Initialize all required namespaces for multi-agent system"""
        for namespace in VectorNamespace:
            try:
                # Create namespace by upserting a dummy vector and then deleting it
                dummy_vector = {
                    'id': f"__init_{namespace.value}",
                    'values': [0.0] * self.dimension,
                    'metadata': {
                        'type': 'initialization',
                        'timestamp': datetime.utcnow().isoformat(),
                        'temporary': True
                    }
                }
                
                # Upsert dummy vector to create namespace
                self.index.upsert(
                    vectors=[dummy_vector],
                    namespace=namespace.value
                )
                
                # Delete dummy vector
                self.index.delete(
                    ids=[f"__init_{namespace.value}"],
                    namespace=namespace.value
                )
                
                self.logger.debug(f"Initialized namespace: {namespace.value}")
                
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize namespace {namespace.value}: {str(e)}"
                )
    
    async def _setup_monitoring(self) -> None:
        """Setup comprehensive monitoring for Pinecone operations"""
        try:
            # Update namespace statistics
            for namespace in VectorNamespace:
                stats = await self.get_namespace_stats(namespace.value)
                if stats:
                    self.metrics.vector_count.labels(namespace=namespace.value).set(
                        stats.get('total_vector_count', 0)
                    )
            
            self.logger.info("Pinecone monitoring setup complete")
            
        except Exception as e:
            self.logger.warning(f"Monitoring setup failed: {str(e)}")
    
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks"""
        # Health check task
        asyncio.create_task(self._health_check_loop())
        
        # Batch processing task
        asyncio.create_task(self._batch_processor_loop())
        
        # Cache cleanup task
        asyncio.create_task(self._cache_cleanup_loop())
        
        # Learning optimization task
        asyncio.create_task(self._learning_optimization_loop())
        
        self.logger.info("Background tasks started")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((pinecone.exceptions.PineconeException,))
    )
    async def upsert_vectors(self,
                           vectors: List[Dict[str, Any]],
                           namespace: str = VectorNamespace.AGENT_KNOWLEDGE.value,
                           batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Upsert vectors with enhanced metadata and learning integration
        """
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        batch_size = batch_size or self.batch_size
        total_vectors = len(vectors)
        
        start_time = time.time()
        
        try:
            # Process vectors in batches
            upserted_count = 0
            failed_count = 0
            
            for i in range(0, total_vectors, batch_size):
                batch = vectors[i:i + batch_size]
                
                try:
                    # Enhance metadata for learning integration
                    enhanced_batch = await self._enhance_vector_metadata(batch)
                    
                    # Upsert batch
                    response = self.index.upsert(
                        vectors=enhanced_batch,
                        namespace=namespace
                    )
                    
                    upserted_count += len(batch)
                    
                    self.logger.debug(
                        f"Upserted batch {i // batch_size + 1}: {len(batch)} vectors"
                    )
                    
                except Exception as e:
                    failed_count += len(batch)
                    self.logger.error(
                        f"Failed to upsert batch {i // batch_size + 1}: {str(e)}"
                    )
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.UPSERT.value,
                namespace=namespace
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.UPSERT.value,
                namespace=namespace,
                status="success" if failed_count == 0 else "partial"
            ).inc()
            
            # Update namespace stats cache
            await self._update_namespace_stats(namespace)
            
            result = {
                'total_vectors': total_vectors,
                'upserted_count': upserted_count,
                'failed_count': failed_count,
                'duration_seconds': duration,
                'namespace': namespace,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(
                f"Upserted {upserted_count}/{total_vectors} vectors to namespace {namespace}",
                extra=result
            )
            
            return result
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.UPSERT.value,
                namespace=namespace,
                status="error"
            ).inc()
            
            raise YMERAException(f"Vector upsert failed: {str(e)}")
    
    async def _enhance_vector_metadata(self, vectors: List[Dict]) -> List[Dict]:
        """Enhance vector metadata for learning and multi-agent support"""
        enhanced_vectors = []
        
        for vector in vectors:
            enhanced_vector = vector.copy()
            metadata = enhanced_vector.get('metadata', {})
            
            # Add learning-specific metadata
            metadata.update({
                'created_at': datetime.utcnow().isoformat(),
                'last_accessed': datetime.utcnow().isoformat(),
                'access_count': 0,
                'relevance_score': metadata.get('importance_score', 0.5),
                'learning_phase': 'initial',
                'update_count': 0,
                'content_hash': self._generate_content_hash(vector.get('values', []))
            })
            
            # Add TTL if specified
            if 'ttl_hours' in metadata and metadata['ttl_hours']:
                ttl_timestamp = (
                    datetime.utcnow() + timedelta(hours=metadata['ttl_hours'])
                ).isoformat()
                metadata['expires_at'] = ttl_timestamp
            
            enhanced_vector['metadata'] = metadata
            enhanced_vectors.append(enhanced_vector)
        
        return enhanced_vectors
    
    def _generate_content_hash(self, values: List[float]) -> str:
        """Generate hash for content deduplication"""
        content_str = json.dumps(values, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((pinecone.exceptions.PineconeException,))
    )
    async def query_vectors(self,
                          query_vector: List[float],
                          config: VectorSearchConfig = None,
                          use_cache: bool = True) -> List[QueryResult]:
        """
        Advanced vector query with caching, filtering, and learning integration
        """
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        config = config or VectorSearchConfig()
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = None
            if use_cache and self.redis_client:
                cache_key = self._generate_query_cache_key(query_vector, config)
                cached_result = await self._get_cached_query(cache_key)
                if cached_result:
                    return cached_result
            
            # Prepare query parameters
            query_params = {
                'vector': query_vector,
                'top_k': config.top_k,
                'include_metadata': config.include_metadata,
                'include_values': config.include_values,
                'namespace': config.namespace or VectorNamespace.AGENT_KNOWLEDGE.value
            }
            
            # Add filter if specified
            if config.filter_dict:
                query_params['filter'] = self._build_pinecone_filter(config.filter_dict)
            
            # Execute query
            response = self.index.query(**query_params)
            
            # Process results
            results = []
            for match in response.matches:
                if match.score >= config.min_score:
                    result = QueryResult.from_pinecone_match(
                        match.__dict__, 
                        query_params['namespace']
                    )
                    results.append(result)
                    
                    # Update relevance metrics
                    self.metrics.query_relevance.labels(
                        namespace=query_params['namespace']
                    ).observe(match.score)
            
            # Apply reranking if requested
            if config.rerank and len(results) > 1:
                results = await self._rerank_results(results, query_vector)
            
            # Update access tracking
            await self._update_access_tracking(results)
            
            # Cache results
            if cache_key and self.redis_client:
                await self._cache_query_results(cache_key, results)
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.QUERY.value,
                namespace=query_params['namespace']
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.QUERY.value,
                namespace=query_params['namespace'],
                status="success"
            ).inc()
            
            self.logger.debug(
                f"Query returned {len(results)} results from namespace {query_params['namespace']}",
                extra={
                    'results_count': len(results),
                    'duration_seconds': duration,
                    'namespace': query_params['namespace'],
                    'min_score': config.min_score
                }
            )
            
            return results
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.QUERY.value,
                namespace=config.namespace or VectorNamespace.AGENT_KNOWLEDGE.value,
                status="error"
            ).inc()
            
            raise YMERAException(f"Vector query failed: {str(e)}")
    
    def _build_pinecone_filter(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Build Pinecone-compatible filter from filter dictionary"""
        pinecone_filter = {}
        
        for key, value in filter_dict.items():
            if isinstance(value, list):
                pinecone_filter[key] = {"$in": value}
            elif isinstance(value, dict):
                if "$gte" in value or "$lte" in value or "$gt" in value or "$lt" in value:
                    pinecone_filter[key] = value
                else:
                    pinecone_filter[key] = {"$eq": value}
            else:
                pinecone_filter[key] = {"$eq": value}
        
        return pinecone_filter
    
    async def _rerank_results(self, results: List[QueryResult], query_vector: List[float]) -> List[QueryResult]:
        """Rerank results using additional relevance signals"""
        # Add learning-based reranking logic
        for result in results:
            # Boost based on access patterns
            access_count = result.metadata.learning_context.get('access_count', 0)
            recency_boost = self._calculate_recency_boost(
                result.metadata.timestamp
            )
            
            # Adjust score
            learning_boost = min(0.1, access_count * 0.01) + recency_boost
            result.score = min(1.0, result.score + learning_boost)
        
        # Sort by adjusted score
        return sorted(results, key=lambda x: x.score, reverse=True)
    
    def _calculate_recency_boost(self, timestamp: str) -> float:
        """Calculate recency boost for result ranking"""
        try:
            created_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            age_hours = (datetime.utcnow() - created_time.replace(tzinfo=None)).total_seconds() / 3600
            
            # Boost newer content (decay over 168 hours = 1 week)
            return max(0, 0.05 * (1 - age_hours / 168))
            
        except Exception:
            return 0.0
    
    async def _update_access_tracking(self, results: List[QueryResult]) -> None:
        """Update access tracking for learning optimization"""
        try:
            update_batch = []
            
            for result in results:
                # Create update vector with incremented access count
                current_access = result.metadata.learning_context.get('access_count', 0)
                
                update_vector = {
                    'id': result.id,
                    'values': [0.0] * self.dimension,  # Placeholder - actual values would be preserved
                    'set_metadata': {
                        'last_accessed': datetime.utcnow().isoformat(),
                        'access_count': current_access + 1
                    }
                }
                
                update_batch.append(update_vector)
            
            # Update in background to avoid blocking the query
            if update_batch:
                asyncio.create_task(self._background_metadata_update(update_batch, result.namespace))
                
        except Exception as e:
            self.logger.warning(f"Failed to update access tracking: {str(e)}")
    
    async def _background_metadata_update(self, update_batch: List[Dict], namespace: str) -> None:
        """Background metadata update to avoid blocking queries"""
        try:
            for update in update_batch:
                self.index.update(
                    id=update['id'],
                    set_metadata=update['set_metadata'],
                    namespace=namespace
                )
                
        except Exception as e:
            self.logger.warning(f"Background metadata update failed: {str(e)}")
    
    def _generate_query_cache_key(self, query_vector: List[float], config: VectorSearchConfig) -> str:
        """Generate cache key for query results"""
        query_hash = hashlib.md5(
            json.dumps(query_vector + [
                config.top_k, config.min_score, config.namespace,
                str(config.filter_dict)
            ], sort_keys=True).encode()
        ).hexdigest()
        
        return f"query_cache:{query_hash}"
    
    async def _get_cached_query(self, cache_key: str) -> Optional[List[QueryResult]]:
        """Retrieve cached query results"""
        try:
            if not self.redis_client:
                return None
            
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                results_data = json.loads(cached_data)
                return [
                    QueryResult(
                        id=r['id'],
                        score=r['score'],
                        metadata=VectorMetadata(**r['metadata']),
                        content=r.get('content'),
                        namespace=r['namespace']
                    )
                    for r in results_data
                ]
            
        except Exception as e:
            self.logger.warning(f"Cache retrieval failed: {str(e)}")
        
        return None
    
    async def _cache_query_results(self, cache_key: str, results: List[QueryResult]) -> None:
        """Cache query results"""
        try:
            if not self.redis_client:
                return
            
            # Serialize results
            results_data = [
                {
                    'id': r.id,
                    'score': r.score,
                    'metadata': r.metadata.to_dict(),
                    'content': r.content,
                    'namespace': r.namespace
                }
                for r in results
            ]
            
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(results_data)
            )
            
        except Exception as e:
            self.logger.warning(f"Cache storage failed: {str(e)}")
    
    async def delete_vectors(self,
                           ids: List[str],
                           namespace: str = VectorNamespace.AGENT_KNOWLEDGE.value,
                           filter_dict: Dict[str, Any] = None) -> Dict[str, Any]:
        """Delete vectors by ID or filter"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        
        try:
            delete_params = {'namespace': namespace}
            
            if ids:
                delete_params['ids'] = ids
            elif filter_dict:
                delete_params['filter'] = self._build_pinecone_filter(filter_dict)
            else:
                raise YMERAException("Either ids or filter_dict must be provided")
            
            # Execute deletion
            response = self.index.delete(**delete_params)
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.DELETE.value,
                namespace=namespace
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.DELETE.value,
                namespace=namespace,
                status="success"
            ).inc()
            
            # Update namespace stats
            await self._update_namespace_stats(namespace)
            
            result = {
                'deleted_count': len(ids) if ids else 'unknown',
                'duration_seconds': duration,
                'namespace': namespace,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(
                f"Deleted vectors from namespace {namespace}",
                extra=result
            )
            
            return result
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.DELETE.value,
                namespace=namespace,
                status="error"
            ).inc()
            
            raise YMERAException(f"Vector deletion failed: {str(e)}")
    
    async def fetch_vectors(self,
                          ids: List[str],
                          namespace: str = VectorNamespace.AGENT_KNOWLEDGE. async def fetch_vectors(self,
                          ids: List[str],
                          namespace: str = VectorNamespace.AGENT_KNOWLEDGE.value) -> Dict[str, QueryResult]:
        """Fetch vectors by IDs"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        
        try:
            response = self.index.fetch(
                ids=ids,
                namespace=namespace
            )
            
            # Convert to QueryResult objects
            results = {}
            for vector_id, vector_data in response.vectors.items():
                metadata_dict = vector_data.get('metadata', {})
                metadata = VectorMetadata(**metadata_dict)
                
                results[vector_id] = QueryResult(
                    id=vector_id,
                    score=1.0,  # Fetch doesn't provide scores
                    metadata=metadata,
                    content=metadata_dict.get('content'),
                    namespace=namespace
                )
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.FETCH.value,
                namespace=namespace
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.FETCH.value,
                namespace=namespace,
                status="success"
            ).inc()
            
            self.logger.debug(
                f"Fetched {len(results)} vectors from namespace {namespace}",
                extra={
                    'requested_count': len(ids),
                    'returned_count': len(results),
                    'duration_seconds': duration,
                    'namespace': namespace
                }
            )
            
            return results
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.FETCH.value,
                namespace=namespace,
                status="error"
            ).inc()
            
            raise YMERAException(f"Vector fetch failed: {str(e)}")
    
    async def update_vector_metadata(self,
                                   vector_id: str,
                                   metadata_updates: Dict[str, Any],
                                   namespace: str = VectorNamespace.AGENT_KNOWLEDGE.value) -> Dict[str, Any]:
        """Update vector metadata without changing the vector values"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        
        try:
            # Add learning-specific tracking
            metadata_updates.update({
                'last_updated': datetime.utcnow().isoformat(),
                'update_count': metadata_updates.get('update_count', 0) + 1
            })
            
            self.index.update(
                id=vector_id,
                set_metadata=metadata_updates,
                namespace=namespace
            )
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.UPDATE.value,
                namespace=namespace
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.UPDATE.value,
                namespace=namespace,
                status="success"
            ).inc()
            
            result = {
                'vector_id': vector_id,
                'updated_fields': list(metadata_updates.keys()),
                'duration_seconds': duration,
                'namespace': namespace,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.debug(
                f"Updated metadata for vector {vector_id} in namespace {namespace}",
                extra=result
            )
            
            return result
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.UPDATE.value,
                namespace=namespace,
                status="error"
            ).inc()
            
            raise YMERAException(f"Vector metadata update failed: {str(e)}")
    
    async def get_namespace_stats(self, namespace: str = None) -> Dict[str, Any]:
        """Get comprehensive statistics for a namespace or entire index"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"stats:{namespace or 'all'}"
            if cache_key in self.index_stats_cache:
                cached_time, cached_stats = self.index_stats_cache[cache_key]
                if time.time() - cached_time < 60:  # 1-minute cache
                    return cached_stats
            
            # Get stats from Pinecone
            stats = self.index.describe_index_stats()
            
            if namespace:
                namespace_stats = stats.namespaces.get(namespace, {})
                result = {
                    'namespace': namespace,
                    'total_vector_count': namespace_stats.get('vector_count', 0),
                    'dimension': self.dimension,
                    'index_fullness': stats.index_fullness,
                    'total_vectors_all_namespaces': stats.total_vector_count
                }
            else:
                result = {
                    'total_vector_count': stats.total_vector_count,
                    'dimension': self.dimension,
                    'index_fullness': stats.index_fullness,
                    'namespaces': {}
                }
                
                for ns_name, ns_stats in stats.namespaces.items():
                    result['namespaces'][ns_name] = {
                        'vector_count': ns_stats.get('vector_count', 0)
                    }
            
            # Add learning-specific stats
            result.update({
                'last_updated': datetime.utcnow().isoformat(),
                'cache_hit_rate': self._calculate_cache_hit_rate(),
                'average_query_latency': self._calculate_avg_query_latency()
            })
            
            # Cache results
            self.index_stats_cache[cache_key] = (time.time(), result)
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.STATS.value,
                namespace=namespace or "all"
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.STATS.value,
                namespace=namespace or "all",
                status="success"
            ).inc()
            
            return result
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.STATS.value,
                namespace=namespace or "all",
                status="error"
            ).inc()
            
            raise YMERAException(f"Failed to get namespace stats: {str(e)}")
    
    async def list_vectors(self,
                         namespace: str = VectorNamespace.AGENT_KNOWLEDGE.value,
                         prefix: str = None,
                         limit: int = 100) -> List[str]:
        """List vector IDs in a namespace"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        
        try:
            list_params = {
                'namespace': namespace,
                'limit': limit
            }
            
            if prefix:
                list_params['prefix'] = prefix
            
            response = self.index.list(**list_params)
            vector_ids = response.vectors or []
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.operation_duration.labels(
                operation_type=VectorOperationType.LIST.value,
                namespace=namespace
            ).observe(duration)
            
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.LIST.value,
                namespace=namespace,
                status="success"
            ).inc()
            
            self.logger.debug(
                f"Listed {len(vector_ids)} vectors in namespace {namespace}",
                extra={
                    'count': len(vector_ids),
                    'namespace': namespace,
                    'prefix': prefix,
                    'duration_seconds': duration
                }
            )
            
            return vector_ids
            
        except Exception as e:
            self.metrics.operations_total.labels(
                operation_type=VectorOperationType.LIST.value,
                namespace=namespace,
                status="error"
            ).inc()
            
            raise YMERAException(f"Vector listing failed: {str(e)}")
    
    async def search_by_metadata(self,
                               filter_dict: Dict[str, Any],
                               config: VectorSearchConfig = None) -> List[QueryResult]:
        """Search vectors by metadata filters only (no vector similarity)"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        config = config or VectorSearchConfig()
        
        try:
            # Create a zero vector for metadata-only search
            zero_vector = [0.0] * self.dimension
            
            # Update config to use filter
            config.filter_dict = filter_dict
            config.min_score = 0.0  # Accept all scores for metadata search
            
            # Perform search
            results = await self.query_vectors(
                query_vector=zero_vector,
                config=config,
                use_cache=False  # Don't cache metadata searches
            )
            
            self.logger.debug(
                f"Metadata search returned {len(results)} results",
                extra={
                    'filter': filter_dict,
                    'namespace': config.namespace,
                    'results_count': len(results)
                }
            )
            
            return results
            
        except Exception as e:
            raise YMERAException(f"Metadata search failed: {str(e)}")
    
    async def cleanup_expired_vectors(self,
                                    namespace: str = None,
                                    batch_size: int = 1000) -> Dict[str, Any]:
        """Clean up vectors that have exceeded their TTL"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        namespaces_to_clean = [namespace] if namespace else [ns.value for ns in VectorNamespace]
        
        total_deleted = 0
        
        try:
            for ns in namespaces_to_clean:
                # Find expired vectors
                expired_filter = {
                    'expires_at': {'$lt': datetime.utcnow().isoformat()}
                }
                
                # Get expired vector IDs
                expired_vectors = await self.search_by_metadata(
                    filter_dict=expired_filter,
                    config=VectorSearchConfig(
                        top_k=batch_size,
                        namespace=ns,
                        include_metadata=False
                    )
                )
                
                if expired_vectors:
                    expired_ids = [v.id for v in expired_vectors]
                    
                    # Delete expired vectors
                    delete_result = await self.delete_vectors(
                        ids=expired_ids,
                        namespace=ns
                    )
                    
                    deleted_count = delete_result.get('deleted_count', 0)
                    if isinstance(deleted_count, int):
                        total_deleted += deleted_count
                    
                    self.logger.info(
                        f"Cleaned up {len(expired_ids)} expired vectors from namespace {ns}"
                    )
            
            duration = time.time() - start_time
            
            result = {
                'total_deleted': total_deleted,
                'namespaces_cleaned': len(namespaces_to_clean),
                'duration_seconds': duration,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info("Vector cleanup completed", extra=result)
            
            return result
            
        except Exception as e:
            raise YMERAException(f"Vector cleanup failed: {str(e)}")
    
    async def optimize_learning_vectors(self,
                                      namespace: str = VectorNamespace.LEARNING_PATTERNS.value,
                                      min_access_threshold: int = 5) -> Dict[str, Any]:
        """Optimize vectors based on learning patterns and access frequency"""
        if not self.is_initialized:
            raise YMERAException("Pinecone manager not initialized")
        
        start_time = time.time()
        
        try:
            # Find underused vectors
            underused_filter = {
                'access_count': {'$lt': min_access_threshold},
                'created_at': {'$lt': (datetime.utcnow() - timedelta(days=7)).isoformat()}
            }
            
            underused_vectors = await self.search_by_metadata(
                filter_dict=underused_filter,
                config=VectorSearchConfig(
                    top_k=1000,
                    namespace=namespace,
                    include_metadata=True
                )
            )
            
            # Archive or remove underused vectors
            archived_count = 0
            removed_count = 0
            
            for vector in underused_vectors:
                importance = vector.metadata.learning_context.get('importance_score', 0.5)
                
                if importance < 0.3:
                    # Remove low importance, underused vectors
                    await self.delete_vectors(ids=[vector.id], namespace=namespace)
                    removed_count += 1
                else:
                    # Archive medium importance vectors by reducing their relevance
                    await self.update_vector_metadata(
                        vector_id=vector.id,
                        metadata_updates={
                            'learning_phase': 'archived',
                            'relevance_score': importance * 0.5,
                            'archived_at': datetime.utcnow().isoformat()
                        },
                        namespace=namespace
                    )
                    archived_count += 1
            
            # Update frequently accessed vectors
            popular_filter = {
                'access_count': {'$gte': min_access_threshold * 3}
            }
            
            popular_vectors = await self.search_by_metadata(
                filter_dict=popular_filter,
                config=VectorSearchConfig(
                    top_k=500,
                    namespace=namespace,
                    include_metadata=True
                )
            )
            
            boosted_count = 0
            for vector in popular_vectors:
                current_importance = vector.metadata.learning_context.get('importance_score', 0.5)
                new_importance = min(1.0, current_importance * 1.2)
                
                await self.update_vector_metadata(
                    vector_id=vector.id,
                    metadata_updates={
                        'learning_phase': 'optimized',
                        'importance_score': new_importance,
                        'optimized_at': datetime.utcnow().isoformat()
                    },
                    namespace=namespace
                )
                boosted_count += 1
            
            duration = time.time() - start_time
            
            result = {
                'archived_count': archived_count,
                'removed_count': removed_count,
                'boosted_count': boosted_count,
                'total_processed': len(underused_vectors) + len(popular_vectors),
                'duration_seconds': duration,
                'namespace': namespace,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info("Learning optimization completed", extra=result)
            
            return result
            
        except Exception as e:
            raise YMERAException(f"Learning optimization failed: {str(e)}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the Pinecone manager"""
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'initialized': self.is_initialized,
                'last_health_check': self.last_health_check,
                'active_connections': self.active_connections,
                'components': {}
            }
            
            # Check Pinecone connection
            try:
                stats = await self.get_namespace_stats()
                health_status['components']['pinecone'] = {
                    'status': 'healthy',
                    'total_vectors': stats.get('total_vector_count', 0),
                    'index_fullness': stats.get('index_fullness', 0)
                }
            except Exception as e:
                health_status['components']['pinecone'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_status['status'] = 'degraded'
            
            # Check Redis cache
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    health_status['components']['redis'] = {
                        'status': 'healthy',
                        'cache_enabled': True
                    }
                except Exception as e:
                    health_status['components']['redis'] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
                    health_status['status'] = 'degraded'
            else:
                health_status['components']['redis'] = {
                    'status': 'disabled',
                    'cache_enabled': False
                }
            
            # Add performance metrics
            health_status['performance'] = {
                'cache_hit_rate': self._calculate_cache_hit_rate(),
                'average_query_latency': self._calculate_avg_query_latency(),
                'operations_per_minute': self._calculate_operations_per_minute()
            }
            
            self.last_health_check = datetime.utcnow().isoformat()
            
            return health_status
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
                'initialized': self.is_initialized
            }
    
    # Background task methods
    
    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                health = await self.get_health_status()
                
                if health['status'] != 'healthy':
                    self.logger.warning("Health check failed", extra=health)
                    
            except Exception as e:
                self.logger.error(f"Health check loop error: {str(e)}")
    
    async def _batch_processor_loop(self) -> None:
        """Background batch processing loop"""
        while True:
            try:
                await asyncio.sleep(5)  # Process every 5 seconds
                
                if self.batch_operations:
                    operations = self.batch_operations[:]
                    self.batch_operations.clear()
                    
                    # Process batch operations
                    await self._process_batch_operations(operations)
                    
            except Exception as e:
                self.logger.error(f"Batch processor loop error: {str(e)}")
    
    async def _cache_cleanup_loop(self) -> None:
        """Background cache cleanup loop"""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                # Clean query cache
                current_time = time.time()
                expired_keys = [
                    key for key, (timestamp, _) in self.query_cache.items()
                    if current_time - timestamp > self.cache_ttl
                ]
                
                for key in expired_keys:
                    del self.query_cache[key]
                
                # Clean stats cache
                expired_stats = [
                    key for key, (timestamp, _) in self.index_stats_cache.items()
                    if current_time - timestamp > 60
                ]
                
                for key in expired_stats:
                    del self.index_stats_cache[key]
                
                if expired_keys or expired_stats:
                    self.logger.debug(
                        f"Cache cleanup: removed {len(expired_keys)} query cache entries "
                        f"and {len(expired_stats)} stats cache entries"
                    )
                    
            except Exception as e:
                self.logger.error(f"Cache cleanup loop error: {str(e)}")
    
    async def _learning_optimization_loop(self) -> None:
        """Background learning optimization loop"""
        while True:
            try:
                await asyncio.sleep(3600)  # Optimize every hour
                
                # Run optimization for learning patterns namespace
                await self.optimize_learning_vectors()
                
                # Cleanup expired vectors
                await self.cleanup_expired_vectors()
                
            except Exception as e:
                self.logger.error(f"Learning optimization loop error: {str(e)}")
    
    async def _process_batch_operations(self, operations: List[Dict]) -> None:
        """Process queued batch operations"""
        try:
            # Group operations by type and namespace
            grouped_ops = {}
            
            for op in operations:
                key = (op['type'], op['namespace'])
                if key not in grouped_ops:
                    grouped_ops[key] = []
                grouped_ops[key].append(op)
            
            # Process each group
            for (op_type, namespace), ops in grouped_ops.items():
                if op_type == 'upsert':
                    vectors = [op['data'] for op in ops]
                    await self.upsert_vectors(vectors, namespace)
                elif op_type == 'delete':
                    ids = [op['data'] for op in ops]
                    await self.delete_vectors(ids, namespace)
                # Add more operation types as needed
                
        except Exception as e:
            self.logger.error(f"Batch operation processing failed: {str(e)}")
    
    async def _update_namespace_stats(self, namespace: str) -> None:
        """Update cached namespace statistics"""
        try:
            cache_key = f"stats:{namespace}"
            if cache_key in self.index_stats_cache:
                del self.index_stats_cache[cache_key]
            
            # Update metrics
            stats = await self.get_namespace_stats(namespace)
            if stats:
                self.metrics.vector_count.labels(namespace=namespace).set(
                    stats.get('total_vector_count', 0)
                )
                
        except Exception as e:
            self.logger.warning(f"Failed to update namespace stats: {str(e)}")
    
    # Utility methods
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate for performance monitoring"""
        # This would be implemented based on actual cache statistics
        return 0.85  # Placeholder
    
    def _calculate_avg_query_latency(self) -> float:
        """Calculate average query latency"""
        # This would be implemented based on actual timing data
        return 0.15  # Placeholder in seconds
    
    def _calculate_operations_per_minute(self) -> float:
        """Calculate operations per minute rate"""
        # This would be implemented based on actual operation counts
        return 120.0  # Placeholder
    
    async def shutdown(self) -> None:
        """Graceful shutdown of the Pinecone manager"""
        try:
            self.logger.info("Shutting down Pinecone manager...")
            
            # Process any remaining batch operations
            if self.batch_operations:
                await self._process_batch_operations(self.batch_operations)
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            # Clear caches
            self.query_cache.clear()
            self.index_stats_cache.clear()
            
            self.is_initialized = False
            self.logger.info("Pinecone manager shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager for connection management"""
        self.active_connections += 1
        try:
            yield self
        finally:
            self.active_connections -= 1
    
    def __str__(self) -> str:
        return f"PineconeManager(index={self.index_name}, initialized={self.is_initialized})"
    
    def __repr__(self) -> str:
        return (
            f"PineconeManager(index_name='{self.index_name}', "
            f"dimension={self.dimension}, metric='{self.metric}', "
            f"initialized={self.is_initialized})"
        )