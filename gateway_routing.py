“””
YMERA Enterprise API Gateway & Routing System
Advanced routing with load balancing, circuit breaker, and service discovery
“””

import asyncio
import time
import json
import uuid
import aiohttp
import aiofiles
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import weakref
from collections import defaultdict, deque
import contextlib
import random
import traceback

from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog
from pydantic import BaseModel, Field

from ymera_middleware import SecurityManager, FileSecurityManager, AuditLogger, PermissionManager

logger = structlog.get_logger(“ymera.routing”)

# ===================== ROUTING MODELS =====================

class ServiceStatus(Enum):
HEALTHY = “healthy”
DEGRADED = “degraded”
UNHEALTHY = “unhealthy”
OFFLINE = “offline”

class RoutingStrategy(Enum):
ROUND_ROBIN = “round_robin”
WEIGHTED = “weighted”
LEAST_CONNECTIONS = “least_connections”
PERFORMANCE_BASED = “performance_based”

@dataclass
class ServiceEndpoint:
“”“Service endpoint configuration”””
id: str
name: str
url: str
weight: int = 1
max_connections: int = 100
timeout: float = 30.0
health_check_url: str = None
status: ServiceStatus = ServiceStatus.HEALTHY
current_connections: int = 0
response_times: deque = field(default_factory=lambda: deque(maxlen=100))
error_count: int = 0
last_health_check: datetime = None

```
def __post_init__(self):
    if self.health_check_url is None:
        self.health_check_url = f"{self.url}/health"
```

@dataclass
class RoutingRule:
“”“Advanced routing rule configuration”””
path_pattern: str
methods: List[str]
service_name: str
strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
rate_limit: int = 1000
auth_required: bool = True
permissions: List[str] = field(default_factory=list)
cache_ttl: int = 0  # seconds, 0 means no cache
retry_attempts: int = 3
circuit_breaker_threshold: int = 5
priority: int = 1

# ===================== CIRCUIT BREAKER =====================

class CircuitBreaker:
“”“Circuit breaker pattern implementation”””

```
def __init__(self, threshold: int = 5, timeout: int = 60):
    self.threshold = threshold
    self.timeout = timeout
    self.failure_count = 0
    self.last_failure_time = None
    self.state = "closed"  # closed, open, half-open

async def call(self, func: Callable, *args, **kwargs):
    """Execute function with circuit breaker protection"""
    if self.state == "open":
        if time.time() - self.last_failure_time > self.timeout:
            self.state = "half-open"
        else:
            raise HTTPException(status_code=503, detail="Service unavailable (circuit breaker open)")
    
    try:
        result = await func(*args, **kwargs)
        if self.state == "half-open":
            self.state = "closed"
            self.failure_count = 0
        return result
    except Exception as e:
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.threshold:
            self.state = "open"
        
        raise e
```

# ===================== SERVICE DISCOVERY =====================

class ServiceRegistry:
“”“Dynamic service discovery and registration”””

