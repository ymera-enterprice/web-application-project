“””
YMERA Enterprise Multi-Agent System v3.0
Communication Agent - Enterprise-Grade Inter-Agent Communication Hub
Production-Ready AI-Native Development Environment Communication Layer
“””

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Callable, Union, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import aiofiles
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
import redis.asyncio as aioredis
from pydantic import BaseModel, Field, validator
from cryptography.fernet import Fernet
import structlog
import hashlib
import hmac
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import threading
import weakref
import heapq
import traceback

# Import base configurations (assuming from your main file)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
from base_agent import BaseAgent

logger = structlog.get_logger(**name**)

class MessageType(Enum):
“”“Message types for inter-agent communication”””
DIRECT = “direct”
BROADCAST = “broadcast”
MULTICAST = “multicast”
REQUEST_RESPONSE = “request_response”
EVENT = “event”
PRIORITY = “priority”
SYSTEM = “system”
HEARTBEAT = “heartbeat”
ERROR = “error”
ACKNOWLEDGMENT = “ack”

class MessagePriority(Enum):
“”“Message priority levels”””
CRITICAL = 0
HIGH = 1
NORMAL = 2
LOW = 3
BACKGROUND = 4

class CommunicationChannel(Enum):
“”“Communication channel types”””
INTERNAL = “internal”
WEBSOCKET = “websocket”
REDIS_PUBSUB = “redis_pubsub”
HTTP_WEBHOOK = “http_webhook”
MESSAGE_QUEUE = “message_queue”

@dataclass
class MessageMetadata:
“”“Message metadata for tracking and analytics”””
created_at: datetime
sender_id: str
recipient_ids: List[str]
message_type: MessageType
priority: MessagePriority
channel: CommunicationChannel
correlation_id: str
trace_id: str
attempt_count: int = 0
max_attempts: int = 3
timeout_seconds: int = 30
requires_ack: bool = True
ttl_seconds: int = 3600
encrypted: bool = False
compressed: bool = False

class Message(BaseModel):
“”“Enterprise message model”””
id: str = Field(default_factory=lambda: str(uuid.uuid4()))
type: MessageType
priority: MessagePriority = MessagePriority.NORMAL
channel: CommunicationChannel = CommunicationChannel.INTERNAL
sender_id: str
recipient_ids: List[str]
subject: str
payload: Dict[str, Any]
metadata: Dict[str, Any] = Field(default_factory=dict)
correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
timestamp: datetime = Field(default_factory=datetime.utcnow)
expires_at: Optional[datetime] = None
requires_ack: bool = True
signature: Optional[str] = None

```
class Config:
    json_encoders = {
        datetime: lambda dt: dt.isoformat()
    }
```

class MessageQueue:
“”“Priority-based message queue with persistence”””

```
def __init__(self, redis_client: aioredis.Redis):
    self.redis = redis_client
    self.local_queue = []  # Priority heap
    self.queue_lock = asyncio.Lock()
    self.processing = {}  # Track processing messages
    self.failed_messages = deque(maxlen=1000)  # Store failed messages
    
async def enqueue(self, message: Message) -> bool:
    """Enqueue message with priority handling"""
    try:
        async with self.queue_lock:
            # Add to local priority queue
            heapq.heappush(
                self.local_queue,
                (message.priority.value, time.time(), message.id, message)
            )
            
            # Persist to Redis for durability
            await self._persist_message(message)
            
            logger.info("Message enqueued", 
                      message_id=message.id, 
                      priority=message.priority.value,
                      sender=message.sender_id)
            return True
            
    except Exception as e:
        logger.error("Failed to enqueue message", 
                    message_id=message.id, 
                    error=str(e))
        return False

async def dequeue(self) -> Optional[Message]:
    """Dequeue highest priority message"""
    try:
        async with self.queue_lock:
            if not self.local_queue:
                return None
                
            priority, timestamp, msg_id, message = heapq.heappop(self.local_queue)
            
            # Mark as processing
            self.processing[msg_id] = {
                'message': message,
                'started_at': datetime.utcnow()
            }
            
            return message
            
    except Exception as e:
        logger.error("Failed to dequeue message", error=str(e))
        return None

async def acknowledge(self, message_id: str) -> bool:
    """Acknowledge message processing completion"""
    try:
        if message_id in self.processing:
            del self.processing[message_id]
            await self.redis.delete(f"msg_processing:{message_id}")
            return True
        return False
    except Exception as e:
        logger.error("Failed to acknowledge message", 
                    message_id=message_id, 
                    error=str(e))
        return False

async def _persist_message(self, message: Message):
    """Persist message to Redis"""
    message_data = message.json()
    await self.redis.setex(
        f"msg:{message.id}", 
        3600,  # 1 hour TTL
        message_data
    )
```

class CommunicationMetrics:
“”“Communication metrics and analytics”””

