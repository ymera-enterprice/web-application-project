"""
YMERA Enterprise Rate Limiter Middleware
Advanced rate limiting with adaptive algorithms, multi-tier limits, and learning capabilities
"""

import time
import asyncio
import hashlib
import json
import math
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import logging

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"


class RateLimitTier(Enum):
    """Rate limit tiers for different user types"""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"
    ADMIN = "admin"
    SYSTEM = "system"


class RateLimitConfig:
    """Rate limit configuration"""
    
    def __init__(
        self,
        requests: int,
        window: int,
        burst: Optional[int] = None,
        tier: RateLimitTier = RateLimitTier.ANONYMOUS,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    ):
        self.requests = requests
        self.window = window  # seconds
        self.burst = burst or requests
        self.tier = tier
        self.algorithm = algorithm


class AdaptiveRateLimiter:
    """Adaptive rate limiter that learns from system load and user behavior"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.base_configs = {
            RateLimitTier.ANONYMOUS: RateLimitConfig(100, 3600),  # 100/hour
            RateLimitTier.AUTHENTICATED: RateLimitConfig(1000, 3600),  # 1000/hour
            RateLimitTier.PREMIUM: RateLimitConfig(5000, 3600),  # 5000/hour
            RateLimitTier.ADMIN: RateLimitConfig(10000, 3600),  # 10000/hour
            RateLimitTier.SYSTEM: RateLimitConfig(50000, 3600),  # 50000/hour
        }
        
        # Adaptive parameters
        self.load_threshold_high = 0.8
        self.load_threshold_low = 0.3
        self.adaptation_factor = 0.1
        self.learning_window = 300  # 5 minutes
        
        # System metrics for adaptation
        self.system_load_history = deque(maxlen=100)
        self.response_time_history = deque(maxlen=1000)
        self.error_rate_history = deque(maxlen=100)
        
        self.logger = logging.getLogger(__name__)

    async def is_allowed(
        self, 
        identifier: str, 
        tier: RateLimitTier,
        endpoint: str = "default"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is allowed under current rate limits"""
        
        # Get current configuration (potentially adapted)
        config = await self._get_adaptive_config(tier, endpoint)
        
        # Apply rate limiting algorithm
        if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            allowed, metadata = await self._token_bucket_check(identifier, config)
        elif config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            allowed, metadata = await self._sliding_window_check(identifier, config)
        elif config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            allowed, metadata = await self._fixed_window_check(identifier, config)
        else:  # ADAPTIVE
            allowed, metadata = await self._adaptive_check(identifier, config, endpoint)
        
        # Add tier information to metadata
        metadata.update({
            "tier": tier.value,
            "algorithm": config.algorithm.value,
            "endpoint": endpoint
        })
        
        return allowed, metadata

    async def _get_adaptive_config(
        self, 
        tier: RateLimitTier, 
        endpoint: str
    ) -> RateLimitConfig:
        """Get potentially adapted rate limit configuration"""
        base_config = self.base_configs[tier]
        
        # Check if we should adapt based on system metrics
        current_load = await self._get_current_system_load()
        adaptation_factor = await self._calculate_adaptation_factor(current_load, endpoint)
        
        if abs(adaptation_factor - 1.0) > 0.05:  # Only adapt if significant change
            adapte if abs(adaptation_factor - 1.0) > 0.05:  # Only adapt if significant change
            adapted_requests = int(base_config.requests * adaptation_factor)
            adapted_burst = int(base_config.burst * adaptation_factor)
            
            self.logger.info(
                f"Adapting rate limits for {tier.value} on {endpoint}: "
                f"{base_config.requests} -> {adapted_requests} requests/hour"
            )
            
            return RateLimitConfig(
                requests=max(1, adapted_requests),  # Never go below 1
                window=base_config.window,
                burst=max(1, adapted_burst),
                tier=tier,
                algorithm=base_config.algorithm
            )
        
        return base_config

    async def _calculate_adaptation_factor(self, current_load: float, endpoint: str) -> float:
        """Calculate how much to adapt rate limits based on system conditions"""
        
        # Get endpoint-specific metrics
        endpoint_error_rate = await self._get_endpoint_error_rate(endpoint)
        endpoint_response_time = await self._get_endpoint_response_time(endpoint)
        
        # Base adaptation on system load
        if current_load > self.load_threshold_high:
            # High load - reduce rate limits
            load_factor = 1.0 - (current_load - self.load_threshold_high) * self.adaptation_factor
        elif current_load < self.load_threshold_low:
            # Low load - increase rate limits
            load_factor = 1.0 + (self.load_threshold_low - current_load) * self.adaptation_factor
        else:
            # Normal load - no adaptation
            load_factor = 1.0
        
        # Adjust based on error rate
        if endpoint_error_rate > 0.05:  # 5% error rate threshold
            error_factor = 1.0 - (endpoint_error_rate * 0.5)  # Reduce by up to 50%
        else:
            error_factor = 1.0
        
        # Adjust based on response time
        if endpoint_response_time > 2.0:  # 2 second threshold
            response_factor = 1.0 - min(0.3, (endpoint_response_time - 2.0) * 0.1)
        else:
            response_factor = 1.0
        
        # Combine factors
        final_factor = load_factor * error_factor * response_factor
        
        # Clamp to reasonable bounds
        return max(0.1, min(2.0, final_factor))

    async def _token_bucket_check(
        self, 
        identifier: str, 
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, Any]]:
        """Token bucket rate limiting algorithm"""
        
        key = f"rate_limit:token_bucket:{identifier}"
        now = time.time()
        
        # Get current bucket state
        bucket_data = await self.redis.hmget(key, "tokens", "last_refill")
        tokens = float(bucket_data[0] or config.burst)
        last_refill = float(bucket_data[1] or now)
        
        # Calculate tokens to add based on time elapsed
        time_elapsed = now - last_refill
        tokens_to_add = time_elapsed * (config.requests / config.window)
        tokens = min(config.burst, tokens + tokens_to_add)
        
        if tokens >= 1.0:
            # Allow request and consume token
            tokens -= 1.0
            await self.redis.hmset(key, {
                "tokens": str(tokens),
                "last_refill": str(now)
            })
            await self.redis.expire(key, config.window)
            
            return True, {
                "remaining": int(tokens),
                "reset_time": now + (config.burst - tokens) * (config.window / config.requests),
                "retry_after": None
            }
        else:
            # Rate limited
            retry_after = (1.0 - tokens) * (config.window / config.requests)
            return False, {
                "remaining": 0,
                "reset_time": now + retry_after,
                "retry_after": retry_after
            }

    async def _sliding_window_check(
        self, 
        identifier: str, 
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, Any]]:
        """Sliding window rate limiting algorithm"""
        
        key = f"rate_limit:sliding:{identifier}"
        now = time.time()
        window_start = now - config.window
        
        # Use Redis sorted set for sliding window
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Execute pipeline
        results = await pipe.execute()
        current_count = results[1]
        
        if current_count < config.requests:
            # Allow request
            await self.redis.zadd(key, {str(now): now})
            await self.redis.expire(key, config.window)
            
            remaining = config.requests - current_count - 1
            reset_time = now + config.window
            
            return True, {
                "remaining": remaining,
                "reset_time": reset_time,
                "retry_after": None
            }
        else:
            # Get oldest request time to calculate retry_after
            oldest_requests = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest_requests:
                oldest_time = oldest_requests[0][1]
                retry_after = oldest_time + config.window - now
            else:
                retry_after = config.window
            
            return False, {
                "remaining": 0,
                "reset_time": now + retry_after,
                "retry_after": retry_after
            }

    async def _fixed_window_check(
        self, 
        identifier: str, 
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, Any]]:
        """Fixed window rate limiting algorithm"""
        
        now = time.time()
        window_start = int(now // config.window) * config.window
        key = f"rate_limit:fixed:{identifier}:{window_start}"
        
        current_count = await self.redis.get(key)
        current_count = int(current_count or 0)
        
        if current_count < config.requests:
            # Allow request
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, config.window)
            await pipe.execute()
            
            remaining = config.requests - current_count - 1
            reset_time = window_start + config.window
            
            return True, {
                "remaining": remaining,
                "reset_time": reset_time,
                "retry_after": None
            }
        else:
            # Rate limited
            reset_time = window_start + config.window
            retry_after = reset_time - now
            
            return False, {
                "remaining": 0,
                "reset_time": reset_time,
                "retry_after": retry_after
            }

    async def _adaptive_check(
        self, 
        identifier: str, 
        config: RateLimitConfig, 
        endpoint: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Adaptive rate limiting that combines multiple algorithms"""
        
        # Use sliding window as base algorithm
        allowed, metadata = await self._sliding_window_check(identifier, config)
        
        # Apply additional adaptive logic
        if not allowed:
            # Check if user has good behavior history
            user_reputation = await self._get_user_reputation(identifier)
            if user_reputation > 0.8:  # Good user, give some leeway
                # Allow burst for good users
                burst_key = f"rate_limit:adaptive_burst:{identifier}"
                burst_used = await self.redis.get(burst_key)
                burst_used = int(burst_used or 0)
                
                if burst_used < config.burst // 2:  # Allow up to half burst limit
                    await self.redis.incr(burst_key)
                    await self.redis.expire(burst_key, config.window)
                    
                    metadata["burst_used"] = True
                    metadata["remaining"] = config.burst // 2 - burst_used - 1
                    return True, metadata
        
        return allowed, metadata

    async def _get_current_system_load(self) -> float:
        """Get current system load metric (0.0 to 1.0)"""
        
        # This would typically integrate with system monitoring
        # For now, simulate based on recent metrics
        
        if len(self.system_load_history) == 0:
            return 0.5  # Default moderate load
        
        # Simple average of recent load measurements
        return sum(self.system_load_history) / len(self.system_load_history)

    async def _get_endpoint_error_rate(self, endpoint: str) -> float:
        """Get error rate for specific endpoint"""
        
        key = f"metrics:errors:{endpoint}"
        error_data = await self.redis.hmget(key, "errors", "total")
        
        errors = int(error_data[0] or 0)
        total = int(error_data[1] or 1)
        
        return errors / total if total > 0 else 0.0

    async def _get_endpoint_response_time(self, endpoint: str) -> float:
        """Get average response time for endpoint"""
        
        key = f"metrics:response_time:{endpoint}"
        response_data = await self.redis.hmget(key, "total_time", "count")
        
        total_time = float(response_data[0] or 0)
        count = int(response_data[1] or 1)
        
        return total_time / count if count > 0 else 0.0

    async def _get_user_reputation(self, identifier: str) -> float:
        """Get user reputation score (0.0 to 1.0)"""
        
        key = f"reputation:{identifier}"
        reputation_data = await self.redis.hmget(key, "score", "updated")
        
        score = float(reputation_data[0] or 0.5)  # Default neutral reputation
        return min(1.0, max(0.0, score))

    async def record_request_metrics(
        self, 
        identifier: str, 
        endpoint: str, 
        response_time: float, 
        status_code: int
    ):
        """Record request metrics for adaptive learning"""
        
        now = time.time()
        
        # Update endpoint metrics
        error_key = f"metrics:errors:{endpoint}"
        time_key = f"metrics:response_time:{endpoint}"
        
        pipe = self.redis.pipeline()
        
        # Update error metrics
        if status_code >= 400:
            pipe.hincrby(error_key, "errors", 1)
        pipe.hincrby(error_key, "total", 1)
        pipe.expire(error_key, 3600)  # 1 hour TTL
        
        # Update response time metrics
        pipe.hincrbyfloat(time_key, "total_time", response_time)
        pipe.hincrby(time_key, "count", 1)
        pipe.expire(time_key, 3600)  # 1 hour TTL
        
        # Update user reputation based on behavior
        if status_code < 400:
            reputation_key = f"reputation:{identifier}"
            pipe.hincrbyfloat(reputation_key, "score", 0.001)  # Small positive increment
            pipe.hset(reputation_key, "updated", str(now))
            pipe.expire(reputation_key, 86400 * 30)  # 30 day TTL
        
        await pipe.execute()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting"""
    
    def __init__(
        self,
        app: ASGIApp,
        redis_url: str = "redis://localhost:6379",
        identifier_func: Optional[Callable] = None,
        tier_func: Optional[Callable] = None,
        skip_paths: Optional[List[str]] = None,
        custom_response: Optional[Callable] = None
    ):
        super().__init__(app)
        self.redis_url = redis_url
        self.identifier_func = identifier_func or self._default_identifier
        self.tier_func = tier_func or self._default_tier
        self.skip_paths = skip_paths or ["/health", "/metrics"]
        self.custom_response = custom_response
        self.rate_limiter = None
        
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter"""
        
        # Initialize rate limiter if needed
        if self.rate_limiter is None:
            redis_client = redis.from_url(self.redis_url)
            self.rate_limiter = AdaptiveRateLimiter(redis_client)
        
        # Skip rate limiting for certain paths
        if any(request.url.path.startswith(skip_path) for skip_path in self.skip_paths):
            return await call_next(request)
        
        # Get identifier and tier for this request
        identifier = await self.identifier_func(request)
        tier = await self.tier_func(request)
        endpoint = f"{request.method}:{request.url.path}"
        
        start_time = time.time()
        
        # Check rate limits
        allowed, metadata = await self.rate_limiter.is_allowed(identifier, tier, endpoint)
        
        if not allowed:
            # Rate limited - return error response
            if self.custom_response:
                return await self.custom_response(request, metadata)
            else:
                return await self._default_rate_limit_response(metadata)
        
        # Process request
        response = await call_next(request)
        
        # Record metrics for adaptive learning
        response_time = time.time() - start_time
        await self.rate_limiter.record_request_metrics(
            identifier, endpoint, response_time, response.status_code
        )
        
        # Add rate limit headers
        response.headers.update(self._get_rate_limit_headers(metadata))
        
        return response

    async def _default_identifier(self, request: Request) -> str:
        """Default function to identify requests (by IP)"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _default_tier(self, request: Request) -> RateLimitTier:
        """Default function to determine user tier"""
        # This would typically check authentication/authorization
        auth_header = request.headers.get("Authorization")
        if auth_header:
            return RateLimitTier.AUTHENTICATED
        return RateLimitTier.ANONYMOUS

    async def _default_rate_limit_response(self, metadata: Dict[str, Any]) -> JSONResponse:
        """Default rate limit exceeded response"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "detail": f"Too many requests for {metadata.get('tier', 'unknown')} tier",
                "retry_after": metadata.get("retry_after"),
                "reset_time": metadata.get("reset_time")
            },
            headers=self._get_rate_limit_headers(metadata)
        )

    def _get_rate_limit_headers(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Generate rate limit headers"""
        headers = {
            "X-RateLimit-Remaining": str(metadata.get("remaining", 0)),
            "X-RateLimit-Reset": str(int(metadata.get("reset_time", 0))),
            "X-RateLimit-Tier": metadata.get("tier", "unknown"),
            "X-RateLimit-Algorithm": metadata.get("algorithm", "unknown")
        }
        
        if metadata.get("retry_after"):
            headers["Retry-After"] = str(int(metadata["retry_after"]))
        
        if metadata.get("burst_used"):
            headers["X-RateLimit-Burst-Used"] = "true"
        
        return headers


# Usage example
async def get_user_tier(request: Request) -> RateLimitTier:
    """Custom tier determination based on user authentication"""
    
    # Check for API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Validate API key and determine tier
        # This would typically query your user database
        if api_key.startswith("premium_"):
            return RateLimitTier.PREMIUM
        elif api_key.startswith("admin_"):
            return RateLimitTier.ADMIN
        else:
            return RateLimitTier.AUTHENTICATED
    
    # Check for JWT token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Validate JWT and extract user info
        # Implementation would decode JWT and check user permissions
        return RateLimitTier.AUTHENTICATED
    
    return RateLimitTier.ANONYMOUS


async def custom_identifier(request: Request) -> str:
    """Custom identifier that combines IP and user info"""
    
    # Try to get user ID from JWT
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        # Extract user ID from JWT (simplified)
        # In reality, you'd decode and validate the JWT
        user_id = "user_from_jwt"  # Placeholder
        return f"user:{user_id}"
    
    # Fall back to IP-based identification
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return f"ip:{ip}"


# FastAPI integration example
"""
from fastapi import FastAPI

app = FastAPI()

# Add rate limiting middleware
app.add_middleware(
    RateLimiterMiddleware,
    redis_url="redis://localhost:6379/0",
    identifier_func=custom_identifier,
    tier_func=get_user_tier,
    skip_paths=["/health", "/metrics", "/docs", "/openapi.json"]
)

@app.get("/api/data")
async def get_data():
    return {"data": "This endpoint is rate limited"}

@app.get("/api/premium")
async def premium_endpoint():
    return {"data": "This endpoint has higher limits for premium users"}
"""