"""
YMERA Enterprise System Metrics Models
Production-Ready Pydantic Models for Comprehensive System Monitoring
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
import uuid


class MetricType(str, Enum):
    """Types of metrics collected by the system"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


class HealthStatus(str, Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    """Agent operational status"""
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    LEARNING = "learning"
    SUSPENDED = "suspended"


class LearningPhase(str, Enum):
    """Learning engine phases"""
    EXPLORATION = "exploration"
    EXPLOITATION = "exploitation"
    ADAPTATION = "adaptation"
    CONSOLIDATION = "consolidation"
    EVALUATION = "evaluation"
    IDLE = "idle"


class SystemComponent(str, Enum):
    """System components for health monitoring"""
    DATABASE = "database"
    REDIS_CACHE = "redis_cache"
    MESSAGE_QUEUE = "message_queue"
    VECTOR_DB = "vector_db"
    AI_SERVICES = "ai_services"
    GITHUB_API = "github_api"
    AGENTS = "agents"
    LEARNING_ENGINE = "learning_engine"
    ORCHESTRATOR = "orchestrator"
    API_GATEWAY = "api_gateway"


# Base Metric Models

class BaseMetric(BaseModel):
    """Base metric model with common fields"""
    metric_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metric_type: MetricType
    name: str = Field(..., description="Metric name")
    value: Union[int, float] = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    tags: Dict[str, str] = Field(default_factory=dict, description="Metric tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CounterMetric(BaseMetric):
    """Counter metric - monotonically increasing value"""
    metric_type: MetricType = Field(default=MetricType.COUNTER, const=True)
    previous_value: Optional[float] = Field(None, description="Previous counter value")
    rate: Optional[float] = Field(None, description="Rate of change per second")

    @validator('value')
    def validate_counter_value(cls, v, values):
        if 'previous_value' in values and values['previous_value'] is not None:
            if v < values['previous_value']:
                raise ValueError("Counter values must be monotonically increasing")
        return v


class GaugeMetric(BaseMetric):
    """Gauge metric - can increase or decrease"""
    metric_type: MetricType = Field(default=MetricType.GAUGE, const=True)
    min_value: Optional[float] = Field(None, description="Minimum recorded value")
    max_value: Optional[float] = Field(None, description="Maximum recorded value")
    trend: Optional[str] = Field(None, description="Trend direction: increasing, decreasing, stable")


class HistogramMetric(BaseMetric):
    """Histogram metric with percentile data"""
    metric_type: MetricType = Field(default=MetricType.HISTOGRAM, const=True)
    buckets: Dict[str, int] = Field(default_factory=dict, description="Histogram buckets")
    percentiles: Dict[str, float] = Field(default_factory=dict, description="Percentile values")
    count: int = Field(..., description="Total number of observations")
    sum: float = Field(..., description="Sum of all observed values")
    
    @validator('percentiles')
    def validate_percentiles(cls, v):
        for percentile in v.keys():
            if not (0 <= float(percentile) <= 100):
                raise ValueError(f"Invalid percentile: {percentile}")
        return v


class TimerMetric(BaseMetric):
    """Timer metric for measuring durations"""
    metric_type: MetricType = Field(default=MetricType.TIMER, const=True)
    duration_ms: float = Field(..., description="Duration in milliseconds")
    operation: str = Field(..., description="Operation being timed")
    success: bool = Field(True, description="Whether operation was successful")


# System Health Models

class ComponentHealth(BaseModel):
    """Health status of individual system component"""
    component: SystemComponent
    status: HealthStatus
    last_check: datetime = Field(default_factory=datetime.utcnow)
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error details if unhealthy")
    details: Dict[str, Any] = Field(default_factory=dict, description="Component-specific health details")
    uptime_seconds: Optional[int] = Field(None, description="Component uptime in seconds")
    
    class Config:
        use_enum_values = True


class SystemHealthMetrics(BaseModel):
    """Comprehensive system health metrics"""
    overall_status: HealthStatus
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    components: List[ComponentHealth] = Field(default_factory=list)
    healthy_components: int = Field(0, description="Number of healthy components")
    total_components: int = Field(0, description="Total number of components")
    uptime_seconds: int = Field(0, description="System uptime in seconds")
    downtime_events: List[Dict[str, Any]] = Field(default_factory=list)
    
    @validator('overall_status', always=True)
    def determine_overall_status(cls, v, values):
        if 'components' in values:
            statuses = [comp.status for comp in values['components']]
            if HealthStatus.CRITICAL in statuses:
                return HealthStatus.CRITICAL
            elif HealthStatus.UNHEALTHY in statuses:
                return HealthStatus.UNHEALTHY
            elif HealthStatus.DEGRADED in statuses:
                return HealthStatus.DEGRADED
            elif all(status == HealthStatus.HEALTHY for status in statuses):
                return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN

    @validator('healthy_components', always=True)
    def count_healthy_components(cls, v, values):
        if 'components' in values:
            return sum(1 for comp in values['components'] if comp.status == HealthStatus.HEALTHY)
        return 0

    @validator('total_components', always=True)
    def count_total_components(cls, v, values):
        if 'components' in values:
            return len(values['components'])
        return 0


# Agent Performance Models

class AgentPerformanceMetrics(BaseModel):
    """Performance metrics for individual agents"""
    agent_id: str = Field(..., description="Unique agent identifier")
    agent_name: str = Field(..., description="Agent name")
    agent_type: str = Field(..., description="Agent type/category")
    status: AgentStatus
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    # Performance metrics
    tasks_completed: int = Field(0, description="Total tasks completed")
    tasks_failed: int = Field(0, description="Total tasks failed")
    success_rate: float = Field(0.0, description="Task success rate (0-1)")
    average_task_duration_ms: float = Field(0.0, description="Average task completion time")
    
    # Resource usage
    cpu_usage_percent: float = Field(0.0, description="CPU usage percentage")
    memory_usage_mb: float = Field(0.0, description="Memory usage in MB")
    active_threads: int = Field(0, description="Number of active threads")
    
    # Learning metrics
    learning_sessions: int = Field(0, description="Number of learning sessions")
    knowledge_items_learned: int = Field(0, description="Knowledge items acquired")
    adaptation_score: float = Field(0.0, description="Adaptation effectiveness score")
    
    # Communication metrics
    messages_sent: int = Field(0, description="Messages sent to other agents")
    messages_received: int = Field(0, description="Messages received from other agents")
    collaboration_score: float = Field(0.0, description="Collaboration effectiveness score")
    
    # Error tracking
    error_count: int = Field(0, description="Number of errors encountered")
    last_error: Optional[str] = Field(None, description="Last error message")
    recovery_count: int = Field(0, description="Number of successful recoveries")
    
    class Config:
        use_enum_values = True

    @validator('success_rate')
    def validate_success_rate(cls, v):
        return max(0.0, min(1.0, v))


class AgentOrchestrationMetrics(BaseModel):
    """Metrics for agent orchestration system"""
    active_workflows: int = Field(0, description="Number of active workflows")
    completed_workflows: int = Field(0, description="Total completed workflows")
    failed_workflows: int = Field(0, description="Total failed workflows")
    average_workflow_duration_ms: float = Field(0.0, description="Average workflow completion time")
    
    # Agent coordination
    agent_coordination_events: int = Field(0, description="Agent coordination events")
    resource_conflicts: int = Field(0, description="Resource conflict events")
    load_balancing_actions: int = Field(0, description="Load balancing actions performed")
    
    # Queue metrics
    pending_tasks: int = Field(0, description="Tasks waiting in queue")
    queue_processing_rate: float = Field(0.0, description="Tasks processed per second")
    average_queue_wait_time_ms: float = Field(0.0, description="Average time tasks spend in queue")


# Learning Engine Models

class LearningEngineMetrics(BaseModel):
    """Comprehensive learning engine performance metrics"""
    current_phase: LearningPhase
    phase_start_time: datetime = Field(default_factory=datetime.utcnow)
    total_learning_sessions: int = Field(0, description="Total learning sessions completed")
    active_learning_sessions: int = Field(0, description="Currently active learning sessions")
    
    # Knowledge metrics
    total_knowledge_items: int = Field(0, description="Total knowledge items in system")
    new_knowledge_items: int = Field(0, description="New knowledge items this period")
    knowledge_quality_score: float = Field(0.0, description="Overall knowledge quality score")
    knowledge_relevance_score: float = Field(0.0, description="Knowledge relevance score")
    
    # Learning performance
    learning_rate: float = Field(0.0, description="Current learning rate")
    convergence_rate: float = Field(0.0, description="Model convergence rate")
    adaptation_speed: float = Field(0.0, description="Speed of adaptation to new patterns")
    
    # Vector database metrics
    vector_embeddings_count: int = Field(0, description="Number of vector embeddings")
    embedding_dimensionality: int = Field(0, description="Embedding vector dimensions")
    similarity_search_avg_time_ms: float = Field(0.0, description="Average similarity search time")
    
    # Feedback processing
    feedback_items_processed: int = Field(0, description="Feedback items processed")
    positive_feedback_ratio: float = Field(0.0, description="Ratio of positive feedback")
    feedback_processing_rate: float = Field(0.0, description="Feedback items per second")
    
    # Model performance
    model_accuracy: float = Field(0.0, description="Current model accuracy")
    model_precision: float = Field(0.0, description="Current model precision")
    model_recall: float = Field(0.0, description="Current model recall")
    model_f1_score: float = Field(0.0, description="Current model F1 score")
    
    class Config:
        use_enum_values = True


# AI Services Models

class AIServiceMetrics(BaseModel):
    """Metrics for AI service providers"""
    provider: str = Field(..., description="AI service provider name")
    model: str = Field(..., description="AI model name")
    
    # Request metrics
    total_requests: int = Field(0, description="Total requests made")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    success_rate: float = Field(0.0, description="Request success rate")
    
    # Performance metrics
    average_response_time_ms: float = Field(0.0, description="Average response time")
    tokens_processed: int = Field(0, description="Total tokens processed")
    tokens_per_second: float = Field(0.0, description="Token processing rate")
    
    # Cost metrics
    estimated_cost_usd: float = Field(0.0, description="Estimated cost in USD")
    cost_per_token: float = Field(0.0, description="Cost per token")
    
    # Rate limiting
    rate_limit_hits: int = Field(0, description="Number of rate limit hits")
    current_quota_usage: float = Field(0.0, description="Current quota usage percentage")
    
    # Error tracking
    timeout_errors: int = Field(0, description="Timeout errors")
    auth_errors: int = Field(0, description="Authentication errors")
    quota_errors: int = Field(0, description="Quota exceeded errors")
    
    @validator('success_rate', always=True)
    def calculate_success_rate(cls, v, values):
        total = values.get('total_requests', 0)
        successful = values.get('successful_requests', 0)
        return successful / total if total > 0 else 0.0


class MultiLLMMetrics(BaseModel):
    """Metrics for multi-LLM management system"""
    primary_provider: str = Field(..., description="Primary LLM provider")
    fallback_providers: List[str] = Field(default_factory=list)
    
    provider_metrics: Dict[str, AIServiceMetrics] = Field(default_factory=dict)
    
    # Load balancing metrics
    load_balancing_decisions: int = Field(0, description="Load balancing decisions made")
    failover_events: int = Field(0, description="Failover events")
    provider_switches: int = Field(0, description="Provider switch events")
    
    # Aggregate performance
    total_requests: int = Field(0, description="Total requests across all providers")
    average_response_time_ms: float = Field(0.0, description="Average response time across providers")
    total_cost_usd: float = Field(0.0, description="Total cost across all providers")
    
    @validator('total_requests', always=True)
    def calculate_total_requests(cls, v, values):
        if 'provider_metrics' in values:
            return sum(metrics.total_requests for metrics in values['provider_metrics'].values())
        return 0

    @validator('total_cost_usd', always=True)
    def calculate_total_cost(cls, v, values):
        if 'provider_metrics' in values:
            return sum(metrics.estimated_cost_usd for metrics in values['provider_metrics'].values())
        return 0.0


# System Resource Models

class SystemResourceMetrics(BaseModel):
    """System resource utilization metrics"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # CPU metrics
    cpu_usage_percent: float = Field(0.0, description="Overall CPU usage percentage")
    cpu_cores: int = Field(0, description="Number of CPU cores")
    cpu_load_average: List[float] = Field(default_factory=list, description="CPU load averages")
    
    # Memory metrics
    memory_total_mb: float = Field(0.0, description="Total memory in MB")
    memory_used_mb: float = Field(0.0, description="Used memory in MB")
    memory_available_mb: float = Field(0.0, description="Available memory in MB")
    memory_usage_percent: float = Field(0.0, description="Memory usage percentage")
    
    # Disk metrics
    disk_total_gb: float = Field(0.0, description="Total disk space in GB")
    disk_used_gb: float = Field(0.0, description="Used disk space in GB")
    disk_available_gb: float = Field(0.0, description="Available disk space in GB")
    disk_usage_percent: float = Field(0.0, description="Disk usage percentage")
    
    # Network metrics
    network_bytes_sent: int = Field(0, description="Network bytes sent")
    network_bytes_received: int = Field(0, description="Network bytes received")
    network_connections: int = Field(0, description="Active network connections")
    
    # Process metrics
    active_processes: int = Field(0, description="Number of active processes")
    thread_count: int = Field(0, description="Total thread count")
    file_descriptors: int = Field(0, description="Open file descriptors")

    @validator('memory_usage_percent', always=True)
    def calculate_memory_usage(cls, v, values):
        total = values.get('memory_total_mb', 0)
        used = values.get('memory_used_mb', 0)
        return (used / total * 100) if total > 0 else 0.0

    @validator('disk_usage_percent', always=True)
    def calculate_disk_usage(cls, v, values):
        total = values.get('disk_total_gb', 0)
        used = values.get('disk_used_gb', 0)
        return (used / total * 100) if total > 0 else 0.0


# Database Performance Models

class DatabaseMetrics(BaseModel):
    """Database performance metrics"""
    connection_pool_size: int = Field(0, description="Connection pool size")
    active_connections: int = Field(0, description="Active connections")
    idle_connections: int = Field(0, description="Idle connections")
    
    # Query performance
    total_queries: int = Field(0, description="Total queries executed")
    slow_queries: int = Field(0, description="Slow queries (above threshold)")
    failed_queries: int = Field(0, description="Failed queries")
    average_query_time_ms: float = Field(0.0, description="Average query execution time")
    
    # Transaction metrics
    transactions_committed: int = Field(0, description="Committed transactions")
    transactions_rolled_back: int = Field(0, description="Rolled back transactions")
    deadlocks: int = Field(0, description="Deadlock occurrences")
    
    # Storage metrics
    database_size_mb: float = Field(0.0, description="Database size in MB")
    index_size_mb: float = Field(0.0, description="Index size in MB")
    table_count: int = Field(0, description="Number of tables")


class RedisMetrics(BaseModel):
    """Redis cache and message queue metrics"""
    # Connection metrics
    connected_clients: int = Field(0, description="Connected clients")
    max_clients: int = Field(0, description="Maximum clients allowed")
    
    # Memory metrics
    used_memory_mb: float = Field(0.0, description="Used memory in MB")
    max_memory_mb: float = Field(0.0, description="Maximum memory in MB")
    memory_fragmentation_ratio: float = Field(0.0, description="Memory fragmentation ratio")
    
    # Operation metrics
    total_commands_processed: int = Field(0, description="Total commands processed")
    commands_per_second: float = Field(0.0, description="Commands processed per second")
    
    # Key metrics
    total_keys: int = Field(0, description="Total number of keys")
    expired_keys: int = Field(0, description="Number of expired keys")
    evicted_keys: int = Field(0, description="Number of evicted keys")
    
    # Message queue specific
    queue_length: int = Field(0, description="Total queue length")
    messages_processed: int = Field(0, description="Messages processed")
    message_processing_rate: float = Field(0.0, description="Messages per second")


# Comprehensive System Metrics

class SystemPerformanceMetrics(BaseModel):
    """Comprehensive system performance metrics"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    collection_duration_ms: float = Field(0.0, description="Time taken to collect metrics")
    
    # System health
    health_metrics: SystemHealthMetrics
    
    # Resource utilization
    resource_metrics: SystemResourceMetrics
    
    # Agent performance
    agent_metrics: List[AgentPerformanceMetrics] = Field(default_factory=list)
    orchestration_metrics: AgentOrchestrationMetrics
    
    # Learning engine
    learning_metrics: LearningEngineMetrics
    
    # AI services
    ai_metrics: MultiLLMMetrics
    
    # Infrastructure
    database_metrics: DatabaseMetrics
    redis_metrics: RedisMetrics
    
    # Custom metrics
    custom_metrics: List[BaseMetric] = Field(default_factory=list)
    
    # Performance summary
    overall_performance_score: float = Field(0.0, description="Overall system performance score (0-100)")
    performance_trends: Dict[str, str] = Field(default_factory=dict, description="Performance trend indicators")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('overall_performance_score', always=True)
    def calculate_performance_score(cls, v, values):
        # Calculate weighted performance score based on various metrics
        score = 0.0
        weights = {
            'health': 0.3,
            'resource': 0.2,
            'agents': 0.2,
            'learning': 0.15,
            'ai_services': 0.15
        }
        
        # Health score (0-100)
        if 'health_metrics' in values:
            health = values['health_metrics']
            health_score = (health.healthy_components / max(health.total_components, 1)) * 100
            score += health_score * weights['health']
        
        # Resource score (inverse of usage percentages)
        if 'resource_metrics' in values:
            resource = values['resource_metrics']
            resource_score = (100 - resource.cpu_usage_percent + 
                            100 - resource.memory_usage_percent + 
                            100 - resource.disk_usage_percent) / 3
            score += resource_score * weights['resource']
        
        # Agent performance score
        if 'agent_metrics' in values and values['agent_metrics']:
            agent_scores = [agent.success_rate * 100 for agent in values['agent_metrics']]
            avg_agent_score = sum(agent_scores) / len(agent_scores) if agent_scores else 0
            score += avg_agent_score * weights['agents']
        
        # Learning effectiveness score
        if 'learning_metrics' in values:
            learning = values['learning_metrics']
            learning_score = (learning.model_accuracy + learning.adaptation_speed * 0.1) * 100
            score += min(learning_score, 100) * weights['learning']
        
        # AI services score
        if 'ai_metrics' in values:
            ai = values['ai_metrics']
            if ai.provider_metrics:
                ai_scores = [metrics.success_rate * 100 for metrics in ai.provider_metrics.values()]
                avg_ai_score = sum(ai_scores) / len(ai_scores) if ai_scores else 0
                score += avg_ai_score * weights['ai_services']
        
        return min(max(score, 0.0), 100.0)


# Metric Collection Models

class MetricCollectionRequest(BaseModel):
    """Request model for metric collection"""
    metric_types: List[MetricType] = Field(default_factory=list, description="Types of metrics to collect")
    components: List[SystemComponent] = Field(default_factory=list, description="Components to collect metrics from")
    agents: List[str] = Field(default_factory=list, description="Specific agents to collect metrics from")
    time_range: Optional[Dict[str, datetime]] = Field(None, description="Time range for historical metrics")
    aggregation: Optional[str] = Field(None, description="Aggregation method: avg, sum, min, max")
    
    class Config:
        use_enum_values = True


class MetricCollectionResponse(BaseModel):
    """Response model for metric collection"""
    collection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    requested_metrics: MetricCollectionRequest
    collected_metrics: SystemPerformanceMetrics
    collection_success: bool = Field(True, description="Whether collection was successful")
    errors: List[str] = Field(default_factory=list, description="Collection errors if any")
    collection_time_ms: float = Field(0.0, description="Time taken to collect metrics")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Alert and Threshold Models

class MetricThreshold(BaseModel):
    """Threshold configuration for metric alerting"""
    metric_name: str = Field(..., description="Name of the metric")
    warning_threshold: float = Field(..., description="Warning threshold value")
    critical_threshold: float = Field(..., description="Critical threshold value")
    comparison_operator: str = Field(..., description="Comparison operator: gt, lt, eq, gte, lte")
    evaluation_window_minutes: int = Field(5, description="Evaluation window in minutes")
    
    @validator('comparison_operator')
    def validate_operator(cls, v):
        valid_operators = ['gt', 'lt', 'eq', 'gte', 'lte', '>', '<', '==', '>=', '<=']
        if v not in valid_operators:
            raise ValueError(f"Invalid comparison operator: {v}")
        return v


class MetricAlert(BaseModel):
    """Metric alert model"""
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metric_name: str = Field(..., description="Name of the metric that triggered alert")
    current_value: float = Field(..., description="Current metric value")
    threshold_value: float = Field(..., description="Threshold that was breached")
    severity: str = Field(..., description="Alert severity: warning, critical")
    message: str = Field(..., description="Alert message")
    component: Optional[SystemComponent] = Field(None, description="Component that triggered alert")
    agent_id: Optional[str] = Field(None, description="Agent ID if agent-specific")
    resolved: bool = Field(False, description="Whether alert has been resolved")
    resolution_timestamp: Optional[datetime] = Field(None, description="When alert was resolved")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Historical Metrics Models

class MetricAggregation(BaseModel):
    """Aggregated metric data over time"""
    metric_name: str = Field(..., description="Name of the metric")
    time_period: str = Field(..., description="Time period: 1m, 5m, 15m, 1h, 6h, 24h")
    start_time: datetime = Field(..., description="Start time of aggregation period")
    end_time: datetime = Field(..., description="End time of aggregation period")
    
    # Statistical aggregations
    count: int = Field(0, description="Number of data points")
    min_value: float = Field(0.0, description="Minimum value in period")
    max_value: float = Field(0.0, description="Maximum value in period")
    avg_value: float = Field(0.0, description="Average value in period")
    sum_value: float = Field(0.0, description="Sum of values in period")
    std_deviation: float = Field(0.0, description="Standard deviation")
    
    # Percentiles
    p50: float = Field(0.0, description="50th percentile")
    p90: float = Field(0.0, description="90th percentile")
    p95: float = Field(0.0, description="95th percentile")
    p99: float = Field(0.0, description="99th percentile")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SystemMetricsHistory(BaseModel):
    """Historical system metrics data"""
    collection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = Field(..., description="Start time of historical data")
    end_time: datetime = Field(..., description="End time of historical data")
    aggregation_period: str = Field(..., description="Aggregation period")
    
    # Aggregated metrics by category
    health_history: List[MetricAggregation] = Field(default_factory=list)
    resource_history: List[MetricAggregation] = Field(default_factory=list)
    agent_history: List[MetricAggregation] = Field(default_factory=list)
    learning_history: List[MetricAggregation] = Field(default_factory=list)
    ai_service_history: List[MetricAggregation] = Field(default_factory=list)
    
    # Summary statistics
    total_data_points: int = Field(0, description="Total number of data points")
    data_completeness: float = Field(0.0, description="Percentage of expected data points collected")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }