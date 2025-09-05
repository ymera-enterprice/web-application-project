"""
YMERA Enterprise Multi-Agent System - Agent Management API Routes
Production-Ready FastAPI Routes with Comprehensive Agent Management
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Path, Body
from fastapi.security import HTTPBearer
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
from uuid import UUID, uuid4
import asyncio
import json
from enum import Enum
import logging

# Core system imports
from ymera_core.config import ConfigManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.security.auth_manager import AuthManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.exceptions import YMERAException, AgentException, ValidationException

# Agent system imports
from ymera_agents.orchestrator import AgentOrchestrator
from ymera_agents.registry import AgentRegistry
from ymera_agents.lifecycle_manager import AgentLifecycleManager
from ymera_agents.communication.message_bus import MessageBus
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.learning.knowledge_base import KnowledgeBase

# Service imports
from ymera_services.ai.multi_llm_manager import MultiLLMManager

# Initialize router
router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("ymera.agents.api")

# Enums
class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"

class AgentType(str, Enum):
    CORE = "core"
    SPECIALIZED = "specialized"
    CUSTOM = "custom"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class OrchestrationStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"
    LEARNING_OPTIMIZED = "learning_optimized"

# Request/Response Models
class AgentConfigModel(BaseModel):
    name: str = Field(..., description="Agent name", min_length=1, max_length=100)
    type: AgentType = Field(..., description="Agent type")
    description: Optional[str] = Field(None, description="Agent description", max_length=500)
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    resource_limits: Dict[str, int] = Field(default_factory=dict, description="Resource limits")
    learning_enabled: bool = Field(True, description="Enable learning for this agent")
    auto_scale: bool = Field(False, description="Enable auto-scaling")

class AgentUpdateModel(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    capabilities: Optional[List[str]] = None
    configuration: Optional[Dict[str, Any]] = None
    resource_limits: Optional[Dict[str, int]] = None
    learning_enabled: Optional[bool] = None
    auto_scale: Optional[bool] = None

class TaskModel(BaseModel):
    task_id: Optional[str] = Field(None, description="Task identifier")
    agent_id: Optional[str] = Field(None, description="Target agent ID")
    task_type: str = Field(..., description="Task type", min_length=1)
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Task priority")
    payload: Dict[str, Any] = Field(..., description="Task payload")
    context: Optional[Dict[str, Any]] = Field(None, description="Task context")
    timeout: Optional[int] = Field(300, description="Task timeout in seconds")
    retry_count: int = Field(3, description="Maximum retry attempts")
    requires_learning: bool = Field(False, description="Whether task results should be learned")

class OrchestrationRequestModel(BaseModel):
    workflow_id: Optional[str] = Field(None, description="Workflow identifier")
    strategy: OrchestrationStrategy = Field(OrchestrationStrategy.ADAPTIVE, description="Orchestration strategy")
    tasks: List[TaskModel] = Field(..., description="Tasks to orchestrate")
    dependencies: Optional[Dict[str, List[str]]] = Field(None, description="Task dependencies")
    timeout: Optional[int] = Field(1800, description="Workflow timeout in seconds")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Workflow priority")
    learning_context: Optional[Dict[str, Any]] = Field(None, description="Learning context for optimization")

class LearningConfigModel(BaseModel):
    learning_rate: float = Field(0.01, ge=0.001, le=1.0, description="Learning rate")
    exploration_factor: float = Field(0.1, ge=0.0, le=1.0, description="Exploration vs exploitation")
    memory_size: int = Field(10000, ge=100, le=100000, description="Memory buffer size")
    batch_size: int = Field(32, ge=1, le=256, description="Training batch size")
    update_frequency: int = Field(100, ge=1, le=10000, description="Update frequency")
    enable_transfer_learning: bool = Field(True, description="Enable transfer learning")

class AgentMetricsModel(BaseModel):
    tasks_completed: int
    tasks_failed: int
    average_response_time: float
    success_rate: float
    cpu_usage: float
    memory_usage: float
    uptime: float
    learning_score: Optional[float] = None

class AgentResponseModel(BaseModel):
    agent_id: str
    name: str
    type: AgentType
    status: AgentStatus
    description: Optional[str] = None
    capabilities: List[str]
    configuration: Dict[str, Any]
    resource_limits: Dict[str, int]
    learning_enabled: bool
    auto_scale: bool
    created_at: datetime
    updated_at: datetime
    last_active: Optional[datetime] = None
    metrics: Optional[AgentMetricsModel] = None

class TaskResponseModel(BaseModel):
    task_id: str
    workflow_id: Optional[str] = None
    agent_id: str
    task_type: str
    status: str
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    retry_count: int

class OrchestrationResponseModel(BaseModel):
    workflow_id: str
    strategy: OrchestrationStrategy
    status: str
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tasks: List[TaskResponseModel]
    execution_summary: Dict[str, Any]

class AgentListResponseModel(BaseModel):
    agents: List[AgentResponseModel]
    total_count: int
    page: int
    page_size: int
    has_next: bool

class LearningInsightsModel(BaseModel):
    agent_id: str
    learning_enabled: bool
    total_experiences: int
    successful_patterns: int
    optimization_score: float
    last_learning_update: Optional[datetime] = None
    knowledge_areas: List[str]
    improvement_suggestions: List[str]

# Dependency functions
async def get_current_user(token: str = Depends(security)):
    """Get current authenticated user"""
    # Implementation would depend on your auth system
    # This is a placeholder that should be replaced with actual auth logic
    return {"user_id": "system", "permissions": ["agent:read", "agent:write", "agent:admin"]}

async def verify_permissions(required_permission: str):
    """Verify user has required permissions"""
    def permission_checker(current_user: dict = Depends(get_current_user)):
        if required_permission not in current_user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_permission}"
            )
        return current_user
    return permission_checker

# Agent Management Endpoints

@router.get(
    "/",
    response_model=AgentListResponseModel,
    summary="List all agents",
    description="Retrieve a paginated list of all registered agents with their current status and metrics"
)
async def list_agents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[AgentStatus] = Query(None, description="Filter by agent status"),
    type_filter: Optional[AgentType] = Query(None, description="Filter by agent type"),
    search: Optional[str] = Query(None, description="Search in agent names/descriptions"),
    include_metrics: bool = Query(True, description="Include performance metrics"),
    registry: AgentRegistry = Depends(),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """List all registered agents with filtering and pagination"""
    try:
        # Get agents from registry with filters
        filters = {}
        if status_filter:
            filters['status'] = status_filter.value
        if type_filter:
            filters['type'] = type_filter.value
        if search:
            filters['search'] = search

        agents_data = await registry.list_agents(
            page=page,
            page_size=page_size,
            filters=filters,
            include_metrics=include_metrics
        )

        # Enhance with real-time status from orchestrator
        for agent in agents_data['agents']:
            try:
                real_time_status = await orchestrator.get_agent_status(agent['agent_id'])
                agent.update(real_time_status)
            except Exception as e:
                logger.warning(f"Failed to get real-time status for agent {agent['agent_id']}: {e}")

        return AgentListResponseModel(
            agents=[AgentResponseModel(**agent) for agent in agents_data['agents']],
            total_count=agents_data['total_count'],
            page=page,
            page_size=page_size,
            has_next=agents_data['has_next']
        )

    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agents: {str(e)}"
        )

@router.get(
    "/{agent_id}",
    response_model=AgentResponseModel,
    summary="Get agent details",
    description="Retrieve detailed information about a specific agent"
)
async def get_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    include_metrics: bool = Query(True, description="Include performance metrics"),
    registry: AgentRegistry = Depends(),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get detailed information about a specific agent"""
    try:
        # Get agent from registry
        agent_data = await registry.get_agent(agent_id, include_metrics=include_metrics)
        if not agent_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )

        # Get real-time status from orchestrator
        try:
            real_time_status = await orchestrator.get_agent_status(agent_id)
            agent_data.update(real_time_status)
        except Exception as e:
            logger.warning(f"Failed to get real-time status for agent {agent_id}: {e}")

        return AgentResponseModel(**agent_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent: {str(e)}"
        )

@router.post(
    "/",
    response_model=AgentResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create new agent",
    description="Create and register a new agent instance"
)
async def create_agent(
    agent_config: AgentConfigModel,
    background_tasks: BackgroundTasks,
    registry: AgentRegistry = Depends(),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    learning_engine: LearningEngine = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Create and register a new agent"""
    try:
        # Generate unique agent ID
        agent_id = str(uuid4())

        # Validate agent configuration
        await _validate_agent_config(agent_config, registry)

        # Create agent instance
        agent_data = {
            "agent_id": agent_id,
            "name": agent_config.name,
            "type": agent_config.type.value,
            "description": agent_config.description,
            "capabilities": agent_config.capabilities,
            "configuration": agent_config.configuration,
            "resource_limits": agent_config.resource_limits,
            "learning_enabled": agent_config.learning_enabled,
            "auto_scale": agent_config.auto_scale,
            "status": AgentStatus.INITIALIZING.value,
            "created_by": current_user["user_id"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Register agent
        await registry.register_agent_config(agent_data)

        # Initialize agent in background
        background_tasks.add_task(
            _initialize_agent_background,
            agent_id,
            agent_config,
            lifecycle_manager,
            learning_engine
        )

        # Return agent response
        agent_data["status"] = AgentStatus.INITIALIZING.value
        return AgentResponseModel(**agent_data)

    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent: {str(e)}"
        )

@router.put(
    "/{agent_id}",
    response_model=AgentResponseModel,
    summary="Update agent configuration",
    description="Update an existing agent's configuration and settings"
)
async def update_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    agent_update: AgentUpdateModel = Body(...),
    registry: AgentRegistry = Depends(),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Update agent configuration"""
    try:
        # Verify agent exists
        existing_agent = await registry.get_agent(agent_id)
        if not existing_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )

        # Prepare update data
        update_data = agent_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        update_data["updated_by"] = current_user["user_id"]

        # Update agent in registry
        updated_agent = await registry.update_agent(agent_id, update_data)

        # Notify orchestrator of configuration change
        await orchestrator.handle_agent_config_update(agent_id, update_data)

        return AgentResponseModel(**updated_agent)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {str(e)}"
        )

