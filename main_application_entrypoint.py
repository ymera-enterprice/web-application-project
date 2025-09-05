“””
YMERA Enterprise Multi-Agent Platform - Main Application
Production-ready FastAPI application with complete middleware stack
“””

import asyncio
import os
import sys
import signal
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
import traceback

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
import structlog

# Import YMERA components

from ymera_middleware import (
SecurityManager, FileSecurityManager, AuditLogger, PermissionManager,
SecurityConfig, create_security_middleware
)
from ymera_routing import YMERAAPIGateway, create_gateway
from ymera_database_advanced import DatabaseManager, UserRepository, ProjectRepository
from additional_components import (
APIKeyManager, SecureVault, AdvancedCacheManager,
IntelligentTaskQueue, SystemHealthMonitor, EventBus,
BrowserManager, ComponentRegistry
)

# Configure structured logging

logging.basicConfig(level=logging.INFO)
structlog.configure(
processors=[
structlog.processors.TimeStamper(fmt=“ISO”),
structlog.processors.add_log_level,
structlog.processors.StackInfoRenderer(),
structlog.dev.ConsoleRenderer()
],
wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
logger_factory=structlog.PrintLoggerFactory(),
cache_logger_on_first_use=True,
)

logger = structlog.get_logger(“ymera.main”)

# ===================== CONFIGURATION =====================

class YMERAConfig:
“”“Central configuration management”””

```
def __init__(self):
    # Database Configuration
    self.DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:password@localhost/ymera_db"
    )
    
    # Redis Configuration
    self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Security Configuration
    self.JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
    self.ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", None)
    
    # File Storage
    self.STORAGE_PATH = os.getenv("STORAGE_PATH", "/tmp/ymera_files")
    self.MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB
    
    # API Configuration
    self.API_HOST = os.getenv("API_HOST", "0.0.0.0")
    self.API_PORT = int(os.getenv("API_PORT", 8000))
    self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Rate Limiting
    self.RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 1000))
    self.RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 3600))
    
    # External APIs
    self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    self.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    
    # Agent Services (for Replit deployment)
    self.AGENT_SERVICES = {
        "manager": os.getenv("MANAGER_SERVICE_URL", "http://localhost:8001"),
        "project": os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002"),
        "examination": os.getenv("EXAMINATION_SERVICE_URL", "http://localhost:8003"),
        "enhancement": os.getenv("ENHANCEMENT_SERVICE_URL", "http://localhost:8004"),
        "validation": os.getenv("VALIDATION_SERVICE_URL", "http://localhost:8005"),
        "monitoring": os.getenv("MONITORING_SERVICE_URL", "http://localhost:8006"),
        "communication": os.getenv("COMMUNICATION_SERVICE_URL", "http://localhost:8007"),
        "editing": os.getenv("EDITING_SERVICE_URL", "http://localhost:8008"),
    }
    
    # Environment Detection
    self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    self.IS_REPLIT = os.getenv("REPL_ID") is not None
    
    # Create necessary directories
    Path(self.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
```

# Global configuration instance

config = YMERAConfig()

# ===================== APPLICATION STATE =====================

class ApplicationState:
“”“Manage application state and components”””

