"""
YMERA Enterprise Multi-Agent System - Agent Management Schemas
Production-ready Pydantic schemas for agent orchestration and management
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Any, Dict, List, Optional, Union, Literal
from datetime import datetime, timezone
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo, PerformanceMetrics


# Agent Enums
class AgentType(str, Enum):
    """Types of agents in the YMERA system"""
    CORE = "core"
    SPECIALIZED = "specialized"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Agent operational status"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"
    MAINTENANCE = "maintenance"


class AgentCapability(str, Enum):
    """Agent capabilities"""
    PROJECT_MANAGEMENT = "project_management"
    CODE_ANALYSIS = "code_analysis"
    CODE_ENHANCEMENT = "code_enhancement"
    VALIDATION = "validation"
    DOCUMENTATION = "documentation"
    SECURITY_SCANNING = "security_scanning"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    EXAMINATION = "examination"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class OrchestrationStrategy(str, Enum):
    """Agent orchestration strategies"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    PIPELINE = "pipeline"
    ADAPTIVE = "adaptive"


class LearningMode(str, Enum):
    """Agent learning modes"""
    PASSIVE = "passive"
    ACTIVE = "active"
    REINFORCEMENT = "reinforcement"
    COLLABORATIVE = "collaborative"


# Agent Configuration Models
class AgentConfig(BaseSchema):
    """Agent configuration parameters"""
    
    name: str = Field(
        description="Agent name identifier"
    )
    type: AgentType = Field(
        description="Agent type classification"
    )
    capabilities: List[AgentCapability] = Field(
        description="List of agent capabilities"
    )
    max_concurrent_tasks: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum number of concurrent tasks"
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Task timeout in seconds"
    )
    retry_attempts: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts for failed tasks"
    )
    learning_enabled: bool = Field(
        default=True,
        description="Whether learning is enabled for this agent"
    )
    learning_mode: LearningMode = Field(
        default=LearningMode.ACTIVE,
        description="Learning mode for the agent"
    )
    resource_limits: Optional[Dict[str, Union[int, float]]] = Field(
        None,
        description="Resource usage limits"
    )
    custom_parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom agent-specific parameters"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "analysis_agent",
                "type": "core",
                "capabilities": ["code_analysis", "validation"],
                "max_concurrent_tasks": 10,
                "timeout_seconds": 600,
                "retry_attempts": 3,
                "learning_enabled": True,
                "learning_mode": "active",
                "resource_limits": {
                    "max_memory_mb": 1024,
                    "max_cpu_percent": 80
                },
                "custom_parameters": {
                    "analysis_depth": "deep",
                    "include_security_scan": True
                }
            }
        }
    }


class AgentState(BaseSchema):
    """Current agent state information"""
    
    status: AgentStatus = Field(
        description="Current agent status"
    )
    current_task_id: Optional[str] = Field(
        None,
        description="Currently executing task ID"
    )
    active_tasks: List[str] = Field(
        default_factory=list,
        description="List of active task IDs"
    )
    task_queue_size: int = Field(
        ge=0,
        description="Number of tasks in queue"
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last activity timestamp"
    )
    uptime_seconds: float = Field(
        ge=0.0,
        description="Agent uptime in seconds"
    )
    resource_usage: Optional[Dict[str, float]] = Field(
        None,
        description="Current resource usage"
    )
    performance_metrics: Optional[PerformanceMetrics] = Field(
        None,
        description="Agent performance metrics"
    )
    error_count: int = Field(
        default=0,
        ge=0,
        description="Number of errors since last reset"
    )
    success_rate: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Success rate percentage"
    )


class Agent(BaseEntity):
    """Agent entity model"""
    
    name: str = Field(
        description="Agent name identifier"
    )
    type: AgentType = Field(
        description="Agent type classification"
    )
    capabilities: List[AgentCapability] = Field(
        description="List of agent capabilities"
    )
    config: AgentConfig = Field(
        description="Agent configuration"
    )
    state: AgentState = Field(
        description="Current agent state"
    )
    version: str = Field(
        description="Agent version"
    )
    description: Optional[str] = Field(
        None,
        description="Agent description"
    )
    owner: Optional[str] = Field(
        None,
        description="Agent owner/creator"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Agent tags for categorization"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of dependent agent names"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Validate agent name format"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Agent name must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()


# Task Models
class TaskInput(BaseSchema):
    """Task input parameters"""
    
    data: Dict[str, Any] = Field(
        description="Task input data"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional task context"
    )
    requirements: Optional[List[str]] = Field(
        None,
        description="Task requirements"
    )
    constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Task constraints"
    )


