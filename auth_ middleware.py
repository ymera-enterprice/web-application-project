"""
YMERA Enterprise Authentication Middleware
Production-Ready Authentication System with Multi-Agent Integration
"""

import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, urlparse
import re
import ipaddress
import base64

import jwt
import bcrypt
import pyotp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException, Request, Response, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import aioredis
import httpx
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
import logging
from contextlib import asynccontextmanager

# Import system components (from your main.py structure)
from ymera_core.database.manager import DatabaseManager
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.exceptions import YMERAException


class UserRole(str, Enum):
    """User roles hierarchy"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    API_USER = "api_user"
    GUEST = "guest"


class Permission(str, Enum):
    """Granular permissions"""
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_DEPLOY = "project:deploy"
    
    # Agent permissions
    AGENT_ORCHESTRATE = "agent:orchestrate"
    AGENT_MONITOR = "agent:monitor"
    AGENT_CONFIGURE = "agent:configure"
    AGENT_LEARN = "agent:learn"
    
    # Analysis permissions
    ANALYSIS_RUN = "analysis:run"
    ANALYSIS_VIEW = "analysis:view"
    ANALYSIS_EXPORT = "analysis:export"
    
    # Security permissions
    SECURITY_SCAN = "security:scan"
    SECURITY_VIEW = "security:view"
    SECURITY_MANAGE = "security:manage"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    
    # Learning permissions
    LEARNING_VIEW = "learning:view"
    LEARNING_MANAGE = "learning:manage"
    LEARNING_TRAIN = "learning:train"


class AuthenticationMethod(str, Enum):
    """Authentication methods"""
    PASSWORD = "password"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    MFA = "mfa"
    SSO = "sso"


class SessionStatus(str, Enum):
    """Session status types"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


# Pydantic Models
class UserSession(BaseModel):
    """User session model"""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    roles: List[UserRole] = Field(..., description="User roles")
    permissions: List[Permission] = Field(..., description="User permissions")
    auth_method: AuthenticationMethod = Field(..., description="Authentication method used")
    ip_address: str = Field(..., description="Client IP address")
    user_agent: str = Field(..., description="Client user agent")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    expires_at: datetime = Field(..., description="Session expiration time")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    mfa_verified: bool = Field(default=False, description="MFA verification status")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")


class AuthenticationRequest(BaseModel):
    """Authentication request model"""
    username: str = Field(..., min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    api_key: Optional[str] = Field(None)
    mfa_token: Optional[str] = Field(None, min_length=6, max_length=8)
    remember_me: bool = Field(default=False)
    client_info: Optional[Dict[str, str]] = Field(default_factory=dict)


class OAuth2Config(BaseModel):
    """OAuth2 configuration"""
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    userinfo_url: str
    redirect_uri: str
    scopes: List[str] = Field(default_factory=list)


class MFAConfig(BaseModel):
    """Multi-Factor Authentication configuration"""
    enabled: bool = Field(default=True)
    issuer: str = Field(default="YMERA Enterprise")
    totp_window: int = Field(default=1)
    backup_codes_count: int = Field(default=10)
    require_for_roles: List[UserRole] = Field(default=[UserRole.ADMIN, UserRole.SUPER_ADMIN])


class PasswordPolicy(BaseModel):
    """Password policy configuration"""
    min_length: int = Field(default=12)
    max_length: int = Field(default=128)
    require_uppercase: bool = Field(default=True)
    require_lowercase: bool = Field(default=True)
    require_numbers: bool = Field(default=True)
    require_special_chars: bool = Field(default=True)
    special_chars: str = Field(default="!@#$%^&*()_+-=[]{}|;:,.<>?")
    max_age_days: int = Field(default=90)
    history_count: int = Field(default=5)
    lockout_attempts: int = Field(default=5)
    lockout_duration_minutes: int = Field(default=30)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    enabled: bool = Field(default=True)
    default_requests_per_minute: int = Field(default=60)
    role_limits: Dict[UserRole, int] = Field(default_factory=lambda: {
        UserRole.GUEST: 10,
        UserRole.VIEWER: 30,
        UserRole.DEVELOPER: 100,
        UserRole.PROJECT_MANAGER: 150,
        UserRole.ADMIN: 300,
        UserRole.SUPER_ADMIN: 1000,
        UserRole.API_USER: 500
    })
    burst_multiplier: float = Field(default=2.0)
    sliding_window_minutes: int = Field(default=5)


class AuthConfig(BaseModel):
    """Authentication configuration"""
    secret_key: str = Field(..., min_length=32)
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    session_expire_minutes: int = Field(default=480)  # 8 hours
    max_sessions_per_user: int = Field(default=5)
    password_policy: PasswordPolicy = Field(default_factory=PasswordPolicy)
    mfa_config: MFAConfig = Field(default_factory=MFAConfig)
    rate_limit_config: RateLimitConfig = Field(default_factory=RateLimitConfig)
    oauth2_providers: Dict[str, OAuth2Config] = Field(default_factory=dict)
    allowed_origins: List[str] = Field(default_factory=list)
    secure_cookies: bool = Field(default=True)
    audit_enabled: bool = Field(default=True)


# Role-based permissions mapping
ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: [p for p in Permission],
    UserRole.ADMIN: [
        Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
        Permission.AGENT_ORCHESTRATE, Permission.AGENT_MONITOR, Permission.AGENT_CONFIGURE,
        Permission.ANALYSIS_RUN, Permission.ANALYSIS_VIEW, Permission.ANALYSIS_EXPORT,
        Permission.SECURITY_SCAN, Permission.SECURITY_VIEW, Permission.SECURITY_MANAGE,
        Permission.SYSTEM_MONITOR, Permission.LEARNING_VIEW, Permission.LEARNING_MANAGE,
    ],
    UserRole.PROJECT_MANAGER: [
        Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE, Permission.PROJECT_DEPLOY,
        Permission.AGENT_ORCHESTRATE, Permission.AGENT_MONITOR,
        Permission.ANALYSIS_RUN, Permission.ANALYSIS_VIEW, Permission.ANALYSIS_EXPORT,
        Permission.SECURITY_SCAN, Permission.SECURITY_VIEW,
        Permission.LEARNING_VIEW,
    ],
    UserRole.DEVELOPER: [
        Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
        Permission.AGENT_MONITOR, Permission.ANALYSIS_RUN, Permission.ANALYSIS_VIEW,
        Permission.SECURITY_SCAN, Permission.SECURITY_VIEW,
        Permission.LEARNING_VIEW,
    ],
    UserRole.ANALYST: [
        Permission.PROJECT_READ, Permission.ANALYSIS_RUN, Permission.ANALYSIS_VIEW, Permission.ANALYSIS_EXPORT,
        Permission.SECURITY_VIEW, Permission.LEARNING_VIEW,
    ],
    UserRole.VIEWER: [
        Permission.PROJECT_READ, Permission.ANALYSIS_VIEW, Permission.SECURITY_VIEW, Permission.LEARNING_VIEW,
    ],
    UserRole.API_USER: [
        Permission.PROJECT_READ, Permission.ANALYSIS_RUN, Permission.ANALYSIS_VIEW,
    ],
    UserRole.GUEST: [
        Permission.PROJECT_READ, Permission.ANALYSIS_VIEW,
    ],
}