```
def __init__(self):
    self.db_manager: DatabaseManager = None
    self.security_components: Dict[str, Any] = {}
    self.api_gateway: YMERAAPIGateway = None
    self.component_registry: ComponentRegistry = None
    self.system_health: SystemHealthMonitor = None
    self.event_bus: EventBus = None
    self.cache_manager: AdvancedCacheManager = None
    self.task_queue: IntelligentTaskQueue = None
    self.api_key_manager: APIKeyManager = None
    self.browser_manager: BrowserManager = None
    self.is_initialized = False
    
async def initialize(self):
    """Initialize all application components"""
    try:
        logger.info("Initializing YMERA Enterprise Platform...")
        
        # Initialize component registry first
        self.component_registry = ComponentRegistry()
        
        # Initialize core utilities
        self.api_key_manager = APIKeyManager(
            openai_keys=[config.OPENAI_API_KEY] if config.OPENAI_API_KEY else [],
            anthropic_keys=[config.ANTHROPIC_API_KEY] if config.ANTHROPIC_API_KEY else [],
            github_tokens=[config.GITHUB_TOKEN] if config.GITHUB_TOKEN else []
        )
        
        # Initialize cache manager
        self.cache_manager = AdvancedCacheManager(config.REDIS_URL)
        await self.cache_manager.initialize()
        
        # Initialize event bus
        self.event_bus = EventBus(self.cache_manager.redis_client)
        
        # Initialize task queue
        self.task_queue = IntelligentTaskQueue(self.cache_manager.redis_client)
        
        # Initialize browser manager
        self.browser_manager = BrowserManager()
        
        # Initialize system health monitor
        self.system_health = SystemHealthMonitor(
            self.cache_manager.redis_client,
            self.event_bus
        )
        await self.system_health.start_monitoring()
        
        # Initialize database
        self.db_manager = DatabaseManager(config.DATABASE_URL, echo=config.DEBUG)
        await self.db_manager.initialize()
        logger.info("Database initialized")
        
        # Initialize security components
        security_config = SecurityConfig(
            jwt_secret=config.JWT_SECRET,
            max_file_size=config.MAX_FILE_SIZE,
            rate_limit_requests=config.RATE_LIMIT_REQUESTS,
            rate_limit_window=config.RATE_LIMIT_WINDOW,
            encryption_key=config.ENCRYPTION_KEY
        )
        
        init_security = create_security_middleware(security_config, config.REDIS_URL)
        self.security_components = await init_security()
        logger.info("Security components initialized")
        
        # Initialize API Gateway
        self.api_gateway = await create_gateway(
            agent_services=config.AGENT_SERVICES,
            api_key_manager=self.api_key_manager,
            event_bus=self.event_bus,
            cache_manager=self.cache_manager
        )
        logger.info("API Gateway initialized")
        
        # Register all components
        await self.component_registry.register_all({
            'db_manager': self.db_manager,
            'api_gateway': self.api_gateway,
            'cache_manager': self.cache_manager,
            'task_queue': self.task_queue,
            'system_health': self.system_health,
            'event_bus': self.event_bus,
            'api_key_manager': self.api_key_manager,
            'browser_manager': self.browser_manager,
            **self.security_components
        })
        
        self.is_initialized = True
        logger.info("YMERA Platform initialization completed successfully")
        
        # Emit startup event
        await self.event_bus.emit('system.startup', {
            'timestamp': asyncio.get_event_loop().time(),
            'environment': config.ENVIRONMENT,
            'components_initialized': len(self.component_registry.components)
        })
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        logger.error(traceback.format_exc())
        raise

async def shutdown(self):
    """Graceful shutdown of all components"""
    logger.info("Shutting down YMERA Platform...")
    
    try:
        # Emit shutdown event
        if self.event_bus:
            await self.event_bus.emit('system.shutdown', {
                'timestamp': asyncio.get_event_loop().time()
            })
        
        # Shutdown components in reverse order
        if self.component_registry:
            await self.component_registry.shutdown_all()
        
        if self.system_health:
            await self.system_health.stop_monitoring()
            
        if self.browser_manager:
            await self.browser_manager.cleanup()
        
        if self.api_gateway:
            await self.api_gateway.stop()
        
        if self.cache_manager:
            await self.cache_manager.close()
        
        if self.db_manager:
            await self.db_manager.close()
            
        logger.info("YMERA Platform shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
```

# Global application state

app_state = ApplicationState()

# ===================== CUSTOM MIDDLEWARE =====================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
“”“Log all requests with timing and metadata”””

```
async def dispatch(self, request: StarletteRequest, call_next):
    start_time = asyncio.get_event_loop().time()
    request_id = str(uuid.uuid4())
    
    # Add request ID to headers for tracing
    request.state.request_id = request_id
    
    logger.info(
        "Request started",
        request_id=request_id,
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None
    )
    
    response = await call_next(request)
    
    duration = asyncio.get_event_loop().time() - start_time
    
    logger.info(
        "Request completed",
        request_id=request_id,
        status_code=response.status_code,
        duration=f"{duration:.3f}s"
    )
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    return response
```

class HealthCheckMiddleware(BaseHTTPMiddleware):
“”“Handle health checks without full processing”””

```
async def dispatch(self, request: StarletteRequest, call_next):
    if request.url.path == "/health":
        return JSONResponse({
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "environment": config.ENVIRONMENT
        })
    
    return await call_next(request)
```

# ===================== LIFESPAN MANAGEMENT =====================

@asynccontextmanager
async def lifespan(app: FastAPI):
“”“Application lifespan management”””
# Startup
await app_state.initialize()

```
# Setup signal handlers for graceful shutdown
def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    asyncio.create_task(app_state.shutdown())

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

yield

# Shutdown
await app_state.shutdown()
```

# ===================== MAIN APPLICATION =====================

def create_app() -> FastAPI:
“”“Create and configure the FastAPI application”””

```
app = FastAPI(
    title="YMERA Enterprise Multi-Agent Platform",
    description="Production-ready AI-native multi-agent system for software development",
    version="1.0.0",
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
    openapi_url="/openapi.json" if config.DEBUG else None,
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if config.DEBUG else ["localhost", "127.0.0.1", "*.replit.dev"]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.DEBUG else ["https://*.replit.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add custom middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(HealthCheckMiddleware)

# Mount static files
static_path = Path("static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

return app
```

# Create the app instance

app = create_app()

# ===================== ROUTE HANDLERS =====================

@app.get(”/”)
async def root():
“”“Root endpoint with platform status”””
return {
“message”: “YMERA Enterprise Multi-Agent Platform”,
“version”: “1.0.0”,
“status”: “operational” if app_state.is_initialized else “initializing”,
“environment”: config.ENVIRONMENT,
“docs_url”: “/docs” if config.DEBUG else None
}

