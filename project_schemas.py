"""
YMERA Enterprise Multi-Agent System - Project Management Schemas
Production-ready Pydantic schemas for project lifecycle management
"""

from pydantic import BaseModel, Field, validator, root_validator, HttpUrl
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from enum import Enum
import uuid

from .base import BaseEntity, BaseSchema, ValidationResult, TimingInfo


# Project Enums
class ProjectStatus(str, Enum):
    """Project status states"""
    DRAFT = "draft"
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ProjectType(str, Enum):
    """Project type classifications"""
    WEB_APPLICATION = "web_application"
    MOBILE_APP = "mobile_app"
    API_SERVICE = "api_service"
    MICROSERVICE = "microservice"
    LIBRARY = "library"
    TOOL = "tool"
    FRAMEWORK = "framework"
    INFRASTRUCTURE = "infrastructure"
    DATA_PIPELINE = "data_pipeline"
    ML_MODEL = "ml_model"
    CUSTOM = "custom"


class ProjectPriority(str, Enum):
    """Project priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RepositoryProvider(str, Enum):
    """Repository hosting providers"""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE_DEVOPS = "azure_devops"
    CUSTOM = "custom"


class DeploymentEnvironment(str, Enum):
    """Deployment environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    TESTING = "testing"
    PRODUCTION = "production"
    PREVIEW = "preview"
    CUSTOM = "custom"


