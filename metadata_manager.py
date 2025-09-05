# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class MetadataConfig:
    """Configuration dataclass for metadata manager settings"""
    max_tags_per_file: int = MAX_TAGS_PER_FILE
    max_tag_key_length: int = MAX_TAG_KEY_LENGTH
    max_tag_value_length: int = MAX_TAG_VALUE_LENGTH
    enable_access_logging: bool = True
    enable_search_indexing: bool = True
    cache_ttl: int = CACHE_TTL

class FileMetadataRequest(BaseModel):
    """Schema for file metadata requests"""
    filename: str = Field(..., max_length=500)
    content_type: str = Field(..., max_length=200)
    tags: Dict[str, str] = Field(default_factory=dict)
    access_level: AccessLevel = AccessLevel.PRIVATE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > MAX_TAGS_PER_FILE:
            raise ValueError(f"Maximum {MAX_TAGS_PER_FILE} tags allowed")
        
        for key, value in v.items():
            if len(key) > MAX_TAG_KEY_LENGTH:
                raise ValueError(f"Tag key too long: {key}")
            if len(str(value)) > MAX_TAG_VALUE_LENGTH:
                raise ValueError(f"Tag value too long: {value}")
        
        return v

class FileMetadataResponse(BaseModel):
    """Schema for file metadata responses"""
    file_id: str
    filename: str
    original_filename: Optional[str]
    content_type: str
    file_size: int
    checksum: str
    status: FileStatus
    access_level: AccessLevel
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    owner_id: Optional[str]
    tags: Dict[str, str]
    metadata: Dict[str, Any]
    is_encrypted: bool
    is_compressed: bool
    version: str
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FileSearchRequest(BaseModel):
    """Schema for file search requests"""
    query: Optional[str] = None
    filename_pattern: Optional[str] = None
    content_type: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    owner_id: Optional[str] = None
    status: Optional[FileStatus] = None
    access_level: Optional[AccessLevel] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    limit: int = Field(default=100, le=MAX_SEARCH_RESULTS)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at", regex="^(created_at|modified_at|filename|file_size)$")
    sort_order: str = Field(default="desc", regex="^(asc|desc)$")

class FileSearchResponse(BaseModel):
    """Schema for file search responses"""
    files: List[FileMetadataResponse]
    total_count: int
    offset: int
    limit: int
    has_more: bool

