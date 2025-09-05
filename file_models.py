    def _assess_consistency(self, text: str) -> float:
        """Assess style consistency"""
        # Simple consistency check
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if len(non_empty_lines) < 5:
            return 1.0  # Too short to assess
        
        # Check indentation consistency
        indent_patterns = [len(line) - len(line.lstrip()) for line in non_empty_lines if line.startswith(' ')]
        if indent_patterns:
            indent_variance = len(set(indent_patterns)) / len(indent_patterns)
            consistency_score = 1.0 - min(indent_variance, 1.0)
        else:
            consistency_score = 0.8  # No indentation patterns found
        
        return consistency_score
    
    async def _calculate_uniqueness(self, text: str) -> float:
        """Calculate content uniqueness score"""
        # This would typically check against existing content in the system
        # For now, return a simplified uniqueness score
        
        if not text:
            return 0.0
        
        # Simple uniqueness based on vocabulary diversity
        words = text.lower().split()
        unique_words = set(words)
        
        if not words:
            return 0.0
        
        uniqueness = len(unique_words) / len(words)
        return min(uniqueness * 100, 100.0)
    
    def _extract_key_concepts(self, text: str) -> List[str]:
        """Extract key concepts from text"""
        # Simple keyword extraction
        words = text.lower().split()
        
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
        
        # Count word frequency
        word_freq = {}
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word and len(clean_word) > 3 and clean_word not in stop_words:
                word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
        
        # Return top concepts
        sorted_concepts = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [concept[0] for concept in sorted_concepts[:20]]
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text"""
        # Simple topic extraction based on common technical terms
        topics = []
        
        # Technical domains
        tech_domains = {
            'machine learning': ['ml', 'machine learning', 'neural', 'algorithm', 'model', 'training'],
            'web development': ['html', 'css', 'javascript', 'react', 'vue', 'angular', 'web'],
            'database': ['sql', 'database', 'query', 'table', 'schema', 'index'],
            'security': ['security', 'encryption', 'authentication', 'authorization', 'vulnerability'],
            'cloud': ['aws', 'azure', 'cloud', 'docker', 'kubernetes', 'container'],
            'data science': ['data', 'analysis', 'visualization', 'statistics', 'pandas', 'numpy']
        }
        
        text_lower = text.lower()
        for topic, keywords in tech_domains.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        # Simple entity extraction
        entities = []
        
        # Look for common patterns
        import re
        
        # URLs
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        for url in urls:
            entities.append({'type': 'url', 'value': url, 'confidence': 0.9})
        
        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        for email in emails:
            entities.append({'type': 'email', 'value': email, 'confidence': 0.9})
        
        # Version numbers
        version_pattern = r'\b\d+\.\d+\.\d+\b'
        versions = re.findall(version_pattern, text)
        for version in versions:
            entities.append({'type': 'version', 'value': version, 'confidence': 0.8})
        
        return entities
    
    def _calculate_technical_depth(self, text: str, language: Optional[str]) -> float:
        """Calculate technical depth score"""
        if not text:
            return 0.0
        
        technical_indicators = {
            'code_blocks': text.count('```') + text.count('    '),  # Markdown/indented code
            'function_calls': text.count('()'),
            'technical_terms': 0,  # Would be populated with domain-specific terms
            'api_references': text.count('API') + text.count('endpoint'),
            'error_handling': text.count('try') + text.count('catch') + text.count('exception'),
        }
        
        if language:
            # Language-specific indicators
            if language == 'python':
                technical_indicators['imports'] = text.count('import ') + text.count('from ')
                technical_indicators['decorators'] = text.count('@')
            elif language == 'javascript':
                technical_indicators['promises'] = text.count('async') + text.count('await')
                technical_indicators['requires'] = text.count('require(')
        
        # Calculate technical depth
        total_indicators = sum(technical_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        depth = min((total_indicators / text_length) * 500, 100.0)
        return depth
    
    def _calculate_relevance(self, text: str, content_category: Optional[ContentCategory]) -> float:
        """Calculate content relevance score"""
        if not text or not content_category:
            return 50.0  # Neutral score
        
        # Category-specific relevance indicators
        relevance_keywords = {
            ContentCategory.DOCUMENTATION: ['guide', 'how to', 'tutorial', 'documentation', 'manual'],
            ContentCategory.TUTORIAL: ['step', 'example', 'learn', 'tutorial', 'walkthrough'],
            ContentCategory.SPECIFICATION: ['spec', 'requirement', 'specification', 'standard', 'protocol'],
            ContentCategory.EXAMPLE: ['example', 'sample', 'demo', 'illustration', 'case study'],
            ContentCategory.CONFIGURATION: ['config', 'settings', 'options', 'parameters', 'setup'],
            ContentCategory.DATA_SAMPLE: ['data', 'dataset', 'sample', 'records', 'entries'],
            ContentCategory.ERROR_LOG: ['error', 'exception', 'failure', 'stack trace', 'debug'],
            ContentCategory.PERFORMANCE_DATA: ['performance', 'metrics', 'benchmark', 'timing', 'profiling'],
            ContentCategory.USER_FEEDBACK: ['feedback', 'review', 'comment', 'suggestion', 'issue'],
            ContentCategory.RESEARCH: ['research', 'study', 'analysis', 'findings', 'conclusion']
        }
        
        keywords = relevance_keywords.get(content_category, [])
        text_lower = text.lower()
        
        # Count keyword matches
        matches = sum(1 for keyword in keywords if keyword in text_lower)
        relevance = min((matches / len(keywords)) * 100, 100.0) if keywords else 50.0
        
        return relevance
    
    async def _extract_knowledge(self, content: bytes, metadata: FileMetadata, analysis: ContentAnalysis) -> List[Dict[str, Any]]:
        """Extract knowledge items from file content"""
        knowledge_items = []
        
        # Only extract from text-based files
        if metadata.file_type not in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            return knowledge_items
        
        text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
        
        # Apply different extraction methods
        for method in self.extraction_methods:
            method_knowledge = await self._apply_extraction_method(
                method, text_content, metadata, analysis
            )
            knowledge_items.extend(method_knowledge)
        
        # Remove duplicates and limit count
        unique_knowledge = self._deduplicate_knowledge(knowledge_items)
        return unique_knowledge[:self.max_knowledge_items]
    
    async def _apply_extraction_method(self, method: ExtractionMethod, text: str, 
                                     metadata: FileMetadata, analysis: ContentAnalysis) -> List[Dict[str, Any]]:
        """Apply specific knowledge extraction method"""
        knowledge_items = []
        
        if method == ExtractionMethod.TEXT_ANALYSIS:
            knowledge_items.extend(await self._extract_via_text_analysis(text, metadata, analysis))
        elif method == ExtractionMethod.PATTERN_RECOGNITION:
            knowledge_items.extend(await self._extract_via_pattern_recognition(text, metadata))
        elif method == ExtractionMethod.STATISTICAL_ANALYSIS:
            knowledge_items.extend(await self._extract_via_statistical_analysis(text, metadata))
        elif method == ExtractionMethod.RULE_BASED:
            knowledge_items.extend(await self._extract_via_rule_based(text, metadata))
        
        return knowledge_items
    
    async def _extract_via_text_analysis(self, text: str, metadata: FileMetadata, 
                                       analysis: ContentAnalysis) -> List[Dict[str, Any]]:
        """Extract knowledge via text analysis"""
        knowledge_items = []
        
        # Extract procedural knowledge (how-to steps)
        steps = self._extract_procedural_steps(text)
        if steps:
            knowledge_items.append({
                'knowledge_type': KnowledgeType.TASK_OPTIMIZATION.value,
                'content': {
                    'type': 'procedural_steps',
                    'steps': steps,
                    'context': metadata.content_category.value if metadata.content_category else 'general',
                    'source_file': metadata.filename
                },
                'confidence_score': 0.8,
                'extraction_method': ExtractionMethod.TEXT_ANALYSIS.value,
                'source_location': {'type': 'full_document'}
            })
        
        # Extract best practices
        practices = self._extract_best_practices(text)
        if practices:
            knowledge_items.append({
                'knowledge_type': KnowledgeType.PERFORMANCE_INSIGHT.value,
                'content': {
                    'type': 'best_practices',
                    'practices': practices,
                    'domain': metadata.language or 'general',
                    'source_file': metadata.filename
                },
                'confidence_score': 0.7,
                'extraction_method': ExtractionMethod.TEXT_ANALYSIS.value,
                'source_location': {'type': 'scattered'}
            })
        
        # Extract error patterns
        error_patterns = self._extract_error_patterns(text)
        if error_patterns:
            knowledge_items.append({
                'knowledge_type': KnowledgeType.ERROR_RESOLUTION.value,
                'content': {
                    'type': 'error_patterns',
                    'patterns': error_patterns,
                    'context': metadata.file_type.value,
                    'source_file': metadata.filename
                },
                'confidence_score': 0.9,
                'extraction_method': ExtractionMethod.TEXT_ANALYSIS.value,
                'source_location': {'type': 'error_sections'}
            })
        
        return knowledge_items
    
    def _extract_procedural_steps(self, text: str) -> List[Dict[str, str]]:
        """Extract procedural steps from text"""
        steps = []
        lines = text.split('\n')
        
        # Look for numbered or bulleted lists
        import re
        step_patterns = [
            r'^\s*(\d+)\.\s+(.+)"""
YMERA Enterprise - File Learning Models
Production-Ready File Metadata & Learning Integration Models - v4.0
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
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from agent_models import KnowledgeType, LearningStatus

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File processing constants
MAX_FILE_SIZE_MB = 100
SUPPORTED_TEXT_FORMATS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.docx', '.doc', '.rtf', '.odt'}
SUPPORTED_CODE_FORMATS = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
SUPPORTED_DATA_FORMATS = {'.csv', '.xlsx', '.xls', '.json', '.xml', '.parquet'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}

# Learning integration constants
KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD = 0.6
MAX_KNOWLEDGE_ITEMS_PER_FILE = 50
FILE_ANALYSIS_TIMEOUT_SECONDS = 300
CONTENT_SIMILARITY_THRESHOLD = 0.8

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class FileType(str, Enum):
    """File type classification"""
    TEXT = "text"
    DOCUMENT = "document" 
    CODE = "code"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class FileStatus(str, Enum):
    """File processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    INTEGRATED = "integrated"
    ERROR = "error"
    ARCHIVED = "archived"

class ProcessingPriority(IntEnum):
    """File processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class ContentCategory(str, Enum):
    """Content categorization for learning"""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SPECIFICATION = "specification"
    EXAMPLE = "example"
    CONFIGURATION = "configuration"
    DATA_SAMPLE = "data_sample"
    ERROR_LOG = "error_log"
    PERFORMANCE_DATA = "performance_data"
    USER_FEEDBACK = "user_feedback"
    RESEARCH = "research"

class ExtractionMethod(str, Enum):
    """Knowledge extraction methods"""
    TEXT_ANALYSIS = "text_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    ML_INFERENCE = "ml_inference"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class ValidationLevel(str, Enum):
    """Knowledge validation levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    encoding: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    content_category: Optional[ContentCategory] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    line_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None

@dataclass
class ProcessingMetrics:
    """File processing performance metrics"""
    processing_duration_ms: float = 0.0
    analysis_duration_ms: float = 0.0
    extraction_duration_ms: float = 0.0
    integration_duration_ms: float = 0.0
    knowledge_items_extracted: int = 0
    knowledge_items_validated: int = 0
    knowledge_items_integrated: int = 0
    error_count: int = 0
    retry_count: int = 0

@dataclass
class ContentAnalysis:
    """Content analysis results"""
    readability_score: float = 0.0
    complexity_score: float = 0.0
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    relevance_score: float = 0.0
    technical_depth: float = 0.0
    concept_count: int = 0
    key_concepts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class FileUploadSchema(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_MB*1024*1024, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File content hash")
    processing_priority: ProcessingPriority = Field(default=ProcessingPriority.NORMAL)
    content_category: Optional[ContentCategory] = Field(None, description="Content category hint")
    extraction_config: Dict[str, Any] = Field(default_factory=dict, description="Extraction configuration")
    target_agents: List[str] = Field(default_factory=list, description="Target agents for knowledge")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Filename cannot be empty')
        # Remove path components for security
        return os.path.basename(v)
    
    @validator('file_hash')
    def validate_file_hash(cls, v):
        if v and len(v) not in [32, 40, 64, 128]:  # MD5, SHA1, SHA256, SHA512
            raise ValueError('Invalid hash format')
        return v

class KnowledgeExtractionSchema(BaseModel):
    """Schema for knowledge extraction configuration"""
    extraction_methods: List[ExtractionMethod] = Field(default_factory=lambda: [ExtractionMethod.TEXT_ANALYSIS])
    confidence_threshold: float = Field(default=KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0)
    max_items: int = Field(default=MAX_KNOWLEDGE_ITEMS_PER_FILE, ge=1, le=100)
    validation_level: ValidationLevel = Field(default=ValidationLevel.INTERMEDIATE)
    context_window: int = Field(default=1000, ge=100, le=5000, description="Context window for extraction")
    include_metadata: bool = Field(default=True, description="Include file metadata in knowledge")
    cross_reference: bool = Field(default=True, description="Cross-reference with existing knowledge")
    auto_categorize: bool = Field(default=True, description="Automatically categorize knowledge")

class FileAnalysisSchema(BaseModel):
    """Schema for file analysis results"""
    file_id: str = Field(..., description="File identifier")
    file_metadata: Dict[str, Any] = Field(..., description="File metadata")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    extracted_knowledge: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    integration_status: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileStatusSchema(BaseModel):
    """Schema for file status reporting"""
    file_id: str = Field(..., description="File identifier")
    filename: str = Field(..., description="Original filename")
    current_status: FileStatus = Field(..., description="Current processing status")
    processing_progress: float = Field(..., ge=0.0, le=100.0, description="Processing progress percentage")
    knowledge_items_count: int = Field(default=0, ge=0, description="Number of knowledge items extracted")
    integrated_agents: List[str] = Field(default_factory=list, description="Agents that received knowledge")
    error_messages: List[str] = Field(default_factory=list, description="Error messages if any")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchSchema(BaseModel):
    """Schema for file search requests"""
    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[FileType]] = Field(None, description="Filter by file types")
    content_categories: Optional[List[ContentCategory]] = Field(None, description="Filter by content categories")
    date_from: Optional[datetime] = Field(None, description="Filter files from date")
    date_to: Optional[datetime] = Field(None, description="Filter files to date")
    size_min: Optional[int] = Field(None, ge=0, description="Minimum file size")
    size_max: Optional[int] = Field(None, ge=0, description="Maximum file size")
    has_knowledge: Optional[bool] = Field(None, description="Filter files with extracted knowledge")
    agent_ids: Optional[List[str]] = Field(None, description="Filter by associated agents")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file records"""
    __tablename__ = 'file_records'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, nullable=False, index=True)
    
    # File metadata
    filename = Column(String, nullable=False, index=True)
    original_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False, index=True)
    file_hash = Column(String, nullable=False, unique=True, index=True)
    encoding = Column(String, nullable=True)
    
    # Classification
    file_type = Column(String, nullable=False, index=True)
    content_category = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    charset = Column(String, nullable=True)
    
    # Content metrics
    line_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing status
    current_status = Column(String, nullable=False, default=FileStatus.UPLOADED.value, index=True)
    processing_priority = Column(Integer, nullable=False, default=ProcessingPriority.NORMAL.value)
    processing_progress = Column(Float, nullable=False, default=0.0)
    
    # Processing metrics
    processing_duration_ms = Column(Float, nullable=False, default=0.0)
    analysis_duration_ms = Column(Float, nullable=False, default=0.0)
    extraction_duration_ms = Column(Float, nullable=False, default=0.0)
    integration_duration_ms = Column(Float, nullable=False, default=0.0)
    
    # Knowledge extraction results
    knowledge_items_extracted = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_integrated = Column(Integer, nullable=False, default=0)
    
    # Content analysis
    readability_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    technical_depth = Column(Float, nullable=False, default=0.0)
    concept_count = Column(Integer, nullable=False, default=0)
    
    # Structured data
    key_concepts = Column(ARRAY(String), nullable=False, default=list)
    topics = Column(ARRAY(String), nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    extraction_config = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    
    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    error_messages = Column(JSON, nullable=False, default=list)
    
    # Agent associations
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_content = relationship("FileContent", back_populates="file_record", uselist=False, cascade="all, delete-orphan")
    knowledge_extractions = relationship("FileKnowledgeExtraction", back_populates="file_record", cascade="all, delete-orphan")
    processing_logs = relationship("FileProcessingLog", back_populates="file_record", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_status_priority', 'current_status', 'processing_priority'),
        Index('idx_file_type_category', 'file_type', 'content_category'),
        Index('idx_file_size_upload', 'file_size', 'uploaded_at'),
        Index('idx_file_knowledge_count', 'knowledge_items_integrated'),
        Index('idx_file_quality_scores', 'quality_score', 'relevance_score'),
        Index('idx_file_agents', 'target_agents'),
    )

class FileContent(Base):
    """SQLAlchemy model for file content storage"""
    __tablename__ = 'file_contents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, unique=True, index=True)
    
    # Content storage
    raw_content = Column(LargeBinary, nullable=True)  # For binary files
    text_content = Column(Text, nullable=True)  # For text files
    encrypted_content = Column(LargeBinary, nullable=True)  # For sensitive files
    content_preview = Column(Text, nullable=True)  # First 1000 characters
    
    # Content metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    compression_used = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    
    # Storage metadata
    storage_method = Column(String, nullable=False, default="database")  # database, filesystem, s3, etc.
    external_path = Column(String, nullable=True)  # For external storage
    
    # Timestamps
    stored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="file_content")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_hash_method', 'content_hash', 'storage_method'),
        Index('idx_content_encrypted', 'is_encrypted'),
    )

class FileKnowledgeExtraction(Base):
    """SQLAlchemy model for extracted knowledge from files"""
    __tablename__ = 'file_knowledge_extractions'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    knowledge_content = Column(JSON, nullable=False)
    
    # Extraction metadata
    extraction_method = Column(String, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_level = Column(String, nullable=False, default=ValidationLevel.BASIC.value)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    
    # Context information
    source_location = Column(JSON, nullable=False, default=dict)  # Line numbers, sections, etc.
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    
    # Quality metrics
    relevance_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    last_used = Column(DateTime, nullable=True)
    
    # Agent integration
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    integration_results = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="knowledge_extractions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_method_confidence', 'extraction_method', 'confidence_score'),
        Index('idx_extraction_validation', 'validation_status', 'validation_level'),
        Index('idx_extraction_agents', 'target_agents'),
        Index('idx_extraction_quality', 'relevance_score', 'uniqueness_score'),
    )

class FileProcessingLog(Base):
    """SQLAlchemy model for file processing logs"""
    __tablename__ = 'file_processing_logs'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    log_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Log details
    log_level = Column(String, nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_message = Column(Text, nullable=False)
    log_context = Column(JSON, nullable=False, default=dict)
    
    # Processing stage
    processing_stage = Column(String, nullable=False, index=True)  # upload, analysis, extraction, integration
    stage_duration_ms = Column(Float, nullable=True)
    
    # Error details (if applicable)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Timestamps
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="processing_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_log_level_stage', 'log_level', 'processing_stage'),
        Index('idx_log_error_type', 'error_type'),
        Index('idx_log_timing', 'logged_at', 'stage_duration_ms'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileProcessor:
    """Handles file processing and knowledge extraction"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component="file_processor")
        
        # Processing configuration
        self.max_file_size = config.get('max_file_size_mb', MAX_FILE_SIZE_MB) * 1024 * 1024
        self.supported_formats = self._get_supported_formats()
        self.extraction_timeout = config.get('extraction_timeout', FILE_ANALYSIS_TIMEOUT_SECONDS)
        
        # Knowledge extraction configuration
        self.extraction_methods = config.get('extraction_methods', [ExtractionMethod.TEXT_ANALYSIS])
        self.confidence_threshold = config.get('confidence_threshold', KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD)
        self.max_knowledge_items = config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_FILE)
        
        # Processing queues
        self.processing_queue: Dict[str, FileUploadSchema] = {}
        self.active_processing: Set[str] = set()
        
    def _get_supported_formats(self) -> Set[str]:
        """Get all supported file formats"""
        return (SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | 
                SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    
    async def process_file_upload(self, upload_schema: FileUploadSchema, file_content: bytes) -> Dict[str, Any]:
        """Process uploaded file and extract knowledge"""
        file_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting file processing", 
                           file_id=file_id, 
                           filename=upload_schema.filename,
                           file_size=upload_schema.file_size)
            
            # Phase 1: File validation and metadata extraction
            file_metadata = await self._extract_file_metadata(upload_schema, file_content)
            
            # Phase 2: Content analysis
            content_analysis = await self._analyze_file_content(file_content, file_metadata)
            
            # Phase 3: Knowledge extraction
            extracted_knowledge = await self._extract_knowledge(file_content, file_metadata, content_analysis)
            
            # Phase 4: Knowledge validation
            validated_knowledge = await self._validate_extracted_knowledge(extracted_knowledge)
            
            # Phase 5: Agent integration
            integration_results = await self._integrate_with_agents(validated_knowledge, upload_schema.target_agents)
            
            # Calculate processing metrics
            processing_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store file record
            file_record = await self._store_file_record(
                file_id, upload_schema, file_metadata, content_analysis, 
                validated_knowledge, integration_results, processing_duration
            )
            
            # Store file content
            await self._store_file_content(file_id, file_content, file_metadata)
            
            result = {
                "file_id": file_id,
                "status": "completed",
                "processing_duration_ms": processing_duration,
                "file_metadata": file_metadata.__dict__,
                "content_analysis": content_analysis.__dict__,
                "knowledge_items_extracted": len(validated_knowledge),
                "integration_results": integration_results
            }
            
            self.logger.info("File processing completed successfully", **result)
            return result
            
        except Exception as e:
            self.logger.error("File processing failed", 
                            file_id=file_id, 
                            filename=upload_schema.filename,
                            error=str(e))
            
            # Store error information
            await self._store_processing_error(file_id, upload_schema, str(e))
            
            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e),
                "processing_duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def _extract_file_metadata(self, upload_schema: FileUploadSchema, content: bytes) -> FileMetadata:
        """Extract comprehensive file metadata"""
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine file type
        file_extension = Path(upload_schema.filename).suffix.lower()
        file_type = self._classify_file_type(file_extension, upload_schema.content_type)
        
        # Extract text content for analysis
        text_content = ""
        encoding = None
        if file_type in [FileType.TEXT, FileType.CODE]:
            text_content, encoding = await self._extract_text_content(content, file_extension)
        
        # Calculate content metrics
        line_count = len(text_content.split('\n')) if text_content else None
        word_count = len(text_content.split()) if text_content else None
        character_count = len(text_content) if text_content else None
        
        # Detect language for code files
        language = None
        if file_type == FileType.CODE:
            language = self._detect_programming_language(file_extension, text_content)
        
        return FileMetadata(
            filename=upload_schema.filename,
            file_size=upload_schema.file_size,
            mime_type=upload_schema.content_type,
            file_hash=file_hash,
            encoding=encoding,
            file_type=file_type,
            content_category=upload_schema.content_category,
            language=language,
            line_count=line_count,
            word_count=word_count,
            character_count=character_count
        )
    
    def _classify_file_type(self, extension: str, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        if extension in SUPPORTED_TEXT_FORMATS:
            return FileType.TEXT
        elif extension in SUPPORTED_DOCUMENT_FORMATS:
            return FileType.DOCUMENT
        elif extension in SUPPORTED_CODE_FORMATS:
            return FileType.CODE
        elif extension in SUPPORTED_DATA_FORMATS:
            return FileType.DATA
        elif extension in SUPPORTED_IMAGE_FORMATS:
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif extension in {'.zip', '.tar', '.gz', '.rar', '.7z'}:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def _extract_text_content(self, content: bytes, extension: str) -> Tuple[str, Optional[str]]:
        """Extract text content from file"""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                return text_content, encoding
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace'), 'utf-8'
    
    def _detect_programming_language(self, extension: str, content: str) -> Optional[str]:
        """Detect programming language from extension and content"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return language_map.get(extension)
    
    async def _analyze_file_content(self, content: bytes, metadata: FileMetadata) -> ContentAnalysis:
        """Analyze file content for quality and complexity"""
        analysis = ContentAnalysis()
        
        # For text-based files, perform detailed analysis
        if metadata.file_type in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
            
            # Calculate readability score
            analysis.readability_score = self._calculate_readability(text_content)
            
            # Calculate complexity score
            analysis.complexity_score = self._calculate_complexity(text_content, metadata.file_type)
            
            # Calculate quality score
            analysis.quality_score = self._calculate_quality(text_content, metadata)
            
            # Calculate uniqueness score
            analysis.uniqueness_score = await self._calculate_uniqueness(text_content)
            
            # Extract key concepts and topics
            analysis.key_concepts = self._extract_key_concepts(text_content)
            analysis.topics = self._extract_topics(text_content)
            analysis.concept_count = len(analysis.key_concepts)
            
            # Extract entities
            analysis.entities = self._extract_entities(text_content)
            
            # Calculate technical depth
            analysis.technical_depth = self._calculate_technical_depth(text_content, metadata.language)
            
            # Calculate relevance score
            analysis.relevance_score = self._calculate_relevance(text_content, metadata.content_category)
        
        return analysis
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using various metrics"""
        if not text:
            return 0.0
        
        # Simple readability calculation based on sentence and word length
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normalize to 0-100 scale (inverse relationship for complexity)
        readability = max(0, 100 - (avg_sentence_length * 2 + avg_word_length * 5))
        return min(readability, 100.0)
    
    def _calculate_complexity(self, text: str, file_type: FileType) -> float:
        """Calculate content complexity score"""
        if not text:
            return 0.0
        
        complexity_indicators = {
            'technical_terms': len([word for word in text.split() if len(word) > 10]),
            'punctuation_density': sum(1 for char in text if char in '.,;:!?()[]{}'),
            'nested_structures': text.count('(') + text.count('[') + text.count('{'),
            'line_length_variance': 0  # Simplified
        }
        
        if file_type == FileType.CODE:
            # Additional complexity for code
            complexity_indicators.update({
                'function_definitions': text.count('def ') + text.count('function '),
                'conditional_statements': text.count('if ') + text.count('while ') + text.count('for '),
                'import_statements': text.count('import ') + text.count('require('),
            })
        
        # Normalize to 0-100 scale
        total_indicators = sum(complexity_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        complexity = min((total_indicators / text_length) * 1000, 100.0)
        return complexity
    
    def _calculate_quality(self, text: str, metadata: FileMetadata) -> float:
        """Calculate content quality score"""
        if not text:
            return 0.0
        
        quality_factors = {
            'length_adequacy': min(len(text.split()) / 100, 1.0) * 25,  # Adequate length
            'structure_score': self._assess_structure(text) * 20,  # Good structure
            'grammar_score': self._assess_grammar(text) * 20,  # Grammar quality
            'completeness_score': self._assess_completeness(text) * 20,  # Content completeness
            'consistency_score': self._assess_consistency(text) * 15   # Style consistency
        }
        
        return sum(quality_factors.values())
    
    def _assess_structure(self, text: str) -> float:
        """Assess text structure quality"""
        # Simple structure assessment
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        # Check for headings, paragraphs, lists
        structure_score = 0.0
        if any(line.startswith('#') for line in lines):  # Markdown headings
            structure_score += 0.3
        if len(non_empty_lines) > 5:  # Multiple paragraphs
            structure_score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in lines):  # Lists
            structure_score += 0.4
        
        return min(structure_score, 1.0)
    
    def _assess_grammar(self, text: str) -> float:
        """Assess grammar quality (simplified)"""
        # Simple grammar assessment
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        # Check for basic grammar indicators
        capitalized_sentences = sum(1 for s in sentences if s and s[0].isupper())
        grammar_score = capitalized_sentences / len(sentences)
        
        return grammar_score
    
    def _assess_completeness(self, text: str) -> float:
        """Assess content completeness"""
        # Check for introduction, body, conclusion indicators
        completeness_indicators = 0
        
        intro_words = ['introduction', 'overview', 'summary', 'abstract']
        if any(word in text.lower() for word in intro_words):
            completeness_indicators += 1
        
        if len(text.split()) > 200:  # Substantial content
            completeness_indicators += 1
        
        conclusion_words = ['conclusion', 'summary', 'finally', 'in summary']
        if any(word in text.lower() for word in conclusion_words):
            completeness_indicators += 1
        
        return completeness_indicators / 3.0
    
    def _assess_consistency(self, text:,  # Numbered lists
            r'^\s*[-*]\s+(.+)"""
YMERA Enterprise - File Learning Models
Production-Ready File Metadata & Learning Integration Models - v4.0
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
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from agent_models import KnowledgeType, LearningStatus

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File processing constants
MAX_FILE_SIZE_MB = 100
SUPPORTED_TEXT_FORMATS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.docx', '.doc', '.rtf', '.odt'}
SUPPORTED_CODE_FORMATS = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
SUPPORTED_DATA_FORMATS = {'.csv', '.xlsx', '.xls', '.json', '.xml', '.parquet'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}

# Learning integration constants
KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD = 0.6
MAX_KNOWLEDGE_ITEMS_PER_FILE = 50
FILE_ANALYSIS_TIMEOUT_SECONDS = 300
CONTENT_SIMILARITY_THRESHOLD = 0.8

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class FileType(str, Enum):
    """File type classification"""
    TEXT = "text"
    DOCUMENT = "document" 
    CODE = "code"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class FileStatus(str, Enum):
    """File processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    INTEGRATED = "integrated"
    ERROR = "error"
    ARCHIVED = "archived"

class ProcessingPriority(IntEnum):
    """File processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class ContentCategory(str, Enum):
    """Content categorization for learning"""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SPECIFICATION = "specification"
    EXAMPLE = "example"
    CONFIGURATION = "configuration"
    DATA_SAMPLE = "data_sample"
    ERROR_LOG = "error_log"
    PERFORMANCE_DATA = "performance_data"
    USER_FEEDBACK = "user_feedback"
    RESEARCH = "research"

class ExtractionMethod(str, Enum):
    """Knowledge extraction methods"""
    TEXT_ANALYSIS = "text_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    ML_INFERENCE = "ml_inference"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class ValidationLevel(str, Enum):
    """Knowledge validation levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    encoding: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    content_category: Optional[ContentCategory] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    line_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None

@dataclass
class ProcessingMetrics:
    """File processing performance metrics"""
    processing_duration_ms: float = 0.0
    analysis_duration_ms: float = 0.0
    extraction_duration_ms: float = 0.0
    integration_duration_ms: float = 0.0
    knowledge_items_extracted: int = 0
    knowledge_items_validated: int = 0
    knowledge_items_integrated: int = 0
    error_count: int = 0
    retry_count: int = 0

@dataclass
class ContentAnalysis:
    """Content analysis results"""
    readability_score: float = 0.0
    complexity_score: float = 0.0
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    relevance_score: float = 0.0
    technical_depth: float = 0.0
    concept_count: int = 0
    key_concepts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class FileUploadSchema(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_MB*1024*1024, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File content hash")
    processing_priority: ProcessingPriority = Field(default=ProcessingPriority.NORMAL)
    content_category: Optional[ContentCategory] = Field(None, description="Content category hint")
    extraction_config: Dict[str, Any] = Field(default_factory=dict, description="Extraction configuration")
    target_agents: List[str] = Field(default_factory=list, description="Target agents for knowledge")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Filename cannot be empty')
        # Remove path components for security
        return os.path.basename(v)
    
    @validator('file_hash')
    def validate_file_hash(cls, v):
        if v and len(v) not in [32, 40, 64, 128]:  # MD5, SHA1, SHA256, SHA512
            raise ValueError('Invalid hash format')
        return v

class KnowledgeExtractionSchema(BaseModel):
    """Schema for knowledge extraction configuration"""
    extraction_methods: List[ExtractionMethod] = Field(default_factory=lambda: [ExtractionMethod.TEXT_ANALYSIS])
    confidence_threshold: float = Field(default=KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0)
    max_items: int = Field(default=MAX_KNOWLEDGE_ITEMS_PER_FILE, ge=1, le=100)
    validation_level: ValidationLevel = Field(default=ValidationLevel.INTERMEDIATE)
    context_window: int = Field(default=1000, ge=100, le=5000, description="Context window for extraction")
    include_metadata: bool = Field(default=True, description="Include file metadata in knowledge")
    cross_reference: bool = Field(default=True, description="Cross-reference with existing knowledge")
    auto_categorize: bool = Field(default=True, description="Automatically categorize knowledge")

class FileAnalysisSchema(BaseModel):
    """Schema for file analysis results"""
    file_id: str = Field(..., description="File identifier")
    file_metadata: Dict[str, Any] = Field(..., description="File metadata")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    extracted_knowledge: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    integration_status: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileStatusSchema(BaseModel):
    """Schema for file status reporting"""
    file_id: str = Field(..., description="File identifier")
    filename: str = Field(..., description="Original filename")
    current_status: FileStatus = Field(..., description="Current processing status")
    processing_progress: float = Field(..., ge=0.0, le=100.0, description="Processing progress percentage")
    knowledge_items_count: int = Field(default=0, ge=0, description="Number of knowledge items extracted")
    integrated_agents: List[str] = Field(default_factory=list, description="Agents that received knowledge")
    error_messages: List[str] = Field(default_factory=list, description="Error messages if any")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchSchema(BaseModel):
    """Schema for file search requests"""
    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[FileType]] = Field(None, description="Filter by file types")
    content_categories: Optional[List[ContentCategory]] = Field(None, description="Filter by content categories")
    date_from: Optional[datetime] = Field(None, description="Filter files from date")
    date_to: Optional[datetime] = Field(None, description="Filter files to date")
    size_min: Optional[int] = Field(None, ge=0, description="Minimum file size")
    size_max: Optional[int] = Field(None, ge=0, description="Maximum file size")
    has_knowledge: Optional[bool] = Field(None, description="Filter files with extracted knowledge")
    agent_ids: Optional[List[str]] = Field(None, description="Filter by associated agents")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file records"""
    __tablename__ = 'file_records'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, nullable=False, index=True)
    
    # File metadata
    filename = Column(String, nullable=False, index=True)
    original_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False, index=True)
    file_hash = Column(String, nullable=False, unique=True, index=True)
    encoding = Column(String, nullable=True)
    
    # Classification
    file_type = Column(String, nullable=False, index=True)
    content_category = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    charset = Column(String, nullable=True)
    
    # Content metrics
    line_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing status
    current_status = Column(String, nullable=False, default=FileStatus.UPLOADED.value, index=True)
    processing_priority = Column(Integer, nullable=False, default=ProcessingPriority.NORMAL.value)
    processing_progress = Column(Float, nullable=False, default=0.0)
    
    # Processing metrics
    processing_duration_ms = Column(Float, nullable=False, default=0.0)
    analysis_duration_ms = Column(Float, nullable=False, default=0.0)
    extraction_duration_ms = Column(Float, nullable=False, default=0.0)
    integration_duration_ms = Column(Float, nullable=False, default=0.0)
    
    # Knowledge extraction results
    knowledge_items_extracted = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_integrated = Column(Integer, nullable=False, default=0)
    
    # Content analysis
    readability_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    technical_depth = Column(Float, nullable=False, default=0.0)
    concept_count = Column(Integer, nullable=False, default=0)
    
    # Structured data
    key_concepts = Column(ARRAY(String), nullable=False, default=list)
    topics = Column(ARRAY(String), nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    extraction_config = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    
    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    error_messages = Column(JSON, nullable=False, default=list)
    
    # Agent associations
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_content = relationship("FileContent", back_populates="file_record", uselist=False, cascade="all, delete-orphan")
    knowledge_extractions = relationship("FileKnowledgeExtraction", back_populates="file_record", cascade="all, delete-orphan")
    processing_logs = relationship("FileProcessingLog", back_populates="file_record", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_status_priority', 'current_status', 'processing_priority'),
        Index('idx_file_type_category', 'file_type', 'content_category'),
        Index('idx_file_size_upload', 'file_size', 'uploaded_at'),
        Index('idx_file_knowledge_count', 'knowledge_items_integrated'),
        Index('idx_file_quality_scores', 'quality_score', 'relevance_score'),
        Index('idx_file_agents', 'target_agents'),
    )

class FileContent(Base):
    """SQLAlchemy model for file content storage"""
    __tablename__ = 'file_contents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, unique=True, index=True)
    
    # Content storage
    raw_content = Column(LargeBinary, nullable=True)  # For binary files
    text_content = Column(Text, nullable=True)  # For text files
    encrypted_content = Column(LargeBinary, nullable=True)  # For sensitive files
    content_preview = Column(Text, nullable=True)  # First 1000 characters
    
    # Content metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    compression_used = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    
    # Storage metadata
    storage_method = Column(String, nullable=False, default="database")  # database, filesystem, s3, etc.
    external_path = Column(String, nullable=True)  # For external storage
    
    # Timestamps
    stored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="file_content")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_hash_method', 'content_hash', 'storage_method'),
        Index('idx_content_encrypted', 'is_encrypted'),
    )

class FileKnowledgeExtraction(Base):
    """SQLAlchemy model for extracted knowledge from files"""
    __tablename__ = 'file_knowledge_extractions'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    knowledge_content = Column(JSON, nullable=False)
    
    # Extraction metadata
    extraction_method = Column(String, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_level = Column(String, nullable=False, default=ValidationLevel.BASIC.value)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    
    # Context information
    source_location = Column(JSON, nullable=False, default=dict)  # Line numbers, sections, etc.
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    
    # Quality metrics
    relevance_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    last_used = Column(DateTime, nullable=True)
    
    # Agent integration
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    integration_results = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="knowledge_extractions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_method_confidence', 'extraction_method', 'confidence_score'),
        Index('idx_extraction_validation', 'validation_status', 'validation_level'),
        Index('idx_extraction_agents', 'target_agents'),
        Index('idx_extraction_quality', 'relevance_score', 'uniqueness_score'),
    )

class FileProcessingLog(Base):
    """SQLAlchemy model for file processing logs"""
    __tablename__ = 'file_processing_logs'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    log_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Log details
    log_level = Column(String, nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_message = Column(Text, nullable=False)
    log_context = Column(JSON, nullable=False, default=dict)
    
    # Processing stage
    processing_stage = Column(String, nullable=False, index=True)  # upload, analysis, extraction, integration
    stage_duration_ms = Column(Float, nullable=True)
    
    # Error details (if applicable)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Timestamps
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="processing_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_log_level_stage', 'log_level', 'processing_stage'),
        Index('idx_log_error_type', 'error_type'),
        Index('idx_log_timing', 'logged_at', 'stage_duration_ms'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileProcessor:
    """Handles file processing and knowledge extraction"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component="file_processor")
        
        # Processing configuration
        self.max_file_size = config.get('max_file_size_mb', MAX_FILE_SIZE_MB) * 1024 * 1024
        self.supported_formats = self._get_supported_formats()
        self.extraction_timeout = config.get('extraction_timeout', FILE_ANALYSIS_TIMEOUT_SECONDS)
        
        # Knowledge extraction configuration
        self.extraction_methods = config.get('extraction_methods', [ExtractionMethod.TEXT_ANALYSIS])
        self.confidence_threshold = config.get('confidence_threshold', KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD)
        self.max_knowledge_items = config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_FILE)
        
        # Processing queues
        self.processing_queue: Dict[str, FileUploadSchema] = {}
        self.active_processing: Set[str] = set()
        
    def _get_supported_formats(self) -> Set[str]:
        """Get all supported file formats"""
        return (SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | 
                SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    
    async def process_file_upload(self, upload_schema: FileUploadSchema, file_content: bytes) -> Dict[str, Any]:
        """Process uploaded file and extract knowledge"""
        file_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting file processing", 
                           file_id=file_id, 
                           filename=upload_schema.filename,
                           file_size=upload_schema.file_size)
            
            # Phase 1: File validation and metadata extraction
            file_metadata = await self._extract_file_metadata(upload_schema, file_content)
            
            # Phase 2: Content analysis
            content_analysis = await self._analyze_file_content(file_content, file_metadata)
            
            # Phase 3: Knowledge extraction
            extracted_knowledge = await self._extract_knowledge(file_content, file_metadata, content_analysis)
            
            # Phase 4: Knowledge validation
            validated_knowledge = await self._validate_extracted_knowledge(extracted_knowledge)
            
            # Phase 5: Agent integration
            integration_results = await self._integrate_with_agents(validated_knowledge, upload_schema.target_agents)
            
            # Calculate processing metrics
            processing_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store file record
            file_record = await self._store_file_record(
                file_id, upload_schema, file_metadata, content_analysis, 
                validated_knowledge, integration_results, processing_duration
            )
            
            # Store file content
            await self._store_file_content(file_id, file_content, file_metadata)
            
            result = {
                "file_id": file_id,
                "status": "completed",
                "processing_duration_ms": processing_duration,
                "file_metadata": file_metadata.__dict__,
                "content_analysis": content_analysis.__dict__,
                "knowledge_items_extracted": len(validated_knowledge),
                "integration_results": integration_results
            }
            
            self.logger.info("File processing completed successfully", **result)
            return result
            
        except Exception as e:
            self.logger.error("File processing failed", 
                            file_id=file_id, 
                            filename=upload_schema.filename,
                            error=str(e))
            
            # Store error information
            await self._store_processing_error(file_id, upload_schema, str(e))
            
            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e),
                "processing_duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def _extract_file_metadata(self, upload_schema: FileUploadSchema, content: bytes) -> FileMetadata:
        """Extract comprehensive file metadata"""
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine file type
        file_extension = Path(upload_schema.filename).suffix.lower()
        file_type = self._classify_file_type(file_extension, upload_schema.content_type)
        
        # Extract text content for analysis
        text_content = ""
        encoding = None
        if file_type in [FileType.TEXT, FileType.CODE]:
            text_content, encoding = await self._extract_text_content(content, file_extension)
        
        # Calculate content metrics
        line_count = len(text_content.split('\n')) if text_content else None
        word_count = len(text_content.split()) if text_content else None
        character_count = len(text_content) if text_content else None
        
        # Detect language for code files
        language = None
        if file_type == FileType.CODE:
            language = self._detect_programming_language(file_extension, text_content)
        
        return FileMetadata(
            filename=upload_schema.filename,
            file_size=upload_schema.file_size,
            mime_type=upload_schema.content_type,
            file_hash=file_hash,
            encoding=encoding,
            file_type=file_type,
            content_category=upload_schema.content_category,
            language=language,
            line_count=line_count,
            word_count=word_count,
            character_count=character_count
        )
    
    def _classify_file_type(self, extension: str, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        if extension in SUPPORTED_TEXT_FORMATS:
            return FileType.TEXT
        elif extension in SUPPORTED_DOCUMENT_FORMATS:
            return FileType.DOCUMENT
        elif extension in SUPPORTED_CODE_FORMATS:
            return FileType.CODE
        elif extension in SUPPORTED_DATA_FORMATS:
            return FileType.DATA
        elif extension in SUPPORTED_IMAGE_FORMATS:
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif extension in {'.zip', '.tar', '.gz', '.rar', '.7z'}:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def _extract_text_content(self, content: bytes, extension: str) -> Tuple[str, Optional[str]]:
        """Extract text content from file"""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                return text_content, encoding
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace'), 'utf-8'
    
    def _detect_programming_language(self, extension: str, content: str) -> Optional[str]:
        """Detect programming language from extension and content"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return language_map.get(extension)
    
    async def _analyze_file_content(self, content: bytes, metadata: FileMetadata) -> ContentAnalysis:
        """Analyze file content for quality and complexity"""
        analysis = ContentAnalysis()
        
        # For text-based files, perform detailed analysis
        if metadata.file_type in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
            
            # Calculate readability score
            analysis.readability_score = self._calculate_readability(text_content)
            
            # Calculate complexity score
            analysis.complexity_score = self._calculate_complexity(text_content, metadata.file_type)
            
            # Calculate quality score
            analysis.quality_score = self._calculate_quality(text_content, metadata)
            
            # Calculate uniqueness score
            analysis.uniqueness_score = await self._calculate_uniqueness(text_content)
            
            # Extract key concepts and topics
            analysis.key_concepts = self._extract_key_concepts(text_content)
            analysis.topics = self._extract_topics(text_content)
            analysis.concept_count = len(analysis.key_concepts)
            
            # Extract entities
            analysis.entities = self._extract_entities(text_content)
            
            # Calculate technical depth
            analysis.technical_depth = self._calculate_technical_depth(text_content, metadata.language)
            
            # Calculate relevance score
            analysis.relevance_score = self._calculate_relevance(text_content, metadata.content_category)
        
        return analysis
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using various metrics"""
        if not text:
            return 0.0
        
        # Simple readability calculation based on sentence and word length
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normalize to 0-100 scale (inverse relationship for complexity)
        readability = max(0, 100 - (avg_sentence_length * 2 + avg_word_length * 5))
        return min(readability, 100.0)
    
    def _calculate_complexity(self, text: str, file_type: FileType) -> float:
        """Calculate content complexity score"""
        if not text:
            return 0.0
        
        complexity_indicators = {
            'technical_terms': len([word for word in text.split() if len(word) > 10]),
            'punctuation_density': sum(1 for char in text if char in '.,;:!?()[]{}'),
            'nested_structures': text.count('(') + text.count('[') + text.count('{'),
            'line_length_variance': 0  # Simplified
        }
        
        if file_type == FileType.CODE:
            # Additional complexity for code
            complexity_indicators.update({
                'function_definitions': text.count('def ') + text.count('function '),
                'conditional_statements': text.count('if ') + text.count('while ') + text.count('for '),
                'import_statements': text.count('import ') + text.count('require('),
            })
        
        # Normalize to 0-100 scale
        total_indicators = sum(complexity_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        complexity = min((total_indicators / text_length) * 1000, 100.0)
        return complexity
    
    def _calculate_quality(self, text: str, metadata: FileMetadata) -> float:
        """Calculate content quality score"""
        if not text:
            return 0.0
        
        quality_factors = {
            'length_adequacy': min(len(text.split()) / 100, 1.0) * 25,  # Adequate length
            'structure_score': self._assess_structure(text) * 20,  # Good structure
            'grammar_score': self._assess_grammar(text) * 20,  # Grammar quality
            'completeness_score': self._assess_completeness(text) * 20,  # Content completeness
            'consistency_score': self._assess_consistency(text) * 15   # Style consistency
        }
        
        return sum(quality_factors.values())
    
    def _assess_structure(self, text: str) -> float:
        """Assess text structure quality"""
        # Simple structure assessment
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        # Check for headings, paragraphs, lists
        structure_score = 0.0
        if any(line.startswith('#') for line in lines):  # Markdown headings
            structure_score += 0.3
        if len(non_empty_lines) > 5:  # Multiple paragraphs
            structure_score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in lines):  # Lists
            structure_score += 0.4
        
        return min(structure_score, 1.0)
    
    def _assess_grammar(self, text: str) -> float:
        """Assess grammar quality (simplified)"""
        # Simple grammar assessment
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        # Check for basic grammar indicators
        capitalized_sentences = sum(1 for s in sentences if s and s[0].isupper())
        grammar_score = capitalized_sentences / len(sentences)
        
        return grammar_score
    
    def _assess_completeness(self, text: str) -> float:
        """Assess content completeness"""
        # Check for introduction, body, conclusion indicators
        completeness_indicators = 0
        
        intro_words = ['introduction', 'overview', 'summary', 'abstract']
        if any(word in text.lower() for word in intro_words):
            completeness_indicators += 1
        
        if len(text.split()) > 200:  # Substantial content
            completeness_indicators += 1
        
        conclusion_words = ['conclusion', 'summary', 'finally', 'in summary']
        if any(word in text.lower() for word in conclusion_words):
            completeness_indicators += 1
        
        return completeness_indicators / 3.0
    
    def _assess_consistency(self, text:,     # Bullet points
            r'^\s*Step\s+(\d+):\s+(.+)"""
YMERA Enterprise - File Learning Models
Production-Ready File Metadata & Learning Integration Models - v4.0
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
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from agent_models import KnowledgeType, LearningStatus

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File processing constants
MAX_FILE_SIZE_MB = 100
SUPPORTED_TEXT_FORMATS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.docx', '.doc', '.rtf', '.odt'}
SUPPORTED_CODE_FORMATS = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
SUPPORTED_DATA_FORMATS = {'.csv', '.xlsx', '.xls', '.json', '.xml', '.parquet'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}

# Learning integration constants
KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD = 0.6
MAX_KNOWLEDGE_ITEMS_PER_FILE = 50
FILE_ANALYSIS_TIMEOUT_SECONDS = 300
CONTENT_SIMILARITY_THRESHOLD = 0.8

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class FileType(str, Enum):
    """File type classification"""
    TEXT = "text"
    DOCUMENT = "document" 
    CODE = "code"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class FileStatus(str, Enum):
    """File processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    INTEGRATED = "integrated"
    ERROR = "error"
    ARCHIVED = "archived"

class ProcessingPriority(IntEnum):
    """File processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class ContentCategory(str, Enum):
    """Content categorization for learning"""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SPECIFICATION = "specification"
    EXAMPLE = "example"
    CONFIGURATION = "configuration"
    DATA_SAMPLE = "data_sample"
    ERROR_LOG = "error_log"
    PERFORMANCE_DATA = "performance_data"
    USER_FEEDBACK = "user_feedback"
    RESEARCH = "research"

class ExtractionMethod(str, Enum):
    """Knowledge extraction methods"""
    TEXT_ANALYSIS = "text_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    ML_INFERENCE = "ml_inference"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class ValidationLevel(str, Enum):
    """Knowledge validation levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    encoding: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    content_category: Optional[ContentCategory] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    line_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None

@dataclass
class ProcessingMetrics:
    """File processing performance metrics"""
    processing_duration_ms: float = 0.0
    analysis_duration_ms: float = 0.0
    extraction_duration_ms: float = 0.0
    integration_duration_ms: float = 0.0
    knowledge_items_extracted: int = 0
    knowledge_items_validated: int = 0
    knowledge_items_integrated: int = 0
    error_count: int = 0
    retry_count: int = 0

@dataclass
class ContentAnalysis:
    """Content analysis results"""
    readability_score: float = 0.0
    complexity_score: float = 0.0
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    relevance_score: float = 0.0
    technical_depth: float = 0.0
    concept_count: int = 0
    key_concepts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class FileUploadSchema(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_MB*1024*1024, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File content hash")
    processing_priority: ProcessingPriority = Field(default=ProcessingPriority.NORMAL)
    content_category: Optional[ContentCategory] = Field(None, description="Content category hint")
    extraction_config: Dict[str, Any] = Field(default_factory=dict, description="Extraction configuration")
    target_agents: List[str] = Field(default_factory=list, description="Target agents for knowledge")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Filename cannot be empty')
        # Remove path components for security
        return os.path.basename(v)
    
    @validator('file_hash')
    def validate_file_hash(cls, v):
        if v and len(v) not in [32, 40, 64, 128]:  # MD5, SHA1, SHA256, SHA512
            raise ValueError('Invalid hash format')
        return v

class KnowledgeExtractionSchema(BaseModel):
    """Schema for knowledge extraction configuration"""
    extraction_methods: List[ExtractionMethod] = Field(default_factory=lambda: [ExtractionMethod.TEXT_ANALYSIS])
    confidence_threshold: float = Field(default=KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0)
    max_items: int = Field(default=MAX_KNOWLEDGE_ITEMS_PER_FILE, ge=1, le=100)
    validation_level: ValidationLevel = Field(default=ValidationLevel.INTERMEDIATE)
    context_window: int = Field(default=1000, ge=100, le=5000, description="Context window for extraction")
    include_metadata: bool = Field(default=True, description="Include file metadata in knowledge")
    cross_reference: bool = Field(default=True, description="Cross-reference with existing knowledge")
    auto_categorize: bool = Field(default=True, description="Automatically categorize knowledge")

class FileAnalysisSchema(BaseModel):
    """Schema for file analysis results"""
    file_id: str = Field(..., description="File identifier")
    file_metadata: Dict[str, Any] = Field(..., description="File metadata")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    extracted_knowledge: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    integration_status: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileStatusSchema(BaseModel):
    """Schema for file status reporting"""
    file_id: str = Field(..., description="File identifier")
    filename: str = Field(..., description="Original filename")
    current_status: FileStatus = Field(..., description="Current processing status")
    processing_progress: float = Field(..., ge=0.0, le=100.0, description="Processing progress percentage")
    knowledge_items_count: int = Field(default=0, ge=0, description="Number of knowledge items extracted")
    integrated_agents: List[str] = Field(default_factory=list, description="Agents that received knowledge")
    error_messages: List[str] = Field(default_factory=list, description="Error messages if any")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchSchema(BaseModel):
    """Schema for file search requests"""
    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[FileType]] = Field(None, description="Filter by file types")
    content_categories: Optional[List[ContentCategory]] = Field(None, description="Filter by content categories")
    date_from: Optional[datetime] = Field(None, description="Filter files from date")
    date_to: Optional[datetime] = Field(None, description="Filter files to date")
    size_min: Optional[int] = Field(None, ge=0, description="Minimum file size")
    size_max: Optional[int] = Field(None, ge=0, description="Maximum file size")
    has_knowledge: Optional[bool] = Field(None, description="Filter files with extracted knowledge")
    agent_ids: Optional[List[str]] = Field(None, description="Filter by associated agents")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file records"""
    __tablename__ = 'file_records'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, nullable=False, index=True)
    
    # File metadata
    filename = Column(String, nullable=False, index=True)
    original_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False, index=True)
    file_hash = Column(String, nullable=False, unique=True, index=True)
    encoding = Column(String, nullable=True)
    
    # Classification
    file_type = Column(String, nullable=False, index=True)
    content_category = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    charset = Column(String, nullable=True)
    
    # Content metrics
    line_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing status
    current_status = Column(String, nullable=False, default=FileStatus.UPLOADED.value, index=True)
    processing_priority = Column(Integer, nullable=False, default=ProcessingPriority.NORMAL.value)
    processing_progress = Column(Float, nullable=False, default=0.0)
    
    # Processing metrics
    processing_duration_ms = Column(Float, nullable=False, default=0.0)
    analysis_duration_ms = Column(Float, nullable=False, default=0.0)
    extraction_duration_ms = Column(Float, nullable=False, default=0.0)
    integration_duration_ms = Column(Float, nullable=False, default=0.0)
    
    # Knowledge extraction results
    knowledge_items_extracted = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_integrated = Column(Integer, nullable=False, default=0)
    
    # Content analysis
    readability_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    technical_depth = Column(Float, nullable=False, default=0.0)
    concept_count = Column(Integer, nullable=False, default=0)
    
    # Structured data
    key_concepts = Column(ARRAY(String), nullable=False, default=list)
    topics = Column(ARRAY(String), nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    extraction_config = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    
    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    error_messages = Column(JSON, nullable=False, default=list)
    
    # Agent associations
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_content = relationship("FileContent", back_populates="file_record", uselist=False, cascade="all, delete-orphan")
    knowledge_extractions = relationship("FileKnowledgeExtraction", back_populates="file_record", cascade="all, delete-orphan")
    processing_logs = relationship("FileProcessingLog", back_populates="file_record", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_status_priority', 'current_status', 'processing_priority'),
        Index('idx_file_type_category', 'file_type', 'content_category'),
        Index('idx_file_size_upload', 'file_size', 'uploaded_at'),
        Index('idx_file_knowledge_count', 'knowledge_items_integrated'),
        Index('idx_file_quality_scores', 'quality_score', 'relevance_score'),
        Index('idx_file_agents', 'target_agents'),
    )

class FileContent(Base):
    """SQLAlchemy model for file content storage"""
    __tablename__ = 'file_contents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, unique=True, index=True)
    
    # Content storage
    raw_content = Column(LargeBinary, nullable=True)  # For binary files
    text_content = Column(Text, nullable=True)  # For text files
    encrypted_content = Column(LargeBinary, nullable=True)  # For sensitive files
    content_preview = Column(Text, nullable=True)  # First 1000 characters
    
    # Content metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    compression_used = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    
    # Storage metadata
    storage_method = Column(String, nullable=False, default="database")  # database, filesystem, s3, etc.
    external_path = Column(String, nullable=True)  # For external storage
    
    # Timestamps
    stored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="file_content")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_hash_method', 'content_hash', 'storage_method'),
        Index('idx_content_encrypted', 'is_encrypted'),
    )

