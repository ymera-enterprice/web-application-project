"""
YMERA Enterprise Multi-Agent System
Enhancement API Routes - Production Ready
Handles code enhancement, optimization, and improvement workflows
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Path, Body
from fastapi.security import HTTPBearer
from typing import Any, Dict, List, Optional, Union
import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
import json

# Pydantic models
from pydantic import BaseModel, Field, validator
from pydantic.types import UUID4

# Core system dependencies
from ymera_core.config import ConfigManager
from ymera_core.database.manager import DatabaseManager
from ymera_core.security.auth_manager import AuthManager, get_current_active_user
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.exceptions import YMERAException

# Agent system dependencies  
from ymera_agents.orchestrator import AgentOrchestrator
from ymera_agents.core.enhancement_agent import EnhancementAgent
from ymera_agents.core.analysis_agent import AnalysisAgent
from ymera_agents.core.validation_agent import ValidationAgent
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.communication.message_bus import MessageBus

# Service dependencies
from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_services.code_analysis.quality_analyzer import CodeQualityAnalyzer
from ymera_services.github.repository_analyzer import GitHubRepositoryAnalyzer
from ymera_services.security.vulnerability_scanner import VulnerabilityScanner

# Response models
from ymera_api.response_models import (
    APIResponse, PaginatedResponse, TaskResponse
)

# Authentication
security = HTTPBearer()
router = APIRouter()

# Enums
class EnhancementType(str, Enum):
    PERFORMANCE = "performance"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    READABILITY = "readability"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    BEST_PRACTICES = "best_practices"
    CODE_STYLE = "code_style"
    ERROR_HANDLING = "error_handling"

class EnhancementPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class EnhancementStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ANALYZING = "analyzing"
    ENHANCING = "enhancing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class LLMProvider(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GROQ = "groq"
    DEEPSEEK = "deepseek"

# Request Models
class CodeEnhancementRequest(BaseModel):
    """Request model for code enhancement"""
    code: str = Field(..., description="Source code to enhance", min_length=1)
    language: str = Field(..., description="Programming language", regex="^[a-zA-Z+#]+$")
    enhancement_types: List[EnhancementType] = Field(
        default=[EnhancementType.PERFORMANCE, EnhancementType.MAINTAINABILITY],
        description="Types of enhancements to apply"
    )
    priority: EnhancementPriority = Field(
        default=EnhancementPriority.MEDIUM,
        description="Enhancement priority level"
    )
    context: Optional[str] = Field(None, description="Additional context for enhancement")
    constraints: Optional[List[str]] = Field(None, description="Enhancement constraints")
    target_frameworks: Optional[List[str]] = Field(None, description="Target frameworks/libraries")
    preferred_llm: Optional[LLMProvider] = Field(None, description="Preferred LLM provider")
    apply_learning: bool = Field(True, description="Apply learning engine insights")
    generate_tests: bool = Field(True, description="Generate unit tests for enhanced code")
    include_documentation: bool = Field(True, description="Include inline documentation")

    @validator('code')
    def validate_code(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Code cannot be empty')
        if len(v) > 1000000:  # 1MB limit
            raise ValueError('Code exceeds maximum size limit')
        return v

class RepositoryEnhancementRequest(BaseModel):
    """Request model for repository enhancement"""
    repository_url: str = Field(..., description="GitHub repository URL")
    branch: str = Field(default="main", description="Branch to enhance")
    file_patterns: Optional[List[str]] = Field(
        None, 
        description="File patterns to include (e.g., ['*.py', '*.js'])"
    )
    exclude_patterns: Optional[List[str]] = Field(
        None,
        description="File patterns to exclude"
    )
    enhancement_types: List[EnhancementType] = Field(
        default=[EnhancementType.PERFORMANCE, EnhancementType.SECURITY],
        description="Types of enhancements to apply"
    )
    priority: EnhancementPriority = Field(
        default=EnhancementPriority.MEDIUM,
        description="Enhancement priority level"
    )
    max_files: int = Field(default=50, ge=1, le=500, description="Maximum files to process")
    create_pull_request: bool = Field(True, description="Create pull request with enhancements")
    apply_learning: bool = Field(True, description="Apply learning engine insights")
    preferred_llm: Optional[LLMProvider] = Field(None, description="Preferred LLM provider")

class BulkEnhancementRequest(BaseModel):
    """Request model for bulk code enhancement"""
    files: List[Dict[str, Any]] = Field(
        ..., 
        description="List of files with code content",
        min_items=1,
        max_items=100
    )
    enhancement_types: List[EnhancementType] = Field(
        default=[EnhancementType.PERFORMANCE],
        description="Types of enhancements to apply"
    )
    priority: EnhancementPriority = Field(
        default=EnhancementPriority.MEDIUM,
        description="Enhancement priority level"
    )
    parallel_processing: bool = Field(True, description="Enable parallel processing")
    apply_learning: bool = Field(True, description="Apply learning engine insights")
    preferred_llm: Optional[LLMProvider] = Field(None, description="Preferred LLM provider")

    @validator('files')
    def validate_files(cls, v):
        for file_data in v:
            if 'content' not in file_data or 'filename' not in file_data:
                raise ValueError('Each file must have content and filename')
            if len(file_data['content']) > 500000:  # 500KB per file
                raise ValueError(f'File {file_data["filename"]} exceeds size limit')
        return v

class EnhancementFeedbackRequest(BaseModel):
    """Request model for enhancement feedback"""
    enhancement_id: UUID4 = Field(..., description="Enhancement task ID")
    rating: int = Field(..., ge=1, le=5, description="Enhancement quality rating (1-5)")
    feedback: Optional[str] = Field(None, description="Detailed feedback text")
    applied_suggestions: List[str] = Field(
        default=[], 
        description="List of applied suggestion IDs"
    )
    rejected_suggestions: List[str] = Field(
        default=[],
        description="List of rejected suggestion IDs"
    )
    improvement_notes: Optional[str] = Field(
        None, 
        description="Notes for future improvements"
    )

# Response Models
class EnhancementSuggestion(BaseModel):
    """Individual enhancement suggestion"""
    id: str = Field(..., description="Suggestion unique identifier")
    type: EnhancementType = Field(..., description="Enhancement type")
    priority: EnhancementPriority = Field(..., description="Suggestion priority")
    title: str = Field(..., description="Enhancement title")
    description: str = Field(..., description="Detailed description")
    original_code: str = Field(..., description="Original code snippet")
    enhanced_code: str = Field(..., description="Enhanced code snippet")
    explanation: str = Field(..., description="Enhancement explanation")
    benefits: List[str] = Field(..., description="Expected benefits")
    potential_risks: List[str] = Field(default=[], description="Potential risks")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="AI confidence score")
    estimated_impact: str = Field(..., description="Estimated impact level")
    line_numbers: Optional[List[int]] = Field(None, description="Affected line numbers")
    dependencies: Optional[List[str]] = Field(None, description="Required dependencies")

class EnhancementResult(BaseModel):
    """Enhancement result model"""
    enhancement_id: UUID4 = Field(..., description="Enhancement task ID")
    status: EnhancementStatus = Field(..., description="Enhancement status")
    original_code: str = Field(..., description="Original code")
    enhanced_code: Optional[str] = Field(None, description="Enhanced code")
    suggestions: List[EnhancementSuggestion] = Field(default=[], description="Enhancement suggestions")
    metrics: Dict[str, Any] = Field(default={}, description="Quality metrics comparison")
    test_code: Optional[str] = Field(None, description="Generated test code")
    documentation: Optional[str] = Field(None, description="Generated documentation")
    processing_time: float = Field(..., description="Processing time in seconds")
    tokens_used: Dict[str, int] = Field(default={}, description="Token usage by provider")
    learning_applied: bool = Field(default=False, description="Whether learning insights were applied")
    validation_results: Optional[Dict[str, Any]] = Field(None, description="Validation results")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

class RepositoryEnhancementResult(BaseModel):
    """Repository enhancement result model"""
    enhancement_id: UUID4 = Field(..., description="Enhancement task ID")
    repository_url: str = Field(..., description="Repository URL")
    branch: str = Field(..., description="Target branch")
    status: EnhancementStatus = Field(..., description="Enhancement status")
    files_processed: int = Field(..., description="Number of files processed")
    total_suggestions: int = Field(..., description="Total enhancement suggestions")
    file_results: List[Dict[str, Any]] = Field(default=[], description="Per-file results")
    pull_request_url: Optional[str] = Field(None, description="Created pull request URL")
    summary: str = Field(..., description="Enhancement summary")
    metrics_improvement: Dict[str, Any] = Field(default={}, description="Overall metrics improvement")
    processing_time: float = Field(..., description="Total processing time")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

class EnhancementStats(BaseModel):
    """Enhancement statistics model"""
    total_enhancements: int = Field(..., description="Total enhancements performed")
    completed_enhancements: int = Field(..., description="Completed enhancements")
    failed_enhancements: int = Field(..., description="Failed enhancements")
    average_processing_time: float = Field(..., description="Average processing time")
    popular_enhancement_types: List[Dict[str, Any]] = Field(..., description="Popular enhancement types")
    success_rate: float = Field(..., description="Success rate percentage")
    total_tokens_used: int = Field(..., description="Total tokens consumed")
    learning_accuracy: float = Field(..., description="Learning engine accuracy")
    user_satisfaction: float = Field(..., description="Average user satisfaction score")

# Dependency injection
async def get_enhancement_agent() -> EnhancementAgent:
    """Get enhancement agent instance"""
    # This would be injected from the main system
    from main import system
    return system.agents.get('enhancement')

async def get_learning_engine() -> LearningEngine:
    """Get learning engine instance"""
    from main import system
    return system.learning_engine

async def get_orchestrator() -> AgentOrchestrator:
    """Get agent orchestrator instance"""
    from main import system
    return system.agent_orchestrator

async def get_ai_manager() -> MultiLLMManager:
    """Get AI manager instance"""
    from main import system
    return system.llm_manager

async def get_cache_manager() -> RedisCacheManager:
    """Get cache manager instance"""
    from main import system
    return system.cache_manager

async def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    from main import system
    return system.db_manager

async def get_logger() -> StructuredLogger:
    """Get structured logger instance"""
    from main import system
    return system.logger

# Routes

@router.post(
    "/code",
    response_model=APIResponse[EnhancementResult],
    summary="Enhance Code",
    description="Enhance a single code snippet with AI-powered suggestions and improvements"
)
async def enhance_code(
    request: CodeEnhancementRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user),
    learning_engine: LearningEngine = Depends(get_learning_engine),
    db_manager: DatabaseManager = Depends(get_db_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Submit feedback for enhancement results to improve the learning engine.
    
    Feedback is used to:
    - Improve future enhancement suggestions
    - Train the learning engine
    - Optimize AI model selection
    - Enhance user experience personalization
    """
    try:
        logger.info(
            "Enhancement feedback submitted",
            extra={
                "enhancement_id": str(feedback.enhancement_id),
                "user_id": current_user["id"],
                "rating": feedback.rating,
                "applied_count": len(feedback.applied_suggestions),
                "rejected_count": len(feedback.rejected_suggestions)
            }
        )
        
        # Verify enhancement exists and belongs to user
        async with db_manager.get_session() as session:
            enhancement = await db_manager.get_enhancement_result(
                session,
                feedback.enhancement_id,
                user_id=current_user["id"]
            )
            
            if not enhancement:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Enhancement not found or access denied"
                )
        
        # Process feedback through learning engine
        feedback_data = {
            "enhancement_id": str(feedback.enhancement_id),
            "user_id": current_user["id"],
            "rating": feedback.rating,
            "feedback_text": feedback.feedback,
            "applied_suggestions": feedback.applied_suggestions,
            "rejected_suggestions": feedback.rejected_suggestions,
            "improvement_notes": feedback.improvement_notes,
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        # Submit to learning engine in background
        background_tasks.add_task(
            learning_engine.process_enhancement_feedback,
            feedback_data,
            enhancement
        )
        
        # Store feedback in database
        background_tasks.add_task(
            db_manager.store_enhancement_feedback,
            feedback_data
        )
        
        return APIResponse(
            success=True,
            data={"feedback_id": str(uuid.uuid4()), "status": "processed"},
            message="Feedback submitted successfully and will be processed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to submit enhancement feedback",
            extra={
                "enhancement_id": str(feedback.enhancement_id),
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )

@router.get(
    "/history",
    response_model=PaginatedResponse[EnhancementResult],
    summary="Get Enhancement History",
    description="Retrieve user's enhancement history with pagination"
)
async def get_enhancement_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    enhancement_type: Optional[EnhancementType] = Query(None, description="Filter by enhancement type"),
    status: Optional[EnhancementStatus] = Query(None, description="Filter by status"),
    language: Optional[str] = Query(None, description="Filter by programming language"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    current_user: dict = Depends(get_current_active_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Retrieve user's enhancement history with comprehensive filtering and pagination.
    
    Supports filtering by:
    - Enhancement type
    - Status
    - Programming language  
    - Date range
    - Search terms
    """
    try:
        filters = {
            "user_id": current_user["id"],
            "enhancement_type": enhancement_type.value if enhancement_type else None,
            "status": status.value if status else None,
            "language": language,
            "start_date": start_date,
            "end_date": end_date
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        async with db_manager.get_session() as session:
            total_count, results = await db_manager.get_enhancements_paginated(
                session,
                page=page,
                limit=limit,
                filters=filters
            )
            
            enhancement_results = [EnhancementResult(**result) for result in results]
            
            return PaginatedResponse(
                items=enhancement_results,
                total=total_count,
                page=page,
                limit=limit,
                pages=((total_count - 1) // limit) + 1 if total_count > 0 else 0
            )
            
    except Exception as e:
        logger.error(
            "Failed to retrieve enhancement history",
            extra={
                "error": str(e),
                "user_id": current_user["id"],
                "filters": filters
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve enhancement history"
        )

@router.get(
    "/stats",
    response_model=APIResponse[EnhancementStats],
    summary="Get Enhancement Statistics",
    description="Retrieve comprehensive enhancement statistics and insights"
)
async def get_enhancement_statistics(
    current_user: dict = Depends(get_current_active_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    learning_engine: LearningEngine = Depends(get_learning_engine),
    cache_manager: RedisCacheManager = Depends(get_cache_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Retrieve comprehensive enhancement statistics and insights.
    
    Provides analytics on:
    - Enhancement performance metrics
    - User satisfaction scores
    - Popular enhancement types
    - Learning engine accuracy
    - Resource utilization
    """
    try:
        # Check cache first
        cache_key = f"enhancement_stats:{current_user['id']}"
        cached_stats = await cache_manager.get(cache_key)
        
        if cached_stats:
            return APIResponse(
                success=True,
                data=EnhancementStats(**cached_stats),
                message="Enhancement statistics retrieved"
            )
        
        async with db_manager.get_session() as session:
            # Get basic enhancement statistics
            basic_stats = await db_manager.get_user_enhancement_stats(
                session,
                current_user["id"]
            )
            
            # Get learning engine statistics
            learning_stats = await learning_engine.get_user_learning_stats(
                current_user["id"]
            )
            
            # Combine statistics
            stats = EnhancementStats(
                total_enhancements=basic_stats["total_enhancements"],
                completed_enhancements=basic_stats["completed_enhancements"],
                failed_enhancements=basic_stats["failed_enhancements"],
                average_processing_time=basic_stats["average_processing_time"],
                popular_enhancement_types=basic_stats["popular_enhancement_types"],
                success_rate=basic_stats["success_rate"],
                total_tokens_used=basic_stats["total_tokens_used"],
                learning_accuracy=learning_stats["accuracy"],
                user_satisfaction=basic_stats["user_satisfaction"]
            )
            
            # Cache for 15 minutes
            await cache_manager.set(cache_key, stats.dict(), ttl=900)
            
            return APIResponse(
                success=True,
                data=stats,
                message="Enhancement statistics retrieved"
            )
            
    except Exception as e:
        logger.error(
            "Failed to retrieve enhancement statistics",
            extra={
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve enhancement statistics"
        )

@router.delete(
    "/{enhancement_id}",
    response_model=APIResponse[dict],
    summary="Delete Enhancement",
    description="Delete a specific enhancement and its associated data"
)
async def delete_enhancement(
    enhancement_id: UUID4 = Path(..., description="Enhancement ID to delete"),
    current_user: dict = Depends(get_current_active_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    cache_manager: RedisCacheManager = Depends(get_cache_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Delete a specific enhancement and all its associated data.
    
    This will remove:
    - Enhancement results and suggestions
    - Associated feedback
    - Cached data
    - Learning engine records (anonymized)
    """
    try:
        async with db_manager.get_session() as session:
            # Verify ownership
            enhancement = await db_manager.get_enhancement_result(
                session,
                enhancement_id,
                user_id=current_user["id"]
            )
            
            if not enhancement:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Enhancement not found or access denied"
                )
            
            # Delete from database
            deleted = await db_manager.delete_enhancement(
                session,
                enhancement_id,
                user_id=current_user["id"]
            )
            
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete enhancement"
                )
            
            # Clear related cache entries
            cache_keys = [
                f"enhancement_result:{enhancement_id}",
                f"enhancement_stats:{current_user['id']}"
            ]
            
            for key in cache_keys:
                await cache_manager.delete(key)
            
            logger.info(
                "Enhancement deleted successfully",
                extra={
                    "enhancement_id": str(enhancement_id),
                    "user_id": current_user["id"]
                }
            )
            
            return APIResponse(
                success=True,
                data={"deleted": True, "enhancement_id": str(enhancement_id)},
                message="Enhancement deleted successfully"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete enhancement",
            extra={
                "enhancement_id": str(enhancement_id),
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete enhancement"
        )

@router.get(
    "/templates",
    response_model=APIResponse[List[dict]],
    summary="Get Enhancement Templates",
    description="Retrieve available enhancement templates and presets"
)
async def get_enhancement_templates(
    language: Optional[str] = Query(None, description="Filter by programming language"),
    enhancement_type: Optional[EnhancementType] = Query(None, description="Filter by enhancement type"),
    current_user: dict = Depends(get_current_active_user),
    learning_engine: LearningEngine = Depends(get_learning_engine),
    cache_manager: RedisCacheManager = Depends(get_cache_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Retrieve available enhancement templates and presets.
    
    Templates include:
    - Language-specific enhancement patterns
    - Framework-specific optimizations
    - Industry best practices
    - User-customized templates
    """
    try:
        cache_key = f"enhancement_templates:{language}:{enhancement_type}"
        cached_templates = await cache_manager.get(cache_key)
        
        if cached_templates:
            return APIResponse(
                success=True,
                data=cached_templates,
                message="Enhancement templates retrieved"
            )
        
        # Get templates from learning engine
        templates = await learning_engine.get_enhancement_templates(
            language=language,
            enhancement_type=enhancement_type.value if enhancement_type else None,
            user_preferences=current_user.get("preferences", {})
        )
        
        # Cache for 1 hour
        await cache_manager.set(cache_key, templates, ttl=3600)
        
        return APIResponse(
            success=True,
            data=templates,
            message=f"Retrieved {len(templates)} enhancement templates"
        )
        
    except Exception as e:
        logger.error(
            "Failed to retrieve enhancement templates",
            extra={
                "error": str(e),
                "language": language,
                "enhancement_type": enhancement_type
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve enhancement templates"
        )

@router.post(
    "/compare",
    response_model=APIResponse[dict],
    summary="Compare Enhancement Results",
    description="Compare multiple enhancement results or before/after code quality"
)
async def compare_enhancements(
    enhancement_ids: List[UUID4] = Body(..., description="Enhancement IDs to compare"),
    current_user: dict = Depends(get_current_active_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    ai_manager: MultiLLMManager = Depends(get_ai_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Compare multiple enhancement results or analyze before/after code quality.
    
    Provides comparative analysis including:
    - Quality metrics comparison
    - Performance impact analysis
    - Security improvement assessment
    - Maintainability score changes
    - Recommendation rankings
    """
    try:
        if len(enhancement_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least 2 enhancements required for comparison"
            )
        
        if len(enhancement_ids) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 5 enhancements can be compared at once"
            )
        
        logger.info(
            "Enhancement comparison initiated",
            extra={
                "user_id": current_user["id"],
                "enhancement_ids": [str(id) for id in enhancement_ids],
                "comparison_count": len(enhancement_ids)
            }
        )
        
        # Retrieve enhancement results
        enhancements = []
        async with db_manager.get_session() as session:
            for enhancement_id in enhancement_ids:
                result = await db_manager.get_enhancement_result(
                    session,
                    enhancement_id,
                    user_id=current_user["id"]
                )
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Enhancement {enhancement_id} not found"
                    )
                
                enhancements.append(result)
        
        # Perform AI-powered comparison analysis
        comparison_prompt = f"""
        Compare the following {len(enhancements)} code enhancements:
        
        {json.dumps(enhancements, indent=2)}
        
        Provide a comprehensive comparison including:
        1. Quality metrics comparison
        2. Performance impact analysis
        3. Security improvements
        4. Maintainability scores
        5. Overall recommendations
        
        Return structured JSON with comparison insights.
        """
        
        comparison_result = await ai_manager.generate_response(
            prompt=comparison_prompt,
            provider="claude",  # Use Claude for complex analysis
            max_tokens=2000,
            temperature=0.1
        )
        
        # Parse and structure the comparison result
        try:
            comparison_data = json.loads(comparison_result)
        except json.JSONDecodeError:
            # Fallback to basic comparison if AI response isn't valid JSON
            comparison_data = {
                "summary": "Comparison completed",
                "enhancements": enhancements,
                "analysis": comparison_result
            }
        
        # Add metadata
        comparison_data.update({
            "comparison_id": str(uuid.uuid4()),
            "compared_enhancements": [str(id) for id in enhancement_ids],
            "comparison_timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user["id"]
        })
        
        return APIResponse(
            success=True,
            data=comparison_data,
            message=f"Successfully compared {len(enhancements)} enhancements"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Enhancement comparison failed",
            extra={
                "error": str(e),
                "user_id": current_user["id"],
                "enhancement_ids": [str(id) for id in enhancement_ids]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare enhancements"
        )

@router.get(
    "/insights",
    response_model=APIResponse[dict],
    summary="Get Enhancement Insights",
    description="Get AI-powered insights and recommendations based on enhancement history"
)
async def get_enhancement_insights(
    current_user: dict = Depends(get_current_active_user),
    learning_engine: LearningEngine = Depends(get_learning_engine),
    ai_manager: MultiLLMManager = Depends(get_ai_manager),
    cache_manager: RedisCacheManager = Depends(get_cache_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Get AI-powered insights and recommendations based on user's enhancement history.
    
    Provides personalized insights including:
    - Code quality trends
    - Improvement recommendations
    - Learning progress analysis
    - Best practices suggestions
    - Skill development opportunities
    """
    try:
        cache_key = f"enhancement_insights:{current_user['id']}"
        cached_insights = await cache_manager.get(cache_key)
        
        if cached_insights:
            return APIResponse(
                success=True,
                data=cached_insights,
                message="Enhancement insights retrieved"
            )
        
        # Get user's enhancement patterns and learning data
        user_patterns = await learning_engine.get_user_enhancement_patterns(
            current_user["id"]
        )
        
        # Generate AI-powered insights
        insights_prompt = f"""
        Analyze the following user's code enhancement patterns and provide personalized insights:
        
        {json.dumps(user_patterns, indent=2)}
        
        Provide insights on:
        1. Code quality trends over time
        2. Most common enhancement types
        3. Areas for improvement
        4. Skill development recommendations
        5. Best practices adoption progress
        
        Return structured JSON with actionable insights.
        """
        
        insights_response = await ai_manager.generate_response(
            prompt=insights_prompt,
            provider="openai",
            max_tokens=1500,
            temperature=0.3
        )
        
        try:
            insights_data = json.loads(insights_response)
        except json.JSONDecodeError:
            insights_data = {
                "summary": "Insights analysis completed",
                "raw_analysis": insights_response,
                "patterns": user_patterns
            }
        
        # Add metadata
        insights_data.update({
            "generated_at": datetime.utcnow().isoformat(),
            "user_id": current_user["id"],
            "data_period": user_patterns.get("analysis_period", "all_time")
        })
        
        # Cache for 4 hours
        await cache_manager.set(cache_key, insights_data, ttl=14400)
        
        return APIResponse(
            success=True,
            data=insights_data,
            message="Enhancement insights generated successfully"
        )
        
    except Exception as e:
        logger.error(
            "Failed to generate enhancement insights",
            extra={
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate enhancement insights"
        )user),
    enhancement_agent: EnhancementAgent = Depends(get_enhancement_agent),
    learning_engine: LearningEngine = Depends(get_learning_engine),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    cache_manager: RedisCacheManager = Depends(get_cache_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Enhance a single code snippet using AI-powered analysis and improvement suggestions.
    
    This endpoint provides comprehensive code enhancement including:
    - Performance optimizations
    - Security improvements  
    - Code maintainability enhancements
    - Readability improvements
    - Best practices application
    - Test generation
    - Documentation generation
    """
    enhancement_id = uuid.uuid4()
    start_time = datetime.utcnow()
    
    try:
        logger.info(
            "Code enhancement request initiated",
            extra={
                "enhancement_id": str(enhancement_id),
                "user_id": current_user["id"],
                "language": request.language,
                "enhancement_types": request.enhancement_types,
                "code_length": len(request.code)
            }
        )
        
        # Check cache for similar enhancement
        cache_key = f"enhancement:{hash(request.code + str(request.enhancement_types))}"
        cached_result = await cache_manager.get(cache_key)
        if cached_result and not request.apply_learning:
            logger.info("Returning cached enhancement result")
            return APIResponse(
                success=True,
                data=EnhancementResult(**cached_result),
                message="Enhancement completed (cached)"
            )
        
        # Apply learning insights if requested
        learning_context = {}
        if request.apply_learning:
            learning_context = await learning_engine.get_enhancement_insights(
                language=request.language,
                enhancement_types=request.enhancement_types,
                user_preferences=current_user.get("preferences", {})
            )
        
        # Configure AI provider preference
        if request.preferred_llm:
            await enhancement_agent.set_preferred_llm(request.preferred_llm.value)
        
        # Create enhancement task
        enhancement_task = {
            "id": str(enhancement_id),
            "type": "code_enhancement",
            "user_id": current_user["id"],
            "code": request.code,
            "language": request.language,
            "enhancement_types": request.enhancement_types,
            "priority": request.priority.value,
            "context": request.context,
            "constraints": request.constraints or [],
            "target_frameworks": request.target_frameworks or [],
            "generate_tests": request.generate_tests,
            "include_documentation": request.include_documentation,
            "learning_context": learning_context,
            "created_at": start_time.isoformat()
        }
        
        # Execute enhancement through orchestrator
        enhancement_result = await orchestrator.execute_workflow(
            workflow_type="code_enhancement",
            task_data=enhancement_task,
            primary_agent="enhancement",
            supporting_agents=["analysis", "validation"] if request.generate_tests else ["analysis"]
        )
        
        # Process results
        suggestions = []
        for suggestion_data in enhancement_result.get("suggestions", []):
            suggestion = EnhancementSuggestion(
                id=suggestion_data["id"],
                type=EnhancementType(suggestion_data["type"]),
                priority=EnhancementPriority(suggestion_data["priority"]),
                title=suggestion_data["title"],
                description=suggestion_data["description"],
                original_code=suggestion_data["original_code"],
                enhanced_code=suggestion_data["enhanced_code"],
                explanation=suggestion_data["explanation"],
                benefits=suggestion_data["benefits"],
                potential_risks=suggestion_data.get("potential_risks", []),
                confidence_score=suggestion_data["confidence_score"],
                estimated_impact=suggestion_data["estimated_impact"],
                line_numbers=suggestion_data.get("line_numbers"),
                dependencies=suggestion_data.get("dependencies")
            )
            suggestions.append(suggestion)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        result = EnhancementResult(
            enhancement_id=enhancement_id,
            status=EnhancementStatus(enhancement_result["status"]),
            original_code=request.code,
            enhanced_code=enhancement_result.get("enhanced_code"),
            suggestions=suggestions,
            metrics=enhancement_result.get("metrics", {}),
            test_code=enhancement_result.get("test_code"),
            documentation=enhancement_result.get("documentation"),
            processing_time=processing_time,
            tokens_used=enhancement_result.get("tokens_used", {}),
            learning_applied=bool(learning_context),
            validation_results=enhancement_result.get("validation_results"),
            created_at=start_time,
            completed_at=datetime.utcnow()
        )
        
        # Cache result for future use
        await cache_manager.set(cache_key, result.dict(), ttl=3600)  # 1 hour
        
        # Submit feedback to learning engine in background
        if request.apply_learning:
            background_tasks.add_task(
                learning_engine.record_enhancement_result,
                enhancement_task,
                result.dict(),
                success=result.status == EnhancementStatus.COMPLETED
            )
        
        logger.info(
            "Code enhancement completed successfully",
            extra={
                "enhancement_id": str(enhancement_id),
                "processing_time": processing_time,
                "suggestions_count": len(suggestions),
                "status": result.status.value
            }
        )
        
        return APIResponse(
            success=True,
            data=result,
            message=f"Code enhancement completed with {len(suggestions)} suggestions"
        )
        
    except Exception as e:
        logger.error(
            "Code enhancement failed",
            extra={
                "enhancement_id": str(enhancement_id),
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        # Record failure for learning
        if request.apply_learning:
            background_tasks.add_task(
                learning_engine.record_enhancement_failure,
                str(enhancement_id),
                str(e),
                {"code_length": len(request.code), "language": request.language}
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enhancement failed: {str(e)}"
        )

@router.post(
    "/repository",
    response_model=TaskResponse,
    summary="Enhance Repository", 
    description="Enhance an entire GitHub repository with comprehensive AI analysis"
)
async def enhance_repository(
    request: RepositoryEnhancementRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user),
    enhancement_agent: EnhancementAgent = Depends(get_enhancement_agent),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Enhance an entire GitHub repository with comprehensive AI-powered analysis.
    
    This endpoint processes multiple files in a repository and provides:
    - Repository-wide code analysis
    - Batch enhancement suggestions
    - Pull request creation with improvements
    - Project-level metrics and insights
    """
    task_id = uuid.uuid4()
    
    try:
        logger.info(
            "Repository enhancement request initiated",
            extra={
                "task_id": str(task_id),
                "user_id": current_user["id"],
                "repository_url": request.repository_url,
                "branch": request.branch,
                "max_files": request.max_files
            }
        )
        
        # Create repository enhancement task
        repo_task = {
            "id": str(task_id),
            "type": "repository_enhancement",
            "user_id": current_user["id"],
            "repository_url": request.repository_url,
            "branch": request.branch,
            "file_patterns": request.file_patterns or [],
            "exclude_patterns": request.exclude_patterns or [],
            "enhancement_types": request.enhancement_types,
            "priority": request.priority.value,
            "max_files": request.max_files,
            "create_pull_request": request.create_pull_request,
            "apply_learning": request.apply_learning,
            "preferred_llm": request.preferred_llm.value if request.preferred_llm else None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Execute as background task through orchestrator
        background_tasks.add_task(
            orchestrator.execute_long_running_workflow,
            workflow_type="repository_enhancement",
            task_data=repo_task,
            primary_agent="enhancement",
            supporting_agents=["analysis", "validation", "security"]
        )
        
        return TaskResponse(
            task_id=task_id,
            status="initiated",
            message="Repository enhancement task started",
            estimated_completion=datetime.utcnow() + timedelta(minutes=30)
        )
        
    except Exception as e:
        logger.error(
            "Repository enhancement initiation failed",
            extra={
                "task_id": str(task_id),
                "error": str(e),
                "repository_url": request.repository_url
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate repository enhancement: {str(e)}"
        )

@router.post(
    "/bulk",
    response_model=TaskResponse,
    summary="Bulk Code Enhancement",
    description="Enhance multiple files simultaneously with parallel processing"
)
async def bulk_enhance_code(
    request: BulkEnhancementRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user),
    enhancement_agent: EnhancementAgent = Depends(get_enhancement_agent),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Enhance multiple code files simultaneously with intelligent parallel processing.
    
    Features:
    - Parallel processing for improved performance
    - Batch optimization for token efficiency
    - Cross-file dependency analysis
    - Consolidated enhancement report
    """
    task_id = uuid.uuid4()
    
    try:
        logger.info(
            "Bulk enhancement request initiated",
            extra={
                "task_id": str(task_id),
                "user_id": current_user["id"],
                "files_count": len(request.files),
                "parallel_processing": request.parallel_processing
            }
        )
        
        # Validate total content size
        total_size = sum(len(f["content"]) for f in request.files)
        if total_size > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Total files size exceeds 10MB limit"
            )
        
        # Create bulk enhancement task
        bulk_task = {
            "id": str(task_id),
            "type": "bulk_enhancement",
            "user_id": current_user["id"],
            "files": request.files,
            "enhancement_types": request.enhancement_types,
            "priority": request.priority.value,
            "parallel_processing": request.parallel_processing,
            "apply_learning": request.apply_learning,
            "preferred_llm": request.preferred_llm.value if request.preferred_llm else None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Execute as background task
        background_tasks.add_task(
            orchestrator.execute_workflow,
            workflow_type="bulk_enhancement",
            task_data=bulk_task,
            primary_agent="enhancement",
            supporting_agents=["analysis"]
        )
        
        estimated_time = len(request.files) * 2  # 2 minutes per file average
        if request.parallel_processing:
            estimated_time = max(estimated_time // 4, 5)  # Parallel processing speedup
        
        return TaskResponse(
            task_id=task_id,
            status="initiated",
            message=f"Bulk enhancement task started for {len(request.files)} files",
            estimated_completion=datetime.utcnow() + timedelta(minutes=estimated_time)
        )
        
    except Exception as e:
        logger.error(
            "Bulk enhancement initiation failed",
            extra={
                "task_id": str(task_id),
                "error": str(e),
                "files_count": len(request.files)
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate bulk enhancement: {str(e)}"
        )

@router.get(
    "/result/{enhancement_id}",
    response_model=APIResponse[EnhancementResult],
    summary="Get Enhancement Result",
    description="Retrieve the result of a specific enhancement task"
)
async def get_enhancement_result(
    enhancement_id: UUID4 = Path(..., description="Enhancement task ID"),
    current_user: dict = Depends(get_current_active_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    cache_manager: RedisCacheManager = Depends(get_cache_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Retrieve the complete result of a specific enhancement task.
    
    Returns detailed enhancement information including:
    - Original and enhanced code
    - All suggestions and improvements
    - Performance metrics comparison
    - Processing statistics
    - Validation results
    """
    try:
        # Check cache first
        cache_key = f"enhancement_result:{enhancement_id}"
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return APIResponse(
                success=True,
                data=EnhancementResult(**cached_result),
                message="Enhancement result retrieved"
            )
        
        # Query database
        async with db_manager.get_session() as session:
            result = await db_manager.get_enhancement_result(
                session, 
                enhancement_id, 
                user_id=current_user["id"]
            )
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Enhancement result not found"
                )
            
            # Cache for future requests
            await cache_manager.set(cache_key, result, ttl=1800)  # 30 minutes
            
            return APIResponse(
                success=True,
                data=EnhancementResult(**result),
                message="Enhancement result retrieved"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve enhancement result",
            extra={
                "enhancement_id": str(enhancement_id),
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve enhancement result"
        )

@router.get(
    "/repository/{task_id}",
    response_model=APIResponse[RepositoryEnhancementResult],
    summary="Get Repository Enhancement Result",
    description="Retrieve the result of a repository enhancement task"
)
async def get_repository_enhancement_result(
    task_id: UUID4 = Path(..., description="Repository enhancement task ID"),
    current_user: dict = Depends(get_current_active_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    logger: StructuredLogger = Depends(get_logger)
):
    """
    Retrieve the complete result of a repository enhancement task.
    
    Returns comprehensive repository enhancement information including:
    - Overall enhancement summary
    - Per-file enhancement results
    - Pull request information
    - Repository metrics improvement
    - Processing statistics
    """
    try:
        async with db_manager.get_session() as session:
            result = await db_manager.get_repository_enhancement_result(
                session,
                task_id,
                user_id=current_user["id"]
            )
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Repository enhancement result not found"
                )
            
            return APIResponse(
                success=True,
                data=RepositoryEnhancementResult(**result),
                message="Repository enhancement result retrieved"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve repository enhancement result",
            extra={
                "task_id": str(task_id),
                "error": str(e),
                "user_id": current_user["id"]
            },
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve repository enhancement result"
        )

@router.post(
    "/feedback",
    response_model=APIResponse[dict],
    summary="Submit Enhancement Feedback",
    description="Submit feedback for enhancement results to improve learning"
)
async def submit_enhancement_feedback(
    feedback: EnhancementFeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_