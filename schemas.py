"""
YMERA Enterprise Multi-Agent System - Complete Pydantic Schemas
Production-ready schemas for enterprise multi-agent workflow automation
"""

# ============================================================================
# File: ymera_api/schemas/communication.py
# ============================================================================

from pydantic import BaseModel, Field, validator, root_validator
from typing import Any, Dict, List, Optional, Union, Literal
from datetime import datetime, timezone
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


class MessageType(str, Enum):
    """Message types for agent communication"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    NOTIFICATION = "notification"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    BROADCAST = "broadcast"


class MessagePriority(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class MessageStatus(str, Enum):
    """Message delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EXPIRED = "expired"


class CommunicationChannel(str, Enum):
    """Communication channel types"""
    DIRECT = "direct"
    BROADCAST = "broadcast"
    GROUP = "group"
    SYSTEM = "system"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"


class Message(BaseEntity):
    """Inter-agent communication message"""
    
    sender_id: str = Field(
        description="Sender agent or user ID"
    )
    recipient_id: Optional[str] = Field(
        None,
        description="Recipient agent or user ID (null for broadcasts)"
    )
    group_id: Optional[str] = Field(
        None,
        description="Group ID for group messages"
    )
    message_type: MessageType = Field(
        description="Type of message"
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority"
    )
    subject: Optional[str] = Field(
        None,
        description="Message subject"
    )
    content: str = Field(
        description="Message content"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata"
    )
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Message attachments"
    )
    channel: CommunicationChannel = Field(
        default=CommunicationChannel.DIRECT,
        description="Communication channel"
    )
    status: MessageStatus = Field(
        default=MessageStatus.PENDING,
        description="Message status"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Message expiration timestamp"
    )
    requires_response: bool = Field(
        default=False,
        description="Whether message requires a response"
    )
    response_timeout_minutes: Optional[int] = Field(
        None,
        ge=1,
        description="Response timeout in minutes"
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for request-response pairs"
    )
    thread_id: Optional[str] = Field(
        None,
        description="Thread ID for message threading"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Message tags"
    )


class ConversationThread(BaseEntity):
    """Conversation thread for organizing related messages"""
    
    name: str = Field(
        description="Thread name"
    )
    description: Optional[str] = Field(
        None,
        description="Thread description"
    )
    participants: List[str] = Field(
        description="Thread participant IDs"
    )
    owner_id: str = Field(
        description="Thread owner ID"
    )
    is_private: bool = Field(
        default=False,
        description="Whether thread is private"
    )
    is_archived: bool = Field(
        default=False,
        description="Whether thread is archived"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Thread tags"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Thread settings"
    )


class NotificationRule(BaseEntity):
    """Notification routing and filtering rules"""
    
    name: str = Field(
        description="Rule name"
    )
    description: Optional[str] = Field(
        None,
        description="Rule description"
    )
    conditions: List[Dict[str, Any]] = Field(
        description="Notification conditions"
    )
    actions: List[Dict[str, Any]] = Field(
        description="Actions to take when conditions match"
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether rule is enabled"
    )
    priority: int = Field(
        default=0,
        description="Rule execution priority"
    )
    owner_id: str = Field(
        description="Rule owner ID"
    )


# ============================================================================
# File: ymera_api/schemas/monitoring.py
# ============================================================================

from pydantic import BaseModel, Field, validator
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


class MetricType(str, Enum):
    """System metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    RATE = "rate"
    PERCENTAGE = "percentage"
    DURATION = "duration"
    THROUGHPUT = "throughput"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class AlertStatus(str, Enum):
    """Alert status states"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