class FileStatsResponse(BaseModel):
    """Schema for file statistics responses"""
    total_files: int
    total_size: int
    files_by_status: Dict[str, int]
    files_by_type: Dict[str, int]
    files_by_access_level: Dict[str, int]
    average_file_size: float
    most_common_tags: List[Dict[str, Any]]
    files_created_today: int
    files_created_this_week: int
    files_created_this_month: int

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class MetadataManager:
    """Main metadata manager for file tracking and search"""
    
    def __init__(self, config: MetadataConfig):
        self.config = config
        self.logger = logger.bind(component="metadata_manager")
        self._cache: Optional[aioredis.Redis] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize metadata manager"""
        if self._initialized:
            return
        
        try:
            # Initialize Redis cache
            self._cache = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            
            self._initialized = True
            self.logger.info("Metadata manager initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize metadata manager", error=str(e))
            raise RuntimeError(f"Metadata manager initialization failed: {str(e)}")
    
    @track_performance
    async def create_file_record(
        self,
        db: AsyncSession,
        file_metadata: FileMetadata,
        request: FileMetadataRequest,
        owner_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> FileRecord:
        """Create a new file metadata record"""
        try:
            # Create file record
            file_record = FileRecord(
                file_id=file_metadata.file_id,
                filename=request.filename,
                original_filename=file_metadata.filename,
                content_type=request.content_type,
                file_size=file_metadata.size,
                checksum=file_metadata.checksum,
                storage_path=file_metadata.storage_path,
                storage_backend=settings.STORAGE_TYPE,
                status=FileStatus.ACTIVE,
                access_level=request.access_level,
                owner_id=owner_id,
                created_by=created_by,
                tags=request.tags,
                metadata=request.metadata,
                encryption_key_id=file_metadata.encryption_key,
                compression_type=file_metadata.compression_type,
                is_encrypted=bool(file_metadata.encryption_key),
                is_compressed=bool(file_metadata.compression_type)
            )
            
            db.add(file_record)
            
            # Create normalized tag records if enabled
            if self.config.enable_search_indexing and request.tags:
                await self._create_tag_records(db, file_metadata.file_id, request.tags)
            
            await db.commit()
            
            # Cache the record
            await self._cache_file_record(file_record)
            
            self.logger.info("File record created",
                           file_id=file_metadata.file_id,
                           filename=request.filename,
                           owner_id=owner_id)
            
            return file_record
            
        except Exception as e:
            await db.rollback()
            self.logger.error("Failed to create file record",
                            file_id=file_metadata.file_id,
                            error=str(e))
            raise
    
    async def _create_tag_records(self, db: AsyncSession, file_id: str, tags: Dict[str, str]) -> None:
        """Create normalized tag records for better search performance"""
        try:
            tag_records = [
                FileTag(
                    file_id=file_id,
                    tag_key=key,
                    tag_value=str(value)
                )
                for key, value in tags.items()
            ]
            
            db.add_all(tag_records)
            
        except Exception as e:
            self.logger.error("Failed to create tag records", file_id=file_id, error=str(e))
            raise
    
    @track_performance
    async def get_file_record(
        self,
        db: AsyncSession,
        file_id: str,
        user_id: Optional[str] = None
    ) -> Optional[FileRecord]:
        """Get file metadata record by ID"""
        try:
            # Try cache first
            cached_record = await self._get_cached_file_record(file_id)
            if cached_record:
                # Log access if user provided
                if user_id and self.config.enable_access_logging:
                    await self._log_file_access(db, file_id, user_id, "read", True)
                return cached_record
            
            # Query database
            stmt = select(FileRecord).where(FileRecord.file_id == file_id)
            result = await db.execute(stmt)
            file_record = result.scalar_one_or_none()
            
            if file_record:
                # Cache the record
                await self._cache_file_record(file_record)
                
                # Log access if user provided
                if user_id and self.config.enable_access_logging:
                    await self._log_file_access(db, file_id, user_id, "read", True)
                
                # Update accessed_at timestamp
                file_record.accessed_at = datetime.utcnow()
                await db.commit()
            
            return file_record
            
        except Exception as e:
            self.logger.error("Failed to get file record", file_id=file_id, error=str(e))
            raise
    
    @track_performance
    async def update_file_record(
        self,
        db: AsyncSession,
        file_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Optional[FileRecord]:
        """Update file metadata record"""
        try:
            # Get existing record
            stmt = select(FileRecord).where(FileRecord.file_id == file_id)
            result = await db.execute(stmt)
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                return None
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(file_record, field):
                    setattr(file_record, field, value)
            
            file_record.modified_at = datetime.utcnow()
            
            # Update tags if provided
            if 'tags' in updates:
                # Delete existing tag records
                if self.config.enable_search_indexing:
                    await self._delete_tag_records(db, file_id)
                    await self._create_tag_records(db, file_id, updates['tags'])
            
            await db.commit()
            
            # Update cache
            await self._cache_file_record(file_record)
            
            # Log access
            if user_id and self.config.enable_access_logging:
                await self._log_file_access(db, file_id, user_id, "write", True)
            
            self.logger.info("File record updated", file_id=file_id, updates=list(updates.keys()))
            
            return file_record
            
        except Exception as e:
            await db.rollback()
            self.logger.error("Failed to update file record", file_id=file_id, error=str(e))
            raise
    
    async def _delete_tag_records(self, db: AsyncSession, file_id: str) -> None:
        """Delete normalized tag records"""
        try:
            stmt = select(FileTag).where(FileTag.file_id == file_id)
            result = await db.execute(stmt)
            tag_records = result.scalars().all()
            
            for tag_record in tag_records:
                await db.delete(tag_record)
                
        except Exception as e:
            self.logger.error("Failed to delete tag records", file_id=file_id, error=str(e))
            raise
    
    @track_performance
    async def delete_file_record(
        self,
        db: AsyncSession,
        file_id: str,
        user_id: Optional[str] = None,
        soft_delete: bool = True
    ) -> bool:
        """Delete or mark file record as deleted"""
        try:
            stmt = select(FileRecord).where(FileRecord.file_id == file_id)
            result = await db.execute(stmt)
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                return False
            
            if soft_delete:
                # Soft delete - mark as deleted
                file_record.status = FileStatus.DELETED
                file_record.modified_at = datetime.utcnow()
            else:
                # Hard delete - remove from database
                await db.delete(file_record)
            
            await db.commit()
            
            # Remove from cache
            await self._remove_cached_file_record(file_id)
            
            # Log access
            if user_id and self.config.enable_access_logging:
                await self._log_file_access(db, file_id, user_id, "delete", True)
            
            self.logger.info("File record deleted",
                           file_id=file_id,
                           soft_delete=soft_delete)
            
            return True
            
        except Exception as e:
            await db.rollback()
            self.logger.error("Failed to delete file record", file_id=file_id, error=str(e))
            raise
    
    @track_performance
    async def search_files(
        self,
        db: AsyncSession,
        search_request: FileSearchRequest,
        user_id: Optional[str] = None
    ) -> FileSearchResponse:
        """Search files based on criteria"""
        try:
            # Build base query
            stmt = select(FileRecord)
            
            # Apply filters
            conditions = []
            
            # Text search in filename
            if search_request.query:
                conditions.append(
                    FileRecord.filename.ilike(f"%{search_request.query}%")
                )
            
            # Filename pattern
            if search_request.filename_pattern:
                conditions.append(
                    FileRecord.filename.ilike(search_request.filename_pattern)
                )
            
            # Content type filter
            if search_request.content_type:
                conditions.append(
                    FileRecord.content_type == search_request.content_type
                )
            
            # Owner filter
            if search_request.owner_id:
                conditions.append(
                    FileRecord.owner_id == search_request.owner_id
                )
            
            # Status filter
            if search_request.status:
                conditions.append(
                    FileRecord.status == search_request.status
                )
            
            # Access level filter
            if search_request.access_level:
                conditions.append(
                    FileRecord.access_level == search_request.access_level
                )
            
            # Date range filters
            if search_request.created_after:
                conditions.append(
                    FileRecord.created_at >= search_request.created_after
                )
            
            if search_request.created_before:
                conditions.append(
                    FileRecord.created_at <= search_request.created_before
                )
            
            # Size filters
            if search_request.min_size is not None:
                conditions.append(
                    FileRecord.file_size >= search_request.min_size
                )
            
            if search_request.max_size is not None:
                conditions.append(
                    FileRecord.file_size <= search_request.max_size
                )
            
            # Tag filters using JSONB operations
            if search_request.tags:
                for key, value in search_request.tags.items():
                    conditions.append(
                        FileRecord.tags[key].astext == value
                    )
            
            # Apply all conditions
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            count_result = await db.execute(count_stmt)
            total_count = count_result.scalar()
            
            # Apply sorting
            sort_column = getattr(FileRecord, search_request.sort_by)
            if search_request.sort_order == "desc":
                stmt = stmt.order_by(desc(sort_column))
            else:
                stmt = stmt.order_by(asc(sort_column))
            
            # Apply pagination
            stmt = stmt.offset(search_request.offset).limit(search_request.limit)
            
            # Execute query
            result = await db.execute(stmt)
            file_records = result.scalars().all()
            
            # Convert to response format
            files = [
                FileMetadataResponse(
                    file_id=record.file_id,
                    filename=record.filename,
                    original_filename=record.original_filename,
                    content_type=record.content_type,
                    file_size=record.file_size,
                    checksum=record.checksum,
                    status=record.status,
                    access_level=record.access_level,
                    created_at=record.created_at,
                    modified_at=record.modified_at,
                    accessed_at=record.accessed_at,
                    owner_id=record.owner_id,
                    tags=record.tags or {},
                    metadata=record.metadata or {},
                    is_encrypted=record.is_encrypted,
                    is_compressed=record.is_compressed,
                    version=record.version
                )
                for record in file_records
            ]
            
            has_more = (search_request.offset + len(files)) < total_count
            
            return FileSearchResponse(
                files=files,
                total_count=total_count,
                offset=search_request.offset,
                limit=search_request.limit,
                has_more=has_more
            )
            
        except Exception as e:
            self.logger.error("File search failed", error=str(e))
            raise
    
    @track_performance
    async def get_file_statistics(
        self,
        db: AsyncSession,
        owner_id: Optional[str] = None
    ) -> FileStatsResponse:
        """Get comprehensive file statistics"""
        try:
            base_query = select(FileRecord)
            if owner_id:
                base_query = base_query.where(FileRecord.owner_id == owner_id)
            
            # Get basic counts
            total_files_stmt = select(func.count()).select_from(base_query.subquery())
            total_size_stmt = select(func.sum(FileRecord.file_size)).select_from(base_query.subquery())
            
            total_files_result = await db.execute(total_files_stmt)
            total_size_result = await db.execute(total_size_stmt)
            
            total_files = total_files_result.scalar() or 0
            total_size = total_size_result.scalar() or 0
            
            # Files by status
            status_stmt = select(
                FileRecord.status,
                func.count()
            ).group_by(FileRecord.status)
            if owner_id:
                status_stmt = status_stmt.where(FileRecord.owner_id == owner_id)
            
            status_result = await db.execute(status_stmt)
            files_by_status = dict(status_result.fetchall())
            
            # Files by content type
            type_stmt = select(
                FileRecord.content_type,
                func.count()
            ).group_by(FileRecord.content_type).order_by(desc(func.count())).limit(10)
            if owner_id:
                type_stmt = type_stmt.where(FileRecord.owner_id == owner_id)
            
            type_result = await db.execute(type_stmt)
            files_by_type = dict(type_result.fetchall())
            
            # Files by access level
            access_stmt = select(
                FileRecord.access_level,
                func.count()
            ).group_by(FileRecord.access_level)
            if owner_id:
                access_stmt = access_stmt.where(FileRecord.owner_id == owner_id)
            
            access_result = await db.execute(access_stmt)
            files_by_access_level = dict(access_result.fetchall())
            
            # Average file size
            avg_size = total_size / total_files if total_files > 0 else 0
            
            # Time-based counts
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Files created today
            today_stmt = select(func.count()).where(
                FileRecord.created_at >= today
            )
            if owner_id:
                today_stmt = today_stmt.where(FileRecord.owner_id == owner_id)
            
            today_result = await db.execute(today_stmt)
            files_created_today = today_result.scalar() or 0
            
            # Files created this week
            week_stmt = select(func.count()).where(
                FileRecord.created_at >= week_ago
            )
            if owner_id:
                week_stmt = week_stmt.where(FileRecord.owner_id == owner_id)
            
            week_result = await db.execute(week_stmt)
            files_created_this_week = week_result.scalar() or 0
            
            # Files created this month
            month_stmt = select(func.count()).where(
                FileRecord.created_at >= month_ago
            )
            if owner_id:
                month_stmt = month_stmt.where(FileRecord.owner_id == owner_id)
            
            month_result = await db.execute(month_stmt)
            files_created_this_month = month_result.scalar() or 0
            
            # Most common tags (requires tag records)
            most_common_tags = []
            if self.config.enable_search_indexing:
                tag_stmt = select(
                    FileTag.tag_key,
                    FileTag.tag_value,
                    func.count().label('count')
                ).group_by(
                    FileTag.tag_key,
                    FileTag.tag_value
                ).order_by(desc('count')).limit(10)
                
                if owner_id:
                    tag_stmt = tag_stmt.join(FileRecord).where(
                        FileRecord.owner_id == owner_id
                    )
                
                tag_result = await db.execute(tag_stmt)
                most_common_tags = [
                    {"key": row[0], "value": row[1], "count": row[2]}
                    for row in tag_result.fetchall()
                ]
            
            return FileStatsResponse(
                total_files=total_files,
                total_size=total_size,
                files_by_status=files_by_status,
                files_by_type=files_by_type,
                files_by_access_level=files_by_access_level,
                average_file_size=avg_size,
                most_common_tags=most_common_tags,
                files_created_today=files_created_today,
                files_created_this_week=files_created_this_week,
                files_created_this_month=files_created_this_month
            )
            
        except Exception as e:
            self.logger.error("Failed to get file statistics", error=str(e))
            raise
    
    async def _log_file_access(
        self,
        db: AsyncSession,
        file_id: str,
        user_id: str,
        access_type: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Log file access for audit purposes"""
        try:
            access_log = FileAccessLog(
                file_id=file_id,
                user_id=user_id,
                access_type=access_type,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                error_message=error_message
            )
            
            db.add(access_log)
            await db.commit()
            
        except Exception as e:
            self.logger.error("Failed to log file access",
                            file_id=file_id,
                            user_id=user_id,
                            error=str(e))
    
    async def _cache_file_record(self, file_record: FileRecord) -> None:
        """Cache file record in Redis"""
        if not self._cache:
            return
        
        try:
            cache_key = f"file_record:{file_record.file_id}"
            cache_data = {
                "file_id": file_record.file_id,
                "filename": file_record.filename,
                "content_type": file_record.content_type,
                "file_size": file_record.file_size,
                "checksum": file_record.checksum,
                "storage_path": file_record.storage_path,
                "status": file_record.status,
                "access_level": file_record.access_level,
                "created_at": file_record.created_at.isoformat(),
                "modified_at": file_record.modified_at.isoformat(),
                "owner_id": file_record.owner_id,
                "tags": file_record.tags or {},
                "metadata": file_record.metadata or {},
                "is_encrypted": file_record.is_encrypted,
                "is_compressed": file_record.is_compressed
            }
            
            await self._cache.set(
                cache_key,
                json.dumps(cache_data, default=str),
                ex=self.config.cache_ttl
            )
            
        except Exception as e:
            self.logger.warning("Failed to cache file record",
                              file_id=file_record.file_id,
                              error=str(e))
    
    async def _get_cached_file_record(self, file_id: str) -> Optional[FileRecord]:
        """Get file record from cache"""
        if not self._cache:
            return None
        
        try:
            cache_key = f"file_record:{file_id}"
            cached_data = await self._cache.get(cache_key)
            
            if not cached_data:
                return None
            
            data = json.loads(cached_data)
            
            # Convert back to FileRecord object
            file_record = FileRecord()
            for key, value in data.items():
                if key in ["created_at", "modified_at"]:
                    value = datetime.fromisoformat(value)
                setattr(file_record, key, value)
            
            return file_record
            
        except Exception as e:
            self.logger.warning("Failed to get cached file record",
                              file_id=file_id,
                              error=str(e))
            return None
    
    async def _remove_cached_file_record(self, file_id: str) -> None:
        """Remove file record from cache"""
        if not self._cache:
            return
        
        try:
            cache_key = f"file_record:{file_id}"
            await self._cache.delete(cache_key)
            
        except Exception as e:
            self.logger.warning("Failed to remove cached file record",
                              file_id=file_id,
                              error=str(e))
    
    async def cleanup(self) -> None:
        """Cleanup metadata manager resources"""
        try:
            if self._cache:
                await self._cache.close()
            self.logger.info("Metadata manager cleaned up")
        except Exception as e:
            self.logger.error("Error during metadata cleanup", error=str(e))

