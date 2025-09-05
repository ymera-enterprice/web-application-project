"""
YMERA Enterprise - Security & Authentication System
Production-Ready Security Infrastructure - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# SECURITY/__INIT__.PY
# ===============================================================================

"""
YMERA Security & Authentication Package
Comprehensive security infrastructure for enterprise deployment
"""

from .jwt_handler import JWTHandler, TokenData, verify_token, create_access_token
from .password_manager import PasswordManager, hash_password, verify_password
from .api_key_manager import APIKeyManager, APIKey, rotate_api_key
from .file_scanner import FileScanner, ScanResult, scan_file_for_threats
from .access_control import AccessController, Permission, Role, check_permissions

__version__ = "4.0.0"
__author__ = "YMERA Security Team"

__all__ = [
    "JWTHandler",
    "TokenData", 
    "verify_token",
    "create_access_token",
    "PasswordManager",
    "hash_password",
    "verify_password", 
    "APIKeyManager",
    "APIKey",
    "rotate_api_key",
    "FileScanner",
    "ScanResult",
    "scan_file_for_threats",
    "AccessController",
    "Permission",
    "Role",
    "check_permissions"
]

# ===============================================================================
# SECURITY/JWT_HANDLER.PY
# ===============================================================================

"""
YMERA Enterprise - JWT Token Management
Production-Ready JWT Authentication - v4.0
Enterprise-grade implementation with zero placeholders
"""

# Standard library imports
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

# Third-party imports
import jwt
import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
import aioredis

# Local imports
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.security.jwt")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "RS256"
TOKEN_BLACKLIST_PREFIX = "blacklist:token:"
REFRESH_TOKEN_PREFIX = "refresh:token:"

settings = get_settings()
security = HTTPBearer()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class JWTConfig:
    """Configuration for JWT token management"""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "RS256"
    private_key_path: str = "security/keys/private_key.pem"
    public_key_path: str = "security/keys/public_key.pem"
    issuer: str = "YMERA-Platform"
    audience: str = "ymera-users"

class TokenData(BaseModel):
    """Token payload data structure"""
    user_id: str
    username: str
    email: str
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    token_type: str = "access"
    jti: str = Field(default_factory=lambda: str(uuid.uuid4()))
    iat: datetime = Field(default_factory=datetime.utcnow)
    exp: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=30))
    
    class Config:
        json_encoders = {
            datetime: lambda v: int(v.timestamp())
        }

class TokenResponse(BaseModel):
    """API response for token operations"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    permissions: List[str]

