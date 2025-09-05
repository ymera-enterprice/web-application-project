"""
YMERA Enterprise Database Models - Production Ready
Comprehensive SQLAlchemy models for multi-agent system with learning engine
"""

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean, JSON, Float, 
    ForeignKey, UniqueConstraint, Index, CheckConstraint, BigInteger,
    Enum, DECIMAL, LargeBinary, Table, MetaData
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum as PyEnum
import uuid
import json

# SQLAlchemy Base
Base = declarative_base()
metadata = MetaData()

# Enums for type safety
class ProjectStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"

class AgentStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    LEARNING = "learning"
    SHUTDOWN = "shutdown"

class AgentType(PyEnum):
    CORE = "core"
    SPECIALIZED = "specialized"
    LEARNING = "learning"
    MONITORING = "monitoring"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    ANALYSIS = "analysis"
    ENHANCEMENT = "enhancement"
    VALIDATION = "validation"
    DOCUMENTATION = "documentation"
    COMMUNICATION = "communication"
    EXAMINATION = "examination"
    PROJECT_MANAGEMENT = "project_management"

class TaskStatus(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"
    RETRY = "retry"

class TaskPriority(PyEnum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5

class LLMProvider(PyEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    LOCAL = "local"

class LearningType(PyEnum):
    FEEDBACK = "feedback"
    PATTERN = "pattern"
    IMPROVEMENT = "improvement"
    ERROR_CORRECTION = "error_correction"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    KNOWLEDGE_ACQUISITION = "knowledge_acquisition"
    BEHAVIORAL_ADAPTATION = "behavioral_adaptation"

class MetricType(PyEnum):
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    EFFICIENCY = "efficiency"
    RESOURCE_USAGE = "resource_usage"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"

class SecurityLevel(PyEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOP_SECRET = "top_secret"

class DeploymentStatus(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"

# Association tables for many-to-many relationships
agent_capabilities_table = Table(
    'agent_capabilities',
    Base.metadata,
    Column('agent_id', String, ForeignKey('agents.id'), primary_key=True),
    Column('capability_id', String, ForeignKey('capabilities.id'), primary_key=True),
    Column('proficiency_score', Float, default=0.0),
    Column('acquired_at', DateTime, default=func.now()),
    Column('last_used', DateTime),
    Index('idx_agent_capabilities_agent', 'agent_id'),
    Index('idx_agent_capabilities_capability', 'capability_id')
)

agent_collaborations_table = Table(
    'agent_collaborations',
    Base.metadata,
    Column('primary_agent_id', String, ForeignKey('agents.id'), primary_key=True),
    Column('collaborator_agent_id', String, ForeignKey('agents.id'), primary_key=True),
    Column('collaboration_type', String, default='support'),
    Column('efficiency_score', Float, default=0.0),
    Column('created_at', DateTime, default=func.now()),
    Column('last_collaboration', DateTime),
    Index('idx_agent_collaborations_primary', 'primary_agent_id'),
    Index('idx_agent_collaborations_collaborator', 'collaborator_agent_id')
)

user_roles_table = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('role_id', String, ForeignKey('roles.id'), primary_key=True),
    Column('assigned_at', DateTime, default=func.now()),
    Column('assigned_by', String, ForeignKey('users.id')),
    Index('idx_user_roles_user', 'user_id'),
    Index('idx_user_roles_role', 'role_id')
)

project_tags_table = Table(
    'project_tags',
    Base.metadata,
    Column('project_id', String, ForeignKey('projects.id'), primary_key=True),
    Column('tag_id', String, ForeignKey('tags.id'), primary_key=True),
    Column('created_at', DateTime, default=func.now()),
    Index('idx_project_tags_project', 'project_id'),
    Index('idx_project_tags_tag', 'tag_id')
)

# Core Models
class User(Base):
    """Enhanced user model with comprehensive security and audit features"""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile information
    first_name = Column(String(100))
    last_name = Column(String(100))
    display_name = Column(String(200))
    avatar_url = Column(String(500))
    bio = Column(Text)
    timezone = Column(String(50), default='UTC')
    locale = Column(String(10), default='en-US')
    
    # Status and security
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    security_level = Column(Enum(SecurityLevel), default=SecurityLevel.INTERNAL, nullable=False)
    
    # Authentication and security
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255))
    api_key = Column(String(255), unique=True, index=True)
    last_password_change = Column(DateTime)
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime)
    
    # Access control
    permissions = Column(JSON, default=list)
    access_restrictions = Column(JSON, default=dict)
    ip_whitelist = Column(JSON, default=list)
    session_timeout = Column(Integer, default=3600)  # seconds
    
    # Audit trail
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime)
    last_activity = Column(DateTime)
    login_count = Column(Integer, default=0)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    
    # Preferences and settings
    preferences = Column(JSON, default=dict)
    notification_settings = Column(JSON, default=dict)
    ui_settings = Column(JSON, default=dict)
    
    # Analytics
    total_projects = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    performance_score = Column(Float, default=0.0)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles_table, back_populates="users")
    created_projects = relationship("Project", back_populates="owner", foreign_keys="Project.owner_id")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    audit_logs = relationship("AuditLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    api_tokens = relationship("APIToken", back_populates="user", cascade="all, delete-orphan")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_users_email_active', 'email', 'is_active'),
        Index('idx_users_username_active', 'username', 'is_active'),
        Index('idx_users_last_activity', 'last_activity'),
        Index('idx_users_security_level', 'security_level'),
        CheckConstraint('length(username) >= 3', name='username_min_length'),
        CheckConstraint('length(email) >= 5', name='email_min_length'),
    )
    
    @validates('email')
    def validate_email(self, key, email):
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Invalid email format")
        return email.lower()
    
    @hybrid_property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.username
    
    @hybrid_property
    def is_locked(self):
        return self.locked_until and self.locked_until > datetime.utcnow()
    
    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email if include_sensitive else None,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        return data

