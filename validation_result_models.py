"""
YMERA Enterprise Multi-Agent System
Validation Result Models - Production Ready
Advanced validation models with learning engine integration and real-time feedback loops
"""

from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
from typing import Dict, List, Optional, Any, Union, Literal, Set, Tuple
from datetime import datetime, timezone
from enum import Enum
from decimal import Decimal
import uuid
import json
from dataclasses import dataclass
import asyncio
from contextlib import asynccontextmanager


class ValidationSeverity(str, Enum):
    """Validation issue severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    WARNING = "warning"


class ValidationType(str, Enum):
    """Types of validations performed"""
    SECURITY = "security"
    QUALITY = "quality"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    FUNCTIONALITY = "functionality"
    ARCHITECTURE = "architecture"
    DOCUMENTATION = "documentation"
    DEPLOYMENT = "deployment"
    ACCESSIBILITY = "accessibility"
    BUSINESS_LOGIC = "business_logic"


class ValidationStatus(str, Enum):
    """Validation execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRY = "retry"


class IssueCategory(str, Enum):
    """Categorization of validation issues"""
    SECURITY_VULNERABILITY = "security_vulnerability"
    CODE_QUALITY = "code_quality"
    PERFORMANCE_ISSUE = "performance_issue"
    COMPLIANCE_VIOLATION = "compliance_violation"
    FUNCTIONAL_DEFECT = "functional_defect"
    ARCHITECTURE_CONCERN = "architecture_concern"
    DOCUMENTATION_GAP = "documentation_gap"
    DEPLOYMENT_RISK = "deployment_risk"
    ACCESSIBILITY_BARRIER = "accessibility_barrier"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"


class ConfidenceLevel(str, Enum):
    """AI confidence in validation results"""
    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"           # 75-89%
    MEDIUM = "medium"       # 50-74%
    LOW = "low"            # 25-49%
    VERY_LOW = "very_low"  # 0-24%


class LearningFeedback(BaseModel):
    """Learning feedback for validation results"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_id: str = Field(..., description="Associated validation ID")
    feedback_type: Literal["accuracy", "relevance", "completeness", "timeliness"] = Field(...)
    rating: float = Field(..., ge=0.0, le=10.0, description="Feedback rating 0-10")
    comments: Optional[str] = Field(None, max_length=2000)
    corrected_result: Optional[Dict[str, Any]] = Field(None)
    learning_context: Dict[str, Any] = Field(default_factory=dict)
    feedback_source: Literal["human", "agent", "system", "external"] = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed: bool = Field(default=False)
    
    @validator('rating')
    def validate_rating(cls, v):
        return round(v, 2)


class ValidationMetrics(BaseModel):
    """Comprehensive validation metrics"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    total_checks: int = Field(..., ge=0)
    passed_checks: int = Field(..., ge=0)
    failed_checks: int = Field(..., ge=0)
    skipped_checks: int = Field(default=0, ge=0)
    
    critical_issues: int = Field(default=0, ge=0)
    high_issues: int = Field(default=0, ge=0)
    medium_issues: int = Field(default=0, ge=0)
    low_issues: int = Field(default=0, ge=0)
    
    execution_time_ms: float = Field(..., ge=0.0)
    memory_usage_mb: Optional[float] = Field(None, ge=0.0)
    cpu_usage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    
    accuracy_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI accuracy score")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")
    
    learning_applied: bool = Field(default=False)
    model_version: Optional[str] = Field(None, description="AI model version used")
    
    @root_validator
    def validate_check_counts(cls, values):
        total = values.get('total_checks', 0)
        passed = values.get('passed_checks', 0)
        failed = values.get('failed_checks', 0)
        skipped = values.get('skipped_checks', 0)
        
        if passed + failed + skipped != total:
            raise ValueError("Check counts must sum to total_checks")
        
        return values
    
    @property
    def success_rate(self) -> float:
        """Calculate validation success rate"""
        if self.total_checks == 0:
            return 0.0
        return round(self.passed_checks / self.total_checks, 4)
    
    @property
    def issue_density(self) -> float:
        """Calculate issue density per check"""
        if self.total_checks == 0:
            return 0.0
        total_issues = self.critical_issues + self.high_issues + self.medium_issues + self.low_issues
        return round(total_issues / self.total_checks, 4)


