"""
YMERA Enterprise Evidence Logger
Production-Ready Comprehensive Logging System for Multi-Agent Environment

Features:
- Structured logging with correlation IDs
- Performance metrics collection
- Agent decision trees and reasoning chains
- Code change tracking and attribution
- Security event logging and alerting
- Compliance audit trails (SOX, GDPR, HIPAA)
- Log aggregation and centralized search
- Real-time log streaming
- Log retention policies and archiving
- Sensitive data redaction and masking
"""

import asyncio
import json
import hashlib
import uuid
import re
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Set
from enum import Enum, auto
from dataclasses import dataclass, asdict, field
from contextlib import asynccontextmanager
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import threading
from concurrent.futures import ThreadPoolExecutor
import gzip
import os
import sys
from pathlib import Path

# Third-party imports
import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch
import structlog
from cryptography.fernet import Fernet
import aiokafka
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import aiofiles
from pydantic import BaseModel, Field, validator
import orjson
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback

# Install rich traceback for better error visualization
install_rich_traceback()

# Constants
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_RETENTION_DAYS = 90
SENSITIVE_PATTERNS = [
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    r'\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b',  # Credit card
    r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',  # SSN
    r'(?i)password["\s]*[:=]["\s]*[^\s"]+',  # Passwords
    r'(?i)token["\s]*[:=]["\s]*[^\s"]+',  # Tokens
    r'(?i)key["\s]*[:=]["\s]*[^\s"]+',  # API keys
    r'\b(?:\d{1,3}\.){3}\d{1,3}\b',  # IP addresses
]

class LogLevel(Enum):
    """Enhanced log levels for different event types"""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    NOTICE = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    SECURITY = 60
    COMPLIANCE = 70
    PERFORMANCE = 15

class EventType(Enum):
    """Comprehensive event type classification"""
    AGENT_INITIALIZATION = auto()
    AGENT_COMMUNICATION = auto()
    AGENT_DECISION = auto()
    AGENT_ACTION = auto()
    AGENT_LEARNING = auto()
    CODE_CHANGE = auto()
    SECURITY_EVENT = auto()
    PERFORMANCE_METRIC = auto()
    ERROR_EVENT = auto()
    COMPLIANCE_EVENT = auto()
    SYSTEM_EVENT = auto()
    USER_ACTION = auto()
    API_REQUEST = auto()
    DATABASE_OPERATION = auto()
    EXTERNAL_SERVICE = auto()

class ComplianceStandard(Enum):
    """Supported compliance standards"""
    SOX = "SOX"
    GDPR = "GDPR" 
    HIPAA = "HIPAA"
    PCI_DSS = "PCI_DSS"
    ISO27001 = "ISO27001"
    NIST = "NIST"

@dataclass
class CorrelationContext:
    """Correlation context for tracing across agent interactions"""
    correlation_id: str
    session_id: str
    user_id: Optional[str]
    agent_id: Optional[str]
    workflow_id: Optional[str]
    parent_span_id: Optional[str]
    span_id: str
    trace_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'correlation_id': self.correlation_id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'agent_id': self.agent_id,
            'workflow_id': self.workflow_id,
            'parent_span_id': self.parent_span_id,
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'started_at': self.started_at.isoformat()
        }

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    operation: str
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    throughput_ops_per_sec: float
    error_count: int
    success_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class AgentDecisionTree:
    """Agent decision tree logging structure"""
    agent_id: str
    decision_point: str
    input_data: Dict[str, Any]
    reasoning_chain: List[str]
    confidence_score: float
    decision_outcome: str
    alternatives_considered: List[str]
    learning_feedback: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass  
class CodeChangeEvent:
    """Code change tracking structure"""
    change_id: str
    repository: str
    branch: str
    commit_hash: Optional[str]
    author: str
    agent_attribution: Optional[str]
    files_changed: List[str]
    lines_added: int
    lines_removed: int
    change_type: str  # create, modify, delete, refactor
    quality_metrics: Dict[str, Any]
    security_scan_results: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class SecurityEvent:
    """Security event logging structure"""
    event_id: str
    severity: str  # low, medium, high, critical
    event_type: str
    source_ip: Optional[str]
    user_agent: Optional[str]
    affected_resource: str
    threat_indicators: List[str]
    mitigation_actions: List[str]
    false_positive: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class ComplianceAuditEvent:
    """Compliance audit trail structure"""
    audit_id: str
    standard: ComplianceStandard
    requirement_id: str
    event_description: str
    data_classification: str
    retention_period_days: int
    access_controls: List[str]
    data_subject_rights: Dict[str, Any]  # For GDPR
    business_justification: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['standard'] = self.standard.value
        result['timestamp'] = self.timestamp.isoformat()
        return result