class Role(Base):
    """Role-based access control model"""
    __tablename__ = 'roles'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    
    # Permissions and access control
    permissions = Column(JSON, default=list)
    resource_access = Column(JSON, default=dict)
    is_system_role = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Hierarchy and inheritance
    parent_role_id = Column(String, ForeignKey('roles.id'))
    inherits_permissions = Column(Boolean, default=True, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String, ForeignKey('users.id'))
    
    # Relationships
    users = relationship("User", secondary=user_roles_table, back_populates="roles")
    parent_role = relationship("Role", remote_side="Role.id", backref="child_roles")
    creator = relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        Index('idx_roles_name_active', 'name', 'is_active'),
        Index('idx_roles_parent', 'parent_role_id'),
    )

class Project(Base):
    """Enhanced project model with comprehensive tracking and analytics"""
    __tablename__ = 'projects'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    display_name = Column(String(300))
    description = Column(Text)
    
    # Repository and source control
    repository_url = Column(String(500), index=True)
    repository_type = Column(String(50), default='git')  # git, svn, etc.
    default_branch = Column(String(100), default='main')
    last_commit_sha = Column(String(40))
    last_commit_date = Column(DateTime)
    
    # Project metadata
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False, index=True)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    security_level = Column(Enum(SecurityLevel), default=SecurityLevel.INTERNAL, nullable=False)
    category = Column(String(100), index=True)
    subcategory = Column(String(100))
    
    # Ownership and team
    owner_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    team_lead_id = Column(String, ForeignKey('users.id'))
    organization_id = Column(String, ForeignKey('organizations.id'))
    
    # Configuration and settings
    configuration = Column(JSON, default=dict)
    environment_config = Column(JSON, default=dict)
    deployment_config = Column(JSON, default=dict)
    quality_gates = Column(JSON, default=dict)
    
    # Analytics and metrics
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    total_agents_used = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    average_task_duration = Column(Float, default=0.0)  # seconds
    code_quality_score = Column(Float, default=0.0)
    security_score = Column(Float, default=0.0)
    performance_score = Column(Float, default=0.0)
    technical_debt_score = Column(Float, default=0.0)
    
    # Resource usage
    cpu_hours_used = Column(Float, default=0.0)
    memory_gb_hours = Column(Float, default=0.0)
    storage_gb_used = Column(Float, default=0.0)
    api_calls_made = Column(BigInteger, default=0)
    cost_accumulated = Column(DECIMAL(10, 2), default=0.00)
    
    # Timeline and scheduling
    start_date = Column(DateTime)
    target_completion_date = Column(DateTime)
    actual_completion_date = Column(DateTime)
    last_analysis_date = Column(DateTime)
    next_scheduled_analysis = Column(DateTime)
    
    # Flags and features
    auto_analysis_enabled = Column(Boolean, default=True, nullable=False)
    continuous_learning_enabled = Column(Boolean, default=True, nullable=False)
    security_scanning_enabled = Column(Boolean, default=True, nullable=False)
    deployment_automation_enabled = Column(Boolean, default=False, nullable=False)
    monitoring_enabled = Column(Boolean, default=True, nullable=False)
    
    # Audit trail
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    archived_at = Column(DateTime)
    
    # Flexible metadata
    metadata_json = Column(JSON, default=dict)
    custom_fields = Column(JSON, default=dict)
    
    # Relationships
    owner = relationship("User", back_populates="created_projects", foreign_keys=[owner_id])
    team_lead = relationship("User", foreign_keys=[team_lead_id])
    organization = relationship("Organization", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")
    security_scans = relationship("SecurityScan", back_populates="project", cascade="all, delete-orphan")
    quality_reports = relationship("QualityReport", back_populates="project", cascade="all, delete-orphan")
    learning_records = relationship("LearningRecord", back_populates="project")
    tags = relationship("Tag", secondary=project_tags_table, back_populates="projects")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_projects_owner_status', 'owner_id', 'status'),
        Index('idx_projects_repository', 'repository_url'),
        Index('idx_projects_created', 'created_at'),
        Index('idx_projects_updated', 'updated_at'),
        Index('idx_projects_category', 'category', 'subcategory'),
        Index('idx_projects_priority_status', 'priority', 'status'),
        UniqueConstraint('name', 'owner_id', name='unique_project_name_per_owner'),
    )
    
    @hybrid_property
    def completion_percentage(self):
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100.0
    
    @hybrid_property
    def is_overdue(self):
        return (self.target_completion_date and 
                self.target_completion_date < datetime.utcnow() and 
                self.status != ProjectStatus.ARCHIVED)

