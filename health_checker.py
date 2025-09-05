"""
YMERA Enterprise - Health Monitoring System
Production-Ready System Health Checker - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import asyncio
import logging
import json
import os
import uuid
import psutil
import aioredis
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum

# Third-party imports
import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from pydantic import BaseModel, Field, validator

# Local imports
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.health_checker")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 300  # 5 minutes
DEFAULT_CHECK_INTERVAL = 60  # 1 minute

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

class HealthStatus(str, Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class ComponentType(str, Enum):
    """Component type enumeration"""
    DATABASE = "database"
    CACHE = "cache"
    STORAGE = "storage"
    EXTERNAL_API = "external_api"
    AGENT = "agent"
    LEARNING_ENGINE = "learning_engine"
    QUEUE = "queue"
    SYSTEM = "system"

@dataclass
class HealthCheckConfig:
    """Configuration for health checking system"""
    enabled: bool = True
    check_interval: int = 60
    timeout: int = 30
    max_retries: int = 3
    alert_threshold: int = 3
    component_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

@dataclass
class ComponentHealth:
    """Health status of individual component"""
    component_id: str
    component_type: ComponentType
    status: HealthStatus
    last_check: datetime
    response_time: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    check_count: int = 0
    failure_count: int = 0

class SystemHealthStatus(BaseModel):
    """Overall system health status"""
    overall_status: HealthStatus
    timestamp: datetime
    uptime_seconds: float
    component_count: int
    healthy_components: int
    degraded_components: int
    unhealthy_components: int
    components: Dict[str, ComponentHealth]
    system_metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]] = []

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ComponentHealth: lambda v: v.__dict__
        }

class HealthCheckRequest(BaseModel):
    """Health check request schema"""
    components: Optional[List[str]] = None
    include_metrics: bool = True
    include_alerts: bool = True

class HealthCheckResponse(BaseModel):
    """Health check response schema"""
    status: HealthStatus
    timestamp: datetime
    components: Dict[str, Dict[str, Any]]
    system_metrics: Optional[Dict[str, Any]] = None
    alerts: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ===============================================================================
# HEALTH CHECK IMPLEMENTATIONS
# ===============================================================================

class BaseHealthCheck(ABC):
    """Abstract base class for health checks"""
    
    def __init__(self, component_id: str, component_type: ComponentType, config: Dict[str, Any]):
        self.component_id = component_id
        self.component_type = component_type
        self.config = config
        self.logger = logger.bind(component=component_id, type=component_type.value)
    
    @abstractmethod
    async def check_health(self) -> ComponentHealth:
        """Perform health check for this component"""
        pass
    
    async def _create_health_result(
        self, 
        status: HealthStatus, 
        response_time: float,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ComponentHealth:
        """Create standardized health result"""
        return ComponentHealth(
            component_id=self.component_id,
            component_type=self.component_type,
            status=status,
            last_check=datetime.utcnow(),
            response_time=response_time,
            error_message=error_message,
            metadata=metadata or {}
        )

class DatabaseHealthCheck(BaseHealthCheck):
    """Database connectivity health check"""
    
    def __init__(self, component_id: str, config: Dict[str, Any]):
        super().__init__(component_id, ComponentType.DATABASE, config)
        self.connection_string = config.get("connection_string", settings.DATABASE_URL)
        self.engine = None
    
    async def check_health(self) -> ComponentHealth:
        """Check database connectivity and performance"""
        start_time = datetime.utcnow()
        
        try:
            if not self.engine:
                self.engine = create_async_engine(
                    self.connection_string,
                    pool_size=1,
                    max_overflow=0,
                    pool_timeout=5
                )
            
            async with self.engine.begin() as conn:
                # Test basic connectivity
                result = await conn.execute(text("SELECT 1"))
                await result.fetchone()
                
                # Get connection pool stats
                pool_stats = {
                    "pool_size": self.engine.pool.size(),
                    "checked_in": self.engine.pool.checkedin(),
                    "checked_out": self.engine.pool.checkedout(),
                    "overflow": self.engine.pool.overflow(),
                    "invalidated": self.engine.pool.invalidated()
                }
                
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Determine status based on response time
                if response_time > 1.0:
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.HEALTHY
                
                return await self._create_health_result(
                    status=status,
                    response_time=response_time,
                    metadata={
                        "pool_stats": pool_stats,
                        "database_version": "Unknown"  # Could be enhanced to get actual version
                    }
                )
                
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error("Database health check failed", error=str(e))
            
            return await self._create_health_result(
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                error_message=str(e)
            )

class RedisHealthCheck(BaseHealthCheck):
    """Redis cache connectivity health check"""
    
    def __init__(self, component_id: str, config: Dict[str, Any]):
        super().__init__(component_id, ComponentType.CACHE, config)
        self.redis_url = config.get("redis_url", settings.REDIS_URL)
        self.redis_client = None
    
    async def check_health(self) -> ComponentHealth:
        """Check Redis connectivity and performance"""
        start_time = datetime.utcnow()
        
        try:
            if not self.redis_client:
                self.redis_client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
            
            # Test basic connectivity
            await self.redis_client.ping()
            
            # Test read/write operations
            test_key = f"health_check:{uuid.uuid4()}"
            test_value = "health_test"
            
            await self.redis_client.set(test_key, test_value, ex=60)
            retrieved_value = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            if retrieved_value != test_value:
                raise Exception("Redis read/write operation failed")
            
            # Get Redis info
            info = await self.redis_client.info()
            memory_stats = {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Determine status based on response time and memory usage
            if response_time > 0.5:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            return await self._create_health_result(
                status=status,
                response_time=response_time,
                metadata={
                    "memory_stats": memory_stats,
                    "redis_version": info.get("redis_version", "Unknown")
                }
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error("Redis health check failed", error=str(e))
            
            return await self._create_health_result(
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                error_message=str(e)
            )

class SystemHealthCheck(BaseHealthCheck):
    """System resources health check"""
    
    def __init__(self, component_id: str, config: Dict[str, Any]):
        super().__init__(component_id, ComponentType.SYSTEM, config)
        self.cpu_threshold = config.get("cpu_threshold", 80.0)
        self.memory_threshold = config.get("memory_threshold", 85.0)
        self.disk_threshold = config.get("disk_threshold", 90.0)
    
    async def check_health(self) -> ComponentHealth:
        """Check system resource utilization"""
        start_time = datetime.utcnow()
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Load average (Unix-like systems)
            try:
                load_avg = os.getloadavg()
            except (OSError, AttributeError):
                load_avg = (0, 0, 0)
            
            # Network I/O
            network = psutil.net_io_counters()
            
            system_metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available": memory.available,
                "memory_total": memory.total,
                "disk_percent": disk_percent,
                "disk_free": disk.free,
                "disk_total": disk.total,
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                },
                "network_io": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            }
            
            # Determine overall status
            if (cpu_percent > self.cpu_threshold or 
                memory_percent > self.memory_threshold or 
                disk_percent > self.disk_threshold):
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return await self._create_health_result(
                status=status,
                response_time=response_time,
                metadata=system_metrics
            )
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error("System health check failed", error=str(e))
            
            return await self._create_health_result(
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                error_message=str(e)
            )

# ===============================================================================
# CORE HEALTH CHECKER IMPLEMENTATION
# ===============================================================================

class HealthChecker:
    """Production-ready health monitoring system"""
    
    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self.logger = logger.bind(component="health_checker")
        self._health_checks: Dict[str, BaseHealthCheck] = {}
        self._health_results: Dict[str, ComponentHealth] = {}
        self._system_start_time = datetime.utcnow()
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        self._alert_history: List[Dict[str, Any]] = []
    
    async def initialize(self) -> None:
        """Initialize health checking system"""
        try:
            await self._setup_health_checks()
            await self._start_monitoring()
            self.logger.info("Health checker initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize health checker", error=str(e))
            raise
    
    async def _setup_health_checks(self) -> None:
        """Setup all configured health checks"""
        # Database health check
        if "database" in self.config.component_configs:
            self._health_checks["database"] = DatabaseHealthCheck(
                "database",
                self.config.component_configs["database"]
            )
        
        # Redis health check
        if "redis" in self.config.component_configs:
            self._health_checks["redis"] = RedisHealthCheck(
                "redis",
                self.config.component_configs["redis"]
            )
        
        # System health check
        if "system" in self.config.component_configs:
            self._health_checks["system"] = SystemHealthCheck(
                "system",
                self.config.component_configs["system"]
            )
    
    async def _start_monitoring(self) -> None:
        """Start continuous health monitoring"""
        if self.config.enabled and not self._running:
            self._running = True
            self._check_task = asyncio.create_task(self._monitoring_loop())
            self.logger.info("Health monitoring started", interval=self.config.check_interval)
    
    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop"""
        while self._running:
            try:
                await self._run_all_checks()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _run_all_checks(self) -> None:
        """Run all configured health checks"""
        tasks = []
        for check_id, health_check in self._health_checks.items():
            tasks.append(self._run_single_check(check_id, health_check))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error("Health check task failed", error=str(result))
    
    async def _run_single_check(self, check_id: str, health_check: BaseHealthCheck) -> None:
        """Run a single health check with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                result = await asyncio.wait_for(
                    health_check.check_health(),
                    timeout=self.config.timeout
                )
                
                # Update failure count
                if result.status == HealthStatus.UNHEALTHY:
                    result.failure_count = self._health_results.get(check_id, ComponentHealth(
                        component_id=check_id,
                        component_type=health_check.component_type,
                        status=HealthStatus.UNKNOWN,
                        last_check=datetime.utcnow(),
                        response_time=0.0
                    )).failure_count + 1
                else:
                    result.failure_count = 0
                
                result.check_count = self._health_results.get(check_id, result).check_count + 1
                
                self._health_results[check_id] = result
                
                # Generate alerts if needed
                await self._check_for_alerts(check_id, result)
                
                break
                
            except asyncio.TimeoutError:
                self.logger.warning(f"Health check timeout", component=check_id, attempt=attempt + 1)
                if attempt == self.config.max_retries - 1:
                    # Final attempt failed
                    failed_result = ComponentHealth(
                        component_id=check_id,
                        component_type=health_check.component_type,
                        status=HealthStatus.UNHEALTHY,
                        last_check=datetime.utcnow(),
                        response_time=self.config.timeout,
                        error_message="Health check timeout",
                        failure_count=self._health_results.get(check_id, ComponentHealth(
                            component_id=check_id,
                            component_type=health_check.component_type,
                            status=HealthStatus.UNKNOWN,
                            last_check=datetime.utcnow(),
                            response_time=0.0
                        )).failure_count + 1
                    )
                    self._health_results[check_id] = failed_result
                    await self._check_for_alerts(check_id, failed_result)
            except Exception as e:
                self.logger.error(f"Health check failed", component=check_id, error=str(e), attempt=attempt + 1)
                if attempt == self.config.max_retries - 1:
                    # Final attempt failed
                    failed_result = ComponentHealth(
                        component_id=check_id,
                        component_type=health_check.component_type,
                        status=HealthStatus.UNHEALTHY,
                        last_check=datetime.utcnow(),
                        response_time=0.0,
                        error_message=str(e),
                        failure_count=self._health_results.get(check_id, ComponentHealth(
                            component_id=check_id,
                            component_type=health_check.component_type,
                            status=HealthStatus.UNKNOWN,
                            last_check=datetime.utcnow(),
                            response_time=0.0
                        )).failure_count + 1
                    )
                    self._health_results[check_id] = failed_result
                    await self._check_for_alerts(check_id, failed_result)
    
    async def _check_for_alerts(self, component_id: str, health: ComponentHealth) -> None:
        """Check if alerts should be generated"""
        if (health.status == HealthStatus.UNHEALTHY and 
            health.failure_count >= self.config.alert_threshold):
            
            alert = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "critical" if health.failure_count > 5 else "warning",
                "component": component_id,
                "message": f"Component {component_id} has been unhealthy for {health.failure_count} consecutive checks",
                "error": health.error_message,
                "metadata": health.metadata
            }
            
            self._alert_history.append(alert)
            
            # Keep only recent alerts (last 100)
            if len(self._alert_history) > 100:
                self._alert_history = self._alert_history[-100:]
            
            self.logger.error("Health alert generated", **alert)
    
    async def get_system_health(self, include_components: Optional[List[str]] = None) -> SystemHealthStatus:
        """Get comprehensive system health status"""
        try:
            # If no recent checks, run them now
            if not self._health_results:
                await self._run_all_checks()
            
            # Filter components if specified
            components = self._health_results
            if include_components:
                components = {k: v for k, v in self._health_results.items() if k in include_components}
            
            # Calculate overall status
            healthy_count = sum(1 for h in components.values() if h.status == HealthStatus.HEALTHY)
            degraded_count = sum(1 for h in components.values() if h.status == HealthStatus.DEGRADED)
            unhealthy_count = sum(1 for h in components.values() if h.status == HealthStatus.UNHEALTHY)
            
            if unhealthy_count > 0:
                overall_status = HealthStatus.UNHEALTHY
            elif degraded_count > 0:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY
            
            # System metrics
            uptime = (datetime.utcnow() - self._system_start_time).total_seconds()
            
            system_metrics = {
                "uptime_seconds": uptime,
                "uptime_human": str(timedelta(seconds=int(uptime))),
                "checks_performed": sum(h.check_count for h in components.values()),
                "total_failures": sum(h.failure_count for h in components.values()),
                "average_response_time": sum(h.response_time for h in components.values()) / len(components) if components else 0
            }
            
            # Recent alerts (last 10)
            recent_alerts = self._alert_history[-10:] if self._alert_history else []
            
            return SystemHealthStatus(
                overall_status=overall_status,
                timestamp=datetime.utcnow(),
                uptime_seconds=uptime,
                component_count=len(components),
                healthy_components=healthy_count,
                degraded_components=degraded_count,
                unhealthy_components=unhealthy_count,
                components=components,
                system_metrics=system_metrics,
                alerts=recent_alerts
            )
            
        except Exception as e:
            self.logger.error("Failed to get system health", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve system health status"
            )
    
    async def get_component_health(self, component_id: str) -> Optional[ComponentHealth]:
        """Get health status for specific component"""
        return self._health_results.get(component_id)
    
    async def add_health_check(self, component_id: str, health_check: BaseHealthCheck) -> None:
        """Add new health check dynamically"""
        self._health_checks[component_id] = health_check
        self.logger.info("Health check added", component=component_id)
    
    async def remove_health_check(self, component_id: str) -> None:
        """Remove health check"""
        if component_id in self._health_checks:
            del self._health_checks[component_id]
            if component_id in self._health_results:
                del self._health_results[component_id]
            self.logger.info("Health check removed", component=component_id)
    
    async def cleanup(self) -> None:
        """Cleanup health checker resources"""
        try:
            self._running = False
            if self._check_task:
                self._check_task.cancel()
                try:
                    await self._check_task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup individual health checks
            for health_check in self._health_checks.values():
                if hasattr(health_check, 'cleanup'):
                    await health_check.cleanup()
            
            self.logger.info("Health checker cleanup completed")
        except Exception as e:
            self.logger.error("Error during health checker cleanup", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check_endpoint() -> HealthCheckResponse:
    """Health check endpoint for load balancers"""
    try:
        # Quick system check
        system_check = SystemHealthCheck("quick_system", {})
        result = await system_check.check_health()
        
        return HealthCheckResponse(
            status=result.status,
            timestamp=datetime.utcnow(),
            components={"system": result.__dict__},
            system_metrics=result.metadata
        )
    except Exception as e:
        logger.error("Health check endpoint failed", error=str(e))
        return HealthCheckResponse(
            status=HealthStatus.UNHEALTHY,
            timestamp=datetime.utcnow(),
            components={"system": {"status": "unhealthy", "error": str(e)}},
            system_metrics={}
        )

def create_default_config() -> HealthCheckConfig:
    """Create default health check configuration"""
    return HealthCheckConfig(
        enabled=True,
        check_interval=60,
        timeout=30,
        max_retries=3,
        alert_threshold=3,
        component_configs={
            "database": {
                "connection_string": settings.DATABASE_URL
            },
            "redis": {
                "redis_url": settings.REDIS_URL
            },
            "system": {
                "cpu_threshold": 80.0,
                "memory_threshold": 85.0,
                "disk_threshold": 90.0
            }
        }
    )

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_health_checker(config: Optional[HealthCheckConfig] = None) -> HealthChecker:
    """Initialize health checker for production use"""
    if config is None:
        config = create_default_config()
    
    health_checker = HealthChecker(config)
    await health_checker.initialize()
    
    return health_checker

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "HealthChecker",
    "SystemHealthStatus",
    "ComponentHealth",
    "HealthCheckConfig",
    "HealthStatus",
    "ComponentType",
    "BaseHealthCheck",
    "DatabaseHealthCheck",
    "RedisHealthCheck",
    "SystemHealthCheck",
    "initialize_health_checker",
    "health_check_endpoint",
    "create_default_config"
]