class MetadataSearchEngine:
    """Advanced search engine for file metadata"""
    
    def __init__(self, metadata_manager: MetadataManager):
        self.metadata_manager = metadata_manager
        self.logger = logger.bind(component="search_engine")
    
    @track_performance
    async def advanced_search(
        self,
        db: AsyncSession,
        query: str,
        filters: Dict[str, Any] = None,
        user_id: Optional[str] = None
    ) -> List[FileMetadataResponse]:
        """Perform advanced search with natural language queries"""
        try:
            # Parse natural language query
            search_terms = self._parse_search_query(query)
            
            # Build search request
            search_request = FileSearchRequest(
                query=search_terms.get("text"),
                content_type=search_terms.get("content_type"),
                tags=search_terms.get("tags", {}),
                limit=filters.get("limit", 100) if filters else 100
            )
            
            # Apply additional filters
            if filters:
                for key, value in filters.items():
                    if hasattr(search_request, key):
                        setattr(search_request, key, value)
            
            # Execute search
            search_result = await self.metadata_manager.search_files(
                db, search_request, user_id
            )
            
            return search_result.files
            
        except Exception as e:
            self.logger.error("Advanced search failed", query=query, error=str(e))
            raise
    
    def _parse_search_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language search query"""
        try:
            search_terms = {"text": query, "tags": {}, "content_type": None}
            
            # Simple parsing for common patterns
            query_lower = query.lower()
            
            # Extract content type patterns
            content_type_patterns = {
                "image": ["image", "photo", "picture", "jpg", "png", "gif"],
                "document": ["document", "doc", "pdf", "text"],
                "video": ["video", "movie", "mp4", "avi"],
                "audio": ["audio", "music", "mp3", "wav"]
            }
            
            for content_type, keywords in content_type_patterns.items():
                if any(keyword in query_lower for keyword in keywords):
                    search_terms["content_type"] = f"{content_type}/%"
                    break
            
            # Extract tag patterns (tag:value)
            import re
            tag_pattern = r'tag:(\w+)=([^\s]+)'
            tag_matches = re.findall(tag_pattern, query)
            
            for key, value in tag_matches:
                search_terms["tags"][key] = value
                # Remove tag patterns from main text search
                search_terms["text"] = re.sub(f'tag:{key}={value}', '', search_terms["text"]).strip()
            
            return search_terms
            
        except Exception as e:
            self.logger.warning("Failed to parse search query", query=query, error=str(e))
            return {"text": query, "tags": {}, "content_type": None}
    
    @track_performance
    async def suggest_similar_files(
        self,
        db: AsyncSession,
        file_id: str,
        limit: int = 10
    ) -> List[FileMetadataResponse]:
        """Suggest similar files based on metadata"""
        try:
            # Get the reference file
            reference_file = await self.metadata_manager.get_file_record(db, file_id)
            if not reference_file:
                return []
            
            # Build similarity search
            conditions = []
            
            # Same content type
            conditions.append(
                FileRecord.content_type == reference_file.content_type
            )
            
            # Exclude the reference file itself
            conditions.append(
                FileRecord.file_id != file_id
            )
            
            # Similar tags (if any)
            if reference_file.tags:
                for key, value in reference_file.tags.items():
                    conditions.append(
                        FileRecord.tags[key].astext == value
                    )
            
            # Similar file size (within 50% range)
            size_min = int(reference_file.file_size * 0.5)
            size_max = int(reference_file.file_size * 1.5)
            conditions.append(
                and_(
                    FileRecord.file_size >= size_min,
                    FileRecord.file_size <= size_max
                )
            )
            
            # Execute query
            stmt = select(FileRecord).where(
                and_(*conditions)
            ).order_by(
                desc(FileRecord.created_at)
            ).limit(limit)
            
            result = await db.execute(stmt)
            similar_files = result.scalars().all()
            
            # Convert to response format
            return [
                FileMetadataResponse(
                    file_id=record.file_id,
                    filename=record.filename,
                    original_filename=record.original_filename,
                    content_type=record.content_type,
                    file_size=record.file_size,
                    checksum=record.checksum,
                    status=record.status,
                    access_level=record.access_level,
                    created_at=record.created_at,
                    modified_at=record.modified_at,
                    accessed_at=record.accessed_at,
                    owner_id=record.owner_id,
                    tags=record.tags or {},
                    metadata=record.metadata or {},
                    is_encrypted=record.is_encrypted,
                    is_compressed=record.is_compressed,
                    version=record.version
                )
                for record in similar_files
            ]
            
        except Exception as e:
            self.logger.error("Failed to suggest similar files", file_id=file_id, error=str(e))
            return []

class MetadataValidator:
    """Validator for file metadata operations"""
    
    @staticmethod
    def validate_file_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize file metadata"""
        try:
            validated = {}
            
            # Validate required fields
            required_fields = ["filename", "content_type", "file_size", "checksum"]
            for field in required_fields:
                if field not in metadata:
                    raise ValueError(f"Missing required field: {field}")
                validated[field] = metadata[field]
            
            # Validate filename
            filename = str(metadata["filename"]).strip()
            if not filename or len(filename) > 500:
                raise ValueError("Invalid filename")
            validated["filename"] = filename
            
            # Validate content type
            content_type = str(metadata["content_type"]).strip()
            if not content_type or len(content_type) > 200:
                raise ValueError("Invalid content type")
            validated["content_type"] = content_type
            
            # Validate file size
            file_size = int(metadata["file_size"])
            if file_size < 0:
                raise ValueError("Invalid file size")
            validated["file_size"] = file_size
            
            # Validate checksum
            checksum = str(metadata["checksum"]).strip()
            if not checksum or len(checksum) != 64:  # SHA-256 hash
                raise ValueError("Invalid checksum")
            validated["checksum"] = checksum
            
            # Validate optional fields
            if "tags" in metadata:
                tags = metadata["tags"]
                if not isinstance(tags, dict):
                    raise ValueError("Tags must be a dictionary")
                
                if len(tags) > MAX_TAGS_PER_FILE:
                    raise ValueError(f"Too many tags (max {MAX_TAGS_PER_FILE})")
                
                validated_tags = {}
                for key, value in tags.items():
                    key_str = str(key).strip()
                    value_str = str(value).strip()
                    
                    if len(key_str) > MAX_TAG_KEY_LENGTH:
                        raise ValueError(f"Tag key too long: {key_str}")
                    if len(value_str) > MAX_TAG_VALUE_LENGTH:
                        raise ValueError(f"Tag value too long: {value_str}")
                    
                    validated_tags[key_str] = value_str
                
                validated["tags"] = validated_tags
            
            # Validate access level
            if "access_level" in metadata:
                access_level = metadata["access_level"]
                if access_level not in [level.value for level in AccessLevel]:
                    raise ValueError(f"Invalid access level: {access_level}")
                validated["access_level"] = access_level
            
            return validated
            
        except Exception as e:
            logger.error("Metadata validation failed", error=str(e))
            raise ValueError(f"Invalid metadata: {str(e)}")
    
    @staticmethod
    def validate_search_request(request: Dict[str, Any]) -> Dict[str, Any]:
        """Validate search request parameters"""
        try:
            validated = {}
            
            # Validate limit
            limit = request.get("limit", 100)
            if not isinstance(limit, int) or limit < 1 or limit > MAX_SEARCH_RESULTS:
                limit = min(100, MAX_SEARCH_RESULTS)
            validated["limit"] = limit
            
            # Validate offset
            offset = request.get("offset", 0)
            if not isinstance(offset, int) or offset < 0:
                offset = 0
            validated["offset"] = offset
            
            # Validate sort parameters
            valid_sort_fields = ["created_at", "modified_at", "filename", "file_size"]
            sort_by = request.get("sort_by", "created_at")
            if sort_by not in valid_sort_fields:
                sort_by = "created_at"
            validated["sort_by"] = sort_by
            
            sort_order = request.get("sort_order", "desc")
            if sort_order not in ["asc", "desc"]:
                sort_order = "desc"
            validated["sort_order"] = sort_order
            
            # Validate query string
            if "query" in request:
                query = str(request["query"]).strip()
                if len(query) > 1000:  # Reasonable query length limit
                    query = query[:1000]
                validated["query"] = query
            
            # Validate date ranges
            for date_field in ["created_after", "created_before"]:
                if date_field in request:
                    try:
                        date_value = request[date_field]
                        if isinstance(date_value, str):
                            date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                        validated[date_field] = date_value
                    except (ValueError, TypeError):
                        # Skip invalid dates
                        pass
            
            # Copy other valid fields
            for field in ["filename_pattern", "content_type", "owner_id", "status", "access_level"]:
                if field in request:
                    validated[field] = request[field]
            
            return validated
            
        except Exception as e:
            logger.error("Search request validation failed", error=str(e))
            raise ValueError(f"Invalid search request: {str(e)}")

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def create_database_tables(engine):
    """Create database tables for metadata management"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise

async def health_check() -> Dict[str, Any]:
    """Metadata manager health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "module": "metadata_manager",
        "version": "4.0"
    }