class CodeQualityLevel(str, Enum):
    """Code quality assessment levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class SecurityLevel(str, Enum):
    """Security assessment levels"""
    SECURE = "secure"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL_RISK = "critical_risk"


# Repository Models
class RepositoryConfig(BaseSchema):
    """Repository configuration"""
    
    provider: RepositoryProvider = Field(
        description="Repository hosting provider"
    )
    url: HttpUrl = Field(
        description="Repository URL"
    )
    branch: str = Field(
        default="main",
        description="Primary branch name"
    )
    access_token: Optional[str] = Field(
        None,
        description="Repository access token (will be masked)"
    )
    webhook_secret: Optional[str] = Field(
        None,
        description="Webhook secret for automated triggers"
    )
    auto_sync: bool = Field(
        default=True,
        description="Enable automatic synchronization"
    )
    sync_interval_minutes: int = Field(
        default=15,
        ge=5,
        le=1440,
        description="Synchronization interval in minutes"
    )
    
    @validator('access_token', pre=True)
    def mask_token(cls, v):
        """Mask access token for security"""
        if v and len(v) > 8:
            return f"{v[:4]}{'*' * (len(v) - 8)}{v[-4:]}"
        return v


class RepositoryStats(BaseSchema):
    """Repository statistics"""
    
    total_commits: int = Field(
        ge=0,
        description="Total number of commits"
    )
    contributors: int = Field(
        ge=0,
        description="Number of contributors"
    )
    branches: int = Field(
        ge=0,
        description="Number of branches"
    )
    tags: int = Field(
        ge=0,
        description="Number of tags/releases"
    )
    issues_open: int = Field(
        ge=0,
        description="Number of open issues"
    )
    issues_closed: int = Field(
        ge=0,
        description="Number of closed issues"
    )
    pull_requests_open: int = Field(
        ge=0,
        description="Number of open pull requests"
    )
    pull_requests_merged: int = Field(
        ge=0,
        description="Number of merged pull requests"
    )
    file_count: int = Field(
        ge=0,
        description="Total number of files"
    )
    lines_of_code: int = Field(
        ge=0,
        description="Total lines of code"
    )
    repository_size_mb: float = Field(
        ge=0.0,
        description="Repository size in megabytes"
    )
    last_commit: Optional[datetime] = Field(
        None,
        description="Last commit timestamp"
    )
    activity_score: float = Field(
        ge=0.0,
        le=10.0,
        description="Repository activity score (0-10)"
    )


# Technology Stack Models
class TechnologyStack(BaseSchema):
    """Project technology stack"""
    
    languages: List[str] = Field(
        description="Programming languages used"
    )
    frameworks: List[str] = Field(
        default_factory=list,
        description="Frameworks and libraries"
    )
    databases: List[str] = Field(
        default_factory=list,
        description="Database technologies"
    )
    cloud_providers: List[str] = Field(
        default_factory=list,
        description="Cloud service providers"
    )
    infrastructure: List[str] = Field(
        default_factory=list,
        description="Infrastructure tools and services"
    )
    testing_tools: List[str] = Field(
        default_factory=list,
        description="Testing frameworks and tools"
    )
    ci_cd_tools: List[str] = Field(
        default_factory=list,
        description="CI/CD pipeline tools"
    )
    monitoring_tools: List[str] = Field(
        default_factory=list,
        description="Monitoring and observability tools"
    )
    security_tools: List[str] = Field(
        default_factory=list,
        description="Security analysis tools"
    )
    other_tools: List[str] = Field(
        default_factory=list,
        description="Other development tools"
    )
    
    @validator('languages')
    def validate_languages(cls, v):
        """Ensure at least one programming language is specified"""
        if not v:
            raise ValueError('At least one programming language must be specified')
        return [lang.lower() for lang in v]


# Quality Assessment Models
class CodeMetrics(BaseSchema):
    """Code quality metrics"""
    
    complexity_score: float = Field(
        ge=0.0,
        le=10.0,
        description="Code complexity score (0-10)"
    )
    maintainability_index: float = Field(
        ge=0.0,
        le=100.0,
        description="Maintainability index (0-100)"
    )
    test_coverage: float = Field(
        ge=0.0,
        le=100.0,
        description="Test coverage percentage"
    )
    duplication_percentage: float = Field(
        ge=0.0,
        le=100.0,
        description="Code duplication percentage"
    )
    technical_debt_hours: float = Field(
        ge=0.0,
        description="Estimated technical debt in hours"
    )
    code_smells: int = Field(
        ge=0,
        description="Number of code smells detected"
    )
    bugs: int = Field(
        ge=0,
        description="Number of bugs detected"
    )
    vulnerabilities: int = Field(
        ge=0,
        description="Number of security vulnerabilities"
    )
    documentation_coverage: float = Field(
        ge=0.0,
        le=100.0,
        description="Documentation coverage percentage"
    )
    performance_score: float = Field(
        ge=0.0,
        le=10.0,
        description="Performance assessment score (0-10)"
    )


class QualityAssessment(BaseSchema):
    """Comprehensive quality assessment"""
    
    overall_score: float = Field(
        ge=0.0,
        le=10.0,
        description="Overall quality score (0-10)"
    )
    quality_level: CodeQualityLevel = Field(
        description="Quality level classification"
    )
    metrics: CodeMetrics = Field(
        description="Detailed code metrics"
    )
    recommendations: List[str] = Field(
        description="Quality improvement recommendations"
    )
    critical_issues: List[str] = Field(
        description="Critical issues requiring immediate attention"
    )
    improvement_priorities: List[str] = Field(
        description="Prioritized improvement areas"
    )
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Assessment timestamp"
    )
    assessor_agent: str = Field(
        description="Agent that performed the assessment"
    )
    assessment_version: str = Field(
        description="Assessment algorithm version"
    )


class SecurityAssessment(BaseSchema):
    """Security vulnerability assessment"""
    
    security_score: float = Field(
        ge=0.0,
        le=10.0,
        description="Security score (0-10, higher is better)"
    )
    security_level: SecurityLevel = Field(
        description="Security level classification"
    )
    vulnerabilities: List[Dict[str, Any]] = Field(
        description="Detailed vulnerability information"
    )
    compliance_checks: Dict[str, bool] = Field(
        description="Security compliance check results"
    )
    risk_factors: List[str] = Field(
        description="Identified security risk factors"
    )
    mitigation_steps: List[str] = Field(
        description="Recommended mitigation steps"
    )
    dependencies_with_issues: List[str] = Field(
        description="Dependencies with known vulnerabilities"
    )
    security_tools_used: List[str] = Field(
        description="Security analysis tools used"
    )
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Assessment timestamp"
    )
    assessor_agent: str = Field(
        description="Agent that performed the assessment"
    )


# Deployment Models
class DeploymentConfig(BaseSchema):
    """Deployment configuration"""
    
    environment: DeploymentEnvironment = Field(
        description="Target deployment environment"
    )
    provider: str = Field(
        description="Deployment provider (e.g., Vercel, Netlify, AWS)"
    )
    build_command: Optional[str] = Field(
        None,
        description="Build command for deployment"
    )
    start_command: Optional[str] = Field(
        None,
        description="Start command for the application"
    )
    environment_variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for deployment"
    )
    domains: List[str] = Field(
        default_factory=list,
        description="Custom domains for the deployment"
    )
    auto_deploy: bool = Field(
        default=False,
        description="Enable automatic deployment on code changes"
    )
    deployment_branch: str = Field(
        default="main",
        description="Branch to deploy from"
    )
    health_check_url: Optional[HttpUrl] = Field(
        None,
        description="Health check endpoint URL"
    )
    rollback_enabled: bool = Field(
        default=True,
        description="Enable automatic rollback on failure"
    )


class DeploymentStatus(BaseSchema):
    """Deployment status information"""
    
    deployment_id: str = Field(
        description="Deployment unique identifier"
    )
    status: str = Field(
        description="Current deployment status"
    )
    url: Optional[HttpUrl] = Field(
        None,
        description="Deployed application URL"
    )
    build_logs: List[str] = Field(
        default_factory=list,
        description="Build and deployment logs"
    )
    deployed_at: Optional[datetime] = Field(
        None,
        description="Deployment completion timestamp"
    )
    build_time_seconds: Optional[float] = Field(
        None,
        ge=0.0,
        description="Build time in seconds"
    )
    deploy_time_seconds: Optional[float] = Field(
        None,
        ge=0.0,
        description="Deployment time in seconds"
    )
    commit_sha: Optional[str] = Field(
        None,
        description="Git commit SHA for this deployment"
    )
    version: Optional[str] = Field(
        None,
        description="Deployment version"
    )
    health_status: Optional[str] = Field(
        None,
        description="Application health status"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if deployment failed"
    )


# Project Models
class ProjectRequirements(BaseSchema):
    """Project requirements specification"""
    
    functional_requirements: List[str] = Field(
        description="Functional requirements list"
    )
    non_functional_requirements: List[str] = Field(
        default_factory=list,
        description="Non-functional requirements list"
    )
    performance_requirements: Optional[Dict[str, Any]] = Field(
        None,
        description="Performance requirements specifications"
    )
    security_requirements: List[str] = Field(
        default_factory=list,
        description="Security requirements list"
    )
    compliance_requirements: List[str] = Field(
        default_factory=list,
        description="Compliance and regulatory requirements"
    )
    integration_requirements: List[str] = Field(
        default_factory=list,
        description="Third-party integration requirements"
    )
    scalability_requirements: Optional[Dict[str, Any]] = Field(
        None,
        description="Scalability requirements specifications"
    )
    availability_requirements: Optional[Dict[str, str]] = Field(
        None,
        description="Availability and uptime requirements"
    )
    business_rules: List[str] = Field(
        default_factory=list,
        description="Business rules and constraints"
    )


class ProjectTimeline(BaseSchema):
    """Project timeline and milestones"""
    
    start_date: datetime = Field(
        description="Project start date"
    )
    target_end_date: Optional[datetime] = Field(
        None,
        description="Target completion date"
    )
    actual_end_date: Optional[datetime] = Field(
        None,
        description="Actual completion date"
    )
    milestones: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Project milestones"
    )
    phases: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Project phases"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="External dependencies"
    )
    estimated_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Estimated development hours"
    )
    actual_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Actual development hours"
    )
    progress_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall progress percentage"
    )


class Project(BaseEntity):
    """Main project entity"""
    
    name: str = Field(
        description="Project name"
    )
    description: str = Field(
        description="Project description"
    )
    type: ProjectType = Field(
        description="Project type classification"
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.DRAFT,
        description="Current project status"
    )
    priority: ProjectPriority = Field(
        default=ProjectPriority.NORMAL,
        description="Project priority level"
    )
    owner: str = Field(
        description="Project owner/manager"
    )
    team_members: List[str] = Field(
        default_factory=list,
        description="Team member identifiers"
    )
    stakeholders: List[str] = Field(
        default_factory=list,
        description="Project stakeholder identifiers"
    )
    repository: Optional[RepositoryConfig] = Field(
        None,
        description="Repository configuration"
    )
    technology_stack: TechnologyStack = Field(
        description="Technology stack and tools used"
    )
    requirements: ProjectRequirements = Field(
        description="Project requirements specification"
    )
    timeline: ProjectTimeline = Field(
        description="Project timeline and milestones"
    )
    budget: Optional[Dict[str, Any]] = Field(
        None,
        description="Project budget information"
    )
    quality_assessment: Optional[QualityAssessment] = Field(
        None,
        description="Latest quality assessment"
    )
    security_assessment: Optional[SecurityAssessment] = Field(
        None,
        description="Latest security assessment"
    )
    deployments: Dict[DeploymentEnvironment, DeploymentConfig] = Field(
        default_factory=dict,
        description="Deployment configurations by environment"
    )
    deployment_status: Dict[DeploymentEnvironment, DeploymentStatus] = Field(
        default_factory=dict,
        description="Current deployment status by environment"
    )
    repository_stats: Optional[RepositoryStats] = Field(
        None,
        description="Repository statistics"
    )
    documentation_urls: List[HttpUrl] = Field(
        default_factory=list,
        description="Documentation and resource URLs"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Project notes and comments"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Project tags for categorization"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Validate project name"""
        if len(v.strip()) < 3:
            raise ValueError('Project name must be at least 3 characters long')
        return v.strip()
    
    @root_validator
    def validate_timeline_dates(cls, values):
        """Validate timeline date consistency"""
        timeline = values.get('timeline')
        if timeline:
            start_date = timeline.start_date
            target_end = timeline.target_end_date
            actual_end = timeline.actual_end_date
            
            if target_end and start_date >= target_end:
                raise ValueError('Target end date must be after start date')
            
            if actual_end and start_date >= actual_end:
                raise ValueError('Actual end date must be after start date')
        
        return values
    
    @root_validator
    def validate_team_structure(cls, values):
        """Validate team structure"""
        owner = values.get('owner')
        team_members = values.get('team_members', [])
        
        if owner in team_members:
            raise ValueError('Owner cannot be listed as a regular team member')
        
        return values


