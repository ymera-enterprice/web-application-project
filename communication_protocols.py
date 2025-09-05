"""
YMERA Enterprise - Communication Protocols
Production-Ready Inter-Agent Message Formats & Protocols - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Type, Protocol
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum
import hashlib
import hmac
import base64

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator, root_validator
from cryptography.fernet import Fernet

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Protocol constants
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PAYLOAD_SIZE = 8 * 1024 * 1024   # 8MB
MESSAGE_TIMEOUT = 300                 # 5 minutes
HEARTBEAT_INTERVAL = 30              # 30 seconds
MAX_RETRY_ATTEMPTS = 3
COMPRESSION_THRESHOLD = 1024         # Compress messages > 1KB

# Protocol versions
PROTOCOL_VERSION = "4.0"
SUPPORTED_VERSIONS = ["3.0", "3.1", "4.0"]

# Message priorities
HIGH_PRIORITY = 1
NORMAL_PRIORITY = 5
LOW_PRIORITY = 9

# Configuration loading
settings = get_settings()

# ===============================================================================
# ENUMS & DATA MODELS
# ===============================================================================

class MessageType(Enum):
    """Message type enumeration"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    BROADCAST = "broadcast"
    ERROR = "error"
    ACK = "acknowledgment"
    PING = "ping"
    PONG = "pong"

class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 5
    LOW = 8
    BACKGROUND = 9

