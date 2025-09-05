"""
YMERA Agent Management API
Enterprise-Grade RESTful API for Managing AI Agents
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import asyncio
import json
import uuid
from enum import Enum
from pydantic import BaseModel, Field, validator
import structlog

# Import your existing models and managers
from main import (
    Agent, Task, LearningRecord, 
    DatabaseManager, RedisManager, AIServiceManager,
    config, logger
)

# Pydantic Models for API
class AgentStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    TERMINATED = "terminated"

class AgentType(str, Enum):
    DEVELOPER = "developer"
    ANALYST = "analyst"
    TESTER = "tester"
    REVIEWER = "reviewer"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"

class AgentCapability(BaseModel):
    name: str
    level: int = Field(ge=1, le=10)
    description: Optional[str] = None

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AgentType
    capabilities: List[AgentCapability] = []
    metadata: Dict[str, Any] = {}
    
    @validator('name')
    def name_must_be_alphanumeric(cls, v):
        if not v.replace('-', '').replace('_', '').replace(' ', '').isalnum():
            raise ValueError('Name must be alphanumeric with optional hyphens, underscores, or spaces')
        return v

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[AgentStatus] = None
    capabilities: Optional[List[AgentCapability]] = None
    metadata: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    type: str
    status: str
    capabilities: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    learning_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    # Runtime statistics
    active_tasks: Optional[int] = None
    completed_tasks: Optional[int] = None
    success_rate: Optional[float] = None
    average_execution_time: Optional[float] = None

class AgentListResponse(BaseModel):
    agents: List[AgentResponse]
    total: int
    page: int
    page_size: int
    has_next: bool

class AgentPerformanceMetrics(BaseModel):
    agent_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float
    average_execution_time: float
    last_activity: Optional[datetime]
    learning_progress: Dict[str, Any]

class TaskAssignmentRequest(BaseModel):
    task_id: str
    priority_override: Optional[int] = Field(None, ge=1, le=10)
    expected_completion: Optional[datetime] = None

# Agent Management Service
class AgentManagementService:
    def __init__(self, db_manager: DatabaseManager, redis_manager: RedisManager, ai_manager: AIServiceManager):
        self.db_manager = db_manager
        self.redis = redis_manager
        self.ai_manager = ai_manager
        self.logger = structlog.get_logger()
    
    async def create_agent(self, agent_data: AgentCreateRequest) -> AgentResponse:
        """Create a new agent with validation and initialization"""
        async with self.db_manager.get_session() as session:
            # Check for duplicate names
            existing = await session.execute(
                select(Agent).where(Agent.name == agent_data.name)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Agent with name '{agent_data.name}' already exists"
                )
            
            # Create agent
            agent = Agent(
                id=str(uuid.uuid4()),
                name=agent_data.name,
                type=agent_data.type.value,
                status=AgentStatus.IDLE.value,
                capabilities=[cap.dict() for cap in agent_data.capabilities],
                performance_metrics={
                    "tasks_completed": 0,
                    "tasks_failed": 0,
                    "total_execution_time": 0.0,
                    "success_rate": 0.0,
                    "created_at": datetime.utcnow().isoformat()
                },
                learning_data={
                    "interactions": 0,
                    "feedback_score": 0.0,
                    "learning_rate": config.system.learning_rate,
                    "knowledge_base": []
                }
            )
            
            session.add(agent)
            await session.commit()
            await session.refresh(agent)
            
            # Cache agent data
            await self._cache_agent_data(agent)
            
            # Initialize agent in AI system
            await self._initialize_agent_ai(agent)
            
            self.logger.info(f"Agent created: {agent.id} ({agent.name})")
            
            return await self._build_agent_response(agent)
    
    async def get_agent(self, agent_id: str) -> AgentResponse:
        """Get agent by ID with performance metrics"""
        async with self.db_manager.get_session() as session:
            agent = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent {agent_id} not found"
                )
            
            return await self._build_agent_response(agent, session)
    
    async def list_agents(
        self, 
        page: int = 1, 
        page_size: int = 20,
        status_filter: Optional[AgentStatus] = None,
        type_filter: Optional[AgentType] = None,
        search: Optional[str] = None
    ) -> AgentListResponse:
        """List agents with filtering and pagination"""
        async with self.db_manager.get_session() as session:
            query = select(Agent)
            
            # Apply filters
            if status_filter:
                query = query.where(Agent.status == status_filter.value)
            if type_filter:
                query = query.where(Agent.type == type_filter.value)
            if search:
                query = query.where(Agent.name.ilike(f"%{search}%"))
            
            # Get total count
            count_query = select(func.count(Agent.id)).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size).order_by(Agent.created_at.desc())
            
            result = await session.execute(query)
            agents = result.scalars().all()
            
            # Build responses with metrics
            agent_responses = []
            for agent in agents:
                agent_responses.append(await self._build_agent_response(agent, session))
            
            return AgentListResponse(
                agents=agent_responses,
                total=total,
                page=page,
                page_size=page_size,
                has_next=(page * page_size) < total
            )
    
    async def update_agent(self, agent_id: str, update_data: AgentUpdateRequest) -> AgentResponse:
        """Update agent configuration"""
        async with self.db_manager.get_session() as session:
            agent = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent {agent_id} not found"
                )
            
            # Update fields
            if update_data.name is not None:
                # Check for duplicate names
                existing = await session.execute(
                    select(Agent).where(and_(Agent.name == update_data.name, Agent.id != agent_id))
                )
                if existing.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Agent with name '{update_data.name}' already exists"
                    )
                agent.name = update_data.name
            
            if update_data.status is not None:
                old_status = agent.status
                agent.status = update_data.status.value
                
                # Handle status transitions
                await self._handle_status_change(agent, old_status, update_data.status.value)
            
            if update_data.capabilities is not None:
                agent.capabilities = [cap.dict() for cap in update_data.capabilities]
            
            if update_data.metadata is not None:
                current_metadata = agent.metadata or {}
                current_metadata.update(update_data.metadata)
                agent.metadata = current_metadata
            
            agent.updated_at = datetime.utcnow()
            await session.commit()
            
            # Update cache
            await self._cache_agent_data(agent)
            
            self.logger.info(f"Agent updated: {agent.id} ({agent.name})")
            
            return await self._build_agent_response(agent, session)
    
    async def delete_agent(self, agent_id: str, force: bool = False) -> Dict[str, str]:
        """Delete agent with safety checks"""
        async with self.db_manager.get_session() as session:
            agent = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent {agent_id} not found"
                )
            
            # Check for active tasks unless forced
            if not force:
                active_tasks = await session.execute(
                    select(func.count(Task.id)).where(
                        and_(Task.agent_id == agent_id, Task.status.in_(["pending", "running"]))
                    )
                )
                if active_tasks.scalar() > 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Agent has active tasks. Use force=true to delete anyway."
                    )
            
            # Terminate agent gracefully
            if agent.status in [AgentStatus.ACTIVE.value, AgentStatus.BUSY.value]:
                agent.status = AgentStatus.TERMINATED.value
                await session.commit()
                await self._terminate_agent_tasks(agent_id, session)
            
            # Delete agent
            await session.delete(agent)
            await session.commit()
            
            # Clean up cache
            await self.redis.delete(f"agent:{agent_id}")
            
            self.logger.info(f"Agent deleted: {agent_id}")
            
            return {"message": f"Agent {agent_id} deleted successfully"}
    
    async def get_agent_performance(self, agent_id: str) -> AgentPerformanceMetrics:
        """Get detailed agent performance metrics"""
        async with self.db_manager.get_session() as session:
            agent = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent {agent_id} not found"
                )
            
            # Get task statistics
            task_stats = await session.execute(
                select(
                    func.count(Task.id).label("total_tasks"),
                    func.sum(func.case([(Task.status == "completed", 1)], else_=0)).label("completed_tasks"),
                    func.sum(func.case([(Task.status == "failed", 1)], else_=0)).label("failed_tasks"),
                    func.avg(Task.execution_time).label("avg_execution_time"),
                    func.max(Task.updated_at).label("last_activity")
                ).where(Task.agent_id == agent_id)
            )
            stats = task_stats.first()
            
            total_tasks = stats.total_tasks or 0
            completed_tasks = stats.completed_tasks or 0
            failed_tasks = stats.failed_tasks or 0
            success_rate = (completed_tasks / total_tasks) if total_tasks > 0 else 0.0
            
            return AgentPerformanceMetrics(
                agent_id=agent_id,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                success_rate=success_rate,
                average_execution_time=stats.avg_execution_time or 0.0,
                last_activity=stats.last_activity,
                learning_progress=agent.learning_data or {}
            )
    
    async def assign_task(self, agent_id: str, assignment: TaskAssignmentRequest) -> Dict[str, str]:
        """Assign task to agent with validation"""
        async with self.db_manager.get_session() as session:
            # Verify agent exists and is available
            agent = await session.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent.scalar_one_or_none()
            
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent {agent_id} not found"
                )
            
            if agent.status not in [AgentStatus.IDLE.value, AgentStatus.ACTIVE.value]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Agent is not available (status: {agent.status})"
                )
            
            # Verify task exists and is assignable
            task = await session.execute(
                select(Task).where(Task.id == assignment.task_id)
            )
            task = task.scalar_one_or_none()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {assignment.task_id} not found"
                )
            
            if task.status != "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Task is not assignable (status: {task.status})"
                )
            
            # Assign task
            task.agent_id = agent_id
            task.status = "assigned"
            if assignment.priority_override:
                task.priority = assignment.priority_override
            
            # Update agent status
            if agent.status == AgentStatus.IDLE.value:
                agent.status = AgentStatus.ACTIVE.value
            
            await session.commit()
            
            self.logger.info(f"Task {assignment.task_id} assigned to agent {agent_id}")
            
            return {"message": f"Task {assignment.task_id} assigned to agent {agent_id}"}
    
    # Private helper methods
    async def _build_agent_response(self, agent: Agent, session: AsyncSession = None) -> AgentResponse:
        """Build agent response with runtime statistics"""
        response_data = {
            "id": agent.id,
            "name": agent.name,
            "type": agent.type,
            "status": agent.status,
            "capabilities": agent.capabilities or [],
            "performance_metrics": agent.performance_metrics or {},
            "learning_data": agent.learning_data or {},
            "created_at": agent.created_at,
            "updated_at": agent.updated_at
        }
        
        # Add runtime statistics if session available
        if session:
            task_stats = await session.execute(
                select(
                    func.sum(func.case([(Task.status.in_(["assigned", "running"]), 1)], else_=0)).label("active_tasks"),
                    func.sum(func.case([(Task.status == "completed", 1)], else_=0)).label("completed_tasks"),
                    func.avg(Task.execution_time).label("avg_execution_time")
                ).where(Task.agent_id == agent.id)
            )
            stats = task_stats.first()
            
            response_data.update({
                "active_tasks": stats.active_tasks or 0,
                "completed_tasks": stats.completed_tasks or 0,
                "average_execution_time": stats.avg_execution_time
            })
            
            # Calculate success rate
            if stats.completed_tasks:
                total_tasks = await session.execute(
                    select(func.count(Task.id)).where(Task.agent_id == agent.id)
                )
                total = total_tasks.scalar() or 0
                response_data["success_rate"] = (stats.completed_tasks / total) if total > 0 else 0.0
        
        return AgentResponse(**response_data)
    
    async def _cache_agent_data(self, agent: Agent):
        """Cache agent data in Redis"""
        cache_data = {
            "id": agent.id,
            "name": agent.name,
            "type": agent.type,
            "status": agent.status,
            "capabilities": agent.capabilities,
            "updated_at": agent.updated_at.isoformat()
        }
        await self.redis.set(
            f"agent:{agent.id}",
            json.dumps(cache_data, default=str),
            ttl=config.system.cache_ttl_seconds
        )
    
    async def _initialize_agent_ai(self, agent: Agent):
        """Initialize agent in AI system"""
        # Create agent-specific AI context
        context = f"Agent {agent.name} ({agent.type}) with capabilities: {', '.join([cap['name'] for cap in agent.capabilities])}"
        
        # Store in vector database if available
        # Implementation depends on your vector database setup
        pass
    
    async def _handle_status_change(self, agent: Agent, old_status: str, new_status: str):
        """Handle agent status transitions"""
        if new_status == AgentStatus.TERMINATED.value:
            await self._terminate_agent_tasks(agent.id)
        elif new_status == AgentStatus.MAINTENANCE.value and old_status in [AgentStatus.ACTIVE.value, AgentStatus.BUSY.value]:
            # Pause active tasks
            async with self.db_manager.get_session() as session:
                await session.execute(
                    update(Task).where(
                        and_(Task.agent_id == agent.id, Task.status == "running")
                    ).values(status="paused")
                )
                await session.commit()
    
    async def _terminate_agent_tasks(self, agent_id: str, session: AsyncSession = None):
        """Terminate all active tasks for agent"""
        if not session:
            session = self.db_manager.get_session()
        
        await session.execute(
            update(Task).where(
                and_(Task.agent_id == agent_id, Task.status.in_(["assigned", "running", "paused"]))
            ).values(status="cancelled", updated_at=datetime.utcnow())
        )
        await session.commit()

# API Router
router = APIRouter(prefix="/api/v1/agents", tags=["Agent Management"])

# Dependency injection
async def get_agent_service() -> AgentManagementService:
    # These should be injected from your main application
    from main import db_manager, redis_manager, ai_manager
    return AgentManagementService(db_manager, redis_manager, ai_manager)

# API Endpoints
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreateRequest,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Create a new agent"""
    return await service.create_agent(agent_data)

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Get agent by ID"""
    return await service.get_agent(agent_id)

@router.get("/", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[AgentStatus] = None,
    type: Optional[AgentType] = None,
    search: Optional[str] = None,
    service: AgentManagementService = Depends(get_agent_service)
):
    """List agents with filtering and pagination"""
    return await service.list_agents(page, page_size, status, type, search)

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    update_data: AgentUpdateRequest,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Update agent configuration"""
    return await service.update_agent(agent_id, update_data)

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    force: bool = Query(False, description="Force delete even with active tasks"),
    service: AgentManagementService = Depends(get_agent_service)
):
    """Delete agent"""
    return await service.delete_agent(agent_id, force)

