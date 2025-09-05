"""
YMERA Enterprise - Agent Communication System
Production-Ready Inter-Agent Communication Infrastructure - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import logging
from typing import Dict, List, Any, Optional

# Third-party imports (alphabetical)
import structlog

# Local imports (alphabetical)
from .agent_registry import AgentRegistry, AgentRegistrationManager
from .communication_protocols import (
    MessageProtocol,
    TaskProtocol,
    LearningProtocol,
    CommunicationProtocolManager
)
from .message_broker import MessageBroker, MessageRouter
from .response_aggregator import ResponseAggregator, ResponseCollector
from .task_dispatcher import TaskDispatcher, TaskDistributionEngine

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.agent_communication")

# ===============================================================================
# MODULE EXPORTS
# ===============================================================================

__version__ = "4.0.0"
__author__ = "YMERA Enterprise Team"

# Core communication components
__all__ = [
    # Registry components
    "AgentRegistry",
    "AgentRegistrationManager",
    
    # Protocol components
    "MessageProtocol", 
    "TaskProtocol",
    "LearningProtocol",
    "CommunicationProtocolManager",
    
    # Messaging infrastructure
    "MessageBroker",
    "MessageRouter",
    
    # Response handling
    "ResponseAggregator",
    "ResponseCollector",
    
    # Task distribution
    "TaskDispatcher", 
    "TaskDistributionEngine",
    
    # System utilities
    "initialize_communication_system",
    "get_communication_health",
    "shutdown_communication_system"
]

# ===============================================================================
# SYSTEM INITIALIZATION
# ===============================================================================

_communication_system: Optional[Dict[str, Any]] = None

async def initialize_communication_system(
    redis_url: str = "redis://localhost:6379",
    max_agents: int = 1000,
    message_ttl: int = 3600
) -> Dict[str, Any]:
    """
    Initialize the complete agent communication system.
    
    Args:
        redis_url: Redis connection URL for message brokering
        max_agents: Maximum number of concurrent agents
        message_ttl: Message time-to-live in seconds
        
    Returns:
        Dictionary containing all initialized communication components
        
    Raises:
        ConnectionError: When Redis connection fails
        ConfigurationError: When system configuration is invalid
    """
    global _communication_system
    
    try:
        logger.info(
            "Initializing agent communication system",
            redis_url=redis_url,
            max_agents=max_agents,
            message_ttl=message_ttl
        )
        
        # Initialize core components
        agent_registry = AgentRegistrationManager(max_agents=max_agents)
        await agent_registry.initialize()
        
        protocol_manager = CommunicationProtocolManager()
        await protocol_manager.initialize()
        
        message_broker = MessageBroker(
            redis_url=redis_url,
            message_ttl=message_ttl
        )
        await message_broker.initialize()
        
        task_dispatcher = TaskDistributionEngine(
            agent_registry=agent_registry,
            message_broker=message_broker
        )
        await task_dispatcher.initialize()
        
        response_aggregator = ResponseCollector(
            message_broker=message_broker,
            timeout_seconds=300
        )
        await response_aggregator.initialize()
        
        _communication_system = {
            "agent_registry": agent_registry,
            "protocol_manager": protocol_manager,
            "message_broker": message_broker,
            "task_dispatcher": task_dispatcher,
            "response_aggregator": response_aggregator,
            "status": "initialized",
            "version": __version__
        }
        
        logger.info("Agent communication system initialized successfully")
        return _communication_system
        
    except Exception as e:
        logger.error("Failed to initialize communication system", error=str(e))
        raise ConnectionError(f"Communication system initialization failed: {str(e)}")

async def get_communication_health() -> Dict[str, Any]:
    """
    Get comprehensive health status of the communication system.
    
    Returns:
        Dictionary containing health metrics for all components
    """
    if not _communication_system:
        return {
            "status": "not_initialized",
            "components": {},
            "overall_health": "unhealthy"
        }
    
    health_status = {
        "status": "healthy",
        "components": {},
        "overall_health": "healthy",
        "timestamp": asyncio.get_event_loop().time()
    }
    
    # Check each component
    for component_name, component in _communication_system.items():
        if hasattr(component, 'get_health_status'):
            try:
                component_health = await component.get_health_status()
                health_status["components"][component_name] = component_health
                
                if component_health.get("status") != "healthy":
                    health_status["overall_health"] = "degraded"
                    
            except Exception as e:
                health_status["components"][component_name] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["overall_health"] = "unhealthy"
    
    return health_status

async def shutdown_communication_system() -> None:
    """
    Gracefully shutdown the entire communication system.
    
    Ensures all components are properly cleaned up and resources are released.
    """
    global _communication_system
    
    if not _communication_system:
        logger.warning("Communication system not initialized, nothing to shutdown")
        return
    
    logger.info("Shutting down agent communication system")
    
    shutdown_tasks = []
    for component_name, component in _communication_system.items():
        if hasattr(component, 'shutdown'):
            shutdown_tasks.append(component.shutdown())
    
    if shutdown_tasks:
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    
    _communication_system = None
    logger.info("Agent communication system shutdown completed")

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

logger.info(
    "YMERA Agent Communication System loaded",
    version=__version__,
    components=len(__all__)
)