def convert_file_record_to_response(record: FileRecord) -> FileMetadataResponse:
    """Convert FileRecord to FileMetadataResponse"""
    return FileMetadataResponse(
        file_id=record.file_id,
        filename=record.filename,
        original_filename=record.original_filename,
        content_type=record.content_type,
        file_size=record.file_size,
        checksum=record.checksum,
        status=record.status,
        access_level=record.access_level,
        created_at=record.created_at,
        modified_at=record.modified_at,
        accessed_at=record.accessed_at,
        owner_id=record.owner_id,
        tags=record.tags or {},
        metadata=record.metadata or {},
        is_encrypted=record.is_encrypted,
        is_compressed=record.is_compressed,
        version=record.version
    )

async def cleanup_old_access_logs(
    db: AsyncSession,
    retention_days: int = 90
) -> int:
    """Clean up old access logs to maintain performance"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        stmt = select(FileAccessLog).where(
            FileAccessLog.accessed_at < cutoff_date
        )
        result = await db.execute(stmt)
        old_logs = result.scalars().all()
        
        count = len(old_logs)
        for log in old_logs:
            await db.delete(log)
        
        await db.commit()
        
        logger.info("Cleaned up old access logs", count=count, retention_days=retention_days)
        return count
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to cleanup old access logs", error=str(e))
        return 0

async def reindex_file_tags(db: AsyncSession, metadata_manager: MetadataManager) -> int:
    """Reindex all file tags for search optimization"""
    try:
        # Get all files
        stmt = select(FileRecord).where(FileRecord.status != FileStatus.DELETED)
        result = await db.execute(stmt)
        files = result.scalars().all()
        
        reindexed_count = 0
        
        for file_record in files:
            if file_record.tags:
                # Delete existing tag records
                await metadata_manager._delete_tag_records(db, file_record.file_id)
                
                # Create new tag records
                await metadata_manager._create_tag_records(
                    db, file_record.file_id, file_record.tags
                )
                
                reindexed_count += 1
        
        await db.commit()
        
        logger.info("Reindexed file tags", count=reindexed_count)
        return reindexed_count
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to reindex file tags", error=str(e))
        return 0

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_metadata_manager() -> MetadataManager:
    """Initialize metadata manager for production use"""
    config = MetadataConfig(
        max_tags_per_file=settings.MAX_TAGS_PER_FILE,
        enable_access_logging=settings.ENABLE_ACCESS_LOGGING,
        enable_search_indexing=settings.ENABLE_SEARCH_INDEXING,
        cache_ttl=settings.METADATA_CACHE_TTL
    )
    
    manager = MetadataManager(config)
    await manager.initialize()
    
    return manager

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "MetadataManager",
    "MetadataSearchEngine",
    "MetadataValidator",
    "MetadataConfig",
    "FileRecord",
    "FileTag",
    "FileAccessLog",
    "FileMetadataRequest",
    "FileMetadataResponse",
    "FileSearchRequest",
    "FileSearchResponse",
    "FileStatsResponse",
    "FileStatus",
    "AccessLevel",
    "initialize_metadata_manager",
    "create_database_tables",
    "convert_file_record_to_response",
    "cleanup_old_access_logs",
    "reindex_file_tags",
    "health_check"
]"""
YMERA Enterprise - Metadata Manager
Production-Ready File Metadata Tracking - v4.0
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
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from enum import Enum

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import HTTPException, Query, Depends
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy import and_, or_, desc, asc, func

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_sensitive_data, decrypt_sensitive_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token
from storage.storage_backend import FileMetadata

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Metadata configuration constants
MAX_TAGS_PER_FILE = 50
MAX_TAG_KEY_LENGTH = 50
MAX_TAG_VALUE_LENGTH = 200
MAX_SEARCH_RESULTS = 1000
CACHE_TTL = 1800  # 30 minutes
METADATA_VERSION = "1.0"

