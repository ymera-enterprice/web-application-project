"""
YMERA Enterprise Enhanced AI Agents System
Implements advanced AI agents with learning capabilities and comprehensive system integration
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import anthropic
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
from pathlib import Path
import pickle


class AgentType(Enum):
    """Types of YMERA agents"""
    CODE_ANALYZER = "code_analyzer"
    SECURITY_SCANNER = "security_scanner"
    QUALITY_ASSURANCE = "quality_assurance"
    MODULE_MANAGER = "module_manager"
    PERFORMANCE_MONITOR = "performance_monitor"
    GENERAL_ASSISTANT = "general_assistant"


class ConfidenceLevel(Enum):
    """Confidence levels for agent responses"""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class PriorityLevel(Enum):
    """Priority levels for recommendations"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class AgentResponse:
    """Structured response from YMERA agents"""
    agent_id: str
    timestamp: str
    confidence_level: str
    executive_summary: str
    detailed_analysis: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    learning_insights: Dict[str, Any]
    next_steps: List[str]
    processing_time: float
    tokens_used: int


@dataclass
class LearningMetric:
    """Learning metrics for continuous improvement"""
    pattern_id: str
    success_rate: float
    usage_count: int
    last_updated: datetime
    effectiveness_score: float
    context_tags: List[str]


@dataclass
class AgentPerformance:
    """Performance metrics for agents"""
    agent_id: str
    total_requests: int
    successful_requests: int
    average_response_time: float
    average_confidence: float
    learning_patterns_count: int
    last_performance_update: datetime


class AgentLearningManager:
    """Manages learning and pattern recognition for agents"""
    
    def __init__(self, db_path: str = "ymera_agent_learning.db"):
        self.db_path = db_path
        self._init_database()
        self.patterns_cache = {}
        self.performance_cache = {}
    
    def _init_database(self):
        """Initialize learning database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Learning patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_patterns (
                pattern_id TEXT PRIMARY KEY,
                agent_type TEXT,
                pattern_data TEXT,
                success_rate REAL,
                usage_count INTEGER,
                last_updated TEXT,
                effectiveness_score REAL,
                context_tags TEXT
            )
        """)
        
        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_performance (
                agent_id TEXT PRIMARY KEY,
                total_requests INTEGER,
                successful_requests INTEGER,
                average_response_time REAL,
                average_confidence REAL,
                learning_patterns_count INTEGER,
                last_update TEXT
            )
        """)
        
        # Feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_feedback (
                feedback_id TEXT PRIMARY KEY,
                agent_id TEXT,
                task_id TEXT,
                user_rating INTEGER,
                outcome_success BOOLEAN,
                feedback_text TEXT,
                timestamp TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_pattern(self, agent_type: str, pattern_data: Dict, success: bool, context_tags: List[str]):
        """Record a learning pattern"""
        pattern_str = json.dumps(pattern_data, sort_keys=True)
        pattern_id = hashlib.md5(pattern_str.encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if pattern exists
        cursor.execute("SELECT * FROM learning_patterns WHERE pattern_id = ?", (pattern_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing pattern
            old_success_rate = existing[3]
            old_usage_count = existing[4]
            
            new_usage_count = old_usage_count + 1
            new_success_rate = ((old_success_rate * old_usage_count) + (1 if success else 0)) / new_usage_count
            effectiveness_score = new_success_rate * min(new_usage_count / 10, 1.0)  # Max at 10 uses
            
            cursor.execute("""
                UPDATE learning_patterns 
                SET success_rate = ?, usage_count = ?, last_updated = ?, 
                    effectiveness_score = ?, context_tags = ?
                WHERE pattern_id = ?
            """, (new_success_rate, new_usage_count, datetime.now().isoformat(),
                  effectiveness_score, json.dumps(context_tags), pattern_id))
        else:
            # Insert new pattern
            cursor.execute("""
                INSERT INTO learning_patterns 
                (pattern_id, agent_type, pattern_data, success_rate, usage_count, 
                 last_updated, effectiveness_score, context_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pattern_id, agent_type, pattern_str, 1.0 if success else 0.0, 1,
                  datetime.now().isoformat(), 1.0 if success else 0.0, json.dumps(context_tags)))
        
        conn.commit()
        conn.close()
        
        # Update cache
        self.patterns_cache[pattern_id] = {
            'agent_type': agent_type,
            'pattern_data': pattern_data,
            'effectiveness_score': effectiveness_score if existing else (1.0 if success else 0.0),
            'context_tags': context_tags
        }
    
    def get_relevant_patterns(self, agent_type: str, context_tags: List[str], limit: int = 5) -> List[Dict]:
        """Get relevant patterns for agent decision making"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_id, pattern_data, effectiveness_score, context_tags
            FROM learning_patterns 
            WHERE agent_type = ? AND effectiveness_score > 0.5
            ORDER BY effectiveness_score DESC
            LIMIT ?
        """, (agent_type, limit))
        
        patterns = []
        for row in cursor.fetchall():
            pattern_tags = json.loads(row[3])
            # Calculate relevance based on tag overlap
            tag_overlap = len(set(context_tags) & set(pattern_tags))
            if tag_overlap > 0 or not context_tags:
                patterns.append({
                    'pattern_id': row[0],
                    'pattern_data': json.loads(row[1]),
                    'effectiveness_score': row[2],
                    'relevance_score': tag_overlap / max(len(context_tags), 1)
                })
        
        conn.close()
        return sorted(patterns, key=lambda x: x['effectiveness_score'] * x['relevance_score'], reverse=True)
    
    def update_performance(self, agent_id: str, response_time: float, confidence: float, success: bool):
        """Update agent performance metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM agent_performance WHERE agent_id = ?", (agent_id,))
        existing = cursor.fetchone()
        
        if existing:
            total_requests = existing[1] + 1
            successful_requests = existing[2] + (1 if success else 0)
            avg_response_time = (existing[3] * existing[1] + response_time) / total_requests
            avg_confidence = (existing[4] * existing[1] + confidence) / total_requests
            
            cursor.execute("""
                UPDATE agent_performance 
                SET total_requests = ?, successful_requests = ?, 
                    average_response_time = ?, average_confidence = ?, last_update = ?
                WHERE agent_id = ?
            """, (total_requests, successful_requests, avg_response_time, 
                  avg_confidence, datetime.now().isoformat(), agent_id))
        else:
            cursor.execute("""
                INSERT INTO agent_performance 
                (agent_id, total_requests, successful_requests, average_response_time, 
                 average_confidence, learning_patterns_count, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, 1, 1 if success else 0, response_time, confidence, 0, 
                  datetime.now().isoformat()))
        
        conn.commit()
        conn.close()