class SensitiveDataRedactor:
    """Advanced sensitive data redaction and masking"""
    
    def __init__(self, custom_patterns: Optional[List[str]] = None):
        self.patterns = SENSITIVE_PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.patterns]
    
    def redact_data(self, data: Any, mask_char: str = "*") -> Any:
        """Recursively redact sensitive data from any data structure"""
        if isinstance(data, str):
            return self._redact_string(data, mask_char)
        elif isinstance(data, dict):
            return {k: self.redact_data(v, mask_char) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.redact_data(item, mask_char) for item in data]
        elif isinstance(data, tuple):
            return tuple(self.redact_data(item, mask_char) for item in data)
        else:
            return data
    
    def _redact_string(self, text: str, mask_char: str) -> str:
        """Redact sensitive patterns in string"""
        for pattern in self.compiled_patterns:
            text = pattern.sub(lambda m: mask_char * len(m.group()), text)
        return text

class LogEncryption:
    """Log data encryption for sensitive information"""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        if encryption_key:
            self.fernet = Fernet(encryption_key)
        else:
            # Generate a new key - in production, this should be managed securely
            key = Fernet.generate_key()
            self.fernet = Fernet(key)
            # In production, store this key securely (e.g., AWS KMS, HashiCorp Vault)
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive log data"""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt log data"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

class LogRetentionManager:
    """Advanced log retention and archival system"""
    
    def __init__(self, base_path: str = "./logs", retention_days: int = DEFAULT_RETENTION_DAYS):
        self.base_path = Path(base_path)
        self.retention_days = retention_days
        self.archive_path = self.base_path / "archive"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.archive_path.mkdir(parents=True, exist_ok=True)
    
    async def cleanup_old_logs(self):
        """Clean up logs based on retention policy"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        for log_file in self.base_path.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                await self._archive_log_file(log_file)
    
    async def _archive_log_file(self, log_file: Path):
        """Archive and compress log file"""
        archive_file = self.archive_path / f"{log_file.name}.gz"
        
        async with aiofiles.open(log_file, 'rb') as f_in:
            content = await f_in.read()
            
        with gzip.open(archive_file, 'wb') as f_out:
            f_out.write(content)
        
        log_file.unlink()  # Remove original file

