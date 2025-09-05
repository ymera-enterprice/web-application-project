"""
YMERA Enterprise - Main Application
Production-Ready FastAPI Application Entry Point - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import asyncio
import logging
import os
import signal
import sys
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party imports
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

# Local imports
from config.settings import get_settings
from database.connection import init_database, close_database
from learning.engine import LearningEngine
from learning.integration import AgentLearningIntegration
from agents.registry import AgentRegistry
from api.routers import (
    agents_router,
    learning_router,
    health_router,
    auth_router,
    analytics_router
)
from middleware.security import SecurityMiddleware
from middleware.rate_limiting import RateLimitMiddleware
from middleware.request_logging import RequestLoggingMiddleware
from utils.exceptions import YMERAException, setup_exception_handlers
from monitoring.performance_tracker import performance_tracker
from security.jwt_handler import jwt_handler

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("ymera.main")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

settings = get_settings()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'ymera_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'ymera_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

LEARNING_METRICS = Counter(
    'ymera_learning_events_total',
    'Total learning events processed',
    ['event_type', 'agent_id']
)

# ===============================================================================
# MIDDLEWARE CLASSES
# ===============================================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus metrics collection middleware"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = datetime.utcnow()
        
        # Extract route path for metrics
        endpoint = request.url.path
        method = request.method
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=status_code
            ).inc()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            return response
            
        except Exception as e:
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=500
            ).inc()
            
            logger.error(
                "Request processing failed",
                method=method,
                endpoint=endpoint,
                error=str(e),
                traceback=traceback.format_exc()
            )
            raise

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to all requests for tracing"""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        
        # Add to request state
        request.state.correlation_id = correlation_id
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response

# ===============================================================================
# APPLICATION LIFECYCLE MANAGEMENT
# ===============================================================================

