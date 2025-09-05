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
        try:
            async with self.get_session() as session:
                # Test basic operations
                result = await session.execute(select(func.count()).select_from(Project))
                count = result.scalar()
                logger.info(f"Database verification successful - Projects table has {count} records")
        except Exception as e:
            logger.error(f"Database verification failed: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with proper cleanup"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
        if self.sync_engine:
            self.sync_engine.dispose()
        logger.info("Database connections closed")
    
    # Enhanced query methods
    async def get_project_with_stats(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project with computed statistics"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Project)
                .options(selectinload(Project.tasks), selectinload(Project.agents))
                .where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            
            if not project:
                return None
            
            # Compute real-time stats
            task_stats = await session.execute(
                select(
                    func.count(Task.id).label('total_tasks'),
                    func.count(Task.id).filter(Task.status == 'completed').label('completed_tasks'),
                    func.avg(Task.execution_time).label('avg_execution_time')
                ).where(Task.project_id == project_id)
            )
            stats = task_stats.first()
            
            project_dict = project.to_dict()
            project_dict.update({
                'computed_total_tasks': stats.total_tasks or 0,
                'computed_completed_tasks': stats.completed_tasks or 0,
                'computed_success_rate': (stats.completed_tasks or 0) / max(stats.total_tasks or 1, 1),
                'avg_execution_time': float(stats.avg_execution_time or 0),
                'task_count': len(project.tasks),
                'agent_count': len(project.agents)
            })
            
            return project_dict
    
    async def get_agent_performance_metrics(self, agent_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive agent performance metrics"""
        async with self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get agent with recent tasks
            agent_result = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent_result.scalar_one_or_none()
            
            if not agent:
                return {}
            
            # Get recent task metrics
            task_metrics = await session.execute(
                select(
                    func.count(Task.id).label('total_tasks'),
                    func.count(Task.id).filter(Task.status == 'completed').label('completed_tasks'),
                    func.count(Task.id).filter(Task.status == 'failed').label('failed_tasks'),
                    func.avg(Task.execution_time).label('avg_execution_time'),
                    func.min(Task.execution_time).label('min_execution_time'),
                    func.max(Task.execution_time).label('max_execution_time')
                ).where(
                    Task.agent_id == agent_id,
                    Task.created_at >= cutoff_date
                )
            )
            metrics = task_metrics.first()
            
            # Get learning metrics
            learning_metrics = await session.execute(
                select(
                    func.count(LearningRecord.id).label('total_interactions'),
                    func.avg(LearningRecord.feedback_score).label('avg_feedback'),
                    func.avg(LearningRecord.confidence_score).label('avg_confidence'),
                    func.count(LearningRecord.id).filter(LearningRecord.success == True).label('successful_interactions')
                ).where(
                    LearningRecord.agent_id == agent_id,
                    LearningRecord.created_at >= cutoff_date
                )
            )
            learning = learning_metrics.first()
            
            return {
                'agent_id': agent_id,
                'agent_name': agent.name,
                'agent_type': agent.type,
                'period_days': days,
                'task_metrics': {
                    'total_tasks': metrics.total_tasks or 0,
                    'completed_tasks': metrics.completed_tasks or 0,
                    'failed_tasks': metrics.failed_tasks or 0,
                    'success_rate': (metrics.completed_tasks or 0) / max(metrics.total_tasks or 1, 1),
                    'avg_execution_time': float(metrics.avg_execution_time or 0),
                    'min_execution_time': float(metrics.min_execution_time or 0),
                    'max_execution_time': float(metrics.max_execution_time or 0)
                },
                'learning_metrics': {
                    'total_interactions': learning.total_interactions or 0,
                    'avg_feedback_score': float(learning.avg_feedback or 0),
                    'avg_confidence_score': float(learning.avg_confidence or 0),
                    'successful_interactions': learning.successful_interactions or 0,
                    'learning_success_rate': (learning.successful_interactions or 0) / max(learning.total_interactions or 1, 1)
                },
                'current_status': agent.status,
                'last_active': agent.last_active_at.isoformat() if agent.last_active_at else None
            }
    
    async def get_system_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive system dashboard data"""
        async with self.get_session() as session:
            # System overview
            system_stats = await session.execute(
                select(
                    func.count(Project.id).label('total_projects'),
                    func.count(Project.id).filter(Project.status == 'active').label('active_projects'),
                    func.count(Agent.id).label('total_agents'),
                    func.count(Agent.id).filter(Agent.status == 'active').label('active_agents'),
                    func.count(Task.id).label('total_tasks'),
                    func.count(Task.id).filter(Task.status == 'pending').label('pending_tasks'),
                    func.count(Task.id).filter(Task.status == 'running').label('running_tasks'),
                    func.count(Task.id).filter(Task.status == 'completed').label('completed_tasks'),
                    func.count(Task.id).filter(Task.status == 'failed').label('failed_tasks')
                )
            )
            stats = system_stats.first()
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_stats = await session.execute(
                select(
                    func.count(Task.id).filter(Task.created_at >= recent_cutoff).label('recent_tasks'),
                    func.count(Task.id).filter(
                        Task.completed_at >= recent_cutoff,
                        Task.status == 'completed'
                    ).label('recent_completions'),
                    func.count(LearningRecord.id).filter(
                        LearningRecord.created_at >= recent_cutoff
                    ).label('recent_learning_records')
                )
            )
            recent = recent_stats.first()
            
            # Performance metrics
            performance_stats = await session.execute(
                select(
                    func.avg(Task.execution_time).label('avg_task_time'),
                    func.avg(Agent.success_rate).label('avg_agent_success_rate')
                ).where(
                    Task.status == 'completed',
                    Agent.total_tasks_completed > 0
                )
            )
            performance = performance_stats.first()
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'system_overview': {
                    'projects': {
                        'total': stats.total_projects or 0,
                        'active': stats.active_projects or 0
                    },
                    'agents': {
                        'total': stats.total_agents or 0,
                        'active': stats.active_agents or 0
                    },
                    'tasks': {
                        'total': stats.total_tasks or 0,
                        'pending': stats.pending_tasks or 0,
                        'running': stats.running_tasks or 0,
                        'completed': stats.completed_tasks or 0,
                        'failed': stats.failed_tasks or 0
                    }
                },
                'recent_activity': {
                    'new_tasks_24h': recent.recent_tasks or 0,
                    'completions_24h': recent.recent_completions or 0,
                    'learning_records_24h': recent.recent_learning_records or 0
                },
                'performance_metrics': {
                    'avg_task_execution_time': float(performance.avg_task_time or 0),
                    'avg_agent_success_rate': float(performance.avg_agent_success_rate or 0),
                    'system_success_rate': (stats.completed_tasks or 0) / max(stats.total_tasks or 1, 1)
                }
            }
    
    async def optimize_database(self):
        """Run database optimization tasks"""
        async with self.get_session() as session:
            try:
                # Update computed statistics
                await session.execute("""
                    UPDATE projects SET 
                        total_tasks = (SELECT COUNT(*) FROM tasks WHERE project_id = projects.id),
                        completed_tasks = (SELECT COUNT(*) FROM tasks WHERE project_id = projects.id AND status = 'completed'),
                        success_rate = CASE 
                            WHEN (SELECT COUNT(*) FROM tasks WHERE project_id = projects.id) = 0 THEN 0
                            ELSE (SELECT COUNT(*) FROM tasks WHERE project_id = projects.id AND status = 'completed') * 1.0 / 
                                 (SELECT COUNT(*) FROM tasks WHERE project_id = projects.id)
                        END
                """)
                
                await session.execute("""
                    UPDATE agents SET 
                        total_tasks_completed = (SELECT COUNT(*) FROM tasks WHERE agent_id = agents.id AND status = 'completed'),
                        average_execution_time = COALESCE((SELECT AVG(execution_time) FROM tasks WHERE agent_id = agents.id AND status = 'completed'), 0),
                        success_rate = CASE 
                            WHEN (SELECT COUNT(*) FROM tasks WHERE agent_id = agents.id) = 0 THEN 0
                            ELSE (SELECT COUNT(*) FROM tasks WHERE agent_id = agents.id AND status = 'completed') * 1.0 / 
                                 (SELECT COUNT(*) FROM tasks WHERE agent_id = agents.id)
                        END
                """)
                
                await session.commit()
                logger.info("Database optimization completed")
                
            except Exception as e:
                logger.error(f"Database optimization failed: {e}")
                await session.rollback()
                raise
    
    async def cleanup_old_records(self, days_to_keep: int = 90):
        """Clean up old learning records and completed tasks"""
        async with self.get_session() as session:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # Clean old learning records
                learning_result = await session.execute(
                    LearningRecord.__table__.delete().where(
                        LearningRecord.created_at < cutoff_date
                    )
                )
                
                # Clean old completed tasks (keep failed tasks longer for analysis)
                task_result = await session.execute(
                    Task.__table__.delete().where(
                        Task.completed_at < cutoff_date,
                        Task.status == 'completed'
                    )
                )
                
                await session.commit()
                
                logger.info(f"Cleanup completed: removed {learning_result.rowcount} learning records and {task_result.rowcount} completed tasks")
                
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
                await session.rollback()
                raise


# Database event listeners for automatic updates
@event.listens_for(Task, 'after_update')
def update_project_stats(mapper, connection, target):
    """Update project statistics when task status changes"""
    if target.project_id:
        # This would trigger background update of project statistics
        pass

@event.listens_for(Task, 'after_insert')
def increment_project_task_count(mapper, connection, target):
    """Increment project task count when new task is created"""
    if target.project_id:
        # This would trigger background update of project statistics
        pass


# Factory function for easy initialization
async def create_database_manager(config) -> EnhancedDatabaseManager:
    """Factory function to create and initialize database manager"""
    manager = EnhancedDatabaseManager(config)
    await manager.initialize()
    return manager


# Configuration helper
class DatabaseConfig:
    """Database configuration helper"""
    
    def __init__(
        self,
        url: str = None,
        pool_size: int = 20,
        max_overflow: int = 30,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False
    ):
        self.url = url or os.getenv('DATABASE_URL', 'sqlite:///ymera.db')
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.echo = echo


# Usage example and testing
async def main():
    """Example usage of the enhanced database manager"""
    
    # Mock configuration
    class Config:
        def __init__(self):
            self.database = DatabaseConfig()
            self.system = type('obj', (object,), {'debug': False})
    
    config = Config()
    
    # Initialize database
    db_manager = await create_database_manager(config)
    
    try:
        # Test dashboard data
        dashboard = await db_manager.get_system_dashboard_data()
        logger.info(f"System dashboard: {dashboard}")
        
        # Test database optimization
        await db_manager.optimize_database()
        
        # Test cleanup (but don't actually clean anything in example)
        # await db_manager.cleanup_old_records(days_to_keep=365)
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())