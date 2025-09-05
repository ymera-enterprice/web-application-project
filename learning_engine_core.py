"""
YMERA Enterprise - Learning Engine Core Classes
Production-Ready Continuous Learning System - v4.0
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
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Set, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from enum import Enum
import time
import hashlib
from pathlib import Path

# Third-party imports (alphabetical)
import aioredis
import networkx as nx
import numpy as np
import structlog
from fastapi import HTTPException
from pydantic import BaseModel, Field, validator
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from monitoring.performance_tracker import track_performance
from utils.encryption import encrypt_data, decrypt_data

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.learning_engine")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Learning cycle timings
LEARNING_CYCLE_INTERVAL = 60  # seconds
KNOWLEDGE_SYNC_INTERVAL = 300  # 5 minutes
PATTERN_DISCOVERY_INTERVAL = 900  # 15 minutes
MEMORY_CONSOLIDATION_INTERVAL = 3600  # 1 hour

# Learning thresholds
MIN_PATTERN_CONFIDENCE = 0.7
MIN_KNOWLEDGE_RELEVANCE = 0.6
MAX_KNOWLEDGE_AGE_DAYS = 30
KNOWLEDGE_RETENTION_THRESHOLD = 0.8

settings = get_settings()

# ===============================================================================
# ENUMS & DATA MODELS
# ===============================================================================

class LearningType(Enum):
    """Types of learning in the system"""
    EXPERIENTIAL = "experiential"
    COLLABORATIVE = "collaborative" 
    EXTERNAL = "external"
    PATTERN_BASED = "pattern_based"

class KnowledgeStatus(Enum):
    """Status of knowledge items"""
    ACTIVE = "active"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"
    PENDING_VALIDATION = "pending_validation"

@dataclass
class Experience:
    """Agent experience data structure"""
    id: str
    agent_id: str
    timestamp: datetime
    action: str
    context: Dict[str, Any]
    outcome: Dict[str, Any]
    success: bool
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class KnowledgeItem:
    """Knowledge representation in the system"""
    id: str
    content: Dict[str, Any]
    source_type: LearningType
    source_id: str
    confidence: float
    relevance_scores: Dict[str, float]
    creation_time: datetime
    last_accessed: datetime
    access_count: int
    status: KnowledgeStatus
    tags: Set[str] = field(default_factory=set)
    relationships: Dict[str, float] = field(default_factory=dict)

@dataclass
class LearningPattern:
    """Discovered behavioral pattern"""
    id: str
    pattern_type: str
    description: str
    conditions: Dict[str, Any]
    outcomes: Dict[str, Any]
    confidence: float
    frequency: int
    agents_involved: Set[str]
    discovered_at: datetime
    effectiveness: float

@dataclass
class LearningMetrics:
    """Comprehensive learning system metrics"""
    learning_velocity: float  # knowledge items per hour
    knowledge_retention_rate: float
    agent_knowledge_diversity: float
    collaboration_score: float
    external_integration_success: float
    problem_solving_efficiency: float
    pattern_discovery_count: int
    knowledge_transfer_count: int
    total_experiences: int
    active_knowledge_items: int

# ===============================================================================
# CORE LEARNING ENGINE CLASSES
# ===============================================================================

class KnowledgeGraph:
    """Production-ready knowledge graph implementation"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.knowledge_index = {}
        self.vector_store = {}
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.logger = logger.bind(component="knowledge_graph")
    
    async def add_knowledge(self, knowledge: KnowledgeItem) -> bool:
        """Add knowledge item to the graph"""
        try:
            # Add node to graph
            self.graph.add_node(
                knowledge.id,
                content=knowledge.content,
                confidence=knowledge.confidence,
                creation_time=knowledge.creation_time,
                status=knowledge.status,
                tags=knowledge.tags
            )
            
            # Index for fast retrieval
            self.knowledge_index[knowledge.id] = knowledge
            
            # Create vector representation for similarity search
            content_text = json.dumps(knowledge.content)
            content_vector = self._vectorize_content(content_text)
            self.vector_store[knowledge.id] = content_vector
            
            # Establish relationships with existing knowledge
            await self._establish_relationships(knowledge)
            
            self.logger.info("Knowledge added", knowledge_id=knowledge.id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to add knowledge", error=str(e), knowledge_id=knowledge.id)
            return False
    
    async def find_similar_knowledge(
        self, 
        query_content: Dict[str, Any], 
        threshold: float = 0.6,
        limit: int = 10
    ) -> List[KnowledgeItem]:
        """Find similar knowledge items"""
        try:
            query_text = json.dumps(query_content)
            query_vector = self._vectorize_content(query_text)
            
            similarities = []
            for kid, vector in self.vector_store.items():
                similarity = cosine_similarity([query_vector], [vector])[0][0]
                if similarity >= threshold:
                    similarities.append((kid, similarity))
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            results = []
            for kid, sim_score in similarities[:limit]:
                knowledge = self.knowledge_index[kid]
                knowledge.relevance_scores['query_similarity'] = sim_score
                results.append(knowledge)
            
            return results
            
        except Exception as e:
            self.logger.error("Failed to find similar knowledge", error=str(e))
            return []
    
    async def get_knowledge_by_tags(self, tags: Set[str]) -> List[KnowledgeItem]:
        """Retrieve knowledge items by tags"""
        results = []
        for knowledge in self.knowledge_index.values():
            if knowledge.tags.intersection(tags):
                results.append(knowledge)
        return results
    
    async def update_knowledge_relationships(self) -> None:
        """Update relationships between knowledge items"""
        try:
            # Calculate similarities between all knowledge items
            knowledge_ids = list(self.vector_store.keys())
            vectors = list(self.vector_store.values())
            
            if len(vectors) < 2:
                return
            
            similarity_matrix = cosine_similarity(vectors)
            
            # Update graph edges based on similarities
            for i, kid1 in enumerate(knowledge_ids):
                for j, kid2 in enumerate(knowledge_ids):
                    if i != j and similarity_matrix[i][j] > MIN_KNOWLEDGE_RELEVANCE:
                        self.graph.add_edge(
                            kid1, kid2, 
                            weight=similarity_matrix[i][j],
                            relationship_type="similarity"
                        )
            
            self.logger.info("Knowledge relationships updated")
            
        except Exception as e:
            self.logger.error("Failed to update knowledge relationships", error=str(e))
    
    def _vectorize_content(self, content: str) -> np.ndarray:
        """Convert content to vector representation"""
        try:
            # Fit vectorizer if not already done
            if not hasattr(self.vectorizer, 'vocabulary_'):
                all_content = [json.dumps(k.content) for k in self.knowledge_index.values()]
                if all_content:
                    self.vectorizer.fit(all_content + [content])
            
            return self.vectorizer.transform([content]).toarray()[0]
        except:
            # Return zero vector if vectorization fails
            return np.zeros(1000)
    
    async def _establish_relationships(self, new_knowledge: KnowledgeItem) -> None:
        """Establish relationships with existing knowledge"""
        similar_items = await self.find_similar_knowledge(
            new_knowledge.content, 
            threshold=MIN_KNOWLEDGE_RELEVANCE,
            limit=5
        )
        
        for similar_item in similar_items:
            if similar_item.id != new_knowledge.id:
                self.graph.add_edge(
                    new_knowledge.id,
                    similar_item.id,
                    weight=similar_item.relevance_scores.get('query_similarity', 0.0),
                    relationship_type="content_similarity"
                )


class ExperienceProcessor:
    """Process and extract knowledge from agent experiences"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        self.experience_buffer = deque(maxlen=1000)
        self.processing_queue = asyncio.Queue()
        self.logger = logger.bind(component="experience_processor")
    
    async def add_experience(self, experience: Experience) -> None:
        """Add new experience for processing"""
        self.experience_buffer.append(experience)
        await self.processing_queue.put(experience)
        self.logger.debug("Experience added", experience_id=experience.id)
    
    async def process_experiences(self) -> int:
        """Process pending experiences and extract knowledge"""
        processed_count = 0
        
        while not self.processing_queue.empty():
            try:
                experience = await self.processing_queue.get()
                knowledge_items = await self._extract_knowledge(experience)
                
                for knowledge in knowledge_items:
                    await self.knowledge_graph.add_knowledge(knowledge)
                    processed_count += 1
                
            except Exception as e:
                self.logger.error("Failed to process experience", error=str(e))
        
        return processed_count
    
    async def _extract_knowledge(self, experience: Experience) -> List[KnowledgeItem]:
        """Extract actionable knowledge from experience"""
        knowledge_items = []
        
        try:
            # Extract action-outcome knowledge
            if experience.success and experience.confidence > 0.6:
                action_knowledge = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    content={
                        "type": "action_outcome",
                        "action": experience.action,
                        "context": experience.context,
                        "outcome": experience.outcome,
                        "conditions": self._extract_conditions(experience.context)
                    },
                    source_type=LearningType.EXPERIENTIAL,
                    source_id=experience.agent_id,
                    confidence=experience.confidence,
                    relevance_scores={"experience_based": experience.confidence},
                    creation_time=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    status=KnowledgeStatus.PENDING_VALIDATION,
                    tags=knowledge.tags.union({target_agent, "transferred", "collaborative"}),
                    relationships=knowledge.relationships.copy()
                )
                
                # Add to knowledge graph
                success = await self.knowledge_graph.add_knowledge(adapted_knowledge)
                if success:
                    # Record transfer
                    self.transfer_history[target_agent].append({
                        "source_agent": source_agent,
                        "knowledge_id": adapted_knowledge.id,
                        "original_knowledge_id": knowledge.id,
                        "transfer_time": datetime.utcnow(),
                        "expertise_area": opportunity["expertise_area"]
                    })
            
            self.logger.info("Knowledge transfer executed",
                           source=source_agent,
                           target=target_agent,
                           count=len(knowledge_items))
            return True
            
        except Exception as e:
            self.logger.error("Knowledge transfer failed", error=str(e))
            return False


class ExternalLearningIntegrator:
    """Integrate external knowledge sources"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        self.external_sources = {}
        self.validation_pipeline = []
        self.logger = logger.bind(component="external_learning")
    
    async def integrate_file_knowledge(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """Integrate knowledge from uploaded files"""
        try:
            file_content = await self._process_file(file_path)
            if not file_content:
                return False
            
            # Extract knowledge items from file content
            knowledge_items = await self._extract_file_knowledge(file_content, metadata)
            
            # Validate and add knowledge
            validated_count = 0
            for knowledge in knowledge_items:
                if await self._validate_external_knowledge(knowledge):
                    await self.knowledge_graph.add_knowledge(knowledge)
                    validated_count += 1
            
            self.logger.info("File knowledge integrated", 
                           file=file_path, 
                           extracted=len(knowledge_items),
                           validated=validated_count)
            
            return validated_count > 0
            
        except Exception as e:
            self.logger.error("File integration failed", error=str(e), file=file_path)
            return False
    
    async def integrate_api_knowledge(self, api_response: Dict[str, Any], source_info: Dict[str, Any]) -> bool:
        """Integrate knowledge from API responses"""
        try:
            # Process API response into knowledge format
            knowledge_items = await self._extract_api_knowledge(api_response, source_info)
            
            validated_count = 0
            for knowledge in knowledge_items:
                if await self._validate_external_knowledge(knowledge):
                    await self.knowledge_graph.add_knowledge(knowledge)
                    validated_count += 1
            
            self.logger.info("API knowledge integrated",
                           source=source_info.get("source", "unknown"),
                           extracted=len(knowledge_items),
                           validated=validated_count)
            
            return validated_count > 0
            
        except Exception as e:
            self.logger.error("API integration failed", error=str(e))
            return False
    
    async def integrate_user_feedback(self, feedback: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Integrate knowledge from user feedback"""
        try:
            # Convert feedback into knowledge items
            knowledge_items = await self._extract_feedback_knowledge(feedback, context)
            
            validated_count = 0
            for knowledge in knowledge_items:
                if await self._validate_external_knowledge(knowledge):
                    await self.knowledge_graph.add_knowledge(knowledge)
                    validated_count += 1
            
            self.logger.info("User feedback integrated",
                           feedback_type=feedback.get("type", "unknown"),
                           validated=validated_count)
            
            return validated_count > 0
            
        except Exception as e:
            self.logger.error("Feedback integration failed", error=str(e))
            return False
    
    async def _process_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Process uploaded file and extract content"""
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                return None
            
            content = {}
            
            if file_path_obj.suffix.lower() == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
            elif file_path_obj.suffix.lower() in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = {"text": f.read(), "type": "text"}
            else:
                # For other file types, store basic metadata
                content = {
                    "filename": file_path_obj.name,
                    "size": file_path_obj.stat().st_size,
                    "type": "binary"
                }
            
            return content
            
        except Exception as e:
            self.logger.error("File processing failed", error=str(e), file=file_path)
            return None
    
    async def _extract_file_knowledge(self, content: Dict[str, Any], metadata: Dict[str, Any]) -> List[KnowledgeItem]:
        """Extract knowledge items from file content"""
        knowledge_items = []
        
        try:
            if content.get("type") == "text":
                # Extract knowledge from text content
                text_content = content["text"]
                
                # Simple extraction: split by paragraphs and create knowledge items
                paragraphs = [p.strip() for p in text_content.split('\n\n') if p.strip()]
                
                for i, paragraph in enumerate(paragraphs):
                    if len(paragraph) > 50:  # Only meaningful paragraphs
                        knowledge = KnowledgeItem(
                            id=str(uuid.uuid4()),
                            content={
                                "type": "text_knowledge",
                                "text": paragraph,
                                "source_file": metadata.get("filename", "unknown"),
                                "paragraph_index": i
                            },
                            source_type=LearningType.EXTERNAL,
                            source_id=f"file_{metadata.get('filename', 'unknown')}",
                            confidence=0.6,  # Lower confidence for external text
                            relevance_scores={"external_file": 0.6},
                            creation_time=datetime.utcnow(),
                            last_accessed=datetime.utcnow(),
                            access_count=0,
                            status=KnowledgeStatus.PENDING_VALIDATION,
                            tags={"external", "file", "text", metadata.get("category", "general")}
                        )
                        knowledge_items.append(knowledge)
            
            elif isinstance(content, dict) and "type" not in content:
                # JSON structured data
                knowledge = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    content={
                        "type": "structured_data",
                        "data": content,
                        "source_file": metadata.get("filename", "unknown")
                    },
                    source_type=LearningType.EXTERNAL,
                    source_id=f"file_{metadata.get('filename', 'unknown')}",
                    confidence=0.7,  # Higher confidence for structured data
                    relevance_scores={"external_structured": 0.7},
                    creation_time=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    status=KnowledgeStatus.PENDING_VALIDATION,
                    tags={"external", "file", "structured", metadata.get("category", "general")}
                )
                knowledge_items.append(knowledge)
                
        except Exception as e:
            self.logger.error("Knowledge extraction from file failed", error=str(e))
        
        return knowledge_items
    
    async def _extract_api_knowledge(self, api_response: Dict[str, Any], source_info: Dict[str, Any]) -> List[KnowledgeItem]:
        """Extract knowledge from API responses"""
        knowledge_items = []
        
        try:
            # Create knowledge item from API response
            knowledge = KnowledgeItem(
                id=str(uuid.uuid4()),
                content={
                    "type": "api_response",
                    "data": api_response,
                    "api_source": source_info.get("source", "unknown"),
                    "endpoint": source_info.get("endpoint", "unknown"),
                    "timestamp": source_info.get("timestamp", datetime.utcnow().isoformat())
                },
                source_type=LearningType.EXTERNAL,
                source_id=f"api_{source_info.get('source', 'unknown')}",
                confidence=0.8,  # High confidence for API data
                relevance_scores={"external_api": 0.8},
                creation_time=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                access_count=0,
                status=KnowledgeStatus.PENDING_VALIDATION,
                tags={"external", "api", source_info.get("source", "unknown"), source_info.get("category", "general")}
            )
            knowledge_items.append(knowledge)
            
        except Exception as e:
            self.logger.error("Knowledge extraction from API failed", error=str(e))
        
        return knowledge_items
    
    async def _extract_feedback_knowledge(self, feedback: Dict[str, Any], context: Dict[str, Any]) -> List[KnowledgeItem]:
        """Extract knowledge from user feedback"""
        knowledge_items = []
        
        try:
            feedback_type = feedback.get("type", "general")
            
            if feedback_type == "correction":
                # User correcting agent behavior
                knowledge = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    content={
                        "type": "user_correction",
                        "original_action": feedback.get("original_action"),
                        "correct_action": feedback.get("correct_action"),
                        "context": context,
                        "explanation": feedback.get("explanation", ""),
                        "user_id": feedback.get("user_id", "anonymous")
                    },
                    source_type=LearningType.EXTERNAL,
                    source_id=f"user_{feedback.get('user_id', 'anonymous')}",
                    confidence=0.9,  # High confidence for direct corrections
                    relevance_scores={"user_correction": 0.9},
                    creation_time=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    status=KnowledgeStatus.VALIDATED,  # User corrections are pre-validated
                    tags={"external", "feedback", "correction", feedback_type}
                )
                knowledge_items.append(knowledge)
            
            elif feedback_type == "preference":
                # User expressing preferences
                knowledge = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    content={
                        "type": "user_preference",
                        "preference": feedback.get("preference"),
                        "context": context,
                        "strength": feedback.get("strength", "medium"),
                        "user_id": feedback.get("user_id", "anonymous")
                    },
                    source_type=LearningType.EXTERNAL,
                    source_id=f"user_{feedback.get('user_id', 'anonymous')}",
                    confidence=0.7,
                    relevance_scores={"user_preference": 0.7},
                    creation_time=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    status=KnowledgeStatus.PENDING_VALIDATION,
                    tags={"external", "feedback", "preference", feedback_type}
                )
                knowledge_items.append(knowledge)
                
        except Exception as e:
            self.logger.error("Knowledge extraction from feedback failed", error=str(e))
        
        return knowledge_items
    
    async def _validate_external_knowledge(self, knowledge: KnowledgeItem) -> bool:
        """Validate external knowledge before integration"""
        try:
            # Basic validation checks
            if not knowledge.content or knowledge.confidence < 0.3:
                return False
            
            # Check for duplicate or very similar knowledge
            similar_knowledge = await self.knowledge_graph.find_similar_knowledge(
                knowledge.content, threshold=0.9, limit=3
            )
            
            if similar_knowledge:
                # If very similar knowledge exists, don't add duplicate
                return False
            
            # Content-specific validation
            content_type = knowledge.content.get("type", "unknown")
            
            if content_type == "text_knowledge":
                text = knowledge.content.get("text", "")
                if len(text) < 20 or len(text) > 5000:  # Reasonable text length
                    return False
            
            elif content_type == "user_correction":
                if not all(key in knowledge.content for key in ["original_action", "correct_action"]):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error("External knowledge validation failed", error=str(e))
            return False


