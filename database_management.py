“””
YMERA Enterprise Database Architecture
Advanced database management with migrations, optimization, and multi-agent support
“””

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from contextlib import asynccontextmanager
import json
import uuid
import hashlib
from pathlib import Path

from sqlalchemy import (
create_engine, MetaData, Table, Column, Integer, String,
DateTime, Text, Boolean, Float, JSON, ForeignKey, Index,
UniqueConstraint, CheckConstraint, event, pool, LargeBinary
)
from sqlalchemy.ext.asyncio import (
create_async_engine, AsyncSession, async_sessionmaker,
AsyncEngine
)
from sqlalchemy.orm import (
declarative_base, sessionmaker, relationship,
selectinload, joinedload, Session
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func, select, insert, update, delete
from sqlalchemy.pool import QueuePool
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations
import structlog

logger = structlog.get_logger(“ymera.database”)

# ===================== ENHANCED BASE CLASSES =====================

class TimestampMixin:
“”“Mixin for automatic timestamp management”””
created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class SoftDeleteMixin:
“”“Mixin for soft deletion support”””
is_deleted = Column(Boolean, default=False, nullable=False, index=True)
deleted_at = Column(DateTime, nullable=True)

class EnhancedBase:
“”“Enhanced base class with advanced functionality”””

```
def to_dict(self, include_relations: bool = False) -> Dict[str, Any]:
    """Convert model instance to dictionary"""
    result = {}
    for column in self.__table__.columns:
        value = getattr(self, column.name)
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            result[column.name] = str(value)
        else:
            result[column.name] = value
    
    if include_relations:
        for relationship in self.__mapper__.relationships:
            value = getattr(self, relationship.key)
            if value is not None:
                if relationship.collection_class is None:  # One-to-one/many-to-one
                    result[relationship.key] = value.to_dict() if hasattr(value, 'to_dict') else str(value)
                else:  # One-to-many/many-to-many
                    result[relationship.key] = [
                        item.to_dict() if hasattr(item, 'to_dict') else str(item) 
                        for item in value
                    ]
    
    return result

def update_from_dict(self, data: Dict[str, Any], exclude: List[str] = None):
    """Update model instance from dictionary"""
    exclude = exclude or ['id', 'created_at']
    for key, value in data.items():
        if key not in exclude and hasattr(self, key):
            setattr(self, key, value)

@classmethod
def create_from_dict(cls, data: Dict[str, Any]):
    """Create model instance from dictionary"""
    return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
```

Base = declarative_base(cls=EnhancedBase)

# ===================== ASSOCIATION TABLES =====================

project_agents_table = Table(
‘project_agents’,
Base.metadata,
Column(‘project_id’, String, ForeignKey(‘projects.id’), primary_key=True),
Column(‘agent_id’, String, ForeignKey(‘agents.id’), primary_key=True),
Column(‘role’, String(50), default=‘member’),
Column(‘assigned_at’, DateTime, default=datetime.utcnow)
)

agent_collaborations_table = Table(
‘agent_collaborations’,
Base.metadata,
Column(‘agent_id’, String, ForeignKey(‘agents.id’), primary_key=True),
Column(‘collaborator_id’, String, ForeignKey(‘agents.id’), primary_key=True),
Column(‘collaboration_type’, String(50)),
Column(‘created_at’, DateTime, default=datetime.utcnow)
)

# ===================== CORE MODELS =====================

class User(Base, TimestampMixin, SoftDeleteMixin):
“”“Enhanced User model with comprehensive features”””
**tablename** = “users”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
username = Column(String(255), unique=True, nullable=False, index=True)
email = Column(String(255), unique=True, nullable=False, index=True)
password_hash = Column(String(255), nullable=False)
first_name = Column(String(100))
last_name = Column(String(100))

# Profile information
avatar_url = Column(String(500))
bio = Column(Text)
location = Column(String(100))
website = Column(String(500))

# Authentication & Security
email_verified = Column(Boolean, default=False)
phone_number = Column(String(20))
phone_verified = Column(Boolean, default=False)
two_factor_enabled = Column(Boolean, default=False)
two_factor_secret = Column(String(32))

# Access Control
role = Column(String(50), default='user', index=True)
permissions = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)
is_active = Column(Boolean, default=True, index=True)
last_login = Column(DateTime)
login_count = Column(Integer, default=0)

# Preferences
preferences = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
timezone = Column(String(50), default='UTC')
language = Column(String(10), default='en')

# API & Integration
api_key = Column(String(64), unique=True, index=True)
api_key_expires = Column(DateTime)
github_username = Column(String(100))

# Relationships
projects = relationship("Project", back_populates="owner")
tasks = relationship("Task", back_populates="user")
files = relationship("File", back_populates="user")
audit_logs = relationship("AuditLog", back_populates="user")

# Constraints
__table_args__ = (
    CheckConstraint('length(username) >= 3', name='username_min_length'),
    CheckConstraint('length(password_hash) >= 8', name='password_min_length'),
    Index('idx_user_email_active', 'email', 'is_active'),
    Index('idx_user_role_active', 'role', 'is_active'),
)
```

class Project(Base, TimestampMixin, SoftDeleteMixin):
“”“Enhanced Project model with comprehensive tracking”””
**tablename** = “projects”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
name = Column(String(255), nullable=False, index=True)
description = Column(Text)
owner_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)

# Project details
github_url = Column(String(500))
project_type = Column(String(50), default='general', index=True)
programming_language = Column(String(50))
framework = Column(String(100))

# Status & Progress
status = Column(String(50), default="active", index=True)
priority = Column(String(20), default='medium', index=True)
progress = Column(Float, default=0.0)
estimated_completion = Column(DateTime)

# Configuration
settings = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
environment_variables = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
dependencies = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)

# Metrics & Analytics
total_tasks = Column(Integer, default=0)
completed_tasks = Column(Integer, default=0)
success_rate = Column(Float, default=0.0)
total_lines_of_code = Column(Integer, default=0)
test_coverage = Column(Float, default=0.0)

# Metadata
tags = Column(ARRAY(String) if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)
metadata_info = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Relationships
owner = relationship("User", back_populates="projects")
tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
files = relationship("File", back_populates="project")
agents = relationship("Agent", secondary=project_agents_table, back_populates="projects")

# Constraints
__table_args__ = (
    CheckConstraint('progress >= 0 AND progress <= 100', name='progress_range'),
    CheckConstraint('success_rate >= 0 AND success_rate <= 100', name='success_rate_range'),
    CheckConstraint('test_coverage >= 0 AND test_coverage <= 100', name='coverage_range'),
    Index('idx_project_owner_status', 'owner_id', 'status'),
    Index('idx_project_type_status', 'project_type', 'status'),
)
```

class Agent(Base, TimestampMixin, SoftDeleteMixin):
“”“Enhanced Agent model with learning capabilities”””
**tablename** = “agents”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
name = Column(String(255), nullable=False, index=True)
agent_type = Column(String(100), nullable=False, index=True)
description = Column(Text)

# Agent Configuration
capabilities = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)
configuration = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
api_endpoints = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Status & Performance
status = Column(String(50), default="active", index=True)
health_status = Column(String(50), default="healthy", index=True)
load_factor = Column(Float, default=0.0)
response_time_avg = Column(Float, default=0.0)
success_rate = Column(Float, default=100.0)

# Learning & Intelligence
learning_model_version = Column(String(50), default="1.0")
knowledge_base = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
learning_history = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)
performance_metrics = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Statistics
tasks_completed = Column(Integer, default=0)
tasks_failed = Column(Integer, default=0)
total_execution_time = Column(Float, default=0.0)
last_active = Column(DateTime, default=datetime.utcnow)

# Relationships
tasks = relationship("Task", back_populates="agent")
communications = relationship("AgentCommunication", foreign_keys="AgentCommunication.sender_agent_id", back_populates="sender_agent")
received_communications = relationship("AgentCommunication", foreign_keys="AgentCommunication.receiver_agent_id", back_populates="receiver_agent")
projects = relationship("Project", secondary=project_agents_table, back_populates="agents")
collaborators = relationship("Agent", secondary=agent_collaborations_table, primaryjoin="Agent.id==agent_collaborations_table.c.agent_id", secondaryjoin="Agent.id==agent_collaborations_table.c.collaborator_id", back_populates="collaborators")

