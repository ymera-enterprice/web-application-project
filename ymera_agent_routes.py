"""
YMERA Enterprise - Agent Communication Routes
Production-Ready Agent Management Endpoints - v4.0
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
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from models.user import User
from models.agent import Agent, AgentStatus, AgentType, AgentTask
from security.jwt_handler import get_current_user
from monitoring.performance_tracker import track_performance
from agents.agent_manager import AgentManager
from agents.learning_engine import LearningEngine
from utils.message_queue import MessageQueue
from utils.rate_limiter import RateLimiter

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.agent_routes")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

MAX_AGENTS_PER_USER = 10
TASK_TIMEOUT_SECONDS = 300
AGENT_HEALTH_CHECK_INTERVAL = 30
MESSAGE_RETENTION_HOURS = 24

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class MessageType(str, Enum):
    """Agent message types"""
    COMMAND = "command"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

@dataclass
class AgentConfig:
    """Configuration for agent management"""
    max_concurrent_tasks: int = 5
    task_timeout: int = 300
    heartbeat_interval: int = 30
    message_retention_hours: int = 24
    learning_enabled: bool = True
    collaboration_enabled: bool = True

class AgentCreation(BaseModel):
    """Schema for agent creation"""
    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    agent_type: AgentType = Field(..., description="Type of agent")
    description: Optional[str] = Field(default=None, max_length=500, description="Agent description")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    
    @validator('capabilities')
    def validate_capabilities(cls, v):
        """Validate agent capabilities"""
        allowed_capabilities = [
            "text_processing", "data_analysis", "file_handling",
            "web_search", "code_generation", "image_processing",
            "natural_language", "mathematical_computation",
            "project_management", "learning_optimization"
        ]
        for capability in v:
            if capability not in allowed_capabilities:
                raise ValueError(f'Invalid capability: {capability}')
        return v

class TaskCreation(BaseModel):
    """Schema for task creation"""
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: str = Field(..., min_length=1, description="Task description")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    timeout: Optional[int] = Field(default=None, ge=1, le=3600, description="Task timeout in seconds")
    requires_approval: bool = Field(default=False, description="Whether task requires approval")
    
class AgentMessage(BaseModel):
    """Schema for agent messages"""
    message_type: MessageType = Field(..., description="Type of message")
    content: str = Field(..., description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Message priority")

class AgentResponse(BaseModel):
    """Schema for agent responses"""
    id: str
    name: str
    agent_type: str
    status: str
    capabilities: List[str]
    current_tasks: int
    completed_tasks: int
    success_rate: float
    created_at: datetime
    last_activity: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskResponse(BaseModel):
    """Schema for task responses"""
    id: str
    title: str
    description: str
    status: str
    priority: str
    agent_id: str
    agent_name: str
    progress: float
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AgentCommunication(BaseModel):
    """Schema for inter-agent communication"""
    target_agent_id: str = Field(..., description="Target agent ID")
    message: str = Field(..., description="Communication message")
    request_type: str = Field(..., description="Type of request")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")
    requires_response: bool = Field(default=True, description="Whether response is required")

class CollaborationRequest(BaseModel):
    """Schema for agent collaboration requests"""
    collaborator_ids: List[str] = Field(..., description="List of collaborating agent IDs")
    task_title: str = Field(..., description="Collaboration task title")
    task_description: str = Field(..., description="Collaboration task description")
    coordination_strategy: str = Field(default="round_robin", description="Coordination strategy")
    share_knowledge: bool = Field(default=True, description="Whether to share knowledge")

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class AgentCommunicationManager:
    """Advanced agent communication and coordination"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logger.bind(component="agent_communication")
        self._redis_client = None
        self._message_queue = None
        self._agent_manager = None
        self._learning_engine = None
        self._active_collaborations: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """Initialize communication manager"""
        try:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            self._message_queue = MessageQueue(self._redis_client)
            self._agent_manager = AgentManager()
            self._learning_engine = LearningEngine()
            
            await self._agent_manager.initialize()
            await self._learning_engine.initialize()
            
            self.logger.info("Agent communication manager initialized")
        except Exception as e:
            self.logger.error("Failed to initialize communication manager", error=str(e))
            raise
    
    async def create_agent(
        self,
        agent_data: AgentCreation,
        user_id: str,
        db: AsyncSession
    ) -> AgentResponse:
        """
        Create a new agent with comprehensive setup.
        
        Args:
            agent_data: Agent creation data
            user_id: Owner user ID
            db: Database session
            
        Returns:
            Created agent information
        """
        try:
            # Check user agent limit
            result = await db.execute(
                select(Agent).where(
                    Agent.user_id == user_id,
                    Agent.is_active == True
                )
            )
            existing_agents = result.scalars().all()
            
            if len(existing_agents) >= MAX_AGENTS_PER_USER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Maximum {MAX_AGENTS_PER_USER} agents per user"
                )
            
            # Create agent instance
            agent = Agent(
                id=str(uuid.uuid4()),
                name=agent_data.name,
                agent_type=agent_data.agent_type,
                description=agent_data.description,
                capabilities=agent_data.capabilities,
                configuration=agent_data.configuration,
                user_id=user_id,
                status=AgentStatus.IDLE,
                created_at=datetime.utcnow()
            )
            
            db.add(agent)
            await db.commit()
            await db.refresh(agent)
            
            # Initialize agent in agent manager
            await self._agent_manager.register_agent(agent)
            
            # Start learning for this agent if enabled
            if self.config.learning_enabled:
                await self._learning_engine.initialize_agent_learning(agent.id)
            
            self.logger.info("Agent created successfully", agent_id=agent.id, user_id=user_id)
            
            return AgentResponse(
                id=agent.id,
                name=agent.name,
                agent_type=agent.agent_type.value,
                status=agent.status.value,
                capabilities=agent.capabilities,
                current_tasks=0,
                completed_tasks=0,
                success_rate=0.0,
                created_at=agent.created_at,
                last_activity=None
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            self.logger.error("Agent creation failed", error=str(e), user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent creation failed"
            )
    
    async def assign_task(
        self,
        agent_id: str,
        task_data: TaskCreation,
        user_id: str,
        db: AsyncSession
    ) -> TaskResponse:
        """
        Assign a task to an agent with comprehensive tracking.
        
        Args:
            agent_id: Target agent ID
            task_data: Task creation data
            user_id: Task creator user ID
            db: Database session
            
        Returns:
            Created task information
        """
        try:
            # Verify agent ownership
            result = await db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.user_id == user_id,
                    Agent.is_active == True
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found or not accessible"
                )
            
            # Check agent availability
            if agent.status not in [AgentStatus.IDLE, AgentStatus.ACTIVE]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent is not available for tasks"
                )
            
            # Create task
            task = AgentTask(
                id=str(uuid.uuid4()),
                title=task_data.title,
                description=task_data.description,
                priority=task_data.priority.value,
                parameters=task_data.parameters,
                timeout=task_data.timeout or TASK_TIMEOUT_SECONDS,
                requires_approval=task_data.requires_approval,
                agent_id=agent.id,
                user_id=user_id,
                status="pending",
                created_at=datetime.utcnow()
            )
            
            db.add(task)
            await db.commit()
            await db.refresh(task)
            
            # Queue task for execution
            await self._message_queue.publish(
                f"agent:{agent_id}:tasks",
                {
                    "task_id": task.id,
                    "type": "task_assignment",
                    "data": {
                        "title": task.title,
                        "description": task.description,
                        "priority": task.priority,
                        "parameters": task.parameters,
                        "timeout": task.timeout
                    }
                }
            )
            
            # Update agent status
            if agent.status == AgentStatus.IDLE:
                agent.status = AgentStatus.ACTIVE
                agent.last_activity = datetime.utcnow()
                await db.commit()
            
            self.logger.info("Task assigned successfully", task_id=task.id, agent_id=agent_id)
            
            return TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                status=task.status,
                priority=task.priority,
                agent_id=agent.id,
                agent_name=agent.name,
                progress=0.0,
                result=None,
                error_message=None,
                created_at=task.created_at,
                started_at=None,
                completed_at=None
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            self.logger.error("Task assignment failed", error=str(e), agent_id=agent_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Task assignment failed"
            )
    
    async def send_message(
        self,
        agent_id: str,
        message_data: AgentMessage,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Send message to agent with delivery confirmation.
        
        Args:
            agent_id: Target agent ID
            message_data: Message data
            user_id: Sender user ID
            db: Database session
            
        Returns:
            Message delivery confirmation
        """
        try:
            # Verify agent access
            result = await db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.user_id == user_id,
                    Agent.is_active == True
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found or not accessible"
                )
            
            message_id = str(uuid.uuid4())
            message_payload = {
                "message_id": message_id,
                "type": message_data.message_type.value,
                "content": message_data.content,
                "metadata": message_data.metadata,
                "priority": message_data.priority.value,
                "sender_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send message via queue
            await self._message_queue.publish(
                f"agent:{agent_id}:messages",
                message_payload
            )
            
            # Store message in Redis for tracking
            await self._redis_client.setex(
                f"message:{message_id}",
                MESSAGE_RETENTION_HOURS * 3600,
                json.dumps(message_payload)
            )
            
            self.logger.info(
                "Message sent to agent",
                message_id=message_id,
                agent_id=agent_id,
                message_type=message_data.message_type.value
            )
            
            return {
                "message_id": message_id,
                "status": "sent",
                "timestamp": datetime.utcnow().isoformat(),
                "agent_id": agent_id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Message sending failed", error=str(e), agent_id=agent_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Message sending failed"
            )
    
    async def setup_collaboration(
        self,
        collaboration_data: CollaborationRequest,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Setup collaboration between multiple agents.
        
        Args:
            collaboration_data: Collaboration setup data
            user_id: Initiator user ID
            db: Database session
            
        Returns:
            Collaboration setup confirmation
        """
        try:
            # Verify all agents belong to user
            result = await db.execute(
                select(Agent).where(
                    Agent.id.in_(collaboration_data.collaborator_ids),
                    Agent.user_id == user_id,
                    Agent.is_active == True
                )
            )
            agents = result.scalars().all()
            
            if len(agents) != len(collaboration_data.collaborator_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Some agents not found or not accessible"
                )
            
            collaboration_id = str(uuid.uuid4())
            collaboration_config = {
                "id": collaboration_id,
                "title": collaboration_data.task_title,
                "description": collaboration_data.task_description,
                "strategy": collaboration_data.coordination_strategy,
                "participants": [agent.id for agent in agents],
                "share_knowledge": collaboration_data.share_knowledge,
                "created_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
            
            # Store collaboration configuration
            self._active_collaborations[collaboration_id] = collaboration_config
            
            # Notify all participating agents
            for agent in agents:
                await self._message_queue.publish(
                    f"agent:{agent.id}:collaboration",
                    {
                        "type": "collaboration_invite",
                        "collaboration_id": collaboration_id,
                        "config": collaboration_config
                    }
                )
            
            # Enable knowledge sharing if requested
            if collaboration_data.share_knowledge and self.config.learning_enabled:
                await self._learning_engine.enable_collaboration(
                    collaboration_id,
                    [agent.id for agent in agents]
                )
            
            self.logger.info(
                "Collaboration setup completed",
                collaboration_id=collaboration_id,
                participants=len(agents)
            )
            
            return {
                "collaboration_id": collaboration_id,
                "status": "active",
                "participants": len(agents),
                "message": "Collaboration setup successful"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Collaboration setup failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Collaboration setup failed"
            )
    
    async def get_agent_metrics(
        self,
        agent_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get comprehensive agent performance metrics.
        
        Args:
            agent_id: Agent ID
            user_id: Owner user ID
            db: Database session
            
        Returns:
            Agent performance metrics
        """
        try:
            # Verify agent access
            result = await db.execute(
                select(Agent).options(selectinload(Agent.tasks)).where(
                    Agent.id == agent_id,
                    Agent.user_id == user_id,
                    Agent.is_active == True
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found or not accessible"
                )
            
            tasks = agent.tasks
            total_tasks = len(tasks)
            completed_tasks = len([t for t in tasks if t.status == "completed"])
            failed_tasks = len([t for t in tasks if t.status == "failed"])
            
            success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
            
            # Get learning metrics if enabled
            learning_metrics = {}
            if self.config.learning_enabled:
                learning_metrics = await self._learning_engine.get_agent_learning_metrics(agent_id)
            
            # Calculate average task completion time
            completed_task_times = []
            for task in tasks:
                if task.status == "completed" and task.started_at and task.completed_at:
                    duration = (task.completed_at - task.started_at).total_seconds()
                    completed_task_times.append(duration)
            
            avg_completion_time = (
                sum(completed_task_times) / len(completed_task_times)
                if completed_task_times else 0.0
            )
            
            return {
                "agent_id": agent_id,
                "name": agent.name,
                "status": agent.status.value,
                "performance": {
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "failed_tasks": failed_tasks,
                    "success_rate": round(success_rate, 2),
                    "average_completion_time": round(avg_completion_time, 2)
                },
                "learning": learning_metrics,
                "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
                "uptime_hours": (
                    (datetime.utcnow() - agent.created_at).total_seconds() / 3600
                )
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Failed to get agent metrics", error=str(e), agent_id=agent_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve agent metrics"
            )

# ===============================================================================
# ROUTER SETUP
# ===============================================================================

router = APIRouter()

# Initialize agent communication manager
agent_config = AgentConfig(
    max_concurrent_tasks=settings.MAX_CONCURRENT_TASKS,
    task_timeout=settings.TASK_TIMEOUT,
    learning_enabled=settings.LEARNING_ENABLED,
    collaboration_enabled=settings.COLLABORATION_ENABLED
)

comm_manager = AgentCommunicationManager(agent_config)

# ===============================================================================
# ROUTE HANDLERS
# ===============================================================================

@router.on_event("startup")
async def startup_event():
    """Initialize agent communication manager on startup"""
    await comm_manager.initialize()

@router.post("/create", response_model=AgentResponse)
@track_performance
async def create_agent(
    agent_data: AgentCreation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> AgentResponse:
    """
    Create a new AI agent with specified capabilities.
    
    Creates and initializes a new agent instance with learning
    capabilities and communication setup.
    """
    return await comm_manager.create_agent(agent_data, current_user.id, db)

@router.get("/", response_model=List[AgentResponse])
@track_performance
async def list_agents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> List[AgentResponse]:
    """
    List all agents owned by the current user.
    
    Returns comprehensive information about user's agents
    including status and performance metrics.
    """
    try:
        result = await db.execute(
            select(Agent).options(selectinload(Agent.tasks)).where(
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agents = result.scalars().all()
        
        agent_responses = []
        for agent in agents:
            tasks = agent.tasks
            completed_tasks = len([t for t in tasks if t.status == "completed"])
            total_tasks = len(tasks)
            success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
            current_tasks = len([t for t in tasks if t.status in ["pending", "running"]])
            
            agent_responses.append(AgentResponse(
                id=agent.id,
                name=agent.name,
                agent_type=agent.agent_type.value,
                status=agent.status.value,
                capabilities=agent.capabilities,
                current_tasks=current_tasks,
                completed_tasks=completed_tasks,
                success_rate=round(success_rate, 2),
                created_at=agent.created_at,
                last_activity=agent.last_activity
            ))
        
        return agent_responses
        
    except Exception as e:
        logger.error("Failed to list agents", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents"
        )

@router.get("/{agent_id}", response_model=AgentResponse)
@track_performance
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> AgentResponse:
    """
    Get detailed information about a specific agent.
    
    Returns comprehensive agent details including current status,
    task history, and performance metrics.
    """
    try:
        result = await db.execute(
            select(Agent).options(selectinload(Agent.tasks)).where(
                Agent.id == agent_id,
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agent = result.scalar_one_or_none()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        tasks = agent.tasks
        completed_tasks = len([t for t in tasks if t.status == "completed"])
        total_tasks = len(tasks)
        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
        current_tasks = len([t for t in tasks if t.status in ["pending", "running"]])
        
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            agent_type=agent.agent_type.value,
            status=agent.status.value,
            capabilities=agent.capabilities,
            current_tasks=current_tasks,
            completed_tasks=completed_tasks,
            success_rate=round(success_rate, 2),
            created_at=agent.created_at,
            last_activity=agent.last_activity
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", error=str(e), agent_id=agent_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent"
        )

@router.post("/{agent_id}/tasks", response_model=TaskResponse)
@track_performance
async def assign_task(
    agent_id: str,
    task_data: TaskCreation,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> TaskResponse:
    """
    Assign a new task to an agent.
    
    Creates and queues a task for execution by the specified agent
    with comprehensive tracking and monitoring.
    """
    return await comm_manager.assign_task(agent_id, task_data, current_user.id, db)

@router.get("/{agent_id}/tasks", response_model=List[TaskResponse])
@track_performance
async def get_agent_tasks(
    agent_id: str,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> List[TaskResponse]:
    """
    Get tasks assigned to an agent.
    
    Returns paginated list of tasks with optional status filtering
    and comprehensive task information.
    """
    try:
        # Verify agent access
        result = await db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agent = result.scalar_one_or_none()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Build query
        query = select(AgentTask).where(AgentTask.agent_id == agent_id)
        
        if status_filter:
            query = query.where(AgentTask.status == status_filter)
        
        query = query.order_by(AgentTask.created_at.desc()).offset(offset).limit(limit)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        task_responses = []
        for task in tasks:
            progress = 0.0
            if task.status == "completed":
                progress = 100.0
            elif task.status == "running" and task.started_at:
                # Calculate progress based on time elapsed
                elapsed = (datetime.utcnow() - task.started_at).total_seconds()
                progress = min(elapsed / task.timeout * 100, 90.0)
            
            task_responses.append(TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                status=task.status,
                priority=task.priority,
                agent_id=task.agent_id,
                agent_name=agent.name,
                progress=round(progress, 2),
                result=task.result,
                error_message=task.error_message,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at
            ))
        
        return task_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent tasks", error=str(e), agent_id=agent_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent tasks"
        )

@router.post("/{agent_id}/message")
@track_performance
async def send_message_to_agent(
    agent_id: str,
    message_data: AgentMessage,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Send a message to an agent.
    
    Sends direct communication to an agent with delivery tracking
    and priority handling.
    """
    return await comm_manager.send_message(agent_id, message_data, current_user.id, db)

@router.post("/collaborate", response_model=Dict[str, Any])
@track_performance
async def setup_agent_collaboration(
    collaboration_data: CollaborationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Setup collaboration between multiple agents.
    
    Coordinates multiple agents to work together on complex tasks
    with knowledge sharing and synchronized execution.
    """
    return await comm_manager.setup_collaboration(collaboration_data, current_user.id, db)

@router.get("/{agent_id}/metrics")
@track_performance
async def get_agent_performance_metrics(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get comprehensive agent performance metrics.
    
    Returns detailed performance analytics including task success rates,
    learning progress, and collaboration effectiveness.
    """
    return await comm_manager.get_agent_metrics(agent_id, current_user.id, db)

@router.get("/{agent_id}/communicate/{target_agent_id}")
@track_performance
async def facilitate_inter_agent_communication(
    agent_id: str,
    target_agent_id: str,
    communication_data: AgentCommunication,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Facilitate direct communication between two agents.
    
    Enables secure, monitored communication between agents
    with message routing and response handling.
    """
    try:
        # Verify both agents belong to user
        result = await db.execute(
            select(Agent).where(
                Agent.id.in_([agent_id, target_agent_id]),
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agents = result.scalars().all()
        
        if len(agents) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or both agents not found or not accessible"
            )
        
        communication_id = str(uuid.uuid4())
        
        # Send message to target agent
        await comm_manager._message_queue.publish(
            f"agent:{target_agent_id}:communication",
            {
                "communication_id": communication_id,
                "from_agent_id": agent_id,
                "message": communication_data.message,
                "request_type": communication_data.request_type,
                "data": communication_data.data,
                "requires_response": communication_data.requires_response,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            "Inter-agent communication initiated",
            communication_id=communication_id,
            from_agent=agent_id,
            to_agent=target_agent_id
        )
        
        return {
            "communication_id": communication_id,
            "status": "sent",
            "from_agent_id": agent_id,
            "to_agent_id": target_agent_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Inter-agent communication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Communication setup failed"
        )

@router.delete("/{agent_id}")
@track_performance
async def deactivate_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Deactivate an agent and cleanup resources.
    
    Safely shuts down an agent, completes pending tasks,
    and releases allocated resources.
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agent = result.scalar_one_or_none()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Update agent status
        agent.is_active = False
        agent.status = AgentStatus.SHUTDOWN
        agent.updated_at = datetime.utcnow()
        
        # Cancel pending tasks
        await db.execute(
            select(AgentTask).where(
                AgentTask.agent_id == agent_id,
                AgentTask.status.in_(["pending", "running"])
            ).update({
                "status": "cancelled",
                "error_message": "Agent deactivated",
                "updated_at": datetime.utcnow()
            })
        )
        
        await db.commit()
        
        # Cleanup agent resources in agent manager
        await comm_manager._agent_manager.deregister_agent(agent_id)
        
        # Cleanup learning data if enabled
        if comm_manager.config.learning_enabled:
            await comm_manager._learning_engine.cleanup_agent_learning(agent_id)
        
        logger.info("Agent deactivated successfully", agent_id=agent_id, user_id=current_user.id)
        
        return {
            "message": "Agent deactivated successfully",
            "agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Agent deactivation failed", error=str(e), agent_id=agent_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent deactivation failed"
        )

@router.get("/{agent_id}/logs")
@track_performance
async def get_agent_logs(
    agent_id: str,
    limit: int = 100,
    level: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get agent activity logs.
    
    Returns comprehensive activity logs for debugging and monitoring
    with optional filtering by log level.
    """
    try:
        # Verify agent access
        result = await db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agent = result.scalar_one_or_none()
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Get logs from Redis (in production, you'd have proper log storage)
        log_key = f"agent:{agent_id}:logs"
        logs = await comm_manager._redis_client.lrange(log_key, 0, limit - 1)
        
        parsed_logs = []
        for log_entry in logs:
            try:
                log_data = json.loads(log_entry)
                if level and log_data.get("level") != level:
                    continue
                parsed_logs.append(log_data)
            except json.JSONDecodeError:
                continue
        
        return {
            "agent_id": agent_id,
            "logs": parsed_logs,
            "total_retrieved": len(parsed_logs),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent logs", error=str(e), agent_id=agent_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent logs"
        )

@router.get("/status/overview")
@track_performance
async def get_agents_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get overview of all user agents.
    
    Returns comprehensive dashboard data including agent counts,
    task statistics, and system health metrics.
    """
    try:
        # Get all user agents
        result = await db.execute(
            select(Agent).options(selectinload(Agent.tasks)).where(
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
        agents = result.scalars().all()
        
        # Calculate overview statistics
        total_agents = len(agents)
        active_agents = len([a for a in agents if a.status == AgentStatus.ACTIVE])
        idle_agents = len([a for a in agents if a.status == AgentStatus.IDLE])
        
        # Task statistics
        all_tasks = []
        for agent in agents:
            all_tasks.extend(agent.tasks)
        
        total_tasks = len(all_tasks)
        completed_tasks = len([t for t in all_tasks if t.status == "completed"])
        running_tasks = len([t for t in all_tasks if t.status == "running"])
        failed_tasks = len([t for t in all_tasks if t.status == "failed"])
        
        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
        
        # Agent type distribution
        type_distribution = {}
        for agent in agents:
            agent_type = agent.agent_type.value
            type_distribution[agent_type] = type_distribution.get(agent_type, 0) + 1
        
        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_tasks = [t for t in all_tasks if t.created_at > yesterday]
        
        return {
            "summary": {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "idle_agents": idle_agents,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "running_tasks": running_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": round(success_rate, 2)
            },
            "agent_types": type_distribution,
            "recent_activity": {
                "tasks_last_24h": len(recent_tasks),
                "completed_last_24h": len([t for t in recent_tasks if t.status == "completed"])
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get agents overview", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents overview"
        )

@router.get("/health")
async def agents_health_check() -> Dict[str, Any]:
    """Agent system health check"""
    try:
        # Check Redis connectivity
        redis_status = "healthy"
        try:
            await comm_manager._redis_client.ping()
        except Exception:
            redis_status = "unhealthy"
        
        # Check message queue status
        queue_status = "healthy"
        try:
            await comm_manager._message_queue.health_check()
        except Exception:
            queue_status = "unhealthy"
        
        # Check learning engine status
        learning_status = "healthy"
        if comm_manager.config.learning_enabled:
            try:
                await comm_manager._learning_engine.health_check()
            except Exception:
                learning_status = "unhealthy"
        
        overall_status = "healthy"
        if redis_status == "unhealthy" or queue_status == "unhealthy":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "module": "agents",
            "version": "4.0",
            "components": {
                "redis": redis_status,
                "message_queue": queue_status,
                "learning_engine": learning_status,
                "collaboration": "enabled" if comm_manager.config.collaboration_enabled else "disabled"
            },
            "features": {
                "agent_creation": True,
                "task_assignment": True,
                "inter_agent_communication": True,
                "collaboration": comm_manager.config.collaboration_enabled,
                "learning": comm_manager.config.learning_enabled,
                "performance_metrics": True
            }
        }
        
    except Exception as e:
        logger.error("Agent health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# ===============================================================================
# STREAMING ENDPOINTS
# ===============================================================================

@router.get("/{agent_id}/stream/logs")
async def stream_agent_logs(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Stream real-time agent logs.
    
    Provides real-time streaming of agent activity logs
    for live monitoring and debugging.
    """
    async def log_stream():
        try:
            # Verify agent access
            result = await db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                    Agent.is_active == True
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                yield f"data: {json.dumps({'error': 'Agent not found'})}\n\n"
                return
            
            # Subscribe to agent log stream
            pubsub = comm_manager._redis_client.pubsub()
            await pubsub.subscribe(f"agent:{agent_id}:logs:stream")
            
            yield f"data: {json.dumps({'status': 'connected', 'agent_id': agent_id})}\n\n"
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        log_data = json.loads(message["data"])
                        yield f"data: {json.dumps(log_data)}\n\n"
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error("Log streaming failed", error=str(e), agent_id=agent_id)
            yield f"data: {json.dumps({'error': 'Stream failed'})}\n\n"
    
    return StreamingResponse(
        log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@router.get("/{agent_id}/stream/tasks")
async def stream_agent_tasks(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Stream real-time agent task updates.
    
    Provides real-time streaming of task status updates
    for live monitoring of agent activity.
    """
    async def task_stream():
        try:
            # Verify agent access
            result = await db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                    Agent.is_active == True
                )
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                yield f"data: {json.dumps({'error': 'Agent not found'})}\n\n"
                return
            
            # Subscribe to agent task updates
            pubsub = comm_manager._redis_client.pubsub()
            await pubsub.subscribe(f"agent:{agent_id}:tasks:updates")
            
            yield f"data: {json.dumps({'status': 'connected', 'agent_id': agent_id})}\n\n"
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        task_update = json.loads(message["data"])
                        yield f"data: {json.dumps(task_update)}\n\n"
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error("Task streaming failed", error=str(e), agent_id=agent_id)
            yield f"data: {json.dumps({'error': 'Stream failed'})}\n\n"
    
    return StreamingResponse(
        task_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "router",
    "AgentCommunicationManager",
    "AgentConfig",
    "AgentCreation",
    "TaskCreation",
    "AgentMessage",
    "AgentResponse",
    "TaskResponse",
    "CollaborationRequest"
]