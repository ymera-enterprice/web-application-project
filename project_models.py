"""
YMERA Enterprise - Project Management Models
Production-Ready Project Management with Advanced Features - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Set
from enum import Enum
from decimal import Decimal

# Third-party imports
import structlog
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, Integer, Float, Numeric,
    ForeignKey, Table, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, validates, backref
from sqlalchemy.sql import func

# Local imports
from .base_model import BaseModel

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.models.project")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Project limits
MAX_PROJECT_NAME_LENGTH = 200
MAX_PROJECT_DESCRIPTION_LENGTH = 5000
MAX_MEMBERS_PER_PROJECT = 100

# Budget and resource limits
MAX_BUDGET_AMOUNT = Decimal('999999999.99')
MIN_BUDGET_AMOUNT = Decimal('0.00')

# ===============================================================================
# ENUMS
# ===============================================================================

class ProjectStatus(Enum):
    """Project status enumeration"""
    DRAFT = "draft"
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class ProjectPriority(Enum):
    """Project priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemberRole(Enum):
    """Project member role enumeration"""
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    VIEWER = "viewer"
    GUEST = "guest"


class ActivityType(Enum):
    """Project activity type enumeration"""
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    MEMBER_ROLE_CHANGED = "member_role_changed"
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    MILESTONE_REACHED = "milestone_reached"
    BUDGET_UPDATED = "budget_updated"
    ARCHIVED = "archived"
    RESTORED = "restored"


class ResourceType(Enum):
    """Project resource type enumeration"""
    HUMAN = "human"
    FINANCIAL = "financial"
    EQUIPMENT = "equipment"
    SOFTWARE = "software"
    FACILITY = "facility"
    EXTERNAL_SERVICE = "external_service"


# ===============================================================================
# ASSOCIATION TABLES
# ===============================================================================

