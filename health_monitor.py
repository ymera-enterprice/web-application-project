"""
YMERA Enterprise Health Monitor
Production-grade system health monitoring with intelligent anomaly detection
"""

import asyncio
import json
import time
import psutil
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import traceback
from collections import deque, defaultdict
import statistics
import aiohttp
import sqlalchemy
from sqlalchemy import text
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
import weakref
import gc

# Custom imports (based on your system structure)
from ..database.manager import DatabaseManager
from ..cache.redis_cache import RedisCacheManager
from ..logging.structured_logger import StructuredLogger
from ..exceptions import YMERAException


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """System component types"""
    DATABASE = "database"
    REDIS = "redis"
    AGENT = "agent"
    SERVICE = "service"
    SYSTEM = "system"
    NETWORK = "network"
    AI_SERVICE = "ai_service"
    LEARNING_ENGINE = "learning_engine"


@dataclass
class HealthMetric:
    """Individual health metric data"""
    name: str
    value: float
    unit: str
    status: HealthStatus
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    timestamp: datetime = None
    message: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ComponentHealth:
    """Health status for a system component"""
    component_id: str
    component_type: ComponentType
    status: HealthStatus
    metrics: List[HealthMetric]
    last_check: datetime
    uptime: float
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "component_id": self.component_id,
            "component_type": self.component_type.value,
            "status": self.status.value,
            "metrics": [asdict(metric) for metric in self.metrics],
            "last_check": self.last_check.isoformat(),
            "uptime": self.uptime,
            "message": self.message,
            "details": self.details
        }


@dataclass
class SystemHealth:
    """Overall system health status"""
    overall_status: HealthStatus
    components: Dict[str, ComponentHealth]
    timestamp: datetime
    uptime: float
    total_components: int
    healthy_components: int
    warning_components: int
    critical_components: int
    system_metrics: List[HealthMetric]
    alerts: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "overall_status": self.overall_status.value,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "timestamp": self.timestamp.isoformat(),
            "uptime": self.uptime,
            "total_components": self.total_components,
            "healthy_components": self.healthy_components,
            "warning_components": self.warning_components,
            "critical_components": self.critical_components,
            "system_metrics": [asdict(metric) for metric in self.system_metrics],
            "alerts": self.alerts,
            "overall_healthy": self.overall_status == HealthStatus.HEALTHY
        }


class HealthChecker:
    """Base class for component health checkers"""
    
    def __init__(self, component_id: str, component_type: ComponentType):
        self.component_id = component_id
        self.component_type = component_type
        self.last_check = None
        self.check_count = 0
        self.failure_count = 0
        self.success_count = 0
        
    async def check_health(self) -> ComponentHealth:
        """Perform health check - to be implemented by subclasses"""
        raise NotImplementedError
        
    def _create_metric(self, name: str, value: float, unit: str, 
                      warning_threshold: float = None, 
                      critical_threshold: float = None,
                      message: str = None) -> HealthMetric:
        """Helper to create health metrics with status evaluation"""
        status = HealthStatus.HEALTHY
        
        if critical_threshold is not None and value >= critical_threshold:
            status = HealthStatus.CRITICAL
        elif warning_threshold is not None and value >= warning_threshold:
            status = HealthStatus.WARNING
            
        return HealthMetric(
            name=name,
            value=value,
            unit=unit,
            status=status,
            threshold_warning=warning_threshold,
            threshold_critical=critical_threshold,
            message=message
        )


class DatabaseHealthChecker(HealthChecker):
    """Database health checker"""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("database", ComponentType.DATABASE)
        self.db_manager = db_manager
        self.connection_pool_size = 0
        
    async def check_health(self) -> ComponentHealth:
        """Check database health"""
        metrics = []
        start_time = time.time()
        
        try:
            # Connection test
            async with self.db_manager.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                connection_test = result.scalar()
                
            connection_time = (time.time() - start_time) * 1000
            metrics.append(self._create_metric(
                "connection_time", connection_time, "ms", 
                warning_threshold=100, critical_threshold=1000
            ))
            
            # Pool status
            engine = self.db_manager.engine
            pool = engine.pool
            
            metrics.append(self._create_metric(
                "pool_size", pool.size(), "connections"
            ))
            metrics.append(self._create_metric(
                "checked_in", pool.checkedin(), "connections"
            ))
            metrics.append(self._create_metric(
                "checked_out", pool.checkedout(), "connections",
                warning_threshold=pool.size() * 0.8,
                critical_threshold=pool.size() * 0.95
            ))
            metrics.append(self._create_metric(
                "overflow", pool.overflow(), "connections",
                warning_threshold=5, critical_threshold=10
            ))
            
            # Query performance test
            query_start = time.time()
            async with self.db_manager.get_session() as session:
                await session.execute(text("""
                    SELECT COUNT(*) as count, 
                           AVG(EXTRACT(EPOCH FROM NOW() - created_at)) as avg_age 
                    FROM projects 
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """))
            query_time = (time.time() - query_start) * 1000
            
            metrics.append(self._create_metric(
                "query_performance", query_time, "ms",
                warning_threshold=500, critical_threshold=2000
            ))
            
            self.success_count += 1
            status = max([m.status for m in metrics], key=lambda s: list(HealthStatus).index(s))
            
        except Exception as e:
            self.failure_count += 1
            status = HealthStatus.CRITICAL
            metrics.append(self._create_metric(
                "connection_error", 1, "boolean",
                message=str(e)
            ))
            
        self.check_count += 1
        self.last_check = datetime.utcnow()
        
        return ComponentHealth(
            component_id=self.component_id,
            component_type=self.component_type,
            status=status,
            metrics=metrics,
            last_check=self.last_check,
            uptime=self.success_count / max(self.check_count, 1) * 100,
            message=f"Database health check completed. Success rate: {self.success_count}/{self.check_count}"
        )


