"""
Enterprise-Grade Base Agent Framework - COMPLETED
Provides comprehensive foundation for all AI agents in the system
"""
import asyncio
import logging
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, TypeVar, Generic
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import aiofiles
from pydantic import BaseModel, Field
import traceback
import hashlib
from concurrent.futures import ThreadPoolExecutor
import threading
import os
import sys
from pathlib import Path

T = TypeVar('T')

class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"

class AgentCapability(Enum):
    """Agent capabilities enumeration"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CODE_OPTIMIZATION = "code_optimization"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    PROJECT_MANAGEMENT = "project_management"
    UI_UX_DESIGN = "ui_ux_design"
    DATABASE_OPERATIONS = "database_operations"
    API_INTEGRATION = "api_integration"
    MONITORING = "monitoring"
    VALIDATION = "validation"
    COMMUNICATION = "communication"
    ORCHESTRATION = "orchestration"
    LEARNING = "learning"
    ANALYSIS = "analysis"
    ENHANCEMENT = "enhancement"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    COLLABORATION = "collaboration"

class AgentState(Enum):
    """Agent operational states"""
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    LEARNING = "learning"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

class LearningType(Enum):
    """Types of learning mechanisms"""
    SUPERVISED = "supervised"
    UNSUPERVISED = "unsupervised"
    REINFORCEMENT = "reinforcement"
    TRANSFER = "transfer"
    CONTINUOUS = "continuous"
    FEDERATED = "federated"

@dataclass
class Task:
    """Represents a task to be executed by an agent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    agent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300  # seconds
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentMetrics:
    """Performance metrics for an agent"""
    tasks_completed: int = 0
    tasks_failed: int = 0
    average_completion_time: float = 0.0
    success_rate: float = 0.0
    learning_score: float = 0.0
    efficiency_score: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    uptime: timedelta = timedelta()
    memory_usage: float = 0.0
    cpu_usage: float = 0.0

