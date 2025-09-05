"""
YMERA Enterprise - Learning Engine Module Initialization
Production-Ready Learning Infrastructure - v4.0
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
from .core_engine import LearningEngine, LearningEngineConfig
from .knowledge_graph import KnowledgeGraph, KnowledgeGraphConfig
from .pattern_recognition import PatternRecognitionEngine, PatternRecognitionConfig
from .agent_integration import AgentIntegrationManager, AgentIntegrationConfig
from .external_learning import ExternalLearningManager, ExternalLearningConfig
from .memory_consolidation import MemoryConsolidationManager, MemoryConsolidationConfig
from .learning_metrics import LearningMetricsCollector, LearningMetricsConfig

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.learning_engine")

# ===============================================================================
# MODULE METADATA
# ===============================================================================

__version__ = "4.0.0"
__author__ = "YMERA Enterprise Team"
__description__ = "Production-Ready Learning Engine Infrastructure"

# ===============================================================================
# LEARNING ENGINE FACTORY
# ===============================================================================

class LearningEngineFactory:
    """Factory class for creating and managing learning engine components"""
    
    def __init__(self):
        self.logger = logger.bind(component="factory")
        self._initialized_components = {}
    
    async def create_full_learning_system(
        self,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a complete learning system with all components.
        
        Args:
            config: Optional configuration dictionary for all components
            
        Returns:
            Dictionary containing all initialized learning components
            
        Raises:
            InitializationError: When component initialization fails
        """
        try:
            self.logger.info("Initializing complete learning system")
            
            # Default configuration
            default_config = {
                "core_engine": LearningEngineConfig(),
                "knowledge_graph": KnowledgeGraphConfig(),
                "pattern_recognition": PatternRecognitionConfig(),
                "agent_integration": AgentIntegrationConfig(),
                "external_learning": ExternalLearningConfig(),
                "memory_consolidation": MemoryConsolidationConfig(),
                "learning_metrics": LearningMetricsConfig()
            }
            
            # Merge with provided config
            if config:
                for component, component_config in config.items():
                    if component in default_config:
                        default_config[component] = component_config
            
            # Initialize all components
            components = {}
            
            # 1. Initialize Knowledge Graph (foundation)
            self.logger.info("Initializing knowledge graph")
            knowledge_graph = KnowledgeGraph(default_config["knowledge_graph"])
            await knowledge_graph._initialize_resources()
            components["knowledge_graph"] = knowledge_graph
            
            # 2. Initialize Learning Metrics (monitoring)
            self.logger.info("Initializing learning metrics")
            metrics_collector = LearningMetricsCollector(default_config["learning_metrics"])
            await metrics_collector._initialize_resources()
            components["learning_metrics"] = metrics_collector
            
            # 3. Initialize Pattern Recognition
            self.logger.info("Initializing pattern recognition")
            pattern_engine = PatternRecognitionEngine(
                default_config["pattern_recognition"],
                knowledge_graph,
                metrics_collector
            )
            await pattern_engine._initialize_resources()
            components["pattern_recognition"] = pattern_engine
            
            # 4. Initialize Memory Consolidation
            self.logger.info("Initializing memory consolidation")
            memory_manager = MemoryConsolidationManager(
                default_config["memory_consolidation"],
                knowledge_graph,
                metrics_collector
            )
            await memory_manager._initialize_resources()
            components["memory_consolidation"] = memory_manager
            
            # 5. Initialize External Learning
            self.logger.info("Initializing external learning")
            external_learning = ExternalLearningManager(
                default_config["external_learning"],
                knowledge_graph,
                metrics_collector
            )
            await external_learning._initialize_resources()
            components["external_learning"] = external_learning
            
            # 6. Initialize Agent Integration
            self.logger.info("Initializing agent integration")
            agent_integration = AgentIntegrationManager(
                default_config["agent_integration"],
                knowledge_graph,
                metrics_collector
            )
            await agent_integration._initialize_resources()
            components["agent_integration"] = agent_integration
            
            # 7. Initialize Core Learning Engine (orchestrator)
            self.logger.info("Initializing core learning engine")
            core_engine = LearningEngine(
                default_config["core_engine"],
                knowledge_graph,
                pattern_engine,
                agent_integration,
                external_learning,
                memory_manager,
                metrics_collector
            )
            await core_engine._initialize_resources()
            components["core_engine"] = core_engine
            
            self._initialized_components = components
            
            self.logger.info(
                "Learning system initialized successfully",
                components_count=len(components),
                components=list(components.keys())
            )
            
            return components
            
        except Exception as e:
            self.logger.error("Failed to initialize learning system", error=str(e))
            await self._cleanup_partial_initialization()
            raise InitializationError(f"Learning system initialization failed: {str(e)}")
    
    async def _cleanup_partial_initialization(self) -> None:
        """Clean up any partially initialized components"""
        for component_name, component in self._initialized_components.items():
            try:
                if hasattr(component, 'cleanup'):
                    await component.cleanup()
                    self.logger.debug("Cleaned up component", component=component_name)
            except Exception as e:
                self.logger.warning(
                    "Failed to cleanup component",
                    component=component_name,
                    error=str(e)
                )
        
        self._initialized_components.clear()
    
    async def get_component(self, component_name: str) -> Any:
        """
        Get a specific initialized component.
        
        Args:
            component_name: Name of the component to retrieve
            
        Returns:
            The requested component instance
            
        Raises:
            ComponentNotFoundError: When component is not found or not initialized
        """
        if component_name not in self._initialized_components:
            raise ComponentNotFoundError(f"Component '{component_name}' not found or not initialized")
        
        return self._initialized_components[component_name]
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all initialized components.
        
        Returns:
            Health status dictionary for all components
        """
        health_status = {
            "status": "healthy",
            "components": {},
            "total_components": len(self._initialized_components),
            "healthy_components": 0,
            "unhealthy_components": 0
        }
        
        for component_name, component in self._initialized_components.items():
            try:
                if hasattr(component, 'health_check'):
                    component_health = await component.health_check()
                    health_status["components"][component_name] = component_health
                    
                    if component_health.get("status") == "healthy":
                        health_status["healthy_components"] += 1
                    else:
                        health_status["unhealthy_components"] += 1
                else:
                    health_status["components"][component_name] = {
                        "status": "unknown",
                        "message": "Health check not implemented"
                    }
                    health_status["unhealthy_components"] += 1
                    
            except Exception as e:
                health_status["components"][component_name] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["unhealthy_components"] += 1
        
        # Determine overall health status
        if health_status["unhealthy_components"] > 0:
            if health_status["healthy_components"] > 0:
                health_status["status"] = "degraded"
            else:
                health_status["status"] = "unhealthy"
        
        return health_status

# ===============================================================================
# EXCEPTION CLASSES
# ===============================================================================

class LearningEngineError(Exception):
    """Base exception for learning engine errors"""
    pass

class InitializationError(LearningEngineError):
    """Raised when component initialization fails"""
    pass

class ComponentNotFoundError(LearningEngineError):
    """Raised when requested component is not found"""
    pass

class ConfigurationError(LearningEngineError):
    """Raised when configuration is invalid"""
    pass

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def create_learning_system(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convenience function to create a complete learning system.
    
    Args:
        config: Optional configuration for all components
        
    Returns:
        Dictionary of initialized learning components
    """
    factory = LearningEngineFactory()
    return await factory.create_full_learning_system(config)