class HealthStatus(str, Enum):
    """System health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SystemMetric(BaseEntity):
    """System performance metric"""
    
    name: str = Field(
        description="Metric name"
    )
    type: MetricType = Field(
        description="Metric type"
    )
    value: float = Field(
        description="Metric value"
    )
    unit: str = Field(
        description="Metric unit of measurement"
    )
    source: str = Field(
        description="Metric source (agent, system, service)"
    )
    source_id: str = Field(
        description="Source identifier"
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Metric labels/tags"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metric timestamp"
    )
    aggregation_window: Optional[str] = Field(
        None,
        description="Aggregation window (e.g., '1m', '5m', '1h')"
    )


class AlertRule(BaseEntity):
    """System monitoring alert rule"""
    
    name: str = Field(
        description="Alert rule name"
    )
    description: str = Field(
        description="Alert rule description"
    )
    query: str = Field(
        description="Alert query/condition"
    )
    severity: AlertSeverity = Field(
        description="Alert severity"
    )
    threshold: float = Field(
        description="Alert threshold value"
    )
    comparison_operator: str = Field(
        description="Comparison operator (>, <, >=, <=, ==, !=)"
    )
    evaluation_window: str = Field(
        description="Evaluation time window"
    )
    evaluation_interval: str = Field(
        default="1m",
        description="How often to evaluate the rule"
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether alert rule is enabled"
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Alert labels"
    )
    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description="Alert annotations"
    )
    notification_channels: List[str] = Field(
        default_factory=list,
        description="Notification channel IDs"
    )


class Alert(BaseEntity):
    """System alert instance"""
    
    rule_id: str = Field(
        description="Alert rule ID"
    )
    name: str = Field(
        description="Alert name"
    )
    description: str = Field(
        description="Alert description"
    )
    severity: AlertSeverity = Field(
        description="Alert severity"
    )
    status: AlertStatus = Field(
        default=AlertStatus.ACTIVE,
        description="Alert status"
    )
    source: str = Field(
        description="Alert source"
    )
    source_id: str = Field(
        description="Source identifier"
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Alert labels"
    )
    annotations: Dict[str, str] = Field(
        default_factory=dict,
        description="Alert annotations"
    )
    value: float = Field(
        description="Current metric value that triggered alert"
    )
    threshold: float = Field(
        description="Alert threshold"
    )
    fired_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When alert was fired"
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="When alert was resolved"
    )
    acknowledged_at: Optional[datetime] = Field(
        None,
        description="When alert was acknowledged"
    )
    acknowledged_by: Optional[str] = Field(
        None,
        description="Who acknowledged the alert"
    )
    suppressed_until: Optional[datetime] = Field(
        None,
        description="Alert suppression end time"
    )


class HealthCheck(BaseEntity):
    """System component health check"""
    
    component: str = Field(
        description="Component name"
    )
    component_id: str = Field(
        description="Component identifier"
    )
    status: HealthStatus = Field(
        description="Health status"
    )
    message: Optional[str] = Field(
        None,
        description="Health check message"
    )
    last_check: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last health check timestamp"
    )
    response_time_ms: Optional[float] = Field(
        None,
        ge=0,
        description="Health check response time in milliseconds"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional health check details"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Component dependencies"
    )


class SystemDashboard(BaseEntity):
    """System monitoring dashboard configuration"""
    
    name: str = Field(
        description="Dashboard name"
    )
    description: Optional[str] = Field(
        None,
        description="Dashboard description"
    )
    owner_id: str = Field(
        description="Dashboard owner ID"
    )
    is_public: bool = Field(
        default=False,
        description="Whether dashboard is public"
    )
    widgets: List[Dict[str, Any]] = Field(
        description="Dashboard widgets configuration"
    )
    layout: Dict[str, Any] = Field(
        description="Dashboard layout configuration"
    )
    refresh_interval: int = Field(
        default=60,
        ge=1,
        description="Auto-refresh interval in seconds"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Dashboard tags"
    )


# ============================================================================
# File: ymera_api/schemas/security.py
# ============================================================================

from pydantic import BaseModel, Field, validator, EmailStr
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


class UserRole(str, Enum):
    """User role types"""
    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    GUEST = "guest"


class Permission(str, Enum):
    """System permissions"""
    # Agent permissions
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_EXECUTE = "agent:execute"
    
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_MANAGE = "project:manage"
    
    # Workflow permissions
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_EXECUTE = "workflow:execute"
    
    # Task permissions
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_ASSIGN = "task:assign"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    USER_MANAGE = "user:manage"


class AuthenticationMethod(str, Enum):
    """Authentication methods"""
    PASSWORD = "password"
    TOKEN = "token"
    API_KEY = "api_key"
    OAUTH = "oauth"
    SAML = "saml"
    LDAP = "ldap"
    MULTI_FACTOR = "multi_factor"


class SessionStatus(str, Enum):
    """User session status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


class SecurityEventType(str, Enum):
    """Security event types"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_ACCESS = "system_access"


class User(BaseEntity):
    """System user"""
    
    username: str = Field(
        description="Unique username"
    )
    email: EmailStr = Field(
        description="User email address"
    )
    first_name: str = Field(
        description="User first name"
    )
    last_name: str = Field(
        description="User last name"
    )
    role: UserRole = Field(
        description="User role"
    )
    is_active: bool = Field(
        default=True,
        description="Whether user account is active"
    )
    is_verified: bool = Field(
        default=False,
        description="Whether user email is verified"
    )
    password_hash: Optional[str] = Field(
        None,
        description="Hashed password"
    )
    last_login: Optional[datetime] = Field(
        None,
        description="Last login timestamp"
    )
    login_attempts: int = Field(
        default=0,
        ge=0,
        description="Failed login attempts"
    )
    locked_until: Optional[datetime] = Field(
        None,
        description="Account lock expiration"
    )
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional user metadata"
    )
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format"""
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be 3-50 characters long')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain alphanumeric characters, hyphens, and underscores')
        return v.lower()


class Role(BaseEntity):
    """User role definition"""
    
    name: str = Field(
        description="Role name"
    )
    description: str = Field(
        description="Role description"
    )
    permissions: List[Permission] = Field(
        description="Role permissions"
    )
    is_system_role: bool = Field(
        default=False,
        description="Whether this is a system-defined role"
    )
    parent_role_id: Optional[str] = Field(
        None,
        description="Parent role ID for inheritance"
    )


class ApiKey(BaseEntity):
    """API key for programmatic access"""
    
    name: str = Field(
        description="API key name"
    )
    key_hash: str = Field(
        description="Hashed API key"
    )
    user_id: str = Field(
        description="Owner user ID"
    )
    permissions: List[Permission] = Field(
        description="API key permissions"
    )
    is_active: bool = Field(
        default=True,
        description="Whether API key is active"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="API key expiration"
    )
    last_used: Optional[datetime] = Field(
        None,
        description="Last usage timestamp"
    )
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Usage count"
    )
    rate_limit: Optional[int] = Field(
        None,
        ge=1,
        description="Rate limit per hour"
    )
    allowed_ips: List[str] = Field(
        default_factory=list,
        description="Allowed IP addresses"
    )


class UserSession(BaseEntity):
    """User session tracking"""
    
    user_id: str = Field(
        description="User ID"
    )
    session_token: str = Field(
        description="Session token hash"
    )
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE,
        description="Session status"
    )
    ip_address: Optional[str] = Field(
        None,
        description="Client IP address"
    )
    user_agent: Optional[str] = Field(
        None,
        description="Client user agent"
    )
    login_method: AuthenticationMethod = Field(
        description="Authentication method used"
    )
    expires_at: datetime = Field(
        description="Session expiration time"
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last activity timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional session metadata"
    )


class SecurityEvent(BaseEntity):
    """Security audit event"""
    
    event_type: SecurityEventType = Field(
        description="Security event type"
    )
    user_id: Optional[str] = Field(
        None,
        description="User ID associated with event"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID associated with event"
    )
    ip_address: Optional[str] = Field(
        None,
        description="Client IP address"
    )
    user_agent: Optional[str] = Field(
        None,
        description="Client user agent"
    )
    resource: Optional[str] = Field(
        None,
        description="Resource accessed"
    )
    action: Optional[str] = Field(
        None,
        description="Action performed"
    )
    success: bool = Field(
        description="Whether action was successful"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event details"
    )
    risk_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Risk score (0.0-1.0)"
    )


# ============================================================================
# File: ymera_api/schemas/integration.py
# ============================================================================

from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


class IntegrationType(str, Enum):
    """Integration types"""
    API = "api"
    WEBHOOK = "webhook"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    EMAIL = "email"
    SLACK = "slack"
    MICROSOFT_TEAMS = "microsoft_teams"
    JIRA = "jira"
    GITHUB = "github"
    GITLAB = "gitlab"
    JENKINS = "jenkins"
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    CUSTOM = "custom"


class IntegrationStatus(str, Enum):
    """Integration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    TESTING = "testing"
    DEPRECATED = "deprecated"


class AuthenticationType(str, Enum):
    """Authentication types for integrations"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