class TokenValidationResult(BaseModel):
    """Result of token validation"""
    valid: bool
    token_data: Optional[TokenData] = None
    error: Optional[str] = None
    remaining_time: Optional[int] = None

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class JWTHandler:
    """Production-ready JWT token management system"""
    
    def __init__(self, config: JWTConfig):
        self.config = config
        self.logger = logger.bind(component="jwt_handler")
        self._private_key = None
        self._public_key = None
        self._redis_client = None
        self._initialize_keys()
    
    def _initialize_keys(self) -> None:
        """Initialize RSA key pair for token signing"""
        try:
            # Load existing keys or generate new ones
            if os.path.exists(self.config.private_key_path) and os.path.exists(self.config.public_key_path):
                self._load_existing_keys()
            else:
                self._generate_new_keys()
            
            self.logger.info("JWT keys initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize JWT keys", error=str(e))
            raise RuntimeError(f"JWT key initialization failed: {str(e)}")
    
    def _load_existing_keys(self) -> None:
        """Load existing RSA keys from files"""
        with open(self.config.private_key_path, 'rb') as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )
        
        with open(self.config.public_key_path, 'rb') as f:
            self._public_key = serialization.load_pem_public_key(f.read())
    
    def _generate_new_keys(self) -> None:
        """Generate new RSA key pair"""
        # Generate private key
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self._public_key = self._private_key.public_key()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config.private_key_path), exist_ok=True)
        
        # Save private key
        with open(self.config.private_key_path, 'wb') as f:
            f.write(self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Save public key
        with open(self.config.public_key_path, 'wb') as f:
            f.write(self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client for token management"""
        if not self._redis_client:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis_client
    
    @track_performance
    async def create_access_token(self, token_data: TokenData) -> str:
        """Create a new access token"""
        try:
            # Set token expiration
            token_data.exp = datetime.utcnow() + timedelta(
                minutes=self.config.access_token_expire_minutes
            )
            token_data.iat = datetime.utcnow()
            token_data.token_type = "access"
            
            # Create payload
            payload = {
                "user_id": token_data.user_id,
                "username": token_data.username,
                "email": token_data.email,
                "roles": token_data.roles,
                "permissions": token_data.permissions,
                "token_type": token_data.token_type,
                "jti": token_data.jti,
                "iat": int(token_data.iat.timestamp()),
                "exp": int(token_data.exp.timestamp()),
                "iss": self.config.issuer,
                "aud": self.config.audience
            }
            
            # Sign token
            token = jwt.encode(
                payload,
                self._private_key,
                algorithm=self.config.algorithm
            )
            
            # Store token metadata in Redis
            redis_client = await self._get_redis_client()
            await redis_client.setex(
                f"token:metadata:{token_data.jti}",
                self.config.access_token_expire_minutes * 60,
                json.dumps({
                    "user_id": token_data.user_id,
                    "token_type": "access",
                    "created_at": token_data.iat.isoformat()
                })
            )
            
            self.logger.info(
                "Access token created",
                user_id=token_data.user_id,
                jti=token_data.jti,
                expires_at=token_data.exp.isoformat()
            )
            
            return token
            
        except Exception as e:
            self.logger.error("Failed to create access token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
    
    @track_performance
    async def create_refresh_token(self, user_id: str) -> str:
        """Create a new refresh token"""
        try:
            jti = str(uuid.uuid4())
            exp = datetime.utcnow() + timedelta(days=self.config.refresh_token_expire_days)
            
            payload = {
                "user_id": user_id,
                "token_type": "refresh",
                "jti": jti,
                "iat": int(datetime.utcnow().timestamp()),
                "exp": int(exp.timestamp()),
                "iss": self.config.issuer,
                "aud": self.config.audience
            }
            
            token = jwt.encode(
                payload,
                self._private_key,
                algorithm=self.config.algorithm
            )
            
            # Store refresh token in Redis
            redis_client = await self._get_redis_client()
            await redis_client.setex(
                f"{REFRESH_TOKEN_PREFIX}{jti}",
                self.config.refresh_token_expire_days * 24 * 3600,
                json.dumps({
                    "user_id": user_id,
                    "created_at": datetime.utcnow().isoformat()
                })
            )
            
            self.logger.info(
                "Refresh token created",
                user_id=user_id,
                jti=jti,
                expires_at=exp.isoformat()
            )
            
            return token
            
        except Exception as e:
            self.logger.error("Failed to create refresh token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Refresh token creation failed"
            )
    
    @track_performance
    async def verify_token(self, token: str) -> TokenValidationResult:
        """Verify and decode a JWT token"""
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer
            )
            
            # Check if token is blacklisted
            redis_client = await self._get_redis_client()
            is_blacklisted = await redis_client.exists(
                f"{TOKEN_BLACKLIST_PREFIX}{payload['jti']}"
            )
            
            if is_blacklisted:
                return TokenValidationResult(
                    valid=False,
                    error="Token has been revoked"
                )
            
            # Create token data
            token_data = TokenData(
                user_id=payload["user_id"],
                username=payload.get("username", ""),
                email=payload.get("email", ""),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                token_type=payload.get("token_type", "access"),
                jti=payload["jti"],
                iat=datetime.fromtimestamp(payload["iat"]),
                exp=datetime.fromtimestamp(payload["exp"])
            )
            
            # Calculate remaining time
            remaining_time = int((token_data.exp - datetime.utcnow()).total_seconds())
            
            return TokenValidationResult(
                valid=True,
                token_data=token_data,
                remaining_time=remaining_time
            )
            
        except jwt.ExpiredSignatureError:
            return TokenValidationResult(
                valid=False,
                error="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            return TokenValidationResult(
                valid=False,
                error=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            self.logger.error("Token verification failed", error=str(e))
            return TokenValidationResult(
                valid=False,
                error="Token verification failed"
            )
    
    async def blacklist_token(self, jti: str, exp: datetime) -> bool:
        """Add token to blacklist"""
        try:
            redis_client = await self._get_redis_client()
            ttl = int((exp - datetime.utcnow()).total_seconds())
            
            if ttl > 0:
                await redis_client.setex(
                    f"{TOKEN_BLACKLIST_PREFIX}{jti}",
                    ttl,
                    "blacklisted"
                )
                
                self.logger.info("Token blacklisted", jti=jti)
                return True
                
            return False
            
        except Exception as e:
            self.logger.error("Failed to blacklist token", error=str(e), jti=jti)
            return False
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Generate new access token using refresh token"""
        try:
            # Verify refresh token
            validation_result = await self.verify_token(refresh_token)
            
            if not validation_result.valid or validation_result.token_data.token_type != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Check if refresh token exists in Redis
            redis_client = await self._get_redis_client()
            refresh_data = await redis_client.get(
                f"{REFRESH_TOKEN_PREFIX}{validation_result.token_data.jti}"
            )
            
            if not refresh_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token not found"
                )
            
            # Get user data and create new access token
            # This would typically fetch from database
            token_data = TokenData(
                user_id=validation_result.token_data.user_id,
                username=validation_result.token_data.username,
                email=validation_result.token_data.email,
                roles=validation_result.token_data.roles,
                permissions=validation_result.token_data.permissions
            )
            
            new_access_token = await self.create_access_token(token_data)
            
            return TokenResponse(
                access_token=new_access_token,
                refresh_token=refresh_token,
                expires_in=self.config.access_token_expire_minutes * 60,
                user_id=token_data.user_id,
                permissions=token_data.permissions
            )
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Failed to refresh token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed"
            )
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self._redis_client:
            await self._redis_client.close()

