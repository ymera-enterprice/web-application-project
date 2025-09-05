"""
YMERA Core Database Manager - Production Ready
Enhanced PostgreSQL/SQLite database management with connection pooling and migrations
"""

import asyncio
import asyncpg
import sqlite3
import aiosqlite
from typing import Generator, Optional, Dict, Any, List
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import os
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, DateTime, Text, Boolean, JSON, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
import json

# SQLAlchemy Base
Base = declarative_base()

class DatabaseManager:
    """Production-ready database manager with connection pooling and migrations"""
    
    def __init__(self, database_url: str, pool_size: int = 10, max_overflow: int = 20):
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.engine = None
        self.async_session_maker = None
        self.metadata = MetaData()
        self.logger = logging.getLogger(__name__)
        self._is_initialized = False
        
        # Determine database type
        self.db_type = self._determine_db_type()
        
    def _determine_db_type(self) -> str:
        """Determine database type from URL"""
        if self.database_url.startswith('postgresql'):
            return 'postgresql'
        elif self.database_url.startswith('sqlite'):
            return 'sqlite'
        else:
            return 'sqlite'  # Default fallback
    
    async def initialize(self):
        """Initialize database connections and setup"""
        try:
            if self.db_type == 'postgresql':
                self.engine = create_async_engine(
                    self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_pre_ping=True,
                    echo=False
                )
            else:
                # SQLite for development/testing
                db_path = self.database_url.replace('sqlite:///', '')
                if db_path == ':memory:':
                    db_path = 'ymera.db'
                
                self.engine = create_async_engine(
                    f"sqlite+aiosqlite:///{db_path}",
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                    echo=False
                )
            
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self._is_initialized = True
            self.logger.info(f"Database manager initialized with {self.db_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    async def create_tables(self):
        """Create all database tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self.logger.info("Database tables created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create tables: {str(e)}")
            raise
    
    @asynccontextmanager
    async def get_session(self):
        """Get database session with automatic cleanup"""
        if not self._is_initialized:
            raise RuntimeError("Database manager not initialized")
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute raw SQL query"""
        async with self.get_session() as session:
            result = await session.execute(query, params or {})
            return [dict(row) for row in result.fetchall()]
    
    async def health_check(self) -> bool:
        """Check database connection health"""
        try:
            async with self.get_session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {str(e)}")
            return False
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            self.logger.info("Database connections closed")

# Database Models
class Project(Base):
    __tablename__ = 'projects'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    repository_url = Column(String)
    status = Column(String, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json = Column(JSON, default=dict)

class Agent(Base):
    __tablename__ = 'agents'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, default='inactive')
    capabilities = Column(JSON, default=list)
    performance_metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    config = Column(JSON, default=dict)

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey('projects.id'))
    agent_id = Column(String, ForeignKey('agents.id'))
    type = Column(String, nullable=False)
    status = Column(String, default='pending')
    priority = Column(Integer, default=1)
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    execution_time = Column(Integer)  # seconds

class LearningRecord(Base):
    __tablename__ = 'learning_records'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'))
    task_id = Column(String, ForeignKey('tasks.id'))
    learning_type = Column(String, nullable=False)  # feedback, pattern, improvement
    content = Column(JSON, nullable=False)
    effectiveness_score = Column(Integer, default=0)
    applied = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeBase(Base):
    __tablename__ = 'knowledge_base'
    
    id = Column(String, primary_key=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    embedding = Column(JSON)  # Vector embedding
    source = Column(String)
    confidence_score = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    permissions = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class SystemMetrics(Base):
    __tablename__ = 'system_metrics'
    
    id = Column(String, primary_key=True)
    metric_type = Column(String, nullable=False)
    metric_name = Column(String, nullable=False)
    value = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tags = Column(JSON, default=dict)

# Database dependency for FastAPI
async def get_db_session():
    """FastAPI dependency for database sessions"""
    from ymera_main_enhanced import system
    
    if not system.db_manager:
        raise RuntimeError("Database manager not initialized")
    
    async with system.db_manager.get_session() as session:
        yield session

def get_db() -> Generator:
    """Synchronous database dependency (for compatibility)"""
    import asyncio
    from ymera_main_enhanced import system
    
    # This is a bridge for sync contexts
    loop = asyncio.get_event_loop()
    session_context = system.db_manager.get_session()
    session = loop.run_until_complete(session_context.__aenter__())
    
    try:
        yield session
    finally:
        loop.run_until_complete(session_context.__aexit__(None, None, None))
