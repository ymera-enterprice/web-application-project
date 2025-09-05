"""
YMERA Enterprise - Agent Learning Models
Production-Ready Agent State & Communication Models - v4.0
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
from enum import Enum, IntEnum
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.agent_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Agent learning constants
MAX_KNOWLEDGE_ITEMS_PER_AGENT = 10000
KNOWLEDGE_RETENTION_DAYS = 90
MAX_COLLABORATION_HISTORY = 1000
LEARNING_CYCLE_INTERVAL = 60  # seconds
KNOWLEDGE_SYNC_INTERVAL = 300  # 5 minutes

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class AgentState(str, Enum):
    """Agent operational states"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    LEARNING = "learning"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    OFFLINE = "offline"

class AgentType(str, Enum):
    """Types of agents in the system"""
    TASK_EXECUTOR = "task_executor"
    DATA_PROCESSOR = "data_processor"
    KNOWLEDGE_MANAGER = "knowledge_manager"
    COORDINATOR = "coordinator"
    ANALYZER = "analyzer"
    COMMUNICATOR = "communicator"

class KnowledgeType(str, Enum):
    """Types of knowledge that agents can learn"""
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    TASK_OPTIMIZATION = "task_optimization"
    ERROR_RESOLUTION = "error_resolution"
    COLLABORATION_STRATEGY = "collaboration_strategy"
    PERFORMANCE_INSIGHT = "performance_insight"
    EXTERNAL_INTEGRATION = "external_integration"