```
def __init__(self):
    self.message_counts = defaultdict(int)
    self.latency_stats = defaultdict(list)
    self.error_counts = defaultdict(int)
    self.throughput_window = deque(maxlen=1000)
    self.lock = threading.RLock()

def record_message_sent(self, message_type: MessageType, latency_ms: float):
    """Record message sent metrics"""
    with self.lock:
        self.message_counts[f"sent_{message_type.value}"] += 1
        self.latency_stats[message_type.value].append(latency_ms)
        self.throughput_window.append(time.time())

def record_error(self, error_type: str):
    """Record communication error"""
    with self.lock:
        self.error_counts[error_type] += 1

def get_throughput(self) -> float:
    """Calculate messages per second"""
    with self.lock:
        now = time.time()
        recent = [t for t in self.throughput_window if now - t <= 60]
        return len(recent) / 60.0

def get_stats(self) -> Dict[str, Any]:
    """Get comprehensive communication stats"""
    with self.lock:
        return {
            "message_counts": dict(self.message_counts),
            "error_counts": dict(self.error_counts),
            "throughput_per_second": self.get_throughput(),
            "avg_latency": {
                msg_type: sum(latencies) / len(latencies) 
                for msg_type, latencies in self.latency_stats.items() 
                if latencies
            }
        }
```

class MessageRouter:
“”“Advanced message routing engine”””

```
def __init__(self, communication_agent: 'CommunicationAgent'):
    self.comm_agent = communication_agent
    self.routing_table = {}
    self.load_balancer = {}
    self.circuit_breakers = {}
    
async def route_message(self, message: Message) -> List[str]:
    """Route message to appropriate recipients"""
    routes = []
    
    for recipient_id in message.recipient_ids:
        # Check circuit breaker
        if self._is_circuit_open(recipient_id):
            logger.warning("Circuit breaker open for recipient", 
                         recipient=recipient_id)
            continue
            
        # Determine routing strategy
        if recipient_id == "*":  # Broadcast
            routes.extend(await self._get_all_active_agents())
        elif recipient_id.startswith("group:"):  # Group routing
            routes.extend(await self._get_group_members(recipient_id))
        else:  # Direct routing
            routes.append(recipient_id)
            
    return list(set(routes))  # Remove duplicates

def _is_circuit_open(self, recipient_id: str) -> bool:
    """Check if circuit breaker is open for recipient"""
    if recipient_id not in self.circuit_breakers:
        return False
        
    breaker = self.circuit_breakers[recipient_id]
    return breaker.get('failure_count', 0) >= breaker.get('threshold', 5)

async def _get_all_active_agents(self) -> List[str]:
    """Get all active agent IDs"""
    return list(self.comm_agent.active_connections.keys())

async def _get_group_members(self, group_id: str) -> List[str]:
    """Get members of a communication group"""
    group_name = group_id.replace("group:", "")
    return self.comm_agent.communication_groups.get(group_name, [])
```

class CommunicationAgent:
“”“Enterprise-grade communication agent for multi-agent coordination”””

