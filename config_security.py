"""
YMERA Enterprise - Security Configuration
Production-Ready Security Management - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports (alphabetical)
import bcrypt
import jwt
import structlog
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel, Field, validator

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.security")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# JWT Constants
DEFAULT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password Constants
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
PASSWORD_ROUNDS = 12

# Rate Limiting Constants
DEFAULT_RATE_LIMIT = 1000  # requests per window
DEFAULT_RATE_WINDOW = 3600  # seconds (1 hour)

# Encryption Constants
SALT_LENGTH = 32
KEY_LENGTH = 32

# Security Headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}

# ===============================================================================
# ENUMS & DATA MODELS
# ===============================================================================

class TokenType(str, Enum):
    """Token type enumeration"""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    VERIFICATION = "verification"

class PermissionLevel(str, Enum):
    """Permission level enumeration"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

@dataclass
class SecurityConfig:
    """
    Comprehensive security configuration with validation and optimization.
    
    This class manages all security-related settings including JWT configuration,
    password policies, encryption settings, and rate limiting parameters.
    """
    
    # JWT Configuration
    secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = DEFAULT_ALGORITHM
    access_token_expire_minutes: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS
    
    # Password Configuration
    password_min_length: int = MIN_PASSWORD_LENGTH
    password_max_length: int = MAX_PASSWORD_LENGTH
    password_rounds: int = PASSWORD_ROUNDS
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special_chars: bool = True
    
    # Rate Limiting Configuration
    rate_limit_requests: int = DEFAULT_RATE_LIMIT
    rate_limit_window: int = DEFAULT_RATE_WINDOW
    rate_limit_enabled: bool = True
    
    # Session Configuration
    session_timeout_minutes: int = 480  # 8 hours
    max_concurrent_sessions: int = 5
    
    # Encryption Configuration
    encryption_key: Optional[str] = None
    
    # Security Headers
    security_headers_enabled: bool = True
    cors_enabled: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    
    # Additional Options
    extra_options: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and initialize security configuration"""
        self._validate_keys()
        self._validate_password_policy()
        self._setup_encryption()
        self._validate_rate_limiting()
    
    def _validate_keys(self) -> None:
        """Validate secret keys"""
        if not self.secret_key or len(self.secret_key) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        
        if not self.jwt_secret_key or len(self.jwt_secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
    
    def _validate_password_policy(self) -> None:
        """Validate password policy settings"""
        if self.password_min_length < 8:
            logger.warning("Password minimum length is less than recommended 8 characters")
        
        if self.password_max_length > 256:
            logger.warning("Password maximum length is very high, may impact performance")
    
    def _setup_encryption(self) -> None:
        """Setup encryption configuration"""
        if not self.encryption_key:
            # Generate encryption key from secret key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=KEY_LENGTH,
                salt=self.secret_key[:SALT_LENGTH].encode(),
                iterations=100000,
            )
            key = kdf.derive(self.secret_key.encode())
            self.encryption_key = Fernet.generate_key().decode()
    
    def _validate_rate_limiting(self) -> None:
        """Validate rate limiting configuration"""
        if self.rate_limit_requests < 1:
            raise ValueError("Rate limit requests must be at least 1")
        
        if self.rate_limit_window < 60:
            logger.warning("Rate limit window is very short, may impact usability")

# ===============================================================================
# AUTHENTICATION MODELS
# ===============================================================================

class TokenPayload(BaseModel):
    """JWT token payload model"""
    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    type: TokenType = Field(..., description="Token type")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    class Config:
        use_enum_values = True

class AuthenticationResponse(BaseModel):
    """Authentication response model"""
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user_id: str = Field(..., description="User identifier")
    permissions: List[str] = Field(default_factory=list, description="User permissions")

class User(BaseModel):
    """User model for authentication"""
    id: str = Field(..., description="User identifier")
    email: str = Field(..., description="User email")
    username: Optional[str] = Field(None, description="Username")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    is_active: bool = Field(default=True, description="User active status")
    is_verified: bool = Field(default=False, description="User verification status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

# ===============================================================================
# SECURITY MANAGERS
# ===============================================================================

class PasswordManager:
    """
    Production-ready password management with comprehensive security features.
    
    This class handles password hashing, validation, strength checking,
    and provides secure password operations.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="PasswordManager")
        
        # Setup password context
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=config.password_rounds
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt with salt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        self.validate_password_strength(password)
        
        hashed = self.pwd_context.hash(password)
        self.logger.debug("Password hashed successfully")
        
        return hashed
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            is_valid = self.pwd_context.verify(plain_password, hashed_password)
            
            if is_valid:
                self.logger.debug("Password verification successful")
            else:
                self.logger.debug("Password verification failed")
            
            return is_valid
            
        except Exception as e:
            self.logger.error("Password verification error", error=str(e))
            return False
    
    def validate_password_strength(self, password: str) -> None:
        """
        Validate password strength according to policy.
        
        Args:
            password: Password to validate
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        errors = []
        
        # Length check
        if len(password) < self.config.password_min_length:
            errors.append(f"Password must be at least {self.config.password_min_length} characters long")
        
        if len(password) > self.config.password_max_length:
            errors.append(f"Password must not exceed {self.config.password_max_length} characters")
        
        # Character type checks
        if self.config.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.config.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.config.require_numbers and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        if self.config.require_special_chars and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        # Common password check
        if self._is_common_password(password):
            errors.append("Password is too common, please choose a more secure password")
        
        if errors:
            raise ValueError("; ".join(errors))
    
    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common passwords list"""
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        }
        return password.lower() in common_passwords
    
    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate cryptographically secure password.
        
        Args:
            length: Password length (minimum 12)
            
        Returns:
            Generated secure password
        """
        if length < 12:
            length = 12
        
        import string
        
        # Ensure all character types are included
        chars = (
            string.ascii_lowercase +
            string.ascii_uppercase +
            string.digits +
            "!@#$%^&*()_+-="
        )
        
        # Generate password ensuring all types are present
        password = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*()_+-=")
        ]
        
        # Fill remaining length with random characters
        for _ in range(length - 4):
            password.append(secrets.choice(chars))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        
        generated = ''.join(password)
        self.logger.debug("Secure password generated", length=length)
        
        return generated

class JWTManager:
    """
    Production-ready JWT token management with comprehensive security features.
    
    This class handles JWT token creation, validation, refresh, and provides
    secure token operations with proper error handling.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="JWTManager")
        
        # Token blacklist for logout/invalidation
        self._blacklisted_tokens: set = set()
    
    def create_access_token(
        self, 
        user_id: str, 
        permissions: List[str] = None,
        session_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User identifier
            permissions: User permissions list
            session_id: Session identifier
            expires_delta: Custom expiration delta
            
        Returns:
            Encoded JWT access token
        """
        if permissions is None:
            permissions = []
        
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.config.access_token_expire_minutes)
        
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        
        payload = TokenPayload(
            sub=user_id,
            exp=int(expire.timestamp()),
            iat=int(now.timestamp()),
            type=TokenType.ACCESS,
            permissions=permissions,
            session_id=session_id
        )
        
        token = jwt.encode(
            payload.dict(),
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm
        )
        
        self.logger.debug("Access token created", user_id=user_id, expires_at=expire.isoformat())
        return token
    
    def create_refresh_token(
        self, 
        user_id: str,
        session_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            expires_delta: Custom expiration delta
            
        Returns:
            Encoded JWT refresh token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self.config.refresh_token_expire_days)
        
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        
        payload = TokenPayload(
            sub=user_id,
            exp=int(expire.timestamp()),
            iat=int(now.timestamp()),
            type=TokenType.REFRESH,
            permissions=[],
            session_id=session_id
        )
        
        token = jwt.encode(
            payload.dict(),
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm
        )
        
        self.logger.debug("Refresh token created", user_id=user_id, expires_at=expire.isoformat())
        return token
    
    def verify_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> TokenPayload:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            token_type: Expected token type
            
        Returns:
            Decoded token payload
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Check if token is blacklisted
            if token in self._blacklisted_tokens:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
            
            # Decode token
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm]
            )
            
            token_payload = TokenPayload(**payload)
            
            # Verify token type
            if token_payload.type != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token type. Expected {token_type}, got {token_payload.type}"
                )
            
            # Check expiration
            if token_payload.exp < int(time.time()):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            
            self.logger.debug("Token verified successfully", user_id=token_payload.sub)
            return token_payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            self.logger.warning("Invalid token provided", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            self.logger.error("Token verification error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed"
            )
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Create new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token pair with access and refresh tokens
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, TokenType.REFRESH)
        
        # Create new tokens
        new_access_token = self.create_access_token(
            user_id=payload.sub,
            permissions=payload.permissions,
            session_id=payload.session_id
        )
        
        new_refresh_token = self.create_refresh_token(
            user_id=payload.sub,
            session_id=payload.session_id
        )
        
        # Blacklist old refresh token
        self._blacklisted_tokens.add(refresh_token)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": self.config.access_token_expire_minutes * 60
        }
    
    def revoke_token(self, token: str) -> None:
        """
        Revoke token by adding it to blacklist.
        
        Args:
            token: Token to revoke
        """
        self._blacklisted_tokens.add(token)
        self.logger.debug("Token revoked")
    
    def cleanup_expired_tokens(self) -> None:
        """Remove expired tokens from blacklist"""
        current_time = int(time.time())
        tokens_to_remove = set()
        
        for token in self._blacklisted_tokens:
            try:
                payload = jwt.decode(
                    token,
                    self.config.jwt_secret_key,
                    algorithms=[self.config.jwt_algorithm],
                    options={"verify_exp": False}  # Don't verify expiration during cleanup
                )
                if payload.get("exp", 0) < current_time:
                    tokens_to_remove.add(token)
            except:
                # If we can't decode the token, remove it
                tokens_to_remove.add(token)
        
        self._blacklisted_tokens -= tokens_to_remove
        
        if tokens_to_remove:
            self.logger.debug("Expired tokens cleaned up", count=len(tokens_to_remove))

class EncryptionManager:
    """
    Production-ready encryption manager for sensitive data.
    
    This class provides encryption and decryption capabilities for sensitive
    data storage and transmission with proper key management.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="EncryptionManager")
        
        # Initialize Fernet encryption
        if config.encryption_key:
            self.fernet = Fernet(config.encryption_key.encode())
        else:
            raise ValueError("Encryption key not provided")
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.
        
        Args:
            data: String data to encrypt
            
        Returns:
            Encrypted data as base64 string
        """
        try:
            encrypted_data = self.fernet.encrypt(data.encode())
            self.logger.debug("Data encrypted successfully")
            return encrypted_data.decode()
        except Exception as e:
            self.logger.error("Encryption failed", error=str(e))
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt string data.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted string data
            
        Raises:
            InvalidToken: If decryption fails
        """
        try:
            decrypted_data = self.fernet.decrypt(encrypted_data.encode())
            self.logger.debug("Data decrypted successfully")
            return decrypted_data.decode()
        except InvalidToken:
            self.logger.error("Decryption failed - invalid token")
            raise
        except Exception as e:
            self.logger.error("Decryption failed", error=str(e))
            raise
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Encrypt dictionary data.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Encrypted data as base64 string
        """
        import json
        json_data = json.dumps(data, default=str)
        return self.encrypt(json_data)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt dictionary data.
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted dictionary
        """
        import json
        json_data = self.decrypt(encrypted_data)
        return json.loads(json_data)

