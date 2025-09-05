"""
YMERA Enterprise Enhancement Request Model
Production-Ready Pydantic Models with Learning Engine Integration
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Literal, Set
from enum import Enum
from uuid import UUID, uuid4
from pathlib import Path

from pydantic import (
    BaseModel, 
    Field, 
    validator, 
    root_validator,
    HttpUrl,
    EmailStr,
    constr,
    conint,
    confloat,
    Json
)
from pydantic.types import StrictStr, StrictInt, StrictFloat, StrictBool

# Custom validators and utilities
from ymera_core.models.base import (
    TimestampedModel, 
    UUIDModel, 
    ValidatedModel,
    MetadataModel
)
from ymera_core.security.validation import SecurityValidator
from ymera_core.utils.text_processing import TextProcessor
from ymera_core.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    SUPPORTED_FILE_EXTENSIONS,
    PRIORITY_LEVELS,
    ENHANCEMENT_CATEGORIES
)


class EnhancementPriority(str, Enum):
    """Enhancement priority levels with business impact mapping"""
    CRITICAL = "critical"          # System-breaking, immediate attention
    HIGH = "high"                  # Major impact, fix within 24h
    MEDIUM = "medium"             # Moderate impact, fix within 1 week
    LOW = "low"                   # Minor impact, fix when possible
    ENHANCEMENT = "enhancement"   # Nice-to-have improvements


class EnhancementCategory(str, Enum):
    """Comprehensive enhancement categories"""
    PERFORMANCE = "performance"
    SECURITY = "security"
    FUNCTIONALITY = "functionality"
    UI_UX = "ui_ux"
    CODE_QUALITY = "code_quality"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ACCESSIBILITY = "accessibility"
    SCALABILITY = "scalability"
    MAINTAINABILITY = "maintainability"
    INTEGRATION = "integration"
    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"
    COMPLIANCE = "compliance"
    AUTOMATION = "automation"


class EnhancementType(str, Enum):
    """Types of enhancements based on scope and nature"""
    BUG_FIX = "bug_fix"
    FEATURE_REQUEST = "feature_request"
    OPTIMIZATION = "optimization"
    REFACTORING = "refactoring"
    ARCHITECTURE_IMPROVEMENT = "architecture_improvement"
    DEPENDENCY_UPDATE = "dependency_update"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_PATCH = "security_patch"
    PERFORMANCE_TUNING = "performance_tuning"
    CODE_CLEANUP = "code_cleanup"


class EnhancementStatus(str, Enum):
    """Enhancement request lifecycle status"""
    PENDING = "pending"                    # Newly created, awaiting triage
    TRIAGED = "triaged"                   # Reviewed and categorized
    IN_ANALYSIS = "in_analysis"           # Being analyzed by analysis agent
    ANALYSIS_COMPLETE = "analysis_complete" # Analysis finished
    IN_ENHANCEMENT = "in_enhancement"     # Enhancement agent working
    ENHANCEMENT_COMPLETE = "enhancement_complete" # Enhancement finished
    IN_VALIDATION = "in_validation"       # Validation agent testing
    VALIDATION_PASSED = "validation_passed" # Validation successful
    VALIDATION_FAILED = "validation_failed" # Validation failed
    IN_DEPLOYMENT = "in_deployment"       # Deployment in progress
    DEPLOYED = "deployed"                 # Successfully deployed
    CLOSED = "closed"                     # Completed and closed
    CANCELLED = "cancelled"               # Cancelled before completion
    ON_HOLD = "on_hold"                  # Temporarily paused


class LearningFeedbackType(str, Enum):
    """Types of learning feedback for the learning engine"""
    QUALITY_RATING = "quality_rating"
    PERFORMANCE_METRICS = "performance_metrics"
    USER_SATISFACTION = "user_satisfaction"
    BUSINESS_IMPACT = "business_impact"
    TECHNICAL_DEBT_REDUCTION = "technical_debt_reduction"
    CODE_MAINTAINABILITY = "code_maintainability"
    SECURITY_IMPROVEMENT = "security_improvement"
    AGENT_EFFECTIVENESS = "agent_effectiveness"


class ComplexityLevel(str, Enum):
    """Code complexity assessment levels"""
    TRIVIAL = "trivial"      # 1-5 lines, simple changes
    LOW = "low"              # 6-50 lines, straightforward
    MEDIUM = "medium"        # 51-200 lines, moderate complexity
    HIGH = "high"            # 201-500 lines, complex logic
    VERY_HIGH = "very_high"  # 500+ lines, architectural changes


class ImpactLevel(str, Enum):
    """Business and technical impact levels"""
    MINIMAL = "minimal"      # No noticeable impact
    LOW = "low"             # Minor improvements
    MODERATE = "moderate"   # Noticeable improvements
    HIGH = "high"           # Significant improvements
    CRITICAL = "critical"   # Major business/technical benefits


# Core Models
class CodeLocation(BaseModel):
    """Precise code location for enhancements"""
    file_path: Path = Field(..., description="Relative file path from project root")
    start_line: Optional[conint(ge=1)] = Field(None, description="Starting line number")
    end_line: Optional[conint(ge=1)] = Field(None, description="Ending line number")
    function_name: Optional[StrictStr] = Field(None, description="Function/method name")
    class_name: Optional[StrictStr] = Field(None, description="Class name if applicable")
    module_name: Optional[StrictStr] = Field(None, description="Module/namespace")
    
    @validator('file_path')
    def validate_file_path(cls, v):
        """Validate file path format and extension"""
        if not str(v).strip():
            raise ValueError("File path cannot be empty")
        
        # Security check - prevent path traversal
        if '..' in str(v) or str(v).startswith('/'):
            raise ValueError("Invalid file path format")
        
        # Check supported file extensions
        suffix = v.suffix.lower()
        if suffix and suffix not in SUPPORTED_FILE_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {suffix}")
        
        return v
    
    @validator('end_line')
    def validate_line_numbers(cls, v, values):
        """Ensure end_line >= start_line"""
        if v is not None and 'start_line' in values and values['start_line'] is not None:
            if v < values['start_line']:
                raise ValueError("End line must be >= start line")
        return v


class SecurityContext(BaseModel):
    """Security-related context for enhancements"""
    involves_authentication: StrictBool = Field(False, description="Affects auth systems")
    involves_authorization: StrictBool = Field(False, description="Affects permission systems")
    involves_sensitive_data: StrictBool = Field(False, description="Handles sensitive information")
    involves_cryptography: StrictBool = Field(False, description="Uses cryptographic functions")
    involves_network_communication: StrictBool = Field(False, description="Network operations")
    involves_file_operations: StrictBool = Field(False, description="File system operations")
    involves_database_operations: StrictBool = Field(False, description="Database operations")
    security_review_required: StrictBool = Field(False, description="Requires security review")
    compliance_frameworks: List[StrictStr] = Field(default_factory=list, description="Applicable compliance frameworks")
    
    @validator('compliance_frameworks')
    def validate_compliance_frameworks(cls, v):
        """Validate compliance framework names"""
        valid_frameworks = {
            'SOC2', 'PCI-DSS', 'HIPAA', 'GDPR', 'SOX', 'ISO27001', 
            'NIST', 'OWASP', 'CIS', 'FISMA', 'FedRAMP'
        }
        
        for framework in v:
            if framework.upper() not in valid_frameworks:
                raise ValueError(f"Unknown compliance framework: {framework}")
        
        return [f.upper() for f in v]


class PerformanceContext(BaseModel):
    """Performance-related context and metrics"""
    affects_performance: StrictBool = Field(False, description="May impact system performance")
    expected_performance_impact: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description="Expected performance impact direction"
    )
    performance_critical_path: StrictBool = Field(False, description="Affects critical performance path")
    memory_impact_expected: Optional[Literal["increase", "decrease", "neutral"]] = Field(
        None, description="Expected memory usage impact"
    )
    cpu_impact_expected: Optional[Literal["increase", "decrease", "neutral"]] = Field(
        None, description="Expected CPU usage impact"
    )
    io_impact_expected: Optional[Literal["increase", "decrease", "neutral"]] = Field(
        None, description="Expected I/O impact"
    )
    scalability_considerations: List[StrictStr] = Field(
        default_factory=list, description="Scalability factors to consider"
    )
    performance_testing_required: StrictBool = Field(False, description="Requires performance testing")
    benchmark_baseline_required: StrictBool = Field(False, description="Needs baseline measurements")


class TestingContext(BaseModel):
    """Testing requirements and context"""
    unit_tests_required: StrictBool = Field(True, description="Requires unit tests")
    integration_tests_required: StrictBool = Field(False, description="Requires integration tests")
    e2e_tests_required: StrictBool = Field(False, description="Requires end-to-end tests")
    performance_tests_required: StrictBool = Field(False, description="Requires performance tests")
    security_tests_required: StrictBool = Field(False, description="Requires security tests")
    manual_testing_required: StrictBool = Field(False, description="Requires manual testing")
    regression_testing_scope: List[StrictStr] = Field(
        default_factory=list, description="Areas requiring regression testing"
    )
    test_data_requirements: Optional[StrictStr] = Field(
        None, max_length=1000, description="Special test data requirements"
    )
    testing_environment_requirements: List[StrictStr] = Field(
        default_factory=list, description="Special testing environment needs"
    )


class LearningContext(BaseModel):
    """Context for learning engine integration"""
    learning_enabled: StrictBool = Field(True, description="Enable learning from this enhancement")
    feedback_collection_enabled: StrictBool = Field(True, description="Collect feedback for learning")
    pattern_extraction_enabled: StrictBool = Field(True, description="Extract patterns for learning")
    knowledge_update_enabled: StrictBool = Field(True, description="Update knowledge base")
    similar_issues_analysis: StrictBool = Field(True, description="Analyze similar past issues")
    success_pattern_learning: StrictBool = Field(True, description="Learn from successful patterns")
    failure_pattern_learning: StrictBool = Field(True, description="Learn from failure patterns")
    agent_performance_tracking: StrictBool = Field(True, description="Track agent performance")
    
    # Learning tags for categorization
    learning_tags: Set[StrictStr] = Field(default_factory=set, description="Tags for learning categorization")
    knowledge_domains: Set[StrictStr] = Field(default_factory=set, description="Knowledge domains involved")
    skill_areas: Set[StrictStr] = Field(default_factory=set, description="Skill areas for learning")
    
    @validator('learning_tags', 'knowledge_domains', 'skill_areas', pre=True)
    def convert_to_set(cls, v):
        """Convert lists to sets and validate"""
        if isinstance(v, list):
            return set(v)
        return v if isinstance(v, set) else set()


class AgentAssignment(BaseModel):
    """Agent assignment with capabilities and constraints"""
    agent_id: UUID = Field(..., description="Assigned agent UUID")
    agent_type: StrictStr = Field(..., description="Type of agent")
    assignment_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority_level: conint(ge=1, le=10) = Field(5, description="Assignment priority (1=lowest, 10=highest)")
    estimated_effort_hours: Optional[confloat(ge=0.1)] = Field(None, description="Estimated effort in hours")
    max_execution_time_minutes: Optional[conint(ge=1)] = Field(None, description="Maximum execution time")
    required_capabilities: List[StrictStr] = Field(default_factory=list, description="Required agent capabilities")
    constraints: Dict[StrictStr, Any] = Field(default_factory=dict, description="Execution constraints")
    dependencies: List[UUID] = Field(default_factory=list, description="Dependent enhancement UUIDs")
    
    @validator('agent_type')
    def validate_agent_type(cls, v):
        """Validate agent type"""
        valid_types = {
            'analysis', 'enhancement', 'validation', 'documentation', 
            'security', 'deployment', 'monitoring', 'learning',
            'communication', 'examination', 'project_management'
        }
        
        if v not in valid_types:
            raise ValueError(f"Invalid agent type: {v}")
        
        return v


class QualityMetrics(BaseModel):
    """Quality metrics for enhancement tracking"""
    code_quality_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Code quality score (0-10)")
    maintainability_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Maintainability score")
    security_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Security score")
    performance_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Performance score")
    test_coverage_percentage: Optional[confloat(ge=0.0, le=100.0)] = Field(None, description="Test coverage %")
    cyclomatic_complexity: Optional[conint(ge=1)] = Field(None, description="Cyclomatic complexity")
    technical_debt_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Technical debt score")
    documentation_completeness: Optional[confloat(ge=0.0, le=100.0)] = Field(None, description="Documentation %")
    
    # Business metrics
    user_satisfaction_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="User satisfaction")
    business_value_score: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Business value")
    roi_estimate: Optional[confloat(ge=0.0)] = Field(None, description="Estimated ROI")


class LearningFeedback(BaseModel):
    """Feedback data for learning engine"""
    feedback_id: UUID = Field(default_factory=uuid4)
    feedback_type: LearningFeedbackType = Field(..., description="Type of feedback")
    feedback_source: StrictStr = Field(..., description="Source of feedback")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Quantitative feedback
    rating: Optional[confloat(ge=0.0, le=10.0)] = Field(None, description="Numeric rating (0-10)")
    metrics: Dict[StrictStr, Union[StrictFloat, StrictInt, StrictStr]] = Field(
        default_factory=dict, description="Additional metrics"
    )
    
    # Qualitative feedback
    comments: Optional[constr(max_length=2000)] = Field(None, description="Feedback comments")
    suggestions: Optional[constr(max_length=2000)] = Field(None, description="Improvement suggestions")
    
    # Context
    context: Dict[StrictStr, Any] = Field(default_factory=dict, description="Feedback context")
    tags: Set[StrictStr] = Field(default_factory=set, description="Feedback tags")
    
    # Learning impact
    should_update_knowledge: StrictBool = Field(True, description="Should update knowledge base")
    should_update_patterns: StrictBool = Field(True, description="Should update pattern recognition")
    confidence_level: confloat(ge=0.0, le=1.0) = Field(0.8, description="Feedback confidence level")


# Main Enhancement Request Model
class EnhancementRequest(TimestampedModel, UUIDModel, ValidatedModel):
    """
    Comprehensive enhancement request model for YMERA enterprise system
    Integrates with learning engine and multi-agent orchestration
    """
    
    # Basic Information
    title: constr(min_length=5, max_length=MAX_TITLE_LENGTH, strip_whitespace=True) = Field(
        ..., description="Clear, descriptive enhancement title"
    )
    
    description: constr(min_length=10, max_length=MAX_DESCRIPTION_LENGTH, strip_whitespace=True) = Field(
        ..., description="Detailed enhancement description"
    )
    
    # Classification
    category: EnhancementCategory = Field(..., description="Enhancement category")
    enhancement_type: EnhancementType = Field(..., description="Type of enhancement")
    priority: EnhancementPriority = Field(..., description="Enhancement priority level")
    complexity: ComplexityLevel = Field(..., description="Estimated complexity level")
    business_impact: ImpactLevel = Field(..., description="Expected business impact")
    technical_impact: ImpactLevel = Field(..., description="Expected technical impact")
    
    # Status and Workflow
    status: EnhancementStatus = Field(
        default=EnhancementStatus.PENDING, description="Current status"
    )
    
    workflow_stage: StrictStr = Field(
        default="initial", description="Current workflow stage"
    )
    
    # Location and Context
    code_locations: List[CodeLocation] = Field(
        default_factory=list, description="Code locations to enhance"
    )
    
    affected_components: List[StrictStr] = Field(
        default_factory=list, description="Affected system components"
    )
    
    affected_services: List[StrictStr] = Field(
        default_factory=list, description="Affected microservices"
    )
    
    # Enhanced Context Objects
    security_context: SecurityContext = Field(
        default_factory=SecurityContext, description="Security-related context"
    )
    
    performance_context: PerformanceContext = Field(
        default_factory=PerformanceContext, description="Performance-related context"
    )
    
    testing_context: TestingContext = Field(
        default_factory=TestingContext, description="Testing requirements and context"
    )
    
    learning_context: LearningContext = Field(
        default_factory=LearningContext, description="Learning engine integration context"
    )
    
    # Agent Management
    assigned_agents: List[AgentAssignment] = Field(
        default_factory=list, description="Assigned agents with details"
    )
    
    agent_orchestration_config: Dict[StrictStr, Any] = Field(
        default_factory=dict, description="Agent orchestration configuration"
    )
    
    # Project Management
    project_id: Optional[UUID] = Field(None, description="Associated project UUID")
    milestone_id: Optional[UUID] = Field(None, description="Associated milestone UUID")
    epic_id: Optional[UUID] = Field(None, description="Associated epic UUID")
    sprint_id: Optional[UUID] = Field(None, description="Associated sprint UUID")
    
    # User and Stakeholder Information
    created_by: UUID = Field(..., description="User UUID who created the request")
    assigned_to: Optional[UUID] = Field(None, description="User UUID responsible for the enhancement")
    stakeholders: List[UUID] = Field(default_factory=list, description="Stakeholder UUIDs")
    reviewers: List[UUID] = Field(default_factory=list, description="Reviewer UUIDs")
    
    # Timing and Effort
    estimated_hours: Optional[confloat(ge=0.1)] = Field(None, description="Estimated effort in hours")
    actual_hours: Optional[confloat(ge=0.0)] = Field(None, description="Actual effort spent")
    due_date: Optional[datetime] = Field(None, description="Due date")
    started_at: Optional[datetime] = Field(None, description="Work start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    
    # Quality and Metrics
    quality_metrics: QualityMetrics = Field(
        default_factory=QualityMetrics, description="Quality and performance metrics"
    )
    
    # Learning and Feedback
    learning_feedback: List[LearningFeedback] = Field(
        default_factory=list, description="Learning feedback data"
    )
    
    knowledge_contributions: List[Dict[StrictStr, Any]] = Field(
        default_factory=list, description="Contributions to knowledge base"
    )
    
    pattern_extractions: List[Dict[StrictStr, Any]] = Field(
        default_factory=list, description="Extracted patterns for learning"
    )
    
    # Dependencies and Relationships
    blocks: List[UUID] = Field(default_factory=list, description="Enhancement UUIDs this blocks")
    blocked_by: List[UUID] = Field(default_factory=list, description="Enhancement UUIDs blocking this")
    related_to: List[UUID] = Field(default_factory=list, description="Related enhancement UUIDs")
    duplicate_of: Optional[UUID] = Field(None, description="Original enhancement if duplicate")
    
    # External References
    github_issue_url: Optional[HttpUrl] = Field(None, description="Related GitHub issue URL")
    external_references: List[HttpUrl] = Field(default_factory=list, description="External reference URLs")
    documentation_links: List[HttpUrl] = Field(default_factory=list, description="Documentation URLs")
    
    # Files and Attachments
    file_attachments: List[Dict[StrictStr, Any]] = Field(
        default_factory=list, description="File attachments metadata"
    )
    
    code_snippets: List[Dict[StrictStr, StrictStr]] = Field(
        default_factory=list, description="Code snippets with language"
    )
    
    # Configuration and Environment
    environment_requirements: Dict[StrictStr, Any] = Field(
        default_factory=dict, description="Environment-specific requirements"
    )
    
    deployment_configuration: Dict[StrictStr, Any] = Field(
        default_factory=dict, description="Deployment-specific configuration"
    )
    
    # Communication and Notifications
    notification_preferences: Dict[StrictStr, StrictBool] = Field(
        default_factory=lambda: {
            "status_changes": True,
            "assignment_changes": True,
            "comments_added": True,
            "completion": True,
            "errors": True
        },
        description="Notification preferences"
    )
    
    communication_history: List[Dict[StrictStr, Any]] = Field(
        default_factory=list, description="Communication history"
    )
    
    # Audit and Compliance
    compliance_requirements: List[StrictStr] = Field(
        default_factory=list, description="Compliance requirements"
    )
    
    audit_trail: List[Dict[StrictStr, Any]] = Field(
        default_factory=list, description="Detailed audit trail"
    )
    
    # Custom Fields and Extensions
    custom_fields: Dict[StrictStr, Any] = Field(
        default_factory=dict, description="Custom organization-specific fields"
    )
    
    extensions: Dict[StrictStr, Any] = Field(
        default_factory=dict, description="Extension data for plugins/integrations"
    )
    
    # Validation and Business Rules
    @validator('title')
    def validate_title(cls, v):
        """Validate and sanitize title"""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        
        # Security validation
        v = SecurityValidator.sanitize_text(v)
        
        # Business rule validation
        forbidden_words = ['test', 'dummy', 'placeholder', 'todo']
        if any(word in v.lower() for word in forbidden_words):
            raise ValueError("Title contains placeholder text")
        
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        """Validate and enhance description"""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        
        # Security validation
        v = SecurityValidator.sanitize_text(v)
        
        # Quality checks
        if len(v.split()) < 5:
            raise ValueError("Description should contain at least 5 words")
        
        # Check for clear requirements
        required_elements = ['what', 'why', 'how']
        v_lower = v.lower()
        missing_elements = [elem for elem in required_elements 
                          if elem not in v_lower and f'{elem}:' not in v_lower]
        
        if len(missing_elements) >= 2:
            raise ValueError(f"Description should address: {', '.join(missing_elements)}")
        
        return v.strip()
    
    @validator('due_date')
    def validate_due_date(cls, v):
        """Validate due date is in the future"""
        if v and v <= datetime.now(timezone.utc):
            raise ValueError("Due date must be in the future")
        return v
    
    @validator('estimated_hours')
    def validate_estimated_hours(cls, v, values):
        """Validate estimated hours based on complexity"""
        if v is None:
            return v
        
        complexity = values.get('complexity')
        if complexity:
            min_hours = {
                ComplexityLevel.TRIVIAL: 0.5,
                ComplexityLevel.LOW: 1.0,
                ComplexityLevel.MEDIUM: 4.0,
                ComplexityLevel.HIGH: 16.0,
                ComplexityLevel.VERY_HIGH: 40.0
            }
            
            if v < min_hours.get(complexity, 0.5):
                raise ValueError(f"Estimated hours too low for {complexity} complexity")
        
        return v
    
    @root_validator
    def validate_consistency(cls, values):
        """Validate internal consistency of the request"""
        # Priority vs Impact consistency
        priority = values.get('priority')
        business_impact = values.get('business_impact')
        
        if (priority == EnhancementPriority.CRITICAL and 
            business_impact in [ImpactLevel.MINIMAL, ImpactLevel.LOW]):
            raise ValueError("Critical priority requires at least moderate business impact")
        
        # Security context validation
        security_context = values.get('security_context', {})
        if isinstance(security_context, dict):
            security_sensitive = any([
                security_context.get('involves_authentication', False),
                security_context.get('involves_authorization', False),
                security_context.get('involves_sensitive_data', False),
                security_context.get('involves_cryptography', False)
            ])
            
            if security_sensitive and values.get('category') != EnhancementCategory.SECURITY:
                if not security_context.get('security_review_required', False):
                    values.setdefault('security_context', {})['security_review_required'] = True
        
        # Performance context validation
        performance_context = values.get('performance_context', {})
        if (isinstance(performance_context, dict) and 
            performance_context.get('affects_performance', False) and
            values.get('category') != EnhancementCategory.PERFORMANCE):
            performance_context['performance_testing_required'] = True
        
        return values
    
    # Business Logic Methods
    def can_be_assigned_to_agent(self, agent_type: str) -> bool:
        """Check if enhancement can be assigned to specific agent type"""
        # Category-agent mapping
        category_agents = {
            EnhancementCategory.SECURITY: ['security', 'validation'],
            EnhancementCategory.PERFORMANCE: ['analysis', 'enhancement', 'validation'],
            EnhancementCategory.CODE_QUALITY: ['analysis', 'enhancement'],
            EnhancementCategory.DOCUMENTATION: ['documentation'],
            # Add more mappings as needed
        }
        
        allowed_agents = category_agents.get(self.category, [
            'analysis', 'enhancement', 'validation'
        ])
        
        return agent_type in allowed_agents
    
    def requires_security_review(self) -> bool:
        """Determine if security review is required"""
        return (
            self.security_context.security_review_required or
            self.category == EnhancementCategory.SECURITY or
            self.priority == EnhancementPriority.CRITICAL or
            any([
                self.security_context.involves_authentication,
                self.security_context.involves_authorization,
                self.security_context.involves_sensitive_data,
                self.security_context.involves_cryptography
            ])
        )
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Extract learning insights from the enhancement"""
        return {
            "complexity_factors": self._extract_complexity_factors(),
            "success_patterns": self._extract_success_patterns(),
            "failure_patterns": self._extract_failure_patterns(),
            "knowledge_domains": list(self.learning_context.knowledge_domains),
            "skill_requirements": self._extract_skill_requirements(),
            "improvement_opportunities": self._extract_improvement_opportunities()
        }
    
    def _extract_complexity_factors(self) -> List[str]:
        """Extract factors contributing to complexity"""
        factors = []
        
        if len(self.code_locations) > 5:
            factors.append("multiple_file_changes")
        
        if self.security_context.involves_cryptography:
            factors.append("cryptographic_operations")
        
        if len(self.affected_services) > 3:
            factors.append("multi_service_impact")
        
        if self.performance_context.affects_performance:
            factors.append("performance_implications")
        
        return factors
    
    def _extract_success_patterns(self) -> List[Dict[str, Any]]:
        """Extract successful patterns from feedback"""
        success_patterns = []
        
        for feedback in self.learning_feedback:
            if feedback.rating and feedback.rating >= 8.0:
                success_patterns.append({
                    "pattern_type": feedback.feedback_type,
                    "rating": feedback.rating,
                    "context": feedback.context,
                    "tags": list(feedback.tags)
                })
        
        return success_patterns
    
    def _extract_failure_patterns(self) -> List[Dict[str, Any]]:
        """Extract failure patterns from feedback"""
        failure_patterns = []
        
        for feedback in self.learning_feedback:
            if feedback.rating and feedback.rating < 5.0:
                failure_patterns.append({
                    "pattern_type": feedback.feedback_type,
                    "rating": feedback.rating,
                    "context": feedback.context,
                    "tags": list(feedback.tags),
                    "suggestions": feedback.suggestions
                })
        
        return failure_patterns
    
    def _extract_skill_requirements(self) -> List[str]:
        """Extract required skills based on enhancement characteristics"""
        skills = []
        
        # Category-based skills
        category_skills = {
            EnhancementCategory.SECURITY: ["security_analysis", "cryptography", "compliance"],
            EnhancementCategory.PERFORMANCE: ["performance_optimization", "profiling", "caching"],
            EnhancementCategory.CODE_QUALITY: ["refactoring", "design_patterns", "clean_code"],
            EnhancementCategory.TESTING: ["test_automation", "test_design", "quality_assurance"],
            EnhancementCategory.INFRASTRUCTURE: ["devops", "containerization", "cloud_platforms"],
            EnhancementCategory.UI_UX: ["frontend_development", "user_experience", "accessibility"]
        }
        
        skills.extend(category_skills.get(self.category, []))
        
        # Context-based skills
        if self.security_context.involves_cryptography:
            skills.append("cryptographic_implementation")
        
        if self.performance_context.affects_performance:
            skills.append("performance_tuning")
        
        if self.testing_context.security_tests_required:
            skills.append("security_testing")
        
        return list(set(skills))  # Remove duplicates
    
    def _extract_improvement_opportunities(self) -> List[str]:
        """Identify improvement opportunities"""
        opportunities = []
        
        # Quality metrics analysis
        if self.quality_metrics.code_quality_score and self.quality_metrics.code_quality_score < 7.0:
            opportunities.append("code_quality_improvement")
        
        if self.quality_metrics.test_coverage_percentage and self.quality_metrics.test_coverage_percentage < 80.0:
            opportunities.append("test_coverage_improvement")
        
        if self.quality_metrics.technical_debt_score and self.quality_metrics.technical_debt_score > 6.0:
            opportunities.append("technical_debt_reduction")
        
        # Context-based opportunities
        if not self.testing_context.unit_tests_required and self.complexity != ComplexityLevel.TRIVIAL:
            opportunities.append("testing_strategy_improvement")
        
        if len(self.documentation_links) == 0 and self.complexity in [ComplexityLevel.HIGH, ComplexityLevel.VERY_HIGH]:
            opportunities.append("documentation_enhancement")
        
        return opportunities
    
    # Integration Methods
    def to_agent_task(self, agent_type: str) -> Dict[str, Any]:
        """Convert enhancement to agent-specific task format"""
        base_task = {
            "enhancement_id": str(self.id),
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "complexity": self.complexity,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "code_locations": [
                {
                    "file_path": str(loc.file_path),
                    "start_line": loc.start_line,
                    "end_line": loc.end_line,
                    "function_name": loc.function_name,
                    "class_name": loc.class_name,
                    "module_name": loc.module_name
                }
                for loc in self.code_locations
            ]
        }
        
        # Agent-specific task configuration
        agent_configs = {
            "analysis": {
                "analysis_type": "comprehensive",
                "include_security_scan": self.requires_security_review(),
                "include_performance_analysis": self.performance_context.affects_performance,
                "complexity_analysis": True,
                "dependency_analysis": True
            },
            "enhancement": {
                "enhancement_approach": self._get_enhancement_approach(),
                "preserve_functionality": True,
                "maintain_performance": not self.performance_context.affects_performance or 
                                      self.performance_context.expected_performance_impact != "negative",
                "apply_best_practices": True,
                "generate_tests": self.testing_context.unit_tests_required
            },
            "validation": {
                "validation_level": "comprehensive",
                "run_security_tests": self.testing_context.security_tests_required,
                "run_performance_tests": self.testing_context.performance_tests_required,
                "regression_scope": self.testing_context.regression_testing_scope,
                "quality_gates": self._get_quality_gates()
            },
            "security": {
                "security_scan_depth": "deep" if self.requires_security_review() else "standard",
                "compliance_checks": self.security_context.compliance_frameworks,
                "vulnerability_assessment": True,
                "secure_coding_review": True
            },
            "documentation": {
                "documentation_level": "comprehensive" if self.complexity in [ComplexityLevel.HIGH, ComplexityLevel.VERY_HIGH] else "standard",
                "include_examples": True,
                "update_existing_docs": True,
                "generate_api_docs": "api" in str(self.code_locations).lower()
            }
        }
        
        # Merge agent-specific config
        if agent_type in agent_configs:
            base_task.update(agent_configs[agent_type])
        
        return base_task
    
    def _get_enhancement_approach(self) -> str:
        """Determine the best enhancement approach"""
        if self.enhancement_type == EnhancementType.REFACTORING:
            return "refactor_first"
        elif self.enhancement_type == EnhancementType.PERFORMANCE_TUNING:
            return "performance_focused"
        elif self.enhancement_type == EnhancementType.SECURITY_PATCH:
            return "security_first"
        elif self.complexity == ComplexityLevel.VERY_HIGH:
            return "incremental_approach"
        else:
            return "standard_approach"
    
    def _get_quality_gates(self) -> Dict[str, Any]:
        """Define quality gates based on enhancement characteristics"""
        gates = {
            "minimum_code_quality": 7.0,
            "minimum_test_coverage": 80.0,
            "maximum_complexity_increase": 2,
            "security_vulnerabilities_allowed": 0
        }
        
        # Adjust based on priority and complexity
        if self.priority == EnhancementPriority.CRITICAL:
            gates["minimum_code_quality"] = 8.5
            gates["minimum_test_coverage"] = 90.0
        
        if self.complexity == ComplexityLevel.VERY_HIGH:
            gates["minimum_test_coverage"] = 85.0
            gates["require_integration_tests"] = True
        
        return gates
    
    def create_learning_feedback(
        self,
        feedback_type: LearningFeedbackType,
        rating: Optional[float] = None,
        comments: Optional[str] = None,
        source: str = "system",
        **kwargs
    ) -> LearningFeedback:
        """Create and add learning feedback"""
        feedback = LearningFeedback(
            feedback_type=feedback_type,
            feedback_source=source,
            rating=rating,
            comments=comments,
            **kwargs
        )
        
        self.learning_feedback.append(feedback)
        return feedback
    
    def update_quality_metrics(self, metrics: Dict[str, Union[float, int]]) -> None:
        """Update quality metrics from analysis results"""
        for metric_name, value in metrics.items():
            if hasattr(self.quality_metrics, metric_name):
                setattr(self.quality_metrics, metric_name, value)
    
    def calculate_effort_variance(self) -> Optional[float]:
        """Calculate effort estimation variance"""
        if self.estimated_hours and self.actual_hours:
            return ((self.actual_hours - self.estimated_hours) / self.estimated_hours) * 100
        return None
    
    def get_completion_percentage(self) -> float:
        """Calculate completion percentage based on status"""
        status_completion = {
            EnhancementStatus.PENDING: 0.0,
            EnhancementStatus.TRIAGED: 10.0,
            EnhancementStatus.IN_ANALYSIS: 20.0,
            EnhancementStatus.ANALYSIS_COMPLETE: 35.0,
            EnhancementStatus.IN_ENHANCEMENT: 60.0,
            EnhancementStatus.ENHANCEMENT_COMPLETE: 75.0,
            EnhancementStatus.IN_VALIDATION: 85.0,
            EnhancementStatus.VALIDATION_PASSED: 90.0,
            EnhancementStatus.VALIDATION_FAILED: 75.0,
            EnhancementStatus.IN_DEPLOYMENT: 95.0,
            EnhancementStatus.DEPLOYED: 100.0,
            EnhancementStatus.CLOSED: 100.0,
            EnhancementStatus.CANCELLED: 0.0,
            EnhancementStatus.ON_HOLD: 50.0  # Maintain current progress
        }
        
        return status_completion.get(self.status, 0.0)
    
    def is_overdue(self) -> bool:
        """Check if enhancement is overdue"""
        if not self.due_date:
            return False
        
        return (
            datetime.now(timezone.utc) > self.due_date and
            self.status not in [EnhancementStatus.DEPLOYED, EnhancementStatus.CLOSED, EnhancementStatus.CANCELLED]
        )
    
    def get_risk_level(self) -> Literal["low", "medium", "high", "critical"]:
        """Calculate risk level based on various factors"""
        risk_score = 0
        
        # Complexity risk
        complexity_risk = {
            ComplexityLevel.TRIVIAL: 0,
            ComplexityLevel.LOW: 1,
            ComplexityLevel.MEDIUM: 2,
            ComplexityLevel.HIGH: 4,
            ComplexityLevel.VERY_HIGH: 6
        }
        risk_score += complexity_risk.get(self.complexity, 0)
        
        # Security risk
        if self.requires_security_review():
            risk_score += 3
        
        # Performance impact risk
        if self.performance_context.affects_performance:
            risk_score += 2
        
        # Dependencies risk
        if len(self.blocked_by) > 2:
            risk_score += 2
        
        # Timeline risk
        if self.is_overdue():
            risk_score += 3
        
        # Map score to risk level
        if risk_score <= 2:
            return "low"
        elif risk_score <= 5:
            return "medium"
        elif risk_score <= 8:
            return "high"
        else:
            return "critical"
    
    class Config:
        """Pydantic model configuration"""
        use_enum_values = True
        validate_assignment = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Path: lambda v: str(v),
            set: lambda v: list(v)
        }
        schema_extra = {
            "example": {
                "title": "Optimize database query performance in user service",
                "description": "The user profile retrieval endpoint is experiencing slow response times (>2s) during peak hours. Need to optimize the database queries, add proper indexing, and implement caching strategy to improve performance to <500ms response time.",
                "category": "performance",
                "enhancement_type": "optimization",
                "priority": "high",
                "complexity": "medium",
                "business_impact": "high",
                "technical_impact": "moderate",
                "code_locations": [
                    {
                        "file_path": "services/user_service/models.py",
                        "start_line": 45,
                        "end_line": 78,
                        "class_name": "UserProfile"
                    }
                ],
                "affected_components": ["user_service", "database"],
                "security_context": {
                    "involves_sensitive_data": True,
                    "security_review_required": True
                },
                "performance_context": {
                    "affects_performance": True,
                    "expected_performance_impact": "positive",
                    "performance_testing_required": True
                },
                "estimated_hours": 16.0,
                "due_date": "2024-03-15T10:00:00Z"
            }
        }


