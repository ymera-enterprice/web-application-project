import asyncio
import logging
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue, PriorityQueue
import pickle
import hashlib
import numpy as np
from enum import Enum
import traceback

# External libraries (install via requirements.txt)
import openai
import anthropic
import google.generativeai as genai
from groq import Groq
import pinecone
from pinecone import Pinecone, ServerlessSpec
import requests
from github import Github
import tiktoken

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('multi_agent_learning.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AgentType(Enum):
    REASONING = "reasoning"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    CODING = "coding"
    RESEARCH = "research"
    SYNTHESIS = "synthesis"

class LearningMode(Enum):
    SUPERVISED = "supervised"
    REINFORCEMENT = "reinforcement"
    SELF_SUPERVISED = "self_supervised"
    META_LEARNING = "meta_learning"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Experience:
    """Represents a learning experience with context and outcome"""
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

@dataclass
class Task:
    """Represents a task in the multi-agent system"""
    task_id: str
    task_type: str
    priority: TaskPriority
    data: Dict[str, Any]
    created_at: datetime
    deadline: Optional[datetime]
    assigned_agent: Optional[str]
    dependencies: List[str]
    status: str = "pending"

class KnowledgeGraph:
    """Advanced knowledge graph for storing and retrieving learned patterns"""
    
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.patterns = {}
        self.embeddings = {}
        self.lock = threading.RLock()
    
    def add_knowledge(self, concept: str, properties: Dict[str, Any], 
                     embedding: Optional[List[float]] = None):
        """Add knowledge node with properties and embedding"""
        with self.lock:
            node_id = hashlib.md5(concept.encode()).hexdigest()
            self.nodes[node_id] = {
                'concept': concept,
                'properties': properties,
                'created_at': datetime.now(),
                'access_count': 0,
                'last_accessed': datetime.now()
            }
            if embedding:
                self.embeddings[node_id] = embedding
    
    def add_relationship(self, concept1: str, concept2: str, 
                        relationship_type: str, strength: float):
        """Add relationship between concepts"""
        with self.lock:
            id1 = hashlib.md5(concept1.encode()).hexdigest()
            id2 = hashlib.md5(concept2.encode()).hexdigest()
            edge_id = f"{id1}-{id2}"
            
            self.edges[edge_id] = {
                'from': id1,
                'to': id2,
                'type': relationship_type,
                'strength': strength,
                'created_at': datetime.now()
            }
    
    def find_related_concepts(self, concept: str, max_distance: int = 3) -> List[str]:
        """Find concepts related to the given concept within max_distance"""
        with self.lock:
            concept_id = hashlib.md5(concept.encode()).hexdigest()
            if concept_id not in self.nodes:
                return []
            
            visited = set()
            queue = [(concept_id, 0)]
            related = []
            
            while queue:
                current_id, distance = queue.pop(0)
                if current_id in visited or distance > max_distance:
                    continue
                
                visited.add(current_id)
                if distance > 0:
                    related.append(self.nodes[current_id]['concept'])
                
                # Find connected nodes
                for edge_id, edge in self.edges.items():
                    if edge['from'] == current_id:
                        queue.append((edge['to'], distance + 1))
                    elif edge['to'] == current_id:
                        queue.append((edge['from'], distance + 1))
            
            return related

class LearningEngine:
    """Advanced learning engine with multiple learning modes"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        self.experience_buffer = []
        self.learning_metrics = {
            'total_experiences': 0,
            'success_rate': 0.0,
            'average_performance': 0.0,
            'learning_rate': 0.01
        }
        self.pattern_detector = PatternDetector()
        self.meta_learner = MetaLearner()
        self.lock = threading.RLock()
    
    def process_experience(self, experience: Experience) -> Dict[str, Any]:
        """Process and learn from a single experience"""
        with self.lock:
            self.experience_buffer.append(experience)
            
            # Extract patterns
            patterns = self.pattern_detector.detect_patterns([experience])
            
            # Update knowledge graph
            for pattern in patterns:
                self.knowledge_graph.add_knowledge(
                    concept=pattern['pattern_id'],
                    properties=pattern,
                    embedding=pattern.get('embedding')
                )
            
            # Update metrics
            self._update_metrics(experience)
            
            # Trigger meta-learning
            insights = self.meta_learner.generate_insights(
                self.experience_buffer[-100:]  # Last 100 experiences
            )
            
            return {
                'patterns_learned': len(patterns),
                'performance_impact': self._calculate_performance_impact(experience),
                'meta_insights': insights,
                'updated_metrics': self.learning_metrics.copy()
            }
    
    def _update_metrics(self, experience: Experience):
        """Update learning metrics based on experience"""
        self.learning_metrics['total_experiences'] += 1
        
        # Update success rate
        success_count = sum(1 for exp in self.experience_buffer if exp.success)
        self.learning_metrics['success_rate'] = success_count / len(self.experience_buffer)
        
        # Update average performance
        avg_score = sum(exp.feedback_score for exp in self.experience_buffer) / len(self.experience_buffer)
        self.learning_metrics['average_performance'] = avg_score
        
        # Adaptive learning rate
        if len(self.experience_buffer) > 10:
            recent_performance = sum(exp.feedback_score for exp in self.experience_buffer[-10:]) / 10
            if recent_performance > self.learning_metrics['average_performance']:
                self.learning_metrics['learning_rate'] *= 1.01
            else:
                self.learning_metrics['learning_rate'] *= 0.99
    
    def _calculate_performance_impact(self, experience: Experience) -> float:
        """Calculate the performance impact of an experience"""
        if len(self.experience_buffer) < 2:
            return 0.0
        
        recent_avg = sum(exp.feedback_score for exp in self.experience_buffer[-5:]) / min(5, len(self.experience_buffer))
        previous_avg = sum(exp.feedback_score for exp in self.experience_buffer[-10:-5]) / min(5, len(self.experience_buffer) - 5)
        
        return recent_avg - previous_avg

class PatternDetector:
    """Detects patterns in experiences and behaviors"""
    
    def __init__(self):
        self.pattern_cache = {}
        self.similarity_threshold = 0.8
    
    def detect_patterns(self, experiences: List[Experience]) -> List[Dict[str, Any]]:
        """Detect patterns in a list of experiences"""
        patterns = []
        
        # Group experiences by task type
        grouped_experiences = {}
        for exp in experiences:
            if exp.task_type not in grouped_experiences:
                grouped_experiences[exp.task_type] = []
            grouped_experiences[exp.task_type].append(exp)
        
        # Detect patterns within each group
        for task_type, exp_group in grouped_experiences.items():
            if len(exp_group) < 2:
                continue
            
            # Performance patterns
            performance_pattern = self._detect_performance_pattern(exp_group)
            if performance_pattern:
                patterns.append(performance_pattern)
            
            # Input-output patterns
            io_patterns = self._detect_io_patterns(exp_group)
            patterns.extend(io_patterns)
            
            # Temporal patterns
            temporal_patterns = self._detect_temporal_patterns(exp_group)
            patterns.extend(temporal_patterns)
        
        return patterns
    
    def _detect_performance_pattern(self, experiences: List[Experience]) -> Optional[Dict[str, Any]]:
        """Detect performance trends in experiences"""
        if len(experiences) < 3:
            return None
        
        scores = [exp.feedback_score for exp in sorted(experiences, key=lambda x: x.timestamp)]
        
        # Simple trend detection
        improvements = sum(1 for i in range(1, len(scores)) if scores[i] > scores[i-1])
        degradations = sum(1 for i in range(1, len(scores)) if scores[i] < scores[i-1])
        
        if improvements > degradations * 1.5:
            trend = "improving"
        elif degradations > improvements * 1.5:
            trend = "degrading"
        else:
            trend = "stable"
        
        return {
            'pattern_id': f"performance_{trend}_{experiences[0].task_type}",
            'type': 'performance',
            'trend': trend,
            'confidence': abs(improvements - degradations) / len(scores),
            'task_type': experiences[0].task_type,
            'sample_size': len(experiences)
        }
    
    def _detect_io_patterns(self, experiences: List[Experience]) -> List[Dict[str, Any]]:
        """Detect input-output patterns"""
        patterns = []
        
        # Simple pattern: successful inputs tend to have certain characteristics
        successful_exps = [exp for exp in experiences if exp.success]
        failed_exps = [exp for exp in experiences if not exp.success]
        
        if len(successful_exps) > 0 and len(failed_exps) > 0:
            # Analyze input differences (simplified)
            success_keys = set()
            for exp in successful_exps:
                success_keys.update(exp.input_data.keys())
            
            fail_keys = set()
            for exp in failed_exps:
                fail_keys.update(exp.input_data.keys())
            
            unique_success_keys = success_keys - fail_keys
            if unique_success_keys:
                patterns.append({
                    'pattern_id': f"success_inputs_{experiences[0].task_type}",
                    'type': 'input_success',
                    'success_indicators': list(unique_success_keys),
                    'confidence': len(unique_success_keys) / len(success_keys),
                    'task_type': experiences[0].task_type
                })
        
        return patterns
    
    def _detect_temporal_patterns(self, experiences: List[Experience]) -> List[Dict[str, Any]]:
        """Detect temporal patterns in execution"""
        patterns = []
        
        # Execution time patterns
        exec_times = [(exp.timestamp, exp.execution_time) for exp in experiences]
        exec_times.sort()
        
        if len(exec_times) > 5:
            times = [t[1] for t in exec_times]
            avg_time = sum(times) / len(times)
            
            # Check if execution time is improving
            recent_avg = sum(times[-3:]) / 3
            early_avg = sum(times[:3]) / 3
            
            if recent_avg < early_avg * 0.8:  # 20% improvement
                patterns.append({
                    'pattern_id': f"execution_optimization_{experiences[0].task_type}",
                    'type': 'temporal_optimization',
                    'improvement_ratio': early_avg / recent_avg,
                    'confidence': 0.8,
                    'task_type': experiences[0].task_type
                })
        
        return patterns

class MetaLearner:
    """Meta-learning component for learning how to learn better"""
    
    def __init__(self):
        self.meta_patterns = {}
        self.learning_strategies = {}
        self.adaptation_history = []
    
    def generate_insights(self, experiences: List[Experience]) -> Dict[str, Any]:
        """Generate meta-learning insights from experiences"""
        if len(experiences) < 10:
            return {'insights': [], 'recommendations': []}
        
        insights = []
        recommendations = []
        
        # Analyze learning velocity
        learning_velocity = self._analyze_learning_velocity(experiences)
        insights.append(learning_velocity)
        
        # Analyze agent performance variations
        agent_analysis = self._analyze_agent_performance(experiences)
        insights.append(agent_analysis)
        
        # Generate strategy recommendations
        strategy_recs = self._recommend_strategies(experiences)
        recommendations.extend(strategy_recs)
        
        return {
            'insights': insights,
            'recommendations': recommendations,
            'meta_score': self._calculate_meta_score(experiences)
        }
    
    def _analyze_learning_velocity(self, experiences: List[Experience]) -> Dict[str, Any]:
        """Analyze how quickly the system is learning"""
        time_sorted = sorted(experiences, key=lambda x: x.timestamp)
        
        # Calculate improvement rate over time
        window_size = 5
        improvement_rates = []
        
        for i in range(window_size, len(time_sorted)):
            current_window = time_sorted[i-window_size:i]
            previous_window = time_sorted[i-window_size*2:i-window_size]
            
            if len(previous_window) == window_size:
                current_avg = sum(exp.feedback_score for exp in current_window) / window_size
                previous_avg = sum(exp.feedback_score for exp in previous_window) / window_size
                improvement_rates.append(current_avg - previous_avg)
        
        if improvement_rates:
            avg_improvement = sum(improvement_rates) / len(improvement_rates)
            return {
                'type': 'learning_velocity',
                'average_improvement_rate': avg_improvement,
                'velocity_trend': 'accelerating' if avg_improvement > 0 else 'decelerating',
                'confidence': min(abs(avg_improvement) * 10, 1.0)
            }
        
        return {'type': 'learning_velocity', 'status': 'insufficient_data'}
    
    def _analyze_agent_performance(self, experiences: List[Experience]) -> Dict[str, Any]:
        """Analyze performance variations across agents"""
        agent_performance = {}
        
        for exp in experiences:
            if exp.agent_id not in agent_performance:
                agent_performance[exp.agent_id] = []
            agent_performance[exp.agent_id].append(exp.feedback_score)
        
        agent_stats = {}
        for agent_id, scores in agent_performance.items():
            if len(scores) > 1:
                agent_stats[agent_id] = {
                    'average_score': sum(scores) / len(scores),
                    'consistency': 1.0 - (max(scores) - min(scores)),
                    'sample_size': len(scores)
                }
        
        return {
            'type': 'agent_performance_analysis',
            'agent_statistics': agent_stats,
            'top_performer': max(agent_stats.items(), 
                               key=lambda x: x[1]['average_score'])[0] if agent_stats else None
        }
    
    def _recommend_strategies(self, experiences: List[Experience]) -> List[Dict[str, Any]]:
        """Recommend learning strategies based on analysis"""
        recommendations = []
        
        # Analyze failure patterns
        failures = [exp for exp in experiences if not exp.success]
        if len(failures) > len(experiences) * 0.3:  # High failure rate
            recommendations.append({
                'type': 'strategy',
                'recommendation': 'increase_exploration',
                'reason': 'high_failure_rate',
                'priority': 'high',
                'expected_impact': 0.7
            })
        
        # Analyze task distribution
        task_types = {}
        for exp in experiences:
            task_types[exp.task_type] = task_types.get(exp.task_type, 0) + 1
        
        if len(task_types) < 3:  # Low task diversity
            recommendations.append({
                'type': 'strategy',
                'recommendation': 'diversify_tasks',
                'reason': 'low_task_diversity',
                'priority': 'medium',
                'expected_impact': 0.5
            })
        
        return recommendations
    
    def _calculate_meta_score(self, experiences: List[Experience]) -> float:
        """Calculate overall meta-learning score"""
        if len(experiences) < 5:
            return 0.0
        
        # Factors: success rate, improvement trend, consistency
        success_rate = sum(1 for exp in experiences if exp.success) / len(experiences)
        
        # Improvement trend
        sorted_exps = sorted(experiences, key=lambda x: x.timestamp)
        first_half = sorted_exps[:len(sorted_exps)//2]
        second_half = sorted_exps[len(sorted_exps)//2:]
        
        first_avg = sum(exp.feedback_score for exp in first_half) / len(first_half)
        second_avg = sum(exp.feedback_score for exp in second_half) / len(second_half)
        improvement = max(0, (second_avg - first_avg))
        
        # Consistency (inverse of standard deviation)
        scores = [exp.feedback_score for exp in experiences]
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        consistency = 1.0 / (1.0 + variance)
        
        meta_score = (success_rate * 0.4 + improvement * 0.3 + consistency * 0.3)
        return min(1.0, max(0.0, meta_score))

class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, agent_id: str, agent_type: AgentType, api_keys: Dict[str, str]):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.api_keys = api_keys
        self.experience_history = []
        self.performance_metrics = {
            'tasks_completed': 0,
            'success_rate': 0.0,
            'average_score': 0.0,
            'specializations': []
        }
        self.learning_preferences = {}
        self.lock = threading.RLock()
    
    @abstractmethod
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a task and return results"""
        pass
    
    @abstractmethod
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from task feedback"""
        pass
    
    def update_performance(self, experience: Experience):
        """Update agent performance metrics"""
        with self.lock:
            self.experience_history.append(experience)
            self.performance_metrics['tasks_completed'] += 1
            
            # Update success rate
            successes = sum(1 for exp in self.experience_history if exp.success)
            self.performance_metrics['success_rate'] = successes / len(self.experience_history)
            
            # Update average score
            total_score = sum(exp.feedback_score for exp in self.experience_history)
            self.performance_metrics['average_score'] = total_score / len(self.experience_history)

class ReasoningAgent(BaseAgent):
    """Agent specialized in logical reasoning and problem solving"""
    
    def __init__(self, agent_id: str, api_keys: Dict[str, str]):
        super().__init__(agent_id, AgentType.REASONING, api_keys)
        self.client = anthropic.Anthropic(api_key=api_keys.get('ANTHROPIC_API_KEY'))
        self.reasoning_patterns = []
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process reasoning tasks using Claude"""
        try:
            start_time = time.time()
            
            # Construct reasoning prompt
            prompt = self._build_reasoning_prompt(task)
            
            # Get reasoning response
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            execution_time = time.time() - start_time
            
            # Parse reasoning steps
            reasoning_steps = self._parse_reasoning_response(message.content[0].text)
            
            return {
                'agent_id': self.agent_id,
                'result': reasoning_steps,
                'execution_time': execution_time,
                'confidence': self._calculate_confidence(reasoning_steps),
                'reasoning_chain': reasoning_steps.get('steps', []),
                'conclusion': reasoning_steps.get('conclusion', ''),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"ReasoningAgent {self.agent_id} error: {str(e)}")
            return {
                'agent_id': self.agent_id,
                'result': None,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'status': 'error'
            }
    
    def _build_reasoning_prompt(self, task: Task) -> str:
        """Build a reasoning-focused prompt"""
        base_prompt = f"""
        You are an expert reasoning agent. Analyze the following problem step by step:
        
        Task Type: {task.task_type}
        Problem: {task.data.get('problem', '')}
        Context: {task.data.get('context', '')}
        
        Please provide:
        1. Step-by-step logical analysis
        2. Key assumptions and their validity
        3. Alternative perspectives or approaches
        4. Final conclusion with confidence level
        5. Potential weaknesses in the reasoning
        
        Format your response as JSON with the structure:
        {
            "steps": [list of reasoning steps],
            "assumptions": [list of assumptions],
            "alternatives": [alternative approaches],
            "conclusion": "final conclusion",
            "confidence": confidence_score_0_to_1,
            "weaknesses": [potential weaknesses]
        }
        """
        
        # Add previous successful patterns if available
        if self.reasoning_patterns:
            base_prompt += f"\n\nPrevious successful reasoning patterns:\n{json.dumps(self.reasoning_patterns[-3:], indent=2)}"
        
        return base_prompt
    
    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """Parse the reasoning response"""
        try:
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: parse unstructured response
                return {
                    'steps': [response],
                    'conclusion': response[-200:],  # Last 200 chars as conclusion
                    'confidence': 0.5,
                    'assumptions': [],
                    'alternatives': [],
                    'weaknesses': []
                }
        except Exception as e:
            logger.error(f"Failed to parse reasoning response: {str(e)}")
            return {
                'steps': [response],
                'conclusion': 'Failed to parse structured response',
                'confidence': 0.3,
                'assumptions': [],
                'alternatives': [],
                'weaknesses': ['Response parsing failed']
            }
    
    def _calculate_confidence(self, reasoning_result: Dict[str, Any]) -> float:
        """Calculate confidence based on reasoning quality"""
        base_confidence = reasoning_result.get('confidence', 0.5)
        
        # Adjust based on completeness
        completeness_bonus = 0.0
        if reasoning_result.get('steps'):
            completeness_bonus += 0.1
        if reasoning_result.get('assumptions'):
            completeness_bonus += 0.05
        if reasoning_result.get('alternatives'):
            completeness_bonus += 0.05
        
        return min(1.0, base_confidence + completeness_bonus)
    
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from reasoning task feedback"""
        experience = Experience(
            experience_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_type=task.task_type,
            input_data={'task_data': task.data},
            output_data=result,
            feedback_score=feedback.get('score', 0.0),
            execution_time=result.get('execution_time', 0.0),
            timestamp=datetime.now(),
            context={'task_priority': task.priority.value},
            success=feedback.get('success', False),
            learned_patterns=[]
        )
        
        # Extract reasoning patterns for future use
        if experience.success and result.get('result'):
            reasoning_pattern = {
                'task_type': task.task_type,
                'successful_approach': result['result'].get('steps', []),
                'confidence_achieved': result.get('confidence', 0.0),
                'timestamp': datetime.now().isoformat()
            }
            self.reasoning_patterns.append(reasoning_pattern)
            
            # Keep only recent patterns
            if len(self.reasoning_patterns) > 10:
                self.reasoning_patterns = self.reasoning_patterns[-10:]
            
            experience.learned_patterns = [f"reasoning_pattern_{len(self.reasoning_patterns)}"]
        
        self.update_performance(experience)
        return experience

class CreativeAgent(BaseAgent):
    """Agent specialized in creative tasks and content generation"""
    
    def __init__(self, agent_id: str, api_keys: Dict[str, str]):
        super().__init__(agent_id, AgentType.CREATIVE, api_keys)
        genai.configure(api_key=api_keys.get('GOOGLE_API_KEY'))
        self.model = genai.GenerativeModel('gemini-pro')
        self.creative_styles = []
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process creative tasks using Gemini"""
        try:
            start_time = time.time()
            
            # Build creative prompt
            prompt = self._build_creative_prompt(task)
            
            # Generate creative content
            response = self.model.generate_content(prompt)
            execution_time = time.time() - start_time
            
            # Analyze creativity metrics
            creativity_metrics = self._analyze_creativity(response.text, task)
            
            return {
                'agent_id': self.agent_id,
                'result': {
                    'content': response.text,
                    'creativity_metrics': creativity_metrics,
                    'style_detected': creativity_metrics.get('style', 'unknown')
                },
                'execution_time': execution_time,
                'confidence': creativity_metrics.get('confidence', 0.7),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"CreativeAgent {self.agent_id} error: {str(e)}")
            return {
                'agent_id': self.agent_id,
                'result': None,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'status': 'error'
            }
    
    def _build_creative_prompt(self, task: Task) -> str:
        """Build creative prompt based on task requirements"""
        creative_type = task.data.get('creative_type', 'general')
        theme = task.data.get('theme', '')
        style = task.data.get('style', 'engaging')
        
        prompt = f"""
        Create {creative_type} content with the following specifications:
        
        Theme: {theme}
        Style: {style}
        Target audience: {task.data.get('audience', 'general')}
        Length: {task.data.get('length', 'medium')}
        Tone: {task.data.get('tone', 'professional')}
        
        Requirements:
        - Be original and engaging
        - Include creative elements that capture attention
        - Ensure content is relevant to the theme
        - Use appropriate language for the target audience
        """
        
        # Add successful styles if available
        if self.creative_styles:
            recent_styles = [s for s in self.creative_styles if s.get('success_score', 0) > 0.7]
            if recent_styles:
                prompt += f"\n\nSuccessful creative approaches from previous work:\n"
                for style in recent_styles[-3:]:
                    prompt += f"- {style.get('approach', '')}\n"
        
        return prompt
    
    def _analyze_creativity(self, content: str, task: Task) -> Dict[str, Any]:
        """Analyze creativity metrics of generated content"""
        metrics = {
            'word_count': len(content.split()),
            'unique_words': len(set(content.lower().split())),
            'sentiment': 'positive',  # Simplified
            'style': 'creative',
            'confidence': 0.7
        }
        
        # Analyze vocabulary diversity
        if metrics['word_count'] > 0:
            vocabulary_diversity = metrics['unique_words'] / metrics['word_count']
            metrics['vocabulary_diversity'] = vocabulary_diversity
            
            # Higher diversity often indicates more creativity
            if vocabulary_diversity > 0.7:
                metrics['creativity_score'] = 0.8
            elif vocabulary_diversity > 0.5:
                metrics['creativity_score'] = 0.6
            else:
                metrics['creativity_ else:
                metrics['creativity_score'] = 0.4
        else:
            metrics['creativity_score'] = 0.0
            
        # Detect creative style patterns
        if 'metaphor' in content.lower() or 'like' in content.lower():
            metrics['style'] = 'metaphorical'
        elif '!' in content or '?' in content:
            metrics['style'] = 'expressive'
        elif len([s for s in content.split('.') if len(s.strip()) > 0]) > 5:
            metrics['style'] = 'detailed'
            
        return metrics
    
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from creative task feedback"""
        experience = Experience(
            experience_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_type=task.task_type,
            input_data={'task_data': task.data},
            output_data=result,
            feedback_score=feedback.get('score', 0.0),
            execution_time=result.get('execution_time', 0.0),
            timestamp=datetime.now(),
            context={'task_priority': task.priority.value},
            success=feedback.get('success', False),
            learned_patterns=[]
        )
        
        # Extract creative styles for future use
        if experience.success and result.get('result'):
            creativity_metrics = result['result'].get('creativity_metrics', {})
            creative_style = {
                'task_type': task.task_type,
                'style': creativity_metrics.get('style', 'unknown'),
                'approach': task.data.get('style', 'default'),
                'success_score': feedback.get('score', 0.0),
                'creativity_score': creativity_metrics.get('creativity_score', 0.0),
                'timestamp': datetime.now().isoformat()
            }
            self.creative_styles.append(creative_style)
            
            # Keep only successful styles
            if len(self.creative_styles) > 15:
                self.creative_styles = sorted(
                    self.creative_styles, 
                    key=lambda x: x.get('success_score', 0), 
                    reverse=True
                )[:15]
            
            experience.learned_patterns = [f"creative_style_{len(self.creative_styles)}"]
        
        self.update_performance(experience)
        return experience

class AnalyticalAgent(BaseAgent):
    """Agent specialized in data analysis and statistical reasoning"""
    
    def __init__(self, agent_id: str, api_keys: Dict[str, str]):
        super().__init__(agent_id, AgentType.ANALYTICAL, api_keys)
        self.openai_client = openai.OpenAI(api_key=api_keys.get('OPENAI_API_KEY'))
        self.analysis_patterns = []
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process analytical tasks using GPT-4"""
        try:
            start_time = time.time()
            
            # Build analytical prompt
            prompt = self._build_analytical_prompt(task)
            
            # Get analytical response
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.3
            )
            
            execution_time = time.time() - start_time
            
            # Parse analytical results
            analysis_result = self._parse_analytical_response(response.choices[0].message.content)
            
            return {
                'agent_id': self.agent_id,
                'result': analysis_result,
                'execution_time': execution_time,
                'confidence': self._calculate_analytical_confidence(analysis_result),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"AnalyticalAgent {self.agent_id} error: {str(e)}")
            return {
                'agent_id': self.agent_id,
                'result': None,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'status': 'error'
            }
    
    def _build_analytical_prompt(self, task: Task) -> str:
        """Build analytical prompt with data and requirements"""
        data = task.data.get('data', [])
        analysis_type = task.data.get('analysis_type', 'descriptive')
        
        prompt = f"""
        You are an expert data analyst. Perform {analysis_type} analysis on the following data:
        
        Data: {json.dumps(data) if isinstance(data, (list, dict)) else str(data)}
        
        Analysis Requirements:
        - Type: {analysis_type}
        - Focus: {task.data.get('focus', 'general insights')}
        - Metrics needed: {task.data.get('metrics', ['mean', 'median', 'trends'])}
        
        Please provide:
        1. Data summary and key statistics
        2. Trends and patterns identified
        3. Statistical significance of findings
        4. Actionable insights and recommendations
        5. Confidence intervals where applicable
        
        Format as JSON:
        {
            "summary": "data summary",
            "statistics": {"key_metrics": "values"},
            "trends": ["list of trends"],
            "insights": ["actionable insights"],
            "confidence": confidence_score_0_to_1,
            "recommendations": ["specific recommendations"]
        }
        """
        
        return prompt
    
    def _parse_analytical_response(self, response: str) -> Dict[str, Any]:
        """Parse analytical response"""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback parsing
                return {
                    'summary': response[:300],
                    'statistics': {},
                    'trends': [response],
                    'insights': [],
                    'confidence': 0.5,
                    'recommendations': []
                }
        except Exception as e:
            logger.error(f"Failed to parse analytical response: {str(e)}")
            return {
                'summary': 'Analysis parsing failed',
                'statistics': {},
                'trends': [],
                'insights': [],
                'confidence': 0.3,
                'recommendations': []
            }
    
    def _calculate_analytical_confidence(self, analysis_result: Dict[str, Any]) -> float:
        """Calculate confidence in analytical results"""
        base_confidence = analysis_result.get('confidence', 0.5)
        
        # Boost confidence based on completeness
        completeness_score = 0.0
        if analysis_result.get('statistics'):
            completeness_score += 0.2
        if analysis_result.get('trends'):
            completeness_score += 0.2
        if analysis_result.get('insights'):
            completeness_score += 0.1
        
        return min(1.0, base_confidence + completeness_score)
    
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from analytical task feedback"""
        experience = Experience(
            experience_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_type=task.task_type,
            input_data={'task_data': task.data},
            output_data=result,
            feedback_score=feedback.get('score', 0.0),
            execution_time=result.get('execution_time', 0.0),
            timestamp=datetime.now(),
            context={'task_priority': task.priority.value},
            success=feedback.get('success', False),
            learned_patterns=[]
        )
        
        # Store successful analysis patterns
        if experience.success and result.get('result'):
            analysis_pattern = {
                'analysis_type': task.data.get('analysis_type', 'descriptive'),
                'data_characteristics': self._analyze_data_characteristics(task.data.get('data', [])),
                'successful_approach': result['result'].get('summary', ''),
                'confidence_achieved': result.get('confidence', 0.0),
                'timestamp': datetime.now().isoformat()
            }
            self.analysis_patterns.append(analysis_pattern)
            
            if len(self.analysis_patterns) > 12:
                self.analysis_patterns = self.analysis_patterns[-12:]
        
        self.update_performance(experience)
        return experience
    
    def _analyze_data_characteristics(self, data: Any) -> Dict[str, Any]:
        """Analyze characteristics of input data"""
        if isinstance(data, list):
            return {
                'type': 'list',
                'length': len(data),
                'sample_type': type(data[0]).__name__ if data else 'empty'
            }
        elif isinstance(data, dict):
            return {
                'type': 'dict',
                'keys': list(data.keys()),
                'key_count': len(data)
            }
        else:
            return {
                'type': type(data).__name__,
                'length': len(str(data))
            }

class CodingAgent(BaseAgent):
    """Agent specialized in coding tasks and software development"""
    
    def __init__(self, agent_id: str, api_keys: Dict[str, str]):
        super().__init__(agent_id, AgentType.CODING, api_keys)
        self.groq_client = Groq(api_key=api_keys.get('GROQ_API_KEY'))
        self.coding_patterns = []
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process coding tasks using Groq"""
        try:
            start_time = time.time()
            
            # Build coding prompt
            prompt = self._build_coding_prompt(task)
            
            # Generate code
            completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="mixtral-8x7b-32768",
                max_tokens=4000,
                temperature=0.1
            )
            
            execution_time = time.time() - start_time
            
            # Analyze code quality
            code_content = completion.choices[0].message.content
            quality_metrics = self._analyze_code_quality(code_content, task)
            
            return {
                'agent_id': self.agent_id,
                'result': {
                    'code': code_content,
                    'quality_metrics': quality_metrics,
                    'language': task.data.get('language', 'python')
                },
                'execution_time': execution_time,
                'confidence': quality_metrics.get('confidence', 0.7),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"CodingAgent {self.agent_id} error: {str(e)}")
            return {
                'agent_id': self.agent_id,
                'result': None,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'status': 'error'
            }
    
    def _build_coding_prompt(self, task: Task) -> str:
        """Build coding prompt with specifications"""
        language = task.data.get('language', 'python')
        problem = task.data.get('problem', '')
        requirements = task.data.get('requirements', [])
        
        prompt = f"""
        Write {language} code to solve the following problem:
        
        Problem: {problem}
        
        Requirements:
        {chr(10).join(f"- {req}" for req in requirements)}
        
        Additional specifications:
        - Follow best practices for {language}
        - Include proper error handling
        - Add comments for complex logic
        - Ensure code is efficient and readable
        - Include example usage if applicable
        
        Provide complete, working code that solves the problem.
        """
        
        # Add successful patterns if available
        if self.coding_patterns:
            relevant_patterns = [p for p in self.coding_patterns 
                               if p.get('language') == language and p.get('success_score', 0) > 0.7]
            if relevant_patterns:
                prompt += f"\n\nSuccessful coding patterns for {language}:\n"
                for pattern in relevant_patterns[-2:]:
                    prompt += f"- {pattern.get('pattern_description', '')}\n"
        
        return prompt
    
    def _analyze_code_quality(self, code: str, task: Task) -> Dict[str, Any]:
        """Analyze code quality metrics"""
        metrics = {
            'lines_of_code': len([line for line in code.split('\n') if line.strip()]),
            'comment_ratio': 0.0,
            'function_count': 0,
            'complexity_estimate': 'medium',
            'confidence': 0.7
        }
        
        lines = code.split('\n')
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        metrics['comment_ratio'] = len(comment_lines) / max(len(lines), 1)
        
        # Count functions (simple heuristic)
        if 'def ' in code:
            metrics['function_count'] = code.count('def ')
        
        # Estimate complexity
        complexity_indicators = ['for ', 'while ', 'if ', 'try:', 'except:', 'class ']
        complexity_score = sum(code.count(indicator) for indicator in complexity_indicators)
        
        if complexity_score > 10:
            metrics['complexity_estimate'] = 'high'
        elif complexity_score > 5:
            metrics['complexity_estimate'] = 'medium'
        else:
            metrics['complexity_estimate'] = 'low'
        
        # Quality score based on metrics
        quality_score = 0.5
        if metrics['comment_ratio'] > 0.1:
            quality_score += 0.1
        if metrics['function_count'] > 0:
            quality_score += 0.1
        if 10 <= metrics['lines_of_code'] <= 100:
            quality_score += 0.1
        
        metrics['quality_score'] = min(1.0, quality_score)
        return metrics
    
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from coding task feedback"""
        experience = Experience(
            experience_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_type=task.task_type,
            input_data={'task_data': task.data},
            output_data=result,
            feedback_score=feedback.get('score', 0.0),
            execution_time=result.get('execution_time', 0.0),
            timestamp=datetime.now(),
            context={'task_priority': task.priority.value},
            success=feedback.get('success', False),
            learned_patterns=[]
        )
        
        # Extract coding patterns
        if experience.success and result.get('result'):
            quality_metrics = result['result'].get('quality_metrics', {})
            coding_pattern = {
                'language': task.data.get('language', 'python'),
                'problem_type': task.data.get('problem', '')[:100],
                'pattern_description': f"Success with {quality_metrics.get('complexity_estimate', 'unknown')} complexity",
                'quality_score': quality_metrics.get('quality_score', 0.0),
                'success_score': feedback.get('score', 0.0),
                'timestamp': datetime.now().isoformat()
            }
            self.coding_patterns.append(coding_pattern)
            
            if len(self.coding_patterns) > 10:
                self.coding_patterns = sorted(
                    self.coding_patterns,
                    key=lambda x: x.get('success_score', 0),
                    reverse=True
                )[:10]
        
        self.update_performance(experience)
        return experience

class ResearchAgent(BaseAgent):
    """Agent specialized in research and information gathering"""
    
    def __init__(self, agent_id: str, api_keys: Dict[str, str]):
        super().__init__(agent_id, AgentType.RESEARCH, api_keys)
        self.github = Github(api_keys.get('GITHUB_TOKEN', ''))
        self.research_sources = []
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process research tasks"""
        try:
            start_time = time.time()
            
            query = task.data.get('query', '')
            research_type = task.data.get('research_type', 'general')
            
            # Perform research based on type
            if research_type == 'github':
                results = await self._research_github(query, task.data)
            else:
                results = await self._research_general(query, task.data)
            
            execution_time = time.time() - start_time
            
            return {
                'agent_id': self.agent_id,
                'result': {
                    'findings': results,
                    'source_count': len(results.get('sources', [])),
                    'research_type': research_type
                },
                'execution_time': execution_time,
                'confidence': self._calculate_research_confidence(results),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"ResearchAgent {self.agent_id} error: {str(e)}")
            return {
                'agent_id': self.agent_id,
                'result': None,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'status': 'error'
            }
    
    async def _research_github(self, query: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Research GitHub repositories and code"""
        try:
            repositories = self.github.search_repositories(query=query)
            results = {
                'sources': [],
                'summary': f"Found repositories related to: {query}",
                'insights': []
            }
            
            for i, repo in enumerate(repositories[:5]):  # Limit to top 5
                repo_info = {
                    'name': repo.name,
                    'description': repo.description,
                    'stars': repo.stargazers_count,
                    'language': repo.language,
                    'url': repo.html_url,
                    'updated': repo.updated_at.isoformat() if repo.updated_at else None
                }
                results['sources'].append(repo_info)
            
            # Generate insights
            if results['sources']:
                popular_languages = {}
                for source in results['sources']:
                    lang = source.get('language', 'Unknown')
                    popular_languages[lang] = popular_languages.get(lang, 0) + 1
                
                results['insights'] = [
                    f"Most popular language: {max(popular_languages, key=popular_languages.get)}",
                    f"Average stars: {sum(s.get('stars', 0) for s in results['sources']) / len(results['sources']):.1f}",
                    f"Total repositories analyzed: {len(results['sources'])}"
                ]
            
            return results
            
        except Exception as e:
            logger.error(f"GitHub research error: {str(e)}")
            return {
                'sources': [],
                'summary': f"GitHub research failed for query: {query}",
                'insights': [f"Error: {str(e)}"]
            }
    
    async def _research_general(self, query: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform general research (placeholder for external APIs)"""
        # In a real implementation, this would use search APIs, academic databases, etc.
        results = {
            'sources': [],
            'summary': f"Research conducted on: {query}",
            'insights': [
                "General research placeholder - would integrate with external APIs",
                f"Query processed: {query}",
                "Would typically gather from multiple academic and web sources"
            ]
        }
        
        # Simulate some research results
        results['sources'] = [
            {
                'title': f"Research finding for {query}",
                'type': 'academic',
                'relevance_score': 0.8,
                'summary': f"Simulated research result about {query}"
            }
        ]
        
        return results
    
    def _calculate_research_confidence(self, results: Dict[str, Any]) -> float:
        """Calculate confidence in research results"""
        source_count = len(results.get('sources', []))
        base_confidence = 0.3
        
        if source_count >= 5:
            base_confidence = 0.9
        elif source_count >= 3:
            base_confidence = 0.7
        elif source_count >= 1:
            base_confidence = 0.5
        
        return base_confidence
    
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from research task feedback"""
        experience = Experience(
            experience_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_type=task.task_type,
            input_data={'task_data': task.data},
            output_data=result,
            feedback_score=feedback.get('score', 0.0),
            execution_time=result.get('execution_time', 0.0),
            timestamp=datetime.now(),
            context={'task_priority': task.priority.value},
            success=feedback.get('success', False),
            learned_patterns=[]
        )
        
        self.update_performance(experience)
        return experience

class SynthesisAgent(BaseAgent):
    """Agent specialized in synthesizing information from multiple sources"""
    
    def __init__(self, agent_id: str, api_keys: Dict[str, str]):
        super().__init__(agent_id, AgentType.SYNTHESIS, api_keys)
        self.client = anthropic.Anthropic(api_key=api_keys.get('ANTHROPIC_API_KEY'))
        self.synthesis_patterns = []
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process synthesis tasks using Claude"""
        try:
            start_time = time.time()
            
            # Build synthesis prompt
            prompt = self._build_synthesis_prompt(task)
            
            # Generate synthesis
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            execution_time = time.time() - start_time
            
            # Parse synthesis result
            synthesis_result = self._parse_synthesis_response(message.content[0].text)
            
            return {
                'agent_id': self.agent_id,
                'result': synthesis_result,
                'execution_time': execution_time,
                'confidence': self._calculate_synthesis_confidence(synthesis_result),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"SynthesisAgent {self.agent_id} error: {str(e)}")
            return {
                'agent_id': self.agent_id,
                'result': None,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'status': 'error'
            }
    
    def _build_synthesis_prompt(self, task: Task) -> str:
        """Build synthesis prompt from multiple inputs"""
        sources = task.data.get('sources', [])
        synthesis_goal = task.data.get('goal', 'comprehensive synthesis')
        
        prompt = f"""
        Synthesize information from the following sources to achieve: {synthesis_goal}
        
        Sources to synthesize:
        """
        
        for i, source in enumerate(sources, 1):
            prompt += f"\nSource {i}:\n{json.dumps(source, indent=2)}\n"
        
        prompt += f"""
        
        Please provide:
        1. Key themes and patterns across sources
        2. Conflicting information and how to resolve it
        3. Comprehensive synthesis addressing the goal
        4. Gaps in information and recommendations
        5. Confidence assessment of the synthesis
        
        Format as JSON:
        {{
            "themes": ["key themes identified"],
            "conflicts": ["conflicting information found"],
            "synthesis": "comprehensive synthesis text",
            "gaps": ["information gaps identified"],
            "confidence": confidence_score_0_to_1,
            "recommendations": ["actionable recommendations"]
        }}
        """
        
        return prompt
    
    def _parse_synthesis_response(self, response: str) -> Dict[str, Any]:
        """Parse synthesis response"""
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return {
                    'themes': [],
                    'conflicts': [],
                    'synthesis': response,
                    'gaps': [],
                    'confidence': 0.5,
                    'recommendations': []
                }
        except Exception as e:
            logger.error(f"Failed to parse synthesis response: {str(e)}")
            return {
                'themes': [],
                'conflicts': [],
                'synthesis': 'Synthesis parsing failed',
                'gaps': ['Response parsing error'],
                'confidence': 0.3,
                'recommendations': []
            }
    
    def _calculate_synthesis_confidence(self, synthesis_result: Dict[str, Any]) -> float:
        """Calculate confidence in synthesis quality"""
        base_confidence = synthesis_result.get('confidence', 0.5)
        
        # Boost based on completeness
        completeness_bonus = 0.0
        if synthesis_result.get('themes'):
            completeness_bonus += 0.1
        if synthesis_result.get('synthesis') and len(synthesis_result['synthesis']) > 100:
            completeness_bonus += 0.15
        if synthesis_result.get('recommendations'):
            completeness_bonus += 0.05
        
        return min(1.0, base_confidence + completeness_bonus)
    
    def learn_from_feedback(self, task: Task, result: Dict[str, Any], 
                          feedback: Dict[str, Any]) -> Experience:
        """Learn from synthesis task feedback"""
        experience = Experience(
            experience_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            task_type=task.task_type,
            input_data={'task_data': task.data},
            output_data=result,
            feedback_score=feedback.get('score', 0.0),
            execution_time=result.get('execution_time', 0.0),
            timestamp=datetime.now(),
            context={'task_priority': task.priority.value},
            success=feedback.get('success', False),
            learned_patterns=[]
        )
        
        # Extract synthesis patterns
        if experience.success and result.get('result'):
            synthesis_pattern = {
                'source_count': len(task.data.get('sources', [])),
                'goal_type': task.data.get('goal', 'general'),
                'themes_identified': len(result['result'].get('themes', [])),
                'synthesis_quality': len(result['result'].get('synthesis', '')),
                'success_score': feedback.get('score', 0.0),
                'timestamp': datetime.now().isoformat()
            }
            self.synthesis_patterns.append(synthesis_pattern)
            
            if len(self.synthesis_patterns) > 8:
                self.synthesis_patterns = sorted(
                    self.synthesis_patterns,
                    key=lambda x: x.get('success_score', 0),
                    reverse=True
                )[:8]
        
        self.update_performance(experience)
        return experience

class TaskScheduler:
    """Manages task scheduling and priority handling"""
    
    def __init__(self):
        self.task_queue = PriorityQueue()
        self.completed_tasks = []
        self.lock = threading.Lock()
    
    def add_task(self, task: Task):
        """Add task to queue with priority"""
        priority_score = (4 - task.priority.value, task.created_at.timestamp())
        self.task_queue.put((priority_score, task))
        logger.info(f"Task {task.task_id} added to queue with priority {task.priority.value}")
    
    def get_next_task(self) -> Optional[Task]:
        """Get next task from queue"""
        try:
            priority_score, task = self.task_queue.get_nowait()
            return task
        except:
            return None
    
    def mark_completed(self, task: Task, result: Dict[str, Any]):
        """Mark task as completed"""
        with self.lock:
            task.status = "completed"
            self.completed_tasks.append({
                'task': task,
                'result': result,
                'completed_at': datetime.now()
            })
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.task_queue.qsize()

class MultiAgentOrchestrator:
    """Main orchestrator for the multi-agent learning system"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.agents = {}
        self.scheduler = TaskScheduler()
        self.meta_learner = MetaLearner()
        self.memory_store = {}
        self.performance_tracker = {}
        self.executor = ThreadPoolExecutor(max_workers=6)
        self.running = False
        
        # Initialize agents
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize all agent types"""
        agent_configs = [
            (AgentType.REASONING, ReasoningAgent),
            (AgentType.CREATIVE, CreativeAgent),
            (AgentType.ANALYTICAL, AnalyticalAgent),
            (AgentType.CODING, CodingAgent),
            (AgentType.RESEARCH, ResearchAgent),
            (AgentType.SYNTHESIS, SynthesisAgent)
        ]
        
        for agent_type, agent_class in agent_configs:
            agent_id = f"{agent_type.value}_agent_001"
            self.agents[agent_id] = agent_class(agent_id, self.api_keys)
            logger.info(f"Initialized {agent_type.value} agent: {agent_id}")
    
    async def submit_task(self, task: Task) -> str:
        """Submit a task to the system"""
        self.scheduler.add_task(task)
        return f"Task {task.task_id} submitted successfully"
    
    async def process_tasks(self):
        """Main task processing loop"""
        self.running = True
        logger.info("Starting task processing loop")
        
        while self.running:
            try:
                task = self.scheduler.get_next_task()
                if task is None:
                    await asyncio.sleep(1)
                    continue
                
                # Select best agent for task
                selected_agent = await self._select_agent_for_task(task)
                if not selected_agent:
                    logger.warning(f"No suitable agent found for task {task.task_id}")
                    continue
                
                # Process task
                logger.info(f"Processing task {task.task_id} with agent {selected_agent.agent_id}")
                result = await selected_agent.process_task(task)
                
                # Generate feedback and learn
                feedback = await self._generate_feedback(task, result)
                experience = selected_agent.learn_from_feedback(task, result, feedback)
                
                # Update meta-learner
                self.meta_learner.add_experience(experience)
                
                # Mark task as completed
                self.scheduler.mark_completed(task, result)
                
                # Update performance tracking
                self._update_performance_tracking(selected_agent.agent_id, experience)
                
                logger.info(f"Task {task.task_id} completed successfully")
                
            except Exception as e:
                logger.error(f"Error processing tasks: {str(e)}")
                await asyncio.sleep(5)
    
    async def _select_agent_for_task(self, task: Task) -> Optional[BaseAgent]:
        """Select the best agent for a given task"""
        task_type_mapping = {
            'reasoning': AgentType.REASONING,
            'creative': AgentType.CREATIVE,
            'analytical': AgentType.ANALYTICAL,
            'coding': AgentType.CODING,
            'research': AgentType.RESEARCH,
            'synthesis': AgentType.SYNTHESIS
        }
        
        # Primary selection by task type
        target_agent_type = task_type_mapping.get(task.task_type)
        if target_agent_type:
            for agent in self.agents.values():
                if agent.agent_type == target_agent_type:
                    return agent
        
        # Fallback: select agent with best performance for this task type
        best_agent = None
        best_score = 0.0
        
        for agent in self.agents.values():
            # Calculate agent suitability score
            relevant_experiences = [exp for exp in agent.experience_history 
                                  if exp.task_type == task.task_type]
            if relevant_experiences:
                avg_score = sum(exp.feedback_score for exp in relevant_experiences) / len(relevant_experiences)
                if avg_score > best_score:
                    best_score = avg_score
                    best_agent = agent
        
        return best_agent or list(self.agents.values())[0]  # Fallback to first agent
    
    async def _generate_feedback(self, task: Task, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate feedback for task completion"""
        # This is a simplified feedback system
        # In a real system, this might involve human feedback, automated testing, etc.
        
        success = result.get('status') == 'success' and result.get('result') is not None
        
        # Base score calculation
        if success:
            base_score = 0.7
            
            # Bonus for quick execution
            execution_time = result.get('execution_time', float('inf'))
            if execution_time < 5.0:
                base_score += 0.1
            elif execution_time > 30.0:
                base_score -= 0.1
            
            # Bonus for high confidence
            confidence = result.get('confidence', 0.5)
            base_score += (confidence - 0.5) * 0.2
            
            # Priority bonus
            if task.priority in [TaskPriority.HIGH, TaskPriority.CRITICAL]:
                base_score += 0.1
        else:
            base_score = 0.2
        
        return {
            'success': success,
            'score': max(0.0, min(1.0, base_score)),
            'feedback_type': 'automated',
            'execution_time': result.get('execution_time', 0.0),
            'confidence': result.get('confidence', 0.5),
            'timestamp': datetime.now()
        }
    
    def _update_performance_tracking(self, agent_id: str, experience: Experience):
        """Update performance tracking for agents"""
        if agent_id not in self.performance_tracker:
            self.performance_tracker[agent_id] = {
                'total_tasks': 0,
                'successful_tasks': 0,
                'average_score': 0.0,
                'recent_scores': [],
                'task_types': {}
            }
        
        tracker = self.performance_tracker[agent_id]
        tracker['total_tasks'] += 1
        
        if experience.success:
            tracker['successful_tasks'] += 1
        
        # Update recent scores (keep last 10)
        tracker['recent_scores'].append(experience.feedback_score)
        if len(tracker['recent_scores']) > 10:
            tracker['recent_scores'] = tracker['recent_scores'][-10:]
        
        tracker['average_score'] = sum(tracker['recent_scores']) / len(tracker['recent_scores'])
        
        # Track task types
        task_type = experience.task_type
        if task_type not in tracker['task_types']:
            tracker['task_types'][task_type] = {'count': 0, 'avg_score': 0.0}
        
        tracker['task_types'][task_type]['count'] += 1
        # Simple running average update
        current_avg = tracker['task_types'][task_type]['avg_score']
        count = tracker['task_types'][task_type]['count']
        new_avg = ((current_avg * (count - 1)) + experience.feedback_score) / count
        tracker['task_types'][task_type]['avg_score'] = new_avg
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status and performance"""
        status = {
            'running': self.running,
            'queue_size': self.scheduler.get_queue_size(),
            'completed_tasks': len(self.scheduler.completed_tasks),
            'agents': {}
        }
        
        for agent_id, agent in self.agents.items():
            agent_status = {
                'type': agent.agent_type.value,
                'total_experiences': len(agent.experience_history),
                'performance_metrics': agent.performance_metrics.copy()
            }
            
            if agent_id in self.performance_tracker:
                agent_status['detailed_performance'] = self.performance_tracker[agent_id].copy()
            
            status['agents'][agent_id] = agent_status
        
        # Meta-learning insights
        meta_analysis = self.meta_learner.analyze_learning_progress()
        status['meta_learning'] = {
            'total_experiences': len(self.meta_learner.experience_database),
            'meta_score': meta_analysis.get('meta_score', 0.0),
            'recommendations': meta_analysis.get('recommendations', [])
        }
        
        return status
    
    async def stop(self):
        """Stop the orchestrator"""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("Multi-Agent Orchestrator stopped")
    
    def save_state(self, filepath: str):
        """Save system state to file"""
        state = {
            'agents': {},
            'performance_tracker': self.performance_tracker,
            'meta_learner_state': {
                'experience_count': len(self.meta_learner.experience_database),
                'patterns': self.meta_learner.learning_patterns
            }
        }
        
        # Save agent states (experiences and patterns)
        for agent_id, agent in self.agents.items():
            agent_state = {
                'experience_history': [asdict(exp) for exp in agent.experience_history],
                'performance_metrics': agent.performance_metrics,
                'agent_type': agent.agent_type.value
            }
            
            # Add agent-specific patterns
            if hasattr(agent, 'reasoning_patterns'):
                agent_state['reasoning_patterns'] = agent.reasoning_patterns
            if hasattr(agent, 'creative_styles'):
                agent_state['creative_styles'] = agent.creative_styles
            if hasattr(agent, 'analysis_patterns'):
                agent_state['analysis_patterns'] = agent.analysis_patterns
            if hasattr(agent, 'coding_patterns'):
                agent_state['coding_patterns'] = agent.coding_patterns
            if hasattr(agent, 'synthesis_patterns'):
                agent_state['synthesis_patterns'] = agent.synthesis_patterns
            
            state['agents'][agent_id] = agent_state
        
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
            logger.info(f"System state saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}")
    
    def load_state(self, filepath: str):
        """Load system state from file"""
        try:
            with open(filepath, 'rb') as f:
                state = pickle.load(f)
            
            # Restore performance tracking
            self.performance_tracker = state.get('performance_tracker', {})
            
            # Restore agent states
            for agent_id, agent_state in state.get('agents', {}).items():
                if agent_id in self.agents:
                    agent = self.agents[agent_id]
                    
                    # Restore experiences
                    agent.experience_history = []
                    for exp_dict in agent_state.get('experience_history', []):
                        # Convert dict back to Experience object
                        exp_dict['timestamp'] = datetime.fromisoformat(exp_dict['timestamp'])
                        experience = Experience(**exp_dict)
                        agent.experience_history.append(experience)
                    
                    # Restore performance metrics
                    agent.performance_metrics = agent_state.get('performance_metrics', {})
                    
                    # Restore agent-specific patterns
                    if 'reasoning_patterns' in agent_state and hasattr(agent, 'reasoning_patterns'):
                        agent.reasoning_patterns = agent_state['reasoning_patterns']
                    if 'creative_styles' in agent_state and hasattr(agent, 'creative_styles'):
                        agent.creative_styles = agent_state['creative_styles']
                    if 'analysis_patterns' in agent_state and hasattr(agent, 'analysis_patterns'):
                        agent.analysis_patterns = agent_state['analysis_patterns']
                    if 'coding_patterns' in agent_state and hasattr(agent, 'coding_patterns'):
                        agent.coding_patterns = agent_state['coding_patterns']
                    if 'synthesis_patterns' in agent_state and hasattr(agent, 'synthesis_patterns'):
                        agent.synthesis_patterns = agent_state['synthesis_patterns']
            
            logger.info(f"System state loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to load state: {str(e)}")

# Utility functions and example usage

def create_sample_tasks() -> List[Task]:
    """Create sample tasks for testing the system"""
    tasks = []
    
    # Reasoning task
    reasoning_task = Task(
        task_id=str(uuid.uuid4()),
        task_type="reasoning",
        priority=TaskPriority.HIGH,
        data={
            "problem": "A company has 100 employees. 30% work in sales, 25% in engineering, 20% in marketing, and the rest in administration. If the company grows by 50% and maintains the same proportions, how many new employees will work in each department?",
            "context": "Business growth analysis"
        },
        created_at=datetime.now(),
        deadline=datetime.now() + timedelta(hours=2),
        assigned_agent=None,
        dependencies=[]
    )
    tasks.append(reasoning_task)
    
    # Creative task
    creative_task = Task(
        task_id=str(uuid.uuid4()),
        task_type="creative",
        priority=TaskPriority.MEDIUM,
        data={
            "creative_type": "story",
            "theme": "AI and human collaboration",
            "style": "engaging",
            "audience": "tech professionals",
            "length": "short",
            "tone": "optimistic"
        },
        created_at=datetime.now(),
        deadline=datetime.now() + timedelta(hours=4),
        assigned_agent=None,
        dependencies=[]
    )
    tasks.append(creative_task)
    
    # Analytical task
    analytical_task = Task(
        task_id=str(uuid.uuid4()),
        task_type="analytical",
        priority=TaskPriority.HIGH,
        data={
            "data": [
                {"month": "Jan", "sales": 10000, "costs": 7000},
                {"month": "Feb", "sales": 12000, "costs": 8000},
                {"month": "Mar", "sales": 15000, "costs": 9000},
                {"month": "Apr", "sales": 13000, "costs": 8500}
            ],
            "analysis_type": "trend_analysis",
            "focus": "profit margins",
            "metrics": ["profit", "growth_rate", "margin_trend"]
        },
        created_at=datetime.now(),
        deadline=datetime.now() + timedelta(hours=3),
        assigned_agent=None,
        dependencies=[]
    )
    tasks.append(analytical_task)
    
    # Coding task
    coding_task = Task(
        task_id=str(uuid.uuid4()),
        task_type="coding",
        priority=TaskPriority.MEDIUM,
        data={
            "language": "python",
            "problem": "Create a function that validates email addresses using regex",
            "requirements": [
                "Must handle common email formats",
                "Should return True/False",
                "Include error handling",
                "Add unit tests"
            ]
        },
        created_at=datetime.now(),
        deadline=datetime.now() + timedelta(hours=2),
        assigned_agent=None,
        dependencies=[]
    )
    tasks.append(coding_task)
    
    # Research task
    research_task = Task(
        task_id=str(uuid.uuid4()),
        task_type="research",
        priority=TaskPriority.LOW,
        data={
            "query": "machine learning frameworks",
            "research_type": "github",
            "focus": "popular ML frameworks"
        },
        created_at=datetime.now(),
        deadline=datetime.now() + timedelta(hours=6),
        assigned_agent=None,
        dependencies=[]
    )
    tasks.append(research_task)
    
    return tasks

async def main():
    """Main function to demonstrate the multi-agent system"""
    
    # API keys (replace with actual keys)
    api_keys = {
        'OPENAI_API_KEY': 'your-openai-key',
        'ANTHROPIC_API_KEY': 'your-anthropic-key',
        'GOOGLE_API_KEY': 'your-google-key',
        'GROQ_API_KEY': 'your-groq-key',
        'GITHUB_TOKEN': 'your-github-token',
        'PINECONE_API_KEY': 'your-pinecone-key'
    }
    
    # Initialize orchestrator
    orchestrator = MultiAgentOrchestrator(api_keys)
    
    try:
        # Create and submit sample tasks
        sample_tasks = create_sample_tasks()
        for task in sample_tasks:
            await orchestrator.submit_task(task)
        
        print("Sample tasks submitted. Starting task processing...")
        
        # Start processing tasks
        processing_task = asyncio.create_task(orchestrator.process_tasks())
        
        # Let it run for a while
        await asyncio.sleep(30)
        
        # Get system status
        status = orchestrator.get_system_status()
        print("\nSystem Status:")
        print(json.dumps(status, indent=2, default=str))
        
        # Save system state
        orchestrator.save_state("system_state.pkl")
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await orchestrator.stop()

if __name__ == "__main__":
    print("Multi-Agent Learning System")
    print("===========================")
    print("Starting demonstration...")
    
    # Run the main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSystem shutdown completed.")
    except Exception as e:
        print(f"System error: {str(e)}")
        logger.error(f"Main execution error: {str(e)}")
        traceback.print_exc()
        