class RedisHealthChecker(HealthChecker):
    """Redis health checker"""
    
    def __init__(self, redis_client):
        super().__init__("redis", ComponentType.REDIS)
        self.redis_client = redis_client
        
    async def check_health(self) -> ComponentHealth:
        """Check Redis health"""
        metrics = []
        start_time = time.time()
        
        try:
            # Connection and ping test
            await self.redis_client.ping()
            ping_time = (time.time() - start_time) * 1000
            
            metrics.append(self._create_metric(
                "ping_time", ping_time, "ms",
                warning_threshold=50, critical_threshold=200
            ))
            
            # Redis info
            info = await self.redis_client.info()
            
            # Memory usage
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            
            if max_memory > 0:
                memory_usage = (used_memory / max_memory) * 100
                metrics.append(self._create_metric(
                    "memory_usage", memory_usage, "%",
                    warning_threshold=80, critical_threshold=95
                ))
            
            metrics.append(self._create_metric(
                "used_memory_mb", used_memory / (1024 * 1024), "MB"
            ))
            
            # Connection stats
            metrics.append(self._create_metric(
                "connected_clients", info.get('connected_clients', 0), "clients",
                warning_threshold=100, critical_threshold=200
            ))
            
            # Operations per second
            metrics.append(self._create_metric(
                "ops_per_sec", info.get('instantaneous_ops_per_sec', 0), "ops/sec"
            ))
            
            # Key statistics
            db_info = info.get('db0', {})
            if db_info:
                keys_count = db_info.get('keys', 0)
                metrics.append(self._create_metric(
                    "total_keys", keys_count, "keys"
                ))
            
            # Persistence stats
            if info.get('rdb_last_save_time', 0) > 0:
                last_save = info.get('rdb_last_save_time', 0)
                time_since_save = time.time() - last_save
                metrics.append(self._create_metric(
                    "time_since_last_save", time_since_save / 3600, "hours",
                    warning_threshold=24, critical_threshold=72
                ))
            
            self.success_count += 1
            status = max([m.status for m in metrics], key=lambda s: list(HealthStatus).index(s))
            
        except Exception as e:
            self.failure_count += 1
            status = HealthStatus.CRITICAL
            metrics.append(self._create_metric(
                "connection_error", 1, "boolean",
                message=str(e)
            ))
            
        self.check_count += 1
        self.last_check = datetime.utcnow()
        
        return ComponentHealth(
            component_id=self.component_id,
            component_type=self.component_type,
            status=status,
            metrics=metrics,
            last_check=self.last_check,
            uptime=self.success_count / max(self.check_count, 1) * 100,
            message=f"Redis health check completed. Success rate: {self.success_count}/{self.check_count}"
        )


class AgentHealthChecker(HealthChecker):
    """Agent health checker"""
    
    def __init__(self, agent_id: str, agent_instance):
        super().__init__(agent_id, ComponentType.AGENT)
        self.agent = agent_instance
        self.response_times = deque(maxlen=100)
        
    async def check_health(self) -> ComponentHealth:
        """Check agent health"""
        metrics = []
        start_time = time.time()
        
        try:
            # Agent status check
            if hasattr(self.agent, 'is_active') and callable(self.agent.is_active):
                is_active = await self.agent.is_active()
            else:
                is_active = hasattr(self.agent, '_active') and getattr(self.agent, '_active', True)
                
            metrics.append(self._create_metric(
                "is_active", 1 if is_active else 0, "boolean"
            ))
            
            # Response time test
            if hasattr(self.agent, 'health_check') and callable(self.agent.health_check):
                health_result = await self.agent.health_check()
                response_time = (time.time() - start_time) * 1000
                self.response_times.append(response_time)
                
                metrics.append(self._create_metric(
                    "response_time", response_time, "ms",
                    warning_threshold=500, critical_threshold=2000
                ))
                
                # Average response time
                if len(self.response_times) > 1:
                    avg_response = statistics.mean(self.response_times)
                    metrics.append(self._create_metric(
                        "avg_response_time", avg_response, "ms",
                        warning_threshold=300, critical_threshold=1000
                    ))
            
            # Task queue size (if applicable)
            if hasattr(self.agent, 'task_queue_size'):
                queue_size = self.agent.task_queue_size()
                metrics.append(self._create_metric(
                    "task_queue_size", queue_size, "tasks",
                    warning_threshold=50, critical_threshold=100
                ))
            
            # Learning metrics (if applicable)
            if hasattr(self.agent, 'get_learning_stats'):
                learning_stats = await self.agent.get_learning_stats()
                if learning_stats:
                    metrics.append(self._create_metric(
                        "learning_accuracy", learning_stats.get('accuracy', 0), "%"
                    ))
                    metrics.append(self._create_metric(
                        "knowledge_items", learning_stats.get('knowledge_items', 0), "items"
                    ))
            
            # Memory usage (if trackable)
            if hasattr(self.agent, 'get_memory_usage'):
                memory_mb = self.agent.get_memory_usage()
                metrics.append(self._create_metric(
                    "memory_usage", memory_mb, "MB",
                    warning_threshold=500, critical_threshold=1000
                ))
            
            self.success_count += 1
            status = HealthStatus.CRITICAL if not is_active else max(
                [m.status for m in metrics], 
                key=lambda s: list(HealthStatus).index(s)
            )
            
        except Exception as e:
            self.failure_count += 1
            status = HealthStatus.CRITICAL
            metrics.append(self._create_metric(
                "health_check_error", 1, "boolean",
                message=str(e)
            ))
            
        self.check_count += 1
        self.last_check = datetime.utcnow()
        
        return ComponentHealth(
            component_id=self.component_id,
            component_type=self.component_type,
            status=status,
            metrics=metrics,
            last_check=self.last_check,
            uptime=self.success_count / max(self.check_count, 1) * 100,
            message=f"Agent {self.component_id} health check completed"
        )


