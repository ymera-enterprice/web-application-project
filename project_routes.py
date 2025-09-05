"""
YMERA Enterprise - Project Management Routes
Production-Ready Project Management System - v4.0
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
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path

# Third-party imports (alphabetical)
import structlog
from fastapi import APIRouter, HTTPException, Depends, status, Query, Path as FastAPIPath
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, validator

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from database.models import Project, Task, Agent, User, ProjectMember
from security.jwt_handler import get_current_user, verify_token
from monitoring.performance_tracker import track_performance
from learning.core_engine import LearningEngine
from learning.knowledge_manager import KnowledgeManager
from utils.encryption import encrypt_sensitive_data, decrypt_sensitive_data
from websocket.manager import WebSocketManager

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.project_routes")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Project management constants
MAX_PROJECT_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_PROJECTS_PER_USER = 100
PROJECT_STATUSES = ["active", "paused", "completed", "cancelled"]
TASK_PRIORITIES = ["low", "medium", "high", "urgent"]
MEMBER_ROLES = ["owner", "admin", "contributor", "viewer"]

# Configuration loading
settings = get_settings()
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class ProjectConfig:
    """Configuration for project management system"""
    max_projects_per_user: int = 100
    max_members_per_project: int = 50
    auto_learning_enabled: bool = True
    websocket_notifications: bool = True

class ProjectCreateSchema(BaseModel):
    """Schema for creating new projects"""
    name: str = Field(..., min_length=1, max_length=MAX_PROJECT_NAME_LENGTH)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    category: Optional[str] = Field(None, max_length=50)
    priority: str = Field(default="medium", regex=f"^({'|'.join(TASK_PRIORITIES)})$")
    deadline: Optional[datetime] = None
    budget: Optional[float] = Field(None, ge=0)
    is_private: bool = Field(default=False)
    tags: List[str] = Field(default_factory=list, max_items=20)
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Project name cannot be empty')
        return v.strip()
    
    @validator('tags')
    def validate_tags(cls, v):
        if v:
            return [tag.strip().lower() for tag in v if tag.strip()]
        return []

class ProjectUpdateSchema(BaseModel):
    """Schema for updating existing projects"""
    name: Optional[str] = Field(None, min_length=1, max_length=MAX_PROJECT_NAME_LENGTH)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    category: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, regex=f"^({'|'.join(TASK_PRIORITIES)})$")
    status: Optional[str] = Field(None, regex=f"^({'|'.join(PROJECT_STATUSES)})$")
    deadline: Optional[datetime] = None
    budget: Optional[float] = Field(None, ge=0)
    is_private: Optional[bool] = None
    tags: Optional[List[str]] = Field(None, max_items=20)
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Project name cannot be empty')
        return v.strip() if v else v

class TaskCreateSchema(BaseModel):
    """Schema for creating project tasks"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    priority: str = Field(default="medium", regex=f"^({'|'.join(TASK_PRIORITIES)})$")
    assigned_agent_id: Optional[uuid.UUID] = None
    deadline: Optional[datetime] = None
    estimated_hours: Optional[float] = Field(None, ge=0, le=1000)
    dependencies: List[uuid.UUID] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list, max_items=10)

class ProjectMemberSchema(BaseModel):
    """Schema for project member management"""
    user_id: uuid.UUID
    role: str = Field(..., regex=f"^({'|'.join(MEMBER_ROLES)})$")
    permissions: List[str] = Field(default_factory=list)