async def validate_learning_config(config: Dict[str, Any]) -> bool:
    """
    Validate learning system configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if configuration is valid
        
    Raises:
        ConfigurationError: When configuration is invalid
    """
    required_components = [
        "core_engine", "knowledge_graph", "pattern_recognition",
        "agent_integration", "external_learning", "memory_consolidation", 
        "learning_metrics"
    ]
    
    for component in required_components:
        if component not in config:
            raise ConfigurationError(f"Missing required component configuration: {component}")
    
    return True

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_learning_engine_module() -> LearningEngineFactory:
    """Initialize the learning engine module for production use"""
    logger.info("Initializing learning engine module", version=__version__)
    
    factory = LearningEngineFactory()
    
    logger.info("Learning engine module initialized successfully")
    return factory

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Core Components
    "LearningEngine",
    "KnowledgeGraph", 
    "PatternRecognitionEngine",
    "AgentIntegrationManager",
    "ExternalLearningManager",
    "MemoryConsolidationManager",
    "LearningMetricsCollector",
    
    # Configuration Classes
    "LearningEngineConfig",
    "KnowledgeGraphConfig",
    "PatternRecognitionConfig", 
    "AgentIntegrationConfig",
    "ExternalLearningConfig",
    "MemoryConsolidationConfig",
    "LearningMetricsConfig",
    
    # Factory and Utilities
    "LearningEngineFactory",
    "create_learning_system",
    "validate_learning_config",
    "initialize_learning_engine_module",
    
    # Exceptions
    "LearningEngineError",
    "InitializationError",
    "ComponentNotFoundError",
    "ConfigurationError",
    
    # Metadata
    "__version__",
    "__author__",
    "__description__"
]