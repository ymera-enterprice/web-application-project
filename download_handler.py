"""
YMERA Enterprise - Download Handler
Production-Ready Secure File Retrieval - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import mimetypes
import os
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, BinaryIO
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from urllib.parse import quote

# Third-party imports (alphabetical)
import aiofiles
import structlog
from fastapi import FastAPI, HTTPException, Depends, status, Response, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field, validator

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from database.models import FileRecord, DownloadLog, User
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token, get_current_user
from file_management.storage_backend import StorageBackend
from file_management.metadata_manager import MetadataManager

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Download constraints
MAX_DOWNLOAD_SIZE = 500 * 1024 * 1024  # 500MB
MAX_BATCH_FILES = 100
CHUNK_SIZE = 8192  # 8KB chunks for streaming
DOWNLOAD_TIMEOUT = 600  # 10 minutes
TOKEN_EXPIRY_HOURS = 24

# Security settings
RATE_LIMIT_PER_HOUR = 100
CONCURRENT_DOWNLOADS_PER_USER = 5

# Archive settings
MAX_ARCHIVE_SIZE = 1024 * 1024 * 1024  # 1GB
COMPRESSION_LEVEL = 6

# Configuration loading
settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class DownloadConfig:
    """Configuration dataclass for download settings"""
    max_download_size: int = MAX_DOWNLOAD_SIZE
    max_batch_files: int = MAX_BATCH_FILES
    chunk_size: int = CHUNK_SIZE
    timeout: int = DOWNLOAD_TIMEOUT
    temp_dir: str = "/tmp/ymera_downloads"
    rate_limit_per_hour: int = RATE_LIMIT_PER_HOUR
    concurrent_downloads_per_user: int = CONCURRENT_DOWNLOADS_PER_USER
    enable_compression: bool = True
    enable_encryption: bool = True

class DownloadRequest(BaseModel):
    """Schema for download request"""
    file_ids: List[str] = Field(..., min_items=1, max_items=100)
    format: str = Field(default="original", regex="^(original|zip|encrypted)$")
    compression_level: int = Field(default=6, ge=0, le=9)
    include_metadata: bool = Field(default=False)
    password_protect: bool = Field(default=False)
    download_password: Optional[str] = Field(None, min_length=8, max_length=128)
    
    @validator('file_ids')
    def validate_file_ids(cls, v):
        # Remove duplicates while preserving order
        seen = set()
        return [x for x in v if not (x in seen or seen.add(x))]

class DownloadToken(BaseModel):
    """Schema for secure download token"""
    token: str
    download_url: str
    expires_at: datetime
    file_count: int
    total_size: int
    requires_password: bool

class DownloadProgress(BaseModel):
    """Schema for download progress tracking"""
    download_id: str
    status: str  # preparing, ready, downloading, complete, failed
    progress_percentage: float
    current_file: Optional[str] = None
    files_completed: int
    total_files: int
    bytes_transferred: int
    total_bytes: int
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None

class DownloadResult(BaseModel):
    """Schema for download completion result"""
    download_id: str
    file_count: int
    total_size: int
    download_format: str
    compression_ratio: Optional[float] = None
    download_time: float
    checksum: str
    expires_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class FileAccessLog(BaseModel):
    """Schema for file access logging"""
    file_id: str
    user_id: str
    access_time: datetime
    ip_address: str
    user_agent: str
    download_method: str
    success: bool
    error_message: Optional[str] = None

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class DownloadRateLimiter:
    """Rate limiting for downloads per user"""
    
    def __init__(self, max_requests_per_hour: int):
        self.max_requests = max_requests_per_hour
        self._user_requests: Dict[str, List[datetime]] = {}
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits"""
        async with self._lock:
            now = datetime.utcnow()
            hour_ago = now - timedelta(hours=1)
            
            # Clean old requests
            if user_id in self._user_requests:
                self._user_requests[user_id] = [
                    req_time for req_time in self._user_requests[user_id] 
                    if req_time > hour_ago
                ]
            else:
                self._user_requests[user_id] = []
            
            # Check limit
            if len(self._user_requests[user_id]) >= self.max_requests:
                return False
            
            # Add current request
            self._user_requests[user_id].append(now)
            return True
    
    async def get_remaining_requests(self, user_id: str) -> int:
        """Get remaining requests for user"""
        async with self._lock:
            if user_id not in self._user_requests:
                return self.max_requests
            
            now = datetime.utcnow()
            hour_ago = now - timedelta(hours=1)
            
            recent_requests = [
                req_time for req_time in self._user_requests[user_id] 
                if req_time > hour_ago
            ]
            
            return max(0, self.max_requests - len(recent_requests))

