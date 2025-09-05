"""
YMERA Enterprise Analysis API Routes
Production-Ready Code Analysis Endpoints with Multi-Agent Integration
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Path
from fastapi.security import HTTPBearer
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import asyncio
import uuid
from enum import Enum
import json

# Core system imports
from ymera_core.database.manager import DatabaseManager
from ymera_core.logging.structured_logger import StructuredLogger
from ymera_core.cache.redis_cache import RedisCacheManager
from ymera_core.security.auth_manager import AuthManager
from ymera_core.exceptions import YMERAException, ValidationError, AnalysisError

# Agent system imports
from ymera_agents.orchestrator import AgentOrchestrator
from ymera_agents.core.analysis_agent import AnalysisAgent
from ymera_agents.learning.learning_engine import LearningEngine
from ymera_agents.communication.message_bus import MessageBus

# Service imports
from ymera_services.ai.multi_llm_manager import MultiLLMManager
from ymera_services.github.repository_analyzer import GitHubRepositoryAnalyzer
from ymera_services.code_analysis.quality_analyzer import CodeQualityAnalyzer
from ymera_services.vector_db.pinecone_manager import PineconeManager

# Dependency injection
from main import (
    get_db_manager, get_auth_manager, get_agent_orchestrator,
    get_learning_engine, get_ai_manager, get_vector_db, get_github_analyzer
)

# Security
security = HTTPBearer()

# Router
router = APIRouter()

# Enums
class AnalysisType(str, Enum):
    """Supported analysis types"""
    FULL = "full"
    QUICK = "quick"
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    ARCHITECTURE = "architecture"
    DEPENDENCIES = "dependencies"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    COMPLEXITY = "complexity"

class AnalysisStatus(str, Enum):
    """Analysis status states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AnalysisPriority(str, Enum):
    """Analysis priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class CodeLanguage(str, Enum):
    """Supported programming languages"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    AUTO_DETECT = "auto_detect"

# Request Models
class AnalysisRequestBase(BaseModel):
    """Base analysis request model"""
    analysis_type: AnalysisType = Field(..., description="Type of analysis to perform")
    priority: AnalysisPriority = Field(default=AnalysisPriority.MEDIUM, description="Analysis priority")
    include_suggestions: bool = Field(default=True, description="Include enhancement suggestions")
    include_metrics: bool = Field(default=True, description="Include detailed metrics")
    learning_context: Optional[str] = Field(None, description="Additional context for learning engine")
    
    class Config:
        use_enum_values = True

class CodeAnalysisRequest(AnalysisRequestBase):
    """Direct code analysis request"""
    code: str = Field(..., min_length=1, max_length=500000, description="Source code to analyze")
    language: CodeLanguage = Field(default=CodeLanguage.AUTO_DETECT, description="Programming language")
    filename: Optional[str] = Field(None, description="Optional filename for context")
    project_context: Optional[str] = Field(None, description="Project context information")
    
    @validator('code')
    def validate_code(cls, v):
        if not v.strip():
            raise ValueError("Code cannot be empty")
        return v

class RepositoryAnalysisRequest(AnalysisRequestBase):
    """Repository analysis request"""
    repository_url: str = Field(..., description="GitHub repository URL")
    branch: Optional[str] = Field(default="main", description="Branch to analyze")
    include_history: bool = Field(default=False, description="Include commit history analysis")
    max_files: Optional[int] = Field(default=1000, description="Maximum files to analyze")
    file_patterns: Optional[List[str]] = Field(None, description="File patterns to include")
    exclude_patterns: Optional[List[str]] = Field(None, description="File patterns to exclude")
    
    @validator('repository_url')
    def validate_repo_url(cls, v):
        if not v.startswith(('https://github.com/', 'https://www.github.com/')):
            raise ValueError("Only GitHub repositories are supported")
        return v

class FileAnalysisRequest(AnalysisRequestBase):
    """File-based analysis request"""
    files: List[Dict[str, Any]] = Field(..., description="Files to analyze")
    project_name: Optional[str] = Field(None, description="Project name")
    project_description: Optional[str] = Field(None, description="Project description")
    
    @validator('files')
    def validate_files(cls, v):
        if not v:
            raise ValueError("At least one file must be provided")
        
        for file_info in v:
            if 'content' not in file_info or 'filename' not in file_info:
                raise ValueError("Each file must have 'content' and 'filename' fields")
            
            if len(file_info['content']) > 100000:  # 100KB limit per file
                raise ValueError(f"File {file_info['filename']} exceeds size limit")
        
        return v

