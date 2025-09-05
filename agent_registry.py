"""
YMERA Enterprise - Agent Registry
Production-Ready Agent Tracking & Management System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, validator

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Module-specific constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 3600
AGENT_HEARTBEAT_INTERVAL = 30
AGENT_TIMEOUT_THRESHOLD = 300
MAX_AGENTS_PER_TYPE = 100
REGISTRY_SYNC_INTERVAL = 60

# Configuration loading
settings = get_settings()

# ===============================================================================
# ENUMS & DATA MODELS
# ===============================================================================

class AgentStatus(Enum):
    """Agent operational status enumeration"""
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    ERROR = "error"

class AgentType(Enum):
    """Agent type classification"""
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    SPECIALIST = "specialist"
    MONITOR = "monitor"
    LEARNER = "learner"

@dataclass
class AgentCapability:
    """Agent capability definition"""
    name: str
    version: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)

@dataclass
class AgentMetrics:
    """Agent performance and health metrics"""
    requests_processed: int = 0
    success_rate: float = 0.0
    average_response_time: float = 0.0
    error_count: int = 0
    last_activity: Optional[datetime] = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_connections: int = 0

@dataclass
class AgentRegistrationInfo:
    """Complete agent registration information"""
    agent_id: str
    agent_type: AgentType
    name: str
    version: str
    status: AgentStatus
    capabilities: List[AgentCapability]
    metrics: AgentMetrics
    metadata: Dict[str, Any]
    registered_at: datetime
    last_heartbeat: datetime
    endpoint_url: Optional[str] = None
    health_check_url: Optional[str] = None
    tags: Set[str] = field(default_factory=set)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class AgentRegistrationRequest(BaseModel):
    """Schema for agent registration requests"""
    name: str = Field(..., min_length=1, max_length=100)
    agent_type: str = Field(..., regex="^(orchestrator|worker|specialist|monitor|learner)$")
    version: str = Field(..., regex=r"^\d+\.\d+\.\d+$")
    capabilities: List[Dict[str, Any]] = Field(default_factory=list)
    endpoint_url: Optional[str] = Field(None, regex=r"^https?://")
    health_check_url: Optional[str] = Field(None, regex=r"^https?://")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    @validator('capabilities')
    def validate_capabilities(cls, v):
        for cap in v:
            if 'name' not in cap or 'version' not in cap:
                raise ValueError("Each capability must have 'name' and 'version'")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class AgentUpdateRequest(BaseModel):
    """Schema for agent status updates"""
    status: Optional[str] = Field(None, regex="^(active|idle|busy|maintenance|offline|error)$")
    metrics: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

class AgentQueryRequest(BaseModel):
    """Schema for agent query requests"""
    agent_types: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    include_metrics: bool = True
    include_offline: bool = False

class AgentRegistryResponse(BaseModel):
    """Schema for registry operation responses"""
    success: bool
    message: str
    agent_id: Optional[str] = None
    agents: Optional[List[Dict[str, Any]]] = None
    total_count: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class AgentRegistryConfig:
    """Configuration for agent registry system"""
    
    def __init__(self):
        self.enabled: bool = settings.AGENT_REGISTRY_ENABLED
        self.max_agents: int = settings.MAX_AGENTS_TOTAL
        self.heartbeat_interval: int = AGENT_HEARTBEAT_INTERVAL
        self.timeout_threshold: int = AGENT_TIMEOUT_THRESHOLD
        self.sync_interval: int = REGISTRY_SYNC_INTERVAL
        self.redis_url: str = settings.REDIS_URL
        self.database_url: str = settings.DATABASE_URL
        self.enable_metrics: bool = settings.ENABLE_AGENT_METRICS
        self.enable_health_checks: bool = settings.ENABLE_HEALTH_CHECKS

class BaseAgentRegistry(ABC):
    """Abstract base class for agent registry implementations"""
    
    def __init__(self, config: AgentRegistryConfig):
        self.config = config
        self.logger = logger.bind(module=self.__class__.__name__)
        
    @abstractmethod
    async def register_agent(self, registration_info: AgentRegistrationInfo) -> str:
        """Register a new agent in the registry"""
        pass
    
    @abstractmethod
    async def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry"""
        pass
    
    @abstractmethod
    async def update_agent_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update agent status"""
        pass
    
    @abstractmethod
    async def get_active_agents(self, filters: Optional[Dict[str, Any]] = None) -> List[AgentRegistrationInfo]:
        """Get list of active agents with optional filtering"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup registry resources"""
        pass