class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_secure_key(length: int = 32) -> str:
        """Generate cryptographically secure key"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    @staticmethod
    def validate_password_policy(password: str, policy: PasswordPolicy) -> List[str]:
        """Validate password against policy"""
        errors = []
        
        if len(password) < policy.min_length:
            errors.append(f"Password must be at least {policy.min_length} characters long")
        
        if len(password) > policy.max_length:
            errors.append(f"Password must not exceed {policy.max_length} characters")
        
        if policy.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if policy.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if policy.require_numbers and not re.search(r'\d', password):
            errors.append("Password must contain at least one number")
        
        if policy.require_special_chars and not re.search(f'[{re.escape(policy.special_chars)}]', password):
            errors.append(f"Password must contain at least one special character: {policy.special_chars}")
        
        return errors
    
    @staticmethod
    def generate_api_key(prefix: str = "ymera") -> str:
        """Generate API key with prefix"""
        key = secrets.token_urlsafe(32)
        return f"{prefix}_{key}"
    
    @staticmethod
    def generate_mfa_secret() -> str:
        """Generate MFA secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate MFA backup codes"""
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    @staticmethod
    def encrypt_data(data: str, key: bytes) -> str:
        """Encrypt sensitive data"""
        f = Fernet(key)
        return f.encrypt(data.encode()).decode()
    
    @staticmethod
    def decrypt_data(encrypted_data: str, key: bytes) -> str:
        """Decrypt sensitive data"""
        f = Fernet(key)
        return f.decrypt(encrypted_data.encode()).decode()
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))


class AuditLogger:
    """Audit logging for authentication events"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    async def log_authentication(self, event: str, user_id: str, ip_address: str, 
                               user_agent: str, success: bool, details: Dict[str, Any] = None):
        """Log authentication event"""
        log_data = {
            "event_type": "authentication",
            "event": event,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        if success:
            self.logger.info(f"Authentication event: {event}", extra=log_data)
        else:
            self.logger.warning(f"Authentication failed: {event}", extra=log_data)
    
    async def log_authorization(self, user_id: str, resource: str, action: str, 
                              allowed: bool, ip_address: str):
        """Log authorization event"""
        log_data = {
            "event_type": "authorization",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "allowed": allowed,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if allowed:
            self.logger.info(f"Authorization granted: {action} on {resource}", extra=log_data)
        else:
            self.logger.warning(f"Authorization denied: {action} on {resource}", extra=log_data)


class SessionManager:
    """Session management with distributed support"""
    
    def __init__(self, redis_manager: RedisCacheManager, config: AuthConfig, logger: StructuredLogger):
        self.redis_manager = redis_manager
        self.config = config
        self.logger = logger
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
    
    async def create_session(self, user_id: str, username: str, roles: List[UserRole], 
                           auth_method: AuthenticationMethod, ip_address: str, 
                           user_agent: str, mfa_verified: bool = False) -> UserSession:
        """Create new user session"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.config.session_expire_minutes)
        
        # Get permissions for roles
        permissions = []
        for role in roles:
            permissions.extend(ROLE_PERMISSIONS.get(role, []))
        permissions = list(set(permissions))  # Remove duplicates
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            username=username,
            roles=roles,
            permissions=permissions,
            auth_method=auth_method,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            last_activity=now,
            expires_at=expires_at,
            mfa_verified=mfa_verified,
            refresh_token=SecurityUtils.generate_secure_key(),
            metadata={}
        )
        
        # Store session in Redis
        await self.redis_manager.set(
            f"{self.session_prefix}{session_id}",
            session.dict(),
            ttl=self.config.session_expire_minutes * 60
        )
        
        # Track user sessions
        await self._add_user_session(user_id, session_id)
        
        # Cleanup old sessions if limit exceeded
        await self._cleanup_user_sessions(user_id)
        
        self.logger.info(f"Session created for user {username}", extra={
            "session_id": session_id,
            "user_id": user_id,
            "auth_method": auth_method,
            "ip_address": ip_address
        })
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Retrieve session by ID"""
        session_data = await self.redis_manager.get(f"{self.session_prefix}{session_id}")
        if session_data:
            return UserSession(**session_data)
        return None
    
    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.last_activity = datetime.utcnow()
        
        await self.redis_manager.set(
            f"{self.session_prefix}{session_id}",
            session.dict(),
            ttl=self.config.session_expire_minutes * 60
        )
        
        return True
    
    async def revoke_session(self, session_id: str) -> bool:
        """Revoke specific session"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.REVOKED
        
        await self.redis_manager.set(
            f"{self.session_prefix}{session_id}",
            session.dict(),
            ttl=60  # Keep for short time for audit
        )
        
        await self._remove_user_session(session.user_id, session_id)
        
        self.logger.info(f"Session revoked", extra={
            "session_id": session_id,
            "user_id": session.user_id
        })
        
        return True
    
    async def revoke_user_sessions(self, user_id: str, except_session_id: str = None) -> int:
        """Revoke all sessions for a user"""
        user_sessions = await self._get_user_sessions(user_id)
        revoked_count = 0
        
        for session_id in user_sessions:
            if session_id != except_session_id:
                if await self.revoke_session(session_id):
                    revoked_count += 1
        
        return revoked_count
    
    async def _add_user_session(self, user_id: str, session_id: str):
        """Add session to user's session list"""
        key = f"{self.user_sessions_prefix}{user_id}"
        sessions = await self.redis_manager.get(key) or []
        sessions.append(session_id)
        await self.redis_manager.set(key, sessions, ttl=self.config.session_expire_minutes * 60)
    
    async def _remove_user_session(self, user_id: str, session_id: str):
        """Remove session from user's session list"""
        key = f"{self.user_sessions_prefix}{user_id}"
        sessions = await self.redis_manager.get(key) or []
        if session_id in sessions:
            sessions.remove(session_id)
            await self.redis_manager.set(key, sessions, ttl=self.config.session_expire_minutes * 60)
    
    async def _get_user_sessions(self, user_id: str) -> List[str]:
        """Get all session IDs for a user"""
        key = f"{self.user_sessions_prefix}{user_id}"
        return await self.redis_manager.get(key) or []
    
    async def _cleanup_user_sessions(self, user_id: str):
        """Clean up old sessions if limit exceeded"""
        sessions = await self._get_user_sessions(user_id)
        if len(sessions) > self.config.max_sessions_per_user:
            # Sort sessions by creation time and remove oldest
            session_data = []
            for session_id in sessions:
                session = await self.get_session(session_id)
                if session:
                    session_data.append((session_id, session.created_at))
            
            session_data.sort(key=lambda x: x[1])
            sessions_to_remove = session_data[:-self.config.max_sessions_per_user]
            
            for session_id, _ in sessions_to_remove:
                await self.revoke_session(session_id)


class TokenManager:
    """JWT token management"""
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self.algorithm = config.algorithm
        self.secret_key = config.secret_key
    
    def create_access_token(self, user_id: str, username: str, roles: List[UserRole], 
                          session_id: str, permissions: List[Permission] = None) -> str:
        """Create JWT access token"""
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=self.config.access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "username": username,
            "roles": [role.value for role in roles],
            "permissions": [perm.value for perm in permissions] if permissions else [],
            "session_id": session_id,
            "iat": now.timestamp(),
            "exp": expires_at.timestamp(),
            "type": "access"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str, session_id: str) -> str:
        """Create JWT refresh token"""
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.config.refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "session_id": session_id,
            "iat": now.timestamp(),
            "exp": expires_at.timestamp(),
            "type": "refresh"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )


class RateLimiter:
    """Advanced rate limiting with role-based limits"""
    
    def __init__(self, redis_manager: RedisCacheManager, config: RateLimitConfig):
        self.redis_manager = redis_manager
        self.config = config
        self.prefix = "rate_limit:"
    
    async def is_allowed(self, identifier: str, role: UserRole = UserRole.GUEST) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limit"""
        if not self.config.enabled:
            return True, {}
        
        limit = self.config.role_limits.get(role, self.config.default_requests_per_minute)
        window_seconds = self.config.sliding_window_minutes * 60
        
        now = int(time.time())
        window_start = now - window_seconds
        
        key = f"{self.prefix}{identifier}"
        
        # Use sliding window log algorithm
        pipe = self.redis_manager.redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcount(key, window_start, now)
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        current_requests = results[2]
        
        allowed = current_requests <= limit
        
        rate_limit_info = {
            "limit": limit,
            "remaining": max(0, limit - current_requests),
            "reset_time": now + window_seconds,
            "window_seconds": window_seconds
        }
        
        return allowed, rate_limit_info


class OAuth2Manager:
    """OAuth2/OpenID Connect integration"""
    
    def __init__(self, providers: Dict[str, OAuth2Config]):
        self.providers = providers
        self.http_client = httpx.AsyncClient()
    
    async def get_authorization_url(self, provider: str, state: str) -> str:
        """Generate OAuth2 authorization URL"""
        if provider not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown OAuth2 provider: {provider}"
            )
        
        config = self.providers[provider]
        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": " ".join(config.scopes),
            "response_type": "code",
            "state": state
        }
        
        return f"{config.authorization_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    async def exchange_code(self, provider: str, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        if provider not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown OAuth2 provider: {provider}"
            )
        
        config = self.providers[provider]
        
        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config.redirect_uri
        }
        
        response = await self.http_client.post(config.token_url, data=data)
        response.raise_for_status()
        
        return response.json()
    
    async def get_user_info(self, provider: str, access_token: str) -> Dict[str, Any]:
        """Get user information from OAuth2 provider"""
        if provider not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown OAuth2 provider: {provider}"
            )
        
        config = self.providers[provider]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = await self.http_client.get(config.userinfo_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


class MFAManager:
    """Multi-Factor Authentication management"""
    
    def __init__(self, config: MFAConfig):
        self.config = config
    
    def generate_qr_code_url(self, username: str, secret: str) -> str:
        """Generate QR code URL for TOTP setup"""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=username,
            issuer_name=self.config.issuer
        )
    
    def verify_totp_token(self, secret: str, token: str) -> bool:
        """Verify TOTP token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=self.config.totp_window)
    
    def verify_backup_code(self, user_backup_codes: List[str], code: str) -> Tuple[bool, List[str]]:
        """Verify backup code and remove it from list"""
        code_upper = code.upper().strip()
        if code_upper in user_backup_codes:
            user_backup_codes.remove(code_upper)
            return True, user_backup_codes
        return False, user_backup_codes
    
    def is_mfa_required(self, roles: List[UserRole]) -> bool:
        """Check if MFA is required for given roles"""
        if not self.config.enabled:
            return False
        
        return any(role in self.config.require_for_roles for role in roles)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Main authentication middleware"""
    
    def __init__(
        self,
        app,
        config: AuthConfig,
        db_manager: DatabaseManager,
        redis_manager: RedisCacheManager,
        logger: StructuredLogger
    ):
        super().__init__(app)
        self.config = config
        self.db_manager = db_manager
        self.redis_manager = redis_manager
        self.logger = logger
        
        # Initialize components
        self.security_utils = SecurityUtils()
        self.audit_logger = AuditLogger(logger)
        self.session_manager = SessionManager(redis_manager, config, logger)
        self.token_manager = TokenManager(config)
        self.rate_limiter = RateLimiter(redis_manager, config.rate_limit_config)
        self.oauth2_manager = OAuth2Manager(config.oauth2_providers)
        self.mfa_manager = MFAManager(config.mfa_config)
        
        # Public endpoints that don't require authentication
        self.public_endpoints = {
            "/", "/health", "/api/docs", "/api/redoc", "/api/openapi.json",
            "/api/v1/auth/login", "/api/v1/auth/register", "/api # Public endpoints that don't require authentication
        self.public_endpoints = {
            "/", "/health", "/api/docs", "/api/redoc", "/api/openapi.json",
            "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/oauth2",
            "/api/v1/auth/refresh", "/api/v1/auth/forgot-password", "/api/v1/auth/reset-password"
        }
        
        # Initialize security bearer
        self.security = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch method"""
        start_time = time.time()
        
        try:
            # Skip authentication for public endpoints
            if self._is_public_endpoint(request.url.path):
                response = await call_next(request)
                return response
            
            # Extract client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            # Rate limiting check
            await self._check_rate_limit(request, client_ip)
            
            # Extract and validate authentication
            session = await self._authenticate_request(request, client_ip, user_agent)
            
            # Add session to request state
            request.state.session = session
            request.state.user_id = session.user_id
            request.state.username = session.username
            request.state.roles = session.roles
            request.state.permissions = session.permissions
            
            # Update session activity
            await self.session_manager.update_session_activity(session.session_id)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            # Log successful request
            processing_time = time.time() - start_time
            await self.audit_logger.log_authentication(
                "request_processed",
                session.user_id,
                client_ip,
                user_agent,
                True,
                {"processing_time": processing_time, "endpoint": request.url.path}
            )
            
            return response
            
        except HTTPException as e:
            # Log authentication failure
            await self.audit_logger.log_authentication(
                "authentication_failed",
                "unknown",
                client_ip,
                user_agent,
                False,
                {"error": str(e.detail), "status_code": e.status_code}
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={"error": e.detail, "timestamp": datetime.utcnow().isoformat()}
            )
        
        except Exception as e:
            # Log unexpected errors
            self.logger.error(f"Authentication middleware error: {str(e)}", extra={
                "client_ip": client_ip,
                "endpoint": request.url.path,
                "error_type": type(e).__name__
            })
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal server error", "timestamp": datetime.utcnow().isoformat()}
            )
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        return any(path.startswith(endpoint) for endpoint in self.public_endpoints)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, request: Request, client_ip: str):
        """Check rate limiting"""
        identifier = client_ip
        role = UserRole.GUEST  # Default role for unauthenticated requests
        
        allowed, rate_info = await self.rate_limiter.is_allowed(identifier, role)
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset_time"]),
                    "Retry-After": str(rate_info["window_seconds"])
                }
            )
    
    async def _authenticate_request(self, request: Request, client_ip: str, user_agent: str) -> UserSession:
        """Authenticate incoming request"""
        # Try different authentication methods
        
        # 1. Bearer token authentication
        credentials = await self.security(request)
        if credentials:
            return await self._authenticate_bearer_token(credentials.credentials, client_ip, user_agent)
        
        # 2. API key authentication
        api_key = request.headers.get("x-api-key") or request.query_params.get("api_key")
        if api_key:
            return await self._authenticate_api_key(api_key, client_ip, user_agent)
        
        # 3. Session cookie authentication
        session_cookie = request.cookies.get("ymera_session")
        if session_cookie:
            return await self._authenticate_session_cookie(session_cookie, client_ip, user_agent)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    async def _authenticate_bearer_token(self, token: str, client_ip: str, user_agent: str) -> UserSession:
        """Authenticate using Bearer token"""
        try:
            payload = self.token_manager.verify_token(token)
            
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            session_id = payload.get("session_id")
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format"
                )
            
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found or expired"
                )
            
            if session.status != SessionStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session is not active"
                )
            
            return session
            
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    async def _authenticate_api_key(self, api_key: str, client_ip: str, user_agent: str) -> UserSession:
        """Authenticate using API key"""
        # Query database for API key
        async with self.db_manager.get_connection() as conn:
            result = await conn.fetch_one(
                """
                SELECT u.id, u.username, u.roles, u.is_active, ak.permissions, ak.rate_limit
                FROM users u 
                JOIN api_keys ak ON u.id = ak.user_id 
                WHERE ak.key_hash = ? AND ak.is_active = 1 AND ak.expires_at > ?
                """,
                (hashlib.sha256(api_key.encode()).hexdigest(), datetime.utcnow())
            )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key"
            )
        
        if not result["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        # Create temporary session for API key authentication
        roles = [UserRole(role) for role in result["roles"].split(",")]
        
        # Create session (API key sessions are typically shorter-lived)
        session = await self.session_manager.create_session(
            user_id=result["id"],
            username=result["username"],
            roles=roles,
            auth_method=AuthenticationMethod.API_KEY,
            ip_address=client_ip,
            user_agent=user_agent,
            mfa_verified=True  # API keys bypass MFA
        )
        
        return session
    
    async def _authenticate_session_cookie(self, session_id: str, client_ip: str, user_agent: str) -> UserSession:
        """Authenticate using session cookie"""
        session = await self.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session is not active"
            )
        
        # Verify IP address consistency (optional security check)
        if session.ip_address != client_ip:
            self.logger.warning("IP address mismatch for session", extra={
                "session_id": session_id,
                "original_ip": session.ip_address,
                "current_ip": client_ip
            })
            # Could optionally revoke session or require re-authentication
        
        return session
    
    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"