@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete agent",
    description="Permanently delete an agent and all its associated data"
)
async def delete_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    force: bool = Query(False, description="Force deletion even if agent is busy"),
    registry: AgentRegistry = Depends(),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    current_user: dict = Depends(verify_permissions("agent:admin"))
):
    """Delete an agent permanently"""
    try:
        # Verify agent exists
        agent = await registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )

        # Check if agent can be safely deleted
        if not force and agent.get('status') in [AgentStatus.BUSY.value, AgentStatus.ACTIVE.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent is currently busy. Use force=true to override"
            )

        # Shutdown agent gracefully
        await lifecycle_manager.shutdown_agent(agent_id)

        # Remove from registry
        await registry.unregister_agent(agent_id)

        logger.info(f"Agent {agent_id} deleted successfully by user {current_user['user_id']}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {str(e)}"
        )

# Agent Control Endpoints

@router.post(
    "/{agent_id}/start",
    summary="Start agent",
    description="Start a paused or stopped agent"
)
async def start_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Start or resume an agent"""
    try:
        result = await lifecycle_manager.start_agent(agent_id)
        return {"message": f"Agent {agent_id} started successfully", "result": result}

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}"
        )

@router.post(
    "/{agent_id}/pause",
    summary="Pause agent",
    description="Pause an active agent, completing current tasks"
)
async def pause_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    wait_for_completion: bool = Query(True, description="Wait for current tasks to complete"),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Pause an agent"""
    try:
        result = await lifecycle_manager.pause_agent(agent_id, wait_for_completion)
        return {"message": f"Agent {agent_id} paused successfully", "result": result}

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error pausing agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause agent: {str(e)}"
        )

