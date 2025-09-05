"""
YMERA Enterprise User Management Models
Production-Ready SQLAlchemy Models with Advanced Features
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, JSON, 
    ForeignKey, Index, CheckConstraint, UniqueConstraint,
    DECIMAL, Enum as SQLEnum, event, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import UUID, JSONB
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set
from enum import Enum
import uuid
import secrets
import hashlib
import pyotp
import re
from dataclasses import dataclass
from pydantic import BaseModel, EmailStr, validator, Field
import logging

Base = declarative_base()

# Security Configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# Enums
class UserRole(str, Enum):
    """User roles in the YMERA system"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin" 
    PROJECT_MANAGER = "project_manager"
    SENIOR_DEVELOPER = "senior_developer"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    SECURITY_OFFICER = "security_officer"
    AUDITOR = "auditor"
    VIEWER = "viewer"
    API_CLIENT = "api_client"

class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    LOCKED = "locked"
    ARCHIVED = "archived"

class AuthenticationMethod(str, Enum):
    """Available authentication methods"""
    PASSWORD = "password"
    MFA_TOTP = "mfa_totp"
    SSO_OAUTH = "sso_oauth"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"

class LearningProfile(str, Enum):
    """User learning interaction profiles"""
    AGGRESSIVE = "aggressive"      # High learning rate, frequent updates
    MODERATE = "moderate"         # Balanced learning approach
    CONSERVATIVE = "conservative" # Slow, careful learning
    PASSIVE = "passive"          # Minimal learning, manual updates only

class AgentInteractionLevel(str, Enum):
    """User's preferred agent interaction level"""
    FULL_AUTONOMOUS = "full_autonomous"
    SEMI_AUTONOMOUS = "semi_autonomous"
    COLLABORATIVE = "collaborative"
    MANUAL_APPROVAL = "manual_approval"
    OBSERVATION_ONLY = "observation_only"

# Core User Model
class User(Base):
    """
    Enterprise User Model with comprehensive features:
    - Multi-factor authentication
    - Role-based access control
    - Learning engine integration
    - Agent interaction preferences
    - Security audit trails
    - Performance analytics
    """
    __tablename__ = "users"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Authentication & Security
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(32), nullable=False, default=lambda: secrets.token_hex(16))
    mfa_secret = Column(String(32), nullable=True)  # TOTP secret
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_backup_codes = Column(JSONB, default=list, nullable=False)  # Encrypted backup codes
    
    # Profile Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    timezone = Column(String(50), default="UTC", nullable=False)
    locale = Column(String(10), default="en-US", nullable=False)
    
    # System Status
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.VIEWER)
    status = Column(SQLEnum(UserStatus), nullable=False, default=UserStatus.PENDING_VERIFICATION)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_service_account = Column(Boolean, default=False, nullable=False)
    
    # Learning Engine Integration
    learning_profile = Column(SQLEnum(LearningProfile), default=LearningProfile.MODERATE, nullable=False)
    agent_interaction_level = Column(SQLEnum(AgentInteractionLevel), default=AgentInteractionLevel.COLLABORATIVE, nullable=False)
    learning_preferences = Column(JSONB, default=dict, nullable=False)
    personalization_data = Column(JSONB, default=dict, nullable=False)
    
    # Activity & Analytics
    total_projects = Column(Integer, default=0, nullable=False)
    total_tasks_completed = Column(Integer, default=0, nullable=False)
    total_agent_interactions = Column(Integer, default=0, nullable=False)
    learning_score = Column(DECIMAL(5, 2), default=0.00, nullable=False)  # 0-100 score
    efficiency_rating = Column(DECIMAL(3, 2), default=1.00, nullable=False)  # Multiplier
    
    # Security & Compliance
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    account_locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 support
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Audit Trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    
    # Metadata
    metadata = Column(JSONB, default=dict, nullable=False)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id], remote_side=[id])
    updated_by = relationship("User", foreign_keys=[updated_by_id], remote_side=[id])
    
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("UserAPIKey", back_populates="user", cascade="all, delete-orphan")
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    learning_interactions = relationship("UserLearningInteraction", back_populates="user", cascade="all, delete-orphan")
    agent_preferences = relationship("UserAgentPreference", back_populates="user", cascade="all, delete-orphan")
    security_events = relationship("UserSecurityEvent", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes and Constraints
    __table_args__ = (
        Index("idx_user_email_status", "email", "status"),
        Index("idx_user_role_status", "role", "status"),
        Index("idx_user_created_at", "created_at"),
        Index("idx_user_last_activity", "last_activity_at"),
        Index("idx_user_learning_profile", "learning_profile"),
        CheckConstraint("learning_score >= 0 AND learning_score <= 100", name="check_learning_score_range"),
        CheckConstraint("efficiency_rating >= 0.1 AND efficiency_rating <= 5.0", name="check_efficiency_range"),
        CheckConstraint("failed_login_attempts >= 0", name="check_failed_attempts_positive"),
        UniqueConstraint("email", "deleted_at", name="unique_active_email"),
    )
    
    # Validation
    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValueError("Invalid email format")
        return email.lower()
    
    @validates('username')
    def validate_username(self, key, username):
        if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', username):
            raise ValueError("Username must be 3-50 characters, alphanumeric, underscore, or hyphen only")
        return username.lower()
    
    @validates('timezone')
    def validate_timezone(self, key, timezone):
        # Basic timezone validation - in production, use pytz
        if not timezone or len(timezone) < 3:
            return "UTC"
        return timezone
    
    # Hybrid Properties
    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @hybrid_property
    def is_active(self):
        return self.status == UserStatus.ACTIVE and not self.deleted_at
    
    @hybrid_property
    def is_locked(self):
        return (self.account_locked_until and 
                self.account_locked_until > datetime.utcnow()) or \
               self.status == UserStatus.LOCKED
    
    @hybrid_property
    def is_admin(self):
        return self.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    
    @hybrid_property
    def learning_effectiveness(self):
        """Calculate learning effectiveness based on interactions and score"""
        if self.total_agent_interactions == 0:
            return 0.0
        return float(self.learning_score) * float(self.efficiency_rating) / 100.0
    
    # Password Management
    def set_password(self, password: str) -> None:
        """Set password with enhanced security"""
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters long")
        
        # Generate new salt for each password
        self.salt = secrets.token_hex(16)
        self.password_hash = pwd_context.hash(password + self.salt)
        self.password_changed_at = datetime.utcnow()
        self.failed_login_attempts = 0  # Reset on password change
    
    def verify_password(self, password: str) -> bool:
        """Verify password with timing attack protection"""
        if not self.password_hash or not self.salt:
            return False
        return pwd_context.verify(password + self.salt, self.password_hash)
    
    # MFA Management
    def generate_mfa_secret(self) -> str:
        """Generate new MFA secret"""
        self.mfa_secret = pyotp.random_base32()
        return self.mfa_secret
    
    def get_mfa_uri(self) -> str:
        """Get MFA URI for QR code generation"""
        if not self.mfa_secret:
            raise ValueError("MFA secret not generated")
        
        return pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(
            name=self.email,
            issuer_name="YMERA Enterprise"
        )
    
    def verify_mfa_token(self, token: str) -> bool:
        """Verify MFA TOTP token"""
        if not self.mfa_enabled or not self.mfa_secret:
            return True  # MFA not enabled
        
        totp = pyotp.TOTP(self.mfa_secret)
        return totp.verify(token, valid_window=1)
    
    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """Generate MFA backup codes"""
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        # In production, encrypt these codes
        self.mfa_backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in codes]
        return codes
    
    def verify_backup_code(self, code: str) -> bool:
        """Verify and consume MFA backup code"""
        if not self.mfa_backup_codes:
            return False
        
        code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
        if code_hash in self.mfa_backup_codes:
            self.mfa_backup_codes.remove(code_hash)
            return True
        return False
    
    # Security Methods
    def lock_account(self, duration_minutes: int = 30) -> None:
        """Lock user account for specified duration"""
        self.account_locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.status = UserStatus.LOCKED
    
    def unlock_account(self) -> None:
        """Unlock user account"""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        if self.status == UserStatus.LOCKED:
            self.status = UserStatus.ACTIVE
    
    def record_failed_login(self) -> None:
        """Record failed login attempt with auto-lock"""
        self.failed_login_attempts += 1
        
        # Auto-lock after 5 failed attempts
        if self.failed_login_attempts >= 5:
            self.lock_account(30)  # 30 minutes
    
    def record_successful_login(self, ip_address: str) -> None:
        """Record successful login"""
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.last_activity_at = datetime.utcnow()
        self.failed_login_attempts = 0
    
    # Learning Engine Integration
    def update_learning_score(self, interaction_quality: float, task_success: bool = True) -> None:
        """Update learning score based on agent interactions"""
        current_score = float(self.learning_score)
        
        # Calculate new score based on profile
        if self.learning_profile == LearningProfile.AGGRESSIVE:
            learning_rate = 0.15
        elif self.learning_profile == LearningProfile.MODERATE:
            learning_rate = 0.10
        elif self.learning_profile == LearningProfile.CONSERVATIVE:
            learning_rate = 0.05
        else:  # PASSIVE
            learning_rate = 0.02
        
        # Adjust based on task success
        if task_success:
            score_delta = learning_rate * interaction_quality * 10
        else:
            score_delta = -learning_rate * interaction_quality * 5
        
        # Update with bounds checking
        new_score = max(0, min(100, current_score + score_delta))
        self.learning_score = new_score
    
    def update_efficiency_rating(self, task_completion_time: float, expected_time: float) -> None:
        """Update efficiency rating based on task performance"""
        if expected_time <= 0:
            return
        
        # Calculate efficiency (lower time = higher efficiency)
        task_efficiency = expected_time / max(task_completion_time, 0.1)
        
        # Exponential moving average
        alpha = 0.1
        current_rating = float(self.efficiency_rating)
        new_rating = alpha * task_efficiency + (1 - alpha) * current_rating
        
        # Bound the rating
        self.efficiency_rating = max(0.1, min(5.0, new_rating))
    
    def get_learning_recommendations(self) -> Dict[str, Any]:
        """Get personalized learning recommendations"""
        score = float(self.learning_score)
        efficiency = float(self.efficiency_rating)
        
        recommendations = {
            "suggested_learning_profile": self.learning_profile,
            "recommended_agent_level": self.agent_interaction_level,
            "focus_areas": [],
            "confidence_score": min(score / 100.0, 1.0)
        }
        
        # Generate focus areas based on performance
        if score < 30:
            recommendations["focus_areas"].append("basic_system_interaction")
        elif score < 60:
            recommendations["focus_areas"].append("intermediate_workflow_optimization")
        else:
            recommendations["focus_areas"].append("advanced_automation_techniques")
        
        if efficiency < 1.0:
            recommendations["focus_areas"].append("efficiency_improvement")
        
        return recommendations
    
    # Utility Methods
    def can_perform_action(self, action: str) -> bool:
        """Check if user can perform specific action based on role and status"""
        if not self.is_active or self.is_locked:
            return False
        
        # Define role-based permissions (simplified)
        role_permissions = {
            UserRole.SUPER_ADMIN: ["*"],  # All actions
            UserRole.ADMIN: ["manage_users", "manage_projects", "view_analytics"],
            UserRole.PROJECT_MANAGER: ["manage_projects", "assign_tasks", "view_reports"],
            UserRole.SENIOR_DEVELOPER: ["create_projects", "modify_code", "deploy"],
            UserRole.DEVELOPER: ["modify_code", "run_tests", "view_projects"],
            UserRole.ANALYST: ["view_analytics", "generate_reports", "view_projects"],
            UserRole.SECURITY_OFFICER: ["security_scan", "view_vulnerabilities", "manage_security"],
            UserRole.AUDITOR: ["view_audit_logs", "generate_reports"],
            UserRole.VIEWER: ["view_projects", "view_reports"],
            UserRole.API_CLIENT: ["api_access"]
        }
        
        allowed_actions = role_permissions.get(self.role, [])
        return "*" in allowed_actions or action in allowed_actions
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert user to dictionary representation"""
        data = {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "role": self.role.value,
            "status": self.status.value,
            "is_verified": self.is_verified,
            "learning_profile": self.learning_profile.value,
            "agent_interaction_level": self.agent_interaction_level.value,
            "learning_score": float(self.learning_score),
            "efficiency_rating": float(self.efficiency_rating),
            "total_projects": self.total_projects,
            "total_tasks_completed": self.total_tasks_completed,
            "total_agent_interactions": self.total_agent_interactions,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "created_at": self.created_at.isoformat(),
            "timezone": self.timezone,
            "locale": self.locale
        }
        
        if include_sensitive:
            data.update({
                "mfa_enabled": self.mfa_enabled,
                "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
                "failed_login_attempts": self.failed_login_attempts,
                "is_locked": self.is_locked
            })
        
        return data
    
    def __repr__(self):
        return f"<User {self.username} ({self.email}) - {self.role.value}>"


# User Session Model
class UserSession(Base):
    """User session management with enhanced security"""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True)
    
    # Session metadata
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Security
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    revoked_by = relationship("User", foreign_keys=[revoked_by_id])
    
    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )
    
    @hybrid_property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def revoke(self, revoked_by_user_id: uuid.UUID = None):
        """Revoke session"""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_by_id = revoked_by_user_id


# API Key Model
class UserAPIKey(Base):
    """User API key management"""
    __tablename__ = "user_api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    prefix = Column(String(10), nullable=False)  # First few chars for identification
    
    # Permissions & Limits
    scopes = Column(JSONB, default=list, nullable=False)  # List of allowed scopes
    rate_limit_per_hour = Column(Integer, default=1000, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Lifecycle
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        Index("idx_api_key_user_active", "user_id", "is_active"),
        Index("idx_api_key_expires", "expires_at"),
    )
    
    @classmethod
    def generate_key(cls) -> tuple[str, str]:
        """Generate API key and return (key, hash)"""
        key = f"ymera_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key, key_hash
    
    def verify_key(self, key: str) -> bool:
        """Verify API key"""
        return hashlib.sha256(key.encode()).hexdigest() == self.key_hash


# Permission Model
class UserPermission(Base):
    """Fine-grained user permissions"""
    __tablename__ = "user_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    resource_type = Column(String(50), nullable=False)  # project, agent, system
    resource_id = Column(String(100), nullable=True)   # specific resource ID
    permission = Column(String(50), nullable=False)    # read, write, delete, admin
    
    # Conditions
    conditions = Column(JSONB, default=dict, nullable=False)  # Time-based, IP-based, etc.
    
    # Lifecycle
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    granted_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="permissions")
    granted_by = relationship("User", foreign_keys=[granted_by_id])
    
    __table_args__ = (
        UniqueConstraint("user_id", "resource_type", "resource_id", "permission", 
                        name="unique_user_permission"),
        Index("idx_permission_user_resource", "user_id", "resource_type"),
    )


# Learning Interaction Model
class UserLearningInteraction(Base):
    """Track user interactions with learning engine"""
    __tablename__ = "user_learning_interactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Interaction details
    interaction_type = Column(String(50), nullable=False)  # agent_chat, code_review, etc.
    agent_id = Column(String(100), nullable=True)
    context = Column(JSONB, default=dict, nullable=False)
    
    # Learning metrics
    interaction_quality = Column(DECIMAL(3, 2), nullable=False)  # 0.00 - 1.00
    user_satisfaction = Column(Integer, nullable=True)  # 1-5 rating
    learning_outcome = Column(String(20), nullable=True)  # success, partial, failure
    
    # Feedback
    user_feedback = Column(Text, nullable=True)
    system_feedback = Column(JSONB, default=dict, nullable=False)
    
    # Timing
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="learning_interactions")
    
    __table_args__ = (
        Index("idx_learning_user_type", "user_id", "interaction_type"),
        Index("idx_learning_created", "created_at"),
    )


# Agent Preference Model
class UserAgentPreference(Base):
    """User preferences for specific agents"""
    __tablename__ = "user_agent_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    agent_type = Column(String(100), nullable=False)  # analysis, enhancement, etc.
    agent_id = Column(String(100), nullable=True)     # specific agent instance
    
    # Preferences
    interaction_level = Column(SQLEnum(AgentInteractionLevel), nullable=False)
    auto_approve_threshold = Column(DECIMAL(3, 2), default=0.80, nullable=False)
    notification_preferences = Column(JSONB, default=dict, nullable=False)
    
    # Custom settings
    custom_prompts = Column(JSONB, default=dict, nullable=False)
    parameter_overrides = Column(JSONB, default=dict, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="agent_preferences")
    
    __table_args__ = (
        UniqueConstraint("user_id", "agent_type", "agent_id", name="unique_user_agent_pref"),
        Index("idx_agent_pref_user_type", "user_id", "agent_type"),
    )


# Security Event Model
class UserSecurityEvent(Base):
    """Security event logging for users"""
    __tablename__ = "user_security_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    event_type = Column(String(50), nullable=False)  # login, logout, password_change, etc.
    severity = Column(String(20), nullable=False)    # low, medium, high, critical
    description = Column(Text, nullable=False)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    additional_data = Column(JSONB, default=dict, nullable=False)
    
    # Status
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="security_events")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    
    __table_args__ = (
        Index("idx_security_event_user_type", "user_id", "event_type"),
        Index("idx_security_event_severity", "severity", "created_at"),
    )


# Pydantic Models for API
class UserBase(BaseModel):
    """Base user model for API responses"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = None
    timezone: str = Field(default="UTC", max_length=50)
    locale: str = Field(default="en-US", max_length=10)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+, v):
            raise ValueError('Username must contain only letters, numbers, underscores, and hyphens')
        return v.lower()


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=12, max_length=128)
    role: UserRole = UserRole.VIEWER
    learning_profile: LearningProfile = LearningProfile.MODERATE
    agent_interaction_level: AgentInteractionLevel = AgentInteractionLevel.COLLABORATIVE
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        
        checks = [
            any(c.islower() for c in v),  # lowercase
            any(c.isupper() for c in v),  # uppercase
            any(c.isdigit() for c in v),  # digit
            any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)  # special char
        ]
        
        if sum(checks) < 3:
            raise ValueError('Password must contain at least 3 of: lowercase, uppercase, digit, special character')
        
        return v