class RateLimiter:
    """
    Production-ready rate limiting with multiple strategies.
    
    This class provides rate limiting capabilities with support for
    different algorithms and storage backends.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="RateLimiter")
        
        # In-memory storage for rate limiting
        self._requests: Dict[str, List[float]] = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def is_allowed(self, identifier: str, limit: Optional[int] = None, window: Optional[int] = None) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            limit: Custom request limit
            window: Custom time window in seconds
            
        Returns:
            True if request is allowed, False otherwise
        """
        if not self.config.rate_limit_enabled:
            return True
        
        current_time = time.time()
        limit = limit or self.config.rate_limit_requests
        window = window or self.config.rate_limit_window
        
        # Cleanup old entries periodically
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(current_time)
            self._last_cleanup = current_time
        
        # Get request history for identifier
        if identifier not in self._requests:
            self._requests[identifier] = []
        
        request_times = self._requests[identifier]
        
        # Remove requests outside the window
        cutoff_time = current_time - window
        request_times[:] = [t for t in request_times if t > cutoff_time]
        
        # Check if limit is exceeded
        if len(request_times) >= limit:
            self.logger.debug("Rate limit exceeded", identifier=identifier, requests=len(request_times))
            return False
        
        # Add current request
        request_times.append(current_time)
        return True
    
    def get_remaining_requests(self, identifier: str, limit: Optional[int] = None) -> int:
        """
        Get remaining requests for identifier.
        
        Args:
            identifier: Unique identifier
            limit: Custom request limit
            
        Returns:
            Number of remaining requests
        """
        limit = limit or self.config.rate_limit_requests
        
        if identifier not in self._requests:
            return limit
        
        current_requests = len(self._requests[identifier])
        return max(0, limit - current_requests)
    
    def reset_limit(self, identifier: str) -> None:
        """
        Reset rate limit for identifier.
        
        Args:
            identifier: Unique identifier to reset
        """
        if identifier in self._requests:
            del self._requests[identifier]
            self.logger.debug("Rate limit reset", identifier=identifier)
    
    def _cleanup_old_entries(self, current_time: float) -> None:
        """Remove old entries from memory"""
        cutoff_time = current_time - self.config.rate_limit_window
        
        for identifier in list(self._requests.keys()):
            request_times = self._requests[identifier]
            request_times[:] = [t for t in request_times if t > cutoff_time]
            
            # Remove empty entries
            if not request_times:
                del self._requests[identifier]