class Organization(Base):
    """Organization/Company model for enterprise features"""
    __tablename__ = 'organizations'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    
    # Contact and location
    website = Column(String(500))
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(JSON, default=dict)  # structured address
    
    # Settings and configuration
    settings = Column(JSON, default=dict)
    security_policy = Column(JSON, default=dict)
    resource_limits = Column(JSON, default=dict)
    
    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    tier = Column(String(50), default='standard')  # free, standard, premium, enterprise
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    projects = relationship("Project", back_populates="organization")
    members = relationship("User", backref="organization")
    
    __table_args__ = (
        Index('idx_organizations_slug', 'slug'),
        Index('idx_organizations_active', 'is_active'),
    )

class Agent(Base):
    """Comprehensive agent model with advanced learning and collaboration features"""
    __tablename__ = 'agents'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    display_name = Column(String(300))
    description = Column(Text)
    
    # Agent classification and behavior
    type = Column(Enum(AgentType), nullable=False, index=True)
    subtype = Column(String(100))
    version = Column(String(50), default='1.0.0')
    status = Column(Enum(AgentStatus), default=AgentStatus.INACTIVE, nullable=False, index=True)
    
    # Core capabilities and configuration
    capabilities = Column(JSON, default=list)
    primary_llm_provider = Column(Enum(LLMProvider), default=LLMProvider.OPENAI, nullable=False)
    fallback_llm_providers = Column(JSON, default=list)
    model_preferences = Column(JSON, default=dict)
    
    # Performance and learning metrics
    performance_metrics = Column(JSON, default=dict)
    learning_rate = Column(Float, default=0.1)
    adaptation_threshold = Column(Float, default=0.8)
    confidence_threshold = Column(Float, default=0.7)
    success_rate = Column(Float, default=0.0)
    average_response_time = Column(Float, default=0.0)  # seconds
    total_tasks_completed = Column(BigInteger, default=0)
    total_tasks_failed = Column(BigInteger, default=0)
    
    # Resource management
    max_concurrent_tasks = Column(Integer, default=5)
    memory_limit_mb = Column(Integer, default=1024)
    cpu_limit_percent = Column(Integer, default=100)
    priority_level = Column(Integer, default=5)
    
    # Learning and improvement
    learns_from_feedback = Column(Boolean, default=True, nullable=False)
    learns_from_errors = Column(Boolean, default=True, nullable=False)
    learns_from_collaboration = Column(Boolean, default=True, nullable=False)
    knowledge_retention_days = Column(Integer, default=365)
    last_learning_update = Column(DateTime)
    learning_iteration = Column(BigInteger, default=0)
    
    # Collaboration and communication
    can_collaborate = Column(Boolean, default=True, nullable=False)
    preferred_collaborators = Column(JSON, default=list)
    communication_style = Column(JSON, default=dict)
    delegation_capabilities = Column(JSON, default=dict)
    
    # Security and access control
    security_clearance = Column(Enum(SecurityLevel), default=SecurityLevel.INTERNAL, nullable=False)
    allowed_operations = Column(JSON, default=list)
    restricted_operations = Column(JSON, default=list)
    audit_all_actions = Column(Boolean, default=True, nullable=False)
    
    # Runtime state and monitoring
    current_task_id = Column(String, ForeignKey('tasks.id'))
    last_heartbeat = Column(DateTime)
    health_status = Column(JSON, default=dict)
    error_count_24h = Column(Integer, default=0)
    last_error_timestamp = Column(DateTime)
    uptime_seconds = Column(BigInteger, default=0)
    
    # Configuration and customization
    config = Column(JSON, default=dict)
    custom_prompts = Column(JSON, default=dict)
    tool_configurations = Column(JSON, default=dict)
    integration_settings = Column(JSON, default=dict)
    
    # Audit and lifecycle
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    activated_at = Column(DateTime)
    last_used_at = Column(DateTime)
    scheduled_maintenance = Column(DateTime)
    
    # Relationships
    current_task = relationship("Task", foreign_keys=[current_task_id], post_update=True)
    assigned_tasks = relationship("Task", back_populates="agent", foreign_keys="Task.agent_id")
    learning_records = relationship("LearningRecord", back_populates="agent", cascade="all, delete-orphan")
    performance_logs = relationship("AgentPerformanceLog", back_populates="agent", cascade="all, delete-orphan")
    interactions = relationship("AgentInteraction", back_populates="agent", cascade="all, delete-orphan")
    capabilities_rel = relationship("Capability", secondary=agent_capabilities_table, back_populates="agents")
    collaborators = relationship(
        "Agent",
        secondary=agent_collaborations_table,
        primaryjoin=id==agent_collaborations_table.c.primary_agent_id,
        secondaryjoin=id==agent_collaborations_table.c.collaborator_agent_id,
        backref="primary_collaborations"
    )
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_agents_type_status', 'type', 'status'),
        Index('idx_agents_performance', 'success_rate', 'average_response_time'),
        Index('idx_agents_last_heartbeat', 'last_heartbeat'),
        Index('idx_agents_security_clearance', 'security_clearance'),
        Index('idx_agents_created', 'created_at'),
        UniqueConstraint('name', 'type', name='unique_agent_name_type'),
        CheckConstraint('learning_rate >= 0.0 AND learning_rate <= 1.0', name='valid_learning_rate'),
        CheckConstraint('success_rate >= 0.0 AND success_rate <= 1.0', name='valid_success_rate'),
    )
    
    @hybrid_property
    def is_healthy(self):
        if not self.last_heartbeat:
            return False
        # Consider agent healthy if heartbeat is within last 5 minutes
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() < 300
    
    @hybrid_property
    def efficiency_score(self):
        if self.total_tasks_completed == 0:
            return 0.0
        return self.success_rate * (1.0 / max(self.average_response_time, 0.1))

