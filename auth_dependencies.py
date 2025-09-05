"""
YMERA Enterprise API Dependencies - Authentication & Authorization
Production-ready authentication system with role-based access control,
session management, and security monitoring
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, List, Set, Union
from datetime import datetime, timedelta
import asyncio
import logging
import jwt
from passlib.context import CryptContext
import secrets
import hashlib
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
from user_agents import parse
import functools

from ymera_core.security.auth_manager import AuthManager
from ymera_core.database.models import User, UserSession, UserRole, Permission
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.exceptions import YMERAException
from .core import dependency_manager, with_dependency_monitoring


class PermissionLevel(Enum):
    """Permission levels for role-based access control"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserRole(Enum):
    """User roles in the YMERA system"""
    VIEWER = "viewer"
    DEVELOPER = "developer"
    PROJECT_MANAGER = "project_manager"
    SECURITY_ANALYST = "security_analyst"
    SYSTEM_ADMIN = "system_admin"
    SUPER_ADMIN = "super_admin"


@dataclass
class SecurityContext:
    """Complete security context for authenticated requests"""
    user_id: str
    username: str
    email: str
    roles: List[UserRole]
    permissions: Set[str]
    session_id: str
    ip_address: str
    user_agent: str
    authenticated_at: datetime
    last_activity: datetime
    mfa_verified: bool = False
    session_expires_at: Optional[datetime] = None
    rate_limit_remaining: int = 1000
    security_flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthenticationResult:
    """Result of authentication attempt"""
    success: bool
    user: Optional[Dict[str, Any]] = None
    security_context: Optional[SecurityContext] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    requires_mfa: bool = False
    lockout_until: Optional[datetime] = None


class SecurityMiddleware:
    """Advanced security middleware with threat detection"""
    
    def __init__(self):
        self.logger = logging.getLogger("ymera.security")
        self.suspicious_patterns = {
            'sql_injection': [
                r"(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)",
                r"(?i)(\-\-|\#|\/\*|\*\/)",
                r"(?i)(or\s+1=1|and\s+1=1|'=')"
            ],
            'xss': [
                r"(?i)(<script|<iframe|<object|<embed|<form)",
                r"(?i)(javascript:|vbscript:|data:)",
                r"(?i)(onload|onerror|onclick|onmouseover)="
            ],
            'directory_traversal': [
                r"(?i)(\.\.\/|\.\.\\|\.\./|\.\.\\)",
                r"(?i)(/etc/passwd|/proc/|/sys/|\.ssh/)",
                r"(?i)(boot\.ini|win\.ini|system\.ini)"
            ]
        }
    
    async def analyze_request_security(self, request: Request) -> Dict[str, Any]:
        """Analyze request for security threats"""
        threats = []
        risk_score = 0
        
        # Analyze URL and query parameters
        full_url = str(request.url)
        for threat_type, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                import re
                if re.search(pattern, full_url):
                    threats.append(f"{threat_type}_in_url")
                    risk_score += 10
        
        # Analyze headers
        suspicious_headers = []
        for header_name, header_value in request.headers.items():
            if header_name.lower() in ['x-forwarded-for', 'x-real-ip', 'x-originating-ip']:
                # Check for header injection
                if '\n' in header_value or '\r' in header_value:
                    threats.append("header_injection")
                    risk_score += 20
            
            # Check user agent
            if header_name.lower() == 'user-agent':
                if len(header_value) > 1000 or not header_value.strip():
                    threats.append("suspicious_user_agent")
                    risk_score += 5
        
        # Rate limiting analysis
        client_ip = self._get_client_ip(request)
        rate_limit_info = await self._check_rate_limits(client_ip)
        
        if rate_limit_info['exceeded']:
            threats.append("rate_limit_exceeded")
            risk_score += 15
        
        # Geographic analysis (if available)
        geo_risk = await self._analyze_geographic_risk(client_ip)
        risk_score += geo_risk
        
        return {
            'threats': threats,
            'risk_score': risk_score,
            'client_ip': client_ip,
            'rate_limit_info': rate_limit_info,
            'timestamp': datetime.utcnow(),
            'requires_additional_verification': risk_score > 20
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers"""
        # Check X-Forwarded-For header first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        return request.client.host if request.client else 'unknown'
    
    async def _check_rate_limits(self, client_ip: str) -> Dict[str, Any]:
        """Check rate limits for client IP"""
        try:
            cache_manager = await dependency_manager.get_dependency('cache_manager')
            
            # Check current request count
            cache_key = f"rate_limit:{client_ip}:requests"
            current_count = await cache_manager.get(cache_key)
            
            if current_count is None:
                current_count = 0
                await cache_manager.set(cache_key, 1, ttl=3600)  # 1 hour window
            else:
                current_count = int(current_count)
                await cache_manager.incr(cache_key)
            
            # Rate limits: 1000 requests per hour for general API
            rate_limit = 1000
            exceeded = current_count >= rate_limit
            
            return {
                'current_count': current_count,
                'limit': rate_limit,
                'exceeded': exceeded,
                'reset_time': datetime.utcnow() + timedelta(hours=1)
            }
            
        except Exception as e:
            logging.getLogger("ymera.security").warning(f"Rate limit check failed: {e}")
            return {
                'current_count': 0,
                'limit': 1000,
                'exceeded': False,
                'reset_time': datetime.utcnow() + timedelta(hours=1)
            }
    
    async def _analyze_geographic_risk(self, client_ip: str) -> int:
        """Analyze geographic risk based on IP address"""
        try:
            # Basic IP validation
            ip = ipaddress.ip_address(client_ip)
            
            # Private IP addresses are low risk
            if ip.is_private or ip.is_loopback:
                return 0
            
            # Could integrate with GeoIP database for more sophisticated analysis
            # For now, return moderate risk for public IPs
            return 2
            
        except ValueError:
            # Invalid IP format
            return 5


class AuthenticationService:
    """Enhanced authentication service with security monitoring"""
    
    def __init__(self):
        self.logger = logging.getLogger("ymera.auth")
        self.security_middleware = SecurityMiddleware()
        self.failed_attempts = {}  # In production, use Redis
        self.active_sessions = {}  # In production, use Redis
        
        # Security configuration
        self.max_failed_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        self.session_timeout = timedelta(hours=8)
        self.mfa_required_roles = {UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN}
    
    @with_dependency_monitoring("auth_manager")
    async def authenticate_user(self, token: str, request: Request) -> AuthenticationResult:
        """Authenticate user with comprehensive security analysis"""
        try:
            # Security analysis
            security_analysis = await self.security_middleware.analyze_request_security(request)
            
            if security_analysis['risk_score'] > 50:
                self.logger.warning(
                    "High-risk authentication attempt blocked",
                    extra={
                        "client_ip": security_analysis['client_ip'],
                        "threats": security_analysis['threats'],
                        "risk_score": security_analysis['risk_score']
                    }
                )
                return AuthenticationResult(
                    success=False,
                    error_code="HIGH_RISK_BLOCKED",
                    error_message="Authentication blocked due to security concerns"
                )
            
            # Get authentication manager
            auth_manager = await dependency_manager.get_dependency('auth_manager')
            
            # Decode and validate token
            try:
                payload = auth_manager.decode_token(token)
                user_id = payload.get('sub')
                session_id = payload.get('session_id')
                
                if not user_id or not session_id:
                    raise jwt.InvalidTokenError("Missing user_id or session_id")
                
            except jwt.ExpiredSignatureError:
                return AuthenticationResult(
                    success=False,
                    error_code="TOKEN_EXPIRED",
                    error_message="Authentication token has expired"
                )
            except jwt.InvalidTokenError as e:
                return AuthenticationResult(
                    success=False,
                    error_code="INVALID_TOKEN",
                    error_message="Invalid authentication token"
                )
            
            # Check if user is locked out
            if await self._is_user_locked_out(user_id):
                lockout_info = self.failed_attempts.get(user_id, {})
                return AuthenticationResult(
                    success=False,
                    error_code="USER_LOCKED_OUT",
                    error_message="User account is temporarily locked",
                    lockout_until=lockout_info.get('lockout_until')
                )
            
            # Retrieve user information
            db_manager = await dependency_manager.get_dependency('db_manager')
            async with db_manager.get_session() as session:
                # Get user with roles and permissions
                user = await self._get_user_with_permissions(session, user_id)
                
                if not user:
                    await self._record_failed_attempt(user_id, "user_not_found")
                    return AuthenticationResult(
                        success=False,
                        error_code="USER_NOT_FOUND",
                        error_message="User not found"
                    )
                
                if not user.get('is_active'):
                    return AuthenticationResult(
                        success=False,
                        error_code="USER_INACTIVE",
                        error_message="User account is inactive"
                    )
            
            # Validate session
            session_valid = await self._validate_session(user_id, session_id, request)
            if not session_valid:
                return AuthenticationResult(
                    success=False,
                    error_code="INVALID_SESSION",
                    error_message="Session is invalid or expired"
                )
            
            # Check MFA requirements
            user_roles = [UserRole(role) for role in user.get('roles', [])]
            requires_mfa = any(role in self.mfa_required_roles for role in user_roles)
            mfa_verified = payload.get('mfa_verified', False)
            
            if requires_mfa and not mfa_verified:
                return AuthenticationResult(
                    success=False,
                    error_code="MFA_REQUIRED",
                    error_message="Multi-factor authentication required",
                    requires_mfa=True
                )
            
            # Create security context
            security_context = SecurityContext(
                user_id=user_id,
                username=user['username'],
                email=user['email'],
                roles=user_roles,
                permissions=set(user.get('permissions', [])),
                session_id=session_id,
                ip_address=security_analysis['client_ip'],
                user_agent=request.headers.get('user-agent', ''),
                authenticated_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                mfa_verified=mfa_verified,
                session_expires_at=datetime.utcnow() + self.session_timeout,
                rate_limit_remaining=security_analysis['rate_limit_info']['limit'] - security_analysis['rate_limit_info']['current_count'],
                security_flags=security_analysis
            )
            
            # Update session activity
            await self._update_session_activity(user_id, session_id, security_context)
            
            # Clear any previous failed attempts
            if user_id in self.failed_attempts:
                del self.failed_attempts[user_id]
            
            self.logger.info(
                "User authentication successful",
                extra={
                    "user_id": user_id,
                    "username": user['username'],
                    "client_ip": security_analysis['client_ip'],
                    "user_agent": request.headers.get('user-agent', ''),
                    "session_id": session_id
                }
            )
            
            return AuthenticationResult(
                success=True,
                user=user,
                security_context=security_context
            )
            
        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return AuthenticationResult(
                success=False,
                error_code="AUTHENTICATION_ERROR",
                error_message="Internal authentication error"
            )
    
    async def _get_user_with_permissions(self, session, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user with roles and permissions from database"""
        # This would be implemented with actual database queries
        # For now, returning a mock structure
        try:
            # In production, this would query the actual database
            # query = session.query(User).filter(User.id == user_id).first()
            # roles = query.roles
            # permissions = [p.name for role in roles for p in role.permissions]
            
            # Mock implementation - replace with actual database queries
            return {
                "id": user_id,
                "username": f"user_{user_id}",
                "email": f"user_{user_id}@example.com",
                "is_active": True,
                "roles": ["developer"],
                "permissions": ["read", "write"],
                "created_at": datetime.utcnow(),
                "last_login": datetime.utcnow()
            }
        except Exception as e:
            self.logger.error(f"Error retrieving user: {str(e)}")
            return None
    
    async def _validate_session(self, user_id: str, session_id: str, request: Request) -> bool:
        """Validate user session"""
        try:
            cache_manager = await dependency_manager.get_dependency('cache_manager')
            
            # Check session in cache
            session_key = f"session:{user_id}:{session_id}"
            session_data = await cache_manager.get(session_key)
            
            if not session_data:
                return False
            
            # Validate session data
            session_info = eval(session_data) if isinstance(session_data, str) else session_data
            
            # Check expiration
            if datetime.fromisoformat(session_info['expires_at']) < datetime.utcnow():
                await cache_manager.delete(session_key)
                return False
            
            # Check IP consistency (optional, can be disabled for mobile users)
            client_ip = self.security_middleware._get_client_ip(request)
            if session_info.get('ip_address') != client_ip:
                self.logger.warning(
                    "Session IP mismatch detected",
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                        "original_ip": session_info.get('ip_address'),
                        "current_ip": client_ip
                    }
                )
                # Could optionally invalidate session or require re-authentication
            
            return True
            
        except Exception as e:
            self.logger.error(f"Session validation error: {str(e)}")
            return False
    
    async def _update_session_activity(self, user_id: str, session_id: str, security_context: SecurityContext):
        """Update session activity timestamp"""
        try:
            cache_manager = await dependency_manager.get_dependency('cache_manager')
            
            session_key = f"session:{user_id}:{session_id}"
            session_data = {
                "user_id": user_id,
                "session_id": session_id,
                "ip_address": security_context.ip_address,
                "user_agent": security_context.user_agent,
                "last_activity": security_context.last_activity.isoformat(),
                "expires_at": security_context.session_expires_at.isoformat(),
                "mfa_verified": security_context.mfa_verified
            }
            
            # Update session with extended TTL
            await cache_manager.set(
                session_key, 
                str(session_data), 
                ttl=int(self.session_timeout.total_seconds())
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update session activity: {str(e)}")
    
    async def _is_user_locked_out(self, user_id: str) -> bool:
        """Check if user is currently locked out"""
        if user_id not in self.failed_attempts:
            return False
        
        attempt_info = self.failed_attempts[user_id]
        if attempt_info['count'] >= self.max_failed_attempts:
            lockout_until = attempt_info.get('lockout_until')
            if lockout_until and datetime.utcnow() < lockout_until:
                return True
            else:
                # Lockout period expired, clear failed attempts
                del self.failed_attempts[user_id]
        
        return False
    
    async def _record_failed_attempt(self, user_id: str, reason: str):
        """Record failed authentication attempt"""
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = {
                'count': 0,
                'first_attempt': datetime.utcnow(),
                'attempts': []
            }
        
        attempt_info = self.failed_attempts[user_id]
        attempt_info['count'] += 1
        attempt_info['last_attempt'] = datetime.utcnow()
        attempt_info['attempts'].append({
            'timestamp': datetime.utcnow(),
            'reason': reason
        })
        
        # Lock user if too many failed attempts
        if attempt_info['count'] >= self.max_failed_attempts:
            attempt_info['lockout_until'] = datetime.utcnow() + self.lockout_duration
            
            self.logger.warning(
                f"User locked out due to failed attempts",
                extra={
                    "user_id": user_id,
                    "failed_attempts": attempt_info['count'],
                    "lockout_until": attempt_info['lockout_until'].isoformat()
                }
            )


# Global authentication service
auth_service = AuthenticationService()

# Security bearer for FastAPI
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> SecurityContext:
    """Get current authenticated user with full security context"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Authenticate user
    auth_result = await auth_service.authenticate_user(credentials.credentials, request)
    
    if not auth_result.success:
        if auth_result.error_code == "TOKEN_EXPIRED":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        elif auth_result.error_code == "MFA_REQUIRED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Multi-factor authentication required",
            )
        elif auth_result.error_code == "USER_LOCKED_OUT":
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked until {auth_result.lockout_until}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result.error_message or "Authentication failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    return auth_result.security_context


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[SecurityContext]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


def require_permissions(*required_permissions: str):
    """Decorator to require specific permissions"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract security context from kwargs or args
            security_context = None
            for arg in args:
                if isinstance(arg, SecurityContext):
                    security_context = arg
                    break
            
            if not security_context:
                for value in kwargs.values():
                    if isinstance(value, SecurityContext):
                        security_context = value
                        break
            
            if not security_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check permissions
            missing_permissions = set(required_permissions) - security_context.permissions
            if missing_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(missing_permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_roles(*required_roles: UserRole):
    """Decorator to require specific roles"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract security context
            security_context = None
            for arg in args:
                if isinstance(arg, SecurityContext):
                    security_context = arg
                    break
            
            if not security_context:
                for value in kwargs.values():
                    if isinstance(value, SecurityContext):
                        security_context = value
                        break
            
            if not security_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check roles
            user_roles = set(security_context.roles)
            required_roles_set = set(required_roles)
            
            if not user_roles.intersection(required_roles_set):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required roles: {', '.join([r.value for r in required_roles])}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Convenience dependency functions
async def require_authenticated_user(
    current_user: SecurityContext = Depends(get_current_user)
) -> SecurityContext:
    """Dependency that requires authentication"""
    return current_user


async def require_admin_user(
    current_user: SecurityContext = Depends(get_current_user)
) -> SecurityContext:
    """Dependency that requires admin role"""
    admin_roles = {UserRole.SYSTEM_ADMIN, UserRole.SUPER_ADMIN}
    user_roles = set(current_user.roles)
    
    if not user_roles.intersection(admin_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    
    return current_user


async def require_project_access(
    project_id: str,
    current_user: SecurityContext = Depends(get_current_user)
) -> SecurityContext:
    """Dependency that requires project access"""
    # In production, check project permissions in database
    # For now, basic role check
    if UserRole.SUPER_ADMIN not in current_user.roles:
        # Check project-specific permissions
        project_permission = f"project:{project_id}:access"
        if project_permission not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project access denied"
            )
    
    return current_user


# Rate limiting dependencies
class RateLimiter:
    """Advanced rate limiting with different tiers"""
    
    def __init__(self):
        self.limits = {
            UserRole.VIEWER: {"requests_per_hour": 100, "burst": 10},
            UserRole.DEVELOPER: {"requests_per_hour": 500, "burst": 20},
            UserRole.PROJECT_MANAGER: {"requests_per_hour": 1000, "burst": 30},
            UserRole.SYSTEM_ADMIN: {"requests_per_hour": 2000, "burst": 50},
            UserRole.SUPER_ADMIN: {"requests_per_hour": 5000, "burst": 100}
        }
    
    async def check_rate_limit(self, user: SecurityContext, endpoint: str = "general") -> bool:
        """Check if user has exceeded rate limits"""
        try:
            cache_manager = await dependency_manager.get_dependency('cache_manager')
            
            # Determine user's highest role for rate limiting
            highest_role = self._get_highest_role(user.roles)
            limits = self.limits.get(highest_role, self.limits[UserRole.VIEWER])
            
            # Check hourly limit
            hourly_key = f"rate_limit:user:{user.user_id}:hour:{datetime.utcnow().strftime('%Y%m%d%H')}"
            hourly_count = await cache_manager.get(hourly_key) or 0
            
            if int(hourly_count) >= limits["requests_per_hour"]:
                return False
            
            # Check burst limit
            burst_key = f"rate_limit:user:{user.user_id}:burst"
            burst_count = await cache_manager.get(burst_key) or 0
            
            if int(burst_count) >= limits["burst"]:
                return False
            
            # Increment counters
            await cache_manager.incr(hourly_key, ttl=3600)  # 1 hour TTL
            await cache_manager.incr(burst_key, ttl=60)     # 1 minute TTL for burst
            
            return True
            
        except Exception as e:
            logging.getLogger("ymera.ratelimit").error(f"Rate limit check failed: {e}")
            return True  # Allow on error
    
    def _get_highest_role(self, roles: List[UserRole]) -> UserRole:
        """Get the highest privilege role from user's roles"""
        role_hierarchy = {
            UserRole.VIEWER: 1,
            UserRole.DEVELOPER: 2,
            UserRole.PROJECT_MANAGER: 3,
            UserRole.SECURITY_ANALYST: 4,
            UserRole.SYSTEM_ADMIN: 5,
            UserRole.SUPER_ADMIN: 6
        }
        
        if not roles:
            return UserRole.VIEWER
        
        return max(roles, key=lambda role: role_hierarchy.get(role, 0))


rate_limiter = RateLimiter()


async def check_rate_limit(
    request: Request,
    current_user: SecurityContext = Depends(get_current_user)
) -> SecurityContext:
    """Dependency that enforces rate limiting"""
    endpoint = str(request.url.path)
    
    if not await rate_limiter.check_rate_limit(current_user, endpoint):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": "60"}
        )
    
    return current_user