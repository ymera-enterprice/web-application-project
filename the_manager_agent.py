"""
YMERA Enterprise Multi-Agent System - The Manager Agent
Core orchestrator responsible for task distribution, outcome evaluation, and live reporting
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from collections import defaultdict, deque
import traceback
import psutil
import threading

from ymera_core.config import ConfigManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_agents.communication.message_bus import MessageBus
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_services.ai.multi_llm_manager import MultiLLMManager

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5

class AgentCapability(Enum):
    CODE_ANALYSIS = "code_analysis"
    CODE_GENERATION = "code_generation"
    SECURITY_SCANNING = "security_scanning"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    UI_DESIGN = "ui_design"
    PROJECT_MANAGEMENT = "project_management"
    COMMUNICATION = "communication"
    LEARNING = "learning"
    VALIDATION = "validation"
    ENHANCEMENT = "enhancement"
    EXAMINATION = "examination"
    ORCHESTRATION = "orchestration"
    EDITING = "editing"
    BROWSER_AUTOMATION = "browser_automation"
    DATA_ANALYSIS = "data_analysis"
    FILE_MANAGEMENT = "file_management"

@dataclass
class Task:
    id: str
    name: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    assigned_agent: Optional[str]
    created_at: datetime
    updated_at: datetime
    deadline: Optional[datetime]
    dependencies: List[str]
    required_capabilities: List[AgentCapability]
    context: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    execution_time: Optional[float] = None
    quality_score: Optional[float] = None

@dataclass
class AgentPerformanceMetrics:
    agent_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_completion_time: float
    success_rate: float
    current_load: int
    capabilities: List[AgentCapability]
    last_active: datetime
    reliability_score: float
    expertise_scores: Dict[str, float]
    resource_usage: Dict[str, float]
    quality_scores: List[float]

class KeyManager:
    """Manages API keys and access distribution among agents"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.key_pools = {
            'openai': {
                'primary': config.openai_api_keys[:5],  # 5 primary keys
                'service': config.openai_service_keys[:3]  # 3 service account keys
            },
            'claude': config.claude_api_keys[:7],
            'gemini': config.gemini_api_keys[:5],
            'deepseek': config.deepseek_api_keys[:5],
            'groq': config.groq_api_keys[:5],
            'github': {
                'admin': config.github_admin_key,
                'regular': config.github_api_keys[:2]
            },
            'pinecone': config.pinecone_api_key
        }
        
        self.key_usage = defaultdict(lambda: defaultdict(int))
        self.key_last_used = defaultdict(lambda: defaultdict(datetime))
        self.key_errors = defaultdict(lambda: defaultdict(int))
        self.rate_limits = {
            'openai': 60,  # requests per minute
            'claude': 50,
            'gemini': 60,
            'deepseek': 100,
            'groq': 100,
            'github': 5000  # per hour
        }
        
    async def get_available_key(self, service: str, agent_id: str) -> Optional[str]:
        """Get an available API key for the specified service"""
        if service not in self.key_pools:
            return None
            
        keys = self.key_pools[service]
        if isinstance(keys, dict):
            # Handle nested key structure (OpenAI, GitHub)
            if service == 'openai':
                # Prefer primary keys for regular operations
                available_keys = keys['primary'] + keys['service']
            elif service == 'github':
                # Use admin key for special operations, regular keys otherwise
                available_keys = [keys['admin']] + keys['regular']
            else:
                available_keys = list(keys.values())
        else:
            available_keys = keys if isinstance(keys, list) else [keys]
        
        # Find least recently used key that's under rate limit
        best_key = None
        min_usage = float('inf')
        
        for key in available_keys:
            # Skip keys with recent errors
            if self.key_errors[service][key] > 5:
                continue
                
            current_usage = self.key_usage[service][key]
            last_used = self.key_last_used[service][key]
            
            # Check rate limiting
            if self._is_rate_limited(service, key, last_used, current_usage):
                continue
                
            if current_usage < min_usage:
                min_usage = current_usage
                best_key = key
        
        if best_key:
            self.key_usage[service][best_key] += 1
            self.key_last_used[service][best_key] = datetime.utcnow()
            
        return best_key
    
    def _is_rate_limited(self, service: str, key: str, last_used: datetime, current_usage: int) -> bool:
        """Check if a key is rate limited"""
        if service not in self.rate_limits:
            return False
            
        limit = self.rate_limits[service]
        time_window = timedelta(minutes=1) if service != 'github' else timedelta(hours=1)
        
        if datetime.utcnow() - last_used > time_window:
            # Reset usage counter for new time window
            self.key_usage[service][key] = 0
            return False
            
        return current_usage >= limit
    
    async def report_key_error(self, service: str, key: str, error: str) -> None:
        """Report an error with a specific key"""
        self.key_errors[service][key] += 1
        
        # If too many errors, temporarily disable key
        if self.key_errors[service][key] > 10:
            # Remove from available keys temporarily
            pass
    
    async def get_key_health_report(self) -> Dict[str, Any]:
        """Get health report for all keys"""
        report = {}
        
        for service, keys in self.key_pools.items():
            service_keys = keys if not isinstance(keys, dict) else []
            if isinstance(keys, dict):
                for key_type, key_list in keys.items():
                    if isinstance(key_list, list):
                        service_keys.extend(key_list)
                    else:
                        service_keys.append(key_list)
            
            service_report = []
            for key in service_keys:
                key_id = key[:8] + "..." if len(key) > 8 else key
                service_report.append({
                    'key_id': key_id,
                    'usage_count': self.key_usage[service][key],
                    'error_count': self.key_errors[service][key],
                    'last_used': self.key_last_used[service][key].isoformat() if self.key_last_used[service][key] else None,
                    'status': 'healthy' if self.key_errors[service][key] < 5 else 'degraded'
                })
            
            report[service] = service_report
        
        return report

class ResourceMonitor:
    """Monitors system resources and agent performance"""
    
    def __init__(self):
        self.cpu_usage_history = deque(maxlen=100)
        self.memory_usage_history = deque(maxlen=100)
        self.disk_usage_history = deque(maxlen=100)
        self.network_stats = {}
        
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Update history
            self.cpu_usage_history.append(cpu_percent)
            self.memory_usage_history.append(memory_percent)
            self.disk_usage_history.append(disk_percent)
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'average_5min': sum(list(self.cpu_usage_history)[-5:]) / min(5, len(self.cpu_usage_history))
                },
                'memory': {
                    'percent': memory_percent,
                    'available_gb': memory_available / (1024**3),
                    'total_gb': memory.total / (1024**3)
                },
                'disk': {
                    'percent': disk_percent,
                    'free_gb': disk.free / (1024**3),
                    'total_gb': disk.total / (1024**3)
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            }
            
        except Exception as e:
            return {'error': str(e)}

