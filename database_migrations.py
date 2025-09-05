"""
YMERA Enterprise - Database Migrations System
Production-Ready Database Migration Management - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field

# Third-party imports (alphabetical)
import structlog
from sqlalchemy import text, Table, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# Local imports (alphabetical)
from .connection import get_database_manager, get_async_engine, Base
from config.settings import get_settings
from monitoring.performance_tracker import track_performance

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.database.migrations")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Migration settings
MIGRATIONS_DIR = Path("database/migrations")
MIGRATION_FILE_PATTERN = r"^(\d{4})_([a-zA-Z0-9_]+)\.py$"
MIGRATION_TABLE_NAME = "schema_migrations"

# Migration statuses
MIGRATION_STATUS_PENDING = "pending"
MIGRATION_STATUS_RUNNING = "running"
MIGRATION_STATUS_COMPLETED = "completed"
MIGRATION_STATUS_FAILED = "failed"
MIGRATION_STATUS_ROLLED_BACK = "rolled_back"

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class MigrationInfo:
    """Information about a migration"""
    version: int
    name: str
    filename: str
    filepath: Path
    checksum: str
    description: Optional[str] = None
    dependencies: List[int] = field(default_factory=list)

@dataclass
class MigrationExecution:
    """Information about migration execution"""
    version: int
    name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    rollback_executed: bool = False

@dataclass
class MigrationPlan:
    """Migration execution plan"""
    pending_migrations: List[MigrationInfo]
    current_version: int
    target_version: int
    total_migrations: int

# ===============================================================================
# MIGRATION TRACKING TABLE
# ===============================================================================

schema_migrations = Table(
    MIGRATION_TABLE_NAME,
    Base.metadata,
    Column('id', String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column('version', Integer, nullable=False, unique=True, index=True),
    Column('name', String(255), nullable=False),
    Column('filename', String(255), nullable=False),
    Column('checksum', String(64), nullable=False),
    Column('status', String(20), nullable=False, default=MIGRATION_STATUS_PENDING),
    Column('started_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('completed_at', DateTime),
    Column('execution_time_ms', Integer),
    Column('error_message', Text),
    Column('rollback_executed', Boolean, nullable=False, default=False),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('updated_at', DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
)

# ===============================================================================
# MIGRATION BASE CLASSES
# ===============================================================================

class BaseMigration(ABC):
    """Abstract base class for all migrations"""
    
    def __init__(self):
        self.version: int = 0
        self.name: str = ""
        self.description: str = ""
        self.dependencies: List[int] = []
    
    @abstractmethod
    async def up(self, session: AsyncSession) -> None:
        """Execute the migration"""
        pass
    
    @abstractmethod
    async def down(self, session: AsyncSession) -> None:
        """Rollback the migration"""
        pass
    
    async def validate_preconditions(self, session: AsyncSession) -> bool:
        """Validate migration preconditions"""
        return True
    
    async def validate_postconditions(self, session: AsyncSession) -> bool:
        """Validate migration postconditions"""
        return True

# ===============================================================================
# MIGRATION MANAGER
# ===============================================================================

class MigrationManager:
    """Production-ready database migration manager"""
    
    def __init__(self, migrations_dir: Optional[Path] = None):
        self.migrations_dir = migrations_dir or MIGRATIONS_DIR
        self.logger = logger.bind(manager="MigrationManager")
        
        # State management
        self._engine: Optional[AsyncEngine] = None
        self._discovered_migrations: Dict[int, MigrationInfo] = {}
        self._loaded_migrations: Dict[int, BaseMigration] = {}
        
        # Ensure migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize migration manager"""
        try:
            self.logger.info("Initializing migration manager")
            
            # Get database engine
            self._engine = await get_async_engine()
            
            # Ensure migration tracking table exists
            await self._ensure_migration_table()
            
            # Discover available migrations
            await self._discover_migrations()
            
            self.logger.info(
                "Migration manager initialized",
                discovered_migrations=len(self._discovered_migrations)
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize migration manager", error=str(e))
            raise RuntimeError(f"Migration manager initialization failed: {str(e)}")
    
    async def _ensure_migration_table(self) -> None:
        """Ensure migration tracking table exists"""
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(lambda sync_conn: schema_migrations.create(sync_conn, checkfirst=True))
            
            self.logger.debug("Migration tracking table ready")
            
        except Exception as e:
            self.logger.error("Failed to create migration tracking table", error=str(e))
            raise
    
    async def _discover_migrations(self) -> None:
        """Discover all migration files"""
        self._discovered_migrations.clear()
        
        try:
            migration_files = []
            
            # Find all Python migration files
            for file_path in self.migrations_dir.glob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                
                match = re.match(MIGRATION_FILE_PATTERN, file_path.name)
                if match:
                    version = int(match.group(1))
                    name = match.group(2)
                    
                    # Calculate file checksum
                    checksum = self._calculate_file_checksum(file_path)
                    
                    migration_info = MigrationInfo(
                        version=version,
                        name=name,
                        filename=file_path.name,
                        filepath=file_path,
                        checksum=checksum
                    )
                    
                    migration_files.append(migration_info)
            
            # Sort by version
            migration_files.sort(key=lambda m: m.version)
            
            # Store discovered migrations
            for migration in migration_files:
                self._discovered_migrations[migration.version] = migration
            
            self.logger.info(
                "Discovered migrations",
                count=len(migration_files),
                versions=[m.version for m in migration_files]
            )
            
        except Exception as e:
            self.logger.error("Failed to discover migrations", error=str(e))
            raise
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of migration file"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            self.logger.error("Failed to calculate checksum", file=str(file_path), error=str(e))
            raise
    
    async def _load_migration(self, migration_info: MigrationInfo) -> BaseMigration:
        """Load migration class from file"""
        if migration_info.version in self._loaded_migrations:
            return self._loaded_migrations[migration_info.version]
        
        try:
            # Import migration module dynamically
            module_name = f"database.migrations.{migration_info.filename[:-3]}"
            
            spec = __import__(module_name, fromlist=['Migration'])
            migration_class = getattr(spec, 'Migration')
            
            # Instantiate migration
            migration = migration_class()
            migration.version = migration_info.version
            migration.name = migration_info.name
            
            # Cache loaded migration
            self._loaded_migrations[migration_info.version] = migration
            
            self.logger.debug("Loaded migration", version=migration_info.version, name=migration_info.name)
            
            return migration
            
        except Exception as e:
            self.logger.error(
                "Failed to load migration",
                version=migration_info.version,
                file=migration_info.filename,
                error=str(e)
            )
            raise ImportError(f"Failed to load migration {migration_info.version}: {str(e)}")
    
    async def get_current_version(self) -> int:
        """Get current database schema version"""
        try:
            db_manager = await get_database_manager()
            
            query = f"""
            SELECT COALESCE(MAX(version), 0) as current_version 
            FROM {MIGRATION_TABLE_NAME} 
            WHERE status = :status
            """
            
            result = await db_manager.execute_query(
                query, 
                {"status": MIGRATION_STATUS_COMPLETED}
            )
            
            current_version = result[0]["current_version"] if result else 0
            
            self.logger.debug("Retrieved current database version", version=current_version)
            
            return current_version
            
        except Exception as e:
            self.logger.error("Failed to get current version", error=str(e))
            return 0
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status"""
        try:
            current_version = await self.get_current_version()
            latest_version = max(self._discovered_migrations.keys()) if self._discovered_migrations else 0
            
            # Get executed migrations
            db_manager = await get_database_manager()
            
            query = f"""
            SELECT version, name, status, started_at, completed_at, execution_time_ms, error_message
            FROM {MIGRATION_TABLE_NAME}
            ORDER BY version
            """
            
            executed_migrations = await db_manager.execute_query(query)
            
            # Get pending migrations
            pending_versions = [
                v for v in self._discovered_migrations.keys() 
                if v > current_version
            ]
            
            return {
                "current_version": current_version,
                "latest_version": latest_version,
                "total_discovered": len(self._discovered_migrations),
                "total_executed": len(executed_migrations),
                "pending_count": len(pending_versions),
                "pending_versions": pending_versions,
                "executed_migrations": executed_migrations,
                "up_to_date": current_version == latest_version
            }
            
        except Exception as e:
            self.logger.error("Failed to get migration status", error=str(e))
            raise
    
    async def create_migration_plan(self, target_version: Optional[int] = None) -> MigrationPlan:
        """Create migration execution plan"""
        try:
            current_version = await self.get_current_version()
            
            if target_version is None:
                target_version = max(self._discovered_migrations.keys()) if self._discovered_migrations else 0
            
            # Find pending migrations
            pending_migrations = []
            
            for version in sorted(self._discovered_migrations.keys()):
                if current_version < version <= target_version:
                    pending_migrations.append(self._discovered_migrations[version])
            
            plan = MigrationPlan(
                pending_migrations=pending_migrations,
                current_version=current_version,
                target_version=target_version,
                total_migrations=len(pending_migrations)
            )
            
            self.logger.info(
                "Created migration plan",
                current_version=current_version,
                target_version=target_version,
                pending_count=len(pending_migrations)
            )
            
            return plan
            
        except Exception as e:
            self.logger.error("Failed to create migration plan", error=str(e))
            raise
    
    @track_performance
    async def execute_migration(self, migration_info: MigrationInfo) -> MigrationExecution:
        """Execute a single migration"""
        execution = MigrationExecution(
            version=migration_info.version,
            name=migration_info.name,
            status=MIGRATION_STATUS_RUNNING,
            started_at=datetime.utcnow()
        )
        
        try:
            self.logger.info(
                "Starting migration execution",
                version=migration_info.version,
                name=migration_info.name
            )
            
            # Record migration start
            await self._record_migration_start(migration_info)
            
            # Load migration
            migration = await self._load_migration(migration_info)
            
            # Execute migration within transaction
            db_manager = await get_database_manager()
            
            async with db_manager.get_session() as session:
                async with session.begin():
                    # Validate preconditions
                    if not await migration.validate_preconditions(session):
                        raise RuntimeError("Migration preconditions not met")
                    
                    # Execute migration
                    await migration.up(session)
                    
                    # Validate postconditions
                    if not await migration.validate_postconditions(session):
                        raise RuntimeError("Migration postconditions not met")
                    
                    await session.flush()
            
            # Record successful completion
            execution.completed_at = datetime.utcnow()
            execution.execution_time_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
            execution.status = MIGRATION_STATUS_COMPLETED
            
            await self._record_migration_completion(execution)
            
            self.logger.info(
                "Migration completed successfully",
                version=migration_info.version,
                execution_time_ms=execution.execution_time_ms
            )
            
            return execution
            
        except Exception as e:
            execution.status = MIGRATION_STATUS_FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            
            await self._record_migration_failure(execution)
            
            self.logger.error(
                "Migration failed",
                version=migration_info.version,
                error=str(e)
            )
            
            raise RuntimeError(f"Migration {migration_info.version} failed: {str(e)}")
    
    async def _record_migration_start(self, migration_info: MigrationInfo) -> None:
        """Record migration start in tracking table"""
        try:
            db_manager = await get_database_manager()
            
            query = f"""
            INSERT INTO {MIGRATION_TABLE_NAME} 
            (id, version, name, filename, checksum, status, started_at)
            VALUES (:id, :version, :name, :filename, :checksum, :status, :started_at)
            ON CONFLICT (version) DO UPDATE SET
                status = :status,
                started_at = :started_at,
                error_message = NULL,
                rollback_executed = FALSE
            """
            
            await db_manager.execute_query(query, {
                "id": str(uuid.uuid4()),
                "version": migration_info.version,
                "name": migration_info.name,
                "filename": migration_info.filename,
                "checksum": migration_info.checksum,
                "status": MIGRATION_STATUS_RUNNING,
                "started_at": datetime.utcnow()
            })
            
        except Exception as e:
            self.logger.error("Failed to record migration start", error=str(e))
            raise
    
    async def _record_migration_completion(self, execution: MigrationExecution) -> None:
        """Record successful migration completion"""
        try:
            db_manager = await get_database_manager()
            
            query = f"""
            UPDATE {MIGRATION_TABLE_NAME}
            SET status = :status,
                completed_at = :completed_at,
                execution_time_ms = :execution_time_ms,
                updated_at = :updated_at
            WHERE version = :version
            """
            
            await db_manager.execute_query(query, {
                "status": execution.status,
                "completed_at": execution.completed_at,
                "execution_time_ms": execution.execution_time_ms,
                "updated_at": datetime.utcnow(),
                "version": execution.version
            })
            
        except Exception as e:
            self.logger.error("Failed to record migration completion", error=str(e))
            raise
    
    async def _record_migration_failure(self, execution: MigrationExecution) -> None:
        """Record migration failure"""
        try:
            db_manager = await get_database_manager()
            
            query = f"""
            UPDATE {MIGRATION_TABLE_NAME}
            SET status = :status,
                completed_at = :completed_at,
                error_message = :error_message,
                updated_at = :updated_at
            WHERE version = :version
            """
            
            await db_manager.execute_query(query, {
                "status": execution.status,
                "completed_at": execution.completed_at,
                "error_message": execution.error_message,
                "updated_at": datetime.utcnow(),
                "version": execution.version
            })
            
        except Exception as e:
            self.logger.error("Failed to record migration failure", error=str(e))
    
    async def migrate(self, target_version: Optional[int] = None) -> Dict[str, Any]:
        """Execute all pending migrations"""
        try:
            self.logger.info("Starting database migration", target_version=target_version)
            
            # Create migration plan
            plan = await self.create_migration_plan(target_version)
            
            if not plan.pending_migrations:
                self.logger.info("No pending migrations")
                return {
                    "status": "up_to_date",
                    "current_version": plan.current_version,
                    "target_version": plan.target_version,
                    "executed_migrations": []
                }
            
            # Execute migrations in order
            executed_migrations = []
            
            for migration_info in plan.pending_migrations:
                try:
                    execution = await self.execute_migration(migration_info)
                    executed_migrations.append(execution)
                    
                except Exception as e:
                    self.logger.error(
                        "Migration execution failed, stopping",
                        failed_version=migration_info.version,
                        error=str(e)
                    )
                    
                    return {
                        "status": "failed",
                        "current_version": await self.get_current_version(),
                        "target_version": plan.target_version,
                        "executed_migrations": executed_migrations,
                        "failed_migration": migration_info.version,
                        "error": str(e)
                    }
            
            final_version = await self.get_current_version()
            
            self.logger.info(
                "Database migration completed",
                initial_version=plan.current_version,
                final_version=final_version,
                executed_count=len(executed_migrations)
            )
            
            return {
                "status": "completed",
                "current_version": final_version,
                "target_version": plan.target_version,
                "executed_migrations": executed_migrations
            }
            
        except Exception as e:
            self.logger.error("Database migration failed", error=str(e))
            raise RuntimeError(f"Database migration failed: {str(e)}")
    
    async def rollback_migration(self, version: int) -> MigrationExecution:
        """Rollback a specific migration"""
        try:
            self.logger.warning("Starting migration rollback", version=version)
            
            # Verify migration exists and is completed
            if version not in self._discovered_migrations:
                raise ValueError(f"Migration {version} not found")
            
            # Check if migration was completed
            db_manager = await get_database_manager()
            
            query = f"""
            SELECT status, rollback_executed 
            FROM {MIGRATION_TABLE_NAME} 
            WHERE version = :version
            """
            
            result = await db_manager.execute_query(query, {"version": version})
            
            if not result:
                raise ValueError(f"Migration {version} was never executed")
            
            migration_record = result[0]
            
            if migration_record["status"] != MIGRATION_STATUS_COMPLETED:
                raise ValueError(f"Migration {version} is not in completed state")
            
            if migration_record["rollback_executed"]:
                raise ValueError(f"Migration {version} has already been rolled back")
            
            # Load and execute rollback
            migration_info = self._discovered_migrations[version]
            migration = await self._load_migration(migration_info)
            
            execution = MigrationExecution(
                version=version,
                name=migration_info.name,
                status=MIGRATION_STATUS_RUNNING,
                started_at=datetime.utcnow()
            )
            
            async with db_manager.get_session() as session:
                async with session.begin():
                    await migration.down(session)
                    await session.flush()
            
            # Record rollback completion
            execution.completed_at = datetime.utcnow()
            execution.execution_time_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
            execution.status = MIGRATION_STATUS_ROLLED_BACK
            execution.rollback_executed = True
            
            # Update migration record
            update_query = f"""
            UPDATE {MIGRATION_TABLE_NAME}
            SET status = :status,
                rollback_executed = TRUE,
                updated_at = :updated_at
            WHERE version = :version
            """
            
            await db_manager.execute_query(update_query, {
                "status": MIGRATION_STATUS_ROLLED_BACK,
                "updated_at": datetime.utcnow(),
                "version": version
            })
            
            self.logger.warning(
                "Migration rollback completed",
                version=version,
                execution_time_ms=execution.execution_time_ms
            )
            
            return execution
            
        except Exception as e:
            self.logger.error("Migration rollback failed", version=version, error=str(e))
            raise RuntimeError(f"Migration rollback failed: {str(e)}")

# ===============================================================================
# MIGRATION GENERATOR
# ===============================================================================

class MigrationGenerator:
    """Generate new migration files"""
    
    def __init__(self, migrations_dir: Optional[Path] = None):
        self.migrations_dir = migrations_dir or MIGRATIONS_DIR
        self.logger = logger.bind(generator="MigrationGenerator")
    
    def generate_migration(self, name: str, description: str = "") -> Path:
        """
        Generate a new migration file.
        
        Args:
            name: Migration name (snake_case)
            description: Migration description
            
        Returns:
            Path to the generated migration file
        """
        try:
            # Validate name
            if not re.match(r'^[a-z0-9_]+, name):
                raise ValueError("Migration name must be snake_case with alphanumeric characters and underscores only")
            
            # Determine next version number
            version = self._get_next_version()
            
            # Generate filename
            filename = f"{version:04d}_{name}.py"
            filepath = self.migrations_dir / filename
            
            # Generate migration content
            content = self._generate_migration_content(version, name, description)
            
            # Write file
            with open(filepath, 'w') as f:
                f.write(content)
            
            self.logger.info(
                "Generated migration file",
                version=version,
                name=name,
                file=filename
            )
            
            return filepath
            
        except Exception as e:
            self.logger.error("Failed to generate migration", name=name, error=str(e))
            raise RuntimeError(f"Migration generation failed: {str(e)}")
    
    def _get_next_version(self) -> int:
        """Get next available version number"""
        existing_versions = []
        
        for file_path in self.migrations_dir.glob("*.py"):
            match = re.match(MIGRATION_FILE_PATTERN, file_path.name)
            if match:
                existing_versions.append(int(match.group(1)))
        
        return max(existing_versions, default=0) + 1
    
    def _generate_migration_content(self, version: int, name: str, description: str) -> str:
        """Generate migration file content"""
        timestamp = datetime.utcnow().isoformat()
        
        return f'''"""
Migration {version:04d}: {name.replace('_', ' ').title()}
{description}

Generated on: {timestamp}
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database.migrations import BaseMigration


class Migration(BaseMigration):
    """Migration {version:04d}: {name.replace('_', ' ').title()}"""
    
    def __init__(self):
        super().__init__()
        self.version = {version}
        self.name = "{name}"
        self.description = "{description}"
        self.dependencies = []  # List of migration versions this depends on
    
    async def up(self, session: AsyncSession) -> None:
        """Execute the migration"""
        # TODO: Implement migration logic
        # Example:
        # await session.execute(text("""
        #     CREATE TABLE example_table (
        #         id SERIAL PRIMARY KEY,
        #         name VARCHAR(255) NOT NULL,
        #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        #     )
        # """))
        
        pass
    
    async def down(self, session: AsyncSession) -> None:
        """Rollback the migration"""
        # TODO: Implement rollback logic
        # Example:
        # await session.execute(text("DROP TABLE IF EXISTS example_table"))
        
        pass
    
    async def validate_preconditions(self, session: AsyncSession) -> bool:
        """Validate migration preconditions"""
        # TODO: Implement precondition checks
        # Example:
        # result = await session.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = 'prerequisite_table'"))
        # return result.fetchone() is not None
        
        return True
    
    async def validate_postconditions(self, session: AsyncSession) -> bool:
        """Validate migration postconditions"""
        # TODO: Implement postcondition checks
        # Example:
        # result = await session.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = 'example_table'"))
        # return result.fetchone() is not None
        
        return True
'''

# ===============================================================================
# GLOBAL MIGRATION MANAGER
# ===============================================================================

_migration_manager: Optional[MigrationManager] = None

async def get_migration_manager() -> MigrationManager:
    """Get or create global migration manager instance"""
    global _migration_manager
    
    if _migration_manager is None:
        _migration_manager = MigrationManager()
        await _migration_manager.initialize()
    
    return _migration_manager

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def migrate_database(target_version: Optional[int] = None) -> Dict[str, Any]:
    """Execute database migrations"""
    manager = await get_migration_manager()
    return await manager.migrate(target_version)

async def get_migration_status() -> Dict[str, Any]:
    """Get migration status"""
    manager = await get_migration_manager()
    return await manager.get_migration_status()

async def rollback_migration(version: int) -> MigrationExecution:
    """Rollback a migration"""
    manager = await get_migration_manager()
    return await manager.rollback_migration(version)

def create_migration(name: str, description: str = "") -> Path:
    """Create a new migration file"""
    generator = MigrationGenerator()
    return generator.generate_migration(name, description)

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Core classes
    "BaseMigration",
    "MigrationManager",
    "MigrationGenerator",
    
    # Data models
    "MigrationInfo",
    "MigrationExecution",
    "MigrationPlan",
    
    # Utility functions
    "migrate_database",
    "get_migration_status",
    "rollback_migration",
    "create_migration",
    "get_migration_manager",
    
    # Constants
    "MIGRATION_STATUS_PENDING",
    "MIGRATION_STATUS_RUNNING",
    "MIGRATION_STATUS_COMPLETED",
    "MIGRATION_STATUS_FAILED",
    "MIGRATION_STATUS_ROLLED_BACK"
]