@dataclass
class LearningEvent:
    """Represents a learning event for the agent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    event_type: LearningType = LearningType.CONTINUOUS
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    feedback: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    effectiveness: Optional[float] = None

class APIProvider(Enum):
    """Available AI API providers"""
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GROQ = "groq"
    GITHUB = "github"
    PINECONE = "pinecone"

@dataclass
class APICredential:
    """API credential management"""
    provider: APIProvider
    key: str
    endpoint: Optional[str] = None
    is_admin: bool = False
    is_service_account: bool = False
    usage_count: int = 0
    rate_limit: int = 1000
    last_used: Optional[datetime] = None
    is_active: bool = True

class BaseAgent(ABC):
    """
    Base class for all AI agents in the system
    Provides core functionality, learning capabilities, and enterprise features
    """
    
    def __init__(
        self,
        agent_id: str = None,
        name: str = "BaseAgent",
        capabilities: List[AgentCapability] = None,
        api_credentials: Dict[APIProvider, List[APICredential]] = None,
        config: Dict[str, Any] = None
    ):
        self.agent_id = agent_id or f"{name}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.capabilities = capabilities or []
        self.state = AgentState.INITIALIZING
        self.api_credentials = api_credentials or {}
        self.config = config or {}
        
        # Core components
        self.logger = self._setup_logger()
        self.metrics = AgentMetrics()
        self.task_queue = asyncio.Queue()
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: List[Task] = []
        self.learning_history: List[LearningEvent] = []
        
        # Concurrency control
        self.max_concurrent_tasks = self.config.get('max_concurrent_tasks', 5)
        self.task_semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        
        # Learning components
        self.learning_enabled = self.config.get('learning_enabled', True)
        self.learning_threshold = self.config.get('learning_threshold', 0.8)
        self.knowledge_base: Dict[str, Any] = {}
        
        # Communication
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.message_queue = asyncio.Queue()
        
        # Performance monitoring
        self.start_time = datetime.now()
        self.heartbeat_interval = self.config.get('heartbeat_interval', 30)
        
        # Thread pool for blocking operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize agent
        asyncio.create_task(self._initialize())
    
    def _setup_logger(self) -> logging.Logger:
        """Setup agent-specific logger"""
        logger = logging.getLogger(f"agent.{self.name}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'%(asctime)s - {self.agent_id} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def _initialize(self):
        """Initialize the agent"""
        try:
            self.logger.info(f"Initializing agent {self.name}")
            
            # Load configuration
            await self._load_configuration()
            
            # Initialize API connections
            await self._initialize_api_connections()
            
            # Load knowledge base
            await self._load_knowledge_base()
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_loop())
            asyncio.create_task(self._process_tasks())
            asyncio.create_task(self._learning_loop())
            asyncio.create_task(self._message_processor())
            
            self.state = AgentState.IDLE
            self.logger.info(f"Agent {self.name} initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {str(e)}")
            self.state = AgentState.ERROR
            raise
    
    async def _load_configuration(self):
        """Load agent configuration"""
        config_path = Path(f"config/{self.agent_id}_config.json")
        if config_path.exists():
            async with aiofiles.open(config_path, 'r') as f:
                content = await f.read()
                saved_config = json.loads(content)
                self.config.update(saved_config)
    
    async def _initialize_api_connections(self):
        """Initialize connections to AI API providers"""
        for provider, credentials in self.api_credentials.items():
            for credential in credentials:
                if credential.is_active:
                    try:
                        # Test API connection
                        await self._test_api_connection(provider, credential)
                        self.logger.info(f"Connected to {provider.value} API")
                    except Exception as e:
                        self.logger.error(f"Failed to connect to {provider.value}: {str(e)}")
                        credential.is_active = False
    
    async def _test_api_connection(self, provider: APIProvider, credential: APICredential):
        """Test API connection"""
        try:
            if provider == APIProvider.OPENAI:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {credential.key}"}
                    async with session.get("https://api.openai.com/v1/models", headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"OpenAI API test failed: {response.status}")
            
            elif provider == APIProvider.CLAUDE:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "x-api-key": credential.key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    }
                    # Test with a minimal request
                    data = {"model": "claude-3-sonnet-20240229", "max_tokens": 1, "messages": [{"role": "user", "content": "Hi"}]}
                    async with session.post("https://api.anthropic.com/v1/messages", headers=headers, json=data) as response:
                        if response.status not in [200, 400]:  # 400 is acceptable for test
                            raise Exception(f"Claude API test failed: {response.status}")
            
            elif provider == APIProvider.GITHUB:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"token {credential.key}"}
                    async with session.get("https://api.github.com/user", headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"GitHub API test failed: {response.status}")
            
            elif provider == APIProvider.GEMINI:
                async with aiohttp.ClientSession() as session:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={credential.key}"
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(f"Gemini API test failed: {response.status}")
            
            elif provider == APIProvider.DEEPSEEK:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {credential.key}"}
                    async with session.get("https://api.deepseek.com/v1/models", headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"DeepSeek API test failed: {response.status}")
            
            elif provider == APIProvider.GROQ:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {credential.key}"}
                    async with session.get("https://api.groq.com/openai/v1/models", headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"Groq API test failed: {response.status}")
            
            elif provider == APIProvider.PINECONE:
                async with aiohttp.ClientSession() as session:
                    headers = {"Api-Key": credential.key}
                    async with session.get("https://api.pinecone.io/databases", headers=headers) as response:
                        if response.status not in [200, 404]:  # 404 is acceptable for empty
                            raise Exception(f"Pinecone API test failed: {response.status}")
            
        except Exception as e:
            raise Exception(f"API connection test failed: {str(e)}")
    
    async def _load_knowledge_base(self):
        """Load agent's knowledge base"""
        kb_path = Path(f"knowledge/{self.agent_id}_kb.json")
        if kb_path.exists():
            async with aiofiles.open(kb_path, 'r') as f:
                content = await f.read()
                self.knowledge_base = json.loads(content)
    
    async def _save_knowledge_base(self):
        """Save knowledge base to persistent storage"""
        kb_path = Path(f"knowledge/{self.agent_id}_kb.json")
        kb_path.parent.mkdir(exist_ok=True)
        
        async with aiofiles.open(kb_path, 'w') as f:
            await f.write(json.dumps(self.knowledge_base, indent=2, default=str))
    
    async def _heartbeat_loop(self):
        """Periodic heartbeat and health monitoring"""
        while self.state != AgentState.OFFLINE:
            try:
                await self._update_metrics()
                await self._health_check()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"Heartbeat error: {str(e)}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _update_metrics(self):
        """Update agent performance metrics"""
        current_time = datetime.now()
        self.metrics.uptime = current_time - self.start_time
        self.metrics.last_updated = current_time
        
        if self.metrics.tasks_completed + self.metrics.tasks_failed > 0:
            self.metrics.success_rate = (
                self.metrics.tasks_completed / 
                (self.metrics.tasks_completed + self.metrics.tasks_failed)
            )
        
        # Calculate learning score based on recent performance
        if len(self.learning_history) > 0:
            recent_events = [e for e in self.learning_history 
                           if e.timestamp > current_time - timedelta(hours=1)]
            if recent_events:
                self.metrics.learning_score = sum(e.confidence for e in recent_events) / len(recent_events)
    
    async def _health_check(self):
        """Perform health check"""
        try:
            # Check memory usage
            import psutil
            process = psutil.Process()
            self.metrics.memory_usage = process.memory_percent()
            self.metrics.cpu_usage = process.cpu_percent()
            
            # Check if agent is responsive
            if self.state == AgentState.BUSY and len(self.active_tasks) == 0:
                self.state = AgentState.IDLE
            
            # Check for stuck tasks
            current_time = datetime.now()
            for task_id, task in list(self.active_tasks.items()):
                if task.started_at and (current_time - task.started_at).seconds > task.timeout:
                    await self._handle_task_timeout(task)
                    
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
    
    async def _handle_task_timeout(self, task: Task):
        """Handle task timeout"""
        self.logger.warning(f"Task {task.id} timed out")
        task.status = TaskStatus.FAILED
        task.error = "Task timed out"
        task.completed_at = datetime.now()
        
        if task.id in self.active_tasks:
            del self.active_tasks[task.id]
        
        self.completed_tasks.append(task)
        self.metrics.tasks_failed += 1
        
        await self._emit_event("task_timeout", {"task": task})
    
    async def _process_tasks(self):
        """Main task processing loop"""
        while self.state != AgentState.OFFLINE:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                asyncio.create_task(self._execute_task(task))
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Task processing error: {str(e)}")
    
    async def _execute_task(self, task: Task):
        """Execute a single task"""
        async with self.task_semaphore:
            try:
                self.state = AgentState.BUSY
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                task.agent_id = self.agent_id
                self.active_tasks[task.id] = task
                
                self.logger.info(f"Starting task: {task.name}")
                
                # Execute the actual task
                result = await self._perform_task(task)
                
                # Complete task
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                
                # Update metrics
                completion_time = (task.completed_at - task.started_at).total_seconds()
                self._update_completion_metrics(completion_time)
                
                # Learn from task execution
                if self.learning_enabled:
                    await self._learn_from_task(task)
                
                self.logger.info(f"Completed task: {task.name}")
                
            except Exception as e:
                await self._handle_task_error(task, e)
            finally:
                if task.id in self.active_tasks:
                    del self.active_tasks[task.id]
                
                self.completed_tasks.append(task)
                
                if len(self.active_tasks) == 0:
                    self.state = AgentState.IDLE
    
    def _update_completion_metrics(self, completion_time: float):
        """Update task completion metrics"""
        self.metrics.tasks_completed += 1
        
        # Update average completion time
        total_tasks = self.metrics.tasks_completed
        self.metrics.average_completion_time = (
            (self.metrics.average_completion_time * (total_tasks - 1) + completion_time) / total_tasks
        )
        
        # Update efficiency score (inverse of completion time, normalized)
        self.metrics.efficiency_score = min(1.0, 100.0 / max(completion_time, 1.0))
    
    async def _handle_task_error(self, task: Task, error: Exception):
        """Handle task execution error"""
        self.logger.error(f"Task {task.name} failed: {str(error)}")
        
        task.error = str(error)
        task.retry_count += 1
        
        if task.retry_count < task.max_retries:
            task.status = TaskStatus.RETRY
            # Re-queue with exponential backoff
            delay = 2 ** task.retry_count
            await asyncio.sleep(delay)
            await self.task_queue.put(task)
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            self.metrics.tasks_failed += 1
            
            await self._emit_event("task_failed", {"task": task, "error": str(error)})
    
    @abstractmethod
    async def _perform_task(self, task: Task) -> Any:
        """
        Abstract method to be implemented by specific agent types
        This is where the actual task execution logic goes
        """
        pass
    
    async def _learning_loop(self):
        """Continuous learning loop"""
        while self.state != AgentState.OFFLINE:
            try:
                if self.learning_enabled and len(self.learning_history) > 10:
                    await self._perform_learning_cycle()
                await asyncio.sleep(300)  # Learn every 5 minutes
            except Exception as e:
                self.logger.error(f"Learning loop error: {str(e)}")
                await asyncio.sleep(300)
    
    async def _perform_learning_cycle(self):
        """Perform a learning cycle"""
        self.state = AgentState.LEARNING
        
        try:
            # Analyze recent performance
            recent_events = [e for e in self.learning_history 
                           if e.timestamp > datetime.now() - timedelta(hours=1)]
            
            if len(recent_events) >= 5:
                # Extract patterns
                patterns = await self._extract_learning_patterns(recent_events)
                
                # Update knowledge base
                await self._update_knowledge_from_patterns(patterns)
                
                # Optimize agent parameters
                await self._optimize_parameters(patterns)
                
                self.logger.info("Learning cycle completed")
        
        except Exception as e:
            self.logger.error(f"Learning cycle failed: {str(e)}")
        
        finally:
            if len(self.active_tasks) == 0:
                self.state = AgentState.IDLE
    
    async def _extract_learning_patterns(self, events: List[LearningEvent]) -> Dict[str, Any]:
        """Extract patterns from learning events"""
        patterns = {
            "success_patterns": [],
            "failure_patterns": [],
            "efficiency_patterns": [],
            "common_contexts": {}
        }
        
        for event in events:
            if event.effectiveness and event.effectiveness > 0.8:
                patterns["success_patterns"].append({
                    "input": event.input_data,
                    "output": event.output_data,
                    "confidence": event.confidence
                })
            elif event.effectiveness and event.effectiveness < 0.3:
                patterns["failure_patterns"].append({
                    "input": event.input_data,
                    "output": event.output_data,
                    "confidence": event.confidence
                })
        
        return patterns
    
    async def _update_knowledge_from_patterns(self, patterns: Dict[str, Any]):
        """Update knowledge base from learned patterns"""
        timestamp = datetime.now().isoformat()
        
        if "learned_patterns" not in self.knowledge_base:
            self.knowledge_base["learned_patterns"] = {}
        
        self.knowledge_base["learned_patterns"][timestamp] = patterns
        
        # Keep only recent patterns (last 30 days)
        cutoff = datetime.now() - timedelta(days=30)
        self.knowledge_base["learned_patterns"] = {
            k: v for k, v in self.knowledge_base["learned_patterns"].items()
            if datetime.fromisoformat(k) > cutoff
        }
        
        await self._save_knowledge_base()
    
    async def _optimize_parameters(self, patterns: Dict[str, Any]):
        """Optimize agent parameters based on learned patterns"""
        # Adjust task timeout based on success patterns
        if patterns["success_patterns"]:
            avg_confidence = sum(p["confidence"] for p in patterns["success_patterns"]) / len(patterns["success_patterns"])
            if avg_confidence > 0.9:
                # Increase concurrent tasks if performing well
                self.max_concurrent_tasks = min(self.max_concurrent_tasks + 1, 10)
            elif avg_confidence < 0.5:
                # Decrease concurrent tasks if struggling
                self.max_concurrent_tasks = max(self.max_concurrent_tasks - 1, 1)
    
    async def _learn_from_task(self, task: Task):
        """Learn from task execution"""
        learning_event = LearningEvent(
            agent_id=self.agent_id,
            event_type=LearningType.CONTINUOUS,
            input_data={
                "task_name": task.name,
                "task_priority": task.priority.value,
                "task_context": task.context
            },
            output_data={
                "result": str(task.result) if task.result else None,
                "completion_time": (task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else None,
                "status": task.status.value
            },
            confidence=1.0 if task.status == TaskStatus.COMPLETED else 0.0
        )
        
        # Calculate effectiveness based on task outcome
        if task.status == TaskStatus.COMPLETED:
            completion_time = (task.completed_at - task.started_at).total_seconds()
            expected_time = self.metrics.average_completion_time or completion_time
            learning_event.effectiveness = min(1.0, expected_time / max(completion_time, 1.0))
        else:
            learning_event.effectiveness = 0.0
        
        self.learning_history.append(learning_event)
        
        # Keep only recent learning events
        cutoff = datetime.now() - timedelta(days=7)
        self.learning_history = [e for e in self.learning_history if e.timestamp > cutoff]
    
    async def _message_processor(self):
        """Process incoming messages"""
        while self.state != AgentState.OFFLINE:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Message processing error: {str(e)}")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message"""
        message_type = message.get("type")
        sender = message.get("sender")
        data = message.get("data", {})
        
        self.logger.debug(f"Received message type '{message_type}' from {sender}")
        
        if message_type == "task_assignment":
            task_data = data.get("task")
            if task_data:
                task = Task(**task_data)
                await self.add_task(task)
        
        elif message_type == "configuration_update":
            config_updates = data.get("config", {})
            self.config.update(config_updates)
            self.logger.info("Configuration updated")
        
        elif message_type == "health_check":
            response = {
                "type": "health_response",
                "sender": self.agent_id,
                "data": {
                    "status": self.state.value,
                    "metrics": {
                        "tasks_completed": self.metrics.tasks_completed,
                        "tasks_failed": self.metrics.tasks_failed,
                        "success_rate": self.metrics.success_rate,
                        "uptime": str(self.metrics.uptime)
                    }
                }
            }
            await self._send_message(sender, response)
        
        await self._emit_event("message_received", {"message": message})
    
    async def _send_message(self, recipient: str, message: Dict[str, Any]):
        """Send message to another agent"""
        # This would typically integrate with the communication system
        await self._emit_event("send_message", {"recipient": recipient, "message": message})
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to registered handlers"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        await asyncio.get_event_loop().run_in_executor(
                            self.executor, handler, data
                        )
                except Exception as e:
                    self.logger.error(f"Event handler error: {str(e)}")
    
    # Public API methods
    
    async def add_task(self, task: Task):
        """Add a task to the agent's queue"""
        await self.task_queue.put(task)
        self.logger.info(f"Task '{task.name}' added to queue")
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """Add an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable):
        """Remove an event handler"""
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "state": self.state.value,
            "capabilities": [cap.value for cap in self.capabilities],
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "success_rate": self.metrics.success_rate,
                "average_completion_time": self.metrics.average_completion_time,
                "learning_score": self.metrics.learning_score,
                "efficiency_score": self.metrics.efficiency_score,
                "uptime": str(self.metrics.uptime)
            },
            "active_tasks": len(self.active_tasks),
            "queue_size": self.task_queue.qsize(),
            "learning_events": len(self.learning_history)
        }
    
    async def shutdown(self):
        """Gracefully shutdown the agent"""
        self.logger.info(f"Shutting down agent {self.name}")
        self.state = AgentState.OFFLINE
        
        # Save final state
        await self._save_knowledge_base()
        
        # Wait for active tasks to complete (with timeout)
        if self.active_tasks:
            self.logger.info(f"Waiting for {len(self.active_tasks)} active tasks to complete")
            timeout = 30
            start_time = time.time()
            
            while self.active_tasks and (time.time() - start_time) < timeout:
                await asyncio.sleep (1)  # Complete the sleep call
            
            # Cancel remaining tasks if timeout exceeded
            if self.active_tasks:
                self.logger.warning(f"Force cancelling {len(self.active_tasks)} tasks due to shutdown timeout")
                for task in self.active_tasks.values():
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now()
                    task.error = "Cancelled during shutdown"
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        self.logger.info(f"Agent {self.name} shutdown complete")
    
    async def get_api_client(self, provider: APIProvider, preference: str = "general") -> Optional[APICredential]:
        """Get an available API credential for the specified provider"""
        if provider not in self.api_credentials:
            return None
        
        # Filter active credentials
        active_credentials = [cred for cred in self.api_credentials[provider] if cred.is_active]
        if not active_credentials:
            return None
        
        # Sort by usage count and last used time for load balancing
        active_credentials.sort(key=lambda x: (x.usage_count, x.last_used or datetime.min))
        
        # Select based on preference
        if preference == "admin" and any(cred.is_admin for cred in active_credentials):
            selected = next(cred for cred in active_credentials if cred.is_admin)
        elif preference == "service" and any(cred.is_service_account for cred in active_credentials):
            selected = next(cred for cred in active_credentials if cred.is_service_account)
        else:
            selected = active_credentials[0]  # Least used
        
        # Update usage tracking
        selected.usage_count += 1
        selected.last_used = datetime.now()
        
        return selected
    
    async def make_api_request(
        self, 
        provider: APIProvider, 
        endpoint: str, 
        method: str = "GET",
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        preference: str = "general"
    ) -> Optional[Dict]:
        """Make an authenticated API request"""
        credential = await self.get_api_client(provider, preference)
        if not credential:
            raise Exception(f"No active credentials available for {provider.value}")
        
        try:
            async with aiohttp.ClientSession() as session:
                request_headers = headers or {}
                
                # Add authentication headers based on provider
                if provider == APIProvider.OPENAI:
                    request_headers["Authorization"] = f"Bearer {credential.key}"
                elif provider == APIProvider.CLAUDE:
                    request_headers["x-api-key"] = credential.key
                    request_headers["anthropic-version"] = "2023-06-01"
                elif provider == APIProvider.GITHUB:
                    request_headers["Authorization"] = f"token {credential.key}"
                elif provider == APIProvider.GEMINI:
                    # Gemini uses key as query parameter
                    endpoint += f"?key={credential.key}"
                elif provider == APIProvider.DEEPSEEK:
                    request_headers["Authorization"] = f"Bearer {credential.key}"
                elif provider == APIProvider.GROQ:
                    request_headers["Authorization"] = f"Bearer {credential.key}"
                elif provider == APIProvider.PINECONE:
                    request_headers["Api-Key"] = credential.key
                
                # Make the request
                if method.upper() == "GET":
                    async with session.get(endpoint, headers=request_headers) as response:
                        return await response.json()
                elif method.upper() == "POST":
                    async with session.post(endpoint, headers=request_headers, json=data) as response:
                        return await response.json()
                elif method.upper() == "PUT":
                    async with session.put(endpoint, headers=request_headers, json=data) as response:
                        return await response.json()
                elif method.upper() == "DELETE":
                    async with session.delete(endpoint, headers=request_headers) as response:
                        return await response.json()
                
        except Exception as e:
            self.logger.error(f"API request to {provider.value} failed: {str(e)}")
            # Mark credential as potentially problematic if multiple failures
            credential.usage_count += 10  # Penalty for failed requests
            raise
    
    async def generate_text(
        self,
        prompt: str,
        provider: APIProvider = APIProvider.CLAUDE,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text using specified AI provider"""
        try:
            if provider == APIProvider.OPENAI:
                model = model or "gpt-4"
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
                response = await self.make_api_request(
                    provider, "https://api.openai.com/v1/chat/completions", "POST", data
                )
                return response["choices"][0]["message"]["content"]
            
            elif provider == APIProvider.CLAUDE:
                model = model or "claude-3-sonnet-20240229"
                data = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                    **kwargs
                }
                response = await self.make_api_request(
                    provider, "https://api.anthropic.com/v1/messages", "POST", data
                )
                return response["content"][0]["text"]
            
            elif provider == APIProvider.GEMINI:
                model = model or "gemini-pro"
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature,
                        **kwargs
                    }
                }
                response = await self.make_api_request(
                    provider, f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", "POST", data
                )
                return response["candidates"][0]["content"]["parts"][0]["text"]
            
            elif provider == APIProvider.DEEPSEEK:
                model = model or "deepseek-coder"
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
                response = await self.make_api_request(
                    provider, "https://api.deepseek.com/v1/chat/completions", "POST", data
                )
                return response["choices"][0]["message"]["content"]
            
            elif provider == APIProvider.GROQ:
                model = model or "mixtral-8x7b-32768"
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs
                }
                response = await self.make_api_request(
                    provider, "https://api.groq.com/openai/v1/chat/completions", "POST", data
                )
                return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            self.logger.error(f"Text generation failed with {provider.value}: {str(e)}")
            raise
    
    async def store_embedding(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """Store text embedding in vector database"""
        if APIProvider.PINECONE not in self.api_credentials:
            self.logger.warning("Pinecone credentials not available for embedding storage")
            return ""
        
        try:
            # Generate embedding using OpenAI
            embedding_data = {
                "model": "text-embedding-ada-002",
                "input": text
            }
            embedding_response = await self.make_api_request(
                APIProvider.OPENAI, "https://api.openai.com/v1/embeddings", "POST", embedding_data
            )
            embedding = embedding_response["data"][0]["embedding"]
            
            # Store in Pinecone
            vector_id = str(uuid.uuid4())
            pinecone_data = {
                "vectors": [{
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "agent_id": self.agent_id,
                        "timestamp": datetime.now().isoformat(),
                        "text": text[:1000],  # Truncate for metadata storage
                        **(metadata or {})
                    }
                }]
            }
            
            await self.make_api_request(
                APIProvider.PINECONE, "https://api.pinecone.io/vectors/upsert", "POST", pinecone_data
            )
            
            return vector_id
            
        except Exception as e:
            self.logger.error(f"Failed to store embedding: {str(e)}")
            return ""
    
    async def search_embeddings(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search for similar embeddings"""
        if APIProvider.PINECONE not in self.api_credentials:
            return []
        
        try:
            # Generate query embedding
            embedding_data = {
                "model": "text-embedding-ada-002",
                "input": query
            }
            embedding_response = await self.make_api_request(
                APIProvider.OPENAI, "https://api.openai.com/v1/embeddings", "POST", embedding_data
            )
            query_embedding = embedding_response["data"][0]["embedding"]
            
            # Search Pinecone
            search_data = {
                "vector": query_embedding,
                "topK": top_k,
                "includeMetadata": True,
                "includeValues": False
            }
            
            search_response = await self.make_api_request(
                APIProvider.PINECONE, "https://api.pinecone.io/query", "POST", search_data
            )
            
            return search_response.get("matches", [])
            
        except Exception as e:
            self.logger.error(f"Failed to search embeddings: {str(e)}")
            return []
    
    async def collaborate_with_agent(self, agent_id: str, message: Dict[str, Any]) -> Optional[Dict]:
        """Send a collaboration request to another agent"""
        collaboration_message = {
            "type": "collaboration_request",
            "sender": self.agent_id,
            "recipient": agent_id,
            "data": message,
            "timestamp": datetime.now().isoformat()
        }
        
        # This would typically go through the communication system
        await self._emit_event("collaboration_request", collaboration_message)
        return collaboration_message
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from learning history"""
        if not self.learning_history:
            return {"insights": "No learning data available"}
        
        recent_events = [e for e in self.learning_history 
                        if e.timestamp > datetime.now() - timedelta(hours=24)]
        
        if not recent_events:
            return {"insights": "No recent learning data available"}
        
        insights = {
            "total_events": len(recent_events),
            "average_confidence": sum(e.confidence for e in recent_events) / len(recent_events),
            "effectiveness_trend": [],
            "common_patterns": {},
            "improvement_areas": []
        }
        
        # Analyze effectiveness trend
        effectiveness_scores = [e.effectiveness for e in recent_events if e.effectiveness is not None]
        if effectiveness_scores:
            insights["average_effectiveness"] = sum(effectiveness_scores) / len(effectiveness_scores)
            insights["effectiveness_trend"] = effectiveness_scores[-10:]  # Last 10 scores
        
        # Identify improvement areas
        failed_events = [e for e in recent_events if e.effectiveness and e.effectiveness < 0.5]
        if failed_events:
            insights["improvement_areas"] = [
                f"Task type: {e.input_data.get('task_name', 'Unknown')}" 
                for e in failed_events[:5]
            ]
        
        return insights
    
    async def backup_state(self) -> str:
        """Create a backup of agent state"""
        backup_data = {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": [cap.value for cap in self.capabilities],
            "config": self.config,
            "knowledge_base": self.knowledge_base,
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "success_rate": self.metrics.success_rate,
                "learning_score": self.metrics.learning_score
            },
            "learning_history": [
                {
                    "id": event.id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "confidence": event.confidence,
                    "effectiveness": event.effectiveness
                }
                for event in self.learning_history[-100:]  # Last 100 events
            ],
            "backup_timestamp": datetime.now().isoformat()
        }
        
        backup_id = f"backup_{self.agent_id}_{int(time.time())}"
        backup_path = Path(f"backups/{backup_id}.json")
        backup_path.parent.mkdir(exist_ok=True)
        
        async with aiofiles.open(backup_path, 'w') as f:
            await f.write(json.dumps(backup_data, indent=2))
        
        self.logger.info(f"Agent state backed up to {backup_path}")
        return backup_id
    
    async def restore_state(self, backup_id: str) -> bool:
        """Restore agent state from backup"""
        backup_path = Path(f"backups/{backup_id}.json")
        
        if not backup_path.exists():
            self.logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            async with aiofiles.open(backup_path, 'r') as f:
                backup_data = json.loads(await f.read())
            
            # Restore configuration
            self.config.update(backup_data.get("config", {}))
            
            # Restore knowledge base
            self.knowledge_base = backup_data.get("knowledge_base", {})
            
            # Restore learning history
            learning_data = backup_data.get("learning_history", [])
            self.learning_history = []
            
            for event_data in learning_data:
                event = LearningEvent(
                    id=event_data["id"],
                    agent_id=self.agent_id,
                    event_type=LearningType(event_data["event_type"]),
                    timestamp=datetime.fromisoformat(event_data["timestamp"]),
                    confidence=event_data["confidence"],
                    effectiveness=event_data.get("effectiveness")
                )
                self.learning_history.append(event)
            
            self.logger.info(f"Agent state restored from {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore state from backup: {str(e)}")
            return False
    
    def __repr__(self) -> str:
        """String representation of the agent"""
        return f"<{self.__class__.__name__}(id='{self.agent_id}', name='{self.name}', state='{self.state.value}')>"
    
    def __str__(self) -> str:
        """Human-readable string representation"""
        return f"{self.name} ({self.agent_id}) - State: {self.state.value}, Tasks: {len(self.active_tasks)} active"