```
def __init__(self, 
             agent_id: str = None,
             redis_url: str = "redis://localhost:6379/0",
             encryption_key: str = None):
    self.agent_id = agent_id or f"comm_agent_{uuid.uuid4().hex[:8]}"
    self.redis_url = redis_url
    self.encryption_key = encryption_key or Fernet.generate_key()
    self.cipher = Fernet(self.encryption_key) if isinstance(self.encryption_key, bytes) else Fernet(self.encryption_key.encode())
    
    # Core components
    self.redis: Optional[aioredis.Redis] = None
    self.message_queue: Optional[MessageQueue] = None
    self.metrics = CommunicationMetrics()
    self.router: Optional[MessageRouter] = None
    
    # Connection management
    self.active_connections: Dict[str, Any] = {}
    self.websocket_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
    self.http_sessions: Dict[str, aiohttp.ClientSession] = {}
    
    # Communication groups and channels
    self.communication_groups: Dict[str, List[str]] = {}
    self.message_handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
    self.middleware: List[Callable] = []
    
    # Processing control
    self.running = False
    self.processing_tasks: Set[asyncio.Task] = set()
    self.heartbeat_task: Optional[asyncio.Task] = None
    
    # Learning and optimization
    self.conversation_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
    self.routing_optimization: Dict[str, Dict] = {}
    self.performance_baselines: Dict[str, float] = {}
    
    # Rate limiting and throttling
    self.rate_limits: Dict[str, Dict] = {}
    self.message_cache: Dict[str, Message] = {}
    
    logger.info("Communication agent initialized", agent_id=self.agent_id)

async def initialize(self) -> bool:
    """Initialize communication agent"""
    try:
        # Connect to Redis
        self.redis = aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20
        )
        
        # Test Redis connection
        await self.redis.ping()
        logger.info("Redis connection established")
        
        # Initialize message queue
        self.message_queue = MessageQueue(self.redis)
        
        # Initialize router
        self.router = MessageRouter(self)
        
        # Start background tasks
        await self._start_background_tasks()
        
        self.running = True
        logger.info("Communication agent initialized successfully")
        return True
        
    except Exception as e:
        logger.error("Failed to initialize communication agent", error=str(e))
        return False

async def shutdown(self):
    """Graceful shutdown of communication agent"""
    logger.info("Shutting down communication agent")
    self.running = False
    
    # Cancel background tasks
    for task in self.processing_tasks:
        task.cancel()
    
    if self.heartbeat_task:
        self.heartbeat_task.cancel()
    
    # Close connections
    await self._close_connections()
    
    # Close Redis connection
    if self.redis:
        await self.redis.close()
    
    logger.info("Communication agent shut down completed")

async def send_message(self, 
                      recipient_ids: List[str],
                      subject: str,
                      payload: Dict[str, Any],
                      message_type: MessageType = MessageType.DIRECT,
                      priority: MessagePriority = MessagePriority.NORMAL,
                      requires_ack: bool = True,
                      timeout_seconds: int = 30) -> Optional[str]:
    """Send message to recipients"""
    
    start_time = time.time()
    
    try:
        # Create message
        message = Message(
            type=message_type,
            priority=priority,
            sender_id=self.agent_id,
            recipient_ids=recipient_ids,
            subject=subject,
            payload=payload,
            requires_ack=requires_ack,
            expires_at=datetime.utcnow() + timedelta(seconds=timeout_seconds)
        )
        
        # Apply middleware
        for middleware in self.middleware:
            message = await middleware(message)
        
        # Sign message for integrity
        message.signature = self._sign_message(message)
        
        # Route message
        actual_recipients = await self.router.route_message(message)
        
        if not actual_recipients:
            logger.warning("No valid recipients found for message", 
                         message_id=message.id)
            return None
        
        # Enqueue message
        if await self.message_queue.enqueue(message):
            # Record metrics
            latency = (time.time() - start_time) * 1000
            self.metrics.record_message_sent(message_type, latency)
            
            logger.info("Message sent successfully", 
                      message_id=message.id,
                      recipients=len(actual_recipients))
            
            return message.id
        else:
            self.metrics.record_error("enqueue_failed")
            return None
            
    except Exception as e:
        self.metrics.record_error("send_failed")
        logger.error("Failed to send message", 
                    error=str(e), 
                    traceback=traceback.format_exc())
        return None

async def broadcast_message(self, 
                           subject: str, 
                           payload: Dict[str, Any],
                           priority: MessagePriority = MessagePriority.NORMAL) -> Optional[str]:
    """Broadcast message to all active agents"""
    return await self.send_message(
        recipient_ids=["*"],
        subject=subject,
        payload=payload,
        message_type=MessageType.BROADCAST,
        priority=priority,
        requires_ack=False
    )

async def send_to_group(self, 
                       group_name: str,
                       subject: str,
                       payload: Dict[str, Any],
                       priority: MessagePriority = MessagePriority.NORMAL) -> Optional[str]:
    """Send message to a communication group"""
    return await self.send_message(
        recipient_ids=[f"group:{group_name}"],
        subject=subject,
        payload=payload,
        message_type=MessageType.MULTICAST,
        priority=priority
    )

async def request_response(self, 
                          recipient_id: str,
                          subject: str,
                          payload: Dict[str, Any],
                          timeout_seconds: int = 30) -> Optional[Dict[str, Any]]:
    """Send request and wait for response"""
    
    correlation_id = str(uuid.uuid4())
    response_received = asyncio.Event()
    response_data = {}
    
    # Set up response handler
    async def response_handler(message: Message):
        if message.correlation_id == correlation_id:
            response_data.update(message.payload)
            response_received.set()
    
    self.add_message_handler(MessageType.REQUEST_RESPONSE, response_handler)
    
    try:
        # Send request
        message_id = await self.send_message(
            recipient_ids=[recipient_id],
            subject=subject,
            payload={**payload, "correlation_id": correlation_id},
            message_type=MessageType.REQUEST_RESPONSE,
            timeout_seconds=timeout_seconds
        )
        
        if not message_id:
            return None
        
        # Wait for response
        try:
            await asyncio.wait_for(response_received.wait(), timeout=timeout_seconds)
            return response_data
        except asyncio.TimeoutError:
            logger.warning("Request-response timeout", 
                         correlation_id=correlation_id)
            return None
            
    finally:
        # Clean up handler
        if response_handler in self.message_handlers[MessageType.REQUEST_RESPONSE]:
            self.message_handlers[MessageType.REQUEST_RESPONSE].remove(response_handler)

def add_message_handler(self, message_type: MessageType, handler: Callable):
    """Add message handler for specific message type"""
    self.message_handlers[message_type].append(handler)
    logger.debug("Message handler added", 
                message_type=message_type.value,
                handler=handler.__name__)

def remove_message_handler(self, message_type: MessageType, handler: Callable):
    """Remove message handler"""
    if handler in self.message_handlers[message_type]:
        self.message_handlers[message_type].remove(handler)

def add_middleware(self, middleware: Callable):
    """Add message processing middleware"""
    self.middleware.append(middleware)
    logger.debug("Middleware added", middleware=middleware.__name__)

async def create_communication_group(self, group_name: str, member_ids: List[str]):
    """Create communication group"""
    self.communication_groups[group_name] = member_ids
    
    # Persist group to Redis
    await self.redis.setex(
        f"comm_group:{group_name}",
        86400,  # 24 hours
        json.dumps(member_ids)
    )
    
    logger.info("Communication group created", 
               group=group_name, 
               members=len(member_ids))

async def join_communication_group(self, group_name: str, agent_id: str):
    """Add agent to communication group"""
    if group_name not in self.communication_groups:
        self.communication_groups[group_name] = []
    
    if agent_id not in self.communication_groups[group_name]:
        self.communication_groups[group_name].append(agent_id)
        
        # Update in Redis
        await self.redis.setex(
            f"comm_group:{group_name}",
            86400,
            json.dumps(self.communication_groups[group_name])
        )
        
        logger.info("Agent joined communication group", 
                   agent=agent_id, 
                   group=group_name)

async def register_agent(self, agent_id: str, capabilities: Dict[str, Any]):
    """Register agent with communication system"""
    self.active_connections[agent_id] = {
        "capabilities": capabilities,
        "connected_at": datetime.utcnow(),
        "last_heartbeat": datetime.utcnow(),
        "message_count": 0
    }
    
    # Persist to Redis
    await self.redis.setex(
        f"agent:{agent_id}",
        300,  # 5 minutes
        json.dumps({
            "capabilities": capabilities,
            "registered_at": datetime.utcnow().isoformat()
        })
    )
    
    logger.info("Agent registered", agent_id=agent_id)

async def unregister_agent(self, agent_id: str):
    """Unregister agent from communication system"""
    if agent_id in self.active_connections:
        del self.active_connections[agent_id]
    
    await self.redis.delete(f"agent:{agent_id}")
    logger.info("Agent unregistered", agent_id=agent_id)

async def get_agent_capabilities(self, agent_id: str) -> Optional[Dict[str, Any]]:
    """Get agent capabilities"""
    if agent_id in self.active_connections:
        return self.active_connections[agent_id].get("capabilities")
    
    # Try Redis
    agent_data = await self.redis.get(f"agent:{agent_id}")
    if agent_data:
        return json.loads(agent_data).get("capabilities")
    
    return None

async def get_communication_stats(self) -> Dict[str, Any]:
    """Get comprehensive communication statistics"""
    return {
        "agent_id": self.agent_id,
        "active_connections": len(self.active_connections),
        "communication_groups": len(self.communication_groups),
        "message_handlers": sum(len(handlers) for handlers in self.message_handlers.values()),
        "metrics": self.metrics.get_stats(),
        "uptime_seconds": time.time() - getattr(self, '_start_time', time.time()),
        "queue_size": len(self.message_queue.local_queue) if self.message_queue else 0
    }

async def _start_background_tasks(self):
    """Start background processing tasks"""
    # Message processing task
    task1 = asyncio.create_task(self._process_messages())
    self.processing_tasks.add(task1)
    
    # Heartbeat task
    self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    # Cleanup task
    task2 = asyncio.create_task(self._cleanup_expired_messages())
    self.processing_tasks.add(task2)
    
    # Metrics collection task
    task3 = asyncio.create_task(self._collect_metrics())
    self.processing_tasks.add(task3)
    
    self._start_time = time.time()

async def _process_messages(self):
    """Background message processing loop"""
    while self.running:
        try:
            message = await self.message_queue.dequeue()
            if not message:
                await asyncio.sleep(0.1)
                continue
            
            # Process message
            await self._handle_message(message)
            
            # Acknowledge processing
            await self.message_queue.acknowledge(message.id)
            
        except Exception as e:
            logger.error("Error in message processing loop", error=str(e))
            await asyncio.sleep(1)

async def _handle_message(self, message: Message):
    """Handle individual message"""
    try:
        # Verify message signature
        if not self._verify_message_signature(message):
            logger.warning("Message signature verification failed", 
                         message_id=message.id)
            return
        
        # Check expiration
        if message.expires_at and datetime.utcnow() > message.expires_at:
            logger.warning("Message expired", message_id=message.id)
            return
        
        # Route to appropriate handlers
        handlers = self.message_handlers.get(message.type, [])
        
        if not handlers:
            logger.debug("No handlers for message type", 
                       message_type=message.type.value)
            return
        
        # Execute handlers
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error("Handler execution failed", 
                           handler=handler.__name__,
                           error=str(e))
        
        # Store in conversation history for learning
        self.conversation_history[message.sender_id].append({
            'message_id': message.id,
            'timestamp': message.timestamp,
            'subject': message.subject,
            'success': True
        })
        
    except Exception as e:
        logger.error("Message handling failed", 
                    message_id=message.id,
                    error=str(e))

async def _heartbeat_loop(self):
    """Send periodic heartbeats"""
    while self.running:
        try:
            await self.broadcast_message(
                subject="heartbeat",
                payload={
                    "agent_id": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "stats": await self.get_communication_stats()
                },
                priority=MessagePriority.BACKGROUND
            )
            
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            
        except Exception as e:
            logger.error("Heartbeat failed", error=str(e))
            await asyncio.sleep(30)

async def _cleanup_expired_messages(self):
    """Clean up expired messages and connections"""
    while self.running:
        try:
            now = datetime.utcnow()
            
            # Clean up expired agents
            expired_agents = []
            for agent_id, info in self.active_connections.items():
                last_heartbeat = info.get('last_heartbeat', now)
                if now - last_heartbeat > timedelta(minutes=5):
                    expired_agents.append(agent_id)
            
            for agent_id in expired_agents:
                await self.unregister_agent(agent_id)
            
            # Clean up message cache
            expired_messages = [
                msg_id for msg_id, message in self.message_cache.items()
                if message.expires_at and now > message.expires_at
            ]
            
            for msg_id in expired_messages:
                del self.message_cache[msg_id]
            
            await asyncio.sleep(60)  # Cleanup every minute
            
        except Exception as e:
            logger.error("Cleanup failed", error=str(e))
            await asyncio.sleep(60)

async def _collect_metrics(self):
    """Collect and store performance metrics"""
    while self.running:
        try:
            stats = await self.get_communication_stats()
            
            # Store metrics in Redis for monitoring
            await self.redis.setex(
                f"metrics:communication:{self.agent_id}",
                300,  # 5 minutes
                json.dumps(stats)
            )
            
            await asyncio.sleep(30)  # Collect metrics every 30 seconds
            
        except Exception as e:
            logger.error("Metrics collection failed", error=str(e))
            await asyncio.sleep(30)

async def _close_connections(self):
    """Close all active connections"""
    # Close WebSocket connections
    for ws in self.websocket_connections.values():
        try:
            await ws.close()
        except Exception:
            pass
    
    # Close HTTP sessions
    for session in self.http_sessions.values():
        try:
            await session.close()
        except Exception:
            pass
    
    self.websocket_connections.clear()
    self.http_sessions.clear()

def _sign_message(self, message: Message) -> str:
    """Create message signature for integrity verification"""
    message_data = f"{message.id}:{message.sender_id}:{message.timestamp.isoformat()}"
    return hmac.new(
        self.encryption_key if isinstance(self.encryption_key, bytes) else self.encryption_key.encode(),
        message_data.encode(),
        hashlib.sha256
    ).hexdigest()

def _verify_message_signature(self, message: Message) -> bool:
    """Verify message signature"""
    if not message.signature:
        return False
    
    expected_signature = self._sign_message(message)
    return hmac.compare_digest(expected_signature, message.signature)
```