class PrometheusMetricsCollector:
    """Prometheus metrics collection for logging system"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # Define metrics
        self.log_entries_total = Counter(
            'ymera_log_entries_total',
            'Total number of log entries',
            ['level', 'agent_id', 'event_type'],
            registry=self.registry
        )
        
        self.log_processing_duration = Histogram(
            'ymera_log_processing_duration_seconds',
            'Time spent processing log entries',
            ['operation'],
            registry=self.registry
        )
        
        self.active_correlations = Gauge(
            'ymera_active_correlations',
            'Number of active correlation contexts',
            registry=self.registry
        )
        
        self.security_events_total = Counter(
            'ymera_security_events_total',
            'Total number of security events',
            ['severity', 'event_type'],
            registry=self.registry
        )
    
    def increment_log_entries(self, level: str, agent_id: str, event_type: str):
        """Increment log entries counter"""
        self.log_entries_total.labels(level=level, agent_id=agent_id, event_type=event_type).inc()
    
    def observe_processing_duration(self, operation: str, duration: float):
        """Record processing duration"""
        self.log_processing_duration.labels(operation=operation).observe(duration)
    
    def set_active_correlations(self, count: int):
        """Set active correlations gauge"""
        self.active_correlations.set(count)
    
    def increment_security_events(self, severity: str, event_type: str):
        """Increment security events counter"""
        self.security_events_total.labels(severity=severity, event_type=event_type).inc()

class ElasticsearchLogStreamer:
    """Real-time log streaming to Elasticsearch"""
    
    def __init__(self, elasticsearch_hosts: List[str], index_prefix: str = "ymera-logs"):
        self.hosts = elasticsearch_hosts
        self.index_prefix = index_prefix
        self.client: Optional[AsyncElasticsearch] = None
    
    async def initialize(self):
        """Initialize Elasticsearch connection"""
        self.client = AsyncElasticsearch(
            hosts=self.hosts,
            verify_certs=False,
            ssl_show_warn=False
        )
        
        # Create index template
        await self._create_index_template()
    
    async def _create_index_template(self):
        """Create Elasticsearch index template"""
        template = {
            "index_patterns": [f"{self.index_prefix}-*"],
            "template": {
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "level": {"type": "keyword"},
                        "message": {"type": "text", "analyzer": "standard"},
                        "correlation_id": {"type": "keyword"},
                        "agent_id": {"type": "keyword"},
                        "event_type": {"type": "keyword"},
                        "performance_metrics": {"type": "object"},
                        "security_event": {"type": "object"},
                        "compliance_data": {"type": "object"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1
                }
            }
        }
        
        await self.client.indices.put_index_template(
            name=f"{self.index_prefix}-template",
            body=template
        )
    
    async def stream_log_entry(self, log_entry: Dict[str, Any]):
        """Stream log entry to Elasticsearch"""
        if not self.client:
            return
        
        index_name = f"{self.index_prefix}-{datetime.utcnow().strftime('%Y.%m.%d')}"
        
        await self.client.index(
            index=index_name,
            body=log_entry,
            refresh=True
        )
    
    async def close(self):
        """Close Elasticsearch connection"""
        if self.client:
            await self.client.close()

class KafkaLogStreamer:
    """Real-time log streaming to Apache Kafka"""
    
    def __init__(self, bootstrap_servers: str, topic: str = "ymera-logs"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
    
    async def initialize(self):
        """Initialize Kafka producer"""
        self.producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda x: orjson.dumps(x),
            key_serializer=lambda x: x.encode() if x else None
        )
        await self.producer.start()
    
    async def stream_log_entry(self, log_entry: Dict[str, Any], key: Optional[str] = None):
        """Stream log entry to Kafka"""
        if not self.producer:
            return
        
        await self.producer.send_and_wait(
            self.topic,
            value=log_entry,
            key=key
        )
    
    async def close(self):
        """Close Kafka producer"""
        if self.producer:
            await self.producer.stop()

class EvidenceLogger:
    """
    Enterprise-grade evidence logging system for YMERA multi-agent system
    
    Features:
    - Structured logging with correlation IDs
    - Performance metrics collection
    - Agent decision trees and reasoning chains logging
    - Code change tracking and attribution
    - Security event logging and alerting
    - Compliance audit trails (SOX, GDPR, HIPAA)
    - Log aggregation and centralized search
    - Real-time log streaming to monitoring systems
    - Log retention policies and archiving
    - Sensitive data redaction and masking
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        redis_client: Optional[redis.Redis] = None,
        elasticsearch_hosts: Optional[List[str]] = None,
        kafka_bootstrap_servers: Optional[str] = None
    ):
        self.config = config
        self.redis_client = redis_client
        
        # Initialize components
        self.redactor = SensitiveDataRedactor(config.get('custom_patterns'))
        self.encryptor = LogEncryption(config.get('encryption_key'))
        self.retention_manager = LogRetentionManager(
            config.get('log_path', './logs'),
            config.get('retention_days', DEFAULT_RETENTION_DAYS)
        )
        self.metrics_collector = PrometheusMetricsCollector()
        
        # Initialize streamers
        self.elasticsearch_streamer = None
        if elasticsearch_hosts:
            self.elasticsearch_streamer = ElasticsearchLogStreamer(elasticsearch_hosts)
        
        self.kafka_streamer = None
        if kafka_bootstrap_servers:
            self.kafka_streamer = KafkaLogStreamer(kafka_bootstrap_servers)
        
        # Correlation context management
        self.correlation_contexts: Dict[str, CorrelationContext] = {}
        self.context_lock = threading.Lock()
        
        # Setup structured logging
        self._setup_structured_logging()
        
        # Background tasks
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Console for rich output
        self.console = Console()
        
        # Initialize logger
        self.logger = structlog.get_logger("evidence_logger")
    
    def _setup_structured_logging(self):
        """Setup structured logging with rich formatting"""
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Setup file handlers with rotation
        log_path = Path(self.config.get('log_path', './logs'))
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Main log file with rotation
        main_handler = TimedRotatingFileHandler(
            log_path / 'ymera.log',
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        
        # Error log file
        error_handler = RotatingFileHandler(
            log_path / 'ymera_errors.log',
            maxBytes=100*1024*1024,  # 100MB
            backupCount=10,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        # Security log file
        security_handler = RotatingFileHandler(
            log_path / 'ymera_security.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=20,
            encoding='utf-8'
        )
        
        # Performance log file
        performance_handler = RotatingFileHandler(
            log_path / 'ymera_performance.log',
            maxBytes=200*1024*1024,  # 200MB
            backupCount=15,
            encoding='utf-8'
        )
        
        # Console handler with rich formatting
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_level=True,
            show_path=True,
            rich_tracebacks=True
        )
        
        # Configure formatters
        json_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        main_handler.setFormatter(json_formatter)
        error_handler.setFormatter(json_formatter)
        security_handler.setFormatter(json_formatter)
        performance_handler.setFormatter(json_formatter)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.config.get('log_level', DEFAULT_LOG_LEVEL))
        root_logger.addHandler(main_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(security_handler)
        root_logger.addHandler(performance_handler)
        root_logger.addHandler(console_handler)
    
    async def initialize(self):
        """Initialize the evidence logging system"""
        try:
            # Initialize streamers
            if self.elasticsearch_streamer:
                await self.elasticsearch_streamer.initialize()
            
            if self.kafka_streamer:
                await self.kafka_streamer.initialize()
            
            # Start background cleanup task
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            
            self.logger.info("Evidence logging system initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize evidence logging system: {str(e)}")
            raise
    
    def create_correlation_context(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        parent_span_id: Optional[str] = None
    ) -> CorrelationContext:
        """Create a new correlation context for tracing"""
        correlation_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        
        context = CorrelationContext(
            correlation_id=correlation_id,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            workflow_id=workflow_id,
            parent_span_id=parent_span_id,
            span_id=span_id,
            trace_id=trace_id
        )
        
        with self.context_lock:
            self.correlation_contexts[correlation_id] = context
            self.metrics_collector.set_active_correlations(len(self.correlation_contexts))
        
        return context
    
    @asynccontextmanager
    async def correlation_context(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        parent_span_id: Optional[str] = None
    ):
        """Context manager for correlation tracking"""
        context = self.create_correlation_context(user_id, agent_id, workflow_id, parent_span_id)
        try:
            yield context
        finally:
            self.close_correlation_context(context.correlation_id)
    
    def close_correlation_context(self, correlation_id: str):
        """Close and clean up correlation context"""
        with self.context_lock:
            if correlation_id in self.correlation_contexts:
                del self.correlation_contexts[correlation_id]
                self.metrics_collector.set_active_correlations(len(self.correlation_contexts))
    
    async def log_agent_decision(
        self,
        correlation_context: CorrelationContext,
        decision_tree: AgentDecisionTree
    ):
        """Log agent decision tree and reasoning chain"""
        start_time = time.time()
        
        try:
            # Redact sensitive data
            redacted_input = self.redactor.redact_data(decision_tree.input_data)
            redacted_reasoning = self.redactor.redact_data(decision_tree.reasoning_chain)
            
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.AGENT_DECISION.name,
                'timestamp': datetime.utcnow().isoformat(),
                'agent_decision': {
                    'agent_id': decision_tree.agent_id,
                    'decision_point': decision_tree.decision_point,
                    'input_data': redacted_input,
                    'reasoning_chain': redacted_reasoning,
                    'confidence_score': decision_tree.confidence_score,
                    'decision_outcome': decision_tree.decision_outcome,
                    'alternatives_considered': decision_tree.alternatives_considered,
                    'learning_feedback': decision_tree.learning_feedback
                }
            }
            
            # Log to structured logger
            self.logger.info(
                "Agent decision recorded",
                **log_entry
            )
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            self.metrics_collector.increment_log_entries(
                level="INFO",
                agent_id=decision_tree.agent_id,
                event_type=EventType.AGENT_DECISION.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("agent_decision", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log agent decision: {str(e)}")
    
    async def log_performance_metrics(
        self,
        correlation_context: CorrelationContext,
        metrics: PerformanceMetrics
    ):
        """Log performance metrics"""
        start_time = time.time()
        
        try:
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.PERFORMANCE_METRIC.name,
                'timestamp': datetime.utcnow().isoformat(),
                'performance_metrics': metrics.to_dict()
            }
            
            self.logger.info(
                "Performance metrics recorded",
                **log_entry
            )
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            self.metrics_collector.increment_log_entries(
                level="INFO",
                agent_id=correlation_context.agent_id or "system",
                event_type=EventType.PERFORMANCE_METRIC.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("performance_metrics", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log performance metrics: {str(e)}")
    
    async def log_code_change(
        self,
        correlation_context: CorrelationContext,
        code_change: CodeChangeEvent
    ):
        """Log code change tracking and attribution"""
        start_time = time.time()
        
        try:
            # Redact sensitive data
            redacted_change = self.redactor.redact_data(code_change.to_dict())
            
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.CODE_CHANGE.name,
                'timestamp': datetime.utcnow().isoformat(),
                'code_change': redacted_change
            }
            
            self.logger.info(
                "Code change recorded",
                **log_entry
            )
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            self.metrics_collector.increment_log_entries(
                level="INFO",
                agent_id=code_change.agent_attribution or "unknown",
                event_type=EventType.CODE_CHANGE.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("code_change", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log code change: {str(e)}")
    
    async def log_security_event(
        self,
        correlation_context: CorrelationContext,
        security_event: SecurityEvent
    ):
        """Log security event with alerting"""
        start_time = time.time()
        
        try:
            # Redact sensitive data (but preserve security context)
            redacted_event = self.redactor.redact_data(security_event.to_dict())
            
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.SECURITY_EVENT.name,
                'timestamp': datetime.utcnow().isoformat(),
                'security_event': redacted_event,
                'alert_level': security_event.severity
            }
            
            # Use appropriate log level based on severity
            if security_event.severity == 'critical':
                self.logger.critical("CRITICAL SECURITY EVENT", **log_entry)
            elif security_event.severity == 'high':
                self.logger.error("HIGH SEVERITY SECURITY EVENT", **log_entry)
            elif security_event.severity == 'medium':
                self.logger.warning("MEDIUM SEVERITY SECURITY EVENT", **log_entry)
            else:
                self.logger.info("LOW SEVERITY SECURITY EVENT", **log_entry)
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update security metrics
            self.metrics_collector.increment_security_events(
                severity=security_event.severity,
                event_type=security_event.event_type
            )
            
            self.metrics_collector.increment_log_entries(
                level="SECURITY",
                agent_id=correlation_context.agent_id or "security_system",
                event_type=EventType.SECURITY_EVENT.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("security_event", duration)
            
            # Send alert for high/critical events
            if security_event.severity in ['high', 'critical']:
                await self._send_security_alert(security_event, log_entry)
            
        except Exception as e:
            self.logger.error(f"Failed to log security event: {str(e)}")
    
    async def log_compliance_event(
        self,
        correlation_context: CorrelationContext,
        compliance_event: ComplianceAuditEvent
    ):
        """Log compliance audit event"""
        start_time = time.time()
        
        try:
            # Apply special handling for compliance data
            compliance_data = compliance_event.to_dict()
            
            # Encrypt sensitive compliance data
            if compliance_event.standard in [ComplianceStandard.GDPR, ComplianceStandard.HIPAA]:
                compliance_data = self._encrypt_compliance_data(compliance_data)
            
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.COMPLIANCE_EVENT.name,
                'timestamp': datetime.utcnow().isoformat(),
                'compliance_event': compliance_data,
                'retention_until': (
                    datetime.utcnow() + timedelta(days=compliance_event.retention_period_days)
                ).isoformat()
            }
            
            self.logger.info(
                f"Compliance event recorded - {compliance_event.standard.value}",
                **log_entry
            )
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            self.metrics_collector.increment_log_entries(
                level="COMPLIANCE",
                agent_id=correlation_context.agent_id or "compliance_system",
                event_type=EventType.COMPLIANCE_EVENT.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("compliance_event", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log compliance event: {str(e)}")
    
    async def log_agent_communication(
        self,
        correlation_context: CorrelationContext,
        from_agent: str,
        to_agent: str,
        message_type: str,
        message_content: Dict[str, Any],
        communication_latency: float
    ):
        """Log inter-agent communication"""
        start_time = time.time()
        
        try:
            # Redact sensitive data
            redacted_content = self.redactor.redact_data(message_content)
            
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.AGENT_COMMUNICATION.name,
                'timestamp': datetime.utcnow().isoformat(),
                'agent_communication': {
                    'from_agent': from_agent,
                    'to_agent': to_agent,
                    'message_type': message_type,
                    'message_content': redacted_content,
                    'communication_latency_ms': communication_latency,
                    'message_size_bytes': len(str(message_content))
                }
            }
            
            self.logger.debug(
                "Agent communication recorded",
                **log_entry
            )
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            self.metrics_collector.increment_log_entries(
                level="DEBUG",
                agent_id=from_agent,
                event_type=EventType.AGENT_COMMUNICATION.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("agent_communication", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log agent communication: {str(e)}")
    
    async def log_learning_event(
        self,
        correlation_context: CorrelationContext,
        learning_type: str,
        input_data: Dict[str, Any],
        learning_outcome: Dict[str, Any],
        model_updates: List[str],
        confidence_improvement: float
    ):
        """Log learning engine events"""
        start_time = time.time()
        
        try:
            # Redact sensitive learning data
            redacted_input = self.redactor.redact_data(input_data)
            redacted_outcome = self.redactor.redact_data(learning_outcome)
            
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.AGENT_LEARNING.name,
                'timestamp': datetime.utcnow().isoformat(),
                'learning_event': {
                    'learning_type': learning_type,
                    'input_data': redacted_input,
                    'learning_outcome': redacted_outcome,
                    'model_updates': model_updates,
                    'confidence_improvement': confidence_improvement,
                    'learning_timestamp': datetime.utcnow().isoformat()
                }
            }
            
            self.logger.info(
                "Learning event recorded",
                **log_entry
            )
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            self.metrics_collector.increment_log_entries(
                level="INFO",
                agent_id=correlation_context.agent_id or "learning_engine",
                event_type=EventType.AGENT_LEARNING.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("learning_event", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log learning event: {str(e)}")
    
    async def log_api_request(
        self,
        correlation_context: CorrelationContext,
        method: str,
        endpoint: str,
        status_code: int,
        response_time: float,
        request_size: int,
        response_size: int,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log API requests"""
        start_time = time.time()
        
        try:
            log_entry = {
                **correlation_context.to_dict(),
                'event_type': EventType.API_REQUEST.name,
                'timestamp': datetime.utcnow().isoformat(),
                'api_request': {
                    'method': method,
                    'endpoint': endpoint,
                    'status_code': status_code,
                    'response_time_ms': response_time,
                    'request_size_bytes': request_size,
                    'response_size_bytes': response_size,
                    'user_agent': self.redactor.redact_data(user_agent) if user_agent else None,
                    'ip_address': self._anonymize_ip(ip_address) if ip_address else None
                }
            }
            
            # Log level based on status code
            if status_code >= 500:
                self.logger.error("API request failed", **log_entry)
            elif status_code >= 400:
                self.logger.warning("API request error", **log_entry)
            else:
                self.logger.info("API request", **log_entry)
            
            # Stream to external systems
            await self._stream_log_entry(log_entry)
            
            # Update metrics
            level = "ERROR" if status_code >= 400 else "INFO"
            self.metrics_collector.increment_log_entries(
                level=level,
                agent_id="api_gateway",
                event_type=EventType.API_REQUEST.name
            )
            
            duration = time.time() - start_time
            self.metrics_collector.observe_processing_duration("api_request", duration)
            
        except Exception as e:
            self.logger.error(f"Failed to log API request: {str(e)}")
    
    async def search_logs(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        agent_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search logs using Elasticsearch"""
        if not self.elasticsearch_streamer or not self.elasticsearch_streamer.client:
            raise RuntimeError("Elasticsearch not configured for log searching")
        
        try:
            # Build Elasticsearch query
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"message": query}}
                        ]
                    }
                },
                "sort": [{"@timestamp": {"order": "desc"}}],
                "size": limit
            }
            
            # Add filters
            filters = []
            
            if start_time:
                filters.append({
                    "range": {
                        "@timestamp": {
                            "gte": start_time.isoformat()
                        }
                    }
                })
            
            if end_time:
                filters.append({
                    "range": {
                        "@timestamp": {
                            "lte": end_time.isoformat()
                        }
                    }
                })
            
            if agent_id:
                filters.append({"term": {"agent_id": agent_id}})
            
            if event_type:
                filters.append({"term": {"event_type": event_type}})
            
            if filters:
                es_query["query"]["bool"]["filter"] = filters
            
            # Execute search
            index_pattern = f"{self.elasticsearch_streamer.index_prefix}-*"
            response = await self.elasticsearch_streamer.client.search(
                index=index_pattern,
                body=es_query
            )
            
            return [hit["_source"] for hit in response["hits"]["hits"]]
            
        except Exception as e:
            self.logger.error(f"Failed to search logs: {str(e)}")
            return []
    
    async def get_agent_performance_metrics(
        self,
        agent_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get performance metrics for specific agent"""
        try:
            # Search for performance events for the agent
            logs = await self.search_logs(
                query="*",
                start_time=start_time,
                end_time=end_time,
                agent_id=agent_id,
                event_type=EventType.PERFORMANCE_METRIC.name
            )
            
            if not logs:
                return {"agent_id": agent_id, "metrics": [], "summary": {}}
            
            # Aggregate metrics
            total_operations = len(logs)
            total_duration = sum(
                log.get("performance_metrics", {}).get("duration_ms", 0) 
                for log in logs
            )
            avg_duration = total_duration / total_operations if total_operations > 0 else 0
            
            error_count = sum(
                log.get("performance_metrics", {}).get("error_count", 0) 
                for log in logs
            )
            success_count = sum(
                log.get("performance_metrics", {}).get("success_count", 0) 
                for log in logs
            )
            
            return {
                "agent_id": agent_id,
                "metrics": logs,
                "summary": {
                    "total_operations": total_operations,
                    "average_duration_ms": avg_duration,
                    "total_errors": error_count,
                    "total_successes": success_count,
                    "error_rate": error_count / (error_count + success_count) if (error_count + success_count) > 0 else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get agent performance metrics: {str(e)}")
            return {"agent_id": agent_id, "error": str(e)}
    
    async def get_compliance_audit_trail(
        self,
        standard: ComplianceStandard,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get compliance audit trail for specific standard"""
        try:
            logs = await self.search_logs(
                query=f"compliance_event.standard:{standard.value}",
                start_time=start_time,
                end_time=end_time,
                event_type=EventType.COMPLIANCE_EVENT.name
            )
            
            # Decrypt compliance data if needed
            decrypted_logs = []
            for log in logs:
                compliance_event = log.get("compliance_event", {})
                if standard in [ComplianceStandard.GDPR, ComplianceStandard.HIPAA]:
                    try:
                        decrypted_event = self._decrypt_compliance_data(compliance_event)
                        log["compliance_event"] = decrypted_event
                    except Exception as e:
                        self.logger.warning(f"Failed to decrypt compliance data: {str(e)}")
                
                decrypted_logs.append(log)
            
            return decrypted_logs
            
        except Exception as e:
            self.logger.error(f"Failed to get compliance audit trail: {str(e)}")
            return []
    
    async def _stream_log_entry(self, log_entry: Dict[str, Any]):
        """Stream log entry to external systems"""
        try:
            # Stream to Elasticsearch
            if self.elasticsearch_streamer:
                await self.elasticsearch_streamer.stream_log_entry(log_entry)
            
            # Stream to Kafka
            if self.kafka_streamer:
                key = log_entry.get("correlation_id")
                await self.kafka_streamer.stream_log_entry(log_entry, key)
            
            # Cache recent entries in Redis for quick access
            if self.redis_client:
                cache_key = f"recent_logs:{log_entry.get('event_type')}"
                await self.redis_client.lpush(
                    cache_key,
                    orjson.dumps(log_entry).decode()
                )
                await self.redis_client.ltrim(cache_key, 0, 999)  # Keep last 1000 entries
                await self.redis_client.expire(cache_key, 3600)  # 1 hour TTL
                
        except Exception as e:
            self.logger.error(f"Failed to stream log entry: {str(e)}")
    
    async def _send_security_alert(
        self,
        security_event: SecurityEvent,
        log_entry: Dict[str, Any]
    ):
        """Send security alert for high/critical events"""
        try:
            alert_data = {
                "alert_type": "security_event",
                "severity": security_event.severity,
                "event_id": security_event.event_id,
                "event_type": security_event.event_type,
                "affected_resource": security_event.affected_resource,
                "threat_indicators": security_event.threat_indicators,
                "timestamp": datetime.utcnow().isoformat(),
                "requires_immediate_attention": security_event.severity == "critical"
            }
            
            # Send to alerting system (Kafka topic for alerts)
            if self.kafka_streamer:
                await self.kafka_streamer.producer.send_and_wait(
                    "ymera-security-alerts",
                    value=alert_data,
                    key=security_event.event_id
                )
            
            # Store in Redis for immediate access by monitoring systems
            if self.redis_client:
                alert_key = f"security_alerts:{security_event.severity}"
                await self.redis_client.lpush(
                    alert_key,
                    orjson.dumps(alert_data).decode()
                )
                await self.redis_client.expire(alert_key, 86400)  # 24 hours
            
            self.logger.info(f"Security alert sent for event {security_event.event_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send security alert: {str(e)}")
    
    def _encrypt_compliance_data(self, compliance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive compliance data"""
        sensitive_fields = [
            'data_subject_rights', 'personal_data', 'sensitive_information',
            'patient_data', 'financial_data', 'access_logs'
        ]
        
        encrypted_data = compliance_data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field]:
                try:
                    encrypted_value = self.encryptor.encrypt_data(
                        orjson.dumps(encrypted_data[field]).decode()
                    )
                    encrypted_data[field] = {
                        "encrypted": True,
                        "data": encrypted_value
                    }
                except Exception as e:
                    self.logger.warning(f"Failed to encrypt field {field}: {str(e)}")
        
        return encrypted_data
    
    def _decrypt_compliance_data(self, compliance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt compliance data"""
        decrypted_data = compliance_data.copy()
        
        for field, value in compliance_data.items():
            if isinstance(value, dict) and value.get("encrypted"):
                try:
                    decrypted_value = self.encryptor.decrypt_data(value["data"])
                    decrypted_data[field] = orjson.loads(decrypted_value.encode())
                except Exception as e:
                    self.logger.warning(f"Failed to decrypt field {field}: {str(e)}")
                    decrypted_data[field] = "[DECRYPTION_FAILED]"
        
        return decrypted_data
    
    def _anonymize_ip(self, ip_address: str) -> str:
        """Anonymize IP address for privacy compliance"""
        try:
            # IPv4 anonymization - zero out last octet
            if '.' in ip_address:
                parts = ip_address.split('.')
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
            
            # IPv6 anonymization - zero out last 64 bits
            elif ':' in ip_address:
                parts = ip_address.split(':')
                if len(parts) >= 4:
                    return ':'.join(parts[:4]) + '::0'
            
            return ip_address
            
        except Exception:
            return "[ANONYMIZED]"
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of old logs and contexts"""
        while True:
            try:
                # Cleanup old correlation contexts (older than 1 hour)
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                expired_contexts = []
                
                with self.context_lock:
                    for correlation_id, context in self.correlation_contexts.items():
                        if context.started_at < cutoff_time:
                            expired_contexts.append(correlation_id)
                    
                    for correlation_id in expired_contexts:
                        del self.correlation_contexts[correlation_id]
                
                if expired_contexts:
                    self.logger.debug(f"Cleaned up {len(expired_contexts)} expired correlation contexts")
                
                # Cleanup old log files
                await self.retention_manager.cleanup_old_logs()
                
                # Update active correlations metric
                self.metrics_collector.set_active_correlations(len(self.correlation_contexts))
                
                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {str(e)}")
                await asyncio.sleep(300)  # Retry in 5 minutes on error
    
    async def get_system_health_logs(self) -> Dict[str, Any]:
        """Get system health from logs perspective"""
        try:
            # Get recent error logs
            recent_errors = []
            if self.redis_client:
                error_logs = await self.redis_client.lrange("recent_logs:ERROR_EVENT", 0, 99)
                recent_errors = [orjson.loads(log.encode()) for log in error_logs]
            
            # Get active correlations count
            active_correlations = len(self.correlation_contexts)
            
            # Get log processing metrics
            health_data = {
                "active_correlations": active_correlations,
                "recent_errors_count": len(recent_errors),
                "recent_errors": recent_errors[:10],  # Last 10 errors
                "log_system_status": "healthy" if len(recent_errors) < 50 else "degraded",
                "elasticsearch_connected": self.elasticsearch_streamer is not None,
                "kafka_connected": self.kafka_streamer is not None,
                "redis_connected": self.redis_client is not None
            }
            
            return health_data
            
        except Exception as e:
            self.logger.error(f"Failed to get system health logs: {str(e)}")
            return {"error": str(e), "log_system_status": "error"}
    
    async def export_logs(
        self,
        format: str = "json",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export logs in specified format"""
        try:
            # Search logs with filters
            query = filters.get("query", "*") if filters else "*"
            logs = await self.search_logs(
                query=query,
                start_time=start_time,
                end_time=end_time,
                agent_id=filters.get("agent_id") if filters else None,
                event_type=filters.get("event_type") if filters else None,
                limit=filters.get("limit", 10000) if filters else 10000
            )
            
            if format.lower() == "json":
                return orjson.dumps(logs, option=orjson.OPT_INDENT_2).decode()
            
            elif format.lower() == "csv":
                if not logs:
                    return "No logs found"
                
                # Flatten log entries for CSV
                import csv
                from io import StringIO
                
                output = StringIO()
                
                # Get all unique keys from all logs
                all_keys = set()
                for log in logs:
                    all_keys.update(self._flatten_dict(log).keys())
                
                writer = csv.DictWriter(output, fieldnames=sorted(all_keys))
                writer.writeheader()
                
                for log in logs:
                    flattened = self._flatten_dict(log)
                    writer.writerow(flattened)
                
                return output.getvalue()
            
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
        except Exception as e:
            self.logger.error(f"Failed to export logs: {str(e)}")
            raise
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    async def close(self):
        """Close and cleanup evidence logger"""
        try:
            # Cancel background tasks
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close streamers
            if self.elasticsearch_streamer:
                await self.elasticsearch_streamer.close()
            
            if self.kafka_streamer:
                await self.kafka_streamer.close()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            # Shutdown thread pool
            self.executor.shutdown(wait=True)
            
            self.logger.info("Evidence logging system closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing evidence logger: {str(e)}")

# Factory function for easy initialization
async def create_evidence_logger(
    config: Dict[str, Any],
    redis_url: Optional[str] = None,
    elasticsearch_hosts: Optional[List[str]] = None,
    kafka_bootstrap_servers: Optional[str] = None
) -> EvidenceLogger:
    """Factory function to create and initialize evidence logger"""
    
    # Initialize Redis client if URL provided
    redis_client = None
    if redis_url:
        redis_client = redis.from_url(redis_url, decode_responses=True)
    
    # Create logger instance
    logger = EvidenceLogger(
        config=config,
        redis_client=redis_client,
        elasticsearch_hosts=elasticsearch_hosts,
        kafka_bootstrap_servers=kafka_bootstrap_servers
    )
    
    # Initialize
    await logger.initialize()
    
    return logger

# Example usage and configuration
if __name__ == "__main__":
    import asyncio
    
    async def example_usage():
        """Example usage of the Evidence Logger"""
        
        # Configuration
        config = {
            'log_path': './logs',
            'log_level': logging.INFO,
            'retention_days': 90,
            'encryption_key': None,  # Will generate new key
            'custom_patterns': [
                r'internal_secret_\w+',  # Custom sensitive pattern
            ]
        }
        
        # Create evidence logger
        logger = await create_evidence_logger(
            config=config,
            redis_url="redis://localhost:6379",
            elasticsearch_hosts=["http://localhost:9200"],
            kafka_bootstrap_servers="localhost:9092"
        )
        
        try:
            # Create correlation context
            async with logger.correlation_context(
                user_id="user_123",
                agent_id="analysis_agent",
                workflow_id="code_review_workflow"
            ) as context:
                
                # Log agent decision
                decision_tree = AgentDecisionTree(
                    agent_id="analysis_agent",
                    decision_point="code_quality_assessment",
                    input_data={"file": "main.py", "complexity": 8.5},
                    reasoning_chain=[
                        "Analyzing code complexity metrics",
                        "Checking coding standards compliance",
                        "Evaluating security patterns"
                    ],
                    confidence_score=0.92,
                    decision_outcome="approve_with_suggestions",
                    alternatives_considered=["reject", "approve_unconditionally"]
                )
                
                await logger.log_agent_decision(context, decision_tree)
                
                # Log performance metrics
                metrics = PerformanceMetrics(
                    operation="code_analysis",
                    duration_ms=1250.5,
                    memory_usage_mb=45.2,
                    cpu_usage_percent=23.1,
                    throughput_ops_per_sec=15.2,
                    error_count=0,
                    success_count=1
                )
                
                await logger.log_performance_metrics(context, metrics)
                
                # Log security event
                security_event = SecurityEvent(
                    event_id=str(uuid.uuid4()),
                    severity="medium",
                    event_type="suspicious_code_pattern",
                    source_ip="192.168.1.100",
                    user_agent="YMERAAgent/2.0",
                    affected_resource="repository:main",
                    threat_indicators=["potential_sql_injection"],
                    mitigation_actions=["code_review_flagged", "notification_sent"]
                )
                
                await logger.log_security_event(context, security_event)
            
            # Search logs
            search_results = await logger.search_logs(
                query="code_analysis",
                agent_id="analysis_agent",
                limit=10
            )
            
            print(f"Found {len(search_results)} log entries")
            
            # Get system health
            health = await logger.get_system_health_logs()
            print(f"Log system health: {health}")
            
        finally:
            await logger.close()
    
    # Run example
    asyncio.run(example_usage())