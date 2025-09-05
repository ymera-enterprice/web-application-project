"""
YMERA Enterprise Multi-Agent System - Task Management Schemas
Production-ready Pydantic schemas for task lifecycle management
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


# Task Enums
class TaskStatus(str, Enum):
    """Task status states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    TESTING = "testing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Task type classifications"""
    FEATURE = "feature"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MAINTENANCE = "maintenance"
    RESEARCH = "research"
    REVIEW = "review"
    OPTIMIZATION = "optimization"


class TaskComplexity(str, Enum):
    """Task complexity levels"""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class BlockerType(str, Enum):
    """Types of task blockers"""
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    TECHNICAL = "technical"
    APPROVAL = "approval"
    EXTERNAL = "external"
    CLARIFICATION = "clarification"


# Task Models
class TaskDependency(BaseSchema):
    """Task dependency relationship"""
    
    task_id: str = Field(
        description="Dependent task identifier"
    )
    type: str = Field(
        description="Dependency type (blocks, requires, etc.)"
    )
    description: Optional[str] = Field(
        None,
        description="Dependency description"
    )
    is_critical: bool = Field(
        default=False,
        description="Whether this dependency is critical"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Dependency creation timestamp"
    )


class TaskBlocker(BaseSchema):
    """Task blocker information"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Blocker unique identifier"
    )
    type: BlockerType = Field(
        description="Type of blocker"
    )
    title: str = Field(
        description="Blocker title"
    )
    description: str = Field(
        description="Detailed blocker description"
    )
    severity: TaskPriority = Field(
        description="Blocker severity level"
    )
    assigned_to: Optional[str] = Field(
        None,
        description="Person assigned to resolve the blocker"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Blocker creation timestamp"
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="Blocker resolution timestamp"
    )
    resolution_notes: Optional[str] = Field(
        None,
        description="Notes about how the blocker was resolved"
    )
    is_resolved: bool = Field(
        default=False,
        description="Whether the blocker is resolved"
    )


class TaskEstimate(BaseSchema):
    """Task time and effort estimates"""
    
    estimated_hours: float = Field(
        ge=0.0,
        description="Estimated hours to complete"
    )
    actual_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Actual hours spent"
    )
    story_points: Optional[int] = Field(
        None,
        ge=0,
        description="Story points for agile estimation"
    )
    complexity: TaskComplexity = Field(
        description="Task complexity assessment"
    )
    confidence_level: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in estimate (0-1)"
    )
    estimation_method: str = Field(
        description="Method used for estimation"
    )
    estimated_by: str = Field(
        description="Person who provided the estimate"
    )
    estimation_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the estimate was made"
    )


class TaskProgress(BaseSchema):
    """Task progress tracking"""
    
    completion_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Task completion percentage"
    )
    milestones_completed: List[str] = Field(
        default_factory=list,
        description="Completed milestone identifiers"
    )
    work_completed: List[str] = Field(
        default_factory=list,
        description="List of completed work items"
    )
    remaining_work: List[str] = Field(
        default_factory=list,
        description="List of remaining work items"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last progress update timestamp"
    )
    updated_by: str = Field(
        description="Person who last updated progress"
    )
    notes: Optional[str] = Field(
        None,
        description="Progress update notes"
    )


class TaskComment(BaseSchema):
    """Task comment/note"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Comment unique identifier"
    )
    author: str = Field(
        description="Comment author identifier"
    )
    content: str = Field(
        description="Comment content"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Comment creation timestamp"
    )
    edited_at: Optional[datetime] = Field(
        None,
        description="Last edit timestamp"
    )
    is_internal: bool = Field(
        default=False,
        description="Whether comment is internal only"
    )
    mentions: List[str] = Field(
        default_factory=list,
        description="User mentions in the comment"
    )
    attachments: List[str] = Field(
        default_factory=list,
        description="File attachment identifiers"
    )


