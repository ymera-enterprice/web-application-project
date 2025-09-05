"""
YMERA Enterprise - Audit Logger System
Production-Ready Audit Trail Management - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

# Third-party imports (alphabetical)
import aioredis
import structlog
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Depends, status, Request
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token, get_current_user

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.audit_logger")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Audit event types
class AuditEventType(str, Enum):
    """Enumeration of audit event types"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    DATA_ACCESS = "data_access"
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    FILE_UPLOADED = "file_uploaded"
    FILE_DOWNLOADED = "file_downloaded"
    API_REQUEST = "api_request"
    SYSTEM_ERROR = "system_error"
    SECURITY_VIOLATION = "security_violation"
    CONFIGURATION_CHANGE = "configuration_change"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    AGENT_CREATED = "agent_created"
    AGENT_UPDATED = "agent_updated"
    AGENT_DELETED = "agent_deleted"
    LEARNING_EVENT = "learning_event"
    KNOWLEDGE_TRANSFER = "knowledge_transfer"

class AuditSeverity(str, Enum):
    """Audit event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuditStatus(str, Enum):
    """Audit event status"""
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    ERROR = "error"

# Module constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 3600
AUDIT_RETENTION_DAYS = 2555  # 7 years for compliance
BATCH_SIZE = 1000
ENCRYPTION_KEY_ROTATION_DAYS = 90

# Configuration loading
settings = get_settings()

# Database base
Base = declarative_base()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class AuditConfig:
    """Configuration dataclass for audit logger settings"""
    enabled: bool = True
    encrypt_sensitive_data: bool = True
    retention_days: int = 2555
    batch_processing: bool = True
    batch_size: int = 1000
    real_time_alerts: bool = True
    compliance_mode: bool = True
    max_connections: int = 100
    timeout: int = 30
    retry_attempts: int = 3

class AuditEvent(Base):
    """SQLAlchemy model for audit events"""
    __tablename__ = "audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    
    # Extract user information
    if user:
        context["user"] = {
            "user_id": user.get("id") or user.get("user_id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "session_id": user.get("session_id"),
            "roles": user.get("roles", []),
            "permissions": user.get("permissions", [])
        }
    
    # Extract request information
    if request:
        context["request"] = {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "referer": request.headers.get("referer"),
            "content_type": request.headers.get("content-type"),
            "request_id": request.headers.get("x-request-id", str(uuid.uuid4()))
        }
    
    # Add system information
    context["system"] = {
        "service_name": "ymera",
        "version": "4.0",
        "environment": settings.ENVIRONMENT,
        "hostname": os.getenv("HOSTNAME", "unknown"),
        "process_id": os.getpid(),
        **(system_info or {})
    }
    
    return context

def sanitize_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive data from audit payloads.
    
    Args:
        data: Original data dictionary
        
    Returns:
        Sanitized data dictionary with sensitive fields masked
    """
    sensitive_fields = {
        "password", "passwd", "pwd", "secret", "token", "key",
        "api_key", "access_token", "refresh_token", "jwt",
        "credit_card", "ssn", "social_security", "phone",
        "email", "address", "ip_address"
    }
    
    sanitized = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if field is sensitive
        if any(sensitive in key_lower for sensitive in sensitive_fields):
            if isinstance(value, str) and len(value) > 4:
                sanitized[key] = f"****{value[-4:]}"  # Show last 4 characters
            else:
                sanitized[key] = "****"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_sensitive_data(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized

async def validate_audit_integrity(
    event: AuditEvent,
    encryption_key: Optional[Fernet] = None
) -> bool:
    """
    Validate the integrity of an audit event.
    
    Args:
        event: Audit event to validate
        encryption_key: Encryption key for payload validation
        
    Returns:
        True if event integrity is valid, False otherwise
    """
    try:
        # Regenerate hash and compare
        hash_data = f"{event.event_id}{event.timestamp}{event.event_type}{event.action}{event.description}"
        expected_hash = hashlib.sha256(hash_data.encode()).hexdigest()
        
        if event.hash_signature != expected_hash:
            logger.warning("Audit event hash mismatch", event_id=event.event_id)
            return False
        
        # Validate encrypted payload if present
        if event.encrypted_payload and encryption_key:
            try:
                decrypted = encryption_key.decrypt(event.encrypted_payload.encode())
                json.loads(decrypted.decode())  # Validate JSON structure
            except Exception as e:
                logger.warning("Encrypted payload validation failed", event_id=event.event_id, error=str(e))
                return False
        
        return True
        
    except Exception as e:
        logger.error("Integrity validation error", event_id=event.event_id, error=str(e))
        return False

# ===============================================================================
# EXCEPTION CLASSES
# ===============================================================================

class AuditLoggingError(Exception):
    """Exception raised when audit logging fails"""
    pass

class AuditSearchError(Exception):
    """Exception raised when audit search fails"""
    pass

class ReportGenerationError(Exception):
    """Exception raised when report generation fails"""
    pass

class IntegrityValidationError(Exception):
    """Exception raised when audit integrity validation fails"""
    pass

# ===============================================================================
# AUDIT DECORATORS
# ===============================================================================

def audit_action(
    event_type: AuditEventType,
    action: str,
    description: Optional[str] = None,
    severity: AuditSeverity = AuditSeverity.LOW,
    resource_type: Optional[str] = None,
    capture_payload: bool = False
):
    """
    Decorator to automatically audit function calls.
    
    Args:
        event_type: Type of audit event
        action: Action being performed
        description: Optional description template
        severity: Event severity level
        resource_type: Type of resource being accessed
        capture_payload: Whether to capture function arguments
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get audit logger instance
            audit_logger = kwargs.pop('_audit_logger', None)
            if not audit_logger:
                # Skip auditing if no logger provided
                return await func(*args, **kwargs)
            
            # Extract context
            request = kwargs.get('request')
            user = kwargs.get('current_user')
            
            # Prepare audit event
            event_description = description or f"Executed {action}"
            payload = None
            
            if capture_payload:
                payload = {
                    "function": func.__name__,
                    "args": sanitize_sensitive_data({"args": args, "kwargs": kwargs})
                }
            
            audit_event = AuditEventRequest(
                event_type=event_type,
                severity=severity,
                action=action,
                description=event_description,
                resource_type=resource_type,
                payload=payload
            )
            
            # Create context
            context = await create_audit_context(request=request, user=user)
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                # Log successful execution
                await audit_logger.log_event(audit_event, context)
                
                return result
                
            except Exception as e:
                # Log failed execution
                audit_event.description = f"Failed to execute {action}: {str(e)}"
                audit_event.severity = AuditSeverity.HIGH
                
                error_context = context.copy()
                error_context["error"] = {
                    "type": type(e).__name__,
                    "message": str(e)
                }
                
                await audit_logger.log_event(audit_event, error_context)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we need to handle differently
            # This is a simplified version - in production, you might want to
            # queue the audit event for async processing
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# ===============================================================================
# REPORT GENERATION UTILITIES
# ===============================================================================

class AuditReportGenerator:
    """Utility class for generating various audit reports"""
    
    def __init__(self, audit_logger: ProductionAuditLogger):
        self.audit_logger = audit_logger
        self.logger = logger.bind(component="report_generator")
    
    async def generate_user_activity_report(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Generate user activity report"""
        user_activities = {}
        
        for event in events:
            if event.user_id:
                user_id = str(event.user_id)
                if user_id not in user_activities:
                    user_activities[user_id] = {
                        "username": event.username,
                        "total_events": 0,
                        "event_types": {},
                        "first_activity": event.timestamp,
                        "last_activity": event.timestamp,
                        "ip_addresses": set(),
                        "failed_attempts": 0
                    }
                
                activity = user_activities[user_id]
                activity["total_events"] += 1
                activity["event_types"][event.event_type] = activity["event_types"].get(event.event_type, 0) + 1
                
                if event.timestamp < activity["first_activity"]:
                    activity["first_activity"] = event.timestamp
                if event.timestamp > activity["last_activity"]:
                    activity["last_activity"] = event.timestamp
                
                if event.ip_address:
                    activity["ip_addresses"].add(event.ip_address)
                
                if event.status in ["failure", "error"]:
                    activity["failed_attempts"] += 1
        
        # Convert sets to lists for JSON serialization
        for activity in user_activities.values():
            activity["ip_addresses"] = list(activity["ip_addresses"])
            activity["first_activity"] = activity["first_activity"].isoformat()
            activity["last_activity"] = activity["last_activity"].isoformat()
        
        return {
            "total_users": len(user_activities),
            "user_activities": user_activities
        }
    
    async def generate_system_events_report(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Generate system events report"""
        event_summary = {}
        severity_distribution = {}
        hourly_distribution = {}
        
        for event in events:
            # Event type summary
            event_summary[event.event_type] = event_summary.get(event.event_type, 0) + 1
            
            # Severity distribution
            severity_distribution[event.severity] = severity_distribution.get(event.severity, 0) + 1
            
            # Hourly distribution
            hour = event.timestamp.hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
        
        return {
            "total_events": len(events),
            "event_type_summary": event_summary,
            "severity_distribution": severity_distribution,
            "hourly_distribution": hourly_distribution
        }
    
    async def generate_security_report(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Generate security-focused report"""
        security_events = [
            event for event in events
            if event.event_type in [
                "user_login", "user_logout", "permission_granted",
                "permission_revoked", "security_violation"
            ] or event.severity in ["high", "critical"]
        ]
        
        failed_logins = {}
        ip_analysis = {}
        critical_events = []
        
        for event in security_events:
            # Failed login tracking
            if event.event_type == "user_login" and event.status == "failure":
                ip = event.ip_address or "unknown"
                failed_logins[ip] = failed_logins.get(ip, 0) + 1
            
            # IP address analysis
            if event.ip_address:
                if event.ip_address not in ip_analysis:
                    ip_analysis[event.ip_address] = {
                        "total_events": 0,
                        "unique_users": set(),
                        "event_types": set(),
                        "suspicious_activity": False
                    }
                
                analysis = ip_analysis[event.ip_address]
                analysis["total_events"] += 1
                if event.user_id:
                    analysis["unique_users"].add(str(event.user_id))
                analysis["event_types"].add(event.event_type)
                
                # Mark as suspicious if multiple failed attempts
                if event.event_type == "user_login" and event.status == "failure":
                    if analysis["total_events"] > 5:  # Threshold for suspicious activity
                        analysis["suspicious_activity"] = True
            
            # Critical events
            if event.severity == "critical":
                critical_events.append({
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "description": event.description,
                    "user_id": str(event.user_id) if event.user_id else None,
                    "ip_address": event.ip_address
                })
        
        # Convert sets to lists for JSON serialization
        for analysis in ip_analysis.values():
            analysis["unique_users"] = list(analysis["unique_users"])
            analysis["event_types"] = list(analysis["event_types"])
        
        return {
            "total_security_events": len(security_events),
            "failed_login_attempts": failed_logins,
            "ip_address_analysis": ip_analysis,
            "critical_events": critical_events,
            "security_summary": {
                "high_risk_ips": [
                    ip for ip, analysis in ip_analysis.items()
                    if analysis["suspicious_activity"]
                ],
                "total_critical_events": len(critical_events),
                "total_failed_logins": sum(failed_logins.values())
            }
        }
    
    async def generate_compliance_report_data(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Generate compliance-focused report"""
        compliance_summary = {
            "data_access_events": 0,
            "data_modification_events": 0,
            "user_management_events": 0,
            "permission_changes": 0,
            "retention_compliance": {"compliant": 0, "non_compliant": 0},
            "encryption_compliance": {"encrypted": 0, "unencrypted": 0}
        }
        
        data_access_patterns = {}
        retention_analysis = {}
        
        current_time = datetime.utcnow()
        
        for event in events:
            # Categorize events for compliance
            if event.event_type in ["data_access", "file_downloaded"]:
                compliance_summary["data_access_events"] += 1
            
            if event.event_type in ["data_created", "data_updated", "data_deleted"]:
                compliance_summary["data_modification_events"] += 1
            
            if event.event_type in ["user_created", "user_updated", "user_deleted"]:
                compliance_summary["user_management_events"] += 1
            
            if event.event_type in ["permission_granted", "permission_revoked"]:
                compliance_summary["permission_changes"] += 1
            
            # Retention compliance check
            if event.retention_date > current_time:
                compliance_summary["retention_compliance"]["compliant"] += 1
            else:
                compliance_summary["retention_compliance"]["non_compliant"] += 1
            
            # Encryption compliance
            if event.encrypted_payload:
                compliance_summary["encryption_compliance"]["encrypted"] += 1
            else:
                compliance_summary["encryption_compliance"]["unencrypted"] += 1
            
            # Data access patterns for compliance monitoring
            if event.resource_type and event.resource_id:
                resource_key = f"{event.resource_type}:{event.resource_id}"
                if resource_key not in data_access_patterns:
                    data_access_patterns[resource_key] = {
                        "access_count": 0,
                        "unique_users": set(),
                        "access_methods": set(),
                        "last_access": event.timestamp
                    }
                
                pattern = data_access_patterns[resource_key]
                pattern["access_count"] += 1
                if event.user_id:
                    pattern["unique_users"].add(str(event.user_id))
                pattern["access_methods"].add(event.action)
                
                if event.timestamp > pattern["last_access"]:
                    pattern["last_access"] = event.timestamp
        
        # Convert sets to lists and timestamps to ISO format
        for pattern in data_access_patterns.values():
            pattern["unique_users"] = list(pattern["unique_users"])
            pattern["access_methods"] = list(pattern["access_methods"])
            pattern["last_access"] = pattern["last_access"].isoformat()
        
        return {
            "compliance_summary": compliance_summary,
            "data_access_patterns": data_access_patterns,
            "compliance_score": self._calculate_compliance_score(compliance_summary),
            "recommendations": self._generate_compliance_recommendations(compliance_summary)
        }
    
    def _calculate_compliance_score(self, summary: Dict[str, Any]) -> float:
        """Calculate overall compliance score (0-100)"""
        total_events = (
            summary["retention_compliance"]["compliant"] +
            summary["retention_compliance"]["non_compliant"]
        )
        
        if total_events == 0:
            return 100.0
        
        # Weight different factors
        retention_score = (summary["retention_compliance"]["compliant"] / total_events) * 100
        encryption_score = (
            summary["encryption_compliance"]["encrypted"] /
            (summary["encryption_compliance"]["encrypted"] + summary["encryption_compliance"]["unencrypted"])
        ) * 100 if (summary["encryption_compliance"]["encrypted"] + summary["encryption_compliance"]["unencrypted"]) > 0 else 100
        
        # Overall weighted score
        compliance_score = (retention_score * 0.6) + (encryption_score * 0.4)
        return round(compliance_score, 2)
    
    def _generate_compliance_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """Generate compliance recommendations based on analysis"""
        recommendations = []
        
        # Retention compliance
        if summary["retention_compliance"]["non_compliant"] > 0:
            recommendations.append(
                f"Archive or delete {summary['retention_compliance']['non_compliant']} "
                "events that have exceeded retention period"
            )
        
        # Encryption compliance
        unencrypted_count = summary["encryption_compliance"]["unencrypted"]
        if unencrypted_count > 0:
            recommendations.append(
                f"Consider encrypting {unencrypted_count} events containing sensitive data"
            )
        
        # Access patterns
        if summary["data_access_events"] > summary["data_modification_events"] * 10:
            recommendations.append(
                "High read-to-write ratio detected - consider implementing read access controls"
            )
        
        if not recommendations:
            recommendations.append("All compliance checks passed - maintain current practices")
        
        return recommendations

# ===============================================================================
# FASTAPI INTEGRATION
# ===============================================================================

def create_audit_router(audit_logger: ProductionAuditLogger) -> Any:
    """Create FastAPI router for audit endpoints"""
    from fastapi import APIRouter, Depends, Query
    from typing import List as TypingList
    
    router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
    
    @router.get("/health")
    async def audit_health_check():
        """Audit system health check"""
        return await audit_logger.get_health_status()
    
    @router.post("/events", response_model=Dict[str, str])
    async def create_audit_event(
        event: AuditEventRequest,
        request: Request,
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Create a new audit event"""
        context = await create_audit_context(request=request, user=current_user)
        event_id = await audit_logger.log_event(event, context)
        return {"event_id": event_id, "status": "created"}
    
    @router.get("/events", response_model=TypingList[AuditEventResponse])
    async def search_audit_events(
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        event_types: Optional[str] = Query(None),
        severities: Optional[str] = Query(None),
        user_id: Optional[str] = Query(None),
        resource_type: Optional[str] = Query(None),
        resource_id: Optional[str] = Query(None),
        search_text: Optional[str] = Query(None),
        limit: int = Query(100, le=1000),
        offset: int = Query(0, ge=0),
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Search audit events with filters"""
        # Parse comma-separated lists
        parsed_event_types = None
        if event_types:
            try:
                parsed_event_types = [AuditEventType(t.strip()) for t in event_types.split(",")]
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"Invalid event type: {str(e)}")
        
        parsed_severities = None
        if severities:
            try:
                parsed_severities = [AuditSeverity(s.strip()) for s in severities.split(",")]
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"Invalid severity: {str(e)}")
        
        search_request = AuditSearchRequest(
            start_date=start_date,
            end_date=end_date,
            event_types=parsed_event_types,
            severities=parsed_severities,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            search_text=search_text,
            limit=limit,
            offset=offset
        )
        
        return await audit_logger.search_events(search_request)
    
    @router.post("/reports", response_model=Dict[str, Any])
    async def generate_audit_report(
        report_request: AuditReportRequest,
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Generate audit compliance report"""
        # Check if user has permission to generate reports
        if "audit_reports" not in current_user.get("permissions", []):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        return await audit_logger.generate_compliance_report(report_request)
    
    @router.get("/metrics")
    async def get_audit_metrics(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        """Get audit system metrics"""
        health_status = await audit_logger.get_health_status()
        return {
            "metrics": health_status.get("metrics", {}),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return router

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_audit_logger() -> ProductionAuditLogger:
    """Initialize audit logger for production use"""
    config = AuditConfig(
        enabled=getattr(settings, 'AUDIT_ENABLED', True),
        encrypt_sensitive_data=getattr(settings, 'AUDIT_ENCRYPT_SENSITIVE', True),
        retention_days=getattr(settings, 'AUDIT_RETENTION_DAYS', 2555),
        batch_processing=getattr(settings, 'AUDIT_BATCH_PROCESSING', True),
        batch_size=getattr(settings, 'AUDIT_BATCH_SIZE', 1000),
        real_time_alerts=getattr(settings, 'AUDIT_REAL_TIME_ALERTS', True),
        compliance_mode=getattr(settings, 'AUDIT_COMPLIANCE_MODE', True),
        max_connections=getattr(settings, 'AUDIT_MAX_CONNECTIONS', 100),
        timeout=getattr(settings, 'AUDIT_TIMEOUT', 30)
    )
    
    audit_logger = ProductionAuditLogger(config)
    await audit_logger._initialize_resources()
    
    return audit_logger

# ===============================================================================
# HEALTH CHECK FUNCTION
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Module health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "audit_logger",
        "version": "4.0"
    }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionAuditLogger",
    "AuditConfig",
    "AuditEventRequest",
    "AuditEventResponse",
    "AuditSearchRequest",
    "AuditReportRequest",
    "AuditEventType",
    "AuditSeverity",
    "AuditStatus",
    "AuditReportGenerator",
    "create_audit_context",
    "sanitize_sensitive_data",
    "validate_audit_integrity",
    "audit_action",
    "create_audit_router",
    "initialize_audit_logger",
    "health_check",
    "AuditLoggingError",
    "AuditSearchError",
    "ReportGenerationError",
    "IntegrityValidationError"
] User and session information
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    username = Column(String(255), nullable=True)
    session_id = Column(String(128), nullable=True, index=True)
    
    # Request information
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True)
    
    # Event details
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    
    # Data payload (encrypted if sensitive)
    payload = Column(JSONB, nullable=True)
    encrypted_payload = Column(Text, nullable=True)
    
    # System information
    service_name = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=True)
    environment = Column(String(50), nullable=False, index=True)
    
    # Compliance and integrity
    hash_signature = Column(String(128), nullable=False)
    compliance_tags = Column(JSONB, nullable=True)
    retention_date = Column(DateTime, nullable=False, index=True)
    
    # Processing status
    processed = Column(Boolean, default=False, index=True)
    archived = Column(Boolean, default=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_audit_timestamp_type', 'timestamp', 'event_type'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_severity_status', 'severity', 'status'),
        Index('idx_audit_compliance', 'compliance_tags'),
    )

class AuditEventRequest(BaseModel):
    """Pydantic schema for audit event creation"""
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.LOW
    action: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    resource_type: Optional[str] = Field(None, max_length=100)
    resource_id: Optional[str] = Field(None, max_length=255)
    payload: Optional[Dict[str, Any]] = None
    compliance_tags: Optional[Dict[str, str]] = None
    
    @validator('action')
    def validate_action(cls, v):
        return v.strip().lower()
    
    @validator('description')
    def validate_description(cls, v):
        return v.strip()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class AuditEventResponse(BaseModel):
    """Pydantic schema for audit event responses"""
    event_id: str
    timestamp: datetime
    event_type: str
    severity: str
    status: str
    action: str
    description: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class AuditSearchRequest(BaseModel):
    """Schema for audit event search requests"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    event_types: Optional[List[AuditEventType]] = None
    severities: Optional[List[AuditSeverity]] = None
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    search_text: Optional[str] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

class AuditReportRequest(BaseModel):
    """Schema for audit report generation"""
    report_type: str = Field(..., regex="^(user_activity|system_events|security|compliance)$")
    start_date: datetime
    end_date: datetime
    filters: Optional[Dict[str, Any]] = None
    format: str = Field(default="json", regex="^(json|csv|pdf)$")

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseAuditLogger(ABC):
    """Abstract base class for audit logging implementations"""
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.logger = logger.bind(module=self.__class__.__name__)
        self._encryption_key = None
        self._redis_client = None
        self._health_status = True
    
    @abstractmethod
    async def log_event(self, event: AuditEventRequest, context: Dict[str, Any]) -> str:
        """Log an audit event"""
        pass
    
    @abstractmethod
    async def search_events(self, search: AuditSearchRequest) -> List[AuditEventResponse]:
        """Search audit events"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup audit logger resources"""
        pass

class ProductionAuditLogger(BaseAuditLogger):
    """Production-ready audit logger implementation"""
    
    def __init__(self, config: AuditConfig):
        super().__init__(config)
        self._db_session_factory = None
        self._event_queue = asyncio.Queue(maxsize=10000)
        self._processing_task = None
        self._metrics = {
            "events_logged": 0,
            "events_processed": 0,
            "processing_errors": 0,
            "queue_size": 0
        }
    
    async def _initialize_resources(self) -> None:
        """Initialize all required resources"""
        try:
            await self._setup_database()
            await self._setup_redis()
            await self._setup_encryption()
            await self._start_background_processing()
            self.logger.info("Audit logger initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize audit logger", error=str(e))
            raise
    
    async def _setup_database(self) -> None:
        """Setup database connection and ensure tables exist"""
        from database.connection import get_async_engine
        
        engine = get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        self._db_session_factory = get_db_session
        self.logger.debug("Database setup complete")
    
    async def _setup_redis(self) -> None:
        """Setup Redis connection for caching and real-time features"""
        try:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            await self._redis_client.ping()
            self.logger.debug("Redis connection established")
        except Exception as e:
            self.logger.warning("Redis connection failed, continuing without cache", error=str(e))
            self._redis_client = None
    
    async def _setup_encryption(self) -> None:
        """Setup encryption for sensitive data"""
        if self.config.encrypt_sensitive_data:
            encryption_key = os.getenv("AUDIT_ENCRYPTION_KEY")
            if not encryption_key:
                # Generate new key for development
                encryption_key = Fernet.generate_key().decode()
                self.logger.warning("Generated new encryption key - store securely for production")
            
            self._encryption_key = Fernet(encryption_key.encode())
            self.logger.debug("Encryption setup complete")
    
    async def _start_background_processing(self) -> None:
        """Start background task for processing audit events"""
        if self.config.batch_processing:
            self._processing_task = asyncio.create_task(self._process_event_queue())
            self.logger.debug("Background processing started")
    
    @track_performance
    async def log_event(
        self,
        event: AuditEventRequest,
        context: Dict[str, Any]
    ) -> str:
        """
        Log an audit event with comprehensive context capture.
        
        Args:
            event: Audit event data to log
            context: Additional context including request info, user data
            
        Returns:
            str: Unique event ID for tracking
            
        Raises:
            AuditLoggingError: When event logging fails
        """
        try:
            # Generate unique event ID
            event_id = self._generate_event_id()
            
            # Extract context information
            user_info = context.get("user", {})
            request_info = context.get("request", {})
            system_info = context.get("system", {})
            
            # Create audit event record
            audit_event = AuditEvent(
                event_id=event_id,
                timestamp=datetime.utcnow(),
                event_type=event.event_type.value,
                severity=event.severity.value,
                status=AuditStatus.SUCCESS.value,
                
                # User information
                user_id=user_info.get("user_id"),
                username=user_info.get("username"),
                session_id=user_info.get("session_id"),
                
                # Request information
                ip_address=request_info.get("ip_address"),
                user_agent=request_info.get("user_agent"),
                request_method=request_info.get("method"),
                request_path=request_info.get("path"),
                
                # Event details
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                action=event.action,
                description=event.description,
                
                # System information
                service_name=system_info.get("service_name", "ymera"),
                version=system_info.get("version", "4.0"),
                environment=settings.ENVIRONMENT,
                
                # Compliance
                compliance_tags=event.compliance_tags or {},
                retention_date=datetime.utcnow() + timedelta(days=self.config.retention_days)
            )
            
            # Handle payload encryption if needed
            if event.payload:
                if self._should_encrypt_payload(event):
                    audit_event.encrypted_payload = self._encrypt_payload(event.payload)
                else:
                    audit_event.payload = event.payload
            
            # Generate integrity hash
            audit_event.hash_signature = self._generate_hash(audit_event)
            
            # Queue for processing or process immediately
            if self.config.batch_processing:
                await self._queue_event(audit_event)
            else:
                await self._store_event_immediately(audit_event)
            
            # Update metrics
            self._metrics["events_logged"] += 1
            
            # Real-time alerts for critical events
            if event.severity == AuditSeverity.CRITICAL:
                await self._send_real_time_alert(audit_event)
            
            self.logger.info(
                "Audit event logged",
                event_id=event_id,
                event_type=event.event_type.value,
                severity=event.severity.value
            )
            
            return event_id
            
        except Exception as e:
            self.logger.error("Failed to log audit event", error=str(e), event_type=event.event_type.value)
            self._metrics["processing_errors"] += 1
            raise AuditLoggingError(f"Failed to log audit event: {str(e)}")
    
    async def search_events(self, search: AuditSearchRequest) -> List[AuditEventResponse]:
        """
        Search audit events with comprehensive filtering.
        
        Args:
            search: Search criteria and filters
            
        Returns:
            List of matching audit events
            
        Raises:
            AuditSearchError: When search operation fails
        """
        try:
            async with self._db_session_factory() as session:
                query = session.query(AuditEvent)
                
                # Apply filters
                if search.start_date:
                    query = query.filter(AuditEvent.timestamp >= search.start_date)
                
                if search.end_date:
                    query = query.filter(AuditEvent.timestamp <= search.end_date)
                
                if search.event_types:
                    query = query.filter(AuditEvent.event_type.in_([t.value for t in search.event_types]))
                
                if search.severities:
                    query = query.filter(AuditEvent.severity.in_([s.value for s in search.severities]))
                
                if search.user_id:
                    query = query.filter(AuditEvent.user_id == search.user_id)
                
                if search.resource_type:
                    query = query.filter(AuditEvent.resource_type == search.resource_type)
                
                if search.resource_id:
                    query = query.filter(AuditEvent.resource_id == search.resource_id)
                
                if search.search_text:
                    search_filter = f"%{search.search_text}%"
                    query = query.filter(
                        AuditEvent.description.ilike(search_filter) |
                        AuditEvent.action.ilike(search_filter)
                    )
                
                # Apply pagination
                query = query.order_by(AuditEvent.timestamp.desc())
                query = query.offset(search.offset).limit(search.limit)
                
                # Execute query
                results = await query.all()
                
                # Convert to response format
                events = []
                for event in results:
                    events.append(AuditEventResponse(
                        event_id=event.event_id,
                        timestamp=event.timestamp,
                        event_type=event.event_type,
                        severity=event.severity,
                        status=event.status,
                        action=event.action,
                        description=event.description,
                        user_id=str(event.user_id) if event.user_id else None,
                        username=event.username,
                        resource_type=event.resource_type,
                        resource_id=event.resource_id
                    ))
                
                self.logger.debug("Audit search completed", results_count=len(events))
                return events
                
        except Exception as e:
            self.logger.error("Audit search failed", error=str(e))
            raise AuditSearchError(f"Search operation failed: {str(e)}")
    
    async def generate_compliance_report(
        self,
        request: AuditReportRequest
    ) -> Dict[str, Any]:
        """
        Generate compliance reports for audit events.
        
        Args:
            request: Report generation parameters
            
        Returns:
            Generated report data
            
        Raises:
            ReportGenerationError: When report generation fails
        """
        try:
            async with self._db_session_factory() as session:
                # Base query
                query = session.query(AuditEvent).filter(
                    AuditEvent.timestamp >= request.start_date,
                    AuditEvent.timestamp <= request.end_date
                )
                
                # Apply filters
                if request.filters:
                    for key, value in request.filters.items():
                        if hasattr(AuditEvent, key):
                            query = query.filter(getattr(AuditEvent, key) == value)
                
                events = await query.all()
                
                # Generate report based on type
                if request.report_type == "user_activity":
                    report_data = await self._generate_user_activity_report(events)
                elif request.report_type == "system_events":
                    report_data = await self._generate_system_events_report(events)
                elif request.report_type == "security":
                    report_data = await self._generate_security_report(events)
                elif request.report_type == "compliance":
                    report_data = await self._generate_compliance_report_data(events)
                else:
                    raise ValueError(f"Unknown report type: {request.report_type}")
                
                report = {
                    "report_id": str(uuid.uuid4()),
                    "generated_at": datetime.utcnow().isoformat(),
                    "report_type": request.report_type,
                    "period": {
                        "start_date": request.start_date.isoformat(),
                        "end_date": request.end_date.isoformat()
                    },
                    "total_events": len(events),
                    "data": report_data
                }
                
                self.logger.info("Compliance report generated", report_type=request.report_type)
                return report
                
        except Exception as e:
            self.logger.error("Report generation failed", error=str(e))
            raise ReportGenerationError(f"Failed to generate report: {str(e)}")
    
    async def _process_event_queue(self) -> None:
        """Background task to process queued audit events"""
        batch = []
        
        while True:
            try:
                # Collect events for batch processing
                timeout = 5.0  # Process every 5 seconds or when batch is full
                
                while len(batch) < self.config.batch_size:
                    try:
                        event = await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
                        batch.append(event)
                    except asyncio.TimeoutError:
                        break
                
                # Process batch if we have events
                if batch:
                    await self._store_events_batch(batch)
                    self._metrics["events_processed"] += len(batch)
                    batch.clear()
                
                # Update queue size metric
                self._metrics["queue_size"] = self._event_queue.qsize()
                
            except Exception as e:
                self.logger.error("Error in event queue processing", error=str(e))
                self._metrics["processing_errors"] += 1
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _queue_event(self, event: AuditEvent) -> None:
        """Queue an event for batch processing"""
        try:
            await self._event_queue.put(event)
        except asyncio.QueueFull:
            # If queue is full, store immediately to prevent data loss
            await self._store_event_immediately(event)
            self.logger.warning("Event queue full, stored event immediately")
    
    async def _store_event_immediately(self, event: AuditEvent) -> None:
        """Store a single event immediately"""
        async with self._db_session_factory() as session:
            try:
                session.add(event)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise
    
    async def _store_events_batch(self, events: List[AuditEvent]) -> None:
        """Store a batch of events efficiently"""
        async with self._db_session_factory() as session:
            try:
                session.add_all(events)
                await session.commit()
                self.logger.debug("Stored audit events batch", count=len(events))
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store events batch", error=str(e))
                raise
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"audit_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:12]}"
    
    def _should_encrypt_payload(self, event: AuditEventRequest) -> bool:
        """Determine if payload should be encrypted"""
        if not self.config.encrypt_sensitive_data or not self._encryption_key:
            return False
        
        # Encrypt sensitive event types
        sensitive_events = {
            AuditEventType.USER_LOGIN,
            AuditEventType.USER_CREATED,
            AuditEventType.USER_UPDATED,
            AuditEventType.PERMISSION_GRANTED,
            AuditEventType.SECURITY_VIOLATION
        }
        
        return event.event_type in sensitive_events
    
    def _encrypt_payload(self, payload: Dict[str, Any]) -> str:
        """Encrypt sensitive payload data"""
        try:
            payload_json = json.dumps(payload, default=str)
            encrypted = self._encryption_key.encrypt(payload_json.encode())
            return encrypted.decode()
        except Exception as e:
            self.logger.error("Payload encryption failed", error=str(e))
            raise
    
    def _decrypt_payload(self, encrypted_payload: str) -> Dict[str, Any]:
        """Decrypt encrypted payload data"""
        try:
            decrypted = self._encryption_key.decrypt(encrypted_payload.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            self.logger.error("Payload decryption failed", error=str(e))
            raise
    
    def _generate_hash(self, event: AuditEvent) -> str:
        """Generate integrity hash for audit event"""
        hash_data = f"{event.event_id}{event.timestamp}{event.event_type}{event.action}{event.description}"
        return hashlib.sha256(hash_data.encode()).hexdigest()
    
    async def _send_real_time_alert(self, event: AuditEvent) -> None:
        """Send real-time alerts for critical events"""
        if not self.config.real_time_alerts:
            return
        
        try:
            alert_data = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "severity": event.severity,
                "description": event.description,
                "user_id": str(event.user_id) if event.user_id else None,
                "ip_address": event.ip_address
            }
            
            # Send to Redis for real-time processing
            if self._redis_client:
                await self._redis_client.publish("audit_alerts", json.dumps(alert_data))
            
            self.logger.warning(
                "Critical audit event alert",
                event_id=event.event_id,
                event_type=event.event_type,
                severity=event.severity
            )
            
        except Exception as e:
            self.logger.error("Failed to send real-time alert", error=str(e))
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get audit logger health status"""
        try:
            # Check database connectivity
            db_healthy = True
            try:
                async with self._db_session_factory() as session:
                    await session.execute("SELECT 1")
            except Exception:
                db_healthy = False
            
            # Check Redis connectivity
            redis_healthy = True
            if self._redis_client:
                try:
                    await self._redis_client.ping()
                except Exception:
                    redis_healthy = False
            
            # Check queue status
            queue_healthy = True
            if self.config.batch_processing:
                queue_size = self._event_queue.qsize()
                if queue_size > self.config.batch_size * 5:  # Queue too large
                    queue_healthy = False
            
            overall_status = "healthy" if all([db_healthy, redis_healthy, queue_healthy]) else "degraded"
            
            return {
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "redis": "healthy" if redis_healthy else "unhealthy",
                    "event_queue": "healthy" if queue_healthy else "unhealthy"
                },
                "metrics": self._metrics.copy(),
                "configuration": {
                    "batch_processing": self.config.batch_processing,
                    "encryption_enabled": self.config.encrypt_sensitive_data,
                    "retention_days": self.config.retention_days,
                    "real_time_alerts": self.config.real_time_alerts
                }
            }
            
        except Exception as e:
            self.logger.error("Health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def cleanup(self) -> None:
        """Cleanup audit logger resources"""
        try:
            # Stop background processing
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
            
            # Process remaining events in queue
            remaining_events = []
            while not self._event_queue.empty():
                try:
                    event = self._event_queue.get_nowait()
                    remaining_events.append(event)
                except asyncio.QueueEmpty:
                    break
            
            if remaining_events:
                await self._store_events_batch(remaining_events)
                self.logger.info("Processed remaining events during cleanup", count=len(remaining_events))
            
            # Close Redis connection
            if self._redis_client:
                await self._redis_client.close()
            
            self.logger.info("Audit logger cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))
            raise

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def create_audit_context(
    request: Optional[Request] = None,
    user: Optional[Dict[str, Any]] = None,
    system_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create comprehensive audit context from request and user information.
    
    Args:
        request: FastAPI request object
        user: User information dictionary
        system_info: Additional system information
        
    Returns:
        Complete audit context dictionary
    """
    context = {
        "user": {},
        "request": {},
        "system": {}
    }
    
    #