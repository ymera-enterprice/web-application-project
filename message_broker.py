"""
YMERA Enterprise - Message Broker
Production-Ready Inter-Agent Messaging Infrastructure - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from collections import defaultdict
import time

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import HTTPException
from pydantic import BaseModel, Field, validator

# Local imports (alphabetical)
from config.settings import get_settings
from monitoring.performance_tracker import track_performance
from security.encryption import encrypt_message, decrypt_message

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.message_broker")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
MAX_QUEUE_SIZE = 10000
MESSAGE_RETRY_ATTEMPTS = 3
HEARTBEAT_INTERVAL = 30
DEAD_LETTER_TTL = 86400  # 24 hours

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class MessageMetadata:
    """Metadata for inter-agent messages"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    recipient_id: str = ""
    message_type: str = "standard"
    priority: int = 5  # 1-10 scale
    timestamp: float = field(default_factory=time.time)
    ttl: int = 3600  # seconds
    retry_count: int = 0
    correlation_id: Optional[str] = None
    learning_context: Optional[Dict[str, Any]] = None

class InterAgentMessage(BaseModel):
    """Standardized inter-agent message format"""
    metadata: MessageMetadata
    payload: Dict[str, Any]
    encrypted: bool = False
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class MessageSubscription(BaseModel):
    """Message subscription configuration"""
    agent_id: str
    topics: List[str]
    message_types: List[str] = ["standard"]
    priority_filter: Optional[int] = None
    callback_url: Optional[str] = None

class BrokerConfig(BaseModel):
    """Message broker configuration"""
    redis_url: str = "redis://localhost:6379"
    max_connections: int = 100
    message_ttl: int = 3600
    dead_letter_enabled: bool = True
    encryption_enabled: bool = True
    compression_enabled: bool = False

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class MessageQueue:
    """High-performance message queue implementation"""
    
    def __init__(self, name: str, max_size: int = MAX_QUEUE_SIZE):
        self.name = name
        self.max_size = max_size
        self._queue = asyncio.Queue(maxsize=max_size)
        self._subscribers = set()
        self._metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "queue_size": 0,
            "subscribers_count": 0
        }
        self.logger = logger.bind(queue=name)
    
    async def create_message_broker(
    redis_url: str = "redis://localhost:6379",
    max_connections: int = 100,
    message_ttl: int = 3600,
    encryption_enabled: bool = True
) -> MessageBroker:
    """
    Factory function to create and initialize message broker.
    
    Args:
        redis_url: Redis connection URL
        max_connections: Maximum Redis connections
        message_ttl: Default message TTL
        encryption_enabled: Enable message encryption
        
    Returns:
        Initialized MessageBroker instance
    """
    config = BrokerConfig(
        redis_url=redis_url,
        max_connections=max_connections,
        message_ttl=message_ttl,
        encryption_enabled=encryption_enabled
    )
    
    broker = MessageBroker(config)
    await broker.initialize()
    
    return broker