class Capability(Base):
    """Agent capability model for skill-based matching and learning"""
    __tablename__ = 'capabilities'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    
    # Capability metadata
    complexity_level = Column(Integer, default=1)  # 1-10 scale
    learning_difficulty = Column(Integer, default=1)  # 1-10 scale
    prerequisites = Column(JSON, default=list)  # list of capability IDs
    related_capabilities = Column(JSON, default=list)
    
    # Usage and effectiveness
    usage_count = Column(BigInteger, default=0)
    average_success_rate = Column(Float, default=0.0)
    is_core_capability = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Learning and evolution
    can_be_learned = Column(Boolean, default=True, nullable=False)
    typical_learning_time_hours = Column(Float, default=1.0)
    improvement_suggestions = Column(JSON, default=list)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    agents = relationship("Agent", secondary=agent_capabilities_table, back_populates="capabilities_rel")
    
    __table_args__ = (
        Index('idx_capabilities_category', 'category'),
        Index('idx_capabilities_complexity', 'complexity_level'),
        CheckConstraint('complexity_level >= 1 AND complexity_level <= 10', name='valid_complexity'),
        CheckConstraint('learning_difficulty >= 1 AND learning_difficulty <= 10', name='valid_difficulty'),
    )

class Task(Base):
    """Enhanced task model with comprehensive tracking and learning integration"""
    __tablename__ = 'tasks'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # Task classification and assignment
    type = Column(String(100), nullable=False, index=True)
    subtype = Column(String(100))
    category = Column(String(100), index=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False, index=True)
    
    # Project and agent assignment
    project_id = Column(String, ForeignKey('projects.id'), index=True)
    agent_id = Column(String, ForeignKey('agents.id'), index=True)
    assignee_id = Column(String, ForeignKey('users.id'), index=True)
    parent_task_id = Column(String, ForeignKey('tasks.id'))
    
    # Task dependencies and relationships
    depends_on = Column(JSON, default=list)  # list of task IDs
    blocks_tasks = Column(JSON, default=list)  # list of task IDs
    related_tasks = Column(JSON, default=list)
    
    # Data and configuration
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    configuration = Column(JSON, default=dict)
    context = Column(JSON, default=dict)
    
    # Execution tracking
    execution_attempts = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)
    timeout_seconds = Column(Integer, default=3600)
    
    # Results and analysis
    result_summary = Column(Text)
    error_message = Column(Text)
    error_type = Column(String(100))
    error_stack_trace = Column(Text)
    warnings = Column(JSON, default=list)
    
    # Performance metrics
    execution_time = Column(Float)  # seconds
    memory_used_mb = Column(Float)
    cpu_time_seconds = Column(Float)
    api_calls_made = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    cost_incurred = Column(DECIMAL(10, 4), default=0.0000)
    
    # Quality and validation
    quality_score = Column(Float, default=0.0)
    validation_results = Column(JSON, default=dict)
    test_results = Column(JSON, default=dict)
    code_coverage_percent = Column(Float, default=0.0)
    
    # Learning and improvement opportunities
    learning_opportunities = Column(JSON, # Learning and improvement opportunities
    learning_opportunities = Column(JSON, default=list)
    feedback_received = Column(JSON, default=dict)
    improvement_suggestions = Column(JSON, default=list)
    knowledge_gained = Column(JSON, default=dict)
    
    # Security and compliance
    security_level = Column(Enum(SecurityLevel), default=SecurityLevel.INTERNAL, nullable=False)
    compliance_requirements = Column(JSON, default=list)
    audit_required = Column(Boolean, default=False, nullable=False)
    data_classification = Column(String(50), default='internal')
    
    # Timeline tracking
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    scheduled_start = Column(DateTime)
    deadline = Column(DateTime)
    
    # Metadata and tags
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)
    custom_fields = Column(JSON, default=dict)
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    agent = relationship("Agent", back_populates="assigned_tasks", foreign_keys=[agent_id])
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    parent_task = relationship("Task", remote_side="Task.id", backref="subtasks")
    task_logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    task_artifacts = relationship("TaskArtifact", back_populates="task", cascade="all, delete-orphan")
    reviews = relationship("TaskReview", back_populates="task", cascade="all, delete-orphan")
    
    # Constraints and indexes
    __table_args__ = (
        Index('idx_tasks_project_status', 'project_id', 'status'),
        Index('idx_tasks_agent_status', 'agent_id', 'status'),
        Index('idx_tasks_assignee', 'assignee_id'),
        Index('idx_tasks_priority_status', 'priority', 'status'),
        Index('idx_tasks_type_category', 'type', 'category'),
        Index('idx_tasks_created', 'created_at'),
        Index('idx_tasks_deadline', 'deadline'),
        Index('idx_tasks_parent', 'parent_task_id'),
        CheckConstraint('execution_attempts >= 0', name='valid_execution_attempts'),
        CheckConstraint('max_retries >= 0', name='valid_max_retries'),
        CheckConstraint('quality_score >= 0.0 AND quality_score <= 1.0', name='valid_quality_score'),
    )
    
    @hybrid_property
    def is_overdue(self):
        return (self.deadline and 
                self.deadline < datetime.utcnow() and 
                self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
    
    @hybrid_property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

class TaskLog(Base):
    """Detailed logging for task execution steps and events"""
    __tablename__ = 'task_logs'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False, index=True)
    
    # Log entry details
    level = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    
    # Context and source
    source = Column(String(100))  # agent, system, user, etc.
    component = Column(String(100))  # which component generated the log
    step_number = Column(Integer)
    
    # Performance data
    execution_time_ms = Column(Float)
    memory_usage_mb = Column(Float)
    
    # Timestamp
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Relationships
    task = relationship("Task", back_populates="task_logs")
    
    __table_args__ = (
        Index('idx_task_logs_task_timestamp', 'task_id', 'timestamp'),
        Index('idx_task_logs_level', 'level'),
    )