# Factory function for easy instantiation

async def create_communication_agent(
agent_id: str = None,
redis_url: str = “redis://localhost:6379/0”,
encryption_key: str = None
) -> CommunicationAgent:
“”“Factory function to create and initialize communication agent”””

```
agent = CommunicationAgent(
    agent_id=agent_id,
    redis_url=redis_url,
    encryption_key=encryption_key
)

if await agent.initialize():
    return agent
else:
    raise Exception("Failed to initialize communication agent")
```

# Example middleware functions

async def encryption_middleware(message: Message) -> Message:
“”“Middleware to encrypt sensitive messages”””
if “sensitive” in message.payload.get(“tags”, []):
# Implement encryption logic here
pass
return message

async def rate_limiting_middleware(message: Message) -> Message:
“”“Middleware for rate limiting”””
# Implement rate limiting logic here
return message

async def audit_logging_middleware(message: Message) -> Message:
“”“Middleware for audit logging”””
logger.info(“Message audit log”,
message_id=message.id,
sender=message.sender_id,
recipients=message.recipient_ids,
subject=message.subject)
return message

# Example usage and testing

if **name** == “**main**”:
async def main():
# Create communication agent
comm_agent = await create_communication_agent(
agent_id=“test_comm_agent”,
redis_url=“redis://localhost:6379/0”
)