class UserUpdate(BaseModel):
    """User update model"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = None
    avatar_url: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = Field(None, max_length=50)
    locale: Optional[str] = Field(None, max_length=10)
    learning_profile: Optional[LearningProfile] = None
    agent_interaction_level: Optional[AgentInteractionLevel] = None
    learning_preferences: Optional[Dict[str, Any]] = None
    personalization_data: Optional[Dict[str, Any]] = None


class UserResponse(UserBase):
    """User response model"""
    id: str
    role: UserRole
    status: UserStatus
    is_verified: bool
    is_service_account: bool
    learning_profile: LearningProfile
    agent_interaction_level: AgentInteractionLevel
    learning_score: float
    efficiency_rating: float
    total_projects: int
    total_tasks_completed: int
    total_agent_interactions: int
    last_activity_at: Optional[datetime]
    created_at: datetime
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Detailed user response with sensitive info (admin only)"""
    mfa_enabled: bool
    last_login_at: Optional[datetime]
    last_login_ip: Optional[str]
    failed_login_attempts: int
    is_locked: bool
    account_locked_until: Optional[datetime]
    password_changed_at: datetime
    learning_effectiveness: float
    metadata: Dict[str, Any]


class UserSecurityResponse(BaseModel):
    """User security status response"""
    mfa_enabled: bool
    active_sessions_count: int
    active_api_keys_count: int
    last_password_change: datetime
    recent_security_events: List[Dict[str, Any]]
    risk_score: float
    
    class Config:
        from_attributes = True


