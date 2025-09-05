"""
YMERA System Initialization
Complete system startup and health checks
"""

import asyncio
import sys
import os
import signal
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import structlog
import uvloop
from pathlib import Path
import aiohttp
import psutil
from contextlib import asynccontextmanager

# Import your existing components
from main import (
    config, logger, Base,
    DatabaseManager, RedisManager, AIServiceManager, VectorDatabase,
    GlobalConfig, DatabaseConfig, RedisConfig, AIConfig, SecurityConfig, SystemConfig
)

class HealthStatus:
    """Health status tracking"""
    def __init__(self):
        self.components = {}
        self.overall_status = "unknown"
        self.startup_time = None
        self.last_check = None

class SystemInitializer:
    """Complete system initialization and health management"""
    
    def __init__(self):
        self.config = config
        self.logger = structlog.get_logger()
        self.health = HealthStatus()
        self.services = {}
        self.shutdown_handlers = []
        
        # Core service managers
        self.db_manager = None
        self.redis_manager = None
        self.ai_manager = None
        self.vector_db = None
        
        # Performance monitoring
        self.process = psutil.Process()
        self.startup_metrics = {}
    
    async def initialize_system(self) -> bool:
        """Initialize complete YMERA system"""
        self.logger.info("Starting YMERA system initialization...")
        start_time = time.time()
        
        try:
            # Set event loop policy
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            
            # Pre-initialization checks
            await self._pre_initialization_checks()
            
            # Initialize core services
            await self._initialize_core_services()
            
            # Initialize database
            await self._initialize_database()
            
            # Initialize cache layer
            await self._initialize_cache()
            
            # Initialize AI services
            await self._initialize_ai_services()
            
            # Initialize vector database
            await self._initialize_vector_database()
            
            # Post-initialization setup
            await self._post_initialization_setup()
            
            # Register shutdown handlers
            self._register_shutdown_handlers()
            
            # Final health check
            await self._perform_health_check()
            
            initialization_time = time.time() - start_time
            self.health.startup_time = initialization_time
            
            self.logger.info(
                f"YMERA system initialized successfully in {initialization_time:.2f}s",
                components=list(self.services.keys()),
                health_status=self.health.overall_status
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"System initialization failed: {e}", exc_info=True)
            await self._cleanup_on_failure()
            return False
    
    async def _pre_initialization_checks(self):
        """Perform pre-initialization system checks"""
        self.logger.info("Performing pre-initialization checks...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8+ required")
        
        # Check environment variables
        required_env_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY"
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {missing_vars}")
        
        # Check system resources
        memory_info = psutil.virtual_memory()
        if memory_info.available < 1024 * 1024 * 1024:  # 1GB
            self.logger.warning("Low memory available", available_gb=memory_info.available / (1024**3))
        
        disk_info = psutil.disk_usage('/')
        if disk_info.free < 5 * 1024 * 1024 * 1024:  # 5GB
            self.logger.warning("Low disk space", free_gb=disk_info.free / (1024**3))
        
        # Create necessary directories
        directories = [
            Path("logs"),
            Path("data"),
            Path("cache"),
            Path("temp")
        ]
        
        for directory in directories:
            directory.mkdir(exist_ok=True)
        
        self.logger.info("Pre-initialization checks completed")
    
    async def _initialize_core_services(self):
        """Initialize core system services"""
        self.logger.info("Initializing core services...")
        
        # Initialize database manager
        self.db_manager = DatabaseManager(self.config.database)
        self.services["database"] = self.db_manager
        
        # Initialize Redis manager
        self.redis_manager = RedisManager(self.config.redis)
        self.services["redis"] = self.redis_manager
        
        # Initialize AI service manager
        self.ai_manager = AIServiceManager(self.config.ai)
        self.services["ai"] = self.ai_manager
        
        # Initialize vector database
        self.vector_db = VectorDatabase(self.config.ai)
        self.services["vector_db"] = self.vector_db
        
        self.logger.info("Core services initialized")
    
    async def _initialize_database(self):
        """Initialize database with health checks"""
        self.logger.info("Initializing database...")
        
        try:
            await self.db_manager.initialize()
            
            # Test database connection
            async with self.db_manager.get_session() as session:
                await session.execute("SELECT 1")
            
            # Run migrations if needed
            await self._run_database_migrations()
            
            self.health.components["database"] = {
                "status": "healthy",
                "initialized_at": datetime.utcnow(),
                "connection_pool_size": self.config.database.pool_size
            }
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.health.components["database"] = {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow()
            }
            raise
    
    async def _initialize_cache(self):
        """Initialize Redis cache with health checks"""
        self.logger.info("Initializing cache layer...")
        
        try:
            await self.redis_manager.initialize()
            
            # Test Redis connection
            await self.redis_manager.ping()
            
            # Set up cache configurations
            await self._setup_cache_policies()
            
            # Warm up frequently accessed data
            await self._warm_up_cache()
            
            self.health.components["redis"] = {
                "status": "healthy",
                "initialized_at": datetime.utcnow(),
                "connection_pool_size": self.config.redis.pool_size,
                "cache_policies_loaded": True
            }
            
            self.logger.info("Cache layer initialized successfully")
            
        except Exception as e:
            self.health.components["redis"] = {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow()
            }
            raise
    
    async def _initialize_ai_services(self):
        """Initialize AI services with model loading"""
        self.logger.info("Initializing AI services...")
        
        try:
            await self.ai_manager.initialize()
            
            # Load and validate models
            await self._load_ai_models()
            
            # Test AI service connectivity
            await self._test_ai_services()
            
            self.health.components["ai"] = {
                "status": "healthy",
                "initialized_at": datetime.utcnow(),
                "models_loaded": len(self.ai_manager.loaded_models),
                "services_available": list(self.ai_manager.available_services.keys())
            }
            
            self.logger.info("AI services initialized successfully")
            
        except Exception as e:
            self.health.components["ai"] = {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow()
            }
            raise
    
    async def _initialize_vector_database(self):
        """Initialize vector database with index validation"""
        self.logger.info("Initializing vector database...")
        
        try:
            await self.vector_db.initialize()
            
            # Validate existing indices
            await self._validate_vector_indices()
            
            # Create missing indices if needed
            await self._create_missing_indices()
            
            self.health.components["vector_db"] = {
                "status": "healthy",
                "initialized_at": datetime.utcnow(),
                "indices_count": len(await self.vector_db.list_indices()),
                "dimension": self.config.ai.embedding_dimension
            }
            
            self.logger.info("Vector database initialized successfully")
            
        except Exception as e:
            self.health.components["vector_db"] = {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow()
            }
            raise
    
    async def _post_initialization_setup(self):
        """Perform post-initialization setup tasks"""
        self.logger.info("Performing post-initialization setup...")
        
        try:
            # Set up monitoring and metrics collection
            await self._setup_monitoring()
            
            # Initialize background tasks
            await self._initialize_background_tasks()
            
            # Load system configurations
            await self._load_system_configurations()
            
            # Set up security policies
            await self._apply_security_policies()
            
            self.logger.info("Post-initialization setup completed")
            
        except Exception as e:
            self.logger.error(f"Post-initialization setup failed: {e}")
            raise
    
    async def _run_database_migrations(self):
        """Run database migrations if needed"""
        try:
            # Check current migration version
            current_version = await self.db_manager.get_migration_version()
            
            # Get available migrations
            migrations_dir = Path("migrations")
            if migrations_dir.exists():
                migration_files = sorted(migrations_dir.glob("*.sql"))
                
                for migration_file in migration_files:
                    migration_version = int(migration_file.stem.split("_")[0])
                    
                    if migration_version > current_version:
                        self.logger.info(f"Running migration: {migration_file.name}")
                        await self.db_manager.run_migration(migration_file)
            
        except Exception as e:
            self.logger.error(f"Database migration failed: {e}")
            raise
    
    async def _setup_cache_policies(self):
        """Set up cache policies and TTL configurations"""
        cache_policies = {
            "user_sessions": {"ttl": 3600, "max_size": 10000},
            "api_responses": {"ttl": 300, "max_size": 5000},
            "model_outputs": {"ttl": 1800, "max_size": 2000},
            "system_config": {"ttl": 86400, "max_size": 100}
        }
        
        for policy_name, config in cache_policies.items():
            await self.redis_manager.set_cache_policy(policy_name, config)
    
    async def _warm_up_cache(self):
        """Warm up cache with frequently accessed data"""
        try:
            # Load system configurations
            system_configs = await self.db_manager.get_system_configurations()
            for config_key, config_value in system_configs.items():
                await self.redis_manager.set(f"config:{config_key}", config_value, ttl=86400)
            
            # Pre-load user permission mappings
            await self._preload_user_permissions()
            
        except Exception as e:
            self.logger.warning(f"Cache warm-up failed: {e}")
    
    async def _load_ai_models(self):
        """Load and validate AI models"""
        required_models = self.config.ai.required_models
        
        for model_name in required_models:
            try:
                await self.ai_manager.load_model(model_name)
                self.logger.info(f"Model loaded successfully: {model_name}")
            except Exception as e:
                self.logger.error(f"Failed to load model {model_name}: {e}")
                if self.config.ai.strict_model_loading:
                    raise
    
    async def _test_ai_services(self):
        """Test AI service connectivity and functionality"""
        test_requests = [
            {"service": "text_generation", "prompt": "Test prompt"},
            {"service": "embeddings", "text": "Test embedding"},
            {"service": "classification", "text": "Test classification"}
        ]
        
        for test_request in test_requests:
            try:
                await self.ai_manager.process_request(test_request)
            except Exception as e:
                self.logger.warning(f"AI service test failed: {test_request['service']}: {e}")
    
    async def _validate_vector_indices(self):
        """Validate existing vector database indices"""
        required_indices = self.config.ai.required_indices
        existing_indices = await self.vector_db.list_indices()
        
        for index_name in required_indices:
            if index_name not in existing_indices:
                self.logger.warning(f"Missing vector index: {index_name}")
            else:
                # Validate index configuration
                index_info = await self.vector_db.get_index_info(index_name)
                if index_info.get("dimension") != self.config.ai.embedding_dimension:
                    self.logger.warning(f"Index dimension mismatch: {index_name}")
    
    async def _create_missing_indices(self):
        """Create missing vector database indices"""
        required_indices = self.config.ai.required_indices
        existing_indices = await self.vector_db.list_indices()
        
        for index_name in required_indices:
            if index_name not in existing_indices:
                try:
                    await self.vector_db.create_index(
                        name=index_name,
                        dimension=self.config.ai.embedding_dimension,
                        metric="cosine"
                    )
                    self.logger.info(f"Created vector index: {index_name}")
                except Exception as e:
                    self.logger.error(f"Failed to create index {index_name}: {e}")
    
    async def _setup_monitoring(self):
        """Set up system monitoring and metrics collection"""
        try:
            # Initialize metrics collectors
            self.startup_metrics = {
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "disk_total": psutil.disk_usage('/').total,
                "python_version": sys.version,
                "startup_time": datetime.utcnow()
            }
            
            # Set up periodic health checks
            asyncio.create_task(self._periodic_health_checks())
            
        except Exception as e:
            self.logger.warning(f"Monitoring setup failed: {e}")
    
    async def _initialize_background_tasks(self):
        """Initialize background tasks"""
        background_tasks = [
            self._cleanup_expired_sessions(),
            self._update_system_metrics(),
            self._backup_critical_data(),
            self._optimize_database_connections()
        ]
        
        for task in background_tasks:
            asyncio.create_task(task)
    
    async def _load_system_configurations(self):
        """Load system-wide configurations"""
        try:
            configs = await self.db_manager.load_system_configs()
            for config_key, config_value in configs.items():
                setattr(self.config.system, config_key, config_value)
                
        except Exception as e:
            self.logger.warning(f"System configuration loading failed: {e}")
    
    async def _apply_security_policies(self):
        """Apply security policies and configurations"""
        try:
            # Set up rate limiting
            await self._setup_rate_limiting()
            
            # Configure security headers
            await self._configure_security_headers()
            
            # Initialize audit logging
            await self._initialize_audit_logging()
            
        except Exception as e:
            self.logger.error(f"Security policy application failed: {e}")
    
    async def _preload_user_permissions(self):
        """Pre-load user permissions for faster access"""
        try:
            permissions = await self.db_manager.get_all_user_permissions()
            for user_id, perms in permissions.items():
                cache_key = f"permissions:{user_id}"
                await self.redis_manager.set(cache_key, perms, ttl=3600)
                
        except Exception as e:
            self.logger.warning(f"User permissions preloading failed: {e}")
    
    async def _setup_rate_limiting(self):
        """Set up API rate limiting policies"""
        rate_limits = {
            "api_general": {"requests": 1000, "window": 3600},
            "api_ai": {"requests": 100, "window": 3600},
            "auth": {"requests": 10, "window": 60}
        }
        
        for limit_name, config in rate_limits.items():
            await self.redis_manager.set_rate_limit(limit_name, config)
    
    async def _configure_security_headers(self):
        """Configure security headers and policies"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
        }
        
        await self.redis_manager.set("security_headers", security_headers)
    
    async def _initialize_audit_logging(self):
        """Initialize audit logging system"""
        audit_config = {
            "enabled": True,
            "log_level": "INFO",
            "retention_days": 90,
            "events": ["auth", "data_access", "system_changes"]
        }
        
        await self.redis_manager.set("audit_config", audit_config)
    
    def _register_shutdown_handlers(self):
        """Register graceful shutdown handlers"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.graceful_shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _perform_health_check(self):
        """Perform comprehensive health check"""
        self.logger.info("Performing system health check...")
        
        health_checks = [
            self._check_database_health(),
            self._check_redis_health(),
            self._check_ai_services_health(),
            self._check_vector_db_health(),
            self._check_system_resources()
        ]
        
        results = await asyncio.gather(*health_checks, return_exceptions=True)
        
        healthy_components = 0
        total_components = len(results)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Health check failed: {result}")
            else:
                healthy_components += 1
        
        if healthy_components == total_components:
            self.health.overall_status = "healthy"
        elif healthy_components > total_components // 2:
            self.health.overall_status = "degraded"
        else:
            self.health.overall_status = "unhealthy"
        
        self.health.last_check = datetime.utcnow()
        
        self.logger.info(
            f"Health check completed: {self.health.overall_status}",
            healthy_components=healthy_components,
            total_components=total_components
        )
    
    async def _check_database_health(self):
        """Check database health"""
        try:
            async with self.db_manager.get_session() as session:
                result = await session.execute("SELECT COUNT(*) FROM information_schema.tables")
                return result.scalar() > 0
        except Exception as e:
            self.health.components["database"]["status"] = "unhealthy"
            self.health.components["database"]["error"] = str(e)
            raise
    
    async def _check_redis_health(self):
        """Check Redis health"""
        try:
            pong = await self.redis_manager.ping()
            return pong is True
        except Exception as e:
            self.health.components["redis"]["status"] = "unhealthy"
            self.health.components["redis"]["error"] = str(e)
            raise
    
    async def _check_ai_services_health(self):
        """Check AI services health"""
        try:
            status = await self.ai_manager.health_check()
            return status.get("overall_status") == "healthy"
        except Exception as e:
            self.health.components["ai"]["status"] = "unhealthy"
            self.health.components["ai"]["error"] = str(e)
            raise
    
    async def _check_vector_db_health(self):
        """Check vector database health"""
        try:
            indices = await self.vector_db.list_indices()
            return len(indices) > 0
        except Exception as e:
            self.health.components["vector_db"]["status"] = "unhealthy"
            self.health.components["vector_db"]["error"] = str(e)
            raise
    
    async def _check_system_resources(self):
        """Check system resource utilization"""
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)
        disk_usage = psutil.disk_usage('/').percent
        
        if memory_usage > 90 or cpu_usage > 90 or disk_usage > 90:
            self.logger.warning(
                "High resource utilization",
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                disk_usage=disk_usage
            )
            return False
        
        return True
    
    async def _periodic_health_checks(self):
        """Run periodic health checks"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._perform_health_check()
            except Exception as e:
                self.logger.error(f"Periodic health check failed: {e}")
    
    async def _cleanup_expired_sessions(self):
        """Background task to cleanup expired sessions"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                expired_count = await self.redis_manager.cleanup_expired_keys("session:*")
                if expired_count > 0:
                    self.logger.info(f"Cleaned up {expired_count} expired sessions")
            except Exception as e:
                self.logger.error(f"Session cleanup failed: {e}")
    
    async def _update_system_metrics(self):
        """Background task to update system metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Update every minute
                metrics = {
                    "cpu_usage": psutil.cpu_percent(),
                    "memory_usage": psutil.virtual_memory().percent,
                    "disk_usage": psutil.disk_usage('/').percent,
                    "active_connections": len(self.db_manager.active_connections),
                    "redis_memory": await self.redis_manager.get_memory_usage(),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await self.redis_manager.set("system_metrics", metrics, ttl=3600)
            except Exception as e:
                self.logger.error(f"Metrics update failed: {e}")
    
    async def _backup_critical_data(self):
        """Background task for critical data backup"""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily backup
                backup_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                
                # Backup system configurations
                configs = await self.db_manager.get_system_configurations()
                backup_file = Path(f"backups/config_backup_{backup_timestamp}.json")
                backup_file.parent.mkdir(exist_ok=True)
                
                with open(backup_file, 'w') as f:
                    import json
                    json.dump(configs, f, indent=2, default=str)
                
                self.logger.info(f"Critical data backup completed: {backup_file}")
                
            except Exception as e:
                self.logger.error(f"Backup failed: {e}")
    
    async def _optimize_database_connections(self):
        """Background task to optimize database connections"""
        while True:
            try:
                await asyncio.sleep(1800)  # Every 30 minutes
                await self.db_manager.optimize_connections()
                self.logger.debug("Database connections optimized")
            except Exception as e:
                self.logger.error(f"Connection optimization failed: {e}")
    
    async def _cleanup_on_failure(self):
        """Cleanup resources on initialization failure"""
        self.logger.info("Performing cleanup after initialization failure...")
        
        cleanup_tasks = []
        
        if self.db_manager:
            cleanup_tasks.append(self.db_manager.cleanup())
        
        if self.redis_manager:
            cleanup_tasks.append(self.redis_manager.cleanup())
        
        if self.ai_manager:
            cleanup_tasks.append(self.ai_manager.cleanup())
        
        if self.vector_db:
            cleanup_tasks.append(self.vector_db.cleanup())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.logger.info("Cleanup completed")
    
    async def graceful_shutdown(self):
        """Perform graceful system shutdown"""
        self.logger.info("Starting graceful shutdown...")
        
        try:
            # Stop accepting new requests
            self.health.overall_status = "shutting_down"
            
            # Cancel background tasks
            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            for task in tasks:
                if task != asyncio.current_task():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            if tasks:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0
                )
            
            # Shutdown services in reverse order
            shutdown_order = ["vector_db", "ai", "redis", "database"]
            
            for service_name in shutdown_order:
                if service_name in self.services:
                    try:
                        await self.services[service_name].shutdown()
                        self.logger.info(f"Service {service_name} shutdown completed")
                    except Exception as e:
                        self.logger.error(f"Error shutting down {service_name}: {e}")
            
            self.logger.info("Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")
        finally:
            sys.exit(0)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        return {
            "overall_status": self.health.overall_status,
            "startup_time": self.health.startup_time,
            "last_check": self.health.last_check,
            "components": self.health.components,
            "system_metrics": self.startup_metrics
        }


# Main initialization function
async def initialize_ymera() -> SystemInitializer:
    """Initialize YMERA system and return initializer instance"""
    initializer = SystemInitializer()
    
    success = await initializer.initialize_system()
    
    if not success:
        raise RuntimeError("YMERA system initialization failed")
    
    return initializer


# Entry point for standalone execution
if __name__ == "__main__":
    async def main():
        try:
            initializer = await initialize_ymera()
            
            # Keep the system running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\nShutdown signal received...")
        except Exception as e:
            print(f"System error: {e}")
        finally:
            if 'initializer' in locals():
                await initializer.graceful_shutdown()
    
    # Run the system
    asyncio.run(main())