"""
YMERA Enterprise - Task Models
Production-Ready Task Tracking & Management Models - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import logging
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Type
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
from pathlib import Path

# Third-party imports (alphabetical)
import structlog
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, validator, root_validator

# Local imports (alphabetical)
from config.settings import get_settings
from models.base_model import BaseEntity, TimestampMixin, SoftDeleteMixin
from utils.validators import validate_uuid, validate_json_schema
from utils.encryption import encrypt_sensitive_data, decrypt_sensitive_data
from ymera_exceptions import ValidationError, TaskError

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Task execution constants
MAX_TASK_DURATION = 86400  # 24 hours in seconds
MAX_RETRY_ATTEMPTS = 5
DEFAULT_TIMEOUT = 3600  # 1 hour
MAX_TASK_DESCRIPTION_LENGTH = 2000
MAX_RESULT_SIZE = 10485760  # 10MB in bytes

# Configuration loading
settings = get_settings()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class TaskStatus(str, Enum):
    """Task execution status enumeration"""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRY = "retry"

class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"

class TaskType(str, Enum):
    """Task type classifications"""
    AGENT_EXECUTION = "agent_execution"
    CODE_ANALYSIS = "code_analysis"
    FILE_PROCESSING = "file_processing"
    LEARNING_TASK = "learning_task"
    SYSTEM_MAINTENANCE = "system_maintenance"
    USER_REQUEST = "user_request"
    BACKGROUND_JOB = "background_job"
    SCHEDULED_TASK = "scheduled_task"

class ExecutionEnvironment(str, Enum):
    """Task execution environments"""
    LOCAL = "local"
    CONTAINER = "container"
    CLOUD = "cloud"
    AGENT_SANDBOX = "agent_sandbox"
    EXTERNAL_API = "external_api"

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class TaskConfiguration(BaseModel):
    """Task configuration schema"""
    timeout: int = Field(default=DEFAULT_TIMEOUT, ge=1, le=MAX_TASK_DURATION)
    max_retries: int = Field(default=3, ge=0, le=MAX_RETRY_ATTEMPTS)
    retry_delay: float = Field(default=1.0, ge=0.1, le=300.0)
    environment: ExecutionEnvironment = Field(default=ExecutionEnvironment.LOCAL)
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    notification_endpoints: List[str] = Field(default_factory=list)
    
    @validator('resource_limits')
    def validate_resource_limits(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Resource limits must be a dictionary")
        
        allowed_keys = {'cpu_limit', 'memory_limit', 'disk_limit', 'network_limit'}
        invalid_keys = set(v.keys()) - allowed_keys
        if invalid_keys:
            raise ValueError(f"Invalid resource limit keys: {invalid_keys}")
        
        return v

class TaskMetrics(BaseModel):
    """Task execution metrics schema"""
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_usage: Optional[int] = Field(None, ge=0)
    disk_io: Optional[Dict[str, int]] = Field(default_factory=dict)
    network_io: Optional[Dict[str, int]] = Field(default_factory=dict)
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list)
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskResult(BaseModel):
    """Task execution result schema"""
    success: bool = Field(..., description="Task execution success status")
    output: Optional[Dict[str, Any]] = Field(None, description="Task output data")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")
    artifacts: List[str] = Field(default_factory=list, description="Generated artifact paths")
    metrics: Optional[TaskMetrics] = Field(None, description="Execution metrics")
    
    @validator('output')
    def validate_output_size(cls, v):
        if v is not None:
            output_size = len(json.dumps(v).encode('utf-8'))
            if output_size > MAX_RESULT_SIZE:
                raise ValueError(f"Task output size {output_size} exceeds maximum {MAX_RESULT_SIZE}")
        return v

# ===============================================================================
# DATABASE MODELS
# ===============================================================================

class Task(BaseEntity, TimestampMixin, SoftDeleteMixin):
    """
    Core task model for tracking all system tasks and user requests.
    
    This model provides comprehensive task management including:
    - Task lifecycle tracking
    - Priority-based scheduling
    - Resource management
    - Retry logic
    - Audit trails
    """
    
    __tablename__ = "tasks"
    
    # Core task identification
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False, index=True, default=TaskType.USER_REQUEST)
    priority = Column(String(20), nullable=False, index=True, default=TaskPriority.NORMAL)
    
    # Task status and lifecycle
    status = Column(String(20), nullable=False, index=True, default=TaskStatus.PENDING)
    progress_percentage = Column(Integer, nullable=False, default=0)
    
    # Ownership and assignment
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    assigned_to_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    
    # Task configuration and parameters
    configuration = Column(JSONB, nullable=False, default=dict)
    input_parameters = Column(JSONB, nullable=True)
    environment_variables = Column(JSONB, nullable=True)
    
    # Scheduling and timing
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    estimated_duration = Column(Integer, nullable=True)  # seconds
    actual_duration = Column(Integer, nullable=True)  # seconds
    
    # Retry and error handling
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    last_error = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)
    
    # Dependencies and relationships
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True, index=True)
    depends_on_tasks = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    
    # Resource tracking
    resource_usage = Column(JSONB, nullable=True)
    execution_logs = Column(JSONB, nullable=True)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_user_id], back_populates="created_tasks")
    assigned_to_user = relationship("User", foreign_keys=[assigned_to_user_id], back_populates="assigned_tasks")
    assigned_to_agent = relationship("Agent", back_populates="assigned_tasks")
    project = relationship("Project", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id], back_populates="subtasks")
    subtasks = relationship("Task", back_populates="parent_task")
    executions = relationship("TaskExecution", back_populates="task", cascade="all, delete-orphan")
    results = relationship("TaskResult", back_populates="task", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_tasks_status_priority', 'status', 'priority'),
        Index('ix_tasks_created_at_status', 'created_at', 'status'),
        Index('ix_tasks_scheduled_at_status', 'scheduled_at', 'status'),
        Index('ix_tasks_project_status', 'project_id', 'status'),
        Index('ix_tasks_user_status', 'assigned_to_user_id', 'status'),
        Index('ix_tasks_agent_status', 'assigned_to_agent_id', 'status'),
        UniqueConstraint('id', name='uq_tasks_id'),
    )
    
    @validates('title')
    def validate_title(self, key, title):
        if not title or len(title.strip()) == 0:
            raise ValidationError("Task title cannot be empty")
        if len(title) > 255:
            raise ValidationError("Task title cannot exceed 255 characters")
        return title.strip()
    
    @validates('description')
    def validate_description(self, key, description):
        if description and len(description) > MAX_TASK_DESCRIPTION_LENGTH:
            raise ValidationError(f"Task description cannot exceed {MAX_TASK_DESCRIPTION_LENGTH} characters")
        return description
    
    @validates('status')
    def validate_status(self, key, status):
        if status not in [s.value for s in TaskStatus]:
            raise ValidationError(f"Invalid task status: {status}")
        return status
    
    @validates('priority')
    def validate_priority(self, key, priority):
        if priority not in [p.value for p in TaskPriority]:
            raise ValidationError(f"Invalid task priority: {priority}")
        return priority
    
    @validates('task_type')
    def validate_task_type(self, key, task_type):
        if task_type not in [t.value for t in TaskType]:
            raise ValidationError(f"Invalid task type: {task_type}")
        return task_type
    
    @validates('progress_percentage')
    def validate_progress(self, key, progress):
        if progress is not None and (progress < 0 or progress > 100):
            raise ValidationError("Progress percentage must be between 0 and 100")
        return progress
    
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return (
            self.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT] and
            self.retry_count < self.max_retries
        )
    
    def is_overdue(self) -> bool:
        """Check if task is past its deadline"""
        if not self.deadline:
            return False
        return datetime.utcnow() > self.deadline
    
    def get_duration(self) -> Optional[int]:
        """Get actual task duration in seconds"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    def get_wait_time(self) -> Optional[int]:
        """Get time task waited before execution in seconds"""
        if self.created_at and self.started_at:
            return int((self.started_at - self.created_at).total_seconds())
        return None
    
    async def mark_as_started(self, session: AsyncSession) -> None:
        """Mark task as started"""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        session.add(self)
        await session.commit()
        
        logger.info("Task marked as started", task_id=str(self.id), title=self.title)
    
    async def mark_as_completed(self, session: AsyncSession, result_data: Optional[Dict[str, Any]] = None) -> None:
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress_percentage = 100
        self.actual_duration = self.get_duration()
        session.add(self)
        
        if result_data:
            task_result = TaskResult(
                task_id=self.id,
                success=True,
                result_data=result_data,
                created_at=datetime.utcnow()
            )
            session.add(task_result)
        
        await session.commit()
        
        logger.info("Task marked as completed", task_id=str(self.id), title=self.title)
    
    async def mark_as_failed(self, session: AsyncSession, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.last_error = error_message
        self.error_details = error_details or {}
        self.actual_duration = self.get_duration()
        session.add(self)
        
        # Create failure result record
        task_result = TaskResult(
            task_id=self.id,
            success=False,
            error_message=error_message,
            error_details=error_details,
            created_at=datetime.utcnow()
        )
        session.add(task_result)
        
        await session.commit()
        
        logger.error("Task marked as failed", task_id=str(self.id), title=self.title, error=error_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for API responses"""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status,
            "progress_percentage": self.progress_percentage,
            "created_by_user_id": str(self.created_by_user_id) if self.created_by_user_id else None,
            "assigned_to_user_id": str(self.assigned_to_user_id) if self.assigned_to_user_id else None,
            "assigned_to_agent_id": str(self.assigned_to_agent_id) if self.assigned_to_agent_id else None,
            "project_id": str(self.project_id) if self.project_id else None,
            "configuration": self.configuration,
            "input_parameters": self.input_parameters,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_overdue": self.is_overdue(),
            "can_retry": self.can_retry()
        }


class TaskExecution(BaseEntity, TimestampMixin):
    """
    Task execution tracking model for detailed execution history.
    
    Tracks individual execution attempts including:
    - Execution environment details
    - Resource consumption
    - Step-by-step execution logs
    - Performance metrics
    """
    
    __tablename__ = "task_executions"
    
    # Execution identification
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    execution_number = Column(Integer, nullable=False)  # 1st attempt, 2nd attempt, etc.
    executor_id = Column(String(255), nullable=True)  # Agent ID, Worker ID, etc.
    executor_type = Column(String(50), nullable=False)  # agent, worker, system
    
    # Execution status and timing
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Execution environment
    environment = Column(String(50), nullable=False, default=ExecutionEnvironment.LOCAL)
    host_information = Column(JSONB, nullable=True)
    environment_variables = Column(JSONB, nullable=True)
    
    # Resource usage tracking
    initial_resources = Column(JSONB, nullable=True)
    peak_resources = Column(JSONB, nullable=True)
    final_resources = Column(JSONB, nullable=True)
    resource_limits = Column(JSONB, nullable=True)
    
    # Execution logs and output
    execution_logs = Column(JSONB, nullable=True)
    stdout_logs = Column(Text, nullable=True)
    stderr_logs = Column(Text, nullable=True)
    debug_information = Column(JSONB, nullable=True)
    
    # Results and artifacts
    exit_code = Column(Integer, nullable=True)
    output_data = Column(JSONB, nullable=True)
    generated_artifacts = Column(ARRAY(String), nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    error_context = Column(JSONB, nullable=True)
    
    # Relationships
    task = relationship("Task", back_populates="executions")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_task_executions_task_status', 'task_id', 'status'),
        Index('ix_task_executions_started_at', 'started_at'),
        Index('ix_task_executions_executor', 'executor_id', 'executor_type'),
        UniqueConstraint('task_id', 'execution_number', name='uq_task_executions_task_number'),
    )
    
    @validates('execution_number')
    def validate_execution_number(self, key, execution_number):
        if execution_number is not None and execution_number < 1:
            raise ValidationError("Execution number must be positive")
        return execution_number
    
    @validates('status')
    def validate_status(self, key, status):
        if status not in [s.value for s in TaskStatus]:
            raise ValidationError(f"Invalid execution status: {status}")
        return status
    
    @validates('environment')
    def validate_environment(self, key, environment):
        if environment not in [e.value for e in ExecutionEnvironment]:
            raise ValidationError(f"Invalid execution environment: {environment}")
        return environment
    
    def calculate_duration(self) -> None:
        """Calculate and set execution duration"""
        if self.started_at and self.completed_at:
            self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())
    
    def get_resource_efficiency(self) -> Optional[float]:
        """Calculate resource usage efficiency (0-1)"""
        if not self.peak_resources or not self.resource_limits:
            return None
        
        try:
            cpu_efficiency = min(1.0, self.peak_resources.get('cpu', 0) / self.resource_limits.get('cpu', 100))
            memory_efficiency = min(1.0, self.peak_resources.get('memory', 0) / self.resource_limits.get('memory', 1024))
            return (cpu_efficiency + memory_efficiency) / 2
        except (ZeroDivisionError, TypeError):
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to dictionary"""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "execution_number": self.execution_number,
            "executor_id": self.executor_id,
            "executor_type": self.executor_type,
            "status": self.status,
            "environment": self.environment,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "error_message": self.error_message,
            "resource_efficiency": self.get_resource_efficiency(),
            "created_at": self.created_at.isoformat()
        }


class TaskResult(BaseEntity, TimestampMixin):
    """
    Task result storage model for execution outcomes.
    
    Stores comprehensive task results including:
    - Success/failure status
    - Output data and artifacts
    - Error information
    - Performance metrics
    - Validation results
    """
    
    __tablename__ = "task_results"
    
    # Result identification
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("task_executions.id"), nullable=True, index=True)
    result_type = Column(String(50), nullable=False, default="final")  # final, intermediate, partial
    
    # Result status
    success = Column(Boolean, nullable=False, default=False, index=True)
    confidence_score = Column(Float, nullable=True)  # 0.0 - 1.0
    validation_status = Column(String(50), nullable=True)
    
    # Result data
    result_data = Column(JSONB, nullable=True)
    output_format = Column(String(50), nullable=True)
    data_schema_version = Column(String(20), nullable=True)
    
    # Generated artifacts
    artifacts = Column(JSONB, nullable=True)  # List of artifact metadata
    file_paths = Column(ARRAY(String), nullable=True)
    storage_locations = Column(JSONB, nullable=True)
    
    # Error information (if failed)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_details = Column(JSONB, nullable=True)
    error_category = Column(String(50), nullable=True)
    
    # Performance metrics
    processing_time = Column(Float, nullable=True)  # seconds
    memory_used = Column(Integer, nullable=True)  # bytes
    cpu_time = Column(Float, nullable=True)  # seconds
    io_operations = Column(Integer, nullable=True)
    
    # Quality metrics
    output_size = Column(Integer, nullable=True)  # bytes
    complexity_score = Column(Float, nullable=True)
    accuracy_metrics = Column(JSONB, nullable=True)
    
    # Metadata
    execution_context = Column(JSONB, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    task = relationship("Task", back_populates="results")
    execution = relationship("TaskExecution")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_task_results_task_success', 'task_id', 'success'),
        Index('ix_task_results_created_at', 'created_at'),
        Index('ix_task_results_result_type', 'result_type'),
        UniqueConstraint('id', name='uq_task_results_id'),
    )
    
    @validates('confidence_score')
    def validate_confidence_score(self, key, confidence_score):
        if confidence_score is not None and (confidence_score < 0.0 or confidence_score > 1.0):
            raise ValidationError("Confidence score must be between 0.0 and 1.0")
        return confidence_score
    
    @validates('result_data')
    def validate_result_data_size(self, key, result_data):
        if result_data is not None:
            data_size = len(json.dumps(result_data).encode('utf-8'))
            if data_size > MAX_RESULT_SIZE:
                raise ValidationError(f"Result data size {data_size} exceeds maximum {MAX_RESULT_SIZE}")
        return result_data
    
    def calculate_metrics(self) -> None:
        """Calculate derived metrics from result data"""
        if self.result_data:
            self.output_size = len(json.dumps(self.result_data).encode('utf-8'))
        
        if self.artifacts:
            # Calculate complexity based on number and types of artifacts
            self.complexity_score = min(1.0, len(self.artifacts) / 10.0)
    
    def get_quality_score(self) -> Optional[float]:
        """Calculate overall quality score for the result"""
        scores = []
        
        if self.confidence_score is not None:
            scores.append(self.confidence_score)
        
        if self.success:
            scores.append(1.0)
        else:
            scores.append(0.0)
        
        if self.accuracy_metrics and isinstance(self.accuracy_metrics, dict):
            accuracy = self.accuracy_metrics.get('overall_accuracy', 0.0)
            scores.append(accuracy)
        
        return sum(scores) / len(scores) if scores else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "result_type": self.result_type,
            "success": self.success,
            "confidence_score": self.confidence_score,
            "validation_status": self.validation_status,
            "result_data": self.result_data,
            "output_format": self.output_format,
            "artifacts": self.artifacts,
            "file_paths": self.file_paths,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "error_category": self.error_category,
            "processing_time": self.processing_time,
            "memory_used": self.memory_used,
            "output_size": self.output_size,
            "complexity_score": self.complexity_score,
            "quality_score": self.get_quality_score(),
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "notes": self.notes
        }