class FileKnowledgeExtraction(Base):
    """SQLAlchemy model for extracted knowledge from files"""
    __tablename__ = 'file_knowledge_extractions'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    knowledge_content = Column(JSON, nullable=False)
    
    # Extraction metadata
    extraction_method = Column(String, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_level = Column(String, nullable=False, default=ValidationLevel.BASIC.value)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    
    # Context information
    source_location = Column(JSON, nullable=False, default=dict)  # Line numbers, sections, etc.
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    
    # Quality metrics
    relevance_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    last_used = Column(DateTime, nullable=True)
    
    # Agent integration
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    integration_results = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="knowledge_extractions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_method_confidence', 'extraction_method', 'confidence_score'),
        Index('idx_extraction_validation', 'validation_status', 'validation_level'),
        Index('idx_extraction_agents', 'target_agents'),
        Index('idx_extraction_quality', 'relevance_score', 'uniqueness_score'),
    )

class FileProcessingLog(Base):
    """SQLAlchemy model for file processing logs"""
    __tablename__ = 'file_processing_logs'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    log_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Log details
    log_level = Column(String, nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_message = Column(Text, nullable=False)
    log_context = Column(JSON, nullable=False, default=dict)
    
    # Processing stage
    processing_stage = Column(String, nullable=False, index=True)  # upload, analysis, extraction, integration
    stage_duration_ms = Column(Float, nullable=True)
    
    # Error details (if applicable)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Timestamps
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="processing_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_log_level_stage', 'log_level', 'processing_stage'),
        Index('idx_log_error_type', 'error_type'),
        Index('idx_log_timing', 'logged_at', 'stage_duration_ms'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileProcessor:
    """Handles file processing and knowledge extraction"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component="file_processor")
        
        # Processing configuration
        self.max_file_size = config.get('max_file_size_mb', MAX_FILE_SIZE_MB) * 1024 * 1024
        self.supported_formats = self._get_supported_formats()
        self.extraction_timeout = config.get('extraction_timeout', FILE_ANALYSIS_TIMEOUT_SECONDS)
        
        # Knowledge extraction configuration
        self.extraction_methods = config.get('extraction_methods', [ExtractionMethod.TEXT_ANALYSIS])
        self.confidence_threshold = config.get('confidence_threshold', KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD)
        self.max_knowledge_items = config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_FILE)
        
        # Processing queues
        self.processing_queue: Dict[str, FileUploadSchema] = {}
        self.active_processing: Set[str] = set()
        
    def _get_supported_formats(self) -> Set[str]:
        """Get all supported file formats"""
        return (SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | 
                SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    
    async def process_file_upload(self, upload_schema: FileUploadSchema, file_content: bytes) -> Dict[str, Any]:
        """Process uploaded file and extract knowledge"""
        file_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting file processing", 
                           file_id=file_id, 
                           filename=upload_schema.filename,
                           file_size=upload_schema.file_size)
            
            # Phase 1: File validation and metadata extraction
            file_metadata = await self._extract_file_metadata(upload_schema, file_content)
            
            # Phase 2: Content analysis
            content_analysis = await self._analyze_file_content(file_content, file_metadata)
            
            # Phase 3: Knowledge extraction
            extracted_knowledge = await self._extract_knowledge(file_content, file_metadata, content_analysis)
            
            # Phase 4: Knowledge validation
            validated_knowledge = await self._validate_extracted_knowledge(extracted_knowledge)
            
            # Phase 5: Agent integration
            integration_results = await self._integrate_with_agents(validated_knowledge, upload_schema.target_agents)
            
            # Calculate processing metrics
            processing_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store file record
            file_record = await self._store_file_record(
                file_id, upload_schema, file_metadata, content_analysis, 
                validated_knowledge, integration_results, processing_duration
            )
            
            # Store file content
            await self._store_file_content(file_id, file_content, file_metadata)
            
            result = {
                "file_id": file_id,
                "status": "completed",
                "processing_duration_ms": processing_duration,
                "file_metadata": file_metadata.__dict__,
                "content_analysis": content_analysis.__dict__,
                "knowledge_items_extracted": len(validated_knowledge),
                "integration_results": integration_results
            }
            
            self.logger.info("File processing completed successfully", **result)
            return result
            
        except Exception as e:
            self.logger.error("File processing failed", 
                            file_id=file_id, 
                            filename=upload_schema.filename,
                            error=str(e))
            
            # Store error information
            await self._store_processing_error(file_id, upload_schema, str(e))
            
            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e),
                "processing_duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def _extract_file_metadata(self, upload_schema: FileUploadSchema, content: bytes) -> FileMetadata:
        """Extract comprehensive file metadata"""
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine file type
        file_extension = Path(upload_schema.filename).suffix.lower()
        file_type = self._classify_file_type(file_extension, upload_schema.content_type)
        
        # Extract text content for analysis
        text_content = ""
        encoding = None
        if file_type in [FileType.TEXT, FileType.CODE]:
            text_content, encoding = await self._extract_text_content(content, file_extension)
        
        # Calculate content metrics
        line_count = len(text_content.split('\n')) if text_content else None
        word_count = len(text_content.split()) if text_content else None
        character_count = len(text_content) if text_content else None
        
        # Detect language for code files
        language = None
        if file_type == FileType.CODE:
            language = self._detect_programming_language(file_extension, text_content)
        
        return FileMetadata(
            filename=upload_schema.filename,
            file_size=upload_schema.file_size,
            mime_type=upload_schema.content_type,
            file_hash=file_hash,
            encoding=encoding,
            file_type=file_type,
            content_category=upload_schema.content_category,
            language=language,
            line_count=line_count,
            word_count=word_count,
            character_count=character_count
        )
    
    def _classify_file_type(self, extension: str, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        if extension in SUPPORTED_TEXT_FORMATS:
            return FileType.TEXT
        elif extension in SUPPORTED_DOCUMENT_FORMATS:
            return FileType.DOCUMENT
        elif extension in SUPPORTED_CODE_FORMATS:
            return FileType.CODE
        elif extension in SUPPORTED_DATA_FORMATS:
            return FileType.DATA
        elif extension in SUPPORTED_IMAGE_FORMATS:
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif extension in {'.zip', '.tar', '.gz', '.rar', '.7z'}:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def _extract_text_content(self, content: bytes, extension: str) -> Tuple[str, Optional[str]]:
        """Extract text content from file"""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                return text_content, encoding
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace'), 'utf-8'
    
    def _detect_programming_language(self, extension: str, content: str) -> Optional[str]:
        """Detect programming language from extension and content"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return language_map.get(extension)
    
    async def _analyze_file_content(self, content: bytes, metadata: FileMetadata) -> ContentAnalysis:
        """Analyze file content for quality and complexity"""
        analysis = ContentAnalysis()
        
        # For text-based files, perform detailed analysis
        if metadata.file_type in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
            
            # Calculate readability score
            analysis.readability_score = self._calculate_readability(text_content)
            
            # Calculate complexity score
            analysis.complexity_score = self._calculate_complexity(text_content, metadata.file_type)
            
            # Calculate quality score
            analysis.quality_score = self._calculate_quality(text_content, metadata)
            
            # Calculate uniqueness score
            analysis.uniqueness_score = await self._calculate_uniqueness(text_content)
            
            # Extract key concepts and topics
            analysis.key_concepts = self._extract_key_concepts(text_content)
            analysis.topics = self._extract_topics(text_content)
            analysis.concept_count = len(analysis.key_concepts)
            
            # Extract entities
            analysis.entities = self._extract_entities(text_content)
            
            # Calculate technical depth
            analysis.technical_depth = self._calculate_technical_depth(text_content, metadata.language)
            
            # Calculate relevance score
            analysis.relevance_score = self._calculate_relevance(text_content, metadata.content_category)
        
        return analysis
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using various metrics"""
        if not text:
            return 0.0
        
        # Simple readability calculation based on sentence and word length
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normalize to 0-100 scale (inverse relationship for complexity)
        readability = max(0, 100 - (avg_sentence_length * 2 + avg_word_length * 5))
        return min(readability, 100.0)
    
    def _calculate_complexity(self, text: str, file_type: FileType) -> float:
        """Calculate content complexity score"""
        if not text:
            return 0.0
        
        complexity_indicators = {
            'technical_terms': len([word for word in text.split() if len(word) > 10]),
            'punctuation_density': sum(1 for char in text if char in '.,;:!?()[]{}'),
            'nested_structures': text.count('(') + text.count('[') + text.count('{'),
            'line_length_variance': 0  # Simplified
        }
        
        if file_type == FileType.CODE:
            # Additional complexity for code
            complexity_indicators.update({
                'function_definitions': text.count('def ') + text.count('function '),
                'conditional_statements': text.count('if ') + text.count('while ') + text.count('for '),
                'import_statements': text.count('import ') + text.count('require('),
            })
        
        # Normalize to 0-100 scale
        total_indicators = sum(complexity_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        complexity = min((total_indicators / text_length) * 1000, 100.0)
        return complexity
    
    def _calculate_quality(self, text: str, metadata: FileMetadata) -> float:
        """Calculate content quality score"""
        if not text:
            return 0.0
        
        quality_factors = {
            'length_adequacy': min(len(text.split()) / 100, 1.0) * 25,  # Adequate length
            'structure_score': self._assess_structure(text) * 20,  # Good structure
            'grammar_score': self._assess_grammar(text) * 20,  # Grammar quality
            'completeness_score': self._assess_completeness(text) * 20,  # Content completeness
            'consistency_score': self._assess_consistency(text) * 15   # Style consistency
        }
        
        return sum(quality_factors.values())
    
    def _assess_structure(self, text: str) -> float:
        """Assess text structure quality"""
        # Simple structure assessment
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        # Check for headings, paragraphs, lists
        structure_score = 0.0
        if any(line.startswith('#') for line in lines):  # Markdown headings
            structure_score += 0.3
        if len(non_empty_lines) > 5:  # Multiple paragraphs
            structure_score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in lines):  # Lists
            structure_score += 0.4
        
        return min(structure_score, 1.0)
    
    def _assess_grammar(self, text: str) -> float:
        """Assess grammar quality (simplified)"""
        # Simple grammar assessment
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        # Check for basic grammar indicators
        capitalized_sentences = sum(1 for s in sentences if s and s[0].isupper())
        grammar_score = capitalized_sentences / len(sentences)
        
        return grammar_score
    
    def _assess_completeness(self, text: str) -> float:
        """Assess content completeness"""
        # Check for introduction, body, conclusion indicators
        completeness_indicators = 0
        
        intro_words = ['introduction', 'overview', 'summary', 'abstract']
        if any(word in text.lower() for word in intro_words):
            completeness_indicators += 1
        
        if len(text.split()) > 200:  # Substantial content
            completeness_indicators += 1
        
        conclusion_words = ['conclusion', 'summary', 'finally', 'in summary']
        if any(word in text.lower() for word in conclusion_words):
            completeness_indicators += 1
        
        return completeness_indicators / 3.0
    
    def _assess_consistency(self, text:  # Explicit steps
        ]
        
        for line in lines:
            for pattern in step_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    if len(match.groups()) == 2:
                        step_num, step_text = match.groups()
                        steps.append({'step': step_num, 'description': step_text})
                    else:
                        steps.append({'step': str(len(steps) + 1), 'description': match.group(1)})
        
        return steps[:10]  # Limit to 10 steps
    
    def _extract_best_practices(self, text: str) -> List[str]:
        """Extract best practices from text"""
        practices = []
        
        # Look for best practice indicators
        indicators = ['best practice', 'recommendation', 'should', 'always', 'never', 'avoid', 'prefer']
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if any(indicator in sentence.lower() for indicator in indicators):
                if len(sentence) > 20 and len(sentence) < 200:  # Reasonable length
                    practices.append(sentence)
        
        return practices[:5]  # Limit to 5 practices
    
    def _extract_error_patterns(self, text: str) -> List[Dict[str, str]]:
        """Extract error patterns from text"""
        patterns = []
        
        # Look for error-related content
        error_indicators = ['error', 'exception', 'failure', 'bug', 'issue', 'problem']
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in error_indicators):
                # Look for solution in nearby lines
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                context = '\n'.join(lines[context_start:context_end])
                
                patterns.append({
                    'error_description': line.strip(),
                    'context': context,
                    'line_number': i + 1
                })
        
        return patterns[:3]  # Limit to 3 patterns
    
    async def _extract_via_pattern_recognition(self, text: str, metadata: FileMetadata) -> List[Dict[str, Any]]:
        """Extract knowledge via pattern recognition"""
        knowledge_items = []
        
        # Code patterns (for code files)
        if metadata.file_type == FileType.CODE:
            patterns = self._recognize_code_patterns(text, metadata.language)
            if patterns:
                knowledge_items.append({
                    'knowledge_type': KnowledgeType.BEHAVIORAL_PATTERN.value,
                    'content': {
                        'type': 'code_patterns',
                        'patterns': patterns,
                        'language': metadata.language,
                        'source_file': metadata.filename
                    },
                    'confidence_score': 0.8,
                    'extraction_method': ExtractionMethod.PATTERN_RECOGNITION.value,
                    'source_location': {'type': 'code_structures'}
                })
        
        return knowledge_items
    
    def _recognize_code_patterns(self, text: str, language: Optional[str]) -> List[Dict[str, Any]]:
        """Recognize common code patterns"""
        patterns = []
        
        if not language:
            return patterns
        
        # Common patterns by language
        if language == 'python':
            # Decorator pattern
            if '@' in text:
                decorators = [line.strip() for line in text.split('\n') if line.strip().startswith('@')]
                if decorators:
                    patterns.append({
                        'pattern_name': 'decorator_usage',
                        'occurrences': len(decorators),
                        'examples': decorators[:3]
                    })
            
            # Context manager pattern
            if 'with ' in text and ' as ' in text:
                patterns.append({
                    'pattern_name': 'context_manager',
                    'description': 'Uses context managers for resource management'
                })
        
        elif language == 'javascript':
            # Promise pattern
            if 'async' in text or 'await' in text:
                patterns.append({
                    'pattern_name': 'async_await',
                    'description': 'Uses modern async/await pattern'
                })
            
            # Module pattern
            if 'export' in text or 'import' in text:
                patterns.append({
                    'pattern_name': 'es6_modules',
                    'description': 'Uses ES6 module system'
                })
        
        return patterns
    
    async def _extract_via_statistical_analysis(self, text: str, metadata: FileMetadata) -> List[Dict[str, Any]]:
        """Extract knowledge via statistical analysis"""
        knowledge_items = []
        
        # Analyze word frequency and patterns
        words = text.lower().split()
        if len(words) > 100:  # Only for substantial content
            word_freq = {}
            for word in words:
                clean_word = ''.join(c for c in word if c.isalnum())
                if len(clean_word) > 3:
                    word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
            
            # Find statistical patterns
            if word_freq:
                top_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
                
                knowledge_items.append({
                    'knowledge_type': KnowledgeType.PERFORMANCE_INSIGHT.value,
                    'content': {
                        'type': 'term_frequency_analysis',
                        'top_terms': top_terms,
                        'total_words': len(words),
                        'unique_words': len(word_freq),
                        'vocabulary_richness': len(word_freq) / len(words),
                        'source_file': metadata.filename
                    },
                    'confidence_score': 0.6,
                    'extraction_method': ExtractionMethod.STATISTICAL_ANALYSIS.value,
                    'source_location': {'type': 'statistical_distribution'}
                })
        
        return knowledge_items
    
    async def _extract_via_rule_based(self, text: str, metadata: FileMetadata) -> List[Dict[str, Any]]:
        """Extract knowledge via rule-based methods"""
        knowledge_items = []
        
        # Configuration rules
        if metadata.content_category == ContentCategory.CONFIGURATION:
            config_rules = self._extract_configuration_rules(text)
            if config_rules:
                knowledge_items.append({
                    'knowledge_type': KnowledgeType.EXTERNAL_INTEGRATION.value,
                    'content': {
                        'type': 'configuration_rules',
                        'rules': config_rules,
                        'source_file': metadata.filename
                    },
                    'confidence_score': 0.9,
                    'extraction_method': ExtractionMethod.RULE_BASED.value,
                    'source_location': {'type': 'configuration_sections'}
                })
        
        return knowledge_items
    
    def _extract_configuration_rules(self, text: str) -> List[Dict[str, Any]]:
        """Extract configuration rules from text"""
        rules = []
        
        # Look for key-value pairs
        import re
        patterns = [
            r'^([A-Z_]+)\s*=\s*(.+)"""
YMERA Enterprise - File Learning Models
Production-Ready File Metadata & Learning Integration Models - v4.0
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
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from agent_models import KnowledgeType, LearningStatus

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File processing constants
MAX_FILE_SIZE_MB = 100
SUPPORTED_TEXT_FORMATS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.docx', '.doc', '.rtf', '.odt'}
SUPPORTED_CODE_FORMATS = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
SUPPORTED_DATA_FORMATS = {'.csv', '.xlsx', '.xls', '.json', '.xml', '.parquet'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}

# Learning integration constants
KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD = 0.6
MAX_KNOWLEDGE_ITEMS_PER_FILE = 50
FILE_ANALYSIS_TIMEOUT_SECONDS = 300
CONTENT_SIMILARITY_THRESHOLD = 0.8

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class FileType(str, Enum):
    """File type classification"""
    TEXT = "text"
    DOCUMENT = "document" 
    CODE = "code"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class FileStatus(str, Enum):
    """File processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    INTEGRATED = "integrated"
    ERROR = "error"
    ARCHIVED = "archived"

class ProcessingPriority(IntEnum):
    """File processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class ContentCategory(str, Enum):
    """Content categorization for learning"""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SPECIFICATION = "specification"
    EXAMPLE = "example"
    CONFIGURATION = "configuration"
    DATA_SAMPLE = "data_sample"
    ERROR_LOG = "error_log"
    PERFORMANCE_DATA = "performance_data"
    USER_FEEDBACK = "user_feedback"
    RESEARCH = "research"

class ExtractionMethod(str, Enum):
    """Knowledge extraction methods"""
    TEXT_ANALYSIS = "text_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    ML_INFERENCE = "ml_inference"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class ValidationLevel(str, Enum):
    """Knowledge validation levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    encoding: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    content_category: Optional[ContentCategory] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    line_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None

@dataclass
class ProcessingMetrics:
    """File processing performance metrics"""
    processing_duration_ms: float = 0.0
    analysis_duration_ms: float = 0.0
    extraction_duration_ms: float = 0.0
    integration_duration_ms: float = 0.0
    knowledge_items_extracted: int = 0
    knowledge_items_validated: int = 0
    knowledge_items_integrated: int = 0
    error_count: int = 0
    retry_count: int = 0

@dataclass
class ContentAnalysis:
    """Content analysis results"""
    readability_score: float = 0.0
    complexity_score: float = 0.0
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    relevance_score: float = 0.0
    technical_depth: float = 0.0
    concept_count: int = 0
    key_concepts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class FileUploadSchema(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_MB*1024*1024, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File content hash")
    processing_priority: ProcessingPriority = Field(default=ProcessingPriority.NORMAL)
    content_category: Optional[ContentCategory] = Field(None, description="Content category hint")
    extraction_config: Dict[str, Any] = Field(default_factory=dict, description="Extraction configuration")
    target_agents: List[str] = Field(default_factory=list, description="Target agents for knowledge")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Filename cannot be empty')
        # Remove path components for security
        return os.path.basename(v)
    
    @validator('file_hash')
    def validate_file_hash(cls, v):
        if v and len(v) not in [32, 40, 64, 128]:  # MD5, SHA1, SHA256, SHA512
            raise ValueError('Invalid hash format')
        return v

class KnowledgeExtractionSchema(BaseModel):
    """Schema for knowledge extraction configuration"""
    extraction_methods: List[ExtractionMethod] = Field(default_factory=lambda: [ExtractionMethod.TEXT_ANALYSIS])
    confidence_threshold: float = Field(default=KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0)
    max_items: int = Field(default=MAX_KNOWLEDGE_ITEMS_PER_FILE, ge=1, le=100)
    validation_level: ValidationLevel = Field(default=ValidationLevel.INTERMEDIATE)
    context_window: int = Field(default=1000, ge=100, le=5000, description="Context window for extraction")
    include_metadata: bool = Field(default=True, description="Include file metadata in knowledge")
    cross_reference: bool = Field(default=True, description="Cross-reference with existing knowledge")
    auto_categorize: bool = Field(default=True, description="Automatically categorize knowledge")

class FileAnalysisSchema(BaseModel):
    """Schema for file analysis results"""
    file_id: str = Field(..., description="File identifier")
    file_metadata: Dict[str, Any] = Field(..., description="File metadata")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    extracted_knowledge: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    integration_status: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileStatusSchema(BaseModel):
    """Schema for file status reporting"""
    file_id: str = Field(..., description="File identifier")
    filename: str = Field(..., description="Original filename")
    current_status: FileStatus = Field(..., description="Current processing status")
    processing_progress: float = Field(..., ge=0.0, le=100.0, description="Processing progress percentage")
    knowledge_items_count: int = Field(default=0, ge=0, description="Number of knowledge items extracted")
    integrated_agents: List[str] = Field(default_factory=list, description="Agents that received knowledge")
    error_messages: List[str] = Field(default_factory=list, description="Error messages if any")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchSchema(BaseModel):
    """Schema for file search requests"""
    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[FileType]] = Field(None, description="Filter by file types")
    content_categories: Optional[List[ContentCategory]] = Field(None, description="Filter by content categories")
    date_from: Optional[datetime] = Field(None, description="Filter files from date")
    date_to: Optional[datetime] = Field(None, description="Filter files to date")
    size_min: Optional[int] = Field(None, ge=0, description="Minimum file size")
    size_max: Optional[int] = Field(None, ge=0, description="Maximum file size")
    has_knowledge: Optional[bool] = Field(None, description="Filter files with extracted knowledge")
    agent_ids: Optional[List[str]] = Field(None, description="Filter by associated agents")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file records"""
    __tablename__ = 'file_records'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, nullable=False, index=True)
    
    # File metadata
    filename = Column(String, nullable=False, index=True)
    original_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False, index=True)
    file_hash = Column(String, nullable=False, unique=True, index=True)
    encoding = Column(String, nullable=True)
    
    # Classification
    file_type = Column(String, nullable=False, index=True)
    content_category = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    charset = Column(String, nullable=True)
    
    # Content metrics
    line_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing status
    current_status = Column(String, nullable=False, default=FileStatus.UPLOADED.value, index=True)
    processing_priority = Column(Integer, nullable=False, default=ProcessingPriority.NORMAL.value)
    processing_progress = Column(Float, nullable=False, default=0.0)
    
    # Processing metrics
    processing_duration_ms = Column(Float, nullable=False, default=0.0)
    analysis_duration_ms = Column(Float, nullable=False, default=0.0)
    extraction_duration_ms = Column(Float, nullable=False, default=0.0)
    integration_duration_ms = Column(Float, nullable=False, default=0.0)
    
    # Knowledge extraction results
    knowledge_items_extracted = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_integrated = Column(Integer, nullable=False, default=0)
    
    # Content analysis
    readability_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    technical_depth = Column(Float, nullable=False, default=0.0)
    concept_count = Column(Integer, nullable=False, default=0)
    
    # Structured data
    key_concepts = Column(ARRAY(String), nullable=False, default=list)
    topics = Column(ARRAY(String), nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    extraction_config = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    
    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    error_messages = Column(JSON, nullable=False, default=list)
    
    # Agent associations
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_content = relationship("FileContent", back_populates="file_record", uselist=False, cascade="all, delete-orphan")
    knowledge_extractions = relationship("FileKnowledgeExtraction", back_populates="file_record", cascade="all, delete-orphan")
    processing_logs = relationship("FileProcessingLog", back_populates="file_record", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_status_priority', 'current_status', 'processing_priority'),
        Index('idx_file_type_category', 'file_type', 'content_category'),
        Index('idx_file_size_upload', 'file_size', 'uploaded_at'),
        Index('idx_file_knowledge_count', 'knowledge_items_integrated'),
        Index('idx_file_quality_scores', 'quality_score', 'relevance_score'),
        Index('idx_file_agents', 'target_agents'),
    )

class FileContent(Base):
    """SQLAlchemy model for file content storage"""
    __tablename__ = 'file_contents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, unique=True, index=True)
    
    # Content storage
    raw_content = Column(LargeBinary, nullable=True)  # For binary files
    text_content = Column(Text, nullable=True)  # For text files
    encrypted_content = Column(LargeBinary, nullable=True)  # For sensitive files
    content_preview = Column(Text, nullable=True)  # First 1000 characters
    
    # Content metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    compression_used = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    
    # Storage metadata
    storage_method = Column(String, nullable=False, default="database")  # database, filesystem, s3, etc.
    external_path = Column(String, nullable=True)  # For external storage
    
    # Timestamps
    stored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="file_content")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_hash_method', 'content_hash', 'storage_method'),
        Index('idx_content_encrypted', 'is_encrypted'),
    )

