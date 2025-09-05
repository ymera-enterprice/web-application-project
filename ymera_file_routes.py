            # Apply filters
            if search_params.query:
                query = query.where(
                    FileRecord.original_filename.contains(search_params.query) |
                    FileRecord.description.contains(search_params.query)
                )
            
            if search_params.file_type:
                query = query.where(FileRecord.file_type == search_params.file_type)
            
            if search_params.status:
                query = query.where(FileRecord.status == search_params.status)
            
            if search_params.tags:
                for tag in search_params.tags:
                    query = query.where(FileRecord.tags.contains([tag]))
            
            if search_params.date_from:
                query = query.where(FileRecord.created_at >= search_params.date_from)
            
            if search_params.date_to:
                query = query.where(FileRecord.created_at <= search_params.date_to)
            
            # Get total count
            count_query = query.with_only_columns([FileRecord.id])
            count_result = await db.execute(count_query)
            total_files = len(count_result.fetchall())
            
            # Apply pagination and ordering
            query = query.order_by(FileRecord.created_at.desc())
            query = query.offset(search_params.offset).limit(search_params.limit)
            
            # Execute query
            result = await db.execute(query)
            files = result.scalars().all()
            
            # Convert to response format
            file_responses = []
            for file_record in files:
                file_responses.append(FileResponse(
                    id=file_record.id,
                    filename=file_record.filename,
                    original_filename=file_record.original_filename,
                    file_type=file_record.file_type.value,
                    file_size=file_record.file_size,
                    mime_type=file_record.mime_type,
                    description=file_record.description,
                    tags=file_record.tags,
                    status=file_record.status.value,
                    is_private=file_record.is_private,
                    processing_status=file_record.processing_status,
                    processing_result=file_record.processing_result,
                    download_count=file_record.download_count,
                    created_at=file_record.created_at,
                    updated_at=file_record.updated_at,
                    expires_at=file_record.expires_at
                ))
            
            return {
                "files": file_responses,
                "pagination": {
                    "total": total_files,
                    "limit": search_params.limit,
                    "offset": search_params.offset,
                    "has_more": search_params.offset + len(files) < total_files
                }
            }
            
        except Exception as e:
            self.logger.error("File search failed", error=str(e), user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File search failed"
            )
    
    async def delete_file(
        self,
        file_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Delete file with cleanup and verification.
        
        Args:
            file_id: File identifier
            user_id: Owner user ID
            db: Database session
            
        Returns:
            Deletion confirmation
        """
        try:
            # Get file record
            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.id == file_id,
                    FileRecord.user_id == user_id,
                    FileRecord.status != FileStatus.DELETED
                )
            )
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            
            # Mark as deleted in database
            file_record.status = FileStatus.DELETED
            file_record.deleted_at = datetime.utcnow()
            await db.commit()
            
            # Schedule physical deletion
            await self._schedule_file_cleanup(file_record)
            
            self.logger.info("File deleted successfully", file_id=file_id, user_id=user_id)
            
            return {
                "message": "File deleted successfully",
                "file_id": file_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            self.logger.error("File deletion failed", error=str(e), file_id=file_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File deletion failed"
            )
    
    async def process_bulk_operation(
        self,
        operation_data: BulkOperation,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Process bulk file operations.
        
        Args:
            operation_data: Bulk operation data
            user_id: User ID
            db: Database session
            
        Returns:
            Operation results
        """
        try:
            # Verify file ownership
            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.id.in_(operation_data.file_ids),
                    FileRecord.user_id == user_id,
                    FileRecord.status != FileStatus.DELETED
                )
            )
            files = result.scalars().all()
            
            if len(files) != len(operation_data.file_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Some files not found or not accessible"
                )
            
            results = {
                "operation": operation_data.operation,
                "total_files": len(files),
                "successful": 0,
                "failed": 0,
                "errors": []
            }
            
            # Process each file
            for file_record in files:
                try:
                    if operation_data.operation == "delete":
                        file_record.status = FileStatus.DELETED
                        file_record.deleted_at = datetime.utcnow()
                        await self._schedule_file_cleanup(file_record)
                    
                    elif operation_data.operation == "update_tags":
                        new_tags = operation_data.parameters.get("tags", [])
                        file_record.tags = new_tags
                        file_record.updated_at = datetime.utcnow()
                    
                    elif operation_data.operation == "update_privacy":
                        is_private = operation_data.parameters.get("is_private", True)
                        file_record.is_private = is_private
                        file_record.updated_at = datetime.utcnow()
                    
                    elif operation_data.operation == "process":
                        processing_type = operation_data.parameters.get("processing_type")
                        if processing_type:
                            await self._start_file_processing(file_record, processing_type)
                    
                    else:
                        raise ValueError(f"Unknown operation: {operation_data.operation}")
                    
                    results["successful"] += 1
                    
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "file_id": file_record.id,
                        "error": str(e)
                    })
            
            await db.commit()
            
            self.logger.info(
                "Bulk operation completed",
                operation=operation_data.operation,
                total_files=results["total_files"],
                successful=results["successful"],
                failed=results["failed"]
            )
            
            return results
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            self.logger.error("Bulk operation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bulk operation failed"
            )
    
    async def _validate_file(self, file: UploadFile, user_id: str, db: AsyncSession):
        """Validate uploaded file"""
        # Check file size
        if file.size > self.config.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of {self.config.max_file_size} bytes"
            )
        
        # Check file extension
        file_extension = Path(file.filename).suffix.lower().lstrip('.')
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type '{file_extension}' is not allowed"
            )
        
        # Check user file limit
        result = await db.execute(
            select(FileRecord).where(
                FileRecord.user_id == user_id,
                FileRecord.status != FileStatus.DELETED
            )
        )
        user_files = result.scalars().all()
        
        if len(user_files) >= self.config.max_files_per_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {self.config.max_files_per_user} files per user exceeded"
            )
    
    async def _save_file_temporarily(self, file: UploadFile, temp_path: Path):
        """Save uploaded file to temporary location"""
        async with aiofiles.open(temp_path, 'wb') as f:
            while chunk := await file.read(CHUNK_SIZE):
                await f.write(chunk)
    
    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(CHUNK_SIZE):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _determine_file_type(self, extension: str, mime_type: str) -> FileType:
        """Determine file type based on extension and MIME type"""
        if extension in {'txt', 'md', 'json', 'xml', 'csv', 'html', 'css', 'js'}:
            return FileType.TEXT
        elif extension in {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx'}:
            return FileType.DOCUMENT
        elif extension in {'jpg', 'jpeg', 'png', 'gif', 'svg', 'bmp'}:
            return FileType.IMAGE
        elif extension in {'mp4', 'avi', 'mov', 'wmv', 'flv'}:
            return FileType.VIDEO
        elif extension in {'mp3', 'wav', 'flac', 'aac'}:
            return FileType.AUDIO
        elif extension in {'zip', 'rar', '7z', 'tar', 'gz'}:
            return FileType.ARCHIVE
        elif extension in {'py', 'java', 'cpp', 'c', 'h', 'cs', 'php', 'rb'}:
            return FileType.CODE
        else:
            return FileType.OTHER
    
    async def _start_file_processing(self, file_record: FileRecord, processing_type: str):
        """Start asynchronous file processing"""
        try:
            file_path = self._storage_path / file_record.filename
            
            # Update processing status
            file_record.processing_status = "processing"
            
            # Queue processing task
            processing_task = {
                "file_id": file_record.id,
                "file_path": str(file_path),
                "processing_type": processing_type,
                "user_id": file_record.user_id
            }
            
            await self._redis_client.lpush(
                "file_processing_queue",
                json.dumps(processing_task)
            )
            
            self.logger.info(
                "File processing queued",
                file_id=file_record.id,
                processing_type=processing_type
            )
            
        except Exception as e:
            self.logger.error("Failed to start file processing", error=str(e))
    
    async def _schedule_file_cleanup(self, file_record: FileRecord):
        """Schedule physical file deletion"""
        try:
            cleanup_task = {
                "file_id": file_record.id,
                "filename": file_record.filename,
                "cloud_url": file_record.cloud_url,
                "scheduled_at": datetime.utcnow().isoformat()
            }
            
            # Schedule cleanup for 24 hours later
            await self._redis_client.zadd(
                "file_cleanup_queue",
                {json.dumps(cleanup_task): datetime.utcnow().timestamp() + 86400}
            )
            
        except Exception as e:
            self.logger.error("Failed to schedule file cleanup", error=str(e))

# ===============================================================================
# ROUTER SETUP
# ===============================================================================

router = APIRouter()

# Initialize file manager
file_config = FileConfig(
    max_file_size=settings.MAX_FILE_SIZE,
    max_files_per_user=settings.MAX_FILES_PER_USER,
    virus_scanning_enabled=settings.VIRUS_SCANNING_ENABLED,
    encryption_enabled=settings.FILE_ENCRYPTION_ENABLED,
    cloud_storage_enabled=settings.CLOUD_STORAGE_ENABLED
)

file_manager = FileManager(file_config)

# ===============================================================================
# ROUTE HANDLERS
# ===============================================================================

@router.on_event("startup")
async def startup_event():
    """Initialize file manager on startup"""
    await file_manager.initialize()

@router.post("/upload", response_model=FileResponse)
@track_performance
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: str = Form("[]"),  # JSON string of tags
    processing_type: ProcessingType = Form(ProcessingType.NONE),
    is_private: bool = Form(True),
    expires_at: Optional[str] = Form(None),  # ISO format datetime string
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> FileResponse:
    """
    Upload a file with metadata and optional processing.
    
    Supports comprehensive file validation, virus scanning,
    encryption, and automatic processing based on file type.
    """
    try:
        # Parse form data
        import json
        parsed_tags = json.loads(tags) if tags else []
        parsed_expires_at = None
        if expires_at:
            parsed_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        metadata = FileUploadRequest(
            description=description,
            tags=parsed_tags,
            processing_type=processing_type,
            is_private=is_private,
            expires_at=parsed_expires_at
        )
        
        return await file_manager.upload_file(file, metadata, current_user.id, db)
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tags format"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=Dict[str, Any])
@track_performance
async def list_files(
    limit: int = 50,
    offset: int = 0,
    file_type: Optional[FileType] = None,
    status: Optional[FileStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    List user files with pagination and filtering.
    
    Returns paginated list of files with comprehensive metadata
    and filtering options by type, status, and date ranges.
    """
    search_params = FileSearchRequest(
        file_type=file_type,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return await file_manager.search_files(search_params, current_user.id, db)

@router.post("/search", response_model=Dict[str, Any])
@track_performance
async def search_files(
    search_params: FileSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Advanced file search with multiple filters.
    
    Supports full-text search, tag filtering, date ranges,
    and comprehensive file metadata searching.
    """
    return await file_manager.search_files(search_params, current_user.id, db)

@router.get("/{file_id}", response_model=FileResponse)
@track_performance
async def get_file_info(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> FileResponse:
    """
    Get detailed file information.
    
    Returns comprehensive file metadata including processing status,
    download statistics, and access information.
    """
    try:
        result = await db.execute(
            select(FileRecord).where(
                FileRecord.id == file_id,
                FileRecord.user_id == current_user.id,
                FileRecord.status != FileStatus.DELETED
            )
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return FileResponse(
            id=file_record.id,
            filename=file_record.filename,
            original_filename=file_record.original_filename,
            file_type=file_record.file_type.value,
            file_size=file_record.file_size,
            mime_type=file_record.mime_type,
            description=file_record.description,
            tags=file_record.tags,
            status=file_record.status.value,
            is_private=file_record.is_private,
            processing_status=file_record.processing_status,
            processing_result=file_record.processing_result,
            download_count=file_record.download_count,
            created_at=file_record.created_at,
            updated_at=file_record.updated_at,
            expires_at=file_record.expires_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get file info", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file information"
        )

@router.get("/{file_id}/download")
@track_performance
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Download a file with access control and tracking.
    
    Provides secure file download with access verification,
    download tracking, and support for resumable downloads.
    """
    try:
        file_path = await file_manager.download_file(file_id, current_user.id, db)
        
        # Get file record for headers
        result = await db.execute(
            select(FileRecord).where(FileRecord.id == file_id)
        )
        file_record = result.scalar_one()
        
        return FileResponse(
            path=file_path,
            filename=file_record.original_filename,
            media_type=file_record.mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={file_record.original_filename}",
                "Content-Length": str(file_record.file_size)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("File download failed", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File download failed"
        )

@router.get("/{file_id}/stream")
@track_performance
async def stream_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Stream a file for media playback.
    
    Provides streaming access for audio/video files with
    range request support and bandwidth optimization.
    """
    try:
        file_path = await file_manager.download_file(file_id, current_user.id, db)
        
        # Get file record
        result = await db.execute(
            select(FileRecord).where(FileRecord.id == file_id)
        )
        file_record = result.scalar_one()
        
        # Check if file type supports streaming
        if file_record.file_type not in [FileType.VIDEO, FileType.AUDIO]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File type does not support streaming"
            )
        
        async def file_stream():
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(CHUNK_SIZE):
                    yield chunk
        
        return StreamingResponse(
            file_stream(),
            media_type=file_record.mime_type,
            headers={
                "Content-Length": str(file_record.file_size),
                "Accept-Ranges": "bytes"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("File streaming failed", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File streaming failed"
        )

@router.put("/{file_id}", response_model=FileResponse)
@track_performance
async def update_file_metadata(
    file_id: str,
    metadata: FileUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> FileResponse:
    """
    Update file metadata.
    
    Allows updating file description, tags, privacy settings,
    and other metadata without re-uploading the file.
    """
    try:
        result = await db.execute(
            select(FileRecord).where(
                FileRecord.id == file_id,
                FileRecord.user_id == current_user.id,
                FileRecord.status != FileStatus.DELETED
            )
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Update metadata
        if metadata.description is not None:
            file_record.description = metadata.description
        if metadata.tags:
            file_record.tags = metadata.tags
        if metadata.is_private is not None:
            file_record.is_private = metadata.is_private
        if metadata.expires_at is not None:
            file_record.expires_at = metadata.expires_at
        
        file_record.updated_at = datetime.utcnow()
        await db.commit()
        
        logger.info("File metadata updated", file_id=file_id, user_id=current_user.id)
        
        return FileResponse(
            id=file_record.id,
            filename=file_record.filename,
            original_filename=file_record.original_filename,
            file_type=file_record.file_type.value,
            file_size=file_record.file_size,
            mime_type=file_record.mime_type,
            description=file_record.description,
            tags=file_record.tags,
            status=file_record.status.value,
            is_private=file_record.is_private,
            processing_status=file_record.processing_status,
            processing_result=file_record.processing_result,
            download_count=file_record.download_count,
            created_at=file_record.created_at,
            updated_at=file_record.updated_at,
            expires_at=file_record.expires_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("File metadata update failed", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File metadata update failed"
        )

@router.delete("/{file_id}")
@track_performance
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Delete a file.
    
    Safely deletes a file with proper cleanup of storage,
    database records, and associated processing data.
    """
    return await file_manager.delete_file(file_id, current_user.id, db)

@router.post("/bulk", response_model=Dict[str, Any])
@track_performance
async def bulk_file_operation(
    operation_data: BulkOperation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Perform bulk operations on multiple files.
    
    Supports bulk delete, tag updates, privacy changes,
    and processing operations on multiple files simultaneously.
    """
    return await file_manager.process_bulk_operation(operation_data, current_user.id, db)

@router.post("/{file_id}/process")
@track_performance
async def trigger_file_processing(
    file_id: str,
    processing_type: ProcessingType,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Trigger file processing.
    
    Initiates specific processing operations on a file
    such as text extraction, image analysis, or document parsing.
    """
    try:
        result = await db.execute(
            select(FileRecord).where(
                FileRecord.id == file_id,
                FileRecord.user_id == current_user.id,
                FileRecord.status == FileStatus.READY
            )
        )
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or not ready for processing"
            )
        
        # Start processing
        await file_manager._start_file_processing(file_record, processing_type.value)
        
        # Update database
        file_record.processing_status = "queued"
        file_record.updated_at = datetime.utcnow()
        await db.commit()
        
        return {
            "message": "File processing initiated",
            "file_id": file_id,
            "processing_type": processing_type.value,
            "status": "queued"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger file processing", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger file processing"
        )

@router.get("/stats/overview")
@track_performance
async def get_file_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get comprehensive file statistics.
    
    Returns detailed analytics about user's files including
    storage usage, file type distribution, and activity metrics.
    """
    try:
        # Get all user files
        result = await db.execute(
            select(FileRecord).where(
                FileRecord.user_id == current_user.id,
                FileRecord.status != FileStatus.DELETED
            )
        )
        files = result.scalars().all()
        
        # Calculate statistics
        total_files = len(files)
        total_size = sum(f.file_size for f in files)
        
        # File type distribution
        type_distribution = {}
        for file_record in files:
            file_type = file_record.file_type.value
            type_distribution[file_type] = type_distribution.get(file_type, 0) + 1
        
        # Status distribution
        status_distribution = {}
        for file_record in files:
            status = file_record.status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Recent activity
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_uploads = len([f for f in files if f.created_at > yesterday])
        
        # Most downloaded files
        top_downloads = sorted(files, key=lambda f: f.download_count, reverse=True)[:5]
        
        return {
            "summary": {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "storage_limit_mb": file_config.max_file_size / (1024 * 1024),
                "file_limit": file_config.max_files_per_user
            },
            "distributions": {
                "by_type": type_distribution,
                "by_status": status_distribution
            },
            "activity": {
                "uploads_last_24h": recent_uploads,
                "total_downloads": sum(f.download_count for f in files)
            },
            "top_downloads": [
                {
                    "file_id": f.id,
                    "filename": f.original_filename,
                    "download_count": f.download_count
                }
                for f in top_downloads
            ]
        }
        
    except Exception as e:
        logger.error("Failed to get file statistics", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file statistics"
        )

@router.get("/health")
async def files_health_check() -> Dict[str, Any]:
    """File system health check"""
    try:
        
        # Check Redis connectivity
        redis_status = "healthy"
        try:
            await file_manager._redis_client.ping()
        except Exception:
            redis_status = "unhealthy"
        
        # Check cloud storage if enabled
        cloud_status = "disabled"
        if file_config.cloud_storage_enabled:
            try:
                await file_manager._cloud_storage.health_check()
                cloud_status = "healthy"
            except Exception:
                cloud_status = "unhealthy"
        
        # Check virus scanner if enabled
        virus_scanner_status = "disabled"
        if file_config.virus_scanning_enabled:
            try:
                await file_manager._virus_scanner.health_check()
                virus_scanner_status = "healthy"
            except Exception:
                virus_scanner_status = "unhealthy"
        
        overall_status = "healthy"
        if storage_status == "unhealthy" or redis_status == "unhealthy":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "module": "files",
            "version": "4.0",
            "components": {
                "storage": storage_status,
                "redis": redis_status,
                "cloud_storage": cloud_status,
                "virus_scanner": virus_scanner_status
            },
            "features": {
                "file_upload": True,
                "file_download": True,
                "file_streaming": True,
                "bulk_operations": True,
                "file_processing": file_config.auto_processing_enabled,
                "encryption": file_config.encryption_enabled,
                "virus_scanning": file_config.virus_scanning_enabled
            },
            "limits": {
                "max_file_size_mb": file_config.max_file_size / (1024 * 1024),
                "max_files_per_user": file_config.max_files_per_user,
                "allowed_extensions": list(ALLOWED_EXTENSIONS)
            }
        }
        
    except Exception as e:
        logger.error("File health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "router",
    "FileManager",
    "FileConfig",
    "FileUploadRequest",
    "FileResponse",
    "FileSearchRequest",
    "BulkOperation",
    "ProcessingType"
]
        """
YMERA Enterprise - File Management Routes
Production-Ready File Upload/Download Endpoints - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, BinaryIO
from dataclasses import dataclass
from enum import Enum

# Third-party imports (alphabetical)
import aiofiles
import aioredis
import structlog
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from models.user import User
from models.file import FileRecord, FileStatus, FileType
from security.jwt_handler import get_current_user
from monitoring.performance_tracker import track_performance
from utils.file_processor import FileProcessor
from utils.virus_scanner import VirusScanner
from utils.encryption import encrypt_file, decrypt_file
from storage.cloud_storage import CloudStorageManager

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.file_routes")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FILES_PER_USER = 1000
CHUNK_SIZE = 8192
UPLOAD_TIMEOUT = 300
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'jpg', 'jpeg', 'png', 'gif', 'svg', 'bmp',
    'mp4', 'avi', 'mov', 'wmv', 'flv',
    'mp3', 'wav', 'flac', 'aac',
    'zip', 'rar', '7z', 'tar', 'gz',
    'json', 'xml', 'csv', 'md', 'html', 'css', 'js',
    'py', 'java', 'cpp', 'c', 'h', 'cs', 'php', 'rb'
}

settings = get_settings()

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

class ProcessingType(str, Enum):
    """File processing types"""
    NONE = "none"
    TEXT_EXTRACTION = "text_extraction"
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_PARSING = "document_parsing"
    DATA_ANALYSIS = "data_analysis"
    VIRUS_SCAN = "virus_scan"
    THUMBNAIL_GENERATION = "thumbnail_generation"

@dataclass
class FileConfig:
    """Configuration for file management"""
    max_file_size: int = MAX_FILE_SIZE
    max_files_per_user: int = MAX_FILES_PER_USER
    upload_timeout: int = UPLOAD_TIMEOUT
    virus_scanning_enabled: bool = True
    encryption_enabled: bool = True
    cloud_storage_enabled: bool = True
    auto_processing_enabled: bool = True

class FileUploadRequest(BaseModel):
    """Schema for file upload metadata"""
    description: Optional[str] = Field(default=None, max_length=500, description="File description")
    tags: List[str] = Field(default_factory=list, description="File tags")
    processing_type: ProcessingType = Field(default=ProcessingType.NONE, description="Processing type")
    is_private: bool = Field(default=True, description="File privacy setting")
    expires_at: Optional[datetime] = Field(default=None, description="File expiration date")
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate file tags"""
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        for tag in v:
            if len(tag) > 50:
                raise ValueError('Tag length cannot exceed 50 characters')
        return v

class FileResponse(BaseModel):
    """Schema for file responses"""
    id: str
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    mime_type: str
    description: Optional[str]
    tags: List[str]
    status: str
    is_private: bool
    processing_status: Optional[str]
    processing_result: Optional[Dict[str, Any]]
    download_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchRequest(BaseModel):
    """Schema for file search"""
    query: Optional[str] = Field(default=None, description="Search query")
    file_type: Optional[FileType] = Field(default=None, description="File type filter")
    tags: List[str] = Field(default_factory=list, description="Tag filters")
    status: Optional[FileStatus] = Field(default=None, description="Status filter")
    date_from: Optional[datetime] = Field(default=None, description="Date range start")
    date_to: Optional[datetime] = Field(default=None, description="Date range end")
    limit: int = Field(default=50, ge=1, le=100, description="Results limit")
    offset: int = Field(default=0, ge=0, description="Results offset")

class BulkOperation(BaseModel):
    """Schema for bulk file operations"""
    file_ids: List[str] = Field(..., min_items=1, max_items=100, description="File IDs")
    operation: str = Field(..., description="Operation type")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class FileManager:
    """Advanced file management system"""
    
    def __init__(self, config: FileConfig):
        self.config = config
        self.logger = logger.bind(component="file_manager")
        self._storage_path = Path(settings.FILE_STORAGE_PATH)
        self._temp_path = Path(settings.TEMP_STORAGE_PATH)
        self._redis_client = None
        self._file_processor = None
        self._virus_scanner = None
        self._cloud_storage = None
        
        # Create directories if they don't exist
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._temp_path.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize file manager resources"""
        try:
            self._redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            self._file_processor = FileProcessor()
            await self._file_processor.initialize()
            
            if self.config.virus_scanning_enabled:
                self._virus_scanner = VirusScanner()
                await self._virus_scanner.initialize()
            
            if self.config.cloud_storage_enabled:
                self._cloud_storage = CloudStorageManager()
                await self._cloud_storage.initialize()
            
            self.logger.info("File manager initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize file manager", error=str(e))
            raise
    
    async def upload_file(
        self,
        file: UploadFile,
        metadata: FileUploadRequest,
        user_id: str,
        db: AsyncSession
    ) -> FileResponse:
        """
        Upload and process file with comprehensive validation.
        
        Args:
            file: Uploaded file object
            metadata: File metadata
            user_id: Owner user ID
            db: Database session
            
        Returns:
            File information response
        """
        try:
            # Validate file
            await self._validate_file(file, user_id, db)
            
            # Generate file ID and paths
            file_id = str(uuid.uuid4())
            file_extension = Path(file.filename).suffix.lower()
            safe_filename = f"{file_id}{file_extension}"
            temp_path = self._temp_path / safe_filename
            
            # Save file temporarily
            await self._save_file_temporarily(file, temp_path)
            
            # Get file information
            file_size = temp_path.stat().st_size
            mime_type = mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
            file_hash = await self._calculate_file_hash(temp_path)
            
            # Virus scan if enabled
            if self.config.virus_scanning_enabled:
                scan_result = await self._virus_scanner.scan_file(temp_path)
                if not scan_result.is_clean:
                    temp_path.unlink()  # Delete infected file
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File failed virus scan: {scan_result.threat_name}"
                    )
            
            # Determine file type
            file_type = self._determine_file_type(file_extension, mime_type)
            
            # Create file record
            file_record = FileRecord(
                id=file_id,
                filename=safe_filename,
                original_filename=file.filename,
                file_type=file_type,
                file_size=file_size,
                mime_type=mime_type,
                file_hash=file_hash,
                description=metadata.description,
                tags=metadata.tags,
                is_private=metadata.is_private,
                expires_at=metadata.expires_at,
                user_id=user_id,
                status=FileStatus.PROCESSING,
                created_at=datetime.utcnow()
            )
            
            db.add(file_record)
            await db.commit()
            await db.refresh(file_record)
            
            # Move file to permanent storage
            permanent_path = self._storage_path / safe_filename
            temp_path.rename(permanent_path)
            
            # Encrypt file if enabled
            if self.config.encryption_enabled:
                await encrypt_file(permanent_path, settings.FILE_ENCRYPTION_KEY)
            
            # Upload to cloud storage if enabled
            if self.config.cloud_storage_enabled:
                cloud_url = await self._cloud_storage.upload_file(
                    permanent_path,
                    f"users/{user_id}/files/{safe_filename}"
                )
                file_record.cloud_url = cloud_url
                await db.commit()
            
            # Start processing if requested
            if metadata.processing_type != ProcessingType.NONE and self.config.auto_processing_enabled:
                await self._start_file_processing(file_record, metadata.processing_type)
            
            # Update status
            file_record.status = FileStatus.READY
            await db.commit()
            
            self.logger.info("File uploaded successfully", file_id=file_id, user_id=user_id)
            
            return FileResponse(
                id=file_record.id,
                filename=file_record.filename,
                original_filename=file_record.original_filename,
                file_type=file_record.file_type.value,
                file_size=file_record.file_size,
                mime_type=file_record.mime_type,
                description=file_record.description,
                tags=file_record.tags,
                status=file_record.status.value,
                is_private=file_record.is_private,
                processing_status=None,
                processing_result=None,
                download_count=0,
                created_at=file_record.created_at,
                updated_at=file_record.updated_at,
                expires_at=file_record.expires_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            # Cleanup temporary file
            if temp_path.exists():
                temp_path.unlink()
            
            self.logger.error("File upload failed", error=str(e), user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File upload failed"
            )
    
    async def download_file(
        self,
        file_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Union[FileResponse, BinaryIO]:
        """
        Download file with access control and tracking.
        
        Args:
            file_id: File identifier
            user_id: Requesting user ID
            db: Database session
            
        Returns:
            File stream or file information
        """
        try:
            # Get file record
            result = await db.execute(
                select(FileRecord).where(
                    FileRecord.id == file_id,
                    FileRecord.status == FileStatus.READY
                )
            )
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            
            # Check access permissions
            if file_record.is_private and file_record.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            # Check file expiration
            if file_record.expires_at and datetime.utcnow() > file_record.expires_at:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="File has expired"
                )
            
            # Get file path
            file_path = self._storage_path / file_record.filename
            
            # Check if file exists locally
            if not file_path.exists():
                # Try to download from cloud storage
                if self.config.cloud_storage_enabled and file_record.cloud_url:
                    await self._cloud_storage.download_file(file_record.cloud_url, file_path)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="File not found in storage"
                    )
            
            # Decrypt file if needed
            if self.config.encryption_enabled:
                await decrypt_file(file_path, settings.FILE_ENCRYPTION_KEY)
            
            # Update download count
            file_record.download_count += 1
            file_record.last_accessed = datetime.utcnow()
            await db.commit()
            
            self.logger.info("File download initiated", file_id=file_id, user_id=user_id)
            
            return file_path
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("File download failed", error=str(e), file_id=file_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File download failed"
            )
    
    async def search_files(
        self,
        search_params: FileSearchRequest,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Search files with advanced filtering.
        
        Args:
            search_params: Search parameters
            user_id: User ID
            db: Database session
            
        Returns:
            Search results with pagination
        """
        try:
            # Build query
            query = select(FileRecord).where(
                FileRecord.user_id == user_id,
                FileRecord.status != FileStatus.DELETED
            )
            
            # Apply filters
            if search_params.query:
                query = query.where(
                    