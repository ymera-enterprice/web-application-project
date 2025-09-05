"""
YMERA Enterprise Analysis Result Models
Production-Ready Pydantic Models for Multi-Agent Analysis System

This module defines comprehensive analysis result models that integrate with:
- Learning Engine for continuous improvement
- Multi-Agent System for collaborative analysis
- Vector Database for semantic search and similarity
- Real-time feedback processing and adaptation
"""

from __future__ import annotations
from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
from typing import Any, Dict, List, Optional, Union, Literal, Set, Tuple
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
import json
from decimal import Decimal
from pathlib import Path

# Core Enums and Types
class AnalysisType(str, Enum):
    """Types of analysis performed by the system"""
    CODE_QUALITY = "code_quality"
    SECURITY_VULNERABILITY = "security_vulnerability"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    ARCHITECTURE_REVIEW = "architecture_review"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    DOCUMENTATION_QUALITY = "documentation_quality"
    TEST_COVERAGE = "test_coverage"
    CODE_COMPLEXITY = "code_complexity"
    MAINTAINABILITY = "maintainability"
    SCALABILITY = "scalability"
    COMPLIANCE = "compliance"
    REFACTORING_OPPORTUNITIES = "refactoring_opportunities"

class SeverityLevel(str, Enum):
    """Severity levels for analysis findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ConfidenceLevel(str, Enum):
    """Confidence levels for analysis results"""
    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"           # 70-89%
    MEDIUM = "medium"       # 50-69%
    LOW = "low"            # 30-49%
    VERY_LOW = "very_low"   # 0-29%

class AnalysisStatus(str, Enum):
    """Status of analysis execution"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"

class RecommendationPriority(str, Enum):
    """Priority levels for recommendations"""
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WHEN_POSSIBLE = "when_possible"

class LearningFeedbackType(str, Enum):
    """Types of learning feedback"""
    ACCURACY_FEEDBACK = "accuracy_feedback"
    EFFECTIVENESS_FEEDBACK = "effectiveness_feedback"
    USER_SATISFACTION = "user_satisfaction"
    IMPLEMENTATION_SUCCESS = "implementation_success"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"

# Base Models
class TimestampedModel(BaseModel):
    """Base model with automatic timestamping"""
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        extra='forbid',
        str_strip_whitespace=True
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the record was created"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the record was last updated"
    )

class IdentifiableModel(TimestampedModel):
    """Base model with UUID identification"""
    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the record"
    )

# Location and Context Models
class CodeLocation(BaseModel):
    """Precise location within code"""
    file_path: str = Field(..., description="Relative path to the file")
    line_number: int = Field(..., ge=1, description="Line number (1-based)")
    column_number: Optional[int] = Field(None, ge=1, description="Column number (1-based)")
    end_line_number: Optional[int] = Field(None, ge=1, description="End line number for ranges")
    end_column_number: Optional[int] = Field(None, ge=1, description="End column number for ranges")
    function_name: Optional[str] = Field(None, description="Function/method name if applicable")
    class_name: Optional[str] = Field(None, description="Class name if applicable")
    module_name: Optional[str] = Field(None, description="Module/namespace name")
    
    @validator('end_line_number')
    def validate_end_line(cls, v, values):
        if v is not None and 'line_number' in values:
            if v < values['line_number']:
                raise ValueError('End line number must be >= start line number')
        return v

class AnalysisContext(BaseModel):
    """Context information for analysis"""
    repository_url: Optional[str] = Field(None, description="Repository URL if applicable")
    branch_name: str = Field(default="main", description="Git branch being analyzed")
    commit_hash: Optional[str] = Field(None, description="Git commit hash")
    project_type: Optional[str] = Field(None, description="Type of project (web, api, library, etc.)")
    programming_languages: List[str] = Field(default_factory=list, description="Languages detected")
    frameworks: List[str] = Field(default_factory=list, description="Frameworks detected")
    environment: Optional[str] = Field(None, description="Target environment (dev, staging, prod)")
    analysis_scope: List[str] = Field(default_factory=list, description="Files/directories analyzed")
    excluded_paths: List[str] = Field(default_factory=list, description="Excluded paths")
    custom_rules: Dict[str, Any] = Field(default_factory=dict, description="Custom analysis rules")

# Learning and Feedback Models
class LearningMetrics(BaseModel):
    """Metrics for learning engine integration"""
    pattern_recognition_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="How well the analysis recognized known patterns"
    )
    novel_pattern_detection: bool = Field(
        default=False,
        description="Whether novel patterns were detected"
    )
    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for improving future analysis"
    )
    knowledge_base_updates: List[str] = Field(
        default_factory=list,
        description="Updates to be made to knowledge base"
    )
    confidence_evolution: Dict[str, float] = Field(
        default_factory=dict,
        description="How confidence evolved during analysis"
    )
    learning_iteration: int = Field(
        default=1, ge=1,
        description="Learning iteration number"
    )

class FeedbackData(BaseModel):
    """Feedback data for learning loop"""
    feedback_type: LearningFeedbackType
    accuracy_rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Accuracy rating (0-5)")
    usefulness_rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Usefulness rating (0-5)")
    implementation_success: Optional[bool] = Field(None, description="Whether recommendation was implemented successfully")
    time_to_fix: Optional[int] = Field(None, ge=0, description="Time taken to address finding (minutes)")
    user_comments: Optional[str] = Field(None, description="Free-form user feedback")
    false_positive_reason: Optional[str] = Field(None, description="Reason if marked as false positive")
    additional_context: Dict[str, Any] = Field(default_factory=dict, description="Additional feedback context")
    provided_by: str = Field(..., description="User or system that provided feedback")
    provided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Core Finding Models
class AnalysisFinding(IdentifiableModel):
    """Individual analysis finding"""
    finding_type: AnalysisType
    severity: SeverityLevel
    confidence: ConfidenceLevel
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Numerical confidence (0-1)")
    
    title: str = Field(..., min_length=1, max_length=200, description="Short finding title")
    description: str = Field(..., min_length=1, description="Detailed finding description")
    
    location: CodeLocation
    affected_lines: List[int] = Field(default_factory=list, description="All affected line numbers")
    code_snippet: Optional[str] = Field(None, description="Relevant code snippet")
    
    # Categorization
    category: str = Field(..., description="Finding category")
    subcategory: Optional[str] = Field(None, description="Finding subcategory")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    
    # Impact and Risk Assessment
    impact_description: str = Field(..., description="Description of potential impact")
    risk_factors: List[str] = Field(default_factory=list, description="Associated risk factors")
    business_impact: Optional[str] = Field(None, description="Potential business impact")
    technical_debt_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Technical debt score")
    
    # Evidence and References
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    external_references: List[str] = Field(default_factory=list, description="External reference URLs")
    cve_references: List[str] = Field(default_factory=list, description="CVE references if applicable")
    
    # Learning Integration
    learning_metrics: Optional[LearningMetrics] = Field(None, description="Learning engine metrics")
    feedback_data: List[FeedbackData] = Field(default_factory=list, description="Accumulated feedback")
    
    # Agent Information
    detected_by_agent: str = Field(..., description="Agent that detected this finding")
    agent_version: str = Field(..., description="Version of the detecting agent")
    detection_method: str = Field(..., description="Method used for detection")
    
    # Resolution Tracking
    is_resolved: bool = Field(default=False, description="Whether finding has been resolved")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolved_by: Optional[str] = Field(None, description="Who resolved the finding")

class RecommendationAction(BaseModel):
    """Specific action recommendation"""
    action_id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    priority: RecommendationPriority
    
    # Implementation details
    implementation_steps: List[str] = Field(default_factory=list)
    code_changes: Optional[str] = Field(None, description="Suggested code changes")
    configuration_changes: Dict[str, Any] = Field(default_factory=dict)
    
    # Effort and Impact Estimation
    estimated_effort_hours: Optional[float] = Field(None, ge=0.0)
    estimated_impact: Optional[str] = Field(None)
    required_skills: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    
    # Validation
    validation_criteria: List[str] = Field(default_factory=list)
    test_suggestions: List[str] = Field(default_factory=list)
    
    # Learning Integration
    success_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of successful implementation")
    historical_effectiveness: Optional[float] = Field(None, ge=0.0, le=1.0, description="Historical effectiveness score")

class AnalysisRecommendation(IdentifiableModel):
    """Analysis recommendation with actions"""
    finding_id: UUID = Field(..., description="Related finding ID")
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=1, description="Recommendation summary")
    
    # Actions
    actions: List[RecommendationAction] = Field(..., min_items=1)
    
    # Prioritization
    overall_priority: RecommendationPriority
    business_value: Optional[str] = Field(None, description="Expected business value")
    risk_mitigation: Optional[str] = Field(None, description="Risk mitigation benefits")
    
    # Implementation Planning
    implementation_order: List[UUID] = Field(default_factory=list, description="Recommended action order")
    prerequisites: List[str] = Field(default_factory=list)
    potential_side_effects: List[str] = Field(default_factory=list)
    rollback_plan: Optional[str] = Field(None, description="Rollback strategy")
    
    # Learning Integration
    generated_by_agent: str = Field(..., description="Agent that generated recommendation")
    learning_confidence: float = Field(..., ge=0.0, le=1.0)
    adaptation_notes: List[str] = Field(default_factory=list, description="How recommendation was adapted based on learning")

# Performance and Metrics Models
class PerformanceMetrics(BaseModel):
    """Performance metrics for analysis execution"""
    total_execution_time_seconds: float = Field(..., ge=0.0)
    agent_execution_times: Dict[str, float] = Field(default_factory=dict)
    
    # Resource usage
    peak_memory_usage_mb: Optional[float] = Field(None, ge=0.0)
    cpu_usage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    
    # Analysis statistics
    files_analyzed: int = Field(..., ge=0)
    lines_of_code_analyzed: int = Field(..., ge=0)
    total_findings: int = Field(..., ge=0)
    findings_by_severity: Dict[SeverityLevel, int] = Field(default_factory=dict)
    
    # Learning metrics
    knowledge_base_queries: int = Field(default=0, ge=0)
    pattern_matches: int = Field(default=0, ge=0)
    novel_patterns_discovered: int = Field(default=0, ge=0)
    
    # Quality metrics
    false_positive_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(None, ge=0.0, le=1.0)

class QualityAssessment(BaseModel):
    """Quality assessment of analysis results"""
    overall_quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    
    # Detailed quality metrics
    accuracy_score: float = Field(..., ge=0.0, le=1.0)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    actionability_score: float = Field(..., ge=0.0, le=1.0)
    
    # Quality factors
    quality_factors: Dict[str, float] = Field(default_factory=dict)
    quality_issues: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    
    # Validation
    validated_by: Optional[str] = Field(None, description="Who/what validated the quality")
    validation_method: Optional[str] = Field(None, description="Validation method used")
    validation_timestamp: Optional[datetime] = Field(None)

