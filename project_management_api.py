"""
YMERA Enterprise Project Management API
Production-Ready FastAPI Router with Multi-Agent Integration & Learning Engine
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Path, Body
from fastapi.security import HTTPBearer
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import asyncio
import json
from enum import Enum
from pydantic import BaseModel, Field, validator

# Core system imports
from ymera_core.database.manager import DatabaseManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.security.auth_manager import AuthManager
from ymera_core.exceptions import YMERAException, ValidationError, AuthenticationError

# Agent system imports
from ymera_agents.orchestrator import AgentOrchestrator
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.communication.message_bus import MessageBus

# Service layer imports
from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_services.github.repository_analyzer import GitHubRepositoryAnalyzer
from ymera_services.code_analysis.quality_analyzer import CodeQualityAnalyzer

# Response models
from ymera_api.response_models import (
    BaseResponse, PaginatedResponse, SuccessResponse, ErrorResponse
)

router = APIRouter()
security = HTTPBearer()

# Enums
class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    IN_REVIEW = "in_review"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"

class ProjectType(str, Enum):
    WEB_APPLICATION = "web_application"
    MOBILE_APPLICATION = "mobile_application"
    API_SERVICE = "api_service"
    MICROSERVICE = "microservice"
    LIBRARY = "library"
    FRAMEWORK = "framework"
    INFRASTRUCTURE = "infrastructure"
    DATA_PIPELINE = "data_pipeline"
    ML_MODEL = "ml_model"
    INTEGRATION = "integration"

class ProjectPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AgentTaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Request/Response Models
class ProjectTechnology(BaseModel):
    name: str = Field(..., description="Technology name (e.g., Python, React, PostgreSQL)")
    version: Optional[str] = Field(None, description="Technology version")
    category: str = Field(..., description="Technology category (language, framework, database, etc.)")
    required: bool = Field(True, description="Whether this technology is required")

class ProjectRequirement(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., description="Requirement title")
    description: str = Field(..., description="Detailed requirement description")
    priority: ProjectPriority = Field(ProjectPriority.MEDIUM)
    category: str = Field(..., description="Requirement category (functional, non-functional, etc.)")
    acceptance_criteria: List[str] = Field(default_factory=list)
    estimated_effort: Optional[int] = Field(None, description="Estimated effort in hours")
    completed: bool = Field(False)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class AgentTaskRequest(BaseModel):
    agent_type: str = Field(..., description="Type of agent to assign task")
    task_type: str = Field(..., description="Specific task type")
    description: str = Field(..., description="Task description")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: ProjectPriority = Field(ProjectPriority.MEDIUM)
    deadline: Optional[datetime] = Field(None)
    dependencies: List[str] = Field(default_factory=list, description="Task IDs this task depends on")

class AgentTaskResponse(BaseModel):
    task_id: str
    agent_type: str
    task_type: str
    status: AgentTaskStatus
    description: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    progress_percentage: float = 0.0
    learning_feedback: Optional[Dict[str, Any]] = None

class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str = Field(..., min_length=10, description="Project description")
    project_type: ProjectType = Field(..., description="Type of project")
    priority: ProjectPriority = Field(ProjectPriority.MEDIUM)
    technologies: List[ProjectTechnology] = Field(default_factory=list)
    requirements: List[ProjectRequirement] = Field(default_factory=list)
    repository_url: Optional[str] = Field(None, description="GitHub repository URL")
    target_completion_date: Optional[datetime] = Field(None)
    budget: Optional[float] = Field(None, ge=0)
    team_members: List[str] = Field(default_factory=list, description="Team member user IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    technologies: Optional[List[ProjectTechnology]] = None
    requirements: Optional[List[ProjectRequirement]] = None
    repository_url: Optional[str] = None
    target_completion_date: Optional[datetime] = None
    budget: Optional[float] = Field(None, ge=0)
    team_members: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class ProjectAnalysisRequest(BaseModel):
    analysis_types: List[str] = Field(..., description="Types of analysis to perform")
    include_repository: bool = Field(True, description="Include repository analysis")
    include_security_scan: bool = Field(True, description="Include security vulnerability scan")
    include_quality_assessment: bool = Field(True, description="Include code quality assessment")
    custom_parameters: Dict[str, Any] = Field(default_factory=dict)

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    project_type: ProjectType
    status: ProjectStatus
    priority: ProjectPriority
    technologies: List[ProjectTechnology]
    requirements: List[ProjectRequirement]
    repository_url: Optional[str] = None
    target_completion_date: Optional[datetime] = None
    budget: Optional[float] = None
    team_members: List[str]
    metadata: Dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime
    progress_percentage: float = 0.0
    active_tasks: int = 0
    completed_tasks: int = 0
    total_tasks: int = 0
    learning_insights: Optional[Dict[str, Any]] = None
    agent_recommendations: Optional[List[Dict[str, Any]]] = None

class ProjectAnalysisResponse(BaseModel):
    project_id: str
    analysis_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    results: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    learning_insights: Dict[str, Any]
    agent_contributions: Dict[str, Any]

class ProjectInsightsResponse(BaseModel):
    project_id: str
    insights: Dict[str, Any]
    predictions: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    learning_data: Dict[str, Any]
    generated_at: datetime

# Dependency functions
async def get_current_user(token: str = Depends(security)) -> Dict[str, Any]:
    """Extract and validate current user from JWT token"""
    try:
        from main import system  # Import system components
        auth_manager = system.auth_manager
        payload = await auth_manager.verify_token(token.credentials)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

async def get_system_components():
    """Get system components for dependency injection"""
    from main import system
    return system

# Project Management Endpoints

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED,
            summary="Create New Project", description="Create a new project with AI-powered initialization")
async def create_project(
    project_data: ProjectCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new project with intelligent initialization using multi-agent system.
    
    Features:
    - Automatic project structure analysis
    - Technology stack validation
    - Initial requirement analysis
    - Agent task assignment
    - Learning engine integration
    """
    system = await get_system_components()
    
    try:
        # Generate unique project ID
        project_id = str(uuid4())
        
        # Create project record
        project_record = {
            "id": project_id,
            "name": project_data.name,
            "description": project_data.description,
            "project_type": project_data.project_type.value,
            "status": ProjectStatus.PLANNING.value,
            "priority": project_data.priority.value,
            "technologies": [tech.dict() for tech in project_data.technologies],
            "requirements": [req.dict() for req in project_data.requirements],
            "repository_url": project_data.repository_url,
            "target_completion_date": project_data.target_completion_date,
            "budget": project_data.budget,
            "team_members": project_data.team_members,
            "metadata": project_data.metadata,
            "created_by": current_user["user_id"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "progress_percentage": 0.0
        }
        
        # Save to database
        await system.db_manager.execute_query(
            """
            INSERT INTO projects (
                id, name, description, project_type, status, priority,
                technologies, requirements, repository_url, target_completion_date,
                budget, team_members, metadata, created_by, created_at, updated_at,
                progress_percentage
            ) VALUES (
                :id, :name, :description, :project_type, :status, :priority,
                :technologies, :requirements, :repository_url, :target_completion_date,
                :budget, :team_members, :metadata, :created_by, :created_at, :updated_at,
                :progress_percentage
            )
            """,
            {
                **project_record,
                "technologies": json.dumps(project_record["technologies"]),
                "requirements": json.dumps(project_record["requirements"]),
                "team_members": json.dumps(project_record["team_members"]),
                "metadata": json.dumps(project_record["metadata"])
            }
        )
        
        # Cache project data
        await system.cache_manager.set(
            f"project:{project_id}",
            json.dumps(project_record, default=str),
            ttl=3600
        )
        
        # Initialize project with multi-agent system
        background_tasks.add_task(
            _initialize_project_with_agents,
            system, project_id, project_data, current_user
        )
        
        # Learning engine: Record project creation
        await system.learning_engine.record_interaction(
            interaction_type="project_creation",
            context={
                "project_type": project_data.project_type.value,
                "technologies": [tech.name for tech in project_data.technologies],
                "requirements_count": len(project_data.requirements),
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        # Prepare response
        response_data = project_record.copy()
        response_data["technologies"] = project_data.technologies
        response_data["requirements"] = project_data.requirements
        response_data["active_tasks"] = 0
        response_data["completed_tasks"] = 0
        response_data["total_tasks"] = 0
        
        system.logger.info(
            f"Project created successfully",
            extra={
                "project_id": project_id,
                "project_name": project_data.name,
                "created_by": current_user["user_id"],
                "project_type": project_data.project_type.value
            }
        )
        
        return ProjectResponse(**response_data)
        
    except Exception as e:
        system.logger.error(f"Error creating project: {str(e)}")
        await system.learning_engine.record_interaction(
            interaction_type="project_creation",
            context={"error": str(e)},
            outcome="error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )

@router.get("/", response_model=PaginatedResponse[ProjectResponse],
           summary="List Projects", description="Get paginated list of projects with filtering")
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[ProjectStatus] = Query(None, description="Filter by project status"),
    project_type: Optional[ProjectType] = Query(None, description="Filter by project type"),
    priority: Optional[ProjectPriority] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Search in project name and description"),
    created_by: Optional[str] = Query(None, description="Filter by creator user ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve paginated list of projects with advanced filtering and search capabilities.
    """
    system = await get_system_components()
    
    try:
        # Build query conditions
        conditions = ["1=1"]  # Base condition
        params = {"offset": (page - 1) * limit, "limit": limit}
        
        if status:
            conditions.append("status = :status")
            params["status"] = status.value
            
        if project_type:
            conditions.append("project_type = :project_type")
            params["project_type"] = project_type.value
            
        if priority:
            conditions.append("priority = :priority")
            params["priority"] = priority.value
            
        if search:
            conditions.append("(name ILIKE :search OR description ILIKE :search)")
            params["search"] = f"%{search}%"
            
        if created_by:
            conditions.append("created_by = :created_by")
            params["created_by"] = created_by
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM projects WHERE {where_clause}"
        count_result = await system.db_manager.fetch_one(count_query, params)
        total = count_result["total"] if count_result else 0
        
        # Get projects
        query = f"""
            SELECT p.*, 
                   COALESCE(task_stats.active_tasks, 0) as active_tasks,
                   COALESCE(task_stats.completed_tasks, 0) as completed_tasks,
                   COALESCE(task_stats.total_tasks, 0) as total_tasks
            FROM projects p
            LEFT JOIN (
                SELECT project_id, 
                       COUNT(*) as total_tasks,
                       COUNT(CASE WHEN status IN ('assigned', 'in_progress') THEN 1 END) as active_tasks,
                       COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks
                FROM agent_tasks 
                GROUP BY project_id
            ) task_stats ON p.id = task_stats.project_id
            WHERE {where_clause}
            ORDER BY p.updated_at DESC
            OFFSET :offset LIMIT :limit
        """
        
        projects = await system.db_manager.fetch_all(query, params)
        
        # Convert to response models
        project_responses = []
        for project in projects:
            project_data = dict(project)
            
            # Parse JSON fields
            project_data["technologies"] = json.loads(project_data["technologies"]) if project_data["technologies"] else []
            project_data["requirements"] = json.loads(project_data["requirements"]) if project_data["requirements"] else []
            project_data["team_members"] = json.loads(project_data["team_members"]) if project_data["team_members"] else []
            project_data["metadata"] = json.loads(project_data["metadata"]) if project_data["metadata"] else {}
            
            # Get learning insights if available
            learning_insights = await system.learning_engine.get_project_insights(project_data["id"])
            if learning_insights:
                project_data["learning_insights"] = learning_insights
            
            project_responses.append(ProjectResponse(**project_data))
        
        # Learning: Record search pattern
        if search or status or project_type or priority:
            await system.learning_engine.record_interaction(
                interaction_type="project_search",
                context={
                    "search_terms": search,
                    "filters": {
                        "status": status.value if status else None,
                        "type": project_type.value if project_type else None,
                        "priority": priority.value if priority else None
                    }
                },
                outcome="success"
            )
        
        return PaginatedResponse(
            items=project_responses,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit
        )
        
    except Exception as e:
        system.logger.error(f"Error listing projects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve projects: {str(e)}"
        )

@router.get("/{project_id}", response_model=ProjectResponse,
           summary="Get Project Details", description="Get detailed project information with agent insights")
async def get_project(
    project_id: str = Path(..., description="Project ID"),
    include_insights: bool = Query(True, description="Include AI insights and recommendations"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve detailed project information including agent insights and learning data.
    """
    system = await get_system_components()
    
    try:
        # Try cache first
        cached_project = await system.cache_manager.get(f"project:{project_id}")
        if cached_project:
            project_data = json.loads(cached_project)
        else:
            # Query database
            query = """
                SELECT p.*, 
                       COALESCE(task_stats.active_tasks, 0) as active_tasks,
                       COALESCE(task_stats.completed_tasks, 0) as completed_tasks,
                       COALESCE(task_stats.total_tasks, 0) as total_tasks
                FROM projects p
                LEFT JOIN (
                    SELECT project_id, 
                           COUNT(*) as total_tasks,
                           COUNT(CASE WHEN status IN ('assigned', 'in_progress') THEN 1 END) as active_tasks,
                           COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks
                    FROM agent_tasks 
                    WHERE project_id = :project_id
                    GROUP BY project_id
                ) task_stats ON p.id = task_stats.project_id
                WHERE p.id = :project_id
            """
            
            project = await system.db_manager.fetch_one(query, {"project_id": project_id})
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found"
                )
            
            project_data = dict(project)
            
            # Cache for future requests
            await system.cache_manager.set(
                f"project:{project_id}",
                json.dumps(project_data, default=str),
                ttl=1800
            )
        
        # Parse JSON fields
        project_data["technologies"] = json.loads(project_data["technologies"]) if project_data["technologies"] else []
        project_data["requirements"] = json.loads(project_data["requirements"]) if project_data["requirements"] else []
        project_data["team_members"] = json.loads(project_data["team_members"]) if project_data["team_members"] else []
        project_data["metadata"] = json.loads(project_data["metadata"]) if project_data["metadata"] else {}
        
        # Get learning insights and agent recommendations if requested
        if include_insights:
            # Get learning insights
            learning_insights = await system.learning_engine.get_project_insights(project_id)
            if learning_insights:
                project_data["learning_insights"] = learning_insights
            
            # Get agent recommendations
            recommendations = await system.agent_orchestrator.get_project_recommendations(project_id)
            if recommendations:
                project_data["agent_recommendations"] = recommendations
        
        # Record project view for learning
        await system.learning_engine.record_interaction(
            interaction_type="project_view",
            context={
                "project_id": project_id,
                "user_id": current_user["user_id"],
                "include_insights": include_insights
            },
            outcome="success"
        )
        
        return ProjectResponse(**project_data)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error retrieving project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve project: {str(e)}"
        )

@router.put("/{project_id}", response_model=ProjectResponse,
           summary="Update Project", description="Update project details with agent notification")
async def update_project(
    project_id: str = Path(..., description="Project ID"),
    update_data: ProjectUpdateRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Update project details and notify relevant agents about changes.
    """
    system = await get_system_components()
    
    try:
        # Verify project exists
        existing_project = await system.db_manager.fetch_one(
            "SELECT * FROM projects WHERE id = :project_id",
            {"project_id": project_id}
        )
        
        if not existing_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Prepare update data
        update_fields = []
        update_params = {"project_id": project_id, "updated_at": datetime.utcnow()}
        changes = {}
        
        for field, value in update_data.dict(exclude_unset=True).items():
            if value is not None:
                if field in ["technologies", "requirements", "team_members", "metadata"]:
                    update_fields.append(f"{field} = :{field}")
                    update_params[field] = json.dumps(value, default=str) if isinstance(value, (list, dict)) else value
                    changes[field] = value
                else:
                    update_fields.append(f"{field} = :{field}")
                    update_params[field] = value.value if hasattr(value, 'value') else value
                    changes[field] = value
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )
        
        # Update database
        update_fields.append("updated_at = :updated_at")
        query = f"UPDATE projects SET {', '.join(update_fields)} WHERE id = :project_id"
        await system.db_manager.execute_query(query, update_params)
        
        # Clear cache
        await system.cache_manager.delete(f"project:{project_id}")
        
        # Notify agents about project changes
        background_tasks.add_task(
            _notify_agents_of_project_changes,
            system, project_id, changes, current_user
        )
        
        # Record learning data
        await system.learning_engine.record_interaction(
            interaction_type="project_update",
            context={
                "project_id": project_id,
                "changes": list(changes.keys()),
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        # Get updated project
        return await get_project(project_id, include_insights=True, current_user=current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )

@router.delete("/{project_id}", response_model=SuccessResponse,
              summary="Archive Project", description="Archive project and cleanup associated resources")
async def archive_project(
    project_id: str = Path(..., description="Project ID"),
    force_delete: bool = Query(False, description="Force delete instead of archive"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Archive or delete a project and cleanup all associated resources.
    """
    system = await get_system_components()
    
    try:
        # Verify project exists
        project = await system.db_manager.fetch_one(
            "SELECT * FROM projects WHERE id = :project_id",
            {"project_id": project_id}
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        if force_delete:
            # Hard delete - remove all traces
            await system.db_manager.execute_query(
                "DELETE FROM projects WHERE id = :project_id",
                {"project_id": project_id}
            )
            
            # Delete related data
            await system.db_manager.execute_query(
                "DELETE FROM agent_tasks WHERE project_id = :project_id",
                {"project_id": project_id}
            )
            
            action = "deleted"
        else:
            # Soft delete - archive
            await system.db_manager.execute_query(
                "UPDATE projects SET status = :status, updated_at = :updated_at WHERE id = :project_id",
                {
                    "project_id": project_id,
                    "status": ProjectStatus.ARCHIVED.value,
                    "updated_at": datetime.utcnow()
                }
            )
            action = "archived"
        
        # Clear cache
        await system.cache_manager.delete(f"project:{project_id}")
        
        # Cleanup background tasks
        background_tasks.add_task(
            _cleanup_project_resources,
            system, project_id, force_delete
        )
        
        # Record learning data
        await system.learning_engine.record_interaction(
            interaction_type="project_archive" if not force_delete else "project_delete",
            context={
                "project_id": project_id,
                "project_name": project["name"],
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        system.logger.info(
            f"Project {action} successfully",
            extra={
                "project_id": project_id,
                "action": action,
                "user_id": current_user["user_id"]
            }
        )
        
        return SuccessResponse(
            message=f"Project {action} successfully",
            data={"project_id": project_id, "action": action}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error archiving project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive project: {str(e)}"
        )

# Agent Task Management Endpoints

@router.post("/{project_id}/tasks", response_model=AgentTaskResponse, status_code=status.HTTP_201_CREATED,
            summary="Create Agent Task", description="Assign a task to an agent for this project")
async def create_agent_task(
    project_id: str = Path(..., description="Project ID"),
    task_request: AgentTaskRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create and assign a task to a specific agent for the project.
    """
    system = await get_system_components()
    
    try:
        # Verify project exists
        project = await system.db_manager.fetch_one(
            "SELECT * FROM projects WHERE id = :project_id",
            {"project_id": project_id}
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Generate task ID
        task_id = str(uuid4())
        
        # Create task record
        task_data = {
            "task_id": task_id,
            "project_id": project_id,
            "agent_type": task_request.agent_type,
            "task_type": task_request.task_type,
            "status": AgentTaskStatus.PENDING.value,
            "description": task_request.description,
            "parameters": json.dumps(task_request.parameters),
            "priority": task_request.priority.value,
            "deadline": task_request.deadline,
            "dependencies": json.dumps(task_request.dependencies),
            "created_by": current_user["user_id"],
            "create # Create task record (continued from where it ended)
        task_data = {
            "task_id": task_id,
            "project_id": project_id,
            "agent_type": task_request.agent_type,
            "task_type": task_request.task_type,
            "status": AgentTaskStatus.PENDING.value,
            "description": task_request.description,
            "parameters": json.dumps(task_request.parameters),
            "priority": task_request.priority.value,
            "deadline": task_request.deadline,
            "dependencies": json.dumps(task_request.dependencies),
            "created_by": current_user["user_id"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Save task to database
        await system.db_manager.execute_query(
            """
            INSERT INTO agent_tasks (
                task_id, project_id, agent_type, task_type, status, description,
                parameters, priority, deadline, dependencies, created_by, created_at, updated_at
            ) VALUES (
                :task_id, :project_id, :agent_type, :task_type, :status, :description,
                :parameters, :priority, :deadline, :dependencies, :created_by, :created_at, :updated_at
            )
            """,
            task_data
        )
        
        # Assign task to agent orchestrator
        background_tasks.add_task(
            _assign_task_to_agent,
            system, task_id, task_request, project_id, current_user
        )
        
        # Record learning data
        await system.learning_engine.record_interaction(
            interaction_type="agent_task_creation",
            context={
                "project_id": project_id,
                "agent_type": task_request.agent_type,
                "task_type": task_request.task_type,
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        # Prepare response
        response_data = {
            "task_id": task_id,
            "agent_type": task_request.agent_type,
            "task_type": task_request.task_type,
            "status": AgentTaskStatus.PENDING,
            "description": task_request.description,
            "created_at": datetime.utcnow(),
            "progress_percentage": 0.0
        }
        
        system.logger.info(
            f"Agent task created successfully",
            extra={
                "task_id": task_id,
                "project_id": project_id,
                "agent_type": task_request.agent_type,
                "created_by": current_user["user_id"]
            }
        )
        
        return AgentTaskResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error creating agent task for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent task: {str(e)}"
        )

@router.get("/{project_id}/tasks", response_model=PaginatedResponse[AgentTaskResponse],
           summary="List Project Tasks", description="Get paginated list of agent tasks for this project")
async def list_project_tasks(
    project_id: str = Path(..., description="Project ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[AgentTaskStatus] = Query(None, description="Filter by task status"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve paginated list of agent tasks for the specified project.
    """
    system = await get_system_components()
    
    try:
        # Verify project exists
        project = await system.db_manager.fetch_one(
            "SELECT id FROM projects WHERE id = :project_id",
            {"project_id": project_id}
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Build query conditions
        conditions = ["project_id = :project_id"]
        params = {
            "project_id": project_id,
            "offset": (page - 1) * limit,
            "limit": limit
        }
        
        if status:
            conditions.append("status = :status")
            params["status"] = status.value
            
        if agent_type:
            conditions.append("agent_type = :agent_type")
            params["agent_type"] = agent_type
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM agent_tasks WHERE {where_clause}"
        count_result = await system.db_manager.fetch_one(count_query, params)
        total = count_result["total"] if count_result else 0
        
        # Get tasks
        query = f"""
            SELECT * FROM agent_tasks 
            WHERE {where_clause}
            ORDER BY created_at DESC
            OFFSET :offset LIMIT :limit
        """
        
        tasks = await system.db_manager.fetch_all(query, params)
        
        # Convert to response models
        task_responses = []
        for task in tasks:
            task_data = dict(task)
            
            # Parse JSON fields
            task_data["parameters"] = json.loads(task_data["parameters"]) if task_data["parameters"] else {}
            task_data["dependencies"] = json.loads(task_data["dependencies"]) if task_data["dependencies"] else []
            task_data["result"] = json.loads(task_data["result"]) if task_data.get("result") else None
            task_data["learning_feedback"] = json.loads(task_data["learning_feedback"]) if task_data.get("learning_feedback") else None
            
            task_responses.append(AgentTaskResponse(**task_data))
        
        return PaginatedResponse(
            items=task_responses,
            total=total,
            page=page,
            limit=limit,
            pages=(total + limit - 1) // limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error listing tasks for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve project tasks: {str(e)}"
        )

@router.get("/{project_id}/tasks/{task_id}", response_model=AgentTaskResponse,
           summary="Get Task Details", description="Get detailed information about a specific agent task")
async def get_agent_task(
    project_id: str = Path(..., description="Project ID"),
    task_id: str = Path(..., description="Task ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve detailed information about a specific agent task.
    """
    system = await get_system_components()
    
    try:
        # Get task details
        query = """
            SELECT * FROM agent_tasks 
            WHERE task_id = :task_id AND project_id = :project_id
        """
        
        task = await system.db_manager.fetch_one(query, {
            "task_id": task_id,
            "project_id": project_id
        })
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        task_data = dict(task)
        
        # Parse JSON fields
        task_data["parameters"] = json.loads(task_data["parameters"]) if task_data["parameters"] else {}
        task_data["dependencies"] = json.loads(task_data["dependencies"]) if task_data["dependencies"] else []
        task_data["result"] = json.loads(task_data["result"]) if task_data.get("result") else None
        task_data["learning_feedback"] = json.loads(task_data["learning_feedback"]) if task_data.get("learning_feedback") else None
        
        return AgentTaskResponse(**task_data)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error retrieving task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve task details: {str(e)}"
        )

# Project Analysis Endpoints

@router.post("/{project_id}/analyze", response_model=ProjectAnalysisResponse, status_code=status.HTTP_202_ACCEPTED,
            summary="Analyze Project", description="Start comprehensive AI-powered project analysis")
async def analyze_project(
    project_id: str = Path(..., description="Project ID"),
    analysis_request: ProjectAnalysisRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Start a comprehensive analysis of the project using multiple AI agents.
    """
    system = await get_system_components()
    
    try:
        # Verify project exists
        project = await system.db_manager.fetch_one(
            "SELECT * FROM projects WHERE id = :project_id",
            {"project_id": project_id}
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Generate analysis ID
        analysis_id = str(uuid4())
        
        # Create analysis record
        analysis_data = {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "status": "started",
            "analysis_types": json.dumps(analysis_request.analysis_types),
            "parameters": json.dumps({
                "include_repository": analysis_request.include_repository,
                "include_security_scan": analysis_request.include_security_scan,
                "include_quality_assessment": analysis_request.include_quality_assessment,
                "custom_parameters": analysis_request.custom_parameters
            }),
            "started_by": current_user["user_id"],
            "started_at": datetime.utcnow(),
            "results": json.dumps({}),
            "recommendations": json.dumps([]),
            "learning_insights": json.dumps({}),
            "agent_contributions": json.dumps({})
        }
        
        # Save analysis record
        await system.db_manager.execute_query(
            """
            INSERT INTO project_analyses (
                analysis_id, project_id, status, analysis_types, parameters,
                started_by, started_at, results, recommendations, learning_insights, agent_contributions
            ) VALUES (
                :analysis_id, :project_id, :status, :analysis_types, :parameters,
                :started_by, :started_at, :results, :recommendations, :learning_insights, :agent_contributions
            )
            """,
            analysis_data
        )
        
        # Start analysis in background
        background_tasks.add_task(
            _run_project_analysis,
            system, analysis_id, project_id, analysis_request, current_user
        )
        
        # Record learning data
        await system.learning_engine.record_interaction(
            interaction_type="project_analysis_start",
            context={
                "project_id": project_id,
                "analysis_types": analysis_request.analysis_types,
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        # Prepare response
        response_data = {
            "project_id": project_id,
            "analysis_id": analysis_id,
            "status": "started",
            "started_at": datetime.utcnow(),
            "results": {},
            "recommendations": [],
            "learning_insights": {},
            "agent_contributions": {}
        }
        
        system.logger.info(
            f"Project analysis started",
            extra={
                "analysis_id": analysis_id,
                "project_id": project_id,
                "started_by": current_user["user_id"]
            }
        )
        
        return ProjectAnalysisResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error starting project analysis for {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start project analysis: {str(e)}"
        )

@router.get("/{project_id}/analyze/{analysis_id}", response_model=ProjectAnalysisResponse,
           summary="Get Analysis Results", description="Get project analysis results and status")
async def get_analysis_results(
    project_id: str = Path(..., description="Project ID"),
    analysis_id: str = Path(..., description="Analysis ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve the results of a project analysis.
    """
    system = await get_system_components()
    
    try:
        # Get analysis results
        query = """
            SELECT * FROM project_analyses 
            WHERE analysis_id = :analysis_id AND project_id = :project_id
        """
        
        analysis = await system.db_manager.fetch_one(query, {
            "analysis_id": analysis_id,
            "project_id": project_id
        })
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        analysis_data = dict(analysis)
        
        # Parse JSON fields
        analysis_data["results"] = json.loads(analysis_data["results"]) if analysis_data["results"] else {}
        analysis_data["recommendations"] = json.loads(analysis_data["recommendations"]) if analysis_data["recommendations"] else []
        analysis_data["learning_insights"] = json.loads(analysis_data["learning_insights"]) if analysis_data["learning_insights"] else {}
        analysis_data["agent_contributions"] = json.loads(analysis_data["agent_contributions"]) if analysis_data["agent_contributions"] else {}
        
        return ProjectAnalysisResponse(**analysis_data)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error retrieving analysis {analysis_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analysis results: {str(e)}"
        )

@router.get("/{project_id}/insights", response_model=ProjectInsightsResponse,
           summary="Get Project Insights", description="Get AI-powered insights and predictions for the project")
async def get_project_insights(
    project_id: str = Path(..., description="Project ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get AI-powered insights, predictions, and recommendations for the project.
    """
    system = await get_system_components()
    
    try:
        # Verify project exists
        project = await system.db_manager.fetch_one(
            "SELECT * FROM projects WHERE id = :project_id",
            {"project_id": project_id}
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Get insights from learning engine
        insights = await system.learning_engine.get_project_insights(project_id)
        predictions = await system.learning_engine.get_project_predictions(project_id)
        recommendations = await system.agent_orchestrator.get_project_recommendations(project_id)
        risk_assessment = await system.learning_engine.assess_project_risks(project_id)
        learning_data = await system.learning_engine.get_project_learning_data(project_id)
        
        response_data = {
            "project_id": project_id,
            "insights": insights or {},
            "predictions": predictions or {},
            "recommendations": recommendations or [],
            "risk_assessment": risk_assessment or {},
            "learning_data": learning_data or {},
            "generated_at": datetime.utcnow()
        }
        
        # Record insights access
        await system.learning_engine.record_interaction(
            interaction_type="insights_access",
            context={
                "project_id": project_id,
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        return ProjectInsightsResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        system.logger.error(f"Error retrieving insights for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve project insights: {str(e)}"
        )

# Background Task Functions

async def _initialize_project_with_agents(
    system, project_id: str, project_data: ProjectCreateRequest, current_user: Dict[str, Any]
):
    """
    Initialize project with multi-agent system in the background.
    """
    try:
        # Analyze project requirements and suggest initial tasks
        initial_tasks = await system.agent_orchestrator.analyze_project_requirements(
            project_id, project_data.dict(), current_user
        )
        
        # Create initial agent tasks
        for task in initial_tasks:
            await system.db_manager.execute_query(
                """
                INSERT INTO agent_tasks (
                    task_id, project_id, agent_type, task_type, status, description,
                    parameters, priority, created_by, created_at, updated_at
                ) VALUES (
                    :task_id, :project_id, :agent_type, :task_type, :status, :description,
                    :parameters, :priority, :created_by, :created_at, :updated_at
                )
                """,
                {
                    "task_id": str(uuid4()),
                    "project_id": project_id,
                    "agent_type": task["agent_type"],
                    "task_type": task["task_type"],
                    "status": AgentTaskStatus.PENDING.value,
                    "description": task["description"],
                    "parameters": json.dumps(task.get("parameters", {})),
                    "priority": task.get("priority", "medium"),
                    "created_by": "system",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
        
        # Update project status
        await system.db_manager.execute_query(
            "UPDATE projects SET status = :status WHERE id = :project_id",
            {"project_id": project_id, "status": ProjectStatus.ACTIVE.value}
        )
        
        system.logger.info(f"Project {project_id} initialized with {len(initial_tasks)} tasks")
        
    except Exception as e:
        system.logger.error(f"Error initializing project {project_id}: {str(e)}")

async def _assign_task_to_agent(
    system, task_id: str, task_request: AgentTaskRequest, project_id: str, current_user: Dict[str, Any]
):
    """
    Assign task to appropriate agent.
    """
    try:
        # Find and assign agent
        agent_result = await system.agent_orchestrator.assign_task(
            agent_type=task_request.agent_type,
            task_type=task_request.task_type,
            task_id=task_id,
            project_id=project_id,
            parameters=task_request.parameters,
            context={"user_id": current_user["user_id"]}
        )
        
        # Update task status
        await system.db_manager.execute_query(
            """
            UPDATE agent_tasks SET 
                status = :status, 
                started_at = :started_at,
                estimated_completion = :estimated_completion,
                updated_at = :updated_at
            WHERE task_id = :task_id
            """,
            {
                "task_id": task_id,
                "status": AgentTaskStatus.ASSIGNED.value,
                "started_at": datetime.utcnow(),
                "estimated_completion": agent_result.get("estimated_completion"),
                "updated_at": datetime.utcnow()
            }
        )
        
        system.logger.info(f"Task {task_id} assigned to agent {task_request.agent_type}")
        
    except Exception as e:
        # Mark task as failed
        await system.db_manager.execute_query(
            """
            UPDATE agent_tasks SET 
                status = :status, 
                error = :error,
                updated_at = :updated_at
            WHERE task_id = :task_id
            """,
            {
                "task_id": task_id,
                "status": AgentTaskStatus.FAILED.value,
                "error": str(e),
                "updated_at": datetime.utcnow()
            }
        )
        
        system.logger.error(f"Error assigning task {task_id}: {str(e)}")

async def _notify_agents_of_project_changes(
    system, project_id: str, changes: Dict[str, Any], current_user: Dict[str, Any]
):
    """
    Notify relevant agents about project changes.
    """
    try:
        # Send notifications to message bus
        await system.message_bus.publish(
            channel="project_updates",
            message={
                "project_id": project_id,
                "changes": changes,
                "updated_by": current_user["user_id"],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        system.logger.info(f"Agents notified of changes to project {project_id}")
        
    except Exception as e:
        system.logger.error(f"Error notifying agents of project changes: {str(e)}")

async def _cleanup_project_resources(
    system, project_id: str, force_delete: bool
):
    """
    Cleanup project resources in background.
    """
    try:
        if force_delete:
            # Cleanup cache entries
            await system.cache_manager.delete_pattern(f"project:{project_id}*")
            
            # Notify agents of project deletion
            await system.message_bus.publish(
                channel="project_deletions",
                message={
                    "project_id": project_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        system.logger.info(f"Resources cleaned up for project {project_id}")
        
    except Exception as e:
        system.logger.error(f"Error cleaning up project resources: {str(e)}")

async def _run_project_analysis(
    system, analysis_id: str, project_id: str, analysis_request: ProjectAnalysisRequest, current_user: Dict[str, Any]
):
    """
    Run comprehensive project analysis in background.
    """
    try:
        # Start analysis
        await system.db_manager.execute_query(
            "UPDATE project_analyses SET status = :status WHERE analysis_id = :analysis_id",
            {"analysis_id": analysis_id, "status": "running"}
        )
        
        # Collect analysis results
        results = {}
        recommendations = []
        agent_contributions = {}
        
        # Repository analysis
        if analysis_request.include_repository:
            repo_analysis = await system.github_analyzer.analyze_project_repository(project_id)
            results["repository"] = repo_analysis
            agent_contributions["github_analyzer"] = repo_analysis
        
        # Security scan
        if analysis_request.include_security_scan:
            security_analysis = await system.code_analyzer.security_scan(project_id)
            results["security"] = security_analysis
            agent_contributions["security_analyzer"] = security_analysis
        
        # Quality assessment
        if analysis_request.include_quality_assessment:
            quality_analysis = await system.code_analyzer.quality_assessment(project_id)
            results["quality"] = quality_analysis
            agent_contributions["quality_analyzer"] = quality_analysis
        
        # Generate recommendations using learning engine
        learning_insights = await system.learning_engine.analyze_project_patterns(project_id, results)
        project_recommendations = await system.agent_orchestrator.generate_recommendations(project_id, results)
        recommendations.extend(project_recommendations)
        
        # Update analysis record with results
        await system.db_manager.execute_query(
            """
            UPDATE project_analyses SET 
                status = :status,
                completed_at = :completed_at,
                results = :results,
                recommendations = :recommendations,
                learning_insights = :learning_insights,
                agent_contributions = :agent_contributions
            WHERE analysis_id = :analysis_id
            """,
            {
                "analysis_id": analysis_id,
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "results": json.dumps(results),
                "recommendations": json.dumps(recommendations),
                "learning_insights": json.dumps(learning_insights),
                "agent_contributions": json.dumps(agent_contributions)
            }
        )
        
        # Record learning data
        await system.learning_engine.record_interaction(
            interaction_type="project_analysis_complete",
            context={
                "project_id": project_id,
                "analysis_id": analysis_id,
                "results_summary": {k: len(str(v)) for k, v in results.items()},
                "user_id": current_user["user_id"]
            },
            outcome="success"
        )
        
        system.logger.info(f"Project analysis {analysis_id} completed successfully")
        
    except Exception as e:
        # Mark analysis as failed
        await system.db_manager.execute_query(
            """
            UPDATE project_analyses SET 
                status = :status,
                error = :error,
                completed_at = :completed_at
            WHERE analysis_id = :analysis_id
            """,
            {
                "analysis_id": analysis_id,
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow()
            }
        )
        
        system.logger.error(f"Error running project analysis {analysis_id}: {str(e)}")

# Health Check and Status Endpoints

@router.get("/health", summary="Health Check", description="Check API health status")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@router.get("/status", summary="System Status", description="Get detailed system status")
async def system_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get detailed system status including agent health.
    """
    system = await get_system_components()
    
    try:
        # Check database connection
        db_status = "healthy"
        try:
            await system.db_manager.fetch_one("SELECT 1")
        except Exception:
            db_status = "unhealthy"
        
        # Check cache connection  
        cache_status = "healthy"
        try:
            await system.cache_manager.get("health_check")
        except Exception:
            cache_status = "unhealthy"
        
        # Check agent orchestrator
        agent_status = await system.agent_orchestrator.get_health_status()
        
        # Get system metrics
        active_projects = await system.db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM projects WHERE status IN ('active', 'in_progress')"
        )
        
        active_tasks = await system.db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM agent_tasks WHERE status IN ('assigned', 'in_progress')"
        )
        
        return {
            "status": "healthy" if all([
                db_status == "healthy",
                cache_status == "healthy",
                agent_status.get("status") == "healthy"
            ]) else "degraded",
            "components": {
                "database": db_status,
                "cache": cache_status,
                "agents": agent_status
            },
            "metrics": {
                "active_projects": active_projects["count"] if active_projects else 0,
                "active_tasks": active_tasks["count"] if active_tasks else 0
            },
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        system.logger.error(f"Error checking system status: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }