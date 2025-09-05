"""
YMERA Enterprise - Enhanced Base Model Classes
Production-Ready Database Base Models with Advanced Features - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Type, TypeVar
from abc import ABC, abstractmethod

# Third-party imports
import structlog
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declared_attr, validates
from sqlalchemy.sql import func

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.models.base")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Model constants
MAX_STRING_LENGTH = 255
MAX_TEXT_LENGTH = 65535
DEFAULT_CACHE_TTL = 3600

# Base model type
BaseModelType = TypeVar('BaseModelType', bound='BaseModel')

# ===============================================================================
# BASE DECLARATIVE MODEL
# ===============================================================================

Base = declarative_base()

# ===============================================================================
# MIXIN CLASSES
# ===============================================================================

class TimestampMixin:
    """Mixin for automatic timestamp management"""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Record creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        doc="Record last update timestamp"
    )


class AuditMixin:
    """Mixin for audit trail functionality"""
    
    created_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="User ID who created the record"
    )
    
    updated_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="User ID who last updated the record"
    )
    
    version = Column(
        Integer,
        default=1,
        nullable=False,
        doc="Record version for optimistic locking"
    )
    
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        doc="Soft delete flag"
    )
    
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Soft delete timestamp"
    )
    
    deleted_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        doc="User ID who deleted the record"
    )


class MetadataMixin:
    """Mixin for flexible metadata storage"""
    
    metadata_json = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Flexible metadata storage as JSONB"
    )
    
    tags = Column(
        JSONB,
        default=list,
        nullable=False,
        doc="Searchable tags array"
    )
    
    @validates('metadata_json')
    def validate_metadata(self, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata JSON structure"""
        if not isinstance(value, dict):
            raise ValueError("Metadata must be a dictionary")
        return value
    
    @validates('tags')
    def validate_tags(self, key: str, value: List[str]) -> List[str]:
        """Validate tags array"""
        if not isinstance(value, list):
            raise ValueError("Tags must be a list")
        
        # Ensure all tags are strings and lowercase
        cleaned_tags = [str(tag).lower().strip() for tag in value if tag]
        return list(set(cleaned_tags))  # Remove duplicates


class CacheMixin:
    """Mixin for caching functionality"""
    
    cache_key = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Cache key for efficient retrieval"
    )
    
    cache_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Cache expiration timestamp"
    )
    
    def generate_cache_key(self) -> str:
        """Generate unique cache key for the record"""
        if hasattr(self, 'id'):
            return f"{self.__class__.__name__.lower()}:{self.id}"
        return f"{self.__class__.__name__.lower()}:{uuid.uuid4()}"
    
    def is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if not self.cache_expires_at:
            return False
        return datetime.utcnow() < self.cache_expires_at
    
    def set_cache_expiry(self, ttl_seconds: int = DEFAULT_CACHE_TTL) -> None:
        """Set cache expiration time"""
        self.cache_expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)


# ===============================================================================
# BASE MODEL CLASS
# ===============================================================================