class DataFormat(str, Enum):
    """Supported data formats"""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    YAML = "yaml"
    TEXT = "text"
    BINARY = "binary"
    FORM_DATA = "form_data"


class ExternalSystem(BaseEntity):
    """External system integration definition"""
    
    name: str = Field(
        description="System name"
    )
    description: str = Field(
        description="System description"
    )
    type: IntegrationType = Field(
        description="Integration type"
    )
    status: IntegrationStatus = Field(
        default=IntegrationStatus.ACTIVE,
        description="Integration status"
    )
    base_url: Optional[HttpUrl] = Field(
        None,
        description="System base URL"
    )
    authentication: Dict[str, Any] = Field(
        description="Authentication configuration"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Default headers"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default parameters"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Request timeout in seconds"
    )
    retry_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Retry configuration"
    )
    rate_limit: Optional[int] = Field(
        None,
        ge=1,
        description="Rate limit per minute"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="System capabilities"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Integration tags"
    )
    owner_id: str = Field(
        description="Integration owner ID"
    )


class IntegrationEndpoint(BaseEntity):
    """Integration endpoint definition"""
    
    name: str = Field(
        description="Endpoint name"
    )
    description: str = Field(
        description="Endpoint description"
    )
    system_id: str = Field(
        description="External system ID"
    )
    method: str = Field(
        description="HTTP method"
    )
    path: str = Field(
        description="Endpoint path"
    )
    input_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Input data schema"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Output data schema"
    )
    parameters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Endpoint parameters"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Endpoint-specific headers"
    )
    authentication_required: bool = Field(
        default=True,
        description="Whether authentication is required"
    )
    rate_limit: Optional[int] = Field(
        None,
        ge=1,
        description="Endpoint rate limit per minute"
    )
    timeout_seconds: Optional[int] = Field(
        None,
        ge=1,
        description="Endpoint timeout override"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Endpoint tags"
    )


class DataConnector(BaseEntity):
    """Data source/destination connector"""
    
    name: str = Field(
        description="Connector name"
    )
    description: str = Field(
        description="Connector description"
    )
    type: IntegrationType = Field(
        description="Connector type"
    )
    connection_string: str = Field(
        description="Connection configuration"
    )
    authentication: Dict[str, Any] = Field(
        description="Authentication details"
    )
    supported_formats: List[DataFormat] = Field(
        description="Supported data formats"
    )
    schema_definitions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data schema definitions"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Connector settings"
    )
    is_read_only: bool = Field(
        default=False,
        description="Whether connector is read-only"
    )
    batch_size: int = Field(
        default=1000,
        ge=1,
        description="Default batch size for operations"
    )
    status: IntegrationStatus = Field(
        default=IntegrationStatus.ACTIVE,
        description="Connector status"
    )
    owner_id: str = Field(
        description="Connector owner ID"
    )


class WebhookEndpoint(BaseEntity):
    """Webhook endpoint configuration"""
    
    name: str = Field(
        description="Webhook name"
    )
    description: str = Field(
        description="Webhook description"
    )
    url: HttpUrl = Field(
        description="Webhook URL"
    )
    secret: Optional[str] = Field(
        None,
        description="Webhook secret for validation"
    )
    events: List[str] = Field(
        description="Events that trigger this webhook"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Headers to send with webhook"
    )
    payload_template: Optional[str] = Field(
        None,
        description="Payload template"
    )
    is_active: bool = Field(
        default=True,
        description="Whether webhook is active"
    )
    retry_attempts: int = Field(
        default=3,
        ge=0,
        description="Number of retry attempts"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Request timeout"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event filters"
    )
    owner_id: str = Field(
        description="Webhook owner ID"
    )