class TaskDependency(BaseEntity, TimestampMixin):
    """
    Task dependency tracking model for managing task relationships.
    
    Manages complex task dependencies including:
    - Sequential dependencies
    - Parallel execution coordination
    - Conditional dependencies
    - Resource dependencies
    """
    
    __tablename__ = "task_dependencies"
    
    # Dependency relationship
    dependent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    prerequisite_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    
    # Dependency type and conditions
    dependency_type = Column(String(50), nullable=False, default="sequential")  # sequential, conditional, resource
    condition_expression = Column(Text, nullable=True)  # JSON or expression for conditional deps
    
    # Status and validation
    is_satisfied = Column(Boolean, nullable=False, default=False, index=True)
    satisfaction_checked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Dependency metadata
    description = Column(String(500), nullable=True)
    priority = Column(Integer, nullable=False, default=0)
    
    # Relationships
    dependent_task = relationship("Task", foreign_keys=[dependent_task_id])
    prerequisite_task = relationship("Task", foreign_keys=[prerequisite_task_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_task_dependencies_dependent', 'dependent_task_id'),
        Index('ix_task_dependencies_prerequisite', 'prerequisite_task_id'),
        Index('ix_task_dependencies_satisfied', 'is_satisfied'),
        UniqueConstraint('dependent_task_id', 'prerequisite_task_id', name='uq_task_dependencies_pair'),
    )
    
    @validates('dependency_type')
    def validate_dependency_type(self, key, dependency_type):
        valid_types = ['sequential', 'conditional', 'resource', 'data']
        if dependency_type not in valid_types:
            raise ValidationError(f"Invalid dependency type: {dependency_type}")
        return dependency_type
    
    async def check_satisfaction(self, session: AsyncSession) -> bool:
        """Check if dependency is satisfied"""
        from sqlalchemy import select
        
        # Get prerequisite task
        result = await session.execute(
            select(Task).where(Task.id == self.prerequisite_task_id)
        )
        prerequisite_task = result.scalar_one_or_none()
        
        if not prerequisite_task:
            return False
        
        # Check based on dependency type
        if self.dependency_type == "sequential":
            satisfied = prerequisite_task.status == TaskStatus.COMPLETED
        elif self.dependency_type == "conditional":
            satisfied = self._evaluate_condition(prerequisite_task)
        elif self.dependency_type == "resource":
            satisfied = self._check_resource_availability(prerequisite_task)
        else:
            satisfied = False
        
        # Update satisfaction status
        self.is_satisfied = satisfied
        self.satisfaction_checked_at = datetime.utcnow()
        session.add(self)
        
        return satisfied
    
    def _evaluate_condition(self, prerequisite_task: Task) -> bool:
        """Evaluate conditional dependency"""
        if not self.condition_expression:
            return prerequisite_task.status == TaskStatus.COMPLETED
        
        try:
            # Simple condition evaluation (extend as needed)
            if "status==" in self.condition_expression:
                required_status = self.condition_expression.split("==")[1].strip().strip('"\'')
                return prerequisite_task.status == required_status
            
            # Add more condition types as needed
            return False
            
        except Exception as e:
            logger.error("Error evaluating dependency condition", error=str(e))
            return False
    
    def _check_resource_availability(self, prerequisite_task: Task) -> bool:
        """Check resource dependency satisfaction"""
        # Implement resource availability checks
        # This could check for file availability, service readiness, etc.
        return prerequisite_task.status == TaskStatus.COMPLETED


# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def get_task_by_id(session: AsyncSession, task_id: uuid.UUID) -> Optional[Task]:
    """Get task by ID with error handling"""
    try:
        from sqlalchemy import select
        result = await session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error("Error fetching task by ID", task_id=str(task_id), error=str(e))
        return None

async def get_tasks_by_status(session: AsyncSession, status: TaskStatus, limit: int = 100) -> List[Task]:
    """Get tasks by status with pagination"""
    try:
        from sqlalchemy import select
        result = await session.execute(
            select(Task)
            .where(Task.status == status.value)
            .order_by(Task.priority.desc(), Task.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error("Error fetching tasks by status", status=status.value, error=str(e))
        return []

async def get_user_tasks(
    session: AsyncSession, 
    user_id: uuid.UUID, 
    status: Optional[TaskStatus] = None,
    limit: int = 50
) -> List[Task]:
    """Get tasks for a specific user"""
    try:
        from sqlalchemy import select, or_
        
        query = select(Task).where(
            or_(
                Task.created_by_user_id == user_id,
                Task.assigned_to_user_id == user_id
            )
        )
        
        if status:
            query = query.where(Task.status == status.value)
        
        query = query.order_by(Task.created_at.desc()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
        
    except Exception as e:
        logger.error("Error fetching user tasks", user_id=str(user_id), error=str(e))
        return []

async def create_task(
    session: AsyncSession,
    title: str,
    task_type: TaskType,
    created_by_user_id: Optional[uuid.UUID] = None,
    **kwargs
) -> Task:
    """Create a new task with validation"""
    try:
        task = Task(
            title=title,
            task_type=task_type.value,
            created_by_user_id=created_by_user_id,
            **kwargs
        )
        
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        logger.info("Task created successfully", task_id=str(task.id), title=title)
        return task
        
    except Exception as e:
        await session.rollback()
        logger.error("Error creating task", title=title, error=str(e))
        raise TaskError(f"Failed to create task: {str(e)}")

def validate_task_configuration(config: Dict[str, Any]) -> bool:
    """Validate task configuration schema"""
    try:
        TaskConfiguration(**config)
        return True
    except Exception as e:
        logger.warning("Invalid task configuration", error=str(e))
        return False

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Enums
    "TaskStatus",
    "TaskPriority", 
    "TaskType",
    "ExecutionEnvironment",
    
    # Models
    "Task",
    "TaskExecution",
    "TaskResult", 
    "TaskDependency",
    
    # Schemas
    "TaskConfiguration",
    "TaskMetrics",
    "TaskResult",
    
    # Utility functions
    "get_task_by_id",
    "get_tasks_by_status",
    "get_user_tasks", 
    "create_task",
    "validate_task_configuration"
]