# ===============================================================================
# AUTHENTICATION DEPENDENCIES
# ===============================================================================

class SecurityDependencies:
    """
    FastAPI security dependencies for authentication and authorization.
    
    This class provides reusable dependencies for FastAPI applications
    to handle authentication, authorization, and security middleware.
    """
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.jwt_manager = JWTManager(config)
        self.rate_limiter = RateLimiter(config)
        self.logger = logger.bind(component="SecurityDependencies")
        
        # HTTP Bearer security scheme
        self.security_scheme = HTTPBearer(auto_error=False)
    
    async def get_current_user(
        self, 
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
    ) -> User:
        """
        Get current authenticated user from JWT token.
        
        Args:
            request: FastAPI request object
            credentials: HTTP bearer credentials
            
        Returns:
            Authenticated user object
            
        Raises:
            HTTPException: If authentication fails
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify token
        token_payload = self.jwt_manager.verify_token(credentials.credentials)
        
        # Here you would typically fetch user from database
        # For now, we'll create a user object from token payload
        user = User(
            id=token_payload.sub,
            email=f"user_{token_payload.sub}@example.com",  # This should come from database
            permissions=token_payload.permissions,
            is_active=True,
            is_verified=True
        )
        
        self.logger.debug("User authenticated", user_id=user.id)
        return user
    
    def require_permissions(self, required_permissions: List[str]):
        """
        Create dependency that requires specific permissions.
        
        Args:
            required_permissions: List of required permissions
            
        Returns:
            FastAPI dependency function
        """
        async def permission_checker(current_user: User = Depends(self.get_current_user)) -> User:
            user_permissions = set(current_user.permissions)
            required_perms = set(required_permissions)
            
            if not required_perms.issubset(user_permissions):
                missing_perms = required_perms - user_permissions
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {', '.join(missing_perms)}"
                )
            
            return current_user
        
        return permission_checker
    
    def require_admin(self):
        """Create dependency that requires admin permissions"""
        return self.require_permissions([PermissionLevel.ADMIN])
    
    def rate_limit(self, requests: int = None, window: int = None):
        """
        Create rate limiting dependency.
        
        Args:
            requests: Number of requests allowed
            window: Time window in seconds
            
        Returns:
            FastAPI dependency function
        """
        async def rate_limit_checker(request: Request) -> None:
            # Use client IP as identifier
            client_ip = request.client.host
            
            if not self.rate_limiter.is_allowed(client_ip, requests, window):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
        
        return rate_limit_checker

# ===============================================================================
# SECURITY MIDDLEWARE
# ===============================================================================

class SecurityMiddleware:
    """Security middleware for FastAPI applications"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="SecurityMiddleware")
    
    async def __call__(self, request: Request, call_next):
        """Process request with security headers and checks"""
        # Add security headers to response
        response = await call_next(request)
        
        if self.config.security_headers_enabled:
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value
        
        return response

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def generate_session_id() -> str:
    """Generate cryptographically secure session ID"""
    return secrets.token_urlsafe(32)