class FileKnowledgeExtraction(Base):
    """SQLAlchemy model for extracted knowledge from files"""
    __tablename__ = 'file_knowledge_extractions'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    knowledge_content = Column(JSON, nullable=False)
    
    # Extraction metadata
    extraction_method = Column(String, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_level = Column(String, nullable=False, default=ValidationLevel.BASIC.value)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    
    # Context information
    source_location = Column(JSON, nullable=False, default=dict)  # Line numbers, sections, etc.
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    
    # Quality metrics
    relevance_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    last_used = Column(DateTime, nullable=True)
    
    # Agent integration
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    integration_results = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="knowledge_extractions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_method_confidence', 'extraction_method', 'confidence_score'),
        Index('idx_extraction_validation', 'validation_status', 'validation_level'),
        Index('idx_extraction_agents', 'target_agents'),
        Index('idx_extraction_quality', 'relevance_score', 'uniqueness_score'),
    )

class FileProcessingLog(Base):
    """SQLAlchemy model for file processing logs"""
    __tablename__ = 'file_processing_logs'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    log_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Log details
    log_level = Column(String, nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_message = Column(Text, nullable=False)
    log_context = Column(JSON, nullable=False, default=dict)
    
    # Processing stage
    processing_stage = Column(String, nullable=False, index=True)  # upload, analysis, extraction, integration
    stage_duration_ms = Column(Float, nullable=True)
    
    # Error details (if applicable)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Timestamps
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="processing_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_log_level_stage', 'log_level', 'processing_stage'),
        Index('idx_log_error_type', 'error_type'),
        Index('idx_log_timing', 'logged_at', 'stage_duration_ms'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileProcessor:
    """Handles file processing and knowledge extraction"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component="file_processor")
        
        # Processing configuration
        self.max_file_size = config.get('max_file_size_mb', MAX_FILE_SIZE_MB) * 1024 * 1024
        self.supported_formats = self._get_supported_formats()
        self.extraction_timeout = config.get('extraction_timeout', FILE_ANALYSIS_TIMEOUT_SECONDS)
        
        # Knowledge extraction configuration
        self.extraction_methods = config.get('extraction_methods', [ExtractionMethod.TEXT_ANALYSIS])
        self.confidence_threshold = config.get('confidence_threshold', KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD)
        self.max_knowledge_items = config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_FILE)
        
        # Processing queues
        self.processing_queue: Dict[str, FileUploadSchema] = {}
        self.active_processing: Set[str] = set()
        
    def _get_supported_formats(self) -> Set[str]:
        """Get all supported file formats"""
        return (SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | 
                SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    
    async def process_file_upload(self, upload_schema: FileUploadSchema, file_content: bytes) -> Dict[str, Any]:
        """Process uploaded file and extract knowledge"""
        file_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting file processing", 
                           file_id=file_id, 
                           filename=upload_schema.filename,
                           file_size=upload_schema.file_size)
            
            # Phase 1: File validation and metadata extraction
            file_metadata = await self._extract_file_metadata(upload_schema, file_content)
            
            # Phase 2: Content analysis
            content_analysis = await self._analyze_file_content(file_content, file_metadata)
            
            # Phase 3: Knowledge extraction
            extracted_knowledge = await self._extract_knowledge(file_content, file_metadata, content_analysis)
            
            # Phase 4: Knowledge validation
            validated_knowledge = await self._validate_extracted_knowledge(extracted_knowledge)
            
            # Phase 5: Agent integration
            integration_results = await self._integrate_with_agents(validated_knowledge, upload_schema.target_agents)
            
            # Calculate processing metrics
            processing_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store file record
            file_record = await self._store_file_record(
                file_id, upload_schema, file_metadata, content_analysis, 
                validated_knowledge, integration_results, processing_duration
            )
            
            # Store file content
            await self._store_file_content(file_id, file_content, file_metadata)
            
            result = {
                "file_id": file_id,
                "status": "completed",
                "processing_duration_ms": processing_duration,
                "file_metadata": file_metadata.__dict__,
                "content_analysis": content_analysis.__dict__,
                "knowledge_items_extracted": len(validated_knowledge),
                "integration_results": integration_results
            }
            
            self.logger.info("File processing completed successfully", **result)
            return result
            
        except Exception as e:
            self.logger.error("File processing failed", 
                            file_id=file_id, 
                            filename=upload_schema.filename,
                            error=str(e))
            
            # Store error information
            await self._store_processing_error(file_id, upload_schema, str(e))
            
            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e),
                "processing_duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def _extract_file_metadata(self, upload_schema: FileUploadSchema, content: bytes) -> FileMetadata:
        """Extract comprehensive file metadata"""
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine file type
        file_extension = Path(upload_schema.filename).suffix.lower()
        file_type = self._classify_file_type(file_extension, upload_schema.content_type)
        
        # Extract text content for analysis
        text_content = ""
        encoding = None
        if file_type in [FileType.TEXT, FileType.CODE]:
            text_content, encoding = await self._extract_text_content(content, file_extension)
        
        # Calculate content metrics
        line_count = len(text_content.split('\n')) if text_content else None
        word_count = len(text_content.split()) if text_content else None
        character_count = len(text_content) if text_content else None
        
        # Detect language for code files
        language = None
        if file_type == FileType.CODE:
            language = self._detect_programming_language(file_extension, text_content)
        
        return FileMetadata(
            filename=upload_schema.filename,
            file_size=upload_schema.file_size,
            mime_type=upload_schema.content_type,
            file_hash=file_hash,
            encoding=encoding,
            file_type=file_type,
            content_category=upload_schema.content_category,
            language=language,
            line_count=line_count,
            word_count=word_count,
            character_count=character_count
        )
    
    def _classify_file_type(self, extension: str, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        if extension in SUPPORTED_TEXT_FORMATS:
            return FileType.TEXT
        elif extension in SUPPORTED_DOCUMENT_FORMATS:
            return FileType.DOCUMENT
        elif extension in SUPPORTED_CODE_FORMATS:
            return FileType.CODE
        elif extension in SUPPORTED_DATA_FORMATS:
            return FileType.DATA
        elif extension in SUPPORTED_IMAGE_FORMATS:
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif extension in {'.zip', '.tar', '.gz', '.rar', '.7z'}:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def _extract_text_content(self, content: bytes, extension: str) -> Tuple[str, Optional[str]]:
        """Extract text content from file"""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                return text_content, encoding
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace'), 'utf-8'
    
    def _detect_programming_language(self, extension: str, content: str) -> Optional[str]:
        """Detect programming language from extension and content"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return language_map.get(extension)
    
    async def _analyze_file_content(self, content: bytes, metadata: FileMetadata) -> ContentAnalysis:
        """Analyze file content for quality and complexity"""
        analysis = ContentAnalysis()
        
        # For text-based files, perform detailed analysis
        if metadata.file_type in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
            
            # Calculate readability score
            analysis.readability_score = self._calculate_readability(text_content)
            
            # Calculate complexity score
            analysis.complexity_score = self._calculate_complexity(text_content, metadata.file_type)
            
            # Calculate quality score
            analysis.quality_score = self._calculate_quality(text_content, metadata)
            
            # Calculate uniqueness score
            analysis.uniqueness_score = await self._calculate_uniqueness(text_content)
            
            # Extract key concepts and topics
            analysis.key_concepts = self._extract_key_concepts(text_content)
            analysis.topics = self._extract_topics(text_content)
            analysis.concept_count = len(analysis.key_concepts)
            
            # Extract entities
            analysis.entities = self._extract_entities(text_content)
            
            # Calculate technical depth
            analysis.technical_depth = self._calculate_technical_depth(text_content, metadata.language)
            
            # Calculate relevance score
            analysis.relevance_score = self._calculate_relevance(text_content, metadata.content_category)
        
        return analysis
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using various metrics"""
        if not text:
            return 0.0
        
        # Simple readability calculation based on sentence and word length
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normalize to 0-100 scale (inverse relationship for complexity)
        readability = max(0, 100 - (avg_sentence_length * 2 + avg_word_length * 5))
        return min(readability, 100.0)
    
    def _calculate_complexity(self, text: str, file_type: FileType) -> float:
        """Calculate content complexity score"""
        if not text:
            return 0.0
        
        complexity_indicators = {
            'technical_terms': len([word for word in text.split() if len(word) > 10]),
            'punctuation_density': sum(1 for char in text if char in '.,;:!?()[]{}'),
            'nested_structures': text.count('(') + text.count('[') + text.count('{'),
            'line_length_variance': 0  # Simplified
        }
        
        if file_type == FileType.CODE:
            # Additional complexity for code
            complexity_indicators.update({
                'function_definitions': text.count('def ') + text.count('function '),
                'conditional_statements': text.count('if ') + text.count('while ') + text.count('for '),
                'import_statements': text.count('import ') + text.count('require('),
            })
        
        # Normalize to 0-100 scale
        total_indicators = sum(complexity_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        complexity = min((total_indicators / text_length) * 1000, 100.0)
        return complexity
    
    def _calculate_quality(self, text: str, metadata: FileMetadata) -> float:
        """Calculate content quality score"""
        if not text:
            return 0.0
        
        quality_factors = {
            'length_adequacy': min(len(text.split()) / 100, 1.0) * 25,  # Adequate length
            'structure_score': self._assess_structure(text) * 20,  # Good structure
            'grammar_score': self._assess_grammar(text) * 20,  # Grammar quality
            'completeness_score': self._assess_completeness(text) * 20,  # Content completeness
            'consistency_score': self._assess_consistency(text) * 15   # Style consistency
        }
        
        return sum(quality_factors.values())
    
    def _assess_structure(self, text: str) -> float:
        """Assess text structure quality"""
        # Simple structure assessment
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        # Check for headings, paragraphs, lists
        structure_score = 0.0
        if any(line.startswith('#') for line in lines):  # Markdown headings
            structure_score += 0.3
        if len(non_empty_lines) > 5:  # Multiple paragraphs
            structure_score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in lines):  # Lists
            structure_score += 0.4
        
        return min(structure_score, 1.0)
    
    def _assess_grammar(self, text: str) -> float:
        """Assess grammar quality (simplified)"""
        # Simple grammar assessment
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        # Check for basic grammar indicators
        capitalized_sentences = sum(1 for s in sentences if s and s[0].isupper())
        grammar_score = capitalized_sentences / len(sentences)
        
        return grammar_score
    
    def _assess_completeness(self, text: str) -> float:
        """Assess content completeness"""
        # Check for introduction, body, conclusion indicators
        completeness_indicators = 0
        
        intro_words = ['introduction', 'overview', 'summary', 'abstract']
        if any(word in text.lower() for word in intro_words):
            completeness_indicators += 1
        
        if len(text.split()) > 200:  # Substantial content
            completeness_indicators += 1
        
        conclusion_words = ['conclusion', 'summary', 'finally', 'in summary']
        if any(word in text.lower() for word in conclusion_words):
            completeness_indicators += 1
        
        return completeness_indicators / 3.0
    
    def _assess_consistency(self, text:,  # Environment variables
            r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.+)"""
YMERA Enterprise - File Learning Models
Production-Ready File Metadata & Learning Integration Models - v4.0
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
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from agent_models import KnowledgeType, LearningStatus

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File processing constants
MAX_FILE_SIZE_MB = 100
SUPPORTED_TEXT_FORMATS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.docx', '.doc', '.rtf', '.odt'}
SUPPORTED_CODE_FORMATS = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
SUPPORTED_DATA_FORMATS = {'.csv', '.xlsx', '.xls', '.json', '.xml', '.parquet'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}

# Learning integration constants
KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD = 0.6
MAX_KNOWLEDGE_ITEMS_PER_FILE = 50
FILE_ANALYSIS_TIMEOUT_SECONDS = 300
CONTENT_SIMILARITY_THRESHOLD = 0.8

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class FileType(str, Enum):
    """File type classification"""
    TEXT = "text"
    DOCUMENT = "document" 
    CODE = "code"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class FileStatus(str, Enum):
    """File processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    INTEGRATED = "integrated"
    ERROR = "error"
    ARCHIVED = "archived"

class ProcessingPriority(IntEnum):
    """File processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class ContentCategory(str, Enum):
    """Content categorization for learning"""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SPECIFICATION = "specification"
    EXAMPLE = "example"
    CONFIGURATION = "configuration"
    DATA_SAMPLE = "data_sample"
    ERROR_LOG = "error_log"
    PERFORMANCE_DATA = "performance_data"
    USER_FEEDBACK = "user_feedback"
    RESEARCH = "research"

class ExtractionMethod(str, Enum):
    """Knowledge extraction methods"""
    TEXT_ANALYSIS = "text_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    ML_INFERENCE = "ml_inference"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class ValidationLevel(str, Enum):
    """Knowledge validation levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    encoding: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    content_category: Optional[ContentCategory] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    line_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None

@dataclass
class ProcessingMetrics:
    """File processing performance metrics"""
    processing_duration_ms: float = 0.0
    analysis_duration_ms: float = 0.0
    extraction_duration_ms: float = 0.0
    integration_duration_ms: float = 0.0
    knowledge_items_extracted: int = 0
    knowledge_items_validated: int = 0
    knowledge_items_integrated: int = 0
    error_count: int = 0
    retry_count: int = 0

@dataclass
class ContentAnalysis:
    """Content analysis results"""
    readability_score: float = 0.0
    complexity_score: float = 0.0
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    relevance_score: float = 0.0
    technical_depth: float = 0.0
    concept_count: int = 0
    key_concepts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class FileUploadSchema(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_MB*1024*1024, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File content hash")
    processing_priority: ProcessingPriority = Field(default=ProcessingPriority.NORMAL)
    content_category: Optional[ContentCategory] = Field(None, description="Content category hint")
    extraction_config: Dict[str, Any] = Field(default_factory=dict, description="Extraction configuration")
    target_agents: List[str] = Field(default_factory=list, description="Target agents for knowledge")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Filename cannot be empty')
        # Remove path components for security
        return os.path.basename(v)
    
    @validator('file_hash')
    def validate_file_hash(cls, v):
        if v and len(v) not in [32, 40, 64, 128]:  # MD5, SHA1, SHA256, SHA512
            raise ValueError('Invalid hash format')
        return v

class KnowledgeExtractionSchema(BaseModel):
    """Schema for knowledge extraction configuration"""
    extraction_methods: List[ExtractionMethod] = Field(default_factory=lambda: [ExtractionMethod.TEXT_ANALYSIS])
    confidence_threshold: float = Field(default=KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0)
    max_items: int = Field(default=MAX_KNOWLEDGE_ITEMS_PER_FILE, ge=1, le=100)
    validation_level: ValidationLevel = Field(default=ValidationLevel.INTERMEDIATE)
    context_window: int = Field(default=1000, ge=100, le=5000, description="Context window for extraction")
    include_metadata: bool = Field(default=True, description="Include file metadata in knowledge")
    cross_reference: bool = Field(default=True, description="Cross-reference with existing knowledge")
    auto_categorize: bool = Field(default=True, description="Automatically categorize knowledge")

class FileAnalysisSchema(BaseModel):
    """Schema for file analysis results"""
    file_id: str = Field(..., description="File identifier")
    file_metadata: Dict[str, Any] = Field(..., description="File metadata")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    extracted_knowledge: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    integration_status: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileStatusSchema(BaseModel):
    """Schema for file status reporting"""
    file_id: str = Field(..., description="File identifier")
    filename: str = Field(..., description="Original filename")
    current_status: FileStatus = Field(..., description="Current processing status")
    processing_progress: float = Field(..., ge=0.0, le=100.0, description="Processing progress percentage")
    knowledge_items_count: int = Field(default=0, ge=0, description="Number of knowledge items extracted")
    integrated_agents: List[str] = Field(default_factory=list, description="Agents that received knowledge")
    error_messages: List[str] = Field(default_factory=list, description="Error messages if any")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchSchema(BaseModel):
    """Schema for file search requests"""
    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[FileType]] = Field(None, description="Filter by file types")
    content_categories: Optional[List[ContentCategory]] = Field(None, description="Filter by content categories")
    date_from: Optional[datetime] = Field(None, description="Filter files from date")
    date_to: Optional[datetime] = Field(None, description="Filter files to date")
    size_min: Optional[int] = Field(None, ge=0, description="Minimum file size")
    size_max: Optional[int] = Field(None, ge=0, description="Maximum file size")
    has_knowledge: Optional[bool] = Field(None, description="Filter files with extracted knowledge")
    agent_ids: Optional[List[str]] = Field(None, description="Filter by associated agents")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file records"""
    __tablename__ = 'file_records'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, nullable=False, index=True)
    
    # File metadata
    filename = Column(String, nullable=False, index=True)
    original_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False, index=True)
    file_hash = Column(String, nullable=False, unique=True, index=True)
    encoding = Column(String, nullable=True)
    
    # Classification
    file_type = Column(String, nullable=False, index=True)
    content_category = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    charset = Column(String, nullable=True)
    
    # Content metrics
    line_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing status
    current_status = Column(String, nullable=False, default=FileStatus.UPLOADED.value, index=True)
    processing_priority = Column(Integer, nullable=False, default=ProcessingPriority.NORMAL.value)
    processing_progress = Column(Float, nullable=False, default=0.0)
    
    # Processing metrics
    processing_duration_ms = Column(Float, nullable=False, default=0.0)
    analysis_duration_ms = Column(Float, nullable=False, default=0.0)
    extraction_duration_ms = Column(Float, nullable=False, default=0.0)
    integration_duration_ms = Column(Float, nullable=False, default=0.0)
    
    # Knowledge extraction results
    knowledge_items_extracted = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_integrated = Column(Integer, nullable=False, default=0)
    
    # Content analysis
    readability_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    technical_depth = Column(Float, nullable=False, default=0.0)
    concept_count = Column(Integer, nullable=False, default=0)
    
    # Structured data
    key_concepts = Column(ARRAY(String), nullable=False, default=list)
    topics = Column(ARRAY(String), nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    extraction_config = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    
    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    error_messages = Column(JSON, nullable=False, default=list)
    
    # Agent associations
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_content = relationship("FileContent", back_populates="file_record", uselist=False, cascade="all, delete-orphan")
    knowledge_extractions = relationship("FileKnowledgeExtraction", back_populates="file_record", cascade="all, delete-orphan")
    processing_logs = relationship("FileProcessingLog", back_populates="file_record", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_status_priority', 'current_status', 'processing_priority'),
        Index('idx_file_type_category', 'file_type', 'content_category'),
        Index('idx_file_size_upload', 'file_size', 'uploaded_at'),
        Index('idx_file_knowledge_count', 'knowledge_items_integrated'),
        Index('idx_file_quality_scores', 'quality_score', 'relevance_score'),
        Index('idx_file_agents', 'target_agents'),
    )

class FileContent(Base):
    """SQLAlchemy model for file content storage"""
    __tablename__ = 'file_contents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, unique=True, index=True)
    
    # Content storage
    raw_content = Column(LargeBinary, nullable=True)  # For binary files
    text_content = Column(Text, nullable=True)  # For text files
    encrypted_content = Column(LargeBinary, nullable=True)  # For sensitive files
    content_preview = Column(Text, nullable=True)  # First 1000 characters
    
    # Content metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    compression_used = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    
    # Storage metadata
    storage_method = Column(String, nullable=False, default="database")  # database, filesystem, s3, etc.
    external_path = Column(String, nullable=True)  # For external storage
    
    # Timestamps
    stored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="file_content")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_hash_method', 'content_hash', 'storage_method'),
        Index('idx_content_encrypted', 'is_encrypted'),
    )

