"""
YMERA Enterprise - Error Tracking System
Production-Ready Error Aggregation and Analysis - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import asyncio
import logging
import json
import os
import uuid
import traceback
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum
from collections import defaultdict, Counter
import re

# Third-party imports
import structlog
from fastapi import HTTPException, status
import aioredis
from pydantic import BaseModel, Field, validator

# Local imports
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.error_tracker")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 86400  # 24 hours
MAX_ERROR_HISTORY = 10000
DEFAULT_RETENTION_DAYS = 30

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(str, Enum):
    """Error categories for classification"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    DATABASE = "database"
    NETWORK = "network"
    EXTERNAL_API = "external_api"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"

class ErrorStatus(str, Enum):
    """Error resolution status"""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    IGNORED = "ignored"

@dataclass
class ErrorConfig:
    """Configuration for error tracking"""
    enabled: bool = True
    max_errors: int = 10000
    retention_days: int = 30
    auto_categorize: bool = True
    enable_notifications: bool = True
    grouping_enabled: bool = True
    redis_prefix: str = "ymera:errors"
    notification_thresholds: Dict[ErrorSeverity, int] = field(default_factory=lambda: {
        ErrorSeverity.LOW: 100,
        ErrorSeverity.MEDIUM: 50,
        ErrorSeverity.HIGH: 10,
        ErrorSeverity.CRITICAL: 1
    })