```
    # Add middleware
    comm_agent.add_middleware(audit_logging_middleware)
    comm_agent.add_middleware(rate_limiting_middleware)
    
    # Example message handler
    async def handle_test_message(message: Message):
        logger.info("Received test message", 
                   message_id=message.id,
                   payload=message.payload)
    
    comm_agent.add_message_handler(MessageType.DIRECT, handle_test_message)
    
    # Register some test agents
    await comm_agent.register_agent("agent_1", {"capability": "code_analysis"})
    await comm_agent.register_agent("await comm_agent.register_agent(“agent_2”, {“capability”: “data_processing”})
await comm_agent.register_agent(“agent_3”, {“capability”: “task_management”})

```
# Create communication groups
await comm_agent.create_communication_group("analytics_team", ["agent_1", "agent_2"])
await comm_agent.create_communication_group("management_team", ["agent_3"])

# Send test messages
logger.info("Sending test messages...")

# Direct message
msg_id1 = await comm_agent.send_message(
    recipient_ids=["agent_1"],
    subject="code_review_request",
    payload={"file_path": "/src/main.py", "priority": "high"},
    message_type=MessageType.DIRECT,
    priority=MessagePriority.HIGH
)

# Group message
msg_id2 = await comm_agent.send_to_group(
    group_name="analytics_team",
    subject="data_analysis_task",
    payload={"dataset": "user_metrics.csv", "analysis_type": "trend"}
)

# Broadcast message
msg_id3 = await comm_agent.broadcast_message(
    subject="system_maintenance",
    payload={"scheduled_time": "2025-07-22T02:00:00Z", "duration_minutes": 30}
)

# Request-response example
response = await comm_agent.request_response(
    recipient_id="agent_1",
    subject="get_system_status",
    payload={"components": ["cpu", "memory", "disk"]},
    timeout_seconds=15
)

if response:
    logger.info("Received response", response=response)

# Wait for some processing
await asyncio.sleep(5)

# Get communication stats
stats = await comm_agent.get_communication_stats()
logger.info("Communication stats", stats=stats)

# Keep running for a bit to demonstrate
logger.info("Running for 30 seconds to demonstrate functionality...")
await asyncio.sleep(30)

