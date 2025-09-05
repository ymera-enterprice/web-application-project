@dataclass
class AggregationResult:
    """Result of response aggregation"""
    request_id: str
    status: AggregationStatus
    aggregated_data: Any = None
    responses_used: List[str] = field(default_factory=list)
    total_responses: int = 0
    processing_time: float = 0.0
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    confidence_score: float = 0.0
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ===============================================================================
# PYDANTIC SCHEMAS
# ===============================================================================

class AggregationRequestSchema(BaseModel):
    """Schema for aggregation requests"""
    correlation_id: str = Field(..., min_length=1, max_length=100)
    strategy: str = Field(..., regex="^(first_response|all_responses|majority_consensus|weighted_average|fastest_n|best_quality|timeout_based|custom)$")
    timeout: int = Field(default=DEFAULT_RESPONSE_TIMEOUT, ge=1, le=3600)
    expected_responses: Optional[int] = Field(None, ge=1, le=MAX_RESPONSES_PER_REQUEST)
    minimum_responses: int = Field(default=1, ge=1, le=MAX_RESPONSES_PER_REQUEST)
    quality_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('expected_responses')
    def validate_expected_responses(cls, v, values):
        if v is not None and 'minimum_responses' in values:
            if v < values['minimum_responses']:
                raise ValueError("Expected responses must be >= minimum responses")
        return v

