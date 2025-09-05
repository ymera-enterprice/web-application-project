"""
YMERA Enterprise - Database Manager
Production-Ready Database Operations Manager - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import logging
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Type, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
import traceback

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import HTTPException, status
from sqlalchemy import create_engine, text, inspect, MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import BaseModel, Field, validator
import asyncpg
from alembic import command
from alembic.config import Config

# Local imports (alphabetical)
from config.settings import get_settings
from models.base_model import BaseEntity
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from ymera_exceptions import DatabaseError, ValidationError, ConnectionError

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Database connection constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 3600
CONNECTION_POOL_SIZE = 20
MAX_OVERFLOW = 40
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class DatabaseConfig:
    """Configuration dataclass for database settings"""
    database_url: str
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo_sql: bool = False
    ssl_require: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0

@dataclass
class ConnectionStats:
    """Database connection statistics"""
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    failed_connections: int = 0
    average_response_time: float = 0.0
    last_health_check: Optional[datetime] = None

class DatabaseHealthStatus(BaseModel):
    """Database health status schema"""
    status: str = Field(..., description="Overall database health status")
    connection_pool: Dict[str, Any] = Field(..., description="Connection pool status")
    last_query_time: Optional[datetime] = Field(None, description="Last successful query timestamp")
    error_count: int = Field(0, description="Recent error count")
    uptime: float = Field(..., description="Database uptime in seconds")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class QueryResult(BaseModel):
    """Database query result schema"""
    success: bool = Field(..., description="Query execution success")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Query result data")
    row_count: int = Field(0, description="Number of rows affected/returned")
    execution_time: float = Field(..., description="Query execution time in seconds")
    query_id: str = Field(..., description="Unique query identifier")

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class DatabaseConnectionManager:
    """Production-ready database connection manager with pooling and monitoring"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = logger.bind(component="database_manager")
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._connection_stats = ConnectionStats()
        self._health_status = True
        self._startup_time = datetime.utcnow()
        
    async def initialize(self) -> None:
        """Initialize database connections and engine"""
        try:
            await self._create_async_engine()
            await self._setup_session_factory()
            await self._verify_connection()
            await self._setup_monitoring()
            
            self.logger.info(
                "Database manager initialized successfully",
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize database manager", error=str(e))
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    async def _create_async_engine(self) -> None:
        """Create async SQLAlchemy engine with connection pooling"""
        try:
            connect_args = {}
            if self.config.ssl_require:
                connect_args["ssl"] = "require"
            
            self._engine = create_async_engine(
                self.config.database_url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                echo=self.config.echo_sql,
                connect_args=connect_args,
                future=True
            )
            
            self.logger.debug("Async database engine created successfully")
            
        except Exception as e:
            self.logger.error("Failed to create database engine", error=str(e))
            raise
    
    async def _setup_session_factory(self) -> None:
        """Setup async session factory"""
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker
            
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            self.logger.debug("Session factory configured successfully")
            
        except Exception as e:
            self.logger.error("Failed to setup session factory", error=str(e))
            raise
    
    async def _verify_connection(self) -> None:
        """Verify database connection is working"""
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.fetchone()
                
            self.logger.info("Database connection verified successfully")
            
        except Exception as e:
            self.logger.error("Database connection verification failed", error=str(e))
            raise ConnectionError(f"Database connection failed: {str(e)}")
    
    async def _setup_monitoring(self) -> None:
        """Setup database monitoring and health checks"""
        try:
            # Initialize connection stats
            self._connection_stats.last_health_check = datetime.utcnow()
            
            # Start background monitoring task
            asyncio.create_task(self._monitoring_loop())
            
            self.logger.debug("Database monitoring setup completed")
            
        except Exception as e:
            self.logger.error("Failed to setup database monitoring", error=str(e))
            raise
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for database health"""
        while True:
            try:
                await self._update_connection_stats()
                await self._perform_health_check()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _update_connection_stats(self) -> None:
        """Update connection pool statistics"""
        try:
            if self._engine and self._engine.pool:
                pool = self._engine.pool
                self._connection_stats.active_connections = pool.checkedout()
                self._connection_stats.idle_connections = pool.checkedin()
                self._connection_stats.total_connections = pool.size()
                
        except Exception as e:
            self.logger.debug("Could not update connection stats", error=str(e))
    
    async def _perform_health_check(self) -> None:
        """Perform database health check"""
        try:
            start_time = datetime.utcnow()
            
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._connection_stats.average_response_time = response_time
            self._connection_stats.last_health_check = datetime.utcnow()
            self._health_status = True
            
        except Exception as e:
            self._health_status = False
            self._connection_stats.failed_connections += 1
            self.logger.warning("Database health check failed", error=str(e))

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup"""
        if not self._session_factory:
            raise DatabaseError("Database not initialized")
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            self.logger.error("Database session error", error=str(e))
            raise
        finally:
            await session.close()

    @track_performance
    async def execute_query(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None,
        fetch_results: bool = True
    ) -> QueryResult:
        """Execute SQL query with comprehensive error handling and monitoring"""
        query_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.debug(
                "Executing database query",
                query_id=query_id,
                query=query[:100] + "..." if len(query) > 100 else query
            )
            
            async with self.get_session() as session:
                result = await session.execute(text(query), parameters or {})
                
                data = None
                row_count = 0
                
                if fetch_results:
                    rows = await result.fetchall()
                    if rows:
                        # Convert rows to dictionaries
                        columns = result.keys()
                        data = [dict(zip(columns, row)) for row in rows]
                        row_count = len(data)
                else:
                    row_count = result.rowcount
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                self.logger.info(
                    "Query executed successfully",
                    query_id=query_id,
                    execution_time=execution_time,
                    row_count=row_count
                )
                
                return QueryResult(
                    success=True,
                    data=data,
                    row_count=row_count,
                    execution_time=execution_time,
                    query_id=query_id
                )
                
        except SQLAlchemyError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(
                "Database query failed",
                query_id=query_id,
                error=str(e),
                execution_time=execution_time
            )
            
            return QueryResult(
                success=False,
                data=None,
                row_count=0,
                execution_time=execution_time,
                query_id=query_id
            )
        
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(
                "Unexpected error during query execution",
                query_id=query_id,
                error=str(e),
                execution_time=execution_time
            )
            raise DatabaseError(f"Query execution failed: {str(e)}")

    async def create_tables(self, models: List[Type[BaseEntity]]) -> bool:
        """Create database tables for given models"""
        try:
            self.logger.info("Creating database tables", model_count=len(models))
            
            # Import all models to ensure they're registered
            from models.user_models import User, UserSession, UserPermission
            from models.project_models import Project, ProjectMember, ProjectSettings
            from models.agent_models import Agent, AgentState, AgentInteraction
            from models.file_models import FileMetadata, FileVersion, FilePermission
            from models.task_models import Task, TaskExecution, TaskResult
            
            async with self._engine.begin() as conn:
                # Create all tables
                await conn.run_sync(BaseEntity.metadata.create_all)
            
            self.logger.info("Database tables created successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to create database tables", error=str(e))
            raise DatabaseError(f"Table creation failed: {str(e)}")

    async def run_migrations(self, migration_dir: str = "alembic") -> bool:
        """Run database migrations using Alembic"""
        try:
            self.logger.info("Running database migrations", migration_dir=migration_dir)
            
            # Configure Alembic
            alembic_cfg = Config(os.path.join(migration_dir, "alembic.ini"))
            alembic_cfg.set_main_option("script_location", migration_dir)
            alembic_cfg.set_main_option("sqlalchemy.url", self.config.database_url)
            
            # Run migrations
            command.upgrade(alembic_cfg, "head")
            
            self.logger.info("Database migrations completed successfully")
            return True
            
        except Exception as e:
            self.logger.error("Database migration failed", error=str(e))
            raise DatabaseError(f"Migration failed: {str(e)}")

    async def backup_database(self, backup_path: str) -> bool:
        """Create database backup"""
        try:
            self.logger.info("Creating database backup", backup_path=backup_path)
            
            # Implementation depends on database type
            # For PostgreSQL, we could use pg_dump
            backup_command = f"pg_dump {self.config.database_url} > {backup_path}"
            
            import subprocess
            result = subprocess.run(backup_command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Database backup created successfully", backup_path=backup_path)
                return True
            else:
                self.logger.error("Database backup failed", error=result.stderr)
                return False
                
        except Exception as e:
            self.logger.error("Database backup error", error=str(e))
            raise DatabaseError(f"Backup failed: {str(e)}")

    async def get_health_status(self) -> DatabaseHealthStatus:
        """Get comprehensive database health status"""
        try:
            uptime = (datetime.utcnow() - self._startup_time).total_seconds()
            
            return DatabaseHealthStatus(
                status="healthy" if self._health_status else "unhealthy",
                connection_pool={
                    "active": self._connection_stats.active_connections,
                    "idle": self._connection_stats.idle_connections,
                    "total": self._connection_stats.total_connections,
                    "failed": self._connection_stats.failed_connections,
                    "max_size": self.config.pool_size,
                    "max_overflow": self.config.max_overflow
                },
                last_query_time=self._connection_stats.last_health_check,
                error_count=self._connection_stats.failed_connections,
                uptime=uptime
            )
            
        except Exception as e:
            self.logger.error("Failed to get health status", error=str(e))
            raise DatabaseError(f"Health status check failed: {str(e)}")

    async def cleanup(self) -> None:
        """Cleanup database connections and resources"""
        try:
            if self._engine:
                await self._engine.dispose()
                self.logger.info("Database connections cleaned up successfully")
                
        except Exception as e:
            self.logger.error("Error during database cleanup", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def create_database_manager(database_url: Optional[str] = None) -> DatabaseConnectionManager:
    """Create and initialize database manager"""
    if not database_url:
        database_url = settings.DATABASE_URL
    
    config = DatabaseConfig(
        database_url=database_url,
        pool_size=getattr(settings, 'DB_POOL_SIZE', 20),
        max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 40),
        pool_timeout=getattr(settings, 'DB_POOL_TIMEOUT', 30),
        pool_recycle=getattr(settings, 'DB_POOL_RECYCLE', 3600),
        echo_sql=getattr(settings, 'DB_ECHO_SQL', False),
        ssl_require=getattr(settings, 'DB_SSL_REQUIRE', True)
    )
    
    manager = DatabaseConnectionManager(config)
    await manager.initialize()
    
    return manager

async def health_check() -> Dict[str, Any]:
    """Database manager health check endpoint"""
    try:
        manager = await create_database_manager()
        health_status = await manager.get_health_status()
        await manager.cleanup()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "database_manager",
            "version": "4.0",
            "database": health_status.dict()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "database_manager",
            "version": "4.0",
            "error": str(e)
        }

def validate_configuration(config: Dict[str, Any]) -> bool:
    """Validate database configuration"""
    required_fields = ["database_url", "pool_size", "max_overflow"]
    return all(field in config for field in required_fields)

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

# Global database manager instance
_database_manager: Optional[DatabaseConnectionManager] = None

async def get_database_manager() -> DatabaseConnectionManager:
    """Get or create global database manager instance"""
    global _database_manager
    
    if _database_manager is None:
        _database_manager = await create_database_manager()
    
    return _database_manager

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    manager = await get_database_manager()
    async with manager.get_session() as session:
        yield session

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "DatabaseConnectionManager",
    "DatabaseConfig",
    "DatabaseHealthStatus",
    "QueryResult",
    "ConnectionStats",
    "create_database_manager",
    "get_database_manager",
    "get_db_session",
    "health_check"
]