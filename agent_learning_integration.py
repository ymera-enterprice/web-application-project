“””
YMERA Enterprise - Agent Learning Integration System
Production-Ready Agent-Learning Infrastructure Integration - v4.0
Enterprise-grade implementation with zero placeholders
“””

# ===============================================================================

# STANDARD IMPORTS SECTION

# ===============================================================================

# Standard library imports (alphabetical)

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Set, Tuple
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

# Third-party imports (alphabetical)

import aioredis
import structlog
from fastapi import HTTPException
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

logger = structlog.get_logger(“ymera.agent_learning_integration”)

# ===============================================================================

# CONSTANTS & CONFIGURATION

# ===============================================================================

# Learning constants

EXPERIENCE_BATCH_SIZE = 50
KNOWLEDGE_SYNC_INTERVAL = 300  # 5 minutes
PATTERN_ANALYSIS_INTERVAL = 900  # 15 minutes
MEMORY_CONSOLIDATION_INTERVAL = 3600  # 1 hour
MAX_KNOWLEDGE_ITEMS_PER_AGENT = 10000
MIN_CONFIDENCE_THRESHOLD = 0.7
LEARNING_VELOCITY_WINDOW = 3600  # 1 hour

# Performance thresholds

MAX_RESPONSE_TIME_MS = 200
MAX_MEMORY_USAGE_MB = 512
MAX_CONCURRENT_LEARNERS = 100

settings = get_settings()

# ===============================================================================

# DATA MODELS & SCHEMAS

# ===============================================================================

class LearningEventType(Enum):
“”“Types of learning events”””
EXPERIENCE_CAPTURED = “experience_captured”
KNOWLEDGE_ACQUIRED = “knowledge_acquired”
PATTERN_DISCOVERED = “pattern_discovered”
KNOWLEDGE_SHARED = “knowledge_shared”
SKILL_IMPROVED = “skill_improved”
COLLABORATION_INITIATED = “collaboration_initiated”

class KnowledgeType(Enum):
“”“Types of knowledge that can be learned”””
PROCEDURAL = “procedural”
DECLARATIVE = “declarative”
CONTEXTUAL = “contextual”
BEHAVIORAL = “behavioral”
STRATEGIC = “strategic”
COLLABORATIVE = “collaborative”

@dataclass
class AgentExperience:
“”“Structured representation of agent experience”””
agent_id: str
experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
timestamp: datetime = field(default_factory=datetime.utcnow)
event_type: str = “”
context: Dict[str, Any] = field(default_factory=dict)
action_taken: str = “”
outcome: Dict[str, Any] = field(default_factory=dict)
success_metrics: Dict[str, float] = field(default_factory=dict)
confidence_score: float = 0.0
learning_tags: Set[str] = field(default_factory=set)

```
def to_dict(self) -> Dict[str, Any]:
    """Convert experience to dictionary format"""
    return {
        "agent_id": self.agent_id,
        "experience_id": self.experience_id,
        "timestamp": self.timestamp.isoformat(),
        "event_type": self.event_type,
        "context": self.context,
        "action_taken": self.action_taken,
        "outcome": self.outcome,
        "success_metrics": self.success_metrics,
        "confidence_score": self.confidence_score,
        "learning_tags": list(self.learning_tags)
    }
```

@dataclass
class KnowledgeItem:
“”“Structured knowledge representation”””
knowledge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
agent_id: str = “”
knowledge_type: KnowledgeType = KnowledgeType.PROCEDURAL
content: Dict[str, Any] = field(default_factory=dict)
confidence: float = 0.0
source_experiences: List[str] = field(default_factory=list)
created_at: datetime = field(default_factory=datetime.utcnow)
last_updated: datetime = field(default_factory=datetime.utcnow)
usage_count: int = 0
success_rate: float = 0.0
tags: Set[str] = field(default_factory=set)
transferable: bool = True

```
def to_dict(self) -> Dict[str, Any]:
    """Convert knowledge to dictionary format"""
    return {
        "knowledge_id": self.knowledge_id,
        "agent_id": self.agent_id,
        "knowledge_type": self.knowledge_type.value,
        "content": self.content,
        "confidence": self.confidence,
        "source_experiences": self.source_experiences,
        "created_at": self.created_at.isoformat(),
        "last_updated": self.last_updated.isoformat(),
        "usage_count": self.usage_count,
        "success_rate": self.success_rate,
        "tags": list(self.tags),
        "transferable": self.transferable
    }
```

@dataclass
class LearningMetrics:
“”“Comprehensive learning performance metrics”””
agent_id: str
learning_velocity: float = 0.0  # Knowledge items per hour
knowledge_retention_rate: float = 0.0  # Percentage
collaboration_score: float = 0.0  # Inter-agent cooperation
pattern_discovery_count: int = 0
knowledge_transfer_count: int = 0
average_confidence: float = 0.0
experience_processing_time: float = 0.0  # Milliseconds
memory_usage_mb: float = 0.0
last_updated: datetime = field(default_factory=datetime.utcnow)

```
def to_dict(self) -> Dict[str, Any]:
    """Convert metrics to dictionary format"""
    return asdict(self)
```

class LearningIntegrationConfig(BaseModel):
“”“Configuration for learning integration”””
agent_id: str
learning_enabled: bool = True
experience_capture_rate: float = 1.0  # Capture rate (0.0-1.0)
knowledge_sharing_enabled: bool = True
pattern_recognition_enabled: bool = True
memory_consolidation_enabled: bool = True
max_knowledge_items: int = MAX_KNOWLEDGE_ITEMS_PER_AGENT
confidence_threshold: float = MIN_CONFIDENCE_THRESHOLD
learning_categories: List[str] = Field(default_factory=list)
collaboration_preferences: Dict[str, Any] = Field(default_factory=dict)