class TheManagerAgent:
    """
    The Manager Agent - Central orchestrator for the multi-agent system
    Responsible for task distribution, agent coordination, and system governance
    """
    
    def __init__(
        self,
        config: ConfigManager,
        db_manager: DatabaseManager,
        cache_manager: RedisCacheManager,
        message_bus: MessageBus,
        learning_engine: LearningEngine,
        ai_manager: MultiLLMManager,
        logger: StructuredLogger
    ):
        self.config = config
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        self.message_bus = message_bus
        self.learning_engine = learning_engine
        self.ai_manager = ai_manager
        self.logger = logger
        
        # Core components
        self.key_manager = KeyManager(config)
        self.resource_monitor = ResourceMonitor()
        self.agent_registry: Dict[str, AgentPerformanceMetrics] = {}
        self.task_queue: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.failed_tasks: Dict[str, Task] = {}
        self.task_history: deque = deque(maxlen=10000)
        
        # Learning and adaptation
        self.performance_history: Dict[str, List[float]] = defaultdict(list)
        self.task_patterns: Dict[str, Any] = {}
        self.optimization_metrics: Dict[str, Any] = {}
        self.learning_cycles: int = 0
        
        # Real-time monitoring
        self.system_health: Dict[str, Any] = {}
        self.live_reports: deque = deque(maxlen=1000)
        self.alert_thresholds = {
            'task_failure_rate': 0.2,
            'agent_response_time': 30.0,
            'system_load': 0.8,
            'memory_usage': 85.0,
            'cpu_usage': 90.0
        }
        
        # Governance and compliance
        self.governance_rules: Dict[str, Any] = {}
        self.compliance_checks: List[str] = []
        self.audit_trail: List[Dict[str, Any]] = []
        self.security_policies: Dict[str, Any] = {}
        
        # Advanced features
        self.auto_scaling_enabled = True
        self.quality_gate_enabled = True
        self.continuous_learning_enabled = True
        self.predictive_scaling = True
        
        self.running = False
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Initialize the manager agent"""
        self.logger.info("Initializing Manager Agent...")
        
        try:
            # Load governance rules and compliance requirements
            await self._load_governance_config()
            
            # Initialize agent registry
            await self._initialize_agent_registry()
            
            # Set up message bus subscriptions
            await self._setup_message_subscriptions()
            
            # Initialize learning engine
            await self._initialize_learning_engine()
            
            # Start background tasks
            background_tasks = [
                asyncio.create_task(self._task_distributor()),
                asyncio.create_task(self._performance_monitor()),
                asyncio.create_task(self._health_monitor()),
                asyncio.create_task(self._learning_optimizer()),
                asyncio.create_task(self._live_reporter()),
                asyncio.create_task(self._resource_monitor()),
                asyncio.create_task(self._auto_scaler()),
                asyncio.create_task(self._quality_controller()),
                asyncio.create_task(self._compliance_monitor()),
                asyncio.create_task(self._predictive_analyzer())
            ]
            
            self.background_tasks = background_tasks
            self.running = True
            
            # Add startup audit entry
            await self._add_audit_entry("system_startup", {
                "timestamp": datetime.utcnow().isoformat(),
                "components_initialized": len(background_tasks),
                "governance_rules_loaded": len(self.governance_rules),
                "compliance_checks_active": len(self.compliance_checks)
            })
            
            self.logger.info("Manager Agent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Manager Agent: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
    async def _load_governance_config(self) -> None:
        """Load AI governance and compliance configuration"""
        self.governance_rules = {
            'model_usage_policies': {
                'openai': {
                    'max_tokens': 4000, 
                    'temperature_range': [0.1, 0.9],
                    'allowed_models': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
                    'content_filters': ['harmful', 'illegal', 'privacy']
                },
                'claude': {
                    'max_tokens': 4000, 
                    'temperature_range': [0.1, 0.9],
                    'allowed_models': ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
                    'content_filters': ['harmful', 'illegal', 'privacy']
                },
                'gemini': {
                    'max_tokens': 4000, 
                    'temperature_range': [0.1, 0.9],
                    'allowed_models': ['gemini-pro', 'gemini-pro-vision'],
                    'safety_settings': 'high'
                },
                'deepseek': {
                    'max_tokens': 4000, 
                    'temperature_range': [0.1, 0.9],
                    'code_execution_allowed': True
                },
                'groq': {
                    'max_tokens': 4000, 
                    'temperature_range': [0.1, 0.9],
                    'high_performance_mode': True
                }
            },
            'data_handling': {
                'pii_protection': True,
                'data_retention_days': 90,
                'encryption_required': True,
                'anonymization_required': True,
                'audit_logging': True
            },
            'code_generation': {
                'security_scan_required': True,
                'license_compliance': True,
                'documentation_required': True,
                'testing_required': True,
                'code_review_required': True,
                'vulnerability_scanning': True
            },
            'quality_gates': {
                'minimum_test_coverage': 80,
                'maximum_cyclomatic_complexity': 10,
                'security_scan_pass': True,
                'performance_benchmarks': True
            },
            'resource_limits': {
                'max_concurrent_tasks_per_agent': 5,
                'max_memory_usage_mb': 2048,
                'max_cpu_time_seconds': 300,
                'max_file_size_mb': 100
            }
        }
        
        self.compliance_checks = [
            'security_vulnerability_scan',
            'license_compliance_check',
            'data_privacy_validation',
            'code_quality_assessment',
            'performance_impact_analysis',
            'accessibility_compliance',
            'regulatory_compliance',
            'ethical_ai_validation'
        ]
        
        self.security_policies = {
            'authentication': {
                'multi_factor_required': True,
                'session_timeout_minutes': 30,
                'password_complexity': True
            },
            'authorization': {
                'role_based_access': True,
                'principle_of_least_privilege': True,
                'regular_access_review': True
            },
            'encryption': {
                'data_at_rest': True,
                'data_in_transit': True,
                'key_rotation_days': 30
            },
            'monitoring': {
                'real_time_threat_detection': True,
                'anomaly_detection': True,
                'incident_response': True
            }
        }
        
    async def _initialize_agent_registry(self) -> None:
        """Initialize the registry of available agents"""
        # Load existing agent data from database
        try:
            stored_agents = await self.db_manager.get_active_agents()
            for agent_data in stored_agents:
                metrics = AgentPerformanceMetrics(**agent_data)
                self.agent_registry[metrics.agent_id] = metrics
                
        except Exception as e:
            self.logger.warning(f"Could not load stored agent data: {str(e)}")
            self.agent_registry = {}
        
    async def _setup_message_subscriptions(self) -> None:
        """Set up message bus subscriptions for agent communication"""
        subscriptions = [
            ("agent_registration", self._handle_agent_registration),
            ("task_completion", self._handle_task_completion),
            ("task_failure", self._handle_task_failure),
            ("task_progress", self._handle_task_progress),
            ("agent_status_update", self._handle_agent_status_update),
            ("system_alert", self._handle_system_alert),
            ("resource_request", self._handle_resource_request),
            ("quality_report", self._handle_quality_report),
            ("learning_feedback", self._handle_learning_feedback)
        ]
        
        for topic, handler in subscriptions:
            await self.message_bus.subscribe(topic, handler)
    
    async def _initialize_learning_engine(self) -> None:
        """Initialize the learning engine with historical data"""
        try:
            # Load historical task data
            historical_tasks = await self.db_manager.get_task_history(limit=1000)
            
            for task_data in historical_tasks:
                await self.learning_engine.add_historical_data(task_data)
            
            # Initialize learning models
            await self.learning_engine.initialize_models()
            
            self.logger.info(f"Learning engine initialized with {len(historical_tasks)} historical tasks")
            
        except Exception as e:
            self.logger.warning(f"Could not fully initialize learning engine: {str(e)}")
    
    async def register_agent(self, agent_id: str, capabilities: List[AgentCapability], 
                           metadata: Dict[str, Any] = None) -> bool:
        """Register a new agent with the manager"""
        try:
            metrics = AgentPerformanceMetrics(
                agent_id=agent_id,
                total_tasks=0,
                completed_tasks=0,
                failed_tasks=0,
                average_completion_time=0.0,
                success_rate=1.0,
                current_load=0,
                capabilities=capabilities,
                last_active=datetime.utcnow(),
                reliability_score=1.0,
                expertise_scores={cap.value: 0.5 for cap in capabilities},
                resource_usage={'cpu': 0.0, 'memory': 0.0},
                quality_scores=[]
            )
            
            self.agent_registry[agent_id] = metrics
            
            # Store in database
            await self.db_manager.store_agent_registration(agent_id, asdict(metrics), metadata or {})
            
            # Notify other agents of new registration
            await self.message_bus.publish("agent_registered", {
                "agent_id": agent_id,
                "capabilities": [cap.value for cap in capabilities],
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            })
            
            # Add to audit trail
            await self._add_audit_entry("agent_registered", {
                "agent_id": agent_id,
                "capabilities": [cap.value for cap in capabilities],
                "metadata": metadata or {}
            })
            
            self.logger.info(f"Agent {agent_id} registered with capabilities: {capabilities}")
            
            # Trigger learning update
            if self.continuous_learning_enabled:
                await self.learning_engine.update_agent_profile(agent_id, capabilities)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register agent {agent_id}: {str(e)}")
            return False
    
    async def submit_task(
        self,
        name: str,
        description: str,
        priority: TaskPriority,
        required_capabilities: List[AgentCapability],
        context: Dict[str, Any],
        deadline: Optional[datetime] = None,
        dependencies: List[str] = None,
        quality_requirements: Dict[str, Any] = None,
        compliance_requirements: List[str] = None
    ) -> str:
        """Submit a new task to the system with enhanced features"""
        
        task_id = str(uuid.uuid4())
        
        # Apply governance rules
        if not await self._validate_task_governance(name, description, context):
            raise ValueError("Task violates governance rules")
        
        # Enhance context with quality and compliance requirements
        enhanced_context = context.copy()
        enhanced_context.update({
            'quality_requirements': quality_requirements or {},
            'compliance_requirements': compliance_requirements or [],
            'governance_rules': self.governance_rules,
            'security_policies': self.security_policies
        })
        
        task = Task(
            id=task_id,
            name=name,
            description=description,
            priority=priority,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            deadline=deadline,
            dependencies=dependencies or [],
            required_capabilities=required_capabilities,
            context=enhanced_context
        )
        
        # Predictive task analysis
        if self.predictive_scaling:
            predicted_complexity = await self._predict_task_complexity(task)
            task.context['predicted_complexity'] = predicted_complexity
            task.context['estimated_duration'] = await self._estimate_task_duration(task)
        
        # Add to priority queue
        self.task_queue[priority].append(task)
        
        # Store in database
        await self.db_manager.store_task(task_id, asdict(task))
        
        # Log task submission
        self.logger.info(f"Task {task_id} submitted: {name} (Priority: {priority.value})")
        
        # Update audit trail
        await self._add_audit_entry("task_submitted", {
            "task_id": task_id,
            "name": name,
            "priority": priority.value,
            "capabilities_required": [cap.value for cap in required_capabilities],
            "compliance_requirements": compliance_requirements or []
        })
        
        # Add to live reports
        await self._add_live_report("task_submitted", {
            "task_id": task_id,
            "task_name": name,
            "priority": priority.value,
            "estimated_duration": task.context.get('estimated_duration'),
            "required_capabilities": [cap.value for cap in required_capabilities]
        })
        
        return task_id
    
    async def _validate_task_governance(self, name: str, description: str, context: Dict[str, Any]) -> bool:
        """Validate task against governance rules"""
        try:
            # Check for prohibited content
            prohibited_keywords = ['hack', 'exploit', 'backdoor', 'malware', 'virus']
            content = f"{name} {description}".lower()
            
            if any(keyword in content for keyword in prohibited_keywords):
                return False
            
            # Validate context data
            if 'sensitive_data' in context and not context.get('encryption_enabled'):
                return False
            
            # Check resource requirements
            if context.get('memory_limit_mb', 0) > self.governance_rules['resource_limits']['max_memory_usage_mb']:
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error validating task governance: {str(e)}")
            return False
    
    async def _predict_task_complexity(self, task: Task) -> float:
        """Predict task complexity using ML models"""
        try:
            if not hasattr(self.learning_engine, 'predict_complexity'):
                return 0.5  # Default moderate complexity
                
            features = {
                'description_length': len(task.description),
                'num_capabilities': len(task.required_capabilities),
                'has_deadline': task.deadline is not None,
                'num_dependencies': len(task.dependencies),
                'priority_level': task.priority.value
            }
            
            complexity = await self.learning_engine.predict_complexity(features)
            return max(0.0, min(1.0, complexity))
            
        except Exception as e:
            self.logger.warning(f"Could not predict task complexity: {str(e)}")
            return 0.5
    
    async def _estimate_task_duration(self, task: Task) -> float:
        """Estimate task duration in minutes"""
        try:
            # Base estimation logic
            base_duration = 10.0  # 10 minutes base
            
            # Adjust based on complexity
            complexity = task.context.get('predicted_complexity', 0.5)
            complexity_factor = 1.0 + complexity * 2.0  # 1x to 3x multiplier
            
            # Adjust based on capabilities required
            capability_factor = 1.0 + len(task.required_capabilities) * 0.2
            
            # Adjust based on priority (higher priority tasks might be more complex)
            priority_factor = 1.0 + (task.priority.value - 1) * 0.3
            
            estimated_duration = base_duration * complexity_factor * capability_factor * priority_factor
            
            # Use learning engine if available
            if hasattr(self.learning_engine, 'estimate_duration'):
                ml_estimate = await self.learning_engine.estimate_duration(task)
                if ml_estimate:
                    estimated_duration = (estimated_duration + ml_estimate) / 2
            
            return estimated_duration
            
        except Exception as e:
            self.logger.warning(f"Could not estimate task duration: {str(e)}")
            return 15.0  # Default 15 minutes
    
    async def _task_distributor(self) -> None:
        """Enhanced task distribution loop with intelligent assignment"""
        while self.running:
            try:
                # Process tasks by priority
                for priority in reversed(TaskPriority):
                    queue = self.task_queue[priority]
                    
                    # Process multiple tasks concurrently if possible
                    tasks_to_assign = []
                    
                    while queue and len(tasks_to_assign) < 5:  # Process up to 5 tasks at once
                        task = queue.popleft()
                        
                        # Check dependencies
                        if not await self._check_task_dependencies(task):
                            # Put back in queue for later
                            queue.append(task)
                            continue
                        
                        # Check if task should be cancelled (expired, etc.)
                        if await self._should_cancel_task(task):
                            await self._cancel_task(task)
                            continue
                        
                        tasks_to_assign.append(task)
                    
                    # Assign tasks to agents
                    for task in tasks_to_assign:
                        best_agent = await self._find_best_agent(task)
                        
                        if best_agent:
                            await self._assign_task(task, best_agent)
                        else:
                            # No available agent, put back in queue
                            queue.appendleft(task)
                
                # Adaptive sleep based on system load
                system_load = len(self.active_tasks) / max(1, len(self.agent_registry) * self.config.max_agent_load)
                sleep_time = max(0.5, min(5.0, 2.0 - system_load))
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in task distributor: {str(e)}")
                await asyncio.sleep(5)
    
    async def _should_cancel_task(self, task: Task) -> bool:
        """Determine if a task should be cancelled"""
        try:
            # Check deadline
            if task.deadline and datetime.utcnow() > task.deadline:
                return True
            
            # Check if stuck in queue too long
            time_in_queue = (datetime.utcnow # Check if stuck in queue too long
            time_in_queue = (datetime.utcnow() - task.created_at).total_seconds() / 60  # minutes
            max_queue_time = self.config.max_task_queue_time_minutes
            
            if time_in_queue > max_queue_time:
                self.logger.warning(f"Task {task.id} cancelled due to excessive queue time: {time_in_queue:.1f} minutes")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking if task should be cancelled: {str(e)}")
            return False
    
    async def _cancel_task(self, task: Task) -> None:
        """Cancel a task and update tracking"""
        try:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.utcnow()
            
            # Store cancellation
            await self.db_manager.update_task_status(task.id, TaskStatus.CANCELLED)
            
            # Add to audit trail
            await self._add_audit_entry("task_cancelled", {
                "task_id": task.id,
                "reason": "deadline_expired_or_queue_timeout",
                "time_in_queue": (datetime.utcnow() - task.created_at).total_seconds() / 60
            })
            
            # Notify stakeholders
            await self.message_bus.publish("task_cancelled", {
                "task_id": task.id,
                "task_name": task.name,
                "reason": "timeout",
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error cancelling task {task.id}: {str(e)}")
    
    async def _check_task_dependencies(self, task: Task) -> bool:
        """Check if all task dependencies are satisfied"""
        try:
            if not task.dependencies:
                return True
            
            for dep_task_id in task.dependencies:
                # Check if dependency is completed
                if dep_task_id in self.completed_tasks:
                    continue
                elif dep_task_id in self.active_tasks:
                    return False  # Still running
                elif dep_task_id in self.failed_tasks:
                    return False  # Failed dependency
                else:
                    # Check database for task status
                    dep_status = await self.db_manager.get_task_status(dep_task_id)
                    if dep_status != TaskStatus.COMPLETED:
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking task dependencies: {str(e)}")
            return False
    
    async def _find_best_agent(self, task: Task) -> Optional[str]:
        """Enhanced intelligent agent selection with ML-based matching"""
        try:
            available_agents = []
            
            for agent_id, metrics in self.agent_registry.items():
                # Check if agent is available and capable
                if (metrics.current_load < self.config.max_agent_load and 
                    self._has_required_capabilities(metrics.capabilities, task.required_capabilities)):
                    
                    # Calculate agent score
                    score = await self._calculate_agent_score(metrics, task)
                    available_agents.append((agent_id, score, metrics))
            
            if not available_agents:
                return None
            
            # Sort by score (higher is better)
            available_agents.sort(key=lambda x: x[1], reverse=True)
            
            # Use learning engine for final selection if available
            if self.continuous_learning_enabled and hasattr(self.learning_engine, 'select_best_agent'):
                ml_selection = await self.learning_engine.select_best_agent(
                    task, [agent[0] for agent in available_agents[:3]]
                )
                if ml_selection:
                    return ml_selection
            
            return available_agents[0][0]  # Return highest scored agent
            
        except Exception as e:
            self.logger.error(f"Error finding best agent for task {task.id}: {str(e)}")
            return None
    
    def _has_required_capabilities(self, agent_caps: List[AgentCapability], 
                                 required_caps: List[AgentCapability]) -> bool:
        """Check if agent has required capabilities"""
        agent_cap_set = set(agent_caps)
        required_cap_set = set(required_caps)
        return required_cap_set.issubset(agent_cap_set)
    
    async def _calculate_agent_score(self, metrics: AgentPerformanceMetrics, task: Task) -> float:
        """Calculate comprehensive agent score for task assignment"""
        try:
            score = 0.0
            
            # Success rate (30% weight)
            score += metrics.success_rate * 0.3
            
            # Reliability (20% weight)
            score += metrics.reliability_score * 0.2
            
            # Load balancing (20% weight)
            load_factor = 1.0 - (metrics.current_load / self.config.max_agent_load)
            score += load_factor * 0.2
            
            # Expertise matching (25% weight)
            expertise_score = 0.0
            for cap in task.required_capabilities:
                expertise_score += metrics.expertise_scores.get(cap.value, 0.5)
            if task.required_capabilities:
                expertise_score /= len(task.required_capabilities)
            score += expertise_score * 0.25
            
            # Recent activity bonus (5% weight)
            time_since_active = (datetime.utcnow() - metrics.last_active).total_seconds() / 60
            activity_bonus = max(0, 1.0 - time_since_active / 60)  # Bonus for active in last hour
            score += activity_bonus * 0.05
            
            # Quality score bonus
            if metrics.quality_scores:
                avg_quality = sum(metrics.quality_scores) / len(metrics.quality_scores)
                score += (avg_quality - 0.5) * 0.1  # Bonus/penalty based on quality
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            self.logger.error(f"Error calculating agent score: {str(e)}")
            return 0.0
    
    async def _assign_task(self, task: Task, agent_id: str) -> None:
        """Assign task to agent with comprehensive tracking"""
        try:
            task.assigned_agent = agent_id
            task.status = TaskStatus.ASSIGNED
            task.updated_at = datetime.utcnow()
            
            # Update agent metrics
            if agent_id in self.agent_registry:
                self.agent_registry[agent_id].current_load += 1
                self.agent_registry[agent_id].total_tasks += 1
            
            # Add to active tasks
            self.active_tasks[task.id] = task
            
            # Get appropriate API key for agent
            api_keys = {}
            for service in ['openai', 'claude', 'gemini', 'deepseek', 'groq', 'github']:
                key = await self.key_manager.get_available_key(service, agent_id)
                if key:
                    api_keys[service] = key
            
            # Prepare enhanced task payload
            task_payload = {
                "task": asdict(task),
                "api_keys": api_keys,
                "system_context": {
                    "governance_rules": self.governance_rules,
                    "compliance_requirements": task.context.get('compliance_requirements', []),
                    "quality_requirements": task.context.get('quality_requirements', {}),
                    "resource_limits": self.governance_rules['resource_limits']
                },
                "learning_context": await self._get_learning_context(task, agent_id)
            }
            
            # Send task to agent
            await self.message_bus.publish(f"agent.{agent_id}.task_assigned", task_payload)
            
            # Update database
            await self.db_manager.update_task_assignment(task.id, agent_id)
            
            # Add to audit trail
            await self._add_audit_entry("task_assigned", {
                "task_id": task.id,
                "agent_id": agent_id,
                "assignment_score": await self._calculate_agent_score(self.agent_registry[agent_id], task),
                "api_keys_provided": list(api_keys.keys())
            })
            
            # Live reporting
            await self._add_live_report("task_assigned", {
                "task_id": task.id,
                "task_name": task.name,
                "agent_id": agent_id,
                "priority": task.priority.value,
                "estimated_duration": task.context.get('estimated_duration'),
                "assignment_timestamp": datetime.utcnow().isoformat()
            })
            
            self.logger.info(f"Task {task.id} assigned to agent {agent_id}")
            
        except Exception as e:
            self.logger.error(f"Error assigning task {task.id} to agent {agent_id}: {str(e)}")
            # Remove from active tasks if assignment failed
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            # Put task back in queue
            self.task_queue[task.priority].appendleft(task)
    
    async def _get_learning_context(self, task: Task, agent_id: str) -> Dict[str, Any]:
        """Get learning context for task execution"""
        try:
            context = {
                "similar_tasks": [],
                "best_practices": [],
                "common_pitfalls": [],
                "performance_expectations": {}
            }
            
            if hasattr(self.learning_engine, 'get_task_context'):
                ml_context = await self.learning_engine.get_task_context(task, agent_id)
                context.update(ml_context)
            
            return context
            
        except Exception as e:
            self.logger.warning(f"Could not get learning context: {str(e)}")
            return {}
    
    async def _performance_monitor(self) -> None:
        """Monitor agent and system performance"""
        while self.running:
            try:
                # Update agent metrics
                for agent_id, metrics in self.agent_registry.items():
                    # Calculate performance metrics
                    if metrics.total_tasks > 0:
                        metrics.success_rate = metrics.completed_tasks / metrics.total_tasks
                    
                    # Update reliability score based on recent performance
                    await self._update_reliability_score(agent_id, metrics)
                    
                    # Update expertise scores based on task outcomes
                    await self._update_expertise_scores(agent_id, metrics)
                
                # System-wide performance metrics
                await self._calculate_system_metrics()
                
                # Trigger alerts if needed
                await self._check_performance_alerts()
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in performance monitor: {str(e)}")
                await asyncio.sleep(60)
    
    async def _update_reliability_score(self, agent_id: str, metrics: AgentPerformanceMetrics) -> None:
        """Update agent reliability score based on recent performance"""
        try:
            # Get recent task outcomes for this agent
            recent_tasks = await self.db_manager.get_agent_recent_tasks(agent_id, hours=24)
            
            if not recent_tasks:
                return
            
            # Calculate reliability factors
            success_factor = sum(1 for task in recent_tasks if task.get('status') == 'completed') / len(recent_tasks)
            
            # Response time factor
            avg_response_time = sum(task.get('response_time', 0) for task in recent_tasks) / len(recent_tasks)
            response_factor = max(0, 1.0 - avg_response_time / 300)  # Penalty for >5 min response
            
            # Quality factor
            quality_scores = [task.get('quality_score', 0.5) for task in recent_tasks if task.get('quality_score')]
            quality_factor = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
            
            # Combined reliability score
            new_reliability = (success_factor * 0.4 + response_factor * 0.3 + quality_factor * 0.3)
            
            # Smooth update
            metrics.reliability_score = metrics.reliability_score * 0.7 + new_reliability * 0.3
            
        except Exception as e:
            self.logger.warning(f"Error updating reliability score for {agent_id}: {str(e)}")
    
    async def _update_expertise_scores(self, agent_id: str, metrics: AgentPerformanceMetrics) -> None:
        """Update agent expertise scores for different capabilities"""
        try:
            # Get recent tasks by capability
            capability_performance = await self.db_manager.get_agent_capability_performance(agent_id, days=7)
            
            for capability, performance_data in capability_performance.items():
                if capability in metrics.expertise_scores:
                    # Calculate expertise based on success rate and quality
                    success_rate = performance_data.get('success_rate', 0.5)
                    avg_quality = performance_data.get('average_quality', 0.5)
                    task_count = performance_data.get('task_count', 0)
                    
                    # Experience factor (more tasks = higher confidence)
                    experience_factor = min(1.0, task_count / 10)
                    
                    new_expertise = (success_rate * 0.4 + avg_quality * 0.4 + experience_factor * 0.2)
                    
                    # Smooth update
                    metrics.expertise_scores[capability] = (
                        metrics.expertise_scores[capability] * 0.8 + new_expertise * 0.2
                    )
            
        except Exception as e:
            self.logger.warning(f"Error updating expertise scores for {agent_id}: {str(e)}")
    
    async def _calculate_system_metrics(self) -> None:
        """Calculate system-wide performance metrics"""
        try:
            current_time = datetime.utcnow()
            
            # Task throughput metrics
            total_active = len(self.active_tasks)
            total_completed_today = len([
                t for t in self.completed_tasks.values() 
                if (current_time - t.updated_at).days == 0
            ])
            total_failed_today = len([
                t for t in self.failed_tasks.values() 
                if (current_time - t.updated_at).days == 0
            ])
            
            # Agent utilization
            total_agents = len(self.agent_registry)
            active_agents = len([
                m for m in self.agent_registry.values() 
                if m.current_load > 0
            ])
            
            # Average response times
            recent_completions = list(self.completed_tasks.values())[-100:]
            avg_completion_time = (
                sum(t.execution_time for t in recent_completions if t.execution_time) / 
                len(recent_completions) if recent_completions else 0
            )
            
            self.optimization_metrics.update({
                'active_tasks': total_active,
                'completed_today': total_completed_today,
                'failed_today': total_failed_today,
                'success_rate_today': (
                    total_completed_today / max(1, total_completed_today + total_failed_today)
                ),
                'agent_utilization': active_agents / max(1, total_agents),
                'average_completion_time': avg_completion_time,
                'system_load': total_active / max(1, total_agents * self.config.max_agent_load),
                'timestamp': current_time.isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error calculating system metrics: {str(e)}")
    
    async def _check_performance_alerts(self) -> None:
        """Check for performance issues and trigger alerts"""
        try:
            alerts = []
            
            # Check task failure rate
            if self.optimization_metrics.get('success_rate_today', 1.0) < self.alert_thresholds['task_failure_rate']:
                alerts.append({
                    'type': 'high_failure_rate',
                    'severity': 'high',
                    'message': f"Task failure rate is {1-self.optimization_metrics['success_rate_today']:.1%}",
                    'threshold': self.alert_thresholds['task_failure_rate']
                })
            
            # Check system load
            if self.optimization_metrics.get('system_load', 0) > self.alert_thresholds['system_load']:
                alerts.append({
                    'type': 'high_system_load',
                    'severity': 'medium',
                    'message': f"System load is {self.optimization_metrics['system_load']:.1%}",
                    'threshold': self.alert_thresholds['system_load']
                })
            
            # Check response times
            if self.optimization_metrics.get('average_completion_time', 0) > self.alert_thresholds['agent_response_time']:
                alerts.append({
                    'type': 'slow_response_time',
                    'severity': 'medium',
                    'message': f"Average completion time is {self.optimization_metrics['average_completion_time']:.1f}s",
                    'threshold': self.alert_thresholds['agent_response_time']
                })
            
            # Send alerts if any
            for alert in alerts:
                await self.message_bus.publish("system_alert", alert)
                await self._add_live_report("alert", alert)
            
        except Exception as e:
            self.logger.error(f"Error checking performance alerts: {str(e)}")
    
    async def _health_monitor(self) -> None:
        """Monitor system health and resources"""
        while self.running:
            try:
                # Collect system metrics
                system_metrics = await self.resource_monitor.collect_system_metrics()
                
                # Update system health
                self.system_health.update({
                    'timestamp': datetime.utcnow().isoformat(),
                    'system_metrics': system_metrics,
                    'agent_count': len(self.agent_registry),
                    'active_tasks': len(self.active_tasks),
                    'queue_sizes': {
                        priority.value: len(queue) 
                        for priority, queue in self.task_queue.items()
                    },
                    'database_health': await self._check_database_health(),
                    'cache_health': await self._check_cache_health(),
                    'message_bus_health': await self._check_message_bus_health(),
                    'api_key_health': await self.key_manager.get_key_health_report()
                })
                
                # Check for resource alerts
                await self._check_resource_alerts(system_metrics)
                
                await asyncio.sleep(60)  # Health check every minute
                
            except Exception as e:
                self.logger.error(f"Error in health monitor: {str(e)}")
                await asyncio.sleep(120)
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            await self.db_manager.ping()
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'last_check': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache connectivity and performance"""
        try:
            start_time = time.time()
            await self.cache_manager.ping()
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'last_check': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_message_bus_health(self) -> Dict[str, Any]:
        """Check message bus connectivity and performance"""
        try:
            start_time = time.time()
            await self.message_bus.ping()
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'last_check': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_resource_alerts(self, system_metrics: Dict[str, Any]) -> None:
        """Check system resources and trigger alerts"""
        try:
            alerts = []
            
            # Check CPU usage
            cpu_usage = system_metrics.get('cpu', {}).get('percent', 0)
            if cpu_usage > self.alert_thresholds['cpu_usage']:
                alerts.append({
                    'type': 'high_cpu_usage',
                    'severity': 'high',
                    'message': f"CPU usage is {cpu_usage:.1f}%",
                    'value': cpu_usage,
                    'threshold': self.alert_thresholds['cpu_usage']
                })
            
            # Check memory usage
            memory_usage = system_metrics.get('memory', {}).get('percent', 0)
            if memory_usage > self.alert_thresholds['memory_usage']:
                alerts.append({
                    'type': 'high_memory_usage',
                    'severity': 'high',
                    'message': f"Memory usage is {memory_usage:.1f}%",
                    'value': memory_usage,
                    'threshold': self.alert_thresholds['memory_usage']
                })
            
            # Send alerts
            for alert in alerts:
                await self.message_bus.publish("resource_alert", alert)
                await self._add_live_report("resource_alert", alert)
            
        except Exception as e:
            self.logger.error(f"Error checking resource alerts: {str(e)}")
    
    async def _learning_optimizer(self) -> None:
        """Continuous learning and optimization loop"""
        while self.running:
            try:
                if not self.continuous_learning_enabled:
                    await asyncio.sleep(300)  # Check every 5 minutes
                    continue
                
                # Collect learning data
                learning_data = await self._collect_learning_data()
                
                # Update learning models
                if learning_data:
                    await self.learning_engine.update_models(learning_data)
                
                # Optimize system parameters
                await self._optimize_system_parameters()
                
                # Update agent assignments based on learning
                await self._optimize_agent_assignments()
                
                self.learning_cycles += 1
                
                # Learning cycle frequency adapts based on system load
                cycle_interval = max(300, min(1800, 600 / max(0.1, len(self.active_tasks) / 10)))
                await asyncio.sleep(cycle_interval)
                
            except Exception as e:
                self.logger.error(f"Error in learning optimizer: {str(e)}")
                await asyncio.sleep(600)
    
    async def _collect_learning_data(self) -> Dict[str, Any]:
        """Collect data for learning and optimization"""
        try:
            # Recent task outcomes
            recent_tasks = await self.db_manager.get_recent_task_outcomes(hours=24)
            
            # Agent performance data
            agent_performance = {}
            for agent_id, metrics in self.agent_registry.items():
                agent_performance[agent_id] = {
                    'success_rate': metrics.success_rate,
                    'average_completion_time': metrics.average_completion_time,
                    'reliability_score': metrics.reliability_score,
                    'expertise_scores': metrics.expertise_scores,
                    'quality_scores': metrics.quality_scores[-10:] if metrics.quality_scores else []
                }
            
            # System performance patterns
            system_patterns = {
                'task_distribution': self.optimization_metrics,
                'resource_utilization': self.system_health.get('system_metrics', {}),
                'error_patterns': await self._analyze_error_patterns()
            }
            
            return {
                'tasks': recent_tasks,
                'agents': agent_performance,
                'system': system_patterns,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting learning data: {str(e)}")
            return {}
    
    async def _analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns for learning"""
        try:
            # Get recent errors
            recent_errors = await self.db_manager.get_recent_errors(hours=24)
            
            error_analysis = {
                'total_errors': len(recent_errors),
                'error_types': defaultdict(int),
                'agent_error_rates': defaultdict(int),
                'capability_errors': defaultdict(int)
            }
            
            for error in recent_errors:
                error_analysis['error_types'][error.get('type', 'unknown')] += 1
                error_analysis['agent_error_rates'][error.get('agent_id', 'unknown')] += 1
                
                for cap in error.get('capabilities', []):
                    error_analysis['capability_errors'][cap] += 1
            
            return dict(error_analysis)
            
        except Exception as e:
            self.logger.error(f"Error analyzing error patterns: {str(e)}")
            return {}
    
    async def _optimize_system_parameters(self) -> None:
        """Optimize system parameters based on learning"""
        try:
            if not hasattr(self.learning_engine, 'suggest_optimizations'):
                return
            
            # Get optimization suggestions
            suggestions = await self.learning_engine.suggest_optimizations(
                self.optimization_metrics, self.system_health
            )
            
            for suggestion in suggestions:
                param = suggestion.get('parameter')
                new_value = suggestion.get('value')
                confidence = suggestion.get('confidence', 0.0)
                
                if confidence < 0.7:  # Only apply high-confidence suggestions
                    continue
                
                # Apply safe parameter updates
                if param == 'max_agent_load' and 1 <= new_value <= 10:
                    self.config.max_agent_load = new_value
                elif param == 'task_queue_timeout' and 5 <= new_value <= 60:
                    self.config.max_task_queue_time_minutes = new_value
                elif param == 'alert_threshold_adjustment':
                    # Adjust alert thresholds based on system performance
                    for threshold_name, adjustment in new_value.items():
                        if threshold_name in self.alert_thresholds:
                            current = self.alert_thresholds[threshold_name]
                            self.alert_thresholds[threshold_name] = max(
                                current * 0.5, min(current * 2.0, current * (1 + adjustment))
                            )
            
        except Exception as e:
            self.logger.error(f"Error optimizing system parameters: {str(e)}")
    
    async def _optimize_agent_assignments(self) -> None:
        """Optimize future agent assignments based on learning"""
        try:
            # Analyze assignment patterns
            assignment_data = await self.db_manager.get_assignment_patterns(days=7)
            
            # Update agent scoring weights based on outcomes
            for pattern in assignment_data:
                agent_id = pattern.get('agent_id')
                capability = pattern.get('capability')
                success_rate = pattern.get('success_rate', 0.5)
                avg_quality = pattern.get('average_quality', 0.5)
                
                if agent_id in self.agent_registry and capability:
                    # Adjust expertise scores
                    current_score = self.agent_registry[agent_id].expertise_scores.get(capability, 0.5)
                    performance_score = (success_rate + avg_quality) / 2
                    
                    # Gradual adjustment
                    new_score = current_score * 0.9 + performance_score * 0.1
                    self.agent_registry[agent_id].expertise_scores[capability] = new_score
            
        except Exception as e:
            self.logger.error(f"Error optimizing agent assignments: {str(e)}")
    
    async def _live_reporter(self) -> None:
        """Generate live reports and dashboards"""
        while self.running:
            try:
                # Generate comprehensive system report
                report = await self._generate_system_report()
                
                # Add to live reports
                await self._add_live_report("system_status", report)
                
                # Store report in database for historical analysis
                await self.db_manager.store_system_report(report)
                
                # Broadcast to interested parties
                await self.message_bus.publish("live_report", report)
                
                await asyncio.sleep(30)  # Report every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in live reporter: {str(e)}")
                await asyncio.sleep(60)
    
    async def _generate_system_report(self) -> Dict[str, Any]:
        """Generate comprehensive system status report"""
        try:
            current_time = datetime.utcnow()
            
            # Task statistics
            task_stats = {
                'active': len(self.active_tasks),
                'queued': sum(len(queue) for queue in self.task_queue.values()),
                'completed_today': len([
                    t for t in self.completed_tasks.values() 
                    if (current_time - t.updated_at).days == 0
                ]),
                'failed_today': len([
                    t for t in self.failed_tasks.values() 
                    if (current_time - t.updated_at).days == 0
                ]),
                'queue_breakdown': {
                    priority.value: len(queue) 
                    for priority, queue in self.task_queue.items()
                }
            }
            
            # Agent statistics
            agent_stats = {
                'total_registered': len(self.agent_registry),
                'currently_active': len([
                    m for m in self.agent_registry.values() 
                    if m.current_load > 0
                ]),
                'utilization_rate': (
                    sum(m.current_load for # Agent statistics (continuing from where the file ended)
            agent_stats = {
                'total_registered': len(self.agent_registry),
                'currently_active': len([
                    m for m in self.agent_registry.values() 
                    if m.current_load > 0
                ]),
                'utilization_rate': (
                    sum(m.current_load for m in self.agent_registry.values()) / 
                    max(1, len(self.agent_registry) * self.config.max_agent_load)
                ),
                'average_success_rate': (
                    sum(m.success_rate for m in self.agent_registry.values()) / 
                    max(1, len(self.agent_registry))
                ),
                'top_performers': sorted([
                    {'agent_id': aid, 'success_rate': m.success_rate, 'reliability': m.reliability_score}
                    for aid, m in self.agent_registry.items()
                ], key=lambda x: x['success_rate'], reverse=True)[:5]
            }
            
            # Performance metrics
            performance = {
                'throughput': task_stats['completed_today'],
                'success_rate': (
                    task_stats['completed_today'] / 
                    max(1, task_stats['completed_today'] + task_stats['failed_today'])
                ),
                'average_completion_time': self.optimization_metrics.get('average_completion_time', 0),
                'system_load': self.optimization_metrics.get('system_load', 0),
                'resource_utilization': self.system_health.get('system_metrics', {}),
                'learning_cycles_completed': self.learning_cycles,
                'optimization_score': await self._calculate_optimization_score()
            }
            
            # Health status
            health = {
                'overall_status': self._determine_overall_health(),
                'database': self.system_health.get('database_health', {}),
                'cache': self.system_health.get('cache_health', {}),
                'message_bus': self.system_health.get('message_bus_health', {}),
                'api_keys': self.system_health.get('api_key_health', {}),
                'active_alerts': len(await self._get_active_alerts()),
                'last_health_check': current_time.isoformat()
            }
            
            # Trending data
            trending = {
                'task_volume_trend': await self._calculate_task_trend(),
                'performance_trend': await self._calculate_performance_trend(),
                'agent_efficiency_trend': await self._calculate_agent_efficiency_trend(),
                'resource_usage_trend': await self._calculate_resource_trend()
            }
            
            return {
                'timestamp': current_time.isoformat(),
                'uptime': (current_time - self.start_time).total_seconds(),
                'version': self.version,
                'tasks': task_stats,
                'agents': agent_stats,
                'performance': performance,
                'health': health,
                'trending': trending,
                'governance': {
                    'rules_enforced': len(self.governance_rules),
                    'compliance_checks': await self._get_compliance_status(),
                    'audit_entries_today': await self._count_audit_entries_today()
                },
                'learning': {
                    'enabled': self.continuous_learning_enabled,
                    'cycles_completed': self.learning_cycles,
                    'model_accuracy': await self._get_learning_model_accuracy(),
                    'optimization_improvements': await self._get_optimization_improvements()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating system report: {str(e)}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': 'Report generation failed',
                'basic_stats': {
                    'active_tasks': len(self.active_tasks),
                    'registered_agents': len(self.agent_registry)
                }
            }
    
    async def _calculate_optimization_score(self) -> float:
        """Calculate overall system optimization score"""
        try:
            score = 0.0
            
            # Task completion efficiency (25%)
            success_rate = self.optimization_metrics.get('success_rate_today', 0.5)
            score += success_rate * 0.25
            
            # Resource utilization efficiency (25%)
            utilization = self.optimization_metrics.get('system_load', 0.5)
            # Optimal load is around 70-80%
            utilization_score = 1.0 - abs(0.75 - utilization) / 0.75
            score += max(0, utilization_score) * 0.25
            
            # Agent performance (25%)
            avg_agent_performance = sum(
                m.success_rate * m.reliability_score 
                for m in self.agent_registry.values()
            ) / max(1, len(self.agent_registry))
            score += avg_agent_performance * 0.25
            
            # System health (25%)
            health_score = self._calculate_health_score()
            score += health_score * 0.25
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            self.logger.error(f"Error calculating optimization score: {str(e)}")
            return 0.5
    
    def _calculate_health_score(self) -> float:
        """Calculate system health score"""
        try:
            health_factors = []
            
            # Database health
            db_health = self.system_health.get('database_health', {})
            if db_health.get('status') == 'healthy':
                health_factors.append(1.0)
            else:
                health_factors.append(0.0)
            
            # Cache health
            cache_health = self.system_health.get('cache_health', {})
            if cache_health.get('status') == 'healthy':
                health_factors.append(1.0)
            else:
                health_factors.append(0.0)
            
            # Message bus health
            bus_health = self.system_health.get('message_bus_health', {})
            if bus_health.get('status') == 'healthy':
                health_factors.append(1.0)
            else:
                health_factors.append(0.0)
            
            # API key health
            api_health = self.system_health.get('api_key_health', {})
            available_keys = sum(
                service.get('available', 0) 
                for service in api_health.values() 
                if isinstance(service, dict)
            )
            total_keys = sum(
                service.get('total', 1) 
                for service in api_health.values() 
                if isinstance(service, dict)
            )
            key_health_score = available_keys / max(1, total_keys)
            health_factors.append(key_health_score)
            
            return sum(health_factors) / max(1, len(health_factors))
            
        except Exception as e:
            self.logger.error(f"Error calculating health score: {str(e)}")
            return 0.5
    
    def _determine_overall_health(self) -> str:
        """Determine overall system health status"""
        try:
            health_score = self._calculate_health_score()
            
            if health_score >= 0.9:
                return 'excellent'
            elif health_score >= 0.7:
                return 'good'
            elif health_score >= 0.5:
                return 'fair'
            elif health_score >= 0.3:
                return 'poor'
            else:
                return 'critical'
                
        except Exception as e:
            self.logger.error(f"Error determining health status: {str(e)}")
            return 'unknown'
    
    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active alerts"""
        try:
            # This would typically query a persistent alert store
            # For now, return recent alerts from live reports
            recent_reports = list(self.live_reports)[-50:]
            alerts = [
                report for report in recent_reports 
                if report.get('type') in ['alert', 'resource_alert']
            ]
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting active alerts: {str(e)}")
            return []
    
    async def _calculate_task_trend(self) -> Dict[str, float]:
        """Calculate task volume trends"""
        try:
            # Get hourly task counts for last 24 hours
            hourly_counts = await self.db_manager.get_hourly_task_counts(hours=24)
            
            if len(hourly_counts) < 2:
                return {'trend': 0.0, 'direction': 'stable'}
            
            # Calculate trend using linear regression
            x = list(range(len(hourly_counts)))
            y = list(hourly_counts.values())
            
            # Simple linear regression
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            
            # Normalize slope to percentage
            avg_tasks = sum_y / n
            trend_percentage = (slope / max(1, avg_tasks)) * 100
            
            direction = 'increasing' if slope > 0.1 else 'decreasing' if slope < -0.1 else 'stable'
            
            return {
                'trend': trend_percentage,
                'direction': direction,
                'current_average': avg_tasks
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating task trend: {str(e)}")
            return {'trend': 0.0, 'direction': 'unknown'}
    
    async def _calculate_performance_trend(self) -> Dict[str, float]:
        """Calculate performance trends"""
        try:
            # Get performance metrics for last 7 days
            daily_performance = await self.db_manager.get_daily_performance(days=7)
            
            if len(daily_performance) < 2:
                return {'trend': 0.0, 'direction': 'stable'}
            
            success_rates = [day.get('success_rate', 0.5) for day in daily_performance]
            
            # Calculate trend
            x = list(range(len(success_rates)))
            y = success_rates
            
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            
            trend_percentage = slope * 100
            direction = 'improving' if slope > 0.01 else 'declining' if slope < -0.01 else 'stable'
            
            return {
                'trend': trend_percentage,
                'direction': direction,
                'current_success_rate': y[-1] if y else 0.5
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating performance trend: {str(e)}")
            return {'trend': 0.0, 'direction': 'unknown'}
    
    async def _calculate_agent_efficiency_trend(self) -> Dict[str, Any]:
        """Calculate agent efficiency trends"""
        try:
            # Get agent efficiency over time
            agent_trends = {}
            
            for agent_id in self.agent_registry.keys():
                efficiency_history = await self.db_manager.get_agent_efficiency_history(
                    agent_id, days=7
                )
                
                if len(efficiency_history) >= 2:
                    # Calculate efficiency trend for this agent
                    y = [point.get('efficiency', 0.5) for point in efficiency_history]
                    x = list(range(len(y)))
                    
                    n = len(x)
                    sum_x = sum(x)
                    sum_y = sum(y)
                    sum_xy = sum(x[i] * y[i] for i in range(n))
                    sum_x2 = sum(x[i] ** 2 for i in range(n))
                    
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
                    
                    agent_trends[agent_id] = {
                        'trend': slope * 100,
                        'current_efficiency': y[-1]
                    }
            
            # Calculate overall trend
            if agent_trends:
                overall_trend = sum(data['trend'] for data in agent_trends.values()) / len(agent_trends)
                direction = 'improving' if overall_trend > 1 else 'declining' if overall_trend < -1 else 'stable'
            else:
                overall_trend = 0.0
                direction = 'stable'
            
            return {
                'overall_trend': overall_trend,
                'direction': direction,
                'agent_trends': agent_trends
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating agent efficiency trend: {str(e)}")
            return {'overall_trend': 0.0, 'direction': 'unknown', 'agent_trends': {}}
    
    async def _calculate_resource_trend(self) -> Dict[str, Any]:
        """Calculate resource usage trends"""
        try:
            # Get resource usage history
            resource_history = await self.db_manager.get_resource_usage_history(hours=24)
            
            trends = {}
            for resource_type in ['cpu', 'memory', 'disk', 'network']:
                values = [
                    point.get(resource_type, {}).get('percent', 0) 
                    for point in resource_history
                ]
                
                if len(values) >= 2:
                    x = list(range(len(values)))
                    y = values
                    
                    n = len(x)
                    sum_x = sum(x)
                    sum_y = sum(y)
                    sum_xy = sum(x[i] * y[i] for i in range(n))
                    sum_x2 = sum(x[i] ** 2 for i in range(n))
                    
                    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
                    
                    trends[resource_type] = {
                        'trend': slope,
                        'current_usage': y[-1],
                        'direction': 'increasing' if slope > 0.5 else 'decreasing' if slope < -0.5 else 'stable'
                    }
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error calculating resource trend: {str(e)}")
            return {}
    
    async def _get_compliance_status(self) -> Dict[str, Any]:
        """Get compliance status"""
        try:
            # Check various compliance aspects
            compliance = {
                'governance_rules_active': len(self.governance_rules) > 0,
                'audit_trail_active': True,  # Always active in this implementation
                'security_policies_enforced': True,
                'data_retention_compliant': await self._check_data_retention_compliance(),
                'access_controls_active': True,
                'encryption_enabled': True,
                'backup_status': await self._check_backup_status(),
                'compliance_score': 0.0
            }
            
            # Calculate compliance score
            compliance_factors = [
                compliance['governance_rules_active'],
                compliance['audit_trail_active'],
                compliance['security_policies_enforced'],
                compliance['data_retention_compliant'],
                compliance['access_controls_active'],
                compliance['encryption_enabled'],
                compliance['backup_status']
            ]
            
            compliance['compliance_score'] = sum(compliance_factors) / len(compliance_factors)
            
            return compliance
            
        except Exception as e:
            self.logger.error(f"Error getting compliance status: {str(e)}")
            return {'compliance_score': 0.0}
    
    async def _check_data_retention_compliance(self) -> bool:
        """Check if data retention policies are being followed"""
        try:
            # Check if old data is being properly cleaned up
            old_tasks = await self.db_manager.count_tasks_older_than(days=90)
            old_logs = await self.db_manager.count_logs_older_than(days=30)
            old_audit_entries = await self.db_manager.count_audit_entries_older_than(days=365)
            
            # These should be within reasonable limits
            return old_tasks < 10000 and old_logs < 100000 and old_audit_entries < 50000
            
        except Exception as e:
            self.logger.error(f"Error checking data retention compliance: {str(e)}")
            return False
    
    async def _check_backup_status(self) -> bool:
        """Check backup status"""
        try:
            # Check if recent backups exist
            last_backup = await self.db_manager.get_last_backup_timestamp()
            if not last_backup:
                return False
            
            # Backup should be within last 24 hours
            backup_age = (datetime.utcnow() - last_backup).total_seconds() / 3600
            return backup_age <= 24
            
        except Exception as e:
            self.logger.error(f"Error checking backup status: {str(e)}")
            return False
    
    async def _count_audit_entries_today(self) -> int:
        """Count audit entries created today"""
        try:
            return await self.db_manager.count_audit_entries_today()
        except Exception as e:
            self.logger.error(f"Error counting audit entries: {str(e)}")
            return 0
    
    async def _get_learning_model_accuracy(self) -> float:
        """Get learning model accuracy"""
        try:
            if not hasattr(self.learning_engine, 'get_model_accuracy'):
                return 0.5
            
            return await self.learning_engine.get_model_accuracy()
            
        except Exception as e:
            self.logger.error(f"Error getting learning model accuracy: {str(e)}")
            return 0.5
    
    async def _get_optimization_improvements(self) -> Dict[str, float]:
        """Get optimization improvements from learning"""
        try:
            if not hasattr(self.learning_engine, 'get_optimization_improvements'):
                return {}
            
            return await self.learning_engine.get_optimization_improvements()
            
        except Exception as e:
            self.logger.error(f"Error getting optimization improvements: {str(e)}")
            return {}
    
    async def _add_live_report(self, report_type: str, data: Dict[str, Any]) -> None:
        """Add entry to live reports"""
        try:
            report_entry = {
                'type': report_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            self.live_reports.append(report_entry)
            
            # Keep only last 1000 reports to prevent memory issues
            if len(self.live_reports) > 1000:
                self.live_reports = self.live_reports[-1000:]
            
            # Store critical reports in database
            if report_type in ['alert', 'resource_alert', 'system_status']:
                await self.db_manager.store_live_report(report_entry)
                
        except Exception as e:
            self.logger.error(f"Error adding live report: {str(e)}")
    
    async def _add_audit_entry(self, action: str, details: Dict[str, Any]) -> None:
        """Add entry to audit trail"""
        try:
            audit_entry = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'action': action,
                'details': details,
                'system_state': {
                    'active_tasks': len(self.active_tasks),
                    'active_agents': len([
                        m for m in self.agent_registry.values() 
                        if m.current_load > 0
                    ]),
                    'system_load': self.optimization_metrics.get('system_load', 0)
                }
            }
            
            # Store in database
            await self.db_manager.store_audit_entry(audit_entry)
            
        except Exception as e:
            self.logger.error(f"Error adding audit entry: {str(e)}")
    
    async def handle_task_completed(self, message: Dict[str, Any]) -> None:
        """Handle task completion from agent"""
        try:
            task_id = message.get('task_id')
            agent_id = message.get('agent_id')
            result = message.get('result')
            execution_time = message.get('execution_time', 0)
            quality_score = message.get('quality_score', 0.5)
            
            if task_id not in self.active_tasks:
                self.logger.warning(f"Received completion for unknown task: {task_id}")
                return
            
            task = self.active_tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.execution_time = execution_time
            task.updated_at = datetime.utcnow()
            
            # Move to completed tasks
            del self.active_tasks[task_id]
            self.completed_tasks[task_id] = task
            
            # Update agent metrics
            if agent_id in self.agent_registry:
                metrics = self.agent_registry[agent_id]
                metrics.current_load = max(0, metrics.current_load - 1)
                metrics.completed_tasks += 1
                metrics.total_execution_time += execution_time
                metrics.average_completion_time = (
                    metrics.total_execution_time / max(1, metrics.completed_tasks)
                )
                metrics.quality_scores.append(quality_score)
                metrics.last_active = datetime.utcnow()
                
                # Keep only recent quality scores
                if len(metrics.quality_scores) > 50:
                    metrics.quality_scores = metrics.quality_scores[-50:]
            
            # Update database
            await self.db_manager.update_task_completion(
                task_id, result, execution_time, quality_score
            )
            
            # Add to audit trail
            await self._add_audit_entry("task_completed", {
                "task_id": task_id,
                "agent_id": agent_id,
                "execution_time": execution_time,
                "quality_score": quality_score
            })
            
            # Notify stakeholders
            await self.message_bus.publish("task_completed", {
                "task_id": task_id,
                "task_name": task.name,
                "result": result,
                "execution_time": execution_time,
                "quality_score": quality_score,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Live reporting
            await self._add_live_report("task_completed", {
                "task_id": task_id,
                "task_name": task.name,
                "agent_id": agent_id,
                "execution_time": execution_time,
                "quality_score": quality_score,
                "completion_timestamp": datetime.utcnow().isoformat()
            })
            
            self.logger.info(f"Task {task_id} completed by agent {agent_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling task completion: {str(e)}")
    
    async def handle_task_failed(self, message: Dict[str, Any]) -> None:
        """Handle task failure from agent"""
        try:
            task_id = message.get('task_id')
            agent_id = message.get('agent_id')
            error = message.get('error')
            error_type = message.get('error_type', 'unknown')
            retry_count = message.get('retry_count', 0)
            
            if task_id not in self.active_tasks:
                self.logger.warning(f"Received failure for unknown task: {task_id}")
                return
            
            task = self.active_tasks[task_id]
            
            # Check if we should retry
            max_retries = task.context.get('max_retries', self.config.default_max_retries)
            if retry_count < max_retries:
                # Retry the task
                task.retry_count = retry_count + 1
                task.status = TaskStatus.QUEUED
                task.assigned_agent = None
                task.updated_at = datetime.utcnow()
                
                # Put back in queue with higher priority for retry
                priority_queue = self.task_queue.get(task.priority, deque())
                priority_queue.appendleft(task)  # Add to front for faster retry
                
                # Move from active back to queued
                del self.active_tasks[task_id]
                
                self.logger.info(f"Task {task_id} queued for retry ({retry_count + 1}/{max_retries})")
            else:
                # Task has failed permanently
                task.status = TaskStatus.FAILED
                task.error = error
                task.updated_at = datetime.utcnow()
                
                # Move to failed tasks
                del self.active_tasks[task_id]
                self.failed_tasks[task_id] = task
                
                self.logger.error(f"Task {task_id} failed permanently: {error}")
            
            # Update agent metrics
            if agent_id in self.agent_registry:
                metrics = self.agent_registry[agent_id]
                metrics.current_load = max(0, metrics.current_load - 1)
                metrics.failed_tasks += 1
                metrics.last_active = datetime.utcnow()
            
            # Update database
            await self.db_manager.update_task_failure(
                task_id, error, error_type, retry_count
            )
            
            # Add to audit trail
            await self._add_audit_entry("task_failed", {
                "task_id": task_id,
                "agent_id": agent_id,
                "error": error,
                "error_type": error_type,
                "retry_count": retry_count,
                "will_retry": retry_count < max_retries
            })
            
            # Notify stakeholders
            await self.message_bus.publish("task_failed", {
                "task_id": task_id,
                "task_name": task.name,
                "error": error,
                "error_type": error_type,
                "retry_count": retry_count,
                "will_retry": retry_count < max_retries,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Live reporting
            await self._add_live_report("task_failed", {
                "task_id": task_id,
                "task_name": task.name,
                "agent_id": agent_id,
                "error": error,
                "error_type": error_type,
                "retry_count": retry_count,
                "failure_timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Error handling task failure: {str(e)}")
    
    async def handle_agent_heartbeat(self, message: Dict[str, Any]) -> None:
        """Handle agent heartbeat"""
        try:
            agent_id = message.get('agent_id')
            status = message.get('status', 'active')
            current_load = message.get('current_load', 0)
            capabilities = message.get('capabilities', [])
            performance_data = message.get('performance_data', {})
            
            if agent_id not in self.agent_registry:
                # New agent registration
                self.agent_registry[agent_id] = AgentPerformanceMetrics(
                    agent_id=agent_id,
                    capabilities=capabilities,
                    current_load=current_load,
                    last_active=datetime.utcnow()
                )
                
                await self._add_audit_entry("agent_registered", {
                    "agent_id": agent_id,
                    "capabilities": [cap.value if hasattr(cap, 'value') else str(cap) for cap in capabilities]
                })
                
                self.logger.info(f"New agent registered: {agent_id}")
            else:
                # Update existing agent
                metrics = self.agent_registry[agent_id]
                metrics.current_load = current_load
                metrics.capabilities = capabilities
                metrics.last_active = datetime.utcnow()
                
                # Update performance data if provided
                if performance_data:
                    metrics.total_execution_time = performance_data.get(
                        'total_execution_time', metrics.total_execution_time
                    )
                    if 'quality_scores' in performance_data:
                        metrics.quality_scores.extend(performance_data['quality_scores'])
                        # Keep only recent scores
                        if len(metrics.quality_scores) > 50:
                            metrics.quality_scores = metrics.quality_scores[-50:]
            
            # Update database
            await self.db_manager.update_agent_heartbeat(agent_id, message)
            
        except Exception as e:
            self.logger.error(f"Error handling agent heartbeat: {str(e)}")
    
    async def handle_resource_request(self, message: Dict[str, Any]) -> None:
        """Handle resource request from agent"""
        try:
            agent_id = message.get('agent_id')
            resource_type = message.get('resource_type')
            requirements = message.get('requirements', {})
            
            response = {
                'agent_id': agent_id,
                'resource_type': resource_type,
                'granted': False,
                'resources': {},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if resource_type == 'api_keys':
                # Provide API keys based on requirements
                requested_services = requirements.get('services', [])
                api_keys = {}
                
                for service in requested_services:
                    key = await self.key_manager.get_available_key(service, agent_id)
                    if key:
                        api_keys[service] = key
                
                if api_keys:
                    response['granted'] = True
                    response['resources'] = {'api_keys': api_keys}
                    
            elif resource_type == 'browser_access':
                # Grant browser access if within limits
                if self._can_grant_browser_access(agent_id):
                    browser_config = await self._get_browser_config(agent_id, requirements)
                    response # Completing the manager agent from where it ended

                    if self._can_grant_browser_access(agent_id):
                        browser_config = await self._get_browser_config(agent_id, requirements)
                        if browser_config:
                            response['granted'] = True
                            response['resources'] = {'browser_config': browser_config}
                            await self._track_browser_allocation(agent_id, browser_config)
                    
            elif resource_type == 'compute':
                # Grant compute resources if available
                compute_resources = await self._allocate_compute_resources(agent_id, requirements)
                if compute_resources:
                    response['granted'] = True
                    response['resources'] = {'compute': compute_resources}
            
            elif resource_type == 'storage':
                # Grant storage resources
                storage_config = await self._allocate_storage(agent_id, requirements)
                if storage_config:
                    response['granted'] = True
                    response['resources'] = {'storage': storage_config}
            
            # Send response back to agent
            await self.message_bus.publish(f"resource_response_{agent_id}", response)
            
            # Log resource allocation
            await self._add_audit_entry("resource_allocated", {
                "agent_id": agent_id,
                "resource_type": resource_type,
                "granted": response['granted'],
                "requirements": requirements
            })
            
        except Exception as e:
            self.logger.error(f"Error handling resource request: {str(e)}")
    
    def _can_grant_browser_access(self, agent_id: str) -> bool:
        """Check if browser access can be granted to agent"""
        try:
            # Check current browser sessions
            active_sessions = len(self.active_browser_sessions)
            max_sessions = self.config.max_browser_sessions
            
            # Check agent's browser usage history
            agent_sessions = sum(1 for session in self.active_browser_sessions.values() 
                               if session.get('agent_id') == agent_id)
            max_per_agent = self.config.max_browser_sessions_per_agent
            
            return active_sessions < max_sessions and agent_sessions < max_per_agent
            
        except Exception as e:
            self.logger.error(f"Error checking browser access: {str(e)}")
            return False
    
    async def _get_browser_config(self, agent_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Get browser configuration for agent"""
        try:
            # Generate unique session ID
            session_id = f"browser_{agent_id}_{uuid.uuid4().hex[:8]}"
            
            # Configure browser based on requirements
            config = {
                'session_id': session_id,
                'user_agent': requirements.get('user_agent', 'AI-Agent/1.0'),
                'viewport': requirements.get('viewport', {'width': 1920, 'height': 1080}),
                'headless': requirements.get('headless', True),
                'timeout': requirements.get('timeout', 30000),
                'proxy': await self._get_proxy_config() if requirements.get('use_proxy') else None,
                'permissions': self._get_browser_permissions(agent_id),
                'resource_limits': {
                    'max_pages': requirements.get('max_pages', 5),
                    'max_requests': requirements.get('max_requests', 100),
                    'session_duration': requirements.get('session_duration', 3600)  # 1 hour
                }
            }
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error getting browser config: {str(e)}")
            return {}
    
    def _get_browser_permissions(self, agent_id: str) -> List[str]:
        """Get browser permissions for agent"""
        # Base permissions for all agents
        base_permissions = [
            'read_dom',
            'click_elements',
            'fill_forms',
            'navigate',
            'take_screenshots'
        ]
        
        # Additional permissions based on agent capabilities
        agent_metrics = self.agent_registry.get(agent_id)
        if agent_metrics and TaskCapability.BROWSER_AUTOMATION in agent_metrics.capabilities:
            base_permissions.extend([
                'download_files',
                'upload_files',
                'execute_javascript',
                'access_local_storage',
                'manage_cookies'
            ])
        
        return base_permissions
    
    async def _track_browser_allocation(self, agent_id: str, config: Dict[str, Any]) -> None:
        """Track browser resource allocation"""
        try:
            session_id = config['session_id']
            
            self.active_browser_sessions[session_id] = {
                'agent_id': agent_id,
                'config': config,
                'start_time': datetime.utcnow(),
                'requests_count': 0,
                'pages_count': 0,
                'status': 'active'
            }
            
            # Store in database
            await self.db_manager.track_browser_session(agent_id, session_id, config)
            
        except Exception as e:
            self.logger.error(f"Error tracking browser allocation: {str(e)}")
    
    async def _allocate_compute_resources(self, agent_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate compute resources to agent"""
        try:
            # Check available resources
            system_resources = await self._get_system_resources()
            requested_cpu = requirements.get('cpu_cores', 1)
            requested_memory = requirements.get('memory_gb', 1)
            
            if (system_resources['available_cpu'] >= requested_cpu and 
                system_resources['available_memory'] >= requested_memory):
                
                allocation_id = f"compute_{agent_id}_{uuid.uuid4().hex[:8]}"
                
                allocation = {
                    'allocation_id': allocation_id,
                    'cpu_cores': requested_cpu,
                    'memory_gb': requested_memory,
                    'gpu_access': requirements.get('gpu_access', False) and system_resources['gpu_available'],
                    'priority': requirements.get('priority', 'normal'),
                    'duration_limit': requirements.get('duration_limit', 3600),  # 1 hour
                    'start_time': datetime.utcnow().isoformat()
                }
                
                # Track allocation
                self.compute_allocations[allocation_id] = {
                    'agent_id': agent_id,
                    'allocation': allocation,
                    'start_time': datetime.utcnow(),
                    'status': 'active'
                }
                
                return allocation
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error allocating compute resources: {str(e)}")
            return {}
    
    async def _allocate_storage(self, agent_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate storage resources to agent"""
        try:
            storage_type = requirements.get('type', 'temp')
            size_mb = requirements.get('size_mb', 100)
            
            # Check available storage
            available_storage = await self._get_available_storage()
            
            if available_storage >= size_mb:
                storage_id = f"storage_{agent_id}_{uuid.uuid4().hex[:8]}"
                storage_path = f"/tmp/agent_storage/{storage_id}"
                
                # Create storage directory
                os.makedirs(storage_path, exist_ok=True)
                
                storage_config = {
                    'storage_id': storage_id,
                    'path': storage_path,
                    'size_mb': size_mb,
                    'type': storage_type,
                    'permissions': ['read', 'write', 'delete'],
                    'retention_hours': requirements.get('retention_hours', 24),
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Track allocation
                self.storage_allocations[storage_id] = {
                    'agent_id': agent_id,
                    'config': storage_config,
                    'start_time': datetime.utcnow(),
                    'status': 'active'
                }
                
                return storage_config
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error allocating storage: {str(e)}")
            return {}
    
    async def _get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource availability"""
        try:
            import psutil
            
            # CPU information
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            available_cpu = max(0, cpu_count - (cpu_count * cpu_percent / 100))
            
            # Memory information
            memory = psutil.virtual_memory()
            available_memory = memory.available / (1024**3)  # GB
            
            # GPU information (simplified)
            gpu_available = False
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                gpu_available = len(gpus) > 0 and any(gpu.memoryFree > 1000 for gpu in gpus)
            except ImportError:
                gpu_available = False
            
            return {
                'available_cpu': available_cpu,
                'available_memory': available_memory,
                'gpu_available': gpu_available,
                'total_cpu': cpu_count,
                'total_memory': memory.total / (1024**3)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system resources: {str(e)}")
            return {
                'available_cpu': 1,
                'available_memory': 1,
                'gpu_available': False,
                'total_cpu': 1,
                'total_memory': 1
            }
    
    async def _get_available_storage(self) -> float:
        """Get available storage in MB"""
        try:
            import shutil
            
            # Check available disk space
            total, used, free = shutil.disk_usage("/tmp")
            return free / (1024**2)  # MB
            
        except Exception as e:
            self.logger.error(f"Error getting available storage: {str(e)}")
            return 1000.0  # Default 1GB
    
    async def _get_proxy_config(self) -> Dict[str, str]:
        """Get proxy configuration if available"""
        try:
            # Return proxy configuration from environment or config
            proxy_config = {
                'http': os.environ.get('HTTP_PROXY'),
                'https': os.environ.get('HTTPS_PROXY'),
                'no_proxy': os.environ.get('NO_PROXY')
            }
            
            # Filter out None values
            return {k: v for k, v in proxy_config.items() if v}
            
        except Exception as e:
            self.logger.error(f"Error getting proxy config: {str(e)}")
            return {}
    
    async def cleanup_expired_resources(self) -> None:
        """Clean up expired resource allocations"""
        try:
            current_time = datetime.utcnow()
            
            # Clean up expired browser sessions
            expired_browser_sessions = []
            for session_id, session_data in self.active_browser_sessions.items():
                start_time = session_data['start_time']
                duration = session_data['config']['resource_limits']['session_duration']
                
                if (current_time - start_time).total_seconds() > duration:
                    expired_browser_sessions.append(session_id)
            
            for session_id in expired_browser_sessions:
                await self._cleanup_browser_session(session_id)
                del self.active_browser_sessions[session_id]
            
            # Clean up expired compute allocations
            expired_compute = []
            for allocation_id, allocation_data in self.compute_allocations.items():
                start_time = allocation_data['start_time']
                duration = allocation_data['allocation']['duration_limit']
                
                if (current_time - start_time).total_seconds() > duration:
                    expired_compute.append(allocation_id)
            
            for allocation_id in expired_compute:
                await self._cleanup_compute_allocation(allocation_id)
                del self.compute_allocations[allocation_id]
            
            # Clean up expired storage allocations
            expired_storage = []
            for storage_id, storage_data in self.storage_allocations.items():
                start_time = storage_data['start_time']
                retention_hours = storage_data['config']['retention_hours']
                
                if (current_time - start_time).total_seconds() > retention_hours * 3600:
                    expired_storage.append(storage_id)
            
            for storage_id in expired_storage:
                await self._cleanup_storage_allocation(storage_id)
                del self.storage_allocations[storage_id]
            
            if expired_browser_sessions or expired_compute or expired_storage:
                self.logger.info(
                    f"Cleaned up {len(expired_browser_sessions)} browser sessions, "
                    f"{len(expired_compute)} compute allocations, "
                    f"{len(expired_storage)} storage allocations"
                )
                
        except Exception as e:
            self.logger.error(f"Error cleaning up expired resources: {str(e)}")
    
    async def _cleanup_browser_session(self, session_id: str) -> None:
        """Clean up a browser session"""
        try:
            # Close any active browser instances for this session
            await self.message_bus.publish("cleanup_browser_session", {
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Update database
            await self.db_manager.cleanup_browser_session(session_id)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up browser session {session_id}: {str(e)}")
    
    async def _cleanup_compute_allocation(self, allocation_id: str) -> None:
        """Clean up a compute allocation"""
        try:
            # Release compute resources
            allocation_data = self.compute_allocations.get(allocation_id)
            if allocation_data:
                agent_id = allocation_data['agent_id']
                await self.message_bus.publish("cleanup_compute_allocation", {
                    'allocation_id': allocation_id,
                    'agent_id': agent_id,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Update database
            await self.db_manager.cleanup_compute_allocation(allocation_id)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up compute allocation {allocation_id}: {str(e)}")
    
    async def _cleanup_storage_allocation(self, storage_id: str) -> None:
        """Clean up a storage allocation"""
        try:
            storage_data = self.storage_allocations.get(storage_id)
            if storage_data:
                storage_path = storage_data['config']['path']
                
                # Remove storage directory
                import shutil
                if os.path.exists(storage_path):
                    shutil.rmtree(storage_path)
                
                # Update database
                await self.db_manager.cleanup_storage_allocation(storage_id)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up storage allocation {storage_id}: {str(e)}")
    
    async def get_live_chat_report(self, report_type: str = "summary", 
                                 timeframe: str = "1h") -> Dict[str, Any]:
        """Generate live chat report for real-time monitoring"""
        try:
            current_time = datetime.utcnow()
            
            # Parse timeframe
            timeframe_seconds = self._parse_timeframe(timeframe)
            start_time = current_time - timedelta(seconds=timeframe_seconds)
            
            # Get recent activities
            recent_reports = [
                report for report in self.live_reports
                if datetime.fromisoformat(report['timestamp'].replace('Z', '+00:00')) >= start_time
            ]
            
            if report_type == "summary":
                return await self._generate_summary_chat_report(recent_reports, timeframe)
            elif report_type == "detailed":
                return await self._generate_detailed_chat_report(recent_reports, timeframe)
            elif report_type == "performance":
                return await self._generate_performance_chat_report(recent_reports, timeframe)
            elif report_type == "alerts":
                return await self._generate_alerts_chat_report(recent_reports, timeframe)
            else:
                return await self._generate_summary_chat_report(recent_reports, timeframe)
                
        except Exception as e:
            self.logger.error(f"Error generating live chat report: {str(e)}")
            return {
                'error': 'Failed to generate report',
                'timestamp': current_time.isoformat(),
                'timeframe': timeframe
            }
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to seconds"""
        timeframe = timeframe.lower()
        if timeframe.endswith('m'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 3600
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 86400
        else:
            return 3600  # Default to 1 hour
    
    async def _generate_summary_chat_report(self, recent_reports: List[Dict], 
                                          timeframe: str) -> Dict[str, Any]:
        """Generate summary chat report"""
        try:
            # Count activities by type
            activity_counts = {}
            for report in recent_reports:
                activity_type = report.get('type', 'unknown')
                activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
            
            # Get key metrics
            total_activities = len(recent_reports)
            completed_tasks = activity_counts.get('task_completed', 0)
            failed_tasks = activity_counts.get('task_failed', 0)
            agent_activities = activity_counts.get('agent_heartbeat', 0)
            
            # Calculate success rate
            total_task_outcomes = completed_tasks + failed_tasks
            success_rate = (completed_tasks / max(1, total_task_outcomes)) * 100
            
            # Generate natural language summary
            summary_text = f"""
🤖 **AI Development Environment Status Report** ({timeframe})

**System Overview:**
• Total Activities: {total_activities}
• Active Agents: {len(self.agent_registry)}
• Success Rate: {success_rate:.1f}%

**Task Performance:**
• Completed: {completed_tasks}
• Failed: {failed_tasks}
• Queue Length: {sum(len(queue) for queue in self.task_queue.values())}

**Agent Health:**
• Registered: {len(self.agent_registry)}
• Currently Active: {len([m for m in self.agent_registry.values() if m.current_load > 0])}
• Heartbeats: {agent_activities}

**System Status:** {self._determine_overall_health().title()}
"""
            
            return {
                'type': 'summary',
                'timeframe': timeframe,
                'timestamp': datetime.utcnow().isoformat(),
                'summary_text': summary_text,
                'metrics': {
                    'total_activities': total_activities,
                    'completed_tasks': completed_tasks,
                    'failed_tasks': failed_tasks,
                    'success_rate': success_rate,
                    'active_agents': len([m for m in self.agent_registry.values() if m.current_load > 0]),
                    'queue_length': sum(len(queue) for queue in self.task_queue.values())
                },
                'activity_breakdown': activity_counts
            }
            
        except Exception as e:
            self.logger.error(f"Error generating summary chat report: {str(e)}")
            return {'error': 'Failed to generate summary report'}
    
    async def _generate_detailed_chat_report(self, recent_reports: List[Dict], 
                                           timeframe: str) -> Dict[str, Any]:
        """Generate detailed chat report"""
        try:
            # Organize reports by type and agent
            reports_by_agent = {}
            critical_events = []
            
            for report in recent_reports:
                report_type = report.get('type', 'unknown')
                data = report.get('data', {})
                agent_id = data.get('agent_id', 'system')
                
                if agent_id not in reports_by_agent:
                    reports_by_agent[agent_id] = []
                reports_by_agent[agent_id].append(report)
                
                # Identify critical events
                if report_type in ['task_failed', 'alert', 'resource_alert']:
                    critical_events.append(report)
            
            # Generate detailed text
            detailed_text = f"""
🔍 **Detailed System Activity Report** ({timeframe})

**Agent Activity Breakdown:**
"""
            
            for agent_id, agent_reports in reports_by_agent.items():
                if agent_id == 'system':
                    continue
                    
                activity_types = {}
                for report in agent_reports:
                    report_type = report.get('type', 'unknown')
                    activity_types[report_type] = activity_types.get(report_type, 0) + 1
                
                detailed_text += f"""
• **{agent_id}:** {len(agent_reports)} activities
  - {', '.join(f"{k}: {v}" for k, v in activity_types.items())}
"""
            
            # Add critical events
            if critical_events:
                detailed_text += f"""
**⚠️ Critical Events ({len(critical_events)}):**
"""
                for event in critical_events[-5:]:  # Show last 5
                    event_time = event.get('timestamp', '')
                    event_type = event.get('type', '')
                    event_data = event.get('data', {})
                    
                    detailed_text += f"""
• {event_time[:19]}: {event_type.replace('_', ' ').title()}
  {event_data.get('task_name', '')} {event_data.get('error', '')[:50]}...
"""
            
            return {
                'type': 'detailed',
                'timeframe': timeframe,
                'timestamp': datetime.utcnow().isoformat(),
                'detailed_text': detailed_text,
                'reports_by_agent': reports_by_agent,
                'critical_events': critical_events,
                'total_reports': len(recent_reports)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating detailed chat report: {str(e)}")
            return {'error': 'Failed to generate detailed report'}
    
    async def _generate_performance_chat_report(self, recent_reports: List[Dict], 
                                              timeframe: str) -> Dict[str, Any]:
        """Generate performance-focused chat report"""
        try:
            # Extract performance metrics
            completion_times = []
            quality_scores = []
            agent_performance = {}
            
            for report in recent_reports:
                if report.get('type') == 'task_completed':
                    data = report.get('data', {})
                    
                    if 'execution_time' in data:
                        completion_times.append(data['execution_time'])
                    
                    if 'quality_score' in data:
                        quality_scores.append(data['quality_score'])
                    
                    agent_id = data.get('agent_id', 'unknown')
                    if agent_id not in agent_performance:
                        agent_performance[agent_id] = {
                            'completed': 0,
                            'total_time': 0,
                            'quality_scores': []
                        }
                    
                    agent_performance[agent_id]['completed'] += 1
                    agent_performance[agent_id]['total_time'] += data.get('execution_time', 0)
                    agent_performance[agent_id]['quality_scores'].append(
                        data.get('quality_score', 0.5)
                    )
            
            # Calculate averages
            avg_completion_time = sum(completion_times) / max(1, len(completion_times))
            avg_quality = sum(quality_scores) / max(1, len(quality_scores))
            
            # Find top performers
            top_performers = []
            for agent_id, perf in agent_performance.items():
                if perf['completed'] > 0:
                    avg_time = perf['total_time'] / perf['completed']
                    avg_quality = sum(perf['quality_scores']) / len(perf['quality_scores'])
                    
                    top_performers.append({
                        'agent_id': agent_id,
                        'completed': perf['completed'],
                        'avg_time': avg_time,
                        'avg_quality': avg_quality,
                        'efficiency': avg_quality / max(0.1, avg_time)  # Quality per second
                    })
            
            top_performers.sort(key=lambda x: x['efficiency'], reverse=True)
            
            # Generate performance text
            performance_text = f"""
📊 **Performance Analytics Report** ({timeframe})

**Overall Metrics:**
• Average Completion Time: {avg_completion_time:.2f} seconds
• Average Quality Score: {avg_quality:.2f}/1.0
• Total Completed Tasks: {len(completion_times)}

**Top Performing Agents:**
"""
            
            for i, performer in enumerate(top_performers[:3], 1):
                performance_text += f"""
{i}. **{performer['agent_id']}**
   - Tasks: {performer['completed']}
   - Avg Time: {performer['avg_time']:.1f}s
   - Quality: {performer['avg_quality']:.2f}
   - Efficiency: {performer['efficiency']:.3f}
"""
            
            # System optimization score
            optimization_score = await self._calculate_optimization_score()
            performance_text += f"""
**System Optimization Score:** {optimization_score:.1%}
"""
            
            return {
                'type': 'performance',
                'timeframe': timeframe,
                'timestamp': datetime.utcnow().isoformat(),
                'performance_text': performance_text,
                'metrics': {
                    'avg_completion_time': avg_completion_time,
                    'avg_quality': avg_quality,
                    'optimization_score': optimization_score,
                    'total_completed': len(completion_times)
                },
                'top_performers': top_performers[:5],
                'agent_performance': agent_performance
            }
            
        except Exception as e:
            self.logger.error(f"Error generating performance chat report: {str(e)}")
            return {'error': 'Failed to generate performance report'}
    
    async def _generate_alerts_chat_report(self, recent_reports: List[Dict], 
                                         timeframe: str) -> Dict[str, Any]:
        """Generate alerts-focused chat report"""
        try:
            # Filter for alert-type reports
            alerts = [
                report for report in recent_reports
                if report.get('type') in ['alert', 'resource_alert', 'task_failed']
            ]
            
            # Categorize alerts
            alert_categories = {
                'critical': [],
                'warning': [],
                'info': []
            }
            
            for alert in alerts:
                alert_data = alert.get('data', {})
                alert_type = alert.get('type', '')
                
                # Determine severity
                if alert_type == 'task_failed' and alert_data.get('retry_count', 0) >= 3:
                    alert_categories['critical'].append(alert)
                elif alert_type == 'resource_alert':
                    alert_categories['warning'].append(alert)
                elif alert_type == 'alert':
                    severity = alert_data.get('severity', 'info')
                    alert_categories[severity].append(alert)
                else:
                    alert_categories['info'].append(alert)
            
            # Generate alerts text
            alerts_text = f"""
🚨 **System Alerts Report** ({timeframe})

**Alert Summary:**
• Critical: {len(alert_categories['critical'])}
• Warning: {len(alert_categories['warning'])}
• Info: {len(alert_categories['info'])}

"""
            
            # Show recent critical alerts
            if alert_categories['critical']:
                alerts_text += "**🔴 Critical Alerts:**\n"
                for alert in alert_categories['critical'][-3:]:
                    timestamp = alert.get('timestamp', '')[:19]
                    data = alert.get('data', {})
                    alerts_text += f"• {timestamp}: {data.get('error', 'Critical system event')}\n"
            
            # Show recent warnings
            if alert_categories['warning']:
                alerts_text += "\n**🟡 Warning Alerts:**\n"
                for alert in alert_categories['warning'][-3:]:
                    timestamp = alert.get('timestamp', '')[:19]
                    data = alert.get('data', {})
                    alerts_text += f"• {timestamp}: {data.get('message', 'System warning')}\n"
            
            if not alerts:
                alerts_text += "✅ **No alerts in this timeframe - system running smoothly!**"
            
            return {
                'type': 'alerts',
                'timeframe': timeframe,
                'timestamp': datetime.utcnow().isoformat(),
                'alerts_text': alerts_text,
                'alert_counts': {k: len(v) for k, v in alert_categories.items()},
                'recent_alerts': alerts[-10:],  # Last 10 alerts
                'total_alerts': len(alerts)
            }
            
        except Exception as e:
            self.logger.error(f"Error generating alerts chat report: {str(e)}")
            return {'error': 'Failed to generate alerts report'}
    
    async def start_continuous_monitoring(self) -> None:
        """Start continuous system monitoring"""
        try:
            self.logger.info("Starting continuous monitoring...")
            
            # Start monitoring tasks
            monitoring_tasks = [
                asyncio.create_task(self._monitor_system_health()),
                asyncio.create_task(self._monitor_agent_performance()),
                asyncio.create_task(self._monitor_resource_usage()),
                asyncio.create_task(self._cleanup_expired_resources_loop()),
                asyncio.create_task(self._generate_periodic_reports())
            ]
            
            self.monitoring_tasks.extend(monitoring_tasks)
            
            # Wait for monitoring tasks (they run indefinitely)
            await asyncio.gather(*monitoring_tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Error in continuous monitoring: {str(e)}")
    
    async def _monitor_system_health(self) -> None:
        """Continuously monitor system health"""
        while self.running:
            try:
                # Completing the manager agent from where it ended

                # Monitor system health metrics
                system_resources = await self._get_system_resources()
                
                # Check critical thresholds
                if system_resources['available_cpu'] < 0.2:
                    await self._create_system_alert('critical', 'Low CPU availability', system_resources)
                
                if system_resources['available_memory'] < 0.5:
                    await self._create_system_alert('critical', 'Low memory availability', system_resources)
                
                # Check agent health
                unhealthy_agents = []
                for agent_id, metrics in self.agent_registry.items():
                    if metrics.last_heartbeat < datetime.utcnow() - timedelta(minutes=5):
                        unhealthy_agents.append(agent_id)
                
                if unhealthy_agents:
                    await self._create_system_alert('warning', f'Unhealthy agents detected', {
                        'agents': unhealthy_agents
                    })
                
                # Check task queue health
                overloaded_queues = []
                for queue_name, tasks in self.task_queue.items():
                    if len(tasks) > self.config.max_queue_size:
                        overloaded_queues.append(queue_name)
                
                if overloaded_queues:
                    await self._create_system_alert('warning', 'Task queues overloaded', {
                        'queues': overloaded_queues
                    })
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in system health monitoring: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _monitor_agent_performance(self) -> None:
        """Monitor individual agent performance"""
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                for agent_id, metrics in self.agent_registry.items():
                    # Calculate performance metrics
                    if metrics.tasks_completed > 0:
                        avg_execution_time = metrics.total_execution_time / metrics.tasks_completed
                        success_rate = metrics.tasks_completed / (metrics.tasks_completed + metrics.tasks_failed)
                        
                        # Check for performance issues
                        if avg_execution_time > self.config.performance_thresholds['max_avg_execution_time']:
                            await self._create_agent_alert(agent_id, 'warning', 'Slow performance detected', {
                                'avg_execution_time': avg_execution_time,
                                'threshold': self.config.performance_thresholds['max_avg_execution_time']
                            })
                        
                        if success_rate < self.config.performance_thresholds['min_success_rate']:
                            await self._create_agent_alert(agent_id, 'critical', 'Low success rate', {
                                'success_rate': success_rate,
                                'threshold': self.config.performance_thresholds['min_success_rate']
                            })
                    
                    # Check for agent overload
                    if metrics.current_load > self.config.performance_thresholds['max_load']:
                        await self._create_agent_alert(agent_id, 'warning', 'Agent overloaded', {
                            'current_load': metrics.current_load,
                            'max_load': self.config.performance_thresholds['max_load']
                        })
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in agent performance monitoring: {str(e)}")
                await asyncio.sleep(120)  # Wait longer on error
    
    async def _monitor_resource_usage(self) -> None:
        """Monitor resource usage across the system"""
        while self.running:
            try:
                # Monitor browser sessions
                active_sessions = len(self.active_browser_sessions)
                max_sessions = self.config.max_browser_sessions
                
                if active_sessions > max_sessions * 0.8:
                    await self._create_system_alert('warning', 'High browser session usage', {
                        'active_sessions': active_sessions,
                        'max_sessions': max_sessions,
                        'utilization': active_sessions / max_sessions
                    })
                
                # Monitor compute allocations
                active_compute = len(self.compute_allocations)
                if active_compute > self.config.max_compute_allocations * 0.8:
                    await self._create_system_alert('warning', 'High compute allocation usage', {
                        'active_allocations': active_compute,
                        'utilization': active_compute / self.config.max_compute_allocations
                    })
                
                # Monitor storage usage
                total_storage_allocated = sum(
                    alloc_data['config']['size_mb'] 
                    for alloc_data in self.storage_allocations.values()
                )
                
                available_storage = await self._get_available_storage()
                if total_storage_allocated > available_storage * 0.8:
                    await self._create_system_alert('warning', 'High storage usage', {
                        'allocated_mb': total_storage_allocated,
                        'available_mb': available_storage
                    })
                
                await asyncio.sleep(120)  # Check every 2 minutes
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {str(e)}")
                await asyncio.sleep(180)
    
    async def _cleanup_expired_resources_loop(self) -> None:
        """Continuous cleanup of expired resources"""
        while self.running:
            try:
                await self.cleanup_expired_resources()
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
            except Exception as e:
                self.logger.error(f"Error in resource cleanup loop: {str(e)}")
                await asyncio.sleep(600)  # Wait longer on error
    
    async def _generate_periodic_reports(self) -> None:
        """Generate periodic system reports"""
        while self.running:
            try:
                # Generate hourly summary reports
                summary_report = await self.get_live_chat_report("summary", "1h")
                await self._store_periodic_report("hourly_summary", summary_report)
                
                # Generate daily detailed reports
                current_hour = datetime.utcnow().hour
                if current_hour == 0:  # Generate at midnight
                    daily_report = await self.get_live_chat_report("detailed", "24h")
                    await self._store_periodic_report("daily_detailed", daily_report)
                
                await asyncio.sleep(3600)  # Generate every hour
                
            except Exception as e:
                self.logger.error(f"Error in periodic report generation: {str(e)}")
                await asyncio.sleep(3600)
    
    async def _create_system_alert(self, severity: str, message: str, data: Dict[str, Any]) -> None:
        """Create system-wide alert"""
        try:
            alert = {
                'type': 'alert',
                'severity': severity,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data,
                'source': 'system'
            }
            
            # Add to live reports
            self.live_reports.append(alert)
            
            # Publish alert
            await self.message_bus.publish("system_alert", alert)
            
            # Store in database
            await self.db_manager.store_alert(alert)
            
            # Log alert
            log_level = logging.CRITICAL if severity == 'critical' else logging.WARNING
            self.logger.log(log_level, f"System Alert ({severity}): {message}")
            
        except Exception as e:
            self.logger.error(f"Error creating system alert: {str(e)}")
    
    async def _create_agent_alert(self, agent_id: str, severity: str, message: str, data: Dict[str, Any]) -> None:
        """Create agent-specific alert"""
        try:
            alert = {
                'type': 'agent_alert',
                'severity': severity,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'data': {**data, 'agent_id': agent_id},
                'source': 'agent'
            }
            
            # Add to live reports
            self.live_reports.append(alert)
            
            # Publish alert
            await self.message_bus.publish(f"agent_alert_{agent_id}", alert)
            
            # Store in database
            await self.db_manager.store_alert(alert)
            
            # Log alert
            log_level = logging.CRITICAL if severity == 'critical' else logging.WARNING
            self.logger.log(log_level, f"Agent Alert ({agent_id}, {severity}): {message}")
            
        except Exception as e:
            self.logger.error(f"Error creating agent alert: {str(e)}")
    
    async def _store_periodic_report(self, report_type: str, report_data: Dict[str, Any]) -> None:
        """Store periodic reports"""
        try:
            # Store in database
            await self.db_manager.store_periodic_report(report_type, report_data)
            
            # Keep limited history in memory
            if not hasattr(self, 'periodic_reports'):
                self.periodic_reports = {}
            
            if report_type not in self.periodic_reports:
                self.periodic_reports[report_type] = []
            
            self.periodic_reports[report_type].append(report_data)
            
            # Keep only last 24 reports for each type
            if len(self.periodic_reports[report_type]) > 24:
                self.periodic_reports[report_type] = self.periodic_reports[report_type][-24:]
            
        except Exception as e:
            self.logger.error(f"Error storing periodic report: {str(e)}")
    
    def _determine_overall_health(self) -> str:
        """Determine overall system health"""
        try:
            # Check recent alerts
            recent_critical = sum(1 for report in self.live_reports[-100:] 
                                if report.get('severity') == 'critical')
            recent_warnings = sum(1 for report in self.live_reports[-100:] 
                                if report.get('severity') == 'warning')
            
            # Check agent health
            total_agents = len(self.agent_registry)
            healthy_agents = sum(1 for metrics in self.agent_registry.values()
                               if metrics.last_heartbeat > datetime.utcnow() - timedelta(minutes=5))
            
            agent_health_ratio = healthy_agents / max(1, total_agents)
            
            # Determine status
            if recent_critical > 5 or agent_health_ratio < 0.5:
                return "critical"
            elif recent_critical > 0 or recent_warnings > 10 or agent_health_ratio < 0.8:
                return "warning"
            else:
                return "healthy"
                
        except Exception as e:
            self.logger.error(f"Error determining system health: {str(e)}")
            return "unknown"
    
    async def _calculate_optimization_score(self) -> float:
        """Calculate system optimization score"""
        try:
            scores = []
            
            # Resource utilization efficiency (0.0-1.0)
            system_resources = await self._get_system_resources()
            cpu_efficiency = 1.0 - abs(0.7 - (1.0 - system_resources['available_cpu'] / system_resources['total_cpu']))
            memory_efficiency = 1.0 - abs(0.7 - ((system_resources['total_memory'] - system_resources['available_memory']) / system_resources['total_memory']))
            
            scores.extend([cpu_efficiency, memory_efficiency])
            
            # Agent performance efficiency
            if self.agent_registry:
                agent_scores = []
                for metrics in self.agent_registry.values():
                    if metrics.tasks_completed > 0:
                        success_rate = metrics.tasks_completed / (metrics.tasks_completed + metrics.tasks_failed)
                        load_efficiency = 1.0 - abs(0.7 - (metrics.current_load / metrics.max_concurrent_tasks))
                        agent_scores.extend([success_rate, load_efficiency])
                
                if agent_scores:
                    scores.append(sum(agent_scores) / len(agent_scores))
            
            # Queue efficiency
            total_queued = sum(len(queue) for queue in self.task_queue.values())
            queue_efficiency = max(0.0, 1.0 - (total_queued / (len(self.task_queue) * 10)))
            scores.append(queue_efficiency)
            
            # Overall optimization score
            return sum(scores) / len(scores) if scores else 0.5
            
        except Exception as e:
            self.logger.error(f"Error calculating optimization score: {str(e)}")
            return 0.5
    
    async def get_api_key_for_service(self, service_name: str, agent_id: str) -> Optional[str]:
        """Get API key for service with load balancing and rate limiting"""
        try:
            service_name = service_name.lower()
            
            # Define available keys for each service
            service_keys = {
                'claude': [
                    {'key': 'claude_key_1', 'weight': 1, 'daily_limit': 10000},
                    {'key': 'claude_key_2', 'weight': 1, 'daily_limit': 10000},
                    {'key': 'claude_key_3', 'weight': 1, 'daily_limit': 10000},
                    {'key': 'claude_key_4', 'weight': 1, 'daily_limit': 10000},
                    {'key': 'claude_key_5', 'weight': 1, 'daily_limit': 10000},
                    {'key': 'claude_key_6', 'weight': 1, 'daily_limit': 10000},
                    {'key': 'claude_key_7', 'weight': 1, 'daily_limit': 10000}
                ],
                'openai': [
                    {'key': 'openai_key_1', 'weight': 1, 'daily_limit': 15000},
                    {'key': 'openai_key_2', 'weight': 1, 'daily_limit': 15000},
                    {'key': 'openai_key_3', 'weight': 1, 'daily_limit': 15000},
                    {'key': 'openai_key_4', 'weight': 1, 'daily_limit': 15000},
                    {'key': 'openai_key_5', 'weight': 1, 'daily_limit': 15000},
                    {'key': 'openai_service_1', 'weight': 2, 'daily_limit': 25000},
                    {'key': 'openai_service_2', 'weight': 2, 'daily_limit': 25000},
                    {'key': 'openai_service_3', 'weight': 2, 'daily_limit': 25000}
                ],
                'gemini': [
                    {'key': 'gemini_key_1', 'weight': 1, 'daily_limit': 12000},
                    {'key': 'gemini_key_2', 'weight': 1, 'daily_limit': 12000},
                    {'key': 'gemini_key_3', 'weight': 1, 'daily_limit': 12000},
                    {'key': 'gemini_key_4', 'weight': 1, 'daily_limit': 12000},
                    {'key': 'gemini_key_5', 'weight': 1, 'daily_limit': 12000}
                ],
                'deepseek': [
                    {'key': 'deepseek_key_1', 'weight': 1, 'daily_limit': 8000},
                    {'key': 'deepseek_key_2', 'weight': 1, 'daily_limit': 8000},
                    {'key': 'deepseek_key_3', 'weight': 1, 'daily_limit': 8000},
                    {'key': 'deepseek_key_4', 'weight': 1, 'daily_limit': 8000},
                    {'key': 'deepseek_key_5', 'weight': 1, 'daily_limit': 8000}
                ],
                'groq': [
                    {'key': 'groq_key_1', 'weight': 1, 'daily_limit': 20000},
                    {'key': 'groq_key_2', 'weight': 1, 'daily_limit': 20000},
                    {'key': 'groq_key_3', 'weight': 1, 'daily_limit': 20000},
                    {'key': 'groq_key_4', 'weight': 1, 'daily_limit': 20000},
                    {'key': 'groq_key_5', 'weight': 1, 'daily_limit': 20000}
                ],
                'github': [
                    {'key': 'github_admin_key', 'weight': 3, 'daily_limit': 50000},
                    {'key': 'github_key_1', 'weight': 1, 'daily_limit': 15000},
                    {'key': 'github_key_2', 'weight': 1, 'daily_limit': 15000}
                ],
                'pinecone': [
                    {'key': 'pinecone_key_1', 'weight': 1, 'daily_limit': 100000}
                ]
            }
            
            if service_name not in service_keys:
                return None
            
            # Get or initialize key usage tracking
            if not hasattr(self, 'api_key_usage'):
                self.api_key_usage = {}
            
            today = datetime.utcnow().date().isoformat()
            
            # Find available key with lowest usage
            available_keys = []
            for key_info in service_keys[service_name]:
                key_name = key_info['key']
                daily_limit = key_info['daily_limit']
                
                # Initialize tracking if needed
                if key_name not in self.api_key_usage:
                    self.api_key_usage[key_name] = {}
                
                # Get today's usage
                today_usage = self.api_key_usage[key_name].get(today, 0)
                
                # Check if key is available
                if today_usage < daily_limit:
                    available_keys.append({
                        'key': key_name,
                        'usage': today_usage,
                        'limit': daily_limit,
                        'weight': key_info['weight'],
                        'utilization': today_usage / daily_limit
                    })
            
            if not available_keys:
                await self._create_system_alert('critical', f'No available API keys for {service_name}', {
                    'service': service_name,
                    'agent_id': agent_id
                })
                return None
            
            # Select key with lowest utilization (weighted)
            selected_key = min(available_keys, key=lambda x: x['utilization'] / x['weight'])
            
            # Track usage
            key_name = selected_key['key']
            self.api_key_usage[key_name][today] = self.api_key_usage[key_name].get(today, 0) + 1
            
            # Log key allocation
            await self._add_audit_entry("api_key_allocated", {
                "agent_id": agent_id,
                "service": service_name,
                "key_name": key_name,
                "daily_usage": self.api_key_usage[key_name][today],
                "daily_limit": selected_key['limit']
            })
            
            # Return actual key value (in production, these would be actual API keys)
            return await self._get_actual_api_key(key_name)
            
        except Exception as e:
            self.logger.error(f"Error getting API key for {service_name}: {str(e)}")
            return None
    
    async def _get_actual_api_key(self, key_name: str) -> Optional[str]:
        """Get actual API key value from secure storage"""
        try:
            # In production, this would retrieve keys from secure key management
            # For now, we'll use environment variables or configuration
            key_mapping = {
                # Claude keys
                'claude_key_1': os.environ.get('CLAUDE_API_KEY_1'),
                'claude_key_2': os.environ.get('CLAUDE_API_KEY_2'),
                'claude_key_3': os.environ.get('CLAUDE_API_KEY_3'),
                'claude_key_4': os.environ.get('CLAUDE_API_KEY_4'),
                'claude_key_5': os.environ.get('CLAUDE_API_KEY_5'),
                'claude_key_6': os.environ.get('CLAUDE_API_KEY_6'),
                'claude_key_7': os.environ.get('CLAUDE_API_KEY_7'),
                
                # OpenAI keys
                'openai_key_1': os.environ.get('OPENAI_API_KEY_1'),
                'openai_key_2': os.environ.get('OPENAI_API_KEY_2'),
                'openai_key_3': os.environ.get('OPENAI_API_KEY_3'),
                'openai_key_4': os.environ.get('OPENAI_API_KEY_4'),
                'openai_key_5': os.environ.get('OPENAI_API_KEY_5'),
                'openai_service_1': os.environ.get('OPENAI_SERVICE_KEY_1'),
                'openai_service_2': os.environ.get('OPENAI_SERVICE_KEY_2'),
                'openai_service_3': os.environ.get('OPENAI_SERVICE_KEY_3'),
                
                # Gemini keys
                'gemini_key_1': os.environ.get('GEMINI_API_KEY_1'),
                'gemini_key_2': os.environ.get('GEMINI_API_KEY_2'),
                'gemini_key_3': os.environ.get('GEMINI_API_KEY_3'),
                'gemini_key_4': os.environ.get('GEMINI_API_KEY_4'),
                'gemini_key_5': os.environ.get('GEMINI_API_KEY_5'),
                
                # Deepseek keys
                'deepseek_key_1': os.environ.get('DEEPSEEK_API_KEY_1'),
                'deepseek_key_2': os.environ.get('DEEPSEEK_API_KEY_2'),
                'deepseek_key_3': os.environ.get('DEEPSEEK_API_KEY_3'),
                'deepseek_key_4': os.environ.get('DEEPSEEK_API_KEY_4'),
                'deepseek_key_5': os.environ.get('DEEPSEEK_API_KEY_5'),
                
                # Groq keys
                'groq_key_1': os.environ.get('GROQ_API_KEY_1'),
                'groq_key_2': os.environ.get('GROQ_API_KEY_2'),
                'groq_key_3': os.environ.get('GROQ_API_KEY_3'),
                'groq_key_4': os.environ.get('GROQ_API_KEY_4'),
                'groq_key_5': os.environ.get('GROQ_API_KEY_5'),
                
                # GitHub keys
                'github_admin_key': os.environ.get('GITHUB_ADMIN_TOKEN'),
                'github_key_1': os.environ.get('GITHUB_TOKEN_1'),
                'github_key_2': os.environ.get('GITHUB_TOKEN_2'),
                
                # Pinecone key
                'pinecone_key_1': os.environ.get('PINECONE_API_KEY')
            }
            
            return key_mapping.get(key_name)
            
        except Exception as e:
            self.logger.error(f"Error retrieving actual API key for {key_name}: {str(e)}")
            return None
    
    async def get_api_usage_report(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate API usage report"""
        try:
            if not hasattr(self, 'api_key_usage'):
                return {'error': 'No usage data available'}
            
            today = datetime.utcnow().date().isoformat()
            
            usage_report = {
                'date': today,
                'services': {},
                'total_requests': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Service limits for reference
            service_limits = {
                'claude': 10000,
                'openai': 15000,
                'gemini': 12000,
                'deepseek': 8000,
                'groq': 20000,
                'github': 15000,
                'pinecone': 100000
            }
            
            for key_name, usage_data in self.api_key_usage.items():
                # Determine service from key name
                key_service = None
                for service in service_limits:
                    if service in key_name:
                        key_service = service
                        break
                
                if not key_service or (service_name and key_service != service_name):
                    continue
                
                if key_service not in usage_report['services']:
                    usage_report['services'][key_service] = {
                        'keys': {},
                        'total_requests': 0,
                        'total_limit': service_limits[key_service]
                    }
                
                today_usage = usage_data.get(today, 0)
                usage_report['services'][key_service]['keys'][key_name] = {
                    'requests': today_usage,
                    'limit': service_limits[key_service],
                    'utilization': today_usage / service_limits[key_service]
                }
                
                usage_report['services'][key_service]['total_requests'] += today_usage
                usage_report['total_requests'] += today_usage
            
            return usage_report
            
        except Exception as e:
            self.logger.error(f"Error generating API usage report: {str(e)}")
            return {'error': 'Failed to generate usage report'}
    
    async def stop_monitoring(self) -> None:
        """Stop all monitoring tasks"""
        try:
            self.logger.info("Stopping continuous monitoring...")
            self.running = False
            
            # Cancel all monitoring tasks
            for task in self.monitoring_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            if self.monitoring_tasks:
                await asyncio.wait(self.monitoring_tasks, timeout=10, return_when=asyncio.ALL_COMPLETED)
            
            self.monitoring_tasks.clear()
            
            # Final cleanup
            await self.cleanup_expired_resources()
            
            self.logger.info("Monitoring stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_monitoring()


# Example usage and configuration
class ManagerConfig:
    """Configuration for the Manager Agent"""
    def __init__(self):
        self.max_browser_sessions = 20
        self.max_browser_sessions_per_agent = 3
        self.max_compute_allocations = 15
        self.max_queue_size = 50
        
        self.performance_thresholds = {
            'max_avg_execution_time': 300.0,  # 5 minutes
            'min_success_rate': 0.8,
            'max_load': 0.9
        }
        
        # Database configuration
        self.database_url = os.environ.get('DATABASE_URL', 'sqlite:///ai_dev_environment.db')
        
        # Message bus configuration
        self.message_bus_url = os.environ.get('MESSAGE_BUS_URL', 'redis://localhost:6379')
        
        # Security configuration
        self.encryption_key = os.environ.get('ENCRYPTION_KEY', 'development-key-32-chars-long!!')
        
        # Logging configuration
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO')


# Production deployment example
async def run_manager_agent():
    """Production deployment example"""
    try:
        config = ManagerConfig()
        
        async with ManagerAgent(config) as manager:
            # Start continuous monitoring
            await manager.start_continuous_monitoring()
            
    except KeyboardInterrupt:
        print("Manager agent stopped by user")
    except Exception as e:
        print(f"Manager agent error: {str(e)}")


if __name__ == "__main__":
    # For Replit deployment
    import asyncio
    asyncio.run(run_manager_agent())