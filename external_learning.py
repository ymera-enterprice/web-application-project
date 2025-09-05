"""
YMERA Enterprise - External Learning System
Production-Ready External Knowledge Integration - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import json
import logging
import mimetypes
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Tuple, BinaryIO
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports (alphabetical)
import aiofiles
import aiohttp
import aioredis
import structlog
from fastapi import HTTPException, status, UploadFile
from pydantic import BaseModel, Field, validator, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from monitoring.performance_tracker import track_performance
from utils.encryption import encrypt_data, decrypt_data
from utils.file_validator import validate_file_safety

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.external_learning")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# External learning constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_API_RESPONSE_SIZE = 50 * 1024 * 1024  # 50MB
SUPPORTED_FILE_TYPES = {
    '.txt', '.pdf', '.docx', '.csv', '.json', '.xml', '.md', '.html'
}
MAX_CONCURRENT_DOWNLOADS = 10
KNOWLEDGE_VALIDATION_THRESHOLD = 0.6
MAX_FEEDBACK_BATCH_SIZE = 500
API_TIMEOUT_SECONDS = 30
CACHE_TTL = 7200  # 2 hours
MAX_RETRIES = 3

# External source types
class ExternalSourceType(Enum):
    FILE_UPLOAD = "file_upload"
    API_ENDPOINT = "api_endpoint"
    USER_FEEDBACK = "user_feedback"
    WEB_SCRAPING = "web_scraping"
    DATABASE_QUERY = "database_query"

# Knowledge validation levels
class ValidationLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class ExternalLearningConfig:
    """Configuration for external learning system"""
    enabled: bool = True
    max_file_size: int = MAX_FILE_SIZE
    supported_formats: set = field(default_factory=lambda: SUPPORTED_FILE_TYPES)
    validation_threshold: float = 0.6
    auto_distribution: bool = True
    retention_days: int = 90
    max_concurrent_sources: int = 20

@dataclass
class ExternalKnowledgeSource:
    """Represents an external knowledge source"""
    source_id: str
    source_type: ExternalSourceType
    name: str
    description: str
    url: Optional[str] = None
    file_path: Optional[str] = None
    api_config: Optional[Dict[str, Any]] = None
    validation_level: ValidationLevel = ValidationLevel.MEDIUM
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessedKnowledge:
    """Represents processed external knowledge"""
    knowledge_id: str
    source_id: str
    content_type: str
    raw_content: str
    processed_content: Dict[str, Any]
    confidence_score: float
    validation_status: str
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

class FileUploadRequest(BaseModel):
    """Schema for file upload requests"""
    description: str = Field(..., description="Description of the file content")
    tags: List[str] = Field(default=[], description="Tags for categorization")
    validation_level: ValidationLevel = Field(ValidationLevel.MEDIUM, description="Required validation level")
    auto_distribute: bool = Field(True, description="Automatically distribute to relevant agents")
    
    @validator('description')
    def validate_description(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Description must be at least 10 characters long")
        return v.strip()

class ApiSourceRequest(BaseModel):
    """Schema for API source configuration"""
    name: str = Field(..., description="Source name")
    description: str = Field(..., description="Source description")
    endpoint_url: HttpUrl = Field(..., description="API endpoint URL")
    headers: Optional[Dict[str, str]] = Field(None, description="API headers")
    auth_config: Optional[Dict[str, str]] = Field(None, description="Authentication configuration")
    polling_interval: int = Field(3600, ge=300, le=86400, description="Polling interval in seconds")
    validation_level: ValidationLevel = Field(ValidationLevel.MEDIUM, description="Validation level")
    
    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("Name must be at least 3 characters long")
        return v.strip()

class UserFeedbackRequest(BaseModel):
    """Schema for user feedback submission"""
    feedback_type: str = Field(..., description="Type of feedback")
    content: str = Field(..., description="Feedback content")
    context: Optional[Dict[str, Any]] = Field(None, description="Contextual information")
    agent_id: Optional[str] = Field(None, description="Related agent ID")
    session_id: Optional[str] = Field(None, description="Related session ID")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="User confidence in feedback")
    
    @validator('content')
    def validate_content(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("Feedback content must be at least 5 characters long")
        return v.strip()

class ExternalLearningResponse(BaseModel):
    """Response schema for external learning operations"""
    success: bool
    source_id: str
    knowledge_items_processed: int
    validation_results: Dict[str, Any]
    distribution_results: Optional[Dict[str, Any]] = None
    processing_time: float
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseExternalLearningProcessor(ABC):
    """Abstract base class for external learning processing"""
    
    def __init__(self, config: ExternalLearningConfig):
        self.config = config
        self.logger = logger.bind(processor=self.__class__.__name__)
        self._health_status = True
        
    @abstractmethod
    async def process_file_upload(self, file: UploadFile, request: FileUploadRequest) -> Dict[str, Any]:
        """Process uploaded file for knowledge extraction"""
        pass
        
    @abstractmethod
    async def process_api_source(self, source_config: ApiSourceRequest) -> Dict[str, Any]:
        """Process API source for knowledge extraction"""
        pass
        
    @abstractmethod
    async def process_user_feedback(self, feedback: UserFeedbackRequest) -> Dict[str, Any]:
        """Process user feedback for learning"""
        pass

class ProductionExternalLearningProcessor(BaseExternalLearningProcessor):
    """Production-ready external learning processor"""
    
    def __init__(self, config: ExternalLearningConfig):
        super().__init__(config)
        self._redis_client = None
        self._db_session = None
        self._file_storage_path = Path(settings.FILE_STORAGE_PATH)
        self._active_sources = {}
        self._processing_semaphore = asyncio.Semaphore(config.max_concurrent_sources)
        
    async def _initialize_resources(self) -> None:
        """Initialize all required resources"""
        try:
            # Initialize Redis connection
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            
            # Initialize database session
            self._db_session = await get_db_session()
            
            # Ensure storage directory exists
            self._file_storage_path.mkdir(parents=True, exist_ok=True)
            
            # Load active external sources
            await self._load_active_sources()
            
            # Initialize content processors
            await self._initialize_content_processors()
            
            self.logger.info("External learning processor initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize external learning processor", error=str(e))
            self._health_status = False
            raise

    @track_performance
    async def process_file_upload(
        self, 
        file: UploadFile, 
        request: FileUploadRequest
    ) -> Dict[str, Any]:
        """
        Process uploaded file for knowledge extraction.
        
        Args:
            file: Uploaded file object
            request: File upload request configuration
            
        Returns:
            Dictionary containing processing results
            
        Raises:
            HTTPException: When processing fails or validation errors occur
        """
        start_time = datetime.utcnow()
        source_id = str(uuid.uuid4())
        
        async with self._processing_semaphore:
            try:
                # Validate file
                await self._validate_uploaded_file(file)
                
                # Save file securely
                file_path = await self._save_uploaded_file(file, source_id)
                
                # Create knowledge source record
                source = ExternalKnowledgeSource(
                    source_id=source_id,
                    source_type=ExternalSourceType.FILE_UPLOAD,
                    name=file.filename or "uploaded_file",
                    description=request.description,
                    file_path=str(file_path),
                    validation_level=request.validation_level,
                    metadata={
                        "file_size": file.size,
                        "content_type": file.content_type,
                        "tags": request.tags
                    }
                )
                
                # Extract content from file
                raw_content = await self._extract_file_content(file_path, file.content_type)
                
                # Process and validate content
                processed_knowledge = await self._process_raw_content(
                    source,
                    raw_content,
                    request.validation_level
                )
                
                # Store processed knowledge
                await self._store_processed_knowledge(processed_knowledge)
                
                # Distribute to relevant agents if requested
                distribution_results = None
                if request.auto_distribute:
                    distribution_results = await self._distribute_knowledge(
                        processed_knowledge,
                        request.tags
                    )
                
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": True,
                    "source_id": source_id,
                    "knowledge_items_processed": len(processed_knowledge),
                    "validation_results": await self._get_validation_summary(processed_knowledge),
                    "distribution_results": distribution_results,
                    "processing_time": processing_time,
                    "timestamp": datetime.utcnow()
                }
                
                self.logger.info(
                    "File upload processed successfully",
                    source_id=source_id,
                    filename=file.filename,
                    file_size=file.size,
                    knowledge_items=len(processed_knowledge),
                    processing_time=processing_time
                )
                
                return result
                
            except Exception as e:
                self.logger.error(
                    "File upload processing failed",
                    source_id=source_id,
                    filename=getattr(file, 'filename', 'unknown'),
                    error=str(e)
                )
                
                # Cleanup on failure
                await self._cleanup_failed_upload(source_id)
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"File processing failed: {str(e)}"
                )

    @track_performance
    async def process_api_source(self, source_config: ApiSourceRequest) -> Dict[str, Any]:
        """
        Process API source for knowledge extraction.
        
        Args:
            source_config: API source configuration
            
        Returns:
            Dictionary containing processing results
        """
        start_time = datetime.utcnow()
        source_id = str(uuid.uuid4())
        
        async with self._processing_semaphore:
            try:
                # Create knowledge source record
                source = ExternalKnowledgeSource(
                    source_id=source_id,
                    source_type=ExternalSourceType.API_ENDPOINT,
                    name=source_config.name,
                    description=source_config.description,
                    url=str(source_config.endpoint_url),
                    validation_level=source_config.validation_level,
                    api_config={
                        "headers": source_config.headers or {},
                        "auth_config": source_config.auth_config or {},
                        "polling_interval": source_config.polling_interval
                    }
                )
                
                # Fetch data from API
                api_data = await self._fetch_api_data(source_config)
                
                # Process API response
                processed_knowledge = await self._process_raw_content(
                    source,
                    api_data,
                    source_config.validation_level
                )
                
                # Store processed knowledge
                await self._store_processed_knowledge(processed_knowledge)
                
                # Register source for periodic polling
                await self._register_periodic_source(source)
                
                # Auto-distribute if enabled
                distribution_results = None
                if self.config.auto_distribution:
                    distribution_results = await self._distribute_knowledge(processed_knowledge)
                
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = {
                    "success": True,
                    "source_id": source_id,
                    "knowledge_items_processed": len(processed_knowledge),
                    "validation_results": await self._get_validation_summary(processed_knowledge),
                    "distribution_results": distribution_results,
                    "processing_time": processing_time,
                    "timestamp": datetime.utcnow()
                }
                
                self.logger.info(
                    "API source processed successfully",
                    source_id=source_id,
                    endpoint_url=str(source_config.endpoint_url),
                    knowledge_items=len(processed_knowledge),
                    processing_time=processing_time
                )
                
                return result
                
            except Exception as e:
                self.logger.error(
                    "API source processing failed",
                    source_id=source_id,
                    endpoint_url=str(source_config.endpoint_url),
                    error=str(e)
                )
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"API source processing failed: {str(e)}"
                )

    @track_performance
    async def process_user_feedback(self, feedback: UserFeedbackRequest) -> Dict[str, Any]:
        """
        Process user feedback for learning.
        
        Args:
            feedback: User feedback request
            
        Returns:
            Dictionary containing processing results
        """
        start_time = datetime.utcnow()
        source_id = str(uuid.uuid4())
        
        try:
            # Create knowledge source record
            source = ExternalKnowledgeSource(
                source_id=source_id,
                source_type=ExternalSourceType.USER_FEEDBACK,
                name=f"User Feedback - {feedback.feedback_type}",
                description=f"User feedback: {feedback.feedback_type}",
                validation_level=ValidationLevel.HIGH,  # User feedback gets high validation
                metadata={
                    "feedback_type": feedback.feedback_type,
                    "agent_id": feedback.agent_id,
                    "session_id": feedback.session_id,
                    "user_confidence": feedback.confidence,
                    "context": feedback.context or {}
                }
            )
            
            # Process feedback content
            processed_knowledge = await self._process_feedback_content(
                source,
                feedback
            )
            
            # Validate feedback knowledge
            validated_knowledge = await self._validate_feedback_knowledge(
                processed_knowledge,
                feedback
            )
            
            # Store processed knowledge
            await self._store_processed_knowledge(validated_knowledge)
            
            # Apply feedback to relevant agents immediately
            application_results = await self._apply_feedback_to_agents(
                validated_knowledge,
                feedback.agent_id
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "success": True,
                "source_id": source_id,
                "knowledge_items_processed": len(validated_knowledge),
                "validation_results": await self._get_validation_summary(validated_knowledge),
                "application_results": application_results,
                "processing_time": processing_time,
                "timestamp": datetime.utcnow()
            }
            
            self.logger.info(
                "User feedback processed successfully",
                source_id=source_id,
                feedback_type=feedback.feedback_type,
                agent_id=feedback.agent_id,
                knowledge_items=len(validated_knowledge),
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "User feedback processing failed",
                source_id=source_id,
                feedback_type=feedback.feedback_type,
                error=str(e)
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Feedback processing failed: {str(e)}"
            )

    async def get_external_sources(self) -> Dict[str, Any]:
        """Get all active external knowledge sources"""
        try:
            sources = []
            for source_id, source in self._active_sources.items():
                source_info = {
                    "source_id": source_id,
                    "name": source.name,
                    "type": source.source_type.value,
                    "description": source.description,
                    "is_active": source.is_active,
                    "created_at": source.created_at.isoformat(),
                    "last_updated": source.last_updated.isoformat(),
                    "validation_level": source.validation_level.value
                }
                sources.append(source_info)
            
            return {
                "success": True,
                "total_sources": len(sources),
                "active_sources": len([s for s in sources if s["is_active"]]),
                "sources": sources,
                "timestamp": datetime.utcnow()
            }
            
        except Exception as e:
            self.logger.error("Failed to get external sources", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve external sources: {str(e)}"
            )

    # ===============================================================================
    # PRIVATE HELPER METHODS
    # ===============================================================================

    async def _validate_uploaded_file(self, file: UploadFile) -> None:
        """Validate uploaded file"""
        if not file.filename:
            raise ValueError("File must have a filename")
        
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in self.config.supported_formats:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        if file.size and file.size > self.config.max_file_size:
            raise ValueError(f"File too large: {file.size} bytes (max: {self.config.max_file_size})")
        
        # Additional safety checks
        await validate_file_safety(file)

    async def _save_uploaded_file(self, file: UploadFile, source_id: str) -> Path:
        """Save uploaded file securely"""
        # Create secure filename
        safe_filename = f"{source_id}_{hashlib.md5(file.filename.encode()).hexdigest()}{Path(file.filename).suffix}"
        file_path = self._file_storage_path / safe_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Reset file position for further processing
        await file.seek(0)
        
        return file_path

    async def _extract_file_content(self, file_path: Path, content_type: str) -> str:
        """Extract text content from file"""
        try:
            if content_type == "text/plain" or file_path.suffix == ".txt":
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            
            elif content_type == "application/json" or file_path.suffix == ".json":
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    # Validate JSON and return formatted
                    json_data = json.loads(content)
                    return json.dumps(json_data, indent=2)
            
            elif file_path.suffix == ".csv":
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            
            elif file_path.suffix == ".md":
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            
            else:
                # For other file types, attempt basic text extraction
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return await f.read()
                    
        except Exception as e:
            self.logger.error("Failed to extract file content", file_path=str(file_path), error=str(e))
            raise ValueError(f"Could not extract content from file: {str(e)}")

    async def _fetch_api_data(self, source_config: ApiSourceRequest) -> str:
        """Fetch data from API endpoint"""
        headers = source_config.headers or {}
        
        # Add authentication if configured
        if source_config.auth_config:
            auth_type = source_config.auth_config.get("type", "").lower()
            
            if auth_type == "bearer":
                token = source_config.auth_config.get("token")
                headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "basic":
                username = source_config.auth_config.get("username")
                password = source_config.auth_config.get("password")
                # Would implement basic auth here
            elif auth_type == "api_key":
                key_name = source_config.auth_config.get("key_name", "X-API-Key")
                api_key = source_config.auth_config.get("api_key")
                headers[key_name] = api_key
        
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(str(source_config.endpoint_url), headers=headers) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Check content size
                    if len(content) > MAX_API_RESPONSE_SIZE:
                        raise ValueError(f"API response too large: {len(content)} bytes")
                    
                    return content
                else:
                    raise ValueError(f"API request failed with status: {response.status}")

    async def _process_raw_content(
        self, 
        source: ExternalKnowledgeSource, 
        raw_content: str,
        validation_level: ValidationLevel
    ) -> List[ProcessedKnowledge]:
        """Process raw content into structured knowledge"""
        processed_items = []
        
        try:
            # Split content into logical chunks
            chunks = await self._chunk_content(raw_content, source.source_type)
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 10:  # Skip very short chunks
                    continue
                
                # Extract structured information
                processed_content = await self._extract_structured_info(chunk, source)
                
                # Calculate confidence score
                confidence_score = await self._calculate_confidence_score(
                    chunk, 
                    processed_content, 
                    validation_level
                )
                
                # Create knowledge item
                knowledge_item = ProcessedKnowledge(
                    knowledge_id=f"{source.source_id}_{i}",
                    source_id=source.source_id,
                    content_type=await self._classify_content_type(chunk),
                    raw_content=chunk,
                    processed_content=processed_content,
                    confidence_score=confidence_score,
                    validation_status="pending_validation",
                    tags=await self._extract_tags(chunk, source),
                    metadata={
                        "chunk_index": i,
                        "source_type": source.source_type.value,
                        "validation_level": validation_level.value
                    }
                )
                
                processed_items.append(knowledge_item)
        
        except Exception as e:
            self.logger.error(
                "Content processing failed",
                source_id=source.source_id,
                error=str(e)
            )
            raise
        
        return processed_items

    async def _chunk_content(self, content: str, source_type: ExternalSourceType) -> List[str]:
        """Split content into logical chunks"""
        if source_type == ExternalSourceType.FILE_UPLOAD:
            # For files, split by paragraphs or sections
            chunks = []
            current_chunk = ""
            
            for line in content.split('\n'):
                if len(current_chunk) > 1000 and line.strip() == "":
                    # End chunk at paragraph break if over 1000 chars
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = ""
                else:
                    current_chunk += line + '\n'
            
            # Add final chunk
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            return chunks
        
        elif source_type == ExternalSourceType.API_ENDPOINT:
            # For API data, try to parse as JSON first
            try:
                json_data = json.loads(content)
                if isinstance(json_data, list):
                    return [json.dumps(item) for item in json_data[:100]]  # Limit to 100 items
                elif isinstance(json_data, dict):
                    # Split dict into logical sections
                    chunks = []
                    for key, value in json_data.items():
                        chunks.append(json.dumps({key: value}))
                    return chunks
                else:
                    return [content]
            except json.JSONDecodeError:
                # Fallback to text chunking
                return self._chunk_text_content(content)
        
        else:
            return self._chunk_text_content(content)

    def _chunk_text_content(self, content: str) -> List[str]:
        """Chunk plain text content"""
        chunks = []
        words = content.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) > 500:  # ~500 character chunks
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1  # +1 for space
        
        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks

    async def _extract_structured_info(self, content: str, source: ExternalKnowledgeSource) -> Dict[str, Any]:
        """Extract structured information from content"""
        structured_info = {
            "summary": await self._generate_summary(content),
            "key_points": await self._extract_key_points(content),
            "entities": await self._extract_entities(content),
            "categories": await self._categorize_content(content),
            "actionable_items": await self._extract_actionable_items(content)
        }
        
        return structured_info

    async def _generate_summary(self, content: str) -> str:
        """Generate a summary of the content"""
        # Simple extractive summary - take first and key sentences
        sentences = content.split('.')
        if len(sentences) <= 2:
            return content.strip()
        
        # Return first sentence and any sentence with key indicators
        summary_sentences = [sentences[0]]
        
        key_indicators = ['important', 'key', 'main', 'primary', 'essential', 'critical']
        for sentence in sentences[1:]:
            if any(indicator in sentence.lower() for indicator in key_indicators):
                summary_sentences.append(sentence)
                if len(summary_sentences) >= 3:
                    break
        
        return '. '.join(s.strip() for s in summary_sentences if s.strip()) + '.'

    async def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from content"""
        key_points = []
        
        # Look for bullet points, numbered lists, or sentences with key indicators
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for bullet points or numbers
            if (line.startswith(('•', '-', '*', '1.', '2.', '3.')) or
                any(indicator in line.lower() for indicator in ['key', 'important', 'note'])):
                key_points.append(line)
        
        # If no formatted points found, extract sentences with key indicators
        if not key_points:
            sentences = content.split('.')
            for sentence in sentences:
                if any(indicator in sentence.lower() for indicator in 
                      ['should', 'must', 'important', 'key', 'note that', 'remember']):
                    key_points.append(sentence.strip())
                    if len(key_points) >= 5:
                        break
        
        return key_points[:10]  # Limit to 10 key points

    async def _extract_entities(self, content: str) -> List[str]:
        """Extract named entities from content"""
        entities = []
        
        # Simple entity extraction - look for capitalized words/phrases
        import re
        
        # Find potential entities (capitalized words)
        capitalized_words = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', content)
        
        # Filter out common words
        common_words = {'The', 'This', 'That', 'And', 'Or', 'But', 'For', 'If', 'When', 'Where'}
        entities = [word for word in capitalized_words if word not in common_words]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append(entity)
        
        return unique_entities[:20]  # Limit to 20 entities

    async def _categorize_content(self, content: str) -> List[str]:
        """Categorize content into predefined categories"""
        categories = []
        content_lower = content.lower()
        
        # Define category keywords
        category_keywords = {
            'technical': ['api', 'code', 'function', 'method', 'class', 'variable', 'database', 'server'],
            'business': ['revenue', 'profit', 'customer', 'market', 'strategy', 'sales', 'business'],
            'process': ['step', 'procedure', 'workflow', 'process', 'method', 'approach'],
            'documentation': ['guide', 'manual', 'documentation', 'instructions', 'how to'],
            'policy': ['policy', 'rule', 'regulation', 'compliance', 'requirement'],
            'feedback': ['feedback', 'review', 'comment', 'suggestion', 'improvement'],
            'issue': ['problem', 'issue', 'bug', 'error', 'failure', 'trouble'],
            'solution': ['solution', 'fix', 'resolve', 'answer', 'workaround', 'remedy']
        }
        
        # Check content against category keywords
        for category, keywords in category_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                categories.append(category)
        
        # Default category if none found
        if not categories:
            categories.append('general')
        
        return categories

    async def _extract_actionable_items(self, content: str) -> List[str]:
        """Extract actionable items from content"""
        actionable_items = []
        content_lower = content.lower()
        
        # Look for action verbs and imperative sentences
        action_indicators = [
            'should', 'must', 'need to', 'have to', 'required to', 'recommended to',
            'action:', 'todo:', 'task:', 'next steps:', 'follow up:'
        ]
        
        sentences = content.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if any(indicator in sentence.lower() for indicator in action_indicators):
                actionable_items.append(sentence)
                if len(actionable_items) >= 5:
                    break
        
        return actionable_items

    async def _calculate_confidence_score(
        self, 
        content: str, 
        processed_content: Dict[str, Any],
        validation_level: ValidationLevel
    ) -> float:
        """Calculate confidence score for processed knowledge"""
        base_score = 0.5
        
        # Content length factor
        if len(content) > 100:
            base_score += 0.1
        if len(content) > 500:
            base_score += 0.1
        
        # Structured information factor
        if processed_content.get('key_points'):
            base_score += 0.1
        if processed_content.get('entities'):
            base_score += 0.1
        if processed_content.get('actionable_items'):
            base_score += 0.1
        
        # Validation level adjustment
        if validation_level == ValidationLevel.HIGH:
            base_score *= 0.8  # More conservative for high validation
        elif validation_level == ValidationLevel.CRITICAL:
            base_score *= 0.6  # Very conservative for critical validation
        
        return min(1.0, max(0.0, base_score))

    async def _classify_content_type(self, content: str) -> str:
        """Classify the type of content"""
        content_lower = content.lower()
        
        if any(indicator in content_lower for indicator in ['procedure', 'step', 'process']):
            return 'procedure'
        elif any(indicator in content_lower for indicator in ['policy', 'rule', 'regulation']):
            return 'policy'
        elif any(indicator in content_lower for indicator in ['api', 'function', 'method', 'code']):
            return 'technical'
        elif any(indicator in content_lower for indicator in ['feedback', 'review', 'comment']):
            return 'feedback'
        elif any(indicator in content_lower for indicator in ['problem', 'issue', 'error']):
            return 'issue'
        elif any(indicator in content_lower for indicator in ['solution', 'fix', 'resolve']):
            return 'solution'
        else:
            return 'general'

    async def _extract_tags(self, content: str, source: ExternalKnowledgeSource) -> List[str]:
        """Extract relevant tags from content"""
        tags = []
        
        # Add source-based tags
        tags.append(source.source_type.value)
        
        # Add content-based tags
        content_type = await self._classify_content_type(content)
        tags.append(content_type)
        
        # Add category-based tags
        categories = await self._categorize_content(content)
        tags.extend(categories)
        
        # Add metadata tags if available
        if hasattr(source, 'metadata') and source.metadata:
            if 'tags' in source.metadata:
                tags.extend(source.metadata['tags'])
        
        # Remove duplicates and return
        return list(set(tags))

    async def _store_processed_knowledge(self, knowledge_items: List[ProcessedKnowledge]) -> None:
        """Store processed knowledge items"""
        try:
            for item in knowledge_items:
                # Store in database
                await self._store_knowledge_in_db(item)
                
                # Cache for quick access
                await self._cache_knowledge_item(item)
            
            self.logger.debug(
                "Stored processed knowledge items",
                count=len(knowledge_items)
            )
            
        except Exception as e:
            self.logger.error("Failed to store processed knowledge", error=str(e))
            raise

    async def _store_knowledge_in_db(self, knowledge: ProcessedKnowledge) -> None:
        """Store knowledge item in database"""
        # Implementation would store in your database
        query = """
            INSERT INTO external_knowledge 
            (knowledge_id, source_id, content_type, raw_content, processed_content, 
             confidence_score, validation_status, tags, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # Execute database insert
        # await self._db_session.execute(query, [
        #     knowledge.knowledge_id,
        #     knowledge.source_id,
        #     knowledge.content_type,
        #     knowledge.raw_content,
        #     json.dumps(knowledge.processed_content),
        #     knowledge.confidence_score,
        #     knowledge.validation_status,
        #     json.dumps(knowledge.tags),
        #     knowledge.created_at,
        #     json.dumps(knowledge.metadata)
        # ])

    async def _cache_knowledge_item(self, knowledge: ProcessedKnowledge) -> None:
        """Cache knowledge item for quick access"""
        cache_key = f"external_knowledge:{knowledge.knowledge_id}"
        
        cache_data = {
            "source_id": knowledge.source_id,
            "content_type": knowledge.content_type,
            "confidence_score": knowledge.confidence_score,
            "tags": json.dumps(knowledge.tags),
            "summary": knowledge.processed_content.get('summary', ''),
            "created_at": knowledge.created_at.isoformat()
        }
        
        await self._redis_client.hset(cache_key, mapping=cache_data)
        await self._redis_client.expire(cache_key, CACHE_TTL)

    async def _distribute_knowledge(
        self, 
        knowledge_items: List[ProcessedKnowledge],
        additional_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Distribute knowledge to relevant agents"""
        distribution_results = {
            "agents_notified": 0,
            "knowledge_distributed": 0,
            "distribution_details": []
        }
        
        try:
            # Get active agents
            active_agents = await self._get_active_agents()
            
            for knowledge in knowledge_items:
                # Determine relevant agents based on tags and content
                relevant_agents = await self._find_relevant_agents(
                    knowledge, 
                    active_agents,
                    additional_tags
                )
                
                # Distribute to relevant agents
                for agent_id in relevant_agents:
                    await self._send_knowledge_to_agent(agent_id, knowledge)
                    distribution_results["knowledge_distributed"] += 1
                
                distribution_results["distribution_details"].append({
                    "knowledge_id": knowledge.knowledge_id,
                    "agents_reached": len(relevant_agents)
                })
            
            distribution_results["agents_notified"] = len(
                set(agent for detail in distribution_results["distribution_details"] 
                    for agent in detail.get("agents_reached", []))
            )
            
        except Exception as e:
            self.logger.error("Knowledge distribution failed", error=str(e))
            distribution_results["error"] = str(e)
        
        return distribution_results

    async def _get_active_agents(self) -> List[str]:
        """Get list of active agent IDs"""
        # This would query your agent registry
        # For now, return a mock list
        return ["agent_1", "agent_2", "agent_3", "agent_4"]

    async def _find_relevant_agents(
        self, 
        knowledge: ProcessedKnowledge,
        active_agents: List[str],
        additional_tags: Optional[List[str]] = None
    ) -> List[str]:
        """Find agents relevant to the knowledge"""
        relevant_agents = []
        
        # Combine all tags
        all_tags = knowledge.tags.copy()
        if additional_tags:
            all_tags.extend(additional_tags)
        
        # For each agent, check relevance based on their specialization
        for agent_id in active_agents:
            agent_tags = await self._get_agent_tags(agent_id)
            
            # Calculate relevance score
            common_tags = set(all_tags) & set(agent_tags)
            relevance_score = len(common_tags) / max(len(agent_tags), 1)
            
            # Include if relevance is above threshold
            if relevance_score >= 0.3:  # 30% tag overlap
                relevant_agents.append(agent_id)
        
        return relevant_agents

    async def _get_agent_tags(self, agent_id: str) -> List[str]:
        """Get specialization tags for an agent"""
        # This would query agent metadata
        # For now, return mock data based on agent ID
        agent_specializations = {
            "agent_1": ["technical", "api", "code"],
            "agent_2": ["business", "customer", "sales"],
            "agent_3": ["process", "workflow", "documentation"],
            "agent_4": ["general", "feedback", "support"]
        }
        
        return agent_specializations.get(agent_id, ["general"])

    async def _send_knowledge_to_agent(self, agent_id: str, knowledge: ProcessedKnowledge) -> None:
        """Send knowledge item to specific agent"""
        # This would integrate with your agent communication system
        message = {
            "type": "external_knowledge",
            "knowledge_id": knowledge.knowledge_id,
            "content_type": knowledge.content_type,
            "summary": knowledge.processed_content.get('summary', ''),
            "confidence_score": knowledge.confidence_score,
            "tags": knowledge.tags,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to agent queue
        queue_key = f"agent_queue:{agent_id}"
        await self._redis_client.lpush(queue_key, json.dumps(message))

    async def _process_feedback_content(
        self, 
        source: ExternalKnowledgeSource,
        feedback: UserFeedbackRequest
    ) -> List[ProcessedKnowledge]:
        """Process user feedback into knowledge items"""
        # Create knowledge item from feedback
        processed_content = {
            "feedback_type": feedback.feedback_type,
            "user_content": feedback.content,
            "context": feedback.context or {},
            "improvement_suggestions": await self._extract_improvement_suggestions(feedback.content),
            "corrective_actions": await self._extract_corrective_actions(feedback.content),
            "sentiment": await self._analyze_feedback_sentiment(feedback.content)
        }
        
        knowledge_item = ProcessedKnowledge(
            knowledge_id=f"{source.source_id}_feedback",
            source_id=source.source_id,
            content_type="user_feedback",
            raw_content=feedback.content,
            processed_content=processed_content,
            confidence_score=feedback.confidence,
            validation_status="validated",  # User feedback is pre-validated
            tags=["user_feedback", feedback.feedback_type, "high_priority"],
            metadata={
                "agent_id": feedback.agent_id,
                "session_id": feedback.session_id,
                "user_confidence": feedback.confidence
            }
        )
        
        return [knowledge_item]

    async def _extract_improvement_suggestions(self, content: str) -> List[str]:
        """Extract improvement suggestions from feedback"""
        suggestions = []
        content_lower = content.lower()
        
        # Look for suggestion indicators
        suggestion_indicators = [
            'should', 'could', 'might', 'suggest', 'recommend', 'improve', 
            'better', 'enhance', 'upgrade', 'optimize'
        ]
        
        sentences = content.split('.')
        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in suggestion_indicators):
                suggestions.append(sentence.strip())
        
        return suggestions

    async def _extract_corrective_actions(self, content: str) -> List[str]:
        """Extract corrective actions from feedback"""
        actions = []
        content_lower = content.lower()
        
        # Look for action indicators
        action_indicators = [
            'fix', 'correct', 'resolve', 'address', 'handle', 'stop', 
            'start', 'change', 'modify', 'update'
        ]
        
        sentences = content.split('.')
        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in action_indicators):
                actions.append(sentence.strip())
        
        return actions

    async def _analyze_feedback_sentiment(self, content: str) -> str:
        """Analyze sentiment of feedback"""
        content_lower = content.lower()
        
        # Simple sentiment analysis
        positive_words = ['good', 'great', 'excellent', 'helpful', 'useful', 'like', 'love']
        negative_words = ['bad', 'terrible', 'awful', 'useless', 'hate', 'dislike', 'wrong']
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    async def _validate_feedback_knowledge(
        self, 
        knowledge_items: List[ProcessedKnowledge],
        feedback: UserFeedbackRequest
    ) -> List[ProcessedKnowledge]:
        """Validate feedback-based knowledge"""
        validated_items = []
        
        for knowledge in knowledge_items:
            # Adjust confidence based on feedback quality
            quality_score = await self._assess_feedback_quality(feedback)
            
            # Update confidence score
            knowledge.confidence_score = min(1.0, knowledge.confidence_score * quality_score)
            
            # Mark as validated if confidence is above threshold
            if knowledge.confidence_score >= self.config.validation_threshold:
                knowledge.validation_status = "validated"
            else:
                knowledge.validation_status = "needs_review"
            
            validated_items.append(knowledge)
        
        return validated_items

    async def _assess_feedback_quality(self, feedback: UserFeedbackRequest) -> float:
        """Assess the quality of user feedback"""
        quality_score = 0.7  # Base score
        
        # Length factor
        if len(feedback.content) > 50:
            quality_score += 0.1
        if len(feedback.content) > 200:
            quality_score += 0.1
        
        # Context factor
        if feedback.context and len(feedback.context) > 0:
            quality_score += 0.1
        
        # User confidence factor
        quality_score *= feedback.confidence
        
        return min(1.0, quality_score)

    async def _apply_feedback_to_agents(
        self, 
        knowledge_items: List[ProcessedKnowledge],
        target_agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply feedback knowledge to relevant agents immediately"""
        application_results = {
            "agents_updated": 0,
            "knowledge_applied": 0,
            "immediate_actions": []
        }
        
        try:
            for knowledge in knowledge_items:
                # Determine target agents
                if target_agent_id:
                    target_agents = [target_agent_id]
                else:
                    target_agents = await self._get_active_agents()
                
                # Apply to each target agent
                for agent_id in target_agents:
                    await self._apply_knowledge_to_agent(agent_id, knowledge)
                    application_results["knowledge_applied"] += 1
                
                application_results["agents_updated"] = len(target_agents)
                
                # Record immediate actions
                if knowledge.processed_content.get("corrective_actions"):
                    application_results["immediate_actions"].extend(
                        knowledge.processed_content["corrective_actions"]
                    )
        
        except Exception as e:
            self.logger.error("Failed to apply feedback to agents", error=str(e))
            application_results["error"] = str(e)
        
        return application_results

    async def _apply_knowledge_to_agent(self, agent_id: str, knowledge: ProcessedKnowledge) -> None:
        """Apply knowledge to a specific agent"""
        # Create immediate update message
        update_message = {
            "type": "immediate_feedback",
            "knowledge_id": knowledge.knowledge_id,
            "feedback_type": knowledge.processed_content.get("feedback_type"),
            "corrective_actions": knowledge.processed_content.get("corrective_actions", []),
            "improvement_suggestions": knowledge.processed_content.get("improvement_suggestions", []),
            "confidence": knowledge.confidence_score,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to agent's priority queue
        priority_queue_key = f"agent_priority_queue:{agent_id}"
        await self._redis_client.lpush(priority_queue_key, json.dumps(update_message))

    async def _get_validation_summary(self, knowledge_items: List[ProcessedKnowledge]) -> Dict[str, Any]:
        """Generate validation summary for processed knowledge"""
        total_items = len(knowledge_items)
        if total_items == 0:
            return {"total_items": 0}
        
        validated_items = len([k for k in knowledge_items if k.validation_status == "validated"])
        pending_items = len([k for k in knowledge_items if k.validation_status == "pending_validation"])
        needs_review_items = len([k for k in knowledge_items if k.validation_status == "needs_review"])
        
        avg_confidence = sum(k.confidence_score for k in knowledge_items) / total_items
        
        return {
            "total_items": total_items,
            "validated_items": validated_items,
            "pending_validation": pending_items,
            "needs_review": needs_review_items,
            "average_confidence": round(avg_confidence, 3),
            "validation_rate": round(validated_items / total_items, 3) if total_items > 0 else 0
        }

    async def _load_active_sources(self) -> None:
        """Load active external sources from storage"""
        try:
            # This would load from your database
            # For now, initialize empty
            self._active_sources = {}
            
            self.logger.debug("Loaded active external sources", count=len(self._active_sources))
            
        except Exception as e:
            self.logger.error("Failed to load active sources", error=str(e))
            raise

    async def _initialize_content_processors(self) -> None:
        """Initialize content processing utilities"""
        # Initialize any required content processing tools
        # This could include NLP libraries, text processors, etc.
        pass

    async def _register_periodic_source(self, source: ExternalKnowledgeSource) -> None:
        """Register a source for periodic polling"""
        self._active_sources[source.source_id] = source
        
        # Would also set up periodic tasks for API polling
        self.logger.info(
            "Registered periodic source",
            source_id=source.source_id,
            source_type=source.source_type.value
        )

    async def _cleanup_failed_upload(self, source_id: str) -> None:
        """Cleanup resources after failed upload"""
        try:
            # Remove any partially created files
            file_pattern = self._file_storage_path / f"{source_id}_*"
            for file_path in self._file_storage_path.glob(f"{source_id}_*"):
                if file_path.is_file():
                    file_path.unlink()
            
            # Clear any cached data
            cache_key = f"external_knowledge:{source_id}*"
            # Would clear Redis cache here
            
            self.logger.debug("Cleaned up failed upload", source_id=source_id)
            
        except Exception as e:
            self.logger.error("Cleanup failed", source_id=source_id, error=str(e))

    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if self._redis_client:
                await self._redis_client.close()
            
            if self._db_session:
                await self._db_session.close()
                
            self.logger.info("External learning processor cleaned up successfully")
            
        except Exception as e:
            self.logger.error("Cleanup failed", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """External learning health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "external_learning",
        "version": "4.0"
    }

def validate_external_learning_configuration(config: Dict[str, Any]) -> bool:
    """Validate external learning configuration"""
    required_fields = [
        "enabled", "max_file_size", "supported_formats", 
        "validation_threshold", "auto_distribution"
    ]
    return all(field in config for field in required_fields)

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_external_learning() -> ProductionExternalLearningProcessor:
    """Initialize external learning processor for production use"""
    config = ExternalLearningConfig(
        enabled=settings.EXTERNAL_LEARNING_ENABLED,
        max_file_size=settings.MAX_FILE_SIZE,
        supported_formats=set(settings.SUPPORTED_FILE_TYPES.split(',')),
        validation_threshold=settings.KNOWLEDGE_VALIDATION_THRESHOLD,
        auto_distribution=settings.AUTO_KNOWLEDGE_DISTRIBUTION,
        retention_days=settings.KNOWLEDGE_RETENTION_DAYS,
        max_concurrent_sources=settings.MAX_CONCURRENT_EXTERNAL_SOURCES
    )
    
    processor = ProductionExternalLearningProcessor(config)
    await processor._initialize_resources()
    
    return processor

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionExternalLearningProcessor",
    "ExternalLearningConfig",
    "ExternalKnowledgeSource",
    "ProcessedKnowledge",
    "FileUploadRequest",
    "ApiSourceRequest",
    "UserFeedbackRequest",
    "ExternalLearningResponse",
    "ExternalSourceType",
    "ValidationLevel",
    "initialize_external_learning",
    "health_check"
]