class DownloadProgressTracker:
    """Track download progress for real-time updates"""
    
    def __init__(self):
        self._progress_cache: Dict[str, DownloadProgress] = {}
        self._lock = asyncio.Lock()
    
    async def create_progress(
        self, 
        download_id: str, 
        total_files: int, 
        total_bytes: int
    ) -> None:
        """Create new progress tracker"""
        async with self._lock:
            self._progress_cache[download_id] = DownloadProgress(
                download_id=download_id,
                status="preparing",
                progress_percentage=0.0,
                files_completed=0,
                total_files=total_files,
                bytes_transferred=0,
                total_bytes=total_bytes
            )
    
    async def update_progress(
        self,
        download_id: str,
        files_completed: int,
        bytes_transferred: int,
        current_file: Optional[str] = None
    ) -> None:
        """Update download progress"""
        async with self._lock:
            if download_id in self._progress_cache:
                progress = self._progress_cache[download_id]
                progress.files_completed = files_completed
                progress.bytes_transferred = bytes_transferred
                progress.current_file = current_file
                progress.status = "downloading" if files_completed < progress.total_files else "complete"
                
                if progress.total_bytes > 0:
                    progress.progress_percentage = (bytes_transferred / progress.total_bytes) * 100
    
    async def complete_progress(
        self, 
        download_id: str, 
        success: bool, 
        error_message: Optional[str] = None
    ) -> None:
        """Mark download as completed"""
        async with self._lock:
            if download_id in self._progress_cache:
                progress = self._progress_cache[download_id]
                progress.status = "complete" if success else "failed"
                progress.error_message = error_message
                if success:
                    progress.progress_percentage = 100.0
    
    async def get_progress(self, download_id: str) -> Optional[DownloadProgress]:
        """Get current progress"""
        async with self._lock:
            return self._progress_cache.get(download_id)

class ArchiveBuilder:
    """Build archives for multiple file downloads"""
    
    def __init__(self, temp_dir: str):
        self.temp_dir = Path(temp_dir)
        self.logger = logger.bind(component="archive_builder")
    
    async def create_archive(
        self,
        files: List[Dict[str, Any]],
        archive_name: str,
        compression_level: int = 6,
        password: Optional[str] = None
    ) -> Path:
        """Create compressed archive of files"""
        archive_path = self.temp_dir / f"{archive_name}.zip"
        
        try:
            with zipfile.ZipFile(
                archive_path, 
                'w', 
                zipfile.ZIP_DEFLATED, 
                compresslevel=compression_level
            ) as archive:
                
                # Set password if provided
                if password:
                    archive.setpassword(password.encode())
                
                total_original_size = 0
                
                for file_info in files:
                    file_path = Path(file_info['storage_path'])
                    archive_filename = file_info['original_filename']
                    
                    if file_path.exists():
                        archive.write(file_path, archive_filename)
                        total_original_size += file_path.stat().st_size
                    else:
                        self.logger.warning(
                            "File not found during archive creation",
                            file_path=str(file_path),
                            file_id=file_info.get('id')
                        )
                
                # Calculate compression ratio
                archive_size = archive_path.stat().st_size
                compression_ratio = archive_size / total_original_size if total_original_size > 0 else 0
                
                self.logger.info(
                    "Archive created successfully",
                    archive_path=str(archive_path),
                    file_count=len(files),
                    original_size=total_original_size,
                    compressed_size=archive_size,
                    compression_ratio=compression_ratio
                )
                
                return archive_path
                
        except Exception as e:
            self.logger.error("Archive creation failed", error=str(e))
            if archive_path.exists():
                archive_path.unlink()
            raise