class SystemResourceChecker(HealthChecker):
    """System resource health checker"""
    
    def __init__(self):
        super().__init__("system_resources", ComponentType.SYSTEM)
        
    async def check_health(self) -> ComponentHealth:
        """Check system resources"""
        metrics = []
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(self._create_metric(
                "cpu_usage", cpu_percent, "%",
                warning_threshold=80, critical_threshold=95
            ))
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics.append(self._create_metric(
                "memory_usage", memory.percent, "%",
                warning_threshold=80, critical_threshold=95
            ))
            metrics.append(self._create_metric(
                "memory_available_gb", memory.available / (1024**3), "GB"
            ))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            metrics.append(self._create_metric(
                "disk_usage", disk_percent, "%",
                warning_threshold=80, critical_threshold=95
            ))
            metrics.append(self._create_metric(
                "disk_free_gb", disk.free / (1024**3), "GB"
            ))
            
            # Network statistics
            net_io = psutil.net_io_counters()
            metrics.append(self._create_metric(
                "network_bytes_sent", net_io.bytes_sent / (1024**2), "MB"
            ))
            metrics.append(self._create_metric(
                "network_bytes_recv", net_io.bytes_recv / (1024**2), "MB"
            ))
            
            # Load average (Unix systems)
            try:
                load_avg = psutil.getloadavg()
                cpu_count = psutil.cpu_count()
                load_percent = (load_avg[0] / cpu_count) * 100
                metrics.append(self._create_metric(
                    "load_average", load_percent, "%",
                    warning_threshold=70, critical_threshold=90
                ))
            except (AttributeError, OSError):
                # Not available on all systems
                pass
            
            # Process count
            process_count = len(psutil.pids())
            metrics.append(self._create_metric(
                "process_count", process_count, "processes"
            ))
            
            # File descriptor usage (Unix systems)
            try:
                import resource
                soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                current_fds = len(psutil.Process().open_files()) + len(psutil.Process().connections())
                fd_percent = (current_fds / soft_limit) * 100 if soft_limit > 0 else 0
                metrics.append(self._create_metric(
                    "file_descriptor_usage", fd_percent, "%",
                    warning_threshold=70, critical_threshold=90
                ))
            except (ImportError, OSError, psutil.AccessDenied):
                pass
            
            self.success_count += 1
            status = max([m.status for m in metrics], key=lambda s: list(HealthStatus).index(s))
            
        except Exception as e:
            self.failure_count += 1
            status = HealthStatus.CRITICAL
            metrics.append(self._create_metric(
                "system_check_error", 1, "boolean",
                message=str(e)
            ))
            
        self.check_count += 1
        self.last_check = datetime.utcnow()
        
        return ComponentHealth(
            component_id=self.component_id,
            component_type=self.component_type,
            status=status,
            metrics=metrics,
            last_check=self.last_check,
            uptime=self.success_count / max(self.check_count, 1) * 100,
            message="System resource health check completed"
        )


class AIServiceHealthChecker(HealthChecker):
    """AI service health checker"""
    
    def __init__(self, service_name: str, ai_manager):
        super().__init__(f"ai_service_{service_name}", ComponentType.AI_SERVICE)
        self.service_name = service_name
        self.ai_manager = ai_manager
        self.response_times = deque(maxlen=50)
        
    async def check_health(self) -> ComponentHealth:
        """Check AI service health"""
        metrics = []
        start_time = time.time()
        
        try:
            # Simple test query
            test_prompt = "Health check: respond with 'OK'"
            
            if hasattr(self.ai_manager, 'generate_response'):
                response = await self.ai_manager.generate_response(
                    prompt=test_prompt,
                    provider=self.service_name,
                    max_tokens=10
                )
                
                response_time = (time.time() - start_time) * 1000
                self.response_times.append(response_time)
                
                metrics.append(self._create_metric(
                    "response_time", response_time, "ms",
                    warning_threshold=5000, critical_threshold=15000
                ))
                
                # Response quality check
                is_valid_response = response and len(response.strip()) > 0
                metrics.append(self._create_metric(
                    "response_valid", 1 if is_valid_response else 0, "boolean"
                ))
                
                # Average response time
                if len(self.response_times) > 1:
                    avg_response = statistics.mean(self.response_times)
                    metrics.append(self._create_metric(
                        "avg_response_time", avg_response, "ms",
                        warning_threshold=3000, critical_threshold=10000
                    ))
                
                # Token usage (if available)
                if hasattr(self.ai_manager, 'get_usage_stats'):
                    usage_stats = await self.ai_manager.get_usage_stats(self.service_name)
                    if usage_stats:
                        metrics.append(self._create_metric(
                            "tokens_used_today", usage_stats.get('tokens_today', 0), "tokens"
                        ))
                        metrics.append(self._create_metric(
                            "requests_today", usage_stats.get('requests_today', 0), "requests"
                        ))
            
            self.success_count += 1
            status = max([m.status for m in metrics], key=lambda s: list(HealthStatus).index(s))
            
        except Exception as e:
            self.failure_count += 1
            status = HealthStatus.CRITICAL
            metrics.append(self._create_metric(
                "service_error", 1, "boolean",
                message=str(e)
            ))
            
        self.check_count += 1
        self.last_check = datetime.utcnow()
        
        return ComponentHealth(
            component_id=self.component_id,
            component_type=self.component_type,
            status=status,
            metrics=metrics,
            last_check=self.last_check,
            uptime=self.success_count / max(self.check_count, 1) * 100,
            message=f"AI service {self.service_name} health check completed"
        )