class AuthService:
    """Main authentication service"""
    
    def __init__(
        self,
        config: AuthConfig,
        db_manager: DatabaseManager,
        redis_manager: RedisCacheManager,
        logger: StructuredLogger
    ):
        self.config = config
        self.db_manager = db_manager
        self.redis_manager = redis_manager
        self.logger = logger
        
        # Initialize components
        self.security_utils = SecurityUtils()
        self.audit_logger = AuditLogger(logger)
        self.session_manager = SessionManager(redis_manager, config, logger)
        self.token_manager = TokenManager(config)
        self.rate_limiter = RateLimiter(redis_manager, config.rate_limit_config)
        self.oauth2_manager = OAuth2Manager(config.oauth2_providers)
        self.mfa_manager = MFAManager(config.mfa_config)
    
    async def authenticate_user(self, auth_request: AuthenticationRequest, 
                              client_ip: str, user_agent: str) -> Tuple[UserSession, str, str]:
        """Authenticate user and create session"""
        
        # Rate limiting check
        allowed, rate_info = await self.rate_limiter.is_allowed(
            f"login:{client_ip}", UserRole.GUEST
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts"
            )
        
        # Authenticate user
        user_data = await self._verify_credentials(auth_request)
        
        # Check MFA if required
        roles = [UserRole(role) for role in user_data["roles"].split(",")]
        if self.mfa_manager.is_mfa_required(roles):
            if not auth_request.mfa_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="MFA token required"
                )
            
            mfa_verified = await self._verify_mfa(user_data["id"], auth_request.mfa_token)
            if not mfa_verified:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA token"
                )
        else:
            mfa_verified = True
        
        # Create session
        auth_method = AuthenticationMethod.PASSWORD if auth_request.password else AuthenticationMethod.API_KEY
        session = await self.session_manager.create_session(
            user_id=user_data["id"],
            username=user_data["username"],
            roles=roles,
            auth_method=auth_method,
            ip_address=client_ip,
            user_agent=user_agent,
            mfa_verified=mfa_verified
        )
        
        # Create tokens
        access_token = self.token_manager.create_access_token(
            user_id=session.user_id,
            username=session.username,
            roles=session.roles,
            session_id=session.session_id,
            permissions=session.permissions
        )
        
        refresh_token = self.token_manager.create_refresh_token(
            user_id=session.user_id,
            session_id=session.session_id
        )
        
        # Update last login
        await self._update_last_login(user_data["id"], client_ip)
        
        # Audit log
        await self.audit_logger.log_authentication(
            "login_success",
            session.user_id,
            client_ip,
            user_agent,
            True,
            {"auth_method": auth_method, "mfa_used": mfa_verified}
        )
        
        return session, access_token, refresh_token
    
    async def refresh_token(self, refresh_token: str, client_ip: str, user_agent: str) -> Tuple[str, str]:
        """Refresh access token using refresh token"""
        try:
            payload = self.token_manager.verify_token(refresh_token)
            
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            session_id = payload.get("session_id")
            user_id = payload.get("sub")
            
            session = await self.session_manager.get_session(session_id)
            if not session or session.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            if session.status != SessionStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session is not active"
                )
            
            # Create new tokens
            new_access_token = self.token_manager.create_access_token(
                user_id=session.user_id,
                username=session.username,
                roles=session.roles,
                session_id=session.session_id,
                permissions=session.permissions
            )
            
            new_refresh_token = self.token_manager.create_refresh_token(
                user_id=session.user_id,
                session_id=session.session_id
            )
            
            # Update session activity
            await self.session_manager.update_session_activity(session_id)
            
            return new_access_token, new_refresh_token
            
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    
    async def logout(self, session_id: str, client_ip: str, user_agent: str):
        """Logout user and revoke session"""
        session = await self.session_manager.get_session(session_id)
        if session:
            await self.session_manager.revoke_session(session_id)
            
            await self.audit_logger.log_authentication(
                "logout",
                session.user_id,
                client_ip,
                user_agent,
                True
            )
    
    async def create_user(self, username: str, email: str, password: str, 
                         roles: List[UserRole], created_by: str) -> Dict[str, Any]:
        """Create new user account"""
        
        # Validate password policy
        password_errors = self.security_utils.validate_password_policy(
            password, self.config.password_policy
        )
        if password_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": password_errors}
            )
        
        # Hash password
        password_hash = self.security_utils.hash_password(password)
        
        # Generate MFA secret if required
        mfa_secret = None
        if self.mfa_manager.is_mfa_required(roles):
            mfa_secret = self.security_utils.generate_mfa_secret()
        
        # Create user in database
        user_id = str(uuid.uuid4())
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, email, password_hash, roles, mfa_secret, 
                                 created_by, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    user_id,
                    username,
                    email,
                    password_hash,
                    ",".join([role.value for role in roles]),
                    mfa_secret,
                    created_by,
                    datetime.utcnow()
                )
            )
        
        result = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "roles": roles,
            "mfa_required": bool(mfa_secret)
        }
        
        if mfa_secret:
            result["mfa_qr_code"] = self.mfa_manager.generate_qr_code_url(username, mfa_secret)
            result["mfa_backup_codes"] = self.security_utils.generate_backup_codes()
        
        return result
    
    async def generate_api_key(self, user_id: str, name: str, permissions: List[Permission],
                              expires_days: int = 365) -> Dict[str, Any]:
        """Generate API key for user"""
        api_key = self.security_utils.generate_api_key()
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO api_keys (user_id, name, key_hash, permissions, expires_at, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    user_id,
                    name,
                    key_hash,
                    ",".join([perm.value for perm in permissions]),
                    expires_at,
                    datetime.utcnow()
                )
            )
        
        return {
            "api_key": api_key,
            "name": name,
            "permissions": permissions,
            "expires_at": expires_at.isoformat()
        }
    
    async def _verify_credentials(self, auth_request: AuthenticationRequest) -> Dict[str, Any]:
        """Verify user credentials"""
        async with self.db_manager.get_connection() as conn:
            user_data = await conn.fetch_one(
                """
                SELECT id, username, password_hash, roles, is_active, failed_login_attempts,
                       locked_until, mfa_secret, backup_codes
                FROM users 
                WHERE username = ? AND is_active = 1
                """,
                (auth_request.username,)
            )
        
        if not user_data:
            # Prevent user enumeration by taking same time as password verification
            self.security_utils.hash_password("dummy_password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check account lockout
        if (user_data["locked_until"] and 
            datetime.fromisoformat(user_data["locked_until"]) > datetime.utcnow()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is temporarily locked"
            )
        
        # Verify password
        if auth_request.password:
            if not self.security_utils.verify_password(
                auth_request.password, user_data["password_hash"]
            ):
                await self._handle_failed_login(user_data["id"])
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
        
        # Reset failed login attempts on success
        await self._reset_failed_login_attempts(user_data["id"])
        
        return user_data
    
    async def _verify_mfa(self, user_id: str, mfa_token: str) -> bool:
        """Verify MFA token"""
        async with self.db_manager.get_connection() as conn:
            user_data = await conn.fetch_one(
                "SELECT mfa_secret, backup_codes FROM users WHERE id = ?",
                (user_id,)
            )
        
        if not user_data:
            return False
        
        # Try TOTP verification first
        if user_data["mfa_secret"]:
            if self.mfa_manager.verify_totp_token(user_data["mfa_secret"], mfa_token):
                return True
        
        # Try backup code verification
        if user_data["backup_codes"]:
            backup_codes = json.loads(user_data["backup_codes"])
            is_valid, updated_codes = self.mfa_manager.verify_backup_code(backup_codes, mfa_token)
            
            if is_valid:
                # Update backup codes in database
                async with self.db_manager.get_connection() as conn:
                    await conn.execute(
                        "UPDATE users SET backup_codes = ? WHERE id = ?",
                        (json.dumps(updated_codes), user_id)
                    )
                return True
        
        return False
    
    async def _handle_failed_login(self, user_id: str):
        """Handle failed login attempt"""
        async with self.db_manager.get_connection() as conn:
            result = await conn.fetch_one(
                "SELECT failed_login_attempts FROM users WHERE id = ?",
                (user_id,)
            )
            
            attempts = (result["failed_login_attempts"] or 0) + 1
            locked_until = None
            
            if attempts >= self.config.password_policy.lockout_attempts:
                locked_until = datetime.utcnow() + timedelta(
                    minutes=self.config.password_policy.lockout_duration_minutes
                )
            
            await conn.execute(
                "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                (attempts, locked_until, user_id)
            )
    
    async def _reset_failed_login_attempts(self, user_id: str):
        """Reset failed login attempts on successful login"""
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
                (user_id,)
            )
    
    async def _update_last_login(self, user_id: str, ip_address: str):
        """Update user's last login information"""
        async with self.db_manager.get_connection() as conn:
            await conn.execute(
                "UPDATE users SET last_login = ?, last_login_ip = ? WHERE id = ?",
                (datetime.utcnow(), ip_address, user_id)
            )