@app.get(”/health”)
async def health_check():
“”“Comprehensive health check”””
health_status = {
“status”: “healthy”,
“timestamp”: asyncio.get_event_loop().time(),
“environment”: config.ENVIRONMENT,
“components”: {}
}

```
if app_state.is_initialized:
    # Check component health
    if app_state.system_health:
        health_status["components"] = await app_state.system_health.get_health_status()
    
    # Check database connectivity
    try:
        await app_state.db_manager.health_check()
        health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check cache connectivity
    try:
        await app_state.cache_manager.health_check()
        health_status["cache"] = "healthy"
    except Exception as e:
        health_status["cache"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
else:
    health_status["status"] = "initializing"

return health_status
```

@app.get(”/metrics”)
async def get_metrics():
“”“System metrics endpoint”””
if not app_state.is_initialized or not app_state.system_health:
raise HTTPException(status_code=503, detail=“System not ready”)

```
return await app_state.system_health.get_metrics()
```

# Include agent routes through API Gateway

@app.api_route(”/api/{path:path}”, methods=[“GET”, “POST”, “PUT”, “DELETE”, “PATCH”])
async def gateway_handler(request: Request, path: str):
“”“Route all /api requests through the gateway”””
if not app_state.is_initialized or not app_state.api_gateway:
raise HTTPException(status_code=503, detail=“Gateway not ready”)

```
return await app_state.api_gateway.handle_request(request, path)
```

# File upload endpoint

@app.post(”/upload”)
async def upload_file(
file: UploadFile = File(…),
project_id: Optional[str] = Form(None),
background_tasks: BackgroundTasks = BackgroundTasks()
):
“”“Secure file upload with validation”””
if not app_state.is_initialized:
raise HTTPException(status_code=503, detail=“System not ready”)

```
# Validate file
if not file.filename:
    raise HTTPException(status_code=400, detail="No file provided")

if file.size > config.MAX_FILE_SIZE:
    raise HTTPException(status_code=413, detail="File too large")

try:
    # Use security manager for file validation
    file_security = app_state.security_components.get('file_security')
    if file_security:
        await file_security.validate_file(file)
    
    # Save file
    file_id = str(uuid.uuid4())
    file_path = Path(config.STORAGE_PATH) / file_id
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Store metadata in database
    async with app_state.db_manager.get_session() as session:
        # This would use your File model from the database
        file_record = {
            "id": file_id,
            "filename": file.filename,
            "size": file.size,
            "content_type": file.content_type,
            "project_id": project_id,
            "path": str(file_path)
        }
        # Save to database here
    
    # Queue file processing task
    await app_state.task_queue.add_task({
        "type": "file_processing",
        "file_id": file_id,
        "project_id": project_id
    })
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": file.size,
        "status": "uploaded"
    }
    
except Exception as e:
    logger.error(f"File upload failed: {e}")
    raise HTTPException(status_code=500, detail="Upload failed")
```

@app.get(”/download/{file_id}”)
async def download_file(file_id: str):
“”“Secure file download”””
if not app_state.is_initialized:
raise HTTPException(status_code=503, detail=“System not ready”)

```
try:
    # Get file metadata from database
    # This would query your File model
    file_path = Path(config.STORAGE_PATH) / file_id
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        media_type='application/octet-stream',
        headers={"Content-Disposition": f"attachment; filename={file_id}"}
    )
    
except Exception as e:
    logger.error(f"File download failed: {e}")
    raise HTTPException(status_code=500, detail="Download failed")
```

# WebSocket endpoint for real-time communication

@app.websocket(”/ws”)
async def websocket_endpoint(websocket):
“”“WebSocket connection for real-time updates”””
if not app_state.is_initialized or not app_state.event_bus:
await websocket.close(code=1013)
return

```
await websocket.accept()

try:
    # Subscribe to events
    async def event_handler(event_type: str, data: dict):
        await websocket.send_json({
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    subscription_id = await app_state.event_bus.subscribe("*", event_handler)
    
    # Keep connection alive
    while True:
        try:
            message = await websocket.receive_text()
            # Handle incoming messages if needed
        except Exception:
            break
            
except Exception as e:
    logger.error(f"WebSocket error: {e}")
finally:
    # Cleanup subscription
    if 'subscription_id' in locals():
        await app_state.event_bus.unsubscribe(subscription_id)
```

# ===================== ENTRY POINT =====================

def main():
“”“Main entry point”””
try:
# Determine host and port for Replit
host = “0.0.0.0” if config.IS_REPLIT else config.API_HOST
port = int(os.getenv(“PORT”, config.API_PORT))

```
    logger.info(f"Starting YMERA Platform on {host}:{port}")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Debug mode: {config.DEBUG}")
    
    # Run with uvicorn
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=config.DEBUG and not config.IS_REPLIT,
        workers=1 if config.DEBUG else 4,
        loop="uvloop",
        log_level="info",
        access_log=config.DEBUG
    )
    
except Exception as e:
    logger.error(f"Failed to start application: {e}")
    sys.exit(1)
```

if **name** == “**main**”:
main()