class TaskOutput(BaseSchema):
    """Task output results"""
    
    result: Dict[str, Any] = Field(
        description="Task result data"
    )
    artifacts: List[str] = Field(
        default_factory=list,
        description="Generated artifacts (file paths, URLs, etc.)"
    )
    metrics: Optional[Dict[str, Union[int, float]]] = Field(
        None,
        description="Task execution metrics"
    )
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Output quality score"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Result confidence score"
    )


class TaskError(BaseSchema):
    """Task error information"""
    
    code: str = Field(
        description="Error code"
    )
    message: str = Field(
        description="Error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed error information"
    )
    stack_trace: Optional[str] = Field(
        None,
        description="Error stack trace"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts"
    )
    is_recoverable: bool = Field(
        description="Whether the error is recoverable"
    )


class Task(BaseEntity):
    """Task entity model"""
    
    name: str = Field(
        description="Task name"
    )
    description: Optional[str] = Field(
        None,
        description="Task description"
    )
    agent_id: str = Field(
        description="Assigned agent ID"
    )
    project_id: Optional[str] = Field(
        None,
        description="Associated project ID"
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Parent workflow ID"
    )
    status: TaskStatus = Field(
        description="Current task status"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Task priority level"
    )
    input: TaskInput = Field(
        description="Task input parameters"
    )
    output: Optional[TaskOutput] = Field(
        None,
        description="Task output results"
    )
    error: Optional[TaskError] = Field(
        None,
        description="Task error information"
    )
    timing: TimingInfo = Field(
        description="Task execution timing"
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Task completion progress percentage"
    )
    estimated_duration: Optional[int] = Field(
        None,
        ge=0,
        description="Estimated duration in seconds"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of dependent task IDs"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Task tags"
    )


# Workflow Models
class WorkflowStep(BaseSchema):
    """Individual workflow step"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Step unique identifier"
    )
    name: str = Field(
        description="Step name"
    )
    agent_capability: AgentCapability = Field(
        description="Required agent capability"
    )
    input_mapping: Dict[str, str] = Field(
        description="Input parameter mapping"
    )
    output_mapping: Dict[str, str] = Field(
        description="Output parameter mapping"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Dependent step IDs"
    )
    conditions: Optional[Dict[str, Any]] = Field(
        None,
        description="Conditional execution rules"
    )
    retry_policy: Optional[Dict[str, Any]] = Field(
        None,
        description="Step-specific retry policy"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        ge=1,
        description="Step timeout override"
    )


class Workflow(BaseEntity):
    """Workflow definition model"""
    
    name: str = Field(
        description="Workflow name"
    )
    description: Optional[str] = Field(
        None,
        description="Workflow description"
    )
    version: str = Field(
        default="1.0.0",
        description="Workflow version"
    )
    steps: List[WorkflowStep] = Field(
        description="Workflow steps"
    )
    strategy: OrchestrationStrategy = Field(
        default=OrchestrationStrategy.SEQUENTIAL,
        description="Orchestration strategy"
    )
    max_execution_time: int = Field(
        default=3600,
        ge=1,
        description="Maximum execution time in seconds"
    )
    input_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow input schema definition"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow output schema definition"
    )
    variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow variables"
    )
    is_template: bool = Field(
        default=False,
        description="Whether this is a workflow template"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Workflow tags"
    )


class WorkflowExecution(BaseEntity):
    """Workflow execution instance"""
    
    workflow_id: str = Field(
        description="Workflow definition ID"
    )
    project_id: Optional[str] = Field(
        None,
        description="Associated project ID"
    )
    status: TaskStatus = Field(
        description="Workflow execution status"
    )
    input_data: Dict[str, Any] = Field(
        description="Workflow input data"
    )
    output_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow output data"
    )
    current_step: Optional[str] = Field(
        None,
        description="Currently executing step ID"
    )
    completed_steps: List[str] = Field(
        default_factory=list,
        description="List of completed step IDs"
    )
    failed_steps: List[str] = Field(
        default_factory=list,
        description="List of failed step IDs"
    )
    task_ids: List[str] = Field(
        default_factory=list,
        description="Associated task IDs"
    )
    timing: TimingInfo = Field(
        description="Workflow execution timing"
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Workflow completion progress"
    )
    error: Optional[TaskError] = Field(
        None,
        description="Workflow error information"
    )


# Agent Communication Models
class Message(BaseSchema):
    """Inter-agent message"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Message unique identifier"
    )
    sender_id: str = Field(
        description="Sender agent ID"
    )
    recipient_id: str = Field(
        description="Recipient agent ID"
    )
    message_type: str = Field(
        description="Message type identifier"
    )
    content: Dict[str, Any] = Field(
        description="Message content"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Message priority"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message timestamp"
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Message correlation ID"
    )
    reply_to: Optional[str] = Field(
        None,
        description="Reply-to message ID"
    )
    expiry: Optional[datetime] = Field(
        None,
        description="Message expiry time"
    )
    delivery_attempts: int = Field(
        default=0,
        ge=0,
        description="Number of delivery attempts"
    )
    acknowledged: bool = Field(
        default=False,
        description="Whether message was acknowledged"
    )