# Authorization decorators and dependencies
def require_permissions(*required_permissions: Permission):
    """Decorator to require specific permissions"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            session = getattr(request.state, 'session', None)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_permissions = set(session.permissions)
            required_perms = set(required_permissions)
            
            if not required_perms.issubset(user_permissions):
                missing_perms = required_perms - user_permissions
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permissions: {', '.join([p.value for p in missing_perms])}"
                )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_roles(*required_roles: UserRole):
    """Decorator to require specific roles"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            session = getattr(request.state, 'session', None)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_roles = set(session.roles)
            required_role_set = set(required_roles)
            
            if not user_roles.intersection(required_role_set):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {', '.join([r.value for r in required_roles])}"
                )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# FastAPI dependencies
async def get_current_session(request: Request) -> UserSession:
    """Get current user session from request"""
    session = getattr(request.state, 'session', None)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return session


async def get_current_user_id(session: UserSession = Depends(get_current_session)) -> str:
    """Get current user ID"""
    return session.user_id


async def get_current_username(session: UserSession = Depends(get_current_session)) -> str:
    """Get current username"""
    return session.username


async def get_current_roles(session: UserSession = Depends(get_current_session)) -> List[UserRole]:
    """Get current user roles"""
    return session.roles


async def get_current_permissions(session: UserSession = Depends(get_current_session)) -> List[Permission]:
    """Get current user permissions"""
    return session.permissions