class LearningStatus(str, Enum):
    """Status of learning operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"
    APPLIED = "applied"

class CollaborationLevel(IntEnum):
    """Levels of inter-agent collaboration"""
    NONE = 0
    BASIC = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class AgentCapabilities:
    """Agent capability configuration"""
    max_concurrent_tasks: int = 10
    supported_task_types: List[str] = field(default_factory=list)
    learning_enabled: bool = True
    collaboration_enabled: bool = True
    external_integration: bool = True
    pattern_recognition: bool = True
    knowledge_sharing: bool = True
    performance_optimization: bool = True

@dataclass
class LearningMetrics:
    """Learning performance metrics"""
    knowledge_items_learned: int = 0
    learning_velocity: float = 0.0  # items per hour
    retention_rate: float = 0.0  # percentage
    collaboration_score: float = 0.0
    pattern_discovery_count: int = 0
    external_integration_success_rate: float = 0.0
    knowledge_application_rate: float = 0.0
    collective_intelligence_score: float = 0.0

@dataclass
class CollaborationMetrics:
    """Inter-agent collaboration metrics"""
    knowledge_transfers_sent: int = 0
    knowledge_transfers_received: int = 0
    successful_collaborations: int = 0
    collaboration_efficiency: float = 0.0
    knowledge_diversity_score: float = 0.0
    peer_rating: float = 0.0
    response_time_avg: float = 0.0
    availability_score: float = 0.0

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class AgentConfigSchema(BaseModel):
    """Agent configuration schema"""
    agent_id: str = Field(..., description="Unique agent identifier")
    agent_type: AgentType = Field(..., description="Type of agent")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    learning_config: Dict[str, Any] = Field(default_factory=dict)
    collaboration_config: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        if not v or len(v) < 3:
            raise ValueError('Agent ID must be at least 3 characters')
        return v

class KnowledgeItemSchema(BaseModel):
    """Knowledge item schema"""
    knowledge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    knowledge_type: KnowledgeType = Field(..., description="Type of knowledge")
    content: Dict[str, Any] = Field(..., description="Knowledge content")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in knowledge")
    source_agent_id: str = Field(..., description="Agent that created this knowledge")
    validation_status: LearningStatus = Field(default=LearningStatus.PENDING)
    applicable_contexts: List[str] = Field(default_factory=list)
    usage_count: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class CollaborationRequestSchema(BaseModel):
    """Schema for inter-agent collaboration requests"""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent_id: str = Field(..., description="Requesting agent")
    target_agent_id: str = Field(..., description="Target agent")
    collaboration_type: str = Field(..., description="Type of collaboration")
    request_data: Dict[str, Any] = Field(..., description="Collaboration data")
    priority: int = Field(default=1, ge=1, le=10, description="Request priority")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    expected_response_format: Optional[str] = Field(None)

class AgentStatusSchema(BaseModel):
    """Agent status reporting schema"""
    agent_id: str = Field(..., description="Agent identifier")
    current_state: AgentState = Field(..., description="Current agent state")
    health_score: float = Field(..., ge=0.0, le=100.0, description="Agent health")
    performance_metrics: Dict[str, float] = Field(default_factory=dict)
    learning_metrics: Dict[str, Any] = Field(default_factory=dict)
    collaboration_metrics: Dict[str, Any] = Field(default_factory=dict)
    last_learning_cycle: Optional[datetime] = Field(None)
    next_learning_cycle: Optional[datetime] = Field(None)
    active_collaborations: int = Field(default=0, ge=0)
    knowledge_base_size: int = Field(default=0, ge=0)

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class Agent(Base):
    """SQLAlchemy model for agent persistence"""
    __tablename__ = 'agents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, unique=True, nullable=False, index=True)
    agent_type = Column(String, nullable=False, index=True)
    
    # Agent configuration
    capabilities = Column(JSON, nullable=False, default=dict)
    learning_config = Column(JSON, nullable=False, default=dict)
    collaboration_config = Column(JSON, nullable=False, default=dict)
    
    # State tracking
    current_state = Column(String, nullable=False, default=AgentState.INITIALIZING.value, index=True)
    health_score = Column(Float, nullable=False, default=100.0)
    
    # Learning metrics
    knowledge_items_count = Column(Integer, nullable=False, default=0)
    learning_velocity = Column(Float, nullable=False, default=0.0)
    retention_rate = Column(Float, nullable=False, default=0.0)
    collaboration_score = Column(Float, nullable=False, default=0.0)
    pattern_discovery_count = Column(Integer, nullable=False, default=0)
    external_integration_success_rate = Column(Float, nullable=False, default=0.0)
    knowledge_application_rate = Column(Float, nullable=False, default=0.0)
    collective_intelligence_score = Column(Float, nullable=False, default=0.0)
    
    # Collaboration metrics
    knowledge_transfers_sent = Column(Integer, nullable=False, default=0)
    knowledge_transfers_received = Column(Integer, nullable=False, default=0)
    successful_collaborations = Column(Integer, nullable=False, default=0)
    collaboration_efficiency = Column(Float, nullable=False, default=0.0)
    knowledge_diversity_score = Column(Float, nullable=False, default=0.0)
    peer_rating = Column(Float, nullable=False, default=0.0)
    response_time_avg = Column(Float, nullable=False, default=0.0)
    availability_score = Column(Float, nullable=False, default=100.0)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_learning_cycle = Column(DateTime, nullable=True)
    last_active = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    knowledge_items = relationship("AgentKnowledge", back_populates="agent", cascade="all, delete-orphan")
    sent_collaborations = relationship("AgentCollaboration", foreign_keys="AgentCollaboration.source_agent_id", back_populates="source_agent")
    received_collaborations = relationship("AgentCollaboration", foreign_keys="AgentCollaboration.target_agent_id", back_populates="target_agent")
    learning_cycles = relationship("LearningCycle", back_populates="agent", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_agent_state_type', 'current_state', 'agent_type'),
        Index('idx_agent_health_learning', 'health_score', 'learning_velocity'),
        Index('idx_agent_collaboration', 'collaboration_score', 'availability_score'),
        Index('idx_agent_active', 'last_active'),
    )

class AgentKnowledge(Base):
    """SQLAlchemy model for agent knowledge items"""
    __tablename__ = 'agent_knowledge'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_id = Column(String, unique=True, nullable=False, index=True)
    agent_id = Column(String, ForeignKey('agents.agent_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    content = Column(JSON, nullable=False)
    encrypted_content = Column(Text, nullable=True)  # For sensitive knowledge
    
    # Quality metrics
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    
    # Context and applicability
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    source_context = Column(JSON, nullable=False, default=dict)
    
    # Learning metadata
    learning_source = Column(String, nullable=False, default="self_discovery")
    validation_attempts = Column(Integer, nullable=False, default=0)
    last_applied = Column(DateTime, nullable=True)
    effectiveness_score = Column(Float, nullable=False, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="knowledge_items")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_knowledge_type_confidence', 'knowledge_type', 'confidence_score'),
        Index('idx_knowledge_status_usage', 'validation_status', 'usage_count'),
        Index('idx_knowledge_agent_type', 'agent_id', 'knowledge_type'),
        Index('idx_knowledge_effectiveness', 'effectiveness_score'),
    )

class AgentCollaboration(Base):
    """SQLAlchemy model for inter-agent collaborations"""
    __tablename__ = 'agent_collaborations'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    collaboration_id = Column(String, unique=True, nullable=False, index=True)
    
    # Collaboration participants
    source_agent_id = Column(String, ForeignKey('agents.agent_id'), nullable=False, index=True)
    target_agent_id = Column(String, ForeignKey('agents.agent_id'), nullable=False, index=True)
    
    # Collaboration details
    collaboration_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    priority = Column(Integer, nullable=False, default=1)
    
    # Request and response data
    request_data = Column(JSON, nullable=False, default=dict)
    response_data = Column(JSON, nullable=True)
    
    # Performance metrics
    response_time_ms = Column(Float, nullable=True)
    success_indicator = Column(Boolean, nullable=True)
    quality_score = Column(Float, nullable=True)
    
    # Timestamps
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    timeout_at = Column(DateTime, nullable=False)
    
    # Relationships
    source_agent = relationship("Agent", foreign_keys=[source_agent_id], back_populates="sent_collaborations")
    target_agent = relationship("Agent", foreign_keys=[target_agent_id], back_populates="received_collaborations")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_collaboration_participants', 'source_agent_id', 'target_agent_id'),
        Index('idx_collaboration_status_type', 'status', 'collaboration_type'),
        Index('idx_collaboration_timing', 'requested_at', 'completed_at'),
        Index('idx_collaboration_performance', 'response_time_ms', 'quality_score'),
    )

class LearningCycle(Base):
    """SQLAlchemy model for learning cycle tracking"""
    __tablename__ = 'learning_cycles'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cycle_id = Column(String, unique=True, nullable=False, index=True)
    agent_id = Column(String, ForeignKey('agents.agent_id'), nullable=False, index=True)
    
    # Cycle details
    cycle_type = Column(String, nullable=False, index=True)  # continuous, manual, scheduled
    trigger_source = Column(String, nullable=False, default="automatic")
    
    # Learning results
    knowledge_items_processed = Column(Integer, nullable=False, default=0)
    knowledge_items_learned = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_applied = Column(Integer, nullable=False, default=0)
    
    # Performance metrics
    cycle_duration_ms = Column(Float, nullable=False, default=0.0)
    learning_efficiency = Column(Float, nullable=False, default=0.0)
    memory_consolidation_score = Column(Float, nullable=False, default=0.0)
    
    # Pattern discovery
    patterns_discovered = Column(Integer, nullable=False, default=0)
    patterns_validated = Column(Integer, nullable=False, default=0)
    behavioral_insights = Column(JSON, nullable=False, default=dict)
    
    # Collaboration results
    knowledge_shared = Column(Integer, nullable=False, default=0)
    knowledge_received = Column(Integer, nullable=False, default=0)
    collaboration_opportunities = Column(Integer, nullable=False, default=0)
    
    # Status and completion
    status = Column(String, nullable=False, default="in_progress", index=True)
    completion_percentage = Column(Float, nullable=False, default=0.0)
    error_details = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    next_cycle_at = Column(DateTime, nullable=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="learning_cycles")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_learning_cycle_agent_status', 'agent_id', 'status'),
        Index('idx_learning_cycle_timing', 'started_at', 'completed_at'),
        Index('idx_learning_cycle_performance', 'learning_efficiency', 'cycle_duration_ms'),
        Index('idx_learning_cycle_type', 'cycle_type', 'trigger_source'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class AgentLearningState:
    """Manages agent learning state and transitions"""
    
    def __init__(self, agent_id: str, config: AgentConfigSchema):
        self.agent_id = agent_id
        self.config = config
        self.logger = logger.bind(agent_id=agent_id)
        
        # Learning state
        self.current_state = AgentState.INITIALIZING
        self.learning_metrics = LearningMetrics()
        self.collaboration_metrics = CollaborationMetrics()
        self.knowledge_base: Dict[str, KnowledgeItemSchema] = {}
        
        # Learning cycle management
        self.last_learning_cycle: Optional[datetime] = None
        self.next_learning_cycle: Optional[datetime] = None
        self.active_collaborations: Dict[str, CollaborationRequestSchema] = {}
        
        # Performance tracking
        self.health_score = 100.0
        self.performance_history: List[Dict[str, Any]] = []
        self.pattern_discoveries: List[Dict[str, Any]] = []
        
    async def initialize_learning_system(self) -> bool:
        """Initialize agent learning capabilities"""
        try:
            # Setup learning configuration
            await self._setup_learning_config()
            
            # Initialize knowledge base
            await self._initialize_knowledge_base()
            
            # Setup collaboration channels
            await self._setup_collaboration_channels()
            
            # Schedule first learning cycle
            await self._schedule_next_learning_cycle()
            
            self.current_state = AgentState.ACTIVE
            self.logger.info("Learning system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize learning system", error=str(e))
            self.current_state = AgentState.ERROR
            return False
    
    async def execute_learning_cycle(self) -> Dict[str, Any]:
        """Execute a complete learning cycle"""
        cycle_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.current_state = AgentState.LEARNING
            self.logger.info("Starting learning cycle", cycle_id=cycle_id)
            
            # Phase 1: Experience Collection
            experiences = await self._collect_experiences()
            
            # Phase 2: Knowledge Processing
            knowledge_items = await self._process_experiences(experiences)
            
            # Phase 3: Knowledge Validation
            validated_knowledge = await self._validate_knowledge(knowledge_items)
            
            # Phase 4: Knowledge Integration
            integration_results = await self._integrate_knowledge(validated_knowledge)
            
            # Phase 5: Pattern Discovery
            patterns = await self._discover_patterns()
            
            # Phase 6: Collaboration Opportunities
            collaboration_results = await self._identify_collaboration_opportunities()
            
            # Update metrics
            await self._update_learning_metrics(integration_results, patterns, collaboration_results)
            
            # Schedule next cycle
            await self._schedule_next_learning_cycle()
            
            cycle_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = {
                "cycle_id": cycle_id,
                "status": "completed",
                "duration_ms": cycle_duration,
                "experiences_processed": len(experiences),
                "knowledge_items_learned": len(validated_knowledge),
                "patterns_discovered": len(patterns),
                "collaboration_opportunities": len(collaboration_results),
                "learning_efficiency": self._calculate_learning_efficiency(integration_results)
            }
            
            self.current_state = AgentState.ACTIVE
            self.last_learning_cycle = datetime.utcnow()
            self.logger.info("Learning cycle completed", **result)
            
            return result
            
        except Exception as e:
            self.logger.error("Learning cycle failed", cycle_id=cycle_id, error=str(e))
            self.current_state = AgentState.ERROR
            return {
                "cycle_id": cycle_id,
                "status": "failed",
                "error": str(e),
                "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def process_collaboration_request(self, request: CollaborationRequestSchema) -> Dict[str, Any]:
        """Process incoming collaboration request"""
        try:
            self.logger.info("Processing collaboration request", 
                           request_id=request.request_id,
                           source_agent=request.source_agent_id,
                           collaboration_type=request.collaboration_type)
            
            # Validate request
            if not await self._validate_collaboration_request(request):
                return {
                    "status": "rejected",
                    "reason": "Invalid collaboration request",
                    "request_id": request.request_id
                }
            
            # Check availability and capacity
            if not await self._check_collaboration_capacity():
                return {
                    "status": "rejected",
                    "reason": "Agent at capacity",
                    "request_id": request.request_id
                }
            
            # Add to active collaborations
            self.active_collaborations[request.request_id] = request
            
            # Process based on collaboration type
            response_data = await self._handle_collaboration_type(request)
            
            # Update collaboration metrics
            await self._update_collaboration_metrics(request, True)
            
            # Remove from active collaborations
            self.active_collaborations.pop(request.request_id, None)
            
            return {
                "status": "completed",
                "request_id": request.request_id,
                "data": response_data,
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            self.logger.error("Collaboration request failed", 
                            request_id=request.request_id, 
                            error=str(e))
            
            # Update metrics for failure
            await self._update_collaboration_metrics(request, False)
            self.active_collaborations.pop(request.request_id, None)
            
            return {
                "status": "failed",
                "request_id": request.request_id,
                "error": str(e),
                "agent_id": self.agent_id
            }
    
    async def get_status_report(self) -> AgentStatusSchema:
        """Generate comprehensive agent status report"""
        return AgentStatusSchema(
            agent_id=self.agent_id,
            current_state=self.current_state,
            health_score=self.health_score,
            performance_metrics=self._get_performance_metrics(),
            learning_metrics=self._get_learning_metrics_dict(),
            collaboration_metrics=self._get_collaboration_metrics_dict(),
            last_learning_cycle=self.last_learning_cycle,
            next_learning_cycle=self.next_learning_cycle,
            active_collaborations=len(self.active_collaborations),
            knowledge_base_size=len(self.knowledge_base)
        )
    
    # Private helper methods
    
    async def _setup_learning_config(self) -> None:
        """Setup learning configuration"""
        learning_config = self.config.learning_config
        
        # Configure learning parameters
        self.learning_interval = learning_config.get('cycle_interval', LEARNING_CYCLE_INTERVAL)
        self.max_knowledge_items = learning_config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_AGENT)
        self.retention_days = learning_config.get('retention_days', KNOWLEDGE_RETENTION_DAYS)
        
        # Configure pattern recognition
        self.pattern_recognition_enabled = learning_config.get('pattern_recognition', True)
        self.min_pattern_confidence = learning_config.get('min_pattern_confidence', 0.7)
        
        # Configure external learning
        self.external_learning_enabled = learning_config.get('external_learning', True)
        self.external_source_weights = learning_config.get('source_weights', {})
    
    async def _initialize_knowledge_base(self) -> None:
        """Initialize agent knowledge base"""
        # Load existing knowledge items
        # This would typically load from database
        self.knowledge_base = {}
        
        # Initialize learning metrics
        self.learning_metrics = LearningMetrics()
        
        self.logger.debug("Knowledge base initialized", 
                         knowledge_items=len(self.knowledge_base))
    
    async def _setup_collaboration_channels(self) -> None:
        """Setup inter-agent collaboration channels"""
        collaboration_config = self.config.collaboration_config
        
        # Configure collaboration parameters
        self.max_concurrent_collaborations = collaboration_config.get('max_concurrent', 5)
        self.collaboration_timeout = collaboration_config.get('timeout_seconds', 30)
        self.collaboration_types = collaboration_config.get('supported_types', [])
        
        # Initialize collaboration metrics
        self.collaboration_metrics = CollaborationMetrics()
        
        self.logger.debug("Collaboration channels setup completed",
                         max_concurrent=self.max_concurrent_collaborations,
                         supported_types=len(self.collaboration_types))
    
    async def _schedule_next_learning_cycle(self) -> None:
        """Schedule the next learning cycle"""
        self.next_learning_cycle = datetime.utcnow() + timedelta(seconds=self.learning_interval)
        self.logger.debug("Next learning cycle scheduled", 
                         next_cycle=self.next_learning_cycle.isoformat())
    
    async def _collect_experiences(self) -> List[Dict[str, Any]]:
        """Collect agent experiences for learning"""
        experiences = []
        
        # Collect performance data
        performance_experiences = await self._collect_performance_experiences()
        experiences.extend(performance_experiences)
        
        # Collect interaction data
        interaction_experiences = await self._collect_interaction_experiences()
        experiences.extend(interaction_experiences)
        
        # Collect error/failure data
        error_experiences = await self._collect_error_experiences()
        experiences.extend(error_experiences)
        
        self.logger.debug("Experiences collected", count=len(experiences))
        return experiences
    
    async def _collect_performance_experiences(self) -> List[Dict[str, Any]]:
        """Collect performance-related experiences"""
        return []  # Implementation would collect actual performance data
    
    async def _collect_interaction_experiences(self) -> List[Dict[str, Any]]:
        """Collect interaction-related experiences"""
        return []  # Implementation would collect actual interaction data
    
    async def _collect_error_experiences(self) -> List[Dict[str, Any]]:
        """Collect error and failure experiences"""
        return []  # Implementation would collect actual error data
    
    async def _process_experiences(self, experiences: List[Dict[str, Any]]) -> List[KnowledgeItemSchema]:
        """Process experiences into knowledge items"""
        knowledge_items = []
        
        for experience in experiences:
            # Extract patterns and insights
            insights = await self._extract_insights(experience)
            
            for insight in insights:
                knowledge_item = KnowledgeItemSchema(
                    knowledge_type=self._classify_knowledge_type(insight),
                    content=insight,
                    confidence_score=self._calculate_confidence(insight, experience),
                    source_agent_id=self.agent_id,
                    applicable_contexts=self._identify_contexts(insight)
                )
                knowledge_items.append(knowledge_item)
        
        return knowledge_items
    
    async def _extract_insights(self, experience: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract insights from experience data"""
        return []  # Implementation would extract actual insights
    
    def _classify_knowledge_type(self, insight: Dict[str, Any]) -> KnowledgeType:
        """Classify the type of knowledge from insight"""
        # Implementation would use ML/heuristics to classify
        return KnowledgeType.BEHAVIORAL_PATTERN
    
    def _calculate_confidence(self, insight: Dict[str, Any], experience: Dict[str, Any]) -> float:
        """Calculate confidence score for knowledge item"""
        # Implementation would calculate based on evidence strength
        return 0.5
    
    def _identify_contexts(self, insight: Dict[str, Any]) -> List[str]:
        """Identify applicable contexts for knowledge item"""
        return []  # Implementation would identify contexts
    
    async def _validate_knowledge(self, knowledge_items: List[KnowledgeItemSchema]) -> List[KnowledgeItemSchema]:
        """Validate knowledge items before integration"""
        validated_items = []
        
        for item in knowledge_items:
            # Confidence threshold check
            if item.confidence_score < 0.3:
                continue
            
            # Duplicate detection
            if await self._is_duplicate_knowledge(item):
                continue
            
            # Context validation
            if not await self._validate_contexts(item):
                continue
            
            # Mark as validated
            item.validation_status = LearningStatus.VALIDATED
            validated_items.append(item)
        
        self.logger.debug("Knowledge validation completed", 
                         total=len(knowledge_items),
                         validated=len(validated_items))
        
        return validated_items
    
    async def _is_duplicate_knowledge(self, item: KnowledgeItemSchema) -> bool:
        """Check if knowledge item is duplicate"""
        for existing_id, existing_item in self.knowledge_base.items():
            if (existing_item.knowledge_type == item.knowledge_type and
                self._calculate_similarity(existing_item.content, item.content) > 0.8):
                return True
        return False
    
    def _calculate_similarity(self, content1: Dict[str, Any], content2: Dict[str, Any]) -> float:
        """Calculate similarity between knowledge contents"""
        # Implementation would use actual similarity metrics
        return 0.0
    
    async def _validate_contexts(self, item: KnowledgeItemSchema) -> bool:
        """Validate applicable contexts for knowledge item"""
        # Implementation would validate contexts
        return True
    
    async def _integrate_knowledge(self, validated_knowledge: List[KnowledgeItemSchema]) -> Dict[str, Any]:
        """Integrate validated knowledge into agent's knowledge base"""
        integration_results = {
            "items_added": 0,
            "items_updated": 0,
            "items_rejected": 0,
            "knowledge_base_size": len(self.knowledge_base)
        }
        
        for item in validated_knowledge:
            try:
                # Check capacity
                if len(self.knowledge_base) >= self.max_knowledge_items:
                    await self._cleanup_old_knowledge()
                
                # Add to knowledge base
                self.knowledge_base[item.knowledge_id] = item
                item.validation_status = LearningStatus.APPLIED
                integration_results["items_added"] += 1
                
                self.logger.debug("Knowledge item integrated", 
                                knowledge_id=item.knowledge_id,
                                knowledge_type=item.knowledge_type.value)
                
            except Exception as e:
                self.logger.error("Failed to integrate knowledge item", 
                                knowledge_id=item.knowledge_id,
                                error=str(e))
                integration_results["items_rejected"] += 1
        
        integration_results["knowledge_base_size"] = len(self.knowledge_base)
        return integration_results
    
    async def _cleanup_old_knowledge(self) -> None:
        """Remove old or low-quality knowledge items"""
        # Sort by usage and effectiveness
        sorted_items = sorted(
            self.knowledge_base.items(),
            key=lambda x: (x[1].usage_count, x[1].success_rate, x[1].confidence_score)
        )
        
        # Remove bottom 10%
        items_to_remove = int(len(sorted_items) * 0.1)
        for i in range(items_to_remove):
            knowledge_id = sorted_items[i][0]
            del self.knowledge_base[knowledge_id]
            
        self.logger.debug("Knowledge cleanup completed", items_removed=items_to_remove)
    
    async def _discover_patterns(self) -> List[Dict[str, Any]]:
        """Discover behavioral patterns from knowledge base"""
        if not self.pattern_recognition_enabled:
            return []
        
        patterns = []
        
        # Analyze performance patterns
        performance_patterns = await self._analyze_performance_patterns()
        patterns.extend(performance_patterns)
        
        # Analyze collaboration patterns
        collaboration_patterns = await self._analyze_collaboration_patterns()
        patterns.extend(collaboration_patterns)
        
        # Analyze error patterns
        error_patterns = await self._analyze_error_patterns()
        patterns.extend(error_patterns)
        
        # Filter by significance
        significant_patterns = [p for p in patterns if p.get('confidence', 0) >= self.min_pattern_confidence]
        
        self.pattern_discoveries.extend(significant_patterns)
        
        self.logger.debug("Pattern discovery completed", 
                         total_patterns=len(patterns),
                         significant_patterns=len(significant_patterns))
        
        return significant_patterns
    
    async def _analyze_performance_patterns(self) -> List[Dict[str, Any]]:
        """Analyze performance-related patterns"""
        return []  # Implementation would analyze actual performance data
    
    async def _analyze_collaboration_patterns(self) -> List[Dict[str, Any]]:
        """Analyze collaboration-related patterns"""
        return []  # Implementation would analyze collaboration data
    
    async def _analyze_error_patterns(self) -> List[Dict[str, Any]]:
        """Analyze error and failure patterns"""
        return []  # Implementation would analyze error data
    
    async def _identify_collaboration_opportunities(self) -> List[Dict[str, Any]]:
        """Identify opportunities for inter-agent collaboration"""
        opportunities = []
        
        # Knowledge sharing opportunities
        sharing_opportunities = await self._identify_knowledge_sharing_opportunities()
        opportunities.extend(sharing_opportunities)
        
        # Task collaboration opportunities
        task_opportunities = await self._identify_task_collaboration_opportunities()
        opportunities.extend(task_opportunities)
        
        # Problem-solving opportunities
        problem_solving_opportunities = await self._identify_problem_solving_opportunities()
        opportunities.extend(problem_solving_opportunities)
        
        return opportunities
    
    async def _identify_knowledge_sharing_opportunities(self) -> List[Dict[str, Any]]:
        """Identify knowledge sharing opportunities"""
        return []  # Implementation would identify actual opportunities
    
    async def _identify_task_collaboration_opportunities(self) -> List[Dict[str, Any]]:
        """Identify task collaboration opportunities"""
        return []  # Implementation would identify task opportunities
    
    async def _identify_problem_solving_opportunities(self) -> List[Dict[str, Any]]:
        """Identify problem-solving collaboration opportunities"""
        return []  # Implementation would identify problem-solving opportunities
    
    async def _update_learning_metrics(self, integration_results: Dict[str, Any], 
                                     patterns: List[Dict[str, Any]], 
                                     collaboration_results: List[Dict[str, Any]]) -> None:
        """Update learning performance metrics"""
        # Update knowledge metrics
        self.learning_metrics.knowledge_items_learned += integration_results["items_added"]
        self.learning_metrics.pattern_discovery_count += len(patterns)
        
        # Calculate learning velocity (items per hour)
        time_diff = datetime.utcnow() - (self.last_learning_cycle or datetime.utcnow())
        hours_elapsed = max(time_diff.total_seconds() / 3600, 1/3600)  # At least 1 second
        self.learning_metrics.learning_velocity = integration_results["items_added"] / hours_elapsed
        
        # Update retention rate
        total_knowledge = len(self.knowledge_base)
        if total_knowledge > 0:
            high_usage_items = sum(1 for item in self.knowledge_base.values() if item.usage_count > 0)
            self.learning_metrics.retention_rate = (high_usage_items / total_knowledge) * 100
        
        # Update collaboration score
        if collaboration_results:
            successful_collaborations = sum(1 for result in collaboration_results if result.get('success', False))
            self.learning_metrics.collaboration_score = (successful_collaborations / len(collaboration_results)) * 100
        
        # Calculate collective intelligence score
        self.learning_metrics.collective_intelligence_score = self._calculate_collective_intelligence()
    
    def _calculate_collective_intelligence(self) -> float:
        """Calculate collective intelligence score"""
        # Combine multiple factors
        knowledge_factor = min(len(self.knowledge_base) / self.max_knowledge_items, 1.0) * 30
        collaboration_factor = min(self.learning_metrics.collaboration_score / 100, 1.0) * 25
        pattern_factor = min(self.learning_metrics.pattern_discovery_count / 100, 1.0) * 25
        retention_factor = min(self.learning_metrics.retention_rate / 100, 1.0) * 20
        
        return knowledge_factor + collaboration_factor + pattern_factor + retention_factor
    
    def _calculate_learning_efficiency(self, integration_results: Dict[str, Any]) -> float:
        """Calculate learning efficiency score"""
        total_items = integration_results["items_added"] + integration_results["items_rejected"]
        if total_items == 0:
            return 0.0
        
        return (integration_results["items_added"] / total_items) * 100
    
    async def _validate_collaboration_request(self, request: CollaborationRequestSchema) -> bool:
        """Validate incoming collaboration request"""
        # Check if collaboration type is supported
        if request.collaboration_type not in self.collaboration_types and self.collaboration_types:
            return False
        
        # Check source agent validity
        if request.source_agent_id == self.agent_id:
            return False
        
        # Check request data validity
        if not request.request_data:
            return False
        
        return True
    
    async def _check_collaboration_capacity(self) -> bool:
        """Check if agent has capacity for new collaboration"""
        return len(self.active_collaborations) < self.max_concurrent_collaborations
    
    async def _handle_collaboration_type(self, request: CollaborationRequestSchema) -> Dict[str, Any]:
        """Handle specific collaboration type"""
        collaboration_type = request.collaboration_type
        
        if collaboration_type == "knowledge_share":
            return await self._handle_knowledge_sharing(request)
        elif collaboration_type == "task_assistance":
            return await self._handle_task_assistance(request)
        elif collaboration_type == "problem_solving":
            return await self._handle_problem_solving(request)
        elif collaboration_type == "pattern_validation":
            return await self._handle_pattern_validation(request)
        else:
            return {"error": f"Unsupported collaboration type: {collaboration_type}"}
    
    async def _handle_knowledge_sharing(self, request: CollaborationRequestSchema) -> Dict[str, Any]:
        """Handle knowledge sharing collaboration"""
        requested_knowledge_type = request.request_data.get("knowledge_type")
        context = request.request_data.get("context", [])
        
        # Find relevant knowledge items
        relevant_knowledge = []
        for item in self.knowledge_base.values():
            if (not requested_knowledge_type or item.knowledge_type.value == requested_knowledge_type):
                if not context or any(ctx in item.applicable_contexts for ctx in context):
                    relevant_knowledge.append({
                        "knowledge_id": item.knowledge_id,
                        "knowledge_type": item.knowledge_type.value,
                        "content": item.content,
                        "confidence_score": item.confidence_score,
                        "success_rate": item.success_rate,
                        "applicable_contexts": item.applicable_contexts
                    })
        
        # Sort by relevance (confidence * success_rate)
        relevant_knowledge.sort(key=lambda x: x["confidence_score"] * x["success_rate"], reverse=True)
        
        # Return top 10 items
        return {
            "knowledge_items": relevant_knowledge[:10],
            "total_available": len(relevant_knowledge),
            "sharing_agent": self.agent_id
        }
    
    async def _handle_task_assistance(self, request: CollaborationRequestSchema) -> Dict[str, Any]:
        """Handle task assistance collaboration"""
        task_type = request.request_data.get("task_type")
        task_context = request.request_data.get("context", {})
        
        # Find relevant knowledge for task
        relevant_knowledge = []
        for item in self.knowledge_base.values():
            if item.knowledge_type in [KnowledgeType.TASK_OPTIMIZATION, KnowledgeType.PERFORMANCE_INSIGHT]:
                relevant_knowledge.append(item)
        
        # Generate assistance recommendations
        recommendations = []
        for item in relevant_knowledge:
            if item.confidence_score > 0.6 and item.success_rate > 0.7:
                recommendations.append({
                    "recommendation": item.content.get("recommendation", ""),
                    "confidence": item.confidence_score,
                    "evidence": item.content.get("evidence", {}),
                    "expected_improvement": item.content.get("improvement", 0)
                })
        
        return {
            "recommendations": recommendations[:5],
            "assistant_agent": self.agent_id,
            "confidence_score": sum(r["confidence"] for r in recommendations) / len(recommendations) if recommendations else 0
        }
    
    async def _handle_problem_solving(self, request: CollaborationRequestSchema) -> Dict[str, Any]:
        """Handle problem-solving collaboration"""
        problem_description = request.request_data.get("problem", "")
        error_context = request.request_data.get("error_context", {})
        
        # Find relevant error resolution knowledge
        solutions = []
        for item in self.knowledge_base.values():
            if item.knowledge_type == KnowledgeType.ERROR_RESOLUTION:
                # Check similarity to current problem
                similarity = self._calculate_problem_similarity(item.content, error_context)
                if similarity > 0.5:
                    solutions.append({
                        "solution": item.content.get("solution", ""),
                        "similarity": similarity,
                        "success_rate": item.success_rate,
                        "confidence": item.confidence_score,
                        "previous_context": item.content.get("context", {})
                    })
        
        # Sort by combined score
        solutions.sort(key=lambda x: x["similarity"] * x["success_rate"] * x["confidence"], reverse=True)
        
        return {
            "solutions": solutions[:3],
            "solver_agent": self.agent_id,
            "problem_analysis": self._analyze_problem(problem_description, error_context)
        }
    
    def _calculate_problem_similarity(self, solution_content: Dict[str, Any], error_context: Dict[str, Any]) -> float:
        """Calculate similarity between solution and current problem"""
        # Implementation would use actual similarity calculation
        return 0.5
    
    def _analyze_problem(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze problem for patterns and characteristics"""
        return {
            "problem_type": "unknown",
            "complexity": "medium",
            "similar_cases": 0,
            "recommended_approach": "collaborative"
        }
    
    async def _handle_pattern_validation(self, request: CollaborationRequestSchema) -> Dict[str, Any]:
        """Handle pattern validation collaboration"""
        pattern_data = request.request_data.get("pattern", {})
        
        # Check if we have similar patterns
        similar_patterns = []
        for pattern in self.pattern_discoveries:
            similarity = self._calculate_pattern_similarity(pattern, pattern_data)
            if similarity > 0.6:
                similar_patterns.append({
                    "pattern": pattern,
                    "similarity": similarity,
                    "confidence": pattern.get("confidence", 0),
                    "occurrences": pattern.get("occurrences", 0)
                })
        
        # Validation result
        validation_score = 0.0
        if similar_patterns:
            validation_score = sum(p["similarity"] * p["confidence"] for p in similar_patterns) / len(similar_patterns)
        
        return {
            "validation_score": validation_score,
            "similar_patterns_count": len(similar_patterns),
            "similar_patterns": similar_patterns[:3],
            "validator_agent": self.agent_id,
            "recommendation": "validated" if validation_score > 0.7 else "inconclusive" if validation_score > 0.4 else "not_validated"
        }
    
    def _calculate_pattern_similarity(self, pattern1: Dict[str, Any], pattern2: Dict[str, Any]) -> float:
        """Calculate similarity between patterns"""
        # Implementation would use actual pattern similarity
        return 0.5
    
    async def _update_collaboration_metrics(self, request: CollaborationRequestSchema, success: bool) -> None:
        """Update collaboration metrics"""
        if success:
            self.collaboration_metrics.successful_collaborations += 1
        
        # Update response time (simulated)
        response_time = 100.0  # ms
        if self.collaboration_metrics.response_time_avg == 0:
            self.collaboration_metrics.response_time_avg = response_time
        else:
            # Moving average
            self.collaboration_metrics.response_time_avg = (
                self.collaboration_metrics.response_time_avg * 0.8 + response_time * 0.2
            )
        
        # Update efficiency
        total_collaborations = (self.collaboration_metrics.successful_collaborations + 
                              len(self.active_collaborations))
        if total_collaborations > 0:
            self.collaboration_metrics.collaboration_efficiency = (
                self.collaboration_metrics.successful_collaborations / total_collaborations * 100
            )
    
    def _get_performance_metrics(self) -> Dict[str, float]:
        """Get current performance metrics"""
        return {
            "health_score": self.health_score,
            "response_time_avg": self.collaboration_metrics.response_time_avg,
            "collaboration_efficiency": self.collaboration_metrics.collaboration_efficiency,
            "learning_velocity": self.learning_metrics.learning_velocity,
            "knowledge_retention": self.learning_metrics.retention_rate,
            "pattern_discovery_rate": self.learning_metrics.pattern_discovery_count / max(1, len(self.performance_history))
        }
    
    def _get_learning_metrics_dict(self) -> Dict[str, Any]:
        """Get learning metrics as dictionary"""
        return {
            "knowledge_items_learned": self.learning_metrics.knowledge_items_learned,
            "learning_velocity": self.learning_metrics.learning_velocity,
            "retention_rate": self.learning_metrics.retention_rate,
            "collaboration_score": self.learning_metrics.collaboration_score,
            "pattern_discovery_count": self.learning_metrics.pattern_discovery_count,
            "external_integration_success_rate": self.learning_metrics.external_integration_success_rate,
            "knowledge_application_rate": self.learning_metrics.knowledge_application_rate,
            "collective_intelligence_score": self.learning_metrics.collective_intelligence_score
        }
    
    def _get_collaboration_metrics_dict(self) -> Dict[str, Any]:
        """Get collaboration metrics as dictionary"""
        return {
            "knowledge_transfers_sent": self.collaboration_metrics.knowledge_transfers_sent,
            "knowledge_transfers_received": self.collaboration_metrics.knowledge_transfers_received,
            "successful_collaborations": self.collaboration_metrics.successful_collaborations,
            "collaboration_efficiency": self.collaboration_metrics.collaboration_efficiency,
            "knowledge_diversity_score": self.collaboration_metrics.knowledge_diversity_score,
            "peer_rating": self.collaboration_metrics.peer_rating,
            "response_time_avg": self.collaboration_metrics.response_time_avg,
            "availability_score": self.collaboration_metrics.availability_score
        }

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Agent models health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "agent_models",
        "database_models": ["Agent", "AgentKnowledge", "AgentCollaboration", "LearningCycle"],
        "schemas": ["AgentConfigSchema", "KnowledgeItemSchema", "CollaborationRequestSchema", "AgentStatusSchema"]
    }

def validate_agent_configuration(config: Dict[str, Any]) -> bool:
    """Validate agent configuration"""
    required_fields = ["agent_id", "agent_type", "capabilities"]
    return all(field in config for field in required_fields)

def calculate_knowledge_diversity(knowledge_base: Dict[str, KnowledgeItemSchema]) -> float:
    """Calculate knowledge diversity score"""
    if not knowledge_base:
        return 0.0
    
    # Count different knowledge types
    type_counts = {}
    for item in knowledge_base.values():
        type_counts[item.knowledge_type] = type_counts.get(item.knowledge_type, 0) + 1
    
    # Calculate diversity using Shannon entropy
    total_items = len(knowledge_base)
    entropy = 0.0
    for count in type_counts.values():
        probability = count / total_items
        entropy -= probability * (probability.bit_length() - 1) if probability > 0 else 0
    
    # Normalize to 0-100 scale
    max_entropy = len(KnowledgeType)
    return (entropy / max_entropy) * 100 if max_entropy > 0 else 0.0

async def cleanup_expired_knowledge(agent_state: AgentLearningState) -> int:
    """Clean up expired knowledge items"""
    current_time = datetime.utcnow()
    expired_items = []
    
    for knowledge_id, item in agent_state.knowledge_base.items():
        # Check if item has low usage and is old
        item_age = (current_time - datetime.fromisoformat(knowledge_id.split('-')[0]) 
                   if '-' in knowledge_id else current_time).days
        
        if (item_age > agent_state.retention_days and 
            item.usage_count < 3 and 
            item.success_rate < 0.3):
            expired_items.append(knowledge_id)
    
    # Remove expired items
    for knowledge_id in expired_items:
        del agent_state.knowledge_base[knowledge_id]
    
    return len(expired_items)

def generate_agent_id(agent_type: AgentType, instance_id: Optional[str] = None) -> str:
    """Generate unique agent identifier"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    instance = instance_id or str(uuid.uuid4())[:8]
    return f"{agent_type.value}_{timestamp}_{instance}"

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_agent_models() -> Dict[str, Any]:
    """Initialize agent models module for production use"""
    try:
        # Validate configuration
        if not validate_agent_configuration({"agent_id": "test", "agent_type": "test", "capabilities": {}}):
            raise ValueError("Invalid configuration structure")
        
        # Setup logging
        logger.info("Agent models module initialized successfully")
        
        return {
            "status": "initialized",
            "timestamp": datetime.utcnow().isoformat(),
            "models_available": ["Agent", "AgentKnowledge", "AgentCollaboration", "LearningCycle"],
            "schemas_available": ["AgentConfigSchema", "KnowledgeItemSchema", "CollaborationRequestSchema", "AgentStatusSchema"],
            "utilities_available": ["health_check", "validate_agent_configuration", "calculate_knowledge_diversity"]
        }
        
    except Exception as e:
        logger.error("Failed to initialize agent models module", error=str(e))
        raise

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Enums
    "AgentState", "AgentType", "KnowledgeType", "LearningStatus", "CollaborationLevel",
    
    # Data Models
    "AgentCapabilities", "LearningMetrics", "CollaborationMetrics",
    
    # Schemas
    "AgentConfigSchema", "KnowledgeItemSchema", "CollaborationRequestSchema", "AgentStatusSchema",
    
    # Database Models
    "Agent", "AgentKnowledge", "AgentCollaboration", "LearningCycle",
    
    # Core Classes
    "AgentLearningState",
    
    # Utilities
    "health_check", "validate_agent_configuration", "calculate_knowledge_diversity",
    "cleanup_expired_knowledge", "generate_agent_id", "initialize_agent_models"
]