“””
YMERA Code Editing Agent FastAPI Application
Production-ready REST API with comprehensive middleware and endpoints
“””

import asyncio
import json
import logging
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from fastapi import (
FastAPI, HTTPException, Depends, Request, Response,
BackgroundTasks, UploadFile, File, Form, Query, Path as PathParam
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response as StarletteResponse
import uvicorn

# YMERA imports (assuming they exist)

from ymera_core.config import ConfigManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.exceptions import YMERAException

from ymera_agents.communication.message_bus import MessageBus
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.learning.knowledge_base import KnowledgeBase

from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_services.code_analysis.quality_analyzer import CodeQualityAnalyzer
from ymera_services.security.vulnerability_scanner import VulnerabilityScanner

# Import the main agent class

from code_editing_agent import CodeEditingAgent, EditType, EditPriority, EditStatus

# Pydantic Models for Request/Response

class EditRequest(BaseModel):
“”“Request model for code editing operations”””
file_path: str = Field(…, description=“Path to the file to be edited”)
edit_type: str = Field(…, description=“Type of edit operation”)
priority: str = Field(default=“medium”, description=“Priority level”)
description: str = Field(…, description=“Description of the edit”)
original_code: str = Field(…, description=“Original code content”)
start_line: int = Field(…, ge=1, description=“Starting line number”)
end_line: int = Field(…, ge=1, description=“Ending line number”)
context: Dict[str, Any] = Field(default_factory=dict, description=“Additional context”)

```
@validator('edit_type')
def validate_edit_type(cls, v):
    valid_types = [e.value for e in EditType]
    if v not in valid_types:
        raise ValueError(f"edit_type must be one of: {valid_types}")
    return v

@validator('priority')
def validate_priority(cls, v):
    valid_priorities = [p.value for p in EditPriority]
    if v not in valid_priorities:
        raise ValueError(f"priority must be one of: {valid_priorities}")
    return v

@validator('end_line')
def validate_line_numbers(cls, v, values):
    if 'start_line' in values and v < values['start_line']:
        raise ValueError("end_line must be >= start_line")
    return v
```

class SessionCreateRequest(BaseModel):
“”“Request model for creating editing sessions”””
project_id: str = Field(…, description=“Project identifier”)
user_id: str = Field(…, description=“User identifier”)
description: str = Field(…, description=“Session description”)
objectives: List[str] = Field(default_factory=list, description=“Session objectives”)
context: Dict[str, Any] = Field(default_factory=dict, description=“Session context”)

class BulkEditRequest(BaseModel):
“”“Request model for bulk editing operations”””
session_id: str = Field(…, description=“Session ID for the bulk operation”)
edits: List[EditRequest] = Field(…, description=“List of edit requests”)
apply_automatically: bool = Field(default=False, description=“Apply edits automatically if confidence is high”)

class EditAnalysisRequest(BaseModel):
“”“Request model for code analysis”””
file_path: str = Field(…, description=“Path to the file to analyze”)
code_content: str = Field(…, description=“Code content to analyze”)
objectives: List[str] = Field(default_factory=list, description=“Analysis objectives”)
context: Dict[str, Any] = Field(default_factory=dict, description=“Analysis context”)

class EditResponse(BaseModel):
“”“Response model for edit operations”””
edit_id: str
session_id: str
file_path: str
edit_type: str
priority: str
description: str
status: str
confidence_score: float
reasoning: str
modified_code: Optional[str] = None
created_at: datetime
applied_at: Optional[datetime] = None

class SessionResponse(BaseModel):
“”“Response model for session operations”””
session_id: str
project_id: str
user_id: str
description: str
status: str
total_edits: int
completed_edits: int
failed_edits: int
success_rate: float
created_at: datetime
completed_at: Optional[datetime] = None

class AnalysisResponse(BaseModel):
“”“Response model for code analysis”””
file_path: str
analysis_id: str
recommendations: List[Dict[str, Any]]
quality_score: float
security_score: float
performance_score: float
issues_found: int
suggestions_count: int

class APIResponse(BaseModel):
“”“Generic API response wrapper”””
success: bool
data: Optional[Any] = None
message: str = “”
error: Optional[str] = None
timestamp: datetime = Field(default_factory=datetime.utcnow)

# Middleware Classes

class RateLimitMiddleware(BaseHTTPMiddleware):
“”“Rate limiting middleware”””

```
def __init__(self, app, calls: int = 100, period: int = 60):
    super().__init__(app)
    self.calls = calls
    self.period = period
    self.clients = {}

async def dispatch(self, request: Request, call_next):
    client_id = self._get_client_id(request)
    now = time.time()
    
    # Clean old entries
    self.clients = {k: v for k, v in self.clients.items() 
                   if now - v['reset_time'] < self.period}
    
    if client_id not in self.clients:
        self.clients[client_id] = {
            'count': 0,
            'reset_time': now
        }
    
    client_data = self.clients[client_id]
    
    # Reset counter if period has passed
    if now - client_data['reset_time'] >= self.period:
        client_data['count'] = 0
        client_data['reset_time'] = now
    
    # Check rate limit
    if client_data['count'] >= self.calls:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": "Rate limit exceeded",
                "message": f"Rate limit: {self.calls} calls per {self.period} seconds"
            }
        )
    
    client_data['count'] += 1
    
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(self.calls)
    response.headers["X-RateLimit-Remaining"] = str(self.calls - client_data['count'])
    response.headers["X-RateLimit-Reset"] = str(int(client_data['reset_time'] + self.period))
    
    return response

def _get_client_id(self, request: Request) -> str:
    """Extract client identifier from request"""
    # Try to get from authorization header first
    auth_header = request.headers.get("authorization")
    if auth_header:
        return f"auth_{hash(auth_header)}"
    
    # Fall back to IP address
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0]
    
    return request.client.host if request.client else "unknown"
```

class LoggingMiddleware(BaseHTTPMiddleware):
“”“Request logging middleware”””

```
def __init__(self, app, logger: StructuredLogger):
    super().__init__(app)
    self.logger = logger

async def dispatch(self, request: Request, call_next):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Log request
    self.logger.info(
        "API Request Started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    )
    
    # Add request ID to response headers
    response = await call_next(request)
    
    # Calculate duration
    process_time = time.time() - start_time
    
    # Log response
    self.logger.info(
        "API Request Completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": round(process_time, 4)
        }
    )
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(round(process_time, 4))
    
    return response
```

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
“”“Global error handling middleware”””

```
def __init__(self, app, logger: StructuredLogger):
    super().__init__(app)
    self.logger = logger

async def dispatch(self, request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except YMERAException as e:
        self.logger.error(
            f"YMERA Exception: {str(e)}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "error_type": "YMERAException"
            }
        )
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Application Error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except ValueError as e:
        self.logger.error(
            f"Validation Error: {str(e)}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "error_type": "ValueError"
            }
        )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "Validation Error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        self.logger.error(
            f"Unexpected Error: {str(e)}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
```

# Authentication

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
“”“Extract and validate user from JWT token”””
token = credentials.credentials

```
# TODO: Implement proper JWT validation
# For now, we'll use a simple token validation
if not token or token == "invalid":
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials"
    )

# Mock user extraction - replace with real JWT decoding
return {
    "user_id": "user123",  # Extract from JWT
    "username": "developer",
    "permissions": ["read", "write", "admin"]
}
```

# Dependency injection

class Dependencies:
“”“Dependency injection container”””

```
def __init__(self):
    self.config = None
    self.db_manager = None
    self.ai_manager = None
    self.message_bus = None
    self.learning_engine = None
    self.knowledge_base = None
    self.cache_manager = None
    self.code_analyzer = None
    self.vulnerability_scanner = None
    self.logger = None
    self.code_editing_agent = None

async def initialize(self):
    """Initialize all dependencies"""
    # Initialize core services
    self.config = ConfigManager()
    self.db_manager = DatabaseManager(self.config)
    self.logger = StructuredLogger("code_editing_api")
    self.cache_manager = RedisCacheManager(self.config)
    
    # Initialize AI services
    self.ai_manager = MultiLLMManager(self.config)
    self.code_analyzer = CodeQualityAnalyzer(self.config)
    self.vulnerability_scanner = VulnerabilityScanner(self.config)
    
    # Initialize agent services
    self.message_bus = MessageBus(self.config)
    self.learning_engine = LearningEngine(self.config, self.db_manager)
    self.knowledge_base = KnowledgeBase(self.config, self.db_manager)
    
    # Initialize the main agent
    self.code_editing_agent = CodeEditingAgent(
        config=self.config,
        db_manager=self.db_manager,
        ai_manager=self.ai_manager,
        message_bus=self.message_bus,
        learning_engine=self.learning_engine,
        knowledge_base=self.knowledge_base,
        cache_manager=self.cache_manager,
        code_analyzer=self.code_analyzer,
        vulnerability_scanner=self.vulnerability_scanner,
        logger=self.logger
    )
    
    await self.code_editing_agent.initialize()
```

# Global dependencies instance

deps = Dependencies()

async def get_agent() -> CodeEditingAgent:
“”“Get the code editing agent instance”””
return deps.code_editing_agent

async def get_logger() -> StructuredLogger:
“”“Get the logger instance”””
return deps.logger

# FastAPI Application

def create_app() -> FastAPI:
“”“Create and configure FastAPI application”””

```
app = FastAPI(
    title="YMERA Code Editing Agent API",
    description="Production-ready AI-powered code editing service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")
app.add_middleware(RateLimitMiddleware, calls=100, period=60)

# Add custom middleware after dependencies are available
@app.middleware("http")
async def add_custom_middleware(request: Request, call_next):
    if deps.logger:
        # Add logging middleware
        logging_middleware = LoggingMiddleware(app, deps.logger)
        return await logging_middleware.dispatch(request, call_next)
    return await call_next(request)

return app
```

app = create_app()

# Startup and shutdown events

@app.on_event(“startup”)
async def startup_event():
“”“Initialize services on startup”””
await deps.initialize()

@app.on_event(“shutdown”)
async def shutdown_event():
“”“Cleanup on shutdown”””
if deps.code_editing_agent:
await deps.code_editing_agent.cleanup()

# Health check endpoint

@app.get(”/health”, tags=[“System”])
async def health_check():
“”“Health check endpoint”””
return {
“status”: “healthy”,
“timestamp”: datetime.utcnow().isoformat(),
“version”: “1.0.0”
}

# Session Management Endpoints

@app.post(”/sessions”, response_model=APIResponse, tags=[“Sessions”])
async def create_session(
request: SessionCreateRequest,
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Create a new editing session”””
try:
session = await agent.create_editing_session(
project_id=request.project_id,
user_id=current_user[“user_id”],
description=request.description,
objectives=request.objectives,
context=request.context
)

```
    return APIResponse(
        success=True,
        data=session,
        message="Session created successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.get(”/sessions”, response_model=APIResponse, tags=[“Sessions”])
async def list_sessions(
project_id: Optional[str] = Query(None),
status: Optional[str] = Query(None),
limit: int = Query(50, ge=1, le=100),
offset: int = Query(0, ge=0),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“List editing sessions with optional filtering”””
try:
sessions = await agent.list_sessions(
project_id=project_id,
status=status,
user_id=current_user[“user_id”],
limit=limit,
offset=offset
)

```
    return APIResponse(
        success=True,
        data=sessions,
        message=f"Retrieved {len(sessions)} sessions"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.get(”/sessions/{session_id}”, response_model=APIResponse, tags=[“Sessions”])
async def get_session(
session_id: str = PathParam(…, description=“Session ID”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Get detailed information about a specific session”””
try:
session = await agent.get_session_details(session_id)
if not session:
raise HTTPException(status_code=404, detail=“Session not found”)

```
    return APIResponse(
        success=True,
        data=session,
        message="Session retrieved successfully"
    )
except HTTPException:
    raise
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.delete(”/sessions/{session_id}”, response_model=APIResponse, tags=[“Sessions”])
async def cancel_session(
session_id: str = PathParam(…, description=“Session ID”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Cancel an active editing session”””
try:
result = await agent.cancel_session(session_id)

```
    return APIResponse(
        success=True,
        data=result,
        message="Session cancelled successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.get(”/sessions/{session_id}/metrics”, response_model=APIResponse, tags=[“Sessions”])
async def get_session_metrics(
session_id: str = PathParam(…, description=“Session ID”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Get performance metrics for a session”””
try:
metrics = await agent.get_session_metrics(session_id)

```
    return APIResponse(
        success=True,
        data=metrics,
        message="Session metrics retrieved successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

# Code Analysis Endpoints

@app.post(”/analyze”, response_model=APIResponse, tags=[“Analysis”])
async def analyze_code(
request: EditAnalysisRequest,
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Analyze code and get improvement recommendations”””
try:
analysis = await agent.analyze_code(
file_path=request.file_path,
code_content=request.code_content,
objectives=request.objectives,
context=request.context
)

```
    return APIResponse(
        success=True,
        data=analysis,
        message="Code analysis completed successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.post(”/analyze/file”, response_model=APIResponse, tags=[“Analysis”])
async def analyze_file(
file: UploadFile = File(…),
objectives: str = Form(””),
context: str = Form(”{}”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Analyze uploaded file”””
try:
# Read file content
content = await file.read()
code_content = content.decode(‘utf-8’)

```
    # Parse objectives and context
    objectives_list = [obj.strip() for obj in objectives.split(",") if obj.strip()]
    context_dict = json.loads(context) if context else {}
    
    analysis = await agent.analyze_code(
        file_path=file.filename,
        code_content=code_content,
        objectives=objectives_list,
        context=context_dict
    )
    
    return APIResponse(
        success=True,
        data=analysis,
        message=f"File {file.filename} analyzed successfully"
    )
except json.JSONDecodeError:
    raise HTTPException(status_code=400, detail="Invalid JSON in context parameter")
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

# Edit Operations Endpoints

@app.post(”/sessions/{session_id}/edits”, response_model=APIResponse, tags=[“Edits”])
async def create_edit(
session_id: str = PathParam(…, description=“Session ID”),
request: EditRequest = …,
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Create a new edit operation”””
try:
edit = await agent.create_edit(
session_id=session_id,
file_path=request.file_path,
edit_type=EditType(request.edit_type),
priority=EditPriority(request.priority),
description=request.description,
original_code=request.original_code,
start_line=request.start_line,
end_line=request.end_line,
context=request.context
)

```
    return APIResponse(
        success=True,
        data=edit,
        message="Edit created successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.post(”/sessions/{session_id}/bulk-edits”, response_model=APIResponse, tags=[“Edits”])
async def create_bulk_edits(
session_id: str = PathParam(…, description=“Session ID”),
request: BulkEditRequest = …,
background_tasks: BackgroundTasks = …,
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Create multiple edit operations in bulk”””
try:
# Create edits
edit_requests = []
for edit_req in request.edits:
edit_requests.append({
“file_path”: edit_req.file_path,
“edit_type”: EditType(edit_req.edit_type),
“priority”: EditPriority(edit_req.priority),
“description”: edit_req.description,
“original_code”: edit_req.original_code,
“start_line”: edit_req.start_line,
“end_line”: edit_req.end_line,
“context”: edit_req.context
})

```
    result = await agent.create_bulk_edits(
        session_id=session_id,
        edit_requests=edit_requests,
        apply_automatically=request.apply_automatically
    )
    
    return APIResponse(
        success=True,
        data=result,
        message=f"Created {len(request.edits)} edits successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.get(”/sessions/{session_id}/edits”, response_model=APIResponse, tags=[“Edits”])
async def list_edits(
session_id: str = PathParam(…, description=“Session ID”),
status: Optional[str] = Query(None),
edit_type: Optional[str] = Query(None),
limit: int = Query(50, ge=1, le=100),
offset: int = Query(0, ge=0),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“List edits for a session”””
try:
edits = await agent.list_edits(
session_id=session_id,
status=status,
edit_type=edit_type,
limit=limit,
offset=offset
)

```
    return APIResponse(
        success=True,
        data=edits,
        message=f"Retrieved {len(edits)} edits"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.post(”/edits/{edit_id}/apply”, response_model=APIResponse, tags=[“Edits”])
async def apply_edit(
edit_id: str = PathParam(…, description=“Edit ID”),
force: bool = Query(False, description=“Force apply even with low confidence”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Apply a specific edit”””
try:
result = await agent.apply_edit(edit_id, force_apply=force)

```
    return APIResponse(
        success=True,
        data=result,
        message="Edit applied successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.post(”/edits/{edit_id}/rollback”, response_model=APIResponse, tags=[“Edits”])
async def rollback_edit(
edit_id: str = PathParam(…, description=“Edit ID”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Rollback a previously applied edit”””
try:
result = await agent.rollback_edit(edit_id)

```
    return APIResponse(
        success=True,
        data=result,
        message="Edit rolled back successfully"
    )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.get(”/edits/{edit_id}”, response_model=APIResponse, tags=[“Edits”])
async def get_edit(
edit_id: str = PathParam(…, description=“Edit ID”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Get detailed information about a specific edit”””
try:
edit = await agent.get_edit_details(edit_id)
if not edit:
raise HTTPException(status_code=404, detail=“Edit not found”)

```
    return APIResponse(
        success=True,
        data=edit,
        message="Edit retrieved successfully"
    )
except HTTPException:
    raise
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

# Reporting Endpoints

@app.get(”/sessions/{session_id}/report”, tags=[“Reports”])
async def get_session_report(
session_id: str = PathParam(…, description=“Session ID”),
format: str = Query(“json”, regex=”^(json|markdown|html)$”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Generate a comprehensive report for a session”””
try:
report = await agent.generate_session_report(session_id, format=format)

```
    if format == "json":
        return APIResponse(
            success=True,
            data=report,
            message="Session report generated successfully"
        )
    elif format == "markdown":
        return Response(
            content=report["content"],
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=session_{session_id}_report.md"
            }
        )
    elif format == "html":
        return Response(
            content=report["content"],
            media_type="text/html"
        )
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

# System Management Endpoints

@app.post(”/system/cleanup”, response_model=APIResponse, tags=[“System”])
async def cleanup_old_sessions(
days_old: int = Query(7, ge=1, description=“Days old to consider for cleanup”),
agent: CodeEditingAgent = Depends(get_agent),
current_user: dict = Depends(get_current_user)
):
“”“Clean up old completed sessions and their data”””
try:
# Check if user has admin permissions
if “admin” not in current_user.get(“permissions”, []):
raise HTTPException(status_code=403, detail=“Admin permissions required”)

```
    result = await agent.cleanup_old_sessions(days_old=days_old)
    
    return APIResponse(
        success=True,
        data=result,
        message=f"Cleaned up {result['cleaned_sessions']} old sessions"
    )
except HTTPException:
    raise
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

@app.get(”/system/stats”, response_model=APIResponse, tags=[“System”])
async def get_system_stats(
agent: CodeEditingAgent = Depends(get_agent),
current_user: ```python
async def get_system_stats(
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive system statistics"""
    try:
        # Check if user has admin permissions
        if "admin" not in current_user.get("permissions", []):
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        stats = await agent.get_system_statistics()
        
        return APIResponse(
            success=True,
            data=stats,
            message="System statistics retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/system/performance", response_model=APIResponse, tags=["System"])
async def get_performance_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Get system performance metrics"""
    try:
        # Check if user has admin permissions
        if "admin" not in current_user.get("permissions", []):
            raise HTTPException(status_code=403, detail="Admin permissions required")
        
        metrics = await agent.get_performance_metrics(hours_back=hours)
        
        return APIResponse(
            success=True,
            data=metrics,
            message="Performance metrics retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# WebSocket Support for Real-time Updates

@app.websocket("/ws/sessions/{session_id}")
async def websocket_session_updates(
    websocket: WebSocket,
    session_id: str = PathParam(..., description="Session ID"),
    token: str = Query(..., description="Authentication token"),
    agent: CodeEditingAgent = Depends(get_agent)
):
    """WebSocket endpoint for real-time session updates"""
    try:
        # Validate token (simplified validation)
        if not token or token == "invalid":
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        await websocket.accept()
        
        # Subscribe to session updates
        async def send_updates():
            """Send real-time updates to client"""
            async for update in agent.subscribe_to_session_updates(session_id):
                try:
                    await websocket.send_json({
                        "type": update["type"],
                        "data": update["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    print(f"Error sending websocket message: {e}")
                    break
        
        # Start sending updates in background
        update_task = asyncio.create_task(send_updates())
        
        try:
            # Keep connection alive and handle client messages
            while True:
                message = await websocket.receive_json()
                
                # Handle client commands
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif message.get("type") == "subscribe":
                    # Handle subscription changes
                    pass
                
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            update_task.cancel()
            await websocket.close()
            
    except Exception as e:
        await websocket.close(code=4000, reason=f"Server error: {str(e)}")

# Streaming Response Endpoints

@app.get("/sessions/{session_id}/edits/stream", tags=["Streaming"])
async def stream_edit_progress(
    session_id: str = PathParam(..., description="Session ID"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Stream edit progress in real-time using Server-Sent Events"""
    
    async def generate_progress():
        """Generate Server-Sent Events for edit progress"""
        try:
            async for progress in agent.stream_edit_progress(session_id):
                yield f"data: {json.dumps(progress)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

# Batch Processing Endpoints

@app.post("/batch/analyze", response_model=APIResponse, tags=["Batch"])
async def batch_analyze_files(
    files: List[UploadFile] = File(..., description="Files to analyze"),
    objectives: str = Form("", description="Comma-separated analysis objectives"),
    context: str = Form("{}", description="JSON context for analysis"),
    background_tasks: BackgroundTasks = ...,
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Analyze multiple files in batch"""
    try:
        # Parse parameters
        objectives_list = [obj.strip() for obj in objectives.split(",") if obj.strip()]
        context_dict = json.loads(context) if context else {}
        
        # Create batch job
        batch_id = str(uuid.uuid4())
        
        # Process files in background
        async def process_batch():
            results = []
            for file in files:
                try:
                    content = await file.read()
                    code_content = content.decode('utf-8')
                    
                    analysis = await agent.analyze_code(
                        file_path=file.filename,
                        code_content=code_content,
                        objectives=objectives_list,
                        context=context_dict
                    )
                    
                    results.append({
                        "file": file.filename,
                        "status": "success",
                        "analysis": analysis
                    })
                except Exception as e:
                    results.append({
                        "file": file.filename,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Store results (implement caching mechanism)
            await agent.store_batch_results(batch_id, results)
        
        background_tasks.add_task(process_batch)
        
        return APIResponse(
            success=True,
            data={"batch_id": batch_id, "files_count": len(files)},
            message=f"Batch analysis started for {len(files)} files"
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in context parameter")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/batch/{batch_id}/status", response_model=APIResponse, tags=["Batch"])
async def get_batch_status(
    batch_id: str = PathParam(..., description="Batch ID"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Get status of a batch operation"""
    try:
        status = await agent.get_batch_status(batch_id)
        if not status:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        return APIResponse(
            success=True,
            data=status,
            message="Batch status retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Export/Import Endpoints

@app.post("/sessions/{session_id}/export", tags=["Export/Import"])
async def export_session(
    session_id: str = PathParam(..., description="Session ID"),
    format: str = Query("json", regex="^(json|zip)$", description="Export format"),
    include_code: bool = Query(True, description="Include modified code in export"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Export session data and edits"""
    try:
        export_data = await agent.export_session(
            session_id=session_id,
            format=format,
            include_code=include_code
        )
        
        if format == "json":
            return Response(
                content=json.dumps(export_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=session_{session_id}_export.json"
                }
            )
        elif format == "zip":
            return Response(
                content=export_data,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=session_{session_id}_export.zip"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/sessions/import", response_model=APIResponse, tags=["Export/Import"])
async def import_session(
    file: UploadFile = File(..., description="Session export file"),
    project_id: str = Form(..., description="Target project ID"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Import session data from export file"""
    try:
        # Read and parse file
        content = await file.read()
        
        if file.filename.endswith('.json'):
            session_data = json.loads(content.decode('utf-8'))
        elif file.filename.endswith('.zip'):
            # Handle zip import (implement zip parsing)
            session_data = await agent.parse_zip_export(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
        
        # Import session
        result = await agent.import_session(
            session_data=session_data,
            project_id=project_id,
            user_id=current_user["user_id"]
        )
        
        return APIResponse(
            success=True,
            data=result,
            message="Session imported successfully"
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Advanced Search and Filtering

@app.get("/search/edits", response_model=APIResponse, tags=["Search"])
async def search_edits(
    query: str = Query(..., description="Search query"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    edit_type: Optional[str] = Query(None, description="Filter by edit type"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Advanced search across edits with full-text search capabilities"""
    try:
        search_filters = {
            "project_id": project_id,
            "edit_type": edit_type,
            "date_from": date_from,
            "date_to": date_to,
            "user_id": current_user["user_id"]
        }
        
        results = await agent.search_edits(
            query=query,
            filters=search_filters,
            limit=limit,
            offset=offset
        )
        
        return APIResponse(
            success=True,
            data=results,
            message=f"Found {results['total_count']} matching edits"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Template Management

@app.post("/templates", response_model=APIResponse, tags=["Templates"])
async def create_edit_template(
    name: str = Form(..., description="Template name"),
    description: str = Form(..., description="Template description"),
    edit_type: str = Form(..., description="Edit type"),
    template_code: str = Form(..., description="Template code pattern"),
    variables: str = Form("{}", description="Template variables as JSON"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Create a reusable edit template"""
    try:
        variables_dict = json.loads(variables) if variables else {}
        
        template = await agent.create_edit_template(
            name=name,
            description=description,
            edit_type=EditType(edit_type),
            template_code=template_code,
            variables=variables_dict,
            created_by=current_user["user_id"]
        )
        
        return APIResponse(
            success=True,
            data=template,
            message="Edit template created successfully"
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in variables")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/templates", response_model=APIResponse, tags=["Templates"])
async def list_templates(
    edit_type: Optional[str] = Query(None, description="Filter by edit type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """List available edit templates"""
    try:
        templates = await agent.list_templates(
            edit_type=edit_type,
            user_id=current_user["user_id"],
            limit=limit,
            offset=offset
        )
        
        return APIResponse(
            success=True,
            data=templates,
            message=f"Retrieved {len(templates)} templates"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/templates/{template_id}/apply", response_model=APIResponse, tags=["Templates"])
async def apply_template(
    template_id: str = PathParam(..., description="Template ID"),
    session_id: str = Form(..., description="Session ID"),
    file_path: str = Form(..., description="Target file path"),
    variables: str = Form("{}", description="Template variables as JSON"),
    agent: CodeEditingAgent = Depends(get_agent),
    current_user: dict = Depends(get_current_user)
):
    """Apply a template to create an edit"""
    try:
        variables_dict = json.loads(variables) if variables else {}
        
        edit = await agent.apply_template(
            template_id=template_id,
            session_id=session_id,
            file_path=file_path,
            variables=variables_dict
        )
        
        return APIResponse(
            success=True,
            data=edit,
            message="Template applied successfully"
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in variables")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Error handling for undefined routes
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Not Found",
            "message": f"The requested endpoint {request.url.path} was not found",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    return JSONResponse(
        status_code=405,
        content={
            "success": False,
            "error": "Method Not Allowed",
            "message": f"Method {request.method} not allowed for {request.url.path}",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Main entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="YMERA Code Editing Agent API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    
    args = parser.parse_args()
    
    uvicorn.run(
        "main:app" if args.reload else app,
        host=args.host,
        port=args.port,
        workers=args.workers if not args.reload else 1,
        reload=args.reload,
        log_level=args.log_level,
        access_log=True,
        server_header=False,
        date_header=False
    )
```