class TaskArtifact(Base):
    """Files and outputs generated by tasks"""
    __tablename__ = 'task_artifacts'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False, index=True)
    
    # Artifact details
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)  # file, code, report, data, etc.
    file_path = Column(String(1000))
    file_size_bytes = Column(BigInteger)
    mime_type = Column(String(100))
    
    # Content and metadata
    content = Column(LargeBinary)  # for small files
    content_hash = Column(String(64))  # SHA-256 hash
    metadata = Column(JSON, default=dict)
    
    # Classification
    is_output = Column(Boolean, default=True, nullable=False)
    is_temporary = Column(Boolean, default=False, nullable=False)
    security_level = Column(Enum(SecurityLevel), default=SecurityLevel.INTERNAL, nullable=False)
    
    # Lifecycle
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime)
    
    # Relationships
    task = relationship("Task", back_populates="task_artifacts")
    
    __table_args__ = (
        Index('idx_task_artifacts_task_type', 'task_id', 'type'),
        Index('idx_task_artifacts_hash', 'content_hash'),
    )

class TaskReview(Base):
    """Human and automated reviews of task results"""
    __tablename__ = 'task_reviews'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False, index=True)
    reviewer_id = Column(String, ForeignKey('users.id'), index=True)
    
    # Review details
    review_type = Column(String(50), nullable=False)  # human, automated, peer, etc.
    status = Column(String(50), nullable=False)  # approved, rejected, needs_changes, etc.
    score = Column(Float)  # 0.0 to 1.0
    
    # Content
    comments = Column(Text)
    suggestions = Column(JSON, default=list)
    issues_found = Column(JSON, default=list)
    
    # Quality metrics
    code_quality_score = Column(Float)
    security_score = Column(Float)
    performance_score = Column(Float)
    maintainability_score = Column(Float)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    task = relationship("Task", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    
    __table_args__ = (
        Index('idx_task_reviews_task_status', 'task_id', 'status'),
        Index('idx_task_reviews_reviewer', 'reviewer_id'),
    )

class LearningRecord(Base):
    """Records of learning events and improvements"""
    __tablename__ = 'learning_records'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    project_id = Column(String, ForeignKey('projects.id'), index=True)
    task_id = Column(String, ForeignKey('tasks.id'), index=True)
    
    # Learning event details
    learning_type = Column(Enum(LearningType), nullable=False, index=True)
    trigger_event = Column(String(100))  # error, feedback, pattern_recognition, etc.
    confidence_level = Column(Float, default=0.5)
    
    # Learning content
    knowledge_before = Column(JSON, default=dict)
    knowledge_after = Column(JSON, default=dict)
    patterns_learned = Column(JSON, default=list)
    improvements_made = Column(JSON, default=list)
    
    # Context and source
    source_data = Column(JSON, default=dict)
    context = Column(JSON, default=dict)
    feedback_source = Column(String(100))  # user, system, peer_agent, etc.
    
    # Effectiveness tracking
    applied_successfully = Column(Boolean, default=False, nullable=False)
    improvement_measured = Column(Float)  # quantified improvement if available
    validation_score = Column(Float)
    
    # Audit and lifecycle
    created_at = Column(DateTime, default=func.now(), nullable=False)
    applied_at = Column(DateTime)
    expires_at = Column(DateTime)
    
    # Relationships
    agent = relationship("Agent", back_populates="learning_records")
    project = relationship("Project", back_populates="learning_records")
    task = relationship("Task", foreign_keys=[task_id])
    
    __table_args__ = (
        Index('idx_learning_records_agent_type', 'agent_id', 'learning_type'),
        Index('idx_learning_records_created', 'created_at'),
        Index('idx_learning_records_project', 'project_id'),
        CheckConstraint('confidence_level >= 0.0 AND confidence_level <= 1.0', name='valid_confidence'),
    )

class AgentPerformanceLog(Base):
    """Performance metrics and monitoring data for agents"""
    __tablename__ = 'agent_performance_logs'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    
    # Performance metrics
    metric_type = Column(Enum(MetricType), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(50))
    
    # Context and metadata
    task_id = Column(String, ForeignKey('tasks.id'), index=True)
    measurement_context = Column(JSON, default=dict)
    baseline_value = Column(Float)
    target_value = Column(Float)
    
    # Timestamp and grouping
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    measurement_period_start = Column(DateTime)
    measurement_period_end = Column(DateTime)
    
    # Additional data
    metadata = Column(JSON, default=dict)
    
    # Relationships
    agent = relationship("Agent", back_populates="performance_logs")
    task = relationship("Task", foreign_keys=[task_id])
    
    __table_args__ = (
        Index('idx_agent_performance_agent_metric', 'agent_id', 'metric_type'),
        Index('idx_agent_performance_timestamp', 'timestamp'),
        Index('idx_agent_performance_task', 'task_id'),
    )

class AgentInteraction(Base):
    """Records of agent-to-agent and agent-to-human interactions"""
    __tablename__ = 'agent_interactions'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    
    # Interaction details
    interaction_type = Column(String(100), nullable=False)  # collaboration, delegation, consultation, etc.
    target_type = Column(String(50), nullable=False)  # agent, human, system
    target_id = Column(String, index=True)  # ID of target agent or user
    
    # Context
    task_id = Column(String, ForeignKey('tasks.id'), index=True)
    project_id = Column(String, ForeignKey('projects.id'), index=True)
    
    # Communication content
    message_sent = Column(Text)
    message_received = Column(Text)
    data_exchanged = Column(JSON, default=dict)
    
    # Effectiveness and outcome
    outcome = Column(String(100))  # successful, failed, partial, etc.
    effectiveness_score = Column(Float)  # 0.0 to 1.0
    response_time_ms = Column(Float)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime)
    
    # Relationships
    agent = relationship("Agent", back_populates="interactions")
    task = relationship("Task", foreign_keys=[task_id])
    project = relationship("Project", foreign_keys=[project_id])
    
    __table_args__ = (
        Index('idx_agent_interactions_agent_type', 'agent_id', 'interaction_type'),
        Index('idx_agent_interactions_target', 'target_type', 'target_id'),
        Index('idx_agent_interactions_created', 'created_at'),
    )

