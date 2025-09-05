"""
YMERA Enterprise - Database Configuration
Production-Ready Database Connection Management - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Third-party imports (alphabetical)
import structlog
from sqlalchemy import MetaData, create_engine, event, pool
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    AsyncEngine, 
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.engine.events import PoolEvents
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError, TimeoutError
from alembic import command
from alembic.config import Config as AlembicConfig

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.database")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Connection constants
DEFAULT_POOL_SIZE = 20
DEFAULT_MAX_OVERFLOW = 40
DEFAULT_POOL_TIMEOUT = 30
DEFAULT_POOL_RECYCLE = 3600
DEFAULT_POOL_PRE_PING = True

# Retry constants
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0
CONNECTION_TIMEOUT = 30

# Database metadata
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)

# Base model for all database models
Base = declarative_base(metadata=metadata)

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class DatabaseConfig:
    """
    Comprehensive database configuration with validation and optimization.
    
    This class manages all database connection parameters, connection pooling,
    and performance optimization settings for production environments.
    """
    
    # Connection settings
    url: str
    echo: bool = False
    echo_pool: bool = False
    
    # Pool settings
    pool_size: int = DEFAULT_POOL_SIZE
    max_overflow: int = DEFAULT_MAX_OVERFLOW
    pool_timeout: int = DEFAULT_POOL_TIMEOUT
    pool_recycle: int = DEFAULT_POOL_RECYCLE
    pool_pre_ping: bool = DEFAULT_POOL_PRE_PING
    
    # Performance settings
    query_timeout: int = 30
    connection_timeout: int = CONNECTION_TIMEOUT
    
    # Retry settings
    max_retry_attempts: int = MAX_RETRY_ATTEMPTS
    retry_delay: float = RETRY_DELAY
    
    # Additional options
    extra_options: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_url()
        self._validate_pool_settings()
        self._optimize_for_environment()
    
    def _validate_url(self) -> None:
        """Validate database URL format"""
        if not self.url:
            raise ValueError("Database URL cannot be empty")
        
        try:
            parsed = urlparse(self.url)
            if not parsed.scheme:
                raise ValueError("Database URL must include scheme (postgresql://, sqlite://, etc.)")
            
            self.database_type = parsed.scheme.split('+')[0]
            self.host = parsed.hostname
            self.port = parsed.port
            self.database = parsed.path.lstrip('/')
            self.username = parsed.username
            
        except Exception as e:
            raise ValueError(f"Invalid database URL format: {e}")
    
    def _validate_pool_settings(self) -> None:
        """Validate connection pool settings"""
        if self.pool_size < 1:
            raise ValueError("Pool size must be at least 1")
        
        if self.max_overflow < 0:
            raise ValueError("Max overflow cannot be negative")
        
        if self.pool_timeout < 1:
            raise ValueError("Pool timeout must be at least 1 second")
        
        if self.pool_recycle < 60:
            logger.warning("Pool recycle time is very low, may impact performance")
    
    def _optimize_for_environment(self) -> None:
        """Optimize settings based on database type and environment"""
        # SQLite optimizations
        if self.database_type == "sqlite":
            self.pool_size = 1
            self.max_overflow = 0
            self.extra_options.update({
                "check_same_thread": False,
                "isolation_level": None
            })
        
        # PostgreSQL optimizations
        elif self.database_type == "postgresql":
            self.extra_options.update({
                "server_side_cursors": True,
                "use_native_unicode": True
            })
        
        # MySQL optimizations
        elif self.database_type == "mysql":
            self.extra_options.update({
                "charset": "utf8mb4",
                "use_unicode": True
            })
    
    @property
    def async_url(self) -> str:
        """Get async-compatible database URL"""
        if self.database_type == "postgresql":
            return self.url.replace("postgresql://", "postgresql+asyncpg://")
        elif self.database_type == "mysql":
            return self.url.replace("mysql://", "mysql+aiomysql://")
        elif self.database_type == "sqlite":
            return self.url.replace("sqlite://", "sqlite+aiosqlite://")
        else:
            return self.url
    
    @property
    def engine_options(self) -> Dict[str, Any]:
        """Get SQLAlchemy engine options"""
        options = {
            "echo": self.echo,
            "echo_pool": self.echo_pool,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "connect_args": self.extra_options
        }
        
        # Add pooling options for non-SQLite databases
        if self.database_type != "sqlite":
            options.update({
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "poolclass": QueuePool
            })
        else:
            options["poolclass"] = NullPool
        
        return options

# ===============================================================================
# DATABASE CONNECTION MANAGEMENT
# ===============================================================================

class DatabaseManager:
    """
    Production-ready database connection manager with comprehensive error handling.
    
    This class manages database connections, connection pooling, health monitoring,
    and automatic retry logic for robust database operations.
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = logger.bind(component="DatabaseManager")
        
        # Connection objects
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_engine: Optional[Any] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        
        # Health monitoring
        self._connection_count = 0
        self._last_health_check = 0
        self._health_status = True
        self._error_count = 0
        
        # Initialize connections
        self._setup_engines()
        self._setup_event_listeners()
    
    def _setup_engines(self) -> None:
        """Setup both async and sync database engines"""
        try:
            # Setup async engine
            self._async_engine = create_async_engine(
                self.config.async_url,
                **self.config.engine_options
            )
            
            # Setup sync engine for migrations and admin tasks
            self._sync_engine = create_engine(
                self.config.url,
                **self.config.engine_options
            )
            
            # Setup session factories
            self._async_session_factory = async_sessionmaker(
                bind=self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            self._sync_session_factory = sessionmaker(
                bind=self._sync_engine,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            self.logger.info(
                "Database engines initialized successfully",
                database_type=self.config.database_type,
                pool_size=self.config.pool_size
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize database engines", error=str(e))
            raise
    
    def _setup_event_listeners(self) -> None:
        """Setup SQLAlchemy event listeners for monitoring and optimization"""
        if self._async_engine and self._sync_engine:
            # Connection tracking
            @event.listens_for(self._async_engine.sync_engine, "connect")
            def on_connect(dbapi_connection, connection_record):
                self._connection_count += 1
                self.logger.debug("Database connection established", 
                                connection_count=self._connection_count)
            
            @event.listens_for(self._async_engine.sync_engine, "close")
            def on_close(dbapi_connection, connection_record):
                self._connection_count -= 1
                self.logger.debug("Database connection closed", 
                                connection_count=self._connection_count)
            
            # Error tracking
            @event.listens_for(self._async_engine.sync_engine, "handle_error")
            def on_error(exception_context):
                self._error_count += 1
                self.logger.error("Database error occurred", 
                                error=str(exception_context.original_exception),
                                error_count=self._error_count)
            
            # Performance optimization for PostgreSQL
            if self.config.database_type == "postgresql":
                @event.listens_for(self._async_engine.sync_engine, "connect")
                def set_postgresql_optimizations(dbapi_connection, connection_record):
                    with dbapi_connection.cursor() as cursor:
                        # Set connection-level optimizations
                        cursor.execute("SET default_transaction_isolation TO 'read committed'")
                        cursor.execute("SET timezone TO 'UTC'")
                        cursor.execute("SET statement_timeout TO '30s'")
    
    @property
    def async_engine(self) -> AsyncEngine:
        """Get async database engine"""
        if self._async_engine is None:
            raise ValueError("Async engine not initialized")
        return self._async_engine
    
    @property
    def sync_engine(self) -> Any:
        """Get sync database engine"""
        if self._sync_engine is None:
            raise ValueError("Sync engine not initialized")
        return self._sync_engine
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session with automatic cleanup.
        
        This context manager ensures proper session lifecycle management
        with automatic rollback on errors and cleanup on completion.
        
        Yields:
            AsyncSession: Database session for async operations
            
        Raises:
            DatabaseConnectionError: When connection fails
            DatabaseTimeoutError: When operation times out
        """
        if self._async_session_factory is None:
            raise ValueError("Async session factory not initialized")
        
        session = self._async_session_factory()
        try:
            self.logger.debug("Async database session created")
            yield session
            await session.commit()
            self.logger.debug("Async database session committed")
            
        except SQLAlchemyError as e:
            await session.rollback()
            self.logger.error("Database error, session rolled back", error=str(e))
            raise DatabaseError(f"Database operation failed: {e}")
            
        except Exception as e:
            await session.rollback()
            self.logger.error("Unexpected error, session rolled back", error=str(e))
            raise
            
        finally:
            await session.close()
            self.logger.debug("Async database session closed")
    
    @asynccontextmanager
    async def get_sync_session(self) -> AsyncGenerator[Session, None]:
        """
        Get sync database session with automatic cleanup.
        
        This context manager provides synchronous database access for
        operations that require sync execution (migrations, admin tasks).
        
        Yields:
            Session: Database session for sync operations
        """
        if self._sync_session_factory is None:
            raise ValueError("Sync session factory not initialized")
        
        session = self._sync_session_factory()
        try:
            self.logger.debug("Sync database session created")
            yield session
            session.commit()
            self.logger.debug("Sync database session committed")
            
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error("Database error, session rolled back", error=str(e))
            raise DatabaseError(f"Database operation failed: {e}")
            
        except Exception as e:
            session.rollback()
            self.logger.error("Unexpected error, session rolled back", error=str(e))
            raise
            
        finally:
            session.close()
            self.logger.debug("Sync database session closed")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive database health check.
        
        Returns:
            Dict containing health status and metrics
        """
        health_info = {
            "status": "healthy",
            "timestamp": time.time(),
            "connection_count": self._connection_count,
            "error_count": self._error_count,
            "pool_info": {},
            "checks": {}
        }
        
        try:
            # Test async connection
            async with self.get_async_session() as session:
                result = await session.execute("SELECT 1")
                health_info["checks"]["async_connection"] = "healthy"
            
            # Get pool information
            if hasattr(self._async_engine.pool, 'size'):
                health_info["pool_info"] = {
                    "pool_size": self._async_engine.pool.size(),
                    "checked_in": self._async_engine.pool.checkedin(),
                    "checked_out": self._async_engine.pool.checkedout(),
                    "overflow": self._async_engine.pool.overflow(),
                    "total_connections": self._async_engine.pool.size() + self._async_engine.pool.overflow()
                }
            
            self._health_status = True
            self._last_health_check = time.time()
            
        except Exception as e:
            health_info["status"] = "unhealthy"
            health_info["checks"]["async_connection"] = f"failed: {str(e)}"
            self._health_status = False
            self.logger.error("Database health check failed", error=str(e))
        
        return health_info
    
    async def execute_with_retry(self, operation: callable, *args, **kwargs) -> Any:
        """
        Execute database operation with automatic retry logic.
        
        Args:
            operation: Async callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of the operation
            
        Raises:
            DatabaseError: When all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(self.config.max_retry_attempts):
            try:
                result = await operation(*args, **kwargs)
                if attempt > 0:
                    self.logger.info("Database operation succeeded after retry", 
                                   attempt=attempt + 1)
                return result
                
            except (DisconnectionError, TimeoutError) as e:
                last_exception = e
                if attempt < self.config.max_retry_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        "Database operation failed, retrying",
                        attempt=attempt + 1,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error("Database operation failed after all retries", 
                                    attempts=self.config.max_retry_attempts,
                                    error=str(e))
                    
            except SQLAlchemyError as e:
                # Don't retry for non-connection errors
                self.logger.error("Database operation failed with non-retryable error", 
                                error=str(e))
                raise DatabaseError(f"Database operation failed: {e}")
        
        raise DatabaseError(f"Database operation failed after {self.config.max_retry_attempts} attempts: {last_exception}")
    
    async def close(self) -> None:
        """Close all database connections and cleanup resources"""
        try:
            if self._async_engine:
                await self._async_engine.dispose()
                self.logger.info("Async database engine disposed")
            
            if self._sync_engine:
                self._sync_engine.dispose()
                self.logger.info("Sync database engine disposed")
            
            self._async_engine = None
            self._sync_engine = None
            self._async_session_factory = None
            self._sync_session_factory = None
            
        except Exception as e:
            self.logger.error("Error closing database connections", error=str(e))
            raise

# ===============================================================================
# MIGRATION MANAGEMENT
# ===============================================================================

class MigrationManager:
    """
    Database migration management with Alembic integration.
    
    This class provides comprehensive migration management including
    automatic migrations, rollback capabilities, and migration validation.
    """
    
    def __init__(self, database_manager: DatabaseManager, alembic_config_path: str = "alembic.ini"):
        self.db_manager = database_manager
        self.alembic_config_path = alembic_config_path
        self.logger = logger.bind(component="MigrationManager")
        
        # Setup Alembic configuration
        self.alembic_cfg = AlembicConfig(alembic_config_path)
        self.alembic_cfg.set_main_option("sqlalchemy.url", database_manager.config.url)
    
    def get_current_revision(self) -> Optional[str]:
        """Get current database revision"""
        try:
            with self.db_manager.sync_engine.connect() as connection:
                from alembic.runtime.migration import MigrationContext
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
        except Exception as e:
            self.logger.error("Failed to get current revision", error=str(e))
            return None
    
    def get_head_revision(self) -> Optional[str]:
        """Get head revision from migration files"""
        try:
            from alembic.script import ScriptDirectory
            script = ScriptDirectory.from_config(self.alembic_cfg)
            return script.get_current_head()
        except Exception as e:
            self.logger.error("Failed to get head revision", error=str(e))
            return None
    
    def is_database_up_to_date(self) -> bool:
        """Check if database is up to date with migrations"""
        current = self.get_current_revision()
        head = self.get_head_revision()
        return current == head
    
    def upgrade_to_head(self) -> bool:
        """Upgrade database to latest migration"""
        try:
            self.logger.info("Starting database migration to head")
            command.upgrade(self.alembic_cfg, "head")
            self.logger.info("Database migration completed successfully")
            return True
        except Exception as e:
            self.logger.error("Database migration failed", error=str(e))
            return False
    
    def downgrade_to_revision(self, revision: str) -> bool:
        """Downgrade database to specific revision"""
        try:
            self.logger.info("Starting database downgrade", target_revision=revision)
            command.downgrade(self.alembic_cfg, revision)
            self.logger.info("Database downgrade completed successfully")
            return True
        except Exception as e:
            self.logger.error("Database downgrade failed", error=str(e))
            return False
    
    def create_migration(self, message: str, auto_generate: bool = True) -> bool:
        """Create new migration file"""
        try:
            self.logger.info("Creating new migration", message=message)
            if auto_generate:
                command.revision(self.alembic_cfg, message=message, autogenerate=True)
            else:
                command.revision(self.alembic_cfg, message=message)
            self.logger.info("Migration file created successfully")
            return True
        except Exception as e:
            self.logger.error("Failed to create migration", error=str(e))
            return False

# ===============================================================================
# EXCEPTION CLASSES
# ===============================================================================

class DatabaseError(Exception):
    """Base exception for database-related errors"""
    pass

class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails"""
    pass

class DatabaseTimeoutError(DatabaseError):
    """Exception raised when database operation times out"""
    pass

class MigrationError(DatabaseError):
    """Exception raised when database migration fails"""
    pass

# ===============================================================================
# DEPENDENCY INJECTION
# ===============================================================================

# Global database manager instance
_database_manager: Optional[DatabaseManager] = None

async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database sessions.
    
    This function provides database sessions for FastAPI dependency injection,
    ensuring proper session lifecycle management and error handling.
    
    Yields:
        AsyncSession: Database session for request processing
    """
    if _database_manager is None:
        raise ValueError("Database manager not initialized")
    
    async with _database_manager.get_async_session() as session:
        yield session

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_database_session for backward compatibility"""
    async for session in get_database_session():
        yield session

# ===============================================================================
# CONFIGURATION FACTORY
# ===============================================================================

@lru_cache()
def get_database_config() -> DatabaseConfig:
    """
    Get database configuration with caching.
    
    This function creates and caches a DatabaseConfig instance based on
    environment variables and default settings.
    
    Returns:
        DatabaseConfig: Configured database settings
    """
    from .settings import get_settings
    
    settings = get_settings()
    
    config = DatabaseConfig(
        url=settings.DATABASE_URL,
        echo=settings.DEBUG and settings.ENVIRONMENT == "development",
        echo_pool=settings.DEBUG and settings.ENVIRONMENT == "development",
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_recycle=settings.DATABASE_POOL_RECYCLE
    )
    
    logger.info(
        "Database configuration initialized",
        database_type=config.database_type,
        pool_size=config.pool_size,
        host=config.host
    )
    
    return config

# ===============================================================================
# INITIALIZATION FUNCTIONS
# ===============================================================================

async def initialize_database() -> DatabaseManager:
    """
    Initialize database manager and perform startup checks.
    
    This function initializes the global database manager, performs health checks,
    and optionally runs migrations based on configuration.
    
    Returns:
        DatabaseManager: Initialized database manager instance
    """
    global _database_manager
    
    if _database_manager is not None:
        return _database_manager
    
    try:
        # Get configuration
        config = get_database_config()
        
        # Create database manager
        _database_manager = DatabaseManager(config)
        
        # Perform health check
        health_info = await _database_manager.health_check()
        if health_info["status"] != "healthy":
            raise DatabaseConnectionError("Database health check failed")
        
        # Check migrations
        migration_manager = MigrationManager(_database_manager)
        if not migration_manager.is_database_up_to_date():
            logger.warning("Database is not up to date with migrations")
            
            # Auto-migrate in development
            if config.database_type != "sqlite" and os.getenv("AUTO_MIGRATE", "false").lower() == "true":
                if migration_manager.upgrade_to_head():
                    logger.info("Database automatically migrated to latest version")
                else:
                    raise MigrationError("Failed to automatically migrate database")
        
        logger.info("Database initialized successfully")
        return _database_manager
        
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise

async def close_database() -> None:
    """Close database connections and cleanup resources"""
    global _database_manager
    
    if _database_manager is not None:
        await _database_manager.close()
        _database_manager = None
        logger.info("Database connections closed")

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_tables() -> None:
    """Create all database tables (for development/testing)"""
    config = get_database_config()
    engine = create_engine(config.url)
    Base.metadata.create_all(engine)
    logger.info("Database tables created")

def drop_tables() -> None:
    """Drop all database tables (for testing)"""
    config = get_database_config()
    engine = create_engine(config.url)
    Base.metadata.drop_all(engine)
    logger.info("Database tables dropped")

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "Base",
    "metadata",
    "DatabaseConfig",
    "DatabaseManager",
    "MigrationManager",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseTimeoutError",
    "MigrationError",
    "get_database_config",
    "get_database_session",
    "get_db_session",
    "initialize_database",
    "close_database",
    "create_tables",
    "drop_tables"
]