"""
YMERA Enterprise - Database Connection Manager
Production-Ready Async Database Connections - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
from dataclasses import dataclass, field

# Third-party imports (alphabetical)
import aioredis
import structlog
from sqlalchemy import text, MetaData, Table, Column, Integer, String, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    AsyncEngine, 
    create_async_engine, 
    async_sessionmaker
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.database.connection")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Connection pool settings
DEFAULT_POOL_SIZE = 20
DEFAULT_MAX_OVERFLOW = 40
DEFAULT_POOL_TIMEOUT = 30
DEFAULT_POOL_RECYCLE = 3600

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1.0
CONNECTION_TIMEOUT = 30

# Health check settings
HEALTH_CHECK_INTERVAL = 60
HEALTH_CHECK_QUERY = "SELECT 1"

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATABASE MODELS & SCHEMAS
# ===============================================================================

class Base(DeclarativeBase):
    """Base class for all database models"""
    pass

@dataclass
class DatabaseConfig:
    """Configuration for database connections"""
    database_url: str
    pool_size: int = DEFAULT_POOL_SIZE
    max_overflow: int = DEFAULT_MAX_OVERFLOW
    pool_timeout: int = DEFAULT_POOL_TIMEOUT
    pool_recycle: int = DEFAULT_POOL_RECYCLE
    echo_sql: bool = False
    ssl_require: bool = True
    connect_timeout: int = CONNECTION_TIMEOUT

@dataclass
class ConnectionMetrics:
    """Metrics for database connection monitoring"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    connection_errors: List[str] = field(default_factory=list)
    last_health_check: Optional[datetime] = None
    average_response_time: float = 0.0

# ===============================================================================
# LEARNING SYSTEM DATABASE TABLES
# ===============================================================================

