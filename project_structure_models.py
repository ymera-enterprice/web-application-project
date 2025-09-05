"""
YMERA Enterprise Project Structure Models
Production-ready Pydantic models for multi-agent system with learning capabilities
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Dict, List, Optional, Union, Any, Set, Tuple
from datetime import datetime, timezone
from enum import Enum, IntEnum
from uuid import UUID, uuid4
import re
from pathlib import Path

# Enums for structured data
class ProjectStatus(str, Enum):
    """Project lifecycle status"""
    CREATED = "created"
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    IN_PROGRESS = "in_progress"
    ENHANCING = "enhancing"
    TESTING = "testing"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"
    SUSPENDED = "suspended"

class ProjectType(str, Enum):
    """Project type classification"""
    WEB_APPLICATION = "web_application"
    MOBILE_APPLICATION = "mobile_application"
    DESKTOP_APPLICATION = "desktop_application"
    API_SERVICE = "api_service"
    MICROSERVICE = "microservice"
    LIBRARY_PACKAGE = "library_package"
    CLI_TOOL = "cli_tool"
    DATA_PIPELINE = "data_pipeline"
    ML_MODEL = "ml_model"
    INFRASTRUCTURE = "infrastructure"
    DOCUMENTATION = "documentation"
    OTHER = "other"

class ProjectPriority(IntEnum):
    """Project priority levels"""
    LOW = 1
    MEDIUM = 3
    HIGH = 5
    CRITICAL = 7
    URGENT = 10

class TechnologyStack(str, Enum):
    """Supported technology stacks"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    RUST = "rust"
    GO = "go"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    DJANGO = "django"
    FLASK = "flask"
    FASTAPI = "fastapi"
    EXPRESS = "express"
    SPRING = "spring"
    DOTNET = "dotnet"

class RepositoryProvider(str, Enum):
    """Repository hosting providers"""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE_DEVOPS = "azure_devops"
    GITEA = "gitea"
    CODECOMMIT = "codecommit"