```
def __init__(self):
    self.services: Dict[str, List[ServiceEndpoint]] = defaultdict(list)
    self.health_check_interval = 30  # seconds
    self.health_check_task = None
    self._circuit_breakers: Dict[str, CircuitBreaker] = {}

def register_service(self, service_name: str, endpoint: ServiceEndpoint):
    """Register a new service endpoint"""
    self.services[service_name].append(endpoint)
    self._circuit_breakers[endpoint.id] = CircuitBreaker()
    logger.info(f"Service registered: {service_name} -> {endpoint.url}")

def unregister_service(self, service_name: str, endpoint_id: str):
    """Unregister a service endpoint"""
    self.services[service_name] = [
        ep for ep in self.services[service_name] 
        if ep.id != endpoint_id
    ]
    self._circuit_breakers.pop(endpoint_id, None)
    logger.info(f"Service unregistered: {service_name} -> {endpoint_id}")

def get_healthy_endpoints(self, service_name: str) -> List[ServiceEndpoint]:
    """Get healthy endpoints for a service"""
    return [
        ep for ep in self.services.get(service_name, [])
        if ep.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]
    ]

async def start_health_checks(self):
    """Start background health checking"""
    self.health_check_task = asyncio.create_task(self._health_check_loop())

async def stop_health_checks(self):
    """Stop background health checking"""
    if self.health_check_task:
        self.health_check_task.cancel()

async def _health_check_loop(self):
    """Background health check loop"""
    while True:
        try:
            await self._perform_health_checks()
            await asyncio.sleep(self.health_check_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Health check error: {e}")

async def _perform_health_checks(self):
    """Perform health checks on all registered services"""
    async with aiohttp.ClientSession() as session:
        for service_name, endpoints in self.services.items():
            for endpoint in endpoints:
                try:
                    async with session.get(
                        endpoint.health_check_url,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            endpoint.status = ServiceStatus.HEALTHY
                            endpoint.error_count = 0
                        else:
                            endpoint.status = ServiceStatus.DEGRADED
                            endpoint.error_count += 1
                except Exception:
                    endpoint.status = ServiceStatus.UNHEALTHY
                    endpoint.error_count += 1
                
                endpoint.last_health_check = datetime.utcnow()
```

# ===================== LOAD BALANCER =====================

class LoadBalancer:
“”“Advanced load balancing with multiple strategies”””

```
def __init__(self, service_registry: ServiceRegistry):
    self.registry = service_registry
    self._round_robin_indices: Dict[str, int] = defaultdict(int)

def select_endpoint(self, service_name: str, strategy: RoutingStrategy) -> ServiceEndpoint:
    """Select endpoint based on strategy"""
    endpoints = self.registry.get_healthy_endpoints(service_name)
    
    if not endpoints:
        raise HTTPException(status_code=503, detail=f"No healthy endpoints for {service_name}")
    
    if strategy == RoutingStrategy.ROUND_ROBIN:
        return self._round_robin(service_name, endpoints)
    elif strategy == RoutingStrategy.WEIGHTED:
        return self._weighted_selection(endpoints)
    elif strategy == RoutingStrategy.LEAST_CONNECTIONS:
        return self._least_connections(endpoints)
    elif strategy == RoutingStrategy.PERFORMANCE_BASED:
        return self._performance_based(endpoints)
    else:
        return random.choice(endpoints)

def _round_robin(self, service_name: str, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
    """Round robin selection"""
    index = self._round_robin_indices[service_name] % len(endpoints)
    self._round_robin_indices[service_name] += 1
    return endpoints[index]

def _weighted_selection(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
    """Weighted random selection"""
    total_weight = sum(ep.weight for ep in endpoints)
    rand = random.uniform(0, total_weight)
    current = 0
    
    for endpoint in endpoints:
        current += endpoint.weight
        if rand <= current:
            return endpoint
    return endpoints[-1]

def _least_connections(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
    """Select endpoint with least connections"""
    return min(endpoints, key=lambda ep: ep.current_connections)

def _performance_based(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
    """Select based on response time performance"""
    def avg_response_time(endpoint):
        return sum(endpoint.response_times) / len(endpoint.response_times) if endpoint.response_times else float('inf')
    
    return min(endpoints, key=avg_response_time)
```

# ===================== REQUEST ROUTER =====================

class RequestRouter:
“”“Main request routing engine”””