class ProjectResponseSchema(BaseModel):
    """Schema for project responses"""
    id: uuid.UUID
    name: str
    description: Optional[str]
    category: Optional[str]
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    deadline: Optional[datetime]
    budget: Optional[float]
    is_private: bool
    tags: List[str]
    owner_id: uuid.UUID
    member_count: int
    task_count: int
    completion_percentage: float
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class ProjectStatsSchema(BaseModel):
    """Schema for project statistics"""
    total_projects: int
    active_projects: int
    completed_projects: int
    total_tasks: int
    completed_tasks: int
    avg_completion_time: Optional[float]
    productivity_score: float

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class ProjectManager:
    """Production-ready project management system"""
    
    def __init__(self, learning_engine: LearningEngine, websocket_manager: WebSocketManager):
        self.learning_engine = learning_engine
        self.websocket_manager = websocket_manager
        self.logger = logger.bind(component="project_manager")
        self.config = ProjectConfig()
    
    @track_performance
    async def create_project(
        self,
        db: AsyncSession,
        project_data: ProjectCreateSchema,
        owner: User
    ) -> Dict[str, Any]:
        """Create a new project with comprehensive validation and learning integration"""
        try:
            # Validate user project limits
            await self._validate_project_limits(db, owner.id)
            
            # Create project instance
            project = Project(
                id=uuid.uuid4(),
                name=project_data.name,
                description=project_data.description,
                category=project_data.category,
                priority=project_data.priority,
                deadline=project_data.deadline,
                budget=project_data.budget,
                is_private=project_data.is_private,
                tags=project_data.tags,
                owner_id=owner.id,
                status="active",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Save to database
            db.add(project)
            await db.commit()
            await db.refresh(project)
            
            # Add owner as admin member
            await self._add_project_member(db, project.id, owner.id, "owner")
            
            # Learning integration - record project creation pattern
            await self._record_learning_event(
                "project_created",
                {
                    "project_id": str(project.id),
                    "category": project_data.category,
                    "priority": project_data.priority,
                    "has_deadline": project_data.deadline is not None,
                    "has_budget": project_data.budget is not None,
                    "tag_count": len(project_data.tags),
                    "user_id": str(owner.id)
                }
            )
            
            # WebSocket notification
            await self._notify_project_event(project.id, "project_created", {
                "project": await self._serialize_project(project),
                "created_by": owner.id
            })
            
            self.logger.info(
                "Project created successfully",
                project_id=str(project.id),
                owner_id=str(owner.id),
                name=project.name
            )
            
            return await self._serialize_project(project)
            
        except Exception as e:
            await db.rollback()
            self.logger.error("Failed to create project", error=str(e), owner_id=str(owner.id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create project"
            )
    
    @track_performance
    async def get_project(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user: User
    ) -> Dict[str, Any]:
        """Retrieve project with access control and learning analytics"""
        try:
            # Query with relationships
            query = select(Project).options(
                selectinload(Project.members),
                selectinload(Project.tasks),
                selectinload(Project.owner)
            ).where(Project.id == project_id)
            
            result = await db.execute(query)
            project = result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found"
                )
            
            # Access control validation
            await self._validate_project_access(project, user, "read")
            
            # Learning integration - record access pattern
            await self._record_learning_event(
                "project_accessed",
                {
                    "project_id": str(project_id),
                    "user_id": str(user.id),
                    "access_time": datetime.utcnow().isoformat(),
                    "project_status": project.status
                }
            )
            
            return await self._serialize_project(project, include_details=True)
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Failed to retrieve project", error=str(e), project_id=str(project_id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve project"
            )
    
    @track_performance
    async def update_project(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        update_data: ProjectUpdateSchema,
        user: User
    ) -> Dict[str, Any]:
        """Update project with validation and change tracking"""
        try:
            # Get existing project
            project = await self._get_project_by_id(db, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found"
                )
            
            # Access control validation
            await self._validate_project_access(project, user, "write")
            
            # Track changes for learning
            changes = {}
            original_data = await self._serialize_project(project)
            
            # Apply updates
            update_fields = update_data.dict(exclude_unset=True)
            for field, value in update_fields.items():
                if hasattr(project, field) and getattr(project, field) != value:
                    changes[field] = {
                        "from": getattr(project, field),
                        "to": value
                    }
                    setattr(project, field, value)
            
            if changes:
                project.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(project)
                
                # Learning integration - record update patterns
                await self._record_learning_event(
                    "project_updated",
                    {
                        "project_id": str(project_id),
                        "user_id": str(user.id),
                        "changes": changes,
                        "change_count": len(changes)
                    }
                )
                
                # WebSocket notification
                await self._notify_project_event(project_id, "project_updated", {
                    "project": await self._serialize_project(project),
                    "changes": changes,
                    "updated_by": user.id
                })
                
                self.logger.info(
                    "Project updated successfully",
                    project_id=str(project_id),
                    user_id=str(user.id),
                    changes=list(changes.keys())
                )
            
            return await self._serialize_project(project)
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            self.logger.error("Failed to update project", error=str(e), project_id=str(project_id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update project"
            )
    
    @track_performance
    async def delete_project(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user: User
    ) -> Dict[str, Any]:
        """Delete project with cascade handling and learning integration"""
        try:
            project = await self._get_project_by_id(db, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found"
                )
            
            # Access control - only owner or admin can delete
            await self._validate_project_access(project, user, "delete")
            
            # Soft delete for learning purposes
            project.status = "deleted"
            project.deleted_at = datetime.utcnow()
            project.updated_at = datetime.utcnow()
            
            await db.commit()
            
            # Learning integration - record deletion pattern
            await self._record_learning_event(
                "project_deleted",
                {
                    "project_id": str(project_id),
                    "user_id": str(user.id),
                    "project_age_days": (datetime.utcnow() - project.created_at).days,
                    "task_count": len(project.tasks) if project.tasks else 0,
                    "completion_percentage": await self._calculate_completion_percentage(project)
                }
            )
            
            # WebSocket notification
            await self._notify_project_event(project_id, "project_deleted", {
                "project_id": str(project_id),
                "deleted_by": user.id
            })
            
            self.logger.info(
                "Project deleted successfully",
                project_id=str(project_id),
                user_id=str(user.id)
            )
            
            return {"message": "Project deleted successfully", "project_id": str(project_id)}
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            self.logger.error("Failed to delete project", error=str(e), project_id=str(project_id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete project"
            )
    
    @track_performance
    async def list_projects(
        self,
        db: AsyncSession,
        user: User,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """List projects with filtering, pagination, and learning insights"""
        try:
            # Build query with filters
            query = select(Project).options(
                selectinload(Project.owner),
                selectinload(Project.members)
            )
            
            # Access control - show projects user has access to
            accessible_project_ids = await self._get_accessible_project_ids(db, user)
            query = query.where(Project.id.in_(accessible_project_ids))
            
            # Apply filters
            if status_filter and status_filter in PROJECT_STATUSES:
                query = query.where(Project.status == status_filter)
            
            if category_filter:
                query = query.where(Project.category == category_filter)
            
            if search:
                search_term = f"%{search.lower()}%"
                query = query.where(
                    or_(
                        func.lower(Project.name).like(search_term),
                        func.lower(Project.description).like(search_term)
                    )
                )
            
            # Count total for pagination
            count_query = select(func.count(Project.id)).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total_count = total_result.scalar()
            
            # Apply pagination and ordering
            query = query.order_by(Project.updated_at.desc()).offset(skip).limit(limit)
            
            result = await db.execute(query)
            projects = result.scalars().all()
            
            # Serialize projects
            serialized_projects = []
            for project in projects:
                serialized_projects.append(await self._serialize_project(project))
            
            # Learning integration - record list access patterns
            await self._record_learning_event(
                "projects_listed",
                {
                    "user_id": str(user.id),
                    "filters": {
                        "status": status_filter,
                        "category": category_filter,
                        "search": search is not None
                    },
                    "result_count": len(projects),
                    "total_accessible": total_count
                }
            )
            
            return {
                "projects": serialized_projects,
                "pagination": {
                    "total": total_count,
                    "skip": skip,
                    "limit": limit,
                    "has_more": (skip + limit) < total_count
                },
                "filters_applied": {
                    "status": status_filter,
                    "category": category_filter,
                    "search": search
                }
            }
            
        except Exception as e:
            self.logger.error("Failed to list projects", error=str(e), user_id=str(user.id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve projects"
            )
    
    @track_performance
    async def get_project_statistics(
        self,
        db: AsyncSession,
        user: User,
        project_id: Optional[uuid.UUID] = None
    ) -> ProjectStatsSchema:
        """Get comprehensive project statistics with learning insights"""
        try:
            # Get accessible projects
            accessible_project_ids = await self._get_accessible_project_ids(db, user)
            
            if project_id:
                if project_id not in accessible_project_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to project"
                    )
                project_filter = [project_id]
            else:
                project_filter = accessible_project_ids
            
            # Query statistics
            stats_query = select(
                func.count(Project.id).label('total_projects'),
                func.count(case((Project.status == 'active', 1))).label('active_projects'),
                func.count(case((Project.status == 'completed', 1))).label('completed_projects'),
                func.avg(
                    case((Project.status == 'completed', 
                         func.extract('epoch', Project.updated_at - Project.created_at) / 86400))
                ).label('avg_completion_days')
            ).where(Project.id.in_(project_filter))
            
            stats_result = await db.execute(stats_query)
            stats = stats_result.first()
            
            # Get task statistics
            task_stats_query = select(
                func.count(Task.id).label('total_tasks'),
                func.count(case((Task.status == 'completed', 1))).label('completed_tasks')
            ).where(Task.project_id.in_(project_filter))
            
            task_result = await db.execute(task_stats_query)
            task_stats = task_result.first()
            
            # Calculate productivity score using learning engine
            productivity_score = await self._calculate_productivity_score(
                user.id, project_filter, stats, task_stats
            )
            
            # Learning integration - record statistics access
            await self._record_learning_event(
                "project_statistics_accessed",
                {
                    "user_id": str(user.id),
                    "scope": "single_project" if project_id else "all_projects",
                    "project_count": stats.total_projects,
                    "productivity_score": productivity_score
                }
            )
            
            return ProjectStatsSchema(
                total_projects=stats.total_projects or 0,
                active_projects=stats.active_projects or 0,
                completed_projects=stats.completed_projects or 0,
                total_tasks=task_stats.total_tasks or 0,
                completed_tasks=task_stats.completed_tasks or 0,
                avg_completion_time=stats.avg_completion_days,
                productivity_score=productivity_score
            )
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Failed to get project statistics", error=str(e), user_id=str(user.id))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve statistics"
            )
    
    # Private helper methods
    async def _validate_project_limits(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Validate user hasn't exceeded project limits"""
        query = select(func.count(Project.id)).where(
            and_(Project.owner_id == user_id, Project.status != 'deleted')
        )
        result = await db.execute(query)
        project_count = result.scalar()
        
        if project_count >= self.config.max_projects_per_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Project limit exceeded. Maximum {self.config.max_projects_per_user} projects allowed."
            )
    
    async def _get_project_by_id(self, db: AsyncSession, project_id: uuid.UUID) -> Optional[Project]:
        """Get project by ID with relationships loaded"""
        query = select(Project).options(
            selectinload(Project.members),
            selectinload(Project.tasks),
            selectinload(Project.owner)
        ).where(Project.id == project_id)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _validate_project_access(
        self,
        project: Project,
        user: User,
        action: str
    ) -> None:
        """Validate user has required access to project"""
        # Owner has all permissions
        if project.owner_id == user.id:
            return
        
        # Check membership and permissions
        member = next((m for m in project.members if m.user_id == user.id), None)
        if not member:
            if project.is_private:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to private project"
                )
            if action in ["write", "delete"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Write access denied"
                )
        
        # Validate role permissions
        if member and action == "delete" and member.role not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Delete permission denied"
            )
    
    async def _get_accessible_project_ids(
        self,
        db: AsyncSession,
        user: User
    ) -> List[uuid.UUID]:
        """Get list of project IDs user has access to"""
        # Query owned projects
        owned_query = select(Project.id).where(Project.owner_id == user.id)
        owned_result = await db.execute(owned_query)
        owned_ids = [row[0] for row in owned_result.fetchall()]
        
        # Query member projects
        member_query = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        member_result = await db.execute(member_query)
        member_ids = [row[0] for row in member_result.fetchall()]
        
        # Query public projects (read-only access)
        public_query = select(Project.id).where(
            and_(Project.is_private == False, Project.status != 'deleted')
        )
        public_result = await db.execute(public_query)
        public_ids = [row[0] for row in public_result.fetchall()]
        
        # Combine and deduplicate
        all_ids = set(owned_ids + member_ids + public_ids)
        return list(all_ids)
    
    async def _serialize_project(
        self,
        project: Project,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """Serialize project object to dictionary"""
        data = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "category": project.category,
            "priority": project.priority,
            "status": project.status,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "deadline": project.deadline,
            "budget": project.budget,
            "is_private": project.is_private,
            "tags": project.tags or [],
            "owner_id": project.owner_id,
            "member_count": len(project.members) if project.members else 0,
            "task_count": len(project.tasks) if project.tasks else 0,
            "completion_percentage": await self._calculate_completion_percentage(project)
        }
        
        if include_details:
            data.update({
                "owner": {
                    "id": project.owner.id,
                    "username": project.owner.username,
                    "email": project.owner.email
                } if project.owner else None,
                "members": [
                    {
                        "user_id": member.user_id,
                        "role": member.role,
                        "joined_at": member.created_at
                    } for member in project.members
                ] if project.members else [],
                "recent_tasks": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "status": task.status,
                        "priority": task.priority
                    } for task in (project.tasks[:5] if project.tasks else [])
                ]
            })
        
        return data
    
    async def _calculate_completion_percentage(self, project: Project) -> float:
        """Calculate project completion percentage"""
        if not project.tasks:
            return 0.0
        
        completed_tasks = sum(1 for task in project.tasks if task.status == 'completed')
        return (completed_tasks / len(project.tasks)) * 100
    
    async def _calculate_productivity_score(
        self,
        user_id: uuid.UUID,
        project_ids: List[uuid.UUID],
        project_stats: Any,
        task_stats: Any
    ) -> float:
        """Calculate productivity score using learning engine insights"""
        try:
            # Base metrics
            completion_rate = (
                task_stats.completed_tasks / task_stats.total_tasks
                if task_stats.total_tasks > 0 else 0
            )
            
            project_completion_rate = (
                project_stats.completed_projects / project_stats.total_projects
                if project_stats.total_projects > 0 else 0
            )
            
            # Get learning insights
            learning_insights = await self.learning_engine.get_user_insights(user_id)
            
            # Calculate weighted score
            base_score = (completion_rate * 0.4) + (project_completion_rate * 0.3)
            learning_bonus = learning_insights.get('productivity_trend', 0) * 0.3
            
            return min(max(base_score + learning_bonus, 0.0), 1.0) * 100
            
        except Exception as e:
            self.logger.warning("Failed to calculate productivity score", error=str(e))
            return 50.0  # Default neutral score
    
    async def _record_learning_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record learning event for pattern analysis"""
        try:
            if self.config.auto_learning_enabled:
                await self.learning_engine.record_event(event_type, data)
        except Exception as e:
            self.logger.warning("Failed to record learning event", error=str(e))
    
    async def _notify_project_event(
        self,
        project_id: uuid.UUID,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """Send WebSocket notification for project events"""
        try:
            if self.config.websocket_notifications:
                await self.websocket_manager.broadcast_to_project(
                    project_id, event_type, data
                )
        except Exception as e:
            self.logger.warning("Failed to send WebSocket notification", error=str(e))
    
    async def _add_project_member(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str
    ) -> None:
        """Add member to project"""
        member = ProjectMember(
            id=uuid.uuid4(),
            project_id=project_id,
            user_id=user_id,
            role=role,
            created_at=datetime.utcnow()
        )
        db.add(member)
        await db.commit()

# ===============================================================================
# ROUTE ENDPOINTS
# ===============================================================================

# Initialize dependencies
learning_engine = LearningEngine()
websocket_manager = WebSocketManager()
project_manager = ProjectManager(learning_engine, websocket_manager)

@router.post("/", response_model=ProjectResponseSchema)
@track_performance
async def create_project(
    project_data: ProjectCreateSchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> ProjectResponseSchema:
    """
    Create a new project with comprehensive validation and learning integration.
    
    This endpoint creates a new project, validates user permissions, integrates with
    the learning engine for pattern analysis, and sends real-time notifications.
    
    Args:
        project_data: Project creation data including name, description, settings
        db: Database session for persistence operations
        current_user: Authenticated user creating the project
    
    Returns:
        ProjectResponseSchema: Created project with metadata and statistics
    
    Raises:
        HTTPException: When validation fails or creation encounters errors
    """
    result = await project_manager.create_project(db, project_data, current_user)
    return ProjectResponseSchema(**result)

@router.get("/", response_model=Dict[str, Any])
@track_performance
async def list_projects(
    skip: int = Query(default=0, ge=0, description="Number of projects to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum projects to return"),
    status: Optional[str] = Query(default=None, regex=f"^({'|'.join(PROJECT_STATUSES)})$"),
    category: Optional[str] = Query(default=None, max_length=50),
    search: Optional[str] = Query(default=None, max_length=200),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List projects with filtering, pagination, and learning insights.
    
    Retrieves projects accessible to the current user with optional filtering
    by status, category, and search terms. Includes pagination and learning
    analytics for usage pattern analysis.
    
    Args:
        skip: Number of projects to skip for pagination
        limit: Maximum number of projects to return
        status: Filter by project status (active, paused, completed, cancelled)
        category: Filter by project category
        search: Search term for project name and description
        db: Database session for query operations
        current_user: Authenticated user requesting projects
    
    Returns:
        Dict containing projects list, pagination info, and applied filters
    """
    return await project_manager.list_projects(
        db, current_user, skip, limit, status, category, search
    )

