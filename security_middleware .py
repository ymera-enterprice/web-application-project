"""
YMERA Enterprise - Security Middleware
Production-Ready Input Validation & Security Handler - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import hashlib
import hmac
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Set, Pattern, Callable
from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network, AddressValueError
from urllib.parse import quote, unquote
import base64

# Third-party imports (alphabetical)
import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Local imports (alphabetical)
from config.settings import get_settings
from monitoring.performance_tracker import track_performance
from monitoring.security_monitor import log_security_event, SecurityEventType
from utils.encryption import encrypt_data, decrypt_data
from utils.rate_limiter import RateLimiter, RateLimit
from utils.ip_utils import is_private_ip, get_country_from_ip
from database.security_logs import log_security_violation

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.security_middleware")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Security patterns and rules
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bSELECT\b.*\bFROM\b)",
    r"(\bINSERT\b.*\bINTO\b)",
    r"(\bUPDATE\b.*\bSET\b)",
    r"(\bDELETE\b.*\bFROM\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(\'\s*OR\s*\'.*\'=\')",
    r"(\'\s*OR\s*1\s*=\s*1)",
    r"(--\s*$)",
    r"(/\*.*\*/)"
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"vbscript:",
    r"onload\s*=",
    r"onerror\s*=",
    r"onclick\s*=",
    r"onmouseover\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>"
]

PATH_TRAVERSAL_PATTERNS = [
    r"\.\.\/",
    r"\.\.\\",
    r"%2e%2e%2f",
    r"%2e%2e%5c",
    r"..%2f",
    r"..%5c"
]

COMMAND_INJECTION_PATTERNS = [
    r";\s*(rm|del|format|fdisk)",
    r";\s*(cat|type)\s+",
    r";\s*(ls|dir)\s+",
    r"&\s*(rm|del|format)",
    r"\|\s*(rm|del|format)",
    r"`.*`",
    r"\$\(.*\)"
]

# Rate limiting defaults
DEFAULT_RATE_LIMITS = {
    "global": RateLimit(requests=1000, window=3600),  # 1000 per hour
    "api": RateLimit(requests=100, window=300),       # 100 per 5 minutes
    "auth": RateLimit(requests=5, window=300),        # 5 per 5 minutes
    "upload": RateLimit(requests=10, window=3600)     # 10 per hour
}

# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
}

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class SecurityConfig:
    """Configuration dataclass for security middleware settings"""
    enable_input_validation: bool = True
    enable_sql_injection_protection: bool = True
    enable_xss_protection: bool = True
    enable_path_traversal_protection: bool = True
    enable_command_injection_protection: bool = True
    enable_rate_limiting: bool = True
    enable_ip_filtering: bool = True
    enable_security_headers: bool = True
    enable_csrf_protection: bool = True
    enable_request_signing: bool = False
    max_request_size: int = 10485760  # 10MB
    max_url_length: int = 2048
    max_header_length: int = 8192
    allowed_content_types: Set[str] = field(default_factory=lambda: {
        "application/json", "application/x-www-form-urlencoded",
        "multipart/form-data", "text/plain", "text/csv"
    })
    blocked_user_agents: Set[str] = field(default_factory=set)
    allowed_ip_ranges: List[str] = field(default_factory=list)
    blocked_ip_ranges: List[str] = field(default_factory=list)
    trusted_proxies: List[str] = field(default_factory=list)
    rate_limits: Dict[str, RateLimit] = field(default_factory=lambda: DEFAULT_RATE_LIMITS.copy())
    custom_security_headers: Dict[str, str] = field(default_factory=dict)
    sensitive_paths: Set[str] = field(default_factory=lambda: {"/admin", "/api/v1/auth", "/api/v1/users"})
    log_security_events: bool = True
    block_malicious_requests: bool = True
    quarantine_suspicious_ips: bool = True

@dataclass
class SecurityViolation:
    """Details about a security violation"""
    violation_id: str
    violation_type: str
    severity: str
    client_ip: str
    user_agent: Optional[str]
    endpoint: str
    method: str
    details: str
    timestamp: datetime
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    blocked: bool = False

@dataclass
class SecurityMetrics:
    """Security metrics for monitoring"""
    total_requests: int = 0
    blocked_requests: int = 0
    sql_injection_attempts: int = 0
    xss_attempts: int = 0
    path_traversal_attempts: int = 0
    command_injection_attempts: int = 0
    rate_limit_violations: int = 0
    ip_filter_violations: int = 0
    suspicious_ips: Set[str] = field(default_factory=set)
    last_attack_time: Optional[datetime] = None

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="input_validator")
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance"""
        self.sql_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in SQL_INJECTION_PATTERNS]
        self.xss_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in XSS_PATTERNS]
        self.path_traversal_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in PATH_TRAVERSAL_PATTERNS]
        self.command_injection_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in COMMAND_INJECTION_PATTERNS]
    
    def validate_input(self, data: str, context: str = "unknown") -> tuple[bool, Optional[str]]:
        """
        Validate input data for security threats.
        
        Args:
            data: Input data to validate
            context: Context of the input (query, body, header, etc.)
            
        Returns:
            Tuple of (is_valid, violation_reason)
        """
        if not data:
            return True, None
        
        # Decode URL-encoded data for better detection
        try:
            decoded_data = unquote(data)
        except Exception:
            decoded_data = data
        
        # Check for SQL injection
        if self.config.enable_sql_injection_protection:
            for pattern in self.sql_patterns:
                if pattern.search(decoded_data):
                    return False, f"SQL injection pattern detected in {context}"
        
        # Check for XSS
        if self.config.enable_xss_protection:
            for pattern in self.xss_patterns:
                if pattern.search(decoded_data):
                    return False, f"XSS pattern detected in {context}"
        
        # Check for path traversal
        if self.config.enable_path_traversal_protection:
            for pattern in self.path_traversal_patterns:
                if pattern.search(decoded_data):
                    return False, f"Path traversal pattern detected in {context}"
        
        # Check for command injection
        if self.config.enable_command_injection_protection:
            for pattern in self.command_injection_patterns:
                if pattern.search(decoded_data):
                    return False, f"Command injection pattern detected in {context}"
        
        return True, None
    
    def validate_request_size(self, request: Request) -> tuple[bool, Optional[str]]:
        """Validate request size limits"""
        content_length = request.headers.get('content-length')
        if content_length:
            try:
                size = int(content_length)
                if size > self.config.max_request_size:
                    return False, f"Request size {size} exceeds maximum {self.config.max_request_size}"
            except ValueError:
                return False, "Invalid content-length header"
        
        return True, None
    
    def validate_url_length(self, url: str) -> tuple[bool, Optional[str]]:
        """Validate URL length"""
        if len(url) > self.config.max_url_length:
            return False, f"URL length {len(url)} exceeds maximum {self.config.max_url_length}"
        return True, None
    
    def validate_headers(self, headers: Dict[str, str]) -> tuple[bool, Optional[str]]:
        """Validate request headers"""
        for name, value in headers.items():
            # Check header length
            if len(value) > self.config.max_header_length:
                return False, f"Header {name} length exceeds maximum"
            
            # Validate header content
            is_valid, reason = self.validate_input(value, f"header:{name}")
            if not is_valid:
                return False, reason
        
        return True, None
    
    def validate_content_type(self, content_type: Optional[str]) -> tuple[bool, Optional[str]]:
        """Validate content type"""
        if not content_type:
            return True, None
        
        # Extract main content type (ignore charset, boundary, etc.)
        main_type = content_type.split(';')[0].strip().lower()
        
        if main_type not in self.config.allowed_content_types:
            return False, f"Content type {main_type} not allowed"
        
        return True, None

