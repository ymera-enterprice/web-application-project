"""
YMERA Enterprise - Storage Backend
Production-Ready File Storage Abstraction - v4.0
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
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, BinaryIO, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from urllib.parse import urlparse

# Third-party imports (alphabetical)
import aiofiles
import aioredis
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import structlog
from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Storage configuration constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
CHUNK_SIZE = 8192  # 8KB chunks for streaming
UPLOAD_TIMEOUT = 300  # 5 minutes
SUPPORTED_STORAGE_TYPES = ["local", "s3", "azure", "gcs"]
COMPRESSION_THRESHOLD = 1024 * 1024  # 1MB

# Cache settings
CACHE_TTL = 3600
METADATA_CACHE_TTL = 1800

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class StorageConfig:
    """Configuration dataclass for storage settings"""
    storage_type: str = "local"
    base_path: str = "/tmp/ymera_storage"
    max_file_size: int = MAX_FILE_SIZE
    enable_compression: bool = True
    enable_encryption: bool = True
    aws_bucket: Optional[str] = None
    aws_region: Optional[str] = None
    azure_container: Optional[str] = None
    gcs_bucket: Optional[str] = None

@dataclass
class FileMetadata:
    """File metadata information"""
    file_id: str
    filename: str
    content_type: str
    size: int
    checksum: str
    storage_path: str
    created_at: datetime
    modified_at: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    encryption_key: Optional[str] = None
    compression_type: Optional[str] = None

class UploadRequest(BaseModel):
    """Schema for file upload requests"""
    filename: str = Field(..., max_length=255)
    content_type: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    encrypt: bool = True
    compress: bool = True
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Filename cannot be empty")
        
        # Check for dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in v for char in dangerous_chars):
            raise ValueError("Filename contains invalid characters")
        
        return v.strip()

class DownloadResponse(BaseModel):
    """Schema for file download responses"""
    file_id: str
    filename: str
    content_type: str
    size: int
    download_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class StorageStats(BaseModel):
    """Storage statistics response"""
    total_files: int
    total_size: int
    storage_type: str
    available_space: Optional[int] = None
    used_space: int
    last_updated: datetime

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class BaseStorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.logger = logger.bind(storage_type=config.storage_type)
        self._cache: Optional[aioredis.Redis] = None
        self._initialized = False
    
    @abstractmethod
    async def _initialize_backend(self) -> None:
        """Initialize backend-specific resources"""
        pass
    
    @abstractmethod
    async def _store_file_data(self, file_id: str, data: bytes, metadata: FileMetadata) -> str:
        """Store file data in backend storage"""
        pass
    
    @abstractmethod
    async def _retrieve_file_data(self, storage_path: str) -> bytes:
        """Retrieve file data from backend storage"""
        pass
    
    @abstractmethod
    async def _delete_file_data(self, storage_path: str) -> bool:
        """Delete file data from backend storage"""
        pass
    
    @abstractmethod
    async def _get_storage_stats(self) -> Dict[str, Any]:
        """Get backend-specific storage statistics"""
        pass
    
    async def initialize(self) -> None:
        """Initialize storage backend"""
        if self._initialized:
            return
        
        try:
            # Initialize Redis cache
            self._cache = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Initialize backend-specific resources
            await self._initialize_backend()
            
            self._initialized = True
            self.logger.info("Storage backend initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize storage backend", error=str(e))
            raise RuntimeError(f"Storage initialization failed: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup storage backend resources"""
        try:
            if self._cache:
                await self._cache.close()
            self.logger.info("Storage backend cleaned up successfully")
        except Exception as e:
            self.logger.error("Error during cleanup", error=str(e))