```
def __init__(self, service_registry: ServiceRegistry, load_balancer: LoadBalancer):
    self.registry = service_registry
    self.load_balancer = load_balancer
    self.routing_rules: List[RoutingRule] = []
    self.cache: Dict[str, Any] = {}

def add_route(self, rule: RoutingRule):
    """Add routing rule"""
    self.routing_rules.append(rule)
    self.routing_rules.sort(key=lambda r: r.priority, reverse=True)

def find_route(self, path: str, method: str) -> Optional[RoutingRule]:
    """Find matching route for request"""
    for rule in self.routing_rules:
        if method in rule.methods and self._match_pattern(path, rule.path_pattern):
            return rule
    return None

def _match_pattern(self, path: str, pattern: str) -> bool:
    """Simple pattern matching (can be enhanced with regex)"""
    # Convert pattern to regex-like matching
    import re
    pattern = pattern.replace('*', '.*').replace('?', '.')
    return re.match(f"^{pattern}$", path) is not None

async def route_request(self, request: Request) -> Response:
    """Route incoming request to appropriate service"""
    rule = self.find_route(request.url.path, request.method)
    
    if not rule:
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Check cache first
    if rule.cache_ttl > 0:
        cache_key = f"{request.method}:{request.url.path}:{hash(str(request.query_params))}"
        if cache_key in self.cache:
            cached_response, timestamp = self.cache[cache_key]
            if time.time() - timestamp < rule.cache_ttl:
                return cached_response
    
    # Select endpoint
    endpoint = self.load_balancer.select_endpoint(rule.service_name, rule.strategy)
    
    # Route request with circuit breaker
    circuit_breaker = self.registry._circuit_breakers[endpoint.id]
    
    try:
        response = await circuit_breaker.call(
            self._forward_request, request, endpoint, rule
        )
        
        # Cache successful responses
        if rule.cache_ttl > 0 and response.status_code == 200:
            self.cache[cache_key] = (response, time.time())
        
        return response
        
    except Exception as e:
        logger.error(f"Request routing failed: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

async def _forward_request(self, request: Request, endpoint: ServiceEndpoint, rule: RoutingRule) -> Response:
    """Forward request to selected endpoint"""
    start_time = time.time()
    endpoint.current_connections += 1
    
    try:
        # Build target URL
        target_url = f"{endpoint.url}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        # Prepare headers
        headers = dict(request.headers)
        headers.pop('host', None)  # Remove original host header
        
        # Forward request
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=await request.body(),
                timeout=aiohttp.ClientTimeout(total=endpoint.timeout)
            ) as response:
                content = await response.read()
                
                # Record response time
                response_time = time.time() - start_time
                endpoint.response_times.append(response_time)
                
                return Response(
                    content=content,
                    status_code=response.status,
                    headers=dict(response.headers),
                    media_type=response.content_type
                )
    
    finally:
        endpoint.current_connections -= 1
```

# ===================== FILE UPLOAD/DOWNLOAD SYSTEM =====================

class FileManager:
“”“Enterprise file management system”””

```
def __init__(self, storage_path: str = "/tmp/ymera_files", max_file_size: int = 100*1024*1024):
    self.storage_path = Path(storage_path)
    self.storage_path.mkdir(parents=True, exist_ok=True)
    self.max_file_size = max_file_size
    self.file_metadata: Dict[str, Dict] = {}

async def upload_file(
    self, 
    file: UploadFile, 
    user_id: str,
    project_id: str = None,
    tags: List[str] = None
) -> Dict[str, Any]:
    """Upload file with metadata tracking"""
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    original_name = file.filename
    file_extension = Path(original_name).suffix
    stored_filename = f"{file_id}{file_extension}"
    file_path = self.storage_path / stored_filename
    
    # Validate file size
    content = await file.read()
    if len(content) > self.max_file_size:
        raise HTTPException(status_code=413, detail="File too large")
    
    # Store file
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Create metadata
    metadata = {
        "file_id": file_id,
        "original_name": original_name,
        "stored_filename": stored_filename,
        "file_path": str(file_path),
        "file_size": len(content),
        "mime_type": file.content_type,
        "user_id": user_id,
        "project_id": project_id,
        "tags": tags or [],
        "upload_timestamp": datetime.utcnow().isoformat(),
        "checksum": hashlib.sha256(content).hexdigest()
    }
    
    self.file_metadata[file_id] = metadata
    
    logger.info(f"File uploaded: {file_id} by user {user_id}")
    return metadata

async def download_file(self, file_id: str, user_id: str) -> FileResponse:
    """Download file with access control"""
    
    if file_id not in self.file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    metadata = self.file_metadata[file_id]
    
    # Access control - users can only download their own files unless admin
    if metadata["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    file_path = Path(metadata["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_path,
        filename=metadata["original_name"],
        media_type=metadata["mime_type"]
    )

def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
    """Get file metadata"""
    if file_id not in self.file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    return self.file_metadata[file_id]

def list_user_files(self, user_id: str, project_id: str = None) -> List[Dict[str, Any]]:
    """List files for a user/project"""
    files = []
    for metadata in self.file_metadata.values():
        if metadata["user_id"] == user_id:
            if project_id is None or metadata.get("project_id") == project_id:
                files.append(metadata)
    return files
```

