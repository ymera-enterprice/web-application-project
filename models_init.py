"""
YMERA Enterprise - Database Models Package
Production-Ready Database Models with Learning Engine Integration - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

from .base_model import BaseModel, TimestampMixin, AuditMixin
from .user_models import (
    User, UserProfile, UserSession, UserPreference, 
    UserActivity, UserPermission, Role, UserRole
)
from .project_models import (
    Project, ProjectMember, ProjectConfig, ProjectActivity,
    ProjectMetrics, ProjectResource, ProjectTemplate
)
from .agent_models import (
    Agent, AgentState, AgentCommunication, AgentKnowledge,
    AgentMetrics, AgentLearning, AgentCollaboration, AgentPattern,
    KnowledgeGraph, LearningCycle, ExternalKnowledge
)
from .file_models import (
    FileMetadata, FileVersion, FileAccess, FileShare,
    FileProcessing, FileThumbnail, FileBackup
)
from .task_models import (
    Task, TaskDependency, TaskExecution, TaskResult,
    TaskMetrics, TaskTemplate, TaskSchedule, TaskCollaboration
)

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Base models
    "BaseModel",
    "TimestampMixin", 
    "AuditMixin",
    
    # User models
    "User",
    "UserProfile",
    "UserSession",
    "UserPreference",
    "UserActivity",
    "UserPermission",
    "Role",
    "UserRole",
    
    # Project models
    "Project",
    "ProjectMember",
    "ProjectConfig",
    "ProjectActivity",
    "ProjectMetrics",
    "ProjectResource",
    "ProjectTemplate",
    
    # Agent models
    "Agent",
    "AgentState",
    "AgentCommunication",
    "AgentKnowledge",
    "AgentMetrics",
    "AgentLearning",
    "AgentCollaboration",
    "AgentPattern",
    "KnowledgeGraph",
    "LearningCycle",
    "ExternalKnowledge",
    
    # File models
    "FileMetadata",
    "FileVersion",
    "FileAccess",
    "FileShare",
    "FileProcessing",
    "FileThumbnail",
    "FileBackup",
    
    # Task models
    "Task",
    "TaskDependency", 
    "TaskExecution",
    "TaskResult",
    "TaskMetrics",
    "TaskTemplate",
    "TaskSchedule",
    "TaskCollaboration"
]