class AgentCommunicationStats(BaseSchema):
    """Agent communication statistics"""
    
    messages_sent: int = Field(
        default=0,
        ge=0,
        description="Total messages sent"
    )
    messages_received: int = Field(
        default=0,
        ge=0,
        description="Total messages received"
    )
    messages_failed: int = Field(
        default=0,
        ge=0,
        description="Total failed messages"
    )
    average_response_time: float = Field(
        default=0.0,
        ge=0.0,
        description="Average response time in milliseconds"
    )
    active_conversations: int = Field(
        default=0,
        ge=0,
        description="Number of active conversations"
    )
    collaboration_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Agent collaboration effectiveness score"
    )


# Learning Models
class LearningData(BaseSchema):
    """Agent learning data point"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Learning data unique identifier"
    )
    agent_id: str = Field(
        description="Learning agent ID"
    )
    task_id: Optional[str] = Field(
        None,
        description="Associated task ID"
    )
    context: Dict[str, Any] = Field(
        description="Learning context data"
    )
    action: Dict[str, Any] = Field(
        description="Action taken"
    )
    outcome: Dict[str, Any] = Field(
        description="Outcome observed"
    )
    reward: Optional[float] = Field(
        None,
        description="Learning reward signal"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Learning confidence score"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Learning data timestamp"
    )
    feedback_source: str = Field(
        description="Source of feedback (human, automated, peer)"
    )
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Data quality score"
    )


class AgentLearningStats(BaseSchema):
    """Agent learning statistics"""
    
    total_learning_instances: int = Field(
        default=0,
        ge=0,
        description="Total learning instances"
    )
    successful_adaptations: int = Field(
        default=0,
        ge=0,
        description="Successful adaptations made"
    )
    learning_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Current learning rate"
    )
    knowledge_entropy: float = Field(
        default=0.0,
        ge=0.0,
        description="Knowledge entropy measure"
    )
    specialization_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Agent specialization score"
    )
    collaboration_learning: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Learning from collaboration score"
    )
    last_learning_event: Optional[datetime] = Field(
        None,
        description="Last learning event timestamp"
    )


# Request/Response Models
class AgentRegistrationRequest(BaseSchema):
    """Agent registration request"""
    
    config: AgentConfig = Field(
        description="Agent configuration"
    )
    initial_state: Optional[AgentState] = Field(
        None,
        description="Initial agent state"
    )
    description: Optional[str] = Field(
        None,
        description="Agent description"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Agent tags"
    )


class AgentUpdateRequest(BaseSchema):
    """Agent update request"""
    
    config: Optional[AgentConfig] = Field(
        None,
        description="Updated agent configuration"
    )
    description: Optional[str] = Field(
        None,
        description="Updated description"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Updated tags"
    )


class TaskCreationRequest(BaseSchema):
    """Task creation request"""
    
    name: str = Field(
        description="Task name"
    )
    description: Optional[str] = Field(
        None,
        description="Task description"
    )
    agent_id: Optional[str] = Field(
        None,
        description="Preferred agent ID (if none, will be auto-assigned)"
    )
    capability_required: Optional[AgentCapability] = Field(
        None,
        description="Required agent capability"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Task priority"
    )
    input: TaskInput = Field(
        description="Task input parameters"
    )
    estimated_duration: Optional[int] = Field(
        None,
        ge=0,
        description="Estimated duration in seconds"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Dependent task IDs"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Task tags"
    )


class WorkflowCreationRequest(BaseSchema):
    """Workflow creation request"""
    
    name: str = Field(
        description="Workflow name"
    )
    description: Optional[str] = Field(
        None,
        description="Workflow description"
    )
    steps: List[WorkflowStep] = Field(
        description="Workflow steps"
    )
    strategy: OrchestrationStrategy = Field(
        default=OrchestrationStrategy.SEQUENTIAL,
        description="Orchestration strategy"
    )
    input_data: Dict[str, Any] = Field(
        description="Workflow input data"
    )
    variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow variables"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Workflow tags"
    )


class AgentOrchestrationStatus(BaseSchema):
    """Agent orchestration status"""
    
    total_agents: int = Field(
        ge=0,
        description="Total number of registered agents"
    )
    active_agents: int = Field(
        ge=0,
        description="Number of active agents"
    )
    busy_agents: int = Field(
        ge=0,
        description="Number of busy agents"
    )
    idle_agents: int = Field(
        ge=0,
        description="Number of idle agents"
    )
    error_agents: int = Field(
        ge=0,
        description="Number of agents with errors"
    )
    total_tasks: int = Field(
        ge=0,
        description="Total tasks in system"
    )
    pending_tasks: int = Field(
        ge=0,
        description="Number of pending tasks"
    )
    running_tasks: int = Field(
        ge=0,
        description="Number of running tasks"
    )
    completed_tasks: int = Field(
        ge=0,
        description="Number of completed tasks"
    )
    failed_tasks: int = Field(
        ge=0,
        description="Number of failed tasks"
    )
    active_workflows: int = Field(
        ge=0,
        description="Number of active workflows"
    )
    orchestration_efficiency: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall orchestration efficiency score"
    )
    load_balance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Load balancing effectiveness score"
    )
    collaboration_index: float = Field(
        ge=0.0,
        le=1.0,
        description="Inter-agent collaboration index"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Status timestamp"
    )


class AgentCapabilityMatch(BaseSchema):
    """Agent capability matching result"""
    
    agent_id: str = Field(
        description="Matched agent ID"
    )
    agent_name: str = Field(
        description="Matched agent name"
    )
    match_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Capability match score"
    )
    availability_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Agent availability score"
    )
    performance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Historical performance score"
    )
    overall_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall matching score"
    )
    current_load: float = Field(
        ge=0.0,
        le=1.0,
        description="Current agent load percentage"
    )
    estimated_completion_time: Optional[int] = Field(
        None,
        ge=0,
        description="Estimated task completion time in seconds"
    )


# Response Models
class AgentListResponse(BaseSchema):
    """Agent list response"""
    
    agents: List[Agent] = Field(
        description="List of agents"
    )
    total_count: int = Field(
        ge=0,
        description="Total number of agents"
    )
    active_count: int = Field(
        ge=0,
        description="Number of active agents"
    )


class TaskListResponse(BaseSchema):
    """Task list response"""
    
    tasks: List[Task] = Field(
        description="List of tasks"
    )
    total_count: int = Field(
        ge=0,
        description="Total number of tasks"
    )
    status_counts: Dict[TaskStatus, int] = Field(
        description="Task counts by status"
    )


class WorkflowListResponse(BaseSchema):
    """Workflow list response"""
    
    workflows: List[Workflow] = Field(
        description="List of workflows"
    )
    executions: List[WorkflowExecution] = Field(
        description="List of workflow executions"
    )
    total_workflows: int = Field(
        ge=0,
        description="Total number of workflows"
    )
    active_executions: int = Field(
        ge=0,
        description="Number of active executions"
    )