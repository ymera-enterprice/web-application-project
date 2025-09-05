"""
YMERA Core Database Migration Manager
Enterprise-grade migration system with version control and rollback capabilities
"""

import asyncio
import asyncpg
import aiosqlite
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import hashlib
import json
from datetime import datetime
import importlib.util
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class MigrationManager:
    """Production-ready database migration manager"""
    
    def __init__(self, db_manager, migrations_dir: str = None):
        self.db_manager = db_manager
        self.migrations_dir = Path(migrations_dir or "ymera_core/database/migrations")
        self.logger = logging.getLogger(__name__)
        self._ensure_migrations_dir()
        
    def _ensure_migrations_dir(self):
        """Ensure migrations directory exists"""
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
    async def initialize(self):
        """Initialize migration tracking table"""
        async with self.db_manager.get_session() as session:
            # Create migration tracking table
            if self.db_manager.db_type == 'postgresql':
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        checksum VARCHAR(64) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        execution_time INTEGER DEFAULT 0,
                        rollback_sql TEXT,
                        metadata JSONB DEFAULT '{}'::jsonb
                    )
                """))
            else:  # SQLite
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        execution_time INTEGER DEFAULT 0,
                        rollback_sql TEXT,
                        metadata TEXT DEFAULT '{}'
                    )
                """))
            
            await session.commit()
            self.logger.info("Migration tracking table initialized")
    
    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of migration content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of applied migrations"""
        async with self.db_manager.get_session() as session:
            result = await session.execute(text("""
                SELECT version, name, checksum, applied_at, execution_time
                FROM schema_migrations
                ORDER BY version
            """))
            
            return [
                {
                    'version': row[0],
                    'name': row[1], 
                    'checksum': row[2],
                    'applied_at': row[3],
                    'execution_time': row[4]
                }
                for row in result.fetchall()
            ]
    
    def _discover_migrations(self) -> List[Tuple[str, Path]]:
        """Discover migration files in migrations directory"""
        migrations = []
        
        for file_path in sorted(self.migrations_dir.glob("*.py")):
            if file_path.name.startswith('__'):
                continue
                
            # Extract version from filename (format: YYYYMMDDHHMMSS_name.py)
            filename = file_path.stem
            if '_' in filename:
                version = filename.split('_')[0]
                migrations.append((version, file_path))
        
        return migrations
    
    async def _load_migration(self, file_path: Path) -> Dict[str, Any]:
        """Load migration from Python file"""
        spec = importlib.util.spec_from_file_location("migration", file_path)
        if not spec or not spec.loader:
            raise ValueError(f"Could not load migration from {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get migration attributes
        migration_data = {
            'upgrade': getattr(module, 'upgrade', None),
            'downgrade': getattr(module, 'downgrade', None),
            'description': getattr(module, 'description', ''),
            'depends_on': getattr(module, 'depends_on', []),
            'metadata': getattr(module, 'metadata', {})
        }
        
        if not migration_data['upgrade']:
            raise ValueError(f"Migration {file_path} missing upgrade function")
        
        return migration_data
    
    async def check_migration_integrity(self) -> List[Dict[str, Any]]:
        """Check integrity of applied migrations"""
        applied_migrations = await self.get_applied_migrations()
        discovered_migrations = self._discover_migrations()
        issues = []
        
        # Check for missing migration files
        applied_versions = {m['version'] for m in applied_migrations}
        discovered_versions = {v for v, _ in discovered_migrations}
        
        missing_files = applied_versions - discovered_versions
        for version in missing_files:
            issues.append({
                'type': 'missing_file',
                'version': version,
                'message': f'Applied migration {version} file not found'
            })
        
        # Check checksums for existing migrations
        for migration in applied_migrations:
            version = migration['version']
            file_path = next((p for v, p in discovered_migrations if v == version), None)
            
            if file_path and file_path.exists():
                content = file_path.read_text()
                current_checksum = self._calculate_checksum(content)
                
                if current_checksum != migration['checksum']:
                    issues.append({
                        'type': 'checksum_mismatch',
                        'version': version,
                        'message': f'Migration {version} checksum mismatch - file may have been modified'
                    })
        
        return issues
    
    async def get_pending_migrations(self) -> List[Tuple[str, Path]]:
        """Get list of pending migrations"""
        applied_migrations = await self.get_applied_migrations()
        applied_versions = {m['version'] for m in applied_migrations}
        
        discovered_migrations = self._discover_migrations()
        
        return [(v, p) for v, p in discovered_migrations if v not in applied_versions]
    
    async def apply_migration(self, version: str, file_path: Path) -> bool:
        """Apply a single migration"""
        try:
            migration_data = await self._load_migration(file_path)
            content = file_path.read_text()
            checksum = self._calculate_checksum(content)
            
            start_time = datetime.utcnow()
            
            async with self.db_manager.get_session() as session:
                # Execute migration
                await migration_data['upgrade'](session, self.db_manager.engine)
                
                # Record migration
                execution_time = int((datetime.utcnow() - start_time).total_seconds())
                
                if self.db_manager.db_type == 'postgresql':
                    await session.execute(text("""
                        INSERT INTO schema_migrations (version, name, checksum, execution_time, metadata)
                        VALUES (:version, :name, :checksum, :execution_time, :metadata)
                    """), {
                        'version': version,
                        'name': file_path.stem,
                        'checksum': checksum,
                        'execution_time': execution_time,
                        'metadata': json.dumps(migration_data['metadata'])
                    })
                else:
                    await session.execute(text("""
                        INSERT INTO schema_migrations (version, name, checksum, execution_time, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    """), (
                        version,
                        file_path.stem,
                        checksum,
                        execution_time,
                        json.dumps(migration_data['metadata'])
                    ))
                
                await session.commit()
                
                self.logger.info(f"Applied migration {version} in {execution_time}s")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to apply migration {version}: {str(e)}")
            return False
    
    async def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration"""
        try:
            # Find migration file
            discovered_migrations = self._discover_migrations()
            file_path = next((p for v, p in discovered_migrations if v == version), None)
            
            if not file_path:
                self.logger.error(f"Migration file for version {version} not found")
                return False
            
            migration_data = await self._load_migration(file_path)
            
            if not migration_data['downgrade']:
                self.logger.error(f"Migration {version} has no downgrade function")
                return False
            
            async with self.db_manager.get_session() as session:
                # Execute rollback
                await migration_data['downgrade'](session, self.db_manager.engine)
                
                # Remove migration record
                if self.db_manager.db_type == 'postgresql':
                    await session.execute(text(
                        "DELETE FROM schema_migrations WHERE version = :version"
                    ), {'version': version})
                else:
                    await session.execute(text(
                        "DELETE FROM schema_migrations WHERE version = ?"
                    ), (version,))
                
                await session.commit()
                
                self.logger.info(f"Rolled back migration {version}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to rollback migration {version}: {str(e)}")
            return False
    
    async def migrate_up(self, target_version: Optional[str] = None) -> Dict[str, Any]:
        """Apply all pending migrations or up to target version"""
        pending_migrations = await self.get_pending_migrations()
        
        if target_version:
            pending_migrations = [
                (v, p) for v, p in pending_migrations 
                if v <= target_version
            ]
        
        if not pending_migrations:
            self.logger.info("No pending migrations to apply")
            return {'applied': 0, 'failed': 0, 'migrations': []}
        
        applied = 0
        failed = 0
        migration_results = []
        
        for version, file_path in pending_migrations:
            result = await self.apply_migration(version, file_path)
            migration_results.append({
                'version': version,
                'name': file_path.stem,
                'success': result
            })
            
            if result:
                applied += 1
            else:
                failed += 1
                break  # Stop on first failure
        
        self.logger.info(f"Migration complete: {applied} applied, {failed} failed")
        return {
            'applied': applied,
            'failed': failed,
            'migrations': migration_results
        }
    
    async def migrate_down(self, target_version: str) -> Dict[str, Any]:
        """Rollback migrations to target version"""
        applied_migrations = await self.get_applied_migrations()
        
        # Find migrations to rollback (in reverse order)
        to_rollback = [
            m for m in reversed(applied_migrations)
            if m['version'] > target_version
        ]
        
        if not to_rollback:
            self.logger.info(f"Already at or below version {target_version}")
            return {'rolled_back': 0, 'failed': 0, 'migrations': []}
        
        rolled_back = 0
        failed = 0
        migration_results = []
        
        for migration in to_rollback:
            result = await self.rollback_migration(migration['version'])
            migration_results.append({
                'version': migration['version'],
                'name': migration['name'],
                'success': result
            })
            
            if result:
                rolled_back += 1
            else:
                failed += 1
                break  # Stop on first failure
        
        self.logger.info(f"Rollback complete: {rolled_back} rolled back, {failed} failed")
        return {
            'rolled_back': rolled_back,
            'failed': failed,
            'migrations': migration_results
        }
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status"""
        applied_migrations = await self.get_applied_migrations()
        pending_migrations = await self.get_pending_migrations()
        integrity_issues = await self.check_migration_integrity()
        
        return {
            'applied_count': len(applied_migrations),
            'pending_count': len(pending_migrations),
            'latest_applied': applied_migrations[-1]['version'] if applied_migrations else None,
            'next_pending': pending_migrations[0][0] if pending_migrations else None,
            'integrity_issues': len(integrity_issues),
            'issues': integrity_issues
        }
    
    def create_migration(self, name: str, description: str = "") -> Path:
        """Create a new migration file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{name.lower().replace(' ', '_')}.py"
        file_path = self.migrations_dir / filename
        
        template = f'''"""
{description or f"Migration: {name}"}
Created: {datetime.utcnow().isoformat()}
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

# Migration metadata
description = "{description or name}"
depends_on = []  # List of migration versions this depends on
metadata = {{
    "author": "YMERA Migration System",
    "created_at": "{datetime.utcnow().isoformat()}",
    "category": "schema_change"
}}

async def upgrade(session: AsyncSession, engine: AsyncEngine):
    """Apply migration changes"""
    # TODO: Implement migration logic
    # Example:
    # await session.execute(text("""
    #     CREATE TABLE example (
    #         id SERIAL PRIMARY KEY,
    #         name VARCHAR(255) NOT NULL
    #     )
    # """))
    pass

async def downgrade(session: AsyncSession, engine: AsyncEngine):
    """Rollback migration changes"""
    # TODO: Implement rollback logic
    # Example:
    # await session.execute(text("DROP TABLE IF EXISTS example"))
    pass
'''
        
        file_path.write_text(template)
        self.logger.info(f"Created migration file: {file_path}")
        return file_path

# CLI-like interface for migrations
class MigrationCLI:
    """Command-line interface for migration management"""
    
    def __init__(self, migration_manager: MigrationManager):
        self.migration_manager = migration_manager
    
    async def status(self):
        """Show migration status"""
        status = await self.migration_manager.get_migration_status()
        print(f"Applied migrations: {status['applied_count']}")
        print(f"Pending migrations: {status['pending_count']}")
        print(f"Latest applied: {status['latest_applied'] or 'None'}")
        print(f"Next pending: {status['next_pending'] or 'None'}")
        print(f"Integrity issues: {status['integrity_issues']}")
        
        if status['issues']:
            print("\nIntegrity Issues:")
            for issue in status['issues']:
                print(f"  - {issue['type']}: {issue['message']}")
    
    async def migrate(self, target_version: Optional[str] = None):
        """Apply migrations"""
        result = await self.migration_manager.migrate_up(target_version)
        print(f"Applied {result['applied']} migrations")
        if result['failed'] > 0:
            print(f"Failed to apply {result['failed']} migrations")
    
    async def rollback(self, target_version: str):
        """Rollback migrations"""
        result = await self.migration_manager.migrate_down(target_version)
        print(f"Rolled back {result['rolled_back']} migrations")
        if result['failed'] > 0:
            print(f"Failed to rollback {result['failed']} migrations")
    
    async def create(self, name: str, description: str = ""):
        """Create new migration"""
        file_path = self.migration_manager.create_migration(name, description)
        print(f"Created migration: {file_path}")

async def history(self, limit: int = 10):
        """Show migration history"""
        applied_migrations = await self.migration_manager.get_applied_migrations()
        
        if not applied_migrations:
            print("No migrations have been applied yet.")
            return
        
        print(f"Migration History (last {min(limit, len(applied_migrations))}):")
        print("-" * 80)
        
        for migration in applied_migrations[-limit:]:
            print(f"Version: {migration['version']}")
            print(f"Name: {migration['name']}")
            print(f"Applied: {migration['applied_at']}")
            print(f"Execution Time: {migration['execution_time']}s")
            print(f"Checksum: {migration['checksum'][:16]}...")
            print("-" * 80)
    
    async def pending(self):
        """Show pending migrations"""
        pending_migrations = await self.migration_manager.get_pending_migrations()
        
        if not pending_migrations:
            print("No pending migrations.")
            return
        
        print(f"Pending Migrations ({len(pending_migrations)}):")
        print("-" * 60)
        
        for version, file_path in pending_migrations:
            try:
                migration_data = await self.migration_manager._load_migration(file_path)
                print(f"Version: {version}")
                print(f"Name: {file_path.stem}")
                print(f"Description: {migration_data.get('description', 'No description')}")
                print(f"File: {file_path}")
                print("-" * 60)
            except Exception as e:
                print(f"Version: {version} (Error loading: {str(e)})")
                print("-" * 60)
    
    async def validate(self):
        """Validate migration integrity"""
        issues = await self.migration_manager.check_migration_integrity()
        
        if not issues:
            print("✅ All migrations are valid and consistent.")
            return
        
        print(f"❌ Found {len(issues)} integrity issues:")
        print("-" * 60)
        
        for issue in issues:
            print(f"Type: {issue['type']}")
            print(f"Version: {issue['version']}")
            print(f"Message: {issue['message']}")
            print("-" * 60)
    
    async def reset(self, confirm: bool = False):
        """Reset migration state (WARNING: Destructive operation)"""
        if not confirm:
            print("⚠️  WARNING: This will remove all migration records!")
            print("Database schema will NOT be modified, only migration tracking.")
            print("Use --confirm flag to proceed.")
            return
        
        async with self.migration_manager.db_manager.get_session() as session:
            await session.execute(text("DELETE FROM schema_migrations"))
            await session.commit()
        
        print("✅ Migration state reset. All migration records removed.")

# Advanced Migration Features
class MigrationValidator:
    """Advanced migration validation and analysis"""
    
    def __init__(self, migration_manager: MigrationManager):
        self.migration_manager = migration_manager
        self.logger = logging.getLogger(__name__)
    
    async def check_dependency_chain(self) -> Dict[str, Any]:
        """Validate migration dependency chain"""
        discovered_migrations = self.migration_manager._discover_migrations()
        issues = []
        dependency_map = {}
        
        # Load all migrations and build dependency map
        for version, file_path in discovered_migrations:
            try:
                migration_data = await self.migration_manager._load_migration(file_path)
                dependency_map[version] = {
                    'depends_on': migration_data.get('depends_on', []),
                    'file_path': file_path
                }
            except Exception as e:
                issues.append({
                    'type': 'load_error',
                    'version': version,
                    'message': f'Failed to load migration: {str(e)}'
                })
        
        # Check for missing dependencies
        all_versions = set(dependency_map.keys())
        for version, data in dependency_map.items():
            for dep in data['depends_on']:
                if dep not in all_versions:
                    issues.append({
                        'type': 'missing_dependency',
                        'version': version,
                        'message': f'Depends on missing migration: {dep}'
                    })
        
        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies(dependency_map)
        for cycle in circular_deps:
            issues.append({
                'type': 'circular_dependency',
                'versions': cycle,
                'message': f'Circular dependency detected: {" -> ".join(cycle)}'
            })
        
        return {
            'issues': issues,
            'dependency_map': dependency_map,
            'has_issues': len(issues) > 0
        }
    
    def _detect_circular_dependencies(self, dependency_map: Dict[str, Dict]) -> List[List[str]]:
        """Detect circular dependencies using DFS"""
        def dfs(version, visited, rec_stack, path):
            visited.add(version)
            rec_stack.add(version)
            path.append(version)
            
            for dep in dependency_map.get(version, {}).get('depends_on', []):
                if dep not in visited:
                    cycle = dfs(dep, visited, rec_stack, path.copy())
                    if cycle:
                        return cycle
                elif dep in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep)
                    return path[cycle_start:] + [dep]
            
            rec_stack.remove(version)
            return None
        
        visited = set()
        cycles = []
        
        for version in dependency_map:
            if version not in visited:
                cycle = dfs(version, visited, set(), [])
                if cycle:
                    cycles.append(cycle)
        
        return cycles
    
    async def analyze_migration_complexity(self) -> Dict[str, Any]:
        """Analyze migration complexity and potential risks"""
        pending_migrations = await self.migration_manager.get_pending_migrations()
        analysis = {
            'total_migrations': len(pending_migrations),
            'risk_levels': {'low': 0, 'medium': 0, 'high': 0},
            'operations': {'create': 0, 'alter': 0, 'drop': 0, 'data': 0},
            'warnings': []
        }
        
        for version, file_path in pending_migrations:
            try:
                content = file_path.read_text().lower()
                migration_data = await self.migration_manager._load_migration(file_path)
                
                # Analyze SQL operations
                risk_level = 'low'
                
                if 'drop table' in content or 'drop column' in content:
                    analysis['operations']['drop'] += 1
                    risk_level = 'high'
                    analysis['warnings'].append(f'{version}: Contains DROP operations - data loss risk')
                
                if 'alter table' in content:
                    analysis['operations']['alter'] += 1
                    if risk_level != 'high':
                        risk_level = 'medium'
                
                if 'create table' in content or 'create index' in content:
                    analysis['operations']['create'] += 1
                
                if 'insert into' in content or 'update' in content or 'delete from' in content:
                    analysis['operations']['data'] += 1
                    if risk_level == 'low':
                        risk_level = 'medium'
                
                # Check for missing rollback
                if not migration_data.get('downgrade'):
                    analysis['warnings'].append(f'{version}: No rollback function defined')
                
                analysis['risk_levels'][risk_level] += 1
                
            except Exception as e:
                analysis['warnings'].append(f'{version}: Analysis failed - {str(e)}')
        
        return analysis

