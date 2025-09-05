"""
YMERA Enterprise Multi-Agent System - Base Schema Definitions
Production-ready Pydantic schemas for core system components
"""

from pydantic import BaseModel, Field, ConfigDict, validator, root_validator
from typing import Any, Dict, List, Optional, Union, Literal, Generic, TypeVar
from datetime import datetime, timezone
from enum import Enum
import uuid
from decimal import Decimal


# Base Configuration
class BaseSchema(BaseModel):
    """Base schema with common configuration for all YMERA schemas"""
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": []
        }
    )


# System Enums
class SystemStatus(str, Enum):
    """System operational status"""
    INITIALIZING = "initializing"
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class HealthStatus(str, Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Environment(str, Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


# Generic Type Variables
T = TypeVar('T')
ResponseT = TypeVar('ResponseT')


# Base Response Models
class APIResponse(BaseSchema, Generic[T]):
    """Generic API response wrapper"""
    
    success: bool = Field(
        description="Indicates if the request was successful"
    )
    message: str = Field(
        description="Human-readable response message"
    )
    data: Optional[T] = Field(
        None,
        description="Response payload data"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response generation timestamp"
    )
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier for tracing"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {},
                "timestamp": "2024-01-20T10:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response wrapper"""
    
    items: List[T] = Field(
        description="List of items for current page"
    )
    total: int = Field(
        ge=0,
        description="Total number of items across all pages"
    )
    page: int = Field(
        ge=1,
        description="Current page number (1-indexed)"
    )
    size: int = Field(
        ge=1,
        le=1000,
        description="Number of items per page"
    )
    pages: int = Field(
        ge=1,
        description="Total number of pages"
    )
    has_next: bool = Field(
        description="Whether there is a next page"
    )
    has_prev: bool = Field(
        description="Whether there is a previous page"
    )
    
    @root_validator
    def validate_pagination(cls, values):
        """Validate pagination consistency"""
        total = values.get('total', 0)
        page = values.get('page', 1)
        size = values.get('size', 10)
        
        if total > 0:
            pages = max(1, (total + size - 1) // size)
            values['pages'] = pages
            values['has_next'] = page < pages
            values['has_prev'] = page > 1
        else:
            values['pages'] = 1
            values['has_next'] = False
            values['has_prev'] = False
            
        return values


class ErrorDetail(BaseSchema):
    """Detailed error information"""
    
    code: str = Field(
        description="Error code identifier"
    )
    message: str = Field(
        description="Human-readable error message"
    )
    field: Optional[str] = Field(
        None,
        description="Field name if validation error"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error context"
    )


class ErrorResponse(BaseSchema):
    """API error response"""
    
    success: bool = Field(
        False,
        description="Always false for error responses"
    )
    error: str = Field(
        description="Error type or category"
    )
    message: str = Field(
        description="Human-readable error message"
    )
    details: Optional[List[ErrorDetail]] = Field(
        None,
        description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error occurrence timestamp"
    )
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "ValidationError",
                "message": "Request validation failed",
                "details": [
                    {
                        "code": "REQUIRED_FIELD",
                        "message": "Field is required",
                        "field": "project_name"
                    }
                ],
                "timestamp": "2024-01-20T10:30:00Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )


# Metrics and Performance
class MetricValue(BaseSchema):
    """Single metric value with metadata"""
    
    name: str = Field(
        description="Metric name identifier"
    )
    value: Union[int, float, Decimal] = Field(
        description="Metric value"
    )
    unit: str = Field(
        description="Measurement unit"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metric collection timestamp"
    )
    tags: Optional[Dict[str, str]] = Field(
        None,
        description="Additional metric tags"
    )


class PerformanceMetrics(BaseSchema):
    """System performance metrics"""
    
    cpu_usage: float = Field(
        ge=0.0,
        le=100.0,
        description="CPU usage percentage"
    )
    memory_usage: float = Field(
        ge=0.0,
        le=100.0,
        description="Memory usage percentage"
    )
    disk_usage: float = Field(
        ge=0.0,
        le=100.0,
        description="Disk usage percentage"
    )
    network_io: Dict[str, float] = Field(
        description="Network I/O metrics (bytes/sec)"
    )
    active_connections: int = Field(
        ge=0,
        description="Number of active connections"
    )
    request_rate: float = Field(
        ge=0.0,
        description="Requests per second"
    )
    response_time_avg: float = Field(
        ge=0.0,
        description="Average response time in milliseconds"
    )
    error_rate: float = Field(
        ge=0.0,
        le=100.0,
        description="Error rate percentage"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "disk_usage": 23.1,
                "network_io": {
                    "bytes_sent": 1024000,
                    "bytes_received": 2048000
                },
                "active_connections": 150,
                "request_rate": 125.5,
                "response_time_avg": 250.3,
                "error_rate": 0.5
            }
        }
    )


# Health Check Models
class ComponentHealth(BaseSchema):
    """Individual component health status"""
    
    name: str = Field(
        description="Component name"
    )
    status: HealthStatus = Field(
        description="Component health status"
    )
    response_time: Optional[float] = Field(
        None,
        ge=0.0,
        description="Component response time in milliseconds"
    )
    last_check: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last health check timestamp"
    )
    message: Optional[str] = Field(
        None,
        description="Additional status message"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed health information"
    )


