"""
YMERA Learning Engine - Production Ready
Implements continuous learning, pattern recognition, and knowledge management
"""

import asyncio
import json
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import logging
import uuid
import pickle
import hashlib

@dataclass
class LearningRecord:
    """Learning record for knowledge capture"""
    id: str
    agent_id: str
    task_id: str
    learning_type: str  # 'feedback', 'pattern', 'improvement', 'error'
    content: Dict[str, Any]
    context: Dict[str, Any]
    effectiveness_score: float
    confidence: float
    timestamp: datetime
    applied: bool = False
    validation_results: Optional[Dict] = None

@dataclass
class Pattern:
    """Identified pattern in agent behavior or data"""
    id: str
    type: str  # 'success', 'failure', 'optimization'
    description: str
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    confidence: float
    frequency: int
    last_seen: datetime
    effectiveness: float

@dataclass
class KnowledgeItem:
    """Knowledge base item"""
    id: str
    category: str
    title: str
    content: str
    tags: List[str]
    embedding: Optional[List[float]]
    source: str
    confidence_score: float
    usage_count: int
    created_at: datetime
    updated_at: datetime

class LearningEngine:
    """Production-ready learning engine with continuous improvement"""
    
    def __init__(self, db_manager, knowledge_base, ai_manager, cache_manager):
        self.db_manager = db_manager
        self.knowledge_base = knowledge_base
        self.ai_manager = ai_manager
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        
        # Learning components
        self.patterns: Dict[str, Pattern] = {}
        self.learning_records: List[LearningRecord] = []
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.pattern_detector = None
        self.feedback_processor = None
        
        # Learning configuration
        self.learning_interval = 3600  # 1 hour
        self.pattern_confidence_threshold = 0.7
        self.effectiveness_threshold = 0.6
        self.max_learning_records = 10000
        
        # State management
        self._learning_task = None
        self._is_running = False
        self._last_learning_cycle = None
    
    async def initialize(self):
        """Initialize the learning engine"""
        try:
            # Load existing patterns and learning records
            await self._load_learning_state()
            
            # Initialize pattern detection
            await self._initialize_pattern_detection()
            
            # Setup feedback processing
            await self._setup_feedback_processing()
            
            self.logger.info("Learning engine initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize learning engine: {str(e)}")
            raise
    
    async def _load_learning_state(self):
        """Load existing learning state from database"""
        try:
            async with self.db_manager.get_session() as session:
                # Load learning records
                query = "SELECT * FROM learning_records ORDER BY created_at DESC LIMIT 1000"
                records = await session.execute(query)
                
                for record in records.fetchall():
                    learning_record = LearningRecord(
                        id=record.id,
                        agent_id=record.agent_id,
                        task_id=record.task_id,
                        learning_type=record.learning_type,
                        content=json.loads(record.content),
                        context={},
                        effectiveness_score=record.effectiveness_score / 100.0,
                        confidence=0.8,  # Default confidence
                        timestamp=record.created_at,
                        applied=record.applied
                    )
                    self.learning_records.append(learning_record)
                
                self.logger.info(f"Loaded {len(self.learning_records)} learning records")
                
        except Exception as e:
            self.logger.warning(f"Could not load learning state: {str(e)}")
    
    async def _initialize_pattern_detection(self):
        """Initialize pattern detection algorithms"""
        try:
            if len(self.learning_records) > 10:
                # Prepare data for pattern detection
                texts = []
                for record in self.learning_records:
                    text = f"{record.learning_type} {json.dumps(record.content)}"
                    texts.append(text)
                
                # Train vectorizer
                self.vectorizer.fit(texts)
                
                # Initialize clustering for pattern detection
                vectors = self.vectorizer.transform(texts)
                n_clusters = min(10, len(texts) // 3)
                if n_clusters > 1:
                    self.pattern_detector = KMeans(n_clusters=n_clusters, random_state=42)
                    self.pattern_detector.fit(vectors.toarray())
                
                self.logger.info("Pattern detection initialized")
            
        except Exception as e:
            self.logger.warning(f"Pattern detection initialization failed: {str(e)}")
    
    async def _setup_feedback_processing(self):
        """Setup feedback processing capabilities"""
        self.feedback_processor = FeedbackProcessor(
            learning_engine=self,
            ai_manager=self.ai_manager
        )
    
    async def start_continuous_learning(self):
        """Start continuous learning loop"""
        if self._is_running:
            self.logger.warning("Learning engine already running")
            return
        
        self._is_running = True
        self._learning_task = asyncio.create_task(self._learning_loop())
        self.logger.info("Continuous learning started")
    
    async def stop_continuous_learning(self):
        """Stop continuous learning loop"""
        self._is_running = False
        if self._learning_task:
            self._learning_task.cancel()
            try:
                await self._learning_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Continuous learning stopped")
    
    async def _learning_loop(self):
        """Main learning loop"""
        while self._is_running:
            try:
                await self._execute_learning_cycle()
                self._last_learning_cycle = datetime.utcnow()
                await asyncio.sleep(self.learning_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Learning cycle failed: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _execute_learning_cycle(self):
        """Execute a single learning cycle"""
        self.logger.info("Starting learning cycle")
        
        # 1. Process recent feedback
        await self._process_recent_feedback()
        
        # 2. Detect new patterns
        await self._detect_patterns()
        
        # 3. Update knowledge base
        await self._update_knowledge_base()
        
        # 4. Evaluate and apply improvements
        await self._evaluate_and_apply_improvements()
        
        # 5. Cleanup old records
        await self._cleanup_learning_records()
        
        self.logger.info("Learning cycle completed")
    
    async def record_learning(self, 
                            agent_id: str,
                            task_id: str,
                            learning_type: str,
                            content: Dict[str, Any],
                            context: Dict[str, Any] = None,
                            effectiveness_score: float = 0.0) -> str:
        """Record a learning event"""
        try:
            record_id = str(uuid.uuid4())
            
            learning_record = LearningRecord(
                id=record_id,
                agent_id=agent_id,
                task_id=task_id,
                learning_type=learning_type,
                content=content,
                context=context or {},
                effectiveness_score=effectiveness_score,
                confidence=0.8,
                timestamp=datetime.utcnow()
            )
            
            # Add to in-memory collection
            self.learning_records.append(learning_record)
            
            # Persist to database
            await self._persist_learning_record(learning_record)
            
            # Process immediately if it's high-value learning
            if effectiveness_score > 0.8:
                await self._process_high_value_learning(learning_record)
            
            self.logger.debug(f"Learning recorded: {learning_type} for agent {agent_id}")
            return record_id
            
        except Exception as e:
            self.logger.error(f"Failed to record learning: {str(e)}")
            raise
    
    async def _persist_learning_record(self, record: LearningRecord):
        """Persist learning record to database"""
        try:
            async with self.db_manager.get_session() as session:
                query = """
                INSERT INTO learning_records 
                (id, agent_id, task_id, learning_type, content, effectiveness_score, applied, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                await session.execute(query, (
                    record.id,
                    record.agent_id,
                    record.task_id,
                    record.learning_type,
                    json.dumps(record.content),
                    int(record.effectiveness_score * 100),
                    record.applied,
                    record.timestamp
                ))
                
        except Exception as e:
            self.logger.error(f"Failed to persist learning record: {str(e)}")
    
    async def _process_recent_feedback(self):
        """Process recent feedback and learning records"""
        try:
            # Get recent unprocessed records
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_records = [
                r for r in self.learning_records 
                if r.timestamp > recent_cutoff and not r.applied
            ]
            
            if not recent_records:
                return
            
            # Group by agent and learning type
            grouped_records = {}
            for record in recent_records:
                key = f"{record.agent_id}_{record.learning_type}"
                if key not in grouped_records:
                    grouped_records[key] = []
                grouped_records[key].append(record)
            
            # Process each group
            for group_key, records in grouped_records.items():
                await self._process_record_group(group_key, records)
                
        except Exception as e:
            self.logger.error(f"Failed to process recent feedback: {str(e)}")
    
    async def _process_record_group(self, group_key: str, records: List[LearningRecord]):
        """Process a group of related learning records"""
        try:
            # Analyze patterns in the group
            if len(records) >= 3:  # Need minimum records for pattern detection
                pattern = await self._analyze_record_patterns(records pattern = await self._analyze_record_patterns(records)
                if pattern and pattern.confidence > self.pattern_confidence_threshold:
                    await self._register_pattern(pattern)
            
            # Apply improvements from successful records
            successful_records = [r for r in records if r.effectiveness_score > self.effectiveness_threshold]
            for record in successful_records:
                await self._apply_learning_record(record)
                
        except Exception as e:
            self.logger.error(f"Failed to process record group {group_key}: {str(e)}")
    
    async def _analyze_record_patterns(self, records: List[LearningRecord]) -> Optional[Pattern]:
        """Analyze patterns in a group of learning records"""
        try:
            if len(records) < 3:
                return None
            
            # Extract common elements
            learning_types = [r.learning_type for r in records]
            most_common_type = max(set(learning_types), key=learning_types.count)
            
            # Calculate average effectiveness
            avg_effectiveness = sum(r.effectiveness_score for r in records) / len(records)
            
            # Extract common content patterns
            content_keys = set()
            for record in records:
                content_keys.update(record.content.keys())
            
            common_conditions = {}
            common_actions = {}
            
            # Find patterns in content
            for key in content_keys:
                values = [r.content.get(key) for r in records if key in r.content]
                if len(values) >= len(records) * 0.6:  # 60% threshold
                    if isinstance(values[0], str):
                        # For string values, find most common
                        most_common = max(set(values), key=values.count) if values else None
                        if most_common:
                            common_conditions[key] = most_common
                    elif isinstance(values[0], (int, float)):
                        # For numeric values, use average
                        common_conditions[key] = sum(values) / len(values)
            
            # Create pattern if we found significant commonalities
            if common_conditions and avg_effectiveness > 0.5:
                pattern = Pattern(
                    id=str(uuid.uuid4()),
                    type=most_common_type,
                    description=f"Pattern in {most_common_type} learning",
                    conditions=common_conditions,
                    actions=common_actions,
                    confidence=min(0.95, avg_effectiveness + 0.1),
                    frequency=len(records),
                    last_seen=datetime.utcnow(),
                    effectiveness=avg_effectiveness
                )
                
                return pattern
                
        except Exception as e:
            self.logger.error(f"Failed to analyze patterns: {str(e)}")
        
        return None
    
    async def _register_pattern(self, pattern: Pattern):
        """Register a new pattern"""
        try:
            self.patterns[pattern.id] = pattern
            
            # Persist pattern to database
            await self._persist_pattern(pattern)
            
            self.logger.info(f"Registered new pattern: {pattern.type} (confidence: {pattern.confidence:.2f})")
            
        except Exception as e:
            self.logger.error(f"Failed to register pattern: {str(e)}")
    
    async def _persist_pattern(self, pattern: Pattern):
        """Persist pattern to database"""
        try:
            async with self.db_manager.get_session() as session:
                query = """
                INSERT INTO patterns 
                (id, type, description, conditions, actions, confidence, frequency, effectiveness, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                now = datetime.utcnow()
                await session.execute(query, (
                    pattern.id,
                    pattern.type,
                    pattern.description,
                    json.dumps(pattern.conditions),
                    json.dumps(pattern.actions),
                    pattern.confidence,
                    pattern.frequency,
                    pattern.effectiveness,
                    now,
                    now
                ))
                
        except Exception as e:
            self.logger.error(f"Failed to persist pattern: {str(e)}")
    
    async def _apply_learning_record(self, record: LearningRecord):
        """Apply a learning record to improve system behavior"""
        try:
            if record.applied:
                return
            
            # Apply based on learning type
            if record.learning_type == 'feedback':
                await self._apply_feedback_learning(record)
            elif record.learning_type == 'pattern':
                await self._apply_pattern_learning(record)
            elif record.learning_type == 'improvement':
                await self._apply_improvement_learning(record)
            elif record.learning_type == 'error':
                await self._apply_error_learning(record)
            
            # Mark as applied
            record.applied = True
            await self._update_learning_record(record)
            
        except Exception as e:
            self.logger.error(f"Failed to apply learning record: {str(e)}")
    
    async def _apply_feedback_learning(self, record: LearningRecord):
        """Apply feedback-based learning"""
        try:
            feedback_data = record.content
            
            # Update agent behavior based on feedback
            if 'improvement_suggestions' in feedback_data:
                suggestions = feedback_data['improvement_suggestions']
                await self._apply_behavior_improvements(record.agent_id, suggestions)
            
            # Update knowledge base with lessons learned
            if 'lessons_learned' in feedback_data:
                lessons = feedback_data['lessons_learned']
                await self._add_knowledge_items(lessons, record.agent_id)
                
        except Exception as e:
            self.logger.error(f"Failed to apply feedback learning: {str(e)}")
    
    async def _apply_pattern_learning(self, record: LearningRecord):
        """Apply pattern-based learning"""
        try:
            pattern_data = record.content
            
            # Create reusable pattern from successful behavior
            if record.effectiveness_score > 0.7:
                pattern = Pattern(
                    id=str(uuid.uuid4()),
                    type='success',
                    description=f"Successful pattern from {record.agent_id}",
                    conditions=pattern_data.get('conditions', {}),
                    actions=pattern_data.get('actions', {}),
                    confidence=record.effectiveness_score,
                    frequency=1,
                    last_seen=datetime.utcnow(),
                    effectiveness=record.effectiveness_score
                )
                
                await self._register_pattern(pattern)
                
        except Exception as e:
            self.logger.error(f"Failed to apply pattern learning: {str(e)}")
    
    async def _apply_improvement_learning(self, record: LearningRecord):
        """Apply improvement-based learning"""
        try:
            improvement_data = record.content
            
            # Update system parameters
            if 'parameter_updates' in improvement_data:
                updates = improvement_data['parameter_updates']
                await self._apply_parameter_updates(record.agent_id, updates)
            
            # Update workflows
            if 'workflow_improvements' in improvement_data:
                workflows = improvement_data['workflow_improvements']
                await self._apply_workflow_improvements(record.agent_id, workflows)
                
        except Exception as e:
            self.logger.error(f"Failed to apply improvement learning: {str(e)}")
    
    async def _apply_error_learning(self, record: LearningRecord):
        """Apply error-based learning"""
        try:
            error_data = record.content
            
            # Add error prevention patterns
            if 'error_conditions' in error_data and 'prevention_strategy' in error_data:
                prevention_pattern = Pattern(
                    id=str(uuid.uuid4()),
                    type='error_prevention',
                    description=f"Error prevention for {error_data.get('error_type', 'unknown')}",
                    conditions=error_data['error_conditions'],
                    actions={'prevention': error_data['prevention_strategy']},
                    confidence=0.8,
                    frequency=1,
                    last_seen=datetime.utcnow(),
                    effectiveness=0.7  # Default for error prevention
                )
                
                await self._register_pattern(prevention_pattern)
            
            # Update error handling procedures
            if 'error_handling' in error_data:
                await self._update_error_handling(record.agent_id, error_data['error_handling'])
                
        except Exception as e:
            self.logger.error(f"Failed to apply error learning: {str(e)}")
    
    async def _detect_patterns(self):
        """Detect new patterns in learning data"""
        try:
            if not self.pattern_detector or len(self.learning_records) < 10:
                return
            
            # Prepare recent data for pattern detection
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_records = [
                r for r in self.learning_records 
                if r.timestamp > recent_cutoff
            ]
            
            if len(recent_records) < 5:
                return
            
            # Vectorize learning records
            texts = []
            for record in recent_records:
                text = f"{record.learning_type} {record.agent_id} {json.dumps(record.content)}"
                texts.append(text)
            
            vectors = self.vectorizer.transform(texts)
            
            # Detect clusters (patterns)
            clusters = self.pattern_detector.predict(vectors.toarray())
            
            # Analyze each cluster
            cluster_records = {}
            for i, cluster_id in enumerate(clusters):
                if cluster_id not in cluster_records:
                    cluster_records[cluster_id] = []
                cluster_records[cluster_id].append(recent_records[i])
            
            # Create patterns from significant clusters
            for cluster_id, records in cluster_records.items():
                if len(records) >= 3:  # Minimum cluster size
                    pattern = await self._analyze_record_patterns(records)
                    if pattern and pattern.id not in self.patterns:
                        await self._register_pattern(pattern)
                        
        except Exception as e:
            self.logger.error(f"Failed to detect patterns: {str(e)}")
    
    async def _update_knowledge_base(self):
        """Update knowledge base with learned information"""
        try:
            # Extract knowledge from successful learning records
            successful_records = [
                r for r in self.learning_records 
                if r.effectiveness_score > 0.7 and not r.applied
            ]
            
            for record in successful_records:
                knowledge_items = await self._extract_knowledge_items(record)
                for item in knowledge_items:
                    await self.knowledge_base.add_knowledge_item(item)
                    
        except Exception as e:
            self.logger.error(f"Failed to update knowledge base: {str(e)}")
    
    async def _extract_knowledge_items(self, record: LearningRecord) -> List[KnowledgeItem]:
        """Extract knowledge items from a learning record"""
        try:
            items = []
            
            # Create knowledge item from successful learning
            if record.effectiveness_score > 0.7:
                item = KnowledgeItem(
                    id=str(uuid.uuid4()),
                    category=record.learning_type,
                    title=f"Learning from {record.task_id}",
                    content=json.dumps(record.content),
                    tags=[record.learning_type, record.agent_id],
                    embedding=None,  # Will be generated later
                    source=f"learning_record_{record.id}",
                    confidence_score=record.effectiveness_score,
                    usage_count=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                items.append(item)
            
            return items
            
        except Exception as e:
            self.logger.error(f"Failed to extract knowledge items: {str(e)}")
            return []
    
    async def _evaluate_and_apply_improvements(self):
        """Evaluate current patterns and apply improvements"""
        try:
            # Evaluate pattern effectiveness
            for pattern_id, pattern in self.patterns.items():
                if pattern.frequency >= 5:  # Enough data for evaluation
                    effectiveness = await self._evaluate_pattern_effectiveness(pattern)
                    if effectiveness > pattern.effectiveness:
                        pattern.effectiveness = effectiveness
                        await self._update_pattern(pattern)
            
            # Apply top performing patterns
            top_patterns = sorted(
                self.patterns.values(),
                key=lambda p: p.effectiveness * p.confidence,
                reverse=True
            )[:10]  # Top 10 patterns
            
            for pattern in top_patterns:
                if pattern.effectiveness > 0.8:
                    await self._apply_pattern_globally(pattern)
                    
        except Exception as e:
            self.logger.error(f"Failed to evaluate and apply improvements: {str(e)}")
    
    async def _evaluate_pattern_effectiveness(self, pattern: Pattern) -> float:
        """Evaluate the effectiveness of a pattern"""
        try:
            # Find records that match this pattern
            matching_records = []
            for record in self.learning_records:
                if await self._record_matches_pattern(record, pattern):
                    matching_records.append(record)
            
            if not matching_records:
                return pattern.effectiveness
            
            # Calculate average effectiveness of matching records
            avg_effectiveness = sum(r.effectiveness_score for r in matching_records) / len(matching_records)
            
            # Weight by frequency and recency
            recency_weight = self._calculate_recency_weight(matching_records)
            frequency_weight = min(1.0, len(matching_records) / 10.0)
            
            final_effectiveness = avg_effectiveness * recency_weight * frequency_weight
            
            return min(1.0, final_effectiveness)
            
        except Exception as e:
            self.logger.error(f"Failed to evaluate pattern effectiveness: {str(e)}")
            return pattern.effectiveness
    
    async def _record_matches_pattern(self, record: LearningRecord, pattern: Pattern) -> bool:
        """Check if a record matches a pattern"""
        try:
            # Check learning type
            if record.learning_type != pattern.type:
                return False
            
            # Check conditions
            for condition_key, condition_value in pattern.conditions.items():
                if condition_key not in record.content:
                    return False
                
                record_value = record.content[condition_key]
                
                # Handle different value types
                if isinstance(condition_value, str) and isinstance(record_value, str):
                    if condition_value.lower() not in record_value.lower():
                        return False
                elif isinstance(condition_value, (int, float)) and isinstance(record_value, (int, float)):
                    if abs(condition_value - record_value) > condition_value * 0.2:  # 20% tolerance
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to match record to pattern: {str(e)}")
            return False
    
    def _calculate_recency_weight(self, records: List[LearningRecord]) -> float:
        """Calculate recency weight for a set of records"""
        try:
            now = datetime.utcnow()
            weights = []
            
            for record in records:
                days_old = (now - record.timestamp).days
                # Exponential decay: newer records have higher weight
                weight = np.exp(-days_old / 30.0)  # 30-day half-life
                weights.append(weight)
            
            return sum(weights) / len(weights) if weights else 0.0
            
        except Exception as e:
            self.logger.error(f"Failed to calculate recency weight: {str(e)}")
            return 1.0
    
    async def _apply_pattern_globally(self, pattern: Pattern):
        """Apply a high-performing pattern globally"""
        try:
            # This would integrate with the agent management system
            # to apply successful patterns to all relevant agents
            
            self.logger.info(f"Applying pattern globally: {pattern.description} (effectiveness: {pattern.effectiveness:.2f})")
            
            # Example: Update agent configurations based on pattern
            if pattern.type == 'success' and pattern.actions:
                await self._broadcast_pattern_update(pattern)
                
        except Exception as e:
            self.logger.error(f"Failed to apply pattern globally: {str(e)}")
    
    async def _broadcast_pattern_update(self, pattern: Pattern):
        """Broadcast pattern update to all agents"""
        try:
            # This would integrate with the agent communication system
            pattern_update = {
                'type': 'pattern_update',
                'pattern_id': pattern.id,
                'conditions': pattern.conditions,
                'actions': pattern.actions,
                'effectiveness': pattern.effectiveness
            }
            
            # Send to all active agents through the agent manager
            # await self.ai_manager.broadcast_update(pattern_update)
            
            self.logger.info(f"Broadcasted pattern update: {pattern.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to broadcast pattern update: {str(e)}")
    
    async def _cleanup_learning_records(self):
        """Clean up old learning records to prevent memory bloat"""
        try:
            # Remove old records beyond the limit
            if len(self.learning_records) > self.max_learning_records:
                # Sort by timestamp and keep the most recent
                self.learning_records.sort(key=lambda r: r.timestamp, reverse=True)
                removed_count = len(self.learning_records) - self.max_learning_records
                self.learning_records = self.learning_records[:self.max_learning_records]
                
                self.logger.info(f"Cleaned up {removed_count} old learning records")
            
            # Clean up patterns with low effectiveness
            low_effectiveness_patterns = [
                pid for pid, pattern in self.patterns.items()
                if pattern.effectiveness < 0.3 and pattern.frequency < 3
            ]
            
            for pattern_id in low_effectiveness_patterns:
                del self.patterns[pattern_id]
            
            if low_effectiveness_patterns:
                self.logger.info(f"Removed {len(low_effectiveness_patterns)} low-effectiveness patterns")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup learning records: {str(e)}")
    
    async def _process_high_value_learning(self, record: LearningRecord):
        """Process high-value learning immediately"""
        try:
            self.logger.info(f"Processing high-value learning: {record.id}")
            
            # Immediately apply high-value learning
            await self._apply_learning_record(record)
            
            # Share with relevant agents
            if record.effectiveness_score > 0.9:
                await self._share_critical_learning(record)
                
        except Exception as e:
            self.logger.error(f"Failed to process high-value learning: {str(e)}")
    
    async def _share_critical_learning(self, record: LearningRecord):
        """Share critical learning with other agents"""
        try:
            critical_learning = {
                'type': 'critical_learning',
                'learning_type': record.learning_type,
                'content': record.content,
                'effectiveness_score': record.effectiveness_score,
                'source_agent': record.agent_id
            }
            
            # Broadcast to all agents
            # await self.ai_manager.broadcast_critical_learning(critical_learning)
            
            self.logger.info(f"Shared critical learning from agent {record.agent_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to share critical learning: {str(e)}")
    
    async def get_learning_insights(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Get learning insights for analysis"""
        try:
            insights = {
                'total_records': len(self.learning_records),
                'patterns_discovered': len(self.patterns),
                'learning_types': {},
                'effectiveness_distribution': {},
                'recent_improvements': []
            }
            
            # Filter records if agent_id specified
            records = self.learning_records
            if agent_id:
                records = [r for r in records if r.agent_id == agent_id]
            
            # Learning type distribution
            for record in records:
                learning_type = record.learning_type
                if learning_type not in insights['learning_types']:
                    insights['learning_types'][learning_type] = 0
                insights['learning_types'][learning_type] += 1
            
            # Effectiveness distribution
            effectiveness_ranges = [
                ('0.0-0.2', 0.0, 0.2),
                ('0.2-0.4', 0.2, 0.4),
                ('0.4-0.6', 0.4, 0.6),
                ('0.6-0.8', 0.6, 0.8),
                ('0.8-1.0', 0.8, 1.0)
            ]
            
            for range_name, min_val, max_val in effectiveness_ranges:
                count = len([
                    r for r in records 
                    if min_val <= r.effectiveness_score < max_val
                ])
                insights['effectiveness_distribution'][range_name] = count
            
            # Recent improvements (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_records = [
                r for r in records 
                if r.timestamp > recent_cutoff and r.effectiveness_score > 0.7
            ]
            
            insights['recent_improvements'] = [
                {
                    'agent_id': r.agent_id,
                    'learning_type': r.learning_type,
                    'effectiveness_score': r.effectiveness_score,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in recent_records[:10]  # Top 10 recent improvements
            ]
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Failed to get learning insights: {str(e)}")
            return {}
    
    async def export_learning_data(self, format_type: str = 'json') -> str:
        """Export learning data for external analysis"""
        try:
            export_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'learning_records': [asdict(record) for record in self.learning_records],
                'patterns': [asdict(pattern) for pattern in self.patterns.values()],
                'config': {
                    'learning_interval': self.learning_interval,
                    'pattern_confidence_threshold': self.pattern_confidence_threshold,
                    'effectiveness_threshold': self.effectiveness_threshold
                }
            }
            
            # Convert datetime objects to ISO format strings
            def convert_datetime(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return obj
            
            for record in export_data['learning_records']:
                record['timestamp'] = convert_datetime(record['timestamp'])
            
            for pattern in export_data['patterns']:
                pattern['last_seen'] = convert_datetime(pattern['last_seen'])
            
            if format_type == 'json':
                return json.dumps(export_data, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format type: {format_type}")
                
        except Exception as e:
            self.logger.error(f"Failed to export learning data: {str(e)}")
            raise


class FeedbackProcessor:
    """Processes feedback and converts it into actionable learning"""
    
    def __init__(self, learning_engine, ai_manager):
        self.learning_engine = learning_engine
        self.ai_manager = ai_manager
        self.logger = logging.getLogger(__name__)
    
    async def process_user_feedback(self, 
                                   agent_id: str,
                                   task_id: str,
                                   feedback: Dict[str, Any]) -> str:
        """Process user feedback and create learning records"""
        try:
            # Analyze feedback sentiment and extract insights
            insights = await self._analyze_feedback(feedback)
            
            # Create learning content
            learning_content = {
                'original_feedback': feedback,
                'insights': insights,
                'improvement_suggestions': await self._generate_improvements(insights),
                'priority': self._calculate_feedback_priority(feedback, insights)
            }
            
            # Calculate effectiveness score
            effectiveness_score = self._calculate_effectiveness_score(insights)
            
            # Record the learning
            record_id = await self.learning_engine.record_learning(
                agent_id=agent_id,
                task_id=task_id,
                learning_type='feedback',
                content=learning_content,
                effectiveness_score=effectiveness_score
            )
            
            return record_id
            
        except Exception as e:
            self.logger.error(f"Failed to process user feedback: {str(e)}")
            raise
    
    async def _analyze_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze feedback to extract actionable insights"""
        try:
            insights = {
                'sentiment': 'neutral',
                'key_points': [],
                'areas_for_improvement': [],
                'strengths': [],
                'actionable_items': []
            }
            
            # Extract text content for analysis
            text_content = ""
            if 'message' in feedback:
                text_content += feedback['message']
            if 'comments' in feedback:
                text_content += " " + feedback['comments']
            
            if text_content:
                # Simple sentiment analysis (would use AI service in production)
                positive_words = ['good', 'great', 'excellent', 'helpful', 'useful', 'effective']
                negative_words = ['bad', 'poor', 'useless', 'ineffective', 'wrong', 'error']
                
                text_lower = text_content.lower()
                positive_count = sum(1 for word in positive_words if word in text_lower)
                negative_count = sum(1 for word in negative_words if word in text_lower)
                
                if positive_count > negative_count:
                    insights['sentiment'] = 'positive'
                elif negative_count > positive_count:
                    insights['sentiment'] = 'negative'
                
                # Extract key points (simplified)
                sentences = text_content.split('.')
                insights['key_points'] = [s.strip() for s in sentences if len(s.strip()) > 10][:5]
            
            # Extract structured feedback
            if 'rating' in feedback:
                rating = feedback['rating']
                if rating >= 4:
                    insights['sentiment'] = 'positive'
                elif rating <= 2:
                    insights['sentiment'] = 'negative'
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Failed to analyze feedback: {str(e)}")
            return {'sentiment': 'neutral', 'key_points': [], 'areas_for_improvement': []}
    
    async def _generate_improvements(self, insights: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions based on insights"""
        try:
            improvements = []
            
            if insights['sentiment'] == 'negative':
                improvements.extend([
                    'Review and improve response quality',
                    'Enhance understanding of user requirements',
                    'Provide more detailed explanations'
                ])
            
            if insights['sentiment'] == 'positive':
                improvements.extend([
                    'Continue current approach',
                    'Document successful patterns for reuse',
                    'Share best practices with other agents'
                ])
            
            # Add specific improvements based on key points
            for point in insights.get('key_points', []):
                if 'slow' in point.lower():
                    improvements.append('Optimize response time')
                elif 'unclear' in point.lower():
                    improvements.append('Improve communication clarity')
                elif 'incomplete' in point.lower():
                    improvements.append('Ensure complete task fulfillment')
            
            return improvements
            
        except Exception as e:
            self.logger.error(f"Failed to generate improvements: {str(e)}")
            return []
    
    def _calculate_feedback_priority(self, feedback: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Calculate feedback priority level"""
        try:
            priority = 'medium'
            
            # High priority conditions
            if insights['sentiment'] == 'negative':
                priority = 'high'
            elif 'urgent' in str(feedback).lower():
                priority = 'high'
            elif feedback.get('rating', 5) <= 2:
                priority = 'high'
            
            # Low priority conditions
            elif insights['sentiment'] == 'positive':
                priority = 'low'
            elif feedback.get('rating', 3) >= 4:
                priority = 'low'
            
            return priority
            
        except Exception as e:
            self.logger.error(f"Failed to calculate feedback priority: {str(e)}")
            return 'medium'
    
    def _calculate_effectiveness_score(self, insights: Dict[str, Any]) -> float:
        """Calculate effectiveness score for the feedback"""
        try:
            base_score = 0.5  # Default medium effectiveness
            
            # Adjust based on sentiment
            if insights['sentiment'] == 'positive':
                base_score += 0.3
            elif insights['sentiment'] == 'negative':
                base_score += 0.2  # Negative feedback is still valuable for learning
            
            # Adjust based on actionable content
            if insights.get('key_points'):
                base_score += len(insights['key_points']) * 0.05
            
            if insights.get('areas_for_improvement'):
                base_score += len(insights['areas_for_improvement']) * 0.1
            
            return min(1.0, base_score)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate effectiveness score: {str(e)}")
            return 0.5


# Utility functions for learning engine
async def create_learning_tables(db_manager):
    """Create necessary database tables for learning engine"""
    try:
        async with db_manager.get_session() as session:
            # Learning records table
            await session.execute("""
                CREATE TABLE IF NOT EXISTS learning_records (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    learning_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    effectiveness_score INTEGER DEFAULT 0,
                    applied BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Patterns table
            await session.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    description TEXT,
                    conditions TEXT NOT NULL,
                    actions TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    frequency INTEGER DEFAULT 0,
                    effectiveness REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            # Create indexes for better performance
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_records_agent_id 
                ON learning_records(agent_id)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_records_task_id 
                ON learning_records(task_id)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_records_learning_type 
                ON learning_records(learning_type)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_records_effectiveness 
                ON learning_records(effectiveness_score)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_learning_records_created_at 
                ON learning_records(created_at)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_type 
                ON patterns(type)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_effectiveness 
                ON patterns(effectiveness)
            """)
            
            await session.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_confidence 
                ON patterns(confidence)
            """)
            
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create learning tables: {str(e)}")
        raise


class LearningMetrics:
    """Tracks and analyzes learning system performance metrics"""
    
    def __init__(self, learning_engine):
        self.learning_engine = learning_engine
        self.logger = logging.getLogger(__name__)
        self.metrics_history = []
        self.metrics_retention_days = 30
    
    async def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive learning system metrics"""
        try:
            now = datetime.utcnow()
            
            metrics = {
                'timestamp': now.isoformat(),
                'learning_velocity': await self._calculate_learning_velocity(),
                'pattern_discovery_rate': await self._calculate_pattern_discovery_rate(),
                'effectiveness_trends': await self._calculate_effectiveness_trends(),
                'learning_diversity': await self._calculate_learning_diversity(),
                'application_success_rate': await self._calculate_application_success_rate(),
                'knowledge_growth': await self._calculate_knowledge_growth(),
                'agent_learning_distribution': await self._calculate_agent_distribution(),
                'learning_type_distribution': await self._calculate_learning_type_distribution(),
                'improvement_impact': await self._calculate_improvement_impact()
            }
            
            # Store metrics for trend analysis
            self.metrics_history.append(metrics)
            
            # Clean up old metrics
            cutoff_date = now - timedelta(days=self.metrics_retention_days)
            self.metrics_history = [
                m for m in self.metrics_history 
                if datetime.fromisoformat(m['timestamp']) > cutoff_date
            ]
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to calculate learning metrics: {str(e)}")
            return {}
    
    async def _calculate_learning_velocity(self) -> float:
        """Calculate rate of new learning per day"""
        try:
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_records = [
                r for r in self.learning_engine.learning_records
                if r.timestamp > recent_cutoff
            ]
            
            if not recent_records:
                return 0.0
            
            # Calculate daily average
            return len(recent_records) / 7.0
            
        except Exception as e:
            self.logger.error(f"Failed to calculate learning velocity: {str(e)}")
            return 0.0
    
    async def _calculate_pattern_discovery_rate(self) -> float:
        """Calculate rate of new pattern discovery"""
        try:
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_patterns = [
                p for p in self.learning_engine.patterns.values()
                if p.last_seen > recent_cutoff
            ]
            
            return len(recent_patterns) / 7.0
            
        except Exception as e:
            self.logger.error(f"Failed to calculate pattern discovery rate: {str(e)}")
            return 0.0
    
    async def _calculate_effectiveness_trends(self) -> Dict[str, float]:
        """Calculate effectiveness trends over time"""
        try:
            recent_cutoff = datetime.utcnow() - timedelta(days=30)
            recent_records = [
                r for r in self.learning_engine.learning_records
                if r.timestamp > recent_cutoff
            ]
            
            if not recent_records:
                return {'current': 0.0, 'trend': 0.0}
            
            # Split into two periods for trend calculation
            mid_point = recent_cutoff + timedelta(days=15)
            
            earlier_records = [r for r in recent_records if r.timestamp < mid_point]
            later_records = [r for r in recent_records if r.timestamp >= mid_point]
            
            earlier_avg = (
                sum(r.effectiveness_score for r in earlier_records) / len(earlier_records)
                if earlier_records else 0.0
            )
            
            later_avg = (
                sum(r.effectiveness_score for r in later_records) / len(later_records)
                if later_records else 0.0
            )
            
            current_avg = sum(r.effectiveness_score for r in recent_records) / len(recent_records)
            trend = later_avg - earlier_avg
            
            return {
                'current': current_avg,
                'trend': trend
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate effectiveness trends: {str(e)}")
            return {'current': 0.0, 'trend': 0.0}
    
    async def _calculate_learning_diversity(self) -> float:
        """Calculate diversity of learning types and sources"""
        try:
            if not self.learning_engine.learning_records:
                return 0.0
            
            # Calculate entropy of learning types
            learning_types = [r.learning_type for r in self.learning_engine.learning_records]
            type_counts = {}
            
            for lt in learning_types:
                type_counts[lt] = type_counts.get(lt, 0) + 1
            
            total = len(learning_types)
            entropy = 0.0
            
            for count in type_counts.values():
                p = count / total
                if p > 0:
                    entropy -= p * np.log2(p)
            
            # Normalize by maximum possible entropy
            max_entropy = np.log2(len(type_counts)) if type_counts else 0
            
            return entropy / max_entropy if max_entropy > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Failed to calculate learning diversity: {str(e)}")
            return 0.0
    
    async def _calculate_application_success_rate(self) -> float:
        """Calculate success rate of applying learned patterns"""
        try:
            applied_records = [r for r in self.learning_engine.learning_records if r.applied]
            
            if not self.learning_engine.learning_records:
                return 0.0
            
            return len(applied_records) / len(self.learning_engine.learning_records)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate application success rate: {str(e)}")
            return 0.0
    
    async def _calculate_knowledge_growth(self) -> Dict[str, float]:
        """Calculate knowledge base growth metrics"""
        try:
            # This would integrate with the knowledge base system
            # For now, we'll estimate based on learning records
            
            recent_cutoff = datetime.utcnow() - timedelta(days=30)
            recent_records = [
                r for r in self.learning_engine.learning_records
                if r.timestamp > recent_cutoff
            ]
            
            high_value_records = [r for r in recent_records if r.effectiveness_score > 0.7]
            
            return {
                'total_new_knowledge': len(recent_records),
                'high_value_knowledge': len(high_value_records),
                'knowledge_quality_ratio': (
                    len(high_value_records) / len(recent_records)
                    if recent_records else 0.0
                )
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate knowledge growth: {str(e)}")
            return {'total_new_knowledge': 0, 'high_value_knowledge': 0, 'knowledge_quality_ratio': 0.0}
    
    async def _calculate_agent_distribution(self) -> Dict[str, int]:
        """Calculate learning distribution across agents"""
        try:
            agent_counts = {}
            
            for record in self.learning_engine.learning_records:
                agent_id = record.agent_id
                agent_counts[agent_id] = agent_counts.get(agent_id, 0) + 1
            
            return agent_counts
            
        except Exception as e:
            self.logger.error(f"Failed to calculate agent distribution: {str(e)}")
            return {}
    
    async def _calculate_learning_type_distribution(self) -> Dict[str, int]:
        """Calculate distribution of learning types"""
        try:
            type_counts = {}
            
            for record in self.learning_engine.learning_records:
                learning_type = record.learning_type
                type_counts[learning_type] = type_counts.get(learning_type, 0) + 1
            
            return type_counts
            
        except Exception as e:
            self.logger.error(f"Failed to calculate learning type distribution: {str(e)}")
            return {}
    
    async def _calculate_improvement_impact(self) -> Dict[str, float]:
        """Calculate the impact of improvements on system performance"""
        try:
            if len(self.metrics_history) < 2:
                return {'velocity_improvement': 0.0, 'effectiveness_improvement': 0.0}
            
            # Compare recent metrics with historical baseline
            current = self.metrics_history[-1]
            baseline = self.metrics_history[0] if len(self.metrics_history) > 5 else self.metrics_history[-2]
            
            velocity_improvement = (
                current.get('learning_velocity', 0) - baseline.get('learning_velocity', 0)
            )
            
            current_eff = current.get('effectiveness_trends', {}).get('current', 0)
            baseline_eff = baseline.get('effectiveness_trends', {}).get('current', 0)
            effectiveness_improvement = current_eff - baseline_eff
            
            return {
                'velocity_improvement': velocity_improvement,
                'effectiveness_improvement': effectiveness_improvement
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate improvement impact: {str(e)}")
            return {'velocity_improvement': 0.0, 'effectiveness_improvement': 0.0}
    
    async def generate_learning_report(self) -> str:
        """Generate comprehensive learning system report"""
        try:
            metrics = await self.calculate_metrics()
            
            report = [
                "# Learning System Performance Report",
                f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "",
                "## Key Metrics",
                f"- Learning Velocity: {metrics.get('learning_velocity', 0):.2f} records/day",
                f"- Pattern Discovery Rate: {metrics.get('pattern_discovery_rate', 0):.2f} patterns/day",
                f"- Application Success Rate: {metrics.get('application_success_rate', 0) * 100:.1f}%",
                f"- Learning Diversity Score: {metrics.get('learning_diversity', 0):.3f}",
                "",
                "## Effectiveness Trends",
                f"- Current Effectiveness: {metrics.get('effectiveness_trends', {}).get('current', 0):.3f}",
                f"- Trend: {metrics.get('effectiveness_trends', {}).get('trend', 0):+.3f}",
                "",
                "## Knowledge Growth",
            ]
            
            knowledge = metrics.get('knowledge_growth', {})
            report.extend([
                f"- New Knowledge Items: {knowledge.get('total_new_knowledge', 0)}",
                f"- High-Value Knowledge: {knowledge.get('high_value_knowledge', 0)}",
                f"- Quality Ratio: {knowledge.get('knowledge_quality_ratio', 0) * 100:.1f}%",
                "",
                "## Learning Distribution",
                ""
            ])
            
            # Add agent distribution
            agent_dist = metrics.get('agent_learning_distribution', {})
            if agent_dist:
                report.append("### By Agent:")
                for agent_id, count in sorted(agent_dist.items(), key=lambda x: x[1], reverse=True)[:10]:
                    report.append(f"- {agent_id}: {count} records")
                report.append("")
            
            # Add learning type distribution
            type_dist = metrics.get('learning_type_distribution', {})
            if type_dist:
                report.append("### By Learning Type:")
                for learning_type, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
                    report.append(f"- {learning_type}: {count} records")
                report.append("")
            
            # Add improvement impact
            impact = metrics.get('improvement_impact', {})
            report.extend([
                "## System Improvements",
                f"- Velocity Improvement: {impact.get('velocity_improvement', 0):+.2f} records/day",
                f"- Effectiveness Improvement: {impact.get('effectiveness_improvement', 0):+.3f}",
                "",
                "## Pattern Summary",
                f"- Active Patterns: {len(self.learning_engine.patterns)}",
                f"- High-Confidence Patterns: {len([p for p in self.learning_engine.patterns.values() if p.confidence > 0.8])}",
                f"- High-Effectiveness Patterns: {len([p for p in self.learning_engine.patterns.values() if p.effectiveness > 0.8])}",
                ""
            ])
            
            return "\n".join(report)
            
        except Exception as e:
            self.logger.error(f"Failed to generate learning report: {str(e)}")
            return "Error generating learning report"


class LearningVisualizer:
    """Creates visualizations for learning system analytics"""
    
    def __init__(self, learning_engine, metrics_calculator):
        self.learning_engine = learning_engine
        self.metrics = metrics_calculator
        self.logger = logging.getLogger(__name__)
    
    async def create_learning_dashboard_data(self) -> Dict[str, Any]:
        """Create data structure for learning dashboard visualization"""
        try:
            # Get current metrics
            current_metrics = await self.metrics.calculate_metrics()
            
            # Prepare timeline data
            timeline_data = await self._prepare_timeline_data()
            
            # Prepare effectiveness heatmap data
            effectiveness_heatmap = await self._prepare_effectiveness_heatmap()
            
            # Prepare pattern network data
            pattern_network = await self._prepare_pattern_network_data()
            
            dashboard_data = {
                'summary': {
                    'total_records': len(self.learning_engine.learning_records),
                    'active_patterns': len(self.learning_engine.patterns),
                    'learning_velocity': current_metrics.get('learning_velocity', 0),
                    'avg_effectiveness': current_metrics.get('effectiveness_trends', {}).get('current', 0)
                },
                'timeline': timeline_data,
                'effectiveness_heatmap': effectiveness_heatmap,
                'pattern_network': pattern_network,
                'learning_distribution': {
                    'by_type': current_metrics.get('learning_type_distribution', {}),
                    'by_agent': current_metrics.get('agent_learning_distribution', {})
                },
                'trends': {
                    'effectiveness': current_metrics.get('effectiveness_trends', {}),
                    'velocity_history': [m.get('learning_velocity', 0) for m in self.metrics.metrics_history],
                    'pattern_discovery_history': [m.get('pattern_discovery_rate', 0) for m in self.metrics.metrics_history]
                }
            }
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Failed to create dashboard data: {str(e)}")
            return {}
    
    async def _prepare_timeline_data(self) -> List[Dict[str, Any]]:
        """Prepare timeline data for visualization"""
        try:
            # Group records by day
            daily_data = {}
            
            for record in self.learning_engine.learning_records:
                date_key = record.timestamp.date().isoformat()
                
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'date': date_key,
                        'total_records': 0,
                        'avg_effectiveness': 0.0,
                        'learning_types': {}
                    }
                
                daily_data[date_key]['total_records'] += 1
                daily_data[date_key]['avg_effectiveness'] += record.effectiveness_score
                
                lt = record.learning_type
                if lt not in daily_data[date_key]['learning_types']:
                    daily_data[date_key]['learning_types'][lt] = 0
                daily_data[date_key]['learning_types'][lt] += 1
            
            # Calculate averages and sort by date
            timeline = []
            for date_key, data in sorted(daily_data.items()):
                if data['total_records'] > 0:
                    data['avg_effectiveness'] /= data['total_records']
                timeline.append(data)
            
            return timeline
            
        except Exception as e:
            self.logger.error(f"Failed to prepare timeline data: {str(e)}")
            return []
    
    async def _prepare_effectiveness_heatmap(self) -> List[Dict[str, Any]]:
        """Prepare effectiveness heatmap data"""
        try:
            # Create agent x learning_type effectiveness matrix
            heatmap_data = []
            
            # Get unique agents and learning types
            agents = set(r.agent_id for r in self.learning_engine.learning_records)
            learning_types = set(r.learning_type for r in self.learning_engine.learning_records)
            
            for agent in agents:
                for learning_type in learning_types:
                    # Find records for this agent-type combination
                    records = [
                        r for r in self.learning_engine.learning_records
                        if r.agent_id == agent and r.learning_type == learning_type
                    ]
                    
                    if records:
                        avg_effectiveness = sum(r.effectiveness_score for r in records) / len(records)
                        heatmap_data.append({
                            'agent': agent,
                            'learning_type': learning_type,
                            'effectiveness': avg_effectiveness,
                            'count': len(records)
                        })
            
            return heatmap_data
            
        except Exception as e:
            self.logger.error(f"Failed to prepare effectiveness heatmap: {str(e)}")
            return []
    
    async def _prepare_pattern_network_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Prepare pattern network data for visualization"""
        try:
            nodes = []
            edges = []
            
            # Create nodes for patterns
            for pattern in self.learning_engine.patterns.values():
                nodes.append({
                    'id': pattern.id,
                    'type': 'pattern',
                    'label': pattern.description[:30] + "..." if len(pattern.description) > 30 else pattern.description,
                    'effectiveness': pattern.effectiveness,
                    'confidence': pattern.confidence,
                    'frequency': pattern.frequency,
                    'size': max(10, min(50, pattern.frequency * 2))  # Node size based on frequency
                })
            
            # Create edges for related patterns (patterns with similar conditions)
            patterns_list = list(self.learning_engine.patterns.values())
            for i, pattern1 in enumerate(patterns_list):
                for pattern2 in patterns_list[i+1:]:
                    similarity = await self._calculate_pattern_similarity(pattern1, pattern2)
                    if similarity > 0.5:  # Threshold for connection
                        edges.append({
                            'source': pattern1.id,
                            'target': pattern2.id,
                            'weight': similarity,
                            'width': max(1, similarity * 5)  # Edge width based on similarity
                        })
            
            return {
                'nodes': nodes,
                'edges': edges
            }
            
        except Exception as e:
            self.logger.error(f"Failed to prepare pattern network data: {str(e)}")
            return {'nodes': [], 'edges': []}
    
    async def _calculate_pattern_similarity(self, pattern1: Pattern, pattern2: Pattern) -> float:
        """Calculate similarity between two patterns"""
        try:
            # Compare conditions
            common_keys = set(pattern1.conditions.keys()) & set(pattern2.conditions.keys())
            if not common_keys:
                return 0.0
            
            similarity_scores = []
            
            for key in common_keys:
                val1 = pattern1.conditions[key]
                val2 = pattern2.conditions[key]
                
                if isinstance(val1, str) and isinstance(val2, str):
                    # Simple string similarity
                    similarity = len(set(val1.lower().split()) & set(val2.lower().split())) / len(set(val1.lower().split()) | set(val2.lower().split()))
                elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    # Numeric similarity
                    if val1 == 0 and val2 == 0:
                        similarity = 1.0
                    else:
                        similarity = 1.0 - abs(val1 - val2) / (abs(val1) + abs(val2))
                else:
                    similarity = 1.0 if val1 == val2 else 0.0
                
                similarity_scores.append(similarity)
            
            return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
            
        except Exception as e:
            self.logger.error(f"Failed to calculate pattern similarity: {str(e)}")
            return 0.0


# Initialize learning system
async def initialize_learning_system(db_manager, ai_manager, knowledge_base) -> Tuple[LearningEngine, FeedbackProcessor, LearningMetrics, LearningVisualizer]:
    """Initialize the complete learning system"""
    try:
        # Create database tables
        await create_learning_tables(db_manager)
        
        # Initialize learning engine
        learning_engine = LearningEngine(db_manager, ai_manager, knowledge_base)
        await learning_engine.initialize()
        
        # Initialize feedback processor
        feedback_processor = FeedbackProcessor(learning_engine, ai_manager)
        
        # Initialize metrics calculator
        metrics_calculator = LearningMetrics(learning_engine)
        
        # Initialize visualizer
        visualizer = LearningVisualizer(learning_engine, metrics_calculator)
        
        logging.getLogger(__name__).info("Learning system initialized successfully")
        
        return learning_engine, feedback_processor, metrics_calculator, visualizer
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to initialize learning system: {str(e)}")
        raise


# Example usage and testing functions
async def test_learning_system(learning_engine: LearningEngine, feedback_processor: FeedbackProcessor):
    """Test the learning system with sample data"""
    try:
        # Record some sample learning
        await learning_engine.record_learning(
            agent_id="test_agent_1",
            task_id="task_001",
            learning_type="improvement",
            content={
                "optimization": "reduced response time by caching",
                "performance_gain": 0.3,
                "method": "caching"
            },
            effectiveness_score=0.8
        )
        
        # Process sample feedback
        sample_feedback = {
            "message": "The response was helpful but could be more detailed",
            "rating": 4,
            "suggestions": ["add more examples", "improve clarity"]
        }
        
        await feedback_processor.process_user_feedback(
            agent_id="test_agent_1",
            task_id="task_001",
            feedback=sample_feedback
        )
        
        # Get learning insights
        insights = await learning_engine.get_learning_insights()
        
        logging.getLogger(__name__).info(f"Learning system test completed. Insights: {insights}")
        
        return True
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Learning system test failed: {str(e)}")
        return False