class ResponseSubmissionSchema(BaseModel):
    """Schema for response submissions"""
    correlation_id: str = Field(..., min_length=1, max_length=100)
    agent_id: str = Field(..., min_length=1, max_length=100)
    data: Any = None
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    processing_time: float = Field(default=0.0, ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AggregationResultSchema(BaseModel):
    """Schema for aggregation results"""
    request_id: str
    status: str
    aggregated_data: Any = None
    responses_used: List[str] = Field(default_factory=list)
    total_responses: int = 0
    processing_time: float = 0.0
    quality_metrics: Dict[str, float] = Field(default_factory=dict)
    confidence_score: float = 0.0
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class AggregatorConfig:
    """Configuration for response aggregator"""
    
    def __init__(self):
        self.enabled: bool = settings.RESPONSE_AGGREGATOR_ENABLED
        self.max_concurrent: int = MAX_CONCURRENT_AGGREGATIONS
        self.default_timeout: int = DEFAULT_RESPONSE_TIMEOUT
        self.max_response_size: int = MAX_RESPONSE_SIZE
        self.cleanup_interval: int = CLEANUP_INTERVAL
        self.statistics_retention: int = STATISTICS_RETENTION_HOURS
        self.redis_url: str = settings.REDIS_URL
        self.enable_quality_scoring: bool = settings.ENABLE_QUALITY_SCORING
        self.enable_agent_reputation: bool = settings.ENABLE_AGENT_REPUTATION

class BaseResponseAggregator(ABC):
    """Abstract base class for response aggregators"""
    
    def __init__(self, config: AggregatorConfig):
        self.config = config
        self.logger = logger.bind(module=self.__class__.__name__)
    
    @abstractmethod
    async def create_aggregation_request(self, request: AggregationRequest) -> str:
        """Create new aggregation request"""
        pass
    
    @abstractmethod
    async def submit_response(self, response: AggregatedResponse) -> bool:
        """Submit response for aggregation"""
        pass
    
    @abstractmethod
    async def get_aggregation_result(self, request_id: str) -> Optional[AggregationResult]:
        """Get aggregation result"""
        pass
    
    @abstractmethod
    async def cancel_aggregation(self, request_id: str) -> bool:
        """Cancel aggregation request"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup aggregator resources"""
        pass

class ProductionResponseAggregator(BaseResponseAggregator):
    """Production-ready response aggregator implementation"""
    
    def __init__(self, config: AggregatorConfig):
        super().__init__(config)
        self._redis_client: Optional[aioredis.Redis] = None
        self._active_requests: Dict[str, AggregationRequest] = {}
        self._collected_responses: Dict[str, List[AggregatedResponse]] = defaultdict(list)
        self._completed_results: Dict[str, AggregationResult] = {}
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._statistics: Dict[str, Any] = defaultdict(int)
        self._agent_reputation: Dict[str, float] = defaultdict(lambda: 1.0)
        self._lock = asyncio.Lock()
        self._health_status = True
    
    async def _initialize_resources(self) -> None:
        """Initialize aggregator resources"""
        try:
            await self._setup_redis_connection()
            await self._setup_background_tasks()
            await self._load_agent_reputation()
            self.logger.info("Response aggregator initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize response aggregator", error=str(e))
            raise
    
    async def _setup_redis_connection(self) -> None:
        """Setup Redis connection for caching and coordination"""
        try:
            self._redis_client = await aioredis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=30,
                socket_connect_timeout=10,
                retry_on_timeout=True,
                max_connections=20
            )
            
            await self._redis_client.ping()
            self.logger.info("Redis connection established for aggregator")
            
        except Exception as e:
            self.logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def _setup_background_tasks(self) -> None:
        """Setup background maintenance tasks"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_requests())
        self.logger.info("Background tasks started")
    
    async def _load_agent_reputation(self) -> None:
        """Load agent reputation scores from storage"""
        try:
            if not self._redis_client:
                return
            
            reputation_data = await self._redis_client.hgetall("agent_reputation")
            
            for agent_id, score in reputation_data.items():
                self._agent_reputation[agent_id] = float(score)
            
            self.logger.info("Loaded agent reputation data", count=len(reputation_data))
            
        except Exception as e:
            self.logger.error("Failed to load agent reputation", error=str(e))
    
    @track_performance
    async def create_aggregation_request(self, request: AggregationRequest) -> str:
        """Create new aggregation request"""
        async with self._lock:
            try:
                # Generate unique request ID
                request_id = str(uuid.uuid4())
                request.request_id = request_id
                
                # Validate request
                await self._validate_aggregation_request(request)
                
                # Check concurrent limit
                if len(self._active_requests) >= self.config.max_concurrent:
                    raise HTTPException(
                        status_code=429,
                        detail="Maximum concurrent aggregations reached"
                    )
                
                # Store request
                self._active_requests[request_id] = request
                self._collected_responses[request_id] = []
                
                # Start processing task
                processing_task = asyncio.create_task(
                    self._process_aggregation_request(request_id)
                )
                self._processing_tasks[request_id] = processing_task
                
                # Store in Redis for coordination
                await self._persist_aggregation_request(request)
                
                # Update statistics
                self._statistics["requests_created"] += 1
                self._statistics[f"strategy_{request.strategy.value}"] += 1
                
                self.logger.info(
                    "Aggregation request created",
                    request_id=request_id,
                    correlation_id=request.correlation_id,
                    strategy=request.strategy.value,
                    timeout=request.timeout
                )
                
                return request_id
                
            except Exception as e:
                self.logger.error("Failed to create aggregation request", error=str(e))
                raise
    
    async def _validate_aggregation_request(self, request: AggregationRequest) -> None:
        """Validate aggregation request parameters"""
        if not request.correlation_id:
            raise ValueError("Correlation ID is required")
        
        if request.timeout <= 0 or request.timeout > 3600:
            raise ValueError("Timeout must be between 1 and 3600 seconds")
        
        if request.minimum_responses <= 0:
            raise ValueError("Minimum responses must be positive")
        
        if request.expected_responses and request.expected_responses < request.minimum_responses:
            raise ValueError("Expected responses must be >= minimum responses")
        
        if request.quality_threshold < 0 or request.quality_threshold > 1:
            raise ValueError("Quality threshold must be between 0 and 1")
    
    async def _persist_aggregation_request(self, request: AggregationRequest) -> None:
        """Persist aggregation request to Redis"""
        if not self._redis_client:
            return
        
        request_data = {
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "strategy": request.strategy.value,
            "timeout": request.timeout,
            "expected_responses": request.expected_responses or 0,
            "minimum_responses": request.minimum_responses,
            "quality_threshold": request.quality_threshold,
            "created_at": request.created_at.isoformat(),
            "metadata": json.dumps(request.metadata)
        }
        
        await self._redis_client.hset(
            f"aggregation_request:{request.request_id}",
            mapping=request_data
        )
        await self._redis_client.expire(
            f"aggregation_request:{request.request_id}",
            request.timeout + 300  # Keep for 5 minutes after timeout
        )
    
    @track_performance
    async def submit_response(self, response: AggregatedResponse) -> bool:
        """Submit response for aggregation"""
        try:
            # Find matching aggregation request
            request_id = None
            for rid, request in self._active_requests.items():
                if request.correlation_id == response.correlation_id:
                    request_id = rid
                    break
            
            if not request_id:
                self.logger.warning(
                    "No matching aggregation request found",
                    correlation_id=response.correlation_id,
                    agent_id=response.agent_id
                )
                return False
            
            async with self._lock:
                # Check if request is still active
                if request_id not in self._active_requests:
                    self.logger.warning(
                        "Aggregation request no longer active",
                        request_id=request_id,
                        correlation_id=response.correlation_id
                    )
                    return False
                
                # Validate response
                await self._validate_response(response)
                
                # Apply agent reputation to quality scoring
                if self.config.enable_agent_reputation:
                    agent_reputation = self._agent_reputation[response.agent_id]
                    response.metrics.agent_reputation = agent_reputation
                    response.metrics.quality_score *= agent_reputation
                
                # Add response to collection
                self._collected_responses[request_id].append(response)
                
                # Update statistics
                self._statistics["responses_received"] += 1
                
                self.logger.info(
                    "Response submitted for aggregation",
                    request_id=request_id,
                    response_id=response.response_id,
                    agent_id=response.agent_id,
                    quality_score=response.metrics.quality_score
                )
                
                return True
                
        except Exception as e:
            self.logger.error(
                "Failed to submit response",
                response_id=response.response_id,
                error=str(e)
            )
            return False
    
    async def _validate_response(self, response: AggregatedResponse) -> None:
        """Validate response data"""
        if not response.response_id:
            raise ValueError("Response ID is required")
        
        if not response.agent_id:
            raise ValueError("Agent ID is required")
        
        if not response.correlation_id:
            raise ValueError("Correlation ID is required")
        
        # Check response size
        response_size = len(json.dumps(response.data, default=str))
        if response_size > self.config.max_response_size:
            raise ValueError(f"Response size {response_size} exceeds maximum {self.config.max_response_size}")
    
    async def _process_aggregation_request(self, request_id: str) -> None:
        """Process aggregation request with timeout handling"""
        try:
            request = self._active_requests[request_id]
            start_time = datetime.utcnow()
            
            self.logger.info(
                "Starting aggregation processing",
                request_id=request_id,
                strategy=request.strategy.value
            )
            
            # Wait for responses or timeout
            await self._wait_for_responses(request_id, request.timeout)
            
            # Process collected responses
            result = await self._aggregate_responses(request_id)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            result.processing_time = processing_time
            result.completed_at = datetime.utcnow()
            
            # Store result
            async with self._lock:
                self._completed_results[request_id] = result
                
                # Clean up active request
                if request_id in self._active_requests:
                    del self._active_requests[request_id]
                
                if request_id in self._collected_responses:
                    del self._collected_responses[request_id]
            
            # Update agent reputation based on results
            if self.config.enable_agent_reputation:
                await self._update_agent_reputation(request_id, result)
            
            # Update statistics
            self._statistics["requests_completed"] += 1
            self._statistics[f"status_{result.status.value}"] += 1
            
            self.logger.info(
                "Aggregation processing completed",
                request_id=request_id,
                status=result.status.value,
                responses_used=len(result.responses_used),
                processing_time=processing_time
            )
            
        except Exception as e:
            # Handle processing error
            error_result = AggregationResult(
                request_id=request_id,
                status=AggregationStatus.ERROR,
                error_message=str(e),
                completed_at=datetime.utcnow()
            )
            
            async with self._lock:
                self._completed_results[request_id] = error_result
                
                if request_id in self._active_requests:
                    del self._active_requests[request_id]
                
                if request_id in self._collected_responses:
                    del self._collected_responses[request_id]
            
            self._statistics["requests_failed"] += 1
            
            self.logger.error(
                "Aggregation processing failed",
                request_id=request_id,
                error=str(e)
            )
        
        finally:
            # Clean up processing task
            if request_id in self._processing_tasks:
                del self._processing_tasks[request_id]
    
    async def _wait_for_responses(self, request_id: str, timeout: int) -> None:
        """Wait for responses with various completion conditions"""
        request = self._active_requests[request_id]
        start_time = datetime.utcnow()
        
        while True:
            current_time = datetime.utcnow()
            elapsed = (current_time - start_time).total_seconds()
            
            # Check timeout
            if elapsed >= timeout:
                self.logger.info(
                    "Aggregation timeout reached",
                    request_id=request_id,
                    elapsed=elapsed,
                    responses_collected=len(self._collected_responses[request_id])
                )
                break
            
            responses = self._collected_responses[request_id]
            
            # Check if we have minimum responses
            if len(responses) >= request.minimum_responses:
                # Strategy-specific completion checks
                if request.strategy == AggregationStrategy.FIRST_RESPONSE:
                    break
                elif request.strategy == AggregationStrategy.ALL_RESPONSES:
                    if request.expected_responses and len(responses) >= request.expected_responses:
                        break
                elif request.strategy in [AggregationStrategy.MAJORITY_CONSENSUS, AggregationStrategy.WEIGHTED_AVERAGE]:
                    if request.expected_responses and len(responses) >= request.expected_responses:
                        break
                    elif len(responses) >= 3:  # Minimum for consensus
                        # Check if we have enough quality responses
                        quality_responses = [r for r in responses if r.metrics.quality_score >= request.quality_threshold]
                        if len(quality_responses) >= request.minimum_responses:
                            break
            
            # Wait before next check
            await asyncio.sleep(0.1)
    
    async def _aggregate_responses(self, request_id: str) -> AggregationResult:
        """Aggregate collected responses based on strategy"""
        request = self._active_requests[request_id]
        responses = self._collected_responses[request_id]
        
        if not responses:
            return AggregationResult(
                request_id=request_id,
                status=AggregationStatus.TIMEOUT,
                error_message="No responses received"
            )
        
        # Filter responses based on quality threshold
        quality_responses = [
            r for r in responses 
            if r.metrics.quality_score >= request.quality_threshold
        ]
        
        if not quality_responses:
            return AggregationResult(
                request_id=request_id,
                status=AggregationStatus.ERROR,
                error_message="No responses meet quality threshold"
            )
        
        # Apply custom filter if provided
        if request.filter_function:
            quality_responses = [r for r in quality_responses if request.filter_function(r)]
        
        if not quality_responses:
            return AggregationResult(
                request_id=request_id,
                status=AggregationStatus.ERROR,
                error_message="No responses passed filter function"
            )
        
        # Apply aggregation strategy
        try:
            if request.strategy == AggregationStrategy.FIRST_RESPONSE:
                aggregated_data = await self._aggregate_first_response(quality_responses)
            elif request.strategy == AggregationStrategy.ALL_RESPONSES:
                aggregated_data = await self._aggregate_all_responses(quality_responses)
            elif request.strategy == AggregationStrategy.MAJORITY_CONSENSUS:
                aggregated_data = await self._aggregate_majority_consensus(quality_responses)
            elif request.strategy == AggregationStrategy.WEIGHTED_AVERAGE:
                aggregated_data = await self._aggregate_weighted_average(quality_responses, request.weight_function)
            elif request.strategy == AggregationStrategy.FASTEST_N:
                aggregated_data = await self._aggregate_fastest_n(quality_responses, request.minimum_responses)
            elif request.strategy == AggregationStrategy.BEST_QUALITY:
                aggregated_data = await self._aggregate_best_quality(quality_responses)
            elif request.strategy == AggregationStrategy.TIMEOUT_BASED:
                aggregated_data = await self._aggregate_timeout_based(quality_responses)
            elif request.strategy == AggregationStrategy.CUSTOM:
                if request.custom_aggregator:
                    aggregated_data = request.custom_aggregator(quality_responses)
                else:
                    raise ValueError("Custom aggregator function not provided")
            else:
                raise ValueError(f"Unsupported aggregation strategy: {request.strategy}")
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(quality_responses)
            confidence_score = self._calculate_confidence_score(quality_responses, request.strategy)
            
            return AggregationResult(
                request_id=request_id,
                status=AggregationStatus.COMPLETED,
                aggregated_data=aggregated_data,
                responses_used=[r.response_id for r in quality_responses],
                total_responses=len(responses),
                quality_metrics=quality_metrics,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            return AggregationResult(
                request_id=request_id,
                status=AggregationStatus.ERROR,
                error_message=f"Aggregation failed: {str(e)}"
            )
    
    async def _aggregate_first_response(self, responses: List[AggregatedResponse]) -> Any:
        """Aggregate using first response strategy"""
        # Sort by received time and return first
        responses.sort(key=lambda r: r.received_at)
        return responses[0].data
    
    async def _aggregate_all_responses(self, responses: List[AggregatedResponse]) -> Any:
        """Aggregate all responses into a list"""
        return [
            {
                "agent_id": r.agent_id,
                "data": r.data,
                "quality_score": r.metrics.quality_score,
                "confidence": r.metrics.confidence,
                "response_time": r.metrics.response_time
            }
            for r in responses
        ]
    
    async def _aggregate_majority_consensus(self, responses: List[AggregatedResponse]) -> Any:
        """Aggregate using majority consensus"""
        if len(responses) < 3:
            # Not enough for consensus, return best quality
            return await self._aggregate_best_quality(responses)
        
        # Group similar responses
        response_groups = defaultdict(list)
        
        for response in responses:
            # Simple string-based grouping (could be enhanced with semantic similarity)
            response_str = json.dumps(response.data, sort_keys=True, default=str)
            response_groups[response_str].append(response)
        
        # Find majority group
        majority_group = max(response_groups.values(), key=len)
        
        if len(majority_group) >= len(responses) / 2:
            # Return best quality response from majority
            best_response = max(majority_group, key=lambda r: r.metrics.quality_score)
            return best_response.data
        else:
            # No clear majority, return best quality overall
            return await self._aggregate_best_quality(responses)
    
    async def _aggregate_weighted_average(self, responses: List[AggregatedResponse], weight_function: Optional[Callable] = None) -> Any:
        """Aggregate using weighted average"""
        if not weight_function:
            # Default weight function based on quality and reputation
            weight_function = lambda r: r.metrics.quality_score * r.metrics.agent_reputation * r.metrics.confidence
        
        # Check if responses contain numeric data for averaging
        numeric_responses = []
        for response in responses:
            try:
                if isinstance(response.data, (int, float)):
                    numeric_responses.append((response.data, weight_function(response)))
                elif isinstance(response.data, dict) and all(isinstance(v, (int, float)) for v in response.data.values()):
                    numeric_responses.append((response.data, weight_function(response)))
            except:
                continue
        
        if numeric_responses:
            if isinstance(numeric_responses[0][0], dict):
                # Weighted average of dictionaries
                result = {}
                total_weight = sum(weight for _, weight in numeric_responses)
                
                for key in numeric_responses[0][0].keys():
                    weighted_sum = sum(data[key] * weight for data, weight in numeric_responses if key in data)
                    result[key] = weighted_sum / total_weight if total_weight > 0 else 0
                
                return result
            else:
                # Weighted average of scalars
                total_weighted = sum(value * weight for value, weight in numeric_responses)
                total_weight = sum(weight for _, weight in numeric_responses)
                return total_weighted / total_weight if total_weight > 0 else 0
        else:
            # Non-numeric data, return best quality
            return await self._aggregate_best_quality(responses)
    
    async def _aggregate_fastest_n(self, responses: List[AggregatedResponse], n: int) -> Any:
        """Aggregate N fastest responses"""
        # Sort by response time and take first N
        responses.sort(key=lambda r: r.metrics.response_time)
        fastest_responses = responses[:n]
        
        return await self._aggregate_all_responses(fastest_responses)
    
    async def _aggregate_best_quality(self, responses: List[AggregatedResponse]) -> Any:
        """Return response with best quality score"""
        best_response = max(responses, key=lambda r: r.metrics.quality_score)
        return best_response.data
    
    async def _aggregate_timeout_based(self, responses: List[AggregatedResponse]) -> Any:
        """Aggregate based on timeout conditions"""
        # Use responses received within first 80% of timeout period
        if not responses:
            return None
        
        earliest_time = min(r.received_at for r in responses)
        latest_time = max(r.received_at for r in responses)
        time_range = (latest_time - earliest_time).total_seconds()
        
        if time_range > 0:
            cutoff_time = earliest_time + timedelta(seconds=time_range * 0.8)
            early_responses = [r for r in responses if r.received_at <= cutoff_time]
            
            if early_responses:
                return await self._aggregate_best_quality(early_responses)
        
        return await self._aggregate_best_quality(responses)
    
    def _calculate_quality_metrics(self, responses: List[AggregatedResponse]) -> Dict[str, float]:
        """Calculate aggregate quality metrics"""
        if not responses:
            return {}
        
        quality_scores = [r.metrics.quality_score for r in responses]
        confidence_scores = [r.metrics.confidence for r in responses]
        response_times = [r.metrics.response_time for r in responses]
        
        return {
            "average_quality": statistics.mean(quality_scores),
            "quality_std": statistics.stdev(quality_scores) if len(quality_scores) > 1 else 0,
            "average_confidence": statistics.mean(confidence_scores),
            "confidence_std": statistics.stdev(confidence_scores) if len(confidence_scores) > 1 else 0,
            "average_response_time": statistics.mean(response_times),
            "response_time_std": statistics.stdev(response_times) if len(response_times) > 1 else 0,
            "min_quality": min(quality_scores),
            "max_quality": max(quality_scores)
        }
    
    def _calculate_confidence_score(self, responses: List[AggregatedResponse], strategy: AggregationStrategy) -> float:
        """Calculate overall confidence score for aggregation"""
        if not responses:
            return 0.0
        
        # Base confidence from individual responses
        base_confidence = statistics.mean([r.metrics.confidence for r in responses])
        
        # Adjust based on strategy and response characteristics
        strategy_multiplier = {
            AggregationStrategy.FIRST_RESPONSE: 0.7,
            AggregationStrategy.ALL_RESPONSES: 0.9,
            AggregationStrategy.MAJORITY_CONSENSUS: 0.95,
            AggregationStrategy.WEIGHTED_AVERAGE: 0.85,
            AggregationStrategy.FASTEST_N: 0.8,
            AggregationStrategy.BEST_QUALITY: 0.9,
            AggregationStrategy.TIMEOUT_BASED: 0.75,
            AggregationStrategy.CUSTOM: 0.8
        }.get(strategy, 0.8)
        
        # Adjust for number of responses
        response_count_boost = min(len(responses) / 5, 1.0) * 0.1
        
        # Adjust for quality consistency
        quality_scores = [r.metrics.quality_score for r in responses]
        quality_consistency = 1.0 - (statistics.stdev(quality_scores) if len(quality_scores) > 1 else 0)
        
        final_confidence = (base_confidence * strategy_multiplier + response_count_boost) * quality_consistency
        
        return min(max(final_confidence, 0.0), 1.0)
    
    async def _update_agent_reputation(self, request_id: str, result: AggregationResult) -> None:
        """Update agent reputation based on aggregation results"""
        try:
            if result.status != AggregationStatus.COMPLETED:
                return
            
            responses = self._collected_responses.get(request_id, [])
            if not responses:
                return
            
            # Calculate reputation adjustments
            for response in responses:
                agent_id = response.agent_id
                current_reputation = self._agent_reputation[agent_id]
                
                # Positive adjustment for high quality responses
                if response.response_id in result.responses_used:
                    if response.metrics.quality_score > 0.8:
                        adjustment = 0.01  # Small positive adjustment
                    elif response.metrics.quality_score > 0.6:
                        adjustment = 0.005
                    else:
                        adjustment = 0.0
                else:
                    # Negative adjustment for unused responses
                    adjustment = -0.005
                
                # Apply adjustment with decay
                new_reputation = current_reputation + adjustment
                new_reputation = max(0.1, min(2.0, new_reputation))  # Clamp between 0.1 and 2.0
                
                self._agent_reputation[agent_id] = new_reputation
            
            # Persist updated reputation
            if self._redis_client:
                reputation_updates = {
                    agent_id: str(reputation) 
                    for agent_id, reputation in self._agent_reputation.items()
                }
                await self._redis_client.hset("agent_reputation", mapping=reputation_updates)
            
        except Exception as e:
            self.logger.error("Failed to update agent reputation", error=str(e))
    
    @track_performance
    async def get_aggregation_result(self, request_id: str) -> Optional[AggregationResult]:
        """Get aggregation result by request ID"""
        try:
            # Check completed results first
            if request_id in self._completed_results:
                return self._completed_results[request_id]
            
            # Check if request is still active
            if request_id in self._active_requests:
                # Return pending status
                return AggregationResult(
                    request_id=request_id,
                    status=AggregationStatus.COLLECTING,
                    total_responses=len(self._collected_responses.get(request_id, []))
                )
            
            # Try to load from Redis
            if self._redis_client:
                result_data = await self._redis_client.hgetall(f"aggregation_result:{request_id}")
                if result_data:
                    return self._deserialize_result(result_data)
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get aggregation result", request_id=request_id, error=str(e))
            return None
    
    def _deserialize_result(self, result_data: Dict[str, str]) -> AggregationResult:
        """Deserialize aggregation result from Redis"""
        return AggregationResult(
            request_id=result_data["request_id"],
            status=AggregationStatus(result_data["status"]),
            aggregated_data=json.loads(result_data.get("aggregated_data", "null")),
            responses_used=json.loads(result_data.get("responses_used", "[]")),
            total_responses=int(result_data.get("total_responses", 0)),
            processing_time=float(result_data.get("processing_time", 0.0)),
            quality_metrics=json.loads(result_data.get("quality_metrics", "{}")),
            confidence_score=float(result_data.get("confidence_score", 0.0)),
            error_message=result_data.get("error_message"),
            completed_at=datetime.fromisoformat(result_data["completed_at"]) if result_data.get("completed_at") else None,
            metadata=json.loads(result_data.get("metadata", "{}"))
        )
    
    async def cancel_aggregation(self, request_id: str) -> bool:
        """Cancel active aggregation request"""
        try:
            async with self._lock:
                if request_id not in self._active_requests:
                    return False
                
                # Cancel processing task
                if request_id in self._processing_tasks:
                    self._processing_tasks[request_id].cancel()
                    del self._processing_tasks[request_id]
                
                # Create cancelled result
                cancelled_result = AggregationResult(
                    request_id=request_id,
                    status=AggregationStatus.CANCELLED,
                    total_responses=len(self._collected_responses.get(request_id, [])),
                    completed_at=datetime.utcnow()
                )
                
                # Store result and cleanup
                self._completed_results[request_id] = cancelled_result
                
                if request_id in self._active_requests:
                    del self._active_requests[request_id]
                
                if request_id in self._collected_responses:
                    del self._collected_responses[request_id]
                
                # Update statistics
                self._statistics["requests_cancelled"] += 1
                
                self.logger.info("Aggregation request cancelled", request_id=request_id)
                return True
                
        except Exception as e:
            self.logger.error("Failed to cancel aggregation", request_id=request_id, error=str(e))
            return False
    
    async def get_aggregator_statistics(self) -> Dict[str, Any]:
        """Get comprehensive aggregator statistics"""
        try:
            current_time = datetime.utcnow()
            
            return {
                "active_requests": len(self._active_requests),
                "completed_results": len(self._completed_results),
                "processing_tasks": len(self._processing_tasks),
                "agent_count": len(self._agent_reputation),
                "statistics": dict(self._statistics),
                "average_agent_reputation": statistics.mean(self._agent_reputation.values()) if self._agent_reputation else 0.0,
                "health_status": self._health_status,
                "timestamp": current_time.isoformat()
            }
        except Exception as e:
            self.logger.error("Failed to get aggregator statistics", error=str(e))
            return {"error": str(e)}
    
    async def get_active_requests(self) -> List[Dict[str, Any]]:
        """Get list of active aggregation requests"""
        try:
            active_list = []
            
            for request_id, request in self._active_requests.items():
                response_count = len(self._collected_responses.get(request_id, []))
                elapsed = (datetime.utcnow() - request.created_at).total_seconds()
                
                active_list.append({
                    "request_id": request_id,
                    "correlation_id": request.correlation_id,
                    "strategy": request.strategy.value,
                    "timeout": request.timeout,
                    "expected_responses": request.expected_responses,
                    "minimum_responses": request.minimum_responses,
                    "responses_collected": response_count,
                    "elapsed_time": elapsed,
                    "created_at": request.created_at.isoformat()
                })
            
            return active_list
            
        except Exception as e:
            self.logger.error("Failed to get active requests", error=str(e))
            return []
    
    async def _cleanup_expired_requests(self) -> None:
        """Background task to cleanup expired requests and results"""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                
                current_time = datetime.utcnow()
                expired_requests = []
                expired_results = []
                
                # Find expired active requests
                for request_id, request in self._active_requests.items():
                    elapsed = (current_time - request.created_at).total_seconds()
                    if elapsed > (request.timeout + 60):  # Grace period
                        expired_requests.append(request_id)
                
                # Find old completed results
                retention_seconds = self.config.statistics_retention * 3600
                for request_id, result in self._completed_results.items():
                    if result.completed_at:
                        age = (current_time - result.completed_at).total_seconds()
                        if age > retention_seconds:
                            expired_results.append(request_id)
                
                # Cleanup expired items
                async with self._lock:
                    for request_id in expired_requests:
                        # Cancel processing task
                        if request_id in self._processing_tasks:
                            self._processing_tasks[request_id].cancel()
                            del self._processing_tasks[request_id]
                        
                        # Create timeout result
                        timeout_result = AggregationResult(
                            request_id=request_id,
                            status=AggregationStatus.TIMEOUT,
                            total_responses=len(self._collected_responses.get(request_id, [])),
                            completed_at=current_time
                        )
                        
                        self._completed_results[request_id] = timeout_result
                        
                        # Cleanup
                        if request_id in self._active_requests:
                            del self._active_requests[request_id]
                        
                        if request_id in self._collected_responses:
                            del self._collected_responses[request_id]
                        
                        self._statistics["requests_timeout"] += 1
                    
                    # Remove old results
                    for request_id in expired_results:
                        del self._completed_results[request_id]
                
                if expired_requests or expired_results:
                    self.logger.info(
                        "Cleanup completed",
                        expired_requests=len(expired_requests),
                        expired_results=len(expired_results)
                    )
                
            except Exception as e:
                self.logger.error("Error in cleanup task", error=str(e))
    
    async def cleanup(self) -> None:
        """Cleanup aggregator resources"""
        try:
            # Cancel cleanup task
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            # Cancel all processing tasks
            for task in self._processing_tasks.values():
                task.cancel()
            
            # Wait for tasks to complete
            if self._processing_tasks:
                await asyncio.gather(*self._processing_tasks.values(), return_exceptions=True)
            
            # Close Redis connection
            if self._redis_client:
                await self._redis_client.close()
            
            self.logger.info("Response aggregator cleanup completed")
            
        except Exception as e:
            self.logger.error("Error during aggregator cleanup", error=str(e))

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

async def health_check() -> Dict[str, Any]:
    """Response aggregator health check"""
    try:
        aggregator = await get_response_aggregator()
        stats = await aggregator.get_aggregator_statistics()
        
        return {
            "status": "healthy" if stats.get("health_status", False) else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "response_aggregator",
            "version": "4.0",
            "statistics": stats
        }
    except Exception as e:
        logger.error("Aggregator health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "module": "response_aggregator",
            "error": str(e)
        }

def validate_aggregation_request(data: Dict[str, Any]) -> AggregationRequestSchema:
    """Validate aggregation request data"""
    try:
        return AggregationRequestSchema(**data)
    except Exception as e:
        logger.warning("Aggregation request validation failed", errors=str(e))
        raise HTTPException(status_code=422, detail="Invalid aggregation request data")

def validate_response_submission(data: Dict[str, Any]) -> ResponseSubmissionSchema:
    """Validate response submission data"""
    try:
        return ResponseSubmissionSchema(**data)
    except Exception as e:
        logger.warning("Response submission validation failed", errors=str(e))
        raise HTTPException(status_code=422, detail="Invalid response submission data")

async def create_aggregation_request_from_schema(schema: AggregationRequestSchema) -> AggregationRequest:
    """Create AggregationRequest from validated schema"""
    return AggregationRequest(
        request_id="",  # Will be generated
        correlation_id=schema.correlation_id,
        strategy=AggregationStrategy(schema.strategy),
        timeout=schema.timeout,
        expected_responses=schema.expected_responses,
        minimum_responses=schema.minimum_responses,
        quality_threshold=schema.quality_threshold,
        metadata=schema.metadata
    )

async def create_aggregated_response_from_schema(schema: ResponseSubmissionSchema) -> AggregatedResponse:
    """Create AggregatedResponse from validated schema"""
    response_id = str(uuid.uuid4())
    
    metrics = ResponseMetrics(
        processing_time=schema.processing_time,
        quality_score=schema.quality_score,
        confidence=schema.confidence,
        size_bytes=len(json.dumps(schema.data, default=str))
    )
    
    return AggregatedResponse(
        response_id=response_id,
        agent_id=schema.agent_id,
        correlation_id=schema.correlation_id,
        data=schema.data,
        metrics=metrics,
        metadata=schema.metadata
    )

def format_aggregation_result_for_response(result: AggregationResult) -> Dict[str, Any]:
    """Format aggregation result for API response"""
    return {
        "request_id": result.request_id,
        "status": result.status.value,
        "aggregated_data": result.aggregated_data,
        "responses_used": result.responses_used,
        "total_responses": result.total_responses,
        "processing_time": result.processing_time,
        "quality_metrics": result.quality_metrics,
        "confidence_score": result.confidence_score,
        "error_message": result.error_message,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "metadata": result.metadata
    }

# ===============================================================================
# RESPONSE QUALITY EVALUATORS
# ===============================================================================

class ResponseQualityEvaluator:
    """Utility class for evaluating response quality"""
    
    @staticmethod
    def evaluate_content_quality(data: Any) -> float:
        """Evaluate content quality based on various factors"""
        try:
            score = 0.5  # Base score
            
            # Check if data is not empty/null
            if data is not None:
                score += 0.2
            
            # Check data structure complexity
            if isinstance(data, dict):
                score += 0.1
                if len(data) > 1:
                    score += 0.1
            elif isinstance(data, list):
                score += 0.1
                if len(data) > 0:
                    score += 0.1
            
            # Check for common quality indicators
            if isinstance(data, str):
                if len(data) > 10:
                    score += 0.1
                if len(data.split()) > 5:
                    score += 0.1
            
            return min(score, 1.0)
            
        except Exception:
            return 0.1  # Low score for evaluation errors
    
    @staticmethod
    def evaluate_response_completeness(response: AggregatedResponse, expected_fields: Optional[List[str]] = None) -> float:
        """Evaluate response completeness"""
        try:
            if not expected_fields:
                return 1.0
            
            if not isinstance(response.data, dict):
                return 0.5
            
            present_fields = sum(1 for field in expected_fields if field in response.data)
            return present_fields / len(expected_fields)
            
        except Exception:
            return 0.0
    
    @staticmethod
    def evaluate_response_consistency(responses: List[AggregatedResponse]) -> Dict[str, float]:
        """Evaluate consistency across multiple responses"""
        try:
            if len(responses) < 2:
                return {"consistency_score": 1.0}
            
            # Simple consistency check based on response similarity
            response_strings = []
            for response in responses:
                try:
                    response_str = json.dumps(response.data, sort_keys=True, default=str)
                    response_strings.append(response_str)
                except:
                    response_strings.append(str(response.data))
            
            # Calculate pairwise similarity
            similarities = []
            for i in range(len(response_strings)):
                for j in range(i + 1, len(response_strings)):
                    # Simple string similarity (could be enhanced)
                    str1, str2 = response_strings[i], response_strings[j]
                    if str1 == str2:
                        similarity = 1.0
                    else:
                        # Jaccard similarity on words
                        words1 = set(str1.split())
                        words2 = set(str2.split())
                        if words1 or words2:
                            similarity = len(words1.intersection(words2)) / len(words1.union(words2))
                        else:
                            similarity = 0.0
                    similarities.append(similarity)
            
            consistency_score = statistics.mean(similarities) if similarities else 0.0
            
            return {
                "consistency_score": consistency_score,
                "similarity_std": statistics.stdev(similarities) if len(similarities) > 1 else 0.0,
                "unique_responses": len(set(response_strings))
            }
            
        except Exception as e:
            logger.error("Failed to evaluate response consistency", error=str(e))
            return {"consistency_score": 0.0}

# ===============================================================================
# CUSTOM AGGREGATION STRATEGIES
# ===============================================================================

class CustomAggregationStrategies:
    """Collection of custom aggregation strategies"""
    
    @staticmethod
    def consensus_with_fallback(responses: List[AggregatedResponse]) -> Any:
        """Consensus with fallback to best quality"""
        try:
            if len(responses) < 3:
                return max(responses, key=lambda r: r.metrics.quality_score).data
            
            # Group identical responses
            response_groups = defaultdict(list)
            for response in responses:
                key = json.dumps(response.data, sort_keys=True, default=str)
                response_groups[key].append(response)
            
            # Find consensus (majority)
            majority_threshold = len(responses) / 2
            for group in response_groups.values():
                if len(group) >= majority_threshold:
                    # Return best quality from consensus group
                    best_response = max(group, key=lambda r: r.metrics.quality_score)
                    return best_response.data
            
            # No consensus, return best quality overall
            return max(responses, key=lambda r: r.metrics.quality_score).data
            
        except Exception:
            return responses[0].data if responses else None
    
    @staticmethod
    def quality_weighted_consensus(responses: List[AggregatedResponse]) -> Any:
        """Consensus weighted by quality scores"""
        try:
            if not responses:
                return None
            
            # Weight responses by quality score
            weighted_groups = defaultdict(float)
            response_data = {}
            
            for response in responses:
                key = json.dumps(response.data, sort_keys=True, default=str)
                weight = response.metrics.quality_score * response.metrics.confidence
                weighted_groups[key] += weight
                response_data[key] = response.data
            
            # Return data with highest weighted score
            best_key = max(weighted_groups.keys(), key=lambda k: weighted_groups[k])
            return response_data[best_key]
            
        except Exception:
            return responses[0].data if responses else None
    
    @staticmethod
    def temporal_decay_aggregation(responses: List[AggregatedResponse]) -> Any:
        """Aggregate with temporal decay (newer responses weighted higher)"""
        try:
            if not responses:
                return None
            
            current_time = datetime.utcnow()
            weighted_responses = []
            
            for response in responses:
                # Calculate time decay (responses lose weight over time)
                age_seconds = (current_time - response.received_at).total_seconds()
                decay_factor = max(0.1, 1.0 - (age_seconds / 300))  # 5-minute decay
                
                total_weight = (
                    response.metrics.quality_score * 
                    response.metrics.confidence * 
                    decay_factor
                )
                
                weighted_responses.append((response, total_weight))
            
            # Return response with highest weight
            best_response = max(weighted_responses, key=lambda x: x[1])[0]
            return best_response.data
            
        except Exception:
            return responses[0].data if responses else None

# ===============================================================================
# SINGLETON AGGREGATOR INSTANCE
# ===============================================================================

_aggregator_instance: Optional[ProductionResponseAggregator] = None
_aggregator_lock = asyncio.Lock()

async def get_response_aggregator() -> ProductionResponseAggregator:
    """Get singleton response aggregator instance"""
    global _aggregator_instance
    
    if not _aggregator_instance:
        async with _aggregator_lock:
            if not _aggregator_instance:
                config = AggregatorConfig()
                _aggregator_instance = ProductionResponseAggregator(config)
                await _aggregator_instance._initialize_resources()
    
    return _aggregator_instance

async def shutdown_response_aggregator() -> None:
    """Shutdown the response aggregator instance"""
    global _aggregator_instance
    
    if _aggregator_instance:
        await _aggregator_instance.cleanup()
        _aggregator_instance = None

# ===============================================================================
# MODULE INITIALIZATION
# ===============================================================================

async def initialize_response_aggregator() -> ProductionResponseAggregator:
    """Initialize response aggregator for production use"""
    try:
        aggregator = await get_response_aggregator()
        logger.info("Response aggregator initialized successfully")
        return aggregator
    except Exception as e:
        logger.error("Failed to initialize response aggregator", error=str(e))
        raise

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "ProductionResponseAggregator",
    "AggregatorConfig",
    "AggregationRequest",
    "AggregatedResponse",
    "AggregationResult",
    "AggregationStrategy",
    "AggregationStatus",
    "ResponseMetrics",
    "ResponseQuality",
    "AggregationRequestSchema",
    "ResponseSubmissionSchema",
    "AggregationResultSchema",
    "ResponseQualityEvaluator",
    "CustomAggregationStrategies",
    "get_response_aggregator",
    "initialize_response_aggregator",
    "shutdown_response_aggregator",
    "validate_aggregation_request",
    "validate_response_submission",
    "create_aggregation_request_from_schema",
    "create_aggregated_response_from_schema",
    "format_aggregation_result_for_response",
    "health_check"
]"""
YMERA Enterprise - Response Aggregator
Production-Ready Response Collection & Processing System - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from enum import Enum
from collections import defaultdict
import statistics
import heapq

