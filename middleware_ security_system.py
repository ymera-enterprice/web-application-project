“””
YMERA Enterprise Middleware & Security System
Production-ready middleware for multi-agent platform with enterprise-grade security
“””

import asyncio
import jwt
import bcrypt
import hashlib
import hmac
import time
import uuid
import json
import magic
import aiofiles
import aioredis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import re
import secrets
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from fastapi import HTTPException, Request, Response, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(“ymera.middleware”)

# ===================== SECURITY ENUMS & CONFIGS =====================

class SecurityLevel(Enum):
PUBLIC = “public”
AUTHENTICATED = “authenticated”
AGENT = “agent”
ADMIN = “admin”
SYSTEM = “system”

class FileCategory(Enum):
IMAGE = “image”
DOCUMENT = “document”
CODE = “code”
ARCHIVE = “archive”
MEDIA = “media”
DATA = “data”
EXECUTABLE = “executable”
UNKNOWN = “unknown”

@dataclass
class SecurityConfig:
“”“Enterprise security configuration”””
jwt_secret: str
jwt_algorithm: str = “HS256”
jwt_expiry_hours: int = 24
refresh_token_days: int = 30
max_file_size: int = 100 * 1024 * 1024  # 100MB
allowed_file_types: Set[str] = None
rate_limit_requests: int = 1000
rate_limit_window: int = 3600  # 1 hour
encryption_key: str = None

```
def __post_init__(self):
    if self.allowed_file_types is None:
        self.allowed_file_types = {
            'txt', 'pdf', 'doc', 'docx', 'py', 'js', 'json', 'yaml', 'yml',
            'jpg', 'jpeg', 'png', 'gif', 'svg', 'mp4', 'avi', 'mov',
            'zip', 'tar', 'gz', 'rar', 'csv', 'xlsx', 'xml', 'md'
        }
    if self.encryption_key is None:
        self.encryption_key = Fernet.generate_key().decode()
```

# ===================== ENCRYPTION & SECURITY UTILITIES =====================

class SecurityManager:
“”“Enterprise-grade security manager”””

```
def __init__(self, config: SecurityConfig):
    self.config = config
    self.fernet = Fernet(config.encryption_key.encode())
    self.redis_client = None
    
async def init_redis(self, redis_url: str = "redis://localhost:6379"):
    """Initialize Redis connection"""
    try:
        self.redis_client = await aioredis.from_url(redis_url)
        await self.redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        
def hash_password(self, password: str) -> str:
    """Hash password with bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(self, password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def generate_token(self, user_id: str, role: str, permissions: List[str] = None) -> Dict[str, str]:
    """Generate JWT tokens"""
    now = datetime.utcnow()
    
    # Access token payload
    access_payload = {
        "user_id": user_id,
        "role": role,
        "permissions": permissions or [],
        "iat": now,
        "exp": now + timedelta(hours=self.config.jwt_expiry_hours),
        "jti": str(uuid.uuid4())
    }
    
    # Refresh token payload
    refresh_payload = {
        "user_id": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=self.config.refresh_token_days),
        "jti": str(uuid.uuid4())
    }
    
    access_token = jwt.encode(access_payload, self.config.jwt_secret, self.config.jwt_algorithm)
    refresh_token = jwt.encode(refresh_payload, self.config.jwt_secret, self.config.jwt_algorithm)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": self.config.jwt_expiry_hours * 3600
    }

def verify_token(self, token: str) -> Dict[str, Any]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, self.config.jwt_secret, algorithms=[self.config.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def encrypt_sensitive_data(self, data: str) -> str:
    """Encrypt sensitive data"""
    return self.fernet.encrypt(data.encode()).decode()

def decrypt_sensitive_data(self, encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    return self.fernet.decrypt(encrypted_data.encode()).decode()
```

# ===================== FILE SECURITY & VALIDATION =====================

class FileSecurityManager:
“”“Advanced file security and validation”””

