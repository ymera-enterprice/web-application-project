"""
YMERA Enterprise - Core Learning Engine
Production-Ready Learning Orchestration Engine - v4.0
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
from pathlib import Path

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from database.connection import get_db_session

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.learning_engine.core")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Core learning constants
LEARNING_CYCLE_INTERVAL = 60  # seconds
KNOWLEDGE_SYNC_INTERVAL = 300  # 5 minutes
PATTERN_ANALYSIS_INTERVAL = 900  # 15 minutes
MEMORY_CONSOLIDATION_INTERVAL = 3600  # 1 hour
MAX_CONCURRENT_LEARNING_TASKS = 10
LEARNING_TIMEOUT = 30  # seconds

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class LearningEngineConfig:
    """Configuration for the core learning engine"""
    enabled: bool = True
    learning_cycle_interval: int = LEARNING_CYCLE_INTERVAL
    knowledge_sync_interval: int = KNOWLEDGE_SYNC_INTERVAL
    pattern_analysis_interval: int = PATTERN_ANALYSIS_INTERVAL
    memory_consolidation_interval: int = MEMORY_CONSOLIDATION_INTERVAL
    max_concurrent_tasks: int = MAX_CONCURRENT_LEARNING_TASKS
    learning_timeout: int = LEARNING_TIMEOUT
    auto_start_background_tasks: bool = True
    enable_real_time_learning: bool = True
    enable_adaptive_learning_rates: bool = True

@dataclass
class LearningEvent:
    """Represents a learning event in the system"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: str = ""
    agent_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "unknown"
    priority: int = 1  # 1=highest, 5=lowest