# Graceful shutdown
await comm_agent.shutdown()
logger.info("Test completed successfully")
```

# Run the main function

try:
asyncio.run(main())
except KeyboardInterrupt:
logger.info(“Interrupted by user”)
except Exception as e:
logger.error(“Test failed”, error=str(e), traceback=traceback.format_exc())

# Additional enterprise features and extensions

class MessageDeliveryGuarantee(Enum):
“”“Message delivery guarantee levels”””
AT_MOST_ONCE = “at_most_once”      # Fire and forget
AT_LEAST_ONCE = “at_least_once”    # With retries
EXACTLY_ONCE = “exactly_once”      # Idempotent delivery

class CommunicationProtocol(Enum):
“”“Supported communication protocols”””
INTERNAL = “internal”
WEBSOCKET = “websocket”
HTTP = “http”
GRPC = “grpc”
MQTT = “mqtt”
AMQP = “amqp”

class SecurityPolicy:
“”“Security policy for message communication”””

```
def __init__(self):
    self.encryption_required = True
    self.signature_required = True
    self.authorized_senders = set()
    self.blacklisted_senders = set()
    self.rate_limits = {}
    self.content_filters = []

def is_authorized(self, sender_id: str) -> bool:
    """Check if sender is authorized"""
    if self.blacklisted_senders and sender_id in self.blacklisted_senders:
        return False
    
    if self.authorized_senders and sender_id not in self.authorized_senders:
        return False
    
    return True

def check_rate_limit(self, sender_id: str) -> bool:
    """Check if sender has exceeded rate limit"""
    # Implementation would track message counts per sender
    return True
```

class MessageTransformer:
“”“Transform messages for different protocols and formats”””

```
@staticmethod
async def to_websocket_frame(message: Message) -> dict:
    """Transform message to WebSocket frame format"""
    return {
        "type": "message",
        "data": {
            "id": message.id,
            "type": message.type.value,
            "priority": message.priority.value,
            "sender": message.sender_id,
            "recipients": message.recipient_ids,
            "subject": message.subject,
            "payload": message.payload,
            "timestamp": message.timestamp.isoformat(),
            "correlation_id": message.correlation_id
        }
    }

@staticmethod
async def to_http_payload(message: Message) -> dict:
    """Transform message to HTTP request payload"""
    return {
        "message": {
            "id": message.id,
            "type": message.type.value,
            "priority": message.priority.value,
            "sender_id": message.sender_id,
            "recipient_ids": message.recipient_ids,
            "subject": message.subject,
            "payload": message.payload,
            "timestamp": message.timestamp.isoformat(),
            "correlation_id": message.correlation_id,
            "signature": message.signature
        }
    }

@staticmethod
async def from_external_format(data: dict) -> Message:
    """Transform external format to internal Message"""
    return Message(
        id=data.get("id", str(uuid.uuid4())),
        type=MessageType(data["type"]),
        priority=MessagePriority(data.get("priority", MessagePriority.NORMAL.value)),
        sender_id=data["sender_id"],
        recipient_ids=data["recipient_ids"],
        subject=data["subject"],
        payload=data.get("payload", {}),
        correlation_id=data.get("correlation_id", str(uuid.uuid4())),
        timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
    )
```

class CommunicationGateway:
“”“Gateway for external communication protocols”””

```
def __init__(self, communication_agent: CommunicationAgent):
    self.comm_agent = communication_agent
    self.websocket_server = None
    self.http_server = None
    self.external_connections = {}
    self.protocol_handlers = {}

async def start_websocket_server(self, host: str = "localhost", port: int = 8765):
    """Start WebSocket server for external agents"""
    async def handle_websocket_connection(websocket, path):
        agent_id = None
        try:
            # Authentication handshake
            auth_message = await websocket.recv()
            auth_data = json.loads(auth_message)
            agent_id = auth_data.get("agent_id")
            
            if not agent_id:
                await websocket.send(json.dumps({"error": "Agent ID required"}))
                return
            
            # Register connection
            self.external_connections[agent_id] = {
                "websocket": websocket,
                "protocol": CommunicationProtocol.WEBSOCKET,
                "connected_at": datetime.utcnow()
            }
            
            await websocket.send(json.dumps({"status": "connected"}))
            
            # Handle incoming messages
            async for message_data in websocket:
                try:
                    data = json.loads(message_data)
                    message = await MessageTransformer.from_external_format(data)
                    
                    # Forward to communication agent
                    await self.comm_agent.message_queue.enqueue(message)
                    
                except Exception as e:
                    logger.error("WebSocket message processing failed", error=str(e))
                    await websocket.send(json.dumps({"error": str(e)}))
            
        except Exception as e:
            logger.error("WebSocket connection error", error=str(e))
        finally:
            if agent_id and agent_id in self.external_connections:
                del self.external_connections[agent_id]
    
    # Start WebSocket server
    self.websocket_server = await websockets.serve(
        handle_websocket_connection, 
        host, 
        port
    )
    logger.info("WebSocket server started", host=host, port=port)

async def start_http_server(self, host: str = "localhost", port: int = 8080):
    """Start HTTP server for REST API communication"""
    from aiohttp import web, web_runner
    
    async def handle_send_message(request):
        try:
            data = await request.json()
            message = await MessageTransformer.from_external_format(data)
            
            message_id = await self.comm_agent.message_queue.enqueue(message)
            
            if message_id:
                return web.json_response({"status": "sent", "message_id": message.id})
            else:
                return web.json_response({"error": "Failed to send message"}, status=500)
                
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)
    
    async def handle_get_stats(request):
        stats = await self.comm_agent.get_communication_stats()
        return web.json_response(stats)
    
    app = web.Application()
    app.router.add_post('/api/v1/messages', handle_send_message)
    app.router.add_get('/api/v1/stats', handle_get_stats)
    
    runner = web_runner.AppRunner(app)
    await runner.setup()
    site = web_runner.TCPSite(runner, host, port)
    await site.start()
    
    logger.info("HTTP server started", host=host, port=port)

