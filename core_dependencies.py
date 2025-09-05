"""
YMERA Enterprise API Dependencies - Core Dependencies Manager
Production-ready dependency injection system with health monitoring and lifecycle management
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, List, AsyncGenerator
import asyncio
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import functools
from dataclasses import dataclass
import weakref
import sys
import traceback

from ymera_core.config import ConfigManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.message_queue.redis_queue import RedisMessageQueue
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.monitoring.health_monitor import HealthMonitor
from ymera_core.metrics.collector import MetricsCollector
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.security.auth_manager import AuthManager
from ymera_agents.orchestrator import AgentOrchestrator
from ymera_agents.registry import AgentRegistry
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.learning.knowledge_base import KnowledgeBase
from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_services.vector_db.pinecone_manager import PineconeManager
from ymera_services.github.repository_analyzer import GitHubRepositoryAnalyzer
from ymera_core.exceptions import YMERAException


@dataclass
class DependencyHealth:
    """Health status for individual dependencies"""
    name: str
    healthy: bool
    last_check: datetime
    error_message: Optional[str] = None
    response_time_ms: float = 0.0
    consecutive_failures: int = 0


class DependencyManager:
    """
    Enterprise-grade dependency manager with health monitoring, 
    circuit breaker patterns, and automatic recovery
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ymera.dependencies")
        self._dependencies: Dict[str, Any] = {}
        self._health_status: Dict[str, DependencyHealth] = {}
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self._dependency_locks: Dict[str, asyncio.Lock] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        self._monitoring_enabled = True
        self._initialization_complete = False
        
        # Circuit breaker configuration
        self._circuit_breaker_config = {
            'failure_threshold': 5,
            'timeout_seconds': 60,
            'half_open_max_calls': 3
        }
        
    async def initialize(self, system_components):
        """Initialize dependency manager with system components"""
        try:
            self.logger.info("Initializing enterprise dependency manager...")
            
            # Store system components
            self._system = system_components
            
            # Register core dependencies
            await self._register_dependencies()
            
            # Start health monitoring
            if self._monitoring_enabled:
                await self._start_health_monitoring()
            
            self._initialization_complete = True
            self.logger.info("✅ Dependency manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize dependency manager: {str(e)}")
            raise YMERAException(
                message="Dependency manager initialization failed",
                error_code="DEPENDENCY_INIT_ERROR",
                details={"error": str(e)}
            )
    
    async def _register_dependencies(self):
        """Register all system dependencies with health checks"""
        dependencies = {
            'config_manager': self._system.config_manager,
            'db_manager': self._system.db_manager,
            'cache_manager': self._system.cache_manager,
            'message_queue': self._system.message_queue,
            'auth_manager': self._system.auth_manager,
            'health_monitor': self._system.health_monitor,
            'metrics_collector': self._system.metrics_collector,
            'llm_manager': self._system.llm_manager,
            'vector_db': self._system.vector_db,
            'github_analyzer': self._system.github_analyzer,
            'agent_orchestrator': self._system.agent_orchestrator,
            'agent_registry': self._system.agent_registry,
            'learning_engine': self._system.learning_engine,
            'knowledge_base': self._system.knowledge_base,
            'logger': self._system.logger
        }
        
        for name, dependency in dependencies.items():
            if dependency is not None:
                await self._register_dependency(name, dependency)
    
    async def _register_dependency(self, name: str, dependency: Any):
        """Register a single dependency with circuit breaker"""
        try:
            self._dependencies[name] = dependency
            self._dependency_locks[name] = asyncio.Lock()
            
            # Initialize circuit breaker
            self._circuit_breakers[name] = {
                'state': 'CLOSED',  # CLOSED, OPEN, HALF_OPEN
                'failure_count': 0,
                'last_failure_time': None,
                'successful_calls': 0
            }
            
            # Initialize health status
            self._health_status[name] = DependencyHealth(
                name=name,
                healthy=True,
                last_check=datetime.utcnow()
            )
            
            self.logger.debug(f"Registered dependency: {name}")
            
        except Exception as e:
            self.logger.error(f"Failed to register dependency {name}: {str(e)}")
            raise
    
    async def _start_health_monitoring(self):
        """Start continuous health monitoring for all dependencies"""
        for name in self._dependencies.keys():
            task = asyncio.create_task(self._monitor_dependency_health(name))
            self._health_check_tasks[name] = task
            
        self.logger.info(f"Started health monitoring for {len(self._dependencies)} dependencies")
    
    async def _monitor_dependency_health(self, name: str):
        """Continuous health monitoring for a specific dependency"""
        while self._monitoring_enabled:
            try:
                await self._check_dependency_health(name)
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error for {name}: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_dependency_health(self, name: str):
        """Check health of a specific dependency"""
        start_time = datetime.utcnow()
        
        try:
            dependency = self._dependencies[name]
            
            # Perform health check based on dependency type
            if hasattr(dependency, 'health_check'):
                await dependency.health_check()
            elif hasattr(dependency, 'ping'):
                await dependency.ping()
            elif name == 'db_manager':
                async with dependency.get_session() as session:
                    await session.execute("SELECT 1")
            elif name == 'cache_manager':
                await dependency.ping()
            elif name == 'message_queue':
                await dependency.health_check()
            
            # Calculate response time
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update health status
            self._health_status[name] = DependencyHealth(
                name=name,
                healthy=True,
                last_check=datetime.utcnow(),
                response_time_ms=response_time,
                consecutive_failures=0
            )
            
            # Reset circuit breaker on success
            await self._reset_circuit_breaker(name)
            
        except Exception as e:
            # Update health status with failure
            current_health = self._health_status.get(name)
            consecutive_failures = current_health.consecutive_failures + 1 if current_health else 1
            
            self._health_status[name] = DependencyHealth(
                name=name,
                healthy=False,
                last_check=datetime.utcnow(),
                error_message=str(e),
                consecutive_failures=consecutive_failures
            )
            
            # Update circuit breaker
            await self._record_failure(name)
            
            self.logger.warning(
                f"Health check failed for {name}: {str(e)}", 
                extra={
                    "dependency": name,
                    "consecutive_failures": consecutive_failures,
                    "error": str(e)
                }
            )
    
    async def _reset_circuit_breaker(self, name: str):
        """Reset circuit breaker on successful operation"""
        circuit_breaker = self._circuit_breakers[name]
        circuit_breaker['failure_count'] = 0
        circuit_breaker['successful_calls'] += 1
        
        if circuit_breaker['state'] == 'HALF_OPEN':
            if circuit_breaker['successful_calls'] >= self._circuit_breaker_config['half_open_max_calls']:
                circuit_breaker['state'] = 'CLOSED'
                circuit_breaker['successful_calls'] = 0
                self.logger.info(f"Circuit breaker for {name} reset to CLOSED")
    
    async def _record_failure(self, name: str):
        """Record failure and update circuit breaker state"""
        circuit_breaker = self._circuit_breakers[name]
        circuit_breaker['failure_count'] += 1
        circuit_breaker['last_failure_time'] = datetime.utcnow()
        
        if (circuit_breaker['failure_count'] >= self._circuit_breaker_config['failure_threshold'] 
            and circuit_breaker['state'] == 'CLOSED'):
            circuit_breaker['state'] = 'OPEN'
            self.logger.warning(f"Circuit breaker for {name} opened due to failures")
    
    async def _check_circuit_breaker(self, name: str) -> bool:
        """Check if circuit breaker allows operation"""
        circuit_breaker = self._circuit_breakers[name]
        
        if circuit_breaker['state'] == 'CLOSED':
            return True
        elif circuit_breaker['state'] == 'OPEN':
            # Check if timeout period has passed
            if circuit_breaker['last_failure_time']:
                time_since_failure = datetime.utcnow() - circuit_breaker['last_failure_time']
                if time_since_failure.seconds >= self._circuit_breaker_config['timeout_seconds']:
                    circuit_breaker['state'] = 'HALF_OPEN'
                    circuit_breaker['successful_calls'] = 0
                    self.logger.info(f"Circuit breaker for {name} moved to HALF_OPEN")
                    return True
            return False
        else:  # HALF_OPEN
            return True
    
    async def get_dependency(self, name: str, required: bool = True):
        """Get dependency with circuit breaker protection"""
        if not self._initialization_complete:
            raise YMERAException(
                message="Dependency manager not initialized",
                error_code="DEPENDENCY_NOT_INITIALIZED"
            )
        
        if name not in self._dependencies:
            if required:
                raise YMERAException(
                    message=f"Required dependency '{name}' not found",
                    error_code="DEPENDENCY_NOT_FOUND",
                    details={"dependency": name}
                )
            return None
        
        # Check circuit breaker
        if not await self._check_circuit_breaker(name):
            if required:
                raise YMERAException(
                    message=f"Dependency '{name}' unavailable (circuit breaker open)",
                    error_code="DEPENDENCY_CIRCUIT_BREAKER_OPEN",
                    details={"dependency": name}
                )
            return None
        
        # Check health status
        health = self._health_status.get(name)
        if health and not health.healthy and required:
            self.logger.warning(
                f"Accessing unhealthy dependency: {name}",
                extra={
                    "dependency": name,
                    "consecutive_failures": health.consecutive_failures,
                    "last_error": health.error_message
                }
            )
        
        return self._dependencies[name]
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of all dependencies"""
        healthy_count = sum(1 for h in self._health_status.values() if h.healthy)
        total_count = len(self._health_status)
        
        return {
            "overall_healthy": healthy_count == total_count,
            "healthy_dependencies": healthy_count,
            "total_dependencies": total_count,
            "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 100,
            "dependencies": {
                name: {
                    "healthy": health.healthy,
                    "last_check": health.last_check.isoformat(),
                    "response_time_ms": health.response_time_ms,
                    "consecutive_failures": health.consecutive_failures,
                    "error_message": health.error_message,
                    "circuit_breaker_state": self._circuit_breakers.get(name, {}).get('state', 'UNKNOWN')
                }
                for name, health in self._health_status.items()
            }
        }
    
    async def force_health_check(self, dependency_name: Optional[str] = None):
        """Force immediate health check for specific dependency or all"""
        if dependency_name:
            if dependency_name in self._dependencies:
                await self._check_dependency_health(dependency_name)
            else:
                raise YMERAException(
                    message=f"Dependency '{dependency_name}' not found",
                    error_code="DEPENDENCY_NOT_FOUND"
                )
        else:
            # Check all dependencies
            tasks = [
                self._check_dependency_health(name) 
                for name in self._dependencies.keys()
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def shutdown(self):
        """Shutdown dependency manager and clean up resources"""
        self.logger.info("Shutting down dependency manager...")
        
        # Stop monitoring
        self._monitoring_enabled = False
        
        # Cancel health check tasks
        for task in self._health_check_tasks.values():
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._health_check_tasks:
            await asyncio.gather(*self._health_check_tasks.values(), return_exceptions=True)
        
        self.logger.info("✅ Dependency manager shutdown complete")


# Global dependency manager instance
dependency_manager = DependencyManager()


# Dependency injection decorators and functions
def with_dependency_monitoring(dependency_name: str):
    """Decorator to add dependency monitoring to functions"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Record dependency usage
                start_time = datetime.utcnow()
                result = await func(*args, **kwargs)
                
                # Log successful usage
                duration = (datetime.utcnow() - start_time).total_seconds() * 1000
                logging.getLogger("ymera.dependencies").debug(
                    f"Dependency {dependency_name} used successfully",
                    extra={
                        "dependency": dependency_name,
                        "duration_ms": duration,
                        "function": func.__name__
                    }
                )
                
                return result
                
            except Exception as e:
                # Log dependency usage failure
                logging.getLogger("ymera.dependencies").error(
                    f"Dependency {dependency_name} usage failed",
                    extra={
                        "dependency": dependency_name,
                        "function": func.__name__,
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                )
                raise
        
        return wrapper
    return decorator


@asynccontextmanager
async def dependency_context(dependency_names: List[str], required: bool = True) -> AsyncGenerator[Dict[str, Any], None]:
    """Context manager for accessing multiple dependencies safely"""
    dependencies = {}
    
    try:
        # Acquire all dependencies
        for name in dependency_names:
            dependency = await dependency_manager.get_dependency(name, required=required)
            if dependency is not None:
                dependencies[name] = dependency
        
        yield dependencies
        
    except Exception as e:
        logging.getLogger("ymera.dependencies").error(
            f"Error in dependency context: {str(e)}",
            extra={
                "dependencies": dependency_names,
                "error": str(e)
            }
        )
        raise
    
    finally:
        # Cleanup if needed
        pass


# Core dependency functions
async def get_dependency_manager() -> DependencyManager:
    """Get the global dependency manager instance"""
    return dependency_manager


async def get_config_manager() -> ConfigManager:
    """Get configuration manager dependency"""
    return await dependency_manager.get_dependency('config_manager')


async def get_database_manager() -> DatabaseManager:
    """Get database manager dependency"""
    return await dependency_manager.get_dependency('db_manager')


async def get_cache_manager() -> RedisCacheManager:
    """Get cache manager dependency"""
    return await dependency_manager.get_dependency('cache_manager')


async def get_auth_manager() -> AuthManager:
    """Get authentication manager dependency"""
    return await dependency_manager.get_dependency('auth_manager')


async def get_logger() -> StructuredLogger:
    """Get structured logger dependency"""
    return await dependency_manager.get_dependency('logger')


async def get_health_monitor() -> HealthMonitor:
    """Get health monitor dependency"""
    return await dependency_manager.get_dependency('health_monitor')


async def get_metrics_collector() -> MetricsCollector:
    """Get metrics collector dependency"""
    return await dependency_manager.get_dependency('metrics_collector')