class YMERAEnhancedAgent:
    """Enhanced YMERA AI Agent with learning capabilities"""
    
    # Comprehensive system prompt from the document
    SYSTEM_PROMPT = """
# YMERA Enterprise AI Agent System Prompt

## System Role Definition

You are an elite AI agent within the YMERA Enterprise system, a sophisticated enterprise-grade application management platform. You operate as a specialized expert in your assigned domain while maintaining deep integration with the broader YMERA ecosystem.

## Core Agent Identity

- **System Context**: YMERA Enterprise - Advanced application architecture with multi-agent orchestration
- **Expertise Level**: Senior/Principal level expertise in your domain
- **Performance Standard**: Enterprise-grade efficiency, accuracy, and reliability
- **Learning Mode**: Continuous improvement through feedback loops and pattern recognition

## Agent Capabilities Framework

### 1. **Domain Expertise** (Specialized by Agent Type)

- **Code Analysis Agent**: Senior software architect with expertise in static analysis, security scanning, performance optimization
- **Security Agent**: Cybersecurity expert with deep knowledge of OWASP, threat modeling, vulnerability assessment
- **Quality Assurance Agent**: Test automation expert with comprehensive testing strategies
- **Module Management Agent**: Software engineering expert in component architecture and dependency management
- **Monitoring Agent**: DevOps expert in observability, metrics, and system health

### 2. **Speed & Efficiency Optimization**

- **Parallel Processing**: Break complex tasks into concurrent subtasks when possible
- **Caching Strategy**: Remember and reuse previous analysis results for similar patterns
- **Pattern Recognition**: Identify recurring issues and apply proven solutions immediately
- **Prioritization**: Focus on high-impact issues first using risk-based assessment
- **Optimization Heuristics**: Apply 80/20 rule - identify the 20% of issues causing 80% of problems

### 3. **Intelligence Enhancement**

- **Context Awareness**: Maintain awareness of the entire YMERA system state and component interactions
- **Predictive Analysis**: Anticipate potential issues before they manifest
- **Root Cause Analysis**: Dig deeper than surface symptoms to identify underlying causes
- **Cross-Domain Correlation**: Connect insights across different system components
- **Strategic Thinking**: Consider long-term implications of recommendations

### 4. **Learning Loop Implementation**

- **Continuous Feedback**: Actively seek and incorporate feedback from system outcomes
- **Pattern Learning**: Build internal knowledge base of successful patterns and anti-patterns
- **Adaptation**: Adjust strategies based on observed results and changing system conditions
- **Knowledge Sharing**: Contribute learnings to the broader YMERA agent ecosystem
- **Performance Metrics**: Track and improve your own effectiveness over time

## Operational Excellence Standards

### **Response Structure**

1. **Immediate Assessment**: Quick executive summary of findings
2. **Detailed Analysis**: Comprehensive breakdown with supporting evidence
3. **Actionable Recommendations**: Specific, prioritized steps with implementation guidance
4. **Risk Assessment**: Potential impacts and mitigation strategies
5. **Learning Capture**: What patterns were observed and what was learned

### **Quality Criteria**

- **Accuracy**: All findings must be verifiable and technically sound
- **Completeness**: Address all aspects of the request within scope
- **Clarity**: Use clear, technical language appropriate for developers and architects
- **Actionability**: Every recommendation must be specific and implementable
- **Efficiency**: Optimize for maximum value with minimal resource expenditure

### **Communication Protocol**

- **Structured Output**: Use consistent formatting for easy parsing by other system components
- **Severity Levels**: CRITICAL, HIGH, MEDIUM, LOW for prioritization
- **Confidence Scores**: Indicate certainty level of assessments (High/Medium/Low)
- **Cross-References**: Link to related YMERA components and dependencies
- **Metrics**: Provide quantitative measures where possible

You must respond in this exact JSON format:

{
  "agent_id": "your_agent_type",
  "timestamp": "ISO_8601_timestamp",
  "confidence_level": "High/Medium/Low",
  "executive_summary": "Brief overview of findings",
  "detailed_analysis": {
    "findings": ["finding1", "finding2"],
    "metrics": {"metric1": "value1", "metric2": "value2"},
    "patterns_identified": ["pattern1", "pattern2"]
  },
  "recommendations": [
    {
      "priority": "CRITICAL/HIGH/MEDIUM/LOW",
      "action": "specific_action",
      "rationale": "explanation",
      "implementation": "how_to_implement",
      "estimated_effort": "time_estimate"
    }
  ],
  "learning_insights": {
    "new_patterns": ["pattern1", "pattern2"],
    "success_factors": ["factor1", "factor2"],
    "areas_for_improvement": ["area1", "area2"]
  },
  "next_steps": ["step1", "step2", "step3"]
}
"""

    AGENT_SPECIALIZATIONS = {
        AgentType.CODE_ANALYZER: "Senior software architect with expertise in static analysis, security scanning, performance optimization, and code quality assessment",
        AgentType.SECURITY_SCANNER: "Cybersecurity expert with deep knowledge of OWASP Top 10, threat modeling, vulnerability assessment, and security best practices",
        AgentType.QUALITY_ASSURANCE: "Test automation expert with comprehensive testing strategies, quality metrics, and continuous integration practices",
        AgentType.MODULE_MANAGER: "Software engineering expert in component architecture, dependency management, and modular design patterns",
        AgentType.PERFORMANCE_MONITOR: "DevOps expert in observability, metrics collection, performance optimization, and system health monitoring",
        AgentType.GENERAL_ASSISTANT: "Full-stack expert with broad knowledge across development, operations, and project management"
    }
    
    def __init__(self, 
                 agent_type: AgentType,
                 api_key: str,
                 learning_manager: AgentLearningManager,
                 logger: Optional[logging.Logger] = None):
        self.agent_type = agent_type
        self.agent_id = f"{agent_type.value}_{int(time.time())}"
        self.client = anthropic.Anthropic(api_key=api_key)
        self.learning_manager = learning_manager
        self.logger = logger or logging.getLogger(__name__)
        self.response_cache = {}
        self.performance_metrics = []
        
        # Customize system prompt based on agent type
        self.system_prompt = self._build_specialized_prompt()
    
    def _build_specialized_prompt(self) -> str:
        """Build specialized system prompt for this agent type"""
        base_prompt = self.SYSTEM_PROMPT
        specialization = self.AGENT_SPECIALIZATIONS[self.agent_type]
        
        specialized_prompt = base_prompt.replace(
            "You are an elite AI agent within the YMERA Enterprise system",
            f"You are an elite {self.agent_type.value.replace('_', ' ').title()} AI agent within the YMERA Enterprise system. Your specialization: {specialization}"
        )
        
        return specialized_prompt
    
    def _generate_cache_key(self, task: str, context: Dict[str, Any]) -> str:
        """Generate cache key for task and context"""
        cache_string = f"{task}_{json.dumps(context, sort_keys=True)}"
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _extract_context_tags(self, task: str, context: Dict[str, Any]) -> List[str]:
        """Extract context tags for learning pattern matching"""
        tags = [self.agent_type.value]
        
        # Add tags based on task content
        task_lower = task.lower()
        if 'security' in task_lower or 'vulnerability' in task_lower:
            tags.append('security')
        if 'performance' in task_lower or 'optimization' in task_lower:
            tags.append('performance')
        if 'test' in task_lower or 'quality' in task_lower:
            tags.append('testing')
        if 'code' in task_lower or 'function' in task_lower:
            tags.append('code_analysis')
        if 'error' in task_lower or 'bug' in task_lower:
            tags.append('debugging')
        
        # Add tags from context
        if context:
            if 'file_type' in context:
                tags.append(f"file_type_{context['file_type']}")
            if 'complexity' in context:
                tags.append(f"complexity_{context['complexity']}")
            if 'domain' in context:
                tags.append(f"domain_{context['domain']}")
        
        return list(set(tags))
    
    def _apply_learning_patterns(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply relevant learning patterns to current task"""
        context_tags = self._extract_context_tags(task, context)
        relevant_patterns = self.learning_manager.get_relevant_patterns(
            self.agent_type.value, context_tags, limit=3
        )
        
        learning_context = {
            'relevant_patterns': relevant_patterns,
            'context_tags': context_tags,
            'pattern_suggestions': []
        }
        
        # Generate suggestions based on patterns
        for pattern in relevant_patterns:
            if pattern['effectiveness_score'] > 0.7:
                learning_context['pattern_suggestions'].append(
                    f"Based on similar tasks, consider: {pattern['pattern_data'].get('suggestion', 'No specific suggestion')}"
                )
        
        return learning_context
    
    async def analyze(self, 
                     task: str, 
                     context: Optional[Dict[str, Any]] = None,
                     use_cache: bool = True) -> AgentResponse:
        """Main analysis method with learning integration"""
        start_time = time.time()
        context = context or {}
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(task, context)
            if use_cache and cache_key in self.response_cache:
                cached_response = self.response_cache[cache_key]
                self.logger.info(f"Cache hit for agent {self.agent_id}")
                return cached_response
            
            # Apply learning patterns
            learning_context = self._apply_learning_patterns(task, context)
            
            # Prepare enhanced prompt with learning insights
            enhanced_context = {
                **context,
                'learning_insights': learning_context,
                'agent_specialization': self.AGENT_SPECIALIZATIONS[self.agent_type]
            }
            
            # Prepare the user message
            user_message = f"""
Task: {task}

Context: {json.dumps(enhanced_context, indent=2)}

Learning Patterns Available: {len(learning_context['relevant_patterns'])}
Pattern Suggestions: {learning_context['pattern_suggestions']}

Please analyze this task using your specialized expertise as a {self.agent_type.value.replace('_', ' ').title()} and provide your response in the required JSON format.
"""
            
            # Call Claude API
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.1,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            processing_time = time.time() - start_time
            
            # Parse response
            try:
                response_text = response.content[0].text if response.content else ""
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                response_data = {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "confidence_level": "Medium",
                    "executive_summary": "Analysis completed but response format error occurred",
                    "detailed_analysis": {
                        "findings": ["Response parsing error"],
                        "metrics": {},
                        "patterns_identified": []
                    },
                    "recommendations": [],
                    "learning_insights": {
                        "new_patterns": [],
                        "success_factors": [],
                        "areas_for_improvement": ["Response formatting needs improvement"]
                    },
                    "next_steps": ["Review response format"]
                }
            
            # Create structured response
            agent_response = AgentResponse(
                agent_id=self.agent_id,
                timestamp=response_data.get("timestamp", datetime.now().isoformat()),
                confidence_level=response_data.get("confidence_level", "Medium"),
                executive_summary=response_data.get("executive_summary", ""),
                detailed_analysis=response_data.get("detailed_analysis", {}),
                recommendations=response_data.get("recommendations", []),
                learning_insights=response_data.get("learning_insights", {}),
                next_steps=response_data.get("next_steps", []),
                processing_time=processing_time,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
            )
            
            # Record learning pattern
            pattern_data = {
                'task_type': task[:100],  # First 100 chars
                'context_summary': str(context)[:200],  # First 200 chars
                'response_confidence': agent_response.confidence_level,
                'processing_time': processing_time,
                'recommendations_count': len(agent_response.recommendations)
            }
            
            context_tags = self._extract_context_tags(task, context)
            success = agent_response.confidence_level in ["High", "Medium"]
            
            self.learning_manager.record_pattern(
                self.agent_type.value, pattern_data, success, context_tags
            )
            
            # Update performance metrics
            confidence_score = {"High": 1.0, "Medium": 0.7, "Low": 0.4}[agent_response.confidence_level]
            self.learning_manager.update_performance(
                self.agent_id, processing_time, confidence_score, success
            )
            
            # Cache response
            if use_cache:
                self.response_cache[cache_key] = agent_response
            
            self.logger.info(f"Analysis completed by {self.agent_id} in {processing_time:.2f}s")
            return agent_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Analysis failed for {self.agent_id}: {str(e)}")
            
            # Record failure
            self.learning_manager.update_performance(
                self.agent_id, processing_time, 0.0, False
            )
            
            # Return error response
            return AgentResponse(
                agent_id=self.agent_id,
                timestamp=datetime.now().isoformat(),
                confidence_level="Low",
                executive_summary=f"Analysis failed: {str(e)}",
                detailed_analysis={
                    "findings": [f"Error: {str(e)}"],
                    "metrics": {"processing_time": processing_time},
                    "patterns_identified": []
                },
                recommendations=[{
                    "priority": "HIGH",
                    "action": "Review error and retry",
                    "rationale": "Analysis failed due to system error",
                    "implementation": "Check logs and retry request",
                    "estimated_effort": "5 minutes"
                }],
                learning_insights={
                    "new_patterns": [],
                    "success_factors": [],
                    "areas_for_improvement": ["Error handling", "System reliability"]
                },
                next_steps=["Review error logs", "Retry analysis", "Contact support if persistent"],
                processing_time=processing_time,
                tokens_used=0
            )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for this agent"""
        conn = sqlite3.connect(self.learning_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM agent_performance 
            WHERE agent_id LIKE ? 
            ORDER BY last_update DESC LIMIT 1
        """, (f"{self.agent_type.value}%",))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "agent_id": result[0],
                "agent_type": self.agent_type.value,
                "total_requests": result[1],
                "successful_requests": result[2],
                "success_rate": result[2] / result[1] if result[1] > 0 else 0,
                "average_response_time": result[3],
                "average_confidence": result[4],
                "learning_patterns_count": result[5],
                "last_update": result[6]
            }
        
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "total_requests": 0,
            "successful_requests": 0,
            "success_rate": 0,
            "average_response_time": 0,
            "average_confidence": 0,
            "learning_patterns_count": 0,
            "last_update": datetime.now().isoformat()
        }


class YMERAAgentOrchestrator:
    """Orchestrates multiple YMERA agents with load balancing and collaboration"""
    
    def __init__(self, api_key: str, db_path: str = "ymera_agents.db"):
        self.api_key = api_key
        self.learning_manager = AgentLearningManager(db_path)
        self.agents: Dict[AgentType, YMERAEnhancedAgent] = {}
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Initialize all agent types
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize all agent types"""
        for agent_type in AgentType:
            self.agents[agent_type] = YMERAEnhancedAgent(
                agent_type=agent_type,
                api_key=self.api_key,
                learning_manager=self.learning_manager,
                logger=self.logger
            )
    
    def get_agent(self, agent_type: AgentType) -> YMERAEnhancedAgent:
        """Get specific agent by type"""
        return self.agents[agent_type]
    
    async def analyze_with_best_agent(self, 
                                     task: str, 
                                     context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Automatically select the best agent for the task"""
        
        # Simple task classification logic
        task_lower = task.lower()
        
        if any(keyword in task_lower for keyword in ['security', 'vulnerability', 'exploit', 'attack']):
            agent_type = AgentType.SECURITY_SCANNER
        elif any(keyword in task_lower for keyword in ['test', 'quality', 'bug', 'defect']):
            agent_type = AgentType.QUALITY_ASSURANCE
        elif any(keyword in task_lower for keyword in ['performance', 'optimization', 'slow', 'memory']):
            agent_type = AgentType.PERFORMANCE_MONITOR
        elif any(keyword in task_lower for keyword in ['module', 'dependency', 'architecture', 'design']):
            agent_type = AgentType.MODULE_MANAGER
        elif any(keyword in task_lower for keyword in ['code', 'function', 'class', 'method']):
            agent_type = AgentType.CODE_ANALYZER
        else:
            agent_type = AgentType.GENERAL_ASSISTANT
        
        selected_agent = self.agents[agent_type]
        self.logger.info(f"Selected {agent_type.value} for task: {task[:50]}...")
        
        return await selected_agent.analyze(task, context)
    
    async def collaborative_analysis(self, 
                                   task: str, 
                                   agent_types: List[AgentType],
                                   context: Optional[Dict[str, Any]] = None) -> Dict[AgentType, AgentResponse]:
        """Run collaborative analysis with multiple agents"""
        
        tasks = []
        for agent_type in agent_types:
            agent = self.agents[agent_type]
            tasks.append(agent.analyze(task, context))
        
        responses = await asyncio.gather(*tasks)
        
        result = {}
        for i, agent_type in enumerate(agent_types):
            result[agent_type] = responses[i]
        
        return result
    
    def get_system_performance(self) -> Dict[str, Any]:
        """Get overall system performance metrics"""
        performance_data = {}
        
        for agent_type, agent in self.agents.items():
            performance_data[agent_type.value] = agent.get_performance_summary()
        
        # Calculate overall metrics
        total_requests = sum(p["total_requests"] for p in performance_data.values())
        total_successful = sum(p["successful_requests"] for p in performance_data.values())
        avg_success_rate = total_successful / total_requests if total_requests > 0 else 0
        
        return {
            "agents": performance_data,
            "overall": {
                "total_requests": total_requests,
                "total_successful": total_successful,
                "overall_success_rate": avg_success_rate,
                "agents_count": len(self.agents),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        self.logger.info("YMERA Agent Orchestrator cleaned up")


# Example usage and testing
async def example_usage():
    """Example of how to use the enhanced YMERA agents"""
    
    # Initialize the orchestrator
    orchestrator = YMERAAgentOrchestrator(
        api_key="your-anthropic-api-key-here"
    )
    
    # Example 1: Automatic agent selection
    print("=== Automatic Agent Selection ===")
    response = await orchestrator.analyze_with_best_agent(
        task="Analyze this Python code for security vulnerabilities and potential SQL injection risks",
        context={
            "file_type": "python",
            "complexity": "medium",
            "domain": "web_application"
        }
    )
    
    print(f"Agent: {response.agent_id}")
    print(f"Confidence: {response.confidence_level}")
    print(f"Summary: {response.executive_summary}")
    print(f"Recommendations: {len(response. print(f"Recommendations: {len(response.recommendations)}")
    print(f"Processing time: {response.processing_time:.2f}s")
    print("\n")
    
    # Example 2: Specific agent usage
    print("=== Specific Agent Usage ===")
    code_agent = orchestrator.get_agent(AgentType.CODE_ANALYZER)
    code_response = await code_agent.analyze(
        task="Review this function for performance optimization opportunities",
        context={
            "code": """
def process_data(items):
    result = []
    for item in items:
        if item['status'] == 'active':
            processed = expensive_operation(item)
            result.append(processed)
    return result
""",
            "language": "python",
            "performance_critical": True
        }
    )
    
    print(f"Code Analysis Summary: {code_response.executive_summary}")
    for rec in code_response.recommendations[:2]:  # Show first 2 recommendations
        print(f"- {rec.get('priority', 'MEDIUM')}: {rec.get('action', 'No action specified')}")
    print("\n")
    
    # Example 3: Collaborative analysis
    print("=== Collaborative Analysis ===")
    collaborative_agents = [AgentType.CODE_ANALYZER, AgentType.SECURITY_SCANNER, AgentType.PERFORMANCE_MONITOR]
    collaborative_responses = await orchestrator.collaborative_analysis(
        task="Analyze this authentication function for code quality, security, and performance",
        agent_types=collaborative_agents,
        context={
            "function": "authenticate_user",
            "criticality": "high",
            "environment": "production"
        }
    )
    
    for agent_type, response in collaborative_responses.items():
        print(f"{agent_type.value}: {response.confidence_level} confidence - {len(response.recommendations)} recommendations")
    print("\n")
    
    # Example 4: Performance monitoring
    print("=== System Performance ===")
    performance = orchestrator.get_system_performance()
    print(f"Total requests: {performance['overall']['total_requests']}")
    print(f"Success rate: {performance['overall']['overall_success_rate']:.2%}")
    print(f"Active agents: {performance['overall']['agents_count']}")
    
    # Cleanup
    await orchestrator.cleanup()


class YMERAAgentAPI:
    """REST API wrapper for YMERA agents"""
    
    def __init__(self, orchestrator: YMERAAgentOrchestrator):
        self.orchestrator = orchestrator
        self.request_history = []
        self.active_sessions = {}
    
    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process API request"""
        try:
            request_id = request_data.get('request_id', f"req_{int(time.time())}")
            task = request_data.get('task', '')
            context = request_data.get('context', {})
            agent_type = request_data.get('agent_type', 'auto')
            
            # Record request
            self.request_history.append({
                'request_id': request_id,
                'timestamp': datetime.now().isoformat(),
                'task': task[:100],  # Truncate for storage
                'agent_type': agent_type
            })
            
            # Process based on agent type
            if agent_type == 'auto':
                response = await self.orchestrator.analyze_with_best_agent(task, context)
            elif agent_type == 'collaborative':
                agent_types = request_data.get('collaborative_agents', [AgentType.CODE_ANALYZER, AgentType.SECURITY_SCANNER])
                responses = await self.orchestrator.collaborative_analysis(task, agent_types, context)
                # Combine responses for API return
                response = self._combine_collaborative_responses(responses)
            else:
                try:
                    selected_agent_type = AgentType(agent_type)
                    agent = self.orchestrator.get_agent(selected_agent_type)
                    response = await agent.analyze(task, context)
                except ValueError:
                    return {
                        'success': False,
                        'error': f'Invalid agent type: {agent_type}',
                        'available_types': [at.value for at in AgentType]
                    }
            
            # Format response for API
            return {
                'success': True,
                'request_id': request_id,
                'response': asdict(response),
                'metadata': {
                    'processing_time': response.processing_time,
                    'tokens_used': response.tokens_used,
                    'agent_id': response.agent_id
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'request_id': request_data.get('request_id', 'unknown')
            }
    
    def _combine_collaborative_responses(self, responses: Dict[AgentType, AgentResponse]) -> AgentResponse:
        """Combine multiple agent responses into one"""
        combined_summary = "Collaborative analysis completed by multiple agents:\n"
        combined_recommendations = []
        combined_insights = {
            'new_patterns': [],
            'success_factors': [],
            'areas_for_improvement': []
        }
        
        total_processing_time = 0
        total_tokens = 0
        
        for agent_type, response in responses.items():
            combined_summary += f"\n{agent_type.value}: {response.executive_summary}"
            combined_recommendations.extend(response.recommendations)
            
            # Combine insights
            for key in combined_insights.keys():
                combined_insights[key].extend(response.learning_insights.get(key, []))
            
            total_processing_time += response.processing_time
            total_tokens += response.tokens_used
        
        # Create combined response
        return AgentResponse(
            agent_id="collaborative_analysis",
            timestamp=datetime.now().isoformat(),
            confidence_level="High",  # Collaborative analysis typically has high confidence
            executive_summary=combined_summary,
            detailed_analysis={
                'findings': [f"Analysis from {len(responses)} specialized agents"],
                'metrics': {'agents_used': len(responses)},
                'patterns_identified': []
            },
            recommendations=combined_recommendations,
            learning_insights=combined_insights,
            next_steps=["Review all recommendations", "Prioritize by urgency", "Implement highest priority items first"],
            processing_time=total_processing_time,
            tokens_used=total_tokens
        )
    
    def get_request_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent request history"""
        return self.request_history[-limit:]
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get API usage analytics"""
        if not self.request_history:
            return {'total_requests': 0, 'agent_usage': {}, 'average_processing_time': 0}
        
        total_requests = len(self.request_history)
        agent_usage = {}
        
        for request in self.request_history:
            agent_type = request['agent_type']
            agent_usage[agent_type] = agent_usage.get(agent_type, 0) + 1
        
        return {
            'total_requests': total_requests,
            'agent_usage': agent_usage,
            'recent_requests': self.get_request_history(5),
            'system_performance': self.orchestrator.get_system_performance()
        }


class YMERAAgentCLI:
    """Command Line Interface for YMERA agents"""
    
    def __init__(self, api_key: str):
        self.orchestrator = YMERAAgentOrchestrator(api_key)
        self.api = YMERAAgentAPI(self.orchestrator)
        
    async def interactive_mode(self):
        """Run interactive CLI mode"""
        print("=== YMERA Enterprise AI Agents CLI ===")
        print("Available commands: analyze, collaborative, performance, history, help, exit")
        print("Available agents:", [at.value for at in AgentType])
        print("\nType 'help' for detailed usage information.\n")
        
        while True:
            try:
                command = input("YMERA> ").strip().lower()
                
                if command == 'exit':
                    print("Shutting down YMERA agents...")
                    await self.orchestrator.cleanup()
                    break
                    
                elif command == 'help':
                    self._show_help()
                    
                elif command == 'performance':
                    await self._show_performance()
                    
                elif command == 'history':
                    self._show_history()
                    
                elif command.startswith('analyze'):
                    await self._handle_analyze_command(command)
                    
                elif command.startswith('collaborative'):
                    await self._handle_collaborative_command(command)
                    
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\nShutting down...")
                await self.orchestrator.cleanup()
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def _show_help(self):
        """Show help information"""
        help_text = """
=== YMERA Agent CLI Help ===

Commands:
  analyze <task>                    - Automatically select best agent for task
  analyze <agent_type> <task>      - Use specific agent type
  collaborative <task>             - Use multiple agents collaboratively
  performance                      - Show system performance metrics
  history                         - Show recent request history
  help                           - Show this help message
  exit                           - Exit the CLI

Agent Types:
  code_analyzer        - Code analysis and review
  security_scanner     - Security vulnerability assessment
  quality_assurance    - Quality and testing analysis
  module_manager       - Module and dependency management
  performance_monitor  - Performance optimization
  general_assistant    - General purpose assistant

Examples:
  analyze Check this Python function for bugs
  analyze security_scanner Look for SQL injection vulnerabilities
  collaborative Review this authentication system
        """
        print(help_text)
    
    async def _handle_analyze_command(self, command: str):
        """Handle analyze command"""
        parts = command.split(' ', 2)
        
        if len(parts) < 2:
            print("Usage: analyze <task> or analyze <agent_type> <task>")
            return
        
        if len(parts) == 2:
            # Auto-select agent
            task = parts[1]
            response = await self.orchestrator.analyze_with_best_agent(task)
        else:
            # Specific agent
            try:
                agent_type = AgentType(parts[1])
                task = parts[2]
                agent = self.orchestrator.get_agent(agent_type)
                response = await agent.analyze(task)
            except ValueError:
                print(f"Invalid agent type: {parts[1]}")
                print("Available types:", [at.value for at in AgentType])
                return
        
        self._display_response(response)
    
    async def _handle_collaborative_command(self, command: str):
        """Handle collaborative command"""
        parts = command.split(' ', 1)
        
        if len(parts) < 2:
            print("Usage: collaborative <task>")
            return
        
        task = parts[1]
        agent_types = [AgentType.CODE_ANALYZER, AgentType.SECURITY_SCANNER, AgentType.QUALITY_ASSURANCE]
        responses = await self.orchestrator.collaborative_analysis(task, agent_types)
        
        print(f"\n=== Collaborative Analysis Results ===")
        for agent_type, response in responses.items():
            print(f"\n--- {agent_type.value.replace('_', ' ').title()} ---")
            print(f"Confidence: {response.confidence_level}")
            print(f"Summary: {response.executive_summary}")
            print(f"Recommendations: {len(response.recommendations)}")
    
    async def _show_performance(self):
        """Show performance metrics"""
        performance = self.orchestrator.get_system_performance()
        
        print("\n=== System Performance ===")
        print(f"Total Requests: {performance['overall']['total_requests']}")
        print(f"Success Rate: {performance['overall']['overall_success_rate']:.2%}")
        print(f"Active Agents: {performance['overall']['agents_count']}")
        
        print("\n--- Agent Performance ---")
        for agent_type, metrics in performance['agents'].items():
            if metrics['total_requests'] > 0:
                print(f"{agent_type}: {metrics['success_rate']:.2%} success, {metrics['average_response_time']:.2f}s avg")
    
    def _show_history(self):
        """Show request history"""
        history = self.api.get_request_history(10)
        
        print("\n=== Recent Requests ===")
        for request in history[-5:]:  # Show last 5
            print(f"{request['timestamp']}: {request['task']} ({request['agent_type']})")
    
    def _display_response(self, response: AgentResponse):
        """Display agent response"""
        print(f"\n=== Analysis Results ===")
        print(f"Agent: {response.agent_id}")
        print(f"Confidence: {response.confidence_level}")
        print(f"Processing Time: {response.processing_time:.2f}s")
        print(f"\nSummary: {response.executive_summary}")
        
        if response.recommendations:
            print(f"\nRecommendations ({len(response.recommendations)}):")
            for i, rec in enumerate(response.recommendations[:3], 1):  # Show first 3
                priority = rec.get('priority', 'MEDIUM')
                action = rec.get('action', 'No action specified')
                print(f"  {i}. [{priority}] {action}")
        
        if response.next_steps:
            print(f"\nNext Steps:")
            for step in response.next_steps[:3]:  # Show first 3
                print(f"  - {step}")


# Main execution
if __name__ == "__main__":
    import sys
    import argparse
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ymera_agents.log'),
            logging.StreamHandler()
        ]
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='YMERA Enterprise AI Agents System')
    parser.add_argument('--api-key', required=True, help='Anthropic API key')
    parser.add_argument('--mode', choices=['cli', 'example'], default='cli', 
                       help='Run mode: cli (interactive) or example (demonstration)')
    parser.add_argument('--db-path', default='ymera_agents.db', help='Database path for learning data')
    
    args = parser.parse_args()
    
    async def main():
        if args.mode == 'cli':
            cli = YMERAAgentCLI(args.api_key)
            await cli.interactive_mode()
        else:
            # Run example
            await example_usage()
    
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)