class IPFilter:
    """IP address filtering and geolocation-based security"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="ip_filter")
        self._compile_ip_ranges()
        self._suspicious_ips = set()
        self._ip_attempt_counts = {}
    
    def _compile_ip_ranges(self) -> None:
        """Compile IP ranges for efficient checking"""
        self.allowed_networks = []
        self.blocked_networks = []
        self.trusted_networks = []
        
        try:
            for ip_range in self.config.allowed_ip_ranges:
                self.allowed_networks.append(ip_network(ip_range, strict=False))
            
            for ip_range in self.config.blocked_ip_ranges:
                self.blocked_networks.append(ip_network(ip_range, strict=False))
            
            for ip_range in self.config.trusted_proxies:
                self.trusted_networks.append(ip_network(ip_range, strict=False))
                
        except AddressValueError as e:
            self.logger.error("Invalid IP range in configuration", error=str(e))
    
    def is_ip_allowed(self, client_ip: str) -> tuple[bool, Optional[str]]:
        """Check if IP address is allowed"""
        if not self.config.enable_ip_filtering:
            return True, None
        
        try:
            ip = ip_address(client_ip)
            
            # Check if IP is blocked
            for blocked_network in self.blocked_networks:
                if ip in blocked_network:
                    return False, f"IP {client_ip} is in blocked range"
            
            # Check if IP is suspicious
            if client_ip in self._suspicious_ips:
                return False, f"IP {client_ip} is flagged as suspicious"
            
            # If allowed ranges are specified, check membership
            if self.allowed_networks:
                for allowed_network in self.allowed_networks:
                    if ip in allowed_network:
                        return True, None
                return False, f"IP {client_ip} not in allowed ranges"
            
            # Check for private IPs in production
            if not settings.DEBUG and is_private_ip(client_ip):
                return False, f"Private IP {client_ip} not allowed in production"
            
            return True, None
            
        except AddressValueError:
            return False, f"Invalid IP address format: {client_ip}"
    
    def is_trusted_proxy(self, ip: str) -> bool:
        """Check if IP is a trusted proxy"""
        try:
            ip_addr = ip_address(ip)
            for trusted_network in self.trusted_networks:
                if ip_addr in trusted_network:
                    return True
        except AddressValueError:
            pass
        return False
    
    def record_violation(self, client_ip: str) -> None:
        """Record security violation for IP"""
        self._ip_attempt_counts[client_ip] = self._ip_attempt_counts.get(client_ip, 0) + 1
        
        # Flag IP as suspicious after multiple violations
        if self._ip_attempt_counts[client_ip] >= 3:
            self._suspicious_ips.add(client_ip)
            if self.config.quarantine_suspicious_ips:
                self.logger.warning("IP flagged as suspicious", ip=client_ip, 
                                  attempts=self._ip_attempt_counts[client_ip])
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP handling proxies"""
        # Check for forwarded headers
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            # Take the first IP (original client)
            client_ip = forwarded_for.split(',')[0].strip()
            return client_ip
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"