class Deployment(Base):
    """Deployment tracking and management"""
    __tablename__ = 'deployments'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id'), nullable=False, index=True)
    
    # Deployment details
    version = Column(String(100), nullable=False)
    environment = Column(String(50), nullable=False, index=True)  # dev, staging, prod, etc.
    status = Column(Enum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False, index=True)
    
    # Source and artifacts
    commit_sha = Column(String(40))
    branch = Column(String(100))
    tag = Column(String(100))
    artifacts = Column(JSON, default=list)
    
    # Configuration
    deployment_config = Column(JSON, default=dict)
    environment_variables = Column(JSON, default=dict)
    resource_requirements = Column(JSON, default=dict)
    
    # Execution details
    initiated_by = Column(String, ForeignKey('users.id'), index=True)
    deployment_strategy = Column(String(50), default='rolling')  # rolling, blue_green, canary, etc.
    rollback_version = Column(String(100))
    
    # Results and metrics
    deployment_logs = Column(Text)
    error_message = Column(Text)
    health_check_results = Column(JSON, default=dict)
    performance_metrics = Column(JSON, default=dict)
    
    # Timeline
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="deployments")
    initiator = relationship("User", foreign_keys=[initiated_by])
    
    __table_args__ = (
        Index('idx_deployments_project_env', 'project_id', 'environment'),
        Index('idx_deployments_status', 'status'),
        Index('idx_deployments_version', 'version'),
    )