# Migration Backup and Recovery
class MigrationBackup:
    """Handle migration backups and recovery"""
    
    def __init__(self, migration_manager: MigrationManager, backup_dir: str = None):
        self.migration_manager = migration_manager
        self.backup_dir = Path(backup_dir or "ymera_core/database/backups")
        self.logger = logging.getLogger(__name__)
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self):
        """Ensure backup directory exists"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, name: str = None) -> Path:
        """Create a backup of current migration state"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"migration_backup_{timestamp}"
        backup_file = self.backup_dir / f"{backup_name}.json"
        
        # Get current state
        applied_migrations = await self.migration_manager.get_applied_migrations()
        status = await self.migration_manager.get_migration_status()
        
        backup_data = {
            'created_at': datetime.utcnow().isoformat(),
            'backup_name': backup_name,
            'applied_migrations': applied_migrations,
            'status': status,
            'database_type': self.migration_manager.db_manager.db_type
        }
        
        # Write backup file
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        self.logger.info(f"Created migration backup: {backup_file}")
        return backup_file
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups"""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.json"):
            try:
                with open(backup_file, 'r') as f:
                    backup_data = json.load(f)
                
                backups.append({
                    'name': backup_data.get('backup_name', backup_file.stem),
                    'created_at': backup_data.get('created_at'),
                    'applied_migrations': len(backup_data.get('applied_migrations', [])),
                    'file_path': backup_file
                })
            except Exception as e:
                self.logger.warning(f"Could not read backup {backup_file}: {str(e)}")
        
        return sorted(backups, key=lambda x: x['created_at'] or '', reverse=True)
    
    async def restore_backup(self, backup_name: str, confirm: bool = False) -> bool:
        """Restore from backup (WARNING: Destructive operation)"""
        if not confirm:
            self.logger.warning("Restore operation requires confirmation")
            return False
        
        backup_file = self.backup_dir / f"{backup_name}.json"
        if not backup_file.exists():
            self.logger.error(f"Backup file not found: {backup_file}")
            return False
        
        try:
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
            
            # Clear current migration state
            async with self.migration_manager.db_manager.get_session() as session:
                await session.execute(text("DELETE FROM schema_migrations"))
                
                # Restore migration records
                for migration in backup_data['applied_migrations']:
                    if self.migration_manager.db_manager.db_type == 'postgresql':
                        await session.execute(text("""
                            INSERT INTO schema_migrations (version, name, checksum, applied_at, execution_time)
                            VALUES (:version, :name, :checksum, :applied_at, :execution_time)
                        """), migration)
                    else:
                        await session.execute(text("""
                            INSERT INTO schema_migrations (version, name, checksum, applied_at, execution_time)
                            VALUES (?, ?, ?, ?, ?)
                        """), (
                            migration['version'],
                            migration['name'],
                            migration['checksum'],
                            migration['applied_at'],
                            migration['execution_time']
                        ))
                
                await session.commit()
            
            self.logger.info(f"Successfully restored backup: {backup_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {str(e)}")
            return False

# Migration Hooks and Events
class MigrationHooks:
    """Event hooks for migration operations"""
    
    def __init__(self):
        self.hooks = {
            'before_migrate': [],
            'after_migrate': [],
            'before_rollback': [],
            'after_rollback': [],
            'on_error': []
        }
    
    def register_hook(self, event: str, callback):
        """Register a hook for specific events"""
        if event in self.hooks:
            self.hooks[event].append(callback)
    
    async def execute_hooks(self, event: str, *args, **kwargs):
        """Execute all hooks for an event"""
        for hook in self.hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(*args, **kwargs)
                else:
                    hook(*args, **kwargs)
            except Exception as e:
                logging.getLogger(__name__).error(f"Hook execution failed: {str(e)}")

# Enhanced Migration Manager with additional features
class EnhancedMigrationManager(MigrationManager):
    """Enhanced migration manager with advanced features"""
    
    def __init__(self, db_manager, migrations_dir: str = None, backup_dir: str = None):
        super().__init__(db_manager, migrations_dir)
        self.validator = MigrationValidator(self)
        self.backup = MigrationBackup(self, backup_dir)
        self.hooks = MigrationHooks()
    
    async def safe_migrate(self, target_version: Optional[str] = None, 
                          create_backup: bool = True) -> Dict[str, Any]:
        """Safe migration with backup and validation"""
        # Create backup before migration
        backup_file = None
        if create_backup:
            backup_file = await self.backup.create_backup(
                f"pre_migration_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            )
        
        # Validate before migration
        validation_result = await self.validator.check_dependency_chain()
        if validation_result['has_issues']:
            return {
                'success': False,
                'error': 'Validation failed',
                'issues': validation_result['issues'],
                'backup_file': str(backup_file) if backup_file else None
            }
        
        # Analyze complexity
        complexity_analysis = await self.validator.analyze_migration_complexity()
        high_risk_count = complexity_analysis['risk_levels']['high']
        
        if high_risk_count > 0:
            self.logger.warning(f"Found {high_risk_count} high-risk migrations")
        
        try:
            # Execute hooks
            await self.hooks.execute_hooks('before_migrate', target_version)
            
            # Perform migration
            result = await self.migrate_up(target_version)
            
            # Execute success hooks
            await self.hooks.execute_hooks('after_migrate', result)
            
            return {
                'success': True,
                'result': result,
                'backup_file': str(backup_file) if backup_file else None,
                'complexity_analysis': complexity_analysis
            }
            
        except Exception as e:
            # Execute error hooks
            await self.hooks.execute_hooks('on_error', e)
            
            return {
                'success': False,
                'error': str(e),
                'backup_file': str(backup_file) if backup_file else None
            }

# Usage example and factory function
def create_migration_manager(db_manager, migrations_dir: str = None, 
                           backup_dir: str = None, enhanced: bool = True):
    """Factory function to create migration manager"""
    if enhanced:
        return EnhancedMigrationManager(db_manager, migrations_dir, backup_dir)
    else:
        return MigrationManager(db_manager, migrations_dir)

# Example usage
async def example_usage():
    """Example of how to use the migration system"""
    from ymera_core.database.manager import DatabaseManager
    
    # Initialize database manager (pseudo-code)
    db_manager = DatabaseManager()
    
    # Create enhanced migration manager
    migration_manager = create_migration_manager(
        db_manager, 
        migrations_dir="migrations",
        backup_dir="backups",
        enhanced=True
    )
    
    # Initialize
    await migration_manager.initialize()
    
    # Create CLI interface
    cli = MigrationCLI(migration_manager)
    
    # Example operations
    await cli.status()
    await cli.pending()
    
    # Safe migration with backup
    result = await migration_manager.safe_migrate()
    print(f"Migration result: {result}")
    
    # Register custom hooks
    async def custom_before_migrate_hook(target_version):
        print(f"About to migrate to version: {target_version}")
    
    migration_manager.hooks.register_hook('before_migrate', custom_before_migrate_hook)

if __name__ == "__main__":
    # Example CLI usage
    import sys
    
    async def main():
        # This would typically be integrated with your application's CLI
        if len(sys.argv) < 2:
            print("Usage: python migration_manager.py <command> [args]")
            return
        
        command = sys.argv[1]
        # Implementation would depend on your specific setup
        print(f"Would execute command: {command}")
    
    asyncio.run(main())