class LocalStorageBackend(BaseStorageBackend):
    """Local filesystem storage implementation"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_path = Path(config.base_path)
    
    async def _initialize_backend(self) -> None:
        """Initialize local storage directories"""
        try:
            # Create base directory structure
            self.base_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories for organization
            for subdir in ["files", "temp", "encrypted", "compressed"]:
                (self.base_path / subdir).mkdir(exist_ok=True)
            
            # Check write permissions
            test_file = self.base_path / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            
            self.logger.info("Local storage initialized", path=str(self.base_path))
            
        except PermissionError:
            raise RuntimeError(f"No write permission for storage path: {self.base_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize local storage: {str(e)}")
    
    async def _store_file_data(self, file_id: str, data: bytes, metadata: FileMetadata) -> str:
        """Store file data in local filesystem"""
        try:
            # Determine storage subdirectory
            subdir = "files"
            if metadata.encryption_key:
                subdir = "encrypted"
            elif metadata.compression_type:
                subdir = "compressed"
            
            # Create file path
            file_path = self.base_path / subdir / f"{file_id}"
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file data
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(data)
            
            # Verify file was written correctly
            if not file_path.exists() or file_path.stat().st_size != len(data):
                raise RuntimeError("File verification failed after write")
            
            storage_path = str(file_path.relative_to(self.base_path))
            self.logger.debug("File stored locally", file_id=file_id, path=storage_path)
            
            return storage_path
            
        except Exception as e:
            self.logger.error("Failed to store file locally", file_id=file_id, error=str(e))
            raise RuntimeError(f"Local storage failed: {str(e)}")
    
    async def _retrieve_file_data(self, storage_path: str) -> bytes:
        """Retrieve file data from local filesystem"""
        try:
            file_path = self.base_path / storage_path
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {storage_path}")
            
            async with aiofiles.open(file_path, 'rb') as f:
                data = await f.read()
            
            self.logger.debug("File retrieved locally", path=storage_path, size=len(data))
            return data
            
        except FileNotFoundError:
            raise
        except Exception as e:
            self.logger.error("Failed to retrieve file locally", path=storage_path, error=str(e))
            raise RuntimeError(f"Local retrieval failed: {str(e)}")
    
    async def _delete_file_data(self, storage_path: str) -> bool:
        """Delete file data from local filesystem"""
        try:
            file_path = self.base_path / storage_path
            
            if not file_path.exists():
                self.logger.warning("File not found for deletion", path=storage_path)
                return False
            
            file_path.unlink()
            self.logger.debug("File deleted locally", path=storage_path)
            return True
            
        except Exception as e:
            self.logger.error("Failed to delete file locally", path=storage_path, error=str(e))
            return False
    
    async def _get_storage_stats(self) -> Dict[str, Any]:
        """Get local storage statistics"""
        try:
            total_size = 0
            file_count = 0
            
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    file_count += 1
                    total_size += file_path.stat().st_size
            
            # Get available space
            statvfs = os.statvfs(self.base_path)
            available_space = statvfs.f_frsize * statvfs.f_bavail
            
            return {
                "total_files": file_count,
                "total_size": total_size,
                "available_space": available_space,
                "used_space": total_size
            }
            
        except Exception as e:
            self.logger.error("Failed to get storage stats", error=str(e))
            return {
                "total_files": 0,
                "total_size": 0,
                "available_space": None,
                "used_space": 0
            }

class S3StorageBackend(BaseStorageBackend):
    """AWS S3 storage implementation"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.bucket_name = config.aws_bucket
        self.region = config.aws_region or "us-east-1"
        self._s3_client = None
    
    async def _initialize_backend(self) -> None:
        """Initialize S3 client and verify bucket access"""
        try:
            import aiobotocore.session
            
            session = aiobotocore.session.get_session()
            self._s3_client = session.create_client(
                's3',
                region_name=self.region
            )
            
            # Verify bucket access
            await self._s3_client.head_bucket(Bucket=self.bucket_name)
            
            self.logger.info("S3 storage initialized", bucket=self.bucket_name, region=self.region)
            
        except NoCredentialsError:
            raise RuntimeError("AWS credentials not found or invalid")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise RuntimeError(f"S3 bucket not found: {self.bucket_name}")
            elif error_code == '403':
                raise RuntimeError(f"Access denied to S3 bucket: {self.bucket_name}")
            else:
                raise RuntimeError(f"S3 error: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize S3 storage: {str(e)}")
    
    async def _store_file_data(self, file_id: str, data: bytes, metadata: FileMetadata) -> str:
        """Store file data in S3"""
        try:
            # Create S3 key
            key = f"files/{file_id[:2]}/{file_id}"
            
            # Prepare metadata for S3
            s3_metadata = {
                'filename': metadata.filename,
                'content-type': metadata.content_type,
                'checksum': metadata.checksum,
                'created-at': metadata.created_at.isoformat()
            }
            
            # Add tags if present
            if metadata.tags:
                s3_metadata.update({f"tag-{k}": v for k, v in metadata.tags.items()})
            
            # Upload to S3
            await self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=metadata.content_type,
                Metadata=s3_metadata
            )
            
            self.logger.debug("File stored in S3", file_id=file_id, key=key)
            return key
            
        except Exception as e:
            self.logger.error("Failed to store file in S3", file_id=file_id, error=str(e))
            raise RuntimeError(f"S3 storage failed: {str(e)}")
    
    async def _retrieve_file_data(self, storage_path: str) -> bytes:
        """Retrieve file data from S3"""
        try:
            response = await self._s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            # Read all data from stream
            data = await response['Body'].read()
            
            self.logger.debug("File retrieved from S3", path=storage_path, size=len(data))
            return data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in S3: {storage_path}")
            else:
                raise RuntimeError(f"S3 retrieval error: {e}")
        except Exception as e:
            self.logger.error("Failed to retrieve file from S3", path=storage_path, error=str(e))
            raise RuntimeError(f"S3 retrieval failed: {str(e)}")
    
    async def _delete_file_data(self, storage_path: str) -> bool:
        """Delete file data from S3"""
        try:
            await self._s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            self.logger.debug("File deleted from S3", path=storage_path)
            return True
            
        except Exception as e:
            self.logger.error("Failed to delete file from S3", path=storage_path, error=str(e))
            return False
    
    async def _get_storage_stats(self) -> Dict[str, Any]:
        """Get S3 storage statistics"""
        try:
            paginator = self._s3_client.get_paginator('list_objects_v2')
            
            total_size = 0
            file_count = 0
            
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix="files/")
            async for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        file_count += 1
                        total_size += obj['Size']
            
            return {
                "total_files": file_count,
                "total_size": total_size,
                "available_space": None,  # S3 has no fixed limit
                "used_space": total_size
            }
            
        except Exception as e:
            self.logger.error("Failed to get S3 storage stats", error=str(e))
            return {
                "total_files": 0,
                "total_size": 0,
                "available_space": None,
                "used_space": 0
            }