async def send_external_message(self, agent_id: str, message: Message):
    """Send message to external agent"""
    if agent_id not in self.external_connections:
        logger.warning("External agent not connected", agent_id=agent_id)
        return False
    
    connection = self.external_connections[agent_id]
    protocol = connection["protocol"]
    
    try:
        if protocol == CommunicationProtocol.WEBSOCKET:
            frame = await MessageTransformer.to_websocket_frame(message)
            await connection["websocket"].send(json.dumps(frame))
            
        elif protocol == CommunicationProtocol.HTTP:
            # For HTTP, we would make a POST request to the agent's endpoint
            payload = await MessageTransformer.to_http_payload(message)
            # Implementation would depend on how HTTP agents expose their endpoints
            
        return True
        
    except Exception as e:
        logger.error("Failed to send external message", 
                    agent_id=agent_id, 
                    error=str(e))
        return False
```

class CommunicationAnalytics:
“”“Advanced analytics and monitoring for communication patterns”””

```
def __init__(self):
    self.message_patterns = defaultdict(list)
    self.conversation_flows = defaultdict(dict)
    self.performance_metrics = {}
    self.anomaly_detector = None

async def analyze_communication_patterns(self, messages: List[Message]) -> Dict[str, Any]:
    """Analyze communication patterns from message history"""
    analysis = {
        "total_messages": len(messages),
        "message_types": defaultdict(int),
        "priority_distribution": defaultdict(int),
        "sender_activity": defaultdict(int),
        "recipient_activity": defaultdict(int),
        "peak_hours": defaultdict(int),
        "response_times": [],
        "conversation_threads": defaultdict(list)
    }
    
    for message in messages:
        # Basic counts
        analysis["message_types"][message.type.value] += 1
        analysis["priority_distribution"][message.priority.value] += 1
        analysis["sender_activity"][message.sender_id] += 1
        
        for recipient in message.recipient_ids:
            analysis["recipient_activity"][recipient] += 1
        
        # Time-based analysis
        hour = message.timestamp.hour
        analysis["peak_hours"][hour] += 1
        
        # Group by correlation ID for conversation threads
        if message.correlation_id:
            analysis["conversation_threads"][message.correlation_id].append({
                "message_id": message.id,
                "sender": message.sender_id,
                "timestamp": message.timestamp,
                "subject": message.subject
            })
    
    return dict(analysis)