class MessageStatus(Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRY = "retry"

class SecurityLevel(Enum):
    """Message security levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"

class CompressionType(Enum):
    """Message compression types"""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    BROTLI = "brotli"

@dataclass
class MessageHeaders:
    """Standard message headers"""
    message_id: str
    correlation_id: Optional[str] = None
    sender_id: str = ""
    recipient_id: Optional[str] = None
    message_type: MessageType = MessageType.REQUEST
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expiry: Optional[datetime] = None
    reply_to: Optional[str] = None
    routing_key: Optional[str] = None
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    compression: CompressionType = CompressionType.NONE
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    protocol_version: str = PROTOCOL_VERSION
    custom_headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class MessageSecurity:
    """Message security information"""
    encrypted: bool = False
    signed: bool = False
    signature: Optional[str] = None
    encryption_key_id: Optional[str] = None
    checksum: Optional[str] = None
    auth_token: Optional[str] = None

@dataclass
class MessageMetadata:
    """Message processing metadata"""
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = MAX_RETRY_ATTEMPTS
    processing_time: Optional[float] = None
    route_history: List[str] = field(default_factory=list)
    error_count: int = 0
    last_error: Optional[str] = None

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class MessageHeadersSchema(BaseModel):
    """Pydantic schema for message headers"""
    message_id: str = Field(..., min_length=1, max_length=100)
    correlation_id: Optional[str] = Field(None, max_length=100)
    sender_id: str = Field(..., min_length=1, max_length=100)
    recipient_id: Optional[str] = Field(None, max_length=100)
    message_type: str = Field(..., regex="^(request|response|notification|heartbeat|broadcast|error|acknowledgment|ping|pong)$")
    priority: int = Field(default=5, ge=1, le=9)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    expiry: Optional[datetime] = None
    reply_to: Optional[str] = Field(None, max_length=100)
    routing_key: Optional[str] = Field(None, max_length=200)
    content_type: str = Field(default="application/json", max_length=100)
    content_encoding: str = Field(default="utf-8", max_length=50)
    compression: str = Field(default="none", regex="^(none|gzip|zlib|brotli)$")
    security_level: str = Field(default="internal", regex="^(public|internal|restricted|confidential|secret)$")
    protocol_version: str = Field(default=PROTOCOL_VERSION, regex=r"^\d+\.\d+$")
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    
    @validator('expiry')
    def validate_expiry(cls, v, values):
        if v and 'timestamp' in values and v <= values['timestamp']:
            raise ValueError("Expiry must be after timestamp")
        return v
    
    @validator('custom_headers')
    def validate_custom_headers(cls, v):
        if len(json.dumps(v)) > 2048:  # 2KB limit for custom headers
            raise ValueError("Custom headers too large")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MessagePayloadSchema(BaseModel):
    """Pydantic schema for message payload"""
    data: Any = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    
    @validator('data')
    def validate_payload_size(cls, v):
        if v is not None:
            payload_size = len(json.dumps(v, default=str))
            if payload_size > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload size {payload_size} exceeds maximum {MAX_PAYLOAD_SIZE}")
        return v

class MessageSchema(BaseModel):
    """Complete message schema"""
    headers: MessageHeadersSchema
    payload: MessagePayloadSchema
    security: Optional[Dict[str, Any]] = None
    
    @root_validator
    def validate_message_size(cls, values):
        message_size = len(json.dumps(values, default=str))
        if message_size > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message size {message_size} exceeds maximum {MAX_MESSAGE_SIZE}")
        return values

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MessageResponseSchema(BaseModel):
    """Schema for message processing responses"""
    success: bool
    message_id: str
    status: str
    processing_time: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ===============================================================================
# CORE PROTOCOL CLASSES
# ===============================================================================

class ProtocolConfig:
    """Configuration for communication protocols"""
    
    def __init__(self):
        self.enabled: bool = settings.PROTOCOL_ENABLED
        self.max_message_size: int = MAX_MESSAGE_SIZE
        self.max_payload_size: int = MAX_PAYLOAD_SIZE
        self.message_timeout: int = MESSAGE_TIMEOUT
        self.max_retries: int = MAX_RETRY_ATTEMPTS
        self.enable_compression: bool = settings.ENABLE_COMPRESSION
        self.enable_encryption: bool = settings.ENABLE_MESSAGE_ENCRYPTION
        self.enable_signing: bool = settings.ENABLE_MESSAGE_SIGNING
        self.compression_threshold: int = COMPRESSION_THRESHOLD
        self.supported_versions: List[str] = SUPPORTED_VERSIONS
        self.encryption_key: str = settings.MESSAGE_ENCRYPTION_KEY
        self.signing_key: str = settings.MESSAGE_SIGNING_KEY

class BaseMessage(ABC):
    """Abstract base class for all message types"""
    
    def __init__(self, headers: MessageHeaders, payload: Any, security: Optional[MessageSecurity] = None):
        self.headers = headers
        self.payload = payload
        self.security = security or MessageSecurity()
        self.metadata = MessageMetadata()
        self._validate_message()
    
    @abstractmethod
    def serialize(self) -> bytes:
        """Serialize message to bytes"""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes) -> 'BaseMessage':
        """Deserialize message from bytes"""
        pass
    
    def _validate_message(self) -> None:
        """Validate message structure and constraints"""
        if not self.headers.message_id:
            raise ValueError("Message ID is required")
        
        if not self.headers.sender_id:
            raise ValueError("Sender ID is required")
        
        if self.headers.expiry and self.headers.expiry <= datetime.utcnow():
            raise ValueError("Message has expired")

class ProductionMessage(BaseMessage):
    """Production-ready message implementation"""
    
    def __init__(self, headers: MessageHeaders, payload: Any, security: Optional[MessageSecurity] = None):
        super().__init__(headers, payload, security)
        self.logger = logger.bind(message_id=headers.message_id)
    
    def serialize(self) -> bytes:
        """Serialize message to compressed and optionally encrypted bytes"""
        try:
            # Create message dictionary
            message_dict = {
                "headers": {
                    "message_id": self.headers.message_id,
                    "correlation_id": self.headers.correlation_id,
                    "sender_id": self.headers.sender_id,
                    "recipient_id": self.headers.recipient_id,
                    "message_type": self.headers.message_type.value,
                    "priority": self.headers.priority.value,
                    "timestamp": self.headers.timestamp.isoformat(),
                    "expiry": self.headers.expiry.isoformat() if self.headers.expiry else None,
                    "reply_to": self.headers.reply_to,
                    "routing_key": self.headers.routing_key,
                    "content_type": self.headers.content_type,
                    "content_encoding": self.headers.content_encoding,
                    "compression": self.headers.compression.value,
                    "security_level": self.headers.security_level.value,
                    "protocol_version": self.headers.protocol_version,
                    "custom_headers": self.headers.custom_headers
                },
                "payload": self.payload,
                "security": {
                    "encrypted": self.security.encrypted,
                    "signed": self.security.signed,
                    "signature": self.security.signature,
                    "encryption_key_id": self.security.encryption_key_id,
                    "checksum": self.security.checksum,
                    "auth_token": self.security.auth_token
                }
            }
            
            # Convert to JSON
            json_data = json.dumps(message_dict, default=self._json_serializer)
            message_bytes = json_data.encode(self.headers.content_encoding)
            
            # Calculate checksum
            self.security.checksum = self._calculate_checksum(message_bytes)
            message_dict["security"]["checksum"] = self.security.checksum
            
            # Re-serialize with checksum
            json_data = json.dumps(message_dict, default=self._json_serializer)
            message_bytes = json_data.encode(self.headers.content_encoding)
            
            # Apply compression if needed
            if len(message_bytes) > COMPRESSION_THRESHOLD and self.headers.compression != CompressionType.NONE:
                message_bytes = self._compress_data(message_bytes, self.headers.compression)
            
            # Apply encryption if needed
            if self.security.encrypted:
                message_bytes = self._encrypt_data(message_bytes)
            
            # Apply signing if needed
            if self.security.signed:
                signature = self._sign_data(message_bytes)
                self.security.signature = signature
                
                # Add signature to the beginning of the message
                signature_bytes = signature.encode('utf-8')
                signature_length = len(signature_bytes).to_bytes(4, byteorder='big')
                message_bytes = signature_length + signature_bytes + message_bytes
            
            return message_bytes
            
        except Exception as e:
            self.logger.error("Message serialization failed", error=str(e))
            raise
    
    @classmethod
    def deserialize(cls, data: bytes, config: Optional[ProtocolConfig] = None) -> 'ProductionMessage':
        """Deserialize message from bytes"""
        try:
            message_bytes = data
            security = MessageSecurity()
            
            # Extract signature if present
            if len(message_bytes) > 4:
                signature_length = int.from_bytes(message_bytes[:4], byteorder='big')
                if signature_length > 0 and signature_length < len(message_bytes):
                    signature = message_bytes[4:4+signature_length].decode('utf-8')
                    message_bytes = message_bytes[4+signature_length:]
                    security.signed = True
                    security.signature = signature
            
            # Decrypt if needed
            if config and config.enable_encryption:
                try:
                    message_bytes = cls._decrypt_data(message_bytes, config.encryption_key)
                    security.encrypted = True
                except:
                    pass  # Not encrypted
            
            # Decompress if needed
            try:
                message_bytes = cls._decompress_data(message_bytes)
            except:
                pass  # Not compressed
            
            # Parse JSON
            json_data = message_bytes.decode('utf-8')
            message_dict = json.loads(json_data)
            
            # Validate checksum
            if "security" in message_dict and message_dict["security"].get("checksum"):
                # Recalculate checksum without the security.checksum field
                temp_dict = message_dict.copy()
                temp_dict["security"] = temp_dict["security"].copy()
                temp_dict["security"]["checksum"] = None
                temp_json = json.dumps(temp_dict, default=cls._json_serializer)
                temp_bytes = temp_json.encode('utf-8')
                expected_checksum = cls._calculate_checksum(temp_bytes)
                
                if expected_checksum != message_dict["security"]["checksum"]:
                    raise ValueError("Message checksum validation failed")
            
            # Parse headers
            headers_data = message_dict["headers"]
            headers = MessageHeaders(
                message_id=headers_data["message_id"],
                correlation_id=headers_data.get("correlation_id"),
                sender_id=headers_data["sender_id"],
                recipient_id=headers_data.get("recipient_id"),
                message_type=MessageType(headers_data["message_type"]),
                priority=MessagePriority(headers_data["priority"]),
                timestamp=datetime.fromisoformat(headers_data["timestamp"]),
                expiry=datetime.fromisoformat(headers_data["expiry"]) if headers_data.get("expiry") else None,
                reply_to=headers_data.get("reply_to"),
                routing_key=headers_data.get("routing_key"),
                content_type=headers_data.get("content_type", "application/json"),
                content_encoding=headers_data.get("content_encoding", "utf-8"),
                compression=CompressionType(headers_data.get("compression", "none")),
                security_level=SecurityLevel(headers_data.get("security_level", "internal")),
                protocol_version=headers_data.get("protocol_version", PROTOCOL_VERSION),
                custom_headers=headers_data.get("custom_headers", {})
            )
            
            # Parse security
            if "security" in message_dict:
                security_data = message_dict["security"]
                security.encrypted = security_data.get("encrypted", False)
                security.signed = security_data.get("signed", False)
                security.signature = security_data.get("signature")
                security.encryption_key_id = security_data.get("encryption_key_id")
                security.checksum = security_data.get("checksum")
                security.auth_token = security_data.get("auth_token")
            
            # Create message
            payload = message_dict["payload"]
            message = cls(headers, payload, security)
            
            return message
            
        except Exception as e:
            logger.error("Message deserialization failed", error=str(e))
            raise
    
    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for complex objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    @staticmethod
    def _calculate_checksum(data: bytes) -> str:
        """Calculate SHA-256 checksum of data"""
        return hashlib.sha256(data).hexdigest()
    
    def _compress_data(self, data: bytes, compression_type: CompressionType) -> bytes:
        """Compress data using specified algorithm"""
        import gzip
        import zlib
        
        try:
            if compression_type == CompressionType.GZIP:
                return gzip.compress(data)
            elif compression_type == CompressionType.ZLIB:
                return zlib.compress(data)
            elif compression_type == CompressionType.BROTLI:
                import brotli
                return brotli.compress(data)
            else:
                return data
        except Exception as e:
            self.logger.warning("Compression failed, using uncompressed data", error=str(e))
            return data
    
    @staticmethod
    def _decompress_data(data: bytes) -> bytes:
        """Auto-detect and decompress data"""
        import gzip
        import zlib
        
        # Try different decompression methods
        try:
            return gzip.decompress(data)
        except:
            pass
        
        try:
            return zlib.decompress(data)
        except:
            pass
        
        try:
            import brotli
            return brotli.decompress(data)
        except:
            pass
        
        # Return original data if no decompression worked
        return data
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using configured encryption key"""
        try:
            fernet = Fernet(settings.MESSAGE_ENCRYPTION_KEY.encode())
            return fernet.encrypt(data)
        except Exception as e:
            self.logger.error("Encryption failed", error=str(e))
            raise
    
    @staticmethod
    def _decrypt_data(data: bytes, encryption_key: str) -> bytes:
        """Decrypt data using provided encryption key"""
        try:
            fernet = Fernet(encryption_key.encode())
            return fernet.decrypt(data)
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise
    
    def _sign_data(self, data: bytes) -> str:
        """Sign data using HMAC-SHA256"""
        try:
            signature = hmac.new(
                settings.MESSAGE_SIGNING_KEY.encode(),
                data,
                hashlib.sha256
            ).hexdigest()
            return signature
        except Exception as e:
            self.logger.error("Signing failed", error=str(e))
            raise
    
    def verify_signature(self, signing_key: str) -> bool:
        """Verify message signature"""
        if not self.security.signed or not self.security.signature:
            return False
        
        try:
            # Re-serialize message without signature for verification
            temp_security = MessageSecurity(
                encrypted=self.security.encrypted,
                signed=False,
                signature=None,
                encryption_key_id=self.security.encryption_key_id,
                checksum=self.security.checksum,
                auth_token=self.security.auth_token
            )
            
            temp_message = ProductionMessage(self.headers, self.payload, temp_security)
            data_to_verify = temp_message.serialize()
            
            expected_signature = hmac.new(
                signing_key.encode(),
                data_to_verify,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, self.security.signature)
            
        except Exception as e:
            self.logger.error("Signature verification failed", error=str(e))
            return False
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        if not self.headers.expiry:
            return False
        return datetime.utcnow() > self.headers.expiry
    
    def get_age(self) -> timedelta:
        """Get message age"""
        return datetime.utcnow() - self.headers.timestamp
    
    def get_size(self) -> int:
        """Get message size in bytes"""
        return len(self.serialize())

# ===============================================================================
# MESSAGE BUILDERS
# ===============================================================================

class MessageBuilder:
    """Builder pattern for creating messages"""
    
    def __init__(self, message_type: MessageType = MessageType.REQUEST):
        self._headers = MessageHeaders(
            message_id=str(uuid.uuid4()),
            message_type=message_type
        )
        self._payload = None
        self._security = MessageSecurity()
    
    def with_id(self, message_id: str) -> 'MessageBuilder':
        """Set message ID"""
        self._headers.message_id = message_id
        return self
    
    def with_correlation_id(self, correlation_id: str) -> 'MessageBuilder':
        """Set correlation ID"""
        self._headers.correlation_id = correlation_id
        return self
    
    def with_sender(self, sender_id: str) -> 'MessageBuilder':
        """Set sender ID"""
        self._headers.sender_id = sender_id
        return self
    
    def with_recipient(self, recipient_id: str) -> 'MessageBuilder':
        """Set recipient ID"""
        self._headers.recipient_id = recipient_id
        return self
    
    def with_priority(self, priority: MessagePriority) -> 'MessageBuilder':
        """Set message priority"""
        self._headers.priority = priority
        return self
    
    def with_expiry(self, expiry: datetime) -> 'MessageBuilder':
        """Set message expiry"""
        self._headers.expiry = expiry
        return self
    
    def with_reply_to(self, reply_to: str) -> 'MessageBuilder':
        """Set reply-to address"""
        self._headers.reply_to = reply_to
        return self
    
    def with_routing_key(self, routing_key: str) -> 'MessageBuilder':
        """Set routing key"""
        self._headers.routing_key = routing_key
        return self
    
    def with_security_level(self, security_level: SecurityLevel) -> 'MessageBuilder':
        """Set security level"""
        self._headers.security_level = security_level
        return self
    
    def with_compression(self, compression: CompressionType) -> 'MessageBuilder':
        """Set compression type"""
        self._headers.compression = compression
        return self
    
    def with_custom_header(self, key: str, value: str) -> 'MessageBuilder':
        """Add custom header"""
        self._headers.custom_headers[key] = value
        return self
    
    def with_payload(self, payload: Any) -> 'MessageBuilder':
        """Set message payload"""
        self._payload = payload
        return self
    
    def with_encryption(self, enabled: bool = True, key_id: Optional[str] = None) -> 'MessageBuilder':
        """Enable message encryption"""
        self._security.encrypted = enabled
        self._security.encryption_key_id = key_id
        return self
    
    def with_signing(self, enabled: bool = True) -> 'MessageBuilder':
        """Enable message signing"""
        self._security.signed = enabled
        return self
    
    def with_auth_token(self, token: str) -> 'MessageBuilder':
        """Set authentication token"""
        self._security.auth_token = token
        return self
    
    def build(self) -> ProductionMessage:
        """Build the message"""
        if not self._headers.sender_id:
            raise ValueError("Sender ID is required")
        
        return ProductionMessage(self._headers, self._payload, self._security)

# ===============================================================================
# PROTOCOL HANDLERS
# ===============================================================================

class BaseProtocolHandler(ABC):
    """Abstract base class for protocol handlers"""
    
    def __init__(self, config: ProtocolConfig):
        self.config = config
        self.logger = logger.bind(handler=self.__class__.__name__)
    
    @abstractmethod
    async def send_message(self, message: ProductionMessage, destination: str) -> bool:
        """Send message to destination"""
        pass
    
    @abstractmethod
    async def receive_message(self, source: str) -> Optional[ProductionMessage]:
        """Receive message from source"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup handler resources"""
        pass

class ProductionProtocolHandler(BaseProtocolHandler):
    """Production-ready protocol handler implementation"""
    
    def __init__(self, config: ProtocolConfig):
        super().__init__(config)
        self._redis_client: Optional[aioredis.Redis] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._active_connections: Dict[str, Any] = {}
        self._retry_queues: Dict[str, List[ProductionMessage]] = {}
        self._processing_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
    
    async def _initialize_resources(self) -> None:
        """Initialize protocol handler resources"""
        try:
            await self._setup_redis_connection()
            await self._setup_message_processing()
            self.logger.info("Protocol handler initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize protocol handler", error=str(e))
            raise
    
    async def _setup_redis_connection(self) -> None:
        """Setup Redis connection for message transport"""
        try:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,  # Handle binary data
                socket_timeout=30,
                socket_connect_timeout=10,
                retry_on_timeout=True,
                max_connections=50
            )
            
            await self._redis_client.ping()
            self.logger.info("Redis connection established for protocol handler")
            
        except Exception as e:
            self.logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def _setup_message_processing(self) -> None:
        """Setup background message processing tasks"""
        # Start message processor
        processor_task = asyncio.create_task(self._process_messages())
        self._processing_tasks.add(processor_task)
        
        # Start retry handler
        retry_task = asyncio.create_task(self._handle_retries())
        self._processing_tasks.add(retry_task)
        
        self.logger.info("Message processing tasks started")
    
    @track_performance
    async def send_message(self, message: ProductionMessage, destination: str) -> bool:
        """Send message to destination with retry logic"""
        try:
            # Validate message before sending
            if message.is_expired():
                self.logger.warning("Attempted to send expired message", message_id=message.headers.message_id)
                return False
            
            # Update route history
            message.metadata.route_history.append(f"sent_to:{destination}")
            
            # Serialize message
            serialized_data = message.serialize()
            
            # Send via Redis streams or pub/sub based on message type
            if message.headers.message_type == MessageType.BROADCAST:
                await self._send_broadcast(serialized_data, destination)
            else:
                await self._send_direct(serialized_data, destination, message.headers.message_id)
            
            # Log successful send
            self.logger.info(
                "Message sent successfully",
                message_id=message.headers.message_id,
                destination=destination,
                message_type=message.headers.message_type.value,
                size=len(serialized_data)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to send message",
                message_id=message.headers.message_id,
                destination=destination,
                error=str(e)
            )
            
            # Add to retry queue if not exceeded max retries
            if message.metadata.retry_count < message.metadata.max_retries:
                await self._add_to_retry_queue(message, destination)
            
            return False
    
    async def _send_direct(self, data: bytes, destination: str, message_id: str) -> None:
        """Send message directly to specific destination"""
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")
        
        # Use Redis streams for reliable delivery
        stream_key = f"agent_messages:{destination}"
        
        await self._redis_client.xadd(
            stream_key,
            {
                "message_id": message_id,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            },
            maxlen=1000  # Keep last 1000 messages
        )
    
    async def _send_broadcast(self, data: bytes, channel: str) -> None:
        """Send broadcast message via pub/sub"""
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")
        
        # Use Redis pub/sub for broadcast messages
        await self._redis_client.publish(f"broadcast:{channel}", data)
    
    @track_performance
    async def receive_message(self, source: str, timeout: Optional[int] = None) -> Optional[ProductionMessage]:
        """Receive message from source with timeout"""
        try:
            if not self._redis_client:
                raise RuntimeError("Redis client not initialized")
            
            stream_key = f"agent_messages:{source}"
            
            # Read from Redis stream
            timeout_ms = (timeout or self.config.message_timeout) * 1000
            
            result = await self._redis_client.xread(
                {stream_key: "$"},  # Read from latest
                count=1,
                block=timeout_ms
            )
            
            if not result:
                return None
            
            # Parse received data
            stream_name, messages = result[0]
            if not messages:
                return None
            
            message_id, fields = messages[0]
            message_data = fields[b"data"]
            
            # Deserialize message
            message = ProductionMessage.deserialize(message_data, self.config)
            
            # Update metadata
            message.metadata.processed_at = datetime.utcnow()
            message.metadata.route_history.append(f"received_from:{source}")
            
            self.logger.info(
                "Message received successfully",
                message_id=message.headers.message_id,
                source=source,
                message_type=message.headers.message_type.value
            )
            
            # Acknowledge message receipt
            await self._acknowledge_message(stream_key, message_id)
            
            return message
            
        except Exception as e:
            self.logger.error(
                "Failed to receive message",
                source=source,
                error=str(e)
            )
            return None
    
    async def _acknowledge_message(self, stream_key: str, message_id: str) -> None:
        """Acknowledge message receipt"""
        try:
            # Remove processed message from stream
            await self._redis_client.xdel(stream_key, message_id)
        except Exception as e:
            self.logger.warning("Failed to acknowledge message", stream_key=stream_key, message_id=message_id, error=str(e))
    
    async def subscribe_to_broadcasts(self, channels: List[str], callback: Callable[[ProductionMessage], None]) -> None:
        """Subscribe to broadcast channels"""
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")
        
        try:
            # Create pub/sub connection
            pubsub = self._redis_client.pubsub()
            
            # Subscribe to channels
            for channel in channels:
                await pubsub.subscribe(f"broadcast:{channel}")
            
            self.logger.info("Subscribed to broadcast channels", channels=channels)
            
            # Start listening task
            listen_task = asyncio.create_task(self._listen_to_broadcasts(pubsub, callback))
            self._processing_tasks.add(listen_task)
            
        except Exception as e:
            self.logger.error("Failed to subscribe to broadcasts", channels=channels, error=str(e))
            raise
    
    async def _listen_to_broadcasts(self, pubsub, callback: Callable[[ProductionMessage], None]) -> None:
        """Listen to broadcast messages"""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Deserialize message
                        message_data = message["data"]
                        production_message = ProductionMessage.deserialize(message_data, self.config)
                        
                        # Call callback
                        callback(production_message)
                        
                    except Exception as e:
                        self.logger.error("Error processing broadcast message", error=str(e))
                        
        except Exception as e:
            self.logger.error("Error in broadcast listener", error=str(e))
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()
    
    async def _add_to_retry_queue(self, message: ProductionMessage, destination: str) -> None:
        """Add message to retry queue"""
        async with self._lock:
            if destination not in self._retry_queues:
                self._retry_queues[destination] = []
            
            message.metadata.retry_count += 1
            message.metadata.last_error = f"Send failed, retry {message.metadata.retry_count}"
            
            self._retry_queues[destination].append(message)
            
            self.logger.info(
                "Message added to retry queue",
                message_id=message.headers.message_id,
                destination=destination,
                retry_count=message.metadata.retry_count
            )
    
    async def _handle_retries(self) -> None:
        """Background task to handle message retries"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                async with self._lock:
                    for destination, messages in self._retry_queues.items():
                        if not messages:
                            continue
                        
                        # Process up to 10 retry messages per destination
                        messages_to_retry = messages[:10]
                        
                        for message in messages_to_retry:
                            # Check if message has expired
                            if message.is_expired():
                                messages.remove(message)
                                self.logger.warning(
                                    "Expired message removed from retry queue",
                                    message_id=message.headers.message_id
                                )
                                continue
                            
                            # Attempt retry
                            success = await self.send_message(message, destination)
                            
                            if success:
                                messages.remove(message)
                                self.logger.info(
                                    "Message retry successful",
                                    message_id=message.headers.message_id,
                                    retry_count=message.metadata.retry_count
                                )
                            elif message.metadata.retry_count >= message.metadata.max_retries:
                                messages.remove(message)
                                self.logger.error(
                                    "Message retry limit exceeded",
                                    message_id=message.headers.message_id,
                                    retry_count=message.metadata.retry_count
                                )
                
            except Exception as e:
                self.logger.error("Error in retry handler", error=str(e))
    
    async def _process_messages(self) -> None:
        """Background task to process queued messages"""
        while True:
            try:
                # Process messages from queue
                if not self._message_queue.empty():
                    message = await self._message_queue.get()
                    await self._handle_message_processing(message)
                
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                
            except Exception as e:
                self.logger.error("Error in message processor", error=str(e))
    
    async def _handle_message_processing(self, message: ProductionMessage) -> None:
        """Handle individual message processing"""
        start_time = datetime.utcnow()
        
        try:
            # Update processing metadata
            message.metadata.processed_at = start_time
            
            # Process message based on type
            if message.headers.message_type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(message)
            elif message.headers.message_type == MessageType.PING:
                await self._handle_ping(message)
            elif message.headers.message_type == MessageType.REQUEST:
                await self._handle_request(message)
            # Add more message type handlers as needed
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            message.metadata.processing_time = processing_time
            
            self.logger.debug(
                "Message processed successfully",
                message_id=message.headers.message_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            message.metadata.error_count += 1
            message.metadata.last_error = str(e)
            
            self.logger.error(
                "Message processing failed",
                message_id=message.headers.message_id,
                error=str(e)
            )
    
    async def _handle_heartbeat(self, message: ProductionMessage) -> None:
        """Handle heartbeat messages"""
        # Update agent last seen timestamp
        if self._redis_client:
            await self._redis_client.set(
                f"agent_heartbeat:{message.headers.sender_id}",
                datetime.utcnow().isoformat(),
                ex=HEARTBEAT_INTERVAL * 3  # Expire after 3 intervals
            )
    
    async def _handle_ping(self, message: ProductionMessage) -> None:
        """Handle ping messages by sending pong response"""
        if not message.headers.reply_to:
            return
        
        # Create pong response
        pong_message = MessageBuilder(MessageType.PONG) \
            .with_sender("protocol_handler") \
            .with_recipient(message.headers.sender_id) \
            .with_correlation_id(message.headers.message_id) \
            .with_payload({"timestamp": datetime.utcnow().isoformat()}) \
            .build()
        
        await self.send_message(pong_message, message.headers.reply_to)
    
    async def _handle_request(self, message: ProductionMessage) -> None:
        """Handle request messages"""
        # Log request for monitoring
        self.logger.info(
            "Request message received",
            message_id=message.headers.message_id,
            sender=message.headers.sender_id,
            routing_key=message.headers.routing_key
        )
        
        # Request messages are typically handled by the receiving agent
        # This is just for logging and monitoring
    
    async def get_handler_statistics(self) -> Dict[str, Any]:
        """Get protocol handler statistics"""
        queue_size = self._message_queue.qsize()
        active_tasks = len(self._processing_tasks)
        retry_queue_sizes = {dest: len(msgs) for dest, msgs in self._retry_queues.items()}
        
        return {
            "queue_size": queue_size,
            "active_tasks": active_tasks,
            "retry_queues": retry_queue_sizes,
            "active_connections": len(self._active_connections),
            "protocol_version": self.config.supported_versions[-1],
            "compression_enabled": self.config.enable_compression,
            "encryption_enabled": self.config.enable_encryption,
            "signing_enabled": self.config.enable_signing
        }
    
    async def cleanup(self) -> None:
        """Cleanup protocol handler resources"""
        try:
            # Cancel processing tasks
            for task in self._processing_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self._processing_tasks:
                await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            
            # Close Redis connection
            if self._redis_client:
                await self._redis_client.close()
            
            self.logger.info("Protocol handler cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during protocol handler cleanup", error=str(e))

# ===============================================================================
# PROTOCOL UTILITIES
# ===============================================================================

class MessageValidator:
    """Utility class for message validation"""
    
    @staticmethod
    def validate_message_schema(message_data: Dict[str, Any]) -> bool:
        """Validate message against schema"""
        try:
            MessageSchema(**message_data)
            return True
        except Exception as e:
            logger.warning("Message validation failed", error=str(e))
            return False
    
    @staticmethod
    def validate_protocol_version(version: str) -> bool:
        """Validate protocol version compatibility"""
        return version in SUPPORTED_VERSIONS
    
    @staticmethod
    def validate_message_size(message: ProductionMessage) -> bool:
        """Validate message size constraints"""
        return message.get_size() <= MAX_MESSAGE_SIZE
    
    @staticmethod
    def validate_security_requirements(message: ProductionMessage, requirements: Dict[str, bool]) -> bool:
        """Validate message meets security requirements"""
        if requirements.get("encryption_required", False) and not message.security.encrypted:
            return False
        
        if requirements.get("signing_required", False) and not message.security.signed:
            return False
        
        return True

class MessageRouter:
    """Utility class for message routing"""
    
    def __init__(self):
        self._routing_table: Dict[str, str] = {}
        self._load_balancers: Dict[str, List[str]] = {}
    
    def add_route(self, routing_key: str, destination: str) -> None:
        """Add route to routing table"""
        self._routing_table[routing_key] = destination
    
    def add_load_balanced_route(self, routing_key: str, destinations: List[str]) -> None:
        """Add load-balanced route"""
        self._load_balancers[routing_key] = destinations
    
    def resolve_destination(self, message: ProductionMessage) -> Optional[str]:
        """Resolve message destination based on routing rules"""
        # Direct recipient
        if message.headers.recipient_id:
            return message.headers.recipient_id
        
        # Routing key lookup
        if message.headers.routing_key:
            # Check load-balanced routes first
            if message.headers.routing_key in self._load_balancers:
                destinations = self._load_balancers[message.headers.routing_key]
                # Simple round-robin selection
                import random
                return random.choice(destinations)
            
            # Check direct routes
            if message.headers.routing_key in self._routing_table:
                return self._routing_table[message.headers.routing_key]
        
        return None

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Protocol system health check"""
    try:
        handler = await get_protocol_handler()
        stats = await handler.get_handler_statistics()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "communication_protocols",
            "version": "4.0",
            "protocol_version": PROTOCOL_VERSION,
            "statistics": stats
        }
    except Exception as e:
        logger.error("Protocol health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "communication_protocols",
            "error": str(e)
        }