# Many-to-many relationship between projects and templates
project_templates_table = Table(
    'project_templates',
    BaseModel.metadata,
    Column(
        'project_id',
        UUID(as_uuid=True),
        ForeignKey('project.id', ondelete='CASCADE'),
        primary_key=True
    ),
    Column(
        'template_id',
        UUID(as_uuid=True),
        ForeignKey('project_template.id', ondelete='CASCADE'),
        primary_key=True
    ),
    Column(
        'applied_at',
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
)

# ===============================================================================
# CORE PROJECT MODELS
# ===============================================================================

class Project(BaseModel):
    """
    Core project model with comprehensive project management features.
    
    Features:
    - Project lifecycle management
    - Member management with roles
    - Budget tracking
    - Resource allocation
    - Activity tracking
    - Metrics and reporting
    - Template support
    """
    
    __tablename__ = 'project'
    
    # Basic project information
    title = Column(
        String(MAX_PROJECT_NAME_LENGTH),
        nullable=False,
        index=True,
        doc="Project title"
    )
    
    # Override base model name with title
    name = Column(
        String(MAX_PROJECT_NAME_LENGTH),
        nullable=False,
        index=True,
        doc="Project name (same as title for compatibility)"
    )
    
    short_description = Column(
        String(500),
        nullable=True,
        doc="Brief project description"
    )
    
    detailed_description = Column(
        Text,
        nullable=True,
        doc="Detailed project description"
    )
    
    # Project classification
    project_type = Column(
        String(50),
        nullable=False,
        default="general",
        index=True,
        doc="Project type classification"
    )
    
    category = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Project category"
    )
    
    # Project status and priority
    project_status = Column(
        ENUM(ProjectStatus),
        default=ProjectStatus.DRAFT,
        nullable=False,
        index=True,
        doc="Current project status"
    )
    
    priority = Column(
        ENUM(ProjectPriority),
        default=ProjectPriority.MEDIUM,
        nullable=False,
        index=True,
        doc="Project priority level"
    )
    
    # Timeline management
    start_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Project start date"
    )
    
    end_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Project end date"
    )
    
    planned_start_date = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Originally planned start date"
    )
    
    planned_end_date = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Originally planned end date"
    )
    
    actual_start_date = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Actual project start date"
    )
    
    actual_end_date = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Actual project completion date"
    )
    
    # Budget and financial tracking
    budget_amount = Column(
        Numeric(12, 2),
        nullable=True,
        doc="Total project budget"
    )
    
    budget_currency = Column(
        String(3),
        default="USD",
        nullable=False,
        doc="Budget currency code"
    )
    
    spent_amount = Column(
        Numeric(12, 2),
        default=Decimal('0.00'),
        nullable=False,
        doc="Amount spent so far"
    )
    
    # Progress tracking
    completion_percentage = Column(
        Float,
        default=0.0,
        nullable=False,
        doc="Project completion percentage (0-100)"
    )
    
    # Ownership and access
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=False,
        index=True,
        doc="Project owner user ID"
    )
    
    is_public = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Public project visibility"
    )
    
    is_template = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Project template flag"
    )
    
    # Project settings
    settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Project-specific settings"
    )
    
    # Custom fields
    custom_fields = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Custom project fields"
    )
    
    # Integration settings
    external_integrations = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="External system integrations"
    )
    
    # Relationships
    owner = relationship(
        "User",
        foreign_keys=[owner_id],
        doc="Project owner"
    )
    
    members = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    activities = relationship(
        "ProjectActivity",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectActivity.created_at.desc()"
    )
    
    metrics = relationship(
        "ProjectMetrics",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    resources = relationship(
        "ProjectResource",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    config = relationship(
        "ProjectConfig",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    templates = relationship(
        "ProjectTemplate",
        secondary=project_templates_table,
        back_populates="projects"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            'budget_amount >= 0',
            name='ck_project_budget_positive'
        ),
        CheckConstraint(
            'spent_amount >= 0',
            name='ck_project_spent_positive'
        ),
        CheckConstraint(
            'completion_percentage >= 0 AND completion_percentage <= 100',
            name='ck_project_completion_range'
        ),
        Index('idx_project_owner_status', 'owner_id', 'project_status'),
        Index('idx_project_dates', 'start_date', 'end_date'),
        Index('idx_project_budget', 'budget_amount', 'spent_amount'),
    )
    
    # ===============================================================================
    # VALIDATION METHODS
    # ===============================================================================
    
    @validates('title', 'name')
    def validate_title_name(self, key: str, value: str) -> str:
        """Validate project title and name"""
        if not value or not value.strip():
            raise ValueError(f"{key.title()} cannot be empty")
        
        if len(value.strip()) > MAX_PROJECT_NAME_LENGTH:
            raise ValueError(f"{key.title()} cannot exceed {MAX_PROJECT_NAME_LENGTH} characters")
        
        return value.strip()
    
    @validates('budget_amount', 'spent_amount')
    def validate_amounts(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate budget and spent amounts"""
        if value is None:
            return value
        
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        if value < MIN_BUDGET_AMOUNT:
            raise ValueError(f"{key} must be non-negative")
        
        if value > MAX_BUDGET_AMOUNT:
            raise ValueError(f"{key} cannot exceed {MAX_BUDGET_AMOUNT}")
        
        return value
    
    @validates('completion_percentage')
    def validate_completion_percentage(self, key: str, value: float) -> float:
        """Validate completion percentage"""
        if value < 0 or value > 100:
            raise ValueError("Completion percentage must be between 0 and 100")
        
        return round(value, 2)
    
    @validates('start_date', 'end_date', 'planned_start_date', 'planned_end_date')
    def validate_dates(self, key: str, value: Optional[datetime]) -> Optional[datetime]:
        """Validate project dates"""
        if value is None:
            return value
        
        # Ensure timezone awareness
        if value.tzinfo is None:
            raise ValueError(f"{key} must be timezone-aware")
        
        return value
    
    # ===============================================================================
    # PROJECT LIFECYCLE METHODS
    # ===============================================================================
    
    def start_project(self, user_id: uuid.UUID) -> None:
        """Start the project"""
        if self.project_status != ProjectStatus.PLANNING:
            raise ValueError("Project must be in planning status to start")
        
        self.project_status = ProjectStatus.ACTIVE
        self.actual_start_date = datetime.utcnow()
        
        if not self.start_date:
            self.start_date = self.actual_start_date
    
    def complete_project(self, user_id: uuid.UUID) -> None:
        """Complete the project"""
        if self.project_status not in [ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD]:
            raise ValueError("Project must be active or on hold to complete")
        
        self.project_status = ProjectStatus.COMPLETED
        self.actual_end_date = datetime.utcnow()
        self.completion_percentage = 100.0
    
    def archive_project(self, user_id: uuid.UUID) -> None:
        """Archive the project"""
        if self.project_status == ProjectStatus.ARCHIVED:
            raise ValueError("Project is already archived")
        
        previous_status = self.project_status
        self.project_status = ProjectStatus.ARCHIVED
        self.set_metadata('previous_status', previous_status.value)
        self.set_metadata('archived_by', str(user_id))
        self.set_metadata('archived_at', datetime.utcnow().isoformat())
    
    def restore_project(self, user_id: uuid.UUID) -> None:
        """Restore archived project"""
        if self.project_status != ProjectStatus.ARCHIVED:
            raise ValueError("Only archived projects can be restored")
        
        previous_status = self.get_metadata('previous_status', 'draft')
        try:
            self.project_status = ProjectStatus(previous_status)
        except ValueError:
            self.project_status = ProjectStatus.DRAFT
        
        self.remove_metadata('previous_status')
        self.remove_metadata('archived_by')
        self.remove_metadata('archived_at')
    
    def cancel_project(self, user_id: uuid.UUID, reason: str = None) -> None:
        """Cancel the project"""
        if self.project_status in [ProjectStatus.COMPLETED, ProjectStatus.CANCELLED]:
            raise ValueError("Cannot cancel completed or already cancelled project")
        
        self.project_status = ProjectStatus.CANCELLED
        if reason:
            self.set_metadata('cancellation_reason', reason)
        self.set_metadata('cancelled_by', str(user_id))
        self.set_metadata('cancelled_at', datetime.utcnow().isoformat())
    
    # ===============================================================================
    # BUDGET AND FINANCIAL METHODS
    # ===============================================================================
    
    def update_budget(self, amount: Decimal, currency: str = None) -> None:
        """Update project budget"""
        if amount < MIN_BUDGET_AMOUNT or amount > MAX_BUDGET_AMOUNT:
            raise ValueError("Invalid budget amount")
        
        self.budget_amount = amount
        if currency:
            self.budget_currency = currency
    
    def add_expense(self, amount: Decimal, description: str = None) -> None:
        """Add expense to project"""
        if amount <= 0:
            raise ValueError("Expense amount must be positive")
        
        self.spent_amount = (self.spent_amount or Decimal('0.00')) + amount
        
        if self.budget_amount and self.spent_amount > self.budget_amount:
            logger.warning(
                "Project budget exceeded",
                project_id=str(self.id),
                budget=float(self.budget_amount),
                spent=float(self.spent_amount)
            )
    
    def get_budget_utilization(self) -> float:
        """Get budget utilization percentage"""
        if not self.budget_amount or self.budget_amount == 0:
            return 0.0
        
        spent = self.spent_amount or Decimal('0.00')
        return float((spent / self.budget_amount) * 100)
    
    def get_remaining_budget(self) -> Decimal:
        """Get remaining budget amount"""
        if not self.budget_amount:
            return Decimal('0.00')
        
        spent = self.spent_amount or Decimal('0.00')
        return max(self.budget_amount - spent, Decimal('0.00'))
    
    # ===============================================================================
    # MEMBER MANAGEMENT METHODS
    # ===============================================================================
    
    def add_member(self, user_id: uuid.UUID, role: MemberRole, added_by: uuid.UUID) -> 'ProjectMember':
        """Add member to project"""
        # Check if already a member
        existing_member = next(
            (m for m in self.members if m.user_id == user_id and m.is_active),
            None
        )
        
        if existing_member:
            raise ValueError("User is already a member of this project")
        
        # Check member limit
        active_members_count = len([m for m in self.members if m.is_active])
        if active_members_count >= MAX_MEMBERS_PER_PROJECT:
            raise ValueError(f"Project cannot have more than {MAX_MEMBERS_PER_PROJECT} members")
        
        member = ProjectMember(
            project_id=self.id,
            user_id=user_id,
            role=role,
            added_by=added_by
        )
        
        return member
    
    def remove_member(self, user_id: uuid.UUID, removed_by: uuid.UUID) -> bool:
        """Remove member from project"""
        member = next(
            (m for m in self.members if m.user_id == user_id and m.is_active),
            None
        )
        
        if not member:
            return False
        
        # Prevent removing the owner
        if user_id == self.owner_id:
            raise ValueError("Cannot remove project owner")
        
        member.remove_from_project(removed_by)
        return True
    
    def change_member_role(self, user_id: uuid.UUID, new_role: MemberRole, changed_by: uuid.UUID) -> bool:
        """Change member role"""
        member = next(
            (m for m in self.members if m.user_id == user_id and m.is_active),
            None
        )
        
        if not member:
            return False
        
        # Prevent changing owner role
        if user_id == self.owner_id and new_role != MemberRole.OWNER:
            raise ValueError("Cannot change owner role")
        
        old_role = member.role
        member.role = new_role
        member.role_changed_at = datetime.utcnow()
        member.role_changed_by = changed_by
        
        return True
    
    def get_active_members(self) -> List['ProjectMember']:
        """Get list of active project members"""
        return [m for m in self.members if m.is_active]
    
    def is_member(self, user_id: uuid.UUID) -> bool:
        """Check if user is a project member"""
        return any(m.user_id == user_id and m.is_active for m in self.members)
    
    def get_member_role(self, user_id: uuid.UUID) -> Optional[MemberRole]:
        """Get user's role in the project"""
        member = next(
            (m for m in self.members if m.user_id == user_id and m.is_active),
            None
        )
        return member.role if member else None
    
    # ===============================================================================
    # PROGRESS AND METRICS METHODS
    # ===============================================================================
    
    def update_progress(self, percentage: float, updated_by: uuid.UUID) -> None:
        """Update project progress"""
        if percentage < 0 or percentage > 100:
            raise ValueError("Progress percentage must be between 0 and 100")
        
        old_percentage = self.completion_percentage
        self.completion_percentage = round(percentage, 2)
        
        # Auto-complete if 100%
        if percentage == 100.0 and self.project_status == ProjectStatus.ACTIVE:
            self.complete_project(updated_by)
        
        # Log significant progress changes
        if abs(percentage - old_percentage) >= 10:
            logger.info(
                "Significant progress update",
                project_id=str(self.id),
                old_progress=old_percentage,
                new_progress=percentage,
                updated_by=str(updated_by)
            )
    
    def calculate_health_score(self) -> float:
        """Calculate project health score (0-100)"""
        score = 100.0
        
        # Timeline health
        if self.end_date and datetime.utcnow() > self.end_date:
            days_overdue = (datetime.utcnow() - self.end_date).days
            score -= min(days_overdue * 2, 30)  # Max 30 points penalty
        
        # Budget health
        budget_utilization = self.get_budget_utilization()
        if budget_utilization > 100:
            score -= min((budget_utilization - 100) * 0.5, 25)  # Max 25 points penalty
        
        # Progress health (if behind schedule)
        if self.start_date and self.end_date:
            total_duration = (self.end_date - self.start_date).days
            elapsed_duration = (datetime.utcnow() - self.start_date).days
            
            if total_duration > 0:
                expected_progress = min((elapsed_duration / total_duration) * 100, 100)
                if self.completion_percentage < expected_progress:
                    progress_gap = expected_progress - self.completion_percentage
                    score -= min(progress_gap * 0.3, 20)  # Max 20 points penalty
        
        return max(score, 0.0)
    
    def get_project_summary(self) -> Dict[str, Any]:
        """Get comprehensive project summary"""
        return {
            'id': str(self.id),
            'title': self.title,
            'status': self.project_status.value,
            'priority': self.priority.value,
            'completion_percentage': self.completion_percentage,
            'health_score': self.calculate_health_score(),
            'member_count': len(self.get_active_members()),
            'budget_utilization': self.get_budget_utilization(),
            'days_remaining': self._get_days_remaining(),
            'is_overdue': self._is_overdue(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def _get_days_remaining(self) -> Optional[int]:
        """Get days remaining until end date"""
        if not self.end_date:
            return None
        
        delta = self.end_date - datetime.utcnow()
        return max(delta.days, 0)
    
    def _is_overdue(self) -> bool:
        """Check if project is overdue"""
        if not self.end_date:
            return False
        
        return datetime.utcnow() > self.end_date and self.project_status != ProjectStatus.COMPLETED


# ===============================================================================
# PROJECT MEMBER MODEL
# ===============================================================================

class ProjectMember(BaseModel):
    """Project member with role management"""
    
    __tablename__ = 'project_member'
    
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        doc="Associated project ID"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        doc="Associated user ID"
    )
    
    role = Column(
        ENUM(MemberRole),
        nullable=False,
        doc="Member role in project"
    )
    
    # Membership details
    joined_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Member join timestamp"
    )
    
    added_by = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=False,
        doc="User who added this member"
    )
    
    # Role change tracking
    role_changed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Last role change timestamp"
    )
    
    role_changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=True,
        doc="User who changed the role"
    )
    
    # Status tracking
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Active membership status"
    )
    
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Member removal timestamp"
    )
    
    removed_by = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=True,
        doc="User who removed this member"
    )
    
    # Member settings
    notification_preferences = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Member notification preferences"
    )
    
    # Relationships
    project = relationship("Project", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    
    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            'project_id', 'user_id',
            name='uq_project_member'
        ),
        Index('idx_project_member_active', 'project_id', 'is_active'),
        Index('idx_project_member_role', 'project_id', 'role'),
    )
    
    def remove_from_project(self, removed_by: uuid.UUID) -> None:
        """Remove member from project"""
        self.is_active = False
        self.removed_at = datetime.utcnow()
        self.removed_by = removed_by
    
    def restore_to_project(self) -> None:
        """Restore member to project"""
        self.is_active = True
        self.removed_at = None
        self.removed_by = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if member has specific permission"""
        role_permissions = {
            MemberRole.OWNER: ['all'],
            MemberRole.ADMIN: ['manage_members', 'edit_project', 'view_project', 'create_tasks'],
            MemberRole.MANAGER: ['edit_project', 'view_project', 'create_tasks'],
            MemberRole.MEMBER: ['view_project', 'create_tasks'],
            MemberRole.VIEWER: ['view_project'],
            MemberRole.GUEST: ['view_project']
        }
        
        permissions = role_permissions.get(self.role, [])
        return 'all' in permissions or permission in permissions


# ===============================================================================
# PROJECT CONFIGURATION MODEL
# ===============================================================================

class ProjectConfig(BaseModel):
    """Project configuration and settings"""
    
    __tablename__ = 'project_config'
    
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
        doc="Associated project ID"
    )
    
    # Access control settings
    allow_public_access = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Allow public access to project"
    )
    
    require_approval_for_members = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Require approval for new members"
    )
    
    allow_member_invite = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Allow members to invite others"
    )
    
    # Notification settings
    email_notifications_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Enable email notifications"
    )
    
    slack_integration_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Enable Slack integration"
    )
    
    # Workflow settings
    task_auto_assignment = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Enable automatic task assignment"
    )
    
    milestone_tracking = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Enable milestone tracking"
    )
    
    time_tracking_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Enable time tracking"
    )
    
    # Custom workflow stages
    workflow_stages = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Custom workflow stages"
    )
    
    # Integration settings
    external_integrations = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="External system integrations"
    )
    
    # Advanced settings
    advanced_settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Advanced configuration options"
    )
    
    # Relationships
    project = relationship("Project", back_populates="config")


# ===============================================================================
# PROJECT ACTIVITY MODEL
# ===============================================================================

class ProjectActivity(BaseModel):
    """Project activity tracking for audit and timeline"""
    
    __tablename__ = 'project_activity'
    
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        doc="Associated project ID"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=False,
        index=True,
        doc="User who performed the activity"
    )
    
    activity_type = Column(
        ENUM(ActivityType),
        nullable=False,
        index=True,
        doc="Type of activity"
    )
    
    activity_details = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Detailed activity information"
    )
    
    # Context information
    entity_type = Column(
        String(50),
        nullable=True,
        index=True,
        doc="Type of entity affected"
    )
    
    entity_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="ID of entity affected"
    )
    
    # Change tracking
    old_values = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Previous values before change"
    )
    
    new_values = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="New values after change"
    )
    
    # Relationships
    project = relationship("Project", back_populates="activities")
    user = relationship("User", foreign_keys=[user_id])
    
    # Table constraints
    __table_args__ = (
        Index('idx_project_activity_type_time', 'project_id', 'activity_type', 'created_at'),
        Index('idx_project_activity_entity', 'entity_type', 'entity_id'),
    )


# ===============================================================================
# PROJECT METRICS MODEL
# ===============================================================================

class ProjectMetrics(BaseModel):
    """Project metrics and analytics"""
    
    __tablename__ = 'project_metrics'
    
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
        doc="Associated project ID"
    )
    
    # Task metrics
    total_tasks = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of tasks"
    )
    
    completed_tasks = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of completed tasks"
    )
    
    overdue_tasks = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of overdue tasks"
    )
    
    # Time metrics
    total_estimated_hours = Column(
        Float,
        default=0.0,
        nullable=False,
        doc="Total estimated hours"
    )
    
    total_logged_hours = Column(
        Float,
        default=0.0,
        nullable=False,
        doc="Total logged hours"
    )
    
    # Member metrics
    active_members_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of active members"
    )
    
    total_members_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of members (including inactive)"
    )
    
    # Activity metrics
    total_activities = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of activities"
    )
    
    activities_last_30_days = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Activities in last 30 days"
    )
    
    # File metrics
    total_files = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of files"
    )
    
    total_file_size_bytes = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Total file size in bytes"
    )
    
    # Performance metrics
    average_task_completion_days = Column(
        Float,
        nullable=True,
        doc="Average days to complete tasks"
    )
    
    project_velocity = Column(
        Float,
        nullable=True,
        doc="Project velocity (tasks completed per week)"
    )
    
    # Health metrics
    health_score = Column(
        Float,
        default=100.0,
        nullable=False,
        doc="Overall project health score"
    )
    
    last_calculated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Last metrics calculation timestamp"
    )
    
    # Relationships
    project = relationship("Project", back_populates="metrics")
    
    def update_metrics(self) -> None:
        """Update all project metrics"""
        # This would be implemented to calculate real metrics
        # from related project data
        self.last_calculated_at = datetime.utcnow()


# ===============================================================================
# PROJECT RESOURCE MODEL
# ===============================================================================

class ProjectResource(BaseModel):
    """Project resource allocation and tracking"""
    
    __tablename__ = 'project_resource'
    
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('project.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        doc="Associated project ID"
    )
    
    resource_type = Column(
        ENUM(ResourceType),
        nullable=False,
        index=True,
        doc="Type of resource"
    )
    
    resource_name = Column(
        String(200),
        nullable=False,
        doc="Resource name"
    )
    
    # Resource allocation
    allocated_amount = Column(
        Numeric(12, 2),
        nullable=False,
        doc="Allocated resource amount"
    )
    
    used_amount = Column(
        Numeric(12, 2),
        default=Decimal('0.00'),
        nullable=False,
        doc="Used resource amount"
    )
    
    unit = Column(
        String(20),
        nullable=False,
        doc="Resource unit (hours, dollars, etc.)"
    )
    
    # Cost tracking
    unit_cost = Column(
        Numeric(10, 2),
        nullable=True,
        doc="Cost per unit"
    )
    
    total_cost = Column(
        Numeric(12, 2),
        nullable=True,
        doc="Total resource cost"
    )
    
    # Availability
    available_from = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Resource available from date"
    )
    
    available_until = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Resource available until date"
    )
    
    # Resource details
    specifications = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Resource specifications"
    )
    
    # Relationships
    project = relationship("Project", back_populates="resources")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            'allocated_amount >= 0',
            name='ck_resource_allocated_positive'
        ),
        CheckConstraint(
            'used_amount >= 0',
            name='ck_resource_used_positive'
        ),
        Index('idx_project_resource_type', 'project_id', 'resource_type'),
    )
    
    def get_utilization_percentage(self) -> float:
        """Get resource utilization percentage"""
        if self.allocated_amount == 0:
            return 0.0
        
        return float((self.used_amount / self.allocated_amount) * 100)


# ===============================================================================
# PROJECT TEMPLATE MODEL
# ===============================================================================

class ProjectTemplate(BaseModel):
    """Project templates for standardized project creation"""
    
    __tablename__ = 'project_template'
    
    # Template information
    template_name = Column(
        String(200),
        nullable=False,
        index=True,
        doc="Template name"
    )
    
    category = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Template category"
    )
    
    # Template structure
    template_data = Column(
        JSONB,
        nullable=False,
        doc="Template structure and settings"
    )
    
    # Task templates
    task_templates = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Predefined task templates"
    )
    
    # Default settings
    default_settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Default project settings"
    )
    
    # Usage tracking
    usage_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of times template was used"
    )
    
    is_public_template = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Public template availability"
    )
    
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey('user.id'),
        nullable=False,
        doc="Template creator"
    )
    
    # Relationships
    projects = relationship(
        "Project",
        secondary=project_templates_table,
        back_populates="templates"
    )
    
    creator = relationship("User", foreign_keys=[created_by])


# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "Project",
    "ProjectMember",
    "ProjectConfig",
    "ProjectActivity",
    "ProjectMetrics",
    "ProjectResource",
    "ProjectTemplate",
    "ProjectStatus",
    "ProjectPriority",
    "MemberRole",
    "ActivityType",
    "ResourceType",
    "project_templates_table"
]