# Third-party imports (alphabetical)
import aioredis
import structlog
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
import numpy as np

# Local imports (alphabetical)
from config.settings import get_settings
from database.connection import get_db_session
from utils.encryption import encrypt_data, decrypt_data
from monitoring.performance_tracker import track_performance
from security.jwt_handler import verify_token
from communication.communication_protocols import ProductionMessage, MessageType, get_protocol_handler

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger(f"ymera.{__name__.split('.')[-1]}")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Aggregation constants
MAX_CONCURRENT_AGGREGATIONS = 1000
DEFAULT_RESPONSE_TIMEOUT = 300  # 5 minutes
MAX_RESPONSE_SIZE = 50 * 1024 * 1024  # 50MB
CLEANUP_INTERVAL = 60  # 1 minute
STATISTICS_RETENTION_HOURS = 24
MAX_RESPONSES_PER_REQUEST = 1000

# Aggregation strategies
STRATEGY_FIRST_RESPONSE = "first_response"
STRATEGY_ALL_RESPONSES = "all_responses" 
STRATEGY_MAJORITY_CONSENSUS = "majority_consensus"
STRATEGY_WEIGHTED_AVERAGE = "weighted_average"
STRATEGY_FASTEST_N = "fastest_n"
STRATEGY_BEST_QUALITY = "best_quality"
STRATEGY_TIMEOUT_BASED = "timeout_based"