def create_request_message(sender_id: str, recipient_id: str, payload: Any, **kwargs) -> ProductionMessage:
    """Utility function to create request messages"""
    builder = MessageBuilder(MessageType.REQUEST) \
        .with_sender(sender_id) \
        .with_recipient(recipient_id) \
        .with_payload(payload)
    
    # Apply optional parameters
    if "priority" in kwargs:
        builder.with_priority(MessagePriority(kwargs["priority"]))
    
    if "correlation_id" in kwargs:
        builder.with_correlation_id(kwargs["correlation_id"])
    
    if "routing_key" in kwargs:
        builder.with_routing_key(kwargs["routing_key"])
    
    if "reply_to" in kwargs:
        builder.with_reply_to(kwargs["reply_to"])
    
    if "expiry" in kwargs:
        builder.with_expiry(kwargs["expiry"])
    
    return builder.build()

def create_response_message(request_message: ProductionMessage, payload: Any, success: bool = True) -> ProductionMessage:
    """Utility function to create response messages"""
    builder = MessageBuilder(MessageType.RESPONSE) \
        .with_sender("response_handler") \
        .with_recipient(request_message.headers.sender_id) \
        .with_correlation_id(request_message.headers.message_id) \
        .with_payload(payload)
    
    if request_message.headers.reply_to:
        builder.with_routing_key(request_message.headers.reply_to)
    
    return builder.build()