class SystemHealthResponse(BaseSchema):
    """Comprehensive system health response"""
    
    overall_healthy: bool = Field(
        description="Overall system health status"
    )
    status: HealthStatus = Field(
        description="Aggregated health status"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Health check timestamp"
    )
    uptime: float = Field(
        ge=0.0,
        description="System uptime in seconds"
    )
    version: str = Field(
        description="System version"
    )
    environment: Environment = Field(
        description="Deployment environment"
    )
    components: List[ComponentHealth] = Field(
        description="Individual component health statuses"
    )
    performance: PerformanceMetrics = Field(
        description="Current performance metrics"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_healthy": True,
                "status": "healthy",
                "timestamp": "2024-01-20T10:30:00Z",
                "uptime": 86400.5,
                "version": "2.0.0",
                "environment": "production",
                "components": [
                    {
                        "name": "database",
                        "status": "healthy",
                        "response_time": 15.2,
                        "last_check": "2024-01-20T10:30:00Z",
                        "message": "All database connections healthy"
                    }
                ],
                "performance": {
                    "cpu_usage": 45.2,
                    "memory_usage": 67.8,
                    "disk_usage": 23.1,
                    "network_io": {"bytes_sent": 1024000, "bytes_received": 2048000},
                    "active_connections": 150,
                    "request_rate": 125.5,
                    "response_time_avg": 250.3,
                    "error_rate": 0.5
                }
            }
        }
    )


# Resource Usage Models
class ResourceUsage(BaseSchema):
    """System resource usage information"""
    
    cpu: Dict[str, Union[float, int]] = Field(
        description="CPU usage details"
    )
    memory: Dict[str, Union[float, int]] = Field(
        description="Memory usage details"
    )
    disk: Dict[str, Union[float, int]] = Field(
        description="Disk usage details"
    )
    network: Dict[str, Union[float, int]] = Field(
        description="Network usage details"
    )
    processes: int = Field(
        ge=0,
        description="Number of active processes"
    )
    threads: int = Field(
        ge=0,
        description="Number of active threads"
    )
    file_descriptors: int = Field(
        ge=0,
        description="Number of open file descriptors"
    )


