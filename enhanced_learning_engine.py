"""
YMERA Enterprise Multi-Agent Learning Engine v4.0
Production-Ready AI-Native Learning System with Advanced Capabilities
"""

import asyncio
import logging
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple, Set, Union
from dataclasses import dataclass, asdict, field
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue, PriorityQueue, Empty
import pickle
import hashlib
import numpy as np
from enum import Enum, IntEnum
import traceback
from pathlib import Path
import weakref
from collections import defaultdict, deque
import contextlib
import functools
import gc
from typing_extensions import Annotated
import multiprocessing
import psutil

# External libraries
import openai
import anthropic
import google.generativeai as genai
from groq import Groq
from pinecone import Pinecone, ServerlessSpec
import requests
from github import Github
import tiktoken
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

class AgentType(Enum):
    REASONING = "reasoning"
    CREATIVE = "creative" 
    ANALYTICAL = "analytical"
    CODING = "coding"
    RESEARCH = "research"
    SYNTHESIS = "synthesis"
    VALIDATION = "validation"
    OPTIMIZATION = "optimization"

class LearningMode(Enum):
    SUPERVISED = "supervised"
    REINFORCEMENT = "reinforcement"
    SELF_SUPERVISED = "self_supervised"
    META_LEARNING = "meta_learning"
    TRANSFER_LEARNING = "transfer_learning"
    CONTINUAL_LEARNING = "continual_learning"

class TaskPriority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5

class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    LEARNING = "learning"
    COMMUNICATING = "communicating"
    ERROR = "error"
    SHUTDOWN = "shutdown"