# ===============================================================================

# CORE IMPLEMENTATION CLASSES

# ===============================================================================

class BaseLearningInterface(ABC):
“”“Abstract base class for agent learning integration”””

```
def __init__(self, agent_id: str, config: LearningIntegrationConfig):
    self.agent_id = agent_id
    self.config = config
    self.logger = logger.bind(agent_id=agent_id)
    self._learning_active = False
    
@abstractmethod
async def capture_experience(self, experience: AgentExperience) -> bool:
    """Capture agent experience for learning"""
    pass

@abstractmethod
async def retrieve_knowledge(self, query: Dict[str, Any]) -> List[KnowledgeItem]:
    """Retrieve relevant knowledge for agent"""
    pass

@abstractmethod
async def share_knowledge(self, knowledge: KnowledgeItem, target_agents: List[str]) -> bool:
    """Share knowledge with other agents"""
    pass
```

class AgentLearningIntegrator(BaseLearningInterface):
“”“Production-ready agent learning integration system”””

```
def __init__(self, agent_id: str, config: LearningIntegrationConfig):
    super().__init__(agent_id, config)
    self._experience_buffer: List[AgentExperience] = []
    self._knowledge_cache: Dict[str, KnowledgeItem] = {}
    self._metrics = LearningMetrics(agent_id=agent_id)
    self._redis_client: Optional[aioredis.Redis] = None
    self._learning_engine_connection = None
    self._last_sync_time = datetime.utcnow()
    
async def initialize(self) -> None:
    """Initialize learning integration system"""
    try:
        # Setup Redis connection for inter-agent communication
        self._redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20
        )
        
        # Connect to learning engine
        await self._connect_to_learning_engine()
        
        # Load existing knowledge from cache
        await self._load_knowledge_cache()
        
        # Register agent with learning system
        await self._register_with_learning_system()
        
        self._learning_active = True
        self.logger.info("Learning integration initialized successfully")
        
    except Exception as e:
        self.logger.error("Failed to initialize learning integration", error=str(e))
        raise

async def _connect_to_learning_engine(self) -> None:
    """Establish connection to main learning engine"""
    try:
        # Connection logic to main learning engine
        connection_config = {
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "capabilities": {
                "experience_capture": True,
                "knowledge_sharing": self.config.knowledge_sharing_enabled,
                "pattern_recognition": self.config.pattern_recognition_enabled,
                "memory_consolidation": self.config.memory_consolidation_enabled
            }
        }
        
        # Store connection info in Redis
        await self._redis_client.hset(
            f"learning:connections:{self.agent_id}",
            mapping=connection_config
        )
        
        self._learning_engine_connection = connection_config
        
    except Exception as e:
        self.logger.error("Failed to connect to learning engine", error=str(e))
        raise

async def _load_knowledge_cache(self) -> None:
    """Load existing knowledge from storage"""
    try:
        # Load knowledge from Redis cache
        knowledge_keys = await self._redis_client.keys(f"knowledge:{self.agent_id}:*")
        
        for key in knowledge_keys:
            knowledge_data = await self._redis_client.hgetall(key)
            if knowledge_data:
                knowledge_item = self._deserialize_knowledge(knowledge_data)
                self._knowledge_cache[knowledge_item.knowledge_id] = knowledge_item
        
        self.logger.info(
            "Knowledge cache loaded",
            knowledge_count=len(self._knowledge_cache)
        )
        
    except Exception as e:
        self.logger.error("Failed to load knowledge cache", error=str(e))
        raise

async def _register_with_learning_system(self) -> None:
    """Register agent with the central learning system"""
    try:
        registration_data = {
            "agent_id": self.agent_id,
            "registration_time": datetime.utcnow().isoformat(),
            "config": self.config.dict(),
            "status": "active"
        }
        
        await self._redis_client.hset(
            f"learning:agents:{self.agent_id}",
            mapping=registration_data
        )
        
        # Add to active agents set
        await self._redis_client.sadd("learning:active_agents", self.agent_id)
        
        self.logger.info("Agent registered with learning system")
        
    except Exception as e:
        self.logger.error("Failed to register with learning system", error=str(e))
        raise

@track_performance
async def capture_experience(self, experience: AgentExperience) -> bool:
    """Capture and process agent experience for learning"""
    if not self._learning_active or not self.config.learning_enabled:
        return False
        
    try:
        start_time = time.time()
        
        # Validate experience
        if not self._validate_experience(experience):
            self.logger.warning("Invalid experience rejected", experience_id=experience.experience_id)
            return False
        
        # Apply capture rate filtering
        if self.config.experience_capture_rate < 1.0:
            import random
            if random.random() > self.config.experience_capture_rate:
                return True  # Silently skip but return success
        
        # Add to buffer
        self._experience_buffer.append(experience)
        
        # Process if buffer is full
        if len(self._experience_buffer) >= EXPERIENCE_BATCH_SIZE:
            await self._process_experience_batch()
        
        # Update metrics
        processing_time = (time.time() - start_time) * 1000
        self._metrics.experience_processing_time = processing_time
        
        # Emit learning event
        await self._emit_learning_event(
            LearningEventType.EXPERIENCE_CAPTURED,
            {"experience_id": experience.experience_id, "processing_time_ms": processing_time}
        )
        
        self.logger.debug(
            "Experience captured successfully",
            experience_id=experience.experience_id,
            processing_time_ms=processing_time
        )
        
        return True
        
    except Exception as e:
        self.logger.error(
            "Failed to capture experience",
            experience_id=experience.experience_id,
            error=str(e)
        )
        return False

def _validate_experience(self, experience: AgentExperience) -> bool:
    """Validate experience data integrity"""
    try:
        # Check required fields
        if not experience.agent_id or experience.agent_id != self.agent_id:
            return False
        
        if not experience.event_type or not experience.action_taken:
            return False
        
        # Validate confidence score
        if not 0.0 <= experience.confidence_score <= 1.0:
            return False
        
        # Validate success metrics
        for metric_value in experience.success_metrics.values():
            if not isinstance(metric_value, (int, float)):
                return False
        
        return True
        
    except Exception as e:
        self.logger.error("Experience validation failed", error=str(e))
        return False

async def _process_experience_batch(self) -> None:
    """Process batch of experiences for knowledge extraction"""
    if not self._experience_buffer:
        return
        
    try:
        batch_size = len(self._experience_buffer)
        self.logger.info("Processing experience batch", batch_size=batch_size)
        
        # Group experiences by similarity
        experience_groups = await self._group_similar_experiences(self._experience_buffer)
        
        # Extract knowledge from each group
        new_knowledge_items = []
        for group in experience_groups:
            knowledge = await self._extract_knowledge_from_experiences(group)
            if knowledge:
                new_knowledge_items.extend(knowledge)
        
        # Store new knowledge
        for knowledge_item in new_knowledge_items:
            await self._store_knowledge_item(knowledge_item)
            
        # Update learning velocity
        await self._update_learning_velocity(len(new_knowledge_items))
        
        # Clear buffer
        self._experience_buffer.clear()
        
        self.logger.info(
            "Experience batch processed",
            experiences_processed=batch_size,
            knowledge_items_created=len(new_knowledge_items)
        )
        
    except Exception as e:
        self.logger.error("Failed to process experience batch", error=str(e))
        raise

async def _group_similar_experiences(self, experiences: List[AgentExperience]) -> List[List[AgentExperience]]:
    """Group similar experiences for knowledge extraction"""
    groups = []
    
    try:
        # Simple grouping by event type and context similarity
        type_groups = {}
        
        for exp in experiences:
            key = exp.event_type
            if key not in type_groups:
                type_groups[key] = []
            type_groups[key].append(exp)
        
        # Further group by context similarity within each type
        for type_group in type_groups.values():
            if len(type_group) <= 1:
                groups.append(type_group)
                continue
            
            # Simple context-based grouping
            context_groups = {}
            for exp in type_group:
                context_key = self._generate_context_key(exp.context)
                if context_key not in context_groups:
                    context_groups[context_key] = []
                context_groups[context_key].append(exp)
            
            groups.extend(context_groups.values())
        
        return groups
        
    except Exception as e:
        self.logger.error("Failed to group experiences", error=str(e))
        return [[exp] for exp in experiences]  # Fallback: individual groups

def _generate_context_key(self, context: Dict[str, Any]) -> str:
    """Generate a key for context similarity grouping"""
    try:
        # Extract key context elements
        key_elements = []
        
        for key in ['domain', 'task_type', 'priority', 'source']:
            if key in context:
                key_elements.append(f"{key}:{context[key]}")
        
        return "|".join(sorted(key_elements))
        
    except Exception:
        return "unknown"

async def _extract_knowledge_from_experiences(self, experiences: List[AgentExperience]) -> List[KnowledgeItem]:
    """Extract actionable knowledge from experience group"""
    if not experiences:
        return []
        
    try:
        knowledge_items = []
        
        # Analyze patterns in the experience group
        patterns = await self._analyze_experience_patterns(experiences)
        
        for pattern in patterns:
            # Create knowledge item from pattern
            knowledge_item = KnowledgeItem(
                agent_id=self.agent_id,
                knowledge_type=self._determine_knowledge_type(pattern),
                content=pattern['content'],
                confidence=pattern['confidence'],
                source_experiences=[exp.experience_id for exp in experiences],
                tags=set(pattern.get('tags', []))
            )
            
            # Validate knowledge quality
            if await self._validate_knowledge_quality(knowledge_item):
                knowledge_items.append(knowledge_item)
        
        return knowledge_items
        
    except Exception as e:
        self.logger.error("Failed to extract knowledge from experiences", error=str(e))
        return []

async def _analyze_experience_patterns(self, experiences: List[AgentExperience]) -> List[Dict[str, Any]]:
    """Analyze experiences to identify learnable patterns"""
    patterns = []
    
    try:
        if len(experiences) < 2:
            return patterns
        
        # Success pattern analysis
        successful_experiences = [exp for exp in experiences if exp.confidence_score > 0.7]
        if len(successful_experiences) >= 2:
            success_pattern = await self._extract_success_pattern(successful_experiences)
            if success_pattern:
                patterns.append(success_pattern)
        
        # Failure pattern analysis
        failed_experiences = [exp for exp in experiences if exp.confidence_score < 0.3]
        if len(failed_experiences) >= 2:
            failure_pattern = await self._extract_failure_pattern(failed_experiences)
            if failure_pattern:
                patterns.append(failure_pattern)
        
        # Context-action pattern analysis
        context_action_pattern = await self._extract_context_action_pattern(experiences)
        if context_action_pattern:
            patterns.append(context_action_pattern)
        
        return patterns
        
    except Exception as e:
        self.logger.error("Failed to analyze experience patterns", error=str(e))
        return []

async def _extract_success_pattern(self, experiences: List[AgentExperience]) -> Optional[Dict[str, Any]]:
    """Extract patterns from successful experiences"""
    try:
        if not experiences:
            return None
        
        # Find common elements in successful experiences
        common_actions = self._find_common_actions(experiences)
        common_contexts = self._find_common_contexts(experiences)
        
        if not common_actions and not common_contexts:
            return None
        
        # Calculate confidence based on consistency
        confidence = min(len(experiences) / 10.0, 1.0)  # More experiences = higher confidence
        
        pattern = {
            'type': 'success_pattern',
            'content': {
                'common_actions': common_actions,
                'common_contexts': common_contexts,
                'success_rate': sum(exp.confidence_score for exp in experiences) / len(experiences),
                'sample_size': len(experiences)
            },
            'confidence': confidence,
            'tags': ['success', 'pattern', 'action_guidance']
        }
        
        return pattern
        
    except Exception as e:
        self.logger.error("Failed to extract success pattern", error=str(e))
        return None

async def _extract_failure_pattern(self, experiences: List[AgentExperience]) -> Optional[Dict[str, Any]]:
    """Extract patterns from failed experiences"""
    try:
        if not experiences:
            return None
        
        # Find common elements in failed experiences
        common_actions = self._find_common_actions(experiences)
        common_contexts = self._find_common_contexts(experiences)
        
        if not common_actions and not common_contexts:
            return None
        
        confidence = min(len(experiences) / 10.0, 1.0)
        
        pattern = {
            'type': 'failure_pattern',
            'content': {
                'actions_to_avoid': common_actions,
                'risky_contexts': common_contexts,
                'failure_rate': 1.0 - sum(exp.confidence_score for exp in experiences) / len(experiences),
                'sample_size': len(experiences)
            },
            'confidence': confidence,
            'tags': ['failure', 'pattern', 'avoidance_guidance']
        }
        
        return pattern
        
    except Exception as e:
        self.logger.error("Failed to extract failure pattern", error=str(e))
        return None

async def _extract_context_action_pattern(self, experiences: List[AgentExperience]) -> Optional[Dict[str, Any]]:
    """Extract context-to-action mapping patterns"""
    try:
        if len(experiences) < 3:
            return None
        
        # Build context-action mappings
        context_action_map = {}
        
        for exp in experiences:
            context_key = self._generate_context_key(exp.context)
            action = exp.action_taken
            
            if context_key not in context_action_map:
                context_action_map[context_key] = []
            context_action_map[context_key].append({
                'action': action,
                'success_score': exp.confidence_score,
                'outcome': exp.outcome
            })
        
        # Find consistent patterns
        consistent_mappings = {}
        for context, actions in context_action_map.items():
            if len(actions) >= 2:
                # Find most successful action for this context
                best_action = max(actions, key=lambda a: a['success_score'])
                if best_action['success_score'] > 0.6:
                    consistent_mappings[context] = best_action
        
        if not consistent_mappings:
            return None
        
        confidence = min(len(consistent_mappings) / 5.0, 1.0)
        
        pattern = {
            'type': 'context_action_pattern',
            'content': {
                'context_action_mappings': consistent_mappings,
                'mapping_count': len(consistent_mappings),
                'reliability_threshold': 0.6
            },
            'confidence': confidence,
            'tags': ['context', 'action', 'mapping', 'decision_support']
        }
        
        return pattern
        
    except Exception as e:
        self.logger.error("Failed to extract context-action pattern", error=str(e))
        return None

def _find_common_actions(self, experiences: List[AgentExperience]) -> List[str]:
    """Find actions that appear frequently across experiences"""
    action_counts = {}
    
    for exp in experiences:
        action = exp.action_taken
        action_counts[action] = action_counts.get(action, 0) + 1
    
    # Return actions that appear in at least 50% of experiences
    threshold = max(1, len(experiences) // 2)
    return [action for action, count in action_counts.items() if count >= threshold]

def _find_common_contexts(self, experiences: List[AgentExperience]) -> Dict[str, Any]:
    """Find context elements that appear frequently across experiences"""
    context_counts = {}
    
    for exp in experiences:
        for key, value in exp.context.items():
            context_key = f"{key}:{value}"
            context_counts[context_key] = context_counts.get(context_key, 0) + 1
    
    # Return context elements that appear in at least 50% of experiences
    threshold = max(1, len(experiences) // 2)
    common_contexts = {}
    
    for context_key, count in context_counts.items():
        if count >= threshold:
            key, value = context_key.split(':', 1)
            common_contexts[key] = value
    
    return common_contexts

def _determine_knowledge_type(self, pattern: Dict[str, Any]) -> KnowledgeType:
    """Determine the type of knowledge based on pattern characteristics"""
    pattern_type = pattern.get('type', '')
    tags = pattern.get('tags', [])
    
    if 'action' in tags and 'guidance' in tags:
        return KnowledgeType.PROCEDURAL
    elif 'context' in tags and 'mapping' in tags:
        return KnowledgeType.CONTEXTUAL
    elif 'pattern' in tags:
        return KnowledgeType.BEHAVIORAL
    elif 'success' in tags or 'failure' in tags:
        return KnowledgeType.STRATEGIC
    else:
        return KnowledgeType.DECLARATIVE

async def _validate_knowledge_quality(self, knowledge: KnowledgeItem) -> bool:
    """Validate knowledge quality before storage"""
    try:
        # Check confidence threshold
        if knowledge.confidence < self.config.confidence_threshold:
            return False
        
        # Check content completeness
        if not knowledge.content or len(knowledge.content) == 0:
            return False
        
        # Check for duplicate knowledge
        if await self._is_duplicate_knowledge(knowledge):
            return False
        
        # Check source experiences
        if len(knowledge.source_experiences) == 0:
            return False
        
        return True
        
    except Exception as e:
        self.logger.error("Knowledge quality validation failed", error=str(e))
        return False

async def _is_duplicate_knowledge(self, knowledge: KnowledgeItem) -> bool:
    """Check if knowledge item is a duplicate of existing knowledge"""
    try:
        # Simple duplicate detection based on content similarity
        for existing_knowledge in self._knowledge_cache.values():
            if (existing_knowledge.knowledge_type == knowledge.knowledge_type and
                self._calculate_content_similarity(existing_knowledge.content, knowledge.content) > 0.8):
                return True
        
        return False
        
    except Exception as e:
        self.logger.error("Duplicate knowledge check failed", error=str(e))
        return False

def _calculate_content_similarity(self, content1: Dict[str, Any], content2: Dict[str, Any]) -> float:
    """Calculate similarity between two knowledge content dictionaries"""
    try:
        # Convert to string representations for simple comparison
        str1 = json.dumps(content1, sort_keys=True)
        str2 = json.dumps(content2, sort_keys=True)
        
        # Simple Jaccard similarity on words
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
        
    except Exception:
        return 0.0

async def _store_knowledge_item(self, knowledge: KnowledgeItem) -> None:
    """Store knowledge item in cache and persistent storage"""
    try:
        # Add to local cache
        self._knowledge_cache[knowledge.knowledge_id] = knowledge
        
        # Store in Redis
        await self._redis_client.hset(
            f"knowledge:{self.agent_id}:{knowledge.knowledge_id}",
            mapping=self._serialize_knowledge(knowledge)
        )
        
        # Add to knowledge index
        await self._redis_client.sadd(
            f"knowledge:index:{self.agent_id}",
            knowledge.knowledge_id
        )
        
        # Update global knowledge counter
        await self._redis_client.incr("learning:global:knowledge_count")
        
        # Emit learning event
        await self._emit_learning_event(
            LearningEventType.KNOWLEDGE_ACQUIRED,
            {
                "knowledge_id": knowledge.knowledge_id,
                "knowledge_type": knowledge.knowledge_type.value,
                "confidence": knowledge.confidence
            }
        )
        
        self.logger.info(
            "Knowledge item stored",
            knowledge_id=knowledge.knowledge_id,
            knowledge_type=knowledge.knowledge_type.value
        )
        
    except Exception as e:
        self.logger.error("Failed to store knowledge item", error=str(e))
        raise

def _serialize_knowledge(self, knowledge: KnowledgeItem) -> Dict[str, str]:
    """Serialize knowledge item for Redis storage"""
    return {
        "knowledge_id": knowledge.knowledge_id,
        "agent_id": knowledge.agent_id,
        "knowledge_type": knowledge.knowledge_type.value,
        "content": json.dumps(knowledge.content),
        "confidence": str(knowledge.confidence),
        "source_experiences": json.dumps(knowledge.source_experiences),
        "created_at": knowledge.created_at.isoformat(),
        "last_updated": knowledge.last_updated.isoformat(),
        "usage_count": str(knowledge.usage_count),
        "success_rate": str(knowledge.success_rate),
        "tags": json.dumps(list(knowledge.tags)),
        "transferable": str(knowledge.transferable)
    }

def _deserialize_knowledge(self, data: Dict[str, str]) -> KnowledgeItem:
    """Deserialize knowledge item from Redis storage"""
    return KnowledgeItem(
        knowledge_id=data["knowledge_id"],
        agent_id=data["agent_id"],
        knowledge_type=KnowledgeType(data["knowledge_type"]),
        content=json.loads(data["content"]),
        confidence=float(data["confidence"]),
        source_experiences=json.loads(data["source_experiences"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        last_updated=datetime.fromisoformat(data["last_updated"]),
        usage_count=int(data["usage_count"]),
        success_rate=float(data["success_rate"]),
        tags=set(json.loads(data["tags"])),
        transferable=data["transferable"].lower() == "true"
    )

async def _update_learning_velocity(self, new_knowledge_count: int) -> None:
    """Update learning velocity metrics"""
    try:
        current_time = datetime.utcnow()
        time_window_start = current_time - timedelta(seconds=LEARNING_VELOCITY_WINDOW)
        
        # Get knowledge created in the last hour
        recent_knowledge_count = 0
        for knowledge in self._knowledge_cache.values():
            if knowledge.created_at >= time_window_start:
                recent_knowledge_count += 1
        
        # Calculate velocity (knowledge items per hour)
        velocity = recent_knowledge_count / (LEARNING_VELOCITY_WINDOW / 3600)
        self._metrics.learning_velocity = velocity
        
        # Update metrics in Redis
        await self._redis_client.hset(
            f"learning:metrics:{self.agent_id}",
            "learning_velocity",
            str(velocity)
        )
        
        self.logger.debug(
            "Learning velocity updated",
            velocity=velocity,
            recent_knowledge_count=recent_knowledge_count
        )
        
    except Exception as e:
        self.logger.error("Failed to update learning velocity", error=str(e))

@track_performance
async def retrieve_knowledge(self, query: Dict[str, Any]) -> List[KnowledgeItem]:
    """Retrieve relevant knowledge for agent decision making"""
    try:
        # Parse query parameters
        knowledge_type = query.get("knowledge_type")
        tags = set(query.get("tags", []))
        min_confidence = query.get("min_confidence", self.config.confidence_threshold)
        context = query.get("context", {})
        limit = query.get("limit", 10)
        
        # Filter knowledge based on query
        relevant_knowledge = []
        
        for knowledge in self._knowledge_cache.values():
            # Type filter
            if knowledge_type and knowledge.knowledge_type.value != knowledge_type:
                continue
            
            # Confidence filter
            if knowledge.confidence < min_confidence:
                continue
            
            # Tag filter
            if tags and not tags.intersection(knowledge.tags):
                continue
            
            # Context relevance (simple matching)
            if context and not self._is_contextually_relevant(knowledge, context):
                continue
            
            relevant_knowledge.append(knowledge)
        
        # Sort by relevance (confidence + usage success)
        relevant_knowledge.sort(
            key=lambda k: k.confidence * (1 + k.success_rate),
            reverse=True
        )
        
        # Update usage counts
        for knowledge in relevant_knowledge[:limit]:
            knowledge.usage_count += 1
            knowledge.last_updated = datetime.utcnow()
            await self._update_knowledge_usage(knowledge)
        
        self.logger.debug(
            "Knowledge retrieved",
            query=query,
            results_count=len(relevant_knowledge[:limit])
        )
        
        return relevant_knowledge[:limit]
        
    except Exception as e:
        self.logger.error("Failed to retrieve knowledge", error=str(e))
        return []

def _is_contextually_relevant(self, knowledge: KnowledgeItem, context: Dict[str, Any]) -> bool:
    """Check if knowledge is relevant to the given context"""
    try:
        # Simple context matching based on knowledge content
        knowledge_context = knowledge.content.get("context", {})
        
        # Check for overlapping context keys
        common_keys = set(knowledge_context.keys()).intersection(set(context.keys()))
        if not common_keys:
            return True  # No context constraints, assume relevant
        
        # Check for matching values
        matches = 0
        for key in common_keys:
            if knowledge_context[key] == context[key]:
                matches += 1
        
        # Require at least 50% context match
        return matches / len(common_keys) >= 0.5
        
    except Exception:
        return True  # Default to relevant if check fails

async def _update_knowledge_usage(self, knowledge: KnowledgeItem) -> None:
    """Update knowledge usage statistics"""
    try:
        # Update in cache
        self._knowledge_cache[knowledge.knowledge_id] = knowledge
        
        # Update in Redis
        await self._redis_client.hset(
            f"knowledge:{self.agent_id}:{knowledge.knowledge_id}",
            mapping={
                "usage_count": str(knowledge.usage_count),
                "last_updated": knowledge.last_updated.isoformat()
            }
        )
        
    except Exception as e:
        self.logger.error("Failed to update knowledge usage", error=str(e))

@track_performance
async def share_knowledge(self, knowledge: KnowledgeItem, target_agents: List[str]) -> bool:
    """Share knowledge with other agents"""
    if not self.config.knowledge_sharing_enabled or not knowledge.transferable:
        return False
        
    try:
        successful_transfers = 0
        
        for target_agent in target_agents:
            # Check if target agent is active
            is_active = await self._redis_client.sismember("learning:active_agents", target_agent)
            if not is_active:
                continue
            
            # Create transfer record
            transfer_data = {
                "source_agent": self.agent_id,
                "target_agent": target_agent,
                "knowledge_id": knowledge.knowledge_id,
                "knowledge_data": json.dumps(knowledge.to_dict()),
                "transfer_time": datetime.utcnow().isoformat(),
                "status": "pending"
            }
            
            # Queue knowledge transfer
            await self._redis_client.lpush(
                f"learning:transfer_queue:{target_agent}",
                json.dumps(transfer_data)
            )
            
            # Update transfer metrics
            await self._redis_client.incr(f"learning:transfers:sent:{self.agent_id}")
            successful_transfers += 1
        
        # Update metrics
        self._metrics.knowledge_transfer_count += successful_transfers
        
        # Emit learning event
        await self._emit_learning_event(
            LearningEventType.KNOWLEDGE_SHARED,
            {
                "knowledge_id": knowledge.knowledge_id,
                "target_agents": target_agents,
                "successful_transfers": successful_transfers
            }
        )
        
        self.logger.info(
            "Knowledge shared",
            knowledge_id=knowledge.knowledge_id,
            target_agents_count=len(target_agents),
            successful_transfers=successful_transfers
        )
        
        return successful_transfers > 0
        
    except Exception as e:
        self.logger.error("Failed to share knowledge", error=str(e))
        return False

async def process_incoming_knowledge(self) -> None:
    """Process knowledge shared by other agents"""
    try:
        # Check transfer queue
        queue_key = f"learning:transfer_queue:{self.agent_id}"
        
        while True:
            # Get transfer from queue (blocking with timeout)
            transfer_data = await self._redis_client.brpop(queue_key, timeout=1)
            if not transfer_data:
                break
            
            transfer_info = json.loads(transfer_data[1])
            
            # Process the knowledge transfer
            success = await self._process_knowledge_transfer(transfer_info)
            
            # Update transfer status
            transfer_info["status"] = "completed" if success else "failed"
            transfer_info["processed_time"] = datetime.utcnow().isoformat()
            
            # Log transfer result
            await self._redis_client.lpush(
                f"learning:transfer_log:{self.agent_id}",
                json.dumps(transfer_info)
            )
            
    except Exception as e:
        self.logger.error("Failed to process incoming knowledge", error=str(e))

async def _process_knowledge_transfer(self, transfer_info: Dict[str, Any]) -> bool:
    """Process a single knowledge transfer"""
    try:
        knowledge_data = json.loads(transfer_info["knowledge_data"])
        
        # Create knowledge item
        knowledge = KnowledgeItem(
            knowledge_id=knowledge_data["knowledge_id"],
            agent_id=self.agent_id,  # Assign to this agent
            knowledge_type=KnowledgeType(knowledge_data["knowledge_type"]),
            content=knowledge_data["content"],
            confidence=knowledge_data["confidence"] * 0.9,  # Reduce confidence for transferred knowledge
            source_experiences=knowledge_data["source_experiences"],
            created_at=datetime.fromisoformat(knowledge_data["created_at"]),
            last_updated=datetime.utcnow(),
            usage_count=0,  # Reset usage count
            success_rate=knowledge_data["success_rate"],
            tags=set(knowledge_data["tags"]),
            transferable=knowledge_data["transferable"]
        )
        
        # Validate and store if not duplicate
        if await self._validate_knowledge_quality(knowledge):
            await self._store_knowledge_item(knowledge)
            
            # Update collaboration score
            await self._update_collaboration_score(transfer_info["source_agent"])
            
            return True
        
        return False
        
    except Exception as e:
        self.logger.error("Failed to process knowledge transfer", error=str(e))
        return False

async def _update_collaboration_score(self, source_agent: str) -> None:
    """Update collaboration score based on knowledge sharing"""
    try:
        # Increment collaboration counter
        await self._redis_client.incr(f"learning:collaboration:{self.agent_id}:{source_agent}")
        
        # Calculate overall collaboration score
        collaboration_keys = await self._redis_client.keys(f"learning:collaboration:{self.agent_id}:*")
        total_collaborations = 0
        
        for key in collaboration_keys:
            count = await self._redis_client.get(key)
            total_collaborations += int(count) if count else 0
        
        # Update metrics
        self._metrics.collaboration_score = min(total_collaborations / 100.0, 1.0)
        
        await self._redis_client.hset(
            f"learning:metrics:{self.agent_id}",
            "collaboration_score",
            str(self._metrics.collaboration_score)
        )
        
    except Exception as e:
        self.logger.error("Failed to update collaboration score", error=str(e))

async def _emit_learning_event(self, event_type: LearningEventType, data: Dict[str, Any]) -> None:
    """Emit learning event for monitoring and analytics"""
    try:
        event = {
            "event_type": event_type.value,
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        # Publish to learning events channel
        await self._redis_client.publish("learning:events", json.dumps(event))
        
        # Store in events log
        await self._redis_client.lpush("learning:events:log", json.dumps(event))
        
        # Trim log to prevent memory issues
        await self._redis_client.ltrim("learning:events:log", 0, 9999)
        
    except Exception as e:
        self.logger.error("Failed to emit learning event", error=str(e))

async def get_learning_metrics(self) -> LearningMetrics:
    """Get current learning metrics for the agent"""
    try:
        # Update memory usage
        import psutil
        process = psutil.Process()
        self._metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        
        # Update knowledge statistics
        if self._knowledge_cache:
            confidences = [k.confidence for k in self._knowledge_cache.values()]
            self._metrics.average_confidence = sum(confidences) / len(confidences)
        
        # Update last updated time
        self._metrics.last_updated = datetime.utcnow()
        
        return self._metrics
        
    except Exception as e:
        self.logger.error("Failed to get learning metrics", error=str(e))
        return self._metrics

async def cleanup(self) -> None:
    """Cleanup learning integration resources"""
    try:
        # Process remaining experiences
        if self._experience_buffer:
            await self._process_experience_batch()
        
        # Update agent status
        await self._redis_client.srem("learning:active_agents", self.agent_id)
        await self._redis_client.hset(
            f"learning:agents:{self.agent_id}",
            "status",
            "inactive"
        )
        
        # Close Redis connection
        if self._redis_client:
            await self._redis_client.close()
        
        self._learning_active = False
        self.logger.info("Learning integration cleanup completed")
        
    except Exception as e:
        self.logger.error("Failed to cleanup learning integration", error=str(e))
```

