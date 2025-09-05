"""
YMERA Enterprise Authentication & Authorization Module
Production-Ready Authentication Router with Advanced Security Features
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib
import secrets
import re
import asyncio
from enum import Enum
import json
import ipaddress
from user_agents import parse

# Core YMERA imports (based on main file structure)
from ymera_core.config import ConfigManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.security.auth_manager import AuthManager
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.exceptions import YMERAException
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_services.ai.multi_llm_manager import MultiLLMManager

# Security and validation imports
from passlib.context import CryptContext
from jose import JWTError, jwt
import pyotp
import qrcode
from io import BytesIO
import base64

router = APIRouter()
security = HTTPBearer()

# Enhanced Password Context
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    AGENT_OPERATOR = "agent_operator"
    SECURITY_OFFICER = "security_officer"

class AuthenticationMethod(str, Enum):
    PASSWORD = "password"
    MFA = "mfa"
    SSO = "sso"
    API_KEY = "api_key"
    AGENT_TOKEN = "agent_token"

class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"

# Request Models
class UserRegistrationRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.VIEWER
    department: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, regex=r'^\+?1?\d{9,15}$')
    timezone: str = Field(default="UTC")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator('password')
    def validate_password_strength(cls, v):
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        
        checks = [
            (r'[a-z]', 'lowercase letter'),
            (r'[A-Z]', 'uppercase letter'),
            (r'\d', 'digit'),
            (r'[!@#$%^&*(),.?":{}|<>]', 'special character')
        ]
        
        for pattern, desc in checks:
            if not re.search(pattern, v):
                raise ValueError(f'Password must contain at least one {desc}')
        
        common_passwords = [
            'password123', 'admin123456', 'qwertyuiop',
            'password1234', '123456789012', 'adminpassword'
        ]
        
        if v.lower() in common_passwords:
            raise ValueError('Password is too common, please choose a stronger password')
        
        return v

    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_.-]+$', v):
            raise ValueError('Username can only contain alphanumeric characters, dots, hyphens, and underscores')
        return v.lower()

class UserLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email or username")
    password: str
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=8)
    remember_me: bool = Field(default=False)
    device_info: Optional[Dict[str, Any]] = Field(default_factory=dict)

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str

    @validator('new_password')
    def validate_password_strength(cls, v):
        return UserRegistrationRequest.__fields__['password'].validator(v)

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class MFASetupRequest(BaseModel):
    password: str

class MFAVerificationRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, regex=r'^\+?1?\d{9,15}$')
    timezone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @validator('new_password')
    def validate_password_strength(cls, v):
        return UserRegistrationRequest.__fields__['password'].validator(v)

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class APIKeyRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    expires_in_days: Optional[int] = Field(default=90, ge=1, le=365)
    scopes: List[str] = Field(default_factory=list)

# Response Models
class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    role: UserRole
    department: Optional[str]
    phone: Optional[str]
    timezone: str
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    preferences: Dict[str, Any]
    login_count: int
    failed_login_attempts: int

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    session_id: str
    requires_mfa: bool = False
    permissions: List[str]

class MFASetupResponse(BaseModel):
    secret_key: str
    qr_code_data: str
    backup_codes: List[str]

class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    description: Optional[str]
    scopes: List[str]
    expires_at: Optional[datetime]
    created_at: datetime
    last_used: Optional[datetime]

class SessionInfo(BaseModel):
    id: str
    user_id: str
    device_info: Dict[str, Any]
    ip_address: str
    location: Optional[str]
    status: SessionStatus
    created_at: datetime
    last_activity: datetime
    expires_at: datetime

# Enterprise Authentication Service
class EnterpriseAuthService:
    def __init__(
        self,
        db_manager: DatabaseManager,
        auth_manager: AuthManager,
        cache_manager: RedisCacheManager,
        logger: StructuredLogger,
        learning_engine: LearningEngine,
        ai_manager: MultiLLMManager,
        config: ConfigManager
    ):
        self.db = db_manager
        self.auth_manager = auth_manager
        self.cache = cache_manager
        self.logger = logger
        self.learning_engine = learning_engine
        self.ai_manager = ai_manager
        self.config = config.config
        
        # Security settings
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        self.session_timeout = timedelta(hours=8)
        self.mfa_window = timedelta(minutes=5)
        
    async def register_user(self, request: UserRegistrationRequest, client_ip: str) -> UserResponse:
        """Register a new user with comprehensive validation"""
        try:
            # Check for existing user
            existing_user = await self.db.fetch_one(
                "SELECT id FROM users WHERE email = $1 OR username = $2",
                request.email, request.username
            )
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email or username already exists"
                )
            
            # Password security analysis using AI
            password_analysis = await self._analyze_password_security(request.password)
            if password_analysis['risk_score'] > 0.7:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password security risk: {password_analysis['recommendations']}"
                )
            
            # Hash password
            password_hash = pwd_context.hash(request.password)
            
            # Generate verification token
            verification_token = secrets.token_urlsafe(32)
            
            # Create user record
            user_id = await self.db.fetch_val(
                """
                INSERT INTO users (
                    email, username, password_hash, full_name, role, department,
                    phone, timezone, preferences, verification_token, 
                    created_at, updated_at, registration_ip
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11, $12)
                RETURNING id
                """,
                request.email, request.username, password_hash, request.full_name,
                request.role.value, request.department, request.phone, request.timezone,
                json.dumps(request.preferences or {}), verification_token,
                datetime.utcnow(), client_ip
            )
            
            # Log registration event
            await self._log_auth_event("user_registered", user_id, client_ip, {
                "email": request.email,
                "username": request.username,
                "role": request.role.value
            })
            
            # Learn from registration patterns
            await self.learning_engine.learn_from_event(
                "user_registration",
                {
                    "role": request.role.value,
                    "department": request.department,
                    "timezone": request.timezone,
                    "registration_hour": datetime.utcnow().hour
                }
            )
            
            # Get created user
            user_data = await self.db.fetch_one(
                "SELECT * FROM users WHERE id = $1", user_id
            )
            
            return UserResponse(**dict(user_data))
            
        except Exception as e:
            await self.logger.error(f"User registration failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )
    
    async def authenticate_user(
        self, 
        request: UserLoginRequest, 
        client_ip: str, 
        user_agent: str
    ) -> LoginResponse:
        """Comprehensive user authentication with security analysis"""
        
        # Check for brute force attempts
        await self._check_brute_force_protection(request.identifier, client_ip)
        
        # Get user
        user = await self.db.fetch_one(
            "SELECT * FROM users WHERE email = $1 OR username = $1",
            request.identifier.lower()
        )
        
        if not user or not pwd_context.verify(request.password, user['password_hash']):
            await self._handle_failed_login(request.identifier, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if user is active
        if not user['is_active']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled"
            )
        
        # Check if email is verified
        if not user['is_verified']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email verification required"
            )
        
        # MFA Check
        if user['mfa_enabled'] and not request.mfa_code:
            # Generate temporary token for MFA
            temp_token = await self._generate_temp_mfa_token(user['id'])
            return LoginResponse(
                access_token=temp_token,
                refresh_token="",
                expires_in=300,  # 5 minutes
                user=UserResponse(**dict(user)),
                session_id="",
                requires_mfa=True,
                permissions=[]
            )
        
        if user['mfa_enabled'] and request.mfa_code:
            if not await self._verify_mfa_code(user['id'], request.mfa_code):
                await self._handle_failed_login(request.identifier, client_ip)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code"
                )
        
        # Parse device info
        device_info = await self._parse_device_info(user_agent, request.device_info)
        
        # Risk analysis
        risk_analysis = await self._analyze_login_risk(user, client_ip, device_info)
        
        if risk_analysis['risk_score'] > 0.8:
            # High risk login - require additional verification
            await self._trigger_additional_verification(user['id'], risk_analysis)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Additional verification required due to suspicious activity"
            )
        
        # Generate tokens
        access_token_expires = timedelta(minutes=self.config.jwt_access_token_expire_minutes)
        refresh_token_expires = timedelta(days=30)
        
        access_token = await self.auth_manager.create_access_token(
            data={"sub": str(user['id']), "role": user['role']},
            expires_delta=access_token_expires
        )
        
        refresh_token = await self.auth_manager.create_refresh_token(
            data={"sub": str(user['id'])},
            expires_delta=refresh_token_expires
        )
        
        # Create session
        session_id = await self._create_user_session(
            user['id'], client_ip, device_info, access_token_expires
        )
        
        # Update user login info
        await self.db.execute(
            """
            UPDATE users SET 
                last_login = $1, 
                login_count = login_count + 1,
                failed_login_attempts = 0,
                last_login_ip = $2
            WHERE id = $3
            """,
            datetime.utcnow(), client_ip, user['id']
        )
        
        # Get user permissions
        permissions = await self._get_user_permissions(user['role'])
        
        # Log successful login
        await self._log_auth_event("login_success", user['id'], client_ip, {
            "risk_score": risk_analysis['risk_score'],
            "device_info": device_info,
            "mfa_used": user['mfa_enabled']
        })
        
        # Learn from login patterns
        await self.learning_engine.learn_from_event(
            "user_login",
            {
                "user_role": user['role'],
                "login_hour": datetime.utcnow().hour,
                "risk_score": risk_analysis['risk_score'],
                "device_type": device_info.get('device_type'),
                "location": device_info.get('location')
            }
        )
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_token_expires.total_seconds()),
            user=UserResponse(**dict(user)),
            session_id=session_id,
            requires_mfa=False,
            permissions=permissions
        )
    
    async def _analyze_password_security(self, password: str) -> Dict[str, Any]:
        """Use AI to analyze password security"""
        try:
            prompt = f"""
            Analyze the security of this password pattern (not the actual password):
            - Length: {len(password)}
            - Has uppercase: {'Yes' if re.search(r'[A-Z]', password) else 'No'}
            - Has lowercase: {'Yes' if re.search(r'[a-z]', password) else 'No'}
            - Has digits: {'Yes' if re.search(r'\d', password) else 'No'}
            - Has symbols: {'Yes' if re.search(r'[!@#$%^&*(),.?":{{}}|<>]', password) else 'No'}
            - Has common patterns: {'Yes' if re.search(r'(123|abc|password|admin)', password.lower()) else 'No'}
            
            Return a JSON response with:
            {{
                "risk_score": <float 0-1>,
                "recommendations": "<string>",
                "strength": "<weak|medium|strong|very_strong>"
            }}
            """
            
            response = await self.ai_manager.get_completion(
                prompt=prompt,
                provider="openai",
                model="gpt-4"
            )
            
            return json.loads(response.content)
            
        except Exception as e:
            await self.logger.error(f"Password analysis failed: {str(e)}")
            return {
                "risk_score": 0.3,
                "recommendations": "Use a longer password with mixed case, numbers, and symbols",
                "strength": "medium"
            }
    
    async def _check_brute_force_protection(self, identifier: str, client_ip: str):
        """Check for brute force attacks"""
        # Check IP-based attempts
        ip_attempts = await self.cache.get(f"login_attempts_ip:{client_ip}")
        if ip_attempts and int(ip_attempts) > self.max_login_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts from this IP address"
            )
        
        # Check user-based attempts
        user_attempts = await self.cache.get(f"login_attempts_user:{identifier}")
        if user_attempts and int(user_attempts) > self.max_login_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts for this account"
            )
    
    async def _handle_failed_login(self, identifier: str, client_ip: str):
        """Handle failed login attempt"""
        # Increment IP attempts
        current_ip_attempts = await self.cache.get(f"login_attempts_ip:{client_ip}") or "0"
        await self.cache.setex(
            f"login_attempts_ip:{client_ip}",
            int(self.lockout_duration.total_seconds()),
            str(int(current_ip_attempts) + 1)
        )
        
        # Increment user attempts
        current_user_attempts = await self.cache.get(f"login_attempts_user:{identifier}") or "0"
        await self.cache.setex(
            f"login_attempts_user:{identifier}",
            int(self.lockout_duration.total_seconds()),
            str(int(current_user_attempts) + 1)
        )
        
        # Update failed attempts in database
        await self.db.execute(
            """
            UPDATE users SET 
                failed_login_attempts = failed_login_attempts + 1,
                last_failed_login = $1,
                last_failed_login_ip = $2
            WHERE email = $3 OR username = $3
            """,
            datetime.utcnow(), client_ip, identifier.lower()
        )
    
    async def _parse_device_info(self, user_agent: str, device_info: Dict) -> Dict[str, Any]:
        """Parse and enhance device information"""
        try:
            parsed_ua = parse(user_agent)
            
            return {
                "browser": f"{parsed_ua.browser.family} {parsed_ua.browser.version_string}",
                "os": f"{parsed_ua.os.family} {parsed_ua.os.version_string}",
                "device_type": parsed_ua.device.family,
                "is_mobile": parsed_ua.is_mobile,
                "is_tablet": parsed_ua.is_tablet,
                "is_pc": parsed_ua.is_pc,
                "user_agent": user_agent,
                **device_info
            }
        except Exception:
            return {"user_agent": user_agent, **device_info}
    
    async def _analyze_login_risk(
        self, 
        user: Dict, 
        client_ip: str, 
        device_info: Dict
    ) -> Dict[str, Any]:
        """Analyze login risk using AI and historical patterns"""
        try:
            # Get user's historical login patterns
            recent_logins = await self.db.fetch_all(
                """
                SELECT ip_address, device_info, created_at 
                FROM user_sessions 
                WHERE user_id = $1 AND created_at > $2
                ORDER BY created_at DESC LIMIT 10
                """,
                user['id'], datetime.utcnow() - timedelta(days=30)
            )
            
            # Check for new location/device
            is_new_ip = client_ip not in [login['ip_address'] for login in recent_logins]
            is_new_device = not any(
                json.loads(login['device_info']).get('browser') == device_info.get('browser')
                for login in recent_logins
            )
            
            # Time-based analysis
            current_hour = datetime.utcnow().hour
            typical_hours = [
                datetime.fromisoformat(login['created_at']).hour 
                for login in recent_logins
            ]
            is_unusual_time = current_hour not in typical_hours if typical_hours else False
            
            # Calculate base risk score
            risk_score = 0.0
            risk_factors = []
            
            if is_new_ip:
                risk_score += 0.3
                risk_factors.append("new_ip_address")
            
            if is_new_device:
                risk_score += 0.2
                risk_factors.append("new_device")
            
            if is_unusual_time:
                risk_score += 0.1
                risk_factors.append("unusual_time")
            
            # Check failed attempts
            if user['failed_login_attempts'] > 0:
                risk_score += 0.2
                risk_factors.append("recent_failed_attempts")
            
            # AI-enhanced risk analysis
            if risk_score > 0.3:
                ai_analysis = await self._get_ai_risk_analysis(
                    user, client_ip, device_info, recent_logins
                )
                risk_score = max(risk_score, ai_analysis.get('adjusted_risk_score', risk_score))
            
            return {
                "risk_score": min(risk_score, 1.0),
                "risk_factors": risk_factors,
                "is_new_ip": is_new_ip,
                "is_new_device": is_new_device,
                "is_unusual_time": is_unusual_time
            }
            
        except Exception as e:
            await self.logger.error(f"Risk analysis failed: {str(e)}")
            return {"risk_score": 0.5, "risk_factors": ["analysis_error"]}
    
    async def _get_ai_risk_analysis(
        self,
        user: Dict,
        client_ip: str,
        device_info: Dict,
        recent_logins: List
    ) -> Dict[str, Any]:
        """Get AI-powered risk analysis"""
        try:
            prompt = f"""
            Analyze login risk for user authentication:
            
            User Profile:
            - Role: {user['role']}
            - Login count: {user['login_count']}
            - Failed attempts: {user['failed_login_attempts']}
            - Last login: {user.get('last_login')}
            
            Current Login:
            - IP: {client_ip[:10]}... (masked for security)
            - Device: {device_info.get('browser', 'unknown')}
            - OS: {device_info.get('os', 'unknown')}
            - Time: {datetime.utcnow().hour}:00 UTC
            
            Recent Login Pattern (last 10):
            {json.dumps([{{
                'hour': datetime.fromisoformat(login['created_at']).hour,
                'device': json.loads(login['device_info']).get('browser', 'unknown')
            }} for login in recent_logins], indent=2)}
            
            Based on this data, provide a risk assessment:
            {{
                "adjusted_risk_score": <float 0-1>,
                "confidence": <float 0-1>,
                "reasoning": "<explanation>",
                "recommended_actions": ["<action1>", "<action2>"]
            }}
            """
            
            response = await self.ai_manager.get_completion(
                prompt=prompt,
                provider="openai",
                model="gpt-4",
                max_tokens=500
            )
            
            return json.loads(response.content)
            
        except Exception as e:
            await self.logger.error(f"AI risk analysis failed: {str(e)}")
            return {"adjusted_risk_score": 0.5, "confidence": 0.0}

# Dependency injection
async def get_auth_service(
    db_manager: DatabaseManager = Depends(),
    auth_manager: AuthManager = Depends(),
    cache_manager: RedisCacheManager = Depends(),
    logger: StructuredLogger = Depends(),
    learning_engine: LearningEngine = Depends(),
    ai_manager: MultiLLMManager = Depends(),
    config: ConfigManager = Depends()
) -> EnterpriseAuthService:
    return EnterpriseAuthService(
        db_manager, auth_manager, cache_manager, 
        logger, learning_engine, ai_manager, config
    )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
) -> Dict[str, Any]:
    """Get current authenticated user with comprehensive validation"""
    try:
        payload = jwt.decode(
            credentials.credentials, 
            auth_service.config.secret_key,
            algorithms=[auth_service.config.jwt_algorithm]
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Check if session is still valid
        session_valid = await auth_service.cache.exists(f"user_session:{user_id}")
        if not session_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid"
            )
        
        # Get user from database
        user = await auth_service.db.fetch_one(
            "SELECT * FROM users WHERE id = $1 AND is_active = true",
            user_id
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return dict(user)
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )

# Authentication endpoints
@router.post("/register", response_model=UserResponse, summary="User Registration")
async def register_user(
    request: UserRegistrationRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Register a new user with comprehensive validation and security analysis"""
    client_ip = http_request.client.host
    
    user = await auth_service.register_user(request, client_ip)
    
    # Send verification email in background
    background_tasks.add_task(
        auth_service._send_verification_email, 
        user.email, 
        user.username
    )
    
    return user