class MemoryType(Enum):
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for agents and tasks"""
    agent_id: str
    task_count: int = 0
    success_rate: float = 0.0
    avg_execution_time: float = 0.0
    avg_quality_score: float = 0.0
    learning_efficiency: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    error_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class Experience:
    """Enhanced learning experience with rich context and metadata"""
    experience_id: str
    agent_id: str
    task_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    feedback_score: float
    execution_time: float
    timestamp: datetime
    context: Dict[str, Any]
    success: bool
    learned_patterns: List[str]
    confidence_score: float = 0.0
    complexity_score: float = 0.0
    novelty_score: float = 0.0
    collaborative_agents: List[str] = field(default_factory=list)
    memory_type: MemoryType = MemoryType.EPISODIC
    retrieval_count: int = 0
    decay_factor: float = 1.0

@dataclass
class Task:
    """Enhanced task representation with advanced scheduling and dependencies"""
    task_id: str
    task_type: str
    priority: TaskPriority
    data: Dict[str, Any]
    created_at: datetime
    deadline: Optional[datetime] = None
    assigned_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    progress: float = 0.0
    estimated_duration: Optional[float] = None
    actual_duration: Optional[float] = None
    quality_requirements: Dict[str, float] = field(default_factory=dict)
    resource_requirements: Dict[str, int] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)

class EnhancedKnowledgeGraph:
    """Production-ready knowledge graph with advanced pattern recognition"""
    
    def __init__(self, redis_client: Optional[aioredis.Redis] = None, 
                 embedding_model: Optional[SentenceTransformer] = None):
        self.nodes = {}
        self.edges = {}
        self.patterns = {}
        self.embeddings = {}
        self.concept_clusters = {}
        self.access_patterns = defaultdict(list)
        self.temporal_patterns = {}
        
        # Thread-safe operations
        self.lock = threading.RLock()
        
        # External dependencies
        self.redis_client = redis_client
        self.embedding_model = embedding_model or SentenceTransformer('all-MiniLM-L6-v2')
        
        # Performance optimization
        self.cache_size = 10000
        self.embedding_cache = {}
        self.similarity_threshold = 0.7
        
        # Analytics
        self.query_stats = defaultdict(int)
        self.performance_metrics = {}
        
    async def add_knowledge(self, concept: str, properties: Dict[str, Any], 
                           embedding: Optional[List[float]] = None,
                           persist: bool = True) -> str:
        """Add knowledge node with advanced caching and persistence"""
        try:
            with self.lock:
                node_id = hashlib.sha256(concept.encode()).hexdigest()[:16]
                
                # Generate embedding if not provided
                if embedding is None and concept:
                    if concept in self.embedding_cache:
                        embedding = self.embedding_cache[concept]
                    else:
                        embedding = self.embedding_model.encode([concept])[0].tolist()
                        if len(self.embedding_cache) < self.cache_size:
                            self.embedding_cache[concept] = embedding
                
                node_data = {
                    'concept': concept,
                    'properties': properties,
                    'created_at': datetime.now().isoformat(),
                    'access_count': 0,
                    'last_accessed': datetime.now().isoformat(),
                    'importance_score': self._calculate_importance(properties),
                    'cluster_id': None
                }
                
                self.nodes[node_id] = node_data
                if embedding:
                    self.embeddings[node_id] = embedding
                
                # Persist to Redis if available
                if persist and self.redis_client:
                    await self._persist_node(node_id, node_data, embedding)
                
                # Update clusters
                self._update_clusters(node_id, embedding)
                
                logger.info("Added knowledge node", node_id=node_id, concept=concept)
                return node_id
                
        except Exception as e:
            logger.error("Failed to add knowledge", concept=concept, error=str(e))
            raise

    async def add_relationship(self, concept1: str, concept2: str, 
                             relationship_type: str, strength: float,
                             bidirectional: bool = True) -> str:
        """Add sophisticated relationship with temporal and strength tracking"""
        try:
            with self.lock:
                id1 = hashlib.sha256(concept1.encode()).hexdigest()[:16]
                id2 = hashlib.sha256(concept2.encode()).hexdigest()[:16]
                edge_id = f"{id1}-{id2}-{hashlib.md5(relationship_type.encode()).hexdigest()[:8]}"
                
                edge_data = {
                    'from': id1,
                    'to': id2,
                    'type': relationship_type,
                    'strength': max(0.0, min(1.0, strength)),  # Normalize strength
                    'created_at': datetime.now().isoformat(),
                    'access_count': 0,
                    'decay_rate': 0.01,  # Relationship decay over time
                    'reinforcement_count': 1,
                    'bidirectional': bidirectional
                }
                
                self.edges[edge_id] = edge_data
                
                # Add reverse relationship if bidirectional
                if bidirectional:
                    reverse_edge_id = f"{id2}-{id1}-{hashlib.md5(relationship_type.encode()).hexdigest()[:8]}"
                    reverse_edge_data = edge_data.copy()
                    reverse_edge_data.update({'from': id2, 'to': id1})
                    self.edges[reverse_edge_id] = reverse_edge_data
                
                # Persist to Redis
                if self.redis_client:
                    await self._persist_edge(edge_id, edge_data)
                
                logger.info("Added relationship", edge_id=edge_id, type=relationship_type)
                return edge_id
                
        except Exception as e:
            logger.error("Failed to add relationship", concept1=concept1, 
                        concept2=concept2, error=str(e))
            raise

    async def find_related_concepts(self, concept: str, max_distance: int = 3, 
                                  similarity_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Advanced concept discovery with similarity and graph traversal"""
        try:
            with self.lock:
                concept_id = hashlib.sha256(concept.encode()).hexdigest()[:16]
                
                if concept_id not in self.nodes:
                    # Try semantic similarity search
                    return await self._semantic_similarity_search(concept, similarity_threshold)
                
                # Update access statistics
                self.nodes[concept_id]['access_count'] += 1
                self.nodes[concept_id]['last_accessed'] = datetime.now().isoformat()
                
                # Graph traversal with BFS
                visited = set()
                queue = deque([(concept_id, 0, 1.0)])  # (node_id, distance, relevance)
                related = []
                
                while queue and len(related) < 50:  # Limit results
                    current_id, distance, relevance = queue.popleft()
                    
                    if current_id in visited or distance > max_distance:
                        continue
                    
                    visited.add(current_id)
                    
                    if current_id != concept_id and current_id in self.nodes:
                        node_data = self.nodes[current_id].copy()
                        node_data.update({
                            'node_id': current_id,
                            'distance': distance,
                            'relevance_score': relevance
                        })
                        related.append(node_data)
                    
                    # Find connected nodes
                    for edge_id, edge_data in self.edges.items():
                        if edge_data['from'] == current_id:
                            next_id = edge_data['to']
                            if next_id not in visited:
                                # Calculate relevance based on edge strength and distance
                                next_relevance = relevance * edge_data['strength'] * (0.8 ** distance)
                                queue.append((next_id, distance + 1, next_relevance))
                
                # Sort by relevance score
                related.sort(key=lambda x: x['relevance_score'], reverse=True)
                
                logger.info("Found related concepts", concept=concept, count=len(related))
                return related[:20]  # Return top 20 results
                
        except Exception as e:
            logger.error("Failed to find related concepts", concept=concept, error=str(e))
            return []

    async def _semantic_similarity_search(self, concept: str, 
                                        threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Semantic similarity search using embeddings"""
        try:
            if not self.embedding_model:
                return []
            
            # Get query embedding
            query_embedding = self.embedding_model.encode([concept])[0]
            
            # Compare with stored embeddings
            similarities = []
            for node_id, embedding in self.embeddings.items():
                if node_id in self.nodes:
                    similarity = cosine_similarity([query_embedding], [embedding])[0][0]
                    if similarity >= threshold:
                        node_data = self.nodes[node_id].copy()
                        node_data.update({
                            'node_id': node_id,
                            'distance': 1,
                            'relevance_score': similarity
                        })
                        similarities.append(node_data)
            
            # Sort by similarity
            similarities.sort(key=lambda x: x['relevance_score'], reverse=True)
            return similarities[:10]
            
        except Exception as e:
            logger.error("Semantic similarity search failed", concept=concept, error=str(e))
            return []

    def _calculate_importance(self, properties: Dict[str, Any]) -> float:
        """Calculate importance score based on node properties"""
        score = 0.0
        
        # Factor in various importance indicators
        if 'frequency' in properties:
            score += min(properties['frequency'] / 100.0, 0.3)
        
        if 'quality_score' in properties:
            score += properties['quality_score'] * 0.2
        
        if 'recency' in properties:
            # More recent knowledge gets higher importance
            days_old = (datetime.now() - datetime.fromisoformat(properties['recency'])).days
            score += max(0, (30 - days_old) / 30.0) * 0.2
        
        if 'connections' in properties:
            # Well-connected concepts are more important
            score += min(properties['connections'] / 10.0, 0.3)
        
        return min(score, 1.0)

    def _update_clusters(self, node_id: str, embedding: Optional[List[float]]):
        """Update concept clusters for improved organization"""
        if not embedding or not self.embeddings:
            return
        
        try:
            # Simple clustering based on similarity
            best_cluster = None
            best_similarity = 0.0
            
            for cluster_id, cluster_nodes in self.concept_clusters.items():
                if cluster_nodes:
                    # Get centroid of cluster
                    cluster_embeddings = [self.embeddings[nid] for nid in cluster_nodes 
                                        if nid in self.embeddings]
                    if cluster_embeddings:
                        centroid = np.mean(cluster_embeddings, axis=0)
                        similarity = cosine_similarity([embedding], [centroid])[0][0]
                        
                        if similarity > best_similarity and similarity > self.similarity_threshold:
                            best_cluster = cluster_id
                            best_similarity = similarity
            
            if best_cluster:
                self.concept_clusters[best_cluster].append(node_id)
                if node_id in self.nodes:
                    self.nodes[node_id]['cluster_id'] = best_cluster
            else:
                # Create new cluster
                new_cluster_id = f"cluster_{len(self.concept_clusters)}"
                self.concept_clusters[new_cluster_id] = [node_id]
                if node_id in self.nodes:
                    self.nodes[node_id]['cluster_id'] = new_cluster_id
                    
        except Exception as e:
            logger.error("Failed to update clusters", node_id=node_id, error=str(e))

    async def _persist_node(self, node_id: str, node_data: Dict[str, Any], 
                           embedding: Optional[List[float]]):
        """Persist node data to Redis"""
        try:
            if self.redis_client:
                # Store node data
                await self.redis_client.hset(
                    f"kg:node:{node_id}", 
                    mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                            for k, v in node_data.items()}
                )
                
                # Store embedding separately for efficiency
                if embedding:
                    await self.redis_client.set(
                        f"kg:embedding:{node_id}", 
                        pickle.dumps(embedding),
                        ex=86400  # Expire after 24 hours
                    )
        except Exception as e:
            logger.error("Failed to persist node", node_id=node_id, error=str(e))

    async def _persist_edge(self, edge_id: str, edge_data: Dict[str, Any]):
        """Persist edge data to Redis"""
        try:
            if self.redis_client:
                await self.redis_client.hset(
                    f"kg:edge:{edge_id}",
                    mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                            for k, v in edge_data.items()}
                )
        except Exception as e:
            logger.error("Failed to persist edge", edge_id=edge_id, error=str(e))

    async def get_analytics(self) -> Dict[str, Any]:
        """Get comprehensive knowledge graph analytics"""
        with self.lock:
            return {
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'total_clusters': len(self.concept_clusters),
                'avg_cluster_size': np.mean([len(nodes) for nodes in self.concept_clusters.values()]) if self.concept_clusters else 0,
                'cache_hit_rate': len(self.embedding_cache) / max(1, len(self.nodes)),
                'most_accessed_concepts': sorted(
                    [(nid, data['access_count']) for nid, data in self.nodes.items()],
                    key=lambda x: x[1], reverse=True
                )[:10],
                'query_stats': dict(self.query_stats),
                'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024
            }

class AdvancedMemorySystem:
    """Production-grade memory system with hierarchical storage and forgetting"""
    
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self.short_term_memory = deque(maxlen=1000)
        self.working_memory = {}
        self.long_term_memory = {}
        self.episodic_memory = defaultdict(list)
        self.semantic_memory = {}
        self.procedural_memory = {}
        
        # Memory management
        self.memory_lock = threading.RLock()
        self.decay_rates = {
            MemoryType.SHORT_TERM: 0.1,
            MemoryType.WORKING: 0.05,
            MemoryType.LONG_TERM: 0.001,
            MemoryType.EPISODIC: 0.02,
            MemoryType.SEMANTIC: 0.005,
            MemoryType.PROCEDURAL: 0.002
        }
        
        # Background maintenance
        self._maintenance_task = None
        self.start_maintenance()

    async def store_experience(self, experience: Experience) -> bool:
        """Store experience in appropriate memory systems"""
        try:
            with self.memory_lock:
                # Always store in episodic memory first
                self.episodic_memory[experience.agent_id].append(experience)
                
                # Store in short-term memory
                self.short_term_memory.append(experience)
                
                # Determine if experience should go to long-term memory
                if self._should_store_long_term(experience):
                    memory_key = f"{experience.agent_id}:{experience.task_type}:{experience.experience_id[:8]}"
                    self.long_term_memory[memory_key] = experience
                
                # Extract and store patterns in semantic memory
                for pattern in experience.learned_patterns:
                    pattern_key = hashlib.md5(pattern.encode()).hexdigest()[:16]
                    if pattern_key in self.semantic_memory:
                        self.semantic_memory[pattern_key]['frequency'] += 1
                        self.semantic_memory[pattern_key]['last_seen'] = datetime.now()
                    else:
                        self.semantic_memory[pattern_key] = {
                            'pattern': pattern,
                            'frequency': 1,
                            'first_seen': datetime.now(),
                            'last_seen': datetime.now(),
                            'associated_agents': {experience.agent_id},
                            'success_rate': 1.0 if experience.success else 0.0,
                            'applications': 1
                        }
                
                # Store procedural knowledge if it's a successful coding or execution task
                if experience.success and experience.task_type in ['coding', 'execution', 'optimization']:
                    await self._extract_procedural_knowledge(experience)
                
                # Persist to Redis
                if self.redis_client:
                    await self._persist_experience(experience)
                
                logger.info("Stored experience", 
                           agent_id=experience.agent_id,
                           task_type=experience.task_type,
                           success=experience.success)
                return True
                
        except Exception as e:
            logger.error("Failed to store experience", 
                        experience_id=experience.experience_id, 
                        error=str(e))
            return False

    async def retrieve_relevant_experiences(self, agent_id: str, task_type: str, 
                                          context: Dict[str, Any], 
                                          limit: int = 10) -> List[Experience]:
        """Retrieve contextually relevant experiences"""
        try:
            relevant_experiences = []
            
            with self.memory_lock:
                # Search episodic memory for agent
                agent_experiences = self.episodic_memory.get(agent_id, [])
                
                # Score experiences based on relevance
                scored_experiences = []
                for exp in agent_experiences:
                    score = self._calculate_relevance_score(exp, task_type, context)
                    if score > 0.3:  # Minimum relevance threshold
                        scored_experiences.append((exp, score))
                
                # Sort by relevance and recency
                scored_experiences.sort(key=lambda x: (x[1], x[0].timestamp), reverse=True)
                
                # Get top experiences
                relevant_experiences = [exp for exp, score in scored_experiences[:limit]]
                
                # Update retrieval statistics
                for exp in relevant_experiences:
                    exp.retrieval_count += 1
                
            logger.info("Retrieved relevant experiences", 
                       agent_id=agent_id, 
                       task_type=task_type,
                       count=len(relevant_experiences))
            
            return relevant_experiences
            
        except Exception as e:
            logger.error("Failed to retrieve experiences", 
                        agent_id=agent_id, 
                        task_type=task_type, 
                        error=str(e))
            return []

    def _should_store_long_term(self, experience: Experience) -> bool:
        """Determine if experience should be stored in long-term memory"""
        # High-quality successful experiences
        if experience.success and experience.feedback_score > 0.8:
            return True
        
        # Novel experiences (high novelty score)
        if experience.novelty_score > 0.7:
            return True
        
        # Complex problem-solving experiences
        if experience.complexity_score > 0.6 and experience.success:
            return True
        
        # Collaborative experiences with multiple agents
        if len(experience.collaborative_agents) > 1:
            return True
        
        # High-confidence learnings
        if experience.confidence_score > 0.9:
            return True
        
        return False

    def _calculate_relevance_score(self, experience: Experience, 
                                 task_type: str, context: Dict[str, Any]) -> float:
        """Calculate relevance score for experience retrieval"""
        score = 0.0
        
        # Task type similarity
        if experience.task_type == task_type:
            score += 0.3
        elif self._are_related_tasks(experience.task_type, task_type):
            score += 0.15
        
        # Context similarity (simplified)
        context_overlap = len(set(experience.context.keys()) & set(context.keys()))
        if context_overlap > 0:
            score += min(context_overlap * 0.1, 0.2)
        
        # Success bias - prefer successful experiences
        if experience.success:
            score += 0.2
        
        # Quality score
        score += experience.feedback_score * 0.2
        
        # Recency bonus (more recent experiences are more relevant)
        days_old = (datetime.now() - experience.timestamp).days
        recency_bonus = max(0, (30 - days_old) / 30.0) * 0.1
        score += recency_bonus
        
        # Confidence bonus
        score += experience.confidence_score * 0.1
        
        # Apply decay factor
        score *= experience.decay_factor
        
        return min(score, 1.0)

    def _are_related_tasks(self, task1: str, task2: str) -> bool:
        """Check if two task types are related"""
        related_groups = [
            {'coding', 'debugging', 'optimization', 'testing'},
            {'research', 'analysis', 'synthesis'},
            {'creative', 'writing', 'brainstorming'},
            {'reasoning', 'planning', 'decision_making'}
        ]
        
        for group in related_groups:
            if task1 in group and task2 in group:
                return True
        
        return False

    async def _extract_procedural_knowledge(self, experience: Experience):
        """Extract procedural knowledge from successful experiences"""
        try:
            if 'steps' in experience.output_data:
                steps = experience.output_data['steps']
                procedure_key = f"{experience.task_type}:{hashlib.md5(str(steps).encode()).hexdigest()[:16]}"
                
                if procedure_key in self.procedural_memory:
                    self.procedural_memory[procedure_key]['success_count'] += 1
                    self.procedural_memory[procedure_key]['total_attempts'] += 1
                else:
                    self.procedural_memory[procedure_key] = {
                        'task_type': experience.task_type,
                        'procedure': steps,
                        'success_count': 1,
                        'total_attempts': 1,
                        'created_at': datetime.now(),
                        'last_used': datetime.now(),
                        'average_execution_time': experience.execution_time,
                        'quality_scores': [experience.feedback_score]
                    }
                
        except Exception as e:
            logger.error("Failed to extract procedural knowledge", 
                        experience_id=experience.experience_id, 
                        error=str(e))

    async def _persist_experience(self, experience: Experience):
        """Persist experience to Redis"""
        try:
            if self.redis_client:
                experience_data = asdict(experience)
                # Convert datetime objects to ISO strings
                experience_data['timestamp'] = experience.timestamp.isoformat()
                
                await self.redis_client.setex(
                    f"memory:experience:{experience.experience_id}",
                    86400 * 30,  # Keep for 30 days
                    json.dumps(experience_data, default=str)
                )
        except Exception as e:
            logger.error("Failed to persist experience", 
                        experience_id=experience.experience_id, 
                        error=str(e))

    def start_maintenance(self):
        """Start background memory maintenance"""
        if self._maintenance_task is None:
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())

    async def _maintenance_loop(self):
        """Background maintenance of memory systems"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._apply_decay()
                await self._cleanup_old_memories()
                await self._consolidate_memories()
                logger.info("Memory maintenance completed")
            except Exception as e:
                logger.error("Memory maintenance failed", error=str(e))

    async def _apply_decay(self):
        """Apply decay to memories based on their type and age"""
        with self.memory_lock:
            # Apply decay to long-term memories
            for key, experience in list(self.long_term_memory.items()):
                days_old = (datetime.now() - experience.timestamp).days
                decay_rate = self.decay_rates.get(experience.memory_type, 0.01)
                experience.decay_factor *= (1 - decay_rate * days_old / 30.0)
                
                # Remove heavily decayed memories
                if experience.decay_factor < 0.1:
                    del self.long_term_memory[key]

    async def _cleanup_old_memories(self):
        """Remove old, irrelevant memories"""
        cutoff_date = datetime.now() - timedelta(days=90)
        
        with self.memory_lock:
            # Clean episodic memories
            for agent_id in list(self.episodic_memory.keys()):
                experiences = self.episodic_memory[agent_id]
                self.episodic_memory[agent_id] = [
                    exp for exp in experiences 
                    if exp.timestamp > cutoff_date or exp.feedback_score > 0.8
                ]

    async def _consolidate_memories(self):
        """Consolidate similar memories to reduce storage"""
        # This is a placeholder for memory consolidation logic
        # In a production system, this would involve clustering similar experiences
        # and creating consolidated representations
        pass

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory system statistics"""
        with self.memory_lock:
            return {
                'short_term_count': len(self.short_term_memory),
                'long_term_count': len(self.long_term_memory),
                'episodic_count': sum(len(exp_list) for exp_list in self.episodic_memory.values()),
                'semantic_patterns': len(self.semantic_memory),
                'procedural_knowledge': len(self.procedural_memory),
                'total_agents_tracked': len(self.episodic_memory),
                'memory_usage_mb': sum(
                    len(str(v)) for memories in [
                        self.long_term_memory, self.semantic_memory, self.procedural_memory
                    ] for v in memories.values()
                ) / 1024 / 1024,
                'avg_experience_quality': np.mean([
                    exp.feedback_score for exp_list in self.episodic_memory.values() 
                    for exp in exp_list
                ]) if self.episodic_memory else 0.0
            }


class EnhancedAgent(ABC):
    """Production-ready base agent with advanced capabilities"""
    
    def __init__(self, agent_id: str, agent_type: AgentType, 
                 knowledge_graph: EnhancedKnowledgeGraph,
                 memory_system: AdvancedMemorySystem,
                 config: Dict[str, Any] = None):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state = AgentState.IDLE
        self.knowledge_graph = knowledge_graph
        self.memory_system = memory_system
        self.config = config or {}
        
        # Performance tracking
        self.metrics = PerformanceMetrics(agent_id=agent_id)
        self.task_history = deque(maxlen=1000)
        self.learning_history = []
        
        # Communication and collaboration
        self.message_queue = asyncio.Queue(maxsize=100)
        self.collaborative_agents = set()
        self.communication_protocols = {}
        
        # Resource management
        self.max_concurrent_tasks = self.config.get('max_concurrent_tasks', 3)
        self.current_tasks = {}
        self.task_semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        
        # Learning parameters
        self.learning_rate = self.config.get('learning_rate', 0.01)
        self.exploration_rate = self.config.get('exploration_rate', 0.1)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.7)
        
        # Specialized capabilities
        self.specialized_skills = set()
        self.skill_proficiency = {}
        
        # Error handling and recovery
        self.error_count = 0
        self.last_error = None
        self.recovery_strategies = {}
        
        # Thread safety
        self.lock = asyncio.Lock()

    @abstractmethod
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a task - must be implemented by subclasses"""
        pass

    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Enhanced task execution with comprehensive monitoring"""
        start_time = time.time()
        result = {'success': False, 'error': None, 'output': None}
        
        try:
            async with self.task_semaphore:
                await self._update_state(AgentState.THINKING)
                
                # Pre-execution preparation
                await self._prepare_for_task(task)
                
                # Retrieve relevant experiences
                relevant_experiences = await self.memory_system.retrieve_relevant_experiences(
                    self.agent_id, task.task_type, task.data
                )
                
                # Update state to executing
                await self._update_state(AgentState.EXECUTING)
                self.current_tasks[task.task_id] = task
                
                # Process the task
                task_result = await self.process_task(task)
                result.update(task_result)
                
                # Post-execution learning
                await self._update_state(AgentState.LEARNING)
                await self._learn_from_task(task, result, relevant_experiences, time.time() - start_time)
                
                # Update metrics
                await self._update_metrics(task, result, time.time() - start_time)
                
                result['success'] = True
                
        except Exception as e:
            result['error'] = str(e)
            result['traceback'] = traceback.format_exc()
            await self._handle_error(task, e)
            
        finally:
            # Cleanup
            if task.task_id in self.current_tasks:
                del self.current_tasks[task.task_id]
            await self._update_state(AgentState.IDLE)
            
            # Store task in history
            self.task_history.append({
                'task_id': task.task_id,
                'task_type': task.task_type,
                'execution_time': time.time() - start_time,
                'success': result['success'],
                'timestamp': datetime.now()
            })
        
        return result

    async def _prepare_for_task(self, task: Task):
        """Prepare agent for task execution"""
        try:
            # Load relevant knowledge
            related_concepts = await self.knowledge_graph.find_related_concepts(
                task.task_type, max_distance=2
            )
            
            # Update working memory with relevant information
            self.working_memory = {
                'current_task': task,
                'related_concepts': related_concepts,
                'preparation_timestamp': datetime.now()
            }
            
            # Check for required skills
            required_skills = self._extract_required_skills(task)
            missing_skills = required_skills - self.specialized_skills
            
            if missing_skills:
                await self._acquire_skills(missing_skills)
            
        except Exception as e:
            logger.error("Task preparation failed", 
                        agent_id=self.agent_id, 
                        task_id=task.task_id, 
                        error=str(e))

    def _extract_required_skills(self, task: Task) -> Set[str]:
        """Extract required skills from task specification"""
        skills = set()
        
        # Basic skill mapping
        skill_mappings = {
            'coding': {'programming', 'debugging', 'testing'},
            'research': {'information_gathering', 'analysis', 'synthesis'},
            'creative': {'brainstorming', 'ideation', 'storytelling'},
            'analytical': {'data_analysis', 'pattern_recognition', 'statistics'},
            'reasoning': {'logical_thinking', 'problem_solving', 'decision_making'}
        }
        
        base_skills = skill_mappings.get(task.task_type, set())
        skills.update(base_skills)
        
        # Extract from task data
        if 'required_skills' in task.data:
            skills.update(task.data['required_skills'])
        
        return skills

    async def _acquire_skills(self, skills: Set[str]):
        """Acquire new skills through learning"""
        for skill in skills:
            try:
                # Simulate skill acquisition (in production, this would involve training)
                learning_time = np.random.exponential(30)  # Average 30 seconds
                await asyncio.sleep(min(learning_time, 5))  # Cap at 5 seconds for demo
                
                self.specialized_skills.add(skill)
                self.skill_proficiency[skill] = 0.5  # Start with basic proficiency
                
                logger.info("Acquired new skill", 
                           agent_id=self.agent_id, 
                           skill=skill)
                
            except Exception as e:
                logger.error("Failed to acquire skill", 
                            agent_id=self.agent_id, 
                            skill=skill, 
                            error=str(e))

    async def _learn_from_task(self, task: Task, result: Dict[str, Any], 
                              relevant_experiences: List[Experience], 
                              execution_time: float):
        """Learn from task execution"""
        try:
            # Calculate feedback score
            feedback_score = self._calculate_feedback_score(task, result)
            
            # Determine novelty and complexity
            novelty_score = self._calculate_novelty_score(task, relevant_experiences)
            complexity_score = self._calculate_complexity_score(task)
            
            # Extract learned patterns
            learned_patterns = self._extract_patterns(task, result)
            
            # Create experience
            experience = Experience(
                experience_id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                task_type=task.task_type,
                input_data=task.data,
                output_data=result.get('output', {}),
                feedback_score=feedback_score,
                execution_time=execution_time,
                timestamp=datetime.now(),
                context={'task_priority': task.priority.value},
                success=result.get('success', False),
                learned_patterns=learned_patterns,
                confidence_score=result.get('confidence', 0.0),
                complexity_score=complexity_score,
                novelty_score=novelty_score,
                collaborative_agents=list(self.collaborative_agents)
            )
            
            # Store experience
            await self.memory_system.store_experience(experience)
            self.learning_history.append(experience.experience_id)
            
            # Update knowledge graph
            for pattern in learned_patterns:
                await self.knowledge_graph.add_knowledge(
                    pattern, 
                    {
                        'task_type': task.task_type,
                        'success': result.get('success', False),
                        'agent_id': self.agent_id,
                        'timestamp': datetime.now().isoformat()
                    }
                )
            
            # Update skill proficiency
            await self._update_skill_proficiency(task, result)
            
        except Exception as e:
            logger.error("Learning from task failed", 
                        agent_id=self.agent_id, 
                        task_id=task.task_id, 
                        error=str(e))

    def _calculate_feedback_score(self, task: Task, result: Dict[str, Any]) -> float:
        """Calculate feedback score based on task execution"""
        score = 0.0
        
        # Base score from success
        if result.get('success', False):
            score += 0.5
        
        # Quality indicators
        if 'quality_score' in result:
            score += result['quality_score'] * 0.3
        
        # Efficiency (time-based)
        if task.estimated_duration and 'execution_time' in result:
            efficiency = min(task.estimated_duration / result['execution_time'], 2.0)
            score += efficiency * 0.1
        
        # Completeness
        if 'completeness' in result:
            score += result['completeness'] * 0.1
        
        return min(score, 1.0)

    def _calculate_novelty_score(self, task: Task, 
                                relevant_experiences: List[Experience]) -> float:
        """Calculate how novel/unique this task is"""
        if not relevant_experiences:
            return 1.0  # Completely novel
        
        # Simple similarity-based novelty
        similarities = []
        for exp in relevant_experiences:
            similarity = len(set(task.data.keys()) & set(exp.input_data.keys())) / \
                        max(len(set(task.data.keys()) | set(exp.input_data.keys())), 1)
            similarities.append(similarity)
        
        max_similarity = max(similarities) if similarities else 0
        return 1.0 - max_similarity

    def _calculate_complexity_score(self, task: Task) -> float:
        """Calculate task complexity"""
        score = 0.0
        
        # Data complexity
        if isinstance(task.data, dict):
            score += min(len(task.data) / 10.0, 0.3)
        
        # Dependency complexity
        score += min(len(task.dependencies) / 5.0, 0.2)
        
        # Priority-based complexity
        score += task.priority.value / 10.0
        
        # Task type complexity
        complexity_weights = {
            'coding': 0.8,
            'research': 0.6,
            'creative': 0.7,
            'analytical': 0.8,
            'reasoning': 0.9,
            'synthesis': 0.9
        }
        score += complexity_weights.get(task.task_type, 0.5) * 0.3
        
        return min(score, 1.0)

    def _extract_patterns(self, task: Task, result: Dict[str, Any]) -> List[str]:
        """Extract learnable patterns from task execution"""
        patterns = []
        
        # Task type patterns
        if result.get('success'):
            patterns.append(f"successful_{task.task_type}_execution")
        
        # Input-output patterns
        if 'output' in result and task.data:
            pattern = f"{task.task_type}_{hash(str(sorted(task.data.keys())))}"
            patterns.append(pattern)
        
        # Error patterns
        if 'error' in result and result['error']:
            error_pattern = f"error_in_{task.task_type}_{type(result['error']).__name__}"
            patterns.append(error_pattern)
        
        # Performance patterns
        if 'execution_time' in result:
            if result['execution_time'] < 5:  # Fast execution
                patterns.append(f"fast_{task.task_type}_execution")
            elif result['execution_time'] > 30:  # Slow execution
                patterns.append(f"slow_{task.task_type}_execution")
        
        return patterns

    async def _update_skill_proficiency(self, task: Task, result: Dict[str, Any]):
        """Update skill proficiency based on task performance"""
        required_skills = self._extract_required_skills(task)
        
        for skill in required_skills:
            if skill in self.skill_proficiency:
                # Update based on success and quality
                adjustment = self.learning_rate
                if result.get('success'):
                    adjustment *= 1.5
                if 'quality_score' in result:
                    adjustment *= result['quality_score']
                
                # Apply learning with decay
                current_proficiency = self.skill_proficiency[skill]
                new_proficiency = current_proficiency + adjustment * (1 - current_proficiency)
                self.skill_proficiency[skill] = min(new_proficiency, 1.0)

    async def _update_metrics(self, task: Task, result: Dict[str, Any], execution_time: float):
        """Update performance metrics"""
        async with self.lock:
            self.metrics.task_count += 1
            
            # Update success rate
            if result.get('success'):
                success_count = self.metrics.success_rate * (self.metrics.task_count - 1) + 1
            else:
                success_count = self.metrics.success_rate * (self.metrics.task_count - 1)
            self.metrics.success_rate = success_count / self.metrics.task_count
            
            # Update average execution time
            total_time = self.metrics.avg_execution_time * (self.metrics.task_count - 1) + execution_time
            self.metrics.avg_execution_time = total_time / self.metrics.task_count
            
            # Update quality score
            if 'quality_score' in result:
                total_quality = self.metrics.avg_quality_score * (self.metrics.task_count - 1) + result['quality_score']
                self.metrics.avg_quality_score = total_quality / self.metrics.task_count
            
            # System metrics
            self.metrics.memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
            self.metrics.cpu_usage = psutil.Process().cpu_percent()
            
            self.metrics.last_updated = datetime.now()

    async def _handle_error(self, task: Task, error: Exception):
        """Handle task execution errors"""
        self.error_count += 1
        self.last_error = {
            'task_id': task.task_id,
            'error': str(error),
            'timestamp': datetime.now(),
            'traceback': traceback.format_exc()
        }
        
        # Attempt recovery
        if task.task_id in self.recovery_strategies:
            try:
                recovery_strategy = self.recovery_strategies[task.task_id]
                await recovery_strategy(task, error)
            except Exception as recovery_error:
                logger.error("Recovery strategy failed", 
                           agent_id=self.agent_id,
                           task_id=task.task_id,
                           recovery_error=str(recovery_error))

    async def _update_state(self, new_state: AgentState):
        """Update agent state"""
        old_state = self.state
        self.state = new_state
        logger.debug("Agent state changed", 
                    agent_id=self.agent_id,
                    old_state=old_state.value,
                    new_state=new_state.value)

    async def communicate_with_agent(self, target_agent_id: str, message: Dict[str, Any]) -> bool:
        """Send message to another agent"""
        try:
            # This would integrate with the multi-agent communication system
            # For now, just log the communication
            logger.info("Agent communication", 
                       from_agent=self.agent_id,
                       to_agent=target_agent_id,
                       message_type=message.get('type', 'unknown'))
            
            self.collaborative_agents.add(target_agent_id)
            return True
            
        except Exception as e:
            logger.error("Agent communication failed", 
                        from_agent=self.agent_id,
                        to_agent=target_agent_id,
                        error=str(e))
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive agent status"""
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type.value,
            'state': self.state.value,
            'metrics': asdict(self.metrics),
            'current_tasks': len(self.current_tasks),
            'specialized_skills': list(self.specialized_skills),
            'skill_proficiency': self.skill_proficiency,
            'collaborative_agents': list(self.collaborative_agents),
            'error_count': self.error_count,
            'last_error': self.last_error,
            'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'uptime_seconds': (datetime.now() - self.metrics.last_updated).total_seconds() if self.metrics.last_updated else 0
        }