class ProductionAgentRegistry(BaseAgentRegistry):
    """Production-ready agent registry implementation"""
    
    def __init__(self, config: AgentRegistryConfig):
        super().__init__(config)
        self._redis_client: Optional[aioredis.Redis] = None
        self._agents_cache: Dict[str, AgentRegistrationInfo] = {}
        self._type_counters: Dict[AgentType, int] = {t: 0 for t in AgentType}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._health_status = True
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def _initialize_resources(self) -> None:
        """Initialize all required resources"""
        try:
            await self._setup_redis_connection()
            await self._setup_background_tasks()
            await self._load_existing_agents()
            self.logger.info("Agent registry initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize agent registry", error=str(e))
            raise
    
    async def _setup_redis_connection(self) -> None:
        """Setup Redis connection for caching and pub/sub"""
        try:
            self._redis_client = await aioredis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=30,
                socket_connect_timeout=10,
                retry_on_timeout=True,
                max_connections=20
            )
            
            # Test connection
            await self._redis_client.ping()
            self.logger.info("Redis connection established")
            
        except Exception as e:
            self.logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def _setup_background_tasks(self) -> None:
        """Setup background maintenance tasks"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_agents())
        self._sync_task = asyncio.create_task(self._sync_registry_state())
        self.logger.info("Background tasks started")
    
    async def _load_existing_agents(self) -> None:
        """Load existing agents from persistent storage"""
        try:
            if not self._redis_client:
                return
                
            # Load all agent keys
            agent_keys = await self._redis_client.keys("agent:*")
            
            for key in agent_keys:
                agent_data = await self._redis_client.hgetall(key)
                if agent_data:
                    agent_info = self._deserialize_agent_info(agent_data)
                    if agent_info:
                        self._agents_cache[agent_info.agent_id] = agent_info
                        self._type_counters[agent_info.agent_type] += 1
            
            self.logger.info("Loaded existing agents", count=len(self._agents_cache))
            
        except Exception as e:
            self.logger.error("Failed to load existing agents", error=str(e))
    
    @track_performance
    async def register_agent(self, registration_info: AgentRegistrationInfo) -> str:
        """Register a new agent in the registry"""
        async with self._lock:
            try:
                # Validate registration
                await self._validate_registration(registration_info)
                
                # Check capacity limits
                if self._type_counters[registration_info.agent_type] >= MAX_AGENTS_PER_TYPE:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Maximum agents of type {registration_info.agent_type.value} reached"
                    )
                
                # Generate unique agent ID if not provided
                if not registration_info.agent_id:
                    registration_info.agent_id = str(uuid.uuid4())
                
                # Set registration timestamp
                registration_info.registered_at = datetime.utcnow()
                registration_info.last_heartbeat = datetime.utcnow()
                
                # Store in cache
                self._agents_cache[registration_info.agent_id] = registration_info
                self._type_counters[registration_info.agent_type] += 1
                
                # Persist to Redis
                await self._persist_agent_info(registration_info)
                
                # Publish registration event
                await self._publish_agent_event("agent_registered", registration_info.agent_id, {
                    "agent_type": registration_info.agent_type.value,
                    "name": registration_info.name,
                    "capabilities": [cap.name for cap in registration_info.capabilities]
                })
                
                self.logger.info(
                    "Agent registered successfully",
                    agent_id=registration_info.agent_id,
                    agent_type=registration_info.agent_type.value,
                    name=registration_info.name
                )
                
                return registration_info.agent_id
                
            except Exception as e:
                self.logger.error("Agent registration failed", error=str(e))
                raise
    
    async def _validate_registration(self, registration_info: AgentRegistrationInfo) -> None:
        """Validate agent registration information"""
        if not registration_info.name or len(registration_info.name.strip()) == 0:
            raise ValueError("Agent name is required")
        
        if not registration_info.version:
            raise ValueError("Agent version is required")
        
        if registration_info.agent_id and registration_info.agent_id in self._agents_cache:
            raise ValueError(f"Agent ID {registration_info.agent_id} already exists")
        
        # Validate capabilities
        for capability in registration_info.capabilities:
            if not capability.name or not capability.version:
                raise ValueError("Each capability must have name and version")
    
    async def _persist_agent_info(self, agent_info: AgentRegistrationInfo) -> None:
        """Persist agent information to Redis"""
        if not self._redis_client:
            return
        
        agent_key = f"agent:{agent_info.agent_id}"
        agent_data = self._serialize_agent_info(agent_info)
        
        await self._redis_client.hset(agent_key, mapping=agent_data)
        await self._redis_client.expire(agent_key, self.config.timeout_threshold * 2)
    
    def _serialize_agent_info(self, agent_info: AgentRegistrationInfo) -> Dict[str, str]:
        """Serialize agent info for Redis storage"""
        return {
            "agent_id": agent_info.agent_id,
            "agent_type": agent_info.agent_type.value,
            "name": agent_info.name,
            "version": agent_info.version,
            "status": agent_info.status.value,
            "capabilities": json.dumps([{
                "name": cap.name,
                "version": cap.version,
                "parameters": cap.parameters,
                "performance_metrics": cap.performance_metrics
            } for cap in agent_info.capabilities]),
            "metrics": json.dumps({
                "requests_processed": agent_info.metrics.requests_processed,
                "success_rate": agent_info.metrics.success_rate,
                "average_response_time": agent_info.metrics.average_response_time,
                "error_count": agent_info.metrics.error_count,
                "last_activity": agent_info.metrics.last_activity.isoformat() if agent_info.metrics.last_activity else None,
                "cpu_usage": agent_info.metrics.cpu_usage,
                "memory_usage": agent_info.metrics.memory_usage,
                "active_connections": agent_info.metrics.active_connections
            }),
            "metadata": json.dumps(agent_info.metadata),
            "registered_at": agent_info.registered_at.isoformat(),
            "last_heartbeat": agent_info.last_heartbeat.isoformat(),
            "endpoint_url": agent_info.endpoint_url or "",
            "health_check_url": agent_info.health_check_url or "",
            "tags": json.dumps(list(agent_info.tags))
        }
    
    def _deserialize_agent_info(self, agent_data: Dict[str, str]) -> Optional[AgentRegistrationInfo]:
        """Deserialize agent info from Redis storage"""
        try:
            capabilities_data = json.loads(agent_data.get("capabilities", "[]"))
            capabilities = [
                AgentCapability(
                    name=cap["name"],
                    version=cap["version"],
                    parameters=cap.get("parameters", {}),
                    performance_metrics=cap.get("performance_metrics", {})
                ) for cap in capabilities_data
            ]
            
            metrics_data = json.loads(agent_data.get("metrics", "{}"))
            metrics = AgentMetrics(
                requests_processed=metrics_data.get("requests_processed", 0),
                success_rate=metrics_data.get("success_rate", 0.0),
                average_response_time=metrics_data.get("average_response_time", 0.0),
                error_count=metrics_data.get("error_count", 0),
                last_activity=datetime.fromisoformat(metrics_data["last_activity"]) if metrics_data.get("last_activity") else None,
                cpu_usage=metrics_data.get("cpu_usage", 0.0),
                memory_usage=metrics_data.get("memory_usage", 0.0),
                active_connections=metrics_data.get("active_connections", 0)
            )
            
            return AgentRegistrationInfo(
                agent_id=agent_data["agent_id"],
                agent_type=AgentType(agent_data["agent_type"]),
                name=agent_data["name"],
                version=agent_data["version"],
                status=AgentStatus(agent_data["status"]),
                capabilities=capabilities,
                metrics=metrics,
                metadata=json.loads(agent_data.get("metadata", "{}")),
                registered_at=datetime.fromisoformat(agent_data["registered_at"]),
                last_heartbeat=datetime.fromisoformat(agent_data["last_heartbeat"]),
                endpoint_url=agent_data.get("endpoint_url") or None,
                health_check_url=agent_data.get("health_check_url") or None,
                tags=set(json.loads(agent_data.get("tags", "[]")))
            )
            
        except Exception as e:
            self.logger.error("Failed to deserialize agent info", error=str(e), agent_data=agent_data)
            return None
    
    @track_performance
    async def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry"""
        async with self._lock:
            try:
                if agent_id not in self._agents_cache:
                    self.logger.warning("Attempted to unregister non-existent agent", agent_id=agent_id)
                    return False
                
                agent_info = self._agents_cache[agent_id]
                
                # Remove from cache
                del self._agents_cache[agent_id]
                self._type_counters[agent_info.agent_type] -= 1
                
                # Remove from Redis
                if self._redis_client:
                    await self._redis_client.delete(f"agent:{agent_id}")
                
                # Publish unregistration event
                await self._publish_agent_event("agent_unregistered", agent_id, {
                    "agent_type": agent_info.agent_type.value,
                    "name": agent_info.name
                })
                
                self.logger.info("Agent unregistered successfully", agent_id=agent_id)
                return True
                
            except Exception as e:
                self.logger.error("Agent unregistration failed", agent_id=agent_id, error=str(e))
                return False
    
    @track_performance
    async def update_agent_status(self, agent_id: str, status: AgentStatus, metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Update agent status and metrics"""
        async with self._lock:
            try:
                if agent_id not in self._agents_cache:
                    self.logger.warning("Attempted to update non-existent agent", agent_id=agent_id)
                    return False
                
                agent_info = self._agents_cache[agent_id]
                old_status = agent_info.status
                
                # Update status
                agent_info.status = status
                agent_info.last_heartbeat = datetime.utcnow()
                
                # Update metrics if provided
                if metrics:
                    await self._update_agent_metrics(agent_info, metrics)
                
                # Persist changes
                await self._persist_agent_info(agent_info)
                
                # Publish status change event if status changed
                if old_status != status:
                    await self._publish_agent_event("agent_status_changed", agent_id, {
                        "old_status": old_status.value,
                        "new_status": status.value,
                        "agent_type": agent_info.agent_type.value
                    })
                
                self.logger.debug("Agent status updated", agent_id=agent_id, status=status.value)
                return True
                
            except Exception as e:
                self.logger.error("Agent status update failed", agent_id=agent_id, error=str(e))
                return False
    
    async def _update_agent_metrics(self, agent_info: AgentRegistrationInfo, metrics: Dict[str, Any]) -> None:
        """Update agent performance metrics"""
        agent_metrics = agent_info.metrics
        
        # Update individual metrics
        if "requests_processed" in metrics:
            agent_metrics.requests_processed = metrics["requests_processed"]
        
        if "success_rate" in metrics:
            agent_metrics.success_rate = float(metrics["success_rate"])
        
        if "average_response_time" in metrics:
            agent_metrics.average_response_time = float(metrics["average_response_time"])
        
        if "error_count" in metrics:
            agent_metrics.error_count = metrics["error_count"]
        
        if "cpu_usage" in metrics:
            agent_metrics.cpu_usage = float(metrics["cpu_usage"])
        
        if "memory_usage" in metrics:
            agent_metrics.memory_usage = float(metrics["memory_usage"])
        
        if "active_connections" in metrics:
            agent_metrics.active_connections = metrics["active_connections"]
        
        agent_metrics.last_activity = datetime.utcnow()
    
    @track_performance
    async def get_active_agents(self, filters: Optional[Dict[str, Any]] = None) -> List[AgentRegistrationInfo]:
        """Get list of active agents with optional filtering"""
        try:
            agents = list(self._agents_cache.values())
            
            if not filters:
                return [agent for agent in agents if agent.status != AgentStatus.OFFLINE]
            
            # Apply filters
            filtered_agents = agents
            
            if "agent_types" in filters:
                type_filter = [AgentType(t) for t in filters["agent_types"]]
                filtered_agents = [a for a in filtered_agents if a.agent_type in type_filter]
            
            if "statuses" in filters:
                status_filter = [AgentStatus(s) for s in filters["statuses"]]
                filtered_agents = [a for a in filtered_agents if a.status in status_filter]
            
            if "capabilities" in filters:
                cap_filter = set(filters["capabilities"])
                filtered_agents = [
                    a for a in filtered_agents 
                    if any(cap.name in cap_filter for cap in a.capabilities)
                ]
            
            if "tags" in filters:
                tag_filter = set(filters["tags"])
                filtered_agents = [
                    a for a in filtered_agents 
                    if tag_filter.intersection(a.tags)
                ]
            
            if not filters.get("include_offline", False):
                filtered_agents = [a for a in filtered_agents if a.status != AgentStatus.OFFLINE]
            
            return filtered_agents
            
        except Exception as e:
            self.logger.error("Failed to get active agents", error=str(e))
            return []
    
    async def get_agent_by_id(self, agent_id: str) -> Optional[AgentRegistrationInfo]:
        """Get specific agent by ID"""
        return self._agents_cache.get(agent_id)
    
    async def get_agents_by_capability(self, capability_name: str) -> List[AgentRegistrationInfo]:
        """Get agents that have a specific capability"""
        matching_agents = []
        
        for agent in self._agents_cache.values():
            if agent.status == AgentStatus.OFFLINE:
                continue
                
            for capability in agent.capabilities:
                if capability.name == capability_name:
                    matching_agents.append(agent)
                    break
        
        return matching_agents
    
    async def get_registry_statistics(self) -> Dict[str, Any]:
        """Get comprehensive registry statistics"""
        total_agents = len(self._agents_cache)
        active_agents = len([a for a in self._agents_cache.values() if a.status == AgentStatus.ACTIVE])
        
        status_counts = {}
        for status in AgentStatus:
            status_counts[status.value] = len([a for a in self._agents_cache.values() if a.status == status])
        
        type_counts = {}
        for agent_type in AgentType:
            type_counts[agent_type.value] = self._type_counters[agent_type]
        
        # Calculate average metrics
        all_agents = list(self._agents_cache.values())
        avg_response_time = sum(a.metrics.average_response_time for a in all_agents) / len(all_agents) if all_agents else 0
        avg_success_rate = sum(a.metrics.success_rate for a in all_agents) / len(all_agents) if all_agents else 0
        
        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "average_response_time": avg_response_time,
            "average_success_rate": avg_success_rate,
            "registry_health": self._health_status,
            "last_cleanup": datetime.utcnow().isoformat()
        }
    
    async def _publish_agent_event(self, event_type: str, agent_id: str, data: Dict[str, Any]) -> None:
        """Publish agent events to Redis pub/sub"""
        if not self._redis_client:
            return
        
        try:
            event_data = {
                "event_type": event_type,
                "agent_id": agent_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }
            
            await self._redis_client.publish("agent_events", json.dumps(event_data))
            
        except Exception as e:
            self.logger.error("Failed to publish agent event", error=str(e), event_type=event_type)
    
    async def _cleanup_expired_agents(self) -> None:
        """Background task to cleanup expired agents"""
        while True:
            try:
                await asyncio.sleep(self.config.sync_interval)
                
                current_time = datetime.utcnow()
                expired_agents = []
                
                for agent_id, agent_info in self._agents_cache.items():
                    time_since_heartbeat = (current_time - agent_info.last_heartbeat).total_seconds()
                    
                    if time_since_heartbeat > self.config.timeout_threshold:
                        expired_agents.append(agent_id)
                
                # Remove expired agents
                for agent_id in expired_agents:
                    agent_info = self._agents_cache[agent_id]
                    agent_info.status = AgentStatus.OFFLINE
                    
                    await self._publish_agent_event("agent_timeout", agent_id, {
                        "agent_type": agent_info.agent_type.value,
                        "last_heartbeat": agent_info.last_heartbeat.isoformat()
                    })
                    
                    self.logger.warning("Agent marked as offline due to timeout", agent_id=agent_id)
                
                if expired_agents:
                    self.logger.info("Cleaned up expired agents", count=len(expired_agents))
                    
            except Exception as e:
                self.logger.error("Error in agent cleanup task", error=str(e))
    
    async def _sync_registry_state(self) -> None:
        """Background task to sync registry state"""
        while True:
            try:
                await asyncio.sleep(self.config.sync_interval)
                
                # Perform health checks on agents with health check URLs
                if self.config.enable_health_checks:
                    await self._perform_health_checks()
                
                # Update registry statistics
                stats = await self.get_registry_statistics()
                if self._redis_client:
                    await self._redis_client.set("registry_stats", json.dumps(stats), ex=300)
                
            except Exception as e:
                self.logger.error("Error in registry sync task", error=str(e))
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on registered agents"""
        import aiohttp
        
        agents_to_check = [
            agent for agent in self._agents_cache.values()
            if agent.health_check_url and agent.status != AgentStatus.OFFLINE
        ]
        
        if not agents_to_check:
            return
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for agent in agents_to_check:
                try:
                    async with session.get(agent.health_check_url) as response:
                        if response.status == 200:
                            if agent.status == AgentStatus.ERROR:
                                await self.update_agent_status(agent.agent_id, AgentStatus.ACTIVE)
                                self.logger.info("Agent recovered from error state", agent_id=agent.agent_id)
                        else:
                            await self.update_agent_status(agent.agent_id, AgentStatus.ERROR)
                            self.logger.warning(
                                "Agent health check failed",
                                agent_id=agent.agent_id,
                                status_code=response.status
                            )
                            
                except Exception as e:
                    await self.update_agent_status(agent.agent_id, AgentStatus.ERROR)
                    self.logger.error(
                        "Agent health check exception",
                        agent_id=agent.agent_id,
                        error=str(e)
                    )
    
    async def cleanup(self) -> None:
        """Cleanup registry resources"""
        try:
            # Cancel background tasks
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            if self._sync_task:
                self._sync_task.cancel()
            
            # Close Redis connection
            if self._redis_client:
                await self._redis_client.close()
            
            # Shutdown executor
            self._executor.shutdown(wait=True)
            
            self.logger.info("Agent registry cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during registry cleanup", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Agent registry health check endpoint"""
    try:
        registry = await get_agent_registry()
        stats = await registry.get_registry_statistics()
        
        return {
            "status": "healthy" if stats["registry_health"] else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "agent_registry",
            "version": "4.0",
            "statistics": stats
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "agent_registry",
            "error": str(e)
        }

def validate_agent_registration(data: Dict[str, Any]) -> AgentRegistrationRequest:
    """Validate agent registration data"""
    try:
        return AgentRegistrationRequest(**data)
    except Exception as e:
        logger.warning("Agent registration validation failed", errors=str(e))
        raise HTTPException(status_code=422, detail="Invalid registration data")

async def create_agent_info_from_request(request: AgentRegistrationRequest) -> AgentRegistrationInfo:
    """Create AgentRegistrationInfo from validated request"""
    capabilities = [
        AgentCapability(
            name=cap["name"],
            version=cap["version"],
            parameters=cap.get("parameters", {}),
            performance_metrics=cap.get("performance_metrics", {})
        ) for cap in request.capabilities
    ]
    
    return AgentRegistrationInfo(
        agent_id="",  # Will be generated during registration
        agent_type=AgentType(request.agent_type),
        name=request.name,
        version=request.version,
        status=AgentStatus.ACTIVE,
        capabilities=capabilities,
        metrics=AgentMetrics(),
        metadata=request.metadata,
        registered_at=datetime.utcnow(),
        last_heartbeat=datetime.utcnow(),
        endpoint_url=request.endpoint_url,
        health_check_url=request.health_check_url,
        tags=set(request.tags)
    )

def format_agent_info_for_response(agent_info: AgentRegistrationInfo, include_metrics: bool = True) -> Dict[str, Any]:
    """Format agent info for API response"""
    response_data = {
        "agent_id": agent_info.agent_id,
        "agent_type": agent_info.agent_type.value,
        "name": agent_info.name,
        "version": agent_info.version,
        "status": agent_info.status.value,
        "capabilities": [
            {
                "name": cap.name,
                "version": cap.version,
                "parameters": cap.parameters,
                "performance_metrics": cap.performance_metrics if include_metrics else {}
            } for cap in agent_info.capabilities
        ],
        "metadata": agent_info.metadata,
        "registered_at": agent_info.registered_at.isoformat(),
        "last_heartbeat": agent_info.last_heartbeat.isoformat(),
        "endpoint_url": agent_info.endpoint_url,
        "health_check_url": agent_info.health_check_url,
        "tags": list(agent_info.tags)
    }
    
    if include_metrics:
        response_data["metrics"] = {
            "requests_processed": agent_info.metrics.requests_processed,
            "success_rate": agent_info.metrics.success_rate,
            "average_response_time": agent_info.metrics.average_response_time,
            "error_count": agent_info.metrics.error_count,
            "last_activity": agent_info.metrics.last_activity.isoformat() if agent_info.metrics.last_activity else None,
            "cpu_usage": agent_info.metrics.cpu_usage,
            "memory_usage": agent_info.metrics.memory_usage,
            "active_connections": agent_info.metrics.active_connections
        }
    
    return response_data

# ===============================================================================
# SINGLETON REGISTRY INSTANCE
# ===============================================================================

_registry_instance: Optional[ProductionAgentRegistry] = None
_registry_lock = asyncio.Lock()

async def get_agent_registry() -> ProductionAgentRegistry:
    """Get singleton agent registry instance"""
    global _registry_instance
    
    if not _registry_instance:
        async with _registry_lock:
            if not _registry_instance:
                config = AgentRegistryConfig()
                _registry_instance = ProductionAgentRegistry(config)
                await _registry_instance._initialize_resources()
    
    return _registry_instance

async def shutdown_agent_registry() -> None:
    """Shutdown the agent registry instance"""
    global _registry_instance
    
    if _registry_instance:
        await _registry_instance.cleanup()
        _registry_instance = None

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_agent_registry() -> ProductionAgentRegistry:
    """Initialize agent registry for production use"""
    try:
        registry = await get_agent_registry()
        logger.info("Agent registry initialized successfully")
        return registry
    except Exception as e:
        logger.error("Failed to initialize agent registry", error=str(e))
        raise

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionAgentRegistry",
    "AgentRegistryConfig",
    "AgentRegistrationInfo",
    "AgentRegistrationRequest",
    "AgentUpdateRequest",
    "AgentQueryRequest",
    "AgentRegistryResponse",
    "AgentStatus",
    "AgentType",
    "AgentCapability",
    "AgentMetrics",
    "get_agent_registry",
    "initialize_agent_registry",
    "shutdown_agent_registry",
    "health_check",
    "validate_agent_registration",
    "create_agent_info_from_request",
    "format_agent_info_for_response"
]