class IntegrationLog(BaseEntity):
    """Integration activity log"""
    
    integration_id: str = Field(
        description="Integration ID"
    )
    endpoint_id: Optional[str] = Field(
        None,
        description="Endpoint ID if applicable"
    )
    operation: str = Field(
        description="Operation performed"
    )
    method: Optional[str] = Field(
        None,
        description="HTTP method"
    )
    url: Optional[str] = Field(
        None,
        description="Request URL"
    )
    request_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Request payload"
    )
    response_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Response data"
    )
    status_code: Optional[int] = Field(
        None,
        description="HTTP status code"
    )
    success: bool = Field(
        description="Whether operation succeeded"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    duration_ms: int = Field(
        ge=0,
        description="Operation duration in milliseconds"
    )
    user_id: Optional[str] = Field(
        None,
        description="User who initiated the operation"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional log metadata"
    )


# ============================================================================
# File: ymera_api/schemas/reporting.py
# ============================================================================

from pydantic import BaseModel, Field, validator
from typing import Any, Dict, List, Optional, Union, Literal
from datetime import datetime, timezone, timedelta, date
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


class ReportType(str, Enum):
    """Report types"""
    DASHBOARD = "dashboard"
    SUMMARY = "summary"
    DETAILED = "detailed"
    ANALYTICS = "analytics"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class ReportFormat(str, Enum):
    """Report output formats"""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    HTML = "html"
    XML = "xml"


class ReportStatus(str, Enum):
    """Report generation status"""
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class ChartType(str, Enum):
    """Chart types for visualizations"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"
    HISTOGRAM = "histogram"
    HEATMAP = "heatmap"
    TABLE = "table"
    GAUGE = "gauge"
    TREEMAP = "treemap"


class AggregationType(str, Enum):
    """Data aggregation types"""
    SUM = "sum"
    COUNT = "count"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    PERCENTILE = "percentile"
    DISTINCT = "distinct"


class ReportTemplate(BaseEntity):
    """Reusable report template"""
    
    name: str = Field(
        description="Template name"
    )
    description: str = Field(
        description="Template description"
    )
    type: ReportType = Field(
        description="Report type"
    )
    category: str = Field(
        description="Report category"
    )
    data_sources: List[Dict[str, Any]] = Field(
        description="Data source configurations"
    )
    parameters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Report parameters"
    )
    filters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Default filters"
    )
    visualizations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chart and visualization configs"
    )
    layout: Dict[str, Any] = Field(
        description="Report layout configuration"
    )
    styling: Dict[str, Any] = Field(
        default_factory=dict,
        description="Report styling options"
    )
    is_public: bool = Field(
        default=False,
        description="Whether template is publicly available"
    )
    owner_id: str = Field(
        description="Template owner ID"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Template tags"
    )
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Number of times template was used"
    )


class Report(BaseEntity):
    """Generated report instance"""
    
    name: str = Field(
        description="Report name"
    )
    description: Optional[str] = Field(
        None,
        description="Report description"
    )
    template_id: Optional[str] = Field(
        None,
        description="Source template ID"
    )
    type: ReportType = Field(
        description="Report type"
    )
    status: ReportStatus = Field(
        default=ReportStatus.DRAFT,
        description="Report status"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Report parameters"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Applied filters"
    )
    date_range: Dict[str, datetime] = Field(
        description="Report date range"
    )
    generated_at: Optional[datetime] = Field(
        None,
        description="Report generation timestamp"
    )
    generated_by: str = Field(
        description="User who generated the report"
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Report data"
    )
    visualizations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Report visualizations"
    )
    file_paths: Dict[str, str] = Field(
        default_factory=dict,
        description="Generated file paths by format"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if generation failed"
    )
    size_bytes: Optional[int] = Field(
        None,
        ge=0,
        description="Report size in bytes"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Report expiration timestamp"
    )
    is_cached: bool = Field(
        default=False,
        description="Whether report data is cached"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Report tags"
    )
    
    @validator('date_range')
    def validate_date_range(cls, v):
        """Validate date range"""
        if 'start' not in v or 'end' not in v:
            raise ValueError('Date range must include start and end dates')
        if v['start'] >= v['end']:
            raise ValueError('Start date must be before end date')
        return v


class ReportSchedule(BaseEntity):
    """Scheduled report configuration"""
    
    name: str = Field(
        description="Schedule name"
    )
    description: Optional[str] = Field(
        None,
        description="Schedule description"
    )
    template_id: str = Field(
        description="Report template ID"
    )
    cron_expression: str = Field(
        description="Cron schedule expression"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Report parameters"
    )
    output_formats: List[ReportFormat] = Field(
        description="Output formats to generate"
    )
    recipients: List[str] = Field(
        default_factory=list,
        description="Report recipients"
    )
    delivery_method: str = Field(
        default="email",
        description="Report delivery method"
    )
    is_active: bool = Field(
        default=True,
        description="Whether schedule is active"
    )
    timezone: str = Field(
        default="UTC",
        description="Schedule timezone"
    )
    next_run: Optional[datetime] = Field(
        None,
        description="Next scheduled run"
    )
    last_run: Optional[datetime] = Field(
        None,
        description="Last run timestamp"
    )
    last_success: Optional[datetime] = Field(
        None,
        description="Last successful run"
    )
    failure_count: int = Field(
        default=0,
        ge=0,
        description="Consecutive failure count"
    )
    max_failures: int = Field(
        default=3,
        ge=1,
        description="Max failures before disabling"
    )
    owner_id: str = Field(
        description="Schedule owner ID"
    )


class Dashboard(BaseEntity):
    """Interactive dashboard configuration"""
    
    name: str = Field(
        description="Dashboard name"
    )
    description: Optional[str] = Field(
        None,
        description="Dashboard description"
    )
    category: str = Field(
        description="Dashboard category"
    )
    widgets: List[Dict[str, Any]] = Field(
        description="Dashboard widgets"
    )
    layout: Dict[str, Any] = Field(
        description="Dashboard layout"
    )
    filters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Global dashboard filters"
    )
    refresh_interval: int = Field(
        default=300,
        ge=30,
        description="Auto-refresh interval in seconds"
    )
    is_public: bool = Field(
        default=False,
        description="Whether dashboard is public"
    )
    is_real_time: bool = Field(
        default=False,
        description="Whether dashboard uses real-time data"
    )
    permissions: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Dashboard permissions"
    )
    owner_id: str = Field(
        description="Dashboard owner ID"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Dashboard tags"
    )
    view_count: int = Field(
        default=0,
        ge=0,
        description="Dashboard view count"
    )
    last_viewed: Optional[datetime] = Field(
        None,
        description="Last view timestamp"
    )


class DataVisualization(BaseEntity):
    """Data visualization configuration"""
    
    name: str = Field(
        description="Visualization name"
    )
    description: Optional[str] = Field(
        None,
        description="Visualization description"
    )
    type: ChartType = Field(
        description="Chart type"
    )
    data_source: Dict[str, Any] = Field(
        description="Data source configuration"
    )
    query: str = Field(
        description="Data query"
    )
    dimensions: List[str] = Field(
        description="Chart dimensions"
    )
    metrics: List[Dict[str, Any]] = Field(
        description="Chart metrics with aggregation"
    )
    filters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Visualization filters"
    )
    styling: Dict[str, Any] = Field(
        default_factory=dict,
        description="Chart styling options"
    )
    interactions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Chart interaction settings"
    )
    cache_duration: int = Field(
        default=300,
        ge=0,
        description="Cache duration in seconds"
    )
    owner_id: str = Field(
        description="Visualization owner ID"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Visualization tags"
    )


class ReportExecution(BaseEntity):
    """Report execution tracking"""
    
    report_id: str = Field(
        description="Report ID"
    )
    schedule_id: Optional[str] = Field(
        None,
        description="Schedule ID if from scheduled run"
    )
    status: ReportStatus = Field(
        description="Execution status"
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Execution start time"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Execution completion time"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution parameters"
    )
    output_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Generated output files"
    )
    row_count: Optional[int] = Field(
        None,
        ge=0,
        description="Number of data rows processed"
    )
    file_size_bytes: Optional[int] = Field(
        None,
        ge=0,
        description="Total output file size"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    execution_time_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Execution time in milliseconds"
    )
    triggered_by: str = Field(
        description="User or system that triggered execution"
    )
    
    def get_duration(self) -> Optional[timedelta]:
        """Get execution duration"""
        if not self.completed_at:
            return None
        return self.completed_at - self.started_at


# ============================================================================
# File: ymera_api/schemas/__init__.py
# ============================================================================

"""
YMERA Enterprise Multi-Agent System - Pydantic Schemas
Production-ready schemas for workflow automation and orchestration
"""

from .base import (
    BaseEntity,
    BaseSchema,
    ValidationResult,
    TimingInfo
)

from .agent import (
    Agent,
    AgentCapability,
    AgentConfiguration,
    AgentExecution,
    AgentStatus,
    AgentType,
    ExecutionResult,
    PerformanceMetrics
)

from .project import (
    Project,
    ProjectMember,
    ProjectPhase,
    ProjectStatus,
    ProjectType,
    ResourceAllocation
)

from .task import (
    Task,
    TaskDependency,
    TaskExecution,
    TaskPriority,
    TaskStatus,
    TaskType,
    Subtask
)

from .workflow import (
    Workflow,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStatus,
    WorkflowTemplate,
    WorkflowTrigger,
    WorkflowVariable,
    StepExecution,
    StepRetryConfig,
    StepStatus,
    StepType,
    WorkflowTriggerType,
    RetryStrategy
)

from .communication import (
    Message,
    ConversationThread,
    NotificationRule,
    MessageType,
    MessagePriority,
    MessageStatus,
    CommunicationChannel
)

from .monitoring import (
    SystemMetric,
    AlertRule,
    Alert,
    HealthCheck,
    SystemDashboard,
    MetricType,
    AlertSeverity,
    AlertStatus,
    HealthStatus
)

from .security import (
    User,
    Role,
    ApiKey,
    UserSession,
    SecurityEvent,
    UserRole,
    Permission,
    AuthenticationMethod,
    SessionStatus,
    SecurityEventType
)

from .integration import (
    ExternalSystem,
    IntegrationEndpoint,
    DataConnector,
    WebhookEndpoint,
    IntegrationLog,
    IntegrationType,
    IntegrationStatus,
    AuthenticationType,
    DataFormat
)

from .reporting import (
    Report,
    ReportTemplate,
    ReportSchedule,
    Dashboard,
    DataVisualization,
    ReportExecution,
    ReportType,
    ReportFormat,
    ReportStatus,
    ChartType,
    AggregationType
)

__all__ = [
    # Base schemas
    "BaseEntity",
    "BaseSchema", 
    "ValidationResult",
    "TimingInfo",
    
    # Agent schemas
    "Agent",
    "AgentCapability",
    "AgentConfiguration",
    "AgentExecution",
    "AgentStatus",
    "AgentType",
    "ExecutionResult",
    "PerformanceMetrics",
    
    # Project schemas
    "Project",
    "ProjectMember",
    "ProjectPhase",
    "ProjectStatus",
    "ProjectType",
    "ResourceAllocation",
    
    # Task schemas
    "Task",
    "TaskDependency",
    "TaskExecution",
    "TaskPriority",
    "TaskStatus",
    "TaskType",
    "Subtask",
    
    # Workflow schemas
    "Workflow",
    "WorkflowExecution",
    "WorkflowStep",
    "WorkflowStatus",
    "WorkflowTemplate",
    "WorkflowTrigger",
    "WorkflowVariable",
    "StepExecution",
    "StepRetryConfig",
    "StepStatus",
    "StepType",
    "WorkflowTriggerType",
    "RetryStrategy",
    
    # Communication schemas
    "Message",
    "ConversationThread",
    "NotificationRule",
    "MessageType",
    "MessagePriority",
    "MessageStatus",
    "CommunicationChannel",
    
    # Monitoring schemas
    "SystemMetric",
    "AlertRule",
    "Alert",
    "HealthCheck",
    "SystemDashboard",
    "MetricType",
    "AlertSeverity",
    "AlertStatus",
    "HealthStatus",
    
    # Security schemas
    "User",
    "Role",
    "ApiKey",
    "UserSession",
    "SecurityEvent",
    "UserRole",
    "Permission",
    "AuthenticationMethod",
    "SessionStatus",
    "SecurityEventType",
    
    # Integration schemas
    "ExternalSystem",
    "IntegrationEndpoint",
    "DataConnector",
    "WebhookEndpoint",
    "IntegrationLog",
    "IntegrationType",
    "IntegrationStatus",
    "AuthenticationType",
    "DataFormat",
    
    # Reporting schemas
    "Report",
    "ReportTemplate",
    "ReportSchedule",
    "Dashboard",
    "DataVisualization",
    "ReportExecution",
    "ReportType",
    "ReportFormat",
    "ReportStatus",
    "ChartType",
    "AggregationType",
]