class SecurityScan(Base):
    """Security scanning results and vulnerability tracking"""
    __tablename__ = 'security_scans'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id'), nullable=False, index=True)
    
    # Scan details
    scan_type = Column(String(100), nullable=False)  # sast, dast, dependency, container, etc.
    scanner_name = Column(String(100), nullable=False)
    scanner_version = Column(String(50))
    
    # Results summary
    total_vulnerabilities = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    info_count = Column(Integer, default=0)
    
    # Detailed results
    vulnerabilities = Column(JSON, default=list)  # detailed vulnerability data
    false_positives = Column(JSON, default=list)
    resolved_issues = Column(JSON, default=list)
    
    # Compliance and scoring
    security_score = Column(Float, default=0.0)  # 0.0 to 10.0
    compliance_status = Column(JSON, default=dict)
    risk_rating = Column(String(20))  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Execution context
    commit_sha = Column(String(40))
    branch = Column(String(100))
    triggered_by = Column(String, ForeignKey('users.id'))
    
    # Timeline
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="security_scans")
    trigger_user = relationship("User", foreign_keys=[triggered_by])
    
    __table_args__ = (
        Index('idx_security_scans_project_type', 'project_id', 'scan_type'),
        Index('idx_security_scans_risk_rating', 'risk_rating'),
        Index('idx_security_scans_created', 'created_at'),
    )

class QualityReport(Base):
    """Code quality and technical debt reports"""
    __tablename__ = 'quality_reports'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id'), nullable=False, index=True)
    
    # Report metadata
    report_type = Column(String(100), nullable=False)  # code_quality, test_coverage, performance, etc.
    analyzer_name = Column(String(100), nullable=False)
    analyzer_version = Column(String(50))
    
    # Quality metrics
    overall_score = Column(Float, default=0.0)  # 0.0 to 10.0
    maintainability_rating = Column(String(1))  # A, B, C, D, E
    reliability_rating = Column(String(1))
    security_rating = Column(String(1))
    
    # Detailed metrics
    code_coverage_percent = Column(Float, default=0.0)
    test_success_rate = Column(Float, default=0.0)
    cyclomatic_complexity = Column(Float, default=0.0)
    technical_debt_minutes = Column(Integer, default=0)
    
    # Issue tracking
    total_issues = Column(Integer, default=0)
    blocker_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    major_issues = Column(Integer, default=0)
    minor_issues = Column(Integer, default=0)
    info_issues = Column(Integer, default=0)
    
    # Detailed results
    issues_detail = Column(JSON, default=list)
    metrics_detail = Column(JSON, default=dict)
    trends = Column(JSON, default=dict)
    
    # Context
    commit_sha = Column(String(40))
    branch = Column(String(100))
    lines_of_code = Column(Integer, default=0)
    
    # Timeline
    analyzed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="quality_reports")
    
    __table_args__ = (
        Index('idx_quality_reports_project_type', 'project_id', 'report_type'),
        Index('idx_quality_reports_score', 'overall_score'),
        Index('idx_quality_reports_created', 'created_at'),
    )

class UserSession(Base):
    """User session tracking for security and audit"""
    __tablename__ = 'user_sessions'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    
    # Session details
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, index=True)
    
    # Client information
    ip_address = Column(String(45))  # supports IPv6
    user_agent = Column(String(500))
    device_fingerprint = Column(String(255))
    
    # Geolocation
    country = Column(String(100))
    city = Column(String(100))
    timezone = Column(String(50))
    
    # Session state
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity = Column(DateTime, default=func.now(), nullable=False)
    
    # Security
    mfa_verified = Column(Boolean, default=False, nullable=False)
    risk_score = Column(Float, default=0.0)  # 0.0 to 1.0
    
    # Timeline
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    terminated_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_user_sessions_user_active', 'user_id', 'is_active'),
        Index('idx_user_sessions_token', 'session_token'),
        Index('idx_user_sessions_last_activity', 'last_activity'),
    )

