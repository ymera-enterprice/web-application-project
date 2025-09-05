"""
YMERA Enterprise Multi-Agent System
Task Context Management Models - Production Ready
Comprehensive task context tracking, state management, and learning integration
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import (
    Any, Dict, List, Optional, Union, Set, Tuple, 
    Generic, TypeVar, Callable, AsyncCallable, Awaitable
)
from uuid import uuid4, UUID
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship
import json
import asyncio
from contextvars import ContextVar
import logging
from pathlib import Path
import hashlib
import pickle
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict, deque
from weakref import WeakValueDictionary
import traceback


# Type definitions
T = TypeVar('T')
ContextID = str
AgentID = str
TaskID = str
WorkflowID = str

Base = declarative_base()

# Context variable for current task context
current_task_context: ContextVar[Optional['TaskContext']] = ContextVar(
    'current_task_context', 
    default=None
)

class TaskPriority(IntEnum):
    """Task priority levels with numeric values for sorting"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5

class TaskStatus(Enum):
    """Comprehensive task status enumeration"""
    CREATED = "created"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    BLOCKED = "blocked"
    WAITING_FOR_DEPENDENCY = "waiting_for_dependency"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRY = "retry"
    DELEGATED = "delegated"
    MERGED = "merged"
    SPLIT = "split"

class TaskType(Enum):
    """Task type classification"""
    ANALYSIS = "analysis"
    ENHANCEMENT = "enhancement"
    VALIDATION = "validation"
    DOCUMENTATION = "documentation"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    SECURITY = "security"
    PROJECT_MANAGEMENT = "project_management"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    EXAMINATION = "examination"
    ORCHESTRATION = "orchestration"
    WORKFLOW = "workflow"
    BATCH = "batch"
    REAL_TIME = "real_time"
    SCHEDULED = "scheduled"

class ContextScope(Enum):
    """Context scope levels"""
    GLOBAL = "global"
    WORKFLOW = "workflow"
    AGENT = "agent"
    TASK = "task"
    SUBTASK = "subtask"
    REQUEST = "request"
    SESSION = "session"

class LearningContextType(Enum):
    """Learning context classification"""
    SUCCESS_PATTERN = "success_pattern"
    FAILURE_PATTERN = "failure_pattern"
    OPTIMIZATION = "optimization"
    ADAPTATION = "adaptation"
    FEEDBACK = "feedback"
    PERFORMANCE = "performance"
    COLLABORATION = "collaboration"
    DECISION = "decision"
    ANOMALY = "anomaly"
    TREND = "trend"

class ResourceType(Enum):
    """Resource type enumeration"""
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    API_QUOTA = "api_quota"
    DATABASE_CONNECTION = "database_connection"
    CACHE = "cache"
    VECTOR_DB = "vector_db"
    AI_SERVICE = "ai_service"
    EXTERNAL_API = "external_api"
    FILE_HANDLE = "file_handle"
    LOCK = "lock"

@dataclass
class TaskMetrics:
    """Comprehensive task performance metrics"""
    execution_time: float = 0.0
    cpu_time: float = 0.0
    memory_usage: float = 0.0
    memory_peak: float = 0.0
    network_io: float = 0.0
    disk_io: float = 0.0
    api_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    db_queries: int = 0
    ai_tokens_consumed: int = 0
    ai_cost: float = 0.0
    error_count: int = 0
    retry_count: int = 0
    quality_score: float = 0.0
    confidence_score: float = 0.0
    learning_value: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def add_metrics(self, other: 'TaskMetrics') -> 'TaskMetrics':
        """Add metrics from another TaskMetrics instance"""
        return TaskMetrics(
            execution_time=self.execution_time + other.execution_time,
            cpu_time=self.cpu_time + other.cpu_time,
            memory_usage=max(self.memory_usage, other.memory_usage),
            memory_peak=max(self.memory_peak, other.memory_peak),
            network_io=self.network_io + other.network_io,
            disk_io=self.disk_io + other.disk_io,
            api_calls=self.api_calls + other.api_calls,
            cache_hits=self.cache_hits + other.cache_hits,
            cache_misses=self.cache_misses + other.cache_misses,
            db_queries=self.db_queries + other.db_queries,
            ai_tokens_consumed=self.ai_tokens_consumed + other.ai_tokens_consumed,
            ai_cost=self.ai_cost + other.ai_cost,
            error_count=self.error_count + other.error_count,
            retry_count=self.retry_count + other.retry_count,
            quality_score=(self.quality_score + other.quality_score) / 2,
            confidence_score=(self.confidence_score + other.confidence_score) / 2,
            learning_value=self.learning_value + other.learning_value
        )

@dataclass
class ResourceConstraints:
    """Resource constraints and limits"""
    max_execution_time: Optional[float] = None
    max_memory_mb: Optional[float] = None
    max_cpu_percent: Optional[float] = None
    max_api_calls: Optional[int] = None
    max_cost: Optional[float] = None
    max_retries: int = 3
    timeout_seconds: float = 300.0
    priority_boost_factor: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class TaskDependency:
    """Task dependency definition"""
    task_id: TaskID
    dependency_type: str = "prerequisite"  # prerequisite, resource, data, approval
    condition: Optional[str] = None
    optional: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass 