# Agent Learning Tables
agent_learning_data = Table(
    'agent_learning_data',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('agent_id', String(100), nullable=False, index=True),
    Column('learning_cycle_id', String(36), nullable=False, index=True),
    Column('experience_data', JSON, nullable=False),
    Column('knowledge_extracted', JSON, nullable=False),
    Column('confidence_score', Integer, nullable=False),
    Column('learning_timestamp', DateTime, nullable=False, default=datetime.utcnow),
    Column('source_type', String(50), nullable=False),
    Column('processing_time_ms', Integer, nullable=False),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('updated_at', DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    Index('idx_agent_learning_timestamp', 'agent_id', 'learning_timestamp'),
    Index('idx_learning_cycle_agent', 'learning_cycle_id', 'agent_id')
)

# Knowledge Graph Tables
knowledge_graph_nodes = Table(
    'knowledge_graph_nodes',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('node_type', String(50), nullable=False, index=True),
    Column('node_data', JSON, nullable=False),
    Column('confidence_score', Integer, nullable=False),
    Column('source_agent_id', String(100), nullable=False, index=True),
    Column('creation_timestamp', DateTime, nullable=False, default=datetime.utcnow),
    Column('last_accessed', DateTime, nullable=False, default=datetime.utcnow),
    Column('access_count', Integer, nullable=False, default=0),
    Column('validation_status', String(20), nullable=False, default='pending'),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('updated_at', DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    Index('idx_knowledge_type_confidence', 'node_type', 'confidence_score'),
    Index('idx_knowledge_source_timestamp', 'source_agent_id', 'creation_timestamp')
)

knowledge_graph_edges = Table(
    'knowledge_graph_edges',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('source_node_id', String(36), nullable=False, index=True),
    Column('target_node_id', String(36), nullable=False, index=True),
    Column('relationship_type', String(50), nullable=False, index=True),
    Column('relationship_data', JSON),
    Column('strength_score', Integer, nullable=False),
    Column('created_by_agent', String(100), nullable=False),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('updated_at', DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    Index('idx_edge_source_target', 'source_node_id', 'target_node_id'),
    Index('idx_edge_relationship_strength', 'relationship_type', 'strength_score')
)

# Inter-Agent Knowledge Transfer Tables
knowledge_transfer_logs = Table(
    'knowledge_transfer_logs',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('source_agent_id', String(100), nullable=False, index=True),
    Column('target_agent_id', String(100), nullable=False, index=True),
    Column('knowledge_item_id', String(36), nullable=False),
    Column('transfer_type', String(50), nullable=False),
    Column('transfer_data', JSON, nullable=False),
    Column('success_status', Boolean, nullable=False),
    Column('transfer_timestamp', DateTime, nullable=False, default=datetime.utcnow),
    Column('processing_time_ms', Integer, nullable=False),
    Column('collaboration_score', Integer),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Index('idx_transfer_source_target_time', 'source_agent_id', 'target_agent_id', 'transfer_timestamp'),
    Index('idx_transfer_success_timestamp', 'success_status', 'transfer_timestamp')
)

# Pattern Discovery Tables
behavioral_patterns = Table(
    'behavioral_patterns',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('pattern_type', String(50), nullable=False, index=True),
    Column('pattern_data', JSON, nullable=False),
    Column('discovery_agent_id', String(100), nullable=False),
    Column('significance_score', Integer, nullable=False),
    Column('usage_count', Integer, nullable=False, default=0),
    Column('last_applied', DateTime),
    Column('discovery_timestamp', DateTime, nullable=False, default=datetime.utcnow),
    Column('validation_status', String(20), nullable=False, default='discovered'),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('updated_at', DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    Index('idx_pattern_type_significance', 'pattern_type', 'significance_score'),
    Index('idx_pattern_discovery_timestamp', 'discovery_timestamp'),
    Index('idx_pattern_usage_validation', 'usage_count', 'validation_status')
)

# External Learning Integration Tables
external_knowledge_sources = Table(
    'external_knowledge_sources',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('source_type', String(50), nullable=False, index=True),
    Column('source_identifier', String(255), nullable=False),
    Column('knowledge_data', JSON, nullable=False),
    Column('integration_timestamp', DateTime, nullable=False, default=datetime.utcnow),
    Column('processing_agent_id', String(100), nullable=False),
    Column('validation_status', String(20), nullable=False, default='pending'),
    Column('confidence_score', Integer, nullable=False),
    Column('success_rate', Integer),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('updated_at', DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
    Index('idx_external_source_type_timestamp', 'source_type', 'integration_timestamp'),
    Index('idx_external_validation_confidence', 'validation_status', 'confidence_score')
)

# Memory Consolidation Tables
memory_consolidation_sessions = Table(
    'memory_consolidation_sessions',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('session_timestamp', DateTime, nullable=False, default=datetime.utcnow, index=True),
    Column('consolidation_type', String(50), nullable=False),
    Column('processed_items_count', Integer, nullable=False),
    Column('retained_items_count', Integer, nullable=False),
    Column('removed_items_count', Integer, nullable=False),
    Column('optimization_metrics', JSON, nullable=False),
    Column('processing_duration_ms', Integer, nullable=False),
    Column('memory_usage_before_mb', Integer),
    Column('memory_usage_after_mb', Integer),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Index('idx_consolidation_timestamp_type', 'session_timestamp', 'consolidation_type')
)

# Learning Metrics and Analytics Tables
learning_metrics = Table(
    'learning_metrics',
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('metric_timestamp', DateTime, nullable=False, default=datetime.utcnow, index=True),
    Column('metric_type', String(50), nullable=False, index=True),
    Column('agent_id', String(100), index=True),
    Column('metric_value', Integer, nullable=False),
    Column('metric_data', JSON),
    Column('measurement_period_start', DateTime, nullable=False),
    Column('measurement_period_end', DateTime, nullable=False),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Index('idx_metrics_timestamp_type_agent', 'metric_timestamp', 'metric_type', 'agent_id'),
    Index('idx_metrics_period', 'measurement_period_start', 'measurement_period_end')
)

# ===============================================================================
# CORE DATABASE CONNECTION MANAGER
# ===============================================================================

class DatabaseManager:
    """Production-ready async database connection manager"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or self._load_default_config()
        self.logger = logger.bind(manager="DatabaseManager")
        
        # Connection components
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        
        # Monitoring
        self._metrics = ConnectionMetrics()
        self._health_check_task: Optional[asyncio.Task] = None
        self._last_health_check = None
        
        # State management
        self._initialized = False
        self._shutdown = False
    
    def _load_default_config(self) -> DatabaseConfig:
        """Load default database configuration from settings"""
        return DatabaseConfig(
            database_url=settings.DATABASE_URL,
            pool_size=getattr(settings, 'DB_POOL_SIZE', DEFAULT_POOL_SIZE),
            max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', DEFAULT_MAX_OVERFLOW),
            pool_timeout=getattr(settings, 'DB_POOL_TIMEOUT', DEFAULT_POOL_TIMEOUT),
            pool_recycle=getattr(settings, 'DB_POOL_RECYCLE', DEFAULT_POOL_RECYCLE),
            echo_sql=getattr(settings, 'DB_ECHO_SQL', False),
            ssl_require=getattr(settings, 'DB_SSL_REQUIRE', True),
            connect_timeout=getattr(settings, 'DB_CONNECT_TIMEOUT', CONNECTION_TIMEOUT)
        )
    
    async def initialize(self) -> None:
        """Initialize database connection manager"""
        if self._initialized:
            self.logger.warning("Database manager already initialized")
            return
        
        try:
            self.logger.info("Initializing database connection manager")
            
            # Create async engine
            self._engine = await self._create_async_engine()
            
            # Create session factory
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            # Test initial connection
            await self._test_connection()
            
            # Start health monitoring
            self._health_check_task = asyncio.create_task(self._health_monitor())
            
            self._initialized = True
            self.logger.info("Database connection manager initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize database manager", error=str(e))
            await self.cleanup()
            raise ConnectionError(f"Database initialization failed: {str(e)}")
    
    async def _create_async_engine(self) -> AsyncEngine:
        """Create and configure async database engine"""
        try:
            # Connection arguments
            connect_args = {
                "connect_timeout": self.config.connect_timeout,
                "command_timeout": 60,
                "server_settings": {
                    "application_name": "YMERA_Learning_System",
                    "jit": "off"
                }
            }
            
            if self.config.ssl_require:
                connect_args["ssl"] = "require"
            
            # Create engine with connection pooling
            engine = create_async_engine(
                self.config.database_url,
                echo=self.config.echo_sql,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=True,
                connect_args=connect_args,
                isolation_level="READ_COMMITTED"
            )
            
            self.logger.info(
                "Created async database engine",
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow
            )
            
            return engine
            
        except Exception as e:
            self.logger.error("Failed to create database engine", error=str(e))
            raise
    
    async def _test_connection(self) -> None:
        """Test database connectivity"""
        start_time = time.time()
        
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text(HEALTH_CHECK_QUERY))
                await result.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            self._metrics.average_response_time = response_time
            self._metrics.last_health_check = datetime.utcnow()
            
            self.logger.info(
                "Database connection test successful",
                response_time_ms=response_time
            )
            
        except Exception as e:
            self._metrics.failed_connections += 1
            self._metrics.connection_errors.append(str(e))
            
            self.logger.error("Database connection test failed", error=str(e))
            raise
    
    async def _health_monitor(self) -> None:
        """Background task for database health monitoring"""
        while not self._shutdown:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
                if self._shutdown:
                    break
                
                # Perform health check
                await self._perform_health_check()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Health monitor error", error=str(e))
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive database health check"""
        start_time = time.time()
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        try:
            # Test basic connectivity
            async with self._engine.begin() as conn:
                result = await conn.execute(text(HEALTH_CHECK_QUERY))
                await result.fetchone()
            
            health_data["checks"]["connectivity"] = "healthy"
            
            # Check connection pool status
            pool_status = await self._get_pool_status()
            health_data["checks"]["connection_pool"] = pool_status
            
            # Update metrics
            response_time = (time.time() - start_time) * 1000
            self._metrics.average_response_time = response_time
            self._metrics.last_health_check = datetime.utcnow()
            
            self.logger.debug("Database health check completed", response_time_ms=response_time)
            
        except Exception as e:
            health_data["status"] = "unhealthy"
            health_data["checks"]["connectivity"] = f"failed: {str(e)}"
            
            self._metrics.failed_connections += 1
            self._metrics.connection_errors.append(str(e))
            
            self.logger.error("Database health check failed", error=str(e))
        
        return health_data
    
    async def _get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status"""
        pool = self._engine.pool
        
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session with automatic cleanup.
        
        Yields:
            AsyncSession: Database session
            
        Raises:
            ConnectionError: When database is not available
        """
        if not self._initialized:
            raise ConnectionError("Database manager not initialized")
        
        session = self._session_factory()
        
        try:
            self.logger.debug("Database session created")
            yield session
            
        except Exception as e:
            self.logger.error("Database session error", error=str(e))
            await session.rollback()
            raise
            
        finally:
            await session.close()
            self.logger.debug("Database session closed")
    
    @track_performance
    async def execute_query(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute raw SQL query with parameters.
        
        Args:
            query: SQL query string
            parameters: Query parameters
            
        Returns:
            List of result dictionaries
        """
        async with self.get_session() as session:
            try:
                result = await session.execute(text(query), parameters or {})
                
                # Convert to list of dictionaries
                columns = result.keys()
                rows = result.fetchall()
                
                return [dict(zip(columns, row)) for row in rows]
                
            except SQLAlchemyError as e:
                self.logger.error("Query execution failed", query=query, error=str(e))
                raise
    
    async def get_connection_metrics(self) -> ConnectionMetrics:
        """Get current connection metrics"""
        # Update current pool metrics
        if self._engine:
            pool_status = await self._get_pool_status()
            self._metrics.active_connections = pool_status["checked_out"]
            self._metrics.idle_connections = pool_status["checked_in"]
            self._metrics.total_connections = pool_status["size"]
        
        return self._metrics
    
    async def cleanup(self) -> None:
        """Clean up database resources"""
        self._shutdown = True
        
        try:
            # Cancel health monitoring
            if self._health_check_task and not self._health_check_task.done():
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Close database engine
            if self._engine:
                await self._engine.dispose()
                self.logger.info("Database engine disposed")
            
            self._initialized = False
            self.logger.info("Database manager cleanup completed")
            
        except Exception as e:
            self.logger.error("Database cleanup error", error=str(e))

# ===============================================================================
# GLOBAL DATABASE MANAGER INSTANCE
# ===============================================================================

_db_manager: Optional[DatabaseManager] = None

async def get_database_manager() -> DatabaseManager:
    """Get or create global database manager instance"""
    global _db_manager
    
    if _db_manager is None or not _db_manager._initialized:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    
    return _db_manager

# ===============================================================================
# DATABASE SESSION DEPENDENCY
# ===============================================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Yields:
        AsyncSession: Database session
    """
    db_manager = await get_database_manager()
    
    async with db_manager.get_session() as session:
        yield session

# ===============================================================================
# ENGINE ACCESS FUNCTIONS
# ===============================================================================

async def get_async_engine() -> AsyncEngine:
    """Get the async database engine"""
    db_manager = await get_database_manager()
    
    if not db_manager._engine:
        raise ConnectionError("Database engine not available")
    
    return db_manager._engine

# ===============================================================================
# TABLE MANAGEMENT FUNCTIONS
# ===============================================================================

async def create_all_tables() -> None:
    """Create all database tables"""
    try:
        logger.info("Creating all database tables")
        
        engine = await get_async_engine()
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("All database tables created successfully")
        
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise

async def drop_all_tables() -> None:
    """Drop all database tables (use with caution)"""
    try:
        logger.warning("Dropping all database tables")
        
        engine = await get_async_engine()
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.warning("All database tables dropped")
        
    except Exception as e:
        logger.error("Failed to drop database tables", error=str(e))
        raise

# ===============================================================================
# HEALTH CHECK FUNCTIONS
# ===============================================================================

async def check_database_health() -> Dict[str, Any]:
    """
    Comprehensive database health check.
    
    Returns:
        Dict containing health status and metrics
    """
    try:
        db_manager = await get_database_manager()
        health_data = await db_manager._perform_health_check()
        
        # Add connection metrics
        metrics = await db_manager.get_connection_metrics()
        health_data["metrics"] = {
            "total_connections": metrics.total_connections,
            "active_connections": metrics.active_connections,
            "idle_connections": metrics.idle_connections,
            "failed_connections": metrics.failed_connections,
            "average_response_time_ms": metrics.average_response_time,
            "last_health_check": metrics.last_health_check.isoformat() if metrics.last_health_check else None
        }
        
        return health_data
        
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def execute_raw_query(
    query: str, 
    parameters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute raw SQL query.
    
    Args:
        query: SQL query string
        parameters: Query parameters
        
    Returns:
        List of result dictionaries
    """
    db_manager = await get_database_manager()
    return await db_manager.execute_query(query, parameters)

async def get_table_info(table_name: str) -> Dict[str, Any]:
    """
    Get information about a specific table.
    
    Args:
        table_name: Name of the table
        
    Returns:
        Dict containing table information
    """
    query = """
    SELECT 
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns 
    WHERE table_name = :table_name
    ORDER BY ordinal_position
    """
    
    result = await execute_raw_query(query, {"table_name": table_name})
    
    return {
        "table_name": table_name,
        "columns": result,
        "column_count": len(result)
    }