class UserLearningStatsResponse(BaseModel):
    """User learning statistics response"""
    learning_score: float
    efficiency_rating: float
    learning_profile: LearningProfile
    agent_interaction_level: AgentInteractionLevel
    total_interactions: int
    recent_interactions_count: int
    learning_effectiveness: float
    recommendations: Dict[str, Any]
    progress_trend: List[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    """Session creation request"""
    username: str
    password: str
    mfa_token: Optional[str] = None
    remember_me: bool = False


class SessionResponse(BaseModel):
    """Session response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    
    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    """API key creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = []
    expires_in_days: Optional[int] = Field(None, gt=0, le=365)
    rate_limit_per_hour: int = Field(1000, gt=0, le=10000)


class APIKeyResponse(BaseModel):
    """API key response model"""
    id: str
    name: str
    prefix: str
    scopes: List[str]
    rate_limit_per_hour: int
    is_active: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str = Field(..., min_length=12, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        
        checks = [
            any(c.islower() for c in v),
            any(c.isupper() for c in v),
            any(c.isdigit() for c in v),
            any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)
        ]
        
        if sum(checks) < 3:
            raise ValueError('Password must contain at least 3 character types')
        
        return v


class MFASetupResponse(BaseModel):
    """MFA setup response"""
    secret: str
    qr_uri: str
    backup_codes: List[str]


class LearningInteractionCreate(BaseModel):
    """Learning interaction creation request"""
    interaction_type: str
    agent_id: Optional[str] = None
    context: Dict[str, Any] = {}
    interaction_quality: float = Field(..., ge=0.0, le=1.0)
    user_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    learning_outcome: Optional[str] = None
    user_feedback: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, gt=0)