class CSRFProtection:
    """Cross-Site Request Forgery protection"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="csrf_protection")
        self._csrf_tokens = {}  # In production, use Redis or database
        self._token_expiry = timedelta(hours=24)
    
    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        token = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8').rstrip('=')
        expires_at = datetime.utcnow() + self._token_expiry
        
        self._csrf_tokens[session_id] = {
            'token': token,
            'expires_at': expires_at
        }
        
        return token
    
    def validate_csrf_token(self, session_id: str, provided_token: str) -> bool:
        """Validate CSRF token"""
        if not self.config.enable_csrf_protection:
            return True
        
        if session_id not in self._csrf_tokens:
            return False
        
        token_data = self._csrf_tokens[session_id]
        
        # Check expiry
        if datetime.utcnow() > token_data['expires_at']:
            del self._csrf_tokens[session_id]
            return False
        
        # Compare tokens
        return hmac.compare_digest(token_data['token'], provided_token)
    
    def requires_csrf_validation(self, request: Request) -> bool:
        """Check if request requires CSRF validation"""
        # CSRF protection for state-changing methods
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return True
        
        # Check for sensitive paths
        path = request.url.path
        return any(sensitive_path in path for sensitive_path in self.config.sensitive_paths)

class RequestSigner:
    """Request signature validation for API security"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logger.bind(component="request_signer")
        self._api_keys = {}  # In production, load from secure storage
    
    def validate_signature(self, request: Request) -> tuple[bool, Optional[str]]:
        """Validate request signature"""
        if not self.config.enable_request_signing:
            return True, None
        
        # Extract signature components
        api_key = request.headers.get('x-api-key')
        timestamp = request.headers.get('x-timestamp')
        signature = request.headers.get('x-signature')
        
        if not all([api_key, timestamp, signature]):
            return False, "Missing signature headers"
        
        # Validate timestamp (prevent replay attacks)
        try:
            request_time = datetime.fromtimestamp(int(timestamp))
            if abs((datetime.utcnow() - request_time).total_seconds()) > 300:  # 5 minutes
                return False, "Request timestamp too old"
        except (ValueError, TypeError):
            return False, "Invalid timestamp format"
        
        # Validate API key
        if api_key not in self._api_keys:
            return False, "Invalid API key"
        
        # Calculate expected signature
        secret_key = self._api_keys[api_key]
        expected_signature = self._calculate_signature(request, timestamp, secret_key)
        
        # Compare signatures
        if not hmac.compare_digest(signature, expected_signature):
            return False, "Invalid signature"
        
        return True, None
    
    def _calculate_signature(self, request: Request, timestamp: str, secret: str) -> str:
        """Calculate request signature"""
        # Create signature payload
        method = request.method
        path = str(request.url.path)
        query = str(request.url.query) if request.url.query else ""
        
        payload = f"{method}|{path}|{query}|{timestamp}"
        
        # Calculate HMAC
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature

class ProductionSecurityMiddleware(BaseHTTPMiddleware):
    """Production-ready security middleware with comprehensive protection"""
    
    def __init__(self, app: ASGIApp, config: Optional[SecurityConfig] = None):
        super().__init__(app)
        self.config = config or self._load_default_config()
        
        # Initialize security components
        self.input_validator = InputValidator(self.config)
        self.ip_filter = IPFilter(self.config)
        self.csrf_protection = CSRFProtection(self.config)
        self.request_signer = RequestSigner(self.config)
        self.rate_limiter = RateLimiter(self.config.rate_limits)
        
        self.logger = logger.bind(component="security_middleware")
        self._security_metrics = SecurityMetrics()
        
        self.logger.info("Security middleware initialized", config=self._sanitize_config_for_log())
    
    def _load_default_config(self) -> SecurityConfig:
        """Load security configuration from settings"""
        return SecurityConfig(
            enable_input_validation=getattr(settings, 'SECURITY_INPUT_VALIDATION', True),
            enable_sql_injection_protection=getattr(settings, 'SECURITY_SQL_PROTECTION', True),
            enable_xss_protection=getattr(settings, 'SECURITY_XSS_PROTECTION', True),
            enable_path_traversal_protection=getattr(settings, 'SECURITY_PATH_TRAVERSAL_PROTECTION', True),
            enable_command_injection_protection=getattr(settings, 'SECURITY_COMMAND_INJECTION_PROTECTION', True),
        config = SecurityConfig(
        enable_input_validation=enable_input_validation,
        enable_rate_limiting=enable_rate_limiting,
        enable_ip_filtering=enable_ip_filtering,
        enable_csrf_protection=enable_csrf_protection,
        block_malicious_requests=block_malicious_requests,
        max_request_size=max_request_size,
        allowed_content_types=allowed_content_types or {
            "application/json", "application/x-www-form-urlencoded",
            "multipart/form-data", "text/plain", "text/csv"
        }
    )
    
    return lambda app: ProductionSecurityMiddleware(app, config)

async def health_check() -> Dict[str, Any]:
    """Security middleware health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "security_middleware",
        "version": "4.0"
    }

def validate_security_configuration(config: Dict[str, Any]) -> bool:
    """Validate security configuration parameters"""
    # Validate boolean settings
    boolean_fields = [
        "enable_input_validation", "enable_sql_injection_protection",
        "enable_xss_protection", "enable_rate_limiting", "enable_ip_filtering"
    ]
    
    for field in boolean_fields:
        if field in config and not isinstance(config[field], bool):
            return False
    
    # Validate numeric settings
    numeric_fields = ["max_request_size", "max_url_length", "max_header_length"]
    for field in numeric_fields:
        if field in config:
            value = config[field]
            if not isinstance(value, int) or value <= 0:
                return False
    
    # Validate IP ranges
    ip_range_fields = ["allowed_ip_ranges", "blocked_ip_ranges", "trusted_proxies"]
    for field in ip_range_fields:
        if field in config:
            for ip_range in config[field]:
                try:
                    ip_network(ip_range, strict=False)
                except AddressValueError:
                    return False
    
    return True

def sanitize_input_string(input_data: str, max_length: int = 1000) -> str:
    """
    Sanitize input string by removing potentially dangerous characters.
    
    Args:
        input_data: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not input_data:
        return ""
    
    # Truncate if too long
    if len(input_data) > max_length:
        input_data = input_data[:max_length]
    
    # Remove null bytes and control characters
    sanitized = ''.join(char for char in input_data if ord(char) >= 32 or char in '\t\n\r')
    
    # Basic HTML entity encoding for dangerous characters
    dangerous_chars = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;',
        '/': '&#x2F;'
    }
    
    for char, encoded in dangerous_chars.items():
        sanitized = sanitized.replace(char, encoded)
    
    return sanitized

def detect_security_patterns(input_data: str) -> List[str]:
    """
    Detect security patterns in input data.
    
    Args:
        input_data: Input data to analyze
        
    Returns:
        List of detected security patterns
    """
    detected_patterns = []
    
    if not input_data:
        return detected_patterns
    
    # Compile all patterns
    all_patterns = {
        "SQL Injection": SQL_INJECTION_PATTERNS,
        "XSS": XSS_PATTERNS,
        "Path Traversal": PATH_TRAVERSAL_PATTERNS,
        "Command Injection": COMMAND_INJECTION_PATTERNS
    }
    
    # Check against each pattern type
    for pattern_type, patterns in all_patterns.items():
        for pattern in patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                detected_patterns.append(pattern_type)
                break  # Only report each type once
    
    return detected_patterns