# Request/Response Models for API
class EnhancementRequestCreate(BaseModel):
    """Model for creating enhancement requests"""
    title: constr(min_length=5, max_length=MAX_TITLE_LENGTH, strip_whitespace=True)
    description: constr(min_length=10, max_length=MAX_DESCRIPTION_LENGTH, strip_whitespace=True)
    category: EnhancementCategory
    enhancement_type: EnhancementType
    priority: EnhancementPriority
    complexity: ComplexityLevel
    business_impact: ImpactLevel
    technical_impact: ImpactLevel
    
    # Optional fields
    project_id: Optional[UUID] = None
    milestone_id: Optional[UUID] = None
    code_locations: List[CodeLocation] = Field(default_factory=list)
    affected_components: List[StrictStr] = Field(default_factory=list)
    affected_services: List[StrictStr] = Field(default_factory=list)
    estimated_hours: Optional[confloat(ge=0.1)] = None
    due_date: Optional[datetime] = None
    
    # Context objects
    security_context: Optional[SecurityContext] = None
    performance_context: Optional[PerformanceContext] = None
    testing_context: Optional[TestingContext] = None
    learning_context: Optional[LearningContext] = None
    
    # External references
    github_issue_url: Optional[HttpUrl] = None
    external_references: List[HttpUrl] = Field(default_factory=list)