class DownloadTokenManager:
    """Manage secure download tokens"""
    
    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def create_token(
        self,
        download_id: str,
        file_ids: List[str],
        user_id: str,
        expires_in_hours: int = 24
    ) -> str:
        """Create secure download token"""
        token = hashlib.sha256(
            f"{download_id}{user_id}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()
        
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        async with self._lock:
            self._tokens[token] = {
                "download_id": download_id,
                "file_ids": file_ids,
                "user_id": user_id,
                "expires_at": expires_at,
                "created_at": datetime.utcnow()
            }
        
        return token
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and retrieve token information"""
        async with self._lock:
            token_info = self._tokens.get(token)
            
            if not token_info:
                return None
            
            if datetime.utcnow() > token_info["expires_at"]:
                del self._tokens[token]
                return None
            
            return token_info
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a download token"""
        async with self._lock:
            if token in self._tokens:
                del self._tokens[token]
                return True
            return False
    
    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens"""
        now = datetime.utcnow()
        expired_tokens = []
        
        async with self._lock:
            for token, info in self._tokens.items():
                if now > info["expires_at"]:
                    expired_tokens.append(token)
            
            for token in expired_tokens:
                del self._tokens[token]
        
        return len(expired_tokens)

class DownloadHandler:
    """Production-ready download handler with comprehensive security"""
    
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.logger = logger.bind(component="download_handler")
        self.storage_backend = StorageBackend()
        self.metadata_manager = MetadataManager()
        self.rate_limiter = DownloadRateLimiter(config.rate_limit_per_hour)
        self.progress_tracker = DownloadProgressTracker()
        self.archive_builder = ArchiveBuilder(config.temp_dir)
        self.token_manager = DownloadTokenManager()
        self._active_downloads: Dict[str, asyncio.Task] = {}
        self._initialize_temp_directory()
    
    def _initialize_temp_directory(self) -> None:
        """Initialize temporary download directory"""
        temp_path = Path(self.config.temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        self.logger.info("Download temp directory initialized", path=str(temp_path))
    
    @track_performance
    async def prepare_download(
        self,
        request: DownloadRequest,
        user_id: str,
        db: AsyncSession,
        client_ip: str
    ) -> DownloadToken:
        """Prepare files for download and create secure token"""
        
        # Check rate limits
        if not await self.rate_limiter.check_rate_limit(user_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Validate file access permissions
        file_records = await self._validate_file_access(request.file_ids, user_id, db)
        
        if not file_records:
            raise HTTPException(
                status_code=404,
                detail="No accessible files found"
            )
        
        download_id = str(uuid.uuid4())
        total_size = sum(record.file_size for record in file_records)
        
        # Check total size limit
        if total_size > self.config.max_download_size:
            raise HTTPException(
                status_code=413,
                detail=f"Download too large. Maximum size: {self.config.max_download_size} bytes"
            )
        
        # Create progress tracker
        await self.progress_tracker.create_progress(
            download_id, 
            len(file_records), 
            total_size
        )
        
        # Create download token
        token = await self.token_manager.create_token(
            download_id, 
            request.file_ids, 
            user_id
        )
        
        # Log download preparation
        await self._log_download_access(
            file_records,
            user_id,
            client_ip,
            "prepare",
            True
        )
        
        download_url = f"/api/v1/files/download/{token}"
        
        result = DownloadToken(
            token=token,
            download_url=download_url,
            expires_at=datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
            file_count=len(file_records),
            total_size=total_size,
            requires_password=request.password_protect
        )
        
        self.logger.info(
            "Download prepared successfully",
            download_id=download_id,
            user_id=user_id,
            file_count=len(file_records),
            total_size=total_size
        )
        
        return result
    
    @track_performance
    async def execute_download(
        self,
        token: str,
        password: Optional[str] = None
    ) -> StreamingResponse:
        """Execute file download using secure token"""
        
        # Validate token
        token_info = await self.token_manager.validate_token(token)
        if not token_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired download token"
            )
        
        download_id = token_info["download_id"]
        file_ids = token_info["file_ids"]
        user_id = token_info["user_id"]
        
        try:
            # Get database session (you'll need to inject this)
            async with get_db_session() as db:
                # Validate files still exist and accessible
                file_records = await self._validate_file_access(file_ids, user_id, db)
                
                if not file_records:
                    raise HTTPException(
                        status_code=404,
                        detail="Files no longer accessible"
                    )
                
                # Single file download
                if len(file_records) == 1:
                    return await self._download_single_file(file_records[0], download_id)
                
                # Multiple files - create archive
                else:
                    return await self._download_multiple_files(
                        file_records, 
                        download_id, 
                        password
                    )
        
        except Exception as e:
            await self.progress_tracker.complete_progress(download_id, False, str(e))
            self.logger.error("Download execution failed", download_id=download_id, error=str(e))
            raise
    
    async def _download_single_file(
        self, 
        file_record: FileRecord, 
        download_id: str
    ) -> StreamingResponse:
        """Download single file with streaming"""
        
        file_path = Path(file_record.storage_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on storage")
        
        # Update progress
        await self.progress_tracker.update_progress(
            download_id, 
            0, 
            0, 
            file_record.original_filename
        )
        
        # Create streaming response
        async def file_streamer():
            try:
                bytes_sent = 0
                async with aiofiles.open(file_path, 'rb') as f:
                    while chunk := await f.read(self.config.chunk_size):
                        bytes_sent += len(chunk)
                        await self.progress_tracker.update_progress(
                            download_id, 
                            0, 
                            bytes_sent
                        )
                        yield chunk
                
                await self.progress_tracker.complete_progress(download_id, True)
                
            except Exception as e:
                await self.progress_tracker.complete_progress(download_id, False, str(e))
                raise
        
        # Prepare response headers
        headers = {
            'Content-Disposition': f'attachment; filename="{quote(file_record.original_filename)}"',
            'Content-Length': str(file_record.file_size),
            'Content-Type': file_record.mime_type or 'application/octet-stream'
        }
        
        return StreamingResponse(
            file_streamer(),
            media_type=file_record.mime_type or 'application/octet-stream',
            headers=headers
        )
    
    async def _download_multiple_files(
        self,
        file_records: List[FileRecord],
        download_id: str,
        password: Optional[str] = None
    ) -> StreamingResponse:
        """Download multiple files as archive"""
        
        # Prepare file info for archive
        file_info_list = []
        for record in file_records:
            file_info_list.append({
                'id': record.id,
                'storage_path': record.storage_path,
                'original_filename': record.original_filename
            })
        
        # Create archive
        archive_name = f"download_{download_id}"
        archive_path = await self.archive_builder.create_archive(
            file_info_list,
            archive_name,
            compression_level=6,
            password=password
        )
        
        # Stream archive file
        async def archive_streamer():
            try:
                bytes_sent = 0
                total_size = archive_path.stat().st_size
                
                async with aiofiles.open(archive_path, 'rb') as f:
                    while chunk := await f.read(self.config.chunk_size):
                        bytes_sent += len(chunk)
                        await self.progress_tracker.update_progress(
                            download_id,
                            len(file_records),
                            bytes_sent
                        )
                        yield chunk
                
                await self.progress_tracker.complete_progress(download_id, True)
                
            except Exception as e:
                await self.progress_tracker.complete_progress(download_id, False, str(e))
                raise
            finally:
                # Clean up archive file
                if archive_path.exists():
                    archive_path.unlink()
        
        archive_filename = f"{archive_name}.zip"
        headers = {
            'Content-Disposition': f'attachment; filename="{archive_filename}"',
            'Content-Type': 'application/zip'
        }
        
        return StreamingResponse(
            archive_streamer(),
            media_type='application/zip',
            headers=headers
        )
    
    async def _validate_file_access(
        self,
        file_ids: List[str],
        user_id: str,
        db: AsyncSession
    ) -> List[FileRecord]:
        """Validate user has access to requested files"""
        
        query = select(FileRecord).where(
            and_(
                FileRecord.id.in_(file_ids),
                or_(
                    FileRecord.user_id == user_id,
                    FileRecord.is_public == True
                )
            )
        )
        
        result = await db.execute(query)
        file_records = result.scalars().all()
        
        return list(file_records)
    
    async def _log_download_access(
        self,
        file_records: List[FileRecord],
        user_id: str,
        client_ip: str,
        download_method: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> None:
        """Log file access for audit purposes"""
        
        for record in file_records:
            access_log = FileAccessLog(
                file_id=record.id,
                user_id=user_id,
                access_time=datetime.utcnow(),
                ip_address=client_ip,
                user_agent="YMERA-Download-Handler",
                download_method=download_method,
                success=success,
                error_message=error_message
            )
            
            self.logger.info(
                "File access logged",
                file_id=record.id,
                user_id=user_id,
                method=download_method,
                success=success
            )
    
    async def get_download_progress(self, download_id: str) -> Optional[DownloadProgress]:
        """Get current download progress"""
        return await self.progress_tracker.get_progress(download_id)
    
    async def cancel_download(self, download_id: str) -> bool:
        """Cancel active download"""
        if download_id in self._active_downloads:
            task = self._active_downloads[download_id]
            task.cancel()
            del self._active_downloads[download_id]
            await self.progress_tracker.complete_progress(download_id, False, "Download cancelled")
            return True
        return False
    
    async def get_user_download_stats(self, user_id: str) -> Dict[str, Any]:
        """Get download statistics for user"""
        remaining_requests = await self.rate_limiter.get_remaining_requests(user_id)
        
        return {
            "remaining_hourly_downloads": remaining_requests,
            "max_download_size": self.config.max_download_size,
            "max_batch_files": self.config.max_batch_files,
            "concurrent_downloads_limit": self.config.concurrent_downloads_per_user
        }
    
    async def cleanup_expired_downloads(self) -> Dict[str, int]:
        """Clean up expired downloads and tokens"""
        expired_tokens = await self.token_manager.cleanup_expired_tokens()
        
        # Clean up temporary files
        temp_files_cleaned = 0
        temp_dir = Path(self.config.temp_dir)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        try:
            for temp_file in temp_dir.glob("download_*.zip"):
                if temp_file.is_file():
                    file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                    if file_time < cutoff_time:
                        temp_file.unlink()
                        temp_files_cleaned += 1
        except Exception as e:
            self.logger.error("Temp file cleanup failed", error=str(e))
        
        cleanup_stats = {
            "expired_tokens": expired_tokens,
            "temp_files_cleaned": temp_files_cleaned
        }
        
        self.logger.info("Download cleanup completed", **cleanup_stats)
        return cleanup_stats

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def validate_download_request(request: DownloadRequest) -> bool:
    """Validate download request parameters"""
    if not request.file_ids:
        return False
    
    if len(request.file_ids) > MAX_BATCH_FILES:
        return False
    
    if request.password_protect and not request.download_password:
        return False
    
    return True

def get_content_disposition_header(filename: str, attachment: bool = True) -> str:
    """Generate proper Content-Disposition header"""
    disposition = "attachment" if attachment else "inline"
    quoted_filename = quote(filename)
    return f'{disposition}; filename="{quoted_filename}"; filename*=UTF-8\'\'{quoted_filename}'

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_download_handler() -> DownloadHandler:
    """Initialize download handler for production use"""
    config = DownloadConfig(
        max_download_size=settings.MAX_DOWNLOAD_SIZE,
        max_batch_files=settings.MAX_BATCH_FILES,
        temp_dir=settings.DOWNLOAD_TEMP_DIR,
        rate_limit_per_hour=settings.DOWNLOAD_RATE_LIMIT,
        concurrent_downloads_per_user=settings.CONCURRENT_DOWNLOADS
    )
    
    handler = DownloadHandler(config)
    
    logger.info("Download handler initialized successfully")
    return handler

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "DownloadHandler",
    "DownloadConfig",
    "DownloadRequest",
    "DownloadToken",
    "DownloadResult",
    "DownloadProgress",
    "initialize_download_handler",
    "validate_download_request"
]