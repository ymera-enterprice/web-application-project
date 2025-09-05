"""
YMERA Enterprise Metrics Collection System
Production-Ready Performance Monitoring & Analytics
"""

import asyncio
import json
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import logging
from enum import Enum
import redis.asyncio as redis
from concurrent.futures import ThreadPoolExecutor
import gc
import sys
import platform
import socket
import uuid
from statistics import mean, median, stdev

class MetricType(Enum):
    """Enumeration of metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"

class MetricScope(Enum):
    """Enumeration of metric scopes"""
    SYSTEM = "system"
    AGENT = "agent"
    LEARNING = "learning"
    API = "api"
    DATABASE = "database"
    REDIS = "redis"
    AI_SERVICE = "ai_service"
    ORCHESTRATION = "orchestration"

@dataclass
class MetricPoint:
    """Individual metric data point"""
    name: str
    value: Union[int, float]
    timestamp: datetime
    metric_type: MetricType
    scope: MetricScope
    tags: Dict[str, str]
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'metric_type': self.metric_type.value,
            'scope': self.scope.value,
            'tags': self.tags,
            'metadata': self.metadata or {}
        }

@dataclass
class SystemResourceMetrics:
    """System resource utilization metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    load_average: List[float]
    active_connections: int
    thread_count: int
    process_count: int
    file_descriptors: int
    timestamp: datetime

@dataclass
class AgentPerformanceMetrics:
    """Individual agent performance metrics"""
    agent_id: str
    agent_type: str
    status: str
    task_count_total: int
    task_count_active: int
    task_count_completed: int
    task_count_failed: int
    average_task_duration: float
    last_activity: datetime
    memory_usage_mb: float
    cpu_usage_percent: float
    error_rate: float
    success_rate: float
    throughput_per_minute: float
    queue_size: int
    learning_score: float
    adaptation_rate: float

@dataclass
class LearningEngineMetrics:
    """Learning engine performance metrics"""
    total_learning_sessions: int
    active_learning_sessions: int
    knowledge_base_size: int
    vector_embeddings_count: int
    learning_rate: float
    adaptation_score: float
    model_accuracy: float
    training_iterations: int
    last_training_time: datetime
    feedback_count: int
    positive_feedback_ratio: float
    knowledge_retention_score: float
    inference_latency_ms: float
    embedding_generation_time_ms: float

@dataclass
class OrchestrationMetrics:
    """Agent orchestration metrics"""
    active_workflows: int
    completed_workflows: int
    failed_workflows: int
    average_workflow_duration: float
    coordination_overhead_ms: float
    message_throughput: float
    agent_coordination_score: float
    resource_allocation_efficiency: float

class MetricsAggregator:
    """Advanced metrics aggregation and analysis"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.data_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.lock = threading.RLock()
    
    def add_metric(self, metric: MetricPoint):
        """Add a metric point to the aggregation window"""
        with self.lock:
            key = f"{metric.scope.value}.{metric.name}"
            self.data_windows[key].append(metric)
    
    def get_statistics(self, metric_key: str) -> Dict[str, float]:
        """Get statistical analysis of a metric"""
        with self.lock:
            window = self.data_windows.get(metric_key, deque())
            if not window:
                return {}
            
            values = [point.value for point in window if isinstance(point.value, (int, float))]
            if not values:
                return {}
            
            try:
                return {
                    'count': len(values),
                    'sum': sum(values),
                    'mean': mean(values),
                    'median': median(values),
                    'min': min(values),
                    'max': max(values),
                    'std_dev': stdev(values) if len(values) > 1 else 0.0,
                    'latest': values[-1],
                    'trend': self._calculate_trend(values)
                }
            except Exception as e:
                logging.error(f"Error calculating statistics for {metric_key}: {e}")
                return {}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction"""
        if len(values) < 2:
            return "stable"
        
        recent = values[-min(10, len(values)):]
        older = values[-min(20, len(values)):-10] or values[:1]
        
        recent_avg = mean(recent)
        older_avg = mean(older)
        
        if recent_avg > older_avg * 1.05:
            return "increasing"
        elif recent_avg < older_avg * 0.95:
            return "decreasing"
        else:
            return "stable"