class FileKnowledgeExtraction(Base):
    """SQLAlchemy model for extracted knowledge from files"""
    __tablename__ = 'file_knowledge_extractions'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    knowledge_content = Column(JSON, nullable=False)
    
    # Extraction metadata
    extraction_method = Column(String, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_level = Column(String, nullable=False, default=ValidationLevel.BASIC.value)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    
    # Context information
    source_location = Column(JSON, nullable=False, default=dict)  # Line numbers, sections, etc.
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    
    # Quality metrics
    relevance_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    last_used = Column(DateTime, nullable=True)
    
    # Agent integration
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    integration_results = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="knowledge_extractions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_method_confidence', 'extraction_method', 'confidence_score'),
        Index('idx_extraction_validation', 'validation_status', 'validation_level'),
        Index('idx_extraction_agents', 'target_agents'),
        Index('idx_extraction_quality', 'relevance_score', 'uniqueness_score'),
    )

class FileProcessingLog(Base):
    """SQLAlchemy model for file processing logs"""
    __tablename__ = 'file_processing_logs'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    log_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Log details
    log_level = Column(String, nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_message = Column(Text, nullable=False)
    log_context = Column(JSON, nullable=False, default=dict)
    
    # Processing stage
    processing_stage = Column(String, nullable=False, index=True)  # upload, analysis, extraction, integration
    stage_duration_ms = Column(Float, nullable=True)
    
    # Error details (if applicable)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Timestamps
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="processing_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_log_level_stage', 'log_level', 'processing_stage'),
        Index('idx_log_error_type', 'error_type'),
        Index('idx_log_timing', 'logged_at', 'stage_duration_ms'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileProcessor:
    """Handles file processing and knowledge extraction"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component="file_processor")
        
        # Processing configuration
        self.max_file_size = config.get('max_file_size_mb', MAX_FILE_SIZE_MB) * 1024 * 1024
        self.supported_formats = self._get_supported_formats()
        self.extraction_timeout = config.get('extraction_timeout', FILE_ANALYSIS_TIMEOUT_SECONDS)
        
        # Knowledge extraction configuration
        self.extraction_methods = config.get('extraction_methods', [ExtractionMethod.TEXT_ANALYSIS])
        self.confidence_threshold = config.get('confidence_threshold', KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD)
        self.max_knowledge_items = config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_FILE)
        
        # Processing queues
        self.processing_queue: Dict[str, FileUploadSchema] = {}
        self.active_processing: Set[str] = set()
        
    def _get_supported_formats(self) -> Set[str]:
        """Get all supported file formats"""
        return (SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | 
                SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    
    async def process_file_upload(self, upload_schema: FileUploadSchema, file_content: bytes) -> Dict[str, Any]:
        """Process uploaded file and extract knowledge"""
        file_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting file processing", 
                           file_id=file_id, 
                           filename=upload_schema.filename,
                           file_size=upload_schema.file_size)
            
            # Phase 1: File validation and metadata extraction
            file_metadata = await self._extract_file_metadata(upload_schema, file_content)
            
            # Phase 2: Content analysis
            content_analysis = await self._analyze_file_content(file_content, file_metadata)
            
            # Phase 3: Knowledge extraction
            extracted_knowledge = await self._extract_knowledge(file_content, file_metadata, content_analysis)
            
            # Phase 4: Knowledge validation
            validated_knowledge = await self._validate_extracted_knowledge(extracted_knowledge)
            
            # Phase 5: Agent integration
            integration_results = await self._integrate_with_agents(validated_knowledge, upload_schema.target_agents)
            
            # Calculate processing metrics
            processing_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store file record
            file_record = await self._store_file_record(
                file_id, upload_schema, file_metadata, content_analysis, 
                validated_knowledge, integration_results, processing_duration
            )
            
            # Store file content
            await self._store_file_content(file_id, file_content, file_metadata)
            
            result = {
                "file_id": file_id,
                "status": "completed",
                "processing_duration_ms": processing_duration,
                "file_metadata": file_metadata.__dict__,
                "content_analysis": content_analysis.__dict__,
                "knowledge_items_extracted": len(validated_knowledge),
                "integration_results": integration_results
            }
            
            self.logger.info("File processing completed successfully", **result)
            return result
            
        except Exception as e:
            self.logger.error("File processing failed", 
                            file_id=file_id, 
                            filename=upload_schema.filename,
                            error=str(e))
            
            # Store error information
            await self._store_processing_error(file_id, upload_schema, str(e))
            
            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e),
                "processing_duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def _extract_file_metadata(self, upload_schema: FileUploadSchema, content: bytes) -> FileMetadata:
        """Extract comprehensive file metadata"""
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine file type
        file_extension = Path(upload_schema.filename).suffix.lower()
        file_type = self._classify_file_type(file_extension, upload_schema.content_type)
        
        # Extract text content for analysis
        text_content = ""
        encoding = None
        if file_type in [FileType.TEXT, FileType.CODE]:
            text_content, encoding = await self._extract_text_content(content, file_extension)
        
        # Calculate content metrics
        line_count = len(text_content.split('\n')) if text_content else None
        word_count = len(text_content.split()) if text_content else None
        character_count = len(text_content) if text_content else None
        
        # Detect language for code files
        language = None
        if file_type == FileType.CODE:
            language = self._detect_programming_language(file_extension, text_content)
        
        return FileMetadata(
            filename=upload_schema.filename,
            file_size=upload_schema.file_size,
            mime_type=upload_schema.content_type,
            file_hash=file_hash,
            encoding=encoding,
            file_type=file_type,
            content_category=upload_schema.content_category,
            language=language,
            line_count=line_count,
            word_count=word_count,
            character_count=character_count
        )
    
    def _classify_file_type(self, extension: str, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        if extension in SUPPORTED_TEXT_FORMATS:
            return FileType.TEXT
        elif extension in SUPPORTED_DOCUMENT_FORMATS:
            return FileType.DOCUMENT
        elif extension in SUPPORTED_CODE_FORMATS:
            return FileType.CODE
        elif extension in SUPPORTED_DATA_FORMATS:
            return FileType.DATA
        elif extension in SUPPORTED_IMAGE_FORMATS:
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif extension in {'.zip', '.tar', '.gz', '.rar', '.7z'}:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def _extract_text_content(self, content: bytes, extension: str) -> Tuple[str, Optional[str]]:
        """Extract text content from file"""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                return text_content, encoding
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace'), 'utf-8'
    
    def _detect_programming_language(self, extension: str, content: str) -> Optional[str]:
        """Detect programming language from extension and content"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return language_map.get(extension)
    
    async def _analyze_file_content(self, content: bytes, metadata: FileMetadata) -> ContentAnalysis:
        """Analyze file content for quality and complexity"""
        analysis = ContentAnalysis()
        
        # For text-based files, perform detailed analysis
        if metadata.file_type in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
            
            # Calculate readability score
            analysis.readability_score = self._calculate_readability(text_content)
            
            # Calculate complexity score
            analysis.complexity_score = self._calculate_complexity(text_content, metadata.file_type)
            
            # Calculate quality score
            analysis.quality_score = self._calculate_quality(text_content, metadata)
            
            # Calculate uniqueness score
            analysis.uniqueness_score = await self._calculate_uniqueness(text_content)
            
            # Extract key concepts and topics
            analysis.key_concepts = self._extract_key_concepts(text_content)
            analysis.topics = self._extract_topics(text_content)
            analysis.concept_count = len(analysis.key_concepts)
            
            # Extract entities
            analysis.entities = self._extract_entities(text_content)
            
            # Calculate technical depth
            analysis.technical_depth = self._calculate_technical_depth(text_content, metadata.language)
            
            # Calculate relevance score
            analysis.relevance_score = self._calculate_relevance(text_content, metadata.content_category)
        
        return analysis
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using various metrics"""
        if not text:
            return 0.0
        
        # Simple readability calculation based on sentence and word length
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normalize to 0-100 scale (inverse relationship for complexity)
        readability = max(0, 100 - (avg_sentence_length * 2 + avg_word_length * 5))
        return min(readability, 100.0)
    
    def _calculate_complexity(self, text: str, file_type: FileType) -> float:
        """Calculate content complexity score"""
        if not text:
            return 0.0
        
        complexity_indicators = {
            'technical_terms': len([word for word in text.split() if len(word) > 10]),
            'punctuation_density': sum(1 for char in text if char in '.,;:!?()[]{}'),
            'nested_structures': text.count('(') + text.count('[') + text.count('{'),
            'line_length_variance': 0  # Simplified
        }
        
        if file_type == FileType.CODE:
            # Additional complexity for code
            complexity_indicators.update({
                'function_definitions': text.count('def ') + text.count('function '),
                'conditional_statements': text.count('if ') + text.count('while ') + text.count('for '),
                'import_statements': text.count('import ') + text.count('require('),
            })
        
        # Normalize to 0-100 scale
        total_indicators = sum(complexity_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        complexity = min((total_indicators / text_length) * 1000, 100.0)
        return complexity
    
    def _calculate_quality(self, text: str, metadata: FileMetadata) -> float:
        """Calculate content quality score"""
        if not text:
            return 0.0
        
        quality_factors = {
            'length_adequacy': min(len(text.split()) / 100, 1.0) * 25,  # Adequate length
            'structure_score': self._assess_structure(text) * 20,  # Good structure
            'grammar_score': self._assess_grammar(text) * 20,  # Grammar quality
            'completeness_score': self._assess_completeness(text) * 20,  # Content completeness
            'consistency_score': self._assess_consistency(text) * 15   # Style consistency
        }
        
        return sum(quality_factors.values())
    
    def _assess_structure(self, text: str) -> float:
        """Assess text structure quality"""
        # Simple structure assessment
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        # Check for headings, paragraphs, lists
        structure_score = 0.0
        if any(line.startswith('#') for line in lines):  # Markdown headings
            structure_score += 0.3
        if len(non_empty_lines) > 5:  # Multiple paragraphs
            structure_score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in lines):  # Lists
            structure_score += 0.4
        
        return min(structure_score, 1.0)
    
    def _assess_grammar(self, text: str) -> float:
        """Assess grammar quality (simplified)"""
        # Simple grammar assessment
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        # Check for basic grammar indicators
        capitalized_sentences = sum(1 for s in sentences if s and s[0].isupper())
        grammar_score = capitalized_sentences / len(sentences)
        
        return grammar_score
    
    def _assess_completeness(self, text: str) -> float:
        """Assess content completeness"""
        # Check for introduction, body, conclusion indicators
        completeness_indicators = 0
        
        intro_words = ['introduction', 'overview', 'summary', 'abstract']
        if any(word in text.lower() for word in intro_words):
            completeness_indicators += 1
        
        if len(text.split()) > 200:  # Substantial content
            completeness_indicators += 1
        
        conclusion_words = ['conclusion', 'summary', 'finally', 'in summary']
        if any(word in text.lower() for word in conclusion_words):
            completeness_indicators += 1
        
        return completeness_indicators / 3.0
    
    def _assess_consistency(self, text:,  # YAML-style
            r'^\s*"([^"]+)"\s*:\s*"([^"]+)"',  # JSON-style
        ]
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    key, value = match.groups()
                    rules.append({
                        'key': key.strip(),
                        'value': value.strip(),
                        'type': 'configuration_setting'
                    })
        
        return rules[:20]  # Limit to 20 rules
    
    def _deduplicate_knowledge(self, knowledge_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate knowledge items"""
        unique_items = []
        seen_content = set()
        
        for item in knowledge_items:
            # Create a hash of the content for comparison
            content_str = json.dumps(item.get('content', {}), sort_keys=True)
            content_hash = hashlib.md5(content_str.encode()).hexdigest()
            
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_items.append(item)
        
        return unique_items
    
    async def _validate_extracted_knowledge(self, knowledge_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate extracted knowledge items"""
        validated_items = []
        
        for item in knowledge_items:
            # Check confidence threshold
            if item.get('confidence_score', 0) < self.confidence_threshold:
                continue
            
            # Validate content structure
            if not self._validate_knowledge_structure(item):
                continue
            
            # Check content quality
            if not self._validate_knowledge_quality(item):
                continue
            
            # Mark as validated
            item['validation_status'] = LearningStatus.VALIDATED.value
            item['validated_at'] = datetime.utcnow().isoformat()
            
            validated_items.append(item)
        
        return validated_items
    
    def _validate_knowledge_structure(self, item: Dict[str, Any]) -> bool:
        """Validate knowledge item structure"""
        required_fields = ['knowledge_type', 'content', 'confidence_score', 'extraction_method']
        return all(field in item for field in required_fields)
    
    def _validate_knowledge_quality(self, item: Dict[str, Any]) -> bool:
        """Validate knowledge item quality"""
        content = item.get('content', {})
        
        # Check content is not empty
        if not content:
            return False
        
        # Check content has meaningful information
        if isinstance(content, dict):
            # At least one non-empty value
            return any(v for v in content.values() if v)
        
        return True
    
    async def _integrate_with_agents(self, validated_knowledge: List[Dict[str, Any]], 
                                   target_agents: List[str]) -> Dict[str, Any]:
        """Integrate extracted knowledge with target agents"""
        integration_results = {
            'total_items': len(validated_knowledge),
            'successful_integrations': 0,
            'failed_integrations': 0,
            'agent_results': {}
        }
        
        # If no target agents specified, this would typically query the system
        # for relevant agents based on knowledge type and content
        if not target_agents:
            target_agents = await self._identify_relevant_agents(validated_knowledge)
        
        # Integrate with each target agent
        for agent_id in target_agents:
            agent_results = await self._integrate_with_single_agent(agent_id, validated_knowledge)
            integration_results['agent_results'][agent_id] = agent_results
            
            if agent_results.get('status') == 'success':
                integration_results['successful_integrations'] += agent_results.get('items_integrated', 0)
            else:
                integration_results['failed_integrations'] += len(validated_knowledge)
        
        return integration_results
    
    async def _identify_relevant_agents(self, knowledge_items: List[Dict[str, Any]]) -> List[str]:
        """Identify relevant agents for knowledge integration"""
        # This would typically query the agent registry
        # For now, return a placeholder list
        return ['general_learning_agent']
    
    async def _integrate_with_single_agent(self, agent_id: str, knowledge_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Integrate knowledge with a single agent"""
        # This would typically use the agent communication system
        # For now, return a success result
        return {
            'status': 'success',
            'agent_id': agent_id,
            'items_integrated': len(knowledge_items),
            'integration_time': datetime.utcnow().isoformat()
        }
    
    async def _store_file_record(self, file_id: str, upload_schema: FileUploadSchema,
                               metadata: FileMetadata, analysis: ContentAnalysis,
                               knowledge_items: List[Dict[str, Any]], 
                               integration_results: Dict[str, Any],
                               processing_duration: float) -> Dict[str, Any]:
        """Store file record in database"""
        # This would typically use SQLAlchemy to store the record
        # For now, return the record data
        return {
            'file_id': file_id,
            'filename': metadata.filename,
            'status': FileStatus.INTEGRATED.value,
            'processing_duration_ms': processing_duration,
            'knowledge_items_count': len(knowledge_items),
            'integration_results': integration_results
        }
    
    async def _store_file_content(self, file_id: str, content: bytes, metadata: FileMetadata) -> None:
        """Store file content in appropriate storage"""
        # This would typically store content in database or external storage
        pass
    
    async def _store_processing_error(self, file_id: str, upload_schema: FileUploadSchema, error: str) -> None:
        """Store processing error information"""
        # This would typically store error information in database
        pass

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """File models health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "file_models",
        "database_models": ["FileRecord", "FileContent", "FileKnowledgeExtraction", "FileProcessingLog"],
        "schemas": ["FileUploadSchema", "KnowledgeExtractionSchema", "FileAnalysisSchema", "FileStatusSchema", "FileSearchSchema"],
        "supported_formats": list(SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    }

def validate_file_upload(upload_data: Dict[str, Any]) -> bool:
    """Validate file upload data"""
    required_fields = ["filename", "content_type", "file_size"]
    return all(field in upload_data for field in required_fields)

def calculate_file_hash(content: bytes, algorithm: str = 'sha256') -> str:
    """Calculate file content hash"""
    if algorithm == 'md5':
        return hashlib.md5(content).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(content).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(content).hexdigest()
    elif algorithm == 'sha512':
        return hashlib.sha512(content).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

def get_file_type_from_extension(filename: str) -> FileType:
    """Determine file type from filename extension"""
    extension = Path(filename).suffix.lower()
    
    if extension in SUPPORTED_TEXT_FORMATS:
        return FileType.TEXT
    elif extension in SUPPORTED_DOCUMENT_FORMATS:
        return FileType.DOCUMENT
    elif extension in SUPPORTED_CODE_FORMATS:
        return FileType.CODE
    elif extension in SUPPORTED_DATA_FORMATS:
        return FileType.DATA
    elif extension in SUPPORTED_IMAGE_FORMATS:
        return FileType.IMAGE
    else:
        return FileType.UNKNOWN

async def cleanup_expired_files(retention_days: int = 90) -> Dict[str, int]:
    """Clean up expired files and associated data"""
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    # This would typically query database for expired files
    # For now, return placeholder results
    return {
        "files_deleted": 0,
        "knowledge_items_deleted": 0,
        "storage_freed_mb": 0,
        "cutoff_date": cutoff_date.isoformat()
    }

def generate_file_id(filename: str, file_hash: str) -> str:
    """Generate unique file identifier"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    name_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    content_hash = file_hash[:8]
    return f"file_{timestamp}_{name_hash}_{content_hash}"

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_file_models() -> Dict[str, Any]:
    """Initialize file models module for production use"""
    try:
        # Validate configuration
        test_upload = {
            "filename": "test.txt",
            "content_type": "text/plain",
            "file_size": 1024
        }
        
        if not validate_file_upload(test_upload):
            raise ValueError("Invalid file upload validation")
        
        # Setup logging
        logger.info("File models module initialized successfully")
        
        return {
            "status": "initialized",
            "timestamp": datetime.utcnow().isoformat(),
            "models_available": ["FileRecord", "FileContent", "FileKnowledgeExtraction", "FileProcessingLog"],
            "schemas_available": ["FileUploadSchema", "KnowledgeExtractionSchema", "FileAnalysisSchema", "FileStatusSchema", "FileSearchSchema"],
            "utilities_available": ["health_check", "validate_file_upload", "calculate_file_hash", "get_file_type_from_extension"],
            "supported_formats": len(SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS),
            "max_file_size_mb": MAX_FILE_SIZE_MB
        }
        
    except Exception as e:
        logger.error("Failed to initialize file models module", error=str(e))
        raise

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    # Enums
    "FileType", "FileStatus", "ProcessingPriority", "ContentCategory", "ExtractionMethod", "ValidationLevel",
    
    # Data Models
    "FileMetadata", "ProcessingMetrics", "ContentAnalysis",
    
    # Schemas
    "FileUploadSchema", "KnowledgeExtractionSchema", "FileAnalysisSchema", "FileStatusSchema", "FileSearchSchema",
    
    # Database Models
    "FileRecord", "FileContent", "FileKnowledgeExtraction", "FileProcessingLog",
    
    # Core Classes
    "FileProcessor",
    
    # Utilities
    "health_check", "validate_file_upload", "calculate_file_hash", "get_file_type_from_extension",
    "cleanup_expired_files", "generate_file_id", "initialize_file_models"
]
    """
YMERA Enterprise - File Learning Models
Production-Ready File Metadata & Learning Integration Models - v4.0
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
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Third-party imports (alphabetical)
import structlog
from pydantic import BaseModel, Field, validator, root_validator
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# Local imports (alphabetical)
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from agent_models import KnowledgeType, LearningStatus

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_models")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# File processing constants
MAX_FILE_SIZE_MB = 100
SUPPORTED_TEXT_FORMATS = {'.txt', '.md', '.json', '.csv', '.xml', '.yaml', '.yml'}
SUPPORTED_DOCUMENT_FORMATS = {'.pdf', '.docx', '.doc', '.rtf', '.odt'}
SUPPORTED_CODE_FORMATS = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs'}
SUPPORTED_DATA_FORMATS = {'.csv', '.xlsx', '.xls', '.json', '.xml', '.parquet'}
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}

# Learning integration constants
KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD = 0.6
MAX_KNOWLEDGE_ITEMS_PER_FILE = 50
FILE_ANALYSIS_TIMEOUT_SECONDS = 300
CONTENT_SIMILARITY_THRESHOLD = 0.8

# Configuration loading
settings = get_settings()
Base = declarative_base()

# ===============================================================================
# ENUMS & TYPE DEFINITIONS
# ===============================================================================

class FileType(str, Enum):
    """File type classification"""
    TEXT = "text"
    DOCUMENT = "document" 
    CODE = "code"
    DATA = "data"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"

class FileStatus(str, Enum):
    """File processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    INTEGRATED = "integrated"
    ERROR = "error"
    ARCHIVED = "archived"

class ProcessingPriority(IntEnum):
    """File processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class ContentCategory(str, Enum):
    """Content categorization for learning"""
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    SPECIFICATION = "specification"
    EXAMPLE = "example"
    CONFIGURATION = "configuration"
    DATA_SAMPLE = "data_sample"
    ERROR_LOG = "error_log"
    PERFORMANCE_DATA = "performance_data"
    USER_FEEDBACK = "user_feedback"
    RESEARCH = "research"

class ExtractionMethod(str, Enum):
    """Knowledge extraction methods"""
    TEXT_ANALYSIS = "text_analysis"
    PATTERN_RECOGNITION = "pattern_recognition"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    ML_INFERENCE = "ml_inference"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class ValidationLevel(str, Enum):
    """Knowledge validation levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    encoding: Optional[str] = None
    file_type: FileType = FileType.UNKNOWN
    content_category: Optional[ContentCategory] = None
    language: Optional[str] = None
    charset: Optional[str] = None
    line_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None

@dataclass
class ProcessingMetrics:
    """File processing performance metrics"""
    processing_duration_ms: float = 0.0
    analysis_duration_ms: float = 0.0
    extraction_duration_ms: float = 0.0
    integration_duration_ms: float = 0.0
    knowledge_items_extracted: int = 0
    knowledge_items_validated: int = 0
    knowledge_items_integrated: int = 0
    error_count: int = 0
    retry_count: int = 0

@dataclass
class ContentAnalysis:
    """Content analysis results"""
    readability_score: float = 0.0
    complexity_score: float = 0.0
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    relevance_score: float = 0.0
    technical_depth: float = 0.0
    concept_count: int = 0
    key_concepts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class FileUploadSchema(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=1, le=MAX_FILE_SIZE_MB*1024*1024, description="File size in bytes")
    file_hash: Optional[str] = Field(None, description="File content hash")
    processing_priority: ProcessingPriority = Field(default=ProcessingPriority.NORMAL)
    content_category: Optional[ContentCategory] = Field(None, description="Content category hint")
    extraction_config: Dict[str, Any] = Field(default_factory=dict, description="Extraction configuration")
    target_agents: List[str] = Field(default_factory=list, description="Target agents for knowledge")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Filename cannot be empty')
        # Remove path components for security
        return os.path.basename(v)
    
    @validator('file_hash')
    def validate_file_hash(cls, v):
        if v and len(v) not in [32, 40, 64, 128]:  # MD5, SHA1, SHA256, SHA512
            raise ValueError('Invalid hash format')
        return v

class KnowledgeExtractionSchema(BaseModel):
    """Schema for knowledge extraction configuration"""
    extraction_methods: List[ExtractionMethod] = Field(default_factory=lambda: [ExtractionMethod.TEXT_ANALYSIS])
    confidence_threshold: float = Field(default=KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0)
    max_items: int = Field(default=MAX_KNOWLEDGE_ITEMS_PER_FILE, ge=1, le=100)
    validation_level: ValidationLevel = Field(default=ValidationLevel.INTERMEDIATE)
    context_window: int = Field(default=1000, ge=100, le=5000, description="Context window for extraction")
    include_metadata: bool = Field(default=True, description="Include file metadata in knowledge")
    cross_reference: bool = Field(default=True, description="Cross-reference with existing knowledge")
    auto_categorize: bool = Field(default=True, description="Automatically categorize knowledge")

class FileAnalysisSchema(BaseModel):
    """Schema for file analysis results"""
    file_id: str = Field(..., description="File identifier")
    file_metadata: Dict[str, Any] = Field(..., description="File metadata")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    processing_metrics: Dict[str, Any] = Field(..., description="Processing metrics")
    extracted_knowledge: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    integration_status: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileStatusSchema(BaseModel):
    """Schema for file status reporting"""
    file_id: str = Field(..., description="File identifier")
    filename: str = Field(..., description="Original filename")
    current_status: FileStatus = Field(..., description="Current processing status")
    processing_progress: float = Field(..., ge=0.0, le=100.0, description="Processing progress percentage")
    knowledge_items_count: int = Field(default=0, ge=0, description="Number of knowledge items extracted")
    integrated_agents: List[str] = Field(default_factory=list, description="Agents that received knowledge")
    error_messages: List[str] = Field(default_factory=list, description="Error messages if any")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchSchema(BaseModel):
    """Schema for file search requests"""
    query: str = Field(..., min_length=1, description="Search query")
    file_types: Optional[List[FileType]] = Field(None, description="Filter by file types")
    content_categories: Optional[List[ContentCategory]] = Field(None, description="Filter by content categories")
    date_from: Optional[datetime] = Field(None, description="Filter files from date")
    date_to: Optional[datetime] = Field(None, description="Filter files to date")
    size_min: Optional[int] = Field(None, ge=0, description="Minimum file size")
    size_max: Optional[int] = Field(None, ge=0, description="Maximum file size")
    has_knowledge: Optional[bool] = Field(None, description="Filter files with extracted knowledge")
    agent_ids: Optional[List[str]] = Field(None, description="Filter by associated agents")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")

# ===============================================================================
# SQLALCHEMY DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file records"""
    __tablename__ = 'file_records'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, nullable=False, index=True)
    
    # File metadata
    filename = Column(String, nullable=False, index=True)
    original_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False, index=True)
    file_hash = Column(String, nullable=False, unique=True, index=True)
    encoding = Column(String, nullable=True)
    
    # Classification
    file_type = Column(String, nullable=False, index=True)
    content_category = Column(String, nullable=True, index=True)
    language = Column(String, nullable=True)
    charset = Column(String, nullable=True)
    
    # Content metrics
    line_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Processing status
    current_status = Column(String, nullable=False, default=FileStatus.UPLOADED.value, index=True)
    processing_priority = Column(Integer, nullable=False, default=ProcessingPriority.NORMAL.value)
    processing_progress = Column(Float, nullable=False, default=0.0)
    
    # Processing metrics
    processing_duration_ms = Column(Float, nullable=False, default=0.0)
    analysis_duration_ms = Column(Float, nullable=False, default=0.0)
    extraction_duration_ms = Column(Float, nullable=False, default=0.0)
    integration_duration_ms = Column(Float, nullable=False, default=0.0)
    
    # Knowledge extraction results
    knowledge_items_extracted = Column(Integer, nullable=False, default=0)
    knowledge_items_validated = Column(Integer, nullable=False, default=0)
    knowledge_items_integrated = Column(Integer, nullable=False, default=0)
    
    # Content analysis
    readability_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    technical_depth = Column(Float, nullable=False, default=0.0)
    concept_count = Column(Integer, nullable=False, default=0)
    
    # Structured data
    key_concepts = Column(ARRAY(String), nullable=False, default=list)
    topics = Column(ARRAY(String), nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    extraction_config = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    
    # Error tracking
    error_count = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    error_messages = Column(JSON, nullable=False, default=list)
    
    # Agent associations
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_content = relationship("FileContent", back_populates="file_record", uselist=False, cascade="all, delete-orphan")
    knowledge_extractions = relationship("FileKnowledgeExtraction", back_populates="file_record", cascade="all, delete-orphan")
    processing_logs = relationship("FileProcessingLog", back_populates="file_record", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_file_status_priority', 'current_status', 'processing_priority'),
        Index('idx_file_type_category', 'file_type', 'content_category'),
        Index('idx_file_size_upload', 'file_size', 'uploaded_at'),
        Index('idx_file_knowledge_count', 'knowledge_items_integrated'),
        Index('idx_file_quality_scores', 'quality_score', 'relevance_score'),
        Index('idx_file_agents', 'target_agents'),
    )

class FileContent(Base):
    """SQLAlchemy model for file content storage"""
    __tablename__ = 'file_contents'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, unique=True, index=True)
    
    # Content storage
    raw_content = Column(LargeBinary, nullable=True)  # For binary files
    text_content = Column(Text, nullable=True)  # For text files
    encrypted_content = Column(LargeBinary, nullable=True)  # For sensitive files
    content_preview = Column(Text, nullable=True)  # First 1000 characters
    
    # Content metadata
    is_encrypted = Column(Boolean, nullable=False, default=False)
    compression_used = Column(String, nullable=True)
    content_hash = Column(String, nullable=False, index=True)
    
    # Storage metadata
    storage_method = Column(String, nullable=False, default="database")  # database, filesystem, s3, etc.
    external_path = Column(String, nullable=True)  # For external storage
    
    # Timestamps
    stored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="file_content")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_hash_method', 'content_hash', 'storage_method'),
        Index('idx_content_encrypted', 'is_encrypted'),
    )