# ===================== WEBSOCKET MANAGER =====================

class WebSocketManager:
“”“Enterprise WebSocket connection management”””

```
def __init__(self):
    self.connections: Dict[str, WebSocket] = {}
    self.user_connections: Dict[str, Set[str]] = defaultdict(set)
    self.agent_connections: Dict[str, Set[str]] = defaultdict(set)

async def connect(self, websocket: WebSocket, connection_id: str, user_id: str, connection_type: str = "user"):
    """Accept WebSocket connection"""
    await websocket.accept()
    self.connections[connection_id] = websocket
    
    if connection_type == "user":
        self.user_connections[user_id].add(connection_id)
    elif connection_type == "agent":
        self.agent_connections[user_id].add(connection_id)
    
    logger.info(f"WebSocket connected: {connection_id} for {connection_type} {user_id}")

def disconnect(self, connection_id: str, user_id: str, connection_type: str = "user"):
    """Disconnect WebSocket"""
    self.connections.pop(connection_id, None)
    
    if connection_type == "user":
        self.user_connections[user_id].discard(connection_id)
    elif connection_type == "agent":
        self.agent_connections[user_id].discard(connection_id)
    
    logger.info(f"WebSocket disconnected: {connection_id}")

async def send_to_user(self, user_id: str, message: Dict[str, Any]):
    """Send message to all user connections"""
    connections = self.user_connections.get(user_id, set())
    await self._broadcast_message(connections, message)

async def send_to_agent(self, agent_id: str, message: Dict[str, Any]):
    """Send message to agent connections"""
    connections = self.agent_connections.get(agent_id, set())
    await self._broadcast_message(connections, message)

async def broadcast_to_all(self, message: Dict[str, Any]):
    """Broadcast message to all connections"""
    await self._broadcast_message(set(self.connections.keys()), message)

async def _broadcast_message(self, connection_ids: Set[str], message: Dict[str, Any]):
    """Broadcast message to specific connections"""
    if not connection_ids:
        return
    
    message_json = json.dumps(message)
    disconnected = set()
    
    for conn_id in connection_ids:
        websocket = self.connections.get(conn_id)
        if websocket:
            try:
                await websocket.send_text(message_json)
            except Exception:
                disconnected.add(conn_id)
    
    # Clean up disconnected connections
    for conn_id in disconnected:
        self.connections.pop(conn_id, None)
```

# ===================== MAIN API GATEWAY =====================

class YMERAAPIGateway:
“”“Main API Gateway orchestrating all components”””