# Utility functions for integration
def create_auth_config(
    secret_key: str = None,
    redis_url: str = "redis://localhost:6379",
    session_expire_minutes: int = 480,
    enable_mfa: bool = True,
    oauth2_providers: Dict[str, OAuth2Config] = None
) -> AuthConfig:
    """Create authentication configuration"""
    if not secret_key:
        secret_key = SecurityUtils.generate_secure_key(64)
    
    return AuthConfig(
        secret_key=secret_key,
        session_expire_minutes=session_expire_minutes,
        mfa_config=MFAConfig(enabled=enable_mfa),
        oauth2_providers=oauth2_providers or {}
    )


async def initialize_auth_system(
    app,
    config: AuthConfig,
    db_manager: DatabaseManager,
    redis_manager: RedisCacheManager,
    logger: StructuredLogger
) -> Tuple[AuthenticationMiddleware, AuthService]:
    """Initialize authentication system"""
    
    # Create authentication service
    auth_service = AuthService(config, db_manager, redis_manager, logger)
    
    # Create and add middleware
    auth_middleware = AuthenticationMiddleware(app, config, db_manager, redis_manager, logger)
    app.add_middleware(AuthenticationMiddleware, 
                      config=config, 
                      db_manager=db_manager, 
                      redis_manager=redis_manager, 
                      logger=logger)
    
    return auth_middleware, auth_service


# Exception classes for authentication errors
class AuthenticationError(YMERAException):
    """Base authentication error"""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials error"""
    pass


class SessionExpiredError(AuthenticationError):
    """Session expired error"""
    pass


class InsufficientPermissionsError(AuthenticationError):
    """Insufficient permissions error"""
    pass


class RateLimitExceededError(AuthenticationError):
    """Rate limit exceeded error"""
    pass


class MFARequiredError(AuthenticationError):
    """MFA required error"""
    pass