class BatchAnalysisRequest(BaseModel):
    """Batch analysis request"""
    requests: List[Union[CodeAnalysisRequest, RepositoryAnalysisRequest, FileAnalysisRequest]] = Field(
        ..., max_items=10, description="Analysis requests to process in batch"
    )
    batch_priority: AnalysisPriority = Field(default=AnalysisPriority.MEDIUM)
    parallel_execution: bool = Field(default=True, description="Execute requests in parallel")
    
    @validator('requests')
    def validate_requests(cls, v):
        if not v:
            raise ValueError("At least one analysis request must be provided")
        return v

# Response Models
class QualityMetrics(BaseModel):
    """Code quality metrics"""
    overall_score: float = Field(..., ge=0, le=100, description="Overall quality score")
    maintainability_score: float = Field(..., ge=0, le=100)
    complexity_score: float = Field(..., ge=0, le=100)
    readability_score: float = Field(..., ge=0, le=100)
    test_coverage: Optional[float] = Field(None, ge=0, le=100)
    duplication_percentage: float = Field(..., ge=0, le=100)
    technical_debt_hours: float = Field(..., ge=0)
    
class SecurityIssue(BaseModel):
    """Security issue details"""
    issue_id: str = Field(..., description="Unique issue identifier")
    severity: str = Field(..., description="Issue severity level")
    category: str = Field(..., description="Security category")
    title: str = Field(..., description="Issue title")
    description: str = Field(..., description="Detailed description")
    location: Dict[str, Any] = Field(..., description="Issue location")
    recommendation: str = Field(..., description="Remediation recommendation")
    cwe_id: Optional[str] = Field(None, description="CWE identifier if applicable")
    
class PerformanceInsight(BaseModel):
    """Performance analysis insight"""
    category: str = Field(..., description="Performance category")
    impact: str = Field(..., description="Performance impact level")
    description: str = Field(..., description="Insight description")
    recommendation: str = Field(..., description="Performance improvement recommendation")
    estimated_improvement: Optional[str] = Field(None, description="Estimated performance gain")
    
class EnhancementSuggestion(BaseModel):
    """Code enhancement suggestion"""
    suggestion_id: str = Field(..., description="Unique suggestion identifier")
    category: str = Field(..., description="Enhancement category")
    priority: str = Field(..., description="Suggestion priority")
    title: str = Field(..., description="Suggestion title")
    description: str = Field(..., description="Detailed description")
    before_code: Optional[str] = Field(None, description="Code before enhancement")
    after_code: Optional[str] = Field(None, description="Suggested code after enhancement")
    benefits: List[str] = Field(default_factory=list, description="Enhancement benefits")
    effort_estimate: Optional[str] = Field(None, description="Implementation effort estimate")
    
class LearningInsights(BaseModel):
    """Learning engine insights"""
    patterns_identified: List[str] = Field(default_factory=list)
    knowledge_gaps: List[str] = Field(default_factory=list)
    learning_confidence: float = Field(..., ge=0, le=100)
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class AnalysisResult(BaseModel):
    """Complete analysis result"""
    analysis_id: str = Field(..., description="Unique analysis identifier")
    status: AnalysisStatus = Field(..., description="Analysis status")
    analysis_type: AnalysisType = Field(..., description="Type of analysis performed")
    created_at: datetime = Field(..., description="Analysis creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Analysis completion timestamp")
    duration_seconds: Optional[float] = Field(None, description="Analysis duration")
    
    # Core Results
    quality_metrics: Optional[QualityMetrics] = Field(None)
    security_issues: List[SecurityIssue] = Field(default_factory=list)
    performance_insights: List[PerformanceInsight] = Field(default_factory=list)
    enhancement_suggestions: List[EnhancementSuggestion] = Field(default_factory=list)
    
    # Metadata
    language_detected: Optional[str] = Field(None)
    files_analyzed: int = Field(default=0)
    lines_of_code: int = Field(default=0)
    
    # Learning Integration
    learning_insights: Optional[LearningInsights] = Field(None)
    confidence_score: float = Field(..., ge=0, le=100, description="Analysis confidence score")
    
    # Additional Data
    raw_metrics: Dict[str, Any] = Field(default_factory=dict)
    agent_feedback: Dict[str, Any] = Field(default_factory=dict)
    processing_notes: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True

class AnalysisListResponse(BaseModel):
    """Analysis list response"""
    analyses: List[AnalysisResult] = Field(..., description="List of analyses")
    total_count: int = Field(..., description="Total number of analyses")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")