class HealthMonitor:
    """
    Enterprise-grade health monitoring system with:
    - Real-time component health checking
    - Anomaly detection and alerting
    - Historical health data tracking
    - Learning-based predictive monitoring
    - Auto-recovery mechanisms
    """
    
    def __init__(self, 
                 db_manager: DatabaseManager,
                 redis_client,
                 agents: Dict[str, Any],
                 ai_manager=None,
                 learning_engine=None,
                 check_interval: int = 30,
                 alert_thresholds: Dict[str, int] = None):
        
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.agents = agents
        self.ai_manager = ai_manager
        self.learning_engine = learning_engine
        self.check_interval = check_interval
        
        # Default alert thresholds
        self.alert_thresholds = alert_thresholds or {
            'consecutive_failures': 3,
            'failure_rate_threshold': 0.5,
            'response_time_spike': 2.0  # 2x normal
        }
        
        # Health checkers
        self.checkers: Dict[str, HealthChecker] = {}
        self.health_history = defaultdict(lambda: deque(maxlen=1000))
        self.alerts_history = deque(maxlen=500)
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_task = None
        self._last_system_health = None
        self.start_time = datetime.utcnow()
        
        # Threading for background tasks
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="health_monitor")
        self._lock = threading.RLock()
        
        # Logger
        self.logger = logging.getLogger(f"{__name__}.HealthMonitor")
        
        # Anomaly detection
        self.anomaly_detector = HealthAnomalyDetector()
        
        # Performance tracking
        self.performance_baseline = {}
        self.learning_enabled = learning_engine is not None
        
    async def initialize(self):
        """Initialize the health monitoring system"""
        self.logger.info("Initializing YMERA Health Monitor...")
        
        try:
            # Initialize core checkers
            await self._initialize_core_checkers()
            
            # Initialize agent checkers
            await self._initialize_agent_checkers()
            
            # Initialize AI service checkers
            if self.ai_manager:
                await self._initialize_ai_service_checkers()
            
            # Load historical baselines if learning is enabled
            if self.learning_enabled:
                await self._load_performance_baselines()
            
            # Initialize Redis structures for health data
            await self._initialize_redis_structures()
            
            self.logger.info(f"Health Monitor initialized with {len(self.checkers)} checkers")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Health Monitor: {str(e)}")
            raise
    
    async def _initialize_core_checkers(self):
        """Initialize core system checkers"""
        # Database checker
        if self.db_manager:
            self.checkers['database'] = DatabaseHealthChecker(self.db_manager)
        
        # Redis checker
        if self.redis_client:
            self.checkers['redis'] = RedisHealthChecker(self.redis_client)
        
        # System resources checker
        self.checkers['system_resources'] = SystemResourceChecker()
    
    async def _initialize_agent_checkers(self):
        """Initialize agent-specific health checkers"""
        for agent_id, agent in self.agents.items():
            self.checkers[f'agent_{agent_id}'] = AgentHealthChecker(agent_id, agent)
    
    async def _initialize_ai_service_checkers(self):
        """Initialize AI service health checkers"""
        if hasattr(self.ai_manager, 'providers'):
            for provider_name in self.ai_manager.providers.keys():
                checker_id = f'ai_{provider_name}'
                self.checkers[checker_id] = AIServiceHealthChecker(provider_name, self.ai_manager)
    
    async def _initialize_redis_structures(self):
        """Initialize Redis data structures for health monitoring"""
        try:
            # Health data keys
            await self.redis_client.hset("ymera:health:config", mapping={
                "check_interval": self.check_interval,
                "alert_thresholds": json.dumps(self.alert_thresholds),
                "start_time": self.start_time.isoformat()
            })
            
            # Initialize counters
            await self.redis_client.hset("ymera:health:counters", mapping={
                "total_checks": 0,
                "total_alerts": 0,
                "uptime_seconds": 0
            })
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Redis structures: {str(e)}")
    
    async def _load_performance_baselines(self):
        """Load historical performance baselines for anomaly detection"""
        if not self.learning_engine:
            return
            
        try:
            # Load from learning engine's knowledge base
            baselines = await self.learning_engine.knowledge_base.query(
                query_text="health monitoring performance baselines",
                top_k=1
            )
            
            if baselines and baselines.matches:
                baseline_data = json.loads(baselines.matches[0].metadata.get('baseline_data', '{}'))
                self.performance_baseline = baseline_data
                self.logger.info(f"Loaded {len(baseline_data)} performance baselines")
                
        except Exception as e:
            self.logger.warning(f"Failed to load performance baselines: {str(e)}")
    
    async def start_health_checks(self):
        """Start continuous health monitoring"""
        if self._monitoring_active:
            self.logger.warning("Health monitoring is already active")
            return
        
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Health monitoring started")
    
    async def stop_health_checks(self):
        """Stop continuous health monitoring"""
        self._monitoring_active = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.executor.shutdown(wait=True)
        self.logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info(f"Starting health monitoring loop (interval: {self.check_interval}s)")
        
        while self._monitoring_active:
            try:
                loop_start = time.time()
                
                # Perform health checks
                await self._perform_health_checks()
                
                # Update performance baselines
                if self.learning_enabled:
                    await self._update_performance_baselines()
                
                # Check for anomalies and generate alerts
                await self._process_anomalies_and_alerts()
                
                # Update Redis metrics
                await self._update_redis_metrics()
                
                # Calculate sleep time to maintain interval
                loop_duration = time.time() - loop_start
                sleep_time = max(0, self.check_interval - loop_duration)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    self.logger.warning(f"Health check loop took {loop_duration:.2f}s, longer than interval {self.check_interval}s")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {str(e)}")
                await asyncio.sleep(min(self.check_interval, 10))  # Brief pause on error
    
    async def _perform_health_checks(self):
        """Perform health checks on all components"""
        check_tasks = []
        
        # Create tasks for all health checks
        for checker_id, checker in self.checkers.items():
            task = asyncio.create_task(self._safe_health_check(checker_id, checker))
            check_tasks.append(task)
        
        # Wait for all checks to complete
        if check_tasks:
            results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            # Process results and update health history
            for i, result in enumerate(results):
                checker_id = list(self.checkers.keys())[i]
                
                if isinstance(result, Exception):
                    self.logger.error(f"Health check failed for {checker_id}: {str(result)}")
                    # Create error health status
                    error_health = ComponentHealth(
                        component_id=checker_id,
                        component_type=ComponentType.UNKNOWN,
                        status=HealthStatus.CRITICAL,
                        metrics=[HealthMetric(
                            name="check_error",
                            value=1,
                            unit="boolean",
                            status=HealthStatus.CRITICAL,
                            message=str(result)
                        )],
                        last_check=datetime.utcnow(),
                        uptime=0,
                        message=f"Health check failed: {str(result)}"
                    )
                    self.health_history[checker_id].append(error_health)
                else:
                    self.health_history[checker_id].append(result)
    
    async def _safe_health_check(self, checker_id: str, checker: HealthChecker) -> ComponentHealth:
        """Safely perform a health check with timeout and error handling"""
        try:
            # Set timeout for health checks
            return await asyncio.wait_for(checker.check_health(), timeout=30.0)
        except asyncio.TimeoutError:
            self.logger.warning(f"Health check timeout for {checker_id}")
            return ComponentHealth(
                component_id=checker_id,
                component_type=checker.component_type,
                status=HealthStatus.CRITICAL,
                metrics=[HealthMetric(
                    name="check_timeout",
                    value=1,
                    unit="boolean",
                    status=HealthStatus.CRITICAL,
                    message="Health check timed out"
                )],
                last_check=datetime.utcnow(),
                uptime=0,
                message="Health check timed out after 30 seconds"
            )
        except Exception as e:
            self.logger.error(f"Health check exception for {checker_id}: {str(e)}")
            raise
    
    async def _update_performance_baselines(self):
        """Update performance baselines using learning engine"""
        if not self.learning_enabled:
            return
        
        try:
            # Collect current performance metrics
            current_metrics = {}
            
            for checker_id, health_history in self.health_history.items():
                if len(health_history) < 10:  # Need minimum data points
                    continue
                
                recent_health = list(health_history)[-10:]  # Last 10 checks
                
                # Calculate average response times and other key metrics
                response_times = []
                for health in recent_health:
                    for metric in health.metrics:
                        if 'response_time' in metric.name or 'ping_time' in metric.name:
                            response_times.append(metric.value)
                
                if response_times:
                    current_metrics[f"{checker_id}_avg_response"] = statistics.mean(response_times)
                    current_metrics[f"{checker_id}_response_std"] = statistics.stdev(response_times) if len(response_times) > 1 else 0
            
            # Update baselines using learning engine
            if current_metrics:
                await self.learning_engine.update_knowledge(
                    category="health_baselines",
                    data=current_metrics,
                    source="health_monitor"
                )
                
                # Update local baselines
                self.performance_baseline.update(current_metrics)
                
        except Exception as e:
            self.logger.warning(f"Failed to update performance baselines: {str(e)}")
    
    async def _process_anomalies_and_alerts(self):
        """Process anomalies and generate alerts"""
        try:
            current_time = datetime.utcnow()
            new_alerts = []
            
            for checker_id, health_history in self.health_history.items():
                if not health_history:
                    continue
                
                recent_health = list(health_history)[-5:]  # Last 5 checks
                
                # Check for consecutive failures
                consecutive_failures = 0
                for health in reversed(recent_health):
                    if health.status in [HealthStatus.CRITICAL, HealthStatus.WARNING]:
                        consecutive_failures += 1
                    else:
                        break
                
                if consecutive_failures >= self.alert_thresholds['consecutive_failures']:
                    alert = {
                        "id": f"alert_{int(time.time())}_{checker_id}",
                        "component_id": checker_id,
                        "type": "consecutive_failures",
                        "severity": "critical" if consecutive_failures >= 5 else "warning",
                        "message": f"Component {checker_id} has {consecutive_failures} consecutive failures",
                        "timestamp": current_time.isoformat(),
                        "details": {
                            "consecutive_failures": consecutive_failures,
                            "recent_status": [h.status.value for h in recent_health]
                        }
                    }
                    new_alerts.append(alert)
                
                # Check for performance anomalies
                if len(health_history) >= 20:
                    anomalies = await self.anomaly_detector.detect_anomalies(
                        checker_id, list(health_history)[-20:], self.performance_baseline
                    )
                    
                    for anomaly in anomalies:
                        alert = {
                            "id": f"alert_{int(time.time())}_{checker_id}_{anomaly['type']}",
                            "component_id": checker_id,
                            "type": "performance_anomaly",
                            "severity": anomaly['severity'],
                            "message": f"Performance anomaly detected in {checker_id}: {anomaly['message']}",
                            "timestamp": current_time.isoformat(),
                            "details": anomaly
                        }
                        new_alerts.append(alert)
            
            # Store new alerts
            for alert in new_alerts:
                self.alerts_history.append(alert)
                await self._store_alert(alert)
                
                # Send critical alerts to learning engine
                if alert['severity'] == 'critical' and self.learning_enabled:
                    await self.learning_engine.process_feedback(
                        feedback_type="alert",
                        data=alert,
                        source="health_monitor"
                    )
            
            if new_alerts:
                self.logger.info(f"Generated {len(new_alerts)} new health alerts")
                
        except Exception as e:
            self.logger.error(f"Failed to process anomalies and alerts: {str(e)}")
    
    async def _store_alert(self, alert: Dict[str, Any]):
        """Store alert in Redis and database"""
        try:
            # Store in Redis for quick access
            await self.redis_client.lpush("ymera:health:alerts", json.dumps(alert))
            await self.redis_client.ltrim("ymera:health:alerts", 0, 499)  # Keep last 500
            
            # Store in database for persistence
            if self.db_manager:
                async with self.db_manager.get_session() as session:
                    await session.execute(
                        text("""
                        INSERT INTO health_alerts 
                        (alert_id, component_id, alert_type, severity, message, timestamp, details)
                        VALUES (:alert_id, :component_id, :alert_type, :severity, :message, :timestamp, :details)
                        ON CONFLICT (alert_id) DO NOTHING
                        """),
                        {
                            "alert_id": alert["id"],
                            "component_id": alert["component_id"],
                            "alert_type": alert["type"],
                            "severity": alert["severity"],
                            "message": alert["message"],
                            "timestamp": alert["timestamp"],
                            "details": json.dumps(alert["details"])
                        }
                    )
                    await session.commit()
                    
        except Exception as e:
            self.logger.warning(f"Failed to store alert: {str(e)}")
    
    async def _update_redis_metrics(self):
        """Update health metrics in Redis"""
        try:
            current_time = datetime.utcnow()
            uptime_seconds = (current_time - self.start_time).total_seconds()
            
            # Update counters
            await self.redis_client.hincrby("ymera:health:counters", "total_checks", len(self.checkers))
            await self.redis_client.hset("ymera:health:counters", "uptime_seconds", int(uptime_seconds))
            
            # Store current health snapshot
            if self._last_system_health:
                health_snapshot = {
                    "timestamp": current_time.isoformat(),
                    "overall_status": self._last_system_health.overall_status.value,
                    "healthy_components": self._last_system_health.healthy_components,
                    "warning_components": self._last_system_health.warning_components,
                    "critical_components": self._last_system_health.critical_components
                }
                
                await self.redis_client.lpush("ymera:health:snapshots", json.dumps(health_snapshot))
                await self.redis_client.ltrim("ymera:health:snapshots", 0, 287)  # Keep ~24 hours (5min intervals)
                
        except Exception as e:
            self.logger.warning(f"Failed to update Redis metrics: {str(e)}")
    
    async def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        try:
            current_time = datetime.utcnow()
            components = {}
            system_metrics = []
            
            # Collect health status from all components
            healthy_count = 0
            warning_count = 0
            critical_count = 0
            
            for checker_id, health_history in self.health_history.items():
                if health_history:
                    latest_health = health_history[-1]
                    components[checker_id] = latest_health
                    
                    if latest_health.status == HealthStatus.HEALTHY:
                        healthy_count += 1
                    elif latest_health.status == HealthStatus.WARNING:
                        warning_count += 1
                    elif latest_health.status == HealthStatus.CRITICAL:
                        critical_count += 1
            
            # Determine overall status
            if critical_count > 0:
                overall_status = HealthStatus.CRITICAL
            elif warning_count > 0:
                overall_status = HealthStatus.WARNING
            else:
                overall_status = HealthStatus.HEALTHY
            
            # System-level metrics
            uptime_seconds = (current_time - self.start_time).total_seconds()
            system_metrics.append(HealthMetric(
                name="system_uptime",
                value=uptime_seconds,
                unit="seconds",
                status=HealthStatus.HEALTHY
            ))
            
            system_metrics.append(HealthMetric(
                name="total_components",
                value=len(components),
                unit="components",
                status=HealthStatus.HEALTHY
            ))
            
            system_metrics.append(HealthMetric(
                name="health_check_success_rate",
                value=(healthy_count / max(len(components), 1)) * 100,
                unit="%",
                status=HealthStatus.HEALTHY if healthy_count == len(components) else HealthStatus.WARNING
            ))
            
            # Recent alerts (last hour)
            recent_alerts = [
                alert for alert in list(self.alerts_history)
                if datetime.fromisoformat(alert['timestamp']) > current_time - timedelta(hours=1)
            ]
            
            # Create system health object
            system_health = SystemHealth(
                overall_status=overall_status,
                components=components,
                timestamp=current_time,
                uptime=uptime_seconds,
                total_components=len(components),
                healthy_components=healthy_count,
                warning_components=warning_count,
                critical_components=critical_count,
                system_metrics=system_metrics,
                alerts=recent_alerts
            )
            
            self._last_system_health = system_health
            return system_health.to_dict()
            
        except Exception as e:
            self.logger.error(f"Failed to get comprehensive health: {str(e)}")
            raise
    
    async def get_component_health(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific component"""
        if component_id not in self.health_history:
            return None
        
        health_history = list(self.health_history[component_id])
        if not health_history:
            return None
        
        latest_health = health_history[-1]
        
        # Add historical data
        result = latest_health.to_dict()
        result['history'] = [h.to_dict() for h in health_history[-10:]]  # Last 10 checks
        
        return result
    
    async def get_health_history(self, 
                               component_id: Optional[str] = None,
                               hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Get health history for components"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        result = {}
        
        components_to_check = [component_id] if component_id else list(self.health_history.keys())
        
        for comp_id in components_to_check:
            if comp_id in self.health_history:
                history = [
                    h.to_dict() for h in self.health_history[comp_id]
                    if h.last_check > cutoff_time
                ]
                result[comp_id] = history
        
        return result
    
    async def get_alerts(self, 
                        component_id: Optional[str] = None,
                        severity: Optional[str] = None,
                        hours: int = 24) -> List[Dict[str, Any]]:
        """Get alerts with optional filtering"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        alerts = []
        for alert in self.alerts_history:
            alert_time = datetime.fromisoformat(alert['timestamp'])
            
            # Apply filters
            if alert_time < cutoff_time:
                continue
            
            if component_id and alert['component_id'] != component_id:
                continue
            
            if severity and alert['severity'] != severity:
                continue
            
            alerts.append(alert)
        
        return alerts
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        try:
            # Find and update the alert
            for alert in self.alerts_history:
                if alert['id'] == alert_id:
                    alert['acknowledged'] = True
                    alert['acknowledged_by'] = acknowledged_by
                    alert['acknowledged_at'] = datetime.utcnow().isoformat()
                    
                    # Update in database
                    if self.db_manager:
                        async with self.db_manager.get_session() as session:
                            await session.execute(
                                text("""
                                UPDATE health_alerts 
                                SET acknowledged = true, acknowledged_by = :ack_by, acknowledged_at = :ack_at
                                WHERE alert_id = :alert_id
                                """),
                                {
                                    "alert_id": alert_id,
                                    "ack_by": acknowledged_by,
                                    "ack_at": alert['acknowledged_at']
                                }
                            )
                            await session.commit()
                    
                    self.logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert {alert_id}: {str(e)}")
            return False
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        try:
            current_time = datetime.utcnow()
            uptime = (current_time - self.start_time).total_seconds()
            
            # Basic metrics
            metrics = {
                "uptime_seconds": uptime,
                "uptime_hours": uptime / 3600,
                "total_components": len(self.checkers),
                "active_alerts": len([a for a in self.alerts_history if not a.get('acknowledged', False)]),
                "total_alerts_generated": len(self.alerts_history),
                "health_checks_performed": sum(checker.check_count for checker in self.checkers.values()),
                "average_check_interval": self.check_interval,
                "monitoring_active": self._monitoring_active
            }
            
            # Component statistics
            component_stats = {}
            for checker_id, checker in self.checkers.items():
                component_stats[checker_id] = {
                    "total_checks": checker.check_count,
                    "successful_checks": checker.success_count,
                    "failed_checks": checker.failure_count,
                    "success_rate": (checker.success_count / max(checker.check_count, 1)) * 100,
                    "last_check": checker.last_check.isoformat() if checker.last_check else None
                }
            
            metrics["component_statistics"] = component_stats
            
            # Performance metrics
            if self.performance_baseline:
                metrics["performance_baselines"] = dict(list(self.performance_baseline.items())[:10])  # Top 10
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to get system metrics: {str(e)}")
            raise
    
    async def trigger_manual_check(self, component_id: Optional[str] = None) -> Dict[str, Any]:
        """Trigger manual health check"""
        try:
            if component_id:
                # Check specific component
                if component_id in self.checkers:
                    checker = self.checkers[component_id]
                    health_result = await self._safe_health_check(component_id, checker)
                    self.health_history[component_id].append(health_result)
                    return {component_id: health_result.to_dict()}
                else:
                    raise ValueError(f"Component {component_id} not found")
            else:
                # Check all components
                await self._perform_health_checks()
                return {"message": "Manual health check completed for all components"}
                
        except Exception as e:
            self.logger.error(f"Failed to trigger manual check: {str(e)}")
            raise
    
    async def update_check_interval(self, new_interval: int):
        """Update health check interval"""
        if new_interval < 5:
            raise ValueError("Check interval cannot be less than 5 seconds")
        
        self.check_interval = new_interval
        await self.redis_client.hset("ymera:health:config", "check_interval", new_interval)
        self.logger.info(f"Health check interval updated to {new_interval} seconds")
    
    async def add_custom_checker(self, checker: HealthChecker):
        """Add a custom health checker"""
        self.checkers[checker.component_id] = checker
        self.logger.info(f"Added custom health checker: {checker.component_id}")
    
    async def remove_checker(self, component_id: str):
        """Remove a health checker"""
        if component_id in self.checkers:
            del self.checkers[component_id]
            if component_id in self.health_history:
                del self.health_history[component_id]
            self.logger.info(f"Removed health checker: {component_id}")


class HealthAnomalyDetector:
    """Anomaly detection for health monitoring data"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.HealthAnomalyDetector")
    
    async def detect_anomalies(self, 
                             component_id: str, 
                             health_history: List[ComponentHealth],
                             baselines: Dict[str, float]) -> List[Dict[str, Any]]:
        """Detect anomalies in health data"""
        anomalies = []
        
        try:
            if len(health_history) < 10:
                return anomalies
            
            # Extract time series data for key metrics
            response_times = []
            cpu_usage = []
            memory_usage = []
            
            for health in health_history:
                for metric in health.metrics:
                    if 'response_time' in metric.name or 'ping_time' in metric.name:
                        response_times.append(metric.value)
                    elif 'cpu_usage' in metric.name:
                        cpu_usage.append(metric.value)
                    elif 'memory_usage' in metric.name:
                        memory_usage.append(metric.value)
            
            # Check response time anomalies
            if len(response_times) >= 5:
                anomaly = await self._detect_metric_anomaly(
                    "response_time", 
                    response_times, 
                    baselines.get(f"{component_id}_avg_response", None)
                )
                if anomaly:
                    anomalies.append(anomaly)
            
            # Check resource usage spikes
            if len(cpu_usage) >= 5:
                anomaly = await self._detect_resource_spike("cpu_usage", cpu_usage)
                if anomaly:
                    anomalies.append(anomaly)
            
            if len(memory_usage) >= 5:
                anomaly = await self._detect_resource_spike("memory_usage", memory_usage)
                if anomaly:
                    anomalies.append(anomaly)
            
            # Check for degrading trends
            trend_anomaly = await self._detect_degrading_trend(health_history)
            if trend_anomaly:
                anomalies.append(trend_anomaly)
                
        except Exception as e:
            self.logger.warning(f"Failed to detect anomalies for {component_id}: {str(e)}")
        
        return anomalies
    
    async def _detect_metric_anomaly(self, 
                                   metric_name: str, 
                                   values: List[float], 
                                   baseline: Optional[float]) -> Optional[Dict[str, Any]]:
        """Detect anomalies in metric values"""
        if len(values) < 5:
            return None
        
        recent_values = values[-5:]
        current_avg = statistics.mean(recent_values)
        
        # Z-score based detection
        if len(values) >= 10:
            historical_mean = statistics.mean(values[:-5])
            historical_std = statistics.stdev(values[:-5]) if len(values[:-5]) > 1 else 0
            
            if historical_std > 0:
                z_score = abs(current_avg - historical_mean) / historical_std
                if z_score > 2.5:  # Significant anomaly
                    return {
                        "type": f"{metric_name}_anomaly",
                        "severity": "critical" if z_score > 3.5 else "warning",
                        "message": f"{metric_name} is {z_score:.2f} standard deviations from normal",
                        "details": {
                            "current_value": current_avg,
                            "historical_mean": historical_mean,
                            "z_score": z_score,
                            "threshold": 2.5
                        }
                    }
        
        # Baseline comparison
        if baseline and current_avg > baseline * 2:  # 200% of baseline
            return {
                "type": f"{metric_name}_spike",
                "severity": "warning",
                "message": f"{metric_name} is significantly higher than baseline",
                "details": {
                    "current_value": current_avg,
                    "baseline": baseline,
                    "spike_factor": current_avg / baseline
                }
            }
        
        return None
    
    async def _detect_resource_spike(self, 
                                   resource_name: str, 
                                   values: List[float]) -> Optional[Dict[str, Any]]:
        """Detect resource usage spikes"""
        if len(values) < 5:
            return None
        
        recent_avg = statistics.mean(values[-3:])  # Last 3 values
        
        # High usage thresholds
        if resource_name == "cpu_usage" and recent_avg > 90:
            return {
                "type": "cpu_spike",
                "severity": "critical",
                "message": f"CPU usage is critically high: {recent_avg:.1f}%",
                "details": {
                    "current_usage": recent_avg,
                    "threshold": 90,
                    "recent_values": values[-5:]
                }
            }
        
        if resource_name == "memory_usage" and recent_avg > 90:
            return {
                "type": "memory_spike",
                "severity": "critical", 
                "message": f"Memory usage is critically high: {recent_avg:.1f}%",
                "details": {
                    "current_usage": recent_avg,
                    "threshold": 90,
                    "recent_values": values[-5:]
                }
            }
        
        return None
    
    async def _detect_degrading_trend(self, 
                                    health_history: List[ComponentHealth]) -> Optional[Dict[str, Any]]:
        """Detect degrading performance trends"""
        if len(health_history) < 10:
            return None
        
        # Calculate trend in overall health status
        recent_statuses = [
            1 if h.status == HealthStatus.HEALTHY else
            0.5 if h.status == HealthStatus.WARNING else 0
            for h in health_history[-10:]
        ]
        
        # Check for consistent degradation
        if len(recent_statuses) >= 8:
            early_avg = statistics.mean(recent_statuses[:4])
            late_avg = statistics.mean(recent_statuses[-4:])
            
            if early_avg - late_avg > 0.3:  # Significant degradation
                return {
                    "type": "degrading_trend",
                    "severity": "warning",
                    "message": "Component health is showing a degrading trend",
                    "details": {
                        "early_avg_health": early_avg,
                        "recent_avg_health": late_avg,
                        "degradation": early_avg - late_avg,
                        "threshold": 0.3
                    }
                }
        
        return None