def create_notification_message(sender_id: str, payload: Any, **kwargs) -> ProductionMessage:
    """Utility function to create notification messages"""
    builder = MessageBuilder(MessageType.NOTIFICATION) \
        .with_sender(sender_id) \
        .with_payload(payload)
    
    if "recipients" in kwargs:
        # For multiple recipients, use broadcast
        builder._headers.message_type = MessageType.BROADCAST
    
    if "routing_key" in kwargs:
        builder.with_routing_key(kwargs["routing_key"])
    
    return builder.build()

# ===============================================================================
# SINGLETON PROTOCOL HANDLER
# ===============================================================================

_protocol_handler_instance: Optional[ProductionProtocolHandler] = None
_protocol_lock = asyncio.Lock()

async def get_protocol_handler() -> ProductionProtocolHandler:
    """Get singleton protocol handler instance"""
    global _protocol_handler_instance
    
    if not _protocol_handler_instance:
        async with _protocol_lock:
            if not _protocol_handler_instance:
                config = ProtocolConfig()
                _protocol_handler_instance = ProductionProtocolHandler(config)
                await _protocol_handler_instance._initialize_resources()
    
    return _protocol_handler_instance

async def shutdown_protocol_handler() -> None:
    """Shutdown the protocol handler instance"""
    global _protocol_handler_instance
    
    if _protocol_handler_instance:
        await _protocol_handler_instance.cleanup()
        _protocol_handler_instance = None

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_communication_protocols() -> ProductionProtocolHandler:
    """Initialize communication protocols for production use"""
    try:
        handler = await get_protocol_handler()
        logger.info("Communication protocols initialized successfully")
        return handler
    except Exception as e:
        logger.error("Failed to initialize communication protocols", error=str(e))
        raise

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionMessage",
    "ProductionProtocolHandler",
    "MessageBuilder",
    "MessageHeaders",
    "MessageSecurity",
    "MessageMetadata",
    "MessageType",
    "MessagePriority", 
    "MessageStatus",
    "SecurityLevel",
    "CompressionType",
    "MessageValidator",
    "MessageRouter",
    "ProtocolConfig",
    "get_protocol_handler",
    "initialize_communication_protocols",
    "shutdown_protocol_handler",
    "create_request_message",
    "create_response_message",
    "create_notification_message",
    "health_check"
]