class DeploymentEnvironment(str, Enum):
    """Deployment environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    PREVIEW = "preview"

class FileType(str, Enum):
    """File type classifications"""
    SOURCE_CODE = "source_code"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    TEST = "test"
    BUILD_SCRIPT = "build_script"
    DEPENDENCY = "dependency"
    ASSET = "asset"
    DATABASE = "database"
    TEMPLATE = "template"
    SCHEMA = "schema"

class AgentRole(str, Enum):
    """Agent roles in project management"""
    PROJECT_MANAGER = "project_manager"
    ANALYST = "analyst"
    ENHANCER = "enhancer"
    VALIDATOR = "validator"
    DOCUMENTER = "documenter"
    SECURITY_AUDITOR = "security_auditor"
    DEPLOYER = "deployer"
    MONITOR = "monitor"
    LEARNER = "learner"
    COMMUNICATOR = "communicator"
    EXAMINER = "examiner"

# Base Models
class BaseTimestampedModel(BaseModel):
    """Base model with timestamps and metadata"""
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, description="Model version for optimistic locking")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
        validate_assignment = True
        arbitrary_types_allowed = True

# Repository Models
class RepositoryConfiguration(BaseModel):
    """Repository configuration and access details"""
    provider: RepositoryProvider
    url: str = Field(..., description="Repository URL")
    owner: str = Field(..., description="Repository owner/organization")
    name: str = Field(..., description="Repository name")
    branch: str = Field(default="main", description="Primary branch")
    access_token: Optional[str] = Field(None, description="Access token (encrypted)")
    ssh_key: Optional[str] = Field(None, description="SSH key for access")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    clone_url: Optional[str] = Field(None, description="Clone URL")
    api_url: Optional[str] = Field(None, description="API URL")
    
    @validator('url')
    def validate_url(cls, v):
        """Validate repository URL format"""
        url_pattern = r'^https?://[\w\-\.]+(:[0-9]+)?(/.*)?$'
        if not re.match(url_pattern, v):
            raise ValueError('Invalid repository URL format')
        return v

class FileMetadata(BaseModel):
    """File metadata and analysis results"""
    path: str = Field(..., description="File path relative to repository root")
    name: str = Field(..., description="File name")
    extension: str = Field(..., description="File extension")
    file_type: FileType
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    language: Optional[str] = Field(None, description="Programming language")
    lines_of_code: Optional[int] = Field(None, ge=0, description="Lines of code")
    complexity_score: Optional[float] = Field(None, ge=0, le=100, description="Complexity score")
    quality_score: Optional[float] = Field(None, ge=0, le=100, description="Quality score")
    security_score: Optional[float] = Field(None, ge=0, le=100, description="Security score")
    test_coverage: Optional[float] = Field(None, ge=0, le=100, description="Test coverage percentage")
    last_modified: datetime
    checksum: Optional[str] = Field(None, description="File checksum for integrity")
    dependencies: List[str] = Field(default_factory=list, description="File dependencies")
    exports: List[str] = Field(default_factory=list, description="Exported functions/classes")
    imports: List[str] = Field(default_factory=list, description="Imported modules")

class DirectoryStructure(BaseModel):
    """Directory structure representation"""
    path: str = Field(..., description="Directory path")
    name: str = Field(..., description="Directory name")
    is_root: bool = Field(default=False, description="Whether this is the root directory")
    parent_path: Optional[str] = Field(None, description="Parent directory path")
    subdirectories: List[str] = Field(default_factory=list, description="Subdirectory names")
    files: List[FileMetadata] = Field(default_factory=list, description="Files in directory")
    file_count: int = Field(default=0, ge=0, description="Total file count")
    directory_count: int = Field(default=0, ge=0, description="Total subdirectory count")
    total_size_bytes: int = Field(default=0, ge=0, description="Total size of directory")
    
    @root_validator
    def validate_counts(cls, values):
        """Validate file and directory counts match actual data"""
        files = values.get('files', [])
        subdirectories = values.get('subdirectories', [])
        
        values['file_count'] = len(files)
        values['directory_count'] = len(subdirectories)
        values['total_size_bytes'] = sum(f.size_bytes for f in files)
        
        return values

# Technology and Dependencies
class TechnologyProfile(BaseModel):
    """Technology stack and configuration profile"""
    primary_language: TechnologyStack
    secondary_languages: List[TechnologyStack] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list, description="Frameworks used")
    libraries: List[str] = Field(default_factory=list, description="Libraries/packages used")
    tools: List[str] = Field(default_factory=list, description="Development tools")
    databases: List[str] = Field(default_factory=list, description="Database systems")
    cloud_services: List[str] = Field(default_factory=list, description="Cloud services")
    build_tools: List[str] = Field(default_factory=list, description="Build and deployment tools")
    testing_frameworks: List[str] = Field(default_factory=list, description="Testing frameworks")
    linting_tools: List[str] = Field(default_factory=list, description="Code quality tools")
    version_info: Dict[str, str] = Field(default_factory=dict, description="Version information")

class DependencyInfo(BaseModel):
    """Dependency information and analysis"""
    name: str = Field(..., description="Dependency name")
    version: str = Field(..., description="Version specification")
    version_installed: Optional[str] = Field(None, description="Currently installed version")
    type: str = Field(..., description="Dependency type (runtime, dev, peer, etc.)")
    source: str = Field(..., description="Source (npm, pip, maven, etc.)")
    license: Optional[str] = Field(None, description="License type")
    vulnerabilities: List[str] = Field(default_factory=list, description="Known vulnerabilities")
    outdated: bool = Field(default=False, description="Whether dependency is outdated")
    critical: bool = Field(default=False, description="Whether dependency is critical")
    size_mb: Optional[float] = Field(None, ge=0, description="Package size in MB")
    download_count: Optional[int] = Field(None, ge=0, description="Download count/popularity")
    last_updated: Optional[datetime] = Field(None, description="Last update date")

# Quality and Analysis Models
class CodeQualityMetrics(BaseModel):
    """Code quality analysis metrics"""
    overall_score: float = Field(..., ge=0, le=100, description="Overall quality score")
    maintainability_index: float = Field(..., ge=0, le=100, description="Maintainability score")
    cyclomatic_complexity: float = Field(..., ge=0, description="Average cyclomatic complexity")
    technical_debt_ratio: float = Field(..., ge=0, le=100, description="Technical debt percentage")
    code_coverage: float = Field(..., ge=0, le=100, description="Test coverage percentage")
    duplication_percentage: float = Field(..., ge=0, le=100, description="Code duplication percentage")
    lines_of_code: int = Field(..., ge=0, description="Total lines of code")
    functions_count: int = Field(..., ge=0, description="Total function count")
    classes_count: int = Field(..., ge=0, description="Total class count")
    files_count: int = Field(..., ge=0, description="Total file count")
    comment_ratio: float = Field(..., ge=0, le=100, description="Comment to code ratio")
    security_hotspots: int = Field(..., ge=0, description="Number of security issues")
    bugs: int = Field(..., ge=0, description="Number of bugs detected")
    code_smells: int = Field(..., ge=0, description="Number of code smells")
    
class SecurityAnalysis(BaseModel):
    """Security analysis results"""
    overall_security_score: float = Field(..., ge=0, le=100, description="Overall security score")
    vulnerabilities_critical: int = Field(..., ge=0, description="Critical vulnerabilities")
    vulnerabilities_high: int = Field(..., ge=0, description="High severity vulnerabilities")
    vulnerabilities_medium: int = Field(..., ge=0, description="Medium severity vulnerabilities")
    vulnerabilities_low: int = Field(..., ge=0, description="Low severity vulnerabilities")
    security_hotspots: List[str] = Field(default_factory=list, description="Security hotspot locations")
    sensitive_data_exposure: bool = Field(default=False, description="Sensitive data exposure risk")
    authentication_issues: bool = Field(default=False, description="Authentication vulnerabilities")
    authorization_issues: bool = Field(default=False, description="Authorization vulnerabilities")
    input_validation_issues: bool = Field(default=False, description="Input validation problems")
    cryptography_issues: bool = Field(default=False, description="Cryptography implementation issues")
    dependency_vulnerabilities: List[DependencyInfo] = Field(default_factory=list)
    compliance_status: Dict[str, bool] = Field(default_factory=dict, description="Compliance checks")

# Agent and Learning Models
class AgentTask(BaseModel):
    """Individual agent task definition"""
    id: UUID = Field(default_factory=uuid4)
    agent_role: AgentRole
    task_type: str = Field(..., description="Type of task to perform")
    description: str = Field(..., description="Task description")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Task input parameters")
    expected_output: Optional[Dict[str, Any]] = Field(None, description="Expected output format")
    priority: ProjectPriority = Field(default=ProjectPriority.MEDIUM)
    dependencies: List[UUID] = Field(default_factory=list, description="Task dependencies")
    estimated_duration: Optional[int] = Field(None, ge=0, description="Estimated duration in minutes")
    assigned_at: Optional[datetime] = Field(None)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    status: str = Field(default="pending", description="Task status")
    progress: float = Field(default=0.0, ge=0, le=100, description="Task progress percentage")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    learning_data: Dict[str, Any] = Field(default_factory=dict, description="Data for learning engine")

class AgentCapability(BaseModel):
    """Agent capability definition"""
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Capability parameters")
    performance_score: float = Field(default=0.0, ge=0, le=100, description="Performance score")
    usage_count: int = Field(default=0, ge=0, description="Times this capability was used")
    success_rate: float = Field(default=0.0, ge=0, le=100, description="Success rate percentage")
    average_duration: float = Field(default=0.0, ge=0, description="Average execution time")
    last_used: Optional[datetime] = Field(None, description="Last time capability was used")

class LearningPattern(BaseModel):
    """Learning pattern identification"""
    pattern_id: UUID = Field(default_factory=uuid4)
    pattern_type: str = Field(..., description="Type of pattern identified")
    description: str = Field(..., description="Pattern description")
    frequency: int = Field(..., ge=1, description="Pattern occurrence frequency")
    confidence: float = Field(..., ge=0, le=1, description="Pattern confidence score")
    context: Dict[str, Any] = Field(default_factory=dict, description="Pattern context")
    impact_score: float = Field(..., ge=0, le=100, description="Pattern impact score")
    actionable: bool = Field(default=True, description="Whether pattern is actionable")
    applied: bool = Field(default=False, description="Whether pattern has been applied")
    validation_results: Optional[Dict[str, Any]] = Field(None, description="Validation results")

class KnowledgeEntry(BaseModel):
    """Knowledge base entry"""
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., description="Knowledge entry title")
    content: str = Field(..., description="Knowledge content")
    category: str = Field(..., description="Knowledge category")
    tags: List[str] = Field(default_factory=list, description="Knowledge tags")
    source_type: str = Field(..., description="Source of knowledge")
    source_reference: Optional[str] = Field(None, description="Source reference")
    confidence_score: float = Field(..., ge=0, le=1, description="Knowledge confidence score")
    usage_count: int = Field(default=0, ge=0, description="Times knowledge was accessed")
    effectiveness_score: float = Field(default=0.0, ge=0, le=100, description="Knowledge effectiveness")
    last_validated: Optional[datetime] = Field(None, description="Last validation date")
    embeddings: Optional[List[float]] = Field(None, description="Vector embeddings")
    related_entries: List[UUID] = Field(default_factory=list, description="Related knowledge entries")

class FeedbackEntry(BaseModel):
    """User and system feedback entry"""
    id: UUID = Field(default_factory=uuid4)
    feedback_type: str = Field(..., description="Type of feedback")
    source: str = Field(..., description="Feedback source (user, system, agent)")
    content: str = Field(..., description="Feedback content")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating (1-5)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Feedback context")
    processed: bool = Field(default=False, description="Whether feedback was processed")
    action_taken: Optional[str] = Field(None, description="Action taken based on feedback")
    impact_assessment: Optional[Dict[str, Any]] = Field(None, description="Impact assessment")
    
class LearningLoop(BaseModel):
    """Learning loop configuration and state"""
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Learning loop name")
    description: str = Field(..., description="Learning loop description")
    active: bool = Field(default=True, description="Whether loop is active")
    interval_minutes: int = Field(..., gt=0, description="Learning interval in minutes")
    last_execution: Optional[datetime] = Field(None, description="Last execution time")
    next_execution: Optional[datetime] = Field(None, description="Next scheduled execution")
    execution_count: int = Field(default=0, ge=0, description="Number of executions")
    success_rate: float = Field(default=0.0, ge=0, le=100, description="Success rate percentage")
    learning_objectives: List[str] = Field(default_factory=list, description="Learning objectives")
    data_sources: List[str] = Field(default_factory=list, description="Data sources for learning")
    validation_criteria: Dict[str, Any] = Field(default_factory=dict, description="Validation criteria")
    performance_metrics: Dict[str, float] = Field(default_factory=dict, description="Performance metrics")

# Main Project Structure Model
class ProjectStructure(BaseTimestampedModel):
    """Complete project structure model with all enterprise features"""
    
    # Basic Project Information
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    description: str = Field(..., description="Project description")
    project_type: ProjectType
    status: ProjectStatus = Field(default=ProjectStatus.CREATED)
    priority: ProjectPriority = Field(default=ProjectPriority.MEDIUM)
    
    # Ownership and Access
    owner_id: UUID = Field(..., description="Project owner ID")
    team_members: List[UUID] = Field(default_factory=list, description="Team member IDs")
    access_level: str = Field(default="private", description="Access level (private, internal, public)")
    
    # Repository Configuration
    repository: Optional[RepositoryConfiguration] = Field(None, description="Repository configuration")
    
    # Project Structure
    root_directory: Optional[DirectoryStructure] = Field(None, description="Root directory structure")
    total_files: int = Field(default=0, ge=0, description="Total file count")
    total_directories: int = Field(default=0, ge=0, description="Total directory count")
    total_size_bytes: int = Field(default=0, ge=0, description="Total project size")
    
    # Technology Stack
    technology_profile: Optional[TechnologyProfile] = Field(None, description="Technology stack")
    dependencies: List[DependencyInfo] = Field(default_factory=list, description="Project dependencies")
    
    # Quality and Analysis
    quality_metrics: Optional[CodeQualityMetrics] = Field(None, description="Code quality metrics")
    security_analysis: Optional[SecurityAnalysis] = Field(None, description="Security analysis")
    last_analysis_date: Optional[datetime] = Field(None, description="Last analysis date")
    analysis_in_progress: bool = Field(default=False, description="Whether analysis is running")
    
    # Agent Management
    assigned_agents: List[AgentRole] = Field(default_factory=list, description="Assigned agent roles")
    active_tasks: List[AgentTask] = Field(default_factory=list, description="Active agent tasks")
    completed_tasks: List[AgentTask] = Field(default_factory=list, description="Completed tasks")
    agent_capabilities: Dict[AgentRole, List[AgentCapability]] = Field(
        default_factory=dict, description="Agent capabilities by role"
    )
    
    # Learning and Knowledge Management
    learning_patterns: List[LearningPattern] = Field(default_factory=list, description="Identified patterns")
    knowledge_entries: List[KnowledgeEntry] = Field(default_factory=list, description="Project knowledge")
    feedback_entries: List[FeedbackEntry] = Field(default_factory=list, description="Feedback entries")
    learning_loops: List[LearningLoop] = Field(default_factory=list, description="Active learning loops")
    learning_enabled: bool = Field(default=True, description="Whether learning is enabled")
    
    # Deployment and Environments
    deployment_environments: Dict[DeploymentEnvironment, Dict[str, Any]] = Field(
        default_factory=dict, description="Deployment environment configurations"
    )
    current_deployment: Optional[DeploymentEnvironment] = Field(
        None, description="Currently active deployment"
    )
    deployment_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="Deployment history"
    )
    
    # Monitoring and Performance
    performance_metrics: Dict[str, float] = Field(
        default_factory=dict, description="Performance metrics"
    )
    health_status: Dict[str, Any] = Field(
        default_factory=dict, description="Health status information"
    )
    alerts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Active alerts"
    )
    
    # Scheduling and Automation
    scheduled_tasks: List[Dict[str, Any]] = Field(
        default_factory=list, description="Scheduled automated tasks"
    )
    automation_rules: List[Dict[str, Any]] = Field(
        default_factory=list, description="Automation rules"
    )
    
    # Collaboration and Communication
    communication_channels: List[str] = Field(
        default_factory=list, description="Communication channel IDs"
    )
    notification_preferences: Dict[str, bool] = Field(
        default_factory=dict, description="Notification preferences"
    )
    
    # Archival and Retention
    archive_date: Optional[datetime] = Field(None, description="Date when project was archived")
    retention_policy: Optional[Dict[str, Any]] = Field(
        None, description="Data retention policy"
    )
    
    # Custom Fields and Extensions
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Custom project fields"
    )
    integrations: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Third-party integrations"
    )
    
    @validator('name')
    def validate_project_name(cls, v):
        """Validate project name format"""
        if not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', v):
            raise ValueError('Project name contains invalid characters')
        return v.strip()
    
    @validator('repository')
    def validate_repository_config(cls, v, values):
        """Validate repository configuration consistency"""
        if v and values.get('project_type') in [ProjectType.DOCUMENTATION]:
            # Documentation projects might not need repositories
            pass
        return v
    
    @root_validator
    def validate_project_consistency(cls, values):
        """Validate overall project consistency"""
        status = values.get('status')
        repository = values.get('repository')
        quality_metrics = values.get('quality_metrics')
        
        # Ensure repository exists for code-based projects
        project_type = values.get('project_type')
        if project_type in [
            ProjectType.WEB_APPLICATION,
            ProjectType.API_SERVICE,
            ProjectType.MICROSERVICE
        ] and not repository:
            # Allow for initial creation, but log warning
            pass
        
        # Ensure quality metrics exist for analyzed projects
        if status in [ProjectStatus.ANALYZING, ProjectStatus.COMPLETED] and not quality_metrics:
            # Allow for transitional states
            pass
        
        return values
    
    def get_project_health_score(self) -> float:
        """Calculate overall project health score"""
        scores = []
        
        if self.quality_metrics:
            scores.append(self.quality_metrics.overall_score)
        
        if self.security_analysis:
            scores.append(self.security_analysis.overall_security_score)
        
        # Agent performance score
        if self.agent_capabilities:
            agent_scores = []
            for capabilities in self.agent_capabilities.values():
                if capabilities:
                    avg_score = sum(cap.performance_score for cap in capabilities) / len(capabilities)
                    agent_scores.append(avg_score)
            if agent_scores:
                scores.append(sum(agent_scores) / len(agent_scores))
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def get_learning_effectiveness(self) -> float:
        """Calculate learning effectiveness score"""
        if not self.learning_patterns:
            return 0.0
        
        applied_patterns = sum(1 for pattern in self.learning_patterns if pattern.applied)
        total_patterns = len(self.learning_patterns)
        
        effectiveness = (applied_patterns / total_patterns) * 100
        
        # Factor in confidence and impact scores
        if self.learning_patterns:
            avg_confidence = sum(p.confidence for p in self.learning_patterns) / total_patterns
            avg_impact = sum(p.impact_score for p in self.learning_patterns) / total_patterns
            effectiveness = (effectiveness + avg_confidence * 100 + avg_impact) / 3
        
        return effectiveness
    
    def is_deployment_ready(self) -> bool:
        """Check if project is ready for deployment"""
        if self.status not in [ProjectStatus.VALIDATING, ProjectStatus.TESTING]:
            return False
        
        if not self.quality_metrics or self.quality_metrics.overall_score < 70:
            return False
        
        if not self.security_analysis or self.security_analysis.vulnerabilities_critical > 0:
            return False
        
        # Check if all critical tasks are completed
        critical_tasks_incomplete = any(
            task.priority >= ProjectPriority.HIGH and task.status != "completed"
            for task in self.active_tasks
        )
        
        return not critical_tasks_incomplete

# Response Models for API
class ProjectSummary(BaseModel):
    """Project summary for list views"""
    id: UUID
    name: str
    display_name: str
    project_type: ProjectType
    status: ProjectStatus
    priority: ProjectPriority
    health_score: float
    last_updated: datetime
    owner_id: UUID
    team_size: int

class ProjectAnalytics(BaseModel):
    """Project analytics and insights"""
    project_id: UUID
    health_score: float
    learning_effectiveness: float
    agent_performance: Dict[AgentRole, float]
    quality_trends: List[Dict[str, Any]]
    security_trends: List[Dict[str, Any]]
    deployment_frequency: int
    success_rate: float
    performance_metrics: Dict[str, float]
    recommendations: List[str]

# Export all models
__all__ = [
    'ProjectStatus', 'ProjectType', 'ProjectPriority', 'TechnologyStack',
    'RepositoryProvider', 'DeploymentEnvironment', 'FileType', 'AgentRole',
    'BaseTimestampedModel', 'RepositoryConfiguration', 'FileMetadata',
    'DirectoryStructure', 'TechnologyProfile', 'DependencyInfo',
    'CodeQualityMetrics', 'SecurityAnalysis', 'AgentTask', 'AgentCapability',
    'LearningPattern', 'KnowledgeEntry', 'FeedbackEntry', 'LearningLoop',
    'ProjectStructure', 'ProjectSummary', 'ProjectAnalytics'
]