class BatchAnalysisResponse(BaseModel):
    """Batch analysis response"""
    batch_id: str = Field(..., description="Batch identifier")
    status: str = Field(..., description="Batch status")
    total_requests: int = Field(..., description="Total number of requests")
    completed_requests: int = Field(default=0, description="Number of completed requests")
    failed_requests: int = Field(default=0, description="Number of failed requests")
    results: List[AnalysisResult] = Field(default_factory=list, description="Analysis results")
    created_at: datetime = Field(..., description="Batch creation timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

# Utility Functions
async def get_current_user(token: str = Depends(security), auth_manager: AuthManager = Depends(get_auth_manager)):
    """Get current authenticated user"""
    try:
        payload = auth_manager.verify_token(token.credentials)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def validate_analysis_limits(
    user: dict,
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """Validate user analysis limits"""
    user_id = user.get("sub")
    
    # Check daily analysis limit
    today = datetime.utcnow().date()
    daily_count = await db_manager.get_user_daily_analysis_count(user_id, today)
    
    # Default limits based on user tier (implement your own logic)
    tier = user.get("tier", "free")
    limits = {
        "free": 10,
        "pro": 100,
        "enterprise": 1000
    }
    
    if daily_count >= limits.get(tier, 10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily analysis limit reached ({limits.get(tier, 10)} analyses per day)"
        )

# Main API Endpoints

@router.post("/code", response_model=AnalysisResult, summary="Analyze Code Direct")
async def analyze_code_direct(
    request: CodeAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    learning_engine: LearningEngine = Depends(get_learning_engine),
    ai_manager: MultiLLMManager = Depends(get_ai_manager)
):
    """
    Analyze source code directly with comprehensive quality, security, and performance analysis.
    
    Supports all major programming languages with intelligent auto-detection.
    Provides detailed metrics, enhancement suggestions, and learning-driven insights.
    """
    await validate_analysis_limits(user, db_manager)
    
    try:
        analysis_id = str(uuid.uuid4())
        user_id = user.get("sub")
        
        # Create analysis record
        analysis_data = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "analysis_type": request.analysis_type,
            "status": AnalysisStatus.PENDING,
            "created_at": datetime.utcnow(),
            "request_data": request.dict(),
            "priority": request.priority
        }
        
        await db_manager.create_analysis_record(analysis_data)
        
        # Prepare analysis context
        context = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "code": request.code,
            "language": request.language,
            "filename": request.filename,
            "project_context": request.project_context,
            "analysis_type": request.analysis_type,
            "include_suggestions": request.include_suggestions,
            "include_metrics": request.include_metrics,
            "learning_context": request.learning_context,
            "priority": request.priority
        }
        
        # Execute analysis through agent orchestrator
        analysis_task = await orchestrator.execute_agent_workflow(
            workflow_type="code_analysis",
            context=context,
            priority=request.priority,
            user_id=user_id
        )
        
        # Start background processing
        background_tasks.add_task(
            process_code_analysis,
            analysis_id=analysis_id,
            context=context,
            orchestrator=orchestrator,
            learning_engine=learning_engine,
            db_manager=db_manager
        )
        
        # Return initial response
        return AnalysisResult(
            analysis_id=analysis_id,
            status=AnalysisStatus.IN_PROGRESS,
            analysis_type=request.analysis_type,
            created_at=datetime.utcnow(),
            confidence_score=85.0,
            processing_notes=["Analysis initiated", "Processing through agent workflow"]
        )
        
    except Exception as e:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis initiation failed: {str(e)}"
        )