class ApplicationState:
    """Global application state management"""
    
    def __init__(self):
        self.learning_engine: Optional[LearningEngine] = None
        self.agent_registry: Optional[AgentRegistry] = None
        self.agent_learning_integration: Optional[AgentLearningIntegration] = None
        self.background_tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize all application components"""
        try:
            logger.info("Initializing YMERA application components")
            
            # Initialize database
            await init_database()
            logger.info("Database initialized successfully")
            
            # Initialize learning engine
            self.learning_engine = LearningEngine()
            await self.learning_engine.initialize()
            logger.info("Learning engine initialized successfully")
            
            # Initialize agent registry
            self.agent_registry = AgentRegistry()
            await self.agent_registry.initialize()
            logger.info("Agent registry initialized successfully")
            
            # Initialize agent-learning integration
            self.agent_learning_integration = AgentLearningIntegration(
                learning_engine=self.learning_engine,
                agent_registry=self.agent_registry
            )
            await self.agent_learning_integration.initialize()
            logger.info("Agent-learning integration initialized successfully")
            
            # Start background learning processes
            await self._start_background_tasks()
            logger.info("Background learning processes started successfully")
            
            logger.info("YMERA application initialization completed successfully")
            
        except Exception as e:
            logger.critical(
                "Failed to initialize YMERA application",
                error=str(e),
                traceback=traceback.format_exc()
            )
            raise
    
    async def _start_background_tasks(self):
        """Start all background learning processes"""
        background_tasks = [
            self._create_task(
                self.learning_engine.continuous_learning_loop(),
                "continuous_learning_loop"
            ),
            self._create_task(
                self.learning_engine.inter_agent_knowledge_synchronization(),
                "inter_agent_synchronization"
            ),
            self._create_task(
                self.learning_engine.pattern_discovery_engine(),
                "pattern_discovery"
            ),
            self._create_task(
                self.learning_engine.external_learning_integration(),
                "external_learning"
            ),
            self._create_task(
                self.learning_engine.memory_consolidation_task(),
                "memory_consolidation"
            )
        ]
        
        self.background_tasks.extend(background_tasks)
        logger.info(f"Started {len(background_tasks)} background learning processes")
    
    def _create_task(self, coro, name: str) -> asyncio.Task:
        """Create a named background task with error handling"""
        async def wrapped_coro():
            try:
                await coro
            except asyncio.CancelledError:
                logger.info(f"Background task '{name}' was cancelled")
                raise
            except Exception as e:
                logger.error(
                    f"Background task '{name}' failed",
                    error=str(e),
                    traceback=traceback.format_exc()
                )
                # Re-raise to ensure task failure is noticed
                raise
        
        task = asyncio.create_task(wrapped_coro(), name=name)
        return task
    
    async def cleanup(self):
        """Cleanup all application resources"""
        try:
            logger.info("Starting YMERA application cleanup")
            
            # Signal shutdown to background tasks
            self.shutdown_event.set()
            
            # Cancel all background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            if self.background_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.background_tasks, return_exceptions=True),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Some background tasks did not complete within timeout")
            
            # Cleanup components
            if self.agent_learning_integration:
                await self.agent_learning_integration.cleanup()
            
            if self.agent_registry:
                await self.agent_registry.cleanup()
            
            if self.learning_engine:
                await self.learning_engine.cleanup()
            
            # Close database connections
            await close_database()
            
            logger.info("YMERA application cleanup completed successfully")
            
        except Exception as e:
            logger.error(
                "Error during application cleanup",
                error=str(e),
                traceback=traceback.format_exc()
            )

# Global application state
app_state = ApplicationState()

# ===============================================================================
# APPLICATION FACTORY
# ===============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    
    # Startup
    try:
        logger.info("Starting YMERA Enterprise Platform")
        await app_state.initialize()
        logger.info("YMERA Enterprise Platform started successfully")
        yield
    except Exception as e:
        logger.critical(
            "Failed to start YMERA Enterprise Platform",
            error=str(e),
            traceback=traceback.format_exc()
        )
        sys.exit(1)
    finally:
        # Shutdown
        logger.info("Shutting down YMERA Enterprise Platform")
        await app_state.cleanup()
        logger.info("YMERA Enterprise Platform shutdown completed")

def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    # Create FastAPI app
    app = FastAPI(
        title="YMERA Enterprise Platform",
        description="Advanced Multi-Agent Learning System with Continuous Intelligence",
        version="4.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan
    )
    
    # Configure middleware (order matters!)
    
    # Security middleware (first for security)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )
    
    app.add_middleware(SecurityMiddleware)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Custom middleware
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Configure routers
    app.include_router(health_router, prefix="/health", tags=["Health"])
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(agents_router, prefix="/agents", tags=["Agents"])
    app.include_router(learning_router, prefix="/learning", tags=["Learning"])
    app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler for unhandled errors"""
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        logger.error(
            "Unhandled exception",
            correlation_id=correlation_id,
            path=request.url.path,
            method=request.method,
            error=str(exc),
            traceback=traceback.format_exc()
        )
        
        if isinstance(exc, YMERAException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.error_code,
                    "message": exc.message,
                    "correlation_id": correlation_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return app

# ===============================================================================
# APPLICATION INSTANCE
# ===============================================================================

# Create the application instance
app = create_application()

# ===============================================================================
# SIGNAL HANDLERS
# ===============================================================================

def setup_signal_handlers():
    """Setup graceful shutdown signal handlers"""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        # Let the lifespan manager handle cleanup
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# ===============================================================================
# MAIN ENTRY POINT
# ===============================================================================

if __name__ == "__main__":
    # Setup signal handlers
    setup_signal_handlers()
    
    # Configure uvicorn
    uvicorn_config = {
        "app": "main:app",
        "host": settings.HOST,
        "port": settings.PORT,
        "workers": 1,  # Use 1 worker due to background tasks
        "loop": "uvloop",
        "http": "httptools",
        "log_config": None,  # Use our structured logging
        "access_log": False,  # Use our request logging middleware
        "server_header": False,
        "date_header": False,
    }
    
    # Add SSL config if certificates are provided
    if settings.SSL_CERT_FILE and settings.SSL_KEY_FILE:
        uvicorn_config.update({
            "ssl_certfile": settings.SSL_CERT_FILE,
            "ssl_keyfile": settings.SSL_KEY_FILE,
        })
    
    # Development vs Production configuration
    if settings.ENVIRONMENT == "development":
        uvicorn_config.update({
            "reload": True,
            "reload_dirs": ["./"],
            "log_level": "debug",
        })
    else:
        uvicorn_config.update({
            "log_level": "info",
        })
    
    logger.info(
        "Starting YMERA Enterprise Platform",
        environment=settings.ENVIRONMENT,
        host=settings.HOST,
        port=settings.PORT,
        ssl_enabled=bool(settings.SSL_CERT_FILE and settings.SSL_KEY_FILE)
    )
    
    # Run the application
    uvicorn.run(**uvicorn_config)