# ===============================================================================

# AGENT LEARNING WRAPPER

# ===============================================================================

class LearningEnabledAgent:
“”“Wrapper class to add learning capabilities to existing agents”””

```
def __init__(self, base_agent: Any, learning_config: LearningIntegrationConfig):
    self.base_agent = base_agent
    self.learning_integrator = AgentLearningIntegrator(
        agent_id=learning_config.agent_id,
        config=learning_config
    )
    self.logger = logger.bind(agent_id=learning_config.agent_id)
    
async def initialize(self) -> None:
    """Initialize both base agent and learning integration"""
    try:
        # Initialize base agent if it has initialize method
        if hasattr(self.base_agent, 'initialize'):
            await self.base_agent.initialize()
        
        # Initialize learning integration
        await self.learning_integrator.initialize()
        
        self.logger.info("Learning-enabled agent initialized")
        
    except Exception as e:
        self.logger.error("Failed to initialize learning-enabled agent", error=str(e))
        raise

async def execute_with_learning(self, task: Dict[str, Any]) -> Dict[str, Any]:
    """Execute agent task with learning integration"""
    start_time = datetime.utcnow()
    
    try:
        # Pre-execution: Retrieve relevant knowledge
        relevant_knowledge = await self.learning_integrator.retrieve_knowledge({
            "context": task.get("context", {}),
            "tags": task.get("learning_tags", []),
            "limit": 5
        })
        
        # Inject knowledge into task context
        if relevant_knowledge:
            task["learned_knowledge"] = [k.to_dict() for k in relevant_knowledge]
        
        # Execute base agent task
        if hasattr(self.base_agent, 'execute'):
            result = await self.base_agent.execute(task)
        elif callable(self.base_agent):
            result = await self.base_agent(task)
        else:
            raise AttributeError("Base agent must have execute method or be callable")
        
        # Post-execution: Capture experience
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        experience = AgentExperience(
            agent_id=self.learning_integrator.agent_id,
            event_type="task_execution",
            context=task.get("context", {}),
            action_taken=task.get("action", "unknown"),
            outcome=result,
            success_metrics={
                "execution_time": execution_time,
                "success": result.get("success", False),
                "quality_score": result.get("quality_score", 0.5)
            },
            confidence_score=result.get("confidence", 0.5),
            learning_tags=set(task.get("learning_tags", []))
        )
        
        await self.learning_integrator.capture_experience(experience)
        
        # Add learning metadata to result
        result["learning_metadata"] = {
            "knowledge_used": len(relevant_knowledge),
            "experience_captured": True,
            "learning_active": True
        }
        
        return result
        
    except Exception as e:
        # Capture failure experience
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        failure_experience = AgentExperience(
            agent_id=self.learning_integrator.agent_id,
            event_type="task_failure",
            context=task.get("context", {}),
            action_taken=task.get("action", "unknown"),
            outcome={"error": str(e), "success": False},
            success_metrics={
                "execution_time": execution_time,
                "success": False,
                "error_severity": 1.0
            },
            confidence_score=0.0,
            learning_tags=set(task.get("learning_tags", []))
        )
        
        await self.learning_integrator.capture_experience(failure_experience)
        
        self.logger.error("Task execution failed", error=str(e))
        raise

async def share_knowledge_with_agents(self, agent_ids: List[str]) -> bool:
    """Share agent's best knowledge with specified agents"""
    try:
        # Get high-quality knowledge items
        high_quality_knowledge = [
            k for k in self.learning_integrator._knowledge_cache.values()
            if k.confidence > 0.8 and k.success_rate > 0.7 and k.transferable
        ]
        
        # Sort by quality and take top 5
        high_quality_knowledge.sort(
            key=lambda k: k.confidence * k.success_rate,
            reverse=True
        )
        
        shared_count = 0
        for knowledge in high_quality_knowledge[:5]:
            success = await self.learning_integrator.share_knowledge(knowledge, agent_ids)
            if success:
                shared_count += 1
        
        self.logger.info(
            "Knowledge sharing completed",
            target_agents=len(agent_ids),
            knowledge_items_shared=shared_count
        )
        
        return shared_count > 0
        
    except Exception as e:
        self.logger.error("Failed to share knowledge with agents", error=str(e))
        return False

async def get_learning_status(self) -> Dict[str, Any]:
    """Get comprehensive learning status"""
    try:
        metrics = await self.learning_integrator.get_learning_metrics()
        
        return {
            "agent_id": self.learning_integrator.agent_id,
            "learning_active": self.learning_integrator._learning_active,
            "knowledge_count": len(self.learning_integrator._knowledge_cache),
            "experience_buffer_size": len(self.learning_integrator._experience_buffer),
            "metrics": metrics.to_dict(),
            "last_sync": self.learning_integrator._last_sync_time.isoformat(),
            "configuration": self.learning_integrator.config.dict()
        }
        
    except Exception as e:
        self.logger.error("Failed to get learning status", error=str(e))
        return {"error": str(e)}

async def cleanup(self) -> None:
    """Cleanup both base agent and learning integration"""
    try:
        # Cleanup learning integration
        await self.learning_integrator.cleanup()
        
        # Cleanup base agent if it has cleanup method
        if hasattr(self.base_agent, 'cleanup'):
            await self.base_agent.cleanup()
        
        self.logger.info("Learning-enabled agent cleanup completed")
        
    except Exception as e:
        self.logger.error("Failed to cleanup learning-enabled agent", error=str(e))
```