class APIToken(Base):
    """API tokens for programmatic access"""
    __tablename__ = 'api_tokens'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    
    # Token details
    name = Column(String(200), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    prefix = Column(String(10), nullable=False)  # first few chars for identification
    
    # Permissions and scope
    scopes = Column(JSON, default=list)
    permissions = Column(JSON, default=list)
    resource_restrictions = Column(JSON, default=dict)
    
    # Usage tracking
    last_used_at = Column(DateTime)
    usage_count = Column(BigInteger, default=0)
    rate_limit_per_hour = Column(Integer, default=1000)
    
    # Status and lifecycle
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime)
    revoked_at = Column(DateTime)
    revoked_reason = Column(String(500))
    
    # Relationships
    user = relationship("User", back_populates="api_tokens")
    
    __table_args__ = (
        Index('idx_api_tokens_user_active', 'user_id', 'is_active'),
        Index('idx_api_tokens_hash', 'token_hash'),
    )

class AuditLog(Base):
    """Comprehensive audit logging for security and compliance"""
    __tablename__ = 'audit_logs'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), index=True)
    resource_id = Column(String, index=True)
    
    # Actor information
    user_id = Column(String, ForeignKey('users.id'), index=True)
    agent_id = Column(String, ForeignKey('agents.id'), index=True)
    session_id = Column(String)
    
    # Context and details
    details = Column(JSON, default=dict)
    before_state = Column(JSON, default=dict)
    after_state = Column(JSON, default=dict)
    
    # Request context
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    request_id = Column(String(100))
    
    # Results
    success = Column(Boolean, nullable=False)
    error_message = Column(String(1000))
    response_code = Column(Integer)
    
    # Timeline
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    duration_ms = Column(Float)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    agent = relationship("Agent", foreign_keys=[agent_id])
    
    __table_args__ = (
        Index('idx_audit_logs_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_logs_event_action', 'event_type', 'action'),
        Index('idx_audit_logs_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_logs_timestamp', 'timestamp'),
    )

class Tag(Base):
    """Flexible tagging system for projects, tasks, and other entities"""
    __tablename__ = 'tags'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    
    # Categorization
    category = Column(String(100), index=True)
    color = Column(String(7))  # hex color code
    icon = Column(String(50))
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    is_system_tag = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    created_by = Column(String, ForeignKey('users.id'))
    
    # Relationships
    projects = relationship("Project", secondary=project_tags_table, back_populates="tags")
    creator = relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        Index('idx_tags_name', 'name'),
        Index('idx_tags_category', 'category'),
        Index('idx_tags_usage', 'usage_count'),
    )

# Database utility functions and helpers
class DatabaseUtils:
    """Utility functions for database operations"""
    
    @staticmethod
    def create_all_tables(engine):
        """Create all tables in the database"""
        Base.metadata.create_all(bind=engine)
    
    @staticmethod
    def drop_all_tables(engine):
        """Drop all tables in the database"""
        Base.metadata.drop_all(bind=engine)
    
    @staticmethod
    def get_table_names():
        """Get list of all table names"""
        return list(Base.metadata.tables.keys())
    
    @staticmethod
    def create_indexes(engine):
        """Create additional indexes for performance optimization"""
        # Additional custom indexes can be created here
        pass

# Model registry for dynamic access
MODEL_REGISTRY = {
    'User': User,
    'Role': Role,
    'Project': Project,
    'Organization': Organization,
    'Agent': Agent,
    'Capability': Capability,
    'Task': Task,
    'TaskLog': TaskLog,
    'TaskArtifact': TaskArtifact,
    'TaskReview': TaskReview,
    'LearningRecord': LearningRecord,
    'AgentPerformanceLog': AgentPerformanceLog,
    'AgentInteraction': AgentInteraction,
    'Deployment': Deployment,
    'SecurityScan': SecurityScan,
    'QualityReport': QualityReport,
    'UserSession': UserSession,
    'APIToken': APIToken,
    'AuditLog': AuditLog,
    'Tag': Tag,
}

# Export all models and utilities
__all__ = [
    'Base', 'metadata',
    # Enums
    'ProjectStatus', 'AgentStatus', 'AgentType', 'TaskStatus', 'TaskPriority',
    'LLMProvider', 'LearningType', 'MetricType', 'SecurityLevel', 'DeploymentStatus',
    # Models
    'User', 'Role', 'Project', 'Organization', 'Agent', 'Capability', 'Task',
    'TaskLog', 'TaskArtifact', 'TaskReview', 'LearningRecord', 'AgentPerformanceLog',
    'AgentInteraction', 'Deployment', 'SecurityScan', 'QualityReport',
    'UserSession', 'APIToken', 'AuditLog', 'Tag',
    # Association tables
    'agent_capabilities_table', 'agent_collaborations_table', 'user_roles_table',
    'project_tags_table',
    # Utilities
    'DatabaseUtils', 'MODEL_REGISTRY'
]