class EnhancementRequestUpdate(BaseModel):
    """Model for updating enhancement requests"""
    title: Optional[constr(min_length=5, max_length=MAX_TITLE_LENGTH, strip_whitespace=True)] = None
    description: Optional[constr(min_length=10, max_length=MAX_DESCRIPTION_LENGTH, strip_whitespace=True)] = None
    category: Optional[EnhancementCategory] = None
    enhancement_type: Optional[EnhancementType] = None
    priority: Optional[EnhancementPriority] = None
    complexity: Optional[ComplexityLevel] = None
    business_impact: Optional[ImpactLevel] = None
    technical_impact: Optional[ImpactLevel] = None
    status: Optional[EnhancementStatus] = None
    
    assigned_to: Optional[UUID] = None
    estimated_hours: Optional[confloat(ge=0.1)] = None
    actual_hours: Optional[confloat(ge=0.0)] = None
    due_date: Optional[datetime] = None
    
    # Context updates
    security_context: Optional[SecurityContext] = None
    performance_context: Optional[PerformanceContext] = None
    testing_context: Optional[TestingContext] = None
    learning_context: Optional[LearningContext] = None


class EnhancementRequestResponse(BaseModel):
    """Model for enhancement request responses"""
    id: UUID
    title: str
    description: str
    category: EnhancementCategory
    enhancement_type: EnhancementType
    priority: EnhancementPriority
    complexity: ComplexityLevel
    business_impact: ImpactLevel
    technical_impact: ImpactLevel
    status: EnhancementStatus
    
    created_by: UUID
    assigned_to: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    completion_percentage: float = Field(..., description="Calculated completion percentage")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(..., description="Calculated risk level")
    is_overdue: bool = Field(..., description="Whether the enhancement is overdue")
    
    # Optional detailed fields
    code_locations: Optional[List[CodeLocation]] = None
    quality_metrics: Optional[QualityMetrics] = None
    assigned_agents: Optional[List[AgentAssignment]] = None


class EnhancementRequestList(BaseModel):
    """Model for paginated enhancement request lists"""
    items: List[EnhancementRequestResponse]
    total: int
    page: int
    size: int
    pages: int


class EnhancementAnalytics(BaseModel):
    """Model for enhancement analytics and insights"""
    total_enhancements: int
    by_status: Dict[EnhancementStatus, int]
    by_category: Dict[EnhancementCategory, int]
    by_priority: Dict[EnhancementPriority, int]
    by_complexity: Dict[ComplexityLevel, int]
    
    average_completion_time_hours: Optional[float] = None
    average_effort_variance_percentage: Optional[float] = None
    
    top_categories: List[Dict[str, Union[str, int]]]
    overdue_count: int
    high_risk_count: int
    
    learning_insights: Dict[str, Any] = Field(default_factory=dict)
    quality_trends: Dict[str, List[float]] = Field(default_factory=dict)
    agent_performance: Dict[str, Dict[str, float]] = Field(default_factory=dict)