class TaskResult:
    """Comprehensive task result container"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    error_details: Dict[str, Any] = field(default_factory=dict)
    metrics: TaskMetrics = field(default_factory=TaskMetrics)
    artifacts: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 1.0
    quality: float = 1.0
    learning_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if hasattr(self.data, 'to_dict'):
            result['data'] = self.data.to_dict()
        elif hasattr(self.data, '__dict__'):
            result['data'] = self.data.__dict__
        return result

class LearningContext(BaseModel):
    """Learning context for continuous improvement"""
    context_id: str = Field(default_factory=lambda: str(uuid4()))
    context_type: LearningContextType
    patterns: Dict[str, Any] = Field(default_factory=dict)
    outcomes: Dict[str, Any] = Field(default_factory=dict)
    feedback: Dict[str, Any] = Field(default_factory=dict)
    correlations: Dict[str, float] = Field(default_factory=dict)
    importance: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Set[str] = Field(default_factory=set)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            set: list
        }

class TaskContextSnapshot(BaseModel):
    """Immutable snapshot of task context state"""
    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    context_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: TaskStatus
    progress: float = Field(ge=0.0, le=1.0)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)
    environment: Dict[str, Any] = Field(default_factory=dict)
    checkpoint_data: Optional[bytes] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class TaskContext(BaseModel):
    """
    Comprehensive task context management with enterprise features
    Supports multi-agent coordination, learning integration, and production monitoring
    """
    
    # Core identification
    context_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: Optional[str] = None
    parent_context_id: Optional[str] = None
    root_context_id: Optional[str] = None
    
    # Task definition
    task_type: TaskType
    task_name: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    scope: ContextScope = ContextScope.TASK
    
    # Status and lifecycle
    status: TaskStatus = TaskStatus.CREATED
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    completion_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Agent assignment
    assigned_agent_id: Optional[str] = None
    requesting_agent_id: Optional[str] = None
    responsible_agents: Set[str] = Field(default_factory=set)
    collaborating_agents: Set[str] = Field(default_factory=set)
    
    # Temporal information
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    estimated_duration: Optional[float] = None  # seconds
    
    # Dependencies and relationships
    dependencies: List[TaskDependency] = Field(default_factory=list)
    dependent_tasks: Set[str] = Field(default_factory=set)
    related_contexts: Set[str] = Field(default_factory=set)
    child_contexts: Set[str] = Field(default_factory=set)
    
    # Data and state
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    intermediate_data: Dict[str, Any] = Field(default_factory=dict)
    shared_state: Dict[str, Any] = Field(default_factory=dict)
    private_state: Dict[str, Any] = Field(default_factory=dict)
    environment_context: Dict[str, Any] = Field(default_factory=dict)
    
    # Resource management
    resource_constraints: ResourceConstraints = Field(default_factory=ResourceConstraints)
    allocated_resources: Dict[ResourceType, Any] = Field(default_factory=dict)
    resource_usage: Dict[ResourceType, float] = Field(default_factory=dict)
    
    # Performance and metrics
    metrics: TaskMetrics = Field(default_factory=TaskMetrics)
    performance_history: List[Dict[str, Any]] = Field(default_factory=list)
    benchmarks: Dict[str, float] = Field(default_factory=dict)
    
    # Results and outcomes
    result: Optional[TaskResult] = None
    artifacts: List[str] = Field(default_factory=list)
    generated_files: List[str] = Field(default_factory=list)
    
    # Error handling and recovery
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    recovery_strategy: Optional[str] = None
    
    # Learning and adaptation
    learning_contexts: List[LearningContext] = Field(default_factory=list)
    feedback_data: Dict[str, Any] = Field(default_factory=dict)
    adaptation_history: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_contributions: List[str] = Field(default_factory=list)
    
    # Collaboration and communication
    communication_log: List[Dict[str, Any]] = Field(default_factory=list)
    agent_interactions: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    coordination_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Configuration and preferences
    configuration: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    feature_flags: Dict[str, bool] = Field(default_factory=dict)
    
    # Metadata and tags
    tags: Set[str] = Field(default_factory=set)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit and compliance
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_data: Dict[str, Any] = Field(default_factory=dict)
    security_context: Dict[str, Any] = Field(default_factory=dict)
    
    # Checkpointing and recovery
    checkpoint_data: Optional[bytes] = None
    checkpoint_frequency: float = 60.0  # seconds
    last_checkpoint: Optional[datetime] = None
    snapshots: List[TaskContextSnapshot] = Field(default_factory=list)
    
    # Concurrency and synchronization
    locks: Set[str] = Field(default_factory=set)
    semaphores: Dict[str, int] = Field(default_factory=dict)
    barriers: Set[str] = Field(default_factory=set)
    
    # Event handling
    event_handlers: Dict[str, str] = Field(default_factory=dict)  # event -> handler_id
    event_history: List[Dict[str, Any]] = Field(default_factory=list)
    pending_events: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            set: list,
            UUID: str,
            bytes: lambda v: v.hex() if v else None
        }
        validate_assignment = True
        extra = "forbid"
    
    @root_validator
    def validate_context(cls, values):
        """Comprehensive validation of task context"""
        # Set root context if not provided
        if not values.get('root_context_id'):
            values['root_context_id'] = values.get('parent_context_id') or values.get('context_id')
        
        # Validate temporal constraints
        created_at = values.get('created_at')
        deadline = values.get('deadline')
        if deadline and created_at and deadline <= created_at:
            raise ValueError("Deadline must be after creation time")
        
        # Validate progress consistency
        progress = values.get('progress', 0.0)
        completion_percentage = values.get('completion_percentage', 0.0)
        if abs(progress * 100 - completion_percentage) > 0.1:
            values['completion_percentage'] = progress * 100
        
        return values
    
    @validator('priority')
    def validate_priority(cls, v):
        """Validate task priority"""
        if isinstance(v, int):
            try:
                return TaskPriority(v)
            except ValueError:
                return TaskPriority.MEDIUM
        return v
    
    def update_progress(self, progress: float, details: Optional[str] = None):
        """Update task progress with validation and logging"""
        if not 0.0 <= progress <= 1.0:
            raise ValueError("Progress must be between 0.0 and 1.0")
        
        old_progress = self.progress
        self.progress = progress
        self.completion_percentage = progress * 100
        self.updated_at = datetime.now(timezone.utc)
        
        # Log progress update
        self.audit_trail.append({
            "timestamp": self.updated_at.isoformat(),
            "action": "progress_update",
            "old_value": old_progress,
            "new_value": progress,
            "details": details,
            "agent_id": self.assigned_agent_id
        })
        
        # Auto-complete if progress reaches 100%
        if progress >= 1.0 and self.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.status = TaskStatus.COMPLETED
            self.completed_at = self.updated_at
    
    def update_status(self, status: TaskStatus, reason: Optional[str] = None):
        """Update task status with validation and side effects"""
        old_status = self.status
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        
        # Set timestamps based on status
        if status == TaskStatus.IN_PROGRESS and not self.started_at:
            self.started_at = self.updated_at
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.completed_at = self.updated_at
            if status == TaskStatus.COMPLETED:
                self.progress = 1.0
                self.completion_percentage = 100.0
        
        # Log status change
        self.audit_trail.append({
            "timestamp": self.updated_at.isoformat(),
            "action": "status_change",
            "old_status": old_status.value,
            "new_status": status.value,
            "reason": reason,
            "agent_id": self.assigned_agent_id
        })
    
    def add_error(self, error: str, error_type: str = "general", 
                  details: Optional[Dict[str, Any]] = None, 
                  traceback_info: Optional[str] = None):
        """Add error with comprehensive tracking"""
        error_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "error_type": error_type,
            "details": details or {},
            "traceback": traceback_info or traceback.format_exc(),
            "agent_id": self.assigned_agent_id,
            "context_state": {
                "status": self.status.value,
                "progress": self.progress
            }
        }
        
        self.errors.append(error_entry)
        self.metrics.error_count += 1
        self.updated_at = datetime.now(timezone.utc)
        
        # Auto-fail after max retries
        if len(self.errors) >= self.max_retries and self.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.update_status(TaskStatus.FAILED, f"Max retries ({self.max_retries}) exceeded")
    
    def add_warning(self, warning: str, warning_type: str = "general", 
                   details: Optional[Dict[str, Any]] = None):
        """Add warning with tracking"""
        warning_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warning": warning,
            "warning_type": warning_type,
            "details": details or {},
            "agent_id": self.assigned_agent_id
        }
        
        self.warnings.append(warning_entry)
        self.updated_at = datetime.now(timezone.utc)
    
    def add_learning_context(self, context_type: LearningContextType, 
                           patterns: Dict[str, Any],
                           outcomes: Dict[str, Any],
                           importance: float = 1.0):
        """Add learning context for continuous improvement"""
        learning_context = LearningContext(
            context_type=context_type,
            patterns=patterns,
            outcomes=outcomes,
            importance=importance,
            metadata={
                "task_id": self.task_id,
                "task_type": self.task_type.value,
                "agent_id": self.assigned_agent_id
            }
        )
        
        self.learning_contexts.append(learning_context)
        self.updated_at = datetime.now(timezone.utc)
    
    def log_communication(self, from_agent: str, to_agent: str, 
                         message: str, message_type: str = "general",
                         metadata: Optional[Dict[str, Any]] = None):
        """Log inter-agent communication"""
        comm_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message,
            "message_type": message_type,
            "metadata": metadata or {}
        }
        
        self.communication_log.append(comm_entry)
        
        # Track agent interactions
        if from_agent not in self.agent_interactions:
            self.agent_interactions[from_agent] = []
        self.agent_interactions[from_agent].append(comm_entry)
        
        self.updated_at = datetime.now(timezone.utc)
    
    def create_checkpoint(self) -> TaskContextSnapshot:
        """Create a checkpoint snapshot"""
        checkpoint_data = None
        if self.intermediate_data or self.shared_state:
            checkpoint_data = pickle.dumps({
                'intermediate_data': self.intermediate_data,
                'shared_state': self.shared_state,
                'private_state': self.private_state
            })
        
        snapshot = TaskContextSnapshot(
            context_id=self.context_id,
            status=self.status,
            progress=self.progress,
            metrics=self.metrics.to_dict(),
            state={
                'input_data': self.input_data,
                'environment_context': self.environment_context
            },
            environment=self.environment_context.copy(),
            checkpoint_data=checkpoint_data
        )
        
        self.snapshots.append(snapshot)
        self.last_checkpoint = datetime.now(timezone.utc)
        
        # Keep only recent snapshots (last 10)
        if len(self.snapshots) > 10:
            self.snapshots = self.snapshots[-10:]
        
        return snapshot
    
    def restore_from_checkpoint(self, snapshot: TaskContextSnapshot):
        """Restore context from checkpoint"""
        if snapshot.checkpoint_data:
            try:
                data = pickle.loads(snapshot.checkpoint_data)
                self.intermediate_data = data.get('intermediate_data', {})
                self.shared_state = data.get('shared_state', {})
                self.private_state = data.get('private_state', {})
            except Exception as e:
                self.add_error(f"Checkpoint restoration failed: {str(e)}", "checkpoint_error")
        
        self.status = snapshot.status
        self.progress = snapshot.progress
        self.environment_context.update(snapshot.environment)
        
        self.audit_trail.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "checkpoint_restore",
            "snapshot_id": snapshot.snapshot_id,
            "agent_id": self.assigned_agent_id
        })
    
    def allocate_resource(self, resource_type: ResourceType, resource: Any, 
                         metadata: Optional[Dict[str, Any]] = None):
        """Allocate resource with tracking"""
        self.allocated_resources[resource_type] = resource
        
        self.audit_trail.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "resource_allocation",
            "resource_type": resource_type.value,
            "metadata": metadata or {},
            "agent_id": self.assigned_agent_id
        })
    
    def release_resource(self, resource_type: ResourceType):
        """Release allocated resource"""
        if resource_type in self.allocated_resources:
            del self.allocated_resources[resource_type]
            
            self.audit_trail.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "resource_release",
                "resource_type": resource_type.value,
                "agent_id": self.assigned_agent_id
            })
    
    def update_metrics(self, **metrics):
        """Update performance metrics"""
        for key, value in metrics.items():
            if hasattr(self.metrics, key):
                setattr(self.metrics, key, value)
        
        # Store performance snapshot
        self.performance_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": self.metrics.to_dict()
        })
        
        # Keep only recent history (last 100 entries)
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]
        
        self.updated_at = datetime.now(timezone.utc)
    
    def is_expired(self) -> bool:
        """Check if task has expired based on deadline"""
        if not self.deadline:
            return False
        return datetime.now(timezone.utc) > self.deadline
    
    def is_blocked(self) -> bool:
        """Check if task is blocked by dependencies"""
        return self.status == TaskStatus.BLOCKED or self.status == TaskStatus.WAITING_FOR_DEPENDENCY
    
    def can_execute(self) -> bool:
        """Check if task can be executed (all dependencies met)"""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
        
        if self.is_expired():
            return False
        
        return not self.is_blocked()
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get comprehensive execution summary"""
        duration = None
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            duration = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        
        return {
            "context_id": self.context_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "progress": self.progress,
            "priority": self.priority.value,
            "assigned_agent": self.assigned_agent_id,
            "duration": duration,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metrics": self.metrics.to_dict(),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "learning_contexts": len(self.learning_contexts),
            "dependencies": len(self.dependencies),
            "child_contexts": len(self.child_contexts),
            "artifacts": len(self.artifacts),
            "resource_usage": dict(self.resource_usage)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper serialization"""
        data = self.dict()
        
        # Convert sets to lists for JSON serialization
        for key, value in data.items():
            if isinstance(value, set):
                data[key] = list(value)
            elif isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskContext':
        """Create TaskContext from dictionary"""
        # Convert string enums back to enum types
        if 'task_type' in data and isinstance(data['task_type'], str):
            data['task_type'] = TaskType(data['task_type'])
        
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = TaskStatus(data['status'])
        
        if 'priority' in data and isinstance(data['priority'], (str, int)):
            data['priority'] = TaskPriority(data['priority'])
        
        if 'scope' in data and isinstance(data['scope'], str):
            data['scope'] = ContextScope(data['scope'])
        
        # Convert lists back to sets
        set_fields = ['responsible_agents', 'collaborating_agents', 'dependent_tasks', 
                     'related_contexts', 'child_contexts', 'tags', 'locks', 'barriers']
        
        for field in set_fields:
            if field in data and isinstance(data[field], list):
                data[field] = set(data[field])
        
        # Convert datetime strings back to datetime objects
        datetime_fields = ['created_at', 'started_at', 'updated_at', 'completed_at', 
                          'deadline', 'last_checkpoint']
        
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        
        return cls(**data)


class TaskContextManager:
    """
    Enterprise-grade Task Context Manager
    Handles context lifecycle, persistence, synchronization, and learning integration
    """
    
    def __init__(self, 
                 db_manager=None,
                 cache_manager=None, 
                 message_bus=None,
                 learning_engine=None,
                 logger=None):
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.message_bus = message_bus
        self.learning_engine = learning_engine
        self.logger = logger or logging.getLogger(__name__)
        
        # In-memory context storage with thread-safe access
        self._contexts: Dict[str, TaskContext] = {}
        self._context_locks: Dict[str, asyncio.Lock] = {}
        self._access_lock = asyncio.Lock()
        
        # Context hierarchy tracking
        self._parent_child_map: Dict[str, Set[str]] = defaultdict(set)
        self._child_parent_map: Dict[str, str] = {}
        
        # Performance optimization
        self._context_cache: WeakValueDictionary = WeakValueDictionary()
        self._pending_updates: Dict[str, TaskContext] = {}
        self._update_queue: asyncio.Queue = asyncio.Queue()
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
        # Metrics and monitoring
        self._operation_metrics = {
            'context_created': 0,
            'context_updated': 0,
            'context_deleted': 0,
            'context_retrieved': 0,
            'checkpoint_created': 0,
            'learning_contexts_added': 0
        }
    
    async def initialize(self):
        """Initialize the context manager"""
        self.logger.info("Initializing TaskContextManager...")
        
        # Start background processing tasks
        self._background_tasks.add(
            asyncio.create_task(self._process_update_queue())
        )
        self._background_tasks.add(
            asyncio.create_task(self._periodic_checkpoint_creation())
        )
        self._background_tasks.add(
            asyncio.create_task(self._cleanup_expired_contexts())
        )
        self._background_tasks.add(
            asyncio.create_task(self._metrics_collection())
        )
        
        # Load existing contexts from database if available
        if self.db_manager:
            await self._load_contexts_from_db()
        
        self.logger.info("TaskContextManager initialized successfully")
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down TaskContextManager...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for background tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Save pending contexts
        await self._flush_pending_updates()
        
        self.logger.info("TaskContextManager shutdown complete")
    
    async def create_context(self, 
                           task_type: TaskType,
                           task_name: str,
                           description: str = "",
                           priority: TaskPriority = TaskPriority.MEDIUM,
                           parent_context_id: Optional[str] = None,
                           assigned_agent_id: Optional[str] = None,
                           **kwargs) -> TaskContext:
        """Create a new task context with full initialization"""
        
        context = TaskContext(
            task_type=task_type,
            task_name=task_name,
            description=description,
            priority=priority,
            parent_context_id=parent_context_id,
            assigned_agent_id=assigned_agent_id,
            **kwargs
        )
        
        # Set root context
        if parent_context_id:
            parent_context = await self.get_context(parent_context_id)
            if parent_context:
                context.root_context_id = parent_context.root_context_id
                # Add to parent's children
                parent_context.child_contexts.add(context.context_id)
                await self.update_context(parent_context)
                # Track hierarchy
                self._parent_child_map[parent_context_id].add(context.context_id)
                self._child_parent_map[context.context_id] = parent_context_id
        else:
            context.root_context_id = context.context_id
        
        # Store context
        async with self._access_lock:
            self._contexts[context.context_id] = context
            self._context_locks[context.context_id] = asyncio.Lock()
        
        # Cache context
        if self.cache_manager:
            await self.cache_manager.set(
                f"context:{context.context_id}",
                context.json(),
                ttl=3600  # 1 hour
            )
        
        # Queue for database persistence
        self._pending_updates[context.context_id] = context
        await self._update_queue.put(context.context_id)
        
        # Publish creation event
        if self.message_bus:
            await self.message_bus.publish(
                "task.context.created",
                {
                    "context_id": context.context_id,
                    "task_type": context.task_type.value,
                    "priority": context.priority.value,
                    "agent_id": assigned_agent_id
                }
            )
        
        # Add to learning engine
        if self.learning_engine:
            await self.learning_engine.record_context_creation(context)
        
        self._operation_metrics['context_created'] += 1
        self.logger.info(f"Created task context: {context.context_id}")
        
        return context
    
    async def get_context(self, context_id: str) -> Optional[TaskContext]:
        """Retrieve task context with caching and lazy loading"""
        
        # Check in-memory first
        if context_id in self._contexts:
            self._operation_metrics['context_retrieved'] += 1
            return self._contexts[context_id]
        
        # Check cache
        if self.cache_manager:
            cached_data = await self.cache_manager.get(f"context:{context_id}")
            if cached_data:
                try:
                    context_dict = json.loads(cached_data)
                    context = TaskContext.from_dict(context_dict)
                    
                    async with self._access_lock:
                        self._contexts[context_id] = context
                        if context_id not in self._context_locks:
                            self._context_locks[context_id] = asyncio.Lock()
                    
                    self._operation_metrics['context_retrieved'] += 1
                    return context
                except Exception as e:
                    self.logger.error(f"Error deserializing cached context {context_id}: {e}")
        
        # Load from database
        if self.db_manager:
            try:
                context = await self._load_context_from_db(context_id)
                if context:
                    async with self._access_lock:
                        self._contexts[context_id] = context
                        if context_id not in self._context_locks:
                            self._context_locks[context_id] = asyncio.Lock()
                    
                    self._operation_metrics['context_retrieved'] += 1
                    return context
            except Exception as e:
                self.logger.error(f"Error loading context {context_id} from database: {e}")
        
        return None
    
    async def update_context(self, context: TaskContext):
        """Update task context with optimistic locking"""
        
        context_id = context.context_id
        
        # Get context lock
        if context_id not in self._context_locks:
            async with self._access_lock:
                if context_id not in self._context_locks:
                    self._context_locks[context_id] = asyncio.Lock()
        
        async with self._context_locks[context_id]:
            # Update in-memory
            self._contexts[context_id] = context
            context.updated_at = datetime.now(timezone.utc)
            
            # Queue for persistence
            self._pending_updates[context_id] = context
            await self._update_queue.put(context_id)
            
            # Update cache
            if self.cache_manager:
                await self.cache_manager.set(
                    f"context:{context_id}",
                    context.json(),
                    ttl=3600
                )
            
            # Publish update event
            if self.message_bus:
                await self.message_bus.publish(
                    "task.context.updated",
                    {
                        "context_id": context_id,
                        "status": context.status.value,
                        "progress": context.progress,
                        "agent_id": context.assigned_agent_id
                    }
                )
            
            # Send to learning engine
            if self.learning_engine:
                await self.learning_engine.record_context_update(context)
        
        self._operation_metrics['context_updated'] += 1
    
    async def delete_context(self, context_id: str, cascade: bool = True):
        """Delete task context with optional cascade to children"""
        
        context = await self.get_context(context_id)
        if not context:
            return
        
        # Handle children
        if cascade and context.child_contexts:
            for child_id in context.child_contexts.copy():
                await self.delete_context(child_id, cascade=True)
        
        # Remove from parent
        if context.parent_context_id:
            parent = await self.get_context(context.parent_context_id)
            if parent and context_id in parent.child_contexts:
                parent.child_contexts.remove(context_id)
                await self.update_context(parent)
        
        # Remove from memory and locks
        async with self._access_lock:
            self._contexts.pop(context_id, None)
            self._context_locks.pop(context_id, None)
        
        # Remove from cache
        if self.cache_manager:
            await self.cache_manager.delete(f"context:{context_id}")
        
        # Remove from database
        if self.db_manager:
            await self._delete_context_from_db(context_id)
        
        # Clean up hierarchy tracking
        if context_id in self._child_parent_map:
            parent_id = self._child_parent_map.pop(context_id)
            if parent_id in self._parent_child_map:
                self._parent_child_map[parent_id].discard(context_id)
        
        if context_id in self._parent_child_map:
            del self._parent_child_map[context_id]
        
        # Remove from pending updates
        self._pending_updates.pop(context_id, None)
        
        # Publish deletion event
        if self.message_bus:
            await self.message_bus.publish(
                "task.context.deleted",
                {
                    "context_id": context_id,
                    "cascade": cascade
                }
            )
        
        self._operation_metrics['context_deleted'] += 1
        self.logger.info(f"Deleted task context: {context_id}")
    
    async def get_contexts_by_agent(self, agent_id: str) -> List[TaskContext]:
        """Get all contexts assigned to a specific agent"""
        contexts = []
        
        for context in self._contexts.values():
            if (context.assigned_agent_id == agent_id or
                agent_id in context.responsible_agents or
                agent_id in context.collaborating_agents):
                contexts.append(context)
        
        return contexts
    
    async def get_contexts_by_status(self, status: TaskStatus) -> List[TaskContext]:
        """Get all contexts with specific status"""
        return [ctx for ctx in self._contexts.values() if ctx.status == status]
    
    async def get_contexts_by_type(self, task_type: TaskType) -> List[TaskContext]:
        """Get all contexts of specific type"""
        return [ctx for ctx in self._contexts.values() if ctx.task_type == task_type]
    
    async def get_contexts_by_priority(self, priority: TaskPriority) -> List[TaskContext]:
        """Get all contexts with specific priority"""
        return [ctx for ctx in self._contexts.values() if ctx.priority == priority]
    
    async def get_workflow_contexts(self, workflow_id: str) -> List[TaskContext]:
        """Get all contexts belonging to a workflow"""
        return [ctx for ctx in self._contexts.values() if ctx.workflow_id == workflow_id]
    
    async def get_child_contexts(self, parent_context_id: str) -> List[TaskContext]:
        """Get all child contexts of a parent"""
        child_ids = self._parent_child_map.get(parent_context_id, set())
        contexts = []
        
        for child_id in child_ids:
            context = await self.get_context(child_id)
            if context:
                contexts.append(context)
        
        return contexts
    
    async def get_context_hierarchy(self, root_context_id: str) -> Dict[str, Any]:
        """Get complete context hierarchy as tree structure"""
        
        async def build_tree(context_id: str) -> Dict[str, Any]:
            context = await self.get_context(context_id)
            if not context:
                return None
            
            tree = {
                "context": context.get_execution_summary(),
                "children": []
            }
            
            child_ids = self._parent_child_map.get(context_id, set())
            for child_id in child_ids:
                child_tree = await build_tree(child_id)
                if child_tree:
                    tree["children"].append(child_tree)
            
            return tree
        
        return await build_tree(root_context_id)
    
    async def create_checkpoint(self, context_id: str) -> Optional[TaskContextSnapshot]:
        """Create checkpoint for specific context"""
        context = await self.get_context(context_id)
        if not context:
            return None
        
        async with self._context_locks[context_id]:
            snapshot = context.create_checkpoint()
            await self.update_context(context)
            
            # Store snapshot separately if needed
            if self.db_manager:
                await self._save_snapshot_to_db(snapshot)
            
            self._operation_metrics['checkpoint_created'] += 1
            return snapshot
    
    async def restore_context(self, context_id: str, 
                            snapshot_id: Optional[str] = None) -> bool:
        """Restore context from checkpoint"""
        context = await self.get_context(context_id)
        if not context:
            return False
        
        # Find snapshot
        snapshot = None
        if snapshot_id:
            snapshot = next(
                (s for s in context.snapshots if s.snapshot_id == snapshot_id),
                None
            )
        else:
            # Use latest snapshot
            snapshot = context.snapshots[-1] if context.snapshots else None
        
        if not snapshot:
            return False
        
        async with self._context_locks[context_id]:
            context.restore_from_checkpoint(snapshot)
            await self.update_context(context)
            return True
    
    async def get_learning_data(self, context_id: str) -> List[LearningContext]:
        """Extract learning data from context"""
        context = await self.get_context(context_id)
        if not context:
            return []
        
        return context.learning_contexts
    
    async def add_learning_context(self, context_id: str, 
                                 learning_context: LearningContext):
        """Add learning context to task context"""
        context = await self.get_context(context_id)
        if not context:
            return
        
        async with self._context_locks[context_id]:
            context.learning_contexts.append(learning_context)
            await self.update_context(context)
            
            # Send to learning engine
            if self.learning_engine:
                await self.learning_engine.process_learning_context(
                    context, learning_context
                )
        
        self._operation_metrics['learning_contexts_added'] += 1
    
    async def get_performance_analytics(self, 
                                      time_range: Optional[Tuple[datetime, datetime]] = None,
                                      agent_id: Optional[str] = None,
                                      task_type: Optional[TaskType] = None) -> Dict[str, Any]:
        """Get comprehensive performance analytics"""
        
        contexts = list(self._contexts.values())
        
        # Apply filters
        if time_range:
            start_time, end_time = time_range
            contexts = [
                ctx for ctx in contexts
                if start_time <= ctx.created_at <= end_time
            ]
        
        if agent_id:
            contexts = [
                ctx for ctx in contexts
                if ctx.assigned_agent_id == agent_id
            ]
        
        if task_type:
            contexts = [
                ctx for ctx in contexts
                if ctx.task_type == task_type
            ]
        
        # Calculate analytics
        total_contexts = len(contexts)
        if total_contexts == 0:
            return {"total_contexts": 0}
        
        # Status distribution
        status_counts = defaultdict(int)
        for ctx in contexts:
            status_counts[ctx.status.value] += 1
        
        # Performance metrics
        execution_times = []
        error_counts = []
        retry_counts = []
        quality_scores = []
        
        for ctx in contexts:
            if ctx.started_at and ctx.completed_at:
                execution_times.append(
                    (ctx.completed_at - ctx.started_at).total_seconds()
                )
            error_counts.append(len(ctx.errors))
            retry_counts.append(ctx.retry_count)
            if ctx.metrics.quality_score > 0:
                quality_scores.append(ctx.metrics.quality_score)
        
        analytics = {
            "total_contexts": total_contexts,
            "status_distribution": dict(status_counts),
            "performance": {
                "avg_execution_time": sum(execution_times) / len(execution_times) if execution_times else 0,
                "min_execution_time": min(execution_times) if execution_times else 0,
                "max_execution_time": max(execution_times) if execution_times else 0,
                "avg_error_count": sum(error_counts) / total_contexts,
                "avg_retry_count": sum(retry_counts) / total_contexts,
                "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0
            },
            "completion_rate": status_counts.get('completed', 0) / total_contexts,
            "failure_rate": status_counts.get('failed', 0) / total_contexts,
            "active_contexts": sum(1 for ctx in contexts if ctx.status in [
                TaskStatus.IN_PROGRESS, TaskStatus.QUEUED, TaskStatus.ASSIGNED
            ]),
            "learning_contexts_total": sum(len(ctx.learning_contexts) for ctx in contexts)
        }
        
        return analytics
    
    def get_current_context(self) -> Optional[TaskContext]:
        """Get current task context from context variable"""
        return current_task_context.get()
    
    def set_current_context(self, context: TaskContext):
        """Set current task context"""
        current_task_context.set(context)
    
    async def _process_update_queue(self):
        """Background task to process context updates"""
        while not self._shutdown_event.is_set():
            try:
                # Wait for update or timeout
                context_id = await asyncio.wait_for(
                    self._update_queue.get(),
                    timeout=1.0
                )
                
                if context_id in self._pending_updates:
                    context = self._pending_updates.pop(context_id)
                    
                    # Save to database
                    if self.db_manager:
                        await self._save_context_to_db(context)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing update queue: {e}")
    
    async def _periodic_checkpoint_creation(self):
        """Background task for periodic checkpointing"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = datetime.now(timezone.utc)
                
                for context in self._contexts.values():
                    # Skip if already completed
                    if context.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        continue
                    
                    # Check if checkpoint is needed
                    should_checkpoint = False
                    
                    if not context.last_checkpoint:
                        should_checkpoint = True
                    else:
                        time_since_checkpoint = (now - context.last_checkpoint).total_seconds()
                        if time_since_checkpoint >= context.checkpoint_frequency:
                            should_checkpoint = True
                    
                    if should_checkpoint:
                        await self.create_checkpoint(context.context_id)
                
            except Exception as e:
                self.logger.error(f"Error in periodic checkpoint creation: {e}")
    
    async def _cleanup_expired_contexts(self):
        """Background task to cleanup expired contexts"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                expired_contexts = []
                for context in self._contexts.values():
                    if context.is_expired() and context.status not in [
                        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
                    ]:
                        expired_contexts.append(context)
                
                for context in expired_contexts:
                    context.update_status(TaskStatus.TIMEOUT, "Task deadline exceeded")
                    await self.update_context(context)
                    
                    self.logger.warning(f"Context {context.context_id} expired and marked as timeout")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup expired contexts: {e}")
    
    async def _metrics_collection(self):
        """Background task for metrics collection"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # Collect every 30 seconds
                
                # Collect current metrics
                metrics = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_contexts": len(self._contexts),
                    "active_contexts": len([
                        ctx for ctx in self._contexts.values()
                        if ctx.status in [TaskStatus.IN_PROGRESS, TaskStatus.QUEUED]
                    ]),
                    "operations": self._operation_metrics.copy()
                }
                
                # Send to monitoring system
                if self.message_bus:
                    await self.message_bus.publish("task.context.metrics", metrics)
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
    
    async def _flush_pending_updates(self):
        """Flush all pending updates to database"""
        if not self.db_manager or not self._pending_updates:
            return
        
        try:
            contexts_to_save = list(self._pending_updates.values())
            self._pending_updates.clear()
            
            for context in contexts_to_save:
                await self._save_context_to_db(context)
            
            self.logger.info(f"Flushed {len(contexts_to_save)} pending context updates")
            
        except Exception as e:
            self.logger.error(f"Error flushing pending updates: {e}")
    
    async def _load_contexts_from_db(self):
        """Load existing contexts from database"""
        # This would be implemented based on your specific database schema
        # For now, this is a placeholder for the database integration
        pass
    
    async def _load_context_from_db(self, context_id: str) -> Optional[TaskContext]:
        """Load specific context from database"""
        # This would be implemented based on your specific database schema
        # For now, this is a placeholder for the database integration
        return None
    
    async def _save_context_to_db(self, context: TaskContext):
        """Save context to database"""
        # This would be implemented based on your specific database schema
        # For now, this is a placeholder for the database integration
        pass
    
    async def _delete_context_from_db(self, context_id: str):
        """Delete context from database"""
        # This would be implemented based on your specific database schema
        # For now, this is a placeholder for the database integration
        pass
    
    async def _save_snapshot_to_db(self, snapshot: TaskContextSnapshot):
        """Save snapshot to database"""
        # This would be implemented based on your specific database schema
        # For now, this is a placeholder for the database integration
        pass


# SQLAlchemy Models for Database Persistence
class TaskContextModel(Base):
    """SQLAlchemy model for task context persistence"""
    __tablename__ = "task_contexts"
    
    context_id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False, index=True)
    workflow_id = Column(String, index=True)
    parent_context_id = Column(String, ForeignKey("task_contexts.context_id"))
    root_context_id = Column(String, index=True)
    
    task_type = Column(String, nullable=False)
    task_name = Column(String, nullable=False)
    description = Column(Text)
    priority = Column(Integer, default=3)
    scope = Column(String, default="task")
    
    status = Column(String, nullable=False, default="created")
    progress = Column(Float, default=0.0)
    completion_percentage = Column(Float, default=0.0)
    
    assigned_agent_id = Column(String)
    requesting_agent_id = Column(String)
    responsible_agents = Column(JSONB)
    collaborating_agents = Column(JSONB)
    
    created_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    deadline = Column(DateTime(timezone=True))
    estimated_duration = Column(Float)
    
    dependencies = Column(JSONB)
    dependent_tasks = Column(JSONB)
    related_contexts = Column(JSONB)
    child_contexts = Column(JSONB)
    
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    intermediate_data = Column(JSONB)
    shared_state = Column(JSONB)
    private_state = Column(JSONB)
    environment_context = Column(JSONB)
    
    resource_constraints = Column(JSONB)
    allocated_resources = Column(JSONB)
    resource_usage = Column(JSONB)
    
    metrics = Column(JSONB)
    performance_history = Column(JSONB)
    benchmarks = Column(JSONB)
    
    result = Column(JSONB)
    artifacts = Column(JSONB)
    generated_files = Column(JSONB)
    
    errors = Column(JSONB)
    warnings = Column(JSONB)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    recovery_strategy = Column(String)
    
    learning_contexts = Column(JSONB)
    feedback_data = Column(JSONB)
    adaptation_history = Column(JSONB)
    knowledge_contributions = Column(JSONB)
    
    communication_log = Column(JSONB)
    agent_interactions = Column(JSONB)
    coordination_data = Column(JSONB)
    
    configuration = Column(JSONB)
    preferences = Column(JSONB)
    feature_flags = Column(JSONB)
    
    tags = Column(JSONB)
    labels = Column(JSONB)
    annotations = Column(JSONB)
    custom_attributes = Column(JSONB)
    
    audit_trail = Column(JSONB)
    compliance_data = Column(JSONB)
    security_context = Column(JSONB)
    
    checkpoint_data = Column(Text)  # Base64 encoded
    checkpoint_frequency = Column(Float, default=60.0)
    last_checkpoint = Column(DateTime(timezone=True))
    
    locks = Column(JSONB)
    semaphores = Column(JSONB)
    barriers = Column(JSONB)
    
    event_handlers = Column(JSONB)
    event_history = Column(JSONB)
    pending_events = Column(JSONB)
    
    # Relationships
    children = relationship("TaskContextModel", backref="parent", remote_side=[context_id])