@router.post("/repository", response_model=AnalysisResult, summary="Analyze GitHub Repository")
async def analyze_repository(
    request: RepositoryAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    github_analyzer: GitHubRepositoryAnalyzer = Depends(get_github_analyzer),
    learning_engine: LearningEngine = Depends(get_learning_engine)
):
    """
    Perform comprehensive analysis of a GitHub repository including architecture,
    code quality, security vulnerabilities, and development patterns.
    """
    await validate_analysis_limits(user, db_manager)
    
    try:
        analysis_id = str(uuid.uuid4())
        user_id = user.get("sub")
        
        # Validate repository access
        repo_info = await github_analyzer.get_repository_info(request.repository_url)
        if not repo_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found or not accessible"
            )
        
        # Create analysis record
        analysis_data = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "analysis_type": request.analysis_type,
            "status": AnalysisStatus.PENDING,
            "created_at": datetime.utcnow(),
            "request_data": request.dict(),
            "repository_info": repo_info,
            "priority": request.priority
        }
        
        await db_manager.create_analysis_record(analysis_data)
        
        # Prepare analysis context
        context = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "repository_url": request.repository_url,
            "branch": request.branch,
            "include_history": request.include_history,
            "max_files": request.max_files,
            "file_patterns": request.file_patterns,
            "exclude_patterns": request.exclude_patterns,
            "analysis_type": request.analysis_type,
            "include_suggestions": request.include_suggestions,
            "include_metrics": request.include_metrics,
            "learning_context": request.learning_context,
            "priority": request.priority,
            "repository_info": repo_info
        }
        
        # Execute repository analysis workflow
        analysis_task = await orchestrator.execute_agent_workflow(
            workflow_type="repository_analysis",
            context=context,
            priority=request.priority,
            user_id=user_id
        )
        
        # Start background processing
        background_tasks.add_task(
            process_repository_analysis,
            analysis_id=analysis_id,
            context=context,
            orchestrator=orchestrator,
            github_analyzer=github_analyzer,
            learning_engine=learning_engine,
            db_manager=db_manager
        )
        
        return AnalysisResult(
            analysis_id=analysis_id,
            status=AnalysisStatus.IN_PROGRESS,
            analysis_type=request.analysis_type,
            created_at=datetime.utcnow(),
            confidence_score=90.0,
            processing_notes=[
                "Repository analysis initiated",
                f"Repository: {repo_info.get('name', 'Unknown')}",
                f"Stars: {repo_info.get('stars', 0)}",
                f"Language: {repo_info.get('language', 'Mixed')}"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if 'analysis_id' in locals():
            await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository analysis initiation failed: {str(e)}"
        )

@router.post("/files", response_model=AnalysisResult, summary="Analyze Multiple Files")
async def analyze_files(
    request: FileAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    learning_engine: LearningEngine = Depends(get_learning_engine)
):
    """
    Analyze multiple files as a cohesive project with cross-file analysis,
    architecture insights, and dependency mapping.
    """
    await validate_analysis_limits(user, db_manager)
    
    try:
        analysis_id = str(uuid.uuid4())
        user_id = user.get("sub")
        
        # Validate files
        total_size = sum(len(f['content']) for f in request.files)
        if total_size > 10_000_000:  # 10MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Total file size exceeds limit (10MB)"
            )
        
        # Create analysis record
        analysis_data = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "analysis_type": request.analysis_type,
            "status": AnalysisStatus.PENDING,
            "created_at": datetime.utcnow(),
            "request_data": {
                **request.dict(),
                "files": [{"filename": f["filename"], "size": len(f["content"])} for f in request.files]
            },
            "priority": request.priority
        }
        
        await db_manager.create_analysis_record(analysis_data)
        
        # Prepare analysis context
        context = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "files": request.files,
            "project_name": request.project_name,
            "project_description": request.project_description,
            "analysis_type": request.analysis_type,
            "include_suggestions": request.include_suggestions,
            "include_metrics": request.include_metrics,
            "learning_context": request.learning_context,
            "priority": request.priority
        }
        
        # Execute file analysis workflow
        analysis_task = await orchestrator.execute_agent_workflow(
            workflow_type="multi_file_analysis",
            context=context,
            priority=request.priority,
            user_id=user_id
        )
        
        # Start background processing
        background_tasks.add_task(
            process_file_analysis,
            analysis_id=analysis_id,
            context=context,
            orchestrator=orchestrator,
            learning_engine=learning_engine,
            db_manager=db_manager
        )
        
        return AnalysisResult(
            analysis_id=analysis_id,
            status=AnalysisStatus.IN_PROGRESS,
            analysis_type=request.analysis_type,
            created_at=datetime.utcnow(),
            files_analyzed=len(request.files),
            lines_of_code=sum(f['content'].count('\n') + 1 for f in request.files),
            confidence_score=88.0,
            processing_notes=[
                f"Multi-file analysis initiated for {len(request.files)} files",
                f"Total lines of code: {sum(f['content'].count('\\n') + 1 for f in request.files)}"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if 'analysis_id' in locals():
            await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File analysis initiation failed: {str(e)}"
        )

@router.post("/batch", response_model=BatchAnalysisResponse, summary="Batch Analysis")
async def analyze_batch(
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator)
):
    """
    Execute multiple analysis requests in batch with intelligent scheduling
    and resource optimization.
    """
    await validate_analysis_limits(user, db_manager)
    
    try:
        batch_id = str(uuid.uuid4())
        user_id = user.get("sub")
        
        # Create batch record
        batch_data = {
            "batch_id": batch_id,
            "user_id": user_id,
            "total_requests": len(request.requests),
            "status": "in_progress",
            "created_at": datetime.utcnow(),
            "priority": request.batch_priority,
            "parallel_execution": request.parallel_execution
        }
        
        await db_manager.create_batch_record(batch_data)
        
        # Start batch processing
        background_tasks.add_task(
            process_batch_analysis,
            batch_id=batch_id,
            requests=request.requests,
            user_id=user_id,
            parallel_execution=request.parallel_execution,
            orchestrator=orchestrator,
            db_manager=db_manager
        )
        
        # Calculate estimated completion time
        estimated_duration = len(request.requests) * 30  # 30 seconds per request estimate
        if request.parallel_execution:
            estimated_duration = max(estimated_duration // 3, 60)  # Parallel processing optimization
        
        estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_duration)
        
        return BatchAnalysisResponse(
            batch_id=batch_id,
            status="in_progress",
            total_requests=len(request.requests),
            completed_requests=0,
            failed_requests=0,
            results=[],
            created_at=datetime.utcnow(),
            estimated_completion=estimated_completion
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch analysis initiation failed: {str(e)}"
        )