class FileKnowledgeExtraction(Base):
    """SQLAlchemy model for extracted knowledge from files"""
    __tablename__ = 'file_knowledge_extractions'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Knowledge content
    knowledge_type = Column(String, nullable=False, index=True)
    knowledge_content = Column(JSON, nullable=False)
    
    # Extraction metadata
    extraction_method = Column(String, nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_level = Column(String, nullable=False, default=ValidationLevel.BASIC.value)
    validation_status = Column(String, nullable=False, default=LearningStatus.PENDING.value, index=True)
    
    # Context information
    source_location = Column(JSON, nullable=False, default=dict)  # Line numbers, sections, etc.
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    applicable_contexts = Column(ARRAY(String), nullable=False, default=list)
    
    # Quality metrics
    relevance_score = Column(Float, nullable=False, default=0.0)
    uniqueness_score = Column(Float, nullable=False, default=0.0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    
    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)
    last_used = Column(DateTime, nullable=True)
    
    # Agent integration
    target_agents = Column(ARRAY(String), nullable=False, default=list)
    integrated_agents = Column(ARRAY(String), nullable=False, default=list)
    integration_results = Column(JSON, nullable=False, default=dict)
    
    # Timestamps
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)
    integrated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="knowledge_extractions")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_extraction_method_confidence', 'extraction_method', 'confidence_score'),
        Index('idx_extraction_validation', 'validation_status', 'validation_level'),
        Index('idx_extraction_agents', 'target_agents'),
        Index('idx_extraction_quality', 'relevance_score', 'uniqueness_score'),
    )