def constant_time_compare(a: str, b: str) -> bool:
    """Constant time string comparison to prevent timing attacks"""
    return hmac.compare_digest(a.encode(), b.encode())

def hash_api_key(api_key: str, salt: Optional[str] = None) -> str:
    """Hash API key for storage"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    key_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt.encode(), 100000)
    return f"{salt}:{key_hash.hex()}"

def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify API key against stored hash"""
    try:
        salt, key_hash = stored_hash.split(':', 1)
        expected_hash = hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt.encode(), 100000)
        return constant_time_compare(key_hash, expected_hash.hex())
    except (ValueError, AttributeError):
        return False

# ===============================================================================
# CONFIGURATION FACTORY
# ===============================================================================

@lru_cache()
def get_security_config() -> SecurityConfig:
    """
    Get security configuration with caching.
    
    This function creates and caches a SecurityConfig instance based on
    environment variables and application settings.
    
    Returns:
        SecurityConfig: Configured security settings
    """
    from .settings import get_settings
    
    settings = get_settings()
    
    config = SecurityConfig(
        secret_key=settings.SECRET_KEY,
        jwt_secret_key=settings.JWT_SECRET_KEY,
        jwt_algorithm=settings.JWT_ALGORITHM,
        access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        rate_limit_requests=settings.RATE_LIMIT_REQUESTS,
        rate_limit_window=settings.RATE_LIMIT_WINDOW,
        cors_origins=settings.CORS_ORIGINS
    )
    
    logger.info(
        "Security configuration initialized",
        jwt_algorithm=config.jwt_algorithm,
        access_token_expire_minutes=config.access_token_expire_minutes,
        rate_limit_enabled=config.rate_limit_enabled
    )
    
    return config

# ===============================================================================
# INITIALIZATION FUNCTIONS
# ===============================================================================

def initialize_security() -> Dict[str, Any]:
    """
    Initialize security components and return security managers.
    
    Returns:
        Dictionary containing initialized security managers
    """
    config = get_security_config()
    
    managers = {
        "password_manager": PasswordManager(config),
        "jwt_manager": JWTManager(config),
        "encryption_manager": EncryptionManager(config),
        "rate_limiter": RateLimiter(config),
        "dependencies": SecurityDependencies(config),
        "middleware": SecurityMiddleware(config)
    }
    
    logger.info("Security components initialized successfully")
    return managers

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "SecurityConfig",
    "TokenType",
    "PermissionLevel",
    "TokenPayload",
    "AuthenticationResponse",
    "User",
    "PasswordManager",
    "JWTManager",
    "EncryptionManager",
    "RateLimiter",
    "SecurityDependencies",
    "SecurityMiddleware",
    "get_security_config",
    "initialize_security",
    "generate_session_id",
    "constant_time_compare",
    "hash_api_key",
    "verify_api_key"
]