@router.get("/{agent_id}/performance", response_model=AgentPerformanceMetrics)
async def get_agent_performance(
    agent_id: str,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Get agent performance metrics"""
    return await service.get_agent_performance(agent_id)

@router.post("/{agent_id}/assign-task")
async def assign_task_to_agent(
    agent_id: str,
    assignment: TaskAssignmentRequest,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Assign task to agent"""
    return await service.assign_task(agent_id, assignment)

@router.post("/{agent_id}/start")
async def start_agent(
    agent_id: str,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Start/activate agent"""
    return await service.update_agent(agent_id, AgentUpdateRequest(status=AgentStatus.ACTIVE))

@router.post("/{agent_id}/stop")
async def stop_agent(
    agent_id: str,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Stop/idle agent"""
    return await service.update_agent(agent_id, AgentUpdateRequest(status=AgentStatus.IDLE))

@router.post("/{agent_id}/maintenance")
async def set_agent_maintenance(
    agent_id: str,
    service: AgentManagementService = Depends(get_agent_service)
):
    """Put agent in maintenance mode"""
    return await service.update_agent(agent_id, AgentUpdateRequest(status=AgentStatus.MAINTENANCE))

# Health check endpoint
@router.get("/health/check")
async def health_check():
    """Health check for agent management system"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "agent_management_api"
    }
