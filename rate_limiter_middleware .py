        # API endpoint specific limits
        self.rules.append(RateLimitRule(
            name="auth_endpoints",
            description="Authentication endpoints rate limit",
            requests=10,
            window_seconds=MINUTE,
            burst_size=5,
            scope=RateLimitScope.IP_ENDPOINT,
            path_patterns=["/api/v1/auth/*"],
            methods=["POST"],
            priority=50,
            block_duration_seconds=300  # 5 minute block
        ))
        
        # Admin endpoints stricter limits
        self.rules.append(RateLimitRule(
            name="admin_endpoints",
            description="Admin endpoints rate limit",
            requests=100,
            window_seconds=HOUR,
            burst_size=10,
            scope=RateLimitScope.USER,
            path_patterns=["/api/v1/admin/*"],
            priority=25
        ))

@dataclass
class RateLimitState:
    """Rate limit state tracking for a specific client/scope"""
    
    # Token bucket state
    tokens: float = 0.0
    last_refill: float = 0.0
    
    # Sliding window state
    request_times: deque = field(default_factory=deque)
    
    # Fixed window state
    window_start: float = 0.0
    window_requests: int = 0
    
    # Blocking state
    blocked_until: float = 0.0
    total_blocked_requests: int = 0
    
    # Metrics
    total_requests: int = 0
    total_violations: int = 0
    first_request: float = 0.0
    last_request: float = 0.0

@dataclass
class RateLimitMetrics:
    """Rate limiting metrics tracking"""
    
    total_requests: int = 0
    allowed_requests: int = 0
    blocked_requests: int = 0
    rate_limited_requests: int = 0
    
    # Per-rule metrics
    rule_violations: Dict[str, int] = field(default_factory=dict)
    rule_requests: Dict[str, int] = field(default_factory=dict)
    
    # Client metrics
    top_clients: Dict[str, int] = field(default_factory=dict)
    blocked_clients: Set[str] = field(default_factory=set)
    
    def get_success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.allowed_requests / self.total_requests) * 100

# ===============================================================================
# RATE LIMITING ALGORITHMS
# ===============================================================================