class AgentRegistry:
    """Registry for managing multiple agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[str, type] = {}
        self.logger = logging.getLogger("agent_registry")
    
    def register_agent_type(self, name: str, agent_class: type):
        """Register an agent type"""
        self.agent_types[name] = agent_class
        self.logger.info(f"Registered agent type: {name}")
    
    async def create_agent(
        self, 
        agent_type: str, 
        agent_id: str = None, 
        **kwargs
    ) -> Optional[BaseAgent]:
        """Create a new agent instance"""
        if agent_type not in self.agent_types:
            self.logger.error(f"Unknown agent type: {agent_type}")
            return None
        
        try:
            agent_class = self.agent_types[agent_type]
            agent = agent_class(agent_id=agent_id, **kwargs)
            
            self.agents[agent.agent_id] = agent
            self.logger.info(f"Created agent: {agent.agent_id}")
            
            return agent
            
        except Exception as e:
            self.logger.error(f"Failed to create agent: {str(e)}")
            return None
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_agents_by_capability(self, capability: AgentCapability) -> List[BaseAgent]:
        """Get agents with specific capability"""
        return [agent for agent in self.agents.values() 
                if capability in agent.capabilities]
    
    async def shutdown_all(self):
        """Shutdown all registered agents"""
        self.logger.info("Shutting down all agents")
        
        shutdown_tasks = [agent.shutdown() for agent in self.agents.values()]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        self.agents.clear()
        self.logger.info("All agents shut down")


# Global agent registry instance
agent_registry = AgentRegistry()