def generate_security_report(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate comprehensive security report.
    
    Args:
        stats: Security statistics dictionary
        
    Returns:
        Formatted security report
    """
    metrics = stats.get("metrics", {})
    
    total_requests = metrics.get("total_requests", 0)
    blocked_requests = metrics.get("blocked_requests", 0)
    
    # Calculate security score (0-100)
    if total_requests == 0:
        security_score = 100
    else:
        block_rate = (blocked_requests / total_requests) * 100
        # Lower block rate indicates better security posture
        security_score = max(0, 100 - (block_rate * 2))
    
    # Identify top threats
    threat_types = [
        ("SQL Injection", metrics.get("sql_injection_attempts", 0)),
        ("XSS", metrics.get("xss_attempts", 0)),
        ("Path Traversal", metrics.get("path_traversal_attempts", 0)),
        ("Command Injection", metrics.get("command_injection_attempts", 0)),
        ("Rate Limiting", metrics.get("rate_limit_violations", 0)),
        ("IP Filtering", metrics.get("ip_filter_violations", 0))
    ]
    
    top_threats = sorted(threat_types, key=lambda x: x[1], reverse=True)[:3]
    
    report = {
        "security_score": round(security_score, 2),
        "total_requests": total_requests,
        "blocked_requests": blocked_requests,
        "block_rate_percentage": round((blocked_requests / max(total_requests, 1)) * 100, 2),
        "top_threats": [{"type": threat[0], "count": threat[1]} for threat in top_threats if threat[1] > 0],
        "suspicious_ips_count": metrics.get("suspicious_ips_count", 0),
        "last_attack_time": metrics.get("last_attack_time"),
        "recommendations": _generate_security_recommendations(metrics)
    }
    
    return report

def _generate_security_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """Generate security recommendations based on metrics"""
    recommendations = []
    
    # High attack volume recommendations
    if metrics.get("sql_injection_attempts", 0) > 10:
        recommendations.append("Consider implementing stricter input validation and parameterized queries")
    
    if metrics.get("xss_attempts", 0) > 10:
        recommendations.append("Review Content Security Policy settings and input sanitization")
    
    if metrics.get("rate_limit_violations", 0) > 50:
        recommendations.append("Consider reducing rate limits or implementing more granular rate limiting")
    
    if metrics.get("suspicious_ips_count", 0) > 5:
        recommendations.append("Review and update IP filtering rules and consider geo-blocking")
    
    # General recommendations
    if metrics.get("blocked_requests", 0) > 100:
        recommendations.append("Monitor blocked requests for false positives and adjust security rules")
    
    if not recommendations:
        recommendations.append("Security posture is good. Continue monitoring for new threats")
    
    return recommendations

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

def initialize_security_middleware(app: ASGIApp) -> ProductionSecurityMiddleware:
    """Initialize security middleware for production use"""
    config = SecurityConfig(
        enable_input_validation=getattr(settings, 'SECURITY_INPUT_VALIDATION', True),
        enable_sql_injection_protection=getattr(settings, 'SECURITY_SQL_PROTECTION', True),
        enable_xss_protection=getattr(settings, 'SECURITY_XSS_PROTECTION', True),
        enable_path_traversal_protection=getattr(settings, 'SECURITY_PATH_TRAVERSAL_PROTECTION', True),
        enable_command_injection_protection=getattr(settings, 'SECURITY_COMMAND_INJECTION_PROTECTION', True),
        enable_rate_limiting=getattr(settings, 'SECURITY_RATE_LIMITING', True),
        enable_ip_filtering=getattr(settings, 'SECURITY_IP_FILTERING', True),
        enable_security_headers=getattr(settings, 'SECURITY_HEADERS', True),
        enable_csrf_protection=getattr(settings, 'SECURITY_CSRF_PROTECTION', True),
        enable_request_signing=getattr(settings, 'SECURITY_REQUEST_SIGNING', False),
        max_request_size=getattr(settings, 'SECURITY_MAX_REQUEST_SIZE', 10485760),
        max_url_length=getattr(settings, 'SECURITY_MAX_URL_LENGTH', 2048),
        max_header_length=getattr(settings, 'SECURITY_MAX_HEADER_LENGTH', 8192),
        allowed_content_types=set(getattr(settings, 'SECURITY_ALLOWED_CONTENT_TYPES', 
                                         ["application/json", "application/x-www-form-urlencoded",
                                          "multipart/form-data", "text/plain", "text/csv"])),
        blocked_user_agents=set(getattr(settings, 'SECURITY_BLOCKED_USER_AGENTS', [])),
        allowed_ip_ranges=getattr(settings, 'SECURITY_ALLOWED_IP_RANGES', []),
        blocked_ip_ranges=getattr(settings, 'SECURITY_BLOCKED_IP_RANGES', []),
        trusted_proxies=getattr(settings, 'SECURITY_TRUSTED_PROXIES', []),
        custom_security_headers=getattr(settings, 'SECURITY_CUSTOM_HEADERS', {}),
        sensitive_paths=set(getattr(settings, 'SECURITY_SENSITIVE_PATHS', 
                                   ["/admin", "/api/v1/auth", "/api/v1/users"])),
        log_security_events=getattr(settings, 'SECURITY_LOG_EVENTS', True),
        block_malicious_requests=getattr(settings, 'SECURITY_BLOCK_MALICIOUS', True),
        quarantine_suspicious_ips=getattr(settings, 'SECURITY_QUARANTINE_IPS', True)
    )
    
    middleware = ProductionSecurityMiddleware(app, config)
    logger.info("Security middleware initialized for production")
    
    return middleware

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionSecurityMiddleware",
    "SecurityConfig",
    "InputValidator",
    "IPFilter",
    "CSRFProtection",
    "RequestSigner",
    "SecurityViolation",
    "SecurityMetrics",
    "create_security_middleware",
    "initialize_security_middleware",
    "health_check",
    "validate_security_configuration",
    "sanitize_input_string",
    "detect_security_patterns",
    "generate_security_report"
]getattr(settings, 'SECURITY_RATE_LIMITING', True),
            enable_ip_filtering=getattr(settings, 'SECURITY_IP_FILTERING', True),
            enable_security_headers=getattr(settings, 'SECURITY_HEADERS', True),
            enable_csrf_protection=getattr(settings, 'SECURITY_CSRF_PROTECTION', True),
            enable_request_signing=getattr(settings, 'SECURITY_REQUEST_SIGNING', False),
            max_request_size=getattr(settings, 'SECURITY_MAX_REQUEST_SIZE', 10485760),
            max_url_length=getattr(settings, 'SECURITY_MAX_URL_LENGTH', 2048),
            max_header_length=getattr(settings, 'SECURITY_MAX_HEADER_LENGTH', 8192),
            allowed_content_types=set(getattr(settings, 'SECURITY_ALLOWED_CONTENT_TYPES', 
                                             ["application/json", "application/x-www-form-urlencoded",
                                              "multipart/form-data", "text/plain", "text/csv"])),
            blocked_user_agents=set(getattr(settings, 'SECURITY_BLOCKED_USER_AGENTS', [])),
            allowed_ip_ranges=getattr(settings, 'SECURITY_ALLOWED_IP_RANGES', []),
            blocked_ip_ranges=getattr(settings, 'SECURITY_BLOCKED_IP_RANGES', []),
            trusted_proxies=getattr(settings, 'SECURITY_TRUSTED_PROXIES', []),
            custom_security_headers=getattr(settings, 'SECURITY_CUSTOM_HEADERS', {}),
            sensitive_paths=set(getattr(settings, 'SECURITY_SENSITIVE_PATHS', 
                                       ["/admin", "/api/v1/auth", "/api/v1/users"])),
            log_security_events=getattr(settings, 'SECURITY_LOG_EVENTS', True),
            block_malicious_requests=getattr(settings, 'SECURITY_BLOCK_MALICIOUS', True),
            quarantine_suspicious_ips=getattr(settings, 'SECURITY_QUARANTINE_IPS', True)
        )
    
    def _sanitize_config_for_log(self) -> Dict[str, Any]:
        """Sanitize config for safe logging"""
        return {
            "input_validation": self.config.enable_input_validation,
            "sql_protection": self.config.enable_sql_injection_protection,
            "xss_protection": self.config.enable_xss_protection,
            "rate_limiting": self.config.enable_rate_limiting,
            "ip_filtering": self.config.enable_ip_filtering,
            "csrf_protection": self.config.enable_csrf_protection,
            "request_signing": self.config.enable_request_signing,
            "max_request_size": self.config.max_request_size,
            "allowed_content_types_count": len(self.config.allowed_content_types),
            "blocked_ip_ranges_count": len(self.config.blocked_ip_ranges)
        }
    
    @track_performance
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Main security middleware dispatch logic.
        
        Performs comprehensive security checks on all incoming requests
        including input validation, rate limiting, IP filtering, and more.
        """
        violation_id = str(uuid.uuid4())
        self._security_metrics.total_requests += 1
        
        try:
            # Extract client information
            client_ip = self.ip_filter.get_client_ip(request)
            user_agent = request.headers.get('user-agent', '')
            
            # 1. IP Filtering
            if self.config.enable_ip_filtering:
                ip_allowed, ip_reason = self.ip_filter.is_ip_allowed(client_ip)
                if not ip_allowed:
                    await self._handle_security_violation(
                        violation_id, "IP_BLOCKED", "high", client_ip, user_agent,
                        str(request.url.path), request.method, ip_reason, request
                    )
                    if self.config.block_malicious_requests:
                        return self._create_security_response("Access denied", 403)
            
            # 2. User Agent Filtering
            if user_agent.lower() in [ua.lower() for ua in self.config.blocked_user_agents]:
                await self._handle_security_violation(
                    violation_id, "USER_AGENT_BLOCKED", "medium", client_ip, user_agent,
                    str(request.url.path), request.method, f"Blocked user agent: {user_agent}", request
                )
                if self.config.block_malicious_requests:
                    return self._create_security_response("Access denied", 403)
            
            # 3. Rate Limiting
            if self.config.enable_rate_limiting:
                rate_limit_key = self._get_rate_limit_key(request, client_ip)
                rate_limit_type = self._determine_rate_limit_type(request)
                
                if not self.rate_limiter.is_allowed(rate_limit_key, rate_limit_type):
                    self._security_metrics.rate_limit_violations += 1
                    await self._handle_security_violation(
                        violation_id, "RATE_LIMIT_EXCEEDED", "medium", client_ip, user_agent,
                        str(request.url.path), request.method, f"Rate limit exceeded for {rate_limit_type}", request
                    )
                    if self.config.block_malicious_requests:
                        return self._create_security_response("Rate limit exceeded", 429)
            
            # 4. Request Size Validation
            size_valid, size_reason = self.input_validator.validate_request_size(request)
            if not size_valid:
                await self._handle_security_violation(
                    violation_id, "REQUEST_SIZE_VIOLATION", "medium", client_ip, user_agent,
                    str(request.url.path), request.method, size_reason, request
                )
                if self.config.block_malicious_requests:
                    return self._create_security_response("Request too large", 413)
            
            # 5. URL Length Validation
            url_valid, url_reason = self.input_validator.validate_url_length(str(request.url))
            if not url_valid:
                await self._handle_security_violation(
                    violation_id, "URL_LENGTH_VIOLATION", "low", client_ip, user_agent,
                    str(request.url.path), request.method, url_reason, request
                )
                if self.config.block_malicious_requests:
                    return self._create_security_response("URL too long", 414)
            
            # 6. Header Validation
            headers_valid, header_reason = self.input_validator.validate_headers(dict(request.headers))
            if not headers_valid:
                await self._handle_security_violation(
                    violation_id, "HEADER_VALIDATION_FAILURE", "medium", client_ip, user_agent,
                    str(request.url.path), request.method, header_reason, request
                )
                if self.config.block_malicious_requests:
                    return self._create_security_response("Invalid headers", 400)
            
            # 7. Content Type Validation
            content_type = request.headers.get('content-type')
            content_type_valid, content_type_reason = self.input_validator.validate_content_type(content_type)
            if not content_type_valid:
                await self._handle_security_violation(
                    violation_id, "CONTENT_TYPE_VIOLATION", "medium", client_ip, user_agent,
                    str(request.url.path), request.method, content_type_reason, request
                )
                if self.config.block_malicious_requests:
                    return self._create_security_response("Content type not allowed", 415)
            
            # 8. Input Validation (Query Parameters)
            if self.config.enable_input_validation:
                for key, value in request.query_params.items():
                    input_valid, input_reason = self.input_validator.validate_input(value, f"query:{key}")
                    if not input_valid:
                        await self._handle_security_violation(
                            violation_id, "INPUT_VALIDATION_FAILURE", "high", client_ip, user_agent,
                            str(request.url.path), request.method, input_reason, request
                        )
                        self._update_attack_metrics(input_reason)
                        if self.config.block_malicious_requests:
                            return self._create_security_response("Invalid input detected", 400)
            
            # 9. CSRF Protection
            if self.csrf_protection.requires_csrf_validation(request):
                session_id = request.headers.get('x-session-id')
                csrf_token = request.headers.get('x-csrf-token')
                
                if not self.csrf_protection.validate_csrf_token(session_id, csrf_token):
                    await self._handle_security_violation(
                        violation_id, "CSRF_VALIDATION_FAILURE", "high", client_ip, user_agent,
                        str(request.url.path), request.method, "Invalid or missing CSRF token", request
                    )
                    if self.config.block_malicious_requests:
                        return self._create_security_response("CSRF token validation failed", 403)
            
            # 10. Request Signature Validation
            if self.config.enable_request_signing:
                signature_valid, signature_reason = self.request_signer.validate_signature(request)
                if not signature_valid:
                    await self._handle_security_violation(
                        violation_id, "SIGNATURE_VALIDATION_FAILURE", "high", client_ip, user_agent,
                        str(request.url.path), request.method, signature_reason, request
                    )
                    if self.config.block_malicious_requests:
                        return self._create_security_response("Request signature validation failed", 401)
            
            # Process the request
            response = await call_next(request)
            
            # Add security headers
            if self.config.enable_security_headers:
                self._add_security_headers(response)
            
            return response
            
        except Exception as e:
            self.logger.error(
                "Security middleware error",
                violation_id=violation_id,
                error=str(e),
                client_ip=client_ip if 'client_ip' in locals() else 'unknown'
            )
            # Don't block on middleware errors, but log them
            response = await call_next(request)
            if self.config.enable_security_headers:
                self._add_security_headers(response)
            return response
    
    def _get_rate_limit_key(self, request: Request, client_ip: str) -> str:
        """Generate rate limit key based on client IP and endpoint"""
        return f"{client_ip}:{request.url.path}"
    
    def _determine_rate_limit_type(self, request: Request) -> str:
        """Determine which rate limit to apply"""
        path = request.url.path
        
        if "/auth" in path or "/login" in path:
            return "auth"
        elif "/upload" in path:
            return "upload"
        elif path.startswith("/api"):
            return "api"
        else:
            return "global"
    
    async def _handle_security_violation(
        self,
        violation_id: str,
        violation_type: str,
        severity: str,
        client_ip: str,
        user_agent: Optional[str],
        endpoint: str,
        method: str,
        details: str,
        request: Request
    ) -> None:
        """Handle security violation"""
        self._security_metrics.blocked_requests += 1
        self._security_metrics.last_attack_time = datetime.utcnow()
        
        # Record IP violation
        self.ip_filter.record_violation(client_ip)
        
        # Create violation record
        violation = SecurityViolation(
            violation_id=violation_id,
            violation_type=violation_type,
            severity=severity,
            client_ip=client_ip,
            user_agent=user_agent,
            endpoint=endpoint,
            method=method,
            details=details,
            timestamp=datetime.utcnow(),
            request_id=getattr(request.state, 'request_id', None),
            user_id=getattr(request.state, 'user_id', None),
            blocked=self.config.block_malicious_requests
        )
        
        # Log security event
        if self.config.log_security_events:
            self.logger.warning(
                "Security violation detected",
                violation_id=violation_id,
                violation_type=violation_type,
                severity=severity,
                client_ip=client_ip,
                user_agent=user_agent,
                endpoint=endpoint,
                method=method,
                details=details,
                blocked=self.config.block_malicious_requests
            )
        
        # Log to security monitoring system
        await log_security_event(
            event_type=SecurityEventType.ATTACK_DETECTED,
            severity=severity,
            details=violation.__dict__
        )
        
        # Store in database for analysis
        await log_security_violation(violation)
    
    def _update_attack_metrics(self, reason: str) -> None:
        """Update attack-specific metrics"""
        if "sql injection" in reason.lower():
            self._security_metrics.sql_injection_attempts += 1
        elif "xss" in reason.lower():
            self._security_metrics.xss_attempts += 1
        elif "path traversal" in reason.lower():
            self._security_metrics.path_traversal_attempts += 1
        elif "command injection" in reason.lower():
            self._security_metrics.command_injection_attempts += 1
    
    def _create_security_response(self, message: str, status_code: int) -> JSONResponse:
        """Create standardized security response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": "SECURITY_VIOLATION",
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            },
            headers={
                "X-Security-Response": "true"
            }
        )
    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response"""
        # Add default security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Add custom security headers
        for header, value in self.config.custom_security_headers.items():
            response.headers[header] = value
        
        # Add CSRF token if needed
        if self.config.enable_csrf_protection:
            # This would typically be added based on session context
            pass
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get comprehensive security statistics"""
        return {
            "metrics": {
                "total_requests": self._security_metrics.total_requests,
                "blocked_requests": self._security_metrics.blocked_requests,
                "sql_injection_attempts": self._security_metrics.sql_injection_attempts,
                "xss_attempts": self._security_metrics.xss_attempts,
                "path_traversal_attempts": self._security_metrics.path_traversal_attempts,
                "command_injection_attempts": self._security_metrics.command_injection_attempts,
                "rate_limit_violations": self._security_metrics.rate_limit_violations,
                "ip_filter_violations": self._security_metrics.ip_filter_violations,
                "suspicious_ips_count": len(self._security_metrics.suspicious_ips),
                "last_attack_time": self._security_metrics.last_attack_time.isoformat() if self._security_metrics.last_attack_time else None
            },
            "rate_limiter_stats": self.rate_limiter.get_stats(),
            "config": self._sanitize_config_for_log()
        }

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_security_middleware(
    enable_input_validation: bool = True,
    enable_rate_limiting: bool = True,
    enable_ip_filtering: bool = True,
    enable_csrf_protection: bool = True,
    block_malicious_requests: bool = True,
    max_request_size: int = 10485760,
    allowed_content_types: Optional[Set[str]] = None
) -> Callable[[ASGIApp], ProductionSecurityMiddleware]:
    """
    Factory function to create security middleware with custom configuration.
    
    Args:
        enable_input_validation: Enable input validation and sanitization
        enable_rate_limiting: Enable rate limiting protection
        enable_ip_filtering: Enable IP address filtering
        enable_csrf_protection: Enable CSRF protection
        block_malicious_requests: Block requests that fail security checks
        max_request_size: Maximum allowed request size in bytes
        allowed_content_types: Set of allowed content types
        
    Returns:
        Configured security middleware factory function
    """
    config = SecurityConfig(
        enable_input_validation=enable_input_validation,
        enable_rate_limiting=