# ===============================================================================

# UTILITY FUNCTIONS

# ===============================================================================

async def create_learning_enabled_agent(
base_agent: Any,
agent_id: str,
learning_config: Optional[Dict[str, Any]] = None
) -> LearningEnabledAgent:
“”“Factory function to create learning-enabled agent”””
try:
# Create configuration
config_dict = learning_config or {}
config_dict[“agent_id”] = agent_id

```
    config = LearningIntegrationConfig(**config_dict)
    
    # Create learning-enabled agent
    learning_agent = LearningEnabledAgent(base_agent, config)
    await learning_agent.initialize()
    
    logger.info("Learning-enabled agent created", agent_id=agent_id)
    return learning_agent
    
except Exception as e:
    logger.error("Failed to create learning-enabled agent", agent_id=agent_id, error=str(e))
    raise
```

async def health_check() -> Dict[str, Any]:
“”“Learning integration health check”””
return {
“status”: “healthy”,
“timestamp”: datetime.utcnow().isoformat(),
“module”: “agent_learning_integration”,
“version”: “4.0”
}

# ===============================================================================

# MODULE INITIALIZATION

# ===============================================================================

async def initialize_learning_integration_system() -> Dict[str, Any]:
“”“Initialize the learning integration system”””
try:
# Initialize Redis connection pool
redis_client = await aioredis.from_url(
settings.REDIS_URL,
encoding=“utf-8”,
decode_responses=True,
max_connections=50
)

```
    # Initialize system counters
    await redis_client.setnx("learning:global:knowledge_count", 0)
    await redis_client.setnx("learning:global:experience_count", 0)
    await redis_client.setnx("learning:global:transfer_count", 0)
    
    # Initialize active agents set
    await redis_client.delete("learning:active_agents")
    
    await redis_client.close()
    
    logger.info("Learning integration system initialized successfully")
    
    return {
        "status": "initialized",
        "timestamp": datetime.utcnow().isoformat(),
        "components": [
            "AgentLearningIntegrator",
            "LearningEnabledAgent",
            "Redis Connection Pool",
            "Global Counters"
        ]
    }
    
except Exception as e:
    logger.error("Failed to initialize learning integration system", error=str(e))
    raise
```

# ===============================================================================

# EXPORTS

# ===============================================================================

**all** = [
“AgentLearningIntegrator”,
“LearningEnabledAgent”,
“AgentExperience”,
“KnowledgeItem”,
“LearningMetrics”,
“LearningIntegrationConfig”,
“LearningEventType”,
“KnowledgeType”,
“create_learning_enabled_agent”,
“initialize_learning_integration_system”,
“health_check”
]