class BaseModel(Base, TimestampMixin, AuditMixin, MetadataMixin, CacheMixin):
    """
    Enhanced base model with comprehensive functionality.
    
    Features:
    - UUID primary keys
    - Automatic timestamps
    - Audit trail
    - Soft delete
    - Flexible metadata
    - Caching support
    - Validation
    - Serialization
    """
    
    __abstract__ = True
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        doc="Unique identifier"
    )
    
    # Common fields
    name = Column(
        String(MAX_STRING_LENGTH),
        nullable=False,
        index=True,
        doc="Human-readable name"
    )
    
    description = Column(
        Text,
        nullable=True,
        doc="Detailed description"
    )
    
    status = Column(
        String(50),
        nullable=False,
        default="active",
        index=True,
        doc="Current status"
    )
    
    # Table name generation
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name"""
        # Convert CamelCase to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        return name
    
    # =============================================================================== 
    # VALIDATION METHODS
    # ===============================================================================
    
    @validates('name')
    def validate_name(self, key: str, value: str) -> str:
        """Validate name field"""
        if not value or not value.strip():
            raise ValueError("Name cannot be empty")
        
        if len(value.strip()) > MAX_STRING_LENGTH:
            raise ValueError(f"Name cannot exceed {MAX_STRING_LENGTH} characters")
        
        return value.strip()
    
    @validates('status')
    def validate_status(self, key: str, value: str) -> str:
        """Validate status field"""
        valid_statuses = {
            "active", "inactive", "pending", "processing", 
            "completed", "failed", "cancelled", "archived"
        }
        
        if value not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        
        return value
    
    # ===============================================================================
    # LIFECYCLE METHODS
    # ===============================================================================
    
    def __init__(self, **kwargs):
        """Initialize model with enhanced features"""
        super().__init__(**kwargs)
        
        # Generate cache key
        if not self.cache_key:
            self.cache_key = self.generate_cache_key()
        
        # Set default cache expiry
        if not self.cache_expires_at:
            self.set_cache_expiry()
        
        # Initialize metadata if not provided
        if not self.metadata_json:
            self.metadata_json = {}
        
        # Initialize tags if not provided
        if not self.tags:
            self.tags = []
    
    def __repr__(self) -> str:
        """Enhanced string representation"""
        return f"<{self.__class__.__name__}(id={self.id}, name='{self.name}', status='{self.status}')>"
    
    def __str__(self) -> str:
        """Human-readable string representation"""
        return f"{self.__class__.__name__}: {self.name}"
    
    # ===============================================================================
    # SERIALIZATION METHODS
    # ===============================================================================
    
    def to_dict(self, include_relations: bool = False, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Args:
            include_relations: Include relationship data
            exclude_fields: Fields to exclude from serialization
            
        Returns:
            Dictionary representation of the model
        """
        exclude_fields = exclude_fields or []
        result = {}
        
        # Get all columns
        for column in self.__table__.columns:
            field_name = column.name
            
            if field_name in exclude_fields:
                continue
                
            value = getattr(self, field_name)
            
            # Handle special types
            if isinstance(value, uuid.UUID):
                result[field_name] = str(value)
            elif isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, (dict, list)):
                result[field_name] = value
            else:
                result[field_name] = value
        
        # Include relationships if requested
        if include_relations:
            for relationship in self.__mapper__.relationships:
                rel_name = relationship.key
                if rel_name not in exclude_fields:
                    rel_value = getattr(self, rel_name)
                    if rel_value is not None:
                        if hasattr(rel_value, '__iter__') and not isinstance(rel_value, str):
                            # Collection relationship
                            result[rel_name] = [
                                item.to_dict(include_relations=False) 
                                if hasattr(item, 'to_dict') else str(item)
                                for item in rel_value
                            ]
                        else:
                            # Single relationship
                            result[rel_name] = (
                                rel_value.to_dict(include_relations=False)
                                if hasattr(rel_value, 'to_dict') else str(rel_value)
                            )
        
        return result
    
    def to_json(self, **kwargs) -> str:
        """Convert model to JSON string"""
        return json.dumps(self.to_dict(**kwargs), default=str, indent=2)
    
    @classmethod
    def from_dict(cls: Type[BaseModelType], data: Dict[str, Any]) -> BaseModelType:
        """
        Create model instance from dictionary.
        
        Args:
            data: Dictionary containing model data
            
        Returns:
            New model instance
        """
        # Filter out invalid fields
        valid_columns = {column.name for column in cls.__table__.columns}
        filtered_data = {k: v for k, v in data.items() if k in valid_columns}
        
        # Handle UUID fields
        for column in cls.__table__.columns:
            if column.type.python_type == uuid.UUID and column.name in filtered_data:
                value = filtered_data[column.name]
                if isinstance(value, str):
                    filtered_data[column.name] = uuid.UUID(value)
        
        return cls(**filtered_data)
    
    # ===============================================================================
    # METADATA HELPER METHODS
    # ===============================================================================
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata value"""
        if not isinstance(self.metadata_json, dict):
            self.metadata_json = {}
        
        self.metadata_json[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value"""
        if not isinstance(self.metadata_json, dict):
            return default
        
        return self.metadata_json.get(key, default)
    
    def remove_metadata(self, key: str) -> bool:
        """Remove metadata key"""
        if not isinstance(self.metadata_json, dict):
            return False
        
        if key in self.metadata_json:
            del self.metadata_json[key]
            return True
        
        return False
    
    def add_tag(self, tag: str) -> None:
        """Add tag to the record"""
        if not isinstance(self.tags, list):
            self.tags = []
        
        tag = tag.lower().strip()
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> bool:
        """Remove tag from the record"""
        if not isinstance(self.tags, list):
            return False
        
        tag = tag.lower().strip()
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        
        return False
    
    def has_tag(self, tag: str) -> bool:
        """Check if record has specific tag"""
        if not isinstance(self.tags, list):
            return False
        
        tag = tag.lower().strip()
        return tag in self.tags
    
    # ===============================================================================
    # SOFT DELETE METHODS
    # ===============================================================================
    
    def soft_delete(self, deleted_by: Optional[uuid.UUID] = None) -> None:
        """Perform soft delete"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by
        self.status = "deleted"
    
    def restore(self) -> None:
        """Restore soft deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.status = "active"
    
    # ===============================================================================
    # VERSION CONTROL METHODS
    # ===============================================================================
    
    def increment_version(self) -> None:
        """Increment version number"""
        self.version = (self.version or 0) + 1
    
    # ===============================================================================
    # QUERY HELPER METHODS
    # ===============================================================================
    
    @classmethod
    async def get_by_id(
        cls: Type[BaseModelType], 
        session: AsyncSession, 
        record_id: uuid.UUID,
        include_deleted: bool = False
    ) -> Optional[BaseModelType]:
        """Get record by ID"""
        from sqlalchemy import select
        
        query = select(cls).where(cls.id == record_id)
        
        if not include_deleted:
            query = query.where(cls.is_deleted == False)
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_by_name(
        cls: Type[BaseModelType], 
        session: AsyncSession, 
        name: str,
        include_deleted: bool = False
    ) -> Optional[BaseModelType]:
        """Get record by name"""
        from sqlalchemy import select
        
        query = select(cls).where(cls.name == name)
        
        if not include_deleted:
            query = query.where(cls.is_deleted == False)
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @classmethod
    async def get_active(
        cls: Type[BaseModelType], 
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0
    ) -> List[BaseModelType]:
        """Get active records"""
        from sqlalchemy import select
        
        query = (
            select(cls)
            .where(cls.is_deleted == False)
            .where(cls.status == "active")
            .limit(limit)
            .offset(offset)
            .order_by(cls.created_at.desc())
        )
        
        result = await session.execute(query)
        return result.scalars().all()

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "AuditMixin", 
    "MetadataMixin",
    "CacheMixin",
    "BaseModelType"
]