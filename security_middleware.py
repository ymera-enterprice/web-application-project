"""
YMERA Enterprise Security Middleware
Production-ready security middleware with advanced threat detection and protection
"""

import time
import hmac
import hashlib
import secrets
import re
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
import json
import geoip2.database
import geoip2.errors
from urllib.parse import urlparse
import asyncio
from collections import defaultdict, deque

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

import logging
import ipaddress
from pathlib import Path


class ThreatDetector:
    """Advanced threat detection system"""
    
    def __init__(self):
        self.suspicious_patterns = [
            # SQL Injection patterns
            r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|drop\s+table|delete\s+from)",
            r"(?i)(\'\s*or\s+\d+=\d+|\'\s*or\s+\'.*\'=\'|--\s*$|\s*;\s*--)",
            
            # XSS patterns
            r"(?i)(<script|javascript:|vbscript:|onload=|onerror=|onclick=)",
            r"(?i)(alert\(|confirm\(|prompt\(|document\.cookie|document\.write)",
            
            # Path traversal
            r"(\.\./|\.\.\\/|%2e%2e%2f|%252e%252e%252f)",
            
            # Command injection
            r"(?i)(;?\s*(cat|ls|pwd|whoami|id|uname|wget|curl|nc|netcat)\s)",
            r"(\$\(|\`|&&|\|\||;)",
            
            # LDAP injection
            r"(\(\|\(|\)\(|%28%7c%28)",
            
            # XML/XXE injection
            r"(?i)(<!entity|<!doctype|system\s+['\"])",
            
            # NoSQL injection
            r"(?i)(\$ne|\$gt|\$lt|\$regex|\$where)",
            
            # Header injection
            r"(\r\n|\n\r|\r|\n).*:",
        ]
        
        self.compiled_patterns = [re.compile(pattern) for pattern in self.suspicious_patterns]
        
        # Known malicious user agents
        self.malicious_user_agents = {
            "sqlmap", "nikto", "nmap", "dirbuster", "gobuster", "wfuzz",
            "burp", "owasp", "acunetix", "netsparker", "appscan",
            "python-requests", "curl", "wget", "masscan"
        }
        
        # Suspicious request patterns
        self.attack_indicators = {
            "high_frequency": 100,  # requests per minute
            "path_traversal_attempts": 5,
            "suspicious_headers": 3,
            "payload_size_threshold": 10240  # 10KB
        }

    def detect_threats(self, request: Request, body: bytes = None) -> Dict[str, Any]:
        """Comprehensive threat detection"""
        threats = {
            "detected": False,
            "threat_types": [],
            "risk_level": "low",
            "details": []
        }
        
        # Check URL for threats
        url_threats = self._check_url_threats(str(request.url))
        if url_threats:
            threats["detected"] = True
            threats["threat_types"].extend(url_threats)
            threats["details"].append("Malicious patterns detected in URL")
        
        # Check headers for threats
        header_threats = self._check_header_threats(request.headers)
        if header_threats:
            threats["detected"] = True
            threats["threat_types"].extend(header_threats)
            threats["details"].append("Suspicious headers detected")
        
        # Check user agent
        if self._is_malicious_user_agent(request.headers.get("user-agent", "")):
            threats["detected"] = True
            threats["threat_types"].append("malicious_user_agent")
            threats["details"].append("Known malicious user agent")
        
        # Check request body if present
        if body:
            body_threats = self._check_body_threats(body)
            if body_threats:
                threats["detected"] = True
                threats["threat_types"].extend(body_threats)
                threats["details"].append("Malicious payload detected in body")
        
        # Determine risk level
        threats["risk_level"] = self._calculate_risk_level(threats["threat_types"])
        
        return threats

    def _check_url_threats(self, url: str) -> List[str]:
        """Check URL for malicious patterns"""
        threats = []
        url_lower = url.lower()
        
        for pattern in self.compiled_patterns:
            if pattern.search(url):
                threats.append("injection_attempt")
                break
        
        # Check for path traversal
        if "../" in url or "..%2f" in url_lower or "%2e%2e" in url_lower:
            threats.append("path_traversal")
        
        # Check for excessive parameters (possible DoS)
        if url.count("&") > 50 or url.count("=") > 50:
            threats.append("parameter_pollution")
        
        return threats

    def _check_header_threats(self, headers) -> List[str]:
        """Check headers for threats"""
        threats = []
        
        # Check for header injection
        for name, value in headers.items():
            if any(pattern.search(f"{name}: {value}") for pattern in self.compiled_patterns):
                threats.append("header_injection")
                break
        
        # Check for suspicious headers
        suspicious_headers = ["x-forwarded-for", "x-real-ip", "x-remote-addr"]
        for header in suspicious_headers:
            if header in headers:
                value = headers[header]
                if self._is_suspicious_ip_header(value):
                    threats.append("ip_spoofing_attempt")
        
        return threats

    def _check_body_threats(self, body: bytes) -> List[str]:
        """Check request body for threats"""
        threats = []
        
        try:
            body_str = body.decode('utf-8', errors='ignore')
            
            # Check for injection patterns
            for pattern in self.compiled_patterns:
                if pattern.search(body_str):
                    threats.append("payload_injection")
                    break
            
            # Check for oversized payloads
            if len(body) > self.attack_indicators["payload_size_threshold"]:
                threats.append("oversized_payload")
            
        except Exception:
            # If we can't decode the body, it might be suspicious
            threats.append("malformed_payload")
        
        return threats

    def _is_malicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is known to be malicious"""
        if not user_agent:
            return True  # Empty user agent is suspicious
        
        user_agent_lower = user_agent.lower()
        return any(malicious in user_agent_lower for malicious in self.malicious_user_agents)

    def _is_suspicious_ip_header(self, value: str) -> bool:
        """Check if IP header value is suspicious"""
        # Check for multiple IPs (possible proxy chain manipulation)
        if value.count(',') > 3:
            return True
        
        # Check for private/local IPs in forwarded headers (possible spoofing)
        ips = [ip.strip() for ip in value.split(',')]
        for ip in ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback:
                    continue  # These are expected
            except ValueError:
                return True  # Invalid IP format
        
        return False

    def _calculate_risk_level(self, threat_types: List[str]) -> str:
        """Calculate overall risk level based on detected threats"""
        if not threat_types:
            return "low"
        
        high_risk_threats = {
            "injection_attempt", "payload_injection", "malicious_user_agent"
        }
        medium_risk_threats = {
            "path_traversal", "header_injection", "ip_spoofing_attempt"
        }
        
        if any(threat in high_risk_threats for threat in threat_types):
            return "high"
        elif any(threat in medium_risk_threats for threat in threat_types):
            return "medium"
        else:
            return "low"


class GeoIPDetector:
    """Geographic IP analysis for enhanced security"""
    
    def __init__(self, mmdb_path: Optional[str] = None):
        self.reader = None
        self.enabled = False
        
        if mmdb_path and Path(mmdb_path).exists():
            try:
                self.reader = geoip2.database.Reader(mmdb_path)
                self.enabled = True
            except Exception as e:
                logging.warning(f"Failed to initialize GeoIP: {e}")
        
        # High-risk countries (customize based on your threat model)
        self.high_risk_countries = {
            "CN", "RU", "KP", "IR"  # Add/remove as needed
        }

    def analyze_ip(self, ip_address: str) -> Dict[str, Any]:
        """Analyze IP address for geographic risk factors"""
        result = {
            "country": None,
            "is_high_risk": False,
            "is_tor": False,
            "is_vpn": False,
            "risk_score": 0
        }
        
        if not self.enabled or not ip_address:
            return result
        
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            
            # Skip analysis for private/local IPs
            if ip_obj.is_private or ip_obj.is_loopback:
                return result
            
            response = self.reader.country(ip_address)
            country_code = response.country.iso_code
            
            result["country"] = country_code
            result["is_high_risk"] = country_code in self.high_risk_countries
            
            # Basic heuristics for VPN/Tor detection
            # In production, use dedicated services like MaxMind's Anonymous IP
            result["risk_score"] = self._calculate_ip_risk_score(response)
            
        except (geoip2.errors.AddressNotFoundError, ValueError):
            # IP not found in database or invalid format
            result["risk_score"] = 30  # Unknown IPs get moderate risk
        except Exception as e:
            logging.warning(f"GeoIP analysis failed for {ip_address}: {e}")
        
        return result

    def _calculate_ip_risk_score(self, response) -> int:
        """Calculate risk score (0-100) based on IP characteristics"""
        score = 0
        
        # Country-based risk
        if response.country.iso_code in self.high_risk_countries:
            score += 40
        
        # ISP-based risk (basic heuristics)
        if response.traits.isp:
            isp_lower = response.traits.isp.lower()
            if any(term in isp_lower for term in ["hosting", "server", "cloud", "vps"]):
                score += 20
            if any(term in isp_lower for term in ["proxy", "vpn", "tor"]):
                score += 30
        
        return min(score, 100)


class SecurityMetrics:
    """Security metrics collection and analysis"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.metrics = defaultdict(int)
        self.recent_attacks = deque(maxlen=1000)
        
    async def record_threat(self, request: Request, threat_data: Dict[str, Any]):
        """Record security threat for analysis"""
        timestamp = datetime.utcnow()
        client_ip = self._get_client_ip(request)
        
        attack_record = {
            "timestamp": timestamp.isoformat(),
            "ip": client_ip,
            "path": request.url.path,
            "method": request.method,
            "threat_types": threat_data["threat_types"],
            "risk_level": threat_data["risk_level"],
            "user_agent": request.headers.get("user-agent", "")
        }
        
        self.recent_attacks.append(attack_record)
        
        # Update metrics
        self.metrics["total_threats"] += 1
        self.metrics[f"threats_{threat_data['risk_level']}"] += 1
        
        for threat_type in threat_data["threat_types"]:
            self.metrics[f"threat_type_{threat_type}"] += 1
        
        # Store in Redis if available
        if self.redis_client:
            key = f"security:threats:{timestamp.strftime('%Y%m%d')}"
            await self.redis_client.lpush(key, json.dumps(attack_record))
            await self.redis_client.expire(key, 86400 * 7)  # Keep for 7 days

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"

    def get_security_summary(self) -> Dict[str, Any]:
        """Get security metrics summary"""
        return {
            "total_threats": self.metrics["total_threats"],
            "high_risk_threats": self.metrics["threats_high"],
            "medium_risk_threats": self.metrics["threats_medium"],
            "low_risk_threats": self.metrics["threats_low"],
            "recent_attacks_count": len(self.recent_attacks),
            "top_threat_types": self._get_top_threat_types(),
            "most_targeted_paths": self._get_most_targeted_paths()
        }
    
    def _get_top_threat_types(self) -> List[Dict[str, Any]]:
        """Get most common threat types"""
        threat_counts = {}
        for key, count in self.metrics.items():
            if key.startswith("threat_type_"):
                threat_type = key.replace("threat_type_", "")
                threat_counts[threat_type] = count
        
        return sorted(
            [{"type": t, "count": c} for t, c in threat_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]
    
    def _get_most_targeted_paths(self) -> List[Dict[str, Any]]:
        """Get most targeted paths"""
        path_counts = defaultdict(int)
        for attack in self.recent_attacks:
            path_counts[attack["path"]] += 1
        
        return sorted(
            [{"path": p, "count": c} for p, c in path_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enterprise-grade security middleware"""
    
    def __init__(
        self,
        app: ASGIApp,
        secret_key: Optional[str] = None,
        enable_csrf: bool = True,
        enable_xss_protection: bool = True,
        enable_content_type_options: bool = True,
        enable_frame_options: bool = True,
        enable_hsts: bool = True,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        trusted_hosts: Optional[List[str]] = None,
        geoip_db_path: Optional[str] = None,
        block_high_risk_countries: bool = False,
        redis_client=None
    ):
        super().__init__(app)
        
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.enable_csrf = enable_csrf
        self.enable_xss_protection = enable_xss_protection
        self.enable_content_type_options = enable_content_type_options
        self.enable_frame_options = enable_frame_options
        self.enable_hsts = enable_hsts
        self.max_request_size = max_request_size
        self.trusted_hosts = set(trusted_hosts or [])
        self.block_high_risk_countries = block_high_risk_countries
        
        # Security components
        self.threat_detector = ThreatDetector()
        self.geoip_detector = GeoIPDetector(geoip_db_path)
        self.security_metrics = SecurityMetrics(redis_client)
        
        # Rate limiting for security events
        self.security_violations = defaultdict(list)
        self.violation_threshold = 5
        self.violation_window = 300  # 5 minutes
        
        self.logger = logging.getLogger(__name__)

    async def dispatch(self, request: Request, call_next):
        """Main security middleware dispatch"""
        start_time = time.time()
        
        try:
            # 1. Host validation
            if not self._is_trusted_host(request):
                return self._security_response(
                    "Untrusted host",
                    status.HTTP_400_BAD_REQUEST
                )
            
            # 2. Request size validation
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_request_size:
                return self._security_response(
                    "Request too large",
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                )
            
            # 3. Get client IP and perform GeoIP analysis
            client_ip = self._get_client_ip(request)
            geo_analysis = self.geoip_detector.analyze_ip(client_ip)
            
            # 4. Block high-risk countries if enabled
            if (self.block_high_risk_countries and 
                geo_analysis["is_high_risk"]):
                await self._log_security_event(
                    request, "high_risk_country", geo_analysis
                )
                return self._security_response(
                    "Access denied",
                    status.HTTP_403_FORBIDDEN
                )
            
            # 5. Read request body for threat analysis
            body = b""
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # 6. Threat detection
            threat_analysis = self.threat_detector.detect_threats(request, body)
            
            # 7. Handle detected threats
            if threat_analysis["detected"]:
                await self.security_metrics.record_threat(request, threat_analysis)
                
                # Block high-risk threats immediately
                if threat_analysis["risk_level"] == "high":
                    await self._log_security_event(
                        request, "high_risk_threat", threat_analysis
                    )
                    return self._security_response(
                        "Security threat detected",
                        status.HTTP_403_FORBIDDEN
                    )
                
                # Track violations for medium-risk threats
                elif threat_analysis["risk_level"] == "medium":
                    if await self._should_block_for_violations(client_ip):
                        return self._security_response(
                            "Multiple security violations",
                            status.HTTP_429_TOO_MANY_REQUESTS
                        )
            
            # 8. Continue with request processing
            response = await call_next(request)
            
            # 9. Add security headers
            self._add_security_headers(response)
            
            # 10. Log successful request with security context
            processing_time = time.time() - start_time
            await self._log_request(request, response, processing_time, geo_analysis)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Security middleware error: {str(e)}")
            return self._security_response(
                "Internal security error",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _is_trusted_host(self, request: Request) -> bool:
        """Validate request host against trusted hosts"""
        if not self.trusted_hosts:
            return True
        
        host = request.headers.get("host", "").lower()
        if not host:
            return False
        
        # Remove port if present
        host = host.split(":")[0]
        
        return host in self.trusted_hosts or any(
            host.endswith(f".{trusted_host}") for trusted_host in self.trusted_hosts
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP address"""
        # Check forwarded headers (in order of preference)
        headers = [
            "cf-connecting-ip",  # Cloudflare
            "x-forwarded-for",
            "x-real-ip",
            "x-client-ip"
        ]
        
        for header in headers:
            value = request.headers.get(header)
            if value:
                # Take first IP if comma-separated
                ip = value.split(",")[0].strip()
                try:
                    ipaddress.ip_address(ip)
                    return ip
                except ValueError:
                    continue
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"

    async def _should_block_for_violations(self, client_ip: str) -> bool:
        """Check if client should be blocked for repeated violations"""
        now = time.time()
        violations = self.security_violations[client_ip]
        
        # Remove old violations outside the window
        violations[:] = [v for v in violations if now - v < self.violation_window]
        
        # Add current violation
        violations.append(now)
        
        # Block if threshold exceeded
        return len(violations) >= self.violation_threshold

    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        headers = {}
        
        if self.enable_xss_protection:
            headers["X-XSS-Protection"] = "1; mode=block"
        
        if self.enable_content_type_options:
            headers["X-Content-Type-Options"] = "nosniff"
        
        if self.enable_frame_options:
            headers["X-Frame-Options"] = "DENY"
        
        if self.enable_hsts:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Additional security headers
        headers.update({
            "X-Permitted-Cross-Domain-Policies": "none",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        })
        
        for name, value in headers.items():
            response.headers[name] = value

    def _security_response(self, message: str, status_code: int) -> JSONResponse:
        """Create standardized security response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Security violation",
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": secrets.token_hex(8)
            },
            headers={
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY"
            }
        )

    async def _log_security_event(
        self, 
        request: Request, 
        event_type: str, 
        details: Dict[str, Any]
    ):
        """Log security events for monitoring"""
        event_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "client_ip": self._get_client_ip(request),
            "path": request.url.path,
            "method": request.method,
            "user_agent": request.headers.get("user-agent", ""),
            "details": details
        }
        
        self.logger.warning(
            f"Security event: {event_type}",
            extra=event_data
        )

    async def _log_request(
        self, 
        request: Request, 
        response: Response, 
        processing_time: float,
        geo_analysis: Dict[str, Any]
    ):
        """Log request with security context"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "client_ip": self._get_client_ip(request),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "processing_time": processing_time,
            "user_agent": request.headers.get("user-agent", ""),
            "country": geo_analysis.get("country"),
            "risk_score": geo_analysis.get("risk_score", 0)
        }
        
        self.logger.info(
            "Request processed",
            extra=log_data
        )