class RateLimitAlgorithms:
    """
    Collection of rate limiting algorithm implementations.
    
    This class provides various rate limiting algorithms including token bucket,
    sliding window, fixed window, and leaky bucket implementations.
    """
    
    @staticmethod
    def token_bucket(
        state: RateLimitState,
        rule: RateLimitRule,
        current_time: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Token bucket algorithm implementation.
        
        Args:
            state: Current rate limit state
            rule: Rate limiting rule
            current_time: Current timestamp
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        # Initialize if first request
        if state.last_refill == 0:
            state.tokens = rule.burst_size
            state.last_refill = current_time
        
        # Calculate time elapsed and refill tokens
        time_elapsed = current_time - state.last_refill
        refill_rate = rule.requests / rule.window_seconds
        tokens_to_add = time_elapsed * refill_rate
        
        state.tokens = min(rule.burst_size, state.tokens + tokens_to_add)
        state.last_refill = current_time
        
        # Check if request can be allowed
        if state.tokens >= 1:
            state.tokens -= 1
            allowed = True
            remaining = int(state.tokens)
        else:
            allowed = False
            remaining = 0
        
        # Calculate reset time
        if state.tokens < rule.burst_size:
            time_to_next_token = (1 - (state.tokens % 1)) / refill_rate
            reset_time = current_time + time_to_next_token
        else:
            reset_time = current_time
        
        rate_limit_info = {
            "limit": rule.requests,
            "remaining": remaining,
            "reset_time": int(reset_time),
            "retry_after": int(max(0, reset_time - current_time)) if not allowed else 0
        }
        
        return allowed, rate_limit_info
    
    @staticmethod
    def sliding_window(
        state: RateLimitState,
        rule: RateLimitRule,
        current_time: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Sliding window algorithm implementation.
        
        Args:
            state: Current rate limit state
            rule: Rate limiting rule
            current_time: Current timestamp
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        # Remove old requests outside the window
        window_start = current_time - rule.window_seconds
        
        while state.request_times and state.request_times[0] <= window_start:
            state.request_times.popleft()
        
        # Check if request can be allowed
        current_requests = len(state.request_times)
        allowed = current_requests < rule.requests
        
        if allowed:
            state.request_times.append(current_time)
            remaining = rule.requests - current_requests - 1
        else:
            remaining = 0
        
        # Calculate reset time (when oldest request expires)
        if state.request_times:
            reset_time = state.request_times[0] + rule.window_seconds
        else:
            reset_time = current_time + rule.window_seconds
        
        rate_limit_info = {
            "limit": rule.requests,
            "remaining": remaining,
            "reset_time": int(reset_time),
            "retry_after": int(max(0, reset_time - current_time)) if not allowed else 0
        }
        
        return allowed, rate_limit_info
    
    @staticmethod
    def fixed_window(
        state: RateLimitState,
        rule: RateLimitRule,
        current_time: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Fixed window algorithm implementation.
        
        Args:
            state: Current rate limit state
            rule: Rate limiting rule
            current_time: Current timestamp
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        # Calculate current window
        window_number = int(current_time // rule.window_seconds)
        window_start_time = window_number * rule.window_seconds
        
        # Reset counter if new window
        if state.window_start != window_start_time:
            state.window_start = window_start_time
            state.window_requests = 0
        
        # Check if request can be allowed
        allowed = state.window_requests < rule.requests
        
        if allowed:
            state.window_requests += 1
            remaining = rule.requests - state.window_requests
        else:
            remaining = 0
        
        # Calculate reset time (start of next window)
        reset_time = window_start_time + rule.window_seconds
        
        rate_limit_info = {
            "limit": rule.requests,
            "remaining": remaining,
            "reset_time": int(reset_time),
            "retry_after": int(max(0, reset_time - current_time)) if not allowed else 0
        }
        
        return allowed, rate_limit_info
    
    @staticmethod
    def leaky_bucket(
        state: RateLimitState,
        rule: RateLimitRule,
        current_time: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Leaky bucket algorithm implementation.
        
        Args:
            state: Current rate limit state
            rule: Rate limiting rule
            current_time: Current timestamp
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        # Initialize if first request
        if state.last_refill == 0:
            state.tokens = 0
            state.last_refill = current_time
        
        # Calculate leak rate and remove tokens
        time_elapsed = current_time - state.last_refill
        leak_rate = rule.requests / rule.window_seconds
        tokens_to_leak = time_elapsed * leak_rate
        
        state.tokens = max(0, state.tokens - tokens_to_leak)
        state.last_refill = current_time
        
        # Check if bucket has capacity
        if state.tokens < rule.burst_size:
            state.tokens += 1
            allowed = True
            remaining = int(rule.burst_size - state.tokens)
        else:
            allowed = False
            remaining = 0
        
        # Calculate reset time
        if state.tokens > 0:
            time_to_empty = state.tokens / leak_rate
            reset_time = current_time + time_to_empty
        else:
            reset_time = current_time
        
        rate_limit_info = {
            "limit": rule.requests,
            "remaining": remaining,
            "reset_time": int(reset_time),
            "retry_after": int(max(0, reset_time - current_time)) if not allowed else 0
        }
        
        return allowed, rate_limit_info

# ===============================================================================
# CORE IMPLEMENTATION CLASSES
# ===============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Production-ready rate limiting middleware with comprehensive features.
    
    This middleware provides advanced rate limiting capabilities including
    multiple algorithms, rule-based configuration, and comprehensive monitoring.
    """
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(self.dispatch)
        self.config = config
        self.logger = logger.bind(component="RateLimitMiddleware")
        
        # Rate limiting state storage
        self._client_states: Dict[str, Dict[str, RateLimitState]] = defaultdict(
            lambda: defaultdict(RateLimitState)
        )
        
        # Metrics tracking
        self._metrics = RateLimitMetrics()
        
        # Algorithm mapping
        self._algorithms = {
            RateLimitAlgorithm.TOKEN_BUCKET: RateLimitAlgorithms.token_bucket,
            RateLimitAlgorithm.SLIDING_WINDOW: RateLimitAlgorithms.sliding_window,
            RateLimitAlgorithm.FIXED_WINDOW: RateLimitAlgorithms.fixed_window,
            RateLimitAlgorithm.LEAKY_BUCKET: RateLimitAlgorithms.leaky_bucket
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_cleanup = time.time()
        
        # Initialize middleware
        self._initialize_middleware()
    
    def _initialize_middleware(self) -> None:
        """Initialize middleware components"""
        try:
            # Sort rules by priority (lower = higher priority)
            self.config.rules.sort(key=lambda rule: rule.priority)
            
            # Initialize metrics tracking
            for rule in self.config.rules:
                self._metrics.rule_violations[rule.name] = 0
                self._metrics.rule_requests[rule.name] = 0
            
            # Start cleanup task if needed
            if self.config.cleanup_interval_seconds > 0:
                self._start_cleanup_task()
            
            self.logger.info(
                "Rate limiting middleware initialized",
                enabled=self.config.enabled,
                rules_count=len(self.config.rules),
                default_algorithm=self.config.default_algorithm
            )
            
        except Exception as e:
            self.logger.error("Failed to initialize rate limiting middleware", error=str(e))
            raise
    
    def _start_cleanup_task(self) -> None:
        """Start background cleanup task"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.cleanup_interval_seconds)
                    await self._cleanup_expired_states()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error("Cleanup task error", error=str(e))
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Main middleware dispatch method.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware in chain
            
        Returns:
            HTTP response
        """
        if not self.config.enabled:
            return await call_next(request)
        
        start_time = time.time()
        current_time = time.time()
        
        try:
            # Update metrics
            self._metrics.total_requests += 1
            
            # Get client identifier
            client_ip = self._get_client_ip(request)
            
            # Check blacklist
            if client_ip in self.config.blacklist_ips:
                self._metrics.blocked_requests += 1
                return self._create_rate_limit_response(
                    "IP address is blacklisted",
                    429,
                    {"limit": 0, "remaining": 0, "reset_time": 0, "retry_after": 86400}
                )
            
            # Check whitelist
            if self.config.enable_whitelist and client_ip in self.config.whitelist_ips:
                response = await call_next(request)
                self._metrics.allowed_requests += 1
                return response
            
            # Apply rate limiting rules
            rate_limit_result = await self._apply_rate_limiting_rules(request, client_ip, current_time)
            
            if not rate_limit_result["allowed"]:
                self._metrics.rate_limited_requests += 1
                
                # Log violation if enabled
                if self.config.log_violations:
                    self._log_rate_limit_violation(request, client_ip, rate_limit_result)
                
                return self._create_rate_limit_response(
                    rate_limit_result.get("message", self.config.custom_error_message),
                    429,
                    rate_limit_result["rate_limit_info"]
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers if enabled
            if self.config.include_headers:
                self._add_rate_limit_headers(response, rate_limit_result["rate_limit_info"])
            
            # Update metrics
            self._metrics.allowed_requests += 1
            self._update_client_metrics(client_ip)
            
            return response
            
        except Exception as e:
            self.logger.error("Rate limiting middleware error", error=str(e))
            # Don't block requests due to middleware errors
            return await call_next(request)
    
    async def _apply_rate_limiting_rules(
        self, 
        request: Request, 
        client_ip: str, 
        current_time: float
    ) -> Dict[str, Any]:
        """
        Apply rate limiting rules to request.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            current_time: Current timestamp
            
        Returns:
            Rate limiting result dictionary
        """
        most_restrictive_result = {
            "allowed": True,
            "rate_limit_info": {
                "limit": float('inf'),
                "remaining": float('inf'),
                "reset_time": current_time,
                "retry_after": 0
            }
        }
        
        # Apply each matching rule
        for rule in self.config.rules:
            if not rule.enabled:
                continue
            
            # Check if rule matches request
            if not rule.matches_request(request):
                continue
            
            # Check if request is exempt
            if rule.is_exempt(request, client_ip):
                continue
            
            # Update rule metrics
            self._metrics.rule_requests[rule.name] += 1
            
            # Get client state key
            state_key = self._get_state_key(request, client_ip, rule)
            
            # Check if client is currently blocked
            client_state = self._client_states[client_ip][state_key]
            if client_state.blocked_until > current_time:
                return {
                    "allowed": False,
                    "message": f"Blocked due to rate limit violation (rule: {rule.name})",
                    "rate_limit_info": {
                        "limit": rule.requests,
                        "remaining": 0,
                        "reset_time": int(client_state.blocked_until),
                        "retry_after": int(client_state.blocked_until - current_time)
                    },
                    "rule": rule.name
                }
            
            # Apply rate limiting algorithm
            algorithm_func = self._algorithms[rule.algorithm]
            allowed, rate_limit_info = algorithm_func(client_state, rule, current_time)
            
            # Update state
            client_state.total_requests += 1
            client_state.last_request = current_time
            
            if client_state.first_request == 0:
                client_state.first_request = current_time
            
            if not allowed:
                client_state.total_violations += 1
                self._metrics.rule_violations[rule.name] += 1
                
                # Apply blocking if configured
                if rule.block_duration_seconds > 0:
                    client_state.blocked_until = current_time + rule.block_duration_seconds
                    client_state.total_blocked_requests += 1
                
                return {
                    "allowed": False,
                    "message": f"Rate limit exceeded (rule: {rule.name})",
                    "rate_limit_info": rate_limit_info,
                    "rule": rule.name
                }
            
            # Track most restrictive limit for headers
            if rate_limit_info["remaining"] < most_restrictive_result["rate_limit_info"]["remaining"]:
                most_restrictive_result["rate_limit_info"] = rate_limit_info
        
        return most_restrictive_result
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _get_state_key(self, request: Request, client_ip: str, rule: RateLimitRule) -> str:
        """
        Generate state key for rate limiting based on scope.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            rule: Rate limiting rule
            
        Returns:
            State key string
        """
        if rule.scope == RateLimitScope.GLOBAL:
            return f"global_{rule.name}"
        elif rule.scope == RateLimitScope.IP:
            return f"ip_{client_ip}_{rule.name}"
        elif rule.scope == RateLimitScope.USER:
            user_id = getattr(request.state, 'user_id', 'anonymous')
            return f"user_{user_id}_{rule.name}"
        elif rule.scope == RateLimitScope.ENDPOINT:
            endpoint = f"{request.method}_{request.url.path}"
            return f"endpoint_{endpoint}_{rule.name}"
        elif rule.scope == RateLimitScope.IP_ENDPOINT:
            endpoint = f"{request.method}_{request.url.path}"
            return f"ip_endpoint_{client_ip}_{endpoint}_{rule.name}"
        else:
            return f"default_{rule.name}"
    
    def _update_client_metrics(self, client_ip: str) -> None:
        """Update per-client metrics"""
        if client_ip not in self._metrics.top_clients:
            self._metrics.top_clients[client_ip] = 0
        
        self._metrics.top_clients[client_ip] += 1
        
        # Keep only top clients to prevent memory bloat
        if len(self._metrics.top_clients) > 1000:
            sorted_clients = sorted(
                self._metrics.top_clients.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self._metrics.top_clients = dict(sorted_clients[:500])
    
    def _log_rate_limit_violation(
        self, 
        request: Request, 
        client_ip: str, 
        rate_limit_result: Dict[str, Any]
    ) -> None:
        """Log rate limit violation"""
        self.logger.warning(
            "Rate limit violation",
            client_ip=client_ip,
            path=request.url.path,
            method=request.method,
            user_agent=request.headers.get("User-Agent", ""),
            rule=rate_limit_result.get("rule", "unknown"),
            remaining=rate_limit_result["rate_limit_info"]["remaining"],
            retry_after=rate_limit_result["rate_limit_info"]["retry_after"]
        )
    
    def _add_rate_limit_headers(self, response: Response, rate_limit_info: Dict[str, Any]) -> None:
        """Add rate limit information to response headers"""
        for header_name, info_key in RATE_LIMIT_HEADERS.items():
            if info_key in rate_limit_info:
                response.headers[header_name] = str(rate_limit_info[info_key])
    
    def _create_rate_limit_response(
        self, 
        message: str, 
        status_code: int, 
        rate_limit_info: Dict[str, Any]
    ) -> JSONResponse:
        """
        Create rate limit exceeded response.
        
        Args:
            message: Error message
            status_code: HTTP status code
            rate_limit_info: Rate limit information
            
        Returns:
            JSON error response
        """
        content = {
            "error": self.config.custom_error_code,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rate_limit": rate_limit_info
        }
        
        headers = {}
        if self.config.include_headers:
            for header_name, info_key in RATE_LIMIT_HEADERS.items():
                if info_key in rate_limit_info:
                    headers[header_name] = str(rate_limit_info[info_key])
        
        return JSONResponse(
            status_code=status_code,
            content=content,
            headers=headers
        )
    
    async def _cleanup_expired_states(self) -> None:
        """Clean up expired client states to prevent memory bloat"""
        current_time = time.time()
        cleanup_threshold = 3600  # Remove states older than 1 hour
        
        clients_to_remove = []
        states_cleaned = 0
        
        for client_id, client_states in self._client_states.items():
            states_to_remove = []
            
            for state_key, state in client_states.items():
                # Remove if no recent activity
                if current_time - state.last_request > cleanup_threshold:
                    states_to_remove.append(state_key)
                    states_cleaned += 1
            
            for state_key in states_to_remove:
                del client_states[state_key]
            
            # Remove client if no states left
            if not client_states:
                clients_to_remove.append(client_id)
        
        for client_id in clients_to_remove:
            del self._client_states[client_id]
        
        # Also cleanup blocked IPs that have expired
        for client_id, client_states in self._client_states.items():
            for state in client_states.values():
                if state.blocked_until > 0 and state.blocked_until <= current_time:
                    state.blocked_until = 0
        
        if states_cleaned > 0:
            self.logger.debug(
                "Rate limit states cleaned up",
                states_cleaned=states_cleaned,
                clients_removed=len(clients_to_remove)
            )
    
    # ===============================================================================
    # PUBLIC METHODS FOR MANAGEMENT
    # ===============================================================================
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get middleware configuration as dictionary"""
        return {
            "config": self.config
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get middleware status and metrics.
        
        Returns:
            Status dictionary with metrics and configuration
        """
        return {
            "status": "active",
            "enabled": self.config.enabled,
            "rules_count": len(self.config.rules),
            "tracked_clients": len(self._client_states),
            "metrics": {
                "total_requests": self._metrics.total_requests,
                "allowed_requests": self._metrics.allowed_requests,
                "blocked_requests": self._metrics.blocked_requests,
                "rate_limited_requests": self._metrics.rate_limited_requests,
                "success_rate": self._metrics.get_success_rate(),
                "rule_violations": dict(self._metrics.rule_violations),
                "rule_requests": dict(self._metrics.rule_requests)
            },
            "top_clients": dict(list(self._metrics.top_clients.items())[:10]),
            "configuration": {
                "default_algorithm": self.config.default_algorithm,
                "requests_per_minute": self.config.requests_per_minute,
                "burst_size": self.config.burst_size,
                "whitelist_enabled": self.config.enable_whitelist,
                "whitelist_size": len(self.config.whitelist_ips),
                "blacklist_size": len(self.config.blacklist_ips)
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on rate limiting middleware.
        
        Returns:
            Health check results
        """
        current_time = time.time()
        
        health_status = {
            "status": "healthy",
            "timestamp": current_time,
            "rules_active": len([rule for rule in self.config.rules if rule.enabled]),
            "tracked_clients": len(self._client_states),
            "cleanup_task_running": self._cleanup_task is not None and not self._cleanup_task.done(),
            "metrics": self.get_status()["metrics"],
            "memory_usage": {
                "client_states": len(self._client_states),
                "total_states": sum(len(states) for states in self._client_states.values())
            }
        }
        
        # Check if too many clients are being tracked (memory concern)
        if len(self._client_states) > self.config.max_tracked_clients:
            health_status["status"] = "degraded"
            health_status["warnings"] = ["High memory usage - too many tracked clients"]
        
        return health_status
    
    async def cleanup(self) -> None:
        """Cleanup middleware resources"""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear all state
        self._client_states.clear()
        self._metrics = RateLimitMetrics()
        
        self.logger.info("Rate limiting middleware cleaned up")
    
    def reset_metrics(self) -> None:
        """Reset rate limiting metrics"""
        self._metrics = RateLimitMetrics()
        
        # Initialize rule metrics
        for rule in self.config.rules:
            self._metrics.rule_violations[rule.name] = 0
            self._metrics.rule_requests[rule.name] = 0
        
        self.logger.info("Rate limiting metrics reset")
    
    def reset_client_state(self, client_ip: str) -> bool:
        """
        Reset rate limiting state for specific client.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if client state was reset, False if not found
        """
        if client_ip in self._client_states:
            del self._client_states[client_ip]
            self.logger.info("Client rate limit state reset", client_ip=client_ip)
            return True
        return False
    
    def add_to_whitelist(self, ip_address: str) -> None:
        """
        Add IP address to whitelist.
        
        Args:
            ip_address: IP address to whitelist
        """
        self.config.whitelist_ips.add(ip_address)
        self.logger.info("IP added to whitelist", ip=ip_address)
    
    def remove_from_whitelist(self, ip_address: str) -> bool:
        """
        Remove IP address from whitelist.
        
        Args:
            ip_address: IP address to remove
            
        Returns:
            True if IP was removed, False if not found
        """
        if ip_address in self.config.whitelist_ips:
            self.config.whitelist_ips.remove(ip_address)
            self.logger.info("IP removed from whitelist", ip=ip_address)
            return True
        return False
    
    def add_to_blacklist(self, ip_address: str) -> None:
        """
        Add IP address to blacklist.
        
        Args:
            ip_address: IP address to blacklist
        """
        self.config.blacklist_ips.add(ip_address)
        self.logger.info("IP added to blacklist", ip=ip_address)
    
    def remove_from_blacklist(self, ip_address: str) -> bool:
        """
        Remove IP address from blacklist.
        
        Args:
            ip_address: IP address to remove
            
        Returns:
            True if IP was removed, False if not found
        """
        if ip_address in self.config.blacklist_ips:
            self.config.blacklist_ips.remove(ip_address)
            self.logger.info("IP removed from blacklist", ip=ip_address)
            return True
        return False
    
    def get_client_status(self, client_ip: str) -> Dict[str, Any]:
        """
        Get detailed status for specific client.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            Client status information
        """
        if client_ip not in self._client_states:
            return {"client_ip": client_ip, "status": "not_tracked"}
        
        client_states = self._client_states[client_ip]
        current_time = time.time()
        
        status = {
            "client_ip": client_ip,
            "status": "tracked",
            "total_states": len(client_states),
            "is_whitelisted": client_ip in self.config.whitelist_ips,
            "is_blacklisted": client_ip in self.config.blacklist_ips,
            "request_count": self._metrics.top_clients.get(client_ip, 0),
            "states": {}
        }
        
        for state_key, state in client_states.items():
            state_info = {
                "total_requests": state.total_requests,
                "total_violations": state.total_violations,
                "tokens": getattr(state, 'tokens', 0),
                "last_request": state.last_request,
                "first_request": state.first_request,
                "is_blocked": state.blocked_until > current_time,
                "blocked_until": state.blocked_until if state.blocked_until > current_time else None,
                "window_requests": getattr(state, 'window_requests', 0),
                "request_times_count": len(getattr(state, 'request_times', []))
            }
            status["states"][state_key] = state_info
        
        return status

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_rate_limit_middleware(
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
    burst_size: int = DEFAULT_BURST_SIZE,
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET,
    **kwargs
) -> RateLimitMiddleware:
    """
    Create rate limiting middleware with simple configuration.
    
    Args:
        requests_per_minute: Requests allowed per minute
        burst_size: Burst size for token bucket
        algorithm: Rate limiting algorithm to use
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured rate limiting middleware
    """
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        burst_size=burst_size,
        default_algorithm=algorithm,
        **kwargs
    )
    
    return RateLimitMiddleware(config)

def create_custom_rate_limit_rules() -> List[RateLimitRule]:
    """
    Create example custom rate limiting rules.
    
    Returns:
        List of configured rate limiting rules
    """
    rules = []
    
    # Strict limits for authentication endpoints
    rules.append(RateLimitRule(
        name="auth_strict",
        description="Strict rate limiting for auth endpoints",
        requests=5,
        window_seconds=MINUTE,
        burst_size=2,
        scope=RateLimitScope.IP,
        path_patterns=["/api/v1/auth/login", "/api/v1/auth/register"],
        methods=["POST"],
        priority=10,
        block_duration_seconds=900  # 15 minutes
    ))
    
    # API endpoints general limits
    rules.append(RateLimitRule(
        name="api_general",
        description="General API rate limiting",
        requests=1000,
        window_seconds=HOUR,
        burst_size=100,
        scope=RateLimitScope.IP,
        path_patterns=["/api/*"],
        priority=100
    ))
    
    # File upload limits
    rules.append(RateLimitRule(
        name="file_uploads",
        description="File upload rate limiting",
        requests=10,
        window_seconds=HOUR,
        burst_size=3,
        scope=RateLimitScope.USER,
        path_patterns=["/api/v1/files/upload"],
        methods=["POST"],
        priority=50
    ))
    
    # Admin endpoints
    rules.append(RateLimitRule(
        name="admin_operations",
        description="Admin operations rate limiting",
        requests=100,
        window_seconds=HOUR,
        burst_size=10,
        scope=RateLimitScope.USER,
        path_patterns=["/api/v1/admin/*"],
        priority=25
    ))
    
    # Search endpoints
    rules.append(RateLimitRule(
        name="search_endpoints",
        description="Search functionality rate limiting",
        requests=200,
        window_seconds=MINUTE,
        burst_size=50,
        scope=RateLimitScope.IP,
        path_patterns=["/api/v1/search", "/api/v1/query"],
        methods=["GET", "POST"],
        priority=75
    ))
    
    return rules

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "RateLimitConfig",
    "RateLimitRule",
    "RateLimitState",
    "RateLimitMetrics",
    "RateLimitAlgorithm",
    "RateLimitScope",
    "RateLimitAlgorithms",
    "RateLimitMiddleware",
    "create_rate_limit_middleware",
    "create_custom_rate_limit_rules"
]
                """
YMERA Enterprise - Rate Limiting Middleware
Production-Ready API Rate Limiting - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import asyncio
import hashlib
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports (alphabetical)
import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

# Local imports (alphabetical)
from config.settings import get_settings

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.rate_limiter")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Default rate limits
DEFAULT_REQUESTS_PER_MINUTE = 1000
DEFAULT_REQUESTS_PER_HOUR = 10000
DEFAULT_REQUESTS_PER_DAY = 100000
DEFAULT_BURST_SIZE = 50

# Time windows in seconds
MINUTE = 60
HOUR = 3600
DAY = 86400

# Rate limiting algorithms
class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithm types"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"

# Rate limit scopes
class RateLimitScope(str, Enum):
    """Rate limiting scope types"""
    GLOBAL = "global"           # Global rate limit
    IP = "ip"                   # Per IP address
    USER = "user"               # Per authenticated user
    ENDPOINT = "endpoint"       # Per API endpoint
    IP_ENDPOINT = "ip_endpoint" # Per IP + endpoint combination

# Headers for rate limit information
RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit": "rate_limit",
    "X-RateLimit-Remaining": "remaining",
    "X-RateLimit-Reset": "reset_time",
    "X-RateLimit-RetryAfter": "retry_after"
}

# ===============================================================================
# DATA MODELS & SCHEMAS
# ===============================================================================

@dataclass
class RateLimitRule:
    """
    Individual rate limiting rule configuration.
    
    This class defines a single rate limiting rule with specific parameters
    for requests, time window, and application scope.
    """
    
    # Rule identification
    name: str
    description: str = ""
    
    # Rate limiting parameters
    requests: int = DEFAULT_REQUESTS_PER_MINUTE
    window_seconds: int = MINUTE
    burst_size: int = DEFAULT_BURST_SIZE
    
    # Rule configuration
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    scope: RateLimitScope = RateLimitScope.IP
    
    # Path and method matching
    path_patterns: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=lambda: ["*"])
    
    # Advanced settings
    enabled: bool = True
    priority: int = 100  # Lower numbers = higher priority
    block_duration_seconds: int = 0  # 0 = no blocking, >0 = block duration
    
    # Exemptions
    exempt_ips: Set[str] = field(default_factory=set)
    exempt_user_agents: Set[str] = field(default_factory=set)
    exempt_headers: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate rule configuration"""
        if self.requests <= 0:
            raise ValueError("Requests must be greater than 0")
        
        if self.window_seconds <= 0:
            raise ValueError("Window seconds must be greater than 0")
        
        if self.burst_size <= 0:
            self.burst_size = self.requests
    
    def matches_request(self, request: Request) -> bool:
        """
        Check if this rule applies to the given request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if rule applies to request, False otherwise
        """
        # Check method matching
        if "*" not in self.methods:
            if request.method not in self.methods:
                return False
        
        # Check path pattern matching
        if self.path_patterns:
            path = request.url.path
            matches_pattern = False
            
            for pattern in self.path_patterns:
                if pattern.endswith("*"):
                    # Prefix matching
                    if path.startswith(pattern[:-1]):
                        matches_pattern = True
                        break
                elif pattern == path:
                    # Exact matching
                    matches_pattern = True
                    break
            
            if not matches_pattern:
                return False
        
        return True
    
    def is_exempt(self, request: Request, client_ip: str) -> bool:
        """
        Check if request is exempt from this rate limit rule.
        
        Args:
            request: FastAPI request object
            client_ip: Client IP address
            
        Returns:
            True if request is exempt, False otherwise
        """
        # Check IP exemptions
        if client_ip in self.exempt_ips:
            return True
        
        # Check User-Agent exemptions
        user_agent = request.headers.get("User-Agent", "")
        if user_agent in self.exempt_user_agents:
            return True
        
        # Check custom header exemptions
        for header_name, header_value in self.exempt_headers.items():
            if request.headers.get(header_name) == header_value:
                return True
        
        return False

@dataclass
class RateLimitConfig:
    """
    Comprehensive rate limiting middleware configuration.
    
    This class manages all rate limiting settings including multiple rules,
    storage backends, monitoring, and advanced security features.
    """
    
    # Basic configuration
    enabled: bool = True
    default_algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    
    # Default rate limits
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE
    requests_per_hour: int = DEFAULT_REQUESTS_PER_HOUR
    requests_per_day: int = DEFAULT_REQUESTS_PER_DAY
    burst_size: int = DEFAULT_BURST_SIZE
    
    # Rate limiting rules
    rules: List[RateLimitRule] = field(default_factory=list)
    
    # Global settings
    enable_whitelist: bool = True
    whitelist_ips: Set[str] = field(default_factory=set)
    blacklist_ips: Set[str] = field(default_factory=set)
    
    # Response configuration
    include_headers: bool = True
    custom_error_message: str = "Rate limit exceeded"
    custom_error_code: str = "RATE_LIMIT_EXCEEDED"
    
    # Storage and cleanup
    cleanup_interval_seconds: int = 300  # 5 minutes
    max_tracked_clients: int = 100000
    
    # Monitoring and logging
    log_violations: bool = True
    log_level: str = "INFO"
    track_metrics: bool = True
    
    # Advanced features
    enable_adaptive_limits: bool = False
    adaptive_factor: float = 1.5
    enable_distributed: bool = False
    redis_url: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default rules if none provided"""
        if not self.rules:
            self._create_default_rules()
    
    def _create_default_rules(self):
        """Create default rate limiting rules"""
        # Global rate limit
        self.rules.append(RateLimitRule(
            name="global_per_minute",
            description="Global requests per minute",
            requests=self.requests_per_minute,
            window_seconds=MINUTE,
            burst_size=self.burst_size,
            scope=RateLimitScope.IP,
            priority=100
        ))
        
        # Hourly rate limit
        self.rules.append(RateLimitRule(
            name="global_per_hour",
            description="Global requests per hour",
            requests=self.requests_per_hour,
            window_seconds=HOUR,
            burst_size=self.burst_size * 10,
            scope=RateLimitScope.IP,
            priority=200
        ))
        
        # API endpoint specific limits
        self.rules.append(RateLimitRule(
            name="auth_endpoints",
            description="Authentication endpoints rate limit",