# Configuration loading
settings = get_settings()

# ===============================================================================
# ENUMS & DATA MODELS
# ===============================================================================

class AggregationStrategy(Enum):
    """Response aggregation strategies"""
    FIRST_RESPONSE = "first_response"
    ALL_RESPONSES = "all_responses"
    MAJORITY_CONSENSUS = "majority_consensus"
    WEIGHTED_AVERAGE = "weighted_average"
    FASTEST_N = "fastest_n"
    BEST_QUALITY = "best_quality"
    TIMEOUT_BASED = "timeout_based"
    CUSTOM = "custom"

class AggregationStatus(Enum):
    """Aggregation request status"""
    PENDING = "pending"
    COLLECTING = "collecting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"

class ResponseQuality(Enum):
    """Response quality levels"""
    EXCELLENT = 5
    GOOD = 4
    AVERAGE = 3
    BELOW_AVERAGE = 2
    POOR = 1

@dataclass
class ResponseMetrics:
    """Metrics for individual responses"""
    response_time: float = 0.0
    processing_time: float = 0.0
    size_bytes: int = 0
    quality_score: float = 0.0
    confidence: float = 0.0
    error_count: int = 0
    agent_reputation: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class AggregatedResponse:
    """Individual response in aggregation"""
    response_id: str
    agent_id: str
    correlation_id: str
    data: Any
    metrics: ResponseMetrics
    metadata: Dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class AggregationRequest:
    """Request for response aggregation"""
    request_id: str
    correlation_id: str
    strategy: AggregationStrategy
    timeout: int = DEFAULT_RESPONSE_TIMEOUT
    expected_responses: Optional[int] = None
    minimum_responses: int = 1
    quality_threshold: float = 0.0
    weight_function: Optional[Callable[[AggregatedResponse], float]] = None
    custom_aggregator: Optional[Callable[[List[AggregatedResponse]], Any]] = None
    filter_function: Optional[Callable[[AggregatedResponse], bool]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)