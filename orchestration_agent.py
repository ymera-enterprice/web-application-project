"""
YMERA Enterprise Multi-Agent System v3.0
Orchestration Agent - Central Workflow Coordinator
Production-Ready Agent for Task Distribution and Learning Loop Management
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from concurrent.futures import ThreadPoolExecutor
import time
import hashlib

from base_agent import BaseAgent, AgentStatus, TaskPriority, ExecutionResult
from sqlalchemy import Column, String, DateTime, JSON, Integer, Text, Boolean, Float
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

logger = structlog.get_logger()

class WorkflowStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    LEARNING = "learning"

class WorkflowType(Enum):
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    ENHANCEMENT = "enhancement"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"
    LEARNING_CYCLE = "learning_cycle"

@dataclass
class WorkflowStep:
    """Individual step in a workflow"""
    id: str
    agent_type: str
    task_description: str
    dependencies: List[str]
    parameters: Dict[str, Any]
    timeout_seconds: int = 300
    retry_count: int = 3
    priority: TaskPriority = TaskPriority.MEDIUM
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

@dataclass
class Workflow:
    """Complete workflow definition"""
    id: str
    name: str
    description: str
    workflow_type: WorkflowType
    steps: List[WorkflowStep]
    created_at: datetime
    status: WorkflowStatus = WorkflowStatus.PENDING
    metadata: Dict[str, Any] = None
    learning_enabled: bool = True
    auto_optimize: bool = True

class LearningMetrics(BaseModel):
    """Learning metrics for workflow optimization"""
    workflow_id: str
    execution_time: float
    success_rate: float
    error_patterns: List[str]
    performance_score: float
    optimization_suggestions: List[str]
    learning_confidence: float

class OrchestrationAgent(BaseAgent):
    """
    Enterprise Orchestration Agent
    Manages workflow execution, task distribution, and learning loop optimization
    """
    
    def __init__(self, agent_id: str = None):
        super().__init__(
            agent_id=agent_id or f"orchestration_{uuid.uuid4().hex[:8]}",
            agent_type="orchestration",
            capabilities=[
                "workflow_management",
                "task_distribution", 
                "learning_optimization",
                "performance_monitoring",
                "resource_allocation",
                "failure_recovery",
                "auto_scaling"
            ]
        )
        
        self.active_workflows: Dict[str, Workflow] = {}
        self.workflow_templates: Dict[str, Dict[str, Any]] = {}
        self.learning_history: List[LearningMetrics] = []
        self.agent_registry: Dict[str, Dict[str, Any]] = {}
        self.performance_cache: Dict[str, float] = {}
        self.learning_engine_active = True
        
        # Workflow execution metrics
        self.execution_stats = {
            "total_workflows": 0,
            "successful_workflows": 0,
            "failed_workflows": 0,
            "average_execution_time": 0.0,
            "learning_cycles_completed": 0,
            "optimization_improvements": 0
        }
        
        logger.info("Orchestration Agent initialized", agent_id=self.agent_id)

    async def initialize(self) -> bool:
        """Initialize orchestration agent with enterprise capabilities"""
        try:
            await super().initialize()
            
            # Initialize workflow templates
            await self._load_workflow_templates()
            
            # Register with manager agent
            await self._register_with_manager()
            
            # Start learning engine
            if self.learning_engine_active:
                asyncio.create_task(self._learning_loop())
            
            # Start workflow monitor
            asyncio.create_task(self._workflow_monitor())
            
            logger.info("Orchestration Agent fully initialized", 
                       templates_loaded=len(self.workflow_templates))
            return True
            
        except Exception as e:
            logger.error("Failed to initialize Orchestration Agent", error=str(e))
            return False

    async def _load_workflow_templates(self):
        """Load predefined workflow templates"""
        self.workflow_templates = {
            "code_generation_standard": {
                "name": "Standard Code Generation",
                "type": WorkflowType.CODE_GENERATION,
                "steps": [
                    {
                        "agent_type": "project_agent",
                        "task": "analyze_requirements",
                        "dependencies": [],
                        "timeout": 180
                    },
                    {
                        "agent_type": "examination_agent", 
                        "task": "code_analysis",
                        "dependencies": ["analyze_requirements"],
                        "timeout": 300
                    },
                    {
                        "agent_type": "editing_agent",
                        "task": "generate_code",
                        "dependencies": ["code_analysis"],
                        "timeout": 600
                    },
                    {
                        "agent_type": "validation_agent",
                        "task": "validate_code",
                        "dependencies": ["generate_code"],
                        "timeout": 240
                    },
                    {
                        "agent_type": "enhancement_agent",
                        "task": "optimize_code",
                        "dependencies": ["validate_code"],
                        "timeout": 300
                    }
                ]
            },
            
            "full_development_cycle": {
                "name": "Complete Development Lifecycle",
                "type": WorkflowType.CODE_GENERATION,
                "steps": [
                    {
                        "agent_type": "project_agent",
                        "task": "setup_project_structure",
                        "dependencies": [],
                        "timeout": 120
                    },
                    {
                        "agent_type": "examination_agent",
                        "task": "requirements_analysis", 
                        "dependencies": ["setup_project_structure"],
                        "timeout": 300
                    },
                    {
                        "agent_type": "editing_agent",
                        "task": "generate_application_code",
                        "dependencies": ["requirements_analysis"],
                        "timeout": 900
                    },
                    {
                        "agent_type": "validation_agent",
                        "task": "comprehensive_testing",
                        "dependencies": ["generate_application_code"],
                        "timeout": 600
                    },
                    {
                        "agent_type": "communication_agent",
                        "task": "generate_documentation",
                        "dependencies": ["comprehensive_testing"],
                        "timeout": 300
                    },
                    {
                        "agent_type": "monitoring_agent",
                        "task": "setup_monitoring",
                        "dependencies": ["generate_documentation"],
                        "timeout": 240
                    },
                    {
                        "agent_type": "enhancement_agent",
                        "task": "performance_optimization",
                        "dependencies": ["setup_monitoring"],
                        "timeout": 450
                    }
                ]
            },
            
            "learning_optimization_cycle": {
                "name": "Learning and Optimization Cycle",
                "type": WorkflowType.LEARNING_CYCLE,
                "steps": [
                    {
                        "agent_type": "monitoring_agent",
                        "task": "collect_performance_metrics",
                        "dependencies": [],
                        "timeout": 120
                    },
                    {
                        "agent_type": "examination_agent",
                        "task": "analyze_patterns",
                        "dependencies": ["collect_performance_metrics"],
                        "timeout": 300
                    },
                    {
                        "agent_type": "enhancement_agent",
                        "task": "generate_improvements",
                        "dependencies": ["analyze_patterns"],
                        "timeout": 400
                    },
                    {
                        "agent_type": "validation_agent",
                        "task": "validate_improvements",
                        "dependencies": ["generate_improvements"],
                        "timeout": 300
                    }
                ]
            }
        }

    async def create_workflow(self, 
                            workflow_name: str,
                            workflow_type: WorkflowType,
                            parameters: Dict[str, Any],
                            template_name: Optional[str] = None) -> str:
        """Create a new workflow from template or custom definition"""
        
        try:
            workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
            
            if template_name and template_name in self.workflow_templates:
                template = self.workflow_templates[template_name]
                steps = await self._create_steps_from_template(template["steps"], parameters)
            else:
                steps = await self._create_custom_steps(workflow_type, parameters)
            
            workflow = Workflow(
                id=workflow_id,
                name=workflow_name,
                description=parameters.get("description", ""),
                workflow_type=workflow_type,
                steps=steps,
                created_at=datetime.utcnow(),
                metadata=parameters,
                learning_enabled=parameters.get("enable_learning", True),
                auto_optimize=parameters.get("auto_optimize", True)
            )
            
            self.active_workflows[workflow_id] = workflow
            
            logger.info("Workflow created successfully", 
                       workflow_id=workflow_id,
                       workflow_type=workflow_type.value,
                       steps_count=len(steps))
            
            return workflow_id
            
        except Exception as e:
            logger.error("Failed to create workflow", error=str(e))
            raise

    async def _create_steps_from_template(self, 
                                        template_steps: List[Dict[str, Any]], 
                                        parameters: Dict[str, Any]) -> List[WorkflowStep]:
        """Create workflow steps from template"""
        steps = []
        
        for i, step_template in enumerate(template_steps):
            step_id = f"step_{i+1:03d}_{uuid.uuid4().hex[:8]}"
            
            step = WorkflowStep(
                id=step_id,
                agent_type=step_template["agent_type"],
                task_description=step_template["task"],
                dependencies=step_template.get("dependencies", []),
                parameters={**parameters, **step_template.get("parameters", {})},
                timeout_seconds=step_template.get("timeout", 300),
                retry_count=step_template.get("retry_count", 3),
                priority=TaskPriority(step_template.get("priority", "medium"))
            )
            
            steps.append(step)
        
        return steps

    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute workflow with learning and optimization"""
        
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.active_workflows[workflow_id]
        workflow.status = WorkflowStatus.IN_PROGRESS
        
        start_time = time.time()
        execution_log = []
        
        try:
            logger.info("Starting workflow execution", 
                       workflow_id=workflow_id,
                       workflow_name=workflow.name)
            
            # Execute steps based on dependencies
            completed_steps = set()
            
            while len(completed_steps) < len(workflow.steps):
                ready_steps = self._get_ready_steps(workflow.steps, completed_steps)
                
                if not ready_steps:
                    # Check for circular dependencies or stuck workflow
                    remaining_steps = [s for s in workflow.steps if s.id not in completed_steps]
                    logger.warning("No ready steps found", 
                                 remaining_steps=[s.id for s in remaining_steps])
                    break
                
                # Execute ready steps concurrently
                tasks = []
                for step in ready_steps:
                    task = asyncio.create_task(self._execute_step(step, workflow))
                    tasks.append(task)
                
                # Wait for step completion
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    step = ready_steps[i]
                    
                    if isinstance(result, Exception):
                        step.status = WorkflowStatus.FAILED
                        step.error_message = str(result)
                        execution_log.append({
                            "step_id": step.id,
                            "status": "failed",
                            "error": str(result),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        # Handle failure based on workflow configuration
                        if not await self._handle_step_failure(step, workflow):
                            workflow.status = WorkflowStatus.FAILED
                            break
                    else:
                        step.status = WorkflowStatus.COMPLETED
                        step.result = result
                        step.completed_at = datetime.utcnow()
                        completed_steps.add(step.id)
                        
                        execution_log.append({
                            "step_id": step.id,
                            "status": "completed",
                            "execution_time": (step.completed_at - step.started_at).total_seconds(),
                            "timestamp": step.completed_at.isoformat()
                        })
            
            # Determine final workflow status
            if workflow.status != WorkflowStatus.FAILED:
                if len(completed_steps) == len(workflow.steps):
                    workflow.status = WorkflowStatus.COMPLETED
                    self.execution_stats["successful_workflows"] += 1
                else:
                    workflow.status = WorkflowStatus.FAILED
                    self.execution_stats["failed_workflows"] += 1
            
            execution_time = time.time() - start_time
            self.execution_stats["total_workflows"] += 1
            self.execution_stats["average_execution_time"] = (
                (self.execution_stats["average_execution_time"] * (self.execution_stats["total_workflows"] - 1) + execution_time) /
                self.execution_stats["total_workflows"]
            )
            
            # Learning phase
            if workflow.learning_enabled and workflow.status == WorkflowStatus.COMPLETED:
                await self._learn_from_execution(workflow, execution_time, execution_log)
            
            logger.info("Workflow execution completed", 
                       workflow_id=workflow_id,
                       status=workflow.status.value,
                       execution_time=execution_time,
                       completed_steps=len(completed_steps))
            
            return {
                "workflow_id": workflow_id,
                "status": workflow.status.value,
                "execution_time": execution_time,
                "completed_steps": len(completed_steps),
                "total_steps": len(workflow.steps),
                "execution_log": execution_log,
                "learning_applied": workflow.learning_enabled
            }
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            self.execution_stats["failed_workflows"] += 1
            logger.error("Workflow execution failed", 
                        workflow_id=workflow_id, 
                        error=str(e))
            raise

    def _get_ready_steps(self, steps: List[WorkflowStep], completed_steps: set) -> List[WorkflowStep]:
        """Get steps that are ready to execute based on dependencies"""
        ready_steps = []
        
        for step in steps:
            if (step.status == WorkflowStatus.PENDING and 
                all(dep in completed_steps for dep in step.dependencies)):
                ready_steps.append(step)
        
        return ready_steps

    async def _execute_step(self, step: WorkflowStep, workflow: Workflow) -> Dict[str, Any]:
        """Execute individual workflow step"""
        
        step.started_at = datetime.utcnow()
        step.status = WorkflowStatus.IN_PROGRESS
        
        try:
            logger.info("Executing workflow step", 
                       step_id=step.id,
                       agent_type=step.agent_type,
                       task=step.task_description)
            
            # Get agent for step execution
            agent = await self._get_agent_for_step(step.agent_type)
            
            if not agent:
                raise Exception(f"Agent {step.agent_type} not available")
            
            # Prepare task for agent
            task_data = {
                "task_id": f"{step.id}_task",
                "task_type": step.task_description,
                "parameters": step.parameters,
                "workflow_context": {
                    "workflow_id": workflow.id,
                    "workflow_type": workflow.workflow_type.value,
                    "step_id": step.id
                },
                "priority": step.priority.value,
                "timeout": step.timeout_seconds
            }
            
            # Execute with timeout
            result = await asyncio.wait_for(
                agent.execute_task(task_data),
                timeout=step.timeout_seconds
            )
            
            return result.to_dict() if hasattr(result, 'to_dict') else result
            
        except asyncio.TimeoutError:
            logger.error("Step execution timeout", 
                        step_id=step.id,
                        timeout=step.timeout_seconds)
            raise Exception(f"Step {step.id} timed out after {step.timeout_seconds} seconds")
        
        except Exception as e:
            logger.error("Step execution failed", 
                        step_id=step.id,
                        error=str(e))
            raise

    async def _get_agent_for_step(self, agent_type: str):
        """Get appropriate agent for step execution"""
        # This would integrate with your manager agent to get available agents
        # For now, returning a placeholder that would be connected to actual agent registry
        
        if agent_type in self.agent_registry:
            agent_info = self.agent_registry[agent_type]
            # Return the actual agent instance
            return agent_info.get("instance")
        
        # Request agent from manager
        from the_manager_agent import TheManagerAgent
        manager = TheManagerAgent.get_instance()
        
        if manager:
            return await manager.get_agent(agent_type)
        
        return None

    async def _handle_step_failure(self, step: WorkflowStep, workflow: Workflow) -> bool:
        """Handle step failure with retry logic"""
        
        if step.retry_count > 0:
            step.retry_count -= 1
            step.status = WorkflowStatus.PENDING
            step.error_message = None
            
            logger.info("Retrying failed step", 
                       step_id=step.id,
                       retries_left=step.retry_count)
            
            # Add delay before retry
            await asyncio.sleep(min(5, 3 - step.retry_count))
            return True
        
        # Check if failure is critical for workflow
        critical_failure = step.priority == TaskPriority.HIGH
        
        if critical_failure:
            logger.error("Critical step failed, stopping workflow", 
                        step_id=step.id,
                        workflow_id=workflow.id)
            return False
        
        logger.warning("Non-critical step failed, continuing workflow", 
                      step_id=step.id)
        return True

    async def _learn_from_execution(self, 
                                  workflow: Workflow, 
                                  execution_time: float, 
                                  execution_log: List[Dict[str, Any]]):
        """Learn from workflow execution for optimization"""
        
        try:
            # Calculate metrics
            success_rate = len([log for log in execution_log if log["status"] == "completed"]) / len(execution_log)
            
            error_patterns = [
                log["error"] for log in execution_log 
                if log["status"] == "failed" and "error" in log
            ]
            
            # Performance analysis
            step_times = [
                log["execution_time"] for log in execution_log 
                if "execution_time" in log
            ]
            
            performance_score = self._calculate_performance_score(
                execution_time, success_rate, len(error_patterns)
            )
            
            # Generate optimization suggestions
            suggestions = await self._generate_optimization_suggestions(
                workflow, execution_time, error_patterns, step_times
            )
            
            # Store learning metrics
            learning_metrics = LearningMetrics(
                workflow_id=workflow.id,
                execution_time=execution_time,
                success_rate=success_rate,
                error_patterns=error_patterns,
                performance_score=performance_score,
                optimization_suggestions=suggestions,
                learning_confidence=min(success_rate + 0.1, 1.0)
            )
            
            self.learning_history.append(learning_metrics)
            
            # Apply optimizations if confidence is high
            if learning_metrics.learning_confidence > 0.8 and workflow.auto_optimize:
                await self._apply_optimizations(workflow, suggestions)
            
            self.execution_stats["learning_cycles_completed"] += 1
            
            logger.info("Learning completed for workflow", 
                       workflow_id=workflow.id,
                       performance_score=performance_score,
                       suggestions_count=len(suggestions))
            
        except Exception as e:
            logger.error("Learning process failed", 
                        workflow_id=workflow.id,
                        error=str(e))

    def _calculate_performance_score(self, 
                                   execution_time: float, 
                                   success_rate: float, 
                                   error_count: int) -> float:
        """Calculate performance score for learning"""
        
        # Base score from success rate
        score = success_rate * 100
        
        # Penalty for long execution times
        if execution_time > 300:  # 5 minutes
            score *= 0.9
        if execution_time > 600:  # 10 minutes
            score *= 0.8
        
        # Penalty for errors
        score -= (error_count * 10)
        
        return max(0, min(100, score))

    async def _generate_optimization_suggestions(self, 
                                               workflow: Workflow,
                                               execution_time: float,
                                               error_patterns: List[str],
                                               step_times: List[float]) -> List[str]:
        """Generate optimization suggestions based on execution analysis"""
        
        suggestions = []
        
        # Execution time optimization
        if execution_time > 600:
            suggestions.append("Consider parallelizing independent steps")
            suggestions.append("Optimize agent response times")
        
        # Error pattern analysis
        common_errors = {}
        for error in error_patterns:
            error_type = error.split(":")[0] if ":" in error else error
            common_errors[error_type] = common_errors.get(error_type, 0) + 1
        
        for error_type, count in common_errors.items():
            if count > 1:
                suggestions.append(f"Add error handling for {error_type}")
        
        # Step time analysis
        if step_times:
            avg_step_time = sum(step_times) / len(step_times)
            slow_steps = [t for t in step_times if t > avg_step_time * 2]
            
            if slow_steps:
                suggestions.append("Optimize slow-performing steps")
                suggestions.append("Consider step timeout adjustments")
        
        # Resource optimization
        if len(workflow.steps) > 10:
            suggestions.append("Consider breaking workflow into smaller workflows")
        
        return suggestions

    async def _apply_optimizations(self, workflow: Workflow, suggestions: List[str]):
        """Apply learning-based optimizations to workflow"""
        
        optimizations_applied = 0
        
        for suggestion in suggestions:
            try:
                if "parallelizing" in suggestion.lower():
                    # Analyze step dependencies and create parallel execution groups
                    await self._optimize_parallelization(workflow)
                    optimizations_applied += 1
                
                elif "timeout" in suggestion.lower():
                    # Adjust timeouts based on historical performance
                    await self._optimize_timeouts(workflow)
                    optimizations_applied += 1
                
                elif "error handling" in suggestion.lower():
                    # Improve retry strategies
                    await self._optimize_error_handling(workflow)
                    optimizations_applied += 1
                    
            except Exception as e:
                logger.error("Failed to apply optimization", 
                           suggestion=suggestion,
                           error=str(e))
        
        if optimizations_applied > 0:
            self.execution_stats["optimization_improvements"] += optimizations_applied
            logger.info("Applied workflow optimizations", 
                       workflow_id=workflow.id,
                       optimizations=optimizations_applied)

    async def _optimize_parallelization(self, workflow: Workflow):
        """Optimize step parallelization based on dependencies"""
        # Implementation would analyze dependency graph and create parallel groups
        pass

    async def _optimize_timeouts(self, workflow: Workflow):
        """Optimize step timeouts based on historical performance"""
        # Implementation would adjust timeouts based on average execution times
        pass

    async def _optimize_error_handling(self, workflow: Workflow):
        """Optimize error handling and retry strategies"""
        # Implementation would adjust retry counts and strategies
        pass

    async def _learning_loop(self):
        """Continuous learning loop for system optimization"""
        
        while self.learning_engine_active:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Analyze recent workflows
                recent_workflows = [
                    wf for wf in self.active_workflows.values()
                    if wf.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]
                    and (datetime.utcnow() - wf.created_at) < timedelta(hours=1)
                ]
                
                if recent_workflows:
                    await self._analyze_workflow_patterns(recent_workflows)
                    await self._update_workflow_templates()
                
                # Clean up completed workflows older than retention period
                await self._cleanup_old_workflows()
                
            except Exception as e:
                logger.error("Learning loop error", error=str(e))

    async def _workflow_monitor(self):
        """Monitor active workflows for health and performance"""
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                
                for workflow in self.active_workflows.values():
                    if workflow.status == WorkflowStatus.IN_PROGRESS:
                        # Check for stuck workflows
                        runtime = (current_time - workflow.created_at).total_seconds()
                        max_runtime = sum(step.timeout_seconds for step in workflow.steps) + 300
                        
                        if runtime > max_runtime:
                            logger.warning("Workflow appears stuck", 
                                         workflow_id=workflow.id,
                                         runtime=runtime)
                            await self._handle_stuck_workflow(workflow)
                
            except Exception as e:
                logger.error("Workflow monitor error", error=str(e))

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed workflow status"""
        
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.active_workflows[workflow_id]
        
        step_statuses = [
            {
                "step_id": step.id,
                "agent_type": step.agent_type,
                "task": step.task_description,
                "status": step.status.value,
                "started_at": step.started_at.isoformat() if step.started_at else None,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "error": step.error_message
            }
            for step in workflow.steps
        ]
        
        return {
            "workflow_id": workflow_id,
            "name": workflow.name,
            "description": workflow.description,
            "type": workflow.workflow_type.value,
            "status": workflow.status.value,
            "created_at": workflow.created_at.isoformat(),
            "steps": step_statuses,
            "learning_enabled": workflow.learning_enabled,
            "metadata": workflow.metadata
        }

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel active workflow"""
        
        if workflow_id not in self.active_workflows:
            return False
        
        workflow = self.active_workflows[workflow_id]
        
        if workflow.status == WorkflowStatus.IN_PROGRESS:
            workflow.status = WorkflowStatus.CANCELLED
            
            # Cancel any running steps
            for step in workflow.steps:
                if step.status == WorkflowStatus.IN_PROGRESS:
                    step.status = WorkflowStatus.CANCELLED
            
            logger.info("Workflow cancelled", workflow_id=workflow_id)
            return True
        
        return False

    async def get_execution_statistics(self) -> Dict[str, Any]:
        """Get orchestration execution statistics"""
        
        return {
            "execution_stats": self.execution_stats.copy(),
            "active_workflows": len([
                wf for wf in self.active_workflows.values()
                if wf.status == WorkflowStatus.IN_PROGRESS
            ]),
            "total_workflows": len(self.active_workflows),
            "learning_history_size": len(self.learning_history),
            "template_count": len(self.workflow_templates),
            "agent_registry_size": len(self.agent_registry),
            "system_health": await self._get_system_health()
        }

    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        
        return {
            "memory_usage": psutil.virtual_memory().percent,
            "cpu_usage": psutil.cpu_percent(interval=1),
            "active_agents": len(self.agent_registry),
            "learning_engine_active": self.learning_engine_active,
            "last_learning_cycle": datetime.utcnow().isoformat()
        }

async def _analyze_workflow_patterns(self, workflows: List[Workflow]):
“”“Analyze patterns in completed workflows for optimization”””

```
    try:
        # Group by workflow type for pattern analysis
        type_groups = defaultdict(list)
        for workflow in workflows:
            type_groups[workflow.workflow_type].append(workflow)
        
        for workflow_type, type_workflows in type_groups.items():
            success_rate = len([w for w in type_workflows if w.status == WorkflowStatus.COMPLETED]) / len(type_workflows)
            
            if success_rate < 0.8:  # Less than 80% success rate
                await self._analyze_failure_patterns(workflow_type, type_workflows)
            
            # Analyze execution time patterns
            execution_times = []
            for workflow in type_workflows:
                if workflow.completed_at and workflow.started_at:
                    exec_time = (workflow.completed_at - workflow.started_at).total_seconds()
                    execution_times.append(exec_time)
            
            if execution_times:
                avg_time = sum(execution_times) / len(execution_times)
                if avg_time > 600:  # More than 10 minutes average
                    await self._optimize_workflow_type_performance(workflow_type)
        
        logger.info("Workflow pattern analysis completed", 
                   workflow_types=len(type_groups),
                   total_workflows=len(workflows))
        
    except Exception as e:
        logger.error("Pattern analysis failed", error=str(e))

async def _analyze_failure_patterns(self, workflow_type: WorkflowType, workflows: List[Workflow]):
    """Analyze failure patterns for specific workflow type"""
    
    failed_workflows = [w for w in workflows if w.status == WorkflowStatus.FAILED]
    
    # Collect error patterns
    error_patterns = defaultdict(int)
    failing_agents = defaultdict(int)
    
    for workflow in failed_workflows:
        for step in workflow.steps:
            if step.error_message:
                error_type = step.error_message.split(":")[0] if ":" in step.error_message else "unknown"
                error_patterns[error_type] += 1
                failing_agents[step.agent_type] += 1
    
    # Create optimization rule
    optimization_rule = {
        "workflow_type": workflow_type.value,
        "common_errors": dict(error_patterns),
        "problematic_agents": dict(failing_agents),
        "recommended_actions": [],
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Generate recommendations
    for agent_type, failure_count in failing_agents.items():
        if failure_count > len(failed_workflows) * 0.3:  # Fails in >30% of workflows
            optimization_rule["recommended_actions"].append(
                f"Review and optimize {agent_type} agent configuration"
            )
    
    for error_type, count in error_patterns.items():
        if count > len(failed_workflows) * 0.5:  # Common error
            optimization_rule["recommended_actions"].append(
                f"Add specific error handling for {error_type}"
            )
    
    self.optimization_rules[f"{workflow_type.value}_failures"] = optimization_rule
    
    logger.info("Failure pattern analysis completed", 
               workflow_type=workflow_type.value,
               failed_count=len(failed_workflows),
               error_patterns=len(error_patterns))

async def _optimize_workflow_type_performance(self, workflow_type: WorkflowType):
    """Optimize performance for specific workflow type"""
    
    # Get template for this workflow type
    template_key = f"{workflow_type.value}_template"
    if template_key in self.workflow_templates:
        template = self.workflow_templates[template_key]
        
        # Apply performance optimizations
        optimizations = {
            "parallel_execution": True,
            "timeout_adjustments": {},
            "priority_adjustments": {},
            "caching_enabled": True
        }
        
        # Analyze step performance from historical data
        step_performance = defaultdict(list)
        
        for workflow in self.active_workflows.values():
            if workflow.workflow_type == workflow_type:
                for step in workflow.steps:
                    if step.started_at and step.completed_at:
                        exec_time = (step.completed_at - step.started_at).total_seconds()
                        step_performance[step.agent_type].append(exec_time)
        
        # Adjust timeouts based on actual performance
        for agent_type, times in step_performance.items():
            if times:
                avg_time = sum(times) / len(times)
                max_time = max(times)
                # Set timeout to 150% of max observed time, minimum 60 seconds
                optimized_timeout = max(60, int(max_time * 1.5))
                optimizations["timeout_adjustments"][agent_type] = optimized_timeout
        
        template["optimizations"] = optimizations
        template["last_optimized"] = datetime.utcnow().isoformat()
        
        logger.info("Workflow type optimized", 
                   workflow_type=workflow_type.value,
                   optimizations=len(optimizations))

async def _update_workflow_templates(self):
    """Update workflow templates based on learning"""
    
    for template_name, template in self.workflow_templates.items():
        # Apply learned optimizations
        if "optimizations" in template:
            opts = template["optimizations"]
            
            # Update step configurations
            for step_config in template.get("steps", []):
                agent_type = step_config.get("agent_type")
                
                if agent_type in opts.get("timeout_adjustments", {}):
                    step_config["timeout_seconds"] = opts["timeout_adjustments"][agent_type]
                
                if agent_type in opts.get("priority_adjustments", {}):
                    step_config["priority"] = opts["priority_adjustments"][agent_type]
            
            # Enable parallel execution if beneficial
            if opts.get("parallel_execution", False):
                template["execution_strategy"] = "parallel_optimized"
    
    logger.info("Workflow templates updated", count=len(self.workflow_templates))

async def _cleanup_old_workflows(self):
    """Clean up old completed workflows"""
    
    cutoff_time = datetime.utcnow() - timedelta(hours=24)  # Keep 24 hours
    workflows_to_remove = []
    
    for workflow_id, workflow in self.active_workflows.items():
        if (workflow.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED] and 
            workflow.completed_at and workflow.completed_at < cutoff_time):
            workflows_to_remove.append(workflow_id)
    
    for workflow_id in workflows_to_remove:
        del self.active_workflows[workflow_id]
    
    if workflows_to_remove:
        logger.info("Cleaned up old workflows", count=len(workflows_to_remove))

async def _handle_stuck_workflow(self, workflow: Workflow):
    """Handle workflows that appear to be stuck"""
    
    logger.warning("Handling stuck workflow", 
                  workflow_id=workflow.id,
                  runtime=(datetime.utcnow() - workflow.created_at).total_seconds())
    
    # Try to recover by restarting failed/stuck steps
    stuck_steps = [
        step for step in workflow.steps 
        if step.status == WorkflowStatus.IN_PROGRESS and
        step.started_at and 
        (datetime.utcnow() - step.started_at).total_seconds() > step.timeout_seconds
    ]
    
    recovery_attempted = False
    
    for step in stuck_steps:
        if step.retry_count > 0:
            step.status = WorkflowStatus.PENDING
            step.started_at = None
            step.retry_count -= 1
            recovery_attempted = True
            logger.info("Attempting step recovery", 
                       step_id=step.id,
                       retries_left=step.retry_count)
    
    if not recovery_attempted:
        # Mark workflow as failed if no recovery possible
        workflow.status = WorkflowStatus.FAILED
        workflow.completed_at = datetime.utcnow()
        
        # Add to learning data for future optimization
        await self._learn_from_execution(
            workflow, 
            (datetime.utcnow() - workflow.created_at).total_seconds(),
            [{"status": "stuck", "step_id": step.id} for step in stuck_steps]
        )

def _initialize_workflow_templates(self):
    """Initialize standard workflow templates"""
    
    # Development workflow template
    self.workflow_templates["development_template"] = {
        "name": "Standard Development Workflow",
        "description": "Complete development cycle with AI agents",
        "workflow_type": WorkflowType.DEVELOPMENT.value,
        "steps": [
            {
                "agent_type": "examination",
                "task_description": "Analyze code requirements and architecture",
                "timeout_seconds": 300,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "enhancement",
                "task_description": "Generate and optimize code",
                "dependencies": ["examination"],
                "timeout_seconds": 600,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "validation",
                "task_description": "Test and validate implementation",
                "dependencies": ["enhancement"],
                "timeout_seconds": 400,
                "priority": TaskPriority.MEDIUM.value
            },
            {
                "agent_type": "editing",
                "task_description": "Finalize code edits and formatting",
                "dependencies": ["validation"],
                "timeout_seconds": 200,
                "priority": TaskPriority.MEDIUM.value
            }
        ]
    }
    
    # Testing workflow template
    self.workflow_templates["testing_template"] = {
        "name": "Comprehensive Testing Workflow",
        "description": "Multi-layer testing with AI agents",
        "workflow_type": WorkflowType.TESTING.value,
        "steps": [
            {
                "agent_type": "examination",
                "task_description": "Analyze testing requirements",
                "timeout_seconds": 200,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "validation",
                "task_description": "Execute unit and integration tests",
                "dependencies": ["examination"],
                "timeout_seconds": 500,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "monitoring",
                "task_description": "Monitor test execution and performance",
                "dependencies": ["validation"],
                "timeout_seconds": 300,
                "priority": TaskPriority.MEDIUM.value
            }
        ]
    }
    
    # Deployment workflow template
    self.workflow_templates["deployment_template"] = {
        "name": "AI-Native Deployment Workflow",
        "description": "Automated deployment with monitoring",
        "workflow_type": WorkflowType.DEPLOYMENT.value,
        "steps": [
            {
                "agent_type": "validation",
                "task_description": "Pre-deployment validation",
                "timeout_seconds": 300,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "editing",
                "task_description": "Prepare deployment artifacts",
                "dependencies": ["validation"],
                "timeout_seconds": 200,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "monitoring",
                "task_description": "Deploy and monitor system health",
                "dependencies": ["editing"],
                "timeout_seconds": 600,
                "priority": TaskPriority.HIGH.value
            },
            {
                "agent_type": "communication",
                "task_description": "Report deployment status",
                "dependencies": ["monitoring"],
                "timeout_seconds": 100,
                "priority": TaskPriority.LOW.value
            }
        ]
    }

async def register_agent(self, agent_instance, agent_type: str, capabilities: List[AgentCapability]):
    """Register an agent with the orchestration system"""
    
    registration = AgentRegistration(
        agent_type=agent_type,
        instance=agent_instance,
        capabilities=capabilities
    )
    
    self.agent_registry[agent_type] = registration
    
    logger.info("Agent registered", 
               agent_type=agent_type,
               capabilities=[cap.value for cap in capabilities])

async def create_custom_workflow(self, 
                               name: str,
                               description: str,
                               steps: List[Dict[str, Any]],
                               workflow_type: WorkflowType = WorkflowType.CUSTOM,
                               auto_optimize: bool = True) -> str:
    """Create a custom workflow"""
    
    workflow_id = str(uuid.uuid4())
    
    # Convert step dictionaries to WorkflowStep objects
    workflow_steps = []
    for step_config in steps:
        step = WorkflowStep(
            id=str(uuid.uuid4()),
            agent_type=step_config["agent_type"],
            task_description=step_config["task_description"],
            dependencies=step_config.get("dependencies", []),
            inputs=step_config.get("inputs", {}),
            priority=TaskPriority(step_config.get("priority", TaskPriority.MEDIUM.value)),
            timeout_seconds=step_config.get("timeout_seconds", 300),
            retry_count=step_config.get("retry_count", 3)
        )
        workflow_steps.append(step)
    
    workflow = Workflow(
        id=workflow_id,
        name=name,
        description=description,
        workflow_type=workflow_type,
        steps=workflow_steps,
        auto_optimize=auto_optimize
    )
    
    self.active_workflows[workflow_id] = workflow
    
    logger.info("Custom workflow created", 
               workflow_id=workflow_id,
               steps=len(workflow_steps))
    
    return workflow_id

async def start_learning_engine(self):
    """Start the continuous learning engine"""
    
    if not self.learning_engine_active:
        self.learning_engine_active = True
        
        # Start background tasks
        learning_task = asyncio.create_task(self._learning_loop())
        monitor_task = asyncio.create_task(self._workflow_monitor())
        
        self._background_tasks.add(learning_task)
        self._background_tasks.add(monitor_task)
        
        # Clean up completed tasks
        learning_task.add_done_callback(self._background_tasks.discard)
        monitor_task.add_done_callback(self._background_tasks.discard)
        
        logger.info("Learning engine started with background monitoring")

async def stop_learning_engine(self):
    """Stop the learning engine and background tasks"""
    
    self.learning_engine_active = False
    
    # Cancel all background tasks
    for task in self._background_tasks:
        task.cancel()
    
    # Wait for tasks to complete cancellation
    if self._background_tasks:
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
    
    logger.info("Learning engine stopped")

async def get_learning_insights(self) -> Dict[str, Any]:
    """Get insights from the learning engine"""
    
    if not self.learning_history:
        return {"insights": "No learning data available yet"}
    
    # Calculate overall statistics
    total_workflows = len(self.learning_history)
    avg_performance = sum(lm.performance_score for lm in self.learning_history) / total_workflows
    avg_success_rate = sum(lm.success_rate for lm in self.learning_history) / total_workflows
    
    # Top optimization suggestions
    all_suggestions = []
    for lm in self.learning_history:
        all_suggestions.extend(lm.optimization_suggestions)
    
    suggestion_counts = defaultdict(int)
    for suggestion in all_suggestions:
        suggestion_counts[suggestion] += 1
    
    top_suggestions = sorted(suggestion_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Error pattern analysis
    all_errors = []
    for lm in self.learning_history:
        all_errors.extend(lm.error_patterns)
    
    error_counts = defaultdict(int)
    for error in all_errors:
        error_counts[error] += 1
    
    common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "total_learning_cycles": total_workflows,
        "average_performance_score": round(avg_performance, 2),
        "average_success_rate": round(avg_success_rate, 2),
        "top_optimization_suggestions": [{"suggestion": s, "frequency": c} for s, c in top_suggestions],
        "common_error_patterns": [{"error": e, "frequency": c} for e, c in common_errors],
        "optimization_rules_count": len(self.optimization_rules),
        "learning_engine_active": self.learning_engine_active,
        "workflow_templates": len(self.workflow_templates)
    }

async def export_learning_data(self) -> Dict[str, Any]:
    """Export learning data for analysis or backup"""
    
    return {
        "learning_history": [
            {
                "workflow_id": lm.workflow_id,
                "execution_time": lm.execution_time,
                "success_rate": lm.success_rate,
                "error_patterns": lm.error_patterns,
                "performance_score": lm.performance_score,
                "optimization_suggestions": lm.optimization_suggestions,
                "learning_confidence": lm.learning_confidence,
                "timestamp": lm.timestamp.isoformat()
            }
            for lm in self.learning_history
        ],
        "optimization_rules": self.optimization_rules,
        "execution_stats": self.execution_stats,
        "workflow_templates": self.workflow_templates,
        "agent_registry": {
            agent_type: {
                "capabilities": [cap.value for cap in reg.capabilities],
                "status": reg.status,
                "last_used": reg.last_used.isoformat(),
                "performance_metrics": reg.performance_metrics
            }
            for agent_type, reg in self.agent_registry.items()
        }
    }

async def shutdown(self):
    """Gracefully shutdown the orchestration agent"""
    
    logger.info("Shutting down Orchestration Agent")
    
    # Stop learning engine
    await self.stop_learning_engine()
    
    # Cancel all active workflows
    for workflow_id in list(self.active_workflows.keys()):
        await self.cancel_workflow(workflow_id)
    
    # Final learning cycle
    if self.learning_history:
        logger.info("Final learning summary", 
                   total_workflows=len(self.learning_history),
                   avg_performance=sum(lm.performance_score for lm in self.learning_history) / len(self.learning_history))
    
    logger.info("Orchestration Agent shutdown complete")
```

# Global instance for singleton pattern

_orchestration_instance = None

def get_orchestration_agent() -> OrchestrationAgent:
“”“Get singleton instance of orchestration agent”””
global _orchestration_instance
if _orchestration_instance is None:
_orchestration_instance = OrchestrationAgent()
return _orchestration_instance