"""
YMERA Enterprise - Middleware Module
Production-Ready Middleware Management - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field

# Third-party imports (alphabetical)
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

# Local imports (alphabetical)
from .auth_middleware import AuthenticationMiddleware, AuthConfig
from .rate_limiter import RateLimitMiddleware, RateLimitConfig
from .cors_middleware import CORSMiddleware, CORSConfig
from .logging_middleware import LoggingMiddleware, LoggingConfig
from .error_handler import ErrorHandlerMiddleware, ErrorConfig
from .security_middleware import SecurityMiddleware, SecurityConfig

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.middleware")

# ===============================================================================
# MODULE METADATA
# ===============================================================================

__version__ = "4.0.0"
__author__ = "YMERA Enterprise Team"
__description__ = "Production-ready middleware management system"

# ===============================================================================
# MIDDLEWARE REGISTRY
# ===============================================================================

@dataclass
class MiddlewareConfig:
    """
    Comprehensive middleware configuration management.
    
    This class manages all middleware components and their configurations,
    providing centralized control over middleware behavior and ordering.
    """
    
    # Middleware enable/disable flags
    auth_enabled: bool = True
    rate_limit_enabled: bool = True
    cors_enabled: bool = True
    logging_enabled: bool = True
    error_handler_enabled: bool = True
    security_enabled: bool = True
    
    # Middleware configurations
    auth_config: Optional[AuthConfig] = None
    rate_limit_config: Optional[RateLimitConfig] = None
    cors_config: Optional[CORSConfig] = None
    logging_config: Optional[LoggingConfig] = None
    error_config: Optional[ErrorConfig] = None
    security_config: Optional[SecurityConfig] = None
    
    # Middleware ordering (lower numbers execute first)
    middleware_order: Dict[str, int] = field(default_factory=lambda: {
        "security": 1,      # Security checks first
        "cors": 2,          # CORS handling
        "rate_limit": 3,    # Rate limiting
        "auth": 4,          # Authentication
        "logging": 5,       # Request logging
        "error_handler": 6  # Error handling (last)
    })
    
    # Performance settings
    timeout_seconds: int = 30
    max_body_size: int = 16777216  # 16MB
    
    def __post_init__(self):
        """Initialize default configurations if not provided"""
        if self.auth_config is None and self.auth_enabled:
            self.auth_config = AuthConfig()
        
        if self.rate_limit_config is None and self.rate_limit_enabled:
            self.rate_limit_config = RateLimitConfig()
        
        if self.cors_config is None and self.cors_enabled:
            self.cors_config = CORSConfig()
        
        if self.logging_config is None and self.logging_enabled:
            self.logging_config = LoggingConfig()
        
        if self.error_config is None and self.error_handler_enabled:
            self.error_config = ErrorConfig()
        
        if self.security_config is None and self.security_enabled:
            self.security_config = SecurityConfig()

class MiddlewareRegistry:
    """
    Central registry for all middleware components.
    
    This class manages middleware registration, configuration, and provides
    methods for adding middleware to FastAPI applications in the correct order.
    """
    
    def __init__(self, config: MiddlewareConfig):
        self.config = config
        self.logger = logger.bind(component="MiddlewareRegistry")
        
        # Middleware instances
        self._middleware_instances: Dict[str, BaseHTTPMiddleware] = {}
        self._initialized = False
        
        # Performance metrics
        self._request_count = 0
        self._total_processing_time = 0.0
        self._error_count = 0
    
    def initialize_middleware(self) -> None:
        """Initialize all enabled middleware instances"""
        if self._initialized:
            return
        
        try:
            # Initialize middleware instances based on configuration
            if self.config.auth_enabled and self.config.auth_config:
                self._middleware_instances["auth"] = AuthenticationMiddleware(
                    config=self.config.auth_config
                )
            
            if self.config.rate_limit_enabled and self.config.rate_limit_config:
                self._middleware_instances["rate_limit"] = RateLimitMiddleware(
                    config=self.config.rate_limit_config
                )
            
            if self.config.cors_enabled and self.config.cors_config:
                self._middleware_instances["cors"] = CORSMiddleware(
                    config=self.config.cors_config
                )
            
            if self.config.logging_enabled and self.config.logging_config:
                self._middleware_instances["logging"] = LoggingMiddleware(
                    config=self.config.logging_config
                )
            
            if self.config.error_handler_enabled and self.config.error_config:
                self._middleware_instances["error_handler"] = ErrorHandlerMiddleware(
                    config=self.config.error_config
                )
            
            if self.config.security_enabled and self.config.security_config:
                self._middleware_instances["security"] = SecurityMiddleware(
                    config=self.config.security_config
                )
            
            self._initialized = True
            self.logger.info(
                "Middleware instances initialized",
                enabled_middleware=list(self._middleware_instances.keys())
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize middleware", error=str(e))
            raise
    
    def add_middleware_to_app(self, app: FastAPI) -> None:
        """
        Add all enabled middleware to FastAPI application in correct order.
        
        Args:
            app: FastAPI application instance
        """
        if not self._initialized:
            self.initialize_middleware()
        
        # Sort middleware by order (reverse order for FastAPI middleware stack)
        sorted_middleware = sorted(
            self._middleware_instances.items(),
            key=lambda x: self.config.middleware_order.get(x[0], 999),
            reverse=True  # FastAPI adds middleware in reverse order
        )
        
        for middleware_name, middleware_instance in sorted_middleware:
            try:
                app.add_middleware(
                    type(middleware_instance),
                    **middleware_instance.get_config_dict()
                )
                self.logger.debug(
                    "Middleware added to application",
                    middleware=middleware_name,
                    order=self.config.middleware_order.get(middleware_name, 999)
                )
            except Exception as e:
                self.logger.error(
                    "Failed to add middleware to application",
                    middleware=middleware_name,
                    error=str(e)
                )
                raise
        
        self.logger.info(
            "All middleware added to FastAPI application",
            middleware_count=len(sorted_middleware)
        )
    
    def get_middleware_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all middleware components.
        
        Returns:
            Dictionary containing middleware status and metrics
        """
        status = {
            "initialized": self._initialized,
            "enabled_middleware": list(self._middleware_instances.keys()),
            "middleware_count": len(self._middleware_instances),
            "metrics": {
                "total_requests": self._request_count,
                "total_processing_time": self._total_processing_time,
                "average_processing_time": (
                    self._total_processing_time / self._request_count
                    if self._request_count > 0 else 0
                ),
                "error_count": self._error_count
            },
            "individual_status": {}
        }
        
        # Get individual middleware status
        for name, middleware in self._middleware_instances.items():
            if hasattr(middleware, 'get_status'):
                status["individual_status"][name] = middleware.get_status()
            else:
                status["individual_status"][name] = {"status": "active"}
        
        return status
    
    def update_metrics(self, processing_time: float, has_error: bool = False) -> None:
        """
        Update middleware performance metrics.
        
        Args:
            processing_time: Request processing time in seconds
            has_error: Whether the request resulted in an error
        """
        self._request_count += 1
        self._total_processing_time += processing_time
        
        if has_error:
            self._error_count += 1
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics"""
        self._request_count = 0
        self._total_processing_time = 0.0
        self._error_count = 0
        self.logger.info("Middleware metrics reset")
    
    def get_middleware_instance(self, name: str) -> Optional[BaseHTTPMiddleware]:
        """
        Get specific middleware instance by name.
        
        Args:
            name: Middleware name
            
        Returns:
            Middleware instance or None if not found
        """
        return self._middleware_instances.get(name)
    
    def disable_middleware(self, name: str) -> bool:
        """
        Disable specific middleware component.
        
        Args:
            name: Middleware name to disable
            
        Returns:
            True if successfully disabled, False otherwise
        """
        if name in self._middleware_instances:
            del self._middleware_instances[name]
            self.logger.info("Middleware disabled", middleware=name)
            return True
        return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all middleware components.
        
        Returns:
            Health check results for all middleware
        """
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "middleware_health": {},
            "overall_metrics": self.get_middleware_status()["metrics"]
        }
        
        for name, middleware in self._middleware_instances.items():
            try:
                if hasattr(middleware, 'health_check'):
                    middleware_health = await middleware.health_check()
                    health_status["middleware_health"][name] = middleware_health
                else:
                    health_status["middleware_health"][name] = {
                        "status": "healthy",
                        "message": "No health check method available"
                    }
            except Exception as e:
                health_status["middleware_health"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
        
        return health_status
    
    async def cleanup(self) -> None:
        """Cleanup all middleware resources"""
        for name, middleware in self._middleware_instances.items():
            try:
                if hasattr(middleware, 'cleanup'):
                    await middleware.cleanup()
                self.logger.debug("Middleware cleaned up", middleware=name)
            except Exception as e:
                self.logger.error(
                    "Error cleaning up middleware",
                    middleware=name,
                    error=str(e)
                )
        
        self._middleware_instances.clear()
        self._initialized = False
        self.logger.info("All middleware cleaned up")

# ===============================================================================
# MIDDLEWARE FACTORY
# ===============================================================================

class MiddlewareFactory:
    """
    Factory class for creating and configuring middleware components.
    
    This class provides convenient methods for creating middleware with
    different configuration profiles and use cases.
    """
    
    @staticmethod
    def create_development_middleware() -> MiddlewareRegistry:
        """Create middleware configuration optimized for development"""
        config = MiddlewareConfig(
            auth_enabled=True,
            rate_limit_enabled=False,  # Disabled for development
            cors_enabled=True,
            logging_enabled=True,
            error_handler_enabled=True,
            security_enabled=True,
            cors_config=CORSConfig(
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            ),
            logging_config=LoggingConfig(
                log_level="DEBUG",
                log_requests=True,
                log_responses=True,
                include_body=True
            )
        )
        
        return MiddlewareRegistry(config)
    
    @staticmethod
    def create_production_middleware() -> MiddlewareRegistry:
        """Create middleware configuration optimized for production"""
        config = MiddlewareConfig(
            auth_enabled=True,
            rate_limit_enabled=True,
            cors_enabled=True,
            logging_enabled=True,
            error_handler_enabled=True,
            security_enabled=True,
            rate_limit_config=RateLimitConfig(
                requests_per_minute=1000,
                burst_size=50,
                enable_whitelist=True
            ),
            cors_config=CORSConfig(
                allow_origins=[
                    "https://yourdomain.com",
                    "https://app.yourdomain.com"
                ],
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_headers=["Authorization", "Content-Type"]
            ),
            logging_config=LoggingConfig(
                log_level="INFO",
                log_requests=True,
                log_responses=False,  # Don't log responses in production
                include_body=False    # Don't log request bodies
            )
        )
        
        return MiddlewareRegistry(config)
    
    @staticmethod
    def create_testing_middleware() -> MiddlewareRegistry:
        """Create middleware configuration optimized for testing"""
        config = MiddlewareConfig(
            auth_enabled=False,       # Disabled for easier testing
            rate_limit_enabled=False, # Disabled for testing
            cors_enabled=True,
            logging_enabled=False,    # Disabled to reduce test noise
            error_handler_enabled=True,
            security_enabled=False,   # Disabled for testing
            cors_config=CORSConfig(
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            )
        )
        
        return MiddlewareRegistry(config)
    
    @staticmethod
    def create_custom_middleware(
        auth_enabled: bool = True,
        rate_limit_enabled: bool = True,
        cors_enabled: bool = True,
        logging_enabled: bool = True,
        error_handler_enabled: bool = True,
        security_enabled: bool = True,
        **kwargs
    ) -> MiddlewareRegistry:
        """
        Create custom middleware configuration.
        
        Args:
            auth_enabled: Enable authentication middleware
            rate_limit_enabled: Enable rate limiting middleware
            cors_enabled: Enable CORS middleware
            logging_enabled: Enable logging middleware
            error_handler_enabled: Enable error handler middleware
            security_enabled: Enable security middleware
            **kwargs: Additional configuration parameters
            
        Returns:
            Configured middleware registry
        """
        config = MiddlewareConfig(
            auth_enabled=auth_enabled,
            rate_limit_enabled=rate_limit_enabled,
            cors_enabled=cors_enabled,
            logging_enabled=logging_enabled,
            error_handler_enabled=error_handler_enabled,
            security_enabled=security_enabled,
            **kwargs
        )
        
        return MiddlewareRegistry(config)

# ===============================================================================
# GLOBAL MIDDLEWARE INSTANCE
# ===============================================================================

# Global middleware registry instance
_middleware_registry: Optional[MiddlewareRegistry] = None

def get_middleware_registry() -> MiddlewareRegistry:
    """
    Get global middleware registry instance.
    
    Returns:
        Global middleware registry
    """
    global _middleware_registry
    
    if _middleware_registry is None:
        from config.settings import get_settings
        
        settings = get_settings()
        
        if settings.ENVIRONMENT == "production":
            _middleware_registry = MiddlewareFactory.create_production_middleware()
        elif settings.ENVIRONMENT == "testing":
            _middleware_registry = MiddlewareFactory.create_testing_middleware()
        else:
            _middleware_registry = MiddlewareFactory.create_development_middleware()
    
    return _middleware_registry

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def setup_middleware(
    app: FastAPI,
    environment: str = "development",
    custom_config: Optional[MiddlewareConfig] = None
) -> MiddlewareRegistry:
    """
    Setup middleware for FastAPI application.
    
    Args:
        app: FastAPI application instance
        environment: Deployment environment
        custom_config: Custom middleware configuration
        
    Returns:
        Configured middleware registry
    """
    if custom_config:
        registry = MiddlewareRegistry(custom_config)
    elif environment == "production":
        registry = MiddlewareFactory.create_production_middleware()
    elif environment == "testing":
        registry = MiddlewareFactory.create_testing_middleware()
    else:
        registry = MiddlewareFactory.create_development_middleware()
    
    # Add middleware to application
    registry.add_middleware_to_app(app)
    
    logger.info(
        "Middleware setup completed",
        environment=environment,
        middleware_count=len(registry._middleware_instances)
    )
    
    return registry

async def middleware_health_check() -> Dict[str, Any]:
    """
    Perform health check on global middleware registry.
    
    Returns:
        Health check results
    """
    registry = get_middleware_registry()
    return await registry.health_check()

def get_middleware_metrics() -> Dict[str, Any]:
    """
    Get middleware performance metrics.
    
    Returns:
        Performance metrics for all middleware
    """
    registry = get_middleware_registry()
    return registry.get_middleware_status()

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "MiddlewareConfig",
    "MiddlewareRegistry",
    "MiddlewareFactory",
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "CORSMiddleware",
    "LoggingMiddleware",
    "ErrorHandlerMiddleware",
    "SecurityMiddleware",
    "get_middleware_registry",
    "setup_middleware",
    "middleware_health_check",
    "get_middleware_metrics"
]