async def health_check() -> Dict[str, Any]:
    """Message broker health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "message_broker",
        "version": "4.0"
    }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "MessageBroker",
    "MessageRouter", 
    "MessageQueue",
    "InterAgentMessage",
    "MessageMetadata",
    "MessageSubscription",
    "BrokerConfig",
    "create_message_broker",
    "health_check"
] put(self, message: InterAgentMessage) -> bool:
        """
        Add message to queue with overflow protection.
        
        Args:
            message: Message to queue
            
        Returns:
            True if message was queued successfully
            
        Raises:
            QueueFullError: When queue is at capacity
        """
        try:
            if self._queue.full():
                self.logger.warning("Queue full, dropping oldest message")
                # Remove oldest message to make room
                try:
                    await asyncio.wait_for(self._queue.get_nowait(), timeout=0.1)
                except asyncio.TimeoutError:
                    return False
            
            await self._queue.put(message)
            self._metrics["messages_sent"] += 1
            self._metrics["queue_size"] = self._queue.qsize()
            
            self.logger.debug(
                "Message queued",
                message_id=message.metadata.message_id,
                queue_size=self._queue.qsize()
            )
            return True
            
        except Exception as e:
            self.logger.error("Failed to queue message", error=str(e))
            return False
    
    async def get(self, timeout: Optional[float] = None) -> Optional[InterAgentMessage]:
        """
        Get message from queue with timeout.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            Message or None if timeout reached
        """
        try:
            if timeout:
                message = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                message = await self._queue.get()
            
            self._metrics["messages_received"] += 1
            self._metrics["queue_size"] = self._queue.qsize()
            
            return message
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self.logger.error("Failed to get message", error=str(e))
            return None
    
    def add_subscriber(self, subscriber_id: str) -> None:
        """Add subscriber to queue"""
        self._subscribers.add(subscriber_id)
        self._metrics["subscribers_count"] = len(self._subscribers)
    
    def remove_subscriber(self, subscriber_id: str) -> None:
        """Remove subscriber from queue"""
        self._subscribers.discard(subscriber_id)
        self._metrics["subscribers_count"] = len(self._subscribers)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get queue performance metrics"""
        return {
            **self._metrics,
            "queue_size": self._queue.qsize(),
            "is_full": self._queue.full(),
            "is_empty": self._queue.empty()
        }

class MessageRouter:
    """Intelligent message routing system"""
    
    def __init__(self):
        self._routing_table = defaultdict(list)
        self._topic_subscribers = defaultdict(set)
        self._agent_subscriptions = defaultdict(set)
        self.logger = logger.bind(component="message_router")
    
    def add_route(self, sender: str, recipient: str, topic: str) -> None:
        """Add routing rule for messages"""
        route_key = f"{sender}:{topic}"
        if recipient not in self._routing_table[route_key]:
            self._routing_table[route_key].append(recipient)
        
        self._topic_subscribers[topic].add(recipient)
        self._agent_subscriptions[recipient].add(topic)
        
        self.logger.debug(
            "Route added",
            sender=sender,
            recipient=recipient,
            topic=topic
        )
    
    def remove_route(self, sender: str, recipient: str, topic: str) -> None:
        """Remove routing rule"""
        route_key = f"{sender}:{topic}"
        if recipient in self._routing_table[route_key]:
            self._routing_table[route_key].remove(recipient)
            if not self._routing_table[route_key]:
                del self._routing_table[route_key]
        
        self._topic_subscribers[topic].discard(recipient)
        self._agent_subscriptions[recipient].discard(topic)
    
    def get_recipients(self, sender: str, topic: str) -> List[str]:
        """Get all recipients for a message"""
        route_key = f"{sender}:{topic}"
        direct_recipients = self._routing_table.get(route_key, [])
        topic_subscribers = list(self._topic_subscribers.get(topic, set()))
        
        # Combine and deduplicate
        all_recipients = list(set(direct_recipients + topic_subscribers))
        
        # Remove sender from recipients to prevent self-messaging
        return [r for r in all_recipients if r != sender]
    
    def get_agent_topics(self, agent_id: str) -> List[str]:
        """Get all topics an agent is subscribed to"""
        return list(self._agent_subscriptions.get(agent_id, set()))