# Constraints
__table_args__ = (
    CheckConstraint('load_factor >= 0 AND load_factor <= 100', name='load_factor_range'),
    CheckConstraint('success_rate >= 0 AND success_rate <= 100', name='agent_success_rate_range'),
    Index('idx_agent_type_status', 'agent_type', 'status'),
    Index('idx_agent_health_status', 'health_status', 'status'),
)
```

class Task(Base, TimestampMixin, SoftDeleteMixin):
“”“Enhanced Task model with comprehensive tracking”””
**tablename** = “tasks”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
title = Column(String(500), nullable=False, index=True)
description = Column(Text)
task_type = Column(String(100), nullable=False, index=True)

# Relationships
user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
project_id = Column(String, ForeignKey('projects.id'), nullable=True, index=True)
agent_id = Column(String, ForeignKey('agents.id'), nullable=True, index=True)
parent_task_id = Column(String, ForeignKey('tasks.id'), nullable=True, index=True)

# Status & Priority
status = Column(String(50), default="pending", index=True)
priority = Column(String(20), default="medium", index=True)
urgency = Column(Integer, default=5)  # 1-10 scale

# Execution Details
input_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
output_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
execution_config = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
error_details = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Timing & Performance
scheduled_at = Column(DateTime, nullable=True, index=True)
started_at = Column(DateTime, nullable=True)
completed_at = Column(DateTime, nullable=True)
execution_time = Column(Float, default=0.0)  # in seconds
timeout = Column(Integer, default=3600)  # in seconds

# Progress & Results
progress = Column(Float, default=0.0)
result_summary = Column(Text)
quality_score = Column(Float, default=0.0)
retry_count = Column(Integer, default=0)
max_retries = Column(Integer, default=3)

# Dependencies & Context
dependencies = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)
context_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
tags = Column(ARRAY(String) if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)

# Relationships
user = relationship("User", back_populates="tasks")
project = relationship("Project", back_populates="tasks")
agent = relationship("Agent", back_populates="tasks")
parent_task = relationship("Task", remote_side=[id])
child_tasks = relationship("Task", back_populates="parent_task")

# Constraints
__table_args__ = (
    CheckConstraint('progress >= 0 AND progress <= 100', name='task_progress_range'),
    CheckConstraint('urgency >= 1 AND urgency <= 10', name='urgency_range'),
    CheckConstraint('quality_score >= 0 AND quality_score <= 100', name='quality_score_range'),
    Index('idx_task_status_priority', 'status', 'priority'),
    Index('idx_task_agent_status', 'agent_id', 'status'),
    Index('idx_task_scheduled', 'scheduled_at', 'status'),
)
```

class File(Base, TimestampMixin, SoftDeleteMixin):
“”“Enhanced File model with comprehensive metadata”””
**tablename** = “files”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
filename = Column(String(500), nullable=False, index=True)
original_filename = Column(String(500), nullable=False)
file_path = Column(String(1000), nullable=False)

# File Properties
file_size = Column(Integer, nullable=False)
mime_type = Column(String(200), index=True)
file_extension = Column(String(20), index=True)
encoding = Column(String(50))

# Security & Validation
checksum_md5 = Column(String(32), index=True)
checksum_sha256 = Column(String(64), index=True)
virus_scan_status = Column(String(50), default="pending", index=True)
virus_scan_result = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Access Control
user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
project_id = Column(String, ForeignKey('projects.id'), nullable=True, index=True)
access_level = Column(String(50), default="private", index=True)

# Metadata & Classification
file_category = Column(String(50), index=True)
tags = Column(ARRAY(String) if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)
metadata_extracted = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
content_summary = Column(Text)

# Usage Statistics
download_count = Column(Integer, default=0)
last_accessed = Column(DateTime)
access_history = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)

# Processing Status
processing_status = Column(String(50), default="completed", index=True)
processing_errors = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=list)

# Relationships
user = relationship("User", back_populates="files")
project = relationship("Project", back_populates="files")

# Constraints
__table_args__ = (
    CheckConstraint('file_size > 0', name='positive_file_size'),
    Index('idx_file_user_project', 'user_id', 'project_id'),
    Index('idx_file_category_access', 'file_category', 'access_level'),
)
```

class AgentCommunication(Base, TimestampMixin):
“”“Agent-to-agent communication log”””
**tablename** = “agent_communications”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
sender_agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
receiver_agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)

# Message Details
message_type = Column(String(100), nullable=False, index=True)
subject = Column(String(500))
content = Column(Text, nullable=False)
message_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Status & Processing
status = Column(String(50), default="sent", index=True)
priority = Column(String(20), default="normal", index=True)
read_at = Column(DateTime)
processed_at = Column(DateTime)
response_required = Column(Boolean, default=False)

# Context
conversation_id = Column(String, index=True)
thread_id = Column(String, index=True)
correlation_id = Column(String, index=True)

# Relationships
sender_agent = relationship("Agent", foreign_keys=[sender_agent_id], back_populates="communications")
receiver_agent = relationship("Agent", foreign_keys=[receiver_agent_id], back_populates="received_communications")

# Constraints
__table_args__ = (
    CheckConstraint('sender_agent_id != receiver_agent_id', name='different_agents'),
    Index('idx_comm_conversation', 'conversation_id', 'created_at'),
    Index('idx_comm_status_priority', 'status', 'priority'),
)
```

class AuditLog(Base, TimestampMixin):
“”“Comprehensive audit logging”””
**tablename** = “audit_logs”

```
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
user_id = Column(String, ForeignKey('users.id'), nullable=True, index=True)
agent_id = Column(String, ForeignKey('agents.id'), nullable=True, index=True)

# Action Details
action = Column(String(200), nullable=False, index=True)
resource_type = Column(String(100), nullable=False, index=True)
resource_id = Column(String, index=True)

# Context
ip_address = Column(String(45))  # IPv6 compatible
user_agent = Column(String(500))
session_id = Column(String(100), index=True)
request_id = Column(String(100), index=True)

# Details
action_details = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
before_state = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)
after_state = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=dict)

# Result
success = Column(Boolean, nullable=False, index=True)
error_message = Column(Text)
execution_time = Column(Float)  # in seconds

# Relationships
user = relationship("User", back_populates="audit_logs")

# Constraints
__table_args__ = (
    Index('idx_audit_action_time', 'action', 'created_at'),
    Index('idx_audit_resource', 'resource_type', 'resource_id'),
    Index('idx_audit_user_time', 'user_id', 'created_at'),
)
```

# ===================== DATABASE MANAGER =====================

class DatabaseManager:
“”“Advanced database management with migrations and optimization”””

```
def __init__(self, database_url: str, echo: bool = False):
    self.database_url = database_url
    self.echo = echo
    self.engine: Optional[AsyncEngine] = None
    self.async_session_factory: Optional[async_sessionmaker] = None
    
async def initialize(self):
    """Initialize database connection and create tables"""
    # Create async engine with optimized settings
    self.engine = create_async_engine(
        self.database_url,
        echo=self.echo,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "command_timeout": 60,
            "server_settings": {
                "jit": "off",
                "statement_timeout": "300s",
            }
        } if 'postgresql' in self.database_url else {}
    )
    
    # Create session factory
    self.async_session_factory = async_sessionmaker(
        self.engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create tables
    async with self.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")

@asynccontextmanager
async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
    """Get database session with proper cleanup"""
    async with self.async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def health_check(self) -> Dict[str, Any]:
    """Check database health"""
    try:
        async with self.get_session() as session:
            result = await session.execute(select(func.now()))
            db_time = result.scalar()
            
            return {
                "status": "healthy",
                "database_time": db_time.isoformat() if db_time else None,
                "connection_pool_size": self.engine.pool.size() if hasattr(self.engine.pool, 'size') else 'unknown'
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

async def get_statistics(self) -> Dict[str, Any]:
    """Get database statistics"""
    async with self.get_session() as session:
        stats = {}
        
        # Count records in each table
        for table_name, table_class in {
            'users': User,
            'projects': Project,
            'agents': Agent,
            'tasks': Task,
            'files': File,
            'agent_communications': AgentCommunication,
            'audit_logs': AuditLog
        }.items():
            result = await session.execute(select(func.count(table_class.id)))
            stats[f"{table_name}_count"] = result.scalar()
        
        # Get recent activity
        result = await session.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.created_at > datetime.utcnow() - timedelta(hours=24))
        )
        stats['recent_activity_24h'] = result.scalar()
        
        return stats

async def cleanup_old_data(self, days: int = 30):
    """Clean up old audit logs and soft-deleted records"""
    async with self.get_session() as session:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Clean old audit logs
        result = await session.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff_date)
        )
        audit_cleaned = result.rowcount
        
        # Clean old soft-deleted records
        for model in [User, Project, Agent, Task, File]:
            if hasattr(model, 'is_deleted'):
                result = await session.execute(
                    delete(model).where(
                        model.is_deleted == True,
                        model.deleted_at < cutoff_date
                    )
                )
        
        await session.commit()
        logger.info(f"Cleaned {audit_cleaned} old audit logs and soft-deleted records")

async def close(self):
    """Close database connections"""
    if self.engine:
        await self.engine.dispose()
        logger.info("Database connections closed")
```

# ===================== MIGRATION MANAGER =====================

class MigrationManager:
“”“Handle database migrations with Alembic”””

```
def __init__(self, database_url: str, alembic_cfg_path: str = "alembic.ini"):
    self.database_url = database_url
    self.alembic_cfg_path = alembic_cfg_path
    
def create_migration(self, message: str):
    """Create a new migration"""
    alembic_cfg = Config(self.alembic_cfg_path)
    alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)
    command.revision(alembic_cfg, autogenerate=True, message=message)
    
def upgrade_database(self, revision: str = "head"):
    """Upgrade database to specific revision"""
    alembic_cfg = Config(self.alembic_cfg_path)
    alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)
    command.upgrade(alembic_cfg, revision)
    
def downgrade_database(self, revision: str):
    """Downgrade database to specific revision"""
    alembic_cfg = Config(self.alembic_cfg_path)
    alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)
    command.downgrade(alembic_cfg, revision)
```

# ===================== REPOSITORY PATTERN =====================

class BaseRepository:
“”“Base repository with common CRUD operations”””

```
def __init__(self, session: AsyncSession, model_class):
    self.session = session
    self.model_class = model_class

async def create(self, **kwargs) -> Any:
    """Create new record"""
    instance = self.model_class(**kwargs)
    self.session.add(instance)
    await self.session.flush()
    return instance

async def get_by_id(self, id: str) -> Optional[Any]:
    """Get record by ID"""
    result = await self.session.execute(
        select(self.model_class).where(self.model_class.id == id)
    )
    return result.scalar_one_or_none()

async def get_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
    """Get all records with pagination"""
    result = await self.session.execute(
        select(self.model_class).limit(limit).offset(offset)
    )
    return result.scalars().all()

async def update(self, id: str, **kwargs) -> Optional[Any]:
    """Update record"""
    instance = await self.get_by_id(id)
    if instance:
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
    return instance

async def delete(self, id: str) -> bool:
    """Delete record (hard delete)"""
    instance = await self.get_by_id(id)
    if instance:
        await self.session.delete(instance)
        await self.session.flush()
        return True
    return False

async def soft_delete(self, id: str) -> bool:
    """Soft delete record if supported"""
    if hasattr(self.model_class, 'is_deleted'):
        instance = await self.get_by_id(id)
        if instance:
            instance.is_deleted = True
            instance.deleted_at = datetime.utcnow()
            await self.session.flush()
            return True
    return False
```

# ===================== SPECIALIZED REPOSITORIES =====================

class UserRepository(BaseRepository):
“”“User-specific repository operations”””

```
def __init__(self, session: AsyncSession):
    super().__init__(session, User)

async def get_by_username(self, username: str) -> Optional[User]:
    """Get user by username"""
    result = await self.session.execute(
        select(User).where(User.username == username, User.is_deleted == False)
    )
    return result.scalar_one_or_none()

async def get_by_email(self, email: str) -> Optional[User]:
    """Get user by email"""
    result = await self.session.execute(
        select(User).where(User.email == email, User.is_deleted == False)
    )
    return result.scalar_one_or_none()
```

class ProjectRepository(BaseRepository):
“”“Project-specific repository operations”””

```
def __init__(self, session: AsyncSession):
    super().__init__(session, Project)

async def get_user_projects(self, user_id: str, status: str = None) -> List[Project]:
    """Get projects for a user"""
    query = select(Project).where(Project.owner_id == user_id, Project.is_deleted == False)
    if status:
        query = query.where(Project.status == status)
    
    result = await self.session.execute(query)
    return result.scalars().all()
```

# Export all classes

**all** = [
‘Base’, ‘User’, ‘Project’, ‘Agent’, ‘Task’, ‘File’, ‘AgentCommunication’, ‘AuditLog’,
‘DatabaseManager’, ‘MigrationManager’, ‘BaseRepository’, ‘UserRepository’, ‘ProjectRepository’
]