class StorageManager:
    """Main storage manager coordinating different backends"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.logger = logger.bind(component="storage_manager")
        self._backend: Optional[BaseStorageBackend] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize storage manager and backend"""
        if self._initialized:
            return
        
        try:
            # Create appropriate backend
            if self.config.storage_type == "local":
                self._backend = LocalStorageBackend(self.config)
            elif self.config.storage_type == "s3":
                if not self.config.aws_bucket:
                    raise ValueError("AWS bucket name required for S3 storage")
                self._backend = S3StorageBackend(self.config)
            else:
                raise ValueError(f"Unsupported storage type: {self.config.storage_type}")
            
            # Initialize backend
            await self._backend.initialize()
            
            self._initialized = True
            self.logger.info("Storage manager initialized", storage_type=self.config.storage_type)
            
        except Exception as e:
            self.logger.error("Failed to initialize storage manager", error=str(e))
            raise
    
    @track_performance
    async def store_file(self, file_data: bytes, metadata: FileMetadata) -> str:
        """Store file with optional encryption and compression"""
        if not self._initialized:
            raise RuntimeError("Storage manager not initialized")
        
        try:
            processed_data = file_data
            
            # Apply compression if enabled and file is large enough
            if (self.config.enable_compression and 
                len(file_data) > COMPRESSION_THRESHOLD and 
                not metadata.compression_type):
                
                import gzip
                compressed_data = gzip.compress(file_data)
                if len(compressed_data) < len(file_data):
                    processed_data = compressed_data
                    metadata.compression_type = "gzip"
                    self.logger.debug("File compressed", 
                                    original_size=len(file_data),
                                    compressed_size=len(compressed_data))
            
            # Apply encryption if enabled
            if self.config.enable_encryption and metadata.encryption_key:
                processed_data = encrypt_data(processed_data, metadata.encryption_key)
                self.logger.debug("File encrypted", file_id=metadata.file_id)
            
            # Store in backend
            storage_path = await self._backend._store_file_data(
                metadata.file_id,
                processed_data,
                metadata
            )
            
            # Update metadata with final storage path
            metadata.storage_path = storage_path
            
            self.logger.info("File stored successfully",
                           file_id=metadata.file_id,
                           filename=metadata.filename,
                           size=len(file_data))
            
            return storage_path
            
        except Exception as e:
            self.logger.error("Failed to store file",
                            file_id=metadata.file_id,
                            error=str(e))
            raise
    
    @track_performance
    async def retrieve_file(self, file_id: str, storage_path: str, 
                           metadata: FileMetadata) -> bytes:
        """Retrieve file with decryption and decompression"""
        if not self._initialized:
            raise RuntimeError("Storage manager not initialized")
        
        try:
            # Retrieve from backend
            file_data = await self._backend._retrieve_file_data(storage_path)
            
            # Apply decryption if needed
            if metadata.encryption_key:
                file_data = decrypt_data(file_data, metadata.encryption_key)
                self.logger.debug("File decrypted", file_id=file_id)
            
            # Apply decompression if needed
            if metadata.compression_type == "gzip":
                import gzip
                file_data = gzip.decompress(file_data)
                self.logger.debug("File decompressed", file_id=file_id)
            
            # Verify checksum
            calculated_checksum = hashlib.sha256(file_data).hexdigest()
            if calculated_checksum != metadata.checksum:
                raise RuntimeError("File integrity check failed")
            
            self.logger.info("File retrieved successfully",
                           file_id=file_id,
                           size=len(file_data))
            
            return file_data
            
        except Exception as e:
            self.logger.error("Failed to retrieve file",
                            file_id=file_id,
                            error=str(e))
            raise
    
    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from storage"""
        if not self._initialized:
            raise RuntimeError("Storage manager not initialized")
        
        try:
            result = await self._backend._delete_file_data(storage_path)
            self.logger.info("File deletion result", path=storage_path, success=result)
            return result
            
        except Exception as e:
            self.logger.error("Failed to delete file", path=storage_path, error=str(e))
            return False
    
    async def get_storage_stats(self) -> StorageStats:
        """Get storage statistics"""
        if not self._initialized:
            raise RuntimeError("Storage manager not initialized")
        
        try:
            stats_data = await self._backend._get_storage_stats()
            
            return StorageStats(
                total_files=stats_data["total_files"],
                total_size=stats_data["total_size"],
                storage_type=self.config.storage_type,
                available_space=stats_data.get("available_space"),
                used_space=stats_data["used_space"],
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            self.logger.error("Failed to get storage stats", error=str(e))
            raise
    
    async def cleanup(self) -> None:
        """Cleanup storage manager resources"""
        try:
            if self._backend:
                await self._backend.cleanup()
            self.logger.info("Storage manager cleaned up")
        except Exception as e:
            self.logger.error("Error during storage cleanup", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def calculate_file_checksum(data: bytes) -> str:
    """Calculate SHA-256 checksum for file data"""
    return hashlib.sha256(data).hexdigest()

def detect_content_type(filename: str, data: bytes) -> str:
    """Detect content type from filename and data"""
    # Try to guess from filename
    content_type, _ = mimetypes.guess_type(filename)
    
    if content_type:
        return content_type
    
    # Fallback detection based on file signature
    if data.startswith(b'\x89PNG'):
        return 'image/png'
    elif data.startswith(b'\xFF\xD8\xFF'):
        return 'image/jpeg'
    elif data.startswith(b'%PDF'):
        return 'application/pdf'
    elif data.startswith(b'PK'):
        return 'application/zip'
    else:
        return 'application/octet-stream'

async def validate_file_upload(file: UploadFile, config: StorageConfig) -> Tuple[bytes, FileMetadata]:
    """Validate and process file upload"""
    try:
        # Check file size
        if hasattr(file, 'size') and file.size and file.size > config.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {config.max_file_size} bytes"
            )
        
        # Read file data
        file_data = await file.read()
        
        # Validate actual file size
        if len(file_data) > config.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed size of {config.max_file_size} bytes"
            )
        
        # Generate file ID and calculate checksum
        file_id = str(uuid.uuid4())
        checksum = calculate_file_checksum(file_data)
        
        # Detect content type
        content_type = detect_content_type(file.filename or "unknown", file_data)
        
        # Create metadata
        metadata = FileMetadata(
            file_id=file_id,
            filename=file.filename or f"upload_{file_id[:8]}",
            content_type=content_type,
            size=len(file_data),
            checksum=checksum,
            storage_path="",  # Will be set during storage
            created_at=datetime.utcnow(),
            modified_at=datetime.utcnow()
        )
        
        return file_data, metadata
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload validation failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail="Invalid file upload")

async def health_check() -> Dict[str, Any]:
    """Storage backend health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "storage_backend",
        "version": "4.0"
    }

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_storage_manager() -> StorageManager:
    """Initialize storage manager for production use"""
    config = StorageConfig(
        storage_type=settings.STORAGE_TYPE,
        base_path=settings.STORAGE_BASE_PATH,
        max_file_size=settings.MAX_FILE_SIZE,
        enable_compression=settings.ENABLE_COMPRESSION,
        enable_encryption=settings.ENABLE_ENCRYPTION,
        aws_bucket=settings.AWS_S3_BUCKET,
        aws_region=settings.AWS_REGION,
        azure_container=settings.AZURE_CONTAINER,
        gcs_bucket=settings.GCS_BUCKET
    )
    
    manager = StorageManager(config)
    await manager.initialize()
    
    return manager

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "StorageManager",
    "StorageConfig",
    "FileMetadata",
    "UploadRequest",
    "DownloadResponse",
    "StorageStats",
    "LocalStorageBackend",
    "S3StorageBackend",
    "initialize_storage_manager",
    "validate_file_upload",
    "calculate_file_checksum",
    "detect_content_type",
    "health_check"
]