class MetricsCollector:
    """
    Enterprise-grade metrics collection system for YMERA multi-agent platform
    Provides comprehensive monitoring, analytics, and performance insights
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        health_monitor=None,
        collection_interval: int = 30,
        retention_hours: int = 24,
        batch_size: int = 100,
        enable_detailed_profiling: bool = True
    ):
        self.redis_client = redis_client
        self.health_monitor = health_monitor
        self.collection_interval = collection_interval
        self.retention_hours = retention_hours
        self.batch_size = batch_size
        self.enable_detailed_profiling = enable_detailed_profiling
        
        # Core components
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")
        self.aggregator = MetricsAggregator()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="metrics")
        
        # State management
        self.is_running = False
        self.is_initialized = False
        self.collection_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.last_collection_time: Optional[datetime] = None
        
        # Performance tracking
        self.metrics_buffer: List[MetricPoint] = []
        self.buffer_lock = asyncio.Lock()
        self.collection_count = 0
        self.error_count = 0
        
        # System identification
        self.instance_id = str(uuid.uuid4())[:8]
        self.hostname = socket.gethostname()
        self.platform_info = {
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version()
        }
        
        # Metric keys
        self.redis_keys = {
            'metrics': f"ymera:metrics:{self.instance_id}",
            'system_stats': f"ymera:system_stats:{self.instance_id}",
            'agent_stats': f"ymera:agent_stats:{self.instance_id}",
            'learning_stats': f"ymera:learning_stats:{self.instance_id}",
            'orchestration_stats': f"ymera:orchestration_stats:{self.instance_id}",
            'performance_summary': f"ymera:performance_summary:{self.instance_id}"
        }
        
        # Initialize baseline metrics
        self._baseline_metrics = {}
    
    async def initialize(self) -> bool:
        """Initialize the metrics collection system"""
        try:
            self.logger.info("Initializing YMERA Metrics Collection System...")
            
            # Test Redis connection
            await self.redis_client.ping()
            
            # Set up Redis data structures
            await self._setup_redis_structures()
            
            # Initialize baseline metrics
            await self._collect_baseline_metrics()
            
            # Start background tasks
            if not self.collection_task:
                self.collection_task = asyncio.create_task(self._collection_loop())
            
            if not self.cleanup_task:
                self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            self.is_initialized = True
            self.logger.info("✅ Metrics Collection System initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize metrics collector: {e}")
            return False
    
    async def _setup_redis_structures(self):
        """Set up Redis data structures for metrics storage"""
        pipeline = self.redis_client.pipeline()
        
        # Set expiration for all metric keys
        for key in self.redis_keys.values():
            pipeline.expire(key, self.retention_hours * 3600)
        
        await pipeline.execute()
    
    async def _collect_baseline_metrics(self):
        """Collect baseline system metrics for comparison"""
        try:
            # System resources
            process = psutil.Process()
            system_info = {
                'boot_time': psutil.boot_time(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'disk_total': psutil.disk_usage('/').total,
                'process_start_time': process.create_time()
            }
            
            self._baseline_metrics = system_info
            await self.redis_client.hset(
                f"{self.redis_keys['system_stats']}:baseline",
                mapping={k: json.dumps(v) for k, v in system_info.items()}
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting baseline metrics: {e}")
    
    async def start_collection(self):
        """Start metrics collection"""
        if not self.is_initialized:
            await self.initialize()
        
        self.is_running = True
        self.logger.info("🚀 Metrics collection started")
    
    async def stop_collection(self):
        """Stop metrics collection gracefully"""
        self.is_running = False
        
        # Cancel background tasks
        if self.collection_task and not self.collection_task.done():
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining metrics
        await self._flush_metrics_buffer()
        
        self.executor.shutdown(wait=True)
        self.logger.info("✅ Metrics collection stopped")
    
    async def _collection_loop(self):
        """Main metrics collection loop"""
        while self.is_running:
            try:
                start_time = time.time()
                
                # Collect all metric types
                await asyncio.gather(
                    self._collect_system_metrics(),
                    self._collect_agent_metrics(),
                    self._collect_learning_metrics(),
                    self._collect_orchestration_metrics(),
                    self._collect_api_metrics(),
                    return_exceptions=True
                )
                
                # Flush metrics buffer
                await self._flush_metrics_buffer()
                
                collection_duration = time.time() - start_time
                self.collection_count += 1
                self.last_collection_time = datetime.utcnow()
                
                # Record collection performance
                await self._record_metric(
                    name="collection_duration_seconds",
                    value=collection_duration,
                    metric_type=MetricType.TIMER,
                    scope=MetricScope.SYSTEM,
                    tags={"component": "metrics_collector"}
                )
                
                # Sleep until next collection
                await asyncio.sleep(max(0, self.collection_interval - collection_duration))
                
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _cleanup_loop(self):
        """Background cleanup of old metrics"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Run hourly
                await self._cleanup_old_metrics()
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    async def _collect_system_metrics(self):
        """Collect comprehensive system resource metrics"""
        try:
            # Use thread executor for CPU-intensive operations
            system_metrics = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._get_system_resource_metrics
            )
            
            # Convert to metric points
            timestamp = datetime.utcnow()
            metrics = [
                MetricPoint("cpu_usage_percent", system_metrics.cpu_percent, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("memory_usage_percent", system_metrics.memory_percent, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("memory_used_mb", system_metrics.memory_used_mb, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("disk_usage_percent", system_metrics.disk_usage_percent, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("network_bytes_sent", system_metrics.network_bytes_sent, timestamp, MetricType.COUNTER, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("network_bytes_recv", system_metrics.network_bytes_recv, timestamp, MetricType.COUNTER, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("active_connections", system_metrics.active_connections, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("thread_count", system_metrics.thread_count, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
                MetricPoint("process_count", system_metrics.process_count, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname}),
            ]
            
            # Add load average if available
            if system_metrics.load_average:
                for i, load in enumerate(system_metrics.load_average):
                    metrics.append(
                        MetricPoint(f"load_average_{i+1}min", load, timestamp, MetricType.GAUGE, MetricScope.SYSTEM, {"host": self.hostname})
                    )
            
            await self._add_metrics_to_buffer(metrics)
            
            # Store detailed system stats
            await self.redis_client.hset(
                self.redis_keys['system_stats'],
                f"snapshot_{int(timestamp.timestamp())}",
                json.dumps(asdict(system_metrics), default=str)
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
    
    def _get_system_resource_metrics(self) -> SystemResourceMetrics:
        """Get system resource metrics (CPU-intensive, run in thread)"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_used_mb = (memory.total - memory.available) / 1024 / 1024
            memory_available_mb = memory.available / 1024 / 1024
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / 1024 / 1024 / 1024
            disk_free_gb = disk.free / 1024 / 1024 / 1024
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Load average (Unix-like systems)
            load_average = []
            try:
                if hasattr(psutil, 'getloadavg'):
                    load_average = list(psutil.getloadavg())
            except:
                pass
            
            # Process metrics
            try:
                connections = len(psutil.net_connections())
            except:
                connections = 0
            
            # Thread and process counts
            current_process = psutil.Process()
            thread_count = current_process.num_threads()
            process_count = len(psutil.pids())
            
            # File descriptors (Unix-like systems)
            file_descriptors = 0
            try:
                file_descriptors = current_process.num_fds()
            except:
                pass
            
            return SystemResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_used_gb=disk_used_gb,
                disk_free_gb=disk_free_gb,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                load_average=load_average,
                active_connections=connections,
                thread_count=thread_count,
                process_count=process_count,
                file_descriptors=file_descriptors,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            self.logger.error(f"Error getting system resource metrics: {e}")
            return SystemResourceMetrics(
                cpu_percent=0.0, memory_percent=0.0, memory_used_mb=0.0,
                memory_available_mb=0.0, disk_usage_percent=0.0, disk_used_gb=0.0,
                disk_free_gb=0.0, network_bytes_sent=0, network_bytes_recv=0,
                load_average=[], active_connections=0, thread_count=0,
                process_count=0, file_descriptors=0, timestamp=datetime.utcnow()
            )
    
    async def _collect_agent_metrics(self):
        """Collect metrics from all registered agents"""
        try:
            # Get agent data from health monitor if available
            if not self.health_monitor:
                return
            
            agent_health = await self.health_monitor.get_agent_health()
            timestamp = datetime.utcnow()
            
            for agent_id, health_data in agent_health.items():
                agent_metrics = [
                    MetricPoint(
                        "agent_status", 1 if health_data.get('status') == 'healthy' else 0,
                        timestamp, MetricType.GAUGE, MetricScope.AGENT,
                        {"agent_id": agent_id, "agent_type": health_data.get('type', 'unknown')}
                    ),
                    MetricPoint(
                        "agent_response_time_ms", health_data.get('response_time_ms', 0),
                        timestamp, MetricType.TIMER, MetricScope.AGENT,
                        {"agent_id": agent_id}
                    ),
                    MetricPoint(
                        "agent_memory_usage_mb", health_data.get('memory_usage_mb', 0),
                        timestamp, MetricType.GAUGE, MetricScope.AGENT,
                        {"agent_id": agent_id}
                    ),
                    MetricPoint(
                        "agent_task_count", health_data.get('active_tasks', 0),
                        timestamp, MetricType.GAUGE, MetricScope.AGENT,
                        {"agent_id": agent_id}
                    ),
                    MetricPoint(
                        "agent_error_rate", health_data.get('error_rate', 0),
                        timestamp, MetricType.GAUGE, MetricScope.AGENT,
                        {"agent_id": agent_id}
                    )
                ]
                
                await self._add_metrics_to_buffer(agent_metrics)
                
                # Store detailed agent stats
                await self.redis_client.hset(
                    self.redis_keys['agent_stats'],
                    f"{agent_id}_{int(timestamp.timestamp())}",
                    json.dumps(health_data, default=str)
                )
            
        except Exception as e:
            self.logger.error(f"Error collecting agent metrics: {e}")
    
    async def _collect_learning_metrics(self):
        """Collect learning engine performance metrics"""
        try:
            # This would integrate with your learning engine
            timestamp = datetime.utcnow()
            
            # Placeholder for learning metrics - integrate with actual learning engine
            learning_metrics = [
                MetricPoint(
                    "learning_active_sessions", 0,  # Get from learning engine
                    timestamp, MetricType.GAUGE, MetricScope.LEARNING,
                    {"component": "learning_engine"}
                ),
                MetricPoint(
                    "knowledge_base_size", 0,  # Get from knowledge base
                    timestamp, MetricType.GAUGE, MetricScope.LEARNING,
                    {"component": "knowledge_base"}
                ),
                MetricPoint(
                    "model_accuracy", 0.0,  # Get from learning engine
                    timestamp, MetricType.GAUGE, MetricScope.LEARNING,
                    {"component": "model_performance"}
                )
            ]
            
            await self._add_metrics_to_buffer(learning_metrics)
            
        except Exception as e:
            self.logger.error(f"Error collecting learning metrics: {e}")
    
    async def _collect_orchestration_metrics(self):
        """Collect agent orchestration metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # These would integrate with your orchestrator
            orchestration_metrics = [
                MetricPoint(
                    "active_workflows", 0,  # Get from orchestrator
                    timestamp, MetricType.GAUGE, MetricScope.ORCHESTRATION,
                    {"component": "orchestrator"}
                ),
                MetricPoint(
                    "workflow_completion_rate", 0.0,  # Calculate from orchestrator
                    timestamp, MetricType.GAUGE, MetricScope.ORCHESTRATION,
                    {"component": "orchestrator"}
                ),
                MetricPoint(
                    "coordination_overhead_ms", 0.0,  # Get from orchestrator
                    timestamp, MetricType.TIMER, MetricScope.ORCHESTRATION,
                    {"component": "coordination"}
                )
            ]
            
            await self._add_metrics_to_buffer(orchestration_metrics)
            
        except Exception as e:
            self.logger.error(f"Error collecting orchestration metrics: {e}")
    
    async def _collect_api_metrics(self):
        """Collect API performance metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # Get Redis metrics
            info = await self.redis_client.info()
            redis_metrics = [
                MetricPoint(
                    "redis_connected_clients", info.get('connected_clients', 0),
                    timestamp, MetricType.GAUGE, MetricScope.REDIS,
                    {"component": "redis"}
                ),
                MetricPoint(
                    "redis_used_memory", info.get('used_memory', 0),
                    timestamp, MetricType.GAUGE, MetricScope.REDIS,
                    {"component": "redis"}
                ),
                MetricPoint(
                    "redis_keyspace_hits", info.get('keyspace_hits', 0),
                    timestamp, MetricType.COUNTER, MetricScope.REDIS,
                    {"component": "redis"}
                ),
                MetricPoint(
                    "redis_keyspace_misses", info.get('keyspace_misses', 0),
                    timestamp, MetricType.COUNTER, MetricScope.REDIS,
                    {"component": "redis"}
                )
            ]
            
            await self._add_metrics_to_buffer(redis_metrics)
            
        except Exception as e:
            self.logger.error(f"Error collecting API metrics: {e}")
    
    async def _record_metric(self, name: str, value: Union[int, float], 
                           metric_type: MetricType, scope: MetricScope, 
                           tags: Dict[str, str], metadata: Optional[Dict[str, Any]] = None):
        """Record a single metric"""
        metric = MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            metric_type=metric_type,
            scope=scope,
            tags=tags,
            metadata=metadata
        )
        
        await self._add_metrics_to_buffer([metric])
    
    async def _add_metrics_to_buffer(self, metrics: List[MetricPoint]):
        """Add metrics to the buffer for batch processing"""
        async with self.buffer_lock:
            self.metrics_buffer.extend(metrics)
            
            # Add to aggregator for real-time statistics
            for metric in metrics:
                self.aggregator.add_metric(metric)
    
    async def _flush_metrics_buffer(self):
        """Flush metrics buffer to Redis"""
        async with self.buffer_lock:
            if not self.metrics_buffer:
                return
            
            try:
                # Prepare batch for Redis
                pipeline = self.redis_client.pipeline()
                
                for metric in self.metrics_buffer:
                    # Store individual metric
                    key = f"{self.redis_keys['metrics']}:{metric.scope.value}:{metric.name}"
                    pipeline.zadd(key, {json.dumps(metric.to_dict()): int(metric.timestamp.timestamp())})
                    pipeline.expire(key, self.retention_hours * 3600)
                
                await pipeline.execute()
                
                self.logger.debug(f"Flushed {len(self.metrics_buffer)} metrics to Redis")
                self.metrics_buffer.clear()
                
            except Exception as e:
                self.logger.error(f"Error flushing metrics buffer: {e}")
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics data"""
        try:
            cutoff_timestamp = int((datetime.utcnow() - timedelta(hours=self.retention_hours)).timestamp())
            
            # Clean up all metric keys
            for pattern in [f"{self.redis_keys['metrics']}:*", 
                          f"{self.redis_keys['system_stats']}:*",
                          f"{self.redis_keys['agent_stats']}:*"]:
                
                keys = await self.redis_client.keys(pattern)
                if keys:
                    pipeline = self.redis_client.pipeline()
                    for key in keys:
                        pipeline.zremrangebyscore(key, 0, cutoff_timestamp)
                    await pipeline.execute()
            
            self.logger.info(f"Cleaned up metrics older than {self.retention_hours} hours")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old metrics: {e}")
    
    # Public API Methods
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        try:
            return {
                'collection_stats': {
                    'is_running': self.is_running,
                    'collection_count': self.collection_count,
                    'error_count': self.error_count,
                    'last_collection': self.last_collection_time.isoformat() if self.last_collection_time else None,
                    'instance_id': self.instance_id
                },
                'system_metrics': await self._get_latest_system_metrics(),
                'agent_metrics': await self._get_agent_performance_summary(),
                'learning_metrics': await self._get_learning_performance_summary(),
                'orchestration_metrics': await self._get_orchestration_summary(),
                'resource_efficiency': await self._calculate_resource_efficiency()
            }
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    async def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics"""
        try:
            all_metrics = {}
            
            # Get metrics from all scopes
            for scope in MetricScope:
                scope_metrics = await self._get_metrics_by_scope(scope)
                if scope_metrics:
                    all_metrics[scope.value] = scope_metrics
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': all_metrics,
                'statistics': await self._get_aggregated_statistics(),
                'system_info': {
                    'hostname': self.hostname,
                    'instance_id': self.instance_id,
                    'platform': self.platform_info
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting all metrics: {e}")
            return {}
    
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage metrics"""
        try:
            current_metrics = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._get_system_resource_metrics
            )
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'cpu': {
                    'usage_percent': current_metrics.cpu_percent,
                    'load_average': current_metrics.load_average
                },
                'memory': {
                    'usage_percent': current_metrics.memory_percent,
                    'used_mb': current_metrics.memory_used_mb,
                    'available_mb': current_metrics.memory_available_mb
                },
                'disk': {
                    'usage_percent': current_metrics.disk_usage_percent,
                    'used_gb': current_metrics.disk_used_gb,
                    'free_gb': current_metrics.disk_free_gb
                },
                'network': {
                    'bytes_sent': current_metrics.network_bytes_sent,
                    'bytes_recv': current_metrics.network_bytes_recv,
                    'active_connections': current_metrics.active_connections
                },
                'processes': {
                    'thread_count': current_metrics.thread_count,
                    'process_count': current_metrics.process_count,
                    'file_descriptors': current_metrics.file_descriptors
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting resource usage: {e}")
            return {}
    
    async def get_metric_statistics(self, metric_name: str, scope: MetricScope) -> Dict[str, Any]:
        """Get statistical analysis for a specific metric"""
        try:
            key = f"{scope.value}.{metric_name}"
            stats = self.aggregator.get_statistics(key)
            
            # Get historical data from Redis
            redis_key = f"{self.redis_keys['metrics']}:{scope.value}:{metric_name}"
            historical_data = await self.redis_client.zrange(
                redis_key, 0, -1, withscores=True
            )
            
            historical_points = []
            for data, timestamp in historical_data:
                try:
                    point = json.loads(data)
                    historical_points.append({
                        'value': point['value'],
                        'timestamp': point['timestamp']
                    })
                except:
                    continue
            
            return {
                'metric_name': metric_name,
                'scope': scope.value,
                'statistics': stats,
                'historical_data': historical_points[-50:],  # Last 50 points
                'data_points_count': len(historical_points)
            }
        except Exception as e:
            self.logger.error(f"Error getting metric statistics: {e}")
            return {}
    
    async def get_agent_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive agent metrics summary"""
        try:
            agent_data = {}
            
            # Get latest agent stats from Redis
            agent_stats = await self.redis_client.hgetall(self.redis_keys['agent_stats'])
            
            for key, value in agent_stats.items():
                try:
                    parts = key.split('_')
                    if len(parts) >= 2:
                        agent_id = '_'.join(parts[:-1])
                        timestamp = parts[-1]
                        
                        data = json.loads(value)
                        
                        if agent_id not in agent_data:
                            agent_data[agent_id] = {
                                'latest_stats': data,
                                'performance_history': []
                            }
                        
                        agent_data[agent_id]['performance_history'].append({
                            'timestamp': datetime.fromtimestamp(int(timestamp)).isoformat(),
                            'stats': data
                        })
                except:
                    continue
            
            # Sort performance history by timestamp
            for agent_id in agent_data:
                agent_data[agent_id]['performance_history'].sort(
                    key=lambda x: x['timestamp'], reverse=True
                )
                agent_data[agent_id]['performance_history'] = agent_data[agent_id]['performance_history'][:10]
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'total_agents': len(agent_data),
                'agents': agent_data
            }
        except Exception as e:
            self.logger.error(f"Error getting agent metrics summary: {e}")
            return {}
    
    async def get_learning_insights(self) -> Dict[str, Any]:
        """Get learning engine performance insights"""
        try:
            learning_stats = await self.redis_client.hgetall(self.redis_keys['learning_stats'])
            
            insights = {
                'learning_performance': {},
                'knowledge_growth': {},
                'model_accuracy_trends': {},
                'feedback_analysis': {}
            }
            
            # Process learning statistics
            for key, value in learning_stats.items():
                try:
                    data = json.loads(value)
                    # Process learning insights here
                    # This would integrate with your actual learning engine
                except:
                    continue
            
            return insights
        except Exception as e:
            self.logger.error(f"Error getting learning insights: {e}")
            return {}
    
    async def record_agent_performance(self, agent_id: str, performance_data: Dict[str, Any]):
        """Record performance data for a specific agent"""
        try:
            timestamp = datetime.utcnow()
            
            # Create performance metrics
            metrics = []
            for key, value in performance_data.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        MetricPoint(
                            name=f"agent_{key}",
                            value=value,
                            timestamp=timestamp,
                            metric_type=MetricType.GAUGE,
                            scope=MetricScope.AGENT,
                            tags={"agent_id": agent_id}
                        )
                    )
            
            await self._add_metrics_to_buffer(metrics)
            
            # Store detailed performance data
            await self.redis_client.hset(
                self.redis_keys['agent_stats'],
                f"{agent_id}_{int(timestamp.timestamp())}",
                json.dumps(performance_data, default=str)
            )
            
        except Exception as e:
            self.logger.error(f"Error recording agent performance for {agent_id}: {e}")
    
    async def record_learning_metrics(self, learning_data: Dict[str, Any]):
        """Record learning engine metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # Create learning metrics
            metrics = []
            for key, value in learning_data.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        MetricPoint(
                            name=f"learning_{key}",
                            value=value,
                            timestamp=timestamp,
                            metric_type=MetricType.GAUGE,
                            scope=MetricScope.LEARNING,
                            tags={"component": "learning_engine"}
                        )
                    )
            
            await self._add_metrics_to_buffer(metrics)
            
            # Store detailed learning data
            await self.redis_client.hset(
                self.redis_keys['learning_stats'],
                f"snapshot_{int(timestamp.timestamp())}",
                json.dumps(learning_data, default=str)
            )
            
        except Exception as e:
            self.logger.error(f"Error recording learning metrics: {e}")
    
    async def record_orchestration_metrics(self, orchestration_data: Dict[str, Any]):
        """Record agent orchestration metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # Create orchestration metrics
            metrics = []
            for key, value in orchestration_data.items():
                if isinstance(value, (int, float)):
                    metrics.append(
                        MetricPoint(
                            name=f"orchestration_{key}",
                            value=value,
                            timestamp=timestamp,
                            metric_type=MetricType.GAUGE,
                            scope=MetricScope.ORCHESTRATION,
                            tags={"component": "orchestrator"}
                        )
                    )
            
            await self._add_metrics_to_buffer(metrics)
            
            # Store detailed orchestration data
            await self.redis_client.hset(
                self.redis_keys['orchestration_stats'],
                f"snapshot_{int(timestamp.timestamp())}",
                json.dumps(orchestration_data, default=str)
            )
            
        except Exception as e:
            self.logger.error(f"Error recording orchestration metrics: {e}")
    
    async def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """Get performance alerts based on thresholds"""
        try:
            alerts = []
            current_time = datetime.utcnow()
            
            # Get current system metrics
            system_metrics = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._get_system_resource_metrics
            )
            
            # Check CPU usage
            if system_metrics.cpu_percent > 80:
                alerts.append({
                    'type': 'cpu_high',
                    'severity': 'warning' if system_metrics.cpu_percent < 90 else 'critical',
                    'message': f"High CPU usage: {system_metrics.cpu_percent:.1f}%",
                    'value': system_metrics.cpu_percent,
                    'threshold': 80,
                    'timestamp': current_time.isoformat()
                })
            
            # Check memory usage
            if system_metrics.memory_percent > 85:
                alerts.append({
                    'type': 'memory_high',
                    'severity': 'warning' if system_metrics.memory_percent < 95 else 'critical',
                    'message': f"High memory usage: {system_metrics.memory_percent:.1f}%",
                    'value': system_metrics.memory_percent,
                    'threshold': 85,
                    'timestamp': current_time.isoformat()
                })
            
            # Check disk usage
            if system_metrics.disk_usage_percent > 90:
                alerts.append({
                    'type': 'disk_high',
                    'severity': 'warning' if system_metrics.disk_usage_percent < 95 else 'critical',
                    'message': f"High disk usage: {system_metrics.disk_usage_percent:.1f}%",
                    'value': system_metrics.disk_usage_percent,
                    'threshold': 90,
                    'timestamp': current_time.isoformat()
                })
            
            # Check error rates
            if self.error_count > 0 and self.collection_count > 0:
                error_rate = (self.error_count / self.collection_count) * 100
                if error_rate > 5:
                    alerts.append({
                        'type': 'error_rate_high',
                        'severity': 'warning' if error_rate < 10 else 'critical',
                        'message': f"High error rate in metrics collection: {error_rate:.1f}%",
                        'value': error_rate,
                        'threshold': 5,
                        'timestamp': current_time.isoformat()
                    })
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting performance alerts: {e}")
            return []
    
    async def export_metrics(self, start_time: datetime, end_time: datetime, 
                           scopes: List[MetricScope] = None) -> Dict[str, Any]:
        """Export metrics for a specific time range"""
        try:
            if scopes is None:
                scopes = list(MetricScope)
            
            exported_data = {
                'export_info': {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'scopes': [scope.value for scope in scopes],
                    'instance_id': self.instance_id,
                    'hostname': self.hostname
                },
                'metrics': {}
            }
            
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            for scope in scopes:
                scope_data = {}
                
                # Get all metric keys for this scope
                pattern = f"{self.redis_keys['metrics']}:{scope.value}:*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    metric_name = key.split(':')[-1]
                    
                    # Get metric data in time range
                    data = await self.redis_client.zrangebyscore(
                        key, start_timestamp, end_timestamp, withscores=True
                    )
                    
                    metric_points = []
                    for point_data, timestamp in data:
                        try:
                            point = json.loads(point_data)
                            metric_points.append(point)
                        except:
                            continue
                    
                    if metric_points:
                        scope_data[metric_name] = metric_points
                
                if scope_data:
                    exported_data['metrics'][scope.value] = scope_data
            
            return exported_data
            
        except Exception as e:
            self.logger.error(f"Error exporting metrics: {e}")
            return {}
    
    # Private helper methods
    
    async def _get_latest_system_metrics(self) -> Dict[str, Any]:
        """Get latest system metrics summary"""
        try:
            latest_key = None
            latest_timestamp = 0
            
            # Find latest system stats
            system_stats = await self.redis_client.hgetall(self.redis_keys['system_stats'])
            for key in system_stats.keys():
                if key.startswith('snapshot_'):
                    timestamp = int(key.split('_')[1])
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_key = key
            
            if latest_key:
                data = json.loads(system_stats[latest_key])
                return data
            
            return {}
        except Exception as e:
            self.logger.error(f"Error getting latest system metrics: {e}")
            return {}
    
    async def _get_agent_performance_summary(self) -> Dict[str, Any]:
        """Get agent performance summary"""
        try:
            # Get agent statistics
            agent_stats = self.aggregator.get_statistics("agent.agent_response_time_ms")
            return {
                'response_time_stats': agent_stats,
                'total_agents_monitored': len(set(
                    point.tags.get('agent_id') 
                    for point in self.aggregator.data_windows.get("agent.agent_status", [])
                ))
            }
        except Exception as e:
            self.logger.error(f"Error getting agent performance summary: {e}")
            return {}
    
    async def _get_learning_performance_summary(self) -> Dict[str, Any]:
        """Get learning engine performance summary"""
        try:
            learning_stats = {}
            for key in self.aggregator.data_windows:
                if key.startswith('learning.'):
                    metric_name = key.split('.', 1)[1]
                    learning_stats[metric_name] = self.aggregator.get_statistics(key)
            
            return learning_stats
        except Exception as e:
            self.logger.error(f"Error getting learning performance summary: {e}")
            return {}
    
    async def _get_orchestration_summary(self) -> Dict[str, Any]:
        """Get orchestration performance summary"""
        try:
            orchestration_stats = {}
            for key in self.aggregator.data_windows:
                if key.startswith('orchestration.'):
                    metric_name = key.split('.', 1)[1]
                    orchestration_stats[metric_name] = self.aggregator.get_statistics(key)
            
            return orchestration_stats
        except Exception as e:
            self.logger.error(f"Error getting orchestration summary: {e}")
            return {}
    
    async def _calculate_resource_efficiency(self) -> Dict[str, float]:
        """Calculate resource utilization efficiency scores"""
        try:
            # Get recent system metrics
            system_stats = self.aggregator.get_statistics("system.cpu_usage_percent")
            memory_stats = self.aggregator.get_statistics("system.memory_usage_percent")
            
            # Calculate efficiency scores (0-100, higher is better)
            cpu_efficiency = max(0, 100 - (system_stats.get('mean', 0) - 50) * 2) if system_stats else 50
            memory_efficiency = max(0, 100 - (memory_stats.get('mean', 0) - 50) * 2) if memory_stats else 50
            
            overall_efficiency = (cpu_efficiency + memory_efficiency) / 2
            
            return {
                'cpu_efficiency': round(cpu_efficiency, 2),
                'memory_efficiency': round(memory_efficiency, 2),
                'overall_efficiency': round(overall_efficiency, 2)
            }
        except Exception as e:
            self.logger.error(f"Error calculating resource efficiency: {e}")
            return {'cpu_efficiency': 0.0, 'memory_efficiency': 0.0, 'overall_efficiency': 0.0}
    
    async def _get_metrics_by_scope(self, scope: MetricScope) -> Dict[str, Any]:
        """Get all metrics for a specific scope"""
        try:
            scope_metrics = {}
            
            for key in self.aggregator.data_windows:
                if key.startswith(f"{scope.value}."):
                    metric_name = key.split('.', 1)[1]
                    stats = self.aggregator.get_statistics(key)
                    if stats:
                        scope_metrics[metric_name] = stats
            
            return scope_metrics
        except Exception as e:
            self.logger.error(f"Error getting metrics by scope {scope.value}: {e}")
            return {}
    
    async def _get_aggregated_statistics(self) -> Dict[str, Any]:
        """Get aggregated statistics across all metrics"""
        try:
            stats_summary = {
                'total_metrics_tracked': len(self.aggregator.data_windows),
                'metrics_by_scope': {},
                'collection_performance': {
                    'total_collections': self.collection_count,
                    'error_count': self.error_count,
                    'success_rate': (1 - (self.error_count / max(1, self.collection_count))) * 100
                }
            }
            
            # Group metrics by scope
            for key in self.aggregator.data_windows:
                scope = key.split('.')[0]
                if scope not in stats_summary['metrics_by_scope']:
                    stats_summary['metrics_by_scope'][scope] = 0
                stats_summary['metrics_by_scope'][scope] += 1
            
            return stats_summary
        except Exception as e:
            self.logger.error(f"Error getting aggregated statistics: {e}")
            return {}
    
    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)