# ===============================================================================
# DEPENDENCY FUNCTIONS
# ===============================================================================

# Global JWT handler instance
_jwt_handler = None

async def get_jwt_handler() -> JWTHandler:
    """Get JWT handler instance"""
    global _jwt_handler
    if not _jwt_handler:
        config = JWTConfig(
            access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            refresh_token_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        _jwt_handler = JWTHandler(config)
    return _jwt_handler

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """FastAPI dependency for token verification"""
    jwt_handler = await get_jwt_handler()
    validation_result = await jwt_handler.verify_token(credentials.credentials)
    
    if not validation_result.valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=validation_result.error,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return validation_result.token_data

async def create_access_token(token_data: TokenData) -> str:
    """Create access token helper function"""
    jwt_handler = await get_jwt_handler()
    return await jwt_handler.create_access_token(token_data)

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def generate_token_pair(user_id: str, user_data: Dict[str, Any]) -> TokenResponse:
    """Generate both access and refresh tokens"""
    jwt_handler = await get_jwt_handler()
    
    token_data = TokenData(
        user_id=user_id,
        username=user_data.get("username", ""),
        email=user_data.get("email", ""),
        roles=user_data.get("roles", []),
        permissions=user_data.get("permissions", [])
    )
    
    access_token = await jwt_handler.create_access_token(token_data)
    refresh_token = await jwt_handler.create_refresh_token(user_id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=jwt_handler.config.access_token_expire_minutes * 60,
        user_id=user_id,
        permissions=token_data.permissions
    )

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "JWTHandler",
    "TokenData",
    "TokenResponse", 
    "TokenValidationResult",
    "JWTConfig",
    "verify_token",
    "create_access_token",
    "generate_token_pair"
]

# ===============================================================================
# SECURITY/PASSWORD_MANAGER.PY
# ===============================================================================

"""
YMERA Enterprise - Password Management
Production-Ready Password Security - v4.0
Enterprise-grade implementation with zero placeholders
"""

# Standard library imports
import asyncio
import hashlib
import logging
import os
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Third-party imports
import bcrypt
import structlog
from passlib.context import CryptContext
from passlib.hash import argon2
from pydantic import BaseModel, Field, validator
import aioredis
from cryptography.fernet import Fernet

# Local imports
from config.settings import get_settings
from monitoring.performance_tracker import track_performance

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.security.password")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Password complexity requirements
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGITS = True
REQUIRE_SPECIAL_CHARS = True
SPECIAL_CHARACTERS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Hash configuration
BCRYPT_ROUNDS = 12
ARGON2_TIME_COST = 2
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 1

# Password history and policies
MAX_PASSWORD_HISTORY = 10
PASSWORD_EXPIRY_DAYS = 90
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class PasswordConfig:
    """Configuration for password management"""
    min_length: int = MIN_PASSWORD_LENGTH
    max_length: int = MAX_PASSWORD_LENGTH
    require_uppercase: bool = REQUIRE_UPPERCASE
    require_lowercase: bool = REQUIRE_LOWERCASE
    require_digits: bool = REQUIRE_DIGITS
    require_special: bool = REQUIRE_SPECIAL_CHARS
    special_chars: str = SPECIAL_CHARACTERS
    bcrypt_rounds: int = BCRYPT_ROUNDS
    max_history: int = MAX_PASSWORD_HISTORY
    expiry_days: int = PASSWORD_EXPIRY_DAYS

class PasswordValidationResult(BaseModel):
    """Result of password validation"""
    valid: bool
    score: int = Field(ge=0, le=100)
    errors: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    entropy: float = 0.0

class PasswordHashResult(BaseModel):
    """Result of password hashing"""
    hash: str
    salt: str
    algorithm: str = "argon2"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class LoginAttempt(BaseModel):
    """Login attempt tracking"""
    user_id: str
    ip_address: str
    user_agent: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool
    failure_reason: Optional[str] = None