@router.get("/{analysis_id}", response_model=AnalysisResult, summary="Get Analysis Result")
async def get_analysis_result(
    analysis_id: str = Path(..., description="Analysis ID"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Retrieve detailed results for a specific analysis including all metrics,
    suggestions, and learning insights.
    """
    try:
        user_id = user.get("sub")
        
        # Get analysis from database
        analysis = await db_manager.get_analysis_by_id(analysis_id, user_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analysis: {str(e)}"
        )

@router.get("/", response_model=AnalysisListResponse, summary="List User Analyses")
async def list_user_analyses(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[AnalysisStatus] = Query(None, description="Filter by status"),
    type_filter: Optional[AnalysisType] = Query(None, description="Filter by analysis type"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    List all analyses for the authenticated user with filtering and pagination.
    """
    try:
        user_id = user.get("sub")
        
        # Get analyses with filters
        analyses, total_count = await db_manager.get_user_analyses(
            user_id=user_id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            type_filter=type_filter
        )
        
        has_next = (page * page_size) < total_count
        
        return AnalysisListResponse(
            analyses=analyses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analyses: {str(e)}"
        )

@router.delete("/{analysis_id}", summary="Delete Analysis")
async def delete_analysis(
    analysis_id: str = Path(..., description="Analysis ID"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator)
):
    """
    Delete an analysis and cancel if still in progress.
    """
    try:
        user_id = user.get("sub")
        
        # Check if analysis exists and belongs to user
        analysis = await db_manager.get_analysis_by_id(analysis_id, user_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        # Cancel if in progress
        if analysis.status in [AnalysisStatus.PENDING, AnalysisStatus.IN_PROGRESS]:
            await orchestrator.cancel_analysis(analysis_id)
        
        # Delete from database
        await db_manager.delete_analysis(analysis_id, user_id)
        
        return {"message": "Analysis deleted successfully", "analysis_id": analysis_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete analysis: {str(e)}"
        )

@router.get("/batch/{batch_id}", response_model=BatchAnalysisResponse, summary="Get Batch Analysis Status")
async def get_batch_status(
    batch_id: str = Path(..., description="Batch ID"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Get the current status and results of a batch analysis.
    """
    try:
        user_id = user.get("sub")
        
        # Get batch from database
        batch = await db_manager.get_batch_by_id(batch_id, user_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch analysis not found"
            )
        
        return batch
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batch status: {str(e)}"
        )

@router.post("/{analysis_id}/feedback", summary="Provide Analysis Feedback")
async def provide_analysis_feedback(
    analysis_id: str = Path(..., description="Analysis ID"),
    feedback: Dict[str, Any] = ...,
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    learning_engine: LearningEngine = Depends(get_learning_engine)
):
    """
    Provide feedback on analysis results to improve future analysis quality
    through the learning engine.
    """
    try:
        user_id = user.get("sub")
        
        # Validate analysis exists and belongs to user
        analysis = await db_manager.get_analysis_by_id(analysis_id, user_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        # Process feedback through learning engine
        feedback_result = await learning_engine.process_analysis_feedback(
            analysis_id=analysis_id,
            user_id=user_id,
            feedback=feedback,
            analysis_context=analysis.dict()
        )
        
        # Store feedback in database
        await db_manager.store_analysis_feedback(
            analysis_id=analysis_id,
            user_id=user_id,
            feedback=feedback,
            feedback_result=feedback_result
        )
        
        return {
            "message": "Feedback processed successfully",
            "analysis_id": analysis_id,
            "learning_impact": feedback_result.get("learning_impact", "medium"),
            "improvements_identified": feedback_result.get("improvements", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback: {str(e)}"
        )

@router.get("/{analysis_id}/insights", summary="Get Learning Insights")
async def get_analysis_insights(
    analysis_id: str = Path(..., description="Analysis ID"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    learning_engine: LearningEngine = Depends(get_learning_engine)
):
    """
    Get detailed learning insights and patterns identified during analysis.
    """
    try:
        user_id = user.get("sub")
        
        # Validate analysis exists
        analysis = await db_manager.get_analysis_by_id(analysis_id, user_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        # Get learning insights
        insights = await learning_engine.get_analysis_insights(
            analysis_id=analysis_id,
            user_id=user_id
        )
        
        return insights
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve insights: {str(e)}"
        )

@router.post("/{analysis_id}/retry", response_model=AnalysisResult, summary="Retry Failed Analysis")
async def retry_analysis(
    analysis_id: str = Path(..., description="Analysis ID"),
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    learning_engine: LearningEngine = Depends(get_learning_engine)
):
    """
    Retry a failed analysis with improved parameters based on learning insights.
    """
    try:
        user_id = user.get("sub")
        
        # Get original analysis
        original_analysis = await db_manager.get_analysis_by_id(analysis_id, user_id)
        if not original_analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original analysis not found"
            )
        
        if original_analysis.status != AnalysisStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only retry failed analyses"
            )
        
        # Create new analysis with improved parameters
        new_analysis_id = str(uuid.uuid4())
        
        # Get learning-based improvements
        improvements = await learning_engine.get_retry_improvements(analysis_id)
        
        # Update analysis record
        retry_data = {
            "analysis_id": new_analysis_id,
            "user_id": user_id,
            "analysis_type": original_analysis.analysis_type,
            "status": AnalysisStatus.PENDING,
            "created_at": datetime.utcnow(),
            "request_data": original_analysis.raw_metrics.get("request_data", {}),
            "retry_of": analysis_id,
            "improvements": improvements,
            "priority": "high"
        }
        
        await db_manager.create_analysis_record(retry_data)
        
        # Prepare enhanced context
        context = {
            **original_analysis.raw_metrics.get("context", {}),
            "analysis_id": new_analysis_id,
            "retry_of": analysis_id,
            "improvements": improvements,
            "priority": "high"
        }
        
        # Execute retry through orchestrator
        analysis_task = await orchestrator.execute_agent_workflow(
            workflow_type="analysis_retry",
            context=context,
            priority="high",
            user_id=user_id
        )
        
        # Start background processing
        background_tasks.add_task(
            process_analysis_retry,
            new_analysis_id=new_analysis_id,
            original_analysis_id=analysis_id,
            context=context,
            orchestrator=orchestrator,
            learning_engine=learning_engine,
            db_manager=db_manager
        )
        
        return AnalysisResult(
            analysis_id=new_analysis_id,
            status=AnalysisStatus.IN_PROGRESS,
            analysis_type=original_analysis.analysis_type,
            created_at=datetime.utcnow(),
            confidence_score=95.0,  # Higher confidence due to learning improvements
            processing_notes=[
                f"Retry of analysis {analysis_id}",
                f"Applied {len(improvements)} learning-based improvements",
                "Enhanced processing parameters"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry analysis: {str(e)}"
        )

@router.get("/stats/user", summary="Get User Analysis Statistics")
async def get_user_analysis_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager)
):
    """
    Get comprehensive analysis statistics for the authenticated user.
    """
    try:
        user_id = user.get("sub")
        
        stats = await db_manager.get_user_analysis_stats(user_id, days)
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_analyses": stats.get("total_analyses", 0),
            "completed_analyses": stats.get("completed_analyses", 0),
            "failed_analyses": stats.get("failed_analyses", 0),
            "success_rate": stats.get("success_rate", 0.0),
            "average_duration": stats.get("average_duration", 0.0),
            "most_used_types": stats.get("most_used_types", []),
            "languages_analyzed": stats.get("languages_analyzed", []),
            "total_lines_analyzed": stats.get("total_lines_analyzed", 0),
            "improvement_score": stats.get("improvement_score", 0.0),
            "learning_progress": stats.get("learning_progress", {})
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )

@router.get("/compare/{analysis_id_1}/{analysis_id_2}", summary="Compare Analyses")
async def compare_analyses(
    analysis_id_1: str = Path(..., description="First analysis ID"),
    analysis_id_2: str = Path(..., description="Second analysis ID"),
    user: dict = Depends(get_current_user),
    db_manager: DatabaseManager = Depends(get_db_manager),
    ai_manager: MultiLLMManager = Depends(get_ai_manager)
):
    """
    Compare two analyses to identify improvements, regressions, and patterns.
    """
    try:
        user_id = user.get("sub")
        
        # Get both analyses
        analysis_1 = await db_manager.get_analysis_by_id(analysis_id_1, user_id)
        analysis_2 = await db_manager.get_analysis_by_id(analysis_id_2, user_id)
        
        if not analysis_1 or not analysis_2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both analyses not found"
            )
        
        # Generate AI-powered comparison
        comparison_prompt = f"""
        Compare these two code analyses and provide insights:
        
        Analysis 1 ({analysis_1.created_at}):
        - Quality Score: {analysis_1.quality_metrics.overall_score if analysis_1.quality_metrics else 'N/A'}
        - Security Issues: {len(analysis_1.security_issues)}
        - Enhancement Suggestions: {len(analysis_1.enhancement_suggestions)}
        
        Analysis 2 ({analysis_2.created_at}):
        - Quality Score: {analysis_2.quality_metrics.overall_score if analysis_2.quality_metrics else 'N/A'}
        - Security Issues: {len(analysis_2.security_issues)}
        - Enhancement Suggestions: {len(analysis_2.enhancement_suggestions)}
        
        Provide detailed comparison insights.
        """
        
        comparison_result = await ai_manager.generate_completion(
            prompt=comparison_prompt,
            max_tokens=2000,
            temperature=0.3
        )
        
        # Calculate metric differences
        quality_diff = 0
        if analysis_1.quality_metrics and analysis_2.quality_metrics:
            quality_diff = analysis_2.quality_metrics.overall_score - analysis_1.quality_metrics.overall_score
        
        security_diff = len(analysis_2.security_issues) - len(analysis_1.security_issues)
        suggestions_diff = len(analysis_2.enhancement_suggestions) - len(analysis_1.enhancement_suggestions)
        
        return {
            "analysis_1_id": analysis_id_1,
            "analysis_2_id": analysis_id_2,
            "comparison_date": datetime.utcnow().isoformat(),
            "quality_score_difference": quality_diff,
            "security_issues_difference": security_diff,
            "suggestions_difference": suggestions_diff,
            "ai_insights": comparison_result.get("content", ""),
            "recommendations": [
                "Review security improvements" if security_diff < 0 else "Monitor new security issues",
                "Code quality improved" if quality_diff > 0 else "Focus on quality improvements",
                "Implementation suggestions updated" if suggestions_diff != 0 else "Consistent suggestions"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare analyses: {str(e)}"
        )

# Background Processing Functions

async def process_code_analysis(
    analysis_id: str,
    context: Dict[str, Any],
    orchestrator: AgentOrchestrator,
    learning_engine: LearningEngine,
    db_manager: DatabaseManager
):
    """Process code analysis in background"""
    try:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.IN_PROGRESS)
        
        # Execute through orchestrator
        result = await orchestrator.process_code_analysis(context)
        
        # Process through learning engine
        learning_insights = await learning_engine.analyze_code_patterns(
            analysis_id=analysis_id,
            code=context["code"],
            language=context["language"],
            analysis_result=result
        )
        
        # Update result with learning insights
        result["learning_insights"] = learning_insights
        result["confidence_score"] = learning_insights.get("confidence", 85.0)
        
        # Store final result
        await db_manager.update_analysis_result(analysis_id, AnalysisStatus.COMPLETED, result)
        
        # Feed back to learning engine
        await learning_engine.record_analysis_success(analysis_id, result)
        
    except Exception as e:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        await learning_engine.record_analysis_failure(analysis_id, str(e))

async def process_repository_analysis(
    analysis_id: str,
    context: Dict[str, Any],
    orchestrator: AgentOrchestrator,
    github_analyzer: GitHubRepositoryAnalyzer,
    learning_engine: LearningEngine,
    db_manager: DatabaseManager
):
    """Process repository analysis in background"""
    try:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.IN_PROGRESS)
        
        # Enhanced repository analysis through orchestrator
        result = await orchestrator.process_repository_analysis(context)
        
        # Apply learning insights
        learning_insights = await learning_engine.analyze_repository_patterns(
            analysis_id=analysis_id,
            repository_url=context["repository_url"],
            analysis_result=result
        )
        
        result["learning_insights"] = learning_insights
        result["confidence_score"] = learning_insights.get("confidence", 90.0)
        
        await db_manager.update_analysis_result(analysis_id, AnalysisStatus.COMPLETED, result)
        await learning_engine.record_analysis_success(analysis_id, result)
        
    except Exception as e:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        await learning_engine.record_analysis_failure(analysis_id, str(e))

async def process_file_analysis(
    analysis_id: str,
    context: Dict[str, Any],
    orchestrator: AgentOrchestrator,
    learning_engine: LearningEngine,
    db_manager: DatabaseManager
):
    """Process multi-file analysis in background"""
    try:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.IN_PROGRESS)
        
        # Multi-file analysis through orchestrator
        result = await orchestrator.process_multi_file_analysis(context)
        
        # Apply learning insights for project structure
        learning_insights = await learning_engine.analyze_project_patterns(
            analysis_id=analysis_id,
            files=context["files"],
            analysis_result=result
        )
        
        result["learning_insights"] = learning_insights
        result["confidence_score"] = learning_insights.get("confidence", 88.0)
        
        await db_manager.update_analysis_result(analysis_id, AnalysisStatus.COMPLETED, result)
        await learning_engine.record_analysis_success(analysis_id, result)
        
    except Exception as e:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        await learning_engine.record_analysis_failure(analysis_id, str(e))

async def process_batch_analysis(
    batch_id: str,
    requests: List[Any],
    user_id: str,
    parallel_execution: bool,
    orchestrator: AgentOrchestrator,
    db_manager: DatabaseManager
):
    """Process batch analysis in background"""
    try:
        results = []
        completed = 0
        failed = 0
        
        if parallel_execution:
            # Process requests in parallel
            tasks = []
            for i, request in enumerate(requests):
                task = asyncio.create_task(
                    process_single_batch_item(request, user_id, orchestrator, db_manager)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    failed += 1
                else:
                    completed += 1
                    results.append(result)
        else:
            # Process requests sequentially
            for request in requests:
                try:
                    result = await process_single_batch_item(request, user_id, orchestrator, db_manager)
                    results.append(result)
                    completed += 1
                except Exception as e:
                    failed += 1
                    results.append({"error": str(e), "request": request})
                
                # Update batch progress
                await db_manager.update_batch_progress(batch_id, completed, failed)
        
        # Update final batch status
        final_status = "completed" if failed == 0 else "partial_failure" if completed > 0 else "failed"
        await db_manager.update_batch_status(batch_id, final_status, results)
        
    except Exception as e:
        await db_manager.update_batch_status(batch_id, "failed", str(e))

async def process_single_batch_item(
    request: Any,
    user_id: str,
    orchestrator: AgentOrchestrator,
    db_manager: DatabaseManager
):
    """Process a single item in a batch analysis"""
    analysis_id = str(uuid.uuid4())
    
    try:
        # Create individual analysis record
        analysis_data = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "analysis_type": request.analysis_type,
            "status": AnalysisStatus.PENDING,
            "created_at": datetime.utcnow(),
            "request_data": request.dict(),
            "priority": "medium"
        }
        
        await db_manager.create_analysis_record(analysis_data)
        
        # Process based on request type
        if isinstance(request, CodeAnalysisRequest):
            context = {
                "analysis_id": analysis_id,
                "user_id": user_id,
                "code": request.code,
                "language": request.language,
                "filename": request.filename,
                "analysis_type": request.analysis_type
            }
            result = await orchestrator.process_code_analysis(context)
        elif isinstance(request, RepositoryAnalysisRequest):
            context = {
                "analysis_id": analysis_id,
                "user_id": user_id,
                "repository_url": request.repository_url,
                "branch": request.branch,
                "analysis_type": request.analysis_type
            }
            result = await orchestrator.process_repository_analysis(context)
        elif isinstance(request, FileAnalysisRequest):
            context = {
                "analysis_id": analysis_id,
                "user_id": user_id,
                "files": request.files,
                "analysis_type": request.analysis_type
            }
            result = await orchestrator.process_multi_file_analysis(context)
        else:
            raise ValueError(f"Unsupported request type: {type(request)}")
        
        # Update with results
        await db_manager.update_analysis_result(analysis_id, AnalysisStatus.COMPLETED, result)
        
        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "result": result
        }
        
    except Exception as e:
        await db_manager.update_analysis_status(analysis_id, AnalysisStatus.FAILED, str(e))
        raise

async def process_analysis_retry(
    new_analysis_id: str,
    original_analysis_id: str,
    context: Dict[str, Any],
    orchestrator: AgentOrchestrator,
    learning_engine: LearningEngine,
    db_manager: DatabaseManager
):
    """Process analysis retry with learning improvements"""
    try:
        await db_manager.update_analysis_status(new_analysis_id, AnalysisStatus.IN_PROGRESS)
        
        # Execute with enhanced parameters
        result = await orchestrator.process_enhanced_analysis(context)
        
        # Apply learning insights
        learning_insights = await learning_engine.apply_retry_learnings(
            original_analysis_id=original_analysis_id,
            new_analysis_id=new_analysis_id,
            result=result
        )
        
        result["learning_insights"] = learning_insights
        result["confidence_score"] = min(95.0, learning_insights.get("confidence", 85.0) + 10.0)
        
        await db_manager.update_analysis_result(new_analysis_id, AnalysisStatus.COMPLETED, result)
        await learning_engine.record_retry_success(original_analysis_id, new_analysis_id, result)
        
    except Exception as e:
        await db_manager.update_analysis_status(new_analysis_id, AnalysisStatus.FAILED, str(e))
        await learning_engine.record_retry_failure(original_analysis_id, new_analysis_id, str(e))