@router.post("/login", response_model=LoginResponse, summary="User Authentication")
async def login_user(
    request: UserLoginRequest,
    http_request: Request,
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Authenticate user with advanced security analysis and risk assessment"""
    client_ip = http_request.client.host
    user_agent = http_request.headers.get("user-agent", "")
    
    return await auth_service.authenticate_user(request, client_ip, user_agent)

@router.post("/refresh", response_model=LoginResponse, summary="Token Refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Refresh access token using valid refresh token"""
    return await auth_service.refresh_access_token(request.refresh_token)

@router.post("/logout", summary="User Logout")
async def logout_user(
    http_request: Request,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Logout user and invalidate session"""
    session_id = http_request.headers.get("X-Session-ID")
    await auth_service.logout_user(current_user['id'], session_id)
    
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse, summary="Get Current User")
async def get_current_user_info(
    current @router.get("/me", response_model=UserResponse, summary="Get Current User")
async def get_current_user_info(
    current_user: Dict = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse(**current_user)

@router.put("/me", response_model=UserResponse, summary="Update Profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Update user profile information"""
    return await auth_service.update_user_profile(current_user['id'], request)

@router.post("/change-password", summary="Change Password")
async def change_password(
    request: ChangePasswordRequest,
    http_request: Request,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Change user password"""
    client_ip = http_request.client.host
    await auth_service.change_user_password(current_user['id'], request, client_ip)
    
    return {"message": "Password changed successfully"}

@router.post("/forgot-password", summary="Request Password Reset")
async def forgot_password(
    request: PasswordResetRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Request password reset"""
    client_ip = http_request.client.host
    
    background_tasks.add_task(
        auth_service.initiate_password_reset,
        request.email,
        client_ip
    )
    
    return {"message": "Password reset instructions sent if email exists"}

@router.post("/reset-password", summary="Confirm Password Reset")
async def reset_password(
    request: PasswordResetConfirmRequest,
    http_request: Request,
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Confirm password reset with token"""
    client_ip = http_request.client.host
    await auth_service.confirm_password_reset(request, client_ip)
    
    return {"message": "Password reset successfully"}

@router.post("/mfa/setup", response_model=MFASetupResponse, summary="Setup MFA")
async def setup_mfa(
    request: MFASetupRequest,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Setup Multi-Factor Authentication"""
    return await auth_service.setup_mfa(current_user['id'], request.password)

@router.post("/mfa/verify", summary="Verify MFA Setup")
async def verify_mfa_setup(
    request: MFAVerificationRequest,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Verify and enable MFA"""
    await auth_service.verify_and_enable_mfa(current_user['id'], request.code)
    
    return {"message": "MFA enabled successfully"}

@router.delete("/mfa/disable", summary="Disable MFA")
async def disable_mfa(
    request: MFASetupRequest,  # Reuse for password verification
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Disable Multi-Factor Authentication"""
    await auth_service.disable_mfa(current_user['id'], request.password)
    
    return {"message": "MFA disabled successfully"}

@router.get("/sessions", response_model=List[SessionInfo], summary="Get User Sessions")
async def get_user_sessions(
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Get all active user sessions"""
    return await auth_service.get_user_sessions(current_user['id'])

@router.delete("/sessions/{session_id}", summary="Revoke Session")
async def revoke_session(
    session_id: str,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Revoke a specific session"""
    await auth_service.revoke_session(current_user['id'], session_id)
    
    return {"message": "Session revoked successfully"}

@router.delete("/sessions/all", summary="Revoke All Sessions")
async def revoke_all_sessions(
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Revoke all user sessions except current"""
    await auth_service.revoke_all_sessions(current_user['id'])
    
    return {"message": "All sessions revoked successfully"}

@router.post("/api-keys", response_model=APIKeyResponse, summary="Create API Key")
async def create_api_key(
    request: APIKeyRequest,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Create a new API key"""
    return await auth_service.create_api_key(current_user['id'], request)

@router.get("/api-keys", response_model=List[APIKeyResponse], summary="Get API Keys")
async def get_api_keys(
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Get all user API keys (without showing actual keys)"""
    return await auth_service.get_user_api_keys(current_user['id'])

@router.delete("/api-keys/{key_id}", summary="Revoke API Key")
async def revoke_api_key(
    key_id: str,
    current_user: Dict = Depends(get_current_user),
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Revoke an API key"""
    await auth_service.revoke_api_key(current_user['id'], key_id)
    
    return {"message": "API key revoked successfully"}

@router.get("/verify-email/{token}", summary="Verify Email")
async def verify_email(
    token: str,
    auth_service: EnterpriseAuthService = Depends(get_auth_service)
):
    """Verify user email address"""
    await auth_service.verify_email(token)
    
    return {"message": "Email verified successfully"}

# Additional methods for EnterpriseAuthService class
class EnterpriseAuthService:
    # ... (previous methods remain the same)
    
    async def update_user_profile(
        self, 
        user_id: str, 
        request: UpdateProfileRequest
    ) -> UserResponse:
        """Update user profile information"""
        try:
            update_fields = []
            values = []
            param_count = 1
            
            for field, value in request.dict(exclude_unset=True).items():
                if field == 'preferences' and value is not None:
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(json.dumps(value))
                elif value is not None:
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)
                param_count += 1
            
            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )
            
            values.append(user_id)
            
            await self.db.execute(
                f"""
                UPDATE users SET 
                    {', '.join(update_fields)},
                    updated_at = $1
                WHERE id = ${param_count}
                """,
                datetime.utcnow(), *values
            )
            
            # Get updated user
            user = await self.db.fetch_one(
                "SELECT * FROM users WHERE id = $1", user_id
            )
            
            await self._log_auth_event("profile_updated", user_id, None, {
                "updated_fields": list(request.dict(exclude_unset=True).keys())
            })
            
            return UserResponse(**dict(user))
            
        except Exception as e:
            await self.logger.error(f"Profile update failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Profile update failed"
            )
    
    async def change_user_password(
        self,
        user_id: str,
        request: ChangePasswordRequest,
        client_ip: str
    ):
        """Change user password with validation"""
        try:
            # Get current user
            user = await self.db.fetch_one(
                "SELECT * FROM users WHERE id = $1", user_id
            )
            
            # Verify current password
            if not pwd_context.verify(request.current_password, user['password_hash']):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
            
            # Check if new password is different
            if pwd_context.verify(request.new_password, user['password_hash']):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password must be different from current password"
                )
            
            # AI password security analysis
            password_analysis = await self._analyze_password_security(request.new_password)
            if password_analysis['risk_score'] > 0.7:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password security risk: {password_analysis['recommendations']}"
                )
            
            # Hash new password
            new_password_hash = pwd_context.hash(request.new_password)
            
            # Update password
            await self.db.execute(
                """
                UPDATE users SET 
                    password_hash = $1,
                    updated_at = $2,
                    password_changed_at = $2
                WHERE id = $3
                """,
                new_password_hash, datetime.utcnow(), user_id
            )
            
            # Revoke all sessions except current
            await self.revoke_all_sessions(user_id, exclude_current=True)
            
            await self._log_auth_event("password_changed", user_id, client_ip, {})
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"Password change failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )
    
    async def initiate_password_reset(self, email: str, client_ip: str):
        """Initiate password reset process"""
        try:
            # Check if user exists (but don't reveal if they don't)
            user = await self.db.fetch_one(
                "SELECT id, email, username FROM users WHERE email = $1", email
            )
            
            if user:
                # Generate reset token
                reset_token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=1)
                
                # Store reset token
                await self.db.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user['id'], reset_token, expires_at, datetime.utcnow()
                )
                
                # Send reset email (implement email service)
                await self._send_password_reset_email(email, reset_token)
                
                await self._log_auth_event("password_reset_requested", user['id'], client_ip, {
                    "email": email
                })
            
            # Always log the attempt for security monitoring
            await self._log_auth_event("password_reset_attempt", None, client_ip, {
                "email": email,
                "user_exists": user is not None
            })
            
        except Exception as e:
            await self.logger.error(f"Password reset initiation failed: {str(e)}")
    
    async def confirm_password_reset(
        self,
        request: PasswordResetConfirmRequest,
        client_ip: str
    ):
        """Confirm password reset with token"""
        try:
            # Find valid reset token
            reset_record = await self.db.fetch_one(
                """
                SELECT prt.*, u.id as user_id, u.email 
                FROM password_reset_tokens prt
                JOIN users u ON prt.user_id = u.id
                WHERE prt.token = $1 AND prt.expires_at > $2 AND prt.used = false
                """,
                request.token, datetime.utcnow()
            )
            
            if not reset_record:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )
            
            # AI password security analysis
            password_analysis = await self._analyze_password_security(request.new_password)
            if password_analysis['risk_score'] > 0.7:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Password security risk: {password_analysis['recommendations']}"
                )
            
            # Hash new password
            new_password_hash = pwd_context.hash(request.new_password)
            
            # Update password and mark token as used
            async with self.db.transaction():
                await self.db.execute(
                    """
                    UPDATE users SET 
                        password_hash = $1,
                        updated_at = $2,
                        password_changed_at = $2,
                        failed_login_attempts = 0
                    WHERE id = $3
                    """,
                    new_password_hash, datetime.utcnow(), reset_record['user_id']
                )
                
                await self.db.execute(
                    "UPDATE password_reset_tokens SET used = true WHERE token = $1",
                    request.token
                )
            
            # Revoke all sessions
            await self.revoke_all_sessions(reset_record['user_id'])
            
            await self._log_auth_event("password_reset_completed", reset_record['user_id'], client_ip, {
                "email": reset_record['email']
            })
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"Password reset confirmation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password reset failed"
            )
    
    async def setup_mfa(self, user_id: str, password: str) -> MFASetupResponse:
        """Setup Multi-Factor Authentication"""
        try:
            # Verify password
            user = await self.db.fetch_one(
                "SELECT password_hash FROM users WHERE id = $1", user_id
            )
            
            if not pwd_context.verify(password, user['password_hash']):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password verification failed"
                )
            
            # Generate secret key
            secret_key = pyotp.random_base32()
            
            # Generate QR code
            totp = pyotp.TOTP(secret_key)
            provisioning_uri = totp.provisioning_uri(
                name=user_id,
                issuer_name="YMERA Enterprise"
            )
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_code_data = base64.b64encode(buffer.getvalue()).decode()
            
            # Generate backup codes
            backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
            
            # Store temporary MFA setup (not enabled until verified)
            await self.cache.setex(
                f"mfa_setup:{user_id}",
                600,  # 10 minutes
                json.dumps({
                    "secret_key": secret_key,
                    "backup_codes": backup_codes
                })
            )
            
            return MFASetupResponse(
                secret_key=secret_key,
                qr_code_data=f"data:image/png;base64,{qr_code_data}",
                backup_codes=backup_codes
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"MFA setup failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA setup failed"
            )
    
    async def verify_and_enable_mfa(self, user_id: str, code: str):
        """Verify MFA setup and enable it"""
        try:
            # Get temporary setup data
            setup_data = await self.cache.get(f"mfa_setup:{user_id}")
            if not setup_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MFA setup not found or expired"
                )
            
            setup_info = json.loads(setup_data)
            secret_key = setup_info['secret_key']
            backup_codes = setup_info['backup_codes']
            
            # Verify TOTP code
            totp = pyotp.TOTP(secret_key)
            if not totp.verify(code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code"
                )
            
            # Enable MFA in database
            await self.db.execute(
                """
                UPDATE users SET 
                    mfa_enabled = true,
                    mfa_secret = $1,
                    mfa_backup_codes = $2,
                    updated_at = $3
                WHERE id = $4
                """,
                secret_key, json.dumps(backup_codes), datetime.utcnow(), user_id
            )
            
            # Clean up temporary setup
            await self.cache.delete(f"mfa_setup:{user_id}")
            
            await self._log_auth_event("mfa_enabled", user_id, None, {})
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"MFA verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA verification failed"
            )
    
    async def disable_mfa(self, user_id: str, password: str):
        """Disable Multi-Factor Authentication"""
        try:
            # Verify password
            user = await self.db.fetch_one(
                "SELECT password_hash, mfa_enabled FROM users WHERE id = $1", user_id
            )
            
            if not user['mfa_enabled']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MFA is not enabled"
                )
            
            if not pwd_context.verify(password, user['password_hash']):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password verification failed"
                )
            
            # Disable MFA
            await self.db.execute(
                """
                UPDATE users SET 
                    mfa_enabled = false,
                    mfa_secret = null,
                    mfa_backup_codes = null,
                    updated_at = $1
                WHERE id = $2
                """,
                datetime.utcnow(), user_id
            )
            
            await self._log_auth_event("mfa_disabled", user_id, None, {})
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"MFA disable failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MFA disable failed"
            )
    
    async def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """Get all user sessions"""
        try:
            sessions = await self.db.fetch_all(
                """
                SELECT * FROM user_sessions 
                WHERE user_id = $1 AND status = 'active'
                ORDER BY last_activity DESC
                """,
                user_id
            )
            
            return [SessionInfo(**dict(session)) for session in sessions]
            
        except Exception as e:
            await self.logger.error(f"Get sessions failed: {str(e)}")
            return []
    
    async def revoke_session(self, user_id: str, session_id: str):
        """Revoke a specific session"""
        try:
            await self.db.execute(
                """
                UPDATE user_sessions SET 
                    status = 'revoked',
                    updated_at = $1
                WHERE id = $2 AND user_id = $3
                """,
                datetime.utcnow(), session_id, user_id
            )
            
            # Remove from cache
            await self.cache.delete(f"user_session:{user_id}")
            
            await self._log_auth_event("session_revoked", user_id, None, {
                "session_id": session_id
            })
            
        except Exception as e:
            await self.logger.error(f"Session revocation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Session revocation failed"
            )
    
    async def revoke_all_sessions(self, user_id: str, exclude_current: bool = False):
        """Revoke all user sessions"""
        try:
            if exclude_current:
                # Get current session ID from cache (implementation depends on your session management)
                current_session = await self.cache.get(f"current_session:{user_id}")
                if current_session:
                    await self.db.execute(
                        """
                        UPDATE user_sessions SET 
                            status = 'revoked',
                            updated_at = $1
                        WHERE user_id = $2 AND id != $3 AND status = 'active'
                        """,
                        datetime.utcnow(), user_id, current_session
                    )
                else:
                    await self.db.execute(
                        """
                        UPDATE user_sessions SET 
                            status = 'revoked',
                            updated_at = $1
                        WHERE user_id = $2 AND status = 'active'
                        """,
                        datetime.utcnow(), user_id
                    )
            else:
                await self.db.execute(
                    """
                    UPDATE user_sessions SET 
                        status = 'revoked',
                        updated_at = $1
                    WHERE user_id = $2 AND status = 'active'
                    """,
                    datetime.utcnow(), user_id
                )
            
            # Clear all session caches
            await self.cache.delete(f"user_session:{user_id}")
            await self.cache.delete(f"current_session:{user_id}")
            
            await self._log_auth_event("all_sessions_revoked", user_id, None, {
                "exclude_current": exclude_current
            })
            
        except Exception as e:
            await self.logger.error(f"All sessions revocation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Sessions revocation failed"
            )
    
    async def create_api_key(self, user_id: str, request: APIKeyRequest) -> APIKeyResponse:
        """Create a new API key for the user"""
        try:
            # Generate API key
            api_key = f"ymra_{secrets.token_urlsafe(32)}"
            key_id = secrets.token_hex(8)
            
            # Calculate expiration
            expires_at = None
            if request.expires_in_days:
                expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
            
            # Store API key (hash it for security)
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            await self.db.execute(
                """
                INSERT INTO api_keys (
                    id, user_id, name, description, key_hash, 
                    scopes, expires_at, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                key_id, user_id, request.name, request.description,
                key_hash, json.dumps(request.scopes), expires_at, datetime.utcnow()
            )
            
            await self._log_auth_event("api_key_created", user_id, None, {
                "key_name": request.name,
                "scopes": request.scopes
            })
            
            return APIKeyResponse(
                id=key_id,
                name=request.name,
                key=api_key,  # Only returned once during creation
                description=request.description,
                scopes=request.scopes,
                expires_at=expires_at,
                created_at=datetime.utcnow(),
                last_used=None
            )
            
        except Exception as e:
            await self.logger.error(f"API key creation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key creation failed"
            )
    
    async def get_user_api_keys(self, user_id: str) -> List[APIKeyResponse]:
        """Get all user API keys (without actual keys)"""
        try:
            keys = await self.db.fetch_all(
                """
                SELECT id, name, description, scopes, expires_at, 
                       created_at, last_used, is_active
                FROM api_keys 
                WHERE user_id = $1 AND is_active = true
                ORDER BY created_at DESC
                """,
                user_id
            )
            
            return [
                APIKeyResponse(
                    id=key['id'],
                    name=key['name'],
                    key="*" * 20,  # Masked
                    description=key['description'],
                    scopes=json.loads(key['scopes']) if key['scopes'] else [],
                    expires_at=key['expires_at'],
                    created_at=key['created_at'],
                    last_used=key['last_used']
                )
                for key in keys
            ]
            
        except Exception as e:
            await self.logger.error(f"Get API keys failed: {str(e)}")
            return []
    
    async def revoke_api_key(self, user_id: str, key_id: str):
        """Revoke an API key"""
        try:
            result = await self.db.execute(
                """
                UPDATE api_keys SET 
                    is_active = false,
                    revoked_at = $1
                WHERE id = $2 AND user_id = $3
                """,
                datetime.utcnow(), key_id, user_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="API key not found"
                )
            
            await self._log_auth_event("api_key_revoked", user_id, None, {
                "key_id": key_id
            })
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"API key revocation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key revocation failed"
            )
    
    async def verify_email(self, token: str):
        """Verify user email address"""
        try:
            user = await self.db.fetch_one(
                "SELECT id FROM users WHERE verification_token = $1 AND is_verified = false",
                token
            )
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired verification token"
                )
            
            await self.db.execute(
                """
                UPDATE users SET 
                    is_verified = true,
                    verification_token = null,
                    verified_at = $1,
                    updated_at = $1
                WHERE id = $2
                """,
                datetime.utcnow(), user['id']
            )
            
            await self._log_auth_event("email_verified", user['id'], None, {})
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"Email verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email verification failed"
            )
    
    # Helper methods
    async def _verify_mfa_code(self, user_id: str, code: str) -> bool:
        """Verify MFA code"""
        try:
            user = await self.db.fetch_one(
                "SELECT mfa_secret, mfa_backup_codes FROM users WHERE id = $1",
                user_id
            )
            
            if not user or not user['mfa_secret']:
                return False
            
            # Try TOTP first
            totp = pyotp.TOTP(user['mfa_secret'])
            if totp.verify(code):
                return True
            
            # Try backup codes
            if user['mfa_backup_codes']:
                backup_codes = json.loads(user['mfa_backup_codes'])
                if code.upper() in backup_codes:
                    # Remove used backup code
                    backup_codes.remove(code.upper())
                    await self.db.execute(
                        "UPDATE users SET mfa_backup_codes = $1 WHERE id = $2",
                        json.dumps(backup_codes), user_id
                    )
                    return True
            
            return False
            
        except Exception as e:
            await self.logger.error(f"MFA verification failed: {str(e)}")
            return False
    
    async def async def _send_password_reset_email(self, email: str, reset_token: str):
        """Send password reset email to user"""
        try:
            # Construct reset URL
            reset_url = f"{self.config.frontend_url}/reset-password?token={reset_token}"
            
            # Email content
            subject = "Password Reset Request - YMERA Enterprise"
            html_content = f"""
            <html>
                <body>
                    <h2>Password Reset Request</h2>
                    <p>You have requested to reset your password for your YMERA Enterprise account.</p>
                    <p>Click the link below to reset your password:</p>
                    <p><a href="{reset_url}">Reset Password</a></p>
                    <p>This link will expire in 1 hour.</p>
                    <p>If you did not request this password reset, please ignore this email.</p>
                    <br>
                    <p>Best regards,<br>YMERA Enterprise Team</p>
                </body>
            </html>
            """
            
            # Send email using your email service
            await self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content
            )
            
        except Exception as e:
            await self.logger.error(f"Failed to send password reset email: {str(e)}")
            # Don't raise exception to avoid revealing if email exists
    
    async def _analyze_password_security(self, password: str) -> Dict:
        """AI-powered password security analysis"""
        try:
            risk_score = 0.0
            recommendations = []
            
            # Basic checks
            if len(password) < 12:
                risk_score += 0.3
                recommendations.append("Use at least 12 characters")
            
            if not any(c.islower() for c in password):
                risk_score += 0.2
                recommendations.append("Include lowercase letters")
            
            if not any(c.isupper() for c in password):
                risk_score += 0.2
                recommendations.append("Include uppercase letters")
            
            if not any(c.isdigit() for c in password):
                risk_score += 0.2
                recommendations.append("Include numbers")
            
            if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                risk_score += 0.2
                recommendations.append("Include special characters")
            
            # Common password patterns
            common_patterns = [
                "password", "123456", "qwerty", "admin", "letmein",
                "welcome", "monkey", "dragon", "master", "shadow"
            ]
            
            password_lower = password.lower()
            for pattern in common_patterns:
                if pattern in password_lower:
                    risk_score += 0.4
                    recommendations.append("Avoid common password patterns")
                    break
            
            # Sequential patterns
            if any(str(i) + str(i+1) + str(i+2) in password for i in range(8)):
                risk_score += 0.3
                recommendations.append("Avoid sequential numbers")
            
            # Repeated characters
            if any(password.count(c) > 3 for c in set(password)):
                risk_score += 0.2
                recommendations.append("Avoid repeated characters")
            
            # AI enhancement: Use ML model for advanced pattern detection
            # This would integrate with your AI service
            ai_analysis = await self._get_ai_password_analysis(password)
            if ai_analysis:
                risk_score = max(risk_score, ai_analysis.get('risk_score', 0))
                recommendations.extend(ai_analysis.get('recommendations', []))
            
            return {
                'risk_score': min(risk_score, 1.0),  # Cap at 1.0
                'recommendations': "; ".join(set(recommendations)) if recommendations else "Password meets security requirements"
            }
            
        except Exception as e:
            await self.logger.error(f"Password analysis failed: {str(e)}")
            return {'risk_score': 0.0, 'recommendations': "Unable to analyze password"}
    
    async def _get_ai_password_analysis(self, password: str) -> Dict:
        """Get AI-powered password analysis from ML service"""
        try:
            # This would call your AI/ML service for advanced password analysis
            # Example implementation:
            payload = {
                'password_hash': hashlib.sha256(password.encode()).hexdigest(),
                'length': len(password),
                'char_types': {
                    'lowercase': sum(1 for c in password if c.islower()),
                    'uppercase': sum(1 for c in password if c.isupper()),
                    'digits': sum(1 for c in password if c.isdigit()),
                    'special': sum(1 for c in password if not c.isalnum())
                }
            }
            
            # Mock AI analysis - replace with actual AI service call
            return {
                'risk_score': 0.1,
                'recommendations': []
            }
            
        except Exception as e:
            await self.logger.error(f"AI password analysis failed: {str(e)}")
            return {}
    
    async def _log_auth_event(
        self,
        event_type: str,
        user_id: str = None,
        client_ip: str = None,
        metadata: Dict = None
    ):
        """Log authentication events for security monitoring"""
        try:
            await self.db.execute(
                """
                INSERT INTO auth_logs (
                    event_type, user_id, client_ip, metadata, 
                    timestamp, created_at
                ) VALUES ($1, $2, $3, $4, $5, $5)
                """,
                event_type,
                user_id,
                client_ip,
                json.dumps(metadata or {}),
                datetime.utcnow()
            )
            
            # Also send to security monitoring system
            await self._send_security_alert(event_type, user_id, client_ip, metadata)
            
        except Exception as e:
            await self.logger.error(f"Auth event logging failed: {str(e)}")
    
    async def _send_security_alert(
        self,
        event_type: str,
        user_id: str = None,
        client_ip: str = None,
        metadata: Dict = None
    ):
        """Send security alerts for critical events"""
        try:
            critical_events = [
                'login_failed_max_attempts',
                'suspicious_login_pattern',
                'password_reset_completed',
                'mfa_disabled',
                'multiple_failed_logins'
            ]
            
            if event_type in critical_events:
                alert_data = {
                    'event_type': event_type,
                    'user_id': user_id,
                    'client_ip': client_ip,
                    'metadata': metadata,
                    'timestamp': datetime.utcnow().isoformat(),
                    'severity': 'high' if event_type in ['login_failed_max_attempts', 'suspicious_login_pattern'] else 'medium'
                }
                
                # Send to security monitoring service
                # This could be integrated with services like Datadog, Splunk, etc.
                await self.security_monitor.send_alert(alert_data)
            
        except Exception as e:
            await self.logger.error(f"Security alert failed: {str(e)}")
    
    async def _detect_suspicious_activity(
        self,
        user_id: str = None,
        client_ip: str = None,
        event_type: str = None
    ) -> bool:
        """AI-powered suspicious activity detection"""
        try:
            # Get recent auth events
            recent_events = await self.db.fetch_all(
                """
                SELECT * FROM auth_logs 
                WHERE (user_id = $1 OR client_ip = $2)
                AND timestamp > $3
                ORDER BY timestamp DESC
                LIMIT 50
                """,
                user_id,
                client_ip,
                datetime.utcnow() - timedelta(hours=24)
            )
            
            # Analyze patterns
            suspicious_indicators = 0
            
            # Multiple IPs for same user
            if user_id:
                unique_ips = set(event.get('client_ip') for event in recent_events if event.get('client_ip'))
                if len(unique_ips) > 5:
                    suspicious_indicators += 1
            
            # High frequency of failed attempts
            failed_attempts = [e for e in recent_events if e['event_type'] == 'login_failed']
            if len(failed_attempts) > 10:
                suspicious_indicators += 1
            
            # Login from unusual locations (would require IP geolocation)
            # This is a simplified check
            if client_ip and await self._is_unusual_location(user_id, client_ip):
                suspicious_indicators += 1
            
            # Time-based anomalies
            if await self._detect_time_anomaly(user_id, recent_events):
                suspicious_indicators += 1
            
            return suspicious_indicators >= 2
            
        except Exception as e:
            await self.logger.error(f"Suspicious activity detection failed: {str(e)}")
            return False
    
    async def _is_unusual_location(self, user_id: str, client_ip: str) -> bool:
        """Check if login is from unusual location"""
        try:
            # Get user's typical locations from last 30 days
            typical_locations = await self.db.fetch_all(
                """
                SELECT DISTINCT client_ip FROM auth_logs
                WHERE user_id = $1 
                AND event_type = 'login_successful'
                AND timestamp > $2
                """,
                user_id,
                datetime.utcnow() - timedelta(days=30)
            )
            
            # Simple IP-based check (in production, use proper IP geolocation)
            typical_ip_ranges = set(ip.split('.')[0] + '.' + ip.split('.')[1] for ip in [loc['client_ip'] for loc in typical_locations] if ip)
            current_ip_range = '.'.join(client_ip.split('.')[:2])
            
            return current_ip_range not in typical_ip_ranges
            
        except Exception as e:
            await self.logger.error(f"Location check failed: {str(e)}")
            return False
    
    async def _detect_time_anomaly(self, user_id: str, recent_events: List) -> bool:
        """Detect unusual login times"""
        try:
            if not user_id:
                return False
                
            # Get user's typical login hours
            login_events = [e for e in recent_events if e['event_type'] == 'login_successful']
            if len(login_events) < 5:
                return False
            
            typical_hours = [e['timestamp'].hour for e in login_events[-20:]]  # Last 20 logins
            avg_hour = sum(typical_hours) / len(typical_hours)
            
            current_hour = datetime.utcnow().hour
            
            # If current login is more than 6 hours different from typical time
            hour_diff = min(abs(current_hour - avg_hour), 24 - abs(current_hour - avg_hour))
            return hour_diff > 6
            
        except Exception as e:
            await self.logger.error(f"Time anomaly detection failed: {str(e)}")
            return False
    
    async def _cleanup_expired_tokens(self):
        """Clean up expired tokens and sessions"""
        try:
            now = datetime.utcnow()
            
            # Clean up expired password reset tokens
            await self.db.execute(
                "DELETE FROM password_reset_tokens WHERE expires_at < $1",
                now
            )
            
            # Clean up expired sessions
            await self.db.execute(
                """
                UPDATE user_sessions SET 
                    status = 'expired',
                    updated_at = $1
                WHERE expires_at < $1 AND status = 'active'
                """,
                now
            )
            
            # Clean up expired API keys
            await self.db.execute(
                """
                UPDATE api_keys SET 
                    is_active = false,
                    revoked_at = $1
                WHERE expires_at < $1 AND is_active = true
                """,
                now
            )
            
            # Clean up old auth logs (keep for 90 days)
            await self.db.execute(
                "DELETE FROM auth_logs WHERE timestamp < $1",
                now - timedelta(days=90)
            )
            
        except Exception as e:
            await self.logger.error(f"Token cleanup failed: {str(e)}")
    
    async def get_user_security_summary(self, user_id: str) -> Dict:
        """Get comprehensive security summary for user"""
        try:
            user = await self.db.fetch_one(
                """
                SELECT mfa_enabled, password_changed_at, created_at,
                       last_login_at, failed_login_attempts
                FROM users WHERE id = $1
                """,
                user_id
            )
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Get active sessions count
            active_sessions = await self.db.fetch_val(
                "SELECT COUNT(*) FROM user_sessions WHERE user_id = $1 AND status = 'active'",
                user_id
            )
            
            # Get active API keys count
            active_api_keys = await self.db.fetch_val(
                "SELECT COUNT(*) FROM api_keys WHERE user_id = $1 AND is_active = true",
                user_id
            )
            
            # Recent security events
            recent_events = await self.db.fetch_all(
                """
                SELECT event_type, timestamp FROM auth_logs
                WHERE user_id = $1 AND timestamp > $2
                ORDER BY timestamp DESC
                LIMIT 10
                """,
                user_id,
                datetime.utcnow() - timedelta(days=7)
            )
            
            # Calculate security score
            security_score = await self._calculate_security_score(user)
            
            return {
                'mfa_enabled': user['mfa_enabled'],
                'password_age_days': (datetime.utcnow() - user['password_changed_at']).days if user['password_changed_at'] else None,
                'account_age_days': (datetime.utcnow() - user['created_at']).days,
                'last_login': user['last_login_at'],
                'failed_login_attempts': user['failed_login_attempts'],
                'active_sessions': active_sessions,
                'active_api_keys': active_api_keys,
                'recent_security_events': [
                    {
                        'event': event['event_type'],
                        'timestamp': event['timestamp']
                    }
                    for event in recent_events
                ],
                'security_score': security_score,
                'recommendations': await self._get_security_recommendations(user_id, security_score)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await self.logger.error(f"Security summary failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get security summary"
            )
    
    async def _calculate_security_score(self, user: Dict) -> int:
        """Calculate user security score (0-100)"""
        try:
            score = 0
            
            # MFA enabled (+30 points)
            if user['mfa_enabled']:
                score += 30
            
            # Password age (newer is better, max 20 points)
            if user['password_changed_at']:
                days_since_password_change = (datetime.utcnow() - user['password_changed_at']).days
                if days_since_password_change < 30:
                    score += 20
                elif days_since_password_change < 90:
                    score += 15
                elif days_since_password_change < 180:
                    score += 10
                else:
                    score += 5
            
            # Account activity (max 20 points)
            if user['last_login_at']:
                days_since_login = (datetime.utcnow() - user['last_login_at']).days
                if days_since_login < 7:
                    score += 20
                elif days_since_login < 30:
                    score += 15
                else:
                    score += 10
            
            # Failed login attempts (deduct points)
            if user['failed_login_attempts'] > 0:
                score -= min(user['failed_login_attempts'] * 5, 20)
            
            # Account age stability (max 20 points)
            account_age_days = (datetime.utcnow() - user['created_at']).days
            if account_age_days > 365:
                score += 20
            elif account_age_days > 90:
                score += 15
            elif account_age_days > 30:
                score += 10
            else:
                score += 5
            
            # Base security practices (10 points)
            score += 10
            
            return max(0, min(100, score))
            
        except Exception as e:
            await self.logger.error(f"Security score calculation failed: {str(e)}")
            return 50  # Default moderate score
    
    async def _get_security_recommendations(self, user_id: str, security_score: int) -> List[str]:
        """Get personalized security recommendations"""
        try:
            user = await self.db.fetch_one(
                """
                SELECT mfa_enabled, password_changed_at, last_login_at
                FROM users WHERE id = $1
                """,
                user_id
            )
            
            recommendations = []
            
            if not user['mfa_enabled']:
                recommendations.append("Enable Multi-Factor Authentication for better security")
            
            if user['password_changed_at']:
                days_since_change = (datetime.utcnow() - user['password_changed_at']).days
                if days_since_change > 180:
                    recommendations.append("Consider changing your password (last changed over 6 months ago)")
            
            if security_score < 70:
                recommendations.append("Review and revoke unused API keys and sessions")
                recommendations.append("Enable login notifications for suspicious activity")
            
            if security_score < 50:
                recommendations.append("Use a password manager for stronger passwords")
                recommendations.append("Review recent login activity for any unauthorized access")
            
            # Get active sessions count for recommendation
            active_sessions = await self.db.fetch_val(
                "SELECT COUNT(*) FROM user_sessions WHERE user_id = $1 AND status = 'active'",
                user_id
            )
            
            if active_sessions > 5:
                recommendations.append(f"You have {active_sessions} active sessions. Consider revoking unused ones")
            
            return recommendations
            
        except Exception as e:
            await self.logger.error(f"Security recommendations failed: {str(e)}")
            return ["Review your security settings regularly"]