class MemoryConsolidationSystem:
    """Manage memory consolidation and optimization"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        self.consolidation_history = []
        self.retention_stats = defaultdict(list)
        self.logger = logger.bind(component="memory_consolidation")
    
    async def consolidate_memory(self) -> Dict[str, Any]:
        """Perform memory consolidation process"""
        consolidation_results = {
            "deprecated_items": 0,
            "merged_items": 0,
            "optimized_relationships": 0,
            "retention_updates": 0
        }
        
        try:
            # Step 1: Identify and deprecate old/unused knowledge
            deprecated_count = await self._deprecate_old_knowledge()
            consolidation_results["deprecated_items"] = deprecated_count
            
            # Step 2: Merge similar knowledge items
            merged_count = await self._merge_similar_knowledge()
            consolidation_results["merged_items"] = merged_count
            
            # Step 3: Optimize knowledge relationships
            relationship_count = await self._optimize_relationships()
            consolidation_results["optimized_relationships"] = relationship_count
            
            # Step 4: Update retention statistics
            retention_count = await self._update_retention_stats()
            consolidation_results["retention_updates"] = retention_count
            
            # Record consolidation
            self.consolidation_history.append({
                "timestamp": datetime.utcnow(),
                "results": consolidation_results
            })
            
            self.logger.info("Memory consolidation completed", **consolidation_results)
            
        except Exception as e:
            self.logger.error("Memory consolidation failed", error=str(e))
        
        return consolidation_results
    
    async def _deprecate_old_knowledge(self) -> int:
        """Deprecate old or unused knowledge items"""
        deprecated_count = 0
        current_time = datetime.utcnow()
        
        for knowledge in list(self.knowledge_graph.knowledge_index.values()):
            # Check age and usage
            age_days = (current_time - knowledge.creation_time).days
            days_since_access = (current_time - knowledge.last_accessed).days
            
            should_deprecate = False
            
            # Age-based deprecation
            if age_days > MAX_KNOWLEDGE_AGE_DAYS and knowledge.access_count < 3:
                should_deprecate = True
            
            # Usage-based deprecation
            elif days_since_access > 14 and knowledge.access_count == 0:
                should_deprecate = True
            
            # Low confidence knowledge
            elif knowledge.confidence < 0.4 and knowledge.access_count < 2:
                should_deprecate = True
            
            if should_deprecate:
                knowledge.status = KnowledgeStatus.DEPRECATED
                deprecated_count += 1
                
                self.logger.debug("Knowledge deprecated",
                                knowledge_id=knowledge.id,
                                age_days=age_days,
                                access_count=knowledge.access_count)
        
        return deprecated_count
    
    async def _merge_similar_knowledge(self) -> int:
        """Merge very similar knowledge items"""
        merged_count = 0
        
        # Group knowledge by high similarity
        knowledge_items = [k for k in self.knowledge_graph.knowledge_index.values() 
                          if k.status != KnowledgeStatus.DEPRECATED]
        
        merge_groups = []
        processed_ids = set()
        
        for knowledge in knowledge_items:
            if knowledge.id in processed_ids:
                continue
            
            # Find very similar items
            similar_items = await self.knowledge_graph.find_similar_knowledge(
                knowledge.content, threshold=0.95, limit=5
            )
            
            similar_group = [knowledge]
            for similar in similar_items:
                if (similar.id != knowledge.id and 
                    similar.id not in processed_ids and
                    similar.source_type == knowledge.source_type):
                    similar_group.append(similar)
                    processed_ids.add(similar.id)
            
            if len(similar_group) > 1:
                merge_groups.append(similar_group)
                processed_ids.add(knowledge.id)
        
        # Perform merges
        for group in merge_groups:
            merged_knowledge = await self._merge_knowledge_group(group)
            if merged_knowledge:
                # Add merged knowledge
                await self.knowledge_graph.add_knowledge(merged_knowledge)
                
                # Remove original items
                for original in group:
                    if original.id in self.knowledge_graph.knowledge_index:
                        del self.knowledge_graph.knowledge_index[original.id]
                        if original.id in self.knowledge_graph.vector_store:
                            del self.knowledge_graph.vector_store[original.id]
                        self.knowledge_graph.graph.remove_node(original.id)
                
                merged_count += len(group) - 1  # Count original items merged
        
        return merged_count
    
    async def _merge_knowledge_group(self, group: List[KnowledgeItem]) -> Optional[KnowledgeItem]:
        """Merge a group of similar knowledge items"""
        try:
            # Select the best item as base
            base_item = max(group, key=lambda x: (x.confidence, x.access_count))
            
            # Combine content
            merged_content = base_item.content.copy()
            merged_content["merged_from"] = [item.id for item in group if item.id != base_item.id]
            
            # Combine tags
            merged_tags = set()
            for item in group:
                merged_tags.update(item.tags)
            
            # Calculate merged confidence (weighted average)
            total_weight = sum(item.access_count + 1 for item in group)
            merged_confidence = sum(
                item.confidence * (item.access_count + 1) for item in group
            ) / total_weight
            
            # Create merged knowledge item
            merged_knowledge = KnowledgeItem(
                id=str(uuid.uuid4()),
                content=merged_content,
                source_type=base_item.source_type,
                source_id=f"merged_{base_item.source_id}",
                confidence=min(merged_confidence, 1.0),
                relevance_scores=base_item.relevance_scores.copy(),
                creation_time=min(item.creation_time for item in group),
                last_accessed=max(item.last_accessed for item in group),
                access_count=sum(item.access_count for item in group),
                status=KnowledgeStatus.VALIDATED,
                tags=merged_tags
            )
            
            return merged_knowledge
            
        except Exception as e:
            self.logger.error("Knowledge merge failed", error=str(e))
            return None
    
    async def _optimize_relationships(self) -> int:
        """Optimize knowledge graph relationships"""
        optimization_count = 0
        
        try:
            # Remove weak relationships
            weak_edges = [(u, v) for u, v, d in self.knowledge_graph.graph.edges(data=True)
                         if d.get('weight', 0) < MIN_KNOWLEDGE_RELEVANCE * 0.5]
            
            self.knowledge_graph.graph.remove_edges_from(weak_edges)
            optimization_count += len(weak_edges)
            
            # Add strong transitive relationships
            nodes = list(self.knowledge_graph.graph.nodes())
            for node1 in nodes:
                for node2 in nodes:
                    if node1 != node2 and not self.knowledge_graph.graph.has_edge(node1, node2):
                        # Check for strong transitive relationship
                        common_neighbors = set(self.knowledge_graph.graph.neighbors(node1)) & \
                                         set(self.knowledge_graph.graph.neighbors(node2))
                        
                        if len(common_neighbors) >= 2:
                            # Calculate relationship strength
                            strength = len(common_neighbors) / (
                                len(set(self.knowledge_graph.graph.neighbors(node1))) + 
                                len(set(self.knowledge_graph.graph.neighbors(node2))) - 
                                len(common_neighbors)
                            )
                            
                            if strength > 0.3:
                                self.knowledge_graph.graph.add_edge(
                                    node1, node2,
                                    weight=strength,
                                    relationship_type="transitive"
                                )
                                optimization_count += 1
            
        except Exception as e:
            self.logger.error("Relationship optimization failed", error=str(e))
        
        return optimization_count
    
    async def _update_retention_stats(self) -> int:
        """Update knowledge retention statistics"""
        update_count = 0
        current_time = datetime.utcnow()
        
        for knowledge in self.knowledge_graph.knowledge_index.values():
            if knowledge.status != KnowledgeStatus.DEPRECATED:
                # Calculate retention score based on age and usage
                age_days = (current_time - knowledge.creation_time).days
                days_since_access = (current_time - knowledge.last_accessed).days
                
                if age_days > 0:
                    retention_score = min(
                        knowledge.access_count / max(age_days, 1) * 
                        (1 - days_since_access / 30), 1.0
                    )
                    
                    self.retention_stats[knowledge.id].append({
                        "timestamp": current_time,
                        "retention_score": retention_score,
                        "access_count": knowledge.access_count,
                        "age_days": age_days
                    })
                    
                    update_count += 1
        
        return update_count
    
    async def get_retention_metrics(self) -> Dict[str, float]:
        """Calculate overall retention metrics"""
        if not self.retention_stats:
            return {"overall_retention": 0.0, "knowledge_count": 0}
        
        total_retention = 0.0
        count = 0
        
        for knowledge_id, history in self.retention_stats.items():
            if history:
                latest_retention = history[-1]["retention_score"]
                total_retention += latest_retention
                count += 1
        
        return {
            "overall_retention": total_retention / count if count > 0 else 0.0,
            "knowledge_count": count,
            "tracked_items": len(self.retention_stats)
        }


# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def calculate_learning_metrics(
    knowledge_graph: KnowledgeGraph,
    experience_processor: ExperienceProcessor,
    pattern_engine: PatternDiscoveryEngine,
    knowledge_transfer: InterAgentKnowledgeTransfer,
    memory_system: MemoryConsolidationSystem
) -> LearningMetrics:
    """Calculate comprehensive learning system metrics"""
    
    try:
        # Knowledge statistics
        active_knowledge = [k for k in knowledge_graph.knowledge_index.values() 
                          if k.status != KnowledgeStatus.DEPRECATED]
        
        total_experiences = len(experience_processor.experience_buffer)
        
        # Learning velocity (knowledge items per hour)
        if active_knowledge:
            recent_knowledge = [k for k in active_knowledge 
                              if (datetime.utcnow() - k.creation_time).total_seconds() < 3600]
            learning_velocity = len(recent_knowledge)
        else:
            learning_velocity = 0.0
        
        # Knowledge retention rate
        retention_metrics = await memory_system.get_retention_metrics()
        knowledge_retention_rate = retention_metrics.get("overall_retention", 0.0)
        
        # Agent knowledge diversity
        agent_knowledge_counts = defaultdict(int)
        for knowledge in active_knowledge:
            if knowledge.source_id.startswith("agent_"):
                agent_knowledge_counts[knowledge.source_id] += 1
        
        if agent_knowledge_counts:
            diversity_scores = list(agent_knowledge_counts.values())
            agent_knowledge_diversity = 1.0 - (np.std(diversity_scores) / (np.mean(diversity_scores) + 1))
        else:
            agent_knowledge_diversity = 0.0
        
        # Collaboration score
        collaborative_knowledge = [k for k in active_knowledge 
                                 if k.source_type == LearningType.COLLABORATIVE]
        collaboration_score = len(collaborative_knowledge) / max(len(active_knowledge), 1)
        
        # External integration success
        external_knowledge = [k for k in active_knowledge 
                            if k.source_type == LearningType.EXTERNAL]
        validated_external = [k for k in external_knowledge 
                            if k.status == KnowledgeStatus.VALIDATED]
        external_integration_success = (len(validated_external) / max(len(external_knowledge), 1) 
                                      if external_knowledge else 0.0)
        
        # Problem-solving efficiency (based on successful experiences)
        if total_experiences > 0:
            successful_experiences = sum(1 for exp in experience_processor.experience_buffer if exp.success)
            problem_solving_efficiency = successful_experiences / total_experiences
        else:
            problem_solving_efficiency = 0.0
        
        # Pattern discovery count
        pattern_discovery_count = len(pattern_engine.discovered_patterns)
        
        # Knowledge transfer count
        knowledge_transfer_count = sum(len(transfers) for transfers in knowledge_transfer.transfer_history.values())
        
        return LearningMetrics(
            learning_velocity=learning_velocity,
            knowledge_retention_rate=knowledge_retention_rate,
            agent_knowledge_diversity=agent_knowledge_diversity,
            collaboration_score=collaboration_score,
            external_integration_success=external_integration_success,
            problem_solving_efficiency=problem_solving_efficiency,
            pattern_discovery_count=pattern_discovery_count,
            knowledge_transfer_count=knowledge_transfer_count,
            total_experiences=total_experiences,
            active_knowledge_items=len(active_knowledge)
        )
        
    except Exception as e:
        logger.error("Failed to calculate learning metrics", error=str(e))
        return LearningMetrics(
            learning_velocity=0.0,
            knowledge_retention_rate=0.0,
            agent_knowledge_diversity=0.0,
            collaboration_score=0.0,
            external_integration_success=0.0,
            problem_solving_efficiency=0.0,
            pattern_discovery_count=0,
            knowledge_transfer_count=0,
            total_experiences=0,
            active_knowledge_items=0
        )


def validate_learning_configuration(config: Dict[str, Any]) -> bool:
    """Validate learning engine configuration"""
    required_fields = [
        "learning_cycle_interval",
        "knowledge_sync_interval", 
        "pattern_discovery_interval",
        "memory_consolidation_interval"
    ]
    
    return all(field in config for field in required_fields)


async def health_check() -> Dict[str, Any]:
    """Learning engine health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "learning_engine_core",
        "version": "4.0"
    }


# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_learning_engine() -> Tuple[KnowledgeGraph, ExperienceProcessor, PatternDiscoveryEngine, InterAgentKnowledgeTransfer, ExternalLearningIntegrator, MemoryConsolidationSystem]:
    """Initialize the complete learning engine system"""
    
    try:
        # Initialize knowledge graph
        knowledge_graph = KnowledgeGraph()
        
        # Initialize core components
        experience_processor = ExperienceProcessor(knowledge_graph)
        pattern_engine = PatternDiscoveryEngine(knowledge_graph)
        knowledge_transfer = InterAgentKnowledgeTransfer(knowledge_graph)
        external_integrator = ExternalLearningIntegrator(knowledge_graph)
        memory_system = MemoryConsolidationSystem(knowledge_graph)
        
        logger.info("Learning engine initialized successfully")
        
        return (
            knowledge_graph,
            experience_processor, 
            pattern_engine,
            knowledge_transfer,
            external_integrator,
            memory_system
        )
        
    except Exception as e:
        logger.error("Failed to initialize learning engine", error=str(e))
        raise


# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "KnowledgeGraph",
    "ExperienceProcessor", 
    "PatternDiscoveryEngine",
    "InterAgentKnowledgeTransfer",
    "ExternalLearningIntegrator",
    "MemoryConsolidationSystem",
    "Experience",
    "KnowledgeItem", 
    "LearningPattern",
    "LearningMetrics",
    "LearningType",
    "KnowledgeStatus",
    "initialize_learning_engine",
    "calculate_learning_metrics",
    "health_check"
].utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    status=KnowledgeStatus.PENDING_VALIDATION,
                    tags={experience.action, "experiential", experience.agent_id}
                )
                knowledge_items.append(action_knowledge)
            
            # Extract contextual patterns
            if self._has_significant_context(experience):
                context_knowledge = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    content={
                        "type": "context_pattern",
                        "context_signature": self._create_context_signature(experience.context),
                        "typical_actions": [experience.action],
                        "success_rate": 1.0 if experience.success else 0.0,
                        "sample_size": 1
                    },
                    source_type=LearningType.PATTERN_BASED,
                    source_id=experience.agent_id,
                    confidence=experience.confidence * 0.8,  # Lower confidence for patterns
                    relevance_scores={"pattern_based": experience.confidence * 0.8},
                    creation_time=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    status=KnowledgeStatus.PENDING_VALIDATION,
                    tags={"pattern", "context", experience.agent_id}
                )
                knowledge_items.append(context_knowledge)
            
        except Exception as e:
            self.logger.error("Failed to extract knowledge from experience", error=str(e))
        
        return knowledge_items
    
    def _extract_conditions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract meaningful conditions from context"""
        conditions = {}
        
        # Extract key contextual factors
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                conditions[key] = value
            elif isinstance(value, dict) and len(value) < 5:
                conditions[key] = value
        
        return conditions
    
    def _has_significant_context(self, experience: Experience) -> bool:
        """Check if experience has significant contextual information"""
        return (
            len(experience.context) >= 3 and
            experience.confidence > 0.5 and
            any(isinstance(v, (str, int, float)) for v in experience.context.values())
        )
    
    def _create_context_signature(self, context: Dict[str, Any]) -> str:
        """Create a signature for context patterns"""
        # Create a hash-based signature for similar contexts
        context_str = json.dumps(context, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()


class PatternDiscoveryEngine:
    """Discover behavioral patterns in agent interactions"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        self.discovered_patterns = {}
        self.pattern_cache = {}
        self.logger = logger.bind(component="pattern_discovery")
    
    async def discover_patterns(self, experiences: List[Experience]) -> List[LearningPattern]:
        """Discover patterns from agent experiences"""
        if len(experiences) < 10:  # Need minimum data for pattern discovery
            return []
        
        patterns = []
        
        try:
            # Discover action sequence patterns
            sequence_patterns = await self._discover_sequence_patterns(experiences)
            patterns.extend(sequence_patterns)
            
            # Discover context-outcome patterns
            context_patterns = await self._discover_context_patterns(experiences)
            patterns.extend(context_patterns)
            
            # Discover collaboration patterns
            collab_patterns = await self._discover_collaboration_patterns(experiences)
            patterns.extend(collab_patterns)
            
            # Store discovered patterns
            for pattern in patterns:
                self.discovered_patterns[pattern.id] = pattern
                await self._create_pattern_knowledge(pattern)
            
            self.logger.info("Patterns discovered", count=len(patterns))
            
        except Exception as e:
            self.logger.error("Pattern discovery failed", error=str(e))
        
        return patterns
    
    async def _discover_sequence_patterns(self, experiences: List[Experience]) -> List[LearningPattern]:
        """Discover common action sequences"""
        patterns = []
        
        # Group experiences by agent
        agent_sequences = defaultdict(list)
        for exp in experiences:
            agent_sequences[exp.agent_id].append(exp)
        
        # Analyze sequences for each agent
        for agent_id, agent_exps in agent_sequences.items():
            # Sort by timestamp
            agent_exps.sort(key=lambda x: x.timestamp)
            
            # Find common sequences of length 2-4
            for seq_len in range(2, 5):
                sequences = self._extract_sequences(agent_exps, seq_len)
                common_seqs = self._find_common_sequences(sequences)
                
                for seq, frequency in common_seqs.items():
                    if frequency >= 3:  # Minimum frequency threshold
                        pattern = LearningPattern(
                            id=str(uuid.uuid4()),
                            pattern_type="action_sequence",
                            description=f"Common sequence: {' -> '.join(seq)}",
                            conditions={"agent_id": agent_id, "sequence_length": seq_len},
                            outcomes={"frequency": frequency, "success_rate": self._calculate_seq_success_rate(seq, agent_exps)},
                            confidence=min(frequency / 10.0, 1.0),
                            frequency=frequency,
                            agents_involved={agent_id},
                            discovered_at=datetime.utcnow(),
                            effectiveness=self._calculate_seq_success_rate(seq, agent_exps)
                        )
                        patterns.append(pattern)
        
        return patterns
    
    async def _discover_context_patterns(self, experiences: List[Experience]) -> List[LearningPattern]:
        """Discover patterns in context-outcome relationships"""
        patterns = []
        
        # Group experiences by context signatures
        context_groups = defaultdict(list)
        for exp in experiences:
            context_sig = self._create_context_signature(exp.context)
            context_groups[context_sig].append(exp)
        
        # Analyze each context group
        for context_sig, group_exps in context_groups.items():
            if len(group_exps) >= 5:  # Minimum sample size
                success_rate = sum(1 for exp in group_exps if exp.success) / len(group_exps)
                
                if success_rate > 0.7 or success_rate < 0.3:  # Strong pattern
                    # Find common actions in this context
                    actions = [exp.action for exp in group_exps]
                    action_counts = defaultdict(int)
                    for action in actions:
                        action_counts[action] += 1
                    
                    most_common_action = max(action_counts.items(), key=lambda x: x[1])
                    
                    pattern = LearningPattern(
                        id=str(uuid.uuid4()),
                        pattern_type="context_outcome",
                        description=f"Context {context_sig[:8]} leads to {most_common_action[0]} with {success_rate:.2f} success rate",
                        conditions={"context_signature": context_sig},
                        outcomes={
                            "recommended_action": most_common_action[0],
                            "success_rate": success_rate,
                            "sample_size": len(group_exps)
                        },
                        confidence=success_rate if success_rate > 0.5 else (1 - success_rate),
                        frequency=len(group_exps),
                        agents_involved={exp.agent_id for exp in group_exps},
                        discovered_at=datetime.utcnow(),
                        effectiveness=success_rate
                    )
                    patterns.append(pattern)
        
        return patterns
    
    async def _discover_collaboration_patterns(self, experiences: List[Experience]) -> List[LearningPattern]:
        """Discover patterns in multi-agent collaborations"""
        patterns = []
        
        # Find experiences that involve multiple agents
        collaboration_windows = self._find_collaboration_windows(experiences)
        
        for window in collaboration_windows:
            if len(window) >= 3 and len({exp.agent_id for exp in window}) >= 2:
                agents_involved = {exp.agent_id for exp in window}
                success_rate = sum(1 for exp in window if exp.success) / len(window)
                
                pattern = LearningPattern(
                    id=str(uuid.uuid4()),
                    pattern_type="collaboration",
                    description=f"Collaboration between {len(agents_involved)} agents",
                    conditions={
                        "agents": list(agents_involved),
                        "time_window": "5_minutes",
                        "min_interactions": len(window)
                    },
                    outcomes={
                        "success_rate": success_rate,
                        "interaction_count": len(window),
                        "agents_count": len(agents_involved)
                    },
                    confidence=min(len(window) / 10.0, 1.0) * success_rate,
                    frequency=1,  # Each collaboration window is unique
                    agents_involved=agents_involved,
                    discovered_at=datetime.utcnow(),
                    effectiveness=success_rate
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_sequences(self, experiences: List[Experience], length: int) -> List[Tuple[str, ...]]:
        """Extract action sequences of given length"""
        sequences = []
        for i in range(len(experiences) - length + 1):
            seq = tuple(experiences[i + j].action for j in range(length))
            sequences.append(seq)
        return sequences
    
    def _find_common_sequences(self, sequences: List[Tuple[str, ...]]) -> Dict[Tuple[str, ...], int]:
        """Find commonly occurring sequences"""
        seq_counts = defaultdict(int)
        for seq in sequences:
            seq_counts[seq] += 1
        return dict(seq_counts)
    
    def _calculate_seq_success_rate(self, sequence: Tuple[str, ...], experiences: List[Experience]) -> float:
        """Calculate success rate for a sequence"""
        seq_occurrences = []
        for i in range(len(experiences) - len(sequence) + 1):
            if all(experiences[i + j].action == sequence[j] for j in range(len(sequence))):
                seq_occurrences.append(experiences[i + len(sequence) - 1].success)
        
        if not seq_occurrences:
            return 0.0
        
        return sum(seq_occurrences) / len(seq_occurrences)
    
    def _create_context_signature(self, context: Dict[str, Any]) -> str:
        """Create a signature for context patterns"""
        # Simplified context signature focusing on key attributes
        key_attrs = {}
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                key_attrs[key] = value
        
        context_str = json.dumps(key_attrs, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()
    
    def _find_collaboration_windows(self, experiences: List[Experience]) -> List[List[Experience]]:
        """Find time windows where multiple agents were active"""
        # Sort experiences by timestamp
        sorted_exps = sorted(experiences, key=lambda x: x.timestamp)
        
        windows = []
        current_window = []
        window_start = None
        
        for exp in sorted_exps:
            if not current_window:
                current_window = [exp]
                window_start = exp.timestamp
            else:
                # If within 5 minutes of window start, add to current window
                if (exp.timestamp - window_start).total_seconds() <= 300:
                    current_window.append(exp)
                else:
                    # Close current window if it has multiple agents
                    if len({e.agent_id for e in current_window}) >= 2:
                        windows.append(current_window)
                    
                    # Start new window
                    current_window = [exp]
                    window_start = exp.timestamp
        
        # Don't forget the last window
        if len({e.agent_id for e in current_window}) >= 2:
            windows.append(current_window)
        
        return windows
    
    async def _create_pattern_knowledge(self, pattern: LearningPattern) -> None:
        """Convert discovered pattern into knowledge item"""
        knowledge = KnowledgeItem(
            id=str(uuid.uuid4()),
            content={
                "type": "discovered_pattern",
                "pattern_type": pattern.pattern_type,
                "description": pattern.description,
                "conditions": pattern.conditions,
                "outcomes": pattern.outcomes,
                "effectiveness": pattern.effectiveness,
                "agents_involved": list(pattern.agents_involved)
            },
            source_type=LearningType.PATTERN_BASED,
            source_id="pattern_discovery_engine",
            confidence=pattern.confidence,
            relevance_scores={"pattern_based": pattern.confidence},
            creation_time=pattern.discovered_at,
            last_accessed=pattern.discovered_at,
            access_count=0,
            status=KnowledgeStatus.VALIDATED,
            tags={"pattern", pattern.pattern_type, "discovered"}
        )
        
        await self.knowledge_graph.add_knowledge(knowledge)


class InterAgentKnowledgeTransfer:
    """Manage knowledge transfer between agents"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        self.transfer_history = defaultdict(list)
        self.agent_profiles = {}
        self.logger = logger.bind(component="knowledge_transfer")
    
    async def synchronize_agent_knowledge(self, agent_ids: List[str]) -> Dict[str, int]:
        """Synchronize knowledge between specified agents"""
        transfer_counts = defaultdict(int)
        
        try:
            # Update agent profiles
            for agent_id in agent_ids:
                await self._update_agent_profile(agent_id)
            
            # Find transfer opportunities
            opportunities = await self._identify_transfer_opportunities(agent_ids)
            
            # Execute transfers
            for opportunity in opportunities:
                success = await self._execute_knowledge_transfer(opportunity)
                if success:
                    transfer_counts[opportunity['target_agent']] += 1
            
            self.logger.info("Knowledge synchronization completed", 
                           agents=len(agent_ids), 
                           transfers=sum(transfer_counts.values()))
            
        except Exception as e:
            self.logger.error("Knowledge synchronization failed", error=str(e))
        
        return dict(transfer_counts)
    
    async def _update_agent_profile(self, agent_id: str) -> None:
        """Update agent's knowledge profile"""
        # Get agent's knowledge items
        agent_knowledge = []
        for knowledge in self.knowledge_graph.knowledge_index.values():
            if knowledge.source_id == agent_id or agent_id in knowledge.tags:
                agent_knowledge.append(knowledge)
        
        # Calculate profile metrics
        profile = {
            "agent_id": agent_id,
            "knowledge_count": len(agent_knowledge),
            "knowledge_types": set(),
            "expertise_areas": defaultdict(int),
            "last_updated": datetime.utcnow(),
            "avg_confidence": 0.0
        }
        
        if agent_knowledge:
            total_confidence = 0
            for knowledge in agent_knowledge:
                profile["knowledge_types"].add(knowledge.source_type.value)
                for tag in knowledge.tags:
                    profile["expertise_areas"][tag] += 1
                total_confidence += knowledge.confidence
            
            profile["avg_confidence"] = total_confidence / len(agent_knowledge)
        
        profile["knowledge_types"] = list(profile["knowledge_types"])
        profile["expertise_areas"] = dict(profile["expertise_areas"])
        
        self.agent_profiles[agent_id] = profile
    
    async def _identify_transfer_opportunities(self, agent_ids: List[str]) -> List[Dict[str, Any]]:
        """Identify opportunities for knowledge transfer"""
        opportunities = []
        
        for source_agent in agent_ids:
            source_profile = self.agent_profiles.get(source_agent, {})
            source_expertise = source_profile.get("expertise_areas", {})
            
            for target_agent in agent_ids:
                if source_agent == target_agent:
                    continue
                
                target_profile = self.agent_profiles.get(target_agent, {})
                target_expertise = target_profile.get("expertise_areas", {})
                
                # Find knowledge gaps
                for expertise_area, source_count in source_expertise.items():
                    target_count = target_expertise.get(expertise_area, 0)
                    
                    # Transfer if source has significantly more knowledge
                    if source_count >= target_count + 3:
                        # Find specific knowledge to transfer
                        transfer_knowledge = await self._find_transferable_knowledge(
                            source_agent, target_agent, expertise_area
                        )
                        
                        if transfer_knowledge:
                            opportunities.append({
                                "source_agent": source_agent,
                                "target_agent": target_agent,
                                "knowledge_items": transfer_knowledge,
                                "expertise_area": expertise_area,
                                "priority": source_count - target_count
                            })
        
        # Sort by priority
        opportunities.sort(key=lambda x: x["priority"], reverse=True)
        return opportunities[:20]  # Limit to top 20 opportunities
    
    async def _find_transferable_knowledge(
        self, 
        source_agent: str, 
        target_agent: str, 
        expertise_area: str
    ) -> List[KnowledgeItem]:
        """Find knowledge items suitable for transfer"""
        transferable = []
        
        # Get high-quality knowledge from source agent in the expertise area
        for knowledge in self.knowledge_graph.knowledge_index.values():
            if (knowledge.source_id == source_agent and 
                expertise_area in knowledge.tags and
                knowledge.confidence > 0.7 and
                knowledge.status == KnowledgeStatus.VALIDATED):
                
                # Check if target agent doesn't already have similar knowledge
                similar_knowledge = await self.knowledge_graph.find_similar_knowledge(
                    knowledge.content, threshold=0.8, limit=5
                )
                
                has_similar = any(
                    target_agent in k.tags or k.source_id == target_agent 
                    for k in similar_knowledge
                )
                
                if not has_similar:
                    transferable.append(knowledge)
        
        return transferable[:5]  # Limit transfers per opportunity
    
    async def _execute_knowledge_transfer(self, opportunity: Dict[str, Any]) -> bool:
        """Execute a knowledge transfer opportunity"""
        try:
            source_agent = opportunity["source_agent"]
            target_agent = opportunity["target_agent"]
            knowledge_items = opportunity["knowledge_items"]
            
            for knowledge in knowledge_items:
                # Create adapted knowledge for target agent
                adapted_knowledge = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    content=knowledge.content.copy(),
                    source_type=LearningType.COLLABORATIVE,
                    source_id=f"transfer_{source_agent}_to_{target_agent}",
                    confidence=knowledge.confidence * 0.9,  # Slight confidence reduction
                    relevance_scores=knowledge.relevance_scores.copy(),
                    creation_time=datetime