@router.post(
    "/{agent_id}/restart",
    summary="Restart agent",
    description="Restart an agent with fresh state"
)
async def restart_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    preserve_memory: bool = Query(True, description="Preserve learning memory"),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Restart an agent"""
    try:
        result = await lifecycle_manager.restart_agent(agent_id, preserve_memory)
        return {"message": f"Agent {agent_id} restarted successfully", "result": result}

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error restarting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart agent: {str(e)}"
        )

# Task Management Endpoints

@router.post(
    "/{agent_id}/tasks",
    response_model=TaskResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Assign task to agent",
    description="Assign a new task to a specific agent"
)
async def assign_task_to_agent(
    agent_id: str = Path(..., description="Agent identifier"),
    task: TaskModel = Body(...),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Assign a task directly to a specific agent"""
    try:
        # Set agent_id in task
        task.agent_id = agent_id
        task.task_id = task.task_id or str(uuid4())

        # Submit task to agent via orchestrator
        result = await orchestrator.assign_task_to_agent(
            agent_id=agent_id,
            task=task.dict(),
            submitted_by=current_user["user_id"]
        )

        return TaskResponseModel(**result)

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning task to agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign task: {str(e)}"
        )

@router.get(
    "/{agent_id}/tasks",
    response_model=List[TaskResponseModel],
    summary="Get agent tasks",
    description="Retrieve all tasks assigned to a specific agent"
)
async def get_agent_tasks(
    agent_id: str = Path(..., description="Agent identifier"),
    status_filter: Optional[str] = Query(None, description="Filter by task status"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of tasks to return"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get all tasks for a specific agent"""
    try:
        tasks = await orchestrator.get_agent_tasks(
            agent_id=agent_id,
            status_filter=status_filter,
            limit=limit
        )

        return [TaskResponseModel(**task) for task in tasks]

    except Exception as e:
        logger.error(f"Error getting tasks for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent tasks: {str(e)}"
        )

@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponseModel,
    summary="Get task details",
    description="Retrieve detailed information about a specific task"
)
async def get_task(
    task_id: str = Path(..., description="Task identifier"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get detailed information about a specific task"""
    try:
        task = await orchestrator.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found"
            )

        return TaskResponseModel(**task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve task: {str(e)}"
        )

@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel task",
    description="Cancel a pending or running task"
)
async def cancel_task(
    task_id: str = Path(..., description="Task identifier"),
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Cancel a specific task"""
    try:
        await orchestrator.cancel_task(
            task_id=task_id,
            reason=reason,
            cancelled_by=current_user["user_id"]
        )

        logger.info(f"Task {task_id} cancelled by user {current_user['user_id']}")

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )

# Orchestration Endpoints

@router.post(
    "/orchestrate",
    response_model=OrchestrationResponseModel,
    status_code=status.HTTP_201_CREATED,
    summary="Orchestrate multi-agent workflow",
    description="Create and execute a complex multi-agent workflow"
)
async def orchestrate_workflow(
    orchestration_request: OrchestrationRequestModel,
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Orchestrate a complex multi-agent workflow"""
    try:
        # Generate workflow ID if not provided
        workflow_id = orchestration_request.workflow_id or str(uuid4())

        # Execute orchestration
        result = await orchestrator.orchestrate_workflow(
            workflow_id=workflow_id,
            strategy=orchestration_request.strategy.value,
            tasks=orchestration_request.tasks,
            dependencies=orchestration_request.dependencies,
            timeout=orchestration_request.timeout,
            priority=orchestration_request.priority.value,
            learning_context=orchestration_request.learning_context,
            submitted_by=current_user["user_id"]
        )

        return OrchestrationResponseModel(**result)

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error orchestrating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to orchestrate workflow: {str(e)}"
        )

@router.get(
    "/workflows/{workflow_id}",
    response_model=OrchestrationResponseModel,
    summary="Get workflow status",
    description="Retrieve the current status of a workflow"
)
async def get_workflow(
    workflow_id: str = Path(..., description="Workflow identifier"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get workflow status and details"""
    try:
        workflow = await orchestrator.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow with ID {workflow_id} not found"
            )

        return OrchestrationResponseModel(**workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve workflow: {str(e)}"
        )

@router.delete(
    "/workflows/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel workflow",
    description="Cancel a running workflow and all its tasks"
)
async def cancel_workflow(
    workflow_id: str = Path(..., description="Workflow identifier"),
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Cancel a workflow and all its tasks"""
    try:
        await orchestrator.cancel_workflow(
            workflow_id=workflow_id,
            reason=reason,
            cancelled_by=current_user["user_id"]
        )

        logger.info(f"Workflow {workflow_id} cancelled by user {current_user['user_id']}")

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel workflow: {str(e)}"
        )

# Learning and Optimization Endpoints

@router.get(
    "/{agent_id}/learning/insights",
    response_model=LearningInsightsModel,
    summary="Get agent learning insights",
    description="Retrieve learning insights and optimization recommendations for an agent"
)
async def get_agent_learning_insights(
    agent_id: str = Path(..., description="Agent identifier"),
    learning_engine: LearningEngine = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
): """Get learning insights for a specific agent"""
    try:
        insights = await learning_engine.get_agent_insights(agent_id)
        if not insights:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No learning insights found for agent {agent_id}"
            )

        return LearningInsightsModel(**insights)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting learning insights for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve learning insights: {str(e)}"
        )

@router.put(
    "/{agent_id}/learning/config",
    summary="Update agent learning configuration",
    description="Update learning parameters for a specific agent"
)
async def update_agent_learning_config(
    agent_id: str = Path(..., description="Agent identifier"),
    learning_config: LearningConfigModel = Body(...),
    learning_engine: LearningEngine = Depends(),
    registry: AgentRegistry = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Update learning configuration for an agent"""
    try:
        # Verify agent exists
        agent = await registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )

        # Update learning configuration
        result = await learning_engine.update_agent_config(
            agent_id=agent_id,
            config=learning_config.dict()
        )

        return {
            "message": f"Learning configuration updated for agent {agent_id}",
            "config": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating learning config for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update learning configuration: {str(e)}"
        )

@router.post(
    "/{agent_id}/learning/optimize",
    summary="Trigger learning optimization",
    description="Manually trigger learning optimization for an agent"
)
async def trigger_agent_optimization(
    agent_id: str = Path(..., description="Agent identifier"),
    optimization_context: Optional[Dict[str, Any]] = Body(None),
    learning_engine: LearningEngine = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Trigger manual learning optimization for an agent"""
    try:
        result = await learning_engine.optimize_agent(
            agent_id=agent_id,
            context=optimization_context,
            triggered_by=current_user["user_id"]
        )

        return {
            "message": f"Optimization triggered for agent {agent_id}",
            "optimization_id": result["optimization_id"],
            "estimated_completion": result["estimated_completion"]
        }

    except AgentException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error triggering optimization for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger optimization: {str(e)}"
        )

@router.post(
    "/learning/transfer",
    summary="Transfer learning between agents",
    description="Transfer learned knowledge from one agent to another"
)
async def transfer_learning(
    source_agent_id: str = Query(..., description="Source agent ID"),
    target_agent_id: str = Query(..., description="Target agent ID"),
    knowledge_areas: Optional[List[str]] = Body(None, description="Specific knowledge areas to transfer"),
    learning_engine: LearningEngine = Depends(),
    registry: AgentRegistry = Depends(),
    current_user: dict = Depends(verify_permissions("agent:admin"))
):
    """Transfer learning knowledge between agents"""
    try:
        # Verify both agents exist
        source_agent = await registry.get_agent(source_agent_id)
        target_agent = await registry.get_agent(target_agent_id)
        
        if not source_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source agent {source_agent_id} not found"
            )
        
        if not target_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target agent {target_agent_id} not found"
            )

        # Perform knowledge transfer
        result = await learning_engine.transfer_knowledge(
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            knowledge_areas=knowledge_areas,
            initiated_by=current_user["user_id"]
        )

        return {
            "message": f"Knowledge transfer initiated from {source_agent_id} to {target_agent_id}",
            "transfer_id": result["transfer_id"],
            "transferred_areas": result["transferred_areas"],
            "estimated_completion": result["estimated_completion"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transferring learning: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transfer learning: {str(e)}"
        )

# Metrics and Monitoring Endpoints

@router.get(
    "/{agent_id}/metrics",
    response_model=AgentMetricsModel,
    summary="Get agent metrics",
    description="Retrieve comprehensive performance metrics for an agent"
)
async def get_agent_metrics(
    agent_id: str = Path(..., description="Agent identifier"),
    time_range: Optional[str] = Query("1h", description="Time range (1h, 24h, 7d, 30d)"),
    include_detailed: bool = Query(False, description="Include detailed performance breakdown"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get comprehensive metrics for a specific agent"""
    try:
        metrics = await orchestrator.get_agent_metrics(
            agent_id=agent_id,
            time_range=time_range,
            include_detailed=include_detailed
        )

        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No metrics found for agent {agent_id}"
            )

        return AgentMetricsModel(**metrics)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metrics for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent metrics: {str(e)}"
        )

@router.get(
    "/metrics/system",
    summary="Get system-wide metrics",
    description="Retrieve system-wide agent performance and health metrics"
)
async def get_system_metrics(
    time_range: Optional[str] = Query("1h", description="Time range (1h, 24h, 7d, 30d)"),
    orchestrator: AgentOrchestrator = Depends(),
    registry: AgentRegistry = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get system-wide agent metrics and health status"""
    try:
        # Get overall system metrics
        system_metrics = await orchestrator.get_system_metrics(time_range)
        
        # Get agent registry statistics
        registry_stats = await registry.get_system_stats()

        return {
            "timestamp": datetime.utcnow(),
            "time_range": time_range,
            "system_health": system_metrics,
            "registry_stats": registry_stats,
            "total_agents": registry_stats["total_agents"],
            "active_agents": registry_stats["active_agents"],
            "system_load": system_metrics["system_load"],
            "average_response_time": system_metrics["average_response_time"],
            "total_tasks_processed": system_metrics["total_tasks_processed"],
            "error_rate": system_metrics["error_rate"]
        }

    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system metrics: {str(e)}"
        )

@router.get(
    "/{agent_id}/health",
    summary="Get agent health status",
    description="Retrieve detailed health and diagnostic information for an agent"
)
async def get_agent_health(
    agent_id: str = Path(..., description="Agent identifier"),
    include_diagnostics: bool = Query(True, description="Include diagnostic information"),
    orchestrator: AgentOrchestrator = Depends(),
    current_user: dict = Depends(verify_permissions("agent:read"))
):
    """Get health status and diagnostics for a specific agent"""
    try:
        health_status = await orchestrator.get_agent_health(
            agent_id=agent_id,
            include_diagnostics=include_diagnostics
        )

        if not health_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found or not monitored"
            )

        return health_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health status for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent health: {str(e)}"
        )

# Utility and Helper Functions

async def _validate_agent_config(config: AgentConfigModel, registry: AgentRegistry) -> None:
    """Validate agent configuration before creation"""
    # Check for duplicate names
    existing_agent = await registry.get_agent_by_name(config.name)
    if existing_agent:
        raise ValidationException(f"Agent with name '{config.name}' already exists")

    # Validate capabilities
    if not config.capabilities:
        raise ValidationException("Agent must have at least one capability")

    # Validate resource limits
    if config.resource_limits:
        for resource, limit in config.resource_limits.items():
            if limit <= 0:
                raise ValidationException(f"Resource limit for {resource} must be positive")

    # Validate configuration based on agent type
    if config.type == AgentType.SPECIALIZED:
        required_config_keys = ["specialization", "model_config"]
        missing_keys = [key for key in required_config_keys if key not in config.configuration]
        if missing_keys:
            raise ValidationException(f"Specialized agents require configuration keys: {missing_keys}")

async def _initialize_agent_background(
    agent_id: str,
    agent_config: AgentConfigModel,
    lifecycle_manager: AgentLifecycleManager,
    learning_engine: LearningEngine
) -> None:
    """Initialize agent in background task"""
    try:
        # Initialize agent instance
        await lifecycle_manager.initialize_agent(agent_id, agent_config.dict())

        # Set up learning if enabled
        if agent_config.learning_enabled:
            await learning_engine.setup_agent_learning(agent_id, {
                "learning_rate": 0.01,
                "exploration_factor": 0.1,
                "memory_size": 10000,
                "batch_size": 32,
                "update_frequency": 100
            })

        # Start the agent
        await lifecycle_manager.start_agent(agent_id)

        logger.info(f"Agent {agent_id} initialized and started successfully")

    except Exception as e:
        logger.error(f"Failed to initialize agent {agent_id}: {e}")
        # Update agent status to error
        try:
            await lifecycle_manager.set_agent_status(agent_id, AgentStatus.ERROR.value, str(e))
        except Exception as status_error:
            logger.error(f"Failed to update agent status after initialization error: {status_error}")

# WebSocket endpoints for real-time monitoring
@router.websocket("/{agent_id}/monitor")
async def monitor_agent_websocket(
    websocket,
    agent_id: str = Path(..., description="Agent identifier"),
    orchestrator: AgentOrchestrator = Depends()
):
    """WebSocket endpoint for real-time agent monitoring"""
    await websocket.accept()
    
    try:
        # Start monitoring stream
        async for update in orchestrator.stream_agent_updates(agent_id):
            await websocket.send_json({
                "timestamp": update["timestamp"].isoformat(),
                "agent_id": agent_id,
                "update_type": update["type"],
                "data": update["data"]
            })
    except Exception as e:
        logger.error(f"WebSocket monitoring error for agent {agent_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")

@router.websocket("/system/monitor")
async def monitor_system_websocket(
    websocket,
    orchestrator: AgentOrchestrator = Depends()
):
    """WebSocket endpoint for real-time system monitoring"""
    await websocket.accept()
    
    try:
        # Start system monitoring stream
        async for update in orchestrator.stream_system_updates():
            await websocket.send_json({
                "timestamp": update["timestamp"].isoformat(),
                "update_type": update["type"],
                "data": update["data"]
            })
    except Exception as e:
        logger.error(f"WebSocket system monitoring error: {e}")
        await websocket.close(code=1011, reason="Internal server error")

# Batch Operations Endpoints

@router.post(
    "/batch/create",
    summary="Batch create agents",
    description="Create multiple agents in a single operation"
)
async def batch_create_agents(
    agents: List[AgentConfigModel] = Body(..., description="List of agent configurations"),
    background_tasks: BackgroundTasks,
    registry: AgentRegistry = Depends(),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    learning_engine: LearningEngine = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Create multiple agents in batch"""
    try:
        if len(agents) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 agents can be created in a single batch"
            )

        created_agents = []
        failed_agents = []

        for agent_config in agents:
            try:
                # Validate configuration
                await _validate_agent_config(agent_config, registry)
                
                # Generate unique agent ID
                agent_id = str(uuid4())
                
                # Create agent data
                agent_data = {
                    "agent_id": agent_id,
                    "name": agent_config.name,
                    "type": agent_config.type.value,
                    "description": agent_config.description,
                    "capabilities": agent_config.capabilities,
                    "configuration": agent_config.configuration,
                    "resource_limits": agent_config.resource_limits,
                    "learning_enabled": agent_config.learning_enabled,
                    "auto_scale": agent_config.auto_scale,
                    "status": AgentStatus.INITIALIZING.value,
                    "created_by": current_user["user_id"],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }

                # Register agent
                await registry.register_agent_config(agent_data)
                
                # Schedule background initialization
                background_tasks.add_task(
                    _initialize_agent_background,
                    agent_id,
                    agent_config,
                    lifecycle_manager,
                    learning_engine
                )

                created_agents.append({
                    "agent_id": agent_id,
                    "name": agent_config.name,
                    "status": "initializing"
                })

            except Exception as e:
                failed_agents.append({
                    "name": agent_config.name,
                    "error": str(e)
                })

        return {
            "message": f"Batch operation completed. Created: {len(created_agents)}, Failed: {len(failed_agents)}",
            "created_agents": created_agents,
            "failed_agents": failed_agents
        }

    except Exception as e:
        logger.error(f"Error in batch agent creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agents in batch: {str(e)}"
        )

@router.post(
    "/batch/control",
    summary="Batch agent control",
    description="Control multiple agents simultaneously (start, pause, restart)"
)
async def batch_agent_control(
    agent_ids: List[str] = Body(..., description="List of agent IDs"),
    action: str = Body(..., description="Control action (start, pause, restart)"),
    parameters: Optional[Dict[str, Any]] = Body(None, description="Action parameters"),
    lifecycle_manager: AgentLifecycleManager = Depends(),
    current_user: dict = Depends(verify_permissions("agent:write"))
):
    """Control multiple agents in batch"""
    try:
        if len(agent_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 100 agents can be controlled in a single batch"
            )

        valid_actions = ["start", "pause", "restart"]
        if action not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action. Must be one of: {valid_actions}"
            )

        results = []
        
        # Execute batch operation
        for agent_id in agent_ids:
            try:
                if action == "start":
                    result = await lifecycle_manager.start_agent(agent_id)
                elif action == "pause":
                    wait_for_completion = parameters.get("wait_for_completion", True) if parameters else True
                    result = await lifecycle_manager.pause_agent(agent_id, wait_for_completion)
                elif action == "restart":
                    preserve_memory = parameters.get("preserve_memory", True) if parameters else True
                    result = await lifecycle_manager.restart_agent(agent_id, preserve_memory)

                results.append({
                    "agent_id": agent_id,
                    "status": "success",
                    "result": result
                })

            except Exception as e:
                results.append({
                    "agent_id": agent_id,
                    "status": "failed",
                    "error": str(e)
                })

        successful_count = len([r for r in results if r["status"] == "success"])
        failed_count = len(results) - successful_count

        return {
            "message": f"Batch {action} completed. Successful: {successful_count}, Failed: {failed_count}",
            "action": action,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in batch agent control: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute batch control: {str(e)}"
        )

# Error handlers
@router.exception_handler(YMERAException)
async def ymera_exception_handler(request, exc):
    """Handle YMERA-specific exceptions"""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"YMERA System Error: {str(exc)}"
    )

@router.exception_handler(AgentException)
async def agent_exception_handler(request, exc):
    """Handle agent-specific exceptions"""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Agent Error: {str(exc)}"
    )

@router.exception_handler(ValidationException)
async def validation_exception_handler(request, exc):
    """Handle validation exceptions"""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Validation Error: {str(exc)}"
    )

# Health check endpoint
@router.get(
    "/health",
    summary="API health check",
    description="Check the health of the agent management API"
)
async def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "YMERA Agent Management API",
        "version": "1.0.0"
    }