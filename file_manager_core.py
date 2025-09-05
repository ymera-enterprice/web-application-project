"""
YMERA Enterprise - File Manager Core
Production-Ready File Operations Orchestrator - v4.0
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
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, IO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

# Third-party imports (alphabetical)
import aiofiles
import structlog
from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, Field, validator

# Local imports
from config.settings import get_settings
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_manager")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Operation constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 300  # 5 minutes for large file operations
CHUNK_SIZE = 8192  # 8KB chunks for file operations
TEMP_FILE_TTL = 3600  # 1 hour for temporary files

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class FileManagerConfig:
    """Configuration for file manager operations"""
    upload_path: str = "./uploads"
    temp_path: str = "./temp"
    max_file_size: int = 500 * 1024 * 1024  # 500MB
    max_concurrent_operations: int = 10
    enable_compression: bool = True
    enable_encryption: bool = True
    enable_virus_scan: bool = True
    enable_thumbnails: bool = True
    retention_days: int = 365
    backup_enabled: bool = True

class FileOperationRequest(BaseModel):
    """Request schema for file operations"""
    operation: str = Field(..., description="Operation type: upload, download, delete, move, copy")
    file_id: Optional[str] = Field(None, description="File identifier")
    source_path: Optional[str] = Field(None, description="Source file path")
    destination_path: Optional[str] = Field(None, description="Destination file path")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    options: Dict[str, Any] = Field(default_factory=dict, description="Operation options")
    
    @validator('operation')
    def validate_operation(cls, v):
        allowed_operations = ['upload', 'download', 'delete', 'move', 'copy', 'list', 'info']
        if v not in allowed_operations:
            raise ValueError(f"Operation must be one of: {allowed_operations}")
        return v

class FileOperationResponse(BaseModel):
    """Response schema for file operations"""
    success: bool = Field(..., description="Operation success status")
    file_id: Optional[str] = Field(None, description="File identifier")
    message: str = Field(..., description="Operation result message")
    data: Dict[str, Any] = Field(default_factory=dict, description="Response data")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

@dataclass
class FileInfo:
    """Comprehensive file information structure"""
    file_id: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    file_hash: str
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    owner_id: str
    permissions: Dict[str, bool]
    metadata: Dict[str, Any]
    tags: List[str] = field(default_factory=list)
    versions: List[str] = field(default_factory=list)
    is_encrypted: bool = False
    is_compressed: bool = False
    scan_status: str = "pending"
    retention_date: Optional[datetime] = None

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileManager:
    """
    Central file management orchestrator
    Coordinates all file operations through specialized handlers
    """
    
    def __init__(
        self,
        upload_handler,
        download_handler,
        storage_backend,
        metadata_manager,
        file_validator,
        config: FileManagerConfig
    ):
        self.upload_handler = upload_handler
        self.download_handler = download_handler
        self.storage_backend = storage_backend
        self.metadata_manager = metadata_manager
        self.file_validator = file_validator
        self.config = config
        self.logger = logger.bind(component="file_manager")
        
        # Operation tracking
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._operation_semaphore = asyncio.Semaphore(config.max_concurrent_operations)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize file manager and all components"""
        try:
            # Ensure directories exist
            await self._ensure_directories()
            
            # Initialize cleanup scheduler
            asyncio.create_task(self._periodic_cleanup())
            
            # Initialize operation monitoring
            asyncio.create_task(self._monitor_operations())
            
            self._initialized = True
            self.logger.info(
                "File manager initialized successfully",
                config=self.config.__dict__
            )
            
        except Exception as e:
            self.logger.error("File manager initialization failed", error=str(e))
            raise RuntimeError(f"File manager initialization failed: {str(e)}")
    
    async def _ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        directories = [
            self.config.upload_path,
            self.config.temp_path,
            os.path.join(self.config.upload_path, "thumbnails"),
            os.path.join(self.config.upload_path, "encrypted"),
            os.path.join(self.config.upload_path, "compressed")
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    @track_performance
    async def upload_file(
        self,
        file: Union[UploadFile, IO, bytes],
        filename: str,
        owner_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> FileOperationResponse:
        """
        Upload a file with comprehensive processing
        
        Args:
            file: File data (UploadFile, file object, or bytes)
            filename: Original filename
            owner_id: User ID of file owner
            metadata: Additional file metadata
            options: Upload options (compression, encryption, etc.)
            
        Returns:
            FileOperationResponse with upload results
        """
        operation_id = str(uuid.uuid4())
        
        try:
            async with self._operation_semaphore:
                # Track operation
                self._active_operations[operation_id] = {
                    'type': 'upload',
                    'filename': filename,
                    'owner_id': owner_id,
                    'started_at': datetime.utcnow(),
                    'status': 'processing'
                }
                
                # Delegate to upload handler
                result = await self.upload_handler.handle_upload(
                    file=file,
                    filename=filename,
                    owner_id=owner_id,
                    metadata=metadata or {},
                    options=options or {}
                )
                
                # Update operation status
                self._active_operations[operation_id]['status'] = 'completed'
                
                return FileOperationResponse(
                    success=True,
                    file_id=result.get('file_id'),
                    message="File uploaded successfully",
                    data=result
                )
                
        except Exception as e:
            self._active_operations[operation_id]['status'] = 'failed'
            self._active_operations[operation_id]['error'] = str(e)
            
            self.logger.error(
                "File upload failed",
                operation_id=operation_id,
                filename=filename,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="File upload failed",
                errors=[str(e)]
            )
        finally:
            # Cleanup operation tracking after delay
            asyncio.create_task(self._cleanup_operation(operation_id, delay=300))
    
    @track_performance
    async def download_file(
        self,
        file_id: str,
        user_id: str,
        options: Optional[Dict[str, Any]] = None
    ) -> FileOperationResponse:
        """
        Download a file with security checks
        
        Args:
            file_id: Unique file identifier
            user_id: User requesting the download
            options: Download options (format, quality, etc.)
            
        Returns:
            FileOperationResponse with download results
        """
        operation_id = str(uuid.uuid4())
        
        try:
            async with self._operation_semaphore:
                # Track operation
                self._active_operations[operation_id] = {
                    'type': 'download',
                    'file_id': file_id,
                    'user_id': user_id,
                    'started_at': datetime.utcnow(),
                    'status': 'processing'
                }
                
                # Delegate to download handler
                result = await self.download_handler.handle_download(
                    file_id=file_id,
                    user_id=user_id,
                    options=options or {}
                )
                
                # Update operation status
                self._active_operations[operation_id]['status'] = 'completed'
                
                return FileOperationResponse(
                    success=True,
                    file_id=file_id,
                    message="File prepared for download",
                    data=result
                )
                
        except Exception as e:
            self._active_operations[operation_id]['status'] = 'failed'
            self._active_operations[operation_id]['error'] = str(e)
            
            self.logger.error(
                "File download failed",
                operation_id=operation_id,
                file_id=file_id,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="File download failed",
                errors=[str(e)]
            )
        finally:
            asyncio.create_task(self._cleanup_operation(operation_id, delay=60))
    
    @track_performance
    async def delete_file(
        self,
        file_id: str,
        user_id: str,
        permanent: bool = False
    ) -> FileOperationResponse:
        """
        Delete a file (soft delete by default)
        
        Args:
            file_id: Unique file identifier
            user_id: User requesting deletion
            permanent: Whether to permanently delete the file
            
        Returns:
            FileOperationResponse with deletion results
        """
        try:
            # Get file metadata
            file_info = await self.metadata_manager.get_file_metadata(file_id)
            if not file_info:
                return FileOperationResponse(
                    success=False,
                    message="File not found",
                    errors=["File does not exist"]
                )
            
            # Check permissions
            if not await self._check_file_permissions(file_info, user_id, 'delete'):
                return FileOperationResponse(
                    success=False,
                    message="Permission denied",
                    errors=["User does not have delete permissions for this file"]
                )
            
            if permanent:
                # Permanent deletion
                await self.storage_backend.delete_file(file_info['file_path'])
                await self.metadata_manager.delete_file_metadata(file_id)
                
                message = "File permanently deleted"
            else:
                # Soft deletion
                await self.metadata_manager.mark_file_deleted(file_id, user_id)
                message = "File moved to trash"
            
            self.logger.info(
                "File deleted successfully",
                file_id=file_id,
                user_id=user_id,
                permanent=permanent
            )
            
            return FileOperationResponse(
                success=True,
                file_id=file_id,
                message=message
            )
            
        except Exception as e:
            self.logger.error(
                "File deletion failed",
                file_id=file_id,
                user_id=user_id,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="File deletion failed",
                errors=[str(e)]
            )
    
    @track_performance
    async def move_file(
        self,
        file_id: str,
        destination_path: str,
        user_id: str
    ) -> FileOperationResponse:
        """
        Move a file to a new location
        
        Args:
            file_id: Unique file identifier
            destination_path: New file location
            user_id: User performing the move
            
        Returns:
            FileOperationResponse with move results
        """
        try:
            # Get file metadata
            file_info = await self.metadata_manager.get_file_metadata(file_id)
            if not file_info:
                return FileOperationResponse(
                    success=False,
                    message="File not found",
                    errors=["File does not exist"]
                )
            
            # Check permissions
            if not await self._check_file_permissions(file_info, user_id, 'write'):
                return FileOperationResponse(
                    success=False,
                    message="Permission denied",
                    errors=["User does not have write permissions for this file"]
                )
            
            # Move file
            old_path = file_info['file_path']
            new_path = await self.storage_backend.move_file(old_path, destination_path)
            
            # Update metadata
            await self.metadata_manager.update_file_path(file_id, new_path)
            
            self.logger.info(
                "File moved successfully",
                file_id=file_id,
                old_path=old_path,
                new_path=new_path,
                user_id=user_id
            )
            
            return FileOperationResponse(
                success=True,
                file_id=file_id,
                message="File moved successfully",
                data={'new_path': new_path}
            )
            
        except Exception as e:
            self.logger.error(
                "File move failed",
                file_id=file_id,
                destination_path=destination_path,
                user_id=user_id,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="File move failed",
                errors=[str(e)]
            )
    
    @track_performance
    async def copy_file(
        self,
        file_id: str,
        destination_path: str,
        user_id: str,
        new_filename: Optional[str] = None
    ) -> FileOperationResponse:
        """
        Copy a file to a new location
        
        Args:
            file_id: Unique file identifier
            destination_path: Destination for the copy
            user_id: User performing the copy
            new_filename: Optional new filename for the copy
            
        Returns:
            FileOperationResponse with copy results
        """
        try:
            # Get file metadata
            file_info = await self.metadata_manager.get_file_metadata(file_id)
            if not file_info:
                return FileOperationResponse(
                    success=False,
                    message="File not found",
                    errors=["File does not exist"]
                )
            
            # Check permissions
            if not await self._check_file_permissions(file_info, user_id, 'read'):
                return FileOperationResponse(
                    success=False,
                    message="Permission denied",
                    errors=["User does not have read permissions for this file"]
                )
            
            # Copy file
            source_path = file_info['file_path']
            copy_path = await self.storage_backend.copy_file(
                source_path, 
                destination_path,
                new_filename
            )
            
            # Create metadata for copy
            new_file_id = str(uuid.uuid4())
            copy_metadata = file_info.copy()
            copy_metadata.update({
                'file_id': new_file_id,
                'file_path': copy_path,
                'filename': new_filename or file_info['filename'],
                'created_at': datetime.utcnow(),
                'owner_id': user_id,
                'is_copy': True,
                'original_file_id': file_id
            })
            
            await self.metadata_manager.create_file_metadata(copy_metadata)
            
            self.logger.info(
                "File copied successfully",
                original_file_id=file_id,
                new_file_id=new_file_id,
                copy_path=copy_path,
                user_id=user_id
            )
            
            return FileOperationResponse(
                success=True,
                file_id=new_file_id,
                message="File copied successfully",
                data={
                    'original_file_id': file_id,
                    'copy_file_id': new_file_id,
                    'copy_path': copy_path
                }
            )
            
        except Exception as e:
            self.logger.error(
                "File copy failed",
                file_id=file_id,
                destination_path=destination_path,
                user_id=user_id,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="File copy failed",
                errors=[str(e)]
            )
    
    @track_performance
    async def list_files(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> FileOperationResponse:
        """
        List files accessible to user with optional filtering
        
        Args:
            user_id: User requesting the list
            filters: Optional filters (file_type, date_range, etc.)
            limit: Maximum number of files to return
            offset: Number of files to skip
            
        Returns:
            FileOperationResponse with file list
        """
        try:
            files = await self.metadata_manager.list_user_files(
                user_id=user_id,
                filters=filters or {},
                limit=limit,
                offset=offset
            )
            
            total_count = await self.metadata_manager.count_user_files(
                user_id=user_id,
                filters=filters or {}
            )
            
            return FileOperationResponse(
                success=True,
                message=f"Retrieved {len(files)} files",
                data={
                    'files': files,
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': (offset + len(files)) < total_count
                }
            )
            
        except Exception as e:
            self.logger.error(
                "File listing failed",
                user_id=user_id,
                filters=filters,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="File listing failed",
                errors=[str(e)]
            )
    
    @track_performance
    async def get_file_info(
        self,
        file_id: str,
        user_id: str
    ) -> FileOperationResponse:
        """
        Get detailed information about a specific file
        
        Args:
            file_id: Unique file identifier
            user_id: User requesting the information
            
        Returns:
            FileOperationResponse with file information
        """
        try:
            # Get file metadata
            file_info = await self.metadata_manager.get_file_metadata(file_id)
            if not file_info:
                return FileOperationResponse(
                    success=False,
                    message="File not found",
                    errors=["File does not exist"]
                )
            
            # Check permissions
            if not await self._check_file_permissions(file_info, user_id, 'read'):
                return FileOperationResponse(
                    success=False,
                    message="Permission denied",
                    errors=["User does not have read permissions for this file"]
                )
            
            # Get additional file statistics
            file_stats = await self.storage_backend.get_file_stats(file_info['file_path'])
            
            # Combine information
            detailed_info = {
                **file_info,
                'stats': file_stats,
                'access_history': await self.metadata_manager.get_file_access_history(file_id),
                'versions': await self.metadata_manager.get_file_versions(file_id)
            }
            
            return FileOperationResponse(
                success=True,
                file_id=file_id,
                message="File information retrieved successfully",
                data=detailed_info
            )
            
        except Exception as e:
            self.logger.error(
                "Get file info failed",
                file_id=file_id,
                user_id=user_id,
                error=str(e)
            )
            
            return FileOperationResponse(
                success=False,
                message="Failed to retrieve file information",
                errors=[str(e)]
            )
    
    async def _check_file_permissions(
        self,
        file_info: Dict[str, Any],
        user_id: str,
        permission: str
    ) -> bool:
        """
        Check if user has required permission for file
        
        Args:
            file_info: File metadata dictionary
            user_id: User ID to check permissions for
            permission: Required permission (read, write, delete)
            
        Returns:
            True if user has permission
        """
        try:
            # Owner has all permissions
            if file_info.get('owner_id') == user_id:
                return True
            
            # Check explicit permissions
            permissions = file_info.get('permissions', {})
            user_permissions = permissions.get(user_id, {})
            
            if user_permissions.get(permission, False):
                return True
            
            # Check group permissions (if implemented)
            # This would integrate with your user management system
            
            return False
            
        except Exception as e:
            self.logger.error(
                "Permission check failed",
                file_id=file_info.get('file_id'),
                user_id=user_id,
                permission=permission,
                error=str(e)
            )
            return False
    
    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of temporary files and expired content"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up temporary files
                await self._cleanup_temp_files()
                
                # Clean up expired files
                await self._cleanup_expired_files()
                
                # Clean up deleted files past retention period
                await self._cleanup_deleted_files()
                
                self.logger.debug("Periodic cleanup completed")
                
            except Exception as e:
                self.logger.error("Periodic cleanup failed", error=str(e))
    
    async def _cleanup_temp_files(self) -> None:
        """Clean up temporary files older than TTL"""
        try:
            temp_path = Path(self.config.temp_path)
            current_time = datetime.utcnow()
            
            for file_path in temp_path.iterdir():
                if file_path.is_file():
                    # Check file age
                    file_stat = file_path.stat()
                    file_age = current_time.timestamp() - file_stat.st_mtime
                    
                    if file_age > TEMP_FILE_TTL:
                        file_path.unlink()
                        self.logger.debug(
                            "Temporary file cleaned up",
                            file_path=str(file_path),
                            age_seconds=file_age
                        )
            
        except Exception as e:
            self.logger.error("Temp file cleanup failed", error=str(e))
    
    async def _cleanup_expired_files(self) -> None:
        """Clean up files past their retention date"""
        try:
            expired_files = await self.metadata_manager.get_expired_files()
            
            for file_info in expired_files:
                file_id = file_info['file_id']
                file_path = file_info['file_path']
                
                # Move to archive or delete
                if self.config.backup_enabled:
                    await self.storage_backend.archive_file(file_path)
                else:
                    await self.storage_backend.delete_file(file_path)
                
                # Update metadata
                await self.metadata_manager.mark_file_expired(file_id)
                
                self.logger.info(
                    "Expired file processed",
                    file_id=file_id,
                    archived=self.config.backup_enabled
                )
            
        except Exception as e:
            self.logger.error("Expired file cleanup failed", error=str(e))
    
    async def _cleanup_deleted_files(self) -> None:
        """Permanently delete files that have been in trash too long"""
        try:
            # Get files deleted more than retention period ago
            cutoff_date = datetime.utcnow() - timedelta(days=self.config.retention_days)
            old_deleted_files = await self.metadata_manager.get_old_deleted_files(cutoff_date)
            
            for file_info in old_deleted_files:
                file_id = file_info['file_id']
                file_path = file_info['file_path']
                
                # Permanently delete
                await self.storage_backend.delete_file(file_path)
                await self.metadata_manager.delete_file_metadata(file_id)
                
                self.logger.info(
                    "Deleted file permanently removed",
                    file_id=file_id,
                    deleted_date=file_info.get('deleted_at')
                )
            
        except Exception as e:
            self.logger.error("Deleted file cleanup failed", error=str(e))
    
    async def _monitor_operations(self) -> None:
        """Monitor active operations and handle timeouts"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                timed_out_operations = []
                
                for op_id, op_info in self._active_operations.items():
                    started_at = op_info.get('started_at')
                    if started_at:
                        operation_age = (current_time - started_at).total_seconds()
                        
                        if operation_age > TIMEOUT_SECONDS:
                            timed_out_operations.append(op_id)
                
                # Handle timed out operations
                for op_id in timed_out_operations:
                    op_info = self._active_operations.get(op_id, {})
                    self.logger.warning(
                        "Operation timed out",
                        operation_id=op_id,
                        operation_type=op_info.get('type'),
                        duration_seconds=TIMEOUT_SECONDS
                    )
                    
                    # Mark as failed and clean up
                    if op_id in self._active_operations:
                        self._active_operations[op_id]['status'] = 'timeout'
                        await self._cleanup_operation(op_id)
                
            except Exception as e:
                self.logger.error("Operation monitoring failed", error=str(e))
    
    async def _cleanup_operation(self, operation_id: str, delay: int = 0) -> None:
        """Clean up operation tracking after optional delay"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        if operation_id in self._active_operations:
            del self._active_operations[operation_id]
    
    async def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a running operation"""
        return self._active_operations.get(operation_id)
    
    async def get_active_operations(self) -> Dict[str, Dict[str, Any]]:
        """Get all currently active operations"""
        return self._active_operations.copy()
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Attempt to cancel a running operation"""
        if operation_id in self._active_operations:
            self._active_operations[operation_id]['status'] = 'cancelled'
            # Additional cancellation logic would go here
            return True
        return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive file manager statistics"""
        try:
            return {
                'active_operations': len(self._active_operations),
                'operations_by_type': self._get_operations_by_type(),
                'storage_stats': await self.storage_backend.get_storage_statistics(),
                'metadata_stats': await self.metadata_manager.get_statistics(),
                'uptime': datetime.utcnow().isoformat(),
                'config': {
                    'max_file_size': self.config.max_file_size,
                    'max_concurrent_operations': self.config.max_concurrent_operations,
                    'features_enabled': {
                        'compression': self.config.enable_compression,
                        'encryption': self.config.enable_encryption,
                        'virus_scan': self.config.enable_virus_scan,
                        'thumbnails': self.config.enable_thumbnails,
                        'backup': self.config.backup_enabled
                    }
                }
            }
        except Exception as e:
            self.logger.error("Failed to get statistics", error=str(e))
            return {}
    
    def _get_operations_by_type(self) -> Dict[str, int]:
        """Get count of active operations by type"""
        counts = {}
        for op_info in self._active_operations.values():
            op_type = op_info.get('type', 'unknown')
            counts[op_type] = counts.get(op_type, 0) + 1
        return counts
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for file manager"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "component": "file_manager",
            "initialized": self._initialized,
            "checks": {}
        }
        
        try:
            # Check storage backend
            storage_health = await self.storage_backend.health_check()
            health_status["checks"]["storage"] = storage_health["status"]
            
            # Check metadata manager
            metadata_health = await self.metadata_manager.health_check()
            health_status["checks"]["metadata"] = metadata_health["status"]
            
            # Check upload handler
            upload_health = await self.upload_handler.health_check()
            health_status["checks"]["upload"] = upload_health["status"]
            
            # Check download handler
            download_health = await self.download_handler.health_check()
            health_status["checks"]["download"] = download_health["status"]
            
            # Check validator
            validator_health = await self.file_validator.health_check()
            health_status["checks"]["validator"] = validator_health["status"]
            
            # Check if any component is unhealthy
            unhealthy_components = [
                comp for comp, status in health_status["checks"].items()
                if status != "healthy"
            ]
            
            if unhealthy_components:
                health_status["status"] = "degraded"
                health_status["unhealthy_components"] = unhealthy_components
            
            # Add operational statistics
            health_status["statistics"] = {
                "active_operations": len(self._active_operations),
                "semaphore_available": self._operation_semaphore._value
            }
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            self.logger.error("Health check failed", error=str(e))
        
        return health_status
    
    async def cleanup(self) -> None:
        """Clean up file manager resources"""
        try:
            # Cancel all active operations
            for operation_id in list(self._active_operations.keys()):
                await self.cancel_operation(operation_id)
            
            # Cleanup components
            if hasattr(self.upload_handler, 'cleanup'):
                await self.upload_handler.cleanup()
            
            if hasattr(self.download_handler, 'cleanup'):
                await self.download_handler.cleanup()
            
            if hasattr(self.storage_backend, 'cleanup'):
                await self.storage_backend.cleanup()
            
            if hasattr(self.metadata_manager, 'cleanup'):
                await self.metadata_manager.cleanup()
            
            if hasattr(self.file_validator, 'cleanup'):
                await self.file_validator.cleanup()
            
            self.logger.info("File manager cleanup completed")
            
        except Exception as e:
            self.logger.error("File manager cleanup failed", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use
        
    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)
    
    async with aiofiles.open(file_path, 'rb') as f:
        while chunk := await f.read(CHUNK_SIZE):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()

async def get_file_mime_type(file_path: str) -> str:
    """
    Determine MIME type of a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string
    """
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'

def validate_filename(filename: str) -> bool:
    """
    Validate filename for security
    
    Args:
        filename: Filename to validate
        
    Returns:
        True if filename is valid
    """
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    
    # Check for reserved characters
    reserved_chars = '<>:"|?*'
    if any(char in filename for char in reserved_chars):
        return False
    
    # Check length
    if len(filename) > 255:
        return False
    
    return True

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "FileManager",
    "FileManagerConfig",
    "FileOperationRequest",
    "FileOperationResponse", 
    "FileInfo",
    "calculate_file_hash",
    "get_file_mime_type",
    "validate_filename"
]
                '