# System Status Models
class SystemStatusResponse(BaseSchema):
    """Comprehensive system status response"""
    
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Status report timestamp"
    )
    system_health: SystemHealthResponse = Field(
        description="Overall system health"
    )
    agent_status: Dict[str, Any] = Field(
        description="Current agent statuses"
    )
    performance_metrics: PerformanceMetrics = Field(
        description="Performance metrics"
    )
    learning_stats: Dict[str, Any] = Field(
        description="Learning engine statistics"
    )
    resource_usage: ResourceUsage = Field(
        description="System resource usage"
    )


# Base Entity Models
class BaseEntity(BaseSchema):
    """Base entity with common fields"""
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique entity identifier"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Entity creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Entity last update timestamp"
    )
    created_by: Optional[str] = Field(
        None,
        description="Entity creator identifier"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional entity metadata"
    )
    
    @validator('updated_at')
    def validate_updated_at(cls, v, values):
        """Ensure updated_at is not before created_at"""
        if v and 'created_at' in values and v < values['created_at']:
            raise ValueError('updated_at cannot be before created_at')
        return v


# Configuration Models
class ConfigurationItem(BaseSchema):
    """Individual configuration item"""
    
    key: str = Field(
        description="Configuration key"
    )
    value: Any = Field(
        description="Configuration value"
    )
    type: str = Field(
        description="Value type"
    )
    description: Optional[str] = Field(
        None,
        description="Configuration description"
    )
    is_sensitive: bool = Field(
        False,
        description="Whether the configuration contains sensitive data"
    )
    environment: Optional[Environment] = Field(
        None,
        description="Environment-specific configuration"
    )
    
    @validator('value', pre=True)
    def mask_sensitive_value(cls, v, values):
        """Mask sensitive configuration values"""
        if values.get('is_sensitive', False) and isinstance(v, str):
            return '*' * min(len(v), 8)
        return v


# Validation Models
class ValidationResult(BaseSchema):
    """Validation result with detailed feedback"""
    
    is_valid: bool = Field(
        description="Whether validation passed"
    )
    score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Validation score (0-1)"
    )
    errors: List[ErrorDetail] = Field(
        default_factory=list,
        description="Validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Validation warnings"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Improvement suggestions"
    )
    validated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Validation timestamp"
    )
    validator_version: Optional[str] = Field(
        None,
        description="Validator version used"
    )


# Timing and Duration Models
class TimingInfo(BaseSchema):
    """Execution timing information"""
    
    start_time: datetime = Field(
        description="Operation start time"
    )
    end_time: Optional[datetime] = Field(
        None,
        description="Operation end time"
    )
    duration_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="Duration in milliseconds"
    )
    
    @root_validator
    def calculate_duration(cls, values):
        """Calculate duration if both times are present"""
        start = values.get('start_time')
        end = values.get('end_time')
        
        if start and end:
            duration = (end - start).total_seconds() * 1000
            values['duration_ms'] = round(duration, 3)
            
        return values


# Sorting and Filtering
class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


class SortField(BaseSchema):
    """Sort field specification"""
    
    field: str = Field(
        description="Field name to sort by"
    )
    order: SortOrder = Field(
        SortOrder.ASC,
        description="Sort order"
    )


class FilterOperator(str, Enum):
    """Filter operator options"""
    EQ = "eq"          # Equal
    NE = "ne"          # Not equal
    GT = "gt"          # Greater than
    GTE = "gte"        # Greater than or equal
    LT = "lt"          # Less than
    LTE = "lte"        # Less than or equal
    IN = "in"          # In list
    NOT_IN = "not_in"  # Not in list
    CONTAINS = "contains"      # Contains substring
    STARTS_WITH = "starts_with" # Starts with
    ENDS_WITH = "ends_with"    # Ends with


class FilterCondition(BaseSchema):
    """Filter condition specification"""
    
    field: str = Field(
        description="Field name to filter by"
    )
    operator: FilterOperator = Field(
        description="Filter operator"
    )
    value: Any = Field(
        description="Filter value"
    )
    case_sensitive: bool = Field(
        True,
        description="Whether string comparison is case sensitive"
    )