class ValidationIssue(BaseModel):
    """Individual validation issue with enhanced context"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = Field(..., description="Validation rule identifier")
    rule_name: str = Field(..., min_length=1, max_length=200)
    category: IssueCategory = Field(...)
    severity: ValidationSeverity = Field(...)
    
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    recommendation: str = Field(..., min_length=1, max_length=2000)
    
    # Location information
    file_path: Optional[str] = Field(None, max_length=500)
    line_number: Optional[int] = Field(None, ge=1)
    column_number: Optional[int] = Field(None, ge=1)
    code_snippet: Optional[str] = Field(None, max_length=5000)
    
    # Context and metadata
    affected_components: List[str] = Field(default_factory=list)
    tags: Set[str] = Field(default_factory=set)
    external_references: List[str] = Field(default_factory=list)
    
    # AI-enhanced information
    confidence: ConfidenceLevel = Field(...)
    ai_explanation: Optional[str] = Field(None, max_length=3000)
    suggested_fix: Optional[str] = Field(None, max_length=3000)
    automated_fix_available: bool = Field(default=False)
    
    # Business impact
    business_impact: Optional[str] = Field(None, max_length=1000)
    risk_score: float = Field(..., ge=0.0, le=10.0, description="Risk score 0-10")
    estimated_fix_time_hours: Optional[float] = Field(None, ge=0.0)
    
    # Learning and feedback
    false_positive_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    historical_feedback: List[LearningFeedback] = Field(default_factory=list)
    pattern_match_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('risk_score')
    def validate_risk_score(cls, v):
        return round(v, 2)
    
    @validator('tags', pre=True)
    def validate_tags(cls, v):
        if isinstance(v, list):
            return set(v)
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "issue_id": self.issue_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "location": {
                "file_path": self.file_path,
                "line_number": self.line_number,
                "column_number": self.column_number
            },
            "confidence": self.confidence.value,
            "risk_score": self.risk_score,
            "automated_fix_available": self.automated_fix_available,
            "created_at": self.created_at.isoformat()
        }


class ValidationContext(BaseModel):
    """Context information for validation execution"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    project_id: str = Field(..., description="Project identifier")
    repository_url: Optional[str] = Field(None)
    branch_name: Optional[str] = Field(None, max_length=100)
    commit_hash: Optional[str] = Field(None, max_length=40)
    
    validation_scope: List[str] = Field(default_factory=list, description="Files/modules to validate")
    excluded_paths: List[str] = Field(default_factory=list, description="Paths to exclude")
    
    # Environment context
    environment: Literal["development", "staging", "production", "testing"] = Field(...)
    language: Optional[str] = Field(None, max_length=50)
    framework: Optional[str] = Field(None, max_length=100)
    
    # Agent context
    requesting_agent: str = Field(..., description="Agent requesting validation")
    orchestration_id: Optional[str] = Field(None, description="Orchestration workflow ID")
    
    # Learning context
    use_learned_patterns: bool = Field(default=True)
    feedback_enabled: bool = Field(default=True)
    learning_mode: Literal["conservative", "balanced", "aggressive"] = Field(default="balanced")
    
    # Configuration
    custom_rules: Dict[str, Any] = Field(default_factory=dict)
    rule_overrides: Dict[str, Any] = Field(default_factory=dict)
    severity_overrides: Dict[str, ValidationSeverity] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationConfiguration(BaseModel):
    """Validation configuration with learning parameters"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    enabled_validations: Set[ValidationType] = Field(default_factory=lambda: set(ValidationType))
    severity_threshold: ValidationSeverity = Field(default=ValidationSeverity.LOW)
    max_issues_per_type: int = Field(default=1000, ge=1)
    timeout_seconds: int = Field(default=300, ge=1)
    
    # AI/ML Configuration
    ai_enabled: bool = Field(default=True)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    use_ensemble_models: bool = Field(default=True)
    fallback_to_rules: bool = Field(default=True)
    
    # Learning Configuration
    learning_enabled: bool = Field(default=True)
    auto_learn_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    feedback_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    pattern_matching_enabled: bool = Field(default=True)
    
    # Performance Configuration
    parallel_execution: bool = Field(default=True)
    max_parallel_workers: int = Field(default=4, ge=1, le=20)
    memory_limit_mb: Optional[int] = Field(None, ge=100)
    
    @validator('enabled_validations', pre=True)
    def validate_enabled_validations(cls, v):
        if isinstance(v, list):
            return set(v)
        return v


class ValidationResult(BaseModel):
    """Comprehensive validation result with learning integration"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    # Core identification
    validation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_validation_id: Optional[str] = Field(None, description="For sub-validations")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Execution information
    status: ValidationStatus = Field(...)
    validation_type: ValidationType = Field(...)
    context: ValidationContext = Field(...)
    configuration: ValidationConfiguration = Field(...)
    
    # Results
    issues: List[ValidationIssue] = Field(default_factory=list)
    metrics: ValidationMetrics = Field(...)
    summary: str = Field(..., min_length=1, max_length=5000)
    
    # Timing
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None)
    timeout_at: Optional[datetime] = Field(None)
    
    # Agent and orchestration
    executed_by_agent: str = Field(..., description="Agent that performed validation")
    agent_version: str = Field(..., description="Agent version")
    orchestration_context: Dict[str, Any] = Field(default_factory=dict)
    
    # Learning and AI
    ai_model_used: Optional[str] = Field(None, description="AI model identifier")
    learning_applied: bool = Field(default=False)
    pattern_matches: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_distribution: Dict[ConfidenceLevel, int] = Field(default_factory=dict)
    
    # Quality assurance
    peer_reviewed: bool = Field(default=False)
    reviewer_agent: Optional[str] = Field(None)
    quality_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    
    # Metadata
    tags: Set[str] = Field(default_factory=set)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Learning feedback
    feedback_requests: List[str] = Field(default_factory=list)
    learning_opportunities: List[Dict[str, Any]] = Field(default_factory=list)
    
    @validator('tags', pre=True)
    def validate_tags(cls, v):
        if isinstance(v, list):
            return set(v)
        return v
    
    @root_validator
    def validate_completion_state(cls, values):
        status = values.get('status')
        completed_at = values.get('completed_at')
        
        if status in [ValidationStatus.COMPLETED, ValidationStatus.FAILED] and not completed_at:
            values['completed_at'] = datetime.now(timezone.utc)
        
        return values
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate validation duration"""
        if not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()
    
    @property
    def is_successful(self) -> bool:
        """Check if validation completed successfully"""
        return self.status == ValidationStatus.COMPLETED
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if validation found critical issues"""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)
    
    @property
    def issue_summary(self) -> Dict[ValidationSeverity, int]:
        """Get summary of issues by severity"""
        summary = {severity: 0 for severity in ValidationSeverity}
        for issue in self.issues:
            summary[issue.severity] += 1
        return summary
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all issues"""
        if not self.issues:
            return 0.0
        
        confidence_map = {
            ConfidenceLevel.VERY_HIGH: 0.95,
            ConfidenceLevel.HIGH: 0.82,
            ConfidenceLevel.MEDIUM: 0.62,
            ConfidenceLevel.LOW: 0.37,
            ConfidenceLevel.VERY_LOW: 0.12
        }
        
        total_confidence = sum(confidence_map[issue.confidence] for issue in self.issues)
        return round(total_confidence / len(self.issues), 4)
    
    def add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue with automatic metrics update"""
        self.issues.append(issue)
        self._update_metrics()
    
    def _update_metrics(self) -> None:
        """Update metrics based on current issues"""
        severity_counts = self.issue_summary
        self.metrics.critical_issues = severity_counts[ValidationSeverity.CRITICAL]
        self.metrics.high_issues = severity_counts[ValidationSeverity.HIGH]
        self.metrics.medium_issues = severity_counts[ValidationSeverity.MEDIUM]
        self.metrics.low_issues = severity_counts[ValidationSeverity.LOW]
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary for API responses"""
        return {
            "validation_id": self.validation_id,
            "status": self.status.value,
            "validation_type": self.validation_type.value,
            "total_issues": len(self.issues),
            "critical_issues": self.metrics.critical_issues,
            "high_issues": self.metrics.high_issues,
            "success_rate": self.metrics.success_rate,
            "average_confidence": self.average_confidence,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    async def apply_learning_feedback(self, feedback: LearningFeedback) -> bool:
        """Apply learning feedback to improve future validations"""
        try:
            # Find matching issues and update their feedback
            for issue in self.issues:
                if issue.issue_id == feedback.validation_id:
                    issue.historical_feedback.append(feedback)
                    
                    # Adjust confidence based on feedback
                    if feedback.rating < 5.0:  # Negative feedback
                        if issue.false_positive_probability < 0.9:
                            issue.false_positive_probability += 0.1
                    elif feedback.rating > 7.0:  # Positive feedback
                        if issue.false_positive_probability > 0.1:
                            issue.false_positive_probability -= 0.1
                    
                    return True
            
            return False
        except Exception as e:
            return False
    
    def export_for_learning(self) -> Dict[str, Any]:
        """Export validation data for learning engine consumption"""
        return {
            "validation_id": self.validation_id,
            "validation_type": self.validation_type.value,
            "context": self.context.dict(),
            "issues": [issue.dict() for issue in self.issues],
            "metrics": self.metrics.dict(),
            "patterns": self.pattern_matches,
            "feedback_data": [
                feedback.dict() for issue in self.issues 
                for feedback in issue.historical_feedback
            ],
            "success_indicators": {
                "completion_rate": 1.0 if self.is_successful else 0.0,
                "accuracy_score": self.metrics.accuracy_score or 0.0,
                "confidence_score": self.metrics.confidence_score or 0.0,
                "peer_review_passed": self.peer_reviewed
            },
            "learning_metadata": {
                "agent_version": self.agent_version,
                "ai_model": self.ai_model_used,
                "learning_applied": self.learning_applied,
                "pattern_match_count": len(self.pattern_matches)
            }
        }


class BatchValidationResult(BaseModel):
    """Result for batch validation operations"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_results: List[ValidationResult] = Field(default_factory=list)
    
    batch_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    batch_completed_at: Optional[datetime] = Field(None)
    
    total_validations: int = Field(..., ge=0)
    completed_validations: int = Field(default=0, ge=0)
    failed_validations: int = Field(default=0, ge=0)
    
    overall_success_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    aggregated_metrics: Optional[Dict[str, Any]] = Field(None)
    
    @property
    def is_complete(self) -> bool:
        """Check if all validations in batch are complete"""
        return self.completed_validations + self.failed_validations == self.total_validations
    
    @property
    def batch_duration_seconds(self) -> Optional[float]:
        """Calculate total batch duration"""
        if not self.batch_completed_at:
            return None
        return (self.batch_completed_at - self.batch_started_at).total_seconds()
    
    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result to the batch"""
        self.validation_results.append(result)
        
        if result.is_successful:
            self.completed_validations += 1
        else:
            self.failed_validations += 1
        
        # Update overall success rate
        total_completed = self.completed_validations + self.failed_validations
        if total_completed > 0:
            self.overall_success_rate = self.completed_validations / total_completed
        
        # Mark batch as complete if all validations are done
        if self.is_complete and not self.batch_completed_at:
            self.batch_completed_at = datetime.now(timezone.utc)


# Factory functions for creating validation results
class ValidationResultFactory:
    """Factory for creating validation results with proper defaults"""
    
    @staticmethod
    def create_validation_result(
        validation_type: ValidationType,
        context: ValidationContext,
        executed_by_agent: str,
        agent_version: str = "1.0.0",
        configuration: Optional[ValidationConfiguration] = None
    ) -> ValidationResult:
        """Create a new validation result with proper initialization"""
        
        if configuration is None:
            configuration = ValidationConfiguration()
        
        # Initialize metrics with zero values
        metrics = ValidationMetrics(
            total_checks=0,
            passed_checks=0,
            failed_checks=0,
            execution_time_ms=0.0
        )
        
        return ValidationResult(
            status=ValidationStatus.PENDING,
            validation_type=validation_type,
            context=context,
            configuration=configuration,
            metrics=metrics,
            summary="Validation initialized - pending execution",
            executed_by_agent=executed_by_agent,
            agent_version=agent_version
        )
    
    @staticmethod
    def create_security_validation(
        project_id: str,
        repository_url: str,
        executed_by_agent: str = "security_agent"
    ) -> ValidationResult:
        """Create a security validation result"""
        context = ValidationContext(
            project_id=project_id,
            repository_url=repository_url,
            environment="production",
            requesting_agent="security_agent"
        )
        
        config = ValidationConfiguration(
            enabled_validations={ValidationType.SECURITY},
            severity_threshold=ValidationSeverity.HIGH,
            ai_enabled=True,
            learning_enabled=True
        )
        
        return ValidationResultFactory.create_validation_result(
            validation_type=ValidationType.SECURITY,
            context=context,
            executed_by_agent=executed_by_agent,
            configuration=config
        )
    
    @staticmethod
    def create_code_quality_validation(
        project_id: str,
        file_paths: List[str],
        executed_by_agent: str = "analysis_agent"
    ) -> ValidationResult:
        """Create a code quality validation result"""
        context = ValidationContext(
            project_id=project_id,
            validation_scope=file_paths,
            environment="development",
            requesting_agent="analysis_agent"
        )
        
        config = ValidationConfiguration(
            enabled_validations={ValidationType.QUALITY, ValidationType.PERFORMANCE},
            severity_threshold=ValidationSeverity.MEDIUM,
            ai_enabled=True,
            learning_enabled=True
        )
        
        return ValidationResultFactory.create_validation_result(
            validation_type=ValidationType.QUALITY,
            context=context,
            executed_by_agent=executed_by_agent,
            configuration=config
        )


# Export all models
__all__ = [
    "ValidationSeverity",
    "ValidationType", 
    "ValidationStatus",
    "IssueCategory",
    "ConfidenceLevel",
    "LearningFeedback",
    "ValidationMetrics",
    "ValidationIssue",
    "ValidationContext",
    "ValidationConfiguration", 
    "ValidationResult",
    "BatchValidationResult",
    "ValidationResultFactory"
]