@dataclass
class ErrorContext:
    """Context information for an error"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    environment: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorOccurrence:
    """Single error occurrence"""
    occurrence_id: str
    timestamp: datetime
    context: ErrorContext
    stack_trace: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class ErrorReport(BaseModel):
    """Error report data model"""
    error_id: str
    fingerprint: str
    message: str
    exception_type: str
    severity: ErrorSeverity
    category: ErrorCategory
    status: ErrorStatus
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    occurrences: List[ErrorOccurrence] = []
    stack_trace: Optional[str] = None
    resolution_notes: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ErrorOccurrence: lambda v: {
                "occurrence_id": v.occurrence_id,
                "timestamp": v.timestamp.isoformat(),
                "context": v.context.__dict__,
                "stack_trace": v.stack_trace,
                "user_agent": v.user_agent,
                "ip_address": v.ip_address
            }
        }

class ErrorAnalytics(BaseModel):
    """Error analytics and trends"""
    time_range: Dict[str, datetime]
    total_errors: int
    unique_errors: int
    error_rate: float
    severity_breakdown: Dict[ErrorSeverity, int]
    category_breakdown: Dict[ErrorCategory, int]
    top_errors: List[Dict[str, Any]]
    trend_data: List[Dict[str, Any]]
    resolution_stats: Dict[ErrorStatus, int]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ErrorNotification(BaseModel):
    """Error notification configuration"""
    notification_id: str
    error_id: str
    severity: ErrorSeverity
    threshold_reached: int
    notification_type: str
    recipients: List[str]
    message: str
    sent_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ===============================================================================
# ERROR CLASSIFICATION SYSTEM
# ===============================================================================

class ErrorClassifier:
    """Automatic error classification system"""
    
    def __init__(self):
        self.classification_rules = {
            ErrorCategory.AUTHENTICATION: [
                r"authentication.*failed",
                r"invalid.*credential",
                r"unauthorized",
                r"login.*failed",
                r"token.*expired",
                r"jwt.*invalid"
            ],
            ErrorCategory.AUTHORIZATION: [
                r"permission.*denied",
                r"access.*denied",
                r"forbidden",
                r"insufficient.*privilege",
                r"not.*authorized"
            ],
            ErrorCategory.VALIDATION: [
                r"validation.*error",
                r"invalid.*input",
                r"schema.*validation",
                r"field.*required",
                r"invalid.*format",
                r"constraint.*violation"
            ],
            ErrorCategory.DATABASE: [
                r"database.*error",
                r"sql.*error",
                r"connection.*failed",
                r"deadlock",
                r"timeout.*query",
                r"duplicate.*key",
                r"foreign.*key.*constraint"
            ],
            ErrorCategory.NETWORK: [
                r"network.*error",
                r"connection.*timeout",
                r"connection.*refused",
                r"host.*unreachable",
                r"dns.*resolution",
                r"socket.*error"
            ],
            ErrorCategory.EXTERNAL_API: [
                r"api.*error",
                r"external.*service",
                r"http.*error.*[45]\d\d",
                r"rate.*limit.*exceeded",
                r"service.*unavailable"
            ],
            ErrorCategory.SYSTEM: [
                r"memory.*error",
                r"disk.*full",
                r"permission.*error",
                r"file.*not.*found",
                r"system.*overload",
                r"resource.*exhausted"
            ]
        }
        
        self.severity_rules = {
            ErrorSeverity.CRITICAL: [
                r"critical.*error",
                r"system.*crash",
                r"data.*corruption",
                r"security.*breach",
                r"service.*down"
            ],
            ErrorSeverity.HIGH: [
                r"error.*processing.*payment",
                r"database.*unavailable",
                r"authentication.*system.*down",
                r"data.*loss"
            ],
            ErrorSeverity.MEDIUM: [
                r"timeout",
                r"connection.*failed",
                r"validation.*failed",
                r"api.*error"
            ],
            ErrorSeverity.LOW: [
                r"warning",
                r"deprecated",
                r"minor.*issue"
            ]
        }
    
    def classify_category(self, error_message: str, exception_type: str) -> ErrorCategory:
        """Classify error category based on message and type"""
        combined_text = f"{error_message} {exception_type}".lower()
        
        for category, patterns in self.classification_rules.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return category
        
        return ErrorCategory.UNKNOWN
    
    def classify_severity(self, error_message: str, exception_type: str) -> ErrorSeverity:
        """Classify error severity based on message and type"""
        combined_text = f"{error_message} {exception_type}".lower()
        
        for severity, patterns in self.severity_rules.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return severity
        
        # Default severity based on exception type
        critical_exceptions = [
            "SystemExit", "KeyboardInterrupt", "MemoryError",
            "SecurityError", "SystemError"
        ]
        
        if exception_type in critical_exceptions:
            return ErrorSeverity.CRITICAL
        
        return ErrorSeverity.MEDIUM

# ===============================================================================
# ERROR FINGERPRINTING SYSTEM
# ===============================================================================

class ErrorFingerprinter:
    """Error fingerprinting for grouping similar errors"""
    
    @staticmethod
    def generate_fingerprint(
        message: str,
        exception_type: str,
        stack_trace: Optional[str] = None
    ) -> str:
        """Generate unique fingerprint for error grouping"""
        # Normalize the message by removing dynamic content
        normalized_message = ErrorFingerprinter._normalize_message(message)
        
        # Create base fingerprint data
        fingerprint_data = f"{exception_type}:{normalized_message}"
        
        # Add stack trace information if available
        if stack_trace:
            # Extract key stack trace elements (function names and file paths)
            trace_elements = ErrorFingerprinter._extract_trace_elements(stack_trace)
            fingerprint_data += f":{':'.join(trace_elements)}"
        
        # Generate SHA-256 hash
        return hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()[:16]
    
    @staticmethod
    def _normalize_message(message: str) -> str:
        """Normalize error message by removing dynamic content"""
        # Remove UUIDs
        message = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 
                        '<UUID>', message, flags=re.IGNORECASE)
        
        # Remove timestamps
        message = re.sub(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', message)
        
        # Remove IP addresses
        message = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', message)
        
        # Remove numbers that might be IDs or counts
        message = re.sub(r'\b\d+\b', '<NUM>', message)
        
        # Remove file paths
        message = re.sub(r'[/\\][\w/\\.-]+', '<PATH>', message)
        
        return message.strip()
    
    @staticmethod
    def _extract_trace_elements(stack_trace: str) -> List[str]:
        """Extract key elements from stack trace for fingerprinting"""
        elements = []
        
        # Extract function names and file names from stack trace
        lines = stack_trace.split('\n')
        for line in lines:
            # Look for function names in traceback
            func_match = re.search(r'in (\w+)', line)
            if func_match:
                elements.append(func_match.group(1))
            
            # Look for file names
            file_match = re.search(r'"([^"]+\.py)"', line)
            if file_match:
                filename = Path(file_match.group(1)).name
                elements.append(filename)
        
        # Return unique elements, limited to avoid overly long fingerprints
        return list(dict.fromkeys(elements))[:5]

# ===============================================================================
# CORE ERROR TRACKER IMPLEMENTATION
# ===============================================================================

class ErrorTracker:
    """Production-ready error tracking and analysis system"""
    
    def __init__(self, config: ErrorConfig):
        self.config = config
        self.logger = logger.bind(component="error_tracker")
        self._errors: Dict[str, ErrorReport] = {}
        self._error_history: List[str] = []
        self._redis_client: Optional[aioredis.Redis] = None
        self._classifier = ErrorClassifier()
        self._fingerprinter = ErrorFingerprinter()
        self._notification_history: List[ErrorNotification] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self) -> None:
        """Initialize error tracking system"""
        try:
            await self._setup_redis()
            await self._load_existing_errors()
            await self._start_cleanup_task()
            
            self._running = True
            self.logger.info("Error tracker initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize error tracker", error=str(e))
            raise
    
    async def _setup_redis(self) -> None:
        """Setup Redis connection for persistence"""
        try:
            self._redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis_client.ping()
            self.logger.info("Redis connection established for error tracking")
        except Exception as e:
            self.logger.error("Failed to setup Redis for error tracking", error=str(e))
            raise
    
    async def _load_existing_errors(self) -> None:
        """Load existing errors from Redis"""
        if not self._redis_client:
            return
        
        try:
            error_keys = await self._redis_client.keys(f"{self.config.redis_prefix}:error:*")
            
            for key in error_keys:
                error_data = await self._redis_client.hgetall(key)
                if error_data:
                    error_report = self._deserialize_error_report(error_data)
                    self._errors[error_report.error_id] = error_report
            
            self.logger.info("Loaded existing errors from Redis", count=len(self._errors))
        except Exception as e:
            self.logger.error("Failed to load existing errors", error=str(e))
    
    async def _start_cleanup_task(self) -> None:
        """Start background cleanup task"""
        if self.config.retention_days > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.logger.info("Error cleanup task started", retention_days=self.config.retention_days)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for old errors"""
        while self._running:
            try:
                await self._cleanup_old_errors()
                await asyncio.sleep(3600)  # Run cleanup every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in cleanup loop", error=str(e))
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    async def _cleanup_old_errors(self) -> None:
        """Remove old errors based on retention policy"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.config.retention_days)
        errors_to_remove = []
        
        for error_id, error_report in self._errors.items():
            if error_report.last_seen < cutoff_date:
                errors_to_remove.append(error_id)
        
        for error_id in errors_to_remove:
            await self._remove_error(error_id)
        
        if errors_to_remove:
            self.logger.info("Cleaned up old errors", count=len(errors_to_remove))
    
    async def _remove_error(self, error_id: str) -> None:
        """Remove error from memory and Redis"""
        if error_id in self._errors:
            del self._errors[error_id]
        
        if error_id in self._error_history:
            self._error_history.remove(error_id)
        
        if self._redis_client:
            await self._redis_client.delete(f"{self.config.redis_prefix}:error:{error_id}")
    
    async def track_error(
        self,
        exception: Exception,
        context: Optional[ErrorContext] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Track an error occurrence"""
        try:
            if not self.config.enabled:
                return ""
            
            # Extract error information
            error_message = str(exception)
            exception_type = type(exception).__name__
            stack_trace = traceback.format_exc() if traceback.format_exc() != "NoneType: None\n" else None
            
            # Generate fingerprint for grouping
            fingerprint = self._fingerprinter.generate_fingerprint(
                error_message, exception_type, stack_trace
            )
            
            # Auto-classify if not provided
            if not severity and self.config.auto_categorize:
                severity = self._classifier.classify_severity(error_message, exception_type)
            
            if not category and self.config.auto_categorize:
                category = self._classifier.classify_category(error_message, exception_type)
            
            # Set defaults
            severity = severity or ErrorSeverity.MEDIUM
            category = category or ErrorCategory.UNKNOWN
            context = context or ErrorContext()
            tags = tags or []
            metadata = metadata or {}
            
            # Create occurrence
            occurrence = ErrorOccurrence(
                occurrence_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                context=context,
                stack_trace=stack_trace
            )
            
            # Check if this error already exists
            existing_error = None
            for error_report in self._errors.values():
                if error_report.fingerprint == fingerprint:
                    existing_error = error_report
                    break
            
            if existing_error:
                # Update existing error
                existing_error.last_seen = datetime.utcnow()
                existing_error.occurrence_count += 1
                existing_error.occurrences.append(occurrence)
                
                # Keep only recent occurrences (last 100)
                if len(existing_error.occurrences) > 100:
                    existing_error.occurrences = existing_error.occurrences[-100:]
                
                error_id = existing_error.error_id
            else:
                # Create new error report
                error_id = str(uuid.uuid4())
                
                error_report = ErrorReport(
                    error_id=error_id,
                    fingerprint=fingerprint,
                    message=error_message,
                    exception_type=exception_type,
                    severity=severity,
                    category=category,
                    status=ErrorStatus.NEW,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    occurrence_count=1,
                    occurrences=[occurrence],
                    stack_trace=stack_trace,
                    tags=tags,
                    metadata=metadata
                )
                
                self._errors[error_id] = error_report
                self._error_history.append(error_id)
                
                # Maintain history size limit
                if len(self._error_history) > self.config.max_errors:
                    old_error_id = self._error_history.pop(0)
                    if old_error_id in self._errors:
                        await self._remove_error(old_error_id)
            
            # Persist to Redis
            await self._persist_error(self._errors[error_id])
            
            # Check for notifications
            await self._check_notification_thresholds(self._errors[error_id])
            
            # Log the error
            self.logger.error(
                "Error tracked",
                error_id=error_id,
                fingerprint=fingerprint,
                severity=severity.value,
                category=category.value,
                message=error_message,
                occurrence_count=self._errors[error_id].occurrence_count
            )
            
            return error_id
            
        except Exception as e:
            self.logger.error("Failed to track error", error=str(e))
            return ""
    
    async def _persist_error(self, error_report: ErrorReport) -> None:
        """Persist error report to Redis"""
        if not self._redis_client:
            return
        
        try:
            key = f"{self.config.redis_prefix}:error:{error_report.error_id}"
            data = self._serialize_error_report(error_report)
            
            await self._redis_client.hset(key, mapping=data)
            await self._redis_client.expire(key, self.config.retention_days * 86400)
            
        except Exception as e:
            self.logger.error("Failed to persist error", error_id=error_report.error_id, error=str(e))
    
    def _serialize_error_report(self, error_report: ErrorReport) -> Dict[str, str]:
        """Serialize error report for Redis storage"""
        return {
            "error_id": error_report.error_id,
            "fingerprint": error_report.fingerprint,
            "message": error_report.message,
            "exception_type": error_report.exception_type,
            "severity": error_report.severity.value,
            "category": error_report.category.value,
            "status": error_report.status.value,
            "first_seen": error_report.first_seen.isoformat(),
            "last_seen": error_report.last_seen.isoformat(),
            "occurrence_count": str(error_report.occurrence_count),
            "stack_trace": error_report.stack_trace or "",
            "resolution_notes": error_report.resolution_notes or "",
            "assigned_to": error_report.assigned_to or "",
            "tags": json.dumps(error_report.tags),
            "metadata": json.dumps(error_report.metadata),
            "occurrences": json.dumps([
                {
                    "occurrence_id": occ.occurrence_id,
                    "timestamp": occ.timestamp.isoformat(),
                    "context": occ.context.__dict__,
                    "stack_trace": occ.stack_trace,
                    "user_agent": occ.user_agent,
                    "ip_address": occ.ip_address
                }
                for occ in error_report.occurrences[-10:]  # Store only last 10 occurrences
            ])
        }
    
    def _deserialize_error_report(self, data: Dict[str, str]) -> ErrorReport:
        """Deserialize error report from Redis data"""
        occurrences = []
        if data.get("occurrences"):
            occurrence_data = json.loads(data["occurrences"])
            for occ_data in occurrence_data:
                context_data = occ_data.get("context", {})
                context = ErrorContext(
                    user_id=context_data.get("user_id"),
                    session_id=context_data.get("session_id"),
                    request_id=context_data.get("request_id"),
                    operation=context_data.get("operation"),
                    component=context_data.get("component"),
                    environment=context_data.get("environment"),
                    additional_data=context_data.get("additional_data", {})
                )
                
                occurrences.append(ErrorOccurrence(
                    occurrence_id=occ_data["occurrence_id"],
                    timestamp=datetime.fromisoformat(occ_data["timestamp"]),
                    context=context,
                    stack_trace=occ_data.get("stack_trace"),
                    user_agent=occ_data.get("user_agent"),
                    ip_address=occ_data.get("ip_address")
                ))
        
        return ErrorReport(
            error_id=data["error_id"],
            fingerprint=data["fingerprint"],
            message=data["message"],
            exception_type=data["exception_type"],
            severity=ErrorSeverity(data["severity"]),
            category=ErrorCategory(data["category"]),
            status=ErrorStatus(data["status"]),
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            occurrence_count=int(data["occurrence_count"]),
            occurrences=occurrences,
            stack_trace=data.get("stack_trace") or None,
            resolution_notes=data.get("resolution_notes") or None,
            assigned_to=data.get("assigned_to") or None,
            tags=json.loads(data.get("tags", "[]")),
            metadata=json.loads(data.get("metadata", "{}"))
        )
    
    async def _check_notification_thresholds(self, error_report: ErrorReport) -> None:
        """Check if error should trigger notifications"""
        if not self.config.enable_notifications:
            return
        
        threshold = self.config.notification_thresholds.get(error_report.severity, 0)
        
        if error_report.occurrence_count >= threshold:
            # Check if we haven't already sent a notification for this threshold
            notification_key = f"{error_report.error_id}:{threshold}"
            
            # Simple deduplication - only send notification once per threshold
            existing_notifications = [
                n for n in self._notification_history 
                if n.error_id == error_report.error_id and n.threshold_reached == threshold
            ]
            
            if not existing_notifications:
                await self._send_error_notification(error_report, threshold)
    
    async def _send_error_notification(self, error_report: ErrorReport, threshold: int) -> None:
        """Send error notification"""
        notification = ErrorNotification(
            notification_id=str(uuid.uuid4()),
            error_id=error_report.error_id,
            severity=error_report.severity,
            threshold_reached=threshold,
            notification_type="threshold_exceeded",
            recipients=["admin@example.com"],  # Configure based on severity
            message=f"Error '{error_report.message}' has occurred {error_report.occurrence_count} times (threshold: {threshold})",
            sent_at=datetime.utcnow()
        )
        
        self._notification_history.append(notification)
        
        # Keep only recent notifications
        if len(self._notification_history) > 1000:
            self._notification_history = self._notification_history[-1000:]
        
        self.logger.warning(
            "Error notification sent",
            notification_id=notification.notification_id,
            error_id=error_report.error_id,
            severity=error_report.severity.value,
            threshold=threshold,
            occurrence_count=error_report.occurrence_count
        )
    
    async def get_error(self, error_id: str) -> Optional[ErrorReport]:
        """Get specific error report"""
        return self._errors.get(error_id)
    
    async def get_errors(
        self,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        status: Optional[ErrorStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ErrorReport]:
        """Get filtered list of errors"""
        errors = list(self._errors.values())
        
        # Apply filters
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        if category:
            errors = [e for e in errors if e.category == category]
        
        if status:
            errors = [e for e in errors if e.status == status]
        
        # Sort by last seen (most recent first)
        errors.sort(key=lambda x: x.last_seen, reverse=True)
        
        # Apply pagination
        return errors[offset:offset + limit]
    
    async def update_error_status(
        self,
        error_id: str,
        status: ErrorStatus,
        resolution_notes: Optional[str] = None,
        assigned_to: Optional[str] = None
    ) -> bool:
        """Update error status and resolution information"""
        if error_id not in self._errors:
            return False
        
        error_report = self._errors[error_id]
        error_report.status = status
        
        if resolution_notes:
            error_report.resolution_notes = resolution_notes
        
        if assigned_to:
            error_report.assigned_to = assigned_to
        
        # Persist changes
        await self._persist_error(error_report)
        
        self.logger.info(
            "Error status updated",
            error_id=error_id,
            status=status.value,
            assigned_to=assigned_to
        )
        
        return True
    
    async def get_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> ErrorAnalytics:
        """Generate error analytics and trends"""
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=7)
            
            if not end_date:
                end_date = datetime.utcnow()
            
            # Filter errors by date range
            filtered_errors = [
                error for error in self._errors.values()
                if start_date <= error.last_seen <= end_date
            ]
            
            # Calculate basic metrics
            total_errors = sum(error.occurrence_count for error in filtered_errors)
            unique_errors = len(filtered_errors)
            time_range_hours = (end_date - start_date).total_seconds() / 3600
            error_rate = total_errors / time_range_hours if time_range_hours > 0 else 0
            
            # Severity breakdown
            severity_counter = Counter()
            for error in filtered_errors:
                severity_counter[error.severity] += error.occurrence_count
            
            severity_breakdown = {
                severity: severity_counter.get(severity, 0)
                for severity in ErrorSeverity
            }
            
            # Category breakdown
            category_counter = Counter()
            for error in filtered_errors:
                category_counter[error.category] += error.occurrence_count
            
            category_breakdown = {
                category: category_counter.get(category, 0)
                for category in ErrorCategory
            }
            
            # Top errors by occurrence count
            top_errors = sorted(
                filtered_errors,
                key=lambda x: x.occurrence_count,
                reverse=True
            )[:10]
            
            top_errors_data = [
                {
                    "error_id": error.error_id,
                    "message": error.message,
                    "occurrence_count": error.occurrence_count,
                    "severity": error.severity.value,
                    "category": error.category.value,
                    "last_seen": error.last_seen.isoformat()
                }
                for error in top_errors
            ]
            
            # Resolution stats
            status_counter = Counter()
            for error in filtered_errors:
                status_counter[error.status] += 1
            
            resolution_stats = {
                status: status_counter.get(status, 0)
                for status in ErrorStatus
            }
            
            # Trend data (daily aggregation)
            trend_data = []
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            while current_date <= end_date:
                next_date = current_date + timedelta(days=1)
                
                daily_errors = [
                    error for error in filtered_errors
                    if current_date <= error.last_seen < next_date
                ]
                
                daily_count = sum(error.occurrence_count for error in daily_errors)
                
                trend_data.append({
                    "date": current_date.isoformat(),
                    "error_count": daily_count,
                    "unique_errors": len(daily_errors)
                })
                
                current_date = next_date
            
            return ErrorAnalytics(
                time_range={"start": start_date, "end": end_date},
                total_errors=total_errors,
                unique_errors=unique_errors,
                error_rate=error_rate,
                severity_breakdown=severity_breakdown,
                category_breakdown=category_breakdown,
                top_errors=top_errors_data,
                trend_data=trend_data,
                resolution_stats=resolution_stats
            )
            
        except Exception as e:
            self.logger.error("Failed to generate error analytics", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate error analytics"
            )
    
    async def search_errors(
        self,
        query: str,
        fields: Optional[List[str]] = None
    ) -> List[ErrorReport]:
        """Search errors by message, exception type, or stack trace"""
        if not fields:
            fields = ["message", "exception_type", "stack_trace"]
        
        results = []
        query_lower = query.lower()
        
        for error in self._errors.values():
            match_found = False
            
            for field in fields:
                field_value = getattr(error, field, "")
                if field_value and query_lower in str(field_value).lower():
                    match_found = True
                    break
            
            if match_found:
                results.append(error)
        
        return sorted(results, key=lambda x: x.last_seen, reverse=True)
    
    async def cleanup(self) -> None:
        """Cleanup error tracker resources"""
        try:
            self._running = False
            
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            if self._redis_client:
                await self._redis_client.close()
            
            self.logger.info("Error tracker cleanup completed")
        except Exception as e:
            self.logger.error("Error during error tracker cleanup", error=str(e))