class AgentPreferenceUpdate(BaseModel):
    """Agent preference update request"""
    interaction_level: Optional[AgentInteractionLevel] = None
    auto_approve_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    notification_preferences: Optional[Dict[str, Any]] = None
    custom_prompts: Optional[Dict[str, Any]] = None
    parameter_overrides: Optional[Dict[str, Any]] = None


# Database event handlers for automated features
@event.listens_for(User, 'before_insert')
def set_user_defaults(mapper, connection, target):
    """Set default values before user creation"""
    if not target.display_name:
        target.display_name = target.full_name
    
    # Initialize learning preferences based on profile
    if not target.learning_preferences:
        target.learning_preferences = {
            "auto_suggestions": True,
            "feedback_frequency": "moderate",
            "learning_reminders": True,
            "progress_notifications": True
        }
    
    # Initialize personalization data
    if not target.personalization_data:
        target.personalization_data = {
            "ui_preferences": {},
            "workflow_patterns": {},
            "favorite_agents": [],
            "custom_shortcuts": {}
        }


@event.listens_for(User, 'before_update')
def update_user_metrics(mapper, connection, target):
    """Update user activity metrics before saving"""
    target.updated_at = datetime.utcnow()
    
    # Update learning effectiveness calculation
    if target.total_agent_interactions > 0:
        # This would be calculated by the learning engine
        pass


@event.listens_for(UserSession, 'before_insert')
def generate_session_tokens(mapper, connection, target):
    """Generate secure session tokens"""
    if not target.session_token:
        target.session_token = secrets.token_urlsafe(32)
    
    if not target.refresh_token:
        target.refresh_token = secrets.token_urlsafe(32)


# Utility functions for user management
class UserManager:
    """Enterprise user management utilities"""
    
    @staticmethod
    def calculate_risk_score(user: User, recent_events: List[UserSecurityEvent]) -> float:
        """Calculate user security risk score (0.0 - 1.0)"""
        risk_factors = []
        
        # Failed login attempts
        if user.failed_login_attempts > 0:
            risk_factors.append(min(user.failed_login_attempts / 10.0, 0.3))
        
        # Recent security events
        critical_events = sum(1 for event in recent_events if event.severity == "critical")
        high_events = sum(1 for event in recent_events if event.severity == "high")
        
        if critical_events > 0:
            risk_factors.append(min(critical_events * 0.4, 0.8))
        if high_events > 0:
            risk_factors.append(min(high_events * 0.2, 0.4))
        
        # Account age (newer accounts have higher risk)
        account_age_days = (datetime.utcnow() - user.created_at).days
        if account_age_days < 30:
            risk_factors.append(0.2)
        
        # MFA status
        if not user.mfa_enabled:
            risk_factors.append(0.3)
        
        # Password age
        password_age_days = (datetime.utcnow() - user.password_changed_at).days
        if password_age_days > 90:
            risk_factors.append(0.1)
        
        return min(sum(risk_factors), 1.0)
    
    @staticmethod
    def get_learning_progress_trend(user: User, interactions: List[UserLearningInteraction]) -> List[Dict[str, Any]]:
        """Calculate learning progress trend over time"""
        if not interactions:
            return []
        
        # Group interactions by week
        from collections import defaultdict
        weekly_data = defaultdict(list)
        
        for interaction in interactions:
            week_key = interaction.created_at.strftime("%Y-W%U")
            weekly_data[week_key].append(interaction)
        
        trend = []
        for week, week_interactions in sorted(weekly_data.items()):
            avg_quality = sum(float(i.interaction_quality) for i in week_interactions) / len(week_interactions)
            success_rate = sum(1 for i in week_interactions if i.learning_outcome == "success") / len(week_interactions)
            
            trend.append({
                "week": week,
                "interaction_count": len(week_interactions),
                "average_quality": round(avg_quality, 2),
                "success_rate": round(success_rate, 2),
                "total_duration": sum(i.duration_seconds or 0 for i in week_interactions)
            })
        
        return trend[-12:]  # Last 12 weeks
    
    @staticmethod
    def suggest_role_upgrade(user: User) -> Optional[UserRole]:
        """Suggest role upgrade based on user performance"""
        if user.learning_score < 70 or user.efficiency_rating < 1.5:
            return None
        
        current_role_hierarchy = {
            UserRole.VIEWER: UserRole.DEVELOPER,
            UserRole.DEVELOPER: UserRole.SENIOR_DEVELOPER,
            UserRole.SENIOR_DEVELOPER: UserRole.PROJECT_MANAGER,
            UserRole.ANALYST: UserRole.SENIOR_DEVELOPER,
        }
        
        if user.role in current_role_hierarchy and user.total_tasks_completed >= 50:
            return current_role_hierarchy[user.role]
        
        return None
    
    @staticmethod
    def validate_user_constraints(user: User, session: Session) -> List[str]:
        """Validate user data constraints and return list of violations"""
        violations = []
        
        # Check unique constraints manually (in addition to DB constraints)
        existing_email = session.query(User).filter(
            User.email == user.email,
            User.id != user.id,
            User.deleted_at.is_(None)
        ).first()
        
        if existing_email:
            violations.append("Email address is already in use")
        
        existing_username = session.query(User).filter(
            User.username == user.username,
            User.id != user.id,
            User.deleted_at.is_(None)
        ).first()
        
        if existing_username:
            violations.append("Username is already in use")
        
        # Validate role permissions
        if user.role == UserRole.SUPER_ADMIN:
            # Limit super admin accounts
            super_admin_count = session.query(User).filter(
                User.role == UserRole.SUPER_ADMIN,
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None)
            ).count()
            
            if super_admin_count >= 3:  # Max 3 super admins
                violations.append("Maximum number of super admin accounts reached")
        
        return violations


# Export all models and utilities
__all__ = [
    # Enums
    'UserRole', 'UserStatus', 'AuthenticationMethod', 'LearningProfile', 'AgentInteractionLevel',
    
    # SQLAlchemy Models
    'User', 'UserSession', 'UserAPIKey', 'UserPermission', 'UserLearningInteraction',
    'UserAgentPreference', 'UserSecurityEvent',
    
    # Pydantic Models
    'UserBase', 'UserCreate', 'UserUpdate', 'UserResponse', 'UserDetailResponse',
    'UserSecurityResponse', 'UserLearningStatsResponse', 'SessionCreate', 'SessionResponse',
    'APIKeyCreate', 'APIKeyResponse', 'PasswordChangeRequest', 'MFASetupResponse',
    'LearningInteractionCreate', 'AgentPreferenceUpdate',
    
    # Utilities
    'UserManager', 'pwd_context'
]