```
DANGEROUS_EXTENSIONS = {
    'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jar',
    'app', 'deb', 'pkg', 'rpm', 'dmg', 'msi', 'apk', 'ipa'
}

MIME_TYPE_MAP = {
    'image/jpeg': FileCategory.IMAGE,
    'image/png': FileCategory.IMAGE,
    'image/gif': FileCategory.IMAGE,
    'application/pdf': FileCategory.DOCUMENT,
    'text/plain': FileCategory.DOCUMENT,
    'application/zip': FileCategory.ARCHIVE,
    'text/x-python': FileCategory.CODE,
    'application/json': FileCategory.DATA,
}

def __init__(self, config: SecurityConfig):
    self.config = config
    
async def validate_file(self, file: UploadFile) -> Dict[str, Any]:
    """Comprehensive file validation"""
    # Size validation
    content = await file.read()
    await file.seek(0)  # Reset file pointer
    
    if len(content) > self.config.max_file_size:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Max size: {self.config.max_file_size} bytes"
        )
    
    # Extension validation
    file_ext = Path(file.filename).suffix.lower().lstrip('.')
    if file_ext not in self.config.allowed_file_types:
        raise HTTPException(
            status_code=415,
            detail=f"File type not allowed: {file_ext}"
        )
    
    # MIME type validation
    mime_type = magic.from_buffer(content, mime=True)
    category = self.MIME_TYPE_MAP.get(mime_type, FileCategory.UNKNOWN)
    
    # Security checks
    await self._scan_for_malware(content, file.filename)
    
    return {
        "filename": file.filename,
        "size": len(content),
        "mime_type": mime_type,
        "category": category.value,
        "extension": file_ext,
        "checksum": hashlib.sha256(content).hexdigest(),
        "is_safe": True
    }

async def _scan_for_malware(self, content: bytes, filename: str):
    """Basic malware scanning"""
    # Check for dangerous patterns
    dangerous_patterns = [
        b'<script',
        b'javascript:',
        b'eval(',
        b'exec(',
        b'system(',
        b'shell_exec',
    ]
    
    content_lower = content.lower()
    for pattern in dangerous_patterns:
        if pattern in content_lower:
            raise HTTPException(
                status_code=400,
                detail="Potentially malicious content detected"
            )
    
    # Check file extension against content
    file_ext = Path(filename).suffix.lower().lstrip('.')
    if file_ext in self.DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Dangerous file type detected"
        )
```

# ===================== RATE LIMITING =====================

class RateLimiter:
“”“Advanced rate limiting with Redis backend”””

```
def __init__(self, redis_client):
    self.redis = redis_client

async def check_rate_limit(
    self, 
    identifier: str, 
    limit: int, 
    window: int,
    category: str = "api"
) -> Dict[str, Any]:
    """Check if request is within rate limit"""
    key = f"rate_limit:{category}:{identifier}"
    current_time = int(time.time())
    window_start = current_time - window
    
    # Clean old entries and count current requests
    await self.redis.zremrangebyscore(key, 0, window_start)
    current_requests = await self.redis.zcard(key)
    
    if current_requests >= limit:
        reset_time = await self.redis.zrange(key, 0, 0, withscores=True)
        reset_time = reset_time[0][1] + window if reset_time else current_time + window
        
        return {
            "allowed": False,
            "limit": limit,
            "remaining": 0,
            "reset_time": reset_time,
            "retry_after": int(reset_time - current_time)
        }
    
    # Add current request
    await self.redis.zadd(key, {str(uuid.uuid4()): current_time})
    await self.redis.expire(key, window)
    
    return {
        "allowed": True,
        "limit": limit,
        "remaining": limit - current_requests - 1,
        "reset_time": current_time + window,
        "retry_after": 0
    }
```

# ===================== AUTHENTICATION MIDDLEWARE =====================

class AuthenticationMiddleware(BaseHTTPMiddleware):
“”“Enterprise authentication middleware”””

```
def __init__(self, app, security_manager: SecurityManager, rate_limiter: RateLimiter):
    super().__init__(app)
    self.security_manager = security_manager
    self.rate_limiter = rate_limiter
    self.public_paths = {'/docs', '/redoc', '/openapi.json', '/health', '/metrics'}

async def dispatch(self, request: Request, call_next):
    start_time = time.time()
    
    # Skip auth for public paths
    if request.url.path in self.public_paths:
        response = await call_next(request)
        return self._add_security_headers(response, start_time)
    
    try:
        # Rate limiting
        client_ip = request.client.host
        rate_limit_result = await self.rate_limiter.check_rate_limit(
            client_ip, 
            self.security_manager.config.rate_limit_requests,
            self.security_manager.config.rate_limit_window
        )
        
        if not rate_limit_result["allowed"]:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": rate_limit_result["retry_after"]
                },
                headers={
                    "Retry-After": str(rate_limit_result["retry_after"]),
                    "X-RateLimit-Limit": str(rate_limit_result["limit"]),
                    "X-RateLimit-Remaining": str(rate_limit_result["remaining"])
                }
            )
        
        # Authentication
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid authorization header"}
            )
        
        token = auth_header.split(" ")[1]
        payload = self.security_manager.verify_token(token)
        
        # Add user context to request
        request.state.user = {
            "id": payload["user_id"],
            "role": payload["role"],
            "permissions": payload.get("permissions", [])
        }
        
        response = await call_next(request)
        return self._add_security_headers(response, start_time)
        
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.detail}
        )
    except Exception as e:
        logger.error(f"Authentication middleware error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

def _add_security_headers(self, response: Response, start_time: float) -> Response:
    """Add security headers to response"""
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Response-Time"] = f"{(time.time() - start_time):.3f}s"
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    return response
```

