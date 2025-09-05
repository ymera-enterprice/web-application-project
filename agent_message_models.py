"""
YMERA Enterprise Agent Communication Models
Production-Ready Agent Message System with Learning Integration
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Any, Dict, List, Optional, Union, Literal, Set
from enum import Enum, IntEnum
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import json
from dataclasses import dataclass
import hashlib


# ============================================================================
# Core Enumerations
# ============================================================================

class MessageType(str, Enum):
    """Types of messages in the agent communication system"""
    
    # Basic Communication
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ACKNOWLEDGMENT = "acknowledgment"
    
    # Task Management
    TASK_ASSIGNMENT = "task_assignment"
    TASK_UPDATE = "task_update"
    TASK_COMPLETION = "task_completion"
    TASK_FAILURE = "task_failure"
    
    # Workflow & Orchestration
    WORKFLOW_START = "workflow_start"
    WORKFLOW_STEP = "workflow_step"
    WORKFLOW_COMPLETION = "workflow_completion"
    WORKFLOW_ERROR = "workflow_error"
    
    # Data & Resource Sharing
    DATA_SHARE = "data_share"
    RESOURCE_REQUEST = "resource_request"
    RESOURCE_RESPONSE = "resource_response"
    
    # Learning & Knowledge
    LEARNING_UPDATE = "learning_update"
    KNOWLEDGE_QUERY = "knowledge_query"
    KNOWLEDGE_RESPONSE = "knowledge_response"
    FEEDBACK_REQUEST = "feedback_request"
    FEEDBACK_RESPONSE = "feedback_response"
    
    # System & Health
    HEALTH_CHECK = "health_check"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    PERFORMANCE_METRIC = "performance_metric"
    
    # Security & Compliance
    SECURITY_ALERT = "security_alert"
    AUDIT_LOG = "audit_log"
    COMPLIANCE_CHECK = "compliance_check"


class MessagePriority(IntEnum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class MessageStatus(str, Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AgentRole(str, Enum):
    """Agent roles in the system"""
    ORCHESTRATOR = "orchestrator"
    PROJECT_MANAGEMENT = "project_management"
    ANALYSIS = "analysis"
    ENHANCEMENT = "enhancement"
    VALIDATION = "validation"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    EXAMINATION = "examination"


class DeliveryMode(str, Enum):
    """Message delivery modes"""
    DIRECT = "direct"           # Direct agent-to-agent
    BROADCAST = "broadcast"     # To all agents
    MULTICAST = "multicast"     # To specific agent group
    PUBLISH = "publish"         # Pub/sub pattern
    QUEUE = "queue"            # Queued delivery


class LearningContext(str, Enum):
    """Learning context categories"""
    TASK_EXECUTION = "task_execution"
    ERROR_RESOLUTION = "error_resolution"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    KNOWLEDGE_ACQUISITION = "knowledge_acquisition"
    PATTERN_RECOGNITION = "pattern_recognition"
    DECISION_MAKING = "decision_making"
    COLLABORATION_IMPROVEMENT = "collaboration_improvement"


# ============================================================================
# Core Data Models
# ============================================================================

class MessageMetadata(BaseModel):
    """Comprehensive message metadata"""
    
    # Identification
    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    thread_id: Optional[UUID] = None
    
    # Routing & Delivery
    sender_id: str = Field(..., description="Sending agent identifier")
    sender_role: AgentRole = Field(..., description="Sending agent role")
    recipient_id: Optional[str] = None
    recipient_role: Optional[AgentRole] = None
    recipients: Optional[List[str]] = Field(default_factory=list)
    delivery_mode: DeliveryMode = DeliveryMode.DIRECT
    
    # Message Properties
    message_type: MessageType = Field(..., description="Type of message")
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Processing
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_duration_ms: Optional[float] = None
    
    # Learning Context
    learning_context: Optional[LearningContext] = None
    requires_feedback: bool = False
    feedback_timeout: Optional[datetime] = None
    
    # Security & Compliance
    security_level: str = "standard"
    requires_audit: bool = False
    encryption_required: bool = False
    
    # Performance Tracking
    message_size_bytes: Optional[int] = None
    serialization_time_ms: Optional[float] = None
    network_latency_ms: Optional[float] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    
    @validator('expires_at')
    def validate_expiration(cls, v, values):
        if v and 'timestamp' in values and v <= values['timestamp']:
            raise ValueError("Expiration time must be after timestamp")
        return v
    
    @validator('recipients')
    def validate_recipients(cls, v, values):
        delivery_mode = values.get('delivery_mode')
        if delivery_mode in [DeliveryMode.MULTICAST, DeliveryMode.BROADCAST] and not v:
            raise ValueError(f"Recipients required for {delivery_mode} delivery")
        return v
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        return self.expires_at is not None and datetime.utcnow() > self.expires_at
    
    def calculate_age(self) -> timedelta:
        """Calculate message age"""
        return datetime.utcnow() - self.timestamp
    
    def generate_hash(self) -> str:
        """Generate unique hash for message deduplication"""
        content = f"{self.sender_id}:{self.message_type}:{self.timestamp.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class MessagePayload(BaseModel):
    """Base message payload with common fields"""
    
    # Core Content
    content: Dict[str, Any] = Field(default_factory=dict)
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Context Information
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    session_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Error Handling
    error: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)
    
    # Learning Integration
    learning_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    performance_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Attachments & References
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    
    # Validation & Schema
    schema_version: str = "1.0"
    payload_type: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow additional fields for extensibility
    
    def add_attachment(self, name: str, content: Any, content_type: str = "application/json"):
        """Add attachment to message"""
        attachment = {
            "name": name,
            "content": content,
            "content_type": content_type,
            "size": len(str(content)),
            "timestamp": datetime.utcnow().isoformat()
        }
        self.attachments.append(attachment)
    
    def add_reference(self, reference: str):
        """Add reference to message"""
        if reference not in self.references:
            self.references.append(reference)
    
    def get_size_estimate(self) -> int:
        """Estimate payload size in bytes"""
        try:
            return len(json.dumps(self.dict(), default=str))
        except:
            return 0


# ============================================================================
# Specialized Message Payloads
# ============================================================================

class TaskAssignmentPayload(MessagePayload):
    """Payload for task assignment messages"""
    
    task_id: UUID = Field(default_factory=uuid4)
    task_type: str = Field(..., description="Type of task to be executed")
    task_name: str = Field(..., description="Human-readable task name")
    task_description: str = Field(..., description="Detailed task description")
    
    # Task Requirements
    required_capabilities: List[str] = Field(default_factory=list)
    resource_requirements: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    
    # Execution Parameters
    execution_parameters: Dict[str, Any] = Field(default_factory=dict)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    expected_output: Optional[Dict[str, Any]] = None
    
    # Timing & Dependencies
    deadline: Optional[datetime] = None
    estimated_duration: Optional[timedelta] = None
    dependencies: List[UUID] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    
    # Quality & Success Criteria
    success_criteria: List[str] = Field(default_factory=list)
    quality_thresholds: Dict[str, float] = Field(default_factory=dict)
    validation_rules: List[str] = Field(default_factory=list)
    
    # Learning Integration
    learning_objectives: List[str] = Field(default_factory=list)
    feedback_requirements: List[str] = Field(default_factory=list)


class TaskUpdatePayload(MessagePayload):
    """Payload for task update messages"""
    
    task_id: UUID = Field(..., description="Task being updated")
    update_type: Literal["progress", "status", "data", "error", "completion"] = Field(...)
    
    # Progress Information
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    current_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    remaining_steps: List[str] = Field(default_factory=list)
    
    # Status Updates
    new_status: Optional[str] = None
    status_reason: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    
    # Data Updates
    intermediate_results: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    generated_artifacts: List[str] = Field(default_factory=list)
    
    # Performance Metrics
    execution_time: Optional[float] = None
    resource_usage: Optional[Dict[str, float]] = None
    quality_scores: Optional[Dict[str, float]] = None
    
    # Learning Data
    lessons_learned: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)


class LearningUpdatePayload(MessagePayload):
    """Payload for learning update messages"""
    
    learning_type: LearningContext = Field(..., description="Type of learning update")
    learning_source: str = Field(..., description="Source of learning data")
    
    # Learning Content
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    patterns: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_updates: Dict[str, Any] = Field(default_factory=dict)
    
    # Performance Data
    performance_improvements: Dict[str, float] = Field(default_factory=dict)
    efficiency_gains: Dict[str, float] = Field(default_factory=dict)
    error_reductions: Dict[str, int] = Field(default_factory=dict)
    
    # Model Updates
    model_updates: Optional[Dict[str, Any]] = None
    parameter_adjustments: Optional[Dict[str, float]] = None
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    
    # Validation & Quality
    validation_results: Optional[Dict[str, Any]] = None
    quality_metrics: Dict[str, float] = Field(default_factory=dict)
    reliability_score: Optional[float] = None
    
    # Applicability
    applicable_agents: List[str] = Field(default_factory=list)
    applicable_contexts: List[str] = Field(default_factory=list)
    learning_weight: float = Field(1.0, ge=0, le=1)


class WorkflowStepPayload(MessagePayload):
    """Payload for workflow step messages"""
    
    workflow_id: UUID = Field(..., description="Workflow identifier")
    step_id: UUID = Field(default_factory=uuid4)
    step_name: str = Field(..., description="Step name")
    step_type: str = Field(..., description="Type of workflow step")
    
    # Step Configuration
    step_config: Dict[str, Any] = Field(default_factory=dict)
    input_mappings: Dict[str, str] = Field(default_factory=dict)
    output_mappings: Dict[str, str] = Field(default_factory=dict)
    
    # Execution Context
    execution_context: Dict[str, Any] = Field(default_factory=dict)
    workflow_data: Dict[str, Any] = Field(default_factory=dict)
    shared_state: Dict[str, Any] = Field(default_factory=dict)
    
    # Flow Control
    next_steps: List[str] = Field(default_factory=list)
    conditional_logic: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None
    
    # Quality & Monitoring
    quality_gates: List[str] = Field(default_factory=list)
    monitoring_points: List[str] = Field(default_factory=list)
    success_conditions: List[str] = Field(default_factory=list)


class DataSharePayload(MessagePayload):
    """Payload for data sharing messages"""
    
    data_type: str = Field(..., description="Type of data being shared")
    data_format: str = Field(..., description="Format of the data")
    data_source: str = Field(..., description="Source of the data")
    
    # Data Content
    shared_data: Dict[str, Any] = Field(..., description="The actual data")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    data_schema: Optional[Dict[str, Any]] = None
    
    # Data Properties
    data_size: Optional[int] = None
    compression_used: bool = False
    encryption_used: bool = False
    checksum: Optional[str] = None
    
    # Access Control
    access_permissions: List[str] = Field(default_factory=list)
    usage_restrictions: List[str] = Field(default_factory=list)
    expiry_time: Optional[datetime] = None
    
    # Quality & Lineage
    data_quality_score: Optional[float] = None
    data_lineage: List[str] = Field(default_factory=list)
    transformation_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Learning Value
    learning_potential: Optional[float] = None
    knowledge_category: Optional[str] = None


class SecurityAlertPayload(MessagePayload):
    """Payload for security alert messages"""
    
    alert_type: str = Field(..., description="Type of security alert")
    severity_level: Literal["low", "medium", "high", "critical"] = Field(...)
    alert_source: str = Field(..., description="Source of the security alert")
    
    # Alert Details
    threat_description: str = Field(..., description="Description of the threat")
    affected_components: List[str] = Field(default_factory=list)
    potential_impact: str = Field(..., description="Potential impact description")
    
    # Evidence & Analysis
    evidence: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    vulnerability_details: Optional[Dict[str, Any]] = None
    
    # Response Information
    recommended_actions: List[str] = Field(default_factory=list)
    immediate_steps: List[str] = Field(default_factory=list)
    mitigation_strategies: List[str] = Field(default_factory=list)
    
    # Compliance & Reporting
    compliance_implications: List[str] = Field(default_factory=list)
    reporting_requirements: List[str] = Field(default_factory=list)
    incident_id: Optional[UUID] = None


# ============================================================================
# Main Agent Message Model
# ============================================================================

class AgentMessage(BaseModel):
    """
    Complete agent message model for enterprise multi-agent communication
    """
    
    # Core Components
    metadata: MessageMetadata = Field(..., description="Message metadata and routing info")
    payload: MessagePayload = Field(..., description="Message content and data")
    
    # Message Chain & Threading
    reply_to: Optional[UUID] = None
    forwarded_from: Optional[UUID] = None
    message_chain: List[UUID] = Field(default_factory=list)
    
    # Processing State
    processing_history: List[Dict[str, Any]] = Field(default_factory=list)
    acknowledgments: List[Dict[str, Any]] = Field(default_factory=list)
    delivery_confirmations: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Learning Integration
    learning_weight: float = Field(1.0, ge=0, le=1, description="Weight for learning algorithms")
    feedback_collected: bool = False
    learning_outcomes: Optional[Dict[str, Any]] = None
    
    # Quality & Performance
    quality_score: Optional[float] = Field(None, ge=0, le=1)
    processing_efficiency: Optional[float] = None
    success_indicators: Dict[str, bool] = Field(default_factory=dict)
    
    # Audit Trail
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    version: int = 1
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            timedelta: lambda v: v.total_seconds()
        }
    
    @root_validator
    def validate_message_consistency(cls, values):
        """Validate message consistency and requirements"""
        metadata = values.get('metadata')
        payload = values.get('payload')
        
        if not metadata or not payload:
            return values
        
        # Validate payload type matches message type
        message_type = metadata.message_type
        payload_type = payload.payload_type
        
        if payload_type and not cls._is_payload_compatible(message_type, payload_type):
            raise ValueError(f"Payload type {payload_type} incompatible with message type {message_type}")
        
        # Validate learning requirements
        if metadata.requires_feedback and not metadata.feedback_timeout:
            metadata.feedback_timeout = datetime.utcnow() + timedelta(minutes=30)
        
        return values
    
    @staticmethod
    def _is_payload_compatible(message_type: MessageType, payload_type: str) -> bool:
        """Check if payload type is compatible with message type"""
        compatibility_map = {
            MessageType.TASK_ASSIGNMENT: ["TaskAssignmentPayload", "MessagePayload"],
            MessageType.TASK_UPDATE: ["TaskUpdatePayload", "MessagePayload"],
            MessageType.LEARNING_UPDATE: ["LearningUpdatePayload", "MessagePayload"],
            MessageType.WORKFLOW_STEP: ["WorkflowStepPayload", "MessagePayload"],
            MessageType.DATA_SHARE: ["DataSharePayload", "MessagePayload"],
            MessageType.SECURITY_ALERT: ["SecurityAlertPayload", "MessagePayload"]
        }
        
        compatible_types = compatibility_map.get(message_type, ["MessagePayload"])
        return payload_type in compatible_types
    
    def add_to_chain(self, message_id: UUID):
        """Add message to the processing chain"""
        if message_id not in self.message_chain:
            self.message_chain.append(message_id)
    
    def add_processing_record(self, agent_id: str, action: str, result: str, duration_ms: float):
        """Add processing record to history"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "action": action,
            "result": result,
            "duration_ms": duration_ms,
            "memory_usage": None,  # Could be populated by monitoring
            "cpu_usage": None
        }
        self.processing_history.append(record)
    
    def add_acknowledgment(self, agent_id: str, status: str = "received"):
        """Add acknowledgment from an agent"""
        ack = {
            "agent_id": agent_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "processing_started": status == "processing"
        }
        self.acknowledgments.append(ack)
    
    def add_audit_entry(self, action: str, details: Dict[str, Any], agent_id: Optional[str] = None):
        """Add entry to audit trail"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details,
            "agent_id": agent_id,
            "message_version": self.version
        }
        self.audit_trail.append(entry)
    
    def mark_as_processed(self, result: Optional[Dict[str, Any]] = None):
        """Mark message as successfully processed"""
        self.metadata.status = MessageStatus.PROCESSED
        self.metadata.processing_completed_at = datetime.utcnow()
        
        if self.metadata.processing_started_at:
            duration = self.metadata.processing_completed_at - self.metadata.processing_started_at
            self.metadata.processing_duration_ms = duration.total_seconds() * 1000
        
        if result:
            self.payload.data.update(result)
        
        self.add_audit_entry("message_processed", {"status": "success"})
    
    def mark_as_failed(self, error: str, details: Optional[Dict[str, Any]] = None):
        """Mark message as failed"""
        self.metadata.status = MessageStatus.FAILED
        self.payload.error = {
            "message": error,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": self.metadata.retry_count
        }
        
        self.add_audit_entry("message_failed", {"error": error, "details": details})
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return (
            self.metadata.status == MessageStatus.FAILED and
            self.metadata.retry_count < self.metadata.max_retries and
            not self.metadata.is_expired()
        )
    
    def prepare_retry(self):
        """Prepare message for retry"""
        if self.can_retry():
            self.metadata.retry_count += 1
            self.metadata.status = MessageStatus.PENDING
            self.metadata.processing_started_at = None
            self.metadata.processing_completed_at = None
            self.add_audit_entry("retry_prepared", {"retry_count": self.metadata.retry_count})
    
    def get_learning_data(self) -> Dict[str, Any]:
        """Extract learning-relevant data from the message"""
        learning_data = {
            "message_type": self.metadata.message_type,
            "agent_roles": [self.metadata.sender_role],
            "processing_duration": self.metadata.processing_duration_ms,
            "success": self.metadata.status == MessageStatus.PROCESSED,
            "retry_count": self.metadata.retry_count,
            "quality_score": self.quality_score,
            "learning_context": self.metadata.learning_context,
            "learning_weight": self.learning_weight
        }
        
        # Add recipient roles
        if self.metadata.recipient_role:
            learning_data["agent_roles"].append(self.metadata.recipient_role)
        
        # Add performance metrics
        if self.payload.performance_metrics:
            learning_data.update(self.payload.performance_metrics)
        
        # Add specific learning data from payload
        if hasattr(self.payload, 'learning_data') and self.payload.learning_data:
            learning_data["payload_learning"] = self.payload.learning_data
        
        return learning_data
    
    def calculate_message_hash(self) -> str:
        """Calculate unique hash for message deduplication"""
        return self.metadata.generate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization"""
        return self.dict(exclude_none=True, by_alias=True)
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return self.json(exclude_none=True, by_alias=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create message from dictionary"""
        return cls.parse_obj(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        """Create message from JSON string"""
        return cls.parse_raw(json_str)


# ============================================================================
# Message Builder and Factory Classes
# ============================================================================

class MessageBuilder:
    """Builder class for creating complex agent messages"""
    
    def __init__(self, sender_id: str, sender_role: AgentRole):
        self.metadata = MessageMetadata(sender_id=sender_id, sender_role=sender_role)
        self.payload = MessagePayload()
        self._message_attributes = {}
    
    def message_type(self, msg_type: MessageType) -> "MessageBuilder":
        self.metadata.message_type = msg_type
        return self
    
    def to(self, recipient_id: str, recipient_role: Optional[AgentRole] = None) -> "MessageBuilder":
        self.metadata.recipient_id = recipient_id
        if recipient_role:
            self.metadata.recipient_role = recipient_role
        return self
    
    def multicast_to(self, recipients: List[str]) -> "MessageBuilder":
        self.metadata.recipients = recipients
        self.metadata.delivery_mode = DeliveryMode.MULTICAST
        return self
    
    def broadcast(self) -> "MessageBuilder":
        self.metadata.delivery_mode = DeliveryMode.BROADCAST
        return self
    
    def priority(self, priority: MessagePriority) -> "MessageBuilder":
        self.metadata.priority = priority
        return self
    
    def expires_in(self, minutes: int) -> "MessageBuilder":
        self.metadata.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        return self
    
    def correlation_id(self, corr_id: UUID) -> "MessageBuilder":
        self.metadata.correlation_id = corr_id
        return self
    
    def reply_to(self, message_id: UUID) -> "MessageBuilder":
        self._message_attributes['reply_to'] = message_id
        return self
    
    def content(self, content: Dict[str, Any]) -> "MessageBuilder":
        self.payload.content = content
        return self
    
    def data(self, data: Dict[str, Any]) -> "MessageBuilder":
        self.payload.data = data
        return self
    
    def parameters(self, params: Dict[str, Any]) -> "MessageBuilder":
        self.payload.parameters = params
        return self
    
    def learning_context(self, context: LearningContext) -> "MessageBuilder":
        self.metadata.learning_context = context
        return self
    
    def requires_feedback(self, timeout_minutes: int = 30) -> "MessageBuilder":
        self.metadata.requires_feedback = True
        self.metadata.feedback_timeout = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        return self
    
    def security_level(self, level: str) -> "MessageBuilder":
        self.metadata.security_level = level
        return self
    
    def specialized_payload(self, payload: MessagePayload) -> "MessageBuilder":
        self.payload = payload
        return self
    
    def build(self) -> AgentMessage:
        """Build the final message"""
        message = AgentMessage(
            metadata=self.metadata,
            payload=self.payload,
            **self._message_attributes
        )
        
        # Calculate message size
        message.metadata.message_size_bytes = len(message.to_json())
        
        return message


class MessageFactory:
    """Factory class for creating common message types"""
    
    @staticmethod
    def task_assignment(
        sender_id: str,
        sender_role: AgentRole,
        recipient_id: str,
        task_type: str,
        task_name: str,
        task_description: str,
        **kwargs
    ) -> AgentMessage:
        """Create a task assignment message"""
        
        payload = TaskAssignmentPayload(
            task_type=task_type,
            task_name=task_name,
            task_description=task_description,
            payload_type="TaskAssignmentPayload",
            **{k: v for k, v in kwargs.items() if k in TaskAssignmentPayload.__fields__}
        )
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.TASK_ASSIGNMENT) \
            .to(recipient_id) \
            .specialized_payload(payload) \
            .learning_context(LearningContext.TASK_EXECUTION) \
            .requires_feedback() \
            .build()
    
    @staticmethod
    def learning_update(
        sender_id: str,
        sender_role: AgentRole,
        learning_type: LearningContext,
        learning_source: str,
        insights: List[Dict[str, Any]],
        **kwargs
    ) -> AgentMessage:
        """Create a learning update message"""
        
        payload = LearningUpdatePayload(
            learning_type=learning_type,
            learning_source=learning_source,
            insights=insights,
            payload_type="LearningUpdatePayload",
            **{k: v for k, v in kwargs.items() if k in LearningUpdatePayload.__fields__}
        )
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.LEARNING_UPDATE) \
            .broadcast() \
            .specialized_payload(payload) \
            .learning_context(learning_type) \
            .priority(MessagePriority.HIGH) \
            .build()
    
    @staticmethod
    def workflow_step(
        sender_id: str,
        sender_role: AgentRole,
        recipient_id: str,
        workflow_id: UUID,
        step_name: str,
        step_type: str,
        **kwargs
    ) -> AgentMessage:
        """Create a workflow step message"""
        
        payload = WorkflowStepPayload(
            workflow_id=workflow_id,
            step_name=step_name,
            step_type=step_type,
            payload_type="WorkflowStepPayload",
            **{k: v for k, v in kwargs.items() if k in WorkflowStepPayload.__fields__}
        )
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.WORKFLOW_STEP) \
            .to(recipient_id) \
            .specialized_payload(payload) \
            .learning_context(LearningContext.TASK_EXECUTION) \
            .build()
    
    @staticmethod
    def data_share(
        sender_id: str,
        sender_role: AgentRole,
        recipients: List[str],
        data_type: str,
        data_format: str,
        data_source: str,
        shared_data: Dict[str, Any],
        **kwargs
    ) -> AgentMessage:
        """Create a data sharing message"""
        
        payload = DataSharePayload(
            data_type=data_type,
            data_format=data_format,
            data_source=data_source,
            shared_data=shared_data,
            payload_type="DataSharePayload",
            **{k: v for k, v in kwargs.items() if k in DataSharePayload.__fields__}
        )
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.DATA_SHARE) \
            .multicast_to(recipients) \
            .specialized_payload(payload) \
            .learning_context(LearningContext.KNOWLEDGE_ACQUISITION) \
            .build()
    
    @staticmethod
    def security_alert(
        sender_id: str,
        sender_role: AgentRole,
        alert_type: str,
        severity_level: str,
        alert_source: str,
        threat_description: str,
        potential_impact: str,
        **kwargs
    ) -> AgentMessage:
        """Create a security alert message"""
        
        payload = SecurityAlertPayload(
            alert_type=alert_type,
            severity_level=severity_level,
            alert_source=alert_source,
            threat_description=threat_description,
            potential_impact=potential_impact,
            payload_type="SecurityAlertPayload",
            **{k: v for k, v in kwargs.items() if k in SecurityAlertPayload.__fields__}
        )
        
        priority = MessagePriority.CRITICAL if severity_level == "critical" else MessagePriority.HIGH
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.SECURITY_ALERT) \
            .broadcast() \
            .specialized_payload(payload) \
            .priority(priority) \
            .security_level("high") \
            .build()
    
    @staticmethod
    def simple_request(
        sender_id: str,
        sender_role: AgentRole,
        recipient_id: str,
        request_type: str,
        content: Dict[str, Any],
        **kwargs
    ) -> AgentMessage:
        """Create a simple request message"""
        
        payload = MessagePayload(
            content=content,
            payload_type="MessagePayload"
        )
        payload.content["request_type"] = request_type
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.REQUEST) \
            .to(recipient_id) \
            .specialized_payload(payload) \
            .requires_feedback() \
            .build()
    
    @staticmethod
    def response(
        sender_id: str,
        sender_role: AgentRole,
        recipient_id: str,
        original_message_id: UUID,
        success: bool,
        response_data: Dict[str, Any],
        **kwargs
    ) -> AgentMessage:
        """Create a response message"""
        
        payload = MessagePayload(
            content=response_data,
            payload_type="MessagePayload"
        )
        payload.content["success"] = success
        payload.content["response_type"] = "standard_response"
        
        return MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.RESPONSE) \
            .to(recipient_id) \
            .reply_to(original_message_id) \
            .specialized_payload(payload) \
            .build()
    
    @staticmethod
    def health_check(
        sender_id: str,
        sender_role: AgentRole,
        recipients: Optional[List[str]] = None
    ) -> AgentMessage:
        """Create a health check message"""
        
        payload = MessagePayload(
            content={"check_type": "health_status", "timestamp": datetime.utcnow().isoformat()},
            payload_type="MessagePayload"
        )
        
        builder = MessageBuilder(sender_id, sender_role) \
            .message_type(MessageType.HEALTH_CHECK) \
            .specialized_payload(payload) \
            .expires_in(5)  # Short expiry for health checks
        
        if recipients:
            builder = builder.multicast_to(recipients)
        else:
            builder = builder.broadcast()
        
        return builder.build()


# ============================================================================
# Message Queue and Processing Models
# ============================================================================

class MessageQueue(BaseModel):
    """Model for message queue management"""
    
    queue_name: str = Field(..., description="Name of the message queue")
    queue_type: Literal["fifo", "priority", "delayed", "topic"] = "fifo"
    max_size: int = Field(10000, description="Maximum queue size")
    current_size: int = Field(0, description="Current number of messages")
    
    # Queue Configuration
    priority_enabled: bool = True
    dead_letter_queue: Optional[str] = None
    message_ttl: Optional[int] = None  # Seconds
    max_retries: int = 3
    
    # Performance Metrics
    messages_processed: int = 0
    messages_failed: int = 0
    average_processing_time: float = 0.0
    throughput_per_second: float = 0.0
    
    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: Optional[datetime] = None
    
    def calculate_utilization(self) -> float:
        """Calculate queue utilization percentage"""
        if self.max_size == 0:
            return 0.0
        return (self.current_size / self.max_size) * 100.0
    
    def is_full(self) -> bool:
        """Check if queue is at capacity"""
        return self.current_size >= self.max_size


class MessageBatch(BaseModel):
    """Model for batch message processing"""
    
    batch_id: UUID = Field(default_factory=uuid4)
    messages: List[AgentMessage] = Field(default_factory=list)
    batch_size: int = Field(0, description="Number of messages in batch")
    
    # Processing Configuration
    max_batch_size: int = 100
    processing_timeout: int = 300  # Seconds
    parallel_processing: bool = True
    max_parallel_workers: int = 5
    
    # Status Tracking
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    
    # Results
    successful_messages: List[UUID] = Field(default_factory=list)
    failed_messages: List[UUID] = Field(default_factory=list)
    processing_errors: List[str] = Field(default_factory=list)
    
    # Learning Integration
    learning_data: Dict[str, Any] = Field(default_factory=dict)
    performance_metrics: Dict[str, float] = Field(default_factory=dict)
    
    def add_message(self, message: AgentMessage) -> bool:
        """Add message to batch if there's room"""
        if self.batch_size >= self.max_batch_size:
            return False
        
        self.messages.append(message)
        self.batch_size += 1
        return True
    
    def is_full(self) -> bool:
        """Check if batch is at capacity"""
        return self.batch_size >= self.max_batch_size
    
    def calculate_success_rate(self) -> float:
        """Calculate batch processing success rate"""
        if self.batch_size == 0:
            return 0.0
        return len(self.successful_messages) / self.batch_size
    
    def get_processing_duration(self) -> Optional[float]:
        """Get batch processing duration in seconds"""
        if not self.processing_started_at or not self.processing_completed_at:
            return None
        return (self.processing_completed_at - self.processing_started_at).total_seconds()


class MessagePattern(BaseModel):
    """Model for message pattern detection and analysis"""
    
    pattern_id: UUID = Field(default_factory=uuid4)
    pattern_type: str = Field(..., description="Type of pattern detected")
    pattern_description: str = Field(..., description="Description of the pattern")
    
    # Pattern Characteristics
    message_types: List[MessageType] = Field(default_factory=list)
    agent_roles: List[AgentRole] = Field(default_factory=list)
    frequency: float = Field(0.0, description="Pattern frequency per hour")
    
    # Detection Metrics
    confidence_score: float = Field(0.0, ge=0, le=1)
    sample_size: int = Field(0, description="Number of messages analyzed")
    detection_accuracy: float = Field(0.0, ge=0, le=1)
    
    # Temporal Information
    first_detected: datetime = Field(default_factory=datetime.utcnow)
    last_observed: Optional[datetime] = None
    peak_times: List[str] = Field(default_factory=list)
    
    # Learning Value
    learning_importance: float = Field(0.5, ge=0, le=1)
    optimization_potential: float = Field(0.0, ge=0, le=1)
    
    # Pattern Rules
    conditions: Dict[str, Any] = Field(default_factory=dict)
    triggers: List[str] = Field(default_factory=list)
    expected_outcomes: List[str] = Field(default_factory=list)
    
    def update_observation(self):
        """Update pattern observation timestamp"""
        self.last_observed = datetime.utcnow()
    
    def calculate_age(self) -> timedelta:
        """Calculate pattern age"""
        return datetime.utcnow() - self.first_detected


class MessageAnalytics(BaseModel):
    """Model for message analytics and insights"""
    
    analysis_id: UUID = Field(default_factory=uuid4)
    analysis_period: str = Field(..., description="Time period analyzed")
    analysis_type: str = Field(..., description="Type of analysis performed")
    
    # Volume Metrics
    total_messages: int = 0
    messages_by_type: Dict[str, int] = Field(default_factory=dict)
    messages_by_agent: Dict[str, int] = Field(default_factory=dict)
    messages_by_priority: Dict[str, int] = Field(default_factory=dict)
    
    # Performance Metrics
    average_processing_time: float = 0.0
    median_processing_time: float = 0.0
    processing_time_percentiles: Dict[str, float] = Field(default_factory=dict)
    success_rate: float = 0.0
    error_rate: float = 0.0
    
    # Communication Patterns
    communication_flows: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    peak_communication_times: List[str] = Field(default_factory=list)
    bottleneck_agents: List[str] = Field(default_factory=list)
    
    # Learning Insights
    learning_opportunities: List[Dict[str, Any]] = Field(default_factory=list)
    optimization_suggestions: List[str] = Field(default_factory=list)
    pattern_discoveries: List[str] = Field(default_factory=list)
    
    # Quality Metrics
    message_quality_scores: Dict[str, float] = Field(default_factory=dict)
    feedback_response_rate: float = 0.0
    learning_effectiveness: float = 0.0
    
    # Temporal Analysis
    created_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_duration: Optional[float] = None
    next_analysis_due: Optional[datetime] = None
    
    def add_learning_opportunity(self, opportunity: str, priority: float, details: Dict[str, Any]):
        """Add identified learning opportunity"""
        self.learning_opportunities.append({
            "opportunity": opportunity,
            "priority": priority,
            "details": details,
            "identified_at": datetime.utcnow().isoformat()
        })
    
    def calculate_efficiency_score(self) -> float:
        """Calculate overall communication efficiency score"""
        factors = [
            self.success_rate,
            1.0 - self.error_rate,
            min(1.0, 10.0 / max(1.0, self.average_processing_time)),  # Faster is better
            self.feedback_response_rate,
            self.learning_effectiveness
        ]
        return sum(factors) / len(factors)


# ============================================================================
# Advanced Message Processing Models
# ============================================================================

class MessageRouter(BaseModel):
    """Model for intelligent message routing"""
    
    router_id: str = Field(..., description="Router identifier")
    routing_rules: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Routing Configuration
    load_balancing_enabled: bool = True
    priority_routing: bool = True
    failover_enabled: bool = True
    circuit_breaker_enabled: bool = True
    
    # Performance Tracking
    messages_routed: int = 0
    routing_errors: int = 0
    average_routing_time: float = 0.0
    
    # Agent Load Tracking
    agent_loads: Dict[str, float] = Field(default_factory=dict)
    agent_capacities: Dict[str, int] = Field(default_factory=dict)
    agent_health_scores: Dict[str, float] = Field(default_factory=dict)
    
    # Learning Integration
    routing_optimizations: List[Dict[str, Any]] = Field(default_factory=list)
    learned_patterns: List[str] = Field(default_factory=list)
    
    def add_routing_rule(self, condition: str, target: str, priority: int = 1):
        """Add new routing rule"""
        rule = {
            "condition": condition,
            "target": target,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat(),
            "usage_count": 0,
            "success_rate": 0.0
        }
        self.routing_rules.append(rule)
        self.routing_rules.sort(key=lambda x: x["priority"], reverse=True)
    
    def update_agent_load(self, agent_id: str, load: float):
        """Update agent load information"""
        self.agent_loads[agent_id] = load
    
    def get_least_loaded_agent(self, eligible_agents: List[str]) -> Optional[str]:
        """Get the least loaded eligible agent"""
        if not eligible_agents:
            return None
        
        eligible_loads = {
            agent: self.agent_loads.get(agent, 0.0)
            for agent in eligible_agents
        }
        
        return min(eligible_loads, key=eligible_loads.get)


class MessageTransformer(BaseModel):
    """Model for message transformation and enrichment"""
    
    transformer_id: str = Field(..., description="Transformer identifier")
    transformation_type: str = Field(..., description="Type of transformation")
    
    # Transformation Rules
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    transformation_rules: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Processing Configuration
    validation_enabled: bool = True
    enrichment_enabled: bool = True
    compression_enabled: bool = False
    encryption_enabled: bool = False
    
    # Performance Metrics
    transformations_applied: int = 0
    transformation_errors: int = 0
    average_transformation_time: float = 0.0
    
    # Learning Integration
    learned_transformations: List[Dict[str, Any]] = Field(default_factory=list)
    optimization_suggestions: List[str] = Field(default_factory=list)
    
    def add_transformation_rule(self, rule_name: str, rule_logic: Dict[str, Any]):
        """Add new transformation rule"""
        rule = {
            "name": rule_name,
            "logic": rule_logic,
            "created_at": datetime.utcnow().isoformat(),
            "usage_count": 0,
            "success_rate": 0.0
        }
        self.transformation_rules.append(rule)
    
    def calculate_transformation_efficiency(self) -> float:
        """Calculate transformation efficiency score"""
        if self.transformations_applied == 0:
            return 0.0
        
        success_rate = 1.0 - (self.transformation_errors / self.transformations_applied)
        speed_factor = min(1.0, 100.0 / max(1.0, self.average_transformation_time))
        
        return (success_rate + speed_factor) / 2.0


# ============================================================================
# Export Classes and Constants
# ============================================================================

__all__ = [
    # Enumerations
    "MessageType",
    "MessagePriority", 
    "MessageStatus",
    "AgentRole",
    "DeliveryMode",
    "LearningContext",
    
    # Core Models
    "MessageMetadata",
    "MessagePayload",
    "AgentMessage",
    
    # Specialized Payloads
    "TaskAssignmentPayload",
    "TaskUpdatePayload", 
    "LearningUpdatePayload",
    "WorkflowStepPayload",
    "DataSharePayload",
    "SecurityAlertPayload",
    
    # Builders and Factories
    "MessageBuilder",
    "MessageFactory",
    
    # Queue and Processing
    "MessageQueue",
    "MessageBatch",
    "MessagePattern",
    "MessageAnalytics",
    
    # Advanced Processing
    "MessageRouter",
    "MessageTransformer"
]

# Version information
__version__ = "2.0.0"
__author__ = "YMERA Enterprise Team"
__description__ = "Enterprise-grade agent communication models with learning integration"
        