```
def __init__(self):
    self.app = FastAPI(
        title="YMERA Enterprise API Gateway",
        description="Production-ready API Gateway for Multi-Agent AI Platform",
        version="1.0.0"
    )
    
    # Initialize components
    self.service_registry = ServiceRegistry()
    self.load_balancer = LoadBalancer(self.service_registry)
    self.router = RequestRouter(self.service_registry, self.load_balancer)
    self.file_manager = FileManager()
    self.websocket_manager = WebSocketManager()
    
    self._setup_middleware()
    self._setup_routes()

def _setup_middleware(self):
    """Configure middleware stack"""
    # CORS
    self.app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Compression
    self.app.add_middleware(GZipMiddleware, minimum_size=1000)

def _setup_routes(self):
    """Setup API routes"""
    
    # Health check
    @self.app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    # File upload
    @self.app.post("/api/v1/files/upload")
    async def upload_file(
        file: UploadFile = File(...),
        project_id: str = Form(None),
        tags: str = Form(""),
        request: Request = None
    ):
        user_id = request.state.user["id"]
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        metadata = await self.file_manager.upload_file(
            file=file,
            user_id=user_id,
            project_id=project_id,
            tags=tag_list
        )
        
        return {"success": True, "file": metadata}
    
    # File download
    @self.app.get("/api/v1/files/{file_id}")
    async def download_file(file_id: str, request: Request):
        user_id = request.state.user["id"]
        return await self.file_manager.download_file(file_id, user_id)
    
    # List files
    @self.app.get("/api/v1/files")
    async def list_files(project_id: str = None, request: Request = None):
        user_id = request.state.user["id"]
        files = self.file_manager.list_user_files(user_id, project_id)
        return {"files": files}
    
    # WebSocket endpoint
    @self.app.websocket("/ws/{connection_type}/{user_id}")
    async def websocket_endpoint(
        websocket: WebSocket, 
        connection_type: str, 
        user_id: str
    ):
        connection_id = str(uuid.uuid4())
        await self.websocket_manager.connect(websocket, connection_id, user_id, connection_type)
        
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Echo message back (implement your logic here)
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "data": message,
                    "timestamp": datetime.utcnow().isoformat()
                }))
        except WebSocketDisconnect:
            self.websocket_manager.disconnect(connection_id, user_id, connection_type)
    
    # Dynamic routing for agent services
    @self.app.api_route("/api/v1/agents/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def route_to_agents(request: Request):
        return await self.router.route_request(request)

def register_agent_service(self, agent_name: str, endpoint_url: str):
    """Register an agent service"""
    endpoint = ServiceEndpoint(
        id=f"{agent_name}_{uuid.uuid4()}",
        name=agent_name,
        url=endpoint_url
    )
    self.service_registry.register_service(f"agent_{agent_name}", endpoint)
    
    # Add routing rule
    rule = RoutingRule(
        path_pattern=f"/api/v1/agents/{agent_name}/*",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        service_name=f"agent_{agent_name}",
        strategy=RoutingStrategy.ROUND_ROBIN
    )
    self.router.add_route(rule)

async def start(self):
    """Start the gateway"""
    await self.service_registry.start_health_checks()
    logger.info("YMERA API Gateway started")

async def stop(self):
    """Stop the gateway"""
    await self.service_registry.stop_health_checks()
    logger.info("YMERA API Gateway stopped")
```

# ===================== STARTUP SCRIPT =====================

async def create_gateway() -> YMERAAPIGateway:
“”“Create and configure the API Gateway”””
gateway = YMERAAPIGateway()

```
# Register example agent services (configure for your setup)
agent_services = [
    ("manager", "http://localhost:8001"),
    ("project", "http://localhost:8002"),
    ("examination", "http://localhost:8003"),
    ("enhancement", "http://localhost:8004"),
    ("validation", "http://localhost:8005"),
    ("monitoring", "http://localhost:8006"),
    ("communication", "http://localhost:8007"),
    ("editing", "http://localhost:8008"),
]

for agent_name, url in agent_services:
    gateway.register_agent_service(agent_name, url)

await gateway.start()
return gateway
```

# Export main components

**all** = [
‘YMERAAPIGateway’, ‘ServiceRegistry’, ‘LoadBalancer’, ‘RequestRouter’,
‘FileManager’, ‘WebSocketManager’, ‘ServiceEndpoint’, ‘RoutingRule’,
‘create_gateway’
]