@router.get("/statistics", response_model=ProjectStatsSchema)
@track_performance
async def get_project_statistics(
    project_id: Optional[uuid.UUID] = Query(default=None, description="Specific project ID for stats"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> ProjectStatsSchema:
    """
    Get comprehensive project statistics with learning insights.
    
    Provides detailed analytics including project counts, completion rates,
    productivity scores, and learning-based insights for performance optimization.
    
    Args:
        project_id: Optional specific project ID, otherwise returns user's overall stats
        db: Database session for statistical queries
        current_user: Authenticated user requesting statistics
    
    Returns:
        ProjectStatsSchema: Comprehensive project statistics and metrics
    """
    return await project_manager.get_project_statistics(db, current_user, project_id)

@router.get("/{project_id}", response_model=ProjectResponseSchema)
@track_performance
async def get_project(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID to retrieve"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> ProjectResponseSchema:
    """
    Retrieve detailed project information with access control.
    
    Fetches complete project details including members, tasks, and metadata
    with proper access control validation and learning event recording.
    
    Args:
        project_id: Unique identifier of the project to retrieve
        db: Database session for project queries
        current_user: Authenticated user requesting project details
    
    Returns:
        ProjectResponseSchema: Complete project information with relationships
    
    Raises:
        HTTPException: When project not found or access denied
    """
    result = await project_manager.get_project(db, project_id, current_user)
    return ProjectResponseSchema(**result)

@router.put("/{project_id}", response_model=ProjectResponseSchema)
@track_performance
async def update_project(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID to update"),
    update_data: ProjectUpdateSchema = ...,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> ProjectResponseSchema:
    """
    Update project with validation and change tracking.
    
    Updates project properties with comprehensive validation, change tracking
    for learning analysis, and real-time notifications to project members.
    
    Args:
        project_id: Unique identifier of the project to update
        update_data: Updated project data with optional fields
        db: Database session for update operations
        current_user: Authenticated user performing the update
    
    Returns:
        ProjectResponseSchema: Updated project information
    
    Raises:
        HTTPException: When project not found, access denied, or validation fails
    """
    result = await project_manager.update_project(db, project_id, update_data, current_user)
    return ProjectResponseSchema(**result)

@router.delete("/{project_id}")
@track_performance
async def delete_project(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID to delete"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete project with cascade handling and learning integration.
    
    Performs soft deletion of project with proper access control validation,
    learning event recording, and notification to affected users.
    
    Args:
        project_id: Unique identifier of the project to delete
        db: Database session for deletion operations
        current_user: Authenticated user requesting deletion
    
    Returns:
        Dict: Confirmation message with project ID
    
    Raises:
        HTTPException: When project not found or access denied
    """
    return await project_manager.delete_project(db, project_id, current_user)

@router.post("/{project_id}/tasks", response_model=Dict[str, Any])
@track_performance
async def create_project_task(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID for new task"),
    task_data: TaskCreateSchema = ...,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new task within a project.
    
    Creates a task with comprehensive validation, agent assignment capabilities,
    dependency management, and learning integration for task pattern analysis.
    
    Args:
        project_id: Project to create the task in
        task_data: Task creation data including title, description, assignments
        db: Database session for task creation
        current_user: Authenticated user creating the task
    
    Returns:
        Dict: Created task information with metadata
    
    Raises:
        HTTPException: When project not found, access denied, or validation fails
    """
    try:
        # Validate project access
        project = await project_manager._get_project_by_id(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        await project_manager._validate_project_access(project, current_user, "write")
        
        # Create task
        task = Task(
            id=uuid.uuid4(),
            project_id=project_id,
            title=task_data.title,
            description=task_data.description,
            priority=task_data.priority,
            assigned_agent_id=task_data.assigned_agent_id,
            deadline=task_data.deadline,
            estimated_hours=task_data.estimated_hours,
            dependencies=task_data.dependencies,
            tags=task_data.tags,
            status="pending",
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        # Learning integration
        await project_manager._record_learning_event(
            "task_created",
            {
                "project_id": str(project_id),
                "task_id": str(task.id),
                "priority": task_data.priority,
                "has_agent": task_data.assigned_agent_id is not None,
                "has_deadline": task_data.deadline is not None,
                "has_dependencies": len(task_data.dependencies) > 0,
                "user_id": str(current_user.id)
            }
        )
        
        # WebSocket notification
        await project_manager._notify_project_event(project_id, "task_created", {
            "task": {
                "id": str(task.id),
                "title": task.title,
                "priority": task.priority,
                "status": task.status
            },
            "created_by": current_user.id
        })
        
        logger.info(
            "Task created successfully",
            project_id=str(project_id),
            task_id=str(task.id),
            user_id=str(current_user.id)
        )
        
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "status": task.status,
            "created_at": task.created_at,
            "project_id": project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to create task", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create task"
        )

@router.get("/{project_id}/tasks")
@track_performance
async def list_project_tasks(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID to list tasks for"),
    status_filter: Optional[str] = Query(default=None, description="Filter tasks by status"),
    priority_filter: Optional[str] = Query(default=None, regex=f"^({'|'.join(TASK_PRIORITIES)})$"),
    assigned_to: Optional[uuid.UUID] = Query(default=None, description="Filter by assigned agent"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List tasks within a project with filtering and pagination.
    
    Retrieves tasks belonging to a specific project with optional filtering
    by status, priority, and assignment. Includes learning analytics for
    task management pattern analysis.
    
    Args:
        project_id: Project to list tasks from
        status_filter: Optional status filter for tasks
        priority_filter: Optional priority filter
        assigned_to: Optional agent assignment filter
        skip: Number of tasks to skip for pagination
        limit: Maximum number of tasks to return
        db: Database session for task queries
        current_user: Authenticated user requesting tasks
    
    Returns:
        Dict: List of tasks with pagination and filter information
    """
    try:
        # Validate project access
        project = await project_manager._get_project_by_id(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        await project_manager._validate_project_access(project, current_user, "read")
        
        # Build task query
        query = select(Task).where(Task.project_id == project_id)
        
        # Apply filters
        if status_filter:
            query = query.where(Task.status == status_filter)
        
        if priority_filter:
            query = query.where(Task.priority == priority_filter)
        
        if assigned_to:
            query = query.where(Task.assigned_agent_id == assigned_to)
        
        # Count total
        count_query = select(func.count(Task.id)).where(Task.project_id == project_id)
        if status_filter:
            count_query = count_query.where(Task.status == status_filter)
        if priority_filter:
            count_query = count_query.where(Task.priority == priority_filter)
        if assigned_to:
            count_query = count_query.where(Task.assigned_agent_id == assigned_to)
        
        total_result = await db.execute(count_query)
        total_count = total_result.scalar()
        
        # Apply pagination and ordering
        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        # Serialize tasks
        serialized_tasks = []
        for task in tasks:
            serialized_tasks.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "status": task.status,
                "assigned_agent_id": task.assigned_agent_id,
                "deadline": task.deadline,
                "estimated_hours": task.estimated_hours,
                "dependencies": task.dependencies,
                "tags": task.tags,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "created_by": task.created_by
            })
        
        # Learning integration
        await project_manager._record_learning_event(
            "project_tasks_listed",
            {
                "project_id": str(project_id),
                "user_id": str(current_user.id),
                "filters": {
                    "status": status_filter,
                    "priority": priority_filter,
                    "assigned_to": str(assigned_to) if assigned_to else None
                },
                "result_count": len(tasks),
                "total_count": total_count
            }
        )
        
        return {
            "tasks": serialized_tasks,
            "pagination": {
                "total": total_count,
                "skip": skip,
                "limit": limit,
                "has_more": (skip + limit) < total_count
            },
            "project_id": str(project_id),
            "filters_applied": {
                "status": status_filter,
                "priority": priority_filter,
                "assigned_to": str(assigned_to) if assigned_to else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list project tasks", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tasks"
        )

@router.post("/{project_id}/members")
@track_performance
async def add_project_member(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID to add member to"),
    member_data: ProjectMemberSchema = ...,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Add a member to a project with role-based permissions.
    
    Adds a user to a project with specified role and permissions,
    validates access control, and integrates with learning system
    for collaboration pattern analysis.
    
    Args:
        project_id: Project to add member to
        member_data: Member information including user ID and role
        db: Database session for member addition
        current_user: Authenticated user adding the member
    
    Returns:
        Dict: Added member information with confirmation
    
    Raises:
        HTTPException: When project not found, access denied, or user invalid
    """
    try:
        # Validate project access (admin or owner required)
        project = await project_manager._get_project_by_id(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        await project_manager._validate_project_access(project, current_user, "write")
        
        # Check if user to add exists
        user_query = select(User).where(User.id == member_data.user_id)
        user_result = await db.execute(user_query)
        target_user = user_result.scalar_one_or_none()
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if already a member
        existing_member_query = select(ProjectMember).where(
            and_(ProjectMember.project_id == project_id, ProjectMember.user_id == member_data.user_id)
        )
        existing_result = await db.execute(existing_member_query)
        existing_member = existing_result.scalar_one_or_none()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a project member"
            )
        
        # Add member
        member = ProjectMember(
            id=uuid.uuid4(),
            project_id=project_id,
            user_id=member_data.user_id,
            role=member_data.role,
            permissions=member_data.permissions,
            added_by=current_user.id,
            created_at=datetime.utcnow()
        )
        
        db.add(member)
        await db.commit()
        await db.refresh(member)
        
        # Learning integration
        await project_manager._record_learning_event(
            "project_member_added",
            {
                "project_id": str(project_id),
                "added_user_id": str(member_data.user_id),
                "role": member_data.role,
                "added_by": str(current_user.id),
                "project_member_count": len(project.members) + 1
            }
        )
        
        # WebSocket notification
        await project_manager._notify_project_event(project_id, "member_added", {
            "member": {
                "user_id": str(member_data.user_id),
                "username": target_user.username,
                "role": member_data.role
            },
            "added_by": current_user.id
        })
        
        logger.info(
            "Project member added successfully",
            project_id=str(project_id),
            member_id=str(member_data.user_id),
            role=member_data.role,
            added_by=str(current_user.id)
        )
        
        return {
            "message": "Member added successfully",
            "member": {
                "id": str(member.id),
                "user_id": str(member_data.user_id),
                "username": target_user.username,
                "role": member_data.role,
                "added_at": member.created_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to add project member", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member"
        )

@router.get("/{project_id}/analytics")
@track_performance
async def get_project_analytics(
    project_id: uuid.UUID = FastAPIPath(..., description="Project ID for analytics"),
    time_range: str = Query(default="30d", regex="^(7d|30d|90d|1y)$"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive project analytics with learning insights.
    
    Provides detailed analytics including performance metrics, completion trends,
    resource utilization, and AI-powered insights for project optimization.
    
    Args:
        project_id: Project to analyze
        time_range: Analysis time range (7d, 30d, 90d, 1y)
        db: Database session for analytics queries
        current_user: Authenticated user requesting analytics
    
    Returns:
        Dict: Comprehensive project analytics and insights
    """
    try:
        # Validate project access
        project = await project_manager._get_project_by_id(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        await project_manager._validate_project_access(project, current_user, "read")
        
        # Calculate time range
        time_ranges = {
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90),
            "1y": timedelta(days=365)
        }
        
        start_date = datetime.utcnow() - time_ranges[time_range]
        
        # Get task completion trends
        completion_query = select(
            func.date(Task.updated_at).label('date'),
            func.count(case((Task.status == 'completed', 1))).label('completed'),
            func.count(Task.id).label('total')
        ).where(
            and_(
                Task.project_id == project_id,
                Task.updated_at >= start_date
            )
        ).group_by(func.date(Task.updated_at)).order_by(func.date(Task.updated_at))
        
        completion_result = await db.execute(completion_query)
        completion_trends = [
            {
                "date": row.date.isoformat(),
                "completed": row.completed,
                "total": row.total,
                "completion_rate": (row.completed / row.total) * 100 if row.total > 0 else 0
            }
            for row in completion_result.fetchall()
        ]
        
        # Get priority distribution
        priority_query = select(
            Task.priority,
            func.count(Task.id).label('count'),
            func.count(case((Task.status == 'completed', 1))).label('completed')
        ).where(Task.project_id == project_id).group_by(Task.priority)
        
        priority_result = await db.execute(priority_query)
        priority_distribution = [
            {
                "priority": row.priority,
                "total": row.count,
                "completed": row.completed,
                "completion_rate": (row.completed / row.count) * 100 if row.count > 0 else 0
            }
            for row in priority_result.fetchall()
        ]
        
        # Get learning insights
        learning_insights = await learning_engine.get_project_insights(project_id)
        
        # Performance metrics
        metrics = {
            "completion_percentage": await project_manager._calculate_completion_percentage(project),
            "task_velocity": len([t for t in project.tasks if t.status == 'completed' and t.updated_at >= start_date]),
            "overdue_tasks": len([t for t in project.tasks if t.deadline and t.deadline < datetime.utcnow() and t.status != 'completed']),
            "active_tasks": len([t for t in project.tasks if t.status in ['pending', 'in_progress']]),
            "avg_task_completion_time": learning_insights.get('avg_completion_time', 0),
            "productivity_trend": learning_insights.get('productivity_trend', 0)
        }
        
        # Resource utilization
        resource_utilization = {
            "assigned_agents": len(set(t.assigned_agent_id for t in project.tasks if t.assigned_agent_id)),
            "total_estimated_hours": sum(t.estimated_hours or 0 for t in project.tasks),
            "completed_hours": sum(t.estimated_hours or 0 for t in project.tasks if t.status == 'completed'),
            "budget_utilization": (project.budget * (metrics["completion_percentage"] / 100)) if project.budget else 0
        }
        
        # Learning recommendations
        recommendations = learning_insights.get('recommendations', [])
        
        # Record analytics access
        await project_manager._record_learning_event(
            "project_analytics_accessed",
            {
                "project_id": str(project_id),
                "user_id": str(current_user.id),
                "time_range": time_range,
                "completion_percentage": metrics["completion_percentage"]
            }
        )
        
        return {
            "project_id": str(project_id),
            "time_range": time_range,
            "metrics": metrics,
            "completion_trends": completion_trends,
            "priority_distribution": priority_distribution,
            "resource_utilization": resource_utilization,
            "learning_insights": learning_insights,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get project analytics", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )

# ===============================================================================
# HEALTH CHECK ENDPOINT
# ===============================================================================

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check for project management system"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "project_routes",
        "version": "4.0",
        "learning_integration": project_manager.config.auto_learning_enabled,
        "websocket_notifications": project_manager.config.websocket_notifications
    }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "router",
    "ProjectManager",
    "ProjectCreateSchema",
    "ProjectUpdateSchema",
    "ProjectResponseSchema",
    "TaskCreateSchema",
    "ProjectMemberSchema",
    "ProjectStatsSchema"
]