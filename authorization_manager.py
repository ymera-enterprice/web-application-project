"""
YMERA Enterprise Authentication & Authorization Manager
Production-Ready Security Layer with Advanced Features
"""

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, asdict
import uuid
import re

import bcrypt
import jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt as passlib_bcrypt
import redis.asyncio as redis
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
import base64
import logging
from contextlib import asynccontextmanager

# YMERA Core imports
from ..exceptions import (
    YMERAException, AuthenticationException, AuthorizationException,
    TokenException, SecurityException
)
from ..logging.structured_logger import StructuredLogger
from ..database.manager import DatabaseManager
from ..cache.redis_cache import RedisCacheManager


class UserRole(str, Enum):
    """User roles with hierarchical permissions"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    AGENT = "agent"  # For AI agents
    SERVICE = "service"  # For service-to-service communication
    API_CLIENT = "api_client"  # For external API clients


class Permission(str, Enum):
    """Granular permission system"""
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"
    
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_ADMIN = "project:admin"
    
    # Agent permissions
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_ORCHESTRATE = "agent:orchestrate"
    AGENT_LEARN = "agent:learn"
    
    # Analysis permissions
    ANALYSIS_READ = "analysis:read"
    ANALYSIS_CREATE = "analysis:create"
    ANALYSIS_ADMIN = "analysis:admin"
    
    # Security permissions
    SECURITY_READ = "security:read"
    SECURITY_SCAN = "security:scan"
    SECURITY_ADMIN = "security:admin"
    
    # Deployment permissions
    DEPLOYMENT_READ = "deployment:read"
    DEPLOYMENT_CREATE = "deployment:create"
    DEPLOYMENT_EXECUTE = "deployment:execute"
    DEPLOYMENT_ADMIN = "deployment:admin"
    
    # Learning permissions
    LEARNING_READ = "learning:read"
    LEARNING_WRITE = "learning:write"
    LEARNING_ADMIN = "learning:admin"


class TokenType(str, Enum):
    """Token types for different use cases"""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    AGENT = "agent"
    SERVICE = "service"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"
    MFA = "mfa"


class AuthMethod(str, Enum):
    """Authentication methods"""
    PASSWORD = "password"
    API_KEY = "api_key"
    JWT = "jwt"
    MFA_TOTP = "mfa_totp"
    OAUTH = "oauth"
    CERTIFICATE = "certificate"


@dataclass
class User:
    """User entity with comprehensive metadata"""
    id: str
    username: str
    email: str
    role: UserRole
    permissions: Set[Permission]
    is_active: bool = True
    is_verified: bool = False
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    password_hash: Optional[str] = None
    api_keys: List[str] = None
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.api_keys is None:
            self.api_keys = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Session:
    """User session with security tracking"""
    id: str
    user_id: str
    token: str
    token_type: TokenType
    expires_at: datetime
    created_at: datetime
    last_accessed: datetime
    ip_address: str
    user_agent: str
    is_active: bool = True
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SecurityEvent:
    """Security event for audit logging"""
    id: str
    user_id: Optional[str]
    event_type: str
    description: str
    ip_address: str
    user_agent: str
    success: bool
    risk_score: int  # 0-100
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AuthManager:
    """
    Enterprise-grade Authentication & Authorization Manager
    
    Features:
    - JWT-based authentication with refresh tokens
    - Role-based access control (RBAC) with granular permissions
    - Multi-factor authentication (MFA) support
    - API key management
    - Session management with Redis
    - Security event logging and monitoring
    - Rate limiting and brute force protection
    - Password policy enforcement
    - Token rotation and revocation
    - Agent-specific authentication for AI agents
    """
    
    # Role-Permission mapping
    ROLE_PERMISSIONS = {
        UserRole.SUPER_ADMIN: set(Permission),  # All permissions
        UserRole.ADMIN: {
            Permission.SYSTEM_MONITOR, Permission.SYSTEM_CONFIG,
            Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
            Permission.PROJECT_DELETE, Permission.PROJECT_ADMIN,
            Permission.AGENT_CREATE, Permission.AGENT_READ, Permission.AGENT_UPDATE,
            Permission.AGENT_DELETE, Permission.AGENT_ORCHESTRATE, Permission.AGENT_LEARN,
            Permission.ANALYSIS_READ, Permission.ANALYSIS_CREATE, Permission.ANALYSIS_ADMIN,
            Permission.SECURITY_READ, Permission.SECURITY_SCAN, Permission.SECURITY_ADMIN,
            Permission.DEPLOYMENT_READ, Permission.DEPLOYMENT_CREATE, Permission.DEPLOYMENT_EXECUTE,
            Permission.DEPLOYMENT_ADMIN, Permission.LEARNING_READ, Permission.LEARNING_WRITE,
            Permission.LEARNING_ADMIN
        },
        UserRole.PROJECT_MANAGER: {
            Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
            Permission.PROJECT_ADMIN, Permission.AGENT_READ, Permission.AGENT_ORCHESTRATE,
            Permission.ANALYSIS_READ, Permission.ANALYSIS_CREATE, Permission.SECURITY_READ,
            Permission.DEPLOYMENT_READ, Permission.DEPLOYMENT_CREATE, Permission.LEARNING_READ
        },
        UserRole.DEVELOPER: {
            Permission.PROJECT_READ, Permission.PROJECT_UPDATE, Permission.AGENT_READ,
            Permission.ANALYSIS_READ, Permission.ANALYSIS_CREATE, Permission.SECURITY_READ,
            Permission.DEPLOYMENT_READ, Permission.LEARNING_READ, Permission.LEARNING_WRITE
        },
        UserRole.ANALYST: {
            Permission.PROJECT_READ, Permission.AGENT_READ, Permission.ANALYSIS_READ,
            Permission.ANALYSIS_CREATE, Permission.SECURITY_READ, Permission.LEARNING_READ
        },
        UserRole.VIEWER: {
            Permission.PROJECT_READ, Permission.AGENT_READ, Permission.ANALYSIS_READ,
            Permission.SECURITY_READ, Permission.DEPLOYMENT_READ, Permission.LEARNING_READ
        },
        UserRole.AGENT: {
            Permission.AGENT_READ, Permission.AGENT_LEARN, Permission.LEARNING_READ,
            Permission.LEARNING_WRITE, Permission.ANALYSIS_READ, Permission.SECURITY_READ
        },
        UserRole.SERVICE: {
            Permission.SYSTEM_MONITOR, Permission.AGENT_READ, Permission.LEARNING_READ
        },
        UserRole.API_CLIENT: {
            Permission.PROJECT_READ, Permission.ANALYSIS_READ, Permission.SECURITY_READ
        }
    }
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
        api_key_expire_days: int = 365,
        max_login_attempts: int = 5,
        lockout_duration_minutes: int = 15,
        password_min_length: int = 8,
        db_manager: Optional[DatabaseManager] = None,
        cache_manager: Optional[RedisCacheManager] = None,
        logger: Optional[StructuredLogger] = None
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.api_key_expire_days = api_key_expire_days
        self.max_login_attempts = max_login_attempts
        self.lockout_duration_minutes = lockout_duration_minutes
        self.password_min_length = password_min_length
        
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize password context
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12
        )
        
        # Initialize encryption
        self._init_encryption()
        
        # Redis key prefixes
        self.KEY_PREFIX = "ymera:auth"
        self.SESSION_PREFIX = f"{self.KEY_PREFIX}:session"
        self.USER_PREFIX = f"{self.KEY_PREFIX}:user"
        self.RATE_LIMIT_PREFIX = f"{self.KEY_PREFIX}:rate_limit"
        self.BLACKLIST_PREFIX = f"{self.KEY_PREFIX}:blacklist"
        
        # Security patterns
        self.password_pattern = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]'
        )
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        
        self._initialized = False
    
    def _init_encryption(self):
        """Initialize encryption for sensitive data"""
        # Derive encryption key from secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.secret_key.encode()[:16],
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
        self.cipher = Fernet(key)
    
    async def initialize(self) -> None:
        """Initialize the authentication manager"""
        try:
            await self._create_database_tables()
            await self._create_default_users()
            self._initialized = True
            self.logger.info("Authentication manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize authentication manager: {str(e)}")
            raise SecurityException(f"Authentication initialization failed: {str(e)}")
    
    async def _create_database_tables(self) -> None:
        """Create necessary database tables"""
        if not self.db_manager:
            return
        
        tables = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                role VARCHAR(50) NOT NULL,
                permissions TEXT,
                password_hash TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                mfa_enabled BOOLEAN DEFAULT FALSE,
                mfa_secret TEXT,
                api_keys TEXT,
                last_login TIMESTAMP,
                login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                token_type VARCHAR(50) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS security_events (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36),
                event_type VARCHAR(100) NOT NULL,
                description TEXT NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                success BOOLEAN NOT NULL,
                risk_score INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON security_events(user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp);
            """
        ]
        
        for table_sql in tables:
            await self.db_manager.execute(table_sql)
    
    async def _create_default_users(self) -> None:
        """Create default system users"""
        if not self.db_manager:
            return
        
        # Check if admin user exists
        result = await self.db_manager.fetch_one(
            "SELECT id FROM users WHERE username = ?", ("admin",)
        )
        
        if not result:
            # Create default admin user
            admin_user = User(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@ymera.system",
                role=UserRole.SUPER_ADMIN,
                permissions=self.ROLE_PERMISSIONS[UserRole.SUPER_ADMIN],
                is_active=True,
                is_verified=True
            )
            
            # Generate secure default password
            default_password = secrets.token_urlsafe(16)
            admin_user.password_hash = self.hash_password(default_password)
            
            await self._save_user(admin_user)
            
            self.logger.info(
                f"Default admin user created with password: {default_password}",
                extra={"user_id": admin_user.id}
            )
    
    # Password Management
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password strength"""
        issues = []
        
        if len(password) < self.password_min_length:
            issues.append(f"Password must be at least {self.password_min_length} characters")
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one digit")
        
        if not re.search(r'[@$!%*?&]', password):
            issues.append("Password must contain at least one special character")
        
        if password.lower() in ['password', '123456', 'admin', 'user']:
            issues.append("Password is too common")
        
        return len(issues) == 0, issues
    
    # User Management
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole,
        permissions: Optional[Set[Permission]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> User:
        """Create a new user"""
        try:
            # Validate inputs
            if not self.email_pattern.match(email):
                raise AuthenticationException("Invalid email format")
            
            is_strong, issues = self.validate_password_strength(password)
            if not is_strong:
                raise AuthenticationException(f"Weak password: {', '.join(issues)}")
            
            # Check for existing user
            existing = await self.get_user_by_username(username)
            if existing:
                raise AuthenticationException("Username already exists")
            
            existing = await self.get_user_by_email(email)
            if existing:
                raise AuthenticationException("Email already exists")
            
            # Create user
            user = User(
                id=str(uuid.uuid4()),
                username=username,
                email=email,
                role=role,
                permissions=permissions or self.ROLE_PERMISSIONS.get(role, set()),
                password_hash=self.hash_password(password),
                metadata=metadata or {}
            )
            
            await self._save_user(user)
            
            # Log security event
            await self._log_security_event(
                user_id=user.id,
                event_type="USER_CREATED",
                description=f"User {username} created with role {role}",
                success=True,
                risk_score=10
            )
            
            self.logger.info(f"User created successfully: {username}", extra={"user_id": user.id})
            return user
            
        except Exception as e:
            await self._log_security_event(
                event_type="USER_CREATE_FAILED",
                description=f"Failed to create user {username}: {str(e)}",
                success=False,
                risk_score=30
            )
            raise
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        if not self.db_manager:
            return None
        
        # Try cache first
        if self.cache_manager:
            cached = await self.cache_manager.get(f"{self.USER_PREFIX}:{user_id}")
            if cached:
                return User(**json.loads(cached))
        
        # Query database
        result = await self.db_manager.fetch_one(
            "SELECT * FROM users WHERE id = ? AND is_active = TRUE", (user_id,)
        )
        
        if result:
            user = self._row_to_user(result)
            
            # Cache user
            if self.cache_manager:
                await self.cache_manager.set(
                    f"{self.USER_PREFIX}:{user_id}",
                    json.dumps(asdict(user), default=str),
                    ttl=300  # 5 minutes
                )
            
            return user
        
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        if not self.db_manager:
            return None
        
        result = await self.db_manager.fetch_one(
            "SELECT * FROM users WHERE username = ? AND is_active = TRUE", (username,)
        )
        
        return self._row_to_user(result) if result else None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        if not self.db_manager:
            return None
        
        result = await self.db_manager.fetch_one(
            "SELECT * FROM users WHERE email = ? AND is_active = TRUE", (email,)
        )
        
        return self._row_to_user(result) if result else None
    
    async def update_user(self, user: User) -> User:
        """Update user information"""
        user.updated_at = datetime.now(timezone.utc)
        await self._save_user(user)
        
        # Invalidate cache
        if self.cache_manager:
            await self.cache_manager.delete(f"{self.USER_PREFIX}:{user.id}")
        
        await self._log_security_event(
            user_id=user.id,
            event_type="USER_UPDATED",
            description=f"User {user.username} updated",
            success=True,
            risk_score=5
        )
        
        return user
    
    async def delete_user(self, user_id: str) -> bool:
        """Soft delete user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)
        await self._save_user(user)
        
        # Revoke all sessions
        await self.revoke_all_user_sessions(user_id)
        
        # Invalidate cache
        if self.cache_manager:
            await self.cache_manager.delete(f"{self.USER_PREFIX}:{user_id}")
        
        await self._log_security_event(
            user_id=user_id,
            event_type="USER_DELETED",
            description=f"User {user.username} deleted",
            success=True,
            risk_score=20
        )
        
        return True
    
    # Authentication
    async def authenticate(
        self,
        identifier: str,  # username, email, or API key
        password: str,
        auth_method: AuthMethod = AuthMethod.PASSWORD,
        ip_address: str = "unknown",
        user_agent: str = "unknown"
    ) -> Tuple[Optional[User], Optional[str]]:
        """Authenticate user and return user object and access token"""
        try:
            # Rate limiting check
            await self._check_rate_limit(identifier, ip_address)
            
            user = None
            
            # Determine authentication method
            if auth_method == AuthMethod.PASSWORD:
                # Try username first, then email
                user = await self.get_user_by_username(identifier)
                if not user:
                    user = await self.get_user_by_email(identifier)
                
                if not user or not user.password_hash:
                    await self._increment_rate_limit(identifier, ip_address)
                    raise AuthenticationException("Invalid credentials")
                
                # Check account lock
                if user.locked_until and user.locked_until > datetime.now(timezone.utc):
                    raise AuthenticationException("Account is temporarily locked")
                
                # Verify password
                if not self.verify_password(password, user.password_hash):
                    await self._handle_failed_login(user, ip_address, user_agent)
                    raise AuthenticationException("Invalid credentials")
            
            elif auth_method == AuthMethod.API_KEY:
                # API key authentication
                user = await self._authenticate_api_key(identifier)
                if not user:
                    await self._increment_rate_limit(identifier, ip_address)
                    raise AuthenticationException("Invalid API key")
            
            else:
                raise AuthenticationException(f"Unsupported authentication method: {auth_method}")
            
            # Check if user is active
            if not user.is_active:
                raise AuthenticationException("Account is deactivated")
            
            # Update last login and reset login attempts
            user.last_login = datetime.now(timezone.utc)
            user.login_attempts = 0
            user.locked_until = None
            await self.update_user(user)
            
            # Generate access token
            access_token = await self.create_access_token(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            await self._log_security_event(
                user_id=user.id,
                event_type="LOGIN_SUCCESS",
                description=f"User {user.username} logged in via {auth_method}",
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
                risk_score=0
            )
            
            return user, access_token
            
        except AuthenticationException:
            await self._log_security_event(
                event_type="LOGIN_FAILED",
                description=f"Failed login attempt for {identifier}",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                risk_score=50
            )
            raise
    
    async def _authenticate_api_key(self, api_key: str) -> Optional[User]:
        """Authenticate using API key"""
        # Hash the API key for database lookup
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        if not self.db_manager:
            return None
        
        result = await self.db_manager.fetch_one(
            """
            SELECT u.* FROM users u 
            WHERE u.api_keys LIKE ? AND u.is_active = TRUE
            """,
            (f"%{key_hash}%",)
        )
        
        if result:
            user = self._row_to_user(result)
            # Verify the API key is in the user's API keys list
            if key_hash in user.api_keys:
                return user
        
        return None
    
    # Token Management
    async def create_access_token(
        self,
        user_id: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        
        # Create session
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token="",  # Will be set after token creation
            token_type=TokenType.ACCESS,
            expires_at=expire,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Create JWT payload
        payload = {
            "user_id": user_id,
            "session_id": session.id,
            "token_type": TokenType.ACCESS.value,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4())  # JWT ID for revocation
        }
        
        # Generate token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        session.token = self._hash_token(token)
        
        # Save session
        await self._save_session(session)
        
        return token
    
    async def create_refresh_token(self, user_id: str) -> str:
        """Create refresh token"""
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
        
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token="",
            token_type=TokenType.REFRESH,
            expires_at=expire,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            ip_address="unknown",
            user_agent="unknown"
        )
        
        payload = {
            "user_id": user_id,
            "session_id": session.id,
            "token_type": TokenType.REFRESH.value,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4())
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        session.token = self._hash_token(token)
        
        await self._save_session(session)
        return token
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload"""
        try:
            # Check if token is blacklisted
            if await self._is_token_blacklisted(token):
                raise TokenException("Token has been revoked")
            
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify session exists and is active
            session_id = payload.get("session_id")
            if session_id:
                session = await self.get_session(session_id)
                if not session or not session.is_active:
                    raise TokenException("Session not found or inactive")
                
                # Check if session has expired
                if session.expires_at < datetime.now(timezone.utc):
                    await self.revoke_session(session_id)
                    raise TokenException("Session has expired")
                
                # Update last accessed
                session.last_accessed = datetime.now(timezone.utc)
                await self._save_session(session)
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise TokenException("Token has expired")
        except jwt.InvalidTokenError as e:
            raise TokenException(f"Invalid token: {str(e)}")
    
    async def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token using refresh token"""
        try:
            payload = await self.verify_token(refresh_token)
            
            if payload.get("token_type") != TokenType.REFRESH.value:
                raise TokenException("Invalid token type for refresh")
            
            user_id = payload.get("user_id")
            if not user_id:
                raise TokenException("Invalid token payload")
            
            # Verify user still exists and is active
            user = await self.get_user_by_id(user_id)
            if not user or not user.is_active:
                raise TokenException("User not found or inactive")
            
            # Create new access token
            return await self.create_access_token(user_id)
            
        except Exception as e:
            await self._log_security_event(
                event_type="TOKEN_REFRESH_FAILED",
                description=f"Failed to refresh token: {str(e)}",
                success=False,
                risk_score=40
            )
            raise
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a specific token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            session_id = payload.get("session_id")
            
            if session_id:
                await self.revoke_session(session_id)
            
            # Add to blacklist
            await self._blacklist_token(token, payload.get("exp"))
            
            await self._log_security_event(
                user_id=payload.get("user_id"),
                event_type="TOKEN_REVOKED",
                description="Token revoked",
                success=True,
                risk_score=5
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to revoke token: {str(e)}")
            return False
    
    # API Key Management
    async def create_api_key(
        self,
        user_id: str,
        name: str,
        expires_days: Optional[int] = None
    ) -> str:
        """Create API key for user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationException("User not found")
        
        # Generate API key
        api_key = f"ymera_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Add to user's API keys
        user.api_keys.append(key_hash)
        await self.update_user(user)
        
        # Log security event
        await self._log_security_event(
            user_id=user_id,
            event_type="API_KEY_CREATED",
            description=f"API key '{name}' created",
            success=True,
            risk_score=10
        )
        
        return api_key
    
    async def revoke_api_key(self, user_id: str, api_key: str) -> bool:
        """Revoke API key"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        if key_hash in user.api_keys:
            user.api_keys.remove(key_hash)
            await self.update_user(user)
            
            await self._log_security_event(
                user_id=user_id,
                event_type="API_KEY_REVOKED",
                description="API key revoked",
                success=True,
                risk_score=10
            )
            
            return True
        
        return False
    
    # Session Management
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        if not self.db_manager:
            return None
        
        # Try cache first
        if self.cache_manager:
            cached = await self.cache_manager.get(f"{self.SESSION_PREFIX}:{session_id}")
            if cached:
                return Session(**json.loads(cached))
        
        result = await self.db_manager.fetch_one(
            "SELECT * FROM sessions WHERE id = ? AND is_active = TRUE",
            (session_id,)
        )
        
        if result:
            session = self._row_to_session(result)
            
            # Cache session
            if self.cache_manager:
                await self.cache_manager.set(
                    f"{self.SESSION_PREFIX}:{session_id}",
                    json.dumps(asdict(session), default=str),
                    ttl=300
                )
            
            return session
        
        return None
    
    async def get_user_sessions(self, user_id: str, active_only: bool = True) -> List[Session]:
        """Get all sessions for a user"""
        if not self.db_manager:
            return []
        
        query = "SELECT * FROM sessions WHERE user_id = ?"
        params = [user_id]
        
        if active_only:
            query += " AND is_active = TRUE AND expires_at > ?"
            params.append(datetime.now(timezone.utc))
        
        query += " ORDER BY created_at DESC"
        
        results = await self.db_manager.fetch_all(query, params)
        return [self._row_to_session(row) for row in results]
    
    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.is_active = False
        await self._save_session(session)
        
        # Remove from cache
        if self.cache_manager:
            await self.cache_manager.delete(f"{self.SESSION_PREFIX}:{session_id}")
        
        await self._log_security_event(
            user_id=session.user_id,
            event_type="SESSION_REVOKED",
            description=f"Session {session_id} revoked",
            success=True,
            risk_score=5
        )
        
        return True
    
    async def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user"""
        if not self.db_manager:
            return 0
        
        # Update database
        result = await self.db_manager.execute(
            "UPDATE sessions SET is_active = FALSE WHERE user_id = ? AND is_active = TRUE",
            (user_id,)
        )
        
        # Clear cache entries
        if self.cache_manager:
            sessions = await self.get_user_sessions(user_id, active_only=False)
            for session in sessions:
                await self.cache_manager.delete(f"{self.SESSION_PREFIX}:{session.id}")
        
        await self._log_security_event(
            user_id=user_id,
            event_type="ALL_SESSIONS_REVOKED",
            description="All user sessions revoked",
            success=True,
            risk_score=15
        )
        
        return result.rowcount if hasattr(result, 'rowcount') else 0
    
    # Authorization
    async def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has specific permission"""
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return False
        
        return permission in user.permissions
    
    async def check_permissions(self, user_id: str, permissions: List[Permission]) -> bool:
        """Check if user has all specified permissions"""
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return False
        
        return all(perm in user.permissions for perm in permissions)
    
    async def check_any_permission(self, user_id: str, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return False
        
        return any(perm in user.permissions for perm in permissions)
    
    async def add_permission(self, user_id: str, permission: Permission) -> bool:
        """Add permission to user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.permissions.add(permission)
        await self.update_user(user)
        
        await self._log_security_event(
            user_id=user_id,
            event_type="PERMISSION_ADDED",
            description=f"Permission {permission} added",
            success=True,
            risk_score=5
        )
        
        return True
    
    async def remove_permission(self, user_id: str, permission: Permission) -> bool:
        """Remove permission from user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.permissions.discard(permission)
        await self.update_user(user)
        
        await self._log_security_event(
            user_id=user_id,
            event_type="PERMISSION_REMOVED",
            description=f"Permission {permission} removed",
            success=True,
            risk_score=10
        )
        
        return True
    
    async def update_user_role(self, user_id: str, new_role: UserRole) -> bool:
        """Update user role and associated permissions"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        old_role = user.role
        user.role = new_role
        user.permissions = self.ROLE_PERMISSIONS.get(new_role, set())
        await self.update_user(user)
        
        await self._log_security_event(
            user_id=user_id,
            event_type="ROLE_CHANGED",
            description=f"Role changed from {old_role} to {new_role}",
            success=True,
            risk_score=20
        )
        
        return True
    
    # Multi-Factor Authentication
    async def enable_mfa(self, user_id: str) -> str:
        """Enable MFA and return secret"""
        import pyotp
        
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationException("User not found")
        
        # Generate MFA secret
        secret = pyotp.random_base32()
        encrypted_secret = self.cipher.encrypt(secret.encode()).decode()
        
        user.mfa_secret = encrypted_secret
        user.mfa_enabled = True
        await self.update_user(user)
        
        await self._log_security_event(
            user_id=user_id,
            event_type="MFA_ENABLED",
            description="Multi-factor authentication enabled",
            success=True,
            risk_score=0  # Positive security action
        )
        
        return secret
    
    async def disable_mfa(self, user_id: str) -> bool:
        """Disable MFA for user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.mfa_enabled = False
        user.mfa_secret = None
        await self.update_user(user)
        
        await self._log_security_event(
            user_id=user_id,
            event_type="MFA_DISABLED",
            description="Multi-factor authentication disabled",
            success=True,
            risk_score=25  # Security reduction
        )
        
        return True
    
    async def verify_mfa_token(self, user_id: str, token: str) -> bool:
        """Verify MFA token"""
        import pyotp
        
        user = await self.get_user_by_id(user_id)
        if not user or not user.mfa_enabled or not user.mfa_secret:
            return False
        
        try:
            # Decrypt secret
            secret = self.cipher.decrypt(user.mfa_secret.encode()).decode()
            totp = pyotp.TOTP(secret)
            
            # Verify token with window for clock skew
            is_valid = totp.verify(token, valid_window=1)
            
            await self._log_security_event(
                user_id=user_id,
                event_type="MFA_VERIFICATION",
                description=f"MFA verification {'successful' if is_valid else 'failed'}",
                success=is_valid,
                risk_score=0 if is_valid else 30
            )
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"MFA verification error: {str(e)}")
            return False
    
    # Security Event Logging
    async def _log_security_event(
        self,
        event_type: str,
        description: str,
        success: bool,
        risk_score: int = 0,
        user_id: Optional[str] = None,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log security event"""
        event = SecurityEvent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            risk_score=risk_score,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        # Log to database
        if self.db_manager:
            await self.db_manager.execute(
                """
                INSERT INTO security_events 
                (id, user_id, event_type, description, ip_address, user_agent, 
                 success, risk_score, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id, event.user_id, event.event_type, event.description,
                    event.ip_address, event.user_agent, event.success,
                    event.risk_score, event.timestamp, json.dumps(event.metadata)
                )
            )
        
        # Log to structured logger
        self.logger.info(
            f"Security Event: {event_type}",
            extra={
                "event_id": event.id,
                "event_type": event_type,
                "user_id": user_id,
                "description": description,
                "success": success,
                "risk_score": risk_score,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "metadata": metadata
            }
        )
        
        # High-risk events trigger immediate alerts
        if risk_score >= 70:
            self.logger.warning(
                f"HIGH RISK SECURITY EVENT: {event_type}",
                extra=asdict(event)
            )
    
    async def get_security_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """Get security events with filtering"""
        if not self.db_manager:
            return []
        
        query = "SELECT * FROM security_events WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        results = await self.db_manager.fetch_all(query, params)
        return [self._row_to_security_event(row) for row in results]
    
    # Rate Limiting
    async def _check_rate_limit(self, identifier: str, ip_address: str) -> None:
        """Check rate limiting for login attempts"""
        if not self.cache_manager:
            return
        
        # Check identifier-based rate limiting
        key = f"{self.RATE_LIMIT_PREFIX}:login:{identifier}"
        attempts = await self.cache_manager.get(key)
        
        if attempts and int(attempts) >= self.max_login_attempts:
            raise AuthenticationException("Too many login attempts. Please try again later.")
        
        # Check IP-based rate limiting
        ip_key = f"{self.RATE_LIMIT_PREFIX}:ip:{ip_address}"
        ip_attempts = await self.cache_manager.get(ip_key)
        
        if ip_attempts and int(ip_attempts) >= (self.max_login_attempts * 2):
            raise AuthenticationException("Too many login attempts from this IP. Please try again later.")
    
    async def _increment_rate_limit(self, identifier: str, ip_address: str) -> None:
        """Increment rate limit counters"""
        if not self.cache_manager:
            return
        
        # Increment identifier counter
        key = f"{self.RATE_LIMIT_PREFIX}:login:{identifier}"
        await self.cache_manager.increment(key, ttl=900)  # 15 minutes
        
        # Increment IP counter
        ip_key = f"{self.RATE_LIMIT_PREFIX}:ip:{ip_address}"
        await self.cache_manager.increment(ip_key, ttl=900)
    
    async def _handle_failed_login(
        self,
        user: User,
        ip_address: str,
        user_agent: str
    ) -> None:
        """Handle failed login attempt"""
        user.login_attempts += 1
        
        # Lock account after max attempts
        if user.login_attempts >= self.max_login_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=self.lockout_duration_minutes
            )
            
            await self._log_security_event(
                user_id=user.id,
                event_type="ACCOUNT_LOCKED",
                description=f"Account locked after {self.max_login_attempts} failed attempts",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                risk_score=60
            )
        
        await self.update_user(user)
        await self._increment_rate_limit(user.username, ip_address)
    
    # Token Blacklisting
    async def _blacklist_token(self, token: str, exp: Optional[datetime] = None) -> None:
        """Add token to blacklist"""
        if not self.cache_manager:
            return
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        key = f"{self.BLACKLIST_PREFIX}:{token_hash}"
        
        # Set expiration based on token expiration or default
        if exp:
            if isinstance(exp, (int, float)):
                exp_time = datetime.fromtimestamp(exp, timezone.utc)
            else:
                exp_time = exp
            ttl = max(0, int((exp_time - datetime.now(timezone.utc)).total_seconds()))
        else:
            ttl = self.access_token_expire_minutes * 60
        
        await self.cache_manager.set(key, "1", ttl=ttl)
    
    async def _is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        if not self.cache_manager:
            return False
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        key = f"{self.BLACKLIST_PREFIX}:{token_hash}"
        
        return await self.cache_manager.exists(key)
    
    # Agent Authentication
    async def create_agent_token(
        self,
        agent_id: str,
        agent_name: str,
        permissions: Set[Permission],
        expires_hours: int = 24
    ) -> str:
        """Create authentication token for AI agent"""
        expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        
        payload = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "token_type": TokenType.AGENT.value,
            "permissions": list(permissions),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4())
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Cache agent token info
        if self.cache_manager:
            await self.cache_manager.set(
                f"{self.KEY_PREFIX}:agent:{agent_id}",
                json.dumps(payload, default=str),
                ttl=expires_hours * 3600
            )
        
        await self._log_security_event(
            event_type="AGENT_TOKEN_CREATED",
            description=f"Agent token created for {agent_name}",
            success=True,
            risk_score=5,
            metadata={"agent_id": agent_id, "agent_name": agent_name}
        )
        
        return token
    
    async def verify_agent_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify agent token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("token_type") != TokenType.AGENT.value:
                raise TokenException("Invalid token type for agent")
            
            # Verify agent token is still cached (not revoked)
            agent_id = payload.get("agent_id")
            if self.cache_manager and agent_id:
                cached = await self.cache_manager.get(f"{self.KEY_PREFIX}:agent:{agent_id}")
                if not cached:
                    raise TokenException("Agent token has been revoked")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise TokenException("Agent token has expired")
        except jwt.InvalidTokenError as e:
            raise TokenException(f"Invalid agent token: {str(e)}")
    
    async def revoke_agent_token(self, agent_id: str) -> bool:
        """Revoke agent token"""
        if not self.cache_manager:
            return False
        
        key = f"{self.KEY_PREFIX}:agent:{agent_id}"
        deleted = await self.cache_manager.delete(key)
        
        if deleted:
            await self._log_security_event(
                event_type="AGENT_TOKEN_REVOKED",
                description=f"Agent token revoked for {agent_id}",
                success=True,
                risk_score=5,
                metadata={"agent_id": agent_id}
            )
        
        return deleted > 0
    
    # Utility Methods
    def _hash_token(self, token: str) -> str:
        """Hash token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _row_to_user(self, row) -> User:
        """Convert database row to User object"""
        return User(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            role=UserRole(row['role']),
            permissions=set(json.loads(row['permissions'])) if row['permissions'] else set(),
            is_active=row['is_active'],
            is_verified=row['is_verified'],
            mfa_enabled=row['mfa_enabled'],
            mfa_secret=row['mfa_secret'],
            password_hash=row['password_hash'],
            api_keys=json.loads(row['api_keys']) if row['api_keys'] else [],
            last_login=row['last_login'],
            login_attempts=row['login_attempts'],
            locked_until=row['locked_until'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    def _row_to_session(self, row) -> Session:
        """Convert database row to Session object"""
        return Session(
            id=row['id'],
            user_id=row['user_id'],
            token=row['token_hash'],
            token_type=TokenType(row['token_type']),
            expires_at=row['expires_at'],
            created_at=row['created_at'],
            last_accessed=row['last_accessed'],
            ip_address=row['ip_address'],
            user_agent=row['user_agent'],
            is_active=row['is_active'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    def _row_to_security_event(self, row) -> SecurityEvent:
        """Convert database row to SecurityEvent object"""
        return SecurityEvent(
            id=row['id'],
            user_id=row['user_id'],
            event_type=row['event_type'],
            description=row['description'],
            ip_address=row['ip_address'],
            user_agent=row['user_agent'],
            success=row['success'],
            risk_score=row['risk_score'],
            timestamp=row['timestamp'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    async def _save_user(self, user: User) -> None:
        """Save user to database"""
        if not self.db_manager:
            return
        
        await self.db_manager.execute(
            """
            INSERT OR REPLACE INTO users 
            (id, username, email, role, permissions, password_hash, is_active, 
             is_verified, mfa_enabled, mfa_secret, api_keys, last_login, 
             login_attempts, locked_until, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id, user.username, user.email, user.role.value,
                json.dumps(list(user.permissions)), user.password_hash,
                user.is_active, user.is_verified, user.mfa_enabled,
                user.mfa_secret, json.dumps(user.api_keys), user.last_login,
                user.login_attempts, user.locked_until, user.created_at,
                user.updated_at, json.dumps(user.metadata)
            )
        )
    
    async def _save_session(self, session: Session) -> None:
        """Save session to database"""
        if not self.db_manager:
            return
        
        await self.db_manager.execute(
            """
            INSERT OR REPLACE INTO sessions 
            (id, user_id, token_hash, token_type, expires_at, created_at, 
             last_accessed, ip_address, user_agent, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id, session.user_id, session.token, session.token_type.value,
                session.expires_at, session.created_at, session.last_accessed,
                session.ip_address, session.user_agent, session.is_active,
                json.dumps(session.metadata)
            )
        )
    
    # Health and Monitoring
    async def get_auth_health(self) -> Dict[str, Any]:
        """Get authentication system health"""
        health = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "database": False,
                "cache": False,
                "encryption": True
            },
            "metrics": {
                "active_sessions": 0,
                "total_users": 0,
                "security_events_24h": 0
            }
        }
        
        try:
            # Check database
            if self.db_manager:
                await self.db_manager.fetch_one("SELECT 1")
                health["components"]["database"] = True
                
                # Get user count
                result = await self.db_manager.fetch_one(
                    "SELECT COUNT(*) as count FROM users WHERE is_active = TRUE"
                )
                health["metrics"]["total_users"] = result['count'] if result else 0
                
                # Get active sessions count
                result = await self.db_manager.fetch_one(
                    """
                    SELECT COUNT(*) as count FROM sessions 
                    WHERE is_active = TRUE AND expires_at > ?
                    """,
                    (datetime.now(timezone.utc),)
                )
                health["metrics"]["active_sessions"] = result['count'] if result else 0
                
                # Get recent security events
                result = await self.db_manager.fetch_one(
                    """
                    SELECT COUNT(*) as count FROM security_events 
                    WHERE timestamp > ?
                    """,
                    (datetime.now(timezone.utc) - timedelta(hours=24),)
                )
                health["metrics"]["security_events_24h"] = result['count'] if result else 0
            
            # Check cache
            if self.cache_manager:
                await self.cache_manager.ping()
                health["components"]["cache"] = True
            
            # Overall health
            unhealthy_components = [
                k for k, v in health["components"].items() if not v
            ]
            
            if unhealthy_components:
                health["status"] = "degraded"
                health["issues"] = unhealthy_components
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    # Context Managers
    @asynccontextmanager
    async def temporary_permissions(
        self,
        user_id: str,
        permissions: Set[Permission]
    ):
        """Temporarily grant permissions to user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            yield None
            return
        
        original_permissions = user.permissions.copy()
        
        try:
            # Add temporary permissions
            user.permissions.update(permissions)
            await self.update_user(user)
            
            yield user
            
        finally:
            # Restore original permissions
            user.permissions = original_permissions
            await self.update_user(user)
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        if not self.db_manager:
            return 0
        
        current_time = datetime.now(timezone.utc)
        
        # Get expired sessions for logging
        expired_sessions = await self.db_manager.fetch_all(
            """
            SELECT * FROM sessions 
            WHERE expires_at < ? AND is_active = TRUE
            """,
            (current_time,)
        )
        
        if expired_sessions:
            # Log expired sessions
            for session in expired_sessions:
                await self._log_security_event(
                    user_id=session['user_id'],
                    event_type="SESSION_EXPIRED",
                    description=f"Session {session['id']} expired and cleaned up",
                    success=True,
                    risk_score=0
                )
        
        # Delete expired sessions
        result = await self.db_manager.execute(
            "DELETE FROM sessions WHERE expires_at < ?",
            (current_time,)
        )
        
        # Clear from cache
        if self.cache_manager:
            for session in expired_sessions:
                await self.cache_manager.delete(f"{self.SESSION_PREFIX}:{session['id']}")
        
        return result.rowcount if hasattr(result, 'rowcount') else len(expired_sessions)
    
    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired refresh tokens and security events"""
        if not self.db_manager:
            return 0
        
        current_time = datetime.now(timezone.utc)
        
        # Clean up old security events (keep 90 days)
        old_threshold = current_time - timedelta(days=90)
        result = await self.db_manager.execute(
            "DELETE FROM security_events WHERE timestamp < ?",
            (old_threshold,)
        )
        
        events_cleaned = result.rowcount if hasattr(result, 'rowcount') else 0
        
        # Clean up blacklisted tokens (they expire naturally in cache)
        # This is handled by cache TTL
        
        return events_cleaned
    
    async def get_user_activity_summary(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user activity summary"""
        if not self.db_manager:
            return {}
        
        start_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get login events
        login_events = await self.db_manager.fetch_all(
            """
            SELECT COUNT(*) as count, success 
            FROM security_events 
            WHERE user_id = ? AND event_type = 'LOGIN' AND timestamp > ?
            GROUP BY success
            """,
            (user_id, start_time)
        )
        
        # Get session count
        session_result = await self.db_manager.fetch_one(
            """
            SELECT COUNT(*) as count 
            FROM sessions 
            WHERE user_id = ? AND created_at > ?
            """,
            (user_id, start_time)
        )
        
        # Get permission changes
        permission_events = await self.db_manager.fetch_all(
            """
            SELECT event_type, COUNT(*) as count 
            FROM security_events 
            WHERE user_id = ? AND event_type IN ('PERMISSION_ADDED', 'PERMISSION_REMOVED', 'ROLE_CHANGED') 
            AND timestamp > ?
            GROUP BY event_type
            """,
            (user_id, start_time)
        )
        
        # Calculate success rate
        successful_logins = 0
        failed_logins = 0
        
        for event in login_events:
            if event['success']:
                successful_logins = event['count']
            else:
                failed_logins = event['count']
        
        total_logins = successful_logins + failed_logins
        success_rate = (successful_logins / total_logins * 100) if total_logins > 0 else 0
        
        return {
            "user_id": user_id,
            "period_days": days,
            "successful_logins": successful_logins,
            "failed_logins": failed_logins,
            "login_success_rate": round(success_rate, 2),
            "total_sessions": session_result['count'] if session_result else 0,
            "permission_changes": {
                event['event_type']: event['count'] 
                for event in permission_events
            },
            "last_activity": await self._get_last_activity(user_id)
        }
    
    async def _get_last_activity(self, user_id: str) -> Optional[datetime]:
        """Get user's last activity timestamp"""
        if not self.db_manager:
            return None
        
        result = await self.db_manager.fetch_one(
            """
            SELECT MAX(last_accessed) as last_activity 
            FROM sessions 
            WHERE user_id = ?
            """,
            (user_id,)
        )
        
        return result['last_activity'] if result and result['last_activity'] else None
    
    async def export_security_audit(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export security audit data"""
        if not self.db_manager:
            return {}
        
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        # Get security events
        events = await self.get_security_events(
            start_time=start_date,
            end_time=end_date,
            limit=10000  # Large limit for audit
        )
        
        # Get user statistics
        user_stats = await self.db_manager.fetch_all(
            """
            SELECT role, COUNT(*) as count, 
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count
            FROM users 
            GROUP BY role
            """
        )
        
        # Get session statistics
        session_stats = await self.db_manager.fetch_one(
            """
            SELECT COUNT(*) as total_sessions,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_sessions,
                   COUNT(DISTINCT user_id) as unique_users
            FROM sessions
            WHERE created_at BETWEEN ? AND ?
            """,
            (start_date, end_date)
        )
        
        # Calculate risk metrics
        high_risk_events = [e for e in events if e.risk_score >= 50]
        failed_events = [e for e in events if not e.success]
        
        audit_data = {
            "audit_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": datetime.now(timezone.utc).isoformat()
            },
            "summary": {
                "total_events": len(events),
                "high_risk_events": len(high_risk_events),
                "failed_events": len(failed_events),
                "success_rate": round((len(events) - len(failed_events)) / len(events) * 100, 2) if events else 100
            },
            "user_statistics": [dict(row) for row in user_stats],
            "session_statistics": dict(session_stats) if session_stats else {},
            "event_breakdown": {},
            "risk_analysis": {
                "high_risk_events": len(high_risk_events),
                "average_risk_score": sum(e.risk_score for e in events) / len(events) if events else 0,
                "max_risk_score": max((e.risk_score for e in events), default=0)
            }
        }
        
        # Event type breakdown
        event_types = {}
        for event in events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        audit_data["event_breakdown"] = event_types
        
        # Include detailed events if requested
        if format == "detailed":
            audit_data["events"] = [asdict(event) for event in events]
        
        return audit_data
    
    # Password Policy Management
    async def validate_password_policy(self, password: str, user: Optional[User] = None) -> List[str]:
        """Validate password against policy"""
        errors = []
        
        # Length check
        if len(password) < self.password_min_length:
            errors.append(f"Password must be at least {self.password_min_length} characters long")
        
        # Complexity checks
        if self.password_require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.password_require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.password_require_digits and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if self.password_require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Common password check
        common_passwords = {
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', 'monkey', 'dragon', 'password1'
        }
        if password.lower() in common_passwords:
            errors.append("Password is too common")
        
        # User-specific checks
        if user:
            if user.username.lower() in password.lower():
                errors.append("Password cannot contain username")
            
            if user.email and user.email.split('@')[0].lower() in password.lower():
                errors.append("Password cannot contain email prefix")
        
        return errors
    
    async def get_password_strength(self, password: str) -> Dict[str, Any]:
        """Calculate password strength score"""
        score = 0
        feedback = []
        
        # Length scoring
        if len(password) >= 8:
            score += 25
        elif len(password) >= 6:
            score += 15
            feedback.append("Password could be longer")
        else:
            feedback.append("Password is too short")
        
        # Character variety
        if re.search(r'[a-z]', password):
            score += 15
        else:
            feedback.append("Add lowercase letters")
        
        if re.search(r'[A-Z]', password):
            score += 15
        else:
            feedback.append("Add uppercase letters")
        
        if re.search(r'\d', password):
            score += 15
        else:
            feedback.append("Add numbers")
        
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 15
        else:
            feedback.append("Add special characters")
        
        # Pattern penalties
        if re.search(r'(.)\1{2,}', password):  # Repeated characters
            score -= 10
            feedback.append("Avoid repeated characters")
        
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):
            score -= 10
            feedback.append("Avoid sequential numbers")
        
        if re.search(r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', password, re.IGNORECASE):
            score -= 10
            feedback.append("Avoid sequential letters")
        
        # Bonus for length
        if len(password) >= 12:
            score += 15
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        # Determine strength level
        if score >= 80:
            strength = "Very Strong"
        elif score >= 60:
            strength = "Strong"
        elif score >= 40:
            strength = "Moderate"
        elif score >= 20:
            strength = "Weak"
        else:
            strength = "Very Weak"
        
        return {
            "score": score,
            "strength": strength,
            "feedback": feedback
        }
    
    # Advanced Security Features
    async def detect_anomalous_login(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        location_data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Detect anomalous login patterns"""
        if not self.db_manager:
            return {"anomalous": False, "factors": []}
        
        anomaly_factors = []
        risk_score = 0
        
        # Get recent login history (last 30 days)
        recent_logins = await self.db_manager.fetch_all(
            """
            SELECT ip_address, user_agent, timestamp, metadata 
            FROM security_events 
            WHERE user_id = ? AND event_type = 'LOGIN' AND success = 1 
            AND timestamp > ? 
            ORDER BY timestamp DESC
            """,
            (user_id, datetime.now(timezone.utc) - timedelta(days=30))
        )
        
        if not recent_logins:
            return {"anomalous": False, "factors": [], "risk_score": 0}
        
        # Check for new IP address
        known_ips = {login['ip_address'] for login in recent_logins}
        if ip_address not in known_ips:
            anomaly_factors.append("New IP address")
            risk_score += 20
        
        # Check for new user agent/device
        known_agents = {login['user_agent'] for login in recent_logins}
        if user_agent not in known_agents:
            anomaly_factors.append("New device/browser")
            risk_score += 15
        
        # Check login time patterns
        current_hour = datetime.now(timezone.utc).hour
        recent_hours = [
            datetime.fromisoformat(login['timestamp'].replace('Z', '+00:00')).hour
            if isinstance(login['timestamp'], str) else login['timestamp'].hour
            for login in recent_logins[-20:]  # Last 20 logins
        ]
        
        if recent_hours:
            avg_hour = sum(recent_hours) / len(recent_hours)
            hour_deviation = abs(current_hour - avg_hour)
            
            if hour_deviation > 6:  # More than 6 hours difference
                anomaly_factors.append("Unusual login time")
                risk_score += 10
        
        # Check login frequency
        if len(recent_logins) > 1:
            last_login = recent_logins[0]
            time_since_last = datetime.now(timezone.utc) - datetime.fromisoformat(
                last_login['timestamp'].replace('Z', '+00:00') if isinstance(last_login['timestamp'], str)
                else last_login['timestamp'].isoformat()
            )
            
            if time_since_last.total_seconds() < 300:  # Less than 5 minutes
                anomaly_factors.append("Very frequent login attempts")
                risk_score += 25
        
        # Location-based checks (if location data provided)
        if location_data:
            # This would require a geolocation service
            # For now, we'll add a placeholder
            anomaly_factors.append("Location analysis unavailable")
        
        return {
            "anomalous": risk_score >= 30,
            "risk_score": risk_score,
            "factors": anomaly_factors,
            "recommendation": "require_mfa" if risk_score >= 30 else "allow"
        }
    
    async def require_password_change(self, user_id: str, reason: str = "Security policy") -> bool:
        """Force user to change password on next login"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.metadata['password_change_required'] = True
        user.metadata['password_change_reason'] = reason
        user.metadata['password_change_required_at'] = datetime.now(timezone.utc).isoformat()
        
        await self.update_user(user)
        
        await self._log_security_event(
            user_id=user_id,
            event_type="PASSWORD_CHANGE_REQUIRED",
            description=f"Password change required: {reason}",
            success=True,
            risk_score=10
        )
        
        return True
    
    async def bulk_password_reset(self, user_ids: List[str], reason: str = "Security incident") -> Dict[str, bool]:
        """Force password reset for multiple users"""
        results = {}
        
        for user_id in user_ids:
            try:
                success = await self.require_password_change(user_id, reason)
                results[user_id] = success
                
                if success:
                    # Also revoke all existing sessions
                    await self.revoke_all_user_sessions(user_id)
                    
            except Exception as e:
                self.logger.error(f"Failed to reset password for user {user_id}: {str(e)}")
                results[user_id] = False
        
        await self._log_security_event(
            event_type="BULK_PASSWORD_RESET",
            description=f"Bulk password reset initiated for {len(user_ids)} users: {reason}",
            success=True,
            risk_score=50,
            metadata={"affected_users": len(user_ids), "reason": reason}
        )
        
        return results
    
    # Emergency Security Functions
    async def emergency_lockdown(self, reason: str = "Security incident") -> Dict[str, Any]:
        """Emergency system lockdown - disable all non-admin users"""
        if not self.db_manager:
            return {"success": False, "error": "Database not available"}
        
        try:
            # Disable all non-admin users
            result = await self.db_manager.execute(
                """
                UPDATE users 
                SET is_active = FALSE, 
                    metadata = json_set(
                        COALESCE(metadata, '{}'), 
                        '$.emergency_lockdown', ?,
                        '$.lockdown_reason', ?,
                        '$.lockdown_timestamp', ?
                    )
                WHERE role NOT IN ('super_admin', 'admin')
                """,
                (True, reason, datetime.now(timezone.utc).isoformat())
            )
            
            # Revoke all non-admin sessions
            await self.db_manager.execute(
                """
                UPDATE sessions 
                SET is_active = FALSE 
                WHERE user_id IN (
                    SELECT id FROM users WHERE role NOT IN ('super_admin', 'admin')
                )
                """
            )
            
            # Clear cache for all users
            if self.cache_manager:
                # This is a simplified approach - in production, you might want to
                # iterate through users and clear their specific cache entries
                await self.cache_manager.clear()
            
            affected_users = result.rowcount if hasattr(result, 'rowcount') else 0
            
            await self._log_security_event(
                event_type="EMERGENCY_LOCKDOWN",
                description=f"Emergency lockdown activated: {reason}",
                success=True,
                risk_score=100,
                metadata={
                    "reason": reason,
                    "affected_users": affected_users,
                    "initiated_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return {
                "success": True,
                "affected_users": affected_users,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Emergency lockdown failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def lift_emergency_lockdown(self, reason: str = "Incident resolved") -> Dict[str, Any]:
        """Lift emergency lockdown"""
        if not self.db_manager:
            return {"success": False, "error": "Database not available"}
        
        try:
            # Re-enable users who were disabled during lockdown
            result = await self.db_manager.execute(
                """
                UPDATE users 
                SET is_active = TRUE,
                    metadata = json_remove(metadata, '$.emergency_lockdown', '$.lockdown_reason', '$.lockdown_timestamp')
                WHERE json_extract(metadata, '$.emergency_lockdown') = 1
                """
            )
            
            restored_users = result.rowcount if hasattr(result, 'rowcount') else 0
            
            await self._log_security_event(
                event_type="EMERGENCY_LOCKDOWN_LIFTED",
                description=f"Emergency lockdown lifted: {reason}",
                success=True,
                risk_score=0,
                metadata={
                    "reason": reason,
                    "restored_users": restored_users,
                    "lifted_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return {
                "success": True,
                "restored_users": restored_users,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to lift emergency lockdown: {str(e)}")
            return {"success": False, "error": str(e)}


# Factory function for easy initialization
async def create_auth_manager(
    secret_key: str,
    database_url: str,
    redis_url: Optional[str] = None,
    **kwargs
) -> YMERAAuthManager:
    """Factory function to create and initialize AuthManager"""
    
    # Initialize database manager
    db_manager = DatabaseManager(database_url)
    await db_manager.connect()
    
    # Initialize cache manager if Redis URL provided
    cache_manager = None
    if redis_url:
        cache_manager = RedisCacheManager(redis_url)
        await cache_manager.connect()
    
    # Create and initialize auth manager
    auth_manager = YMERAAuthManager(
        secret_key=secret_key,
        db_manager=db_manager,
        cache_manager=cache_manager,
        **kwargs
    )
    
    await auth_manager.initialize()
    return auth_manager


# Example usage and testing utilities
if __name__ == "__main__":
    async def example_usage():
        """Example usage of YMERA Auth Manager"""
        
        # Initialize with factory function
        auth = await create_auth_manager(
            secret_key="your-super-secret-key-here",
            database_url="sqlite:///auth.db",
            redis_url="redis://localhost:6379/0"
        )
        
        try:
            # Create a test user
            user = await auth.create_user(
                username="testuser",
                email="test@example.com",
                password="SecurePassword123!",
                role=UserRole.DEVELOPER
            )
            print(f"Created user: {user.username}")
            
            # Login and get tokens
            login_result = await auth.login(
                identifier="testuser",
                password="SecurePassword123!",
                ip_address="127.0.0.1",
                user_agent="Test Client"
            )
            print(f"Login successful: {login_result['user'].username}")
            
            # Verify access token
            payload = await auth.verify_access_token(login_result['access_token'])
            print(f"Token verified for user: {payload['user_id']}")
            
            # Check permissions
            has_perm = await auth.check_permission(user.id, Permission.READ_DATA)
            print(f"User has READ_DATA permission: {has_perm}")
            
            # Get health status
            health = await auth.get_auth_health()
            print(f"Auth system health: {health['status']}")
            
        except Exception as e:
            print(f"Error: {str(e)}")
        
        finally:
            # Cleanup
            if auth.db_manager:
                await auth.db_manager.disconnect()
            if auth.cache_manager:
                await auth.cache_manager.disconnect()
    
    # Run example
    asyncio.run(example_usage())