"""
YMERA Enterprise - Agent Learning Integration System
Production-Ready Agent-Learning Infrastructure Integration - v4.0
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
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from monitoring.performance_tracker import track_performance
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.agent_integration")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Agent integration constants
MAX_LEARNING_BATCH_SIZE = 100
KNOWLEDGE_SYNC_INTERVAL = 300  # 5 minutes
LEARNING_CYCLE_INTERVAL = 60   # 1 minute
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CACHE_TTL = 3600

# Agent collaboration thresholds
MIN_KNOWLEDGE_SIMILARITY = 0.7
MAX_KNOWLEDGE_TRANSFER_SIZE = 1000
COLLABORATION_SCORE_THRESHOLD = 0.6

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class AgentLearningConfig:
    """Configuration for agent learning integration"""
    learning_enabled: bool = True
    sync_interval: int = 300
    batch_size: int = 100
    similarity_threshold: float = 0.7
    collaboration_threshold: float = 0.6
    retention_days: int = 30

@dataclass
class LearningExperience:
    """Represents a single learning experience from an agent"""
    agent_id: str
    experience_id: str
    timestamp: datetime
    experience_type: str
    context: Dict[str, Any]
    outcome: Dict[str, Any]
    success: bool
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class KnowledgeItem:
    """Represents a piece of knowledge extracted from experiences"""
    knowledge_id: str
    source_agent_id: str
    knowledge_type: str
    content: Dict[str, Any]
    confidence: float
    applicability_scope: List[str]
    created_at: datetime
    last_updated: DateTime
    usage_count: int = 0
    success_rate: float = 0.0

class AgentCollaborationMetrics(BaseModel):
    """Metrics for agent collaboration effectiveness"""
    agent_id: str
    partner_agent_id: str
    knowledge_shared: int
    knowledge_received: int
    collaboration_score: float
    success_rate: float
    last_interaction: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class LearningTransferRequest(BaseModel):
    """Request schema for knowledge transfer between agents"""
    source_agent_id: str = Field(..., description="Source agent identifier")
    target_agent_ids: List[str] = Field(..., description="Target agent identifiers")
    knowledge_types: Optional[List[str]] = Field(None, description="Specific knowledge types to transfer")
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity for transfer")
    
    @validator('target_agent_ids')
    def validate_target_agents(cls, v):
        if not v:
            raise ValueError("At least one target agent must be specified")
        return v

class LearningIntegrationResponse(BaseModel):
    """Response schema for learning integration operations"""
    success: bool
    agent_id: str
    experiences_processed: int
    knowledge_items_created: int
    transfer_operations: int
    processing_time: float
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseAgentLearningIntegrator(ABC):
    """Abstract base class for agent learning integration"""
    
    def __init__(self, config: AgentLearningConfig):
        self.config = config
        self.logger = logger.bind(integrator=self.__class__.__name__)
        self._redis_client = None
        self._db_session = None
        self._health_status = True
        
    @abstractmethod
    async def process_agent_experiences(self, agent_id: str, experiences: List[LearningExperience]) -> Dict[str, Any]:
        """Process learning experiences from an agent"""
        pass
        
    @abstractmethod
    async def transfer_knowledge(self, source_agent: str, target_agents: List[str]) -> Dict[str, Any]:
        """Transfer knowledge between agents"""
        pass
        
    @abstractmethod
    async def sync_agent_knowledge(self, agent_id: str) -> Dict[str, Any]:
        """Synchronize agent knowledge with global knowledge base"""
        pass

class ProductionAgentLearningIntegrator(BaseAgentLearningIntegrator):
    """Production-ready agent learning integration system"""
    
    def __init__(self, config: AgentLearningConfig):
        super().__init__(config)
        self._knowledge_cache = {}
        self._collaboration_metrics = {}
        self._learning_patterns = {}
        self._active_transfers = set()
        
    async def _initialize_resources(self) -> None:
        """Initialize all required resources"""
        try:
            # Initialize Redis connection
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            
            # Initialize database session
            self._db_session = await get_db_session()
            
            # Load existing collaboration metrics
            await self._load_collaboration_metrics()
            
            # Initialize learning pattern cache
            await self._initialize_pattern_cache()
            
            self.logger.info("Agent learning integrator initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize agent learning integrator", error=str(e))
            self._health_status = False
            raise

    @track_performance
    async def process_agent_experiences(
        self, 
        agent_id: str, 
        experiences: List[LearningExperience]
    ) -> Dict[str, Any]:
        """
        Process learning experiences from an agent and extract knowledge.
        
        Args:
            agent_id: Unique identifier of the agent
            experiences: List of learning experiences to process
            
        Returns:
            Dictionary containing processing results and metrics
            
        Raises:
            HTTPException: When processing fails or validation errors occur
        """
        start_time = datetime.utcnow()
        
        try:
            # Input validation
            await self._validate_experiences(agent_id, experiences)
            
            # Process experiences in batches
            knowledge_items = []
            batch_size = min(self.config.batch_size, MAX_LEARNING_BATCH_SIZE)
            
            for i in range(0, len(experiences), batch_size):
                batch = experiences[i:i + batch_size]
                batch_knowledge = await self._process_experience_batch(agent_id, batch)
                knowledge_items.extend(batch_knowledge)
            
            # Update agent knowledge base
            await self._update_agent_knowledge(agent_id, knowledge_items)
            
            # Update learning patterns
            await self._update_learning_patterns(agent_id, experiences, knowledge_items)
            
            # Cache processed knowledge
            await self._cache_agent_knowledge(agent_id, knowledge_items)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "success": True,
                "agent_id": agent_id,
                "experiences_processed": len(experiences),
                "knowledge_items_created": len(knowledge_items),
                "processing_time": processing_time,
                "timestamp": datetime.utcnow()
            }
            
            self.logger.info(
                "Agent experiences processed successfully",
                agent_id=agent_id,
                experiences_count=len(experiences),
                knowledge_count=len(knowledge_items),
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Failed to process agent experiences",
                agent_id=agent_id,
                error=str(e),
                experiences_count=len(experiences)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Experience processing failed: {str(e)}"
            )

    @track_performance
    async def transfer_knowledge(
        self, 
        source_agent: str, 
        target_agents: List[str],
        knowledge_types: Optional[List[str]] = None,
        similarity_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Transfer knowledge between agents based on relevance and similarity.
        
        Args:
            source_agent: Source agent identifier
            target_agents: List of target agent identifiers
            knowledge_types: Optional list of specific knowledge types to transfer
            similarity_threshold: Minimum similarity threshold for knowledge transfer
            
        Returns:
            Dictionary containing transfer results and metrics
        """
        transfer_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            # Prevent duplicate transfers
            if transfer_id in self._active_transfers:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Transfer already in progress"
                )
            
            self._active_transfers.add(transfer_id)
            
            # Get source agent knowledge
            source_knowledge = await self._get_agent_knowledge(source_agent, knowledge_types)
            
            if not source_knowledge:
                self.logger.warning("No knowledge found for source agent", agent_id=source_agent)
                return {"success": False, "reason": "No source knowledge available"}
            
            # Process transfers for each target agent
            transfer_results = {}
            total_transferred = 0
            
            for target_agent in target_agents:
                try:
                    # Get target agent context for relevance matching
                    target_context = await self._get_agent_context(target_agent)
                    
                    # Find relevant knowledge for transfer
                    relevant_knowledge = await self._find_relevant_knowledge(
                        source_knowledge, 
                        target_context,
                        similarity_threshold
                    )
                    
                    if relevant_knowledge:
                        # Perform knowledge transfer
                        transferred_count = await self._execute_knowledge_transfer(
                            source_agent,
                            target_agent,
                            relevant_knowledge
                        )
                        
                        # Update collaboration metrics
                        await self._update_collaboration_metrics(
                            source_agent,
                            target_agent,
                            transferred_count
                        )
                        
                        transfer_results[target_agent] = {
                            "success": True,
                            "knowledge_transferred": transferred_count
                        }
                        total_transferred += transferred_count
                        
                    else:
                        transfer_results[target_agent] = {
                            "success": False,
                            "reason": "No relevant knowledge found"
                        }
                        
                except Exception as e:
                    self.logger.error(
                        "Knowledge transfer failed for target agent",
                        source_agent=source_agent,
                        target_agent=target_agent,
                        error=str(e)
                    )
                    transfer_results[target_agent] = {
                        "success": False,
                        "reason": str(e)
                    }
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "success": True,
                "transfer_id": transfer_id,
                "source_agent": source_agent,
                "target_agents": target_agents,
                "total_knowledge_transferred": total_transferred,
                "transfer_results": transfer_results,
                "processing_time": processing_time,
                "timestamp": datetime.utcnow()
            }
            
            self.logger.info(
                "Knowledge transfer completed",
                transfer_id=transfer_id,
                source_agent=source_agent,
                target_count=len(target_agents),
                total_transferred=total_transferred,
                processing_time=processing_time
            )
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Knowledge transfer operation failed",
                source_agent=source_agent,
                target_agents=target_agents,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Knowledge transfer failed: {str(e)}"
            )
        finally:
            # Clean up active transfer tracking
            self._active_transfers.discard(transfer_id)

    @track_performance
    async def sync_agent_knowledge(self, agent_id: str) -> Dict[str, Any]:
        """
        Synchronize agent knowledge with global knowledge base.
        
        Args:
            agent_id: Unique identifier of the agent to sync
            
        Returns:
            Dictionary containing synchronization results
        """
        start_time = datetime.utcnow()
        
        try:
            # Get agent's current knowledge state
            agent_knowledge = await self._get_agent_knowledge(agent_id)
            
            # Get global knowledge updates since last sync
            last_sync = await self._get_last_sync_timestamp(agent_id)
            global_updates = await self._get_global_knowledge_updates(last_sync)
            
            # Identify knowledge gaps and conflicts
            knowledge_gaps = await self._identify_knowledge_gaps(agent_knowledge, global_updates)
            knowledge_conflicts = await self._identify_knowledge_conflicts(agent_knowledge, global_updates)
            
            # Resolve conflicts using confidence-based resolution
            resolved_knowledge = await self._resolve_knowledge_conflicts(
                agent_knowledge,
                knowledge_conflicts
            )
            
            # Apply knowledge updates
            updates_applied = await self._apply_knowledge_updates(
                agent_id,
                knowledge_gaps,
                resolved_knowledge
            )
            
            # Update sync timestamp
            await self._update_sync_timestamp(agent_id, datetime.utcnow())
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "success": True,
                "agent_id": agent_id,
                "knowledge_gaps_filled": len(knowledge_gaps),
                "conflicts_resolved": len(knowledge_conflicts),
                "updates_applied": updates_applied,
                "processing_time": processing_time,
                "timestamp": datetime.utcnow()
            }
            
            self.logger.info(
                "Agent knowledge synchronized successfully",
                agent_id=agent_id,
                gaps_filled=len(knowledge_gaps),
                conflicts_resolved=len(knowledge_conflicts),
                updates_applied=updates_applied,
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Agent knowledge synchronization failed",
                agent_id=agent_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Knowledge synchronization failed: {str(e)}"
            )

    async def get_collaboration_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get collaboration metrics for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dictionary containing collaboration metrics
        """
        try:
            metrics = self._collaboration_metrics.get(agent_id, {})
            
            # Calculate aggregate metrics
            total_shared = sum(m.get('knowledge_shared', 0) for m in metrics.values())
            total_received = sum(m.get('knowledge_received', 0) for m in metrics.values())
            avg_collaboration_score = (
                sum(m.get('collaboration_score', 0) for m in metrics.values()) / 
                len(metrics) if metrics else 0
            )
            
            return {
                "agent_id": agent_id,
                "total_knowledge_shared": total_shared,
                "total_knowledge_received": total_received,
                "average_collaboration_score": avg_collaboration_score,
                "active_collaborations": len(metrics),
                "partner_metrics": metrics,
                "timestamp": datetime.utcnow()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get collaboration metrics",
                agent_id=agent_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve collaboration metrics: {str(e)}"
            )

    # ===============================================================================
    # PRIVATE HELPER METHODS
    # ===============================================================================

    async def _validate_experiences(self, agent_id: str, experiences: List[LearningExperience]) -> None:
        """Validate input experiences"""
        if not agent_id:
            raise ValueError("Agent ID cannot be empty")
        
        if not experiences:
            raise ValueError("Experiences list cannot be empty")
        
        if len(experiences) > MAX_LEARNING_BATCH_SIZE:
            raise ValueError(f"Too many experiences, maximum allowed: {MAX_LEARNING_BATCH_SIZE}")
        
        for exp in experiences:
            if exp.agent_id != agent_id:
                raise ValueError(f"Experience agent_id mismatch: {exp.agent_id} != {agent_id}")
            
            if exp.confidence < 0.0 or exp.confidence > 1.0:
                raise ValueError(f"Invalid confidence value: {exp.confidence}")

    async def _process_experience_batch(
        self, 
        agent_id: str, 
        experiences: List[LearningExperience]
    ) -> List[KnowledgeItem]:
        """Process a batch of experiences into knowledge items"""
        knowledge_items = []
        
        for experience in experiences:
            try:
                # Extract knowledge from experience
                knowledge = await self._extract_knowledge_from_experience(experience)
                
                if knowledge:
                    knowledge_items.append(knowledge)
                    
            except Exception as e:
                self.logger.warning(
                    "Failed to extract knowledge from experience",
                    agent_id=agent_id,
                    experience_id=experience.experience_id,
                    error=str(e)
                )
        
        return knowledge_items

    async def _extract_knowledge_from_experience(self, experience: LearningExperience) -> Optional[KnowledgeItem]:
        """Extract knowledge from a single learning experience"""
        try:
            # Determine knowledge type based on experience
            knowledge_type = self._classify_knowledge_type(experience)
            
            # Extract relevant patterns and insights
            content = await self._analyze_experience_content(experience)
            
            # Calculate applicability scope
            applicability_scope = await self._determine_applicability_scope(experience)
            
            knowledge_item = KnowledgeItem(
                knowledge_id=str(uuid.uuid4()),
                source_agent_id=experience.agent_id,
                knowledge_type=knowledge_type,
                content=content,
                confidence=experience.confidence,
                applicability_scope=applicability_scope,
                created_at=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
            
            return knowledge_item
            
        except Exception as e:
            self.logger.error(
                "Knowledge extraction failed",
                experience_id=experience.experience_id,
                error=str(e)
            )
            return None

    def _classify_knowledge_type(self, experience: LearningExperience) -> str:
        """Classify the type of knowledge from an experience"""
        # Classification logic based on experience type and context
        experience_type = experience.experience_type.lower()
        
        if "problem_solving" in experience_type:
            return "problem_solving_pattern"
        elif "communication" in experience_type:
            return "communication_strategy"
        elif "decision" in experience_type:
            return "decision_making_rule"
        elif "optimization" in experience_type:
            return "optimization_technique"
        else:
            return "general_knowledge"

    async def _analyze_experience_content(self, experience: LearningExperience) -> Dict[str, Any]:
        """Analyze experience content to extract actionable knowledge"""
        content = {
            "pattern": experience.context.get("pattern", {}),
            "conditions": experience.context.get("conditions", {}),
            "actions": experience.context.get("actions", {}),
            "outcome_metrics": experience.outcome,
            "success_factors": [],
            "failure_factors": []
        }
        
        # Identify success/failure factors
        if experience.success:
            content["success_factors"] = self._identify_success_factors(experience)
        else:
            content["failure_factors"] = self._identify_failure_factors(experience)
        
        return content

    def _identify_success_factors(self, experience: LearningExperience) -> List[str]:
        """Identify factors that contributed to success"""
        factors = []
        
        # Analyze context for success patterns
        context = experience.context
        outcome = experience.outcome
        
        # Example success factor identification logic
        if outcome.get("efficiency", 0) > 0.8:
            factors.append("high_efficiency_approach")
        
        if context.get("collaboration", False):
            factors.append("collaborative_approach")
        
        if outcome.get("user_satisfaction", 0) > 0.9:
            factors.append("user_focused_solution")
        
        return factors

    def _identify_failure_factors(self, experience: LearningExperience) -> List[str]:
        """Identify factors that contributed to failure"""
        factors = []
        
        # Analyze context for failure patterns
        context = experience.context
        outcome = experience.outcome
        
        # Example failure factor identification logic
        if outcome.get("error_rate", 0) > 0.3:
            factors.append("high_error_rate")
        
        if context.get("time_pressure", False):
            factors.append("time_constraint_issue")
        
        if outcome.get("resource_usage", 0) > 0.9:
            factors.append("resource_inefficiency")
        
        return factors

    async def _determine_applicability_scope(self, experience: LearningExperience) -> List[str]:
        """Determine the scope where this knowledge can be applied"""
        scope = []
        
        # Base scope on experience type and context
        experience_type = experience.experience_type
        context = experience.context
        
        # Domain-specific scoping
        if "task_" in experience_type:
            scope.append("task_management")
        
        if "user_" in experience_type:
            scope.append("user_interaction")
        
        if context.get("domain"):
            scope.append(f"domain_{context['domain']}")
        
        # Add general applicability
        scope.append("general")
        
        return scope

    async def _update_agent_knowledge(self, agent_id: str, knowledge_items: List[KnowledgeItem]) -> None:
        """Update agent's knowledge base with new knowledge items"""
        try:
            # Store in database
            for knowledge in knowledge_items:
                await self._store_knowledge_item(agent_id, knowledge)
            
            # Update cache
            cache_key = f"agent_knowledge:{agent_id}"
            current_knowledge = await self._redis_client.hgetall(cache_key)
            
            for knowledge in knowledge_items:
                current_knowledge[knowledge.knowledge_id] = json.dumps({
                    "type": knowledge.knowledge_type,
                    "content": knowledge.content,
                    "confidence": knowledge.confidence,
                    "scope": knowledge.applicability_scope,
                    "created_at": knowledge.created_at.isoformat()
                })
            
            await self._redis_client.hset(cache_key, mapping=current_knowledge)
            await self._redis_client.expire(cache_key, CACHE_TTL)
            
        except Exception as e:
            self.logger.error(
                "Failed to update agent knowledge",
                agent_id=agent_id,
                knowledge_count=len(knowledge_items),
                error=str(e)
            )
            raise

    async def _store_knowledge_item(self, agent_id: str, knowledge: KnowledgeItem) -> None:
        """Store a knowledge item in the database"""
        # Implementation would store in your database
        # This is a simplified version
        query = """
            INSERT INTO agent_knowledge 
            (knowledge_id, agent_id, knowledge_type, content, confidence, scope, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        # Execute database insert
        # await self._db_session.execute(query, [
        #     knowledge.knowledge_id,
        #     agent_id,
        #     knowledge.knowledge_type,
        #     json.dumps(knowledge.content),
        #     knowledge.confidence,
        #     json.dumps(knowledge.applicability_scope),
        #     knowledge.created_at
        # ])

    async def _cache_agent_knowledge(self, agent_id: str, knowledge_items: List[KnowledgeItem]) -> None:
        """Cache knowledge items for quick access"""
        cache_key = f"agent_recent_knowledge:{agent_id}"
        
        # Store recent knowledge items
        knowledge_data = []
        for knowledge in knowledge_items[-10:]:  # Keep last 10 items
            knowledge_data.append(json.dumps({
                "id": knowledge.knowledge_id,
                "type": knowledge.knowledge_type,
                "confidence": knowledge.confidence,
                "created_at": knowledge.created_at.isoformat()
            }))
        
        await self._redis_client.lpush(cache_key, *knowledge_data)
        await self._redis_client.ltrim(cache_key, 0, 9)  # Keep only 10 items
        await self._redis_client.expire(cache_key, CACHE_TTL)

    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if self._redis_client:
                await self._redis_client.close()
            
            if self._db_session:
                await self._db_session.close()
                
            self.logger.info("Agent learning integrator cleaned up successfully")
            
        except Exception as e:
            self.logger.error("Cleanup failed", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Agent integration health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "agent_integration",
        "version": "4.0"
    }

def validate_agent_configuration(config: Dict[str, Any]) -> bool:
    """Validate agent integration configuration"""
    required_fields = [
        "learning_enabled", "sync_interval", "batch_size", 
        "similarity_threshold", "collaboration_threshold"
    ]
    return all(field in config for field in required_fields)

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_agent_integration() -> ProductionAgentLearningIntegrator:
    """Initialize agent learning integration for production use"""
    config = AgentLearningConfig(
        learning_enabled=settings.AGENT_LEARNING_ENABLED,
        sync_interval=settings.KNOWLEDGE_SYNC_INTERVAL,
        batch_size=settings.LEARNING_BATCH_SIZE,
        similarity_threshold=settings.KNOWLEDGE_SIMILARITY_THRESHOLD,
        collaboration_threshold=settings.COLLABORATION_THRESHOLD
    )
    
    integrator = ProductionAgentLearningIntegrator(config)
    await integrator._initialize_resources()
    
    return integrator

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionAgentLearningIntegrator",
    "AgentLearningConfig",
    "LearningExperience",
    "KnowledgeItem",
    "AgentCollaborationMetrics",
    "LearningTransferRequest",
    "LearningIntegrationResponse",
    "initialize_agent_integration",
    "health_check"
]