# Main Analysis Result Model
class AnalysisResult(IdentifiableModel):
    """Complete analysis result with all components"""
    
    # Basic information
    analysis_type: AnalysisType
    status: AnalysisStatus
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Analysis description")
    
    # Context
    context: AnalysisContext
    requested_by: str = Field(..., description="User or system that requested analysis")
    session_id: Optional[UUID] = Field(None, description="Analysis session ID")
    
    # Results
    findings: List[AnalysisFinding] = Field(default_factory=list)
    recommendations: List[AnalysisRecommendation] = Field(default_factory=list)
    
    # Execution information
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None)
    duration_seconds: Optional[float] = Field(None, ge=0.0)
    
    # Agent orchestration
    orchestrator_version: str = Field(..., description="Version of orchestrator used")
    participating_agents: List[str] = Field(..., min_items=1, description="Agents that participated")
    agent_coordination: Dict[str, Any] = Field(default_factory=dict, description="Agent coordination details")
    
    # Performance and quality
    performance_metrics: Optional[PerformanceMetrics] = Field(None)
    quality_assessment: Optional[QualityAssessment] = Field(None)
    
    # Learning integration
    learning_iteration: int = Field(default=1, ge=1)
    knowledge_base_version: str = Field(..., description="Version of knowledge base used")
    learning_insights: Dict[str, Any] = Field(default_factory=dict)
    adaptations_made: List[str] = Field(default_factory=list, description="Adaptations made during analysis")
    
    # Feedback and improvement
    feedback_summary: Dict[str, Any] = Field(default_factory=dict)
    continuous_improvement_notes: List[str] = Field(default_factory=list)
    
    # Error handling
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated")
    
    # Integration metadata
    vector_embeddings: Optional[Dict[str, List[float]]] = Field(None, description="Vector embeddings for similarity search")
    searchable_content: Optional[str] = Field(None, description="Processed content for text search")
    tags: List[str] = Field(default_factory=list, description="Classification tags")
    
    # Validation and custom validators
    @validator('completed_at')
    def validate_completion_time(cls, v, values):
        if v is not None and 'started_at' in values:
            if v < values['started_at']:
                raise ValueError('Completion time must be after start time')
        return v
    
    @root_validator
    def validate_status_consistency(cls, values):
        status = values.get('status')
        completed_at = values.get('completed_at')
        findings = values.get('findings', [])
        
        if status == AnalysisStatus.COMPLETED:
            if completed_at is None:
                raise ValueError('Completed analyses must have completion time')
            if not findings and values.get('analysis_type') not in [AnalysisType.DOCUMENTATION_QUALITY]:
                values['warnings'] = values.get('warnings', []) + ['No findings generated for completed analysis']
        
        return values
    
    @validator('duration_seconds', always=True)
    def calculate_duration(cls, v, values):
        if v is None and 'started_at' in values and 'completed_at' in values:
            completed_at = values['completed_at']
            if completed_at is not None:
                return (completed_at - values['started_at']).total_seconds()
        return v
    
    # Utility methods
    def get_severity_summary(self) -> Dict[SeverityLevel, int]:
        """Get count of findings by severity"""
        summary = {severity: 0 for severity in SeverityLevel}
        for finding in self.findings:
            summary[finding.severity] += 1
        return summary
    
    def get_high_priority_recommendations(self) -> List[AnalysisRecommendation]:
        """Get high priority recommendations"""
        return [
            rec for rec in self.recommendations 
            if rec.overall_priority in [RecommendationPriority.IMMEDIATE, RecommendationPriority.HIGH]
        ]
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning-related metrics"""
        total_feedback = sum(len(finding.feedback_data) for finding in self.findings)
        avg_confidence = sum(finding.confidence_score for finding in self.findings) / len(self.findings) if self.findings else 0
        
        return {
            "total_feedback_items": total_feedback,
            "average_confidence_score": round(avg_confidence, 3),
            "learning_iteration": self.learning_iteration,
            "adaptations_count": len(self.adaptations_made),
            "novel_patterns": sum(
                1 for finding in self.findings 
                if finding.learning_metrics and finding.learning_metrics.novel_pattern_detection
            )
        }
    
    def is_actionable(self) -> bool:
        """Check if analysis has actionable recommendations"""
        return len(self.recommendations) > 0 and any(
            rec.overall_priority != RecommendationPriority.WHEN_POSSIBLE 
            for rec in self.recommendations
        )

# Batch Analysis Models
class BatchAnalysisRequest(BaseModel):
    """Request for batch analysis of multiple targets"""
    batch_id: UUID = Field(default_factory=uuid4)
    analysis_targets: List[str] = Field(..., min_items=1, description="List of analysis targets")
    analysis_types: List[AnalysisType] = Field(..., min_items=1)
    context: AnalysisContext
    priority: RecommendationPriority = Field(default=RecommendationPriority.MEDIUM)
    parallel_execution: bool = Field(default=True, description="Whether to run analyses in parallel")
    max_concurrent: int = Field(default=5, ge=1, le=20, description="Maximum concurrent analyses")

class BatchAnalysisResult(IdentifiableModel):
    """Results from batch analysis"""
    batch_id: UUID
    total_analyses: int = Field(..., ge=1)
    completed_analyses: int = Field(default=0, ge=0)
    failed_analyses: int = Field(default=0, ge=0)
    
    individual_results: List[AnalysisResult] = Field(default_factory=list)
    batch_summary: Dict[str, Any] = Field(default_factory=dict)
    aggregated_metrics: Optional[PerformanceMetrics] = Field(None)
    
    batch_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    batch_completed_at: Optional[datetime] = Field(None)
    
    @property
    def is_complete(self) -> bool:
        return self.completed_analyses + self.failed_analyses == self.total_analyses
    
    @property
    def success_rate(self) -> float:
        if self.total_analyses == 0:
            return 0.0
        return self.completed_analyses / self.total_analyses

# Export models for external use
__all__ = [
    # Enums
    'AnalysisType', 'SeverityLevel', 'ConfidenceLevel', 'AnalysisStatus',
    'RecommendationPriority', 'LearningFeedbackType',
    
    # Base models
    'TimestampedModel', 'IdentifiableModel',
    
    # Location and context
    'CodeLocation', 'AnalysisContext',
    
    # Learning and feedback
    'LearningMetrics', 'FeedbackData',
    
    # Core models
    'AnalysisFinding', 'RecommendationAction', 'AnalysisRecommendation',
    'PerformanceMetrics', 'QualityAssessment', 'AnalysisResult',
    
    # Batch models
    'BatchAnalysisRequest', 'BatchAnalysisResult'
]