# ===================== PERMISSION SYSTEM =====================

class PermissionManager:
“”“Role-based access control”””

```
ROLE_PERMISSIONS = {
    "user": ["read_own", "upload_files", "create_tasks"],
    "agent": ["read_own", "write_own", "communicate", "execute_tasks"],
    "admin": ["read_all", "write_all", "manage_users", "system_config"],
    "system": ["*"]  # All permissions
}

@classmethod
def check_permission(cls, user_role: str, required_permission: str) -> bool:
    """Check if user has required permission"""
    user_permissions = cls.ROLE_PERMISSIONS.get(user_role, [])
    return "*" in user_permissions or required_permission in user_permissions

@classmethod
def require_permission(cls, permission: str):
    """Decorator for permission-based access control"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user from request (assuming FastAPI dependency injection)
            request = kwargs.get('request') or args[0] if args else None
            if hasattr(request, 'state') and hasattr(request.state, 'user'):
                user = request.state.user
                if not cls.check_permission(user["role"], permission):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied. Required: {permission}"
                    )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

# ===================== AUDIT LOGGING =====================

class AuditLogger:
“”“Comprehensive audit logging system”””

```
def __init__(self, redis_client):
    self.redis = redis_client

async def log_action(
    self,
    user_id: str,
    action: str,
    resource: str,
    result: str,
    metadata: Dict[str, Any] = None,
    ip_address: str = None
):
    """Log user action for audit trail"""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "result": result,
        "metadata": metadata or {},
        "ip_address": ip_address,
        "audit_id": str(uuid.uuid4())
    }
    
    # Store in Redis with TTL (30 days)
    key = f"audit:{datetime.utcnow().strftime('%Y-%m-%d')}:{uuid.uuid4()}"
    await self.redis.setex(key, 2592000, json.dumps(audit_entry))  # 30 days TTL
    
    # Log to structured logger
    logger.info("audit_action", **audit_entry)
```

# ===================== MIDDLEWARE FACTORY =====================

def create_security_middleware(
security_config: SecurityConfig,
redis_url: str = “redis://localhost:6379”
) -> tuple:
“”“Factory function to create all security middleware components”””

```
async def init_components():
    security_manager = SecurityManager(security_config)
    await security_manager.init_redis(redis_url)
    
    rate_limiter = RateLimiter(security_manager.redis_client)
    file_security = FileSecurityManager(security_config)
    audit_logger = AuditLogger(security_manager.redis_client)
    
    auth_middleware = AuthenticationMiddleware(None, security_manager, rate_limiter)
    
    return {
        "security_manager": security_manager,
        "rate_limiter": rate_limiter,
        "file_security": file_security,
        "audit_logger": audit_logger,
        "auth_middleware": auth_middleware,
        "permission_manager": PermissionManager
    }

return init_components
```

# ===================== EXAMPLE USAGE =====================

“””
Example usage in FastAPI application:

from fastapi import FastAPI, Depends
from ymera_middleware import create_security_middleware, SecurityConfig

app = FastAPI()

# Initialize security components

security_config = SecurityConfig(
jwt_secret=“your-secret-key”,
max_file_size=50 * 1024 * 1024,  # 50MB
rate_limit_requests=500
)

security_components = await create_security_middleware(security_config)()

# Add middleware

app.add_middleware(
type(security_components[“auth_middleware”]),
security_manager=security_components[“security_manager”],
rate_limiter=security_components[“rate_limiter”]
)

# Protected endpoint example

@app.post(”/upload”)
@PermissionManager.require_permission(“upload_files”)
async def upload_file(
file: UploadFile = File(…),
request: Request = None
):
file_info = await security_components[“file_security”].validate_file(file)

```
# Log the action
await security_components["audit_logger"].log_action(
    user_id=request.state.user["id"],
    action="file_upload",
    resource=file.filename,
    result="success",
    ip_address=request.client.host
)

return {"message": "File uploaded successfully", "file_info": file_info}
```

“””