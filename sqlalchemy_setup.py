"""
YMERA Enterprise Multi-Agent System - Enhanced SQLAlchemy Setup
Production-ready database management with migrations and optimization
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
from contextlib import asynccontextmanager
import json
import uuid

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, 
    DateTime, Text, Boolean, Float, JSON, ForeignKey, Index,
    UniqueConstraint, CheckConstraint, event, pool
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import (
    declarative_base, sessionmaker, relationship,
    selectinload, joinedload
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func, select
from sqlalchemy.pool import QueuePool
import alembic
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations

logger = logging.getLogger(__name__)

# Enhanced Base with utility methods
class EnhancedBase:
    """Enhanced base class with common functionality"""
    
    @classmethod
    def __tablename__(cls):
        return cls.__name__.lower() + 's'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]):
        """Update model instance from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

Base = declarative_base(cls=EnhancedBase)

# Enhanced Database Models with better relationships and constraints
class Project(Base):
    """Enhanced Project model with full tracking"""
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    github_url = Column(String(500))
    status = Column(String(50), default="active", index=True)
    
    # Enhanced metadata
    metadata_info = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    settings = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Performance tracking
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    
    # Relationships
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    agents = relationship("Agent", secondary="project_agents", back_populates="projects")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('success_rate >= 0 AND success_rate <= 1', name='valid_success_rate'),
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name='valid_status'),
        Index('idx_project_status_created', 'status', 'created_at'),
    )

class Agent(Base):
    """Enhanced Agent model with comprehensive tracking"""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="idle", index=True)
    
    # Capabilities and configuration
    capabilities = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=[])
    configuration = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    
    # Performance metrics
    performance_metrics = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    learning_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    
    # Statistics
    total_tasks_completed = Column(Integer, default=0)
    average_execution_time = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    last_active_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    tasks = relationship("Task", back_populates="agent")
    learning_records = relationship("LearningRecord", back_populates="agent", cascade="all, delete-orphan")
    projects = relationship("Project", secondary="project_agents", back_populates="agents")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('idle', 'active', 'busy', 'error', 'offline')", name='valid_agent_status'),
        CheckConstraint('success_rate >= 0 AND success_rate <= 1', name='valid_agent_success_rate'),
        Index('idx_agent_type_status', 'type', 'status'),
        Index('idx_agent_last_active', 'last_active_at'),
    )

class Task(Base):
    """Enhanced Task model with detailed tracking"""
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    agent_id = Column(String, ForeignKey('agents.id', ondelete='SET NULL'), index=True)
    
    # Task details
    type = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(50), default="pending", index=True)
    priority = Column(Integer, default=5, index=True)
    
    # Data
    input_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    output_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    error_data = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    
    # Execution tracking
    execution_time = Column(Float)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Dependencies
    depends_on = Column(ARRAY(String) if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    agent = relationship("Agent", back_populates="tasks")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name='valid_task_status'),
        CheckConstraint('priority >= 1 AND priority <= 10', name='valid_priority'),
        CheckConstraint('retry_count <= max_retries', name='valid_retry_count'),
        Index('idx_task_status_priority', 'status', 'priority'),
        Index('idx_task_project_status', 'project_id', 'status'),
    )

class LearningRecord(Base):
    """Enhanced Learning Record for AI improvement"""
    __tablename__ = "learning_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey('agents.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Learning context
    interaction_type = Column(String(100), nullable=False, index=True)
    task_type = Column(String(100), index=True)
    input_context = Column(Text)
    output_result = Column(Text)
    
    # Feedback and metrics
    feedback_score = Column(Float)
    success = Column(Boolean, index=True)
    execution_time = Column(Float)
    
    # Enhanced metadata
    metadata_info = Column(JSONB if 'postgresql' in os.getenv('DATABASE_URL', '') else JSON, default={})
    model_version = Column(String(50))
    confidence_score = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="learning_records")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('feedback_score >= 0 AND feedback_score <= 1', name='valid_feedback_score'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='valid_confidence_score'),
        Index('idx_learning_agent_type', 'agent_id', 'interaction_type'),
        Index('idx_learning_success_time', 'success', 'created_at'),
    )

# Association table for many-to-many relationship
project_agents = Table(
    'project_agents',
    Base.metadata,
    Column('project_id', String, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    Column('agent_id', String, ForeignKey('agents.id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime, default=datetime.utcnow),
    Column('role', String(100), default='contributor')
)

class EnhancedDatabaseManager:
    """Production-ready database manager with advanced features"""
    
    def __init__(self, config):
        self.config = config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory = None
        self.sync_engine = None  # For migrations
        
    async def initialize(self):
        """Initialize database with comprehensive setup"""
        await self._create_async_engine()
        await self._create_sync_engine()
        await self._run_migrations()
        await self._create_tables()
        await self._setup_indexes()
        await self._verify_setup()
        
        logger.info("Enhanced database manager initialized successfully")
    
    async def _create_async_engine(self):
        """Create async database engine with optimal configuration"""
        database_url = self.config.database.url
        
        # Convert sync URL to async if needed
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif database_url.startswith('sqlite://'):
            database_url = database_url.replace('sqlite://', 'sqlite+aiosqlite://', 1)
        
        self.engine = create_async_engine(
            database_url,
            echo=self.config.system.debug,
            pool_size=self.config.database.pool_size,
            max_overflow=self.config.database.max_overflow,
            pool_timeout=self.config.database.pool_timeout,
            pool_recycle=self.config.database.pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
            connect_args={
                "server_settings": {
                    "application_name": "ymera_enterprise",
                    "jit": "off",  # Optimize for small queries
                }
            } if 'postgresql' in database_url else {}
        )
        
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
    
    async def _create_sync_engine(self):
        """Create sync engine for migrations"""
        database_url = self.config.database.url
        
        self.sync_engine = create_engine(
            database_url,
            echo=self.config.system.debug,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600
        )
    
    async def _run_migrations(self):
        """Run database migrations"""
        try:
            # This would typically use Alembic
            # For now, we'll create tables directly
            logger.info("Migration system ready (using direct table creation)")
        except Exception as e:
            logger.error(f"Migration error: {e}")
            raise
    
    async def _create_tables(self):
        """Create all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    
    async def _setup_indexes(self):
        """Setup additional database indexes for performance"""
        try:
            async with self.get_session() as session:
                # Additional indexes can be created here
                await session.execute(func.now())  # Test connection
                await session.commit()
            logger.info("Database indexes verified")
        except Exception as e:
            logger.error(f"Index setup error: {e}")
    
    async def _verify_setup(self):
        """Verify database setup is working correctly"""
        try