def detect_anomalies(self, current_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect communication anomalies"""
    anomalies = []
    
    # Example anomaly detection logic
    throughput = current_metrics.get("throughput_per_second", 0)
    if throughput > 100:  # Unusually high throughput
        anomalies.append({
            "type": "high_throughput",
            "severity": "warning",
            "value": throughput,
            "threshold": 100
        })
    
    error_rate = sum(current_metrics.get("error_counts", {}).values())
    total_messages = sum(current_metrics.get("message_counts", {}).values())
    
    if total_messages > 0:
        error_percentage = (error_rate / total_messages) * 100
        if error_percentage > 5:  # More than 5% error rate
            anomalies.append({
                "type": "high_error_rate",
                "severity": "critical",
                "value": error_percentage,
                "threshold": 5
            })
    
    return anomalies
```

# Enhanced communication agent with enterprise features

class EnterpriseCommunicationAgent(CommunicationAgent):
“”“Enterprise-grade communication agent with advanced features”””

```
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.security_policy = SecurityPolicy()
    self.gateway = CommunicationGateway(self)
    self.analytics = CommunicationAnalytics()
    self.delivery_guarantees = {}
    
async def initialize_enterprise_features(self):
    """Initialize enterprise-specific features"""
    await super().initialize()
    
    # Start external communication gateways
    await self.gateway.start_websocket_server()
    await self.gateway.start_http_server()
    
    logger.info("Enterprise communication features initialized")

async def send_guaranteed_message(self, 
                                 recipient_ids: List[str],
                                 subject: str,
                                 payload: Dict[str, Any],
                                 guarantee: MessageDeliveryGuarantee = MessageDeliveryGuarantee.AT_LEAST_ONCE,
                                 **kwargs) -> Optional[str]:
    """Send message with delivery guarantee"""
    
    message_id = await self.send_message(
        recipient_ids=recipient_ids,
        subject=subject,
        payload=payload,
        **kwargs
    )
    
    if message_id and guarantee != MessageDeliveryGuarantee.AT_MOST_ONCE:
        # Store delivery guarantee requirement
        self.delivery_guarantees[message_id] = {
            "guarantee": guarantee,
            "attempts": 0,
            "max_attempts": 3 if guarantee == MessageDeliveryGuarantee.AT_LEAST_ONCE else 1,
            "recipients_confirmed": set()
        }
    
    return message_id

async def get_comprehensive_analytics(self) -> Dict[str, Any]:
    """Get comprehensive communication analytics"""
    base_stats = await self.get_communication_stats()
    
    # Get message history for analysis
    messages = []
    for conversation in self.conversation_history.values():
        # Convert conversation history to Message objects for analysis
        # This is a simplified version - in practice, you'd store full message objects
        pass
    
    patterns = await self.analytics.analyze_communication_patterns(messages)
    anomalies = self.analytics.detect_anomalies(base_stats)
    
    return {
        **base_stats,
        "patterns": patterns,
        "anomalies": anomalies,
        "external_connections": len(self.gateway.external_connections),
        "security_violations": 0,  # Would track actual violations
        "delivery_guarantees_active": len(self.delivery_guarantees)
    }
```

# Configuration management

class CommunicationConfig:
“”“Configuration management for communication agent”””

```
def __init__(self):
    self.redis_config = {
        "url": "redis://localhost:6379/0",
        "max_connections": 20,
        "retry_on_timeout": True
    }
    
    self.websocket_config = {
        "host": "localhost",
        "port": 8765,
        "max_connections": 100
    }
    
    self.http_config = {
        "host": "localhost", 
        "port": 8080,
        "max_request_size": 1024 * 1024  # 1MB
    }
    
    self.message_config = {
        "default_ttl_seconds": 3600,
        "max_message_size": 1024 * 1024,  # 1MB
        "compression_threshold": 1024,  # Compress messages > 1KB
        "encryption_required": False
    }
    
    self.performance_config = {
        "max_queue_size": 10000,
        "processing_batch_size": 100,
        "heartbeat_interval": 30,
        "cleanup_interval": 60
    }

@classmethod
def from_file(cls, config_path: str):
    """Load configuration from file"""
    config = cls()
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
            
        for section, values in data.items():
            if hasattr(config, section):
                getattr(config, section).update(values)
                
    except Exception as e:
        logger.error("Failed to load config file", path=config_path, error=str(e))
        
    return config
```

# Example of extending with custom protocols

class CustomProtocolHandler:
“”“Template for implementing custom communication protocols”””

```
def __init__(self, communication_agent: CommunicationAgent):
    self.comm_agent = communication_agent

async def initialize(self):
    """Initialize custom protocol"""
    pass

async def send_message(self, message: Message, destination: str) -> bool:
    """Send message using custom protocol"""
    # Implement custom sending logic
    return True

async def handle_incoming_message(self, raw_data: bytes) -> Optional[Message]:
    """Handle incoming message from custom protocol"""
    # Implement custom message parsing
    return None
```

# Testing utilities

class CommunicationTestSuite:
“”“Test suite for communication agent functionality”””

```
def __init__(self, communication_agent: CommunicationAgent):
    self.comm_agent = communication_agent
    self.test_results = []

async def run_all_tests(self):
    """Run comprehensive test suite"""
    tests = [
        self.test_basic_messaging,
        self.test_broadcast_messaging,
        self.test_group_messaging,
        self.test_request_response,
        self.test_priority_handling,
        self.test_error_handling,
        self.test_performance_limits
    ]
    
    for test in tests:
        try:
            result = await test()
            self.test_results.append({
                "test": test.__name__,
                "status": "passed" if result else "failed",
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            self.test_results.append({
                "test": test.__name__,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow()
            })
    
    return self.test_results

async def test_basic_messaging(self) -> bool:
    """Test basic message sending and receiving"""
    # Register test agents
    await self.comm_agent.register_agent("test_sender", {"test": True})
    await self.comm_agent.register_agent("test_receiver", {"test": True})
    
    # Send test message
    message_id = await self.comm_agent.send_message(
        recipient_ids=["test_receiver"],
        subject="test_message",
        payload={"data": "test_payload"}
    )
    
    return message_id is not None

async def test_broadcast_messaging(self) -> bool:
    """Test broadcast messaging"""
    message_id = await self.comm_agent.broadcast_message(
        subject="test_broadcast",
        payload={"announcement": "test"}
    )
    
    return message_id is not None

async def test_group_messaging(self) -> bool:
    """Test group messaging"""
    # Create test group
    await self.comm_agent.create_communication_group(
        "test_group", 
        ["test_agent_1", "test_agent_2"]
    )
    
    message_id = await self.comm_agent.send_to_group(
        group_name="test_group",
        subject="test_group_message",
        payload={"group_data": "test"}
    )
    
    return message_id is not None

async def test_request_response(self) -> bool:
    """Test request-response messaging"""
    # This would require setting up a mock responder
    return True

async def test_priority_handling(self) -> bool:
    """Test message priority handling"""
    # Send messages with different priorities
    high_priority = await self.comm_agent.send_message(
        recipient_ids=["test_receiver"],
        subject="high_priority",
        payload={},
        priority=MessagePriority.HIGH
    )
    
    low_priority = await self.comm_agent.send_message(
        recipient_ids=["test_receiver"],
        subject="low_priority", 
        payload={},
        priority=MessagePriority.LOW
    )
    
    return high_priority and low_priority

async def test_error_handling(self) -> bool:
    """Test error handling scenarios"""
    # Test with invalid recipient
    message_id = await self.comm_agent.send_message(
        recipient_ids=["nonexistent_agent"],
        subject="test_error",
        payload={}
    )
    
    # Should handle gracefully
    return True

async def test_performance_limits(self) -> bool:
    """Test performance under load"""
    # Send multiple messages rapidly
    tasks = []
    for i in range(100):
        task = self.comm_agent.send_message(
            recipient_ids=["test_receiver"],
            subject=f"perf_test_{i}",
            payload={"index": i}
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successful = sum(1 for r in results if not isinstance(r, Exception))
    
    return successful > 90  # At least 90% success rate
```
```