# Project Analytics Models
class ProjectMetrics(BaseSchema):
    """Project performance metrics"""
    
    velocity: float = Field(
        ge=0.0,
        description="Development velocity (story points/sprint)"
    )
    burndown_rate: float = Field(
        description="Task completion rate"
    )
    quality_trend: float = Field(
        ge=-1.0,
        le=1.0,
        description="Quality improvement trend (-1 to 1)"
    )
    team_productivity: float = Field(
        ge=0.0,
        le=10.0,
        description="Team productivity score (0-10)"
    )
    deadline_adherence: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentage of deadlines met"
    )
    scope_creep: float = Field(
        ge=0.0,
        description="Scope increase percentage"
    )
    defect_density: float = Field(
        ge=0.0,
        description="Defects per thousand lines of code"
    )
    customer_satisfaction: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Customer satisfaction score (0-10)"
    )
    cost_variance: float = Field(
        description="Budget variance percentage"
    )
    schedule_variance: float = Field(
        description="Schedule variance percentage"
    )


class ProjectAnalytics(BaseSchema):
    """Project analytics and insights"""
    
    metrics: ProjectMetrics = Field(
        description="Current project metrics"
    )
    trends: Dict[str, List[float]] = Field(
        description="Historical metric trends"
    )
    predictions: Dict[str, Any] = Field(
        description="AI-generated project predictions"
    )
    risk_factors: List[Dict[str, Any]] = Field(
        description="Identified risk factors"
    )
    recommendations: List[str] = Field(
        description="AI-generated recommendations"
    )
    bottlenecks: List[str] = Field(
        description="Identified project bottlenecks"
    )
    optimization_opportunities: List[str] = Field(
        description="Process optimization opportunities"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analytics generation timestamp"
    )
    analyzer_agent: str = Field(
        description="Agent that generated the analytics"
    )