class TaskTimeLog(BaseSchema):
    """Time tracking entry for tasks"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Time log entry identifier"
    )
    user: str = Field(
        description="User who logged the time"
    )
    hours: float = Field(
        gt=0.0,
        description="Hours logged"
    )
    description: str = Field(
        description="Description of work performed"
    )
    date: datetime = Field(
        description="Date when work was performed"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Log entry creation timestamp"
    )
    is_billable: bool = Field(
        default=True,
        description="Whether time is billable"
    )
    category: Optional[str] = Field(
        None,
        description="Work category"
    )


class TaskReview(BaseSchema):
    """Task review information"""
    
    reviewer: str = Field(
        description="Reviewer identifier"
    )
    status: str = Field(
        description="Review status (approved, rejected, needs_changes)"
    )
    feedback: str = Field(
        description="Review feedback"
    )
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Review completion timestamp"
    )
    checklist: Dict[str, bool] = Field(
        default_factory=dict,
        description="Review checklist items"
    )
    rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Quality rating (1-5)"
    )


class Task(BaseEntity):
    """Main task entity"""
    
    title: str = Field(
        description="Task title"
    )
    description: str = Field(
        description="Detailed task description"
    )
    type: TaskType = Field(
        description="Task type classification"
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current task status"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Task priority level"
    )
    assigned_to: Optional[str] = Field(
        None,
        description="Assignee identifier"
    )
    created_by: str = Field(
        description="Task creator identifier"
    )
    project_id: Optional[str] = Field(
        None,
        description="Associated project identifier"
    )
    parent_task_id: Optional[str] = Field(
        None,
        description="Parent task identifier for subtasks"
    )
    subtasks: List[str] = Field(
        default_factory=list,
        description="List of subtask identifiers"
    )
    dependencies: List[TaskDependency] = Field(
        default_factory=list,
        description="Task dependencies"
    )
    blockers: List[TaskBlocker] = Field(
        default_factory=list,
        description="Current task blockers"
    )
    estimate: Optional[TaskEstimate] = Field(
        None,
        description="Task time and effort estimates"
    )
    progress: TaskProgress = Field(
        default_factory=TaskProgress,
        description="Task progress information"
    )
    due_date: Optional[datetime] = Field(
        None,
        description="Task due date"
    )
    started_at: Optional[datetime] = Field(
        None,
        description="When work started on the task"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When task was completed"
    )
    comments: List[TaskComment] = Field(
        default_factory=list,
        description="Task comments and notes"
    )
    time_logs: List[TaskTimeLog] = Field(
        default_factory=list,
        description="Time tracking entries"
    )
    reviews: List[TaskReview] = Field(
        default_factory=list,
        description="Task reviews"
    )
    labels: List[str] = Field(
        default_factory=list,
        description="Task labels/tags"
    )
    watchers: List[str] = Field(
        default_factory=list,
        description="Users watching this task"
    )
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom field values"
    )
    external_links: Dict[str, str] = Field(
        default_factory=dict,
        description="Links to external resources"
    )
    
    @validator('title')
    def validate_title(cls, v):
        """Validate task title"""
        if len(v.strip()) < 5:
            raise ValueError('Task title must be at least 5 characters long')
        return v.strip()
    
    @root_validator
    def validate_task_relationships(cls, values):
        """Validate task relationship consistency"""
        parent_task_id = values.get('parent_task_id')
        subtasks = values.get('subtasks', [])
        task_id = values.get('id')
        
        # Prevent circular parent-child relationships
        if parent_task_id and task_id and parent_task_id == task_id:
            raise ValueError('Task cannot be its own parent')
        
        # Prevent task from being in its own subtasks list
        if task_id and task_id in subtasks:
            raise ValueError('Task cannot be its own subtask')
        
        return values
    
    @root_validator
    def validate_status_transitions(cls, values):
        """Validate status transition logic"""
        status = values.get('status')
        blockers = values.get('blockers', [])
        
        # If task has unresolved blockers, it cannot be in progress
        if status == TaskStatus.IN_PROGRESS:
            unresolved_blockers = [b for b in blockers if not b.is_resolved]
            if unresolved_blockers:
                raise ValueError('Cannot start task with unresolved blockers')
        
        # Set timestamps based on status
        if status == TaskStatus.IN_PROGRESS and not values.get('started_at'):
            values['started_at'] = datetime.now(timezone.utc)
        
        if status == TaskStatus.COMPLETED and not values.get('completed_at'):
            values['completed_at'] = datetime.now(timezone.utc)
            values['progress'] = values.get('progress', TaskProgress())
            values['progress'].completion_percentage = 100.0
        
        return values
    
    def get_total_time_logged(self) -> float:
        """Calculate total time logged for this task"""
        return sum(log.hours for log in self.time_logs)
    
    def get_active_blockers(self) -> List[TaskBlocker]:
        """Get list of active (unresolved) blockers"""
        return [blocker for blocker in self.blockers if not blocker.is_resolved]
    
    def is_overdue(self) -> bool:
        """Check if task is overdue"""
        if not self.due_date:
            return False
        return datetime.now(timezone.utc) > self.due_date and self.status != TaskStatus.COMPLETED


# Task Analytics Models
class TaskMetrics(BaseSchema):
    """Task performance metrics"""
    
    cycle_time_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Time from start to completion"
    )
    lead_time_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Time from creation to completion"
    )
    blocked_time_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Total time task was blocked"
    )
    review_time_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Time spent in review"
    )
    rework_count: int = Field(
        default=0,
        ge=0,
        description="Number of times task was reworked"
    )
    estimate_accuracy: Optional[float] = Field(
        None,
        description="Accuracy of time estimate (actual/estimated)"
    )
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Task quality score (0-10)"
    )
    customer_satisfaction: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Customer satisfaction rating"
    )


class TaskBatch(BaseSchema):
    """Batch operation on multiple tasks"""
    
    task_ids: List[str] = Field(
        description="List of task identifiers"
    )
    operation: str = Field(
        description="Batch operation type"
    )
    parameters: Dict[str, Any] = Field(
        description="Operation parameters"
    )
    initiated_by: str = Field(
        description="User who initiated the batch operation"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Batch operation creation timestamp"
    )
    status: str = Field(
        default="pending",
        description="Batch operation status"
    )
    results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operation results per task"
    )


# API Request/Response Models
class TaskCreateRequest(BaseSchema):
    """Task creation request"""
    
    title: str = Field(
        description="Task title"
    )
    description: str = Field(
        description="Task description"
    )
    type: TaskType = Field(
        description="Task type"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Task priority"
    )
    assigned_to: Optional[str] = Field(
        None,
        description="Assignee identifier"
    )
    project_id: Optional[str] = Field(
        None,
        description="Project identifier"
    )
    parent_task_id: Optional[str] = Field(
        None,
        description="Parent task identifier"
    )
    due_date: Optional[datetime] = Field(
        None,
        description="Due date"
    )
    estimate: Optional[TaskEstimate] = Field(
        None,
        description="Time estimate"
    )
    labels: List[str] = Field(
        default_factory=list,
        description="Task labels"
    )
    watchers: List[str] = Field(
        default_factory=list,
        description="Task watchers"
    )


class TaskUpdateRequest(BaseSchema):
    """Task update request"""
    
    title: Optional[str] = Field(
        None,
        description="Updated title"
    )
    description: Optional[str] = Field(
        None,
        description="Updated description"
    )
    status: Optional[TaskStatus] = Field(
        None,
        description="Updated status"
    )
    priority: Optional[TaskPriority] = Field(
        None,
        description="Updated priority"
    )
    assigned_to: Optional[str] = Field(
        None,
        description="Updated assignee"
    )
    due_date: Optional[datetime] = Field(
        None,
        description="Updated due date"
    )
    labels: Optional[List[str]] = Field(
        None,
        description="Updated labels"
    )
    watchers: Optional[List[str]] = Field(
        None,
        description="Updated watchers"
    )


class TaskListResponse(BaseSchema):
    """Task list API response"""
    
    tasks: List[Task] = Field(
        description="List of tasks"
    )
    total_count: int = Field(
        ge=0,
        description="Total number of tasks"
    )
    page: int = Field(
        ge=1,
        description="Current page number"
    )
    page_size: int = Field(
        ge=1,
        le=100,
        description="Number of items per page"
    )
    filters: Dict[str, Any] = Field(
        description="Applied filters"
    )
    sort_by: str = Field(
        description="Sort field"
    )
    sort_order: str = Field(
        description="Sort order (asc/desc)"
    )


class TaskSearchRequest(BaseSchema):
    """Task search request"""
    
    query: Optional[str] = Field(
        None,
        description="Search query string"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Search filters"
    )
    sort_by: str = Field(
        default="created_at",
        description="Sort field"
    )
    sort_order: str = Field(
        default="desc",
        description="Sort order"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number"
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page"
    )
    include_subtasks: bool = Field(
        default=True,
        description="Include subtasks in results"
    )
    include_archived: bool = Field(
        default=False,
        description="Include archived tasks"
    )


# Export all models
__all__ = [
    # Enums
    'TaskStatus',
    'TaskPriority',
    'TaskType',
    'TaskComplexity',
    'BlockerType',
    
    # Core Models
    'TaskDependency',
    'TaskBlocker',
    'TaskEstimate',
    'TaskProgress',
    'TaskComment',
    'TaskTimeLog',
    'TaskReview',
    'Task',
    
    # Analytics
    'TaskMetrics',
    'TaskBatch',
    
    # API Models
    'TaskCreateRequest',
    'TaskUpdateRequest',
    'TaskListResponse',
    'TaskSearchRequest',
]
    