# Search and indexing
SEARCHABLE_FIELDS = ["filename", "content_type", "tags"]
INDEX_BATCH_SIZE = 100

# Configuration loading
settings = get_settings()

# Database base
Base = declarative_base()

# ===============================================================================
# ENUMS
# ===============================================================================

class FileStatus(str, Enum):
    """File status enumeration"""
    UPLOADING = "uploading"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    CORRUPTED = "corrupted"

class AccessLevel(str, Enum):
    """File access level enumeration"""
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"

# ===============================================================================
# DATABASE MODELS
# ===============================================================================

class FileRecord(Base):
    """SQLAlchemy model for file metadata"""
    __tablename__ = "file_records"
    
    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # File information
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=True)
    content_type = Column(String(200), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(128), nullable=False, index=True)
    
    # Storage information
    storage_path = Column(String(1000), nullable=False)
    storage_backend = Column(String(50), default="local")
    
    # Status and access
    status = Column(String(20), default=FileStatus.UPLOADING, nullable=False, index=True)
    access_level = Column(String(20), default=AccessLevel.PRIVATE, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # User and ownership
    owner_id = Column(String(255), nullable=True, index=True)
    created_by = Column(String(255), nullable=True)
    
    # Metadata and tags
    tags = Column(JSONB, default=dict)
    metadata = Column(JSONB, default=dict)
    
    # Security and processing
    encryption_key_id = Column(String(255), nullable=True)
    compression_type = Column(String(50), nullable=True)
    is_encrypted = Column(Boolean, default=False)
    is_compressed = Column(Boolean, default=False)
    
    # Versioning and relationships
    version = Column(String(50), default=METADATA_VERSION)
    parent_file_id = Column(String(255), nullable=True, index=True)
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_file_owner_status', owner_id, status),
        Index('idx_file_created_at_desc', desc(created_at)),
        Index('idx_file_content_type', content_type),
        Index('idx_file_tags_gin', tags, postgresql_using='gin'),
        Index('idx_file_metadata_gin', metadata, postgresql_using='gin'),
    )

class FileTag(Base):
    """SQLAlchemy model for file tags (normalized)"""
    __tablename__ = "file_tags"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(String(255), ForeignKey('file_records.file_id', ondelete='CASCADE'), nullable=False, index=True)
    tag_key = Column(String(MAX_TAG_KEY_LENGTH), nullable=False, index=True)
    tag_value = Column(String(MAX_TAG_VALUE_LENGTH), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_tag_key_value', tag_key, tag_value),
        Index('idx_tag_file_key', file_id, tag_key),
    )

class FileAccessLog(Base):
    """SQLAlchemy model for file access logging"""
    __tablename__ = "file_access_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(String(255), ForeignKey('file_records.file_id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    access_type = Column(String(50), nullable=False)  # read, write, delete
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_access_file_time', file_id, desc(accessed_at)),
        Index('idx_access_user_time', user_id, desc(accessed_at)),
    )