class TaskContextSnapshotModel(Base):
    """SQLAlchemy model for task context snapshots"""
    __tablename__ = "task_context_snapshots"
    
    snapshot_id = Column(String, primary_key=True)
    context_id = Column(String, ForeignKey("task_contexts.context_id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    progress = Column(Float, nullable=False)
    metrics = Column(JSONB)
    state = Column(JSONB)
    environment = Column(JSONB)
    checkpoint_data = Column(Text)  # Base64 encoded


# Context decorators and utilities
class TaskContextDecorator:
    """Decorator for automatic task context management"""
    
    def __init__(self, 
                 task_type: TaskType,
                 task_name: Optional[str] = None,
                 priority: TaskPriority = TaskPriority.MEDIUM,
                 auto_checkpoint: bool = True,
                 context_manager: Optional[TaskContextManager] = None):
        self.task_type = task_type
        self.task_name = task_name
        self.priority = priority
        self.auto_checkpoint = auto_checkpoint
        self.context_manager = context_manager
    
    def __call__(self, func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            return self._async_wrapper(func)
        else:
            return self._sync_wrapper(func)
    
    def _async_wrapper(self, func: AsyncCallable) -> AsyncCallable:
        async def wrapper(*args, **kwargs):
            if not self.context_manager:
                return await func(*args, **kwargs)
            
            task_name = self.task_name or func.__name__
            
            # Create task context
            context = await self.context_manager.create_context(
                task_type=self.task_type,
                task_name=task # Create task context
            context = await self.context_manager.create_context(
                task_type=self.task_type,
                task_name=task_name,
                priority=self.priority,
                description=f"Auto-generated context for {func.__name__}"
            )
            
            # Set current context
            token = current_task_context.set(context)
            
            try:
                # Update status to in progress
                context.update_status(TaskStatus.IN_PROGRESS)
                await self.context_manager.update_context(context)
                
                # Create checkpoint if enabled
                if self.auto_checkpoint:
                    await self.context_manager.create_checkpoint(context.context_id)
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Update context with result
                context.set_result(result)
                context.update_status(TaskStatus.COMPLETED)
                await self.context_manager.update_context(context)
                
                return result
                
            except Exception as e:
                # Handle errors
                context.add_error(str(e), traceback.format_exc())
                context.update_status(TaskStatus.FAILED)
                await self.context_manager.update_context(context)
                raise
                
            finally:
                # Reset context
                current_task_context.reset(token)
        
        return wrapper
    
    def _sync_wrapper(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            if not self.context_manager:
                return func(*args, **kwargs)
            
            # For sync functions, we need to handle async context manager
            # This is a simplified version - in production you might want to use asyncio.run
            # or integrate with an existing event loop
            return func(*args, **kwargs)
        
        return wrapper


# Task context decorators
def task_context(task_type: TaskType, 
                task_name: Optional[str] = None,
                priority: TaskPriority = TaskPriority.MEDIUM,
                auto_checkpoint: bool = True):
    """Decorator for automatic task context management"""
    return TaskContextDecorator(
        task_type=task_type,
        task_name=task_name,
        priority=priority,
        auto_checkpoint=auto_checkpoint
    )


def with_context_manager(context_manager: TaskContextManager):
    """Decorator to set context manager for a function"""
    def decorator(func: Callable) -> Callable:
        if hasattr(func, '_context_manager'):
            func._context_manager = context_manager
        return func
    return decorator


# Context utilities
class ContextUtils:
    """Utility functions for task context management"""
    
    @staticmethod
    def get_current_context() -> Optional[TaskContext]:
        """Get current task context"""
        return current_task_context.get()
    
    @staticmethod
    def get_context_chain() -> List[TaskContext]:
        """Get chain of parent contexts"""
        chain = []
        current = current_task_context.get()
        
        while current:
            chain.append(current)
            # This would need to be implemented with context manager
            current = None  # Placeholder for parent lookup
        
        return chain
    
    @staticmethod
    def create_context_id() -> str:
        """Generate unique context ID"""
        return f"ctx_{uuid4().hex[:12]}"
    
    @staticmethod
    def calculate_context_hash(context: TaskContext) -> str:
        """Calculate hash for context state"""
        state_data = {
            'task_type': context.task_type.value,
            'status': context.status.value,
            'input_data': context.input_data,
            'configuration': context.configuration
        }
        
        state_str = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]


# Context middleware
class TaskContextMiddleware:
    """Middleware for automatic context management in web frameworks"""
    
    def __init__(self, context_manager: TaskContextManager):
        self.context_manager = context_manager
    
    async def __call__(self, request, call_next):
        """ASGI middleware implementation"""
        # Extract task info from request
        task_type = getattr(request, 'task_type', TaskType.ANALYSIS)
        task_name = getattr(request, 'task_name', f"Request_{request.url.path}")
        
        # Create context
        context = await self.context_manager.create_context(
            task_type=task_type,
            task_name=task_name,
            description=f"HTTP request context for {request.method} {request.url.path}"
        )
        
        # Set current context
        token = current_task_context.set(context)
        
        try:
            context.update_status(TaskStatus.IN_PROGRESS)
            await self.context_manager.update_context(context)
            
            response = await call_next(request)
            
            context.update_status(TaskStatus.COMPLETED)
            await self.context_manager.update_context(context)
            
            return response
            
        except Exception as e:
            context.add_error(str(e), traceback.format_exc())
            context.update_status(TaskStatus.FAILED)
            await self.context_manager.update_context(context)
            raise
            
        finally:
            current_task_context.reset(token)


# Database session management
class DatabaseManager:
    """Database session and transaction management for task contexts"""
    
    def __init__(self, engine, session_factory):
        self.engine = engine
        self.session_factory = session_factory
    
    async def save_context(self, context: TaskContext):
        """Save task context to database"""
        async with self.session_factory() as session:
            try:
                # Convert TaskContext to TaskContextModel
                model = self._context_to_model(context)
                session.merge(model)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
    
    async def load_context(self, context_id: str) -> Optional[TaskContext]:
        """Load task context from database"""
        async with self.session_factory() as session:
            model = await session.get(TaskContextModel, context_id)
            if model:
                return self._model_to_context(model)
            return None
    
    async def delete_context(self, context_id: str):
        """Delete task context from database"""
        async with self.session_factory() as session:
            model = await session.get(TaskContextModel, context_id)
            if model:
                await session.delete(model)
                await session.commit()
    
    def _context_to_model(self, context: TaskContext) -> TaskContextModel:
        """Convert TaskContext to SQLAlchemy model"""
        return TaskContextModel(
            context_id=context.context_id,
            task_id=context.task_id,
            workflow_id=context.workflow_id,
            parent_context_id=context.parent_context_id,
            root_context_id=context.root_context_id,
            task_type=context.task_type.value,
            task_name=context.task_name,
            description=context.description,
            priority=context.priority.value,
            scope=context.scope,
            status=context.status.value,
            progress=context.progress,
            completion_percentage=context.completion_percentage,
            assigned_agent_id=context.assigned_agent_id,
            requesting_agent_id=context.requesting_agent_id,
            responsible_agents=list(context.responsible_agents),
            collaborating_agents=list(context.collaborating_agents),
            created_at=context.created_at,
            started_at=context.started_at,
            updated_at=context.updated_at,
            completed_at=context.completed_at,
            deadline=context.deadline,
            estimated_duration=context.estimated_duration,
            dependencies=list(context.dependencies),
            dependent_tasks=list(context.dependent_tasks),
            related_contexts=list(context.related_contexts),
            child_contexts=list(context.child_contexts),
            input_data=context.input_data,
            output_data=context.output_data,
            intermediate_data=context.intermediate_data,
            shared_state=context.shared_state,
            private_state=context.private_state,
            environment_context=context.environment_context,
            resource_constraints=context.resource_constraints,
            allocated_resources=context.allocated_resources,
            resource_usage=context.resource_usage,
            metrics=asdict(context.metrics),
            performance_history=context.performance_history,
            benchmarks=context.benchmarks,
            result=context.result,
            artifacts=context.artifacts,
            generated_files=context.generated_files,
            errors=[asdict(error) for error in context.errors],
            warnings=context.warnings,
            retry_count=context.retry_count,
            max_retries=context.max_retries,
            recovery_strategy=context.recovery_strategy,
            learning_contexts=[asdict(lc) for lc in context.learning_contexts],
            feedback_data=context.feedback_data,
            adaptation_history=context.adaptation_history,
            knowledge_contributions=context.knowledge_contributions,
            communication_log=context.communication_log,
            agent_interactions=context.agent_interactions,
            coordination_data=context.coordination_data,
            configuration=context.configuration,
            preferences=context.preferences,
            feature_flags=context.feature_flags,
            tags=list(context.tags),
            labels=context.labels,
            annotations=context.annotations,
            custom_attributes=context.custom_attributes,
            audit_trail=context.audit_trail,
            compliance_data=context.compliance_data,
            security_context=context.security_context,
            checkpoint_data=context._checkpoint_data,
            checkpoint_frequency=context.checkpoint_frequency,
            last_checkpoint=context.last_checkpoint,
            locks=context._locks,
            semaphores=context._semaphores,
            barriers=context._barriers,
            event_handlers=context._event_handlers,
            event_history=context._event_history,
            pending_events=list(context._pending_events)
        )
    
    def _model_to_context(self, model: TaskContextModel) -> TaskContext:
        """Convert SQLAlchemy model to TaskContext"""
        # This would need to reconstruct the TaskContext from the model
        # Implementation depends on the TaskContext constructor
        context = TaskContext(
            task_type=TaskType(model.task_type),
            task_name=model.task_name,
            description=model.description,
            priority=TaskPriority(model.priority),
            parent_context_id=model.parent_context_id,
            assigned_agent_id=model.assigned_agent_id
        )
        
        # Restore all fields
        context.context_id = model.context_id
        context.task_id = model.task_id
        context.workflow_id = model.workflow_id
        context.root_context_id = model.root_context_id
        context.scope = model.scope
        context.status = TaskStatus(model.status)
        context.progress = model.progress
        context.completion_percentage = model.completion_percentage
        # ... (continue with all other fields)
        
        return context


# Export all public components
__all__ = [
    # Core classes
    'TaskContext', 'TaskContextManager', 'TaskContextSnapshot',
    'TaskMetrics', 'TaskError', 'LearningContext',
    
    # Enums
    'TaskStatus', 'TaskType', 'TaskPriority',
    
    # Database models
    'TaskContextModel', 'TaskContextSnapshotModel',
    
    # Decorators and utilities
    'TaskContextDecorator', 'task_context', 'with_context_manager',
    'ContextUtils', 'TaskContextMiddleware', 'DatabaseManager',
    
    # Context variable
    'current_task_context',
    
    # Type aliases
    'ContextID', 'AgentID', 'TaskID', 'WorkflowID'
]


# Configuration and factory functions
class TaskContextConfig:
    """Configuration for task context management"""
    
    def __init__(self,
                 enable_caching: bool = True,
                 enable_persistence: bool = True,
                 enable_learning: bool = True,
                 enable_metrics: bool = True,
                 checkpoint_frequency: float = 300.0,
                 max_context_age: float = 86400.0,
                 max_snapshots_per_context: int = 10,
                 database_url: Optional[str] = None,
                 redis_url: Optional[str] = None):
        
        self.enable_caching = enable_caching
        self.enable_persistence = enable_persistence
        self.enable_learning = enable_learning
        self.enable_metrics = enable_metrics
        self.checkpoint_frequency = checkpoint_frequency
        self.max_context_age = max_context_age
        self.max_snapshots_per_context = max_snapshots_per_context
        self.database_url = database_url
        self.redis_url = redis_url


async def create_context_manager(config: TaskContextConfig) -> TaskContextManager:
    """Factory function to create configured task context manager"""
    
    # Initialize components based on configuration
    cache_manager = None
    if config.enable_caching and config.redis_url:
        # Initialize Redis cache manager
        pass
    
    db_manager = None
    if config.enable_persistence and config.database_url:
        # Initialize database manager
        pass
    
    learning_engine = None
    if config.enable_learning:
        # Initialize learning engine
        pass
    
    message_bus = None
    # Initialize message bus if needed
    
    # Create and initialize context manager
    context_manager = TaskContextManager(
        cache_manager=cache_manager,
        db_manager=db_manager,
        learning_engine=learning_engine,
        message_bus=message_bus
    )
    
    await context_manager.initialize()
    
    return context_manager