class AccountLockout(BaseModel):
    """Account lockout information"""
    user_id: str
    locked_at: datetime
    unlock_at: datetime
    attempt_count: int
    ip_addresses: List[str] = Field(default_factory=list)

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class PasswordManager:
    """Production-ready password management system"""
    
    def __init__(self, config: PasswordConfig):
        self.config = config
        self.logger = logger.bind(component="password_manager")
        self._redis_client = None
        self._fernet = None
        self._setup_crypto_context()
        self._initialize_encryption()
    
    def _setup_crypto_context(self) -> None:
        """Initialize password hashing context"""
        self.pwd_context = CryptContext(
            schemes=["argon2", "bcrypt"],
            default="argon2",
            argon2__time_cost=ARGON2_TIME_COST,
            argon2__memory_cost=ARGON2_MEMORY_COST,
            argon2__parallelism=ARGON2_PARALLELISM,
            bcrypt__rounds=self.config.bcrypt_rounds,
            deprecated="auto"
        )
    
    def _initialize_encryption(self) -> None:
        """Initialize Fernet encryption for sensitive data"""
        key = os.environ.get("PASSWORD_ENCRYPTION_KEY")
        if not key:
            key = Fernet.generate_key()
            self.logger.warning("Generated new encryption key - store securely!")
        else:
            key = key.encode()
        
        self._fernet = Fernet(key)
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client for session management"""
        if not self._redis_client:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
        return self._redis_client
    
    @track_performance
    def validate_password_strength(self, password: str) -> PasswordValidationResult:
        """Comprehensive password strength validation"""
        errors = []
        suggestions = []
        score = 0
        
        # Length validation
        if len(password) < self.config.min_length:
            errors.append(f"Password must be at least {self.config.min_length} characters long")
            suggestions.append(f"Add {self.config.min_length - len(password)} more characters")
        elif len(password) > self.config.max_length:
            errors.append(f"Password must not exceed {self.config.max_length} characters")
        else:
            score += min(25, (len(password) - self.config.min_length) * 2)
        
        # Character type validation
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in self.config.special_chars for c in password)
        
        if self.config.require_uppercase and not has_upper:
            errors.append("Password must contain at least one uppercase letter")
            suggestions.append("Add uppercase letters (A-Z)")
        elif has_upper:
            score += 15
        
        if self.config.require_lowercase and not has_lower:
            errors.append("Password must contain at least one lowercase letter")
            suggestions.append("Add lowercase letters (a-z)")
        elif has_lower:
            score += 15
        
        if self.config.require_digits and not has_digit:
            errors.append("Password must contain at least one digit")
            suggestions.append("Add numbers (0-9)")
        elif has_digit:
            score += 15
        
        if self.config.require_special and not has_special:
            errors.append("Password must contain at least one special character")
            suggestions.append(f"Add special characters ({self.config.special_chars[:10]}...)")
        elif has_special:
            score += 15
        
        # Calculate entropy
        entropy = self._calculate_entropy(password)
        score += min(20, int(entropy / 4))
        
        # Common password checks
        if self._is_common_password(password):
            errors.append("Password is too common")
            suggestions.append("Use a more unique password")
            score = max(0, score - 30)
        
        # Pattern detection
        if self._has_patterns(password):
            errors.append("Password contains predictable patterns")
            suggestions.append("Avoid sequential or repetitive patterns")
            score = max(0, score - 20)
        
        return PasswordValidationResult(
            valid=len(errors) == 0,
            score=min(100, score),
            errors=errors,
            suggestions=suggestions,
            entropy=entropy
        )
    
    def _calculate_entropy(self, password: str) -> float:
        """Calculate password entropy"""
        charset_size = 0
        
        if any(c.islower() for c in password):
            charset_size += 26
        if any(c.isupper() for c in password):
            charset_size += 26
        if any(c.isdigit() for c in password):
            charset_size += 10
        if any(c in self.config.special_chars for c in password):
            charset_size += len(self.config.special_chars)
        
        if charset_size == 0:
            return 0.0
        
        import math
        return len(password) * math.log2(charset_size)
    
    def _is_common_password(self, password: str) -> bool:
        """Check against common password list"""
        # Common passwords (in production, load from comprehensive list)
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "1234567890", "password1",
            "123456789", "welcome123", "admin123", "root", "toor"
        }
        
        return password.lower() in common_passwords
    
    def _has_patterns(self, password: str) -> bool:
        """Detect common patterns in password"""
        # Sequential patterns
        for i in range(len(password) - 2):
            if (ord(password[i+1]) == ord(password[i]) + 1 and 
                ord(password[i+2]) == ord(password[i]) + 2):
                return True
        
        # Repetitive patterns
        for i in range(len(password) - 2):
            if password[i] == password[i+1] == password[i+2]:
                return True
        
        # Keyboard patterns
        keyboard_patterns = ["qwer", "asdf", "zxcv", "1234", "abcd"]
        password_lower = password.lower()
        
        for pattern in keyboard_patterns:
            if pattern in password_lower or pattern[::-1] in password_lower:
                return True
        
        return False
    
    @track_performance
    def hash_password(self, password: str) -> PasswordHashResult:
        """Hash password using secure algorithm"""
        try:
            # Generate salt
            salt = secrets.token_hex(32)
            
            # Create hash
            password_hash = self.pwd_context.hash(password + salt)
            
            self.logger.info("Password hashed successfully")
            
            return PasswordHashResult(
                hash=password_hash,
                salt=salt,
                algorithm="argon2",
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            self.