@dataclass
class LearningResult:
    """Result of a learning operation"""
    success: bool
    knowledge_items_learned: int
    patterns_discovered: int
    connections_created: int
    processing_time: float
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class LearningCycleStatus(BaseModel):
    """Status of learning cycle operations"""
    cycle_id: str
    status: str  # 'running', 'completed', 'failed'
    start_time: datetime
    end_time: Optional[datetime] = None
    events_processed: int = 0
    knowledge_created: int = 0
    patterns_found: int = 0
    agents_updated: int = 0
    errors: List[str] = []

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseLearningComponent(ABC):
    """Abstract base class for all learning components"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component=self.__class__.__name__)
        self._is_initialized = False
        self._health_status = "unknown"
    
    @abstractmethod
    async def _initialize_resources(self) -> None:
        """Initialize component-specific resources"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup component resources"""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Component health check"""
        return {
            "status": self._health_status,
            "initialized": self._is_initialized,
            "timestamp": datetime.utcnow().isoformat()
        }

class LearningEngine(BaseLearningComponent):
    """
    Core learning engine that orchestrates all learning activities.
    
    This is the central nervous system of the YMERA learning infrastructure,
    coordinating between knowledge graphs, pattern recognition, agent integration,
    external learning, memory consolidation, and metrics collection.
    """
    
    def __init__(
        self,
        config: LearningEngineConfig,
        knowledge_graph,
        pattern_engine,
        agent_integration,
        external_learning,
        memory_consolidation,
        metrics_collector
    ):
        super().__init__(config.__dict__)
        self.config = config
        self.knowledge_graph = knowledge_graph
        self.pattern_engine = pattern_engine
        self.agent_integration = agent_integration
        self.external_learning = external_learning
        self.memory_consolidation = memory_consolidation
        self.metrics_collector = metrics_collector
        
        # Learning state management
        self._learning_queue = asyncio.Queue()
        self._active_cycles = {}
        self._background_tasks = []
        self._learning_velocity = 0.0
        self._total_knowledge_items = 0
        self._system_intelligence_score = 0.0
        
        # Performance tracking
        self._cycle_performance_history = []
        self._learning_effectiveness_score = 0.0
    
    async def _initialize_resources(self) -> None:
        """Initialize core learning engine resources"""
        try:
            self.logger.info("Initializing core learning engine")
            
            # Initialize Redis connection for learning coordination
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                max_connections=20,
                retry_on_timeout=True
            )
            
            # Initialize learning event queue
            await self._initialize_learning_queue()
            
            # Start background learning tasks if enabled
            if self.config.auto_start_background_tasks:
                await self._start_background_learning_tasks()
            
            # Initialize learning metrics
            await self._initialize_learning_metrics()
            
            self._is_initialized = True
            self._health_status = "healthy"
            
            self.logger.info("Core learning engine initialized successfully")
            
        except Exception as e:
            self._health_status = "unhealthy"
            self.logger.error("Failed to initialize core learning engine", error=str(e))
            raise
    
    async def _initialize_learning_queue(self) -> None:
        """Initialize the learning event queue"""
        self._learning_queue = asyncio.Queue(maxsize=1000)
        self.logger.debug("Learning queue initialized")
    
    async def _initialize_learning_metrics(self) -> None:
        """Initialize learning performance metrics"""
        await self.metrics_collector.initialize_core_metrics({
            "learning_velocity": 0.0,
            "knowledge_retention_rate": 0.0,
            "pattern_discovery_rate": 0.0,
            "agent_collaboration_score": 0.0,
            "system_intelligence_score": 0.0
        })
    
    async def _start_background_learning_tasks(self) -> None:
        """Start all background learning processes"""
        self.logger.info("Starting background learning tasks")
        
        # Core learning cycle task
        learning_task = asyncio.create_task(
            self._continuous_learning_loop(),
            name="continuous_learning_loop"
        )
        self._background_tasks.append(learning_task)
        
        # Knowledge synchronization task
        sync_task = asyncio.create_task(
            self._inter_agent_knowledge_synchronization(),
            name="knowledge_synchronization"
        )
        self._background_tasks.append(sync_task)
        
        # Pattern discovery task
        pattern_task = asyncio.create_task(
            self._pattern_discovery_engine(),
            name="pattern_discovery"
        )
        self._background_tasks.append(pattern_task)
        
        # External learning integration task
        external_task = asyncio.create_task(
            self._external_learning_integration(),
            name="external_learning"
        )
        self._background_tasks.append(external_task)
        
        # Memory consolidation task
        memory_task = asyncio.create_task(
            self._memory_consolidation_task(),
            name="memory_consolidation"
        )
        self._background_tasks.append(memory_task)
        
        self.logger.info(f"Started {len(self._background_tasks)} background learning tasks")
    
    @track_performance
    async def process_learning_event(self, event: LearningEvent) -> LearningResult:
        """
        Process a single learning event and extract knowledge.
        
        Args:
            event: Learning event to process
            
        Returns:
            LearningResult with processing outcomes
            
        Raises:
            LearningProcessingError: When event processing fails
        """
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(
                "Processing learning event",
                event_id=event.event_id,
                event_type=event.event_type,
                agent_id=event.agent_id
            )
            
            # Validate event
            await self._validate_learning_event(event)
            
            # Extract knowledge from event
            knowledge_items = await self._extract_knowledge_from_event(event)
            
            # Update knowledge graph
            connections_created = await self.knowledge_graph.add_knowledge_batch(
                knowledge_items, 
                source=event.source,
                confidence=event.confidence
            )
            
            # Check for patterns
            patterns = await self.pattern_engine.analyze_event_patterns([event])
            
            # Update learning metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            await self._update_learning_metrics(
                knowledge_items_count=len(knowledge_items),
                patterns_count=len(patterns),
                processing_time=processing_time
            )
            
            # Create result
            result = LearningResult(
                success=True,
                knowledge_items_learned=len(knowledge_items),
                patterns_discovered=len(patterns),
                connections_created=connections_created,
                processing_time=processing_time,
                metadata={
                    "event_type": event.event_type,
                    "agent_id": event.agent_id,
                    "confidence": event.confidence
                }
            )
            
            self.logger.info(
                "Learning event processed successfully",
                event_id=event.event_id,
                knowledge_items=len(knowledge_items),
                patterns=len(patterns),
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Failed to process learning event {event.event_id}: {str(e)}"
            
            self.logger.error(
                "Learning event processing failed",
                event_id=event.event_id,
                error=str(e),
                processing_time=processing_time
            )
            
            return LearningResult(
                success=False,
                knowledge_items_learned=0,
                patterns_discovered=0,
                connections_created=0,
                processing_time=processing_time,
                errors=[error_msg]
            )
    
    async def _validate_learning_event(self, event: LearningEvent) -> None:
        """Validate learning event data"""
        if not event.event_type:
            raise ValueError("Event type is required")
        
        if not event.data:
            raise ValueError("Event data cannot be empty")
        
        if event.confidence < 0.0 or event.confidence > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
    
    async def _extract_knowledge_from_event(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """Extract knowledge items from learning event"""
        knowledge_items = []
        
        # Extract based on event type
        if event.event_type == "agent_interaction":
            knowledge_items.extend(await self._extract_interaction_knowledge(event))
        elif event.event_type == "task_completion":
            knowledge_items.extend(await self._extract_task_knowledge(event))
        elif event.event_type == "error_occurred":
            knowledge_items.extend(await self._extract_error_knowledge(event))
        elif event.event_type == "performance_metric":
            knowledge_items.extend(await self._extract_performance_knowledge(event))
        else:
            # Generic knowledge extraction
            knowledge_items.extend(await self._extract_generic_knowledge(event))
        
        return knowledge_items
    
    async def _extract_interaction_knowledge(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """Extract knowledge from agent interaction events"""
        knowledge_items = []
        
        interaction_data = event.data.get("interaction", {})
        
        # Extract communication patterns
        if "communication_pattern" in interaction_data:
            knowledge_items.append({
                "type": "communication_pattern",
                "agent_id": event.agent_id,
                "pattern": interaction_data["communication_pattern"],
                "effectiveness": interaction_data.get("effectiveness", 0.5),
                "context": interaction_data.get("context", {}),
                "timestamp": event.timestamp
            })
        
        # Extract collaboration insights
        if "collaboration_success" in interaction_data:
            knowledge_items.append({
                "type": "collaboration_insight",
                "agents_involved": interaction_data.get("participants", []),
                "success_rate": interaction_data["collaboration_success"],
                "task_type": interaction_data.get("task_type", "unknown"),
                "duration": interaction_data.get("duration", 0),
                "timestamp": event.timestamp
            })
        
        return knowledge_items
    
    async def _extract_task_knowledge(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """Extract knowledge from task completion events"""
        knowledge_items = []
        
        task_data = event.data.get("task", {})
        
        # Extract task performance patterns
        knowledge_items.append({
            "type": "task_performance",
            "agent_id": event.agent_id,
            "task_type": task_data.get("type", "unknown"),
            "completion_time": task_data.get("completion_time", 0),
            "success_rate": task_data.get("success_rate", 0.0),
            "resource_usage": task_data.get("resource_usage", {}),
            "complexity_score": task_data.get("complexity", 1.0),
            "timestamp": event.timestamp
        })
        
        # Extract optimization opportunities
        if task_data.get("optimization_suggestions"):
            knowledge_items.append({
                "type": "optimization_opportunity",
                "agent_id": event.agent_id,
                "task_type": task_data.get("type", "unknown"),
                "suggestions": task_data["optimization_suggestions"],
                "potential_improvement": task_data.get("potential_improvement", 0.0),
                "timestamp": event.timestamp
            })
        
        return knowledge_items
    
    async def _extract_error_knowledge(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """Extract knowledge from error events"""
        knowledge_items = []
        
        error_data = event.data.get("error", {})
        
        # Extract error patterns
        knowledge_items.append({
            "type": "error_pattern",
            "agent_id": event.agent_id,
            "error_type": error_data.get("type", "unknown"),
            "error_message": error_data.get("message", ""),
            "context": error_data.get("context", {}),
            "frequency": error_data.get("frequency", 1),
            "severity": error_data.get("severity", "medium"),
            "timestamp": event.timestamp
        })
        
        # Extract recovery strategies
        if error_data.get("recovery_action"):
            knowledge_items.append({
                "type": "recovery_strategy",
                "error_type": error_data.get("type", "unknown"),
                "recovery_action": error_data["recovery_action"],
                "success_rate": error_data.get("recovery_success_rate", 0.0),
                "time_to_recovery": error_data.get("recovery_time", 0),
                "timestamp": event.timestamp
            })
        
        return knowledge_items
    
    async def _extract_performance_knowledge(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """Extract knowledge from performance metric events"""
        knowledge_items = []
        
        performance_data = event.data.get("performance", {})
        
        # Extract performance trends
        knowledge_items.append({
            "type": "performance_trend",
            "agent_id": event.agent_id,
            "metric_name": performance_data.get("metric", "unknown"),
            "metric_value": performance_data.get("value", 0.0),
            "trend_direction": performance_data.get("trend", "stable"),
            "benchmark_comparison": performance_data.get("vs_benchmark", 0.0),
            "context": performance_data.get("context", {}),
            "timestamp": event.timestamp
        })
        
        return knowledge_items
    
    async def _extract_generic_knowledge(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """Extract knowledge from generic events"""
        return [{
            "type": "generic_event",
            "agent_id": event.agent_id,
            "event_type": event.event_type,
            "data": event.data,
            "confidence": event.confidence,
            "timestamp": event.timestamp
        }]
    
    async def _continuous_learning_loop(self) -> None:
        """Continuous learning loop that processes events every 60 seconds"""
        self.logger.info("Starting continuous learning loop")
        
        while True:
            try:
                cycle_id = str(uuid.uuid4())
                cycle_start = datetime.utcnow()
                
                self.logger.debug("Starting learning cycle", cycle_id=cycle_id)
                
                # Create cycle status
                cycle_status = LearningCycleStatus(
                    cycle_id=cycle_id,
                    status="running",
                    start_time=cycle_start
                )
                self._active_cycles[cycle_id] = cycle_status
                
                # Process learning events from queue
                events_processed = 0
                total_knowledge_created = 0
                total_patterns_found = 0
                
                # Process all available events in queue
                while not self._learning_queue.empty() and events_processed < 100:
                    try:
                        event = await asyncio.wait_for(
                            self._learning_queue.get(),
                            timeout=1.0
                        )
                        
                        result = await self.process_learning_event(event)
                        
                        if result.success:
                            events_processed += 1
                            total_knowledge_created += result.knowledge_items_learned
                            total_patterns_found += result.patterns_discovered
                        else:
                            cycle_status.errors.extend(result.errors)
                        
                        self._learning_queue.task_done()
                        
                    except asyncio.TimeoutError:
                        break  # No more events to process
                    except Exception as e:
                        self.logger.warning("Error processing event in learning cycle", error=str(e))
                        cycle_status.errors.append(str(e))
                
                # Update cycle status
                cycle_status.events_processed = events_processed
                cycle_status.knowledge_created = total_knowledge_created
                cycle_status.patterns_found = total_patterns_found
                cycle_status.status = "completed"
                cycle_status.end_time = datetime.utcnow()
                
                # Update learning velocity
                cycle_duration = (cycle_status.end_time - cycle_start).total_seconds()
                if cycle_duration > 0:
                    self._learning_velocity = total_knowledge_created / cycle_duration * 3600  # per hour
                
                # Record cycle performance
                self._cycle_performance_history.append({
                    "cycle_id": cycle_id,
                    "duration": cycle_duration,
                    "events_processed": events_processed,
                    "knowledge_created": total_knowledge_created,
                    "patterns_found": total_patterns_found,
                    "errors": len(cycle_status.errors)
                })
                
                # Keep only last 100 cycles
                if len(self._cycle_performance_history) > 100:
                    self._cycle_performance_history.pop(0)
                
                self.logger.info(
                    "Learning cycle completed",
                    cycle_id=cycle_id,
                    duration=cycle_duration,
                    events_processed=events_processed,
                    knowledge_created=total_knowledge_created,
                    patterns_found=total_patterns_found
                )
                
                # Clean up old cycles
                self._active_cycles.pop(cycle_id, None)
                
                # Wait for next cycle
                await asyncio.sleep(self.config.learning_cycle_interval)
                
            except Exception as e:
                self.logger.error("Error in continuous learning loop", error=str(e))
                await asyncio.sleep(self.config.learning_cycle_interval)
    
    async def _inter_agent_knowledge_synchronization(self) -> None:
        """Inter-agent knowledge synchronization every 5 minutes"""
        self.logger.info("Starting inter-agent knowledge synchronization")
        
        while True:
            try:
                sync_start = datetime.utcnow()
                
                # Get all active agents
                active_agents = await self.agent_integration.get_active_agents()
                
                # Perform knowledge synchronization
                sync_results = await self.agent_integration.synchronize_knowledge(active_agents)
                
                # Update metrics
                await self.metrics_collector.update_metric(
                    "knowledge_sync_count",
                    len(sync_results.get("successful_syncs", []))
                )
                
                sync_duration = (datetime.utcnow() - sync_start).total_seconds()
                
                self.logger.info(
                    "Knowledge synchronization completed",
                    duration=sync_duration,
                    agents_synced=len(active_agents),
                    successful_syncs=len(sync_results.get("successful_syncs", []))
                )
                
                await asyncio.sleep(self.config.knowledge_sync_interval)
                
            except Exception as e:
                self.logger.error("Error in knowledge synchronization", error=str(e))
                await asyncio.sleep(self.config.knowledge_sync_interval)
    
    async def _pattern_discovery_engine(self) -> None:
        """Pattern discovery engine that runs every 15 minutes"""
        self.logger.info("Starting pattern discovery engine")
        
        while True:
            try:
                discovery_start = datetime.utcnow()
                
                # Analyze recent patterns
                patterns = await self.pattern_engine.discover_new_patterns()
                
                # Process discovered patterns
                for pattern in patterns:
                    await self._process_discovered_pattern(pattern)
                
                discovery_duration = (datetime.utcnow() - discovery_start).total_seconds()
                
                self.logger.info(
                    "Pattern discovery completed",
                    duration=discovery_duration,
                    patterns_discovered=len(patterns)
                )
                
                await asyncio.sleep(self.config.pattern_analysis_interval)
                
            except Exception as e:
                self.logger.error("Error in pattern discovery", error=str(e))
                await asyncio.sleep(self.config.pattern_analysis_interval)
    
    async def _external_learning_integration(self) -> None:
        """External learning integration for real-time knowledge acquisition"""
        self.logger.info("Starting external learning integration")
        
        while True:
            try:
                # Process external learning sources
                external_knowledge = await self.external_learning.process_external_sources()
                
                # Integrate external knowledge
                for knowledge_item in external_knowledge:
                    await self.add_learning_event(LearningEvent(
                        event_type="external_knowledge",
                        data={"knowledge": knowledge_item},
                        source="external_learning",
                        confidence=knowledge_item.get("confidence", 0.8)
                    ))
                
                # Check for new external sources
                await self.external_learning.discover_new_sources()
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error("Error in external learning integration", error=str(e))
                await asyncio.sleep(60)
    
    async def _memory_consolidation_task(self) -> None:
        """Memory consolidation task that runs every hour"""
        self.logger.info("Starting memory consolidation task")
        
        while True:
            try:
                consolidation_start = datetime.utcnow()
                
                # Perform memory consolidation
                consolidation_results = await self.memory_consolidation.consolidate_memories()
                
                # Update system intelligence score
                await self._update_system_intelligence_score(consolidation_results)
                
                consolidation_duration = (datetime.utcnow() - consolidation_start).total_seconds()
                
                self.logger.info(
                    "Memory consolidation completed",
                    duration=consolidation_duration,
                    memories_consolidated=consolidation_results.get("consolidated_count", 0)
                )
                
                await asyncio.sleep(self.config.memory_consolidation_interval)
                
            except Exception as e:
                self.logger.error("Error in memory consolidation", error=str(e))
                await asyncio.sleep(self.config.memory_consolidation_interval)
    
    async def _process_discovered_pattern(self, pattern: Dict[str, Any]) -> None:
        """Process a newly discovered pattern"""
        try:
            # Add pattern to knowledge graph
            await self.knowledge_graph.add_pattern(pattern)
            
            # Notify relevant agents about the pattern
            await self.agent_integration.notify_pattern_discovery(pattern)
            
            # Update pattern metrics
            await self.metrics_collector.increment_metric("patterns_discovered")
            
            self.logger.info(
                "Pattern processed successfully",
                pattern_type=pattern.get("type"),
                confidence=pattern.get("confidence")
            )
            
        except Exception as e:
            self.logger.error("Failed to process discovered pattern", error=str(e))
    
    async def _update_learning_metrics(
        self,
        knowledge_items_count: int,
        patterns_count: int,
        processing_time: float
    ) -> None:
        """Update learning performance metrics"""
        try:
            # Update counters
            self._total_knowledge_items += knowledge_items_count
            
            # Update metrics collector
            await self.metrics_collector.update_metrics({
                "total_knowledge_items": self._total_knowledge_items,
                "learning_velocity": self._learning_velocity,
                "avg_processing_time": processing_time,
                "patterns_discovered_total": patterns_count
            })
            
        except Exception as e:
            self.logger.warning("Failed to update learning metrics", error=str(e))
    
    async def _update_system_intelligence_score(self, consolidation_results: Dict[str, Any]) -> None:
        """Update the overall system intelligence score"""
        try:
            # Calculate intelligence score based on various factors
            knowledge_diversity = consolidation_results.get("knowledge_diversity", 0.0)
            pattern_quality = consolidation_results.get("pattern_quality", 0.0)
            learning_efficiency = consolidation_results.get("learning_efficiency", 0.0)
            
            self._system_intelligence_score = (
                knowledge_diversity * 0.3 +
                pattern_quality * 0.4 +
                learning_efficiency * 0.3
            )
            
            await self.metrics_collector.update_metric(
                "system_intelligence_score",
                self._system_intelligence_score
            )
            
        except Exception as e:
            self.logger.warning("Failed to update system intelligence score", error=str(e))
    
    async def add_learning_event(self, event: LearningEvent) -> bool:
        """
        Add a learning event to the processing queue.
        
        Args:
            event: Learning event to add
            
        Returns:
            True if event was added successfully
        """
        try:
            await self._learning_queue.put(event)
            self.logger.debug("Learning event added to queue", event_id=event.event_id)
            return True
        except Exception as e:
            self.logger.error("Failed to add learning event", event_id=event.event_id, error=str(e))
            return False
    
    async def trigger_learning_cycle(self) -> LearningCycleStatus:
        """
        Manually trigger a learning cycle.
        
        Returns:
            Status of the triggered learning cycle
        """
        cycle_id = str(uuid.uuid4())
        
        try:
            self.logger.info("Manually triggering learning cycle", cycle_id=cycle_id)
            
            # Create and execute learning cycle
            cycle_status = LearningCycleStatus(
                cycle_id=cycle_id,
                status="running",
                start_time=datetime.utcnow()
            )
            
            # Process available events
            events_processed = 0
            while not self._learning_queue.empty() and events_processed < 50:
                try:
                    event = await asyncio.wait_for(self._learning_queue.get(), timeout=0.1)
                    result = await self.process_learning_event(event)
                    
                    if result.success:
                        events_processed += 1
                        cycle_status.knowledge_created += result.knowledge_items_learned
                        cycle_status.patterns_found += result.patterns_discovered
                    
                    self._learning_queue.task_done()
                    
                except asyncio.TimeoutError:
                    break
            
            cycle_status.events_processed = events_processed
            cycle_status.status = "completed"
            cycle_status.end_time = datetime.utcnow()
            
            return cycle_status
            
        except Exception as e:
            self.logger.error("Failed to trigger learning cycle", cycle_id=cycle_id, error=str(e))
            return LearningCycleStatus(
                cycle_id=cycle_id,
                status="failed",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                errors=[str(e)]
            )
    
    async def get_learning_status(self) -> Dict[str, Any]:
        """
        Get comprehensive learning engine status.
        
        Returns:
            Dictionary containing learning engine status and metrics
        """
        try:
            # Calculate performance metrics
            avg_cycle_duration = 0.0
            if self._cycle_performance_history:
                avg_cycle_duration = sum(
                    cycle["duration"] for cycle in self._cycle_performance_history
                ) / len(self._cycle_performance_history)
            
            # Get queue status
            queue_size = self._learning_queue.qsize()
            
            # Get active cycles
            active_cycles_count = len(self._active_cycles)
            
            # Get component health
            component_health = {}
            for component_name, component in [
                ("knowledge_graph", self.knowledge_graph),
                ("pattern_engine", self.pattern_engine),
                ("agent_integration", self.agent_integration),
                ("external_learning", self.external_learning),
                ("memory_consolidation", self.memory_consolidation),
                ("metrics_collector", self.metrics_collector)
            ]:
                component_health[component_name] = await component.health_check()
            
            return {
                "status": self._health_status,
                "initialized": self._is_initialized,
                "learning_velocity": self._learning_velocity,
                "total_knowledge_items": self._total_knowledge_items,
                "system_intelligence_score": self._system_intelligence_score,
                "queue_size": queue_size,
                "active_cycles": active_cycles_count,
                "background_tasks_running": len([
                    task for task in self._background_tasks if not task.done()
                ]),
                "avg_cycle_duration": avg_cycle_duration,
                "recent_cycles": self._cycle_performance_history[-10:],
                "component_health": component_health,
                "config": {
                    "learning_cycle_interval": self.config.learning_cycle_interval,
                    "knowledge_sync_interval": self.config.knowledge_sync_interval,
                    "pattern_analysis_interval": self.config.pattern_analysis_interval,
                    "memory_consolidation_interval": self.config.memory_consolidation_interval
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get learning status", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def cleanup(self) -> None:
        """Cleanup learning engine resources"""
        try:
            self.logger.info("Cleaning up learning engine resources")
            
            # Cancel background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            self._background_tasks.clear()
            
            # Close Redis connection
            if hasattr(self, '_redis_client'):
                await self._redis_client.close()
            
            # Clear learning queue
            while not self._learning_queue.empty():
                try:
                    self._learning_queue.get_nowait()
                    self._learning_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            
            self._health_status = "stopped"
            self.logger.info("Learning engine cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during learning engine cleanup", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def create_learning_engine(
    config: Optional[LearningEngineConfig] = None,
    **components
) -> LearningEngine:
    """
    Create and initialize a learning engine instance.
    
    Args:
        config: Learning engine configuration
        **components: Required learning components
        
    Returns:
        Initialized LearningEngine instance
    """
    if config is None:
        config = LearningEngineConfig()
    
    required_components = [
        "knowledge_graph", "pattern_engine", "agent_integration",
        "external_learning", "memory_consolidation", "metrics_collector"
    ]
    
    for component_name in required_components:
        if component_name not in components:
            raise ValueError(f"Required component '{component_name}' not provided")
    
    engine = LearningEngine(config, **components)
    await engine._initialize_resources()
    
    return engine

async def health_check() -> Dict[str, Any]:
    """Learning engine module health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "core_learning_engine",
        "version": "4.0"
    }

# ===============================================================================
# EXCEPTION CLASSES
# ===============================================================================

class LearningEngineError(Exception):
    """Base exception for learning engine errors"""
    pass

class LearningProcessingError(LearningEngineError):
    """Raised when learning event processing fails"""
    pass

class LearningCycleError(LearningEngineError):
    """Raised when learning cycle execution fails"""
    pass

class ComponentIntegrationError(LearningEngineError):
    """Raised when component integration fails"""
    pass

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "LearningEngine",
    "LearningEngineConfig",
    "LearningEvent",
    "LearningResult",
    "LearningCycleStatus",
    "create_learning_engine",
    "health_check",
    "LearningEngineError",
    "LearningProcessingError",
    "LearningCycleError",
    "ComponentIntegrationError"
]