class ProductionTaskScheduler:
    """Production-grade task scheduler with advanced algorithms"""
    
    def __init__(self, max_concurrent_tasks: int = 100):
        self.task_queue = PriorityQueue()
        self.active_tasks = {}
        self.completed_tasks = {}
        self.failed_tasks = {}
        
        # Scheduling parameters
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = 300  # 5 minutes default
        
        # Agent management
        self.available_agents = {}
        self.agent_capabilities = {}
        self.agent_workloads = defaultdict(int)
        
        # Scheduling algorithms
        self.scheduling_algorithms = {
            'priority': self._priority_scheduling,
            'round_robin': self._round_robin_scheduling,
            'load_balanced': self._load_balanced_scheduling,
            'capability_based': self._capability_based_scheduling
        }
        self.current_algorithm = 'load_balanced'
        
        # Performance tracking
        self.scheduling_metrics = {
            'total_scheduled': 0,
            'successful_assignments': 0,
            'failed_assignments': 0,
            'average_wait_time': 0.0,
            'average_execution_time': 0.0
        }
        
        # Thread safety
        self.lock = asyncio.Lock()
        self._scheduler_task = None

    async def submit_task(self, task: Task) -> bool:
        """Submit a task for scheduling"""
        try:
            async with self.lock:
                # Validate task
                if not self._validate_task(task):
                    return False
                
                # Calculate priority score
                priority_score = self._calculate_priority_score(task)
                
                # Add to queue (negative priority for min-heap behavior)
                await self.task_queue.put((-priority_score, time.time(), task))
                
                self.scheduling_metrics['total_scheduled'] += 1
                
                logger.info("Task submitted", 
                           task_id=task.task_id,
                           priority=priority_score)
                
                return True
                
        except Exception as e:
            logger.error("Failed to submit task", 
                        task_id=task.task_id, 
                        error=str(e))
            return False

    def _validate_task(self, task: Task) -> bool:
        """Validate task before scheduling"""
        # Check required fields
        if not all([task.task_id, task.task_type, task.data]):
            return False
        
        # Check dependencies exist
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False
        
        # Check deadline is reasonable
        if task.deadline and task.deadline < datetime.now():
            return False
        
        return True

    def _calculate_priority_score(self, task: Task) -> float:
        """Calculate comprehensive priority score"""
        score = float(task.priority.value) * 20  # Base priority
        
        # Deadline urgency
        if task.deadline:
            time_to_deadline = (task.deadline - datetime.now()).total_seconds()
            if time_to_deadline > 0:
                urgency = max(0, 100 - time_to_deadline / 3600)  # Hours to deadline
                score += urgency
        
        # Dependency chain length (higher priority for blocking tasks)
        if task.subtasks:
            score += len(task.subtasks) * 5
        
        # Resource requirements (simpler tasks get slight boost)
        resource_complexity = sum(task.resource_requirements.values())
        score += max(0, 20 - resource_complexity)
        
        return score

    async def register_agent(self, agent: EnhancedAgent):
        """Register an agent with the scheduler"""
        async with self.lock:
            self.available_agents[agent.agent_id] = agent
            self.agent_capabilities[agent.agent_id] = {
                'agent_type': agent.agent_type,
                'specialized_skills': agent.specialized_skills,
                'skill_proficiency': agent.skill_proficiency,
                'max_concurrent_tasks': agent.max_concurrent_tasks
            }
            self.agent_workloads[agent.agent_id] = 0
            
            logger.info("Agent registered", agent_id=agent.agent_id)

    async def start_scheduling(self):
        """Start the task scheduling loop"""
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduling_loop())
            logger.info("Task scheduler started")

    async def _scheduling_loop(self):
        """Main scheduling loop"""
        while True:
            try:
                await self._schedule_pending_tasks()
                await self._monitor_active_tasks()
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error("Scheduling loop error", error=str(e))
                await asyncio.sleep(5)  # Back off on error

    async def _schedule_pending_tasks(self):
        """Schedule pending tasks to available agents"""
        if self.task_queue.empty():
            return
        
        try:
            # Get scheduling algorithm
            scheduler = self.scheduling_algorithms[self.current_algorithm]
            
            # Process tasks from queue
            tasks_to_schedule = []
            while not self.task_queue.empty() and len(tasks_to_schedule) < 10:
                try:
                    priority, timestamp, task = await asyncio.wait_for(
                        self.task_queue.get(), timeout=0.1
                    )
                    tasks_to_schedule.append((priority, timestamp, task))
                except asyncio.TimeoutError:
                    break
            
            # Schedule each task
            for priority, timestamp, task in tasks_to_schedule:
                agent_id = await scheduler(task)
                
                if agent_id:
                    await self._assign_task_to_agent(task, agent_id)
                    self.scheduling_metrics['successful_assignments'] += 1
                else:
                    # Put task back in queue if no agent available
                    await self.task_queue.put((priority, timestamp, task))
                    self.scheduling_metrics['failed_assignments'] += 1
                    
        except Exception as e:
            logger.error("Task scheduling failed", error=str(e))

    async def _load_balanced_scheduling(self, task: Task) -> Optional[str]:
        """Load-balanced scheduling algorithm"""
        suitable_agents = []
        
        for agent_id, agent in self.available_agents.items():
            # Check if agent can handle this task type
            if self._can_agent_handle_task(agent, task):
                workload = self.agent_workloads[agent_id]
                max_tasks = self.agent_capabilities[agent_id].get('max_concurrent_tasks', 3)
                
                if workload < max_tasks:
                    # Calculate load score (lower is better)
                    load_score = workload / max_tasks
                    skill_match = self._calculate_skill_match(agent, task)
                    combined_score = load_score - (skill_match * 0.3)  # Prefer skilled agents
                    
                    suitable_agents.append((combined_score, agent_id))
        
        if suitable_agents:
            suitable_agents.sort(key=lambda x: x[0])  # Sort by combined score
            return suitable_agents[0][1]  # Return best agent
        
        return None

    async def _capability_based_scheduling(self, task: Task) -> Optional[str]:
        """Capability-based scheduling algorithm"""
        best_agent = None
        best_score = -1
        
        for agent_id, agent in self.available_agents.items():
            if self._can_agent_handle_task(agent, task):
                workload = self.agent_workloads[agent_id]
                max_tasks = self.agent_capabilities[agent_id].get('max_concurrent_tasks', 3)
                
                if workload < max_tasks:
                    skill_score = self._calculate_skill_match(agent, task)
                    availability_score = 1.0 - (workload / max_tasks)
                    combined_score = skill_score * 0.7 + availability_score * 0.3
                    
                    if combined_score > best_score:
                        best_score = combined_score
                        best_agent = agent_id
        
        return best_agent

    async def _priority_scheduling(self, task: Task) -> Optional[str]:
        """Simple priority-based scheduling"""
        for agent_id, agent in self.available_agents.items():
            if (self._can_agent_handle_task(agent, task) and 
                self.agent_workloads[agent_id] < 
                self.agent_capabilities[agent_id].get('max_concurrent_tasks', 3)):
                return agent_id
        return None

    async def _round_robin_scheduling(self, task: Task) -> Optional[str]:
        """Round-robin scheduling among capable agents"""
        capable_agents = [
            agent_id for agent_id, agent in self.available_agents.items()
            if (self._can_agent_handle_task(agent, task) and 
                self.agent_workloads[agent_id] < 
                self.agent_capabilities[agent_id].get('max_concurrent_tasks', 3))
        ]
        
        if capable_agents:
            # Simple round-robin based on task count
            min_tasks = min(self.agent_workloads[aid] for aid in capable_agents)
            for agent_id in capable_agents:
                if self.agent_workloads[agent_id] == min_tasks:
                    return agent_id
        
        return None

    def _can_agent_handle_task(self, agent: EnhancedAgent, task: Task) -> bool:
        """Check if agent can handle the specific task"""
        # Check agent type compatibility
        compatible_types = {
            AgentType.CODING: ['coding', 'debugging', 'optimization'],
            AgentType.RESEARCH: ['research', 'analysis', 'information_gathering'],
            AgentType.CREATIVE: ['creative', 'brainstorming', 'content_creation'],
            AgentType.ANALYTICAL: ['analytical', 'data_analysis', 'pattern_recognition'],
            AgentType.REASONING: ['reasoning', 'planning', 'decision_making'],
            AgentType.SYNTHESIS: ['synthesis', 'integration', 'summarization']
        }
        
        compatible_task_types = compatible_types.get(agent.agent_type, [])
        if task.task_type not in compatible_task_types and task.task_type != 'general':
            return False
        
        # Check required skills
        if 'required_skills' in task.data:
            required_skills = set(task.data['required_skills'])
            agent_skills = agent.specialized_skills
            
            # Agent must have at least 70% of required skills
            skill_overlap = len(required_skills & agent_skills)
            if skill_overlap / len(required_skills) < 0.7:
                return False
        
        return True

    def _calculate_skill_match(self, agent: EnhancedAgent, task: Task) -> float:
        """Calculate how well an agent's skills match the task"""
        if 'required_skills' not in task.data:
            return 0.5  # Default neutral score
        
        required_skills = set(task.data['required_skills'])
        agent_skills = agent.specialized_skills
        
        if not required_skills:
            return 1.0
        
        # Calculate overlap
        skill_overlap = len(required_skills & agent_skills)
        base_score = skill_overlap / len(required_skills)
        
        # Weight by proficiency
        proficiency_bonus = 0.0
        for skill in required_skills & agent_skills:
            proficiency_bonus += agent.skill_proficiency.get(skill, 0.5)
        
        proficiency_bonus /= len(required_skills) if required_skills else 1
        
        return min(base_score + (proficiency_bonus * 0.3), 1.0)

    async def _assign_task_to_agent(self, task: Task, agent_id: str):
        """Assign task to specific agent"""
        try:
            agent = self.available_agents[agent_id]
            
            # Update task assignment
            task.assigned_agent = agent_id
            task.status = "assigned"
            
            # Update workload tracking
                '