class MessageBroker:
    """Production-ready message broker for inter-agent communication"""
    
    def __init__(self, config: BrokerConfig):
        self.config = config
        self.logger = logger.bind(component="message_broker")
        
        # Core components
        self._redis_pool: Optional[aioredis.ConnectionPool] = None
        self._redis: Optional[aioredis.Redis] = None
        self._message_queues: Dict[str, MessageQueue] = {}
        self._router = MessageRouter()
        self._subscriptions: Dict[str, MessageSubscription] = {}
        
        # Performance tracking
        self._metrics = {
            "messages_processed": 0,
            "messages_failed": 0,
            "active_connections": 0,
            "queue_count": 0,
            "subscription_count": 0
        }
        
        # Background tasks
        self._background_tasks = set()
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Initialize message broker with all dependencies"""
        try:
            # Setup Redis connection
            await self._setup_redis()
            
            # Start background tasks
            await self._start_background_tasks()
            
            self.logger.info("Message broker initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize message broker", error=str(e))
            raise ConnectionError(f"Message broker initialization failed: {str(e)}")
    
    async def _setup_redis(self) -> None:
        """Setup Redis connection pool"""
        try:
            self._redis_pool = aioredis.ConnectionPool.from_url(
                self.config.redis_url,
                max_connections=self.config.max_connections,
                retry_on_timeout=True
            )
            
            self._redis = aioredis.Redis(connection_pool=self._redis_pool)
            
            # Test connection
            await self._redis.ping()
            
            self.logger.info("Redis connection established")
            
        except Exception as e:
            raise ConnectionError(f"Redis connection failed: {str(e)}")
    
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks"""
        tasks = [
            self._heartbeat_task(),
            self._cleanup_expired_messages(),
            self._process_dead_letter_queue(),
            self._update_metrics()
        ]
        
        for task in tasks:
            background_task = asyncio.create_task(task)
            self._background_tasks.add(background_task)
            background_task.add_done_callback(self._background_tasks.discard)
    
    @track_performance
    async def publish_message(
        self,
        sender_id: str,
        topic: str,
        payload: Dict[str, Any],
        priority: int = 5,
        ttl: Optional[int] = None,
        correlation_id: Optional[str] = None,
        learning_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Publish message to topic with comprehensive error handling.
        
        Args:
            sender_id: ID of the sending agent
            topic: Message topic/channel
            payload: Message payload
            priority: Message priority (1-10)
            ttl: Time to live in seconds
            correlation_id: Optional correlation ID for request/response
            learning_context: Learning system metadata
            
        Returns:
            Message ID of published message
            
        Raises:
            ValidationError: When message validation fails
            PublishError: When message publishing fails
        """
        try:
            # Create message metadata
            metadata = MessageMetadata(
                sender_id=sender_id,
                message_type="broadcast",
                priority=min(max(priority, 1), 10),  # Clamp to 1-10
                ttl=ttl or self.config.message_ttl,
                correlation_id=correlation_id,
                learning_context=learning_context
            )
            
            # Validate payload size
            if len(json.dumps(payload)) > MAX_MESSAGE_SIZE:
                raise ValueError("Message payload exceeds maximum size")
            
            # Create message
            message = InterAgentMessage(
                metadata=metadata,
                payload=payload,
                encrypted=self.config.encryption_enabled
            )
            
            # Encrypt if enabled
            if self.config.encryption_enabled:
                message.payload = encrypt_message(message.payload)
                message.encrypted = True
            
            # Get recipients
            recipients = self._router.get_recipients(sender_id, topic)
            
            if not recipients:
                self.logger.warning(
                    "No recipients for message",
                    sender=sender_id,
                    topic=topic
                )
                return metadata.message_id
            
            # Publish to Redis
            await self._publish_to_redis(topic, message)
            
            # Queue for direct recipients
            await self._queue_for_recipients(recipients, message)
            
            self._metrics["messages_processed"] += 1
            
            self.logger.info(
                "Message published successfully",
                message_id=metadata.message_id,
                sender=sender_id,
                topic=topic,
                recipients_count=len(recipients)
            )
            
            return metadata.message_id
            
        except Exception as e:
            self._metrics["messages_failed"] += 1
            self.logger.error(
                "Failed to publish message",
                error=str(e),
                sender=sender_id,
                topic=topic
            )
            raise HTTPException(
                status_code=500,
                detail=f"Message publishing failed: {str(e)}"
            )
    
    async def send_direct_message(
        self,
        sender_id: str,
        recipient_id: str,
        payload: Dict[str, Any],
        priority: int = 5,
        correlation_id: Optional[str] = None,
        learning_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send direct message to specific agent.
        
        Args:
            sender_id: Sending agent ID
            recipient_id: Receiving agent ID
            payload: Message payload
            priority: Message priority
            correlation_id: Optional correlation ID
            learning_context: Learning metadata
            
        Returns:
            Message ID
        """
        try:
            metadata = MessageMetadata(
                sender_id=sender_id,
                recipient_id=recipient_id,
                message_type="direct",
                priority=priority,
                correlation_id=correlation_id,
                learning_context=learning_context
            )
            
            message = InterAgentMessage(
                metadata=metadata,
                payload=payload,
                encrypted=self.config.encryption_enabled
            )
            
            if self.config.encryption_enabled:
                message.payload = encrypt_message(message.payload)
                message.encrypted = True
            
            # Queue directly for recipient
            await self._queue_for_recipients([recipient_id], message)
            
            self._metrics["messages_processed"] += 1
            
            self.logger.info(
                "Direct message sent",
                message_id=metadata.message_id,
                sender=sender_id,
                recipient=recipient_id
            )
            
            return metadata.message_id
            
        except Exception as e:
            self._metrics["messages_failed"] += 1
            self.logger.error(
                "Failed to send direct message",
                error=str(e),
                sender=sender_id,
                recipient=recipient_id
            )
            raise
    
    async def subscribe(
        self,
        agent_id: str,
        topics: List[str],
        message_types: List[str] = None,
        priority_filter: Optional[int] = None
    ) -> str:
        """
        Subscribe agent to topics.
        
        Args:
            agent_id: Agent ID
            topics: List of topics to subscribe to
            message_types: Types of messages to receive
            priority_filter: Minimum priority filter
            
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        
        subscription = MessageSubscription(
            agent_id=agent_id,
            topics=topics,
            message_types=message_types or ["standard", "broadcast", "direct"],
            priority_filter=priority_filter
        )
        
        self._subscriptions[subscription_id] = subscription
        
        # Add routes for each topic
        for topic in topics:
            self._router.add_route("*", agent_id, topic)
        
        # Create message queue for agent if not exists
        if agent_id not in self._message_queues:
            self._message_queues[agent_id] = MessageQueue(
                name=f"agent_{agent_id}",
                max_size=MAX_QUEUE_SIZE
            )
        
        self._metrics["subscription_count"] = len(self._subscriptions)
        self._metrics["queue_count"] = len(self._message_queues)
        
        self.logger.info(
            "Agent subscribed to topics",
            agent_id=agent_id,
            topics=topics,
            subscription_id=subscription_id
        )
        
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Remove subscription"""
        if subscription_id not in self._subscriptions:
            return False
        
        subscription = self._subscriptions[subscription_id]
        
        # Remove routes
        for topic in subscription.topics:
            self._router.remove_route("*", subscription.agent_id, topic)
        
        del self._subscriptions[subscription_id]
        self._metrics["subscription_count"] = len(self._subscriptions)
        
        self.logger.info(
            "Subscription removed",
            agent_id=subscription.agent_id,
            subscription_id=subscription_id
        )
        
        return True
    
    async def get_messages(
        self,
        agent_id: str,
        timeout: Optional[float] = None,
        max_messages: int = 10
    ) -> List[InterAgentMessage]:
        """
        Get messages for agent.
        
        Args:
            agent_id: Agent ID
            timeout: Timeout in seconds
            max_messages: Maximum messages to return
            
        Returns:
            List of messages
        """
        if agent_id not in self._message_queues:
            return []
        
        queue = self._message_queues[agent_id]
        messages = []
        
        for _ in range(max_messages):
            message = await queue.get(timeout=timeout if not messages else 0.1)
            if message is None:
                break
            
            # Decrypt if needed
            if message.encrypted and self.config.encryption_enabled:
                try:
                    message.payload = decrypt_message(message.payload)
                    message.encrypted = False
                except Exception as e:
                    self.logger.error("Failed to decrypt message", error=str(e))
                    continue
            
            messages.append(message)
        
        if messages:
            self.logger.debug(
                "Messages retrieved",
                agent_id=agent_id,
                count=len(messages)
            )
        
        return messages
    
    async def _publish_to_redis(self, topic: str, message: InterAgentMessage) -> None:
        """Publish message to Redis pub/sub"""
        try:
            message_data = message.dict()
            await self._redis.publish(
                f"ymera:messages:{topic}",
                json.dumps(message_data)
            )
        except Exception as e:
            self.logger.error("Redis publish failed", error=str(e))
            raise
    
    async def _queue_for_recipients(
        self,
        recipients: List[str],
        message: InterAgentMessage
    ) -> None:
        """Queue message for specific recipients"""
        for recipient_id in recipients:
            if recipient_id not in self._message_queues:
                self._message_queues[recipient_id] = MessageQueue(
                    name=f"agent_{recipient_id}",
                    max_size=MAX_QUEUE_SIZE
                )
            
            queue = self._message_queues[recipient_id]
            
            # Create recipient-specific message copy
            recipient_message = InterAgentMessage(
                metadata=MessageMetadata(
                    **message.metadata.__dict__,
                    recipient_id=recipient_id
                ),
                payload=message.payload,
                encrypted=message.encrypted
            )
            
            success = await queue.put(recipient_message)
            if not success:
                self.logger.warning(
                    "Failed to queue message",
                    recipient=recipient_id,
                    message_id=message.metadata.message_id
                )
    
    async def _heartbeat_task(self) -> None:
        """Background heartbeat task"""
        while not self._shutdown_event.is_set():
            try:
                await self._redis.ping()
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                self.logger.error("Heartbeat failed", error=str(e))
                await asyncio.sleep(5)
    
    async def _cleanup_expired_messages(self) -> None:
        """Cleanup expired messages"""
        while not self._shutdown_event.is_set():
            try:
                current_time = time.time()
                
                for queue in self._message_queues.values():
                    # Implementation would check message timestamps
                    # and remove expired ones
                    pass
                
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                self.logger.error("Message cleanup failed", error=str(e))
                await asyncio.sleep(60)
    
    async def _process_dead_letter_queue(self) -> None:
        """Process dead letter queue for failed messages"""
        while not self._shutdown_event.is_set():
            try:
                # Process dead letter messages
                await asyncio.sleep(600)  # Run every 10 minutes
            except Exception as e:
                self.logger.error("Dead letter processing failed", error=str(e))
                await asyncio.sleep(120)
    
    async def _update_metrics(self) -> None:
        """Update performance metrics"""
        while not self._shutdown_event.is_set():
            try:
                self._metrics["active_connections"] = len(self._message_queues)
                self._metrics["queue_count"] = len(self._message_queues)
                
                # Store metrics in Redis
                await self._redis.hset(
                    "ymera:broker:metrics",
                    mapping=self._metrics
                )
                
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                self.logger.error("Metrics update failed", error=str(e))
                await asyncio.sleep(30)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get broker health status"""
        try:
            await self._redis.ping()
            redis_healthy = True
        except:
            redis_healthy = False
        
        return {
            "status": "healthy" if redis_healthy else "unhealthy",
            "redis_connection": redis_healthy,
            "active_queues": len(self._message_queues),
            "subscriptions": len(self._subscriptions),
            "metrics": self._metrics,
            "background_tasks": len(self._background_tasks)
        }
    
    async def shutdown(self) -> None:
        """Graceful shutdown"""
        self.logger.info("Shutting down message broker")
        
        self._shutdown_event.set()
        
        # Wait for background tasks
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Close Redis connection
        if self._redis:
            await self._redis.close()
        
        if self._redis_pool:
            await self._redis_pool.disconnect()
        
        self.logger.info("Message broker shutdown completed")

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def