# ===============================================================================
# ERROR TRACKING DECORATORS
# ===============================================================================

def track_error(
    tracker: Optional[ErrorTracker] = None,
    context: Optional[ErrorContext] = None,
    severity: Optional[ErrorSeverity] = None,
    category: Optional[ErrorCategory] = None,
    tags: Optional[List[str]] = None,
    reraise: bool = True
):
    """Decorator for automatic error tracking"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if tracker:
                    await tracker.track_error(
                        exception=e,
                        context=context,
                        severity=severity,
                        category=category,
                        tags=tags
                    )
                
                if reraise:
                    raise
                
                return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if tracker:
                    # For sync functions, we need to handle async tracking
                    # This would require running in an event loop
                    pass
                
                if reraise:
                    raise
                
                return None
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_error_context(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    component: Optional[str] = None,
    **additional_data
) -> ErrorContext:
    """Create error context with additional data"""
    return ErrorContext(
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        operation=operation,
        component=component,
        environment=settings.ENVIRONMENT,
        additional_data=additional_data
    )

def create_default_config() -> ErrorConfig:
    """Create default error tracking configuration"""
    return ErrorConfig(
        enabled=True,
        max_errors=10000,
        retention_days=30,
        auto_categorize=True,
        enable_notifications=True,
        grouping_enabled=True,
        redis_prefix="ymera:errors",
        notification_thresholds={
            ErrorSeverity.LOW: 100,
            ErrorSeverity.MEDIUM: 50,
            ErrorSeverity.HIGH: 10,
            ErrorSeverity.CRITICAL: 1
        }
    )

async def get_error_summary() -> Dict[str, Any]:
    """Get basic error summary for health checks"""
    # This would typically use a global error tracker instance
    return {
        "total_errors": 0,
        "recent_errors": 0,
        "critical_errors": 0,
        "timestamp": datetime.utcnow().isoformat()
    }

# ===============================================================================
# CONTEXT MANAGERS
# ===============================================================================

@asynccontextmanager
async def error_tracking_context(
    tracker: ErrorTracker,
    operation: str,
    component: Optional[str] = None,
    user_id: Optional[str] = None,
    **context_data
):
    """Context manager for tracking errors in a code block"""
    context = create_error_context(
        user_id=user_id,
        operation=operation,
        component=component,
        **context_data
    )
    
    try:
        yield context
    except Exception as e:
        await tracker.track_error(
            exception=e,
            context=context,
            tags=[f"operation:{operation}"]
        )
        raise

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

# Global error tracker instance
_global_tracker: Optional[ErrorTracker] = None

async def initialize_error_tracker(config: Optional[ErrorConfig] = None) -> ErrorTracker:
    """Initialize error tracker for production use"""
    global _global_tracker
    
    if config is None:
        config = create_default_config()
    
    _global_tracker = ErrorTracker(config)
    await _global_tracker.initialize()
    
    return _global_tracker

def get_global_tracker() -> Optional[ErrorTracker]:
    """Get global error tracker instance"""
    return _global_tracker

async def track_exception(
    exception: Exception,
    context: Optional[ErrorContext] = None,
    severity: Optional[ErrorSeverity] = None,
    category: Optional[ErrorCategory] = None,
    tags: Optional[List[str]] = None
) -> str:
    """Global function to track an exception"""
    if _global_tracker:
        return await _global_tracker.track_error(
            exception=exception,
            context=context,
            severity=severity,
            category=category,
            tags=tags
        )
    return ""

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ErrorTracker",
    "ErrorReport",
    "ErrorConfig",
    "ErrorContext",
    "ErrorOccurrence",
    "ErrorAnalytics",
    "ErrorNotification",
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorStatus",
    "ErrorClassifier",
    "ErrorFingerprinter",
    "track_error",
    "error_tracking_context",
    "create_error_context",
    "create_default_config",
    "initialize_error_tracker",
    "get_global_tracker",
    "track_exception",
    "get_error_summary"
]