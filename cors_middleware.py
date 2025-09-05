"""
YMERA Enterprise - CORS Middleware
Production-Ready Cross-Origin Resource Sharing Handler - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Set, Pattern
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Third-party imports (alphabetical)
import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp

# Local imports (alphabetical)
from config.settings import get_settings
from monitoring.performance_tracker import track_performance
from utils.security_utils import is_safe_origin, validate_origin_pattern

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.cors_middleware")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Default CORS settings
DEFAULT_ALLOW_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]
DEFAULT_ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
DEFAULT_ALLOW_HEADERS = [
    "Accept",
    "Accept-Language",
    "Content-Language",
    "Content-Type",
    "Authorization",
    "X-Requested-With",
    "X-CSRF-Token",
    "X-API-Key"
]
DEFAULT_EXPOSE_HEADERS = [
    "X-Request-ID",
    "X-Rate-Limit-Remaining",
    "X-Rate-Limit-Reset"
]

# Security constants
MAX_AGE_SECONDS = 86400  # 24 hours
PREFLIGHT_MAX_AGE = 7200  # 2 hours

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class CORSConfig:
    """Configuration dataclass for CORS settings"""
    allow_origins: List[str] = field(default_factory=lambda: DEFAULT_ALLOW_ORIGINS.copy())
    allow_origin_regex: Optional[str] = None
    allow_methods: List[str] = field(default_factory=lambda: DEFAULT_ALLOW_METHODS.copy())
    allow_headers: List[str] = field(default_factory=lambda: DEFAULT_ALLOW_HEADERS.copy())
    allow_credentials: bool = True
    expose_headers: List[str] = field(default_factory=lambda: DEFAULT_EXPOSE_HEADERS.copy())
    max_age: int = PREFLIGHT_MAX_AGE
    enable_development_mode: bool = False
    strict_origin_validation: bool = True
    log_cors_requests: bool = True

@dataclass
class CORSRequestInfo:
    """Information about CORS request for logging and monitoring"""
    origin: Optional[str]
    method: str
    path: str
    is_preflight: bool
    is_cors: bool
    allowed: bool
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class CORSValidator:
    """Production-ready CORS validation logic"""
    
    def __init__(self, config: CORSConfig):
        self.config = config
        self.logger = logger.bind(component="cors_validator")
        self._origin_regex: Optional[Pattern] = None
        self._initialize_regex()
    
    def _initialize_regex(self) -> None:
        """Initialize origin regex pattern if configured"""
        if self.config.allow_origin_regex:
            try:
                self._origin_regex = re.compile(self.config.allow_origin_regex)
                self.logger.info("CORS origin regex compiled", pattern=self.config.allow_origin_regex)
            except re.error as e:
                self.logger.error("Invalid origin regex pattern", error=str(e))
                raise ValueError(f"Invalid origin regex pattern: {e}")
    
    def validate_origin(self, origin: Optional[str]) -> tuple[bool, str]:
        """
        Validate if origin is allowed for CORS requests.
        
        Args:
            origin: The origin header value from the request
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        if not origin:
            if self.config.strict_origin_validation:
                return False, "Origin header missing in strict mode"
            return True, "No origin validation required"
        
        # Development mode allows all origins
        if self.config.enable_development_mode:
            self.logger.debug("Origin allowed in development mode", origin=origin)
            return True, "Development mode enabled"
        
        # Validate origin format
        if not self._is_valid_origin_format(origin):
            return False, "Invalid origin format"
        
        # Check security concerns
        if not is_safe_origin(origin):
            return False, "Origin flagged as potentially unsafe"
        
        # Check against allowed origins list
        if origin in self.config.allow_origins:
            return True, "Origin in allowed list"
        
        # Check wildcard
        if "*" in self.config.allow_origins:
            if self.config.allow_credentials:
                return False, "Wildcard not allowed with credentials"
            return True, "Wildcard origin allowed"
        
        # Check regex pattern
        if self._origin_regex and self._origin_regex.match(origin):
            return True, "Origin matches regex pattern"
        
        return False, "Origin not in allowed list"
    
    def _is_valid_origin_format(self, origin: str) -> bool:
        """Validate origin format according to RFC 6454"""
        try:
            parsed = urlparse(origin)
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False
            # Scheme must be http or https
            if parsed.scheme not in ('http', 'https'):
                return False
            # Should not have path, query, or fragment
            if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                return False
            return True
        except Exception:
            return False
    
    def validate_method(self, method: str) -> tuple[bool, str]:
        """Validate if method is allowed"""
        if method.upper() in [m.upper() for m in self.config.allow_methods]:
            return True, "Method allowed"
        return False, f"Method {method} not in allowed methods"
    
    def validate_headers(self, headers: List[str]) -> tuple[bool, str]:
        """Validate if requested headers are allowed"""
        allowed_headers_lower = [h.lower() for h in self.config.allow_headers]
        
        for header in headers:
            if header.lower() not in allowed_headers_lower:
                return False, f"Header {header} not allowed"
        
        return True, "All headers allowed"

class ProductionCORSMiddleware(BaseHTTPMiddleware):
    """Production-ready CORS middleware with comprehensive security features"""
    
    def __init__(self, app: ASGIApp, config: Optional[CORSConfig] = None):
        super().__init__(app)
        self.config = config or self._load_default_config()
        self.validator = CORSValidator(self.config)
        self.logger = logger.bind(component="cors_middleware")
        self._request_counter = 0
        self._cors_stats = {
            "allowed": 0,
            "blocked": 0,
            "preflight": 0,
            "errors": 0
        }
        
        self.logger.info("CORS middleware initialized", config=self._sanitize_config_for_log())
    
    def _load_default_config(self) -> CORSConfig:
        """Load CORS configuration from settings"""
        return CORSConfig(
            allow_origins=getattr(settings, 'CORS_ALLOW_ORIGINS', DEFAULT_ALLOW_ORIGINS),
            allow_origin_regex=getattr(settings, 'CORS_ALLOW_ORIGIN_REGEX', None),
            allow_methods=getattr(settings, 'CORS_ALLOW_METHODS', DEFAULT_ALLOW_METHODS),
            allow_headers=getattr(settings, 'CORS_ALLOW_HEADERS', DEFAULT_ALLOW_HEADERS),
            allow_credentials=getattr(settings, 'CORS_ALLOW_CREDENTIALS', True),
            expose_headers=getattr(settings, 'CORS_EXPOSE_HEADERS', DEFAULT_EXPOSE_HEADERS),
            max_age=getattr(settings, 'CORS_MAX_AGE', PREFLIGHT_MAX_AGE),
            enable_development_mode=getattr(settings, 'CORS_DEVELOPMENT_MODE', False),
            strict_origin_validation=getattr(settings, 'CORS_STRICT_VALIDATION', True),
            log_cors_requests=getattr(settings, 'CORS_LOG_REQUESTS', True)
        )
    
    def _sanitize_config_for_log(self) -> Dict[str, Any]:
        """Sanitize config for safe logging"""
        return {
            "allow_origins_count": len(self.config.allow_origins),
            "allow_methods": self.config.allow_methods,
            "allow_credentials": self.config.allow_credentials,
            "development_mode": self.config.enable_development_mode,
            "strict_validation": self.config.strict_origin_validation
        }
    
    @track_performance
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Main CORS middleware dispatch logic.
        
        Handles both preflight OPTIONS requests and actual CORS requests
        with comprehensive validation and security checks.
        """
        self._request_counter += 1
        request_id = f"cors-{self._request_counter}"
        
        try:
            # Extract CORS information
            cors_info = self._extract_cors_info(request)
            
            # Log request if enabled
            if self.config.log_cors_requests:
                self.logger.debug(
                    "CORS request received",
                    request_id=request_id,
                    origin=cors_info.origin,
                    method=cors_info.method,
                    path=cors_info.path,
                    is_preflight=cors_info.is_preflight
                )
            
            # Handle preflight requests
            if cors_info.is_preflight:
                return await self._handle_preflight_request(request, cors_info, request_id)
            
            # Handle actual CORS requests
            if cors_info.is_cors:
                # Validate origin for CORS requests
                origin_allowed, reason = self.validator.validate_origin(cors_info.origin)
                cors_info.allowed = origin_allowed
                cors_info.reason = reason
                
                if not origin_allowed:
                    self._cors_stats["blocked"] += 1
                    self.logger.warning(
                        "CORS request blocked",
                        request_id=request_id,
                        origin=cors_info.origin,
                        reason=reason
                    )
                    return self._create_cors_error_response(reason)
                
                self._cors_stats["allowed"] += 1
            
            # Process the actual request
            response = await call_next(request)
            
            # Add CORS headers to response
            if cors_info.is_cors and cors_info.allowed:
                self._add_cors_headers(response, cors_info.origin)
            
            return response
            
        except Exception as e:
            self._cors_stats["errors"] += 1
            self.logger.error(
                "CORS middleware error",
                request_id=request_id,
                error=str(e),
                path=request.url.path,
                method=request.method
            )
            return self._create_cors_error_response("CORS processing error")
    
    def _extract_cors_info(self, request: Request) -> CORSRequestInfo:
        """Extract CORS-related information from request"""
        origin = request.headers.get("origin")
        method = request.method
        path = str(request.url.path)
        
        # Check if this is a preflight request
        is_preflight = (
            method == "OPTIONS" and
            origin is not None and
            request.headers.get("access-control-request-method") is not None
        )
        
        # Check if this is a CORS request
        is_cors = origin is not None
        
        return CORSRequestInfo(
            origin=origin,
            method=method,
            path=path,
            is_preflight=is_preflight,
            is_cors=is_cors,
            allowed=False
        )
    
    async def _handle_preflight_request(
        self, 
        request: Request, 
        cors_info: CORSRequestInfo,
        request_id: str
    ) -> Response:
        """Handle CORS preflight OPTIONS requests"""
        self._cors_stats["preflight"] += 1
        
        # Validate origin
        origin_allowed, origin_reason = self.validator.validate_origin(cors_info.origin)
        if not origin_allowed:
            self.logger.warning(
                "Preflight request blocked - invalid origin",
                request_id=request_id,
                origin=cors_info.origin,
                reason=origin_reason
            )
            return self._create_cors_error_response(f"Origin not allowed: {origin_reason}")
        
        # Validate requested method
        requested_method = request.headers.get("access-control-request-method")
        if requested_method:
            method_allowed, method_reason = self.validator.validate_method(requested_method)
            if not method_allowed:
                self.logger.warning(
                    "Preflight request blocked - invalid method",
                    request_id=request_id,
                    method=requested_method,
                    reason=method_reason
                )
                return self._create_cors_error_response(f"Method not allowed: {method_reason}")
        
        # Validate requested headers
        requested_headers_str = request.headers.get("access-control-request-headers", "")
        if requested_headers_str:
            requested_headers = [h.strip() for h in requested_headers_str.split(",")]
            headers_allowed, headers_reason = self.validator.validate_headers(requested_headers)
            if not headers_allowed:
                self.logger.warning(
                    "Preflight request blocked - invalid headers",
                    request_id=request_id,
                    headers=requested_headers,
                    reason=headers_reason
                )
                return self._create_cors_error_response(f"Headers not allowed: {headers_reason}")
        
        # Create successful preflight response
        response = Response(status_code=200)
        self._add_preflight_headers(response, cors_info.origin, requested_method, requested_headers_str)
        
        self.logger.debug(
            "Preflight request approved",
            request_id=request_id,
            origin=cors_info.origin,
            method=requested_method
        )
        
        return response
    
    def _add_cors_headers(self, response: Response, origin: Optional[str]) -> None:
        """Add CORS headers to actual request response"""
        if origin and origin != "*":
            response.headers["Access-Control-Allow-Origin"] = origin
        elif "*" in self.config.allow_origins and not self.config.allow_credentials:
            response.headers["Access-Control-Allow-Origin"] = "*"
        
        if self.config.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        if self.config.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.config.expose_headers)
        
        # Add Vary header for origin-based responses
        if origin:
            vary_header = response.headers.get("Vary", "")
            if "Origin" not in vary_header:
                response.headers["Vary"] = f"{vary_header}, Origin".strip(", ")
    
    def _add_preflight_headers(
        self, 
        response: Response, 
        origin: Optional[str],
        requested_method: Optional[str],
        requested_headers: Optional[str]
    ) -> None:
        """Add headers for preflight response"""
        # Basic CORS headers
        self._add_cors_headers(response, origin)
        
        # Preflight-specific headers
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.config.allow_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(self.config.allow_headers)
        response.headers["Access-Control-Max-Age"] = str(self.config.max_age)
    
    def _create_cors_error_response(self, message: str) -> JSONResponse:
        """Create standardized CORS error response"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "CORS_ERROR",
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            },
            headers={
                "Content-Type": "application/json"
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get CORS middleware statistics"""
        return {
            "total_requests": self._request_counter,
            "cors_stats": self._cors_stats.copy(),
            "config_summary": self._sanitize_config_for_log()
        }

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_cors_middleware(
    allow_origins: Optional[List[str]] = None,
    allow_origin_regex: Optional[str] = None,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
    allow_credentials: bool = True,
    expose_headers: Optional[List[str]] = None,
    max_age: int = PREFLIGHT_MAX_AGE,
    development_mode: bool = False
) -> ProductionCORSMiddleware:
    """
    Factory function to create CORS middleware with custom configuration.
    
    Args:
        allow_origins: List of allowed origins
        allow_origin_regex: Regex pattern for allowed origins
        allow_methods: List of allowed HTTP methods
        allow_headers: List of allowed headers
        allow_credentials: Whether to allow credentials
        expose_headers: List of headers to expose to client
        max_age: Preflight cache duration in seconds
        development_mode: Enable development mode (allows all origins)
        
    Returns:
        Configured CORS middleware instance
    """
    config = CORSConfig(
        allow_origins=allow_origins or DEFAULT_ALLOW_ORIGINS,
        allow_origin_regex=allow_origin_regex,
        allow_methods=allow_methods or DEFAULT_ALLOW_METHODS,
        allow_headers=allow_headers or DEFAULT_ALLOW_HEADERS,
        allow_credentials=allow_credentials,
        expose_headers=expose_headers or DEFAULT_EXPOSE_HEADERS,
        max_age=max_age,
        enable_development_mode=development_mode
    )
    
    return lambda app: ProductionCORSMiddleware(app, config)

async def health_check() -> Dict[str, Any]:
    """CORS middleware health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "cors_middleware",
        "version": "4.0"
    }

def validate_cors_configuration(config: Dict[str, Any]) -> bool:
    """Validate CORS configuration parameters"""
    required_fields = ["allow_origins", "allow_methods", "allow_headers"]
    
    if not all(field in config for field in required_fields):
        return False
    
    # Validate origins format
    for origin in config.get("allow_origins", []):
        if origin != "*" and not validate_origin_pattern(origin):
            return False
    
    return True

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

def initialize_cors_middleware(app: ASGIApp) -> ProductionCORSMiddleware:
    """Initialize CORS middleware for production use"""
    config = CORSConfig(
        allow_origins=getattr(settings, 'CORS_ALLOW_ORIGINS', DEFAULT_ALLOW_ORIGINS),
        allow_origin_regex=getattr(settings, 'CORS_ALLOW_ORIGIN_REGEX', None),
        allow_methods=getattr(settings, 'CORS_ALLOW_METHODS', DEFAULT_ALLOW_METHODS),
        allow_headers=getattr(settings, 'CORS_ALLOW_HEADERS', DEFAULT_ALLOW_HEADERS),
        allow_credentials=getattr(settings, 'CORS_ALLOW_CREDENTIALS', True),
        expose_headers=getattr(settings, 'CORS_EXPOSE_HEADERS', DEFAULT_EXPOSE_HEADERS),
        max_age=getattr(settings, 'CORS_MAX_AGE', PREFLIGHT_MAX_AGE),
        enable_development_mode=getattr(settings, 'CORS_DEVELOPMENT_MODE', False),
        strict_origin_validation=getattr(settings, 'CORS_STRICT_VALIDATION', True),
        log_cors_requests=getattr(settings, 'CORS_LOG_REQUESTS', True)
    )
    
    middleware = ProductionCORSMiddleware(app, config)
    logger.info("CORS middleware initialized for production")
    
    return middleware

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionCORSMiddleware",
    "CORSConfig",
    "CORSValidator",
    "CORSRequestInfo",
    "create_cors_middleware",
    "initialize_cors_middleware",
    "health_check",
    "validate_cors_configuration"
]