# API Response Models
class ProjectListResponse(BaseSchema):
    """Project list API response"""
    
    projects: List[Project] = Field(
        description="List of projects"
    )
    total_count: int = Field(
        ge=0,
        description="Total number of projects"
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


class ProjectCreateRequest(BaseSchema):
    """Project creation request"""
    
    name: str = Field(
        description="Project name"
    )
    description: str = Field(
        description="Project description"
    )
    type: ProjectType = Field(
        description="Project type"
    )
    priority: ProjectPriority = Field(
        default=ProjectPriority.NORMAL,
        description="Project priority"
    )
    owner: str = Field(
        description="Project owner identifier"
    )
    team_members: List[str] = Field(
        default_factory=list,
        description="Initial team members"
    )
    technology_stack: TechnologyStack = Field(
        description="Technology stack"
    )
    requirements: ProjectRequirements = Field(
        description="Project requirements"
    )
    timeline: ProjectTimeline = Field(
        description="Project timeline"
    )
    repository: Optional[RepositoryConfig] = Field(
        None,
        description="Repository configuration"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Project tags"
    )


class ProjectUpdateRequest(BaseSchema):
    """Project update request"""
    
    name: Optional[str] = Field(
        None,
        description="Updated project name"
    )
    description: Optional[str] = Field(
        None,
        description="Updated project description"
    )
    status: Optional[ProjectStatus] = Field(
        None,
        description="Updated project status"
    )
    priority: Optional[ProjectPriority] = Field(
        None,
        description="Updated project priority"
    )
    team_members: Optional[List[str]] = Field(
        None,
        description="Updated team members list"
    )
    stakeholders: Optional[List[str]] = Field(
        None,
        description="Updated stakeholders list"
    )
    timeline: Optional[ProjectTimeline] = Field(
        None,
        description="Updated timeline"
    )
    notes: Optional[List[str]] = Field(
        None,
        description="Updated notes"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Updated tags"
    )


# Export all models
__all__ = [
    # Enums
    'ProjectStatus',
    'ProjectType', 
    'ProjectPriority',
    'RepositoryProvider',
    'DeploymentEnvironment',
    'CodeQualityLevel',
    'SecurityLevel',
    
    # Repository Models
    'RepositoryConfig',
    'RepositoryStats',
    
    # Technology Models
    'TechnologyStack',
    
    # Quality Models
    'CodeMetrics',
    'QualityAssessment',
    'SecurityAssessment',
    
    # Deployment Models
    'DeploymentConfig',
    'DeploymentStatus',
    
    # Project Core Models
    'ProjectRequirements',
    'ProjectTimeline',
    'Project',
    
    # Analytics Models
    'ProjectMetrics',
    'ProjectAnalytics',
    
    # API Models
    'ProjectListResponse',
    'ProjectCreateRequest',
    'ProjectUpdateRequest',
]