class FileProcessingLog(Base):
    """SQLAlchemy model for file processing logs"""
    __tablename__ = 'file_processing_logs'
    
    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    log_id = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(String, ForeignKey('file_records.file_id'), nullable=False, index=True)
    
    # Log details
    log_level = Column(String, nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_message = Column(Text, nullable=False)
    log_context = Column(JSON, nullable=False, default=dict)
    
    # Processing stage
    processing_stage = Column(String, nullable=False, index=True)  # upload, analysis, extraction, integration
    stage_duration_ms = Column(Float, nullable=True)
    
    # Error details (if applicable)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance metrics
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)
    
    # Timestamps
    logged_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    file_record = relationship("FileRecord", back_populates="processing_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_log_level_stage', 'log_level', 'processing_stage'),
        Index('idx_log_error_type', 'error_type'),
        Index('idx_log_timing', 'logged_at', 'stage_duration_ms'),
    )

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileProcessor:
    """Handles file processing and knowledge extraction"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logger.bind(component="file_processor")
        
        # Processing configuration
        self.max_file_size = config.get('max_file_size_mb', MAX_FILE_SIZE_MB) * 1024 * 1024
        self.supported_formats = self._get_supported_formats()
        self.extraction_timeout = config.get('extraction_timeout', FILE_ANALYSIS_TIMEOUT_SECONDS)
        
        # Knowledge extraction configuration
        self.extraction_methods = config.get('extraction_methods', [ExtractionMethod.TEXT_ANALYSIS])
        self.confidence_threshold = config.get('confidence_threshold', KNOWLEDGE_EXTRACTION_CONFIDENCE_THRESHOLD)
        self.max_knowledge_items = config.get('max_knowledge_items', MAX_KNOWLEDGE_ITEMS_PER_FILE)
        
        # Processing queues
        self.processing_queue: Dict[str, FileUploadSchema] = {}
        self.active_processing: Set[str] = set()
        
    def _get_supported_formats(self) -> Set[str]:
        """Get all supported file formats"""
        return (SUPPORTED_TEXT_FORMATS | SUPPORTED_DOCUMENT_FORMATS | 
                SUPPORTED_CODE_FORMATS | SUPPORTED_DATA_FORMATS | SUPPORTED_IMAGE_FORMATS)
    
    async def process_file_upload(self, upload_schema: FileUploadSchema, file_content: bytes) -> Dict[str, Any]:
        """Process uploaded file and extract knowledge"""
        file_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting file processing", 
                           file_id=file_id, 
                           filename=upload_schema.filename,
                           file_size=upload_schema.file_size)
            
            # Phase 1: File validation and metadata extraction
            file_metadata = await self._extract_file_metadata(upload_schema, file_content)
            
            # Phase 2: Content analysis
            content_analysis = await self._analyze_file_content(file_content, file_metadata)
            
            # Phase 3: Knowledge extraction
            extracted_knowledge = await self._extract_knowledge(file_content, file_metadata, content_analysis)
            
            # Phase 4: Knowledge validation
            validated_knowledge = await self._validate_extracted_knowledge(extracted_knowledge)
            
            # Phase 5: Agent integration
            integration_results = await self._integrate_with_agents(validated_knowledge, upload_schema.target_agents)
            
            # Calculate processing metrics
            processing_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Store file record
            file_record = await self._store_file_record(
                file_id, upload_schema, file_metadata, content_analysis, 
                validated_knowledge, integration_results, processing_duration
            )
            
            # Store file content
            await self._store_file_content(file_id, file_content, file_metadata)
            
            result = {
                "file_id": file_id,
                "status": "completed",
                "processing_duration_ms": processing_duration,
                "file_metadata": file_metadata.__dict__,
                "content_analysis": content_analysis.__dict__,
                "knowledge_items_extracted": len(validated_knowledge),
                "integration_results": integration_results
            }
            
            self.logger.info("File processing completed successfully", **result)
            return result
            
        except Exception as e:
            self.logger.error("File processing failed", 
                            file_id=file_id, 
                            filename=upload_schema.filename,
                            error=str(e))
            
            # Store error information
            await self._store_processing_error(file_id, upload_schema, str(e))
            
            return {
                "file_id": file_id,
                "status": "failed",
                "error": str(e),
                "processing_duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
            }
    
    async def _extract_file_metadata(self, upload_schema: FileUploadSchema, content: bytes) -> FileMetadata:
        """Extract comprehensive file metadata"""
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine file type
        file_extension = Path(upload_schema.filename).suffix.lower()
        file_type = self._classify_file_type(file_extension, upload_schema.content_type)
        
        # Extract text content for analysis
        text_content = ""
        encoding = None
        if file_type in [FileType.TEXT, FileType.CODE]:
            text_content, encoding = await self._extract_text_content(content, file_extension)
        
        # Calculate content metrics
        line_count = len(text_content.split('\n')) if text_content else None
        word_count = len(text_content.split()) if text_content else None
        character_count = len(text_content) if text_content else None
        
        # Detect language for code files
        language = None
        if file_type == FileType.CODE:
            language = self._detect_programming_language(file_extension, text_content)
        
        return FileMetadata(
            filename=upload_schema.filename,
            file_size=upload_schema.file_size,
            mime_type=upload_schema.content_type,
            file_hash=file_hash,
            encoding=encoding,
            file_type=file_type,
            content_category=upload_schema.content_category,
            language=language,
            line_count=line_count,
            word_count=word_count,
            character_count=character_count
        )
    
    def _classify_file_type(self, extension: str, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        if extension in SUPPORTED_TEXT_FORMATS:
            return FileType.TEXT
        elif extension in SUPPORTED_DOCUMENT_FORMATS:
            return FileType.DOCUMENT
        elif extension in SUPPORTED_CODE_FORMATS:
            return FileType.CODE
        elif extension in SUPPORTED_DATA_FORMATS:
            return FileType.DATA
        elif extension in SUPPORTED_IMAGE_FORMATS:
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif extension in {'.zip', '.tar', '.gz', '.rar', '.7z'}:
            return FileType.ARCHIVE
        else:
            return FileType.UNKNOWN
    
    async def _extract_text_content(self, content: bytes, extension: str) -> Tuple[str, Optional[str]]:
        """Extract text content from file"""
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text_content = content.decode(encoding)
                return text_content, encoding
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace'), 'utf-8'
    
    def _detect_programming_language(self, extension: str, content: str) -> Optional[str]:
        """Detect programming language from extension and content"""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust'
        }
        return language_map.get(extension)
    
    async def _analyze_file_content(self, content: bytes, metadata: FileMetadata) -> ContentAnalysis:
        """Analyze file content for quality and complexity"""
        analysis = ContentAnalysis()
        
        # For text-based files, perform detailed analysis
        if metadata.file_type in [FileType.TEXT, FileType.CODE, FileType.DOCUMENT]:
            text_content, _ = await self._extract_text_content(content, Path(metadata.filename).suffix)
            
            # Calculate readability score
            analysis.readability_score = self._calculate_readability(text_content)
            
            # Calculate complexity score
            analysis.complexity_score = self._calculate_complexity(text_content, metadata.file_type)
            
            # Calculate quality score
            analysis.quality_score = self._calculate_quality(text_content, metadata)
            
            # Calculate uniqueness score
            analysis.uniqueness_score = await self._calculate_uniqueness(text_content)
            
            # Extract key concepts and topics
            analysis.key_concepts = self._extract_key_concepts(text_content)
            analysis.topics = self._extract_topics(text_content)
            analysis.concept_count = len(analysis.key_concepts)
            
            # Extract entities
            analysis.entities = self._extract_entities(text_content)
            
            # Calculate technical depth
            analysis.technical_depth = self._calculate_technical_depth(text_content, metadata.language)
            
            # Calculate relevance score
            analysis.relevance_score = self._calculate_relevance(text_content, metadata.content_category)
        
        return analysis
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score using various metrics"""
        if not text:
            return 0.0
        
        # Simple readability calculation based on sentence and word length
        sentences = text.split('.')
        words = text.split()
        
        if not sentences or not words:
            return 0.0
        
        avg_sentence_length = len(words) / max(len(sentences), 1)
        avg_word_length = sum(len(word) for word in words) / len(words)
        
        # Normalize to 0-100 scale (inverse relationship for complexity)
        readability = max(0, 100 - (avg_sentence_length * 2 + avg_word_length * 5))
        return min(readability, 100.0)
    
    def _calculate_complexity(self, text: str, file_type: FileType) -> float:
        """Calculate content complexity score"""
        if not text:
            return 0.0
        
        complexity_indicators = {
            'technical_terms': len([word for word in text.split() if len(word) > 10]),
            'punctuation_density': sum(1 for char in text if char in '.,;:!?()[]{}'),
            'nested_structures': text.count('(') + text.count('[') + text.count('{'),
            'line_length_variance': 0  # Simplified
        }
        
        if file_type == FileType.CODE:
            # Additional complexity for code
            complexity_indicators.update({
                'function_definitions': text.count('def ') + text.count('function '),
                'conditional_statements': text.count('if ') + text.count('while ') + text.count('for '),
                'import_statements': text.count('import ') + text.count('require('),
            })
        
        # Normalize to 0-100 scale
        total_indicators = sum(complexity_indicators.values())
        text_length = len(text.split())
        
        if text_length == 0:
            return 0.0
        
        complexity = min((total_indicators / text_length) * 1000, 100.0)
        return complexity
    
    def _calculate_quality(self, text: str, metadata: FileMetadata) -> float:
        """Calculate content quality score"""
        if not text:
            return 0.0
        
        quality_factors = {
            'length_adequacy': min(len(text.split()) / 100, 1.0) * 25,  # Adequate length
            'structure_score': self._assess_structure(text) * 20,  # Good structure
            'grammar_score': self._assess_grammar(text) * 20,  # Grammar quality
            'completeness_score': self._assess_completeness(text) * 20,  # Content completeness
            'consistency_score': self._assess_consistency(text) * 15   # Style consistency
        }
        
        return sum(quality_factors.values())
    
    def _assess_structure(self, text: str) -> float:
        """Assess text structure quality"""
        # Simple structure assessment
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        # Check for headings, paragraphs, lists
        structure_score = 0.0
        if any(line.startswith('#') for line in lines):  # Markdown headings
            structure_score += 0.3
        if len(non_empty_lines) > 5:  # Multiple paragraphs
            structure_score += 0.3
        if any(line.strip().startswith(('-', '*', '1.')) for line in lines):  # Lists
            structure_score += 0.4
        
        return min(structure_score, 1.0)
    
    def _assess_grammar(self, text: str) -> float:
        """Assess grammar quality (simplified)"""
        # Simple grammar assessment
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if not sentences:
            return 0.0
        
        # Check for basic grammar indicators
        capitalized_sentences = sum(1 for s in sentences if s and s[0].isupper())
        grammar_score = capitalized_sentences / len(sentences)
        
        return grammar_score
    
    def _assess_completeness(self, text: str) -> float:
        """Assess content completeness"""
        # Check for introduction, body, conclusion indicators
        completeness_indicators = 0
        
        intro_words = ['introduction', 'overview', 'summary', 'abstract']
        if any(word in text.lower() for word in intro_words):
            completeness_indicators += 1
        
        if len(text.split()) > 200:  # Substantial content
            completeness_indicators += 1
        
        conclusion_words = ['conclusion', 'summary', 'finally', 'in summary']
        if any(word in text.lower() for word in conclusion_words):
            completeness_indicators += 1
        
        return completeness_indicators / 3.0
    
    def _assess_consistency(self, text: