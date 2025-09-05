"""
YMERA Enterprise Multi-LLM Manager - Production Ready
Advanced AI provider management with intelligent routing, learning integration, and enterprise features
"""

import asyncio
import aiohttp
import time
import json
import hashlib
import random
from typing import Dict, List, Optional, Any, Union, AsyncGenerator, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import ssl
from urllib.parse import urlparse
import numpy as np

# AI Provider imports
import openai
import anthropic
import google.generativeai as genai
from groq import Groq

# Monitoring and metrics
from prometheus_client import Counter, Histogram, Gauge, Summary
import psutil
import traceback

# Circuit breaker pattern
from functools import wraps
from collections import defaultdict, deque

class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GEMINI = "gemini"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"  # Local models
    AZURE_OPENAI = "azure_openai"

class ModelTier(IntEnum):
    """Model performance tiers for intelligent routing"""
    PREMIUM = 1      # GPT-4, Claude-3-Opus
    STANDARD = 2     # GPT-3.5, Claude-3-Sonnet
    FAST = 3        # Groq, local models
    SPECIALIZED = 4  # Code-specific, math-specific models

class RequestType(Enum):
    """Request types for specialized routing"""
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    DOCUMENTATION = "documentation"
    SECURITY_ANALYSIS = "security_analysis"
    GENERAL_CHAT = "general_chat"
    REASONING = "reasoning"
    CREATIVE = "creative"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"

@dataclass
class ModelCapabilities:
    """Model capability specification"""
    max_tokens: int
    context_window: int
    supports_functions: bool
    supports_vision: bool
    supports_code: bool
    cost_per_token: float
    tier: ModelTier
    specialties: List[RequestType] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)

@dataclass
class LLMUsage:
    """Enhanced usage tracking"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    processing_time: float = 0.0
    model_tier: ModelTier = ModelTier.STANDARD

@dataclass
class LLMResponse:
    """Comprehensive LLM response with metadata"""
    content: str
    provider: str
    model: str
    usage: LLMUsage
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = ""
    quality_score: float = 0.0
    confidence_score: float = 0.0
    reasoning_steps: List[str] = field(default_factory=list)
    function_calls: List[Dict] = field(default_factory=list)
    tool_usage: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)

@dataclass
class LLMRequest:
    """Enhanced LLM request with routing hints"""
    messages: List[Dict[str, str]]
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    system_prompt: Optional[str] = None
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None
    timeout: int = 60
    request_type: RequestType = RequestType.GENERAL_CHAT
    priority: int = 1  # 1-10, higher is more priority
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    require_reasoning: bool = False
    prefer_accuracy: bool = False
    prefer_speed: bool = False
    cost_limit: Optional[float] = None
    context_metadata: Dict[str, Any] = field(default_factory=dict)

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open" 
    HALF_OPEN = "half_open"

class CircuitBreaker:
    """Circuit breaker for provider fault tolerance"""
    
    def __init__(self, failure_threshold: int = 5, 
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.failure_count = 0
                else:
                    raise RuntimeError("Circuit breaker is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                return result
                
            except self.expected_exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                
                raise e

class AdaptiveRateLimiter:
    """Adaptive rate limiter with learning capabilities"""
    
    def __init__(self, initial_limit: int = 50, window_size: int = 60):
        self.current_limit = initial_limit
        self.initial_limit = initial_limit
        self.window_size = window_size
        self.requests = deque()
        self.success_rate = 1.0
        self.avg_response_time = 1.0
        self._lock = asyncio.Lock()
        self.adaptation_factor = 0.1
    
    async def acquire(self) -> bool:
        """Acquire rate limit token with adaptive behavior"""
        async with self._lock:
            now = time.time()
            
            # Clean old requests
            while self.requests and now - self.requests[0]['timestamp'] > self.window_size:
                self.requests.popleft()
            
            # Check current rate
            if len(self.requests) >= self.current_limit:
                return False
            
            # Record request
            self.requests.append({
                'timestamp': now,
                'success': True  # Will be updated later
            })
            
            return True
    
    async def record_response(self, success: bool, response_time: float):
        """Record response for adaptive learning"""
        async with self._lock:
            # Update success rate
            recent_requests = [r for r in self.requests 
                             if time.time() - r['timestamp'] < self.window_size]
            
            if recent_requests:
                successes = sum(1 for r in recent_requests if r.get('success', True))
                self.success_rate = successes / len(recent_requests)
            
            # Update average response time
            self.avg_response_time = (self.avg_response_time * 0.9 + response_time * 0.1)
            
            # Adaptive adjustment
            if self.success_rate > 0.95 and self.avg_response_time < 2.0:
                # Increase rate if performing well
                self.current_limit = min(
                    self.current_limit * (1 + self.adaptation_factor),
                    self.initial_limit * 2
                )
            elif self.success_rate < 0.8 or self.avg_response_time > 5.0:
                # Decrease rate if struggling
                self.current_limit = max(
                    self.current_limit * (1 - self.adaptation_factor),
                    self.initial_limit * 0.5
                )

class IntelligentCache:
    """Intelligent caching with semantic similarity and learning"""
    
    def __init__(self, max_size: int = 10000, ttl: int = 3600):
        self.cache: Dict[str, Dict] = {}
        self.access_times: Dict[str, float] = {}
        self.hit_counts: Dict[str, int] = defaultdict(int)
        self.max_size = max_size
        self.ttl = ttl
        self._lock = asyncio.Lock()
        self.embedding_cache: Dict[str, np.ndarray] = {}
        
    def _get_cache_key(self, request: LLMRequest) -> str:
        """Generate semantic cache key"""
        # Create a content-based key
        messages_content = json.dumps([msg['content'] for msg in request.messages], sort_keys=True)
        params = {
            'temperature': request.temperature,
            'max_tokens': request.max_tokens,
            'request_type': request.request_type.value
        }
        params_str = json.dumps(params, sort_keys=True)
        
        return hashlib.sha256((messages_content + params_str).encode()).hexdigest()
    
    def _simple_embedding(self, text: str) -> np.ndarray:
        """Simple text embedding for similarity (in production, use proper embeddings)"""
        # Basic word frequency embedding
        words = text.lower().split()
        word_freq = defaultdict(int)
        for word in words:
            word_freq[word] += 1
        
        # Convert to vector (top 100 most common words as features)
        common_words = sorted(word_freq.keys())[:100]
        vector = np.array([word_freq.get(word, 0) for word in common_words])
        
        # Normalize
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between texts"""
        if text1 in self.embedding_cache:
            emb1 = self.embedding_cache[text1]
        else:
            emb1 = self._simple_embedding(text1)
            self.embedding_cache[text1] = emb1
        
        if text2 in self.embedding_cache:
            emb2 = self.embedding_cache[text2]
        else:
            emb2 = self._simple_embedding(text2)
            self.embedding_cache[text2] = emb2
        
        # Cosine similarity
        if np.linalg.norm(emb1) == 0 or np.linalg.norm(emb2) == 0:
            return 0.0
        
        return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    
    async def get(self, request: LLMRequest, similarity_threshold: float = 0.85) -> Optional[LLMResponse]:
        """Get cached response with semantic similarity matching"""
        async with self._lock:
            cache_key = self._get_cache_key(request)
            
            # Direct key match
            if cache_key in self.cache:
                cached_data = self.cache[cache_key]
                if time.time() - cached_data['timestamp'] < self.ttl:
                    self.access_times[cache_key] = time.time()
                    self.hit_counts[cache_key] += 1
                    return cached_data['response']
                else:
                    del self.cache[cache_key]
            
            # Semantic similarity search for similar requests
            request_content = ' '.join([msg['content'] for msg in request.messages])
            
            best_match_key = None
            best_similarity = 0.0
            
            for key, cached_data in self.cache.items():
                if time.time() - cached_data['timestamp'] >= self.ttl:
                    continue
                
                cached_content = cached_data['request_content']
                similarity = self._semantic_similarity(request_content, cached_content)
                
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match_key = key
            
            if best_match_key:
                cached_data = self.cache[best_match_key]
                self.access_times[best_match_key] = time.time()
                self.hit_counts[best_match_key] += 1
                
                # Modify response to indicate it's from semantic cache
                response = cached_data['response']
                response.metadata['cache_type'] = 'semantic'
                response.metadata['similarity_score'] = best_similarity
                
                return response
            
            return None
    
    async def put(self, request: LLMRequest, response: LLMResponse):
        """Cache response with intelligent eviction"""
        async with self._lock:
            cache_key = self._get_cache_key(request)
            request_content = ' '.join([msg['content'] for msg in request.messages])
            
            # Evict if cache is full
            if len(self.cache) >= self.max_size:
                await self._evict_least_valuable()
            
            self.cache[cache_key] = {
                'response': response,
                'timestamp': time.time(),
                'request_content': request_content,
                'quality_score': response.quality_score
            }
            self.access_times[cache_key] = time.time()
    
    async def _evict_least_valuable(self):
        """Evict least valuable cache entries"""
        # Score = (hit_count * quality_score) / age_hours
        current_time = time.time()
        scores = {}
        
        for key in self.cache.keys():
            age_hours = (current_time - self.access_times.get(key, current_time)) / 3600
            hit_count = self.hit_counts.get(key, 1)
            quality = self.cache[key].get('quality_score', 0.5)
            
            scores[key] = (hit_count * quality) / max(age_hours, 0.1)
        
        # Remove 10% of lowest scoring entries
        to_remove = int(len(self.cache) * 0.1)
        lowest_scoring = sorted(scores.keys(), key=lambda k: scores[k])[:to_remove]
        
        for key in lowest_scoring:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
            self.hit_counts.pop(key, None)

class QualityAssessment:
    """AI response quality assessment"""
    
    @staticmethod
    def assess_response_quality(request: LLMRequest, response: LLMResponse) -> float:
        """Assess response quality based on multiple factors"""
        score = 0.5  # Base score
        
        # Length appropriateness
        response_length = len(response.content)
        if request.request_type in [RequestType.DOCUMENTATION, RequestType.CODE_ANALYSIS]:
            # Longer responses expected
            if response_length > 500:
                score += 0.1
        elif request.request_type == RequestType.GENERAL_CHAT:
            # Moderate length preferred
            if 100 < response_length < 1000:
                score += 0.1
        
        # Content quality indicators
        if response.content:
            # Check for structured content
            if any(marker in response.content for marker in ['```', '1.', '2.', '- ']):
                score += 0.1
            
            # Check for completeness (doesn't end abruptly)
            if response.content.rstrip().endswith(('.', '!', '?', '```')):
                score += 0.1
            
            # Check for code quality if code generation
            if request.request_type == RequestType.CODE_GENERATION:
                if '```' in response.content and 'def ' in response.content:
                    score += 0.2
        
        # Provider tier bonus
        if response.usage.model_tier == ModelTier.PREMIUM:
            score += 0.1
        elif response.usage.model_tier == ModelTier.STANDARD:
            score += 0.05
        
        # Response time penalty
        if response.usage.processing_time > 10:
            score -= 0.1
        
        return max(0.0, min(1.0, score))

class ProviderClient:
    """Enhanced provider client with enterprise features"""
    
    def __init__(self, provider: LLMProvider, api_key: str, 
                 base_url: str = None, rate_limit: int = 50,
                 model_capabilities: Dict[str, ModelCapabilities] = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limiter = AdaptiveRateLimiter(rate_limit)
        self.circuit_breaker = CircuitBreaker()
        self.client = None
        self.session = None
        self.is_healthy = True
        self.last_error = None
        self.logger = logging.getLogger(f"{__name__}.{provider.value}")
        self.model_capabilities = model_capabilities or {}
        
        # Metrics
        self.request_count = Counter(
            f'llm_requests_total_{provider.value}', 
            'Total LLM requests', 
            ['model', 'status']
        )
        self.response_time = Histogram(
            f'llm_response_time_{provider.value}',
            'LLM response time in seconds',
            ['model']
        )
        self.error_count = Counter(
            f'llm_errors_total_{provider.value}',
            'Total LLM errors',
            ['error_type']
        )
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self._ssl_context = ssl.create_default_context()
    
    async def initialize(self):
        """Initialize provider with comprehensive setup"""
        try:
            timeout = aiohttp.ClientTimeout(total=120, connect=30)
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                ssl=self._ssl_context,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={'User-Agent': 'YMERA-Enterprise/2.0'}
            )
            
            if self.provider == LLMProvider.OPENAI:
                self.client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    http_client=self.session
                )
            elif self.provider == LLMProvider.ANTHROPIC:
                self.client = anthropic.AsyncAnthropic(
                    api_key=self.api_key,
                    http_client=self.session
                )
            elif self.provider == LLMProvider.GEMINI:
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel('gemini-pro')
            elif self.provider == LLMProvider.GROQ:
                self.client = Groq(api_key=self.api_key)
            elif self.provider == LLMProvider.DEEPSEEK:
                self.base_url = self.base_url or "https://api.deepseek.com/v1"
            elif self.provider == LLMProvider.AZURE_OPENAI:
                self.client = openai.AsyncAzureOpenAI(
                    api_key=self.api_key,
                    azure_endpoint=self.base_url,
                    api_version="2024-02-15-preview"
                )
            elif self.provider == LLMProvider.OLLAMA:
                self.base_url = self.base_url or "http://localhost:11434"
            
            # Health check
            await self.health_check()
            self.logger.info(f"Provider {self.provider.value} initialized successfully")
            
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            self.logger.error(f"Failed to initialize {self.provider.value}: {e}")
            raise
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate with comprehensive error handling and metrics"""
        if not await self.rate_limiter.acquire():
            raise RuntimeError(f"Rate limit exceeded for {self.provider.value}")
        
        start_time = time.time()
        request_id = hashlib.md5(
            f"{self.provider.value}{time.time()}{random.random()}".encode()
        ).hexdigest()[:12]
        
        try:
            response = await self.circuit_breaker.call(
                self._generate_internal, request
            )
            
            processing_time = time.time() - start_time
            response.request_id = request_id
            response.usage.processing_time = processing_time
            
            # Record success metrics
            await self.rate_limiter.record_response(True, processing_time)
            self.request_count.labels(
                model=response.model, 
                status='success'
            ).inc()
            self.response_time.labels(model=response.model).observe(processing_time)
            
            # Quality assessment
            response.quality_score = QualityAssessment.assess_response_quality(
                request, response
            )
            
            # Performance tracking
            self.performance_history.append({
                'timestamp': time.time(),
                'response_time': processing_time,
                'success': True,
                'model': response.model,
                'tokens': response.usage.total_tokens
            })
            
            self.is_healthy = True
            self.last_error = None
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            await self.rate_limiter.record_response(False, processing_time)
            
            error_type = type(e).__name__
            self.request_count.labels(
                model=request.model or 'unknown',
                status='error'
            ).inc()
            self.error_count.labels(error_type=error_type).inc()
            
            self.last_error = str(e)
            self.logger.error(f"Generation failed for {self.provider.value}: {e}")
            
            # Performance tracking
            self.performance_history.append({
                'timestamp': time.time(),
                'response_time': processing_time,
                'success': False,
                'error': str(e)
            })
            
            raise
    
    async def _generate_internal(self, request: LLMRequest) -> LLMResponse:
        """Internal generation method - provider specific implementation"""
        if self.provider == LLMProvider.OPENAI:
            return await self._openai_generate(request)
        elif self.provider == LLMProvider.ANTHROPIC:
            return await self._anthropic_generate(request)
        elif self.provider == LLMProvider.GEMINI:
            return await self._gemini_generate(request)
        elif self.provider == LLMProvider.GROQ:
            return await self._groq_generate(request)
        elif self.provider == LLMProvider.DEEPSEEK:
            return await self._deepseek_generate(request)
        elif self.provider == LLMProvider.AZURE_OPENAI:
            return await self._azure_openai_generate(request)
        elif self.provider == LLMProvider.OLLAMA:
            return await self._ollama_generate(request)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _openai_generate(self, request: LLMRequest) -> LLMResponse:
        """Enhanced OpenAI generation with function calling support"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        # Model selection with fallback
        model = request.model or "gpt-4-turbo-preview"
        
        # Prepare parameters
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "timeout": request.timeout,
            "user": request.user_id
        }
        
        # Add tools if provided
        if request.tools:
            params["tools"] = request.tools
            if request.tool_choice:
                params["tool_choice"] = request.tool_choice
        
        response = await self.client.chat.completions.create(**params)
        
        # Extract content and function calls
        message = response.choices[0].message
        content = message.content or ""
        function_calls = []
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                function_calls.append({
                    'id': tool_call.id,
                    'name': tool_call.function.name,
                    'arguments': json.loads(tool_call.function.arguments)
                })
        
        # Calculate costs (approximate)
        model_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
        }
        
        cost = 0.0
        if model in model_costs:
            cost = (response.usage.prompt_tokens * model_costs[model]["input"] / 1000 + 
                   response.usage.completion_tokens * model_costs[model]["output"] / 1000)
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model=response.model,
            usage=LLMUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cost=cost,
                model_tier=ModelTier.PREMIUM if "gpt-4" in model else ModelTier.STANDARD
            ),
            metadata={
                "finish_reason": response.choices[0].finish_reason,
                "system_fingerprint": getattr(response, 'system_fingerprint', None)
            },
            function_calls=function_calls
        )
    
    async def _anthropic_generate(self, request: LLMRequest) -> LLMResponse:
        """Enhanced Anthropic generation"""
        messages = request.messages.copy()
        system_prompt = request.system_prompt or ""
        
        # Model selection
        model = request.model or "claude-3-sonnet-20240229"
        
        # Handle function calling for Anthropic (convert to system prompt)
        if request.tools:
            tool_descriptions = []
            for tool in request.tools:
                if 'function' in tool:
                    func = tool['function']
                    desc = f"Function: {func['name']}\nDescription: {func['description']}\n"
                    if 'parameters' in func:
                        desc += f"Parameters: {json.dumps(func['parameters'], indent=2)}\n"
                    tool_descriptions.append(desc)
            
            if tool_descriptions:
                system_prompt += f"\n\nAvailable tools:\n" + "\n".join(tool_descriptions)
                system_prompt += "\nTo use a tool, respond with JSON in format: {\"tool_name\": \"function_name\", \"parameters\": {...}}"
        
        response = await self.client.messages.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            system=system_prompt,
            timeout=request.timeout
        )
        
        content = response.content[0].text
        
        # Parse function calls from content if present
        function_calls = []
        if request.tools and content:
            try:
                if content.strip().startswith('{') and content.strip().endswith('}'):
                    parsed = json.loads(content)
                    if 'tool_name' in parsed and 'parameters' in parsed:
                        function_calls.append({
                            'name': parsed['tool_name'],
                            'arguments': parsed['parameters']
                        })
            except json.JSONDecodeError:
                pass
        
        # Cost calculation
        model_costs = {
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125}
        }
        
        cost = 0.0
        if model in model_costs:
            cost = (response.usage.input_tokens * model_costs[model]["input"] / 1000 + 
                   response.usage.output_tokens * model_costs[model]["output"] / 1000)
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model=response.model,
            usage=LLMUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                cost=cost,
                model_tier=ModelTier.PREMIUM if "opus" in model else ModelTier.STANDARD
            ),
            metadata={"stop_reason": response.stop_reason},
            function_calls=function_calls
        )
    
    async def _groq_generate(self, request: LLMRequest async def _groq_generate(self, request: LLMRequest) -> LLMResponse:
        """Enhanced Groq generation for fast inference"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        # Model selection - Groq specializes in fast models
        model = request.model or "mixtral-8x7b-32768"
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            timeout=request.timeout
        )
        
        content = response.choices[0].message.content or ""
        
        # Groq has very low costs
        cost = response.usage.total_tokens * 0.0001 / 1000  # Estimated
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model=response.model,
            usage=LLMUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cost=cost,
                model_tier=ModelTier.FAST
            ),
            metadata={"finish_reason": response.choices[0].finish_reason}
        )
    
    async def _gemini_generate(self, request: LLMRequest) -> LLMResponse:
        """Enhanced Gemini generation"""
        # Convert messages to Gemini format
        prompt_parts = []
        for message in request.messages:
            role_prefix = f"{message['role'].title()}: " if message['role'] != 'user' else ""
            prompt_parts.append(f"{role_prefix}{message['content']}")
        
        if request.system_prompt:
            prompt_parts.insert(0, f"System: {request.system_prompt}")
        
        prompt = "\n\n".join(prompt_parts)
        
        # Configure generation
        generation_config = {
            'temperature': request.temperature,
            'top_p': request.top_p,
            'max_output_tokens': request.max_tokens,
        }
        
        response = await self.client.generate_content_async(
            prompt,
            generation_config=generation_config
        )
        
        content = response.text
        
        # Estimate token usage (Gemini doesn't always provide exact counts)
        estimated_prompt_tokens = len(prompt.split()) * 1.3  # Rough estimate
        estimated_completion_tokens = len(content.split()) * 1.3
        total_tokens = int(estimated_prompt_tokens + estimated_completion_tokens)
        
        # Cost estimation for Gemini
        cost = total_tokens * 0.001 / 1000  # Estimated
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model="gemini-pro",
            usage=LLMUsage(
                prompt_tokens=int(estimated_prompt_tokens),
                completion_tokens=int(estimated_completion_tokens),
                total_tokens=total_tokens,
                cost=cost,
                model_tier=ModelTier.STANDARD
            ),
            metadata={"safety_ratings": getattr(response, 'safety_ratings', [])}
        )
    
    async def _deepseek_generate(self, request: LLMRequest) -> LLMResponse:
        """DeepSeek generation via API"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        model = request.model or "deepseek-chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=request.timeout)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"DeepSeek API error: {response.status} - {error_text}")
            
            data = await response.json()
        
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        # DeepSeek typically has very competitive pricing
        cost = usage.get("total_tokens", 0) * 0.0002 / 1000
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model=data["model"],
            usage=LLMUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=cost,
                model_tier=ModelTier.STANDARD
            ),
            metadata={"finish_reason": data["choices"][0].get("finish_reason")}
        )
    
    async def _azure_openai_generate(self, request: LLMRequest) -> LLMResponse:
        """Azure OpenAI generation"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        model = request.model or "gpt-4"
        
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "timeout": request.timeout
        }
        
        if request.tools:
            params["tools"] = request.tools
            if request.tool_choice:
                params["tool_choice"] = request.tool_choice
        
        response = await self.client.chat.completions.create(**params)
        
        message = response.choices[0].message
        content = message.content or ""
        function_calls = []
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                function_calls.append({
                    'id': tool_call.id,
                    'name': tool_call.function.name,
                    'arguments': json.loads(tool_call.function.arguments)
                })
        
        # Azure pricing similar to OpenAI
        model_costs = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-35-turbo": {"input": 0.0015, "output": 0.002}
        }
        
        cost = 0.0
        base_model = model.replace("gpt-35", "gpt-3.5").split("-")[0:2]
        base_model = "-".join(base_model)
        if base_model in model_costs:
            cost = (response.usage.prompt_tokens * model_costs[base_model]["input"] / 1000 + 
                   response.usage.completion_tokens * model_costs[base_model]["output"] / 1000)
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model=response.model,
            usage=LLMUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cost=cost,
                model_tier=ModelTier.PREMIUM if "gpt-4" in model else ModelTier.STANDARD
            ),
            metadata={"finish_reason": response.choices[0].finish_reason},
            function_calls=function_calls
        )
    
    async def _ollama_generate(self, request: LLMRequest) -> LLMResponse:
        """Ollama local generation"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        model = request.model or "llama2"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "num_predict": request.max_tokens
            }
        }
        
        async with self.session.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=request.timeout)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Ollama API error: {response.status} - {error_text}")
            
            data = await response.json()
        
        content = data["message"]["content"]
        
        # Estimate token usage for local models
        estimated_prompt_tokens = sum(len(msg["content"].split()) for msg in messages) * 1.3
        estimated_completion_tokens = len(content.split()) * 1.3
        total_tokens = int(estimated_prompt_tokens + estimated_completion_tokens)
        
        return LLMResponse(
            content=content,
            provider=self.provider.value,
            model=data["model"],
            usage=LLMUsage(
                prompt_tokens=int(estimated_prompt_tokens),
                completion_tokens=int(estimated_completion_tokens),
                total_tokens=total_tokens,
                cost=0.0,  # Local models have no API cost
                model_tier=ModelTier.FAST
            ),
            metadata={
                "eval_count": data.get("eval_count", 0),
                "eval_duration": data.get("eval_duration", 0)
            }
        )
    
    async def health_check(self) -> bool:
        """Comprehensive health check for provider"""
        try:
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10,
                timeout=10
            )
            
            await self._generate_internal(test_request)
            self.is_healthy = True
            return True
            
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            self.logger.warning(f"Health check failed for {self.provider.value}: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        self.logger.info(f"Provider {self.provider.value} cleaned up")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        if not self.performance_history:
            return {}
        
        recent_history = [h for h in self.performance_history 
                         if time.time() - h['timestamp'] < 3600]  # Last hour
        
        if not recent_history:
            return {}
        
        success_rate = sum(1 for h in recent_history if h['success']) / len(recent_history)
        avg_response_time = sum(h['response_time'] for h in recent_history) / len(recent_history)
        total_tokens = sum(h.get('tokens', 0) for h in recent_history if h['success'])
        
        return {
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'total_requests': len(recent_history),
            'total_tokens': total_tokens,
            'tokens_per_minute': total_tokens / max(1, len(recent_history) / 60),
            'is_healthy': self.is_healthy,
            'last_error': self.last_error
        }

class IntelligentRouter:
    """Intelligent routing system with learning capabilities"""
    
    def __init__(self):
        self.provider_performance: Dict[str, Dict] = defaultdict(lambda: {
            'success_rate': 1.0,
            'avg_response_time': 1.0,
            'cost_efficiency': 1.0,
            'quality_score': 0.5,
            'specialization_scores': defaultdict(float)
        })
        self.routing_history = deque(maxlen=10000)
        self.learning_rate = 0.1
    
    def select_provider(self, request: LLMRequest, 
                       available_providers: List[ProviderClient],
                       prefer_speed: bool = False,
                       prefer_cost: bool = False,
                       prefer_quality: bool = False) -> ProviderClient:
        """Intelligent provider selection with multi-criteria optimization"""
        
        if not available_providers:
            raise ValueError("No available providers")
        
        healthy_providers = [p for p in available_providers if p.is_healthy]
        if not healthy_providers:
            # Fallback to any provider if none are healthy
            healthy_providers = available_providers
        
        # Score each provider
        provider_scores = {}
        
        for provider in healthy_providers:
            score = self._calculate_provider_score(
                provider, request, prefer_speed, prefer_cost, prefer_quality
            )
            provider_scores[provider] = score
        
        # Select best provider
        best_provider = max(provider_scores, key=provider_scores.get)
        
        # Record selection for learning
        self.routing_history.append({
            'timestamp': time.time(),
            'provider': best_provider.provider.value,
            'request_type': request.request_type.value,
            'score': provider_scores[best_provider],
            'selection_criteria': {
                'prefer_speed': prefer_speed,
                'prefer_cost': prefer_cost,
                'prefer_quality': prefer_quality
            }
        })
        
        return best_provider
    
    def _calculate_provider_score(self, provider: ProviderClient, 
                                request: LLMRequest,
                                prefer_speed: bool = False,
                                prefer_cost: bool = False,
                                prefer_quality: bool = False) -> float:
        """Calculate comprehensive provider score"""
        
        perf_data = self.provider_performance[provider.provider.value]
        provider_metrics = provider.get_performance_metrics()
        
        # Base scores from historical performance
        success_score = perf_data['success_rate']
        speed_score = 1.0 / max(0.1, perf_data['avg_response_time'])  # Inverse of response time
        cost_score = perf_data['cost_efficiency']
        quality_score = perf_data['quality_score']
        
        # Specialization bonus
        specialization_score = perf_data['specialization_scores'].get(
            request.request_type.value, 0.5
        )
        
        # Current health penalty
        health_penalty = 0.0 if provider.is_healthy else -0.3
        
        # Weighted combination based on preferences
        weights = {
            'success': 0.3,
            'speed': 0.2 if not prefer_speed else 0.4,
            'cost': 0.2 if not prefer_cost else 0.4,
            'quality': 0.2 if not prefer_quality else 0.4,
            'specialization': 0.1
        }
        
        # Normalize weights
        weight_sum = sum(weights.values())
        weights = {k: v/weight_sum for k, v in weights.items()}
        
        final_score = (
            weights['success'] * success_score +
            weights['speed'] * speed_score +
            weights['cost'] * cost_score +
            weights['quality'] * quality_score +
            weights['specialization'] * specialization_score +
            health_penalty
        )
        
        return max(0.0, final_score)
    
    def update_performance(self, provider_name: str, request: LLMRequest, 
                          response: LLMResponse, success: bool):
        """Update provider performance metrics for learning"""
        
        perf_data = self.provider_performance[provider_name]
        
        # Update success rate
        perf_data['success_rate'] = (
            perf_data['success_rate'] * (1 - self.learning_rate) +
            (1.0 if success else 0.0) * self.learning_rate
        )
        
        if success:
            # Update response time
            perf_data['avg_response_time'] = (
                perf_data['avg_response_time'] * (1 - self.learning_rate) +
                response.usage.processing_time * self.learning_rate
            )
            
            # Update cost efficiency (tokens per dollar)
            if response.usage.cost > 0:
                efficiency = response.usage.total_tokens / response.usage.cost
                perf_data['cost_efficiency'] = (
                    perf_data['cost_efficiency'] * (1 - self.learning_rate) +
                    efficiency * self.learning_rate
                )
            
            # Update quality score
            perf_data['quality_score'] = (
                perf_data['quality_score'] * (1 - self.learning_rate) +
                response.quality_score * self.learning_rate
            )
            
            # Update specialization score
            request_type = request.request_type.value
            current_spec = perf_data['specialization_scores'][request_type]
            perf_data['specialization_scores'][request_type] = (
                current_spec * (1 - self.learning_rate) +
                response.quality_score * self.learning_rate
            )

class YmeraLLMManager:
    """Production-ready LLM Manager with enterprise features"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.providers: Dict[str, ProviderClient] = {}
        self.router = IntelligentRouter()
        self.cache = IntelligentCache()
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.session_contexts: Dict[str, Dict] = {}
        self.global_rate_limiter = AdaptiveRateLimiter(
            initial_limit=self.config.get('global_rate_limit', 500)
        )
        
        # Metrics
        self.total_requests = Counter('ymera_total_requests', 'Total requests')
        self.cache_hits = Counter('ymera_cache_hits', 'Cache hits')
        self.provider_switches = Counter('ymera_provider_switches', 'Provider switches')
        
        # Background tasks
        self._background_tasks = set()
        self._shutdown_event = asyncio.Event()
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        default_config = {
            'cache_size': 10000,
            'cache_ttl': 3600,
            'global_rate_limit': 500,
            'health_check_interval': 60,
            'performance_monitor_interval': 300,
            'auto_scaling': True,
            'fallback_enabled': True,
            'quality_threshold': 0.3
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                default_config.update(config)
            except Exception as e:
                self.logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return default_config
    
    async def initialize(self):
        """Initialize the LLM manager"""
        self.logger.info("Initializing YMERA LLM Manager...")
        
        # Initialize providers from config
        providers_config = self.config.get('providers', {})
        
        for provider_name, provider_config in providers_config.items():
            try:
                provider_enum = LLMProvider(provider_name.lower())
                client = ProviderClient(
                    provider=provider_enum,
                    api_key=provider_config['api_key'],
                    base_url=provider_config.get('base_url'),
                    rate_limit=provider_config.get('rate_limit', 50),
                    model_capabilities=provider_config.get('capabilities', {})
                )
                await client.initialize()
                self.providers[provider_name] = client
                self.logger.info(f"Initialized provider: {provider_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize provider {provider_name}: {e}")
        
        if not self.providers:
            raise RuntimeError("No providers successfully initialized")
        
        # Start background tasks
        if self.config.get('health_check_interval', 0) > 0:
            task = asyncio.create_task(self._health_monitor())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        
        if self.config.get('performance_monitor_interval', 0) > 0:
            task = asyncio.create_task(self._performance_monitor())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        
        self.logger.info("YMERA LLM Manager initialized successfully")
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Main generation method with intelligent routing and caching"""
        start_time = time.time()
        
        # Global rate limiting
        if not await self.global_rate_limiter.acquire():
            raise RuntimeError("Global rate limit exceeded")
        
        self.total_requests.inc()
        
        # Check cache first
        cached_response = await self.cache.get(request)
        if cached_response:
            self.cache_hits.inc()
            cached_response.metadata['from_cache'] = True
            return cached_response
        
        # Select provider
        available_providers = [p for p in self.providers.values()]
        selected_provider = self.router.select_provider(
            request, 
            available_providers,
            prefer_speed=request.prefer_speed,
            prefer_cost=request.cost_limit is not None,
            prefer_quality=request.prefer_accuracy
        )
        
        # Generate response with fallback
        response = None
        providers_tried = []
        
        for attempt in range(3):  # Max 3 attempts with fallback
            try:
                providers_tried.append(selected_provider.provider.value)
                response = await selected_provider.generate(request)
                
                # Quality check
                if (response.quality_score < self.config.get('quality_threshold', 0.3) and 
                    self.config.get('fallback_enabled', True) and 
                    len(providers_tried) < len(available_providers)):
                    
                    # Try a different provider for better quality
                    remaining_providers = [
                        p for p in available_providers 
                        if p.provider.value not in providers_tried
                    ]
                    
                    if remaining_providers:
                        selected_provider = self.router.select_provider(
                            request, remaining_providers, prefer_quality=True
                        )
                        self.provider_switches.inc()
                        continue
                
                break
                
            except Exception as e:
                self.logger.warning(
                    f"Provider {selected_provider.provider.value} failed: {e}"
                )
                
                if attempt < 2 and len(providers_tried) < len(available_providers):
                    # Try fallback provider
                    remaining_providers = [
                        p for p in available_providers 
                        if p.provider.value not in providers_tried and p.is_healthy
                    ]
                    
                    if remaining_providers:
                        selected_provider = remaining_providers[0]
                        self.provider_switches.inc()
                        continue
                
                raise e
        
        if not response:
            raise RuntimeError("All providers failed")
        
        # Update router performance
        self.router.update_performance(
            selected_provider.provider.value, 
            request, 
            response, 
            True
        )
        
        # Cache successful response
        await self.cache.put(request, response)
        
        # Update global rate limiter
        processing_time = time.time() - start_time
        await self.global_rate_limiter.record_response(True, processing_time)
        
        # Add routing metadata
        response.metadata.update({
            'provider_selected': selected_provider.provider.value,
            'providers_tried': providers_tried,
            'routing_score': self.router._calculate_provider_score(
                selected_provider, request
            )
        })
        
        return response
    
    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream generation (basic implementation)"""
        # For now, return regular response in chunks
        response = await self.generate(request)
        
        # Split response into chunks for streaming simulation
        content = response.content
        chunk_size = 50  # characters
        
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield chunk
            await asyncio.sleep(0.1)  # Simulate streaming delay
    
    async def batch_generate(self, requests: List[LLMRequest]) -> List[LLMResponse]:
        """Batch processing with intelligent load balancing"""
        tasks = []
        
        for request in requests:
            task = asyncio.create_task(self.generate(request))
            tasks.append(task)
            
            # Add small delay to prevent overwhelming
            await asyncio.sleep(0.01)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def add_provider(self, provider: LLMProvider, api_key: str, 
                          base_url: Optional[str] = None,
                          rate_limit: int = 50) -> bool:
        """Dynamically add a new provider"""
        try:
            client = ProviderClient(
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                rate_limit=rate_limit
            )
            await client.initialize()
            self.providers[provider.value] = client
            self.logger.info(f"Added provider: {provider.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add provider {provider.value}: {e}")
            return False
    
    async def remove_provider(self, provider_name: str) -> bool:
        """Remove a provider"""
        if provider_name in self.providers:
            provider = self.providers[provider_name]
            await provider.cleanup()
            del self.providers[provider_name]
            self.logger.info(f"Removed provider: {provider_name}")
            return True
        return False
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers"""
        status = {}
        for name, provider in self.providers.items():
            metrics = provider.get_performance_metrics()
            status[name] = {
                'healthy': provider.is_healthy,
                'last_error': provider.last_error,
                'performance': metrics,
                'provider_type': provider.provider.value
            }
        return status
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get comprehensive system metrics"""
        # System resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Cache statistics
        cache_stats = {
            'size': len(self.cache.cache),
            'hit_rate': self.cache_hits._value.get() / max(1, self.total_requests._value.get())
        }
        
        # Provider performance summary
        provider_summary = {}
        for name, provider in self.providers.items():
            metrics = provider.get_performance_metrics()
            provider_summary[name] = {
                'success_rate': metrics.get('success_rate', 0),
                'avg_response_time': metrics.get('avg_response_time', 0),
                'total_requests': metrics.get('total_requests', 0)
            }
        
        return {
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3)
            },
            'cache': cache_stats,
            'providers': provider_summary,
            'total_requests': self.total_requests._value.get(),
            'cache_hits': self.cache_hits._value.get(),
            'provider_switches': self.provider_switches._value.get()
        }
    
    async def _health_monitor(self):
        """Background health monitoring"""
        while not self._shutdown_event.is_set():
            try:
                for provider in self.providers.values():
                    await provider.health_check()
                
                await asyncio.sleep(self.config.get('health_check_interval', 60))
                
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(10)
    
    async def _performance_monitor(self):
        """Background performance monitoring and optimization"""
        while not self._shutdown_event.is_set():
            try:
                metrics = self.get_system_metrics()
                
                # Log performance summary
                self.logger.info(f"Performance Summary: {json.dumps(metrics, indent=2)}")
                
                # Auto-scaling logic
                if self.config.get('auto_scaling', True):
                    await self._auto_scale_analysis(metrics)
                
                await asyncio.sleep(self.config.get('performance_monitor_interval', 300))
                
            except Exception as e:
                self.logger.error(f"Performance monitor error: {e}")
                await asyncio.sleep(30)
    
    async def _auto_scale_analysis(self, metrics: Dict[str, Any]):
        """Analyze metrics and perform auto-scaling adjustments"""
        # Adjust rate limits based on performance
        for name, provider in self.providers.items():
            provider_metrics = metrics['providers'].get(name, {})
            success_rate = provider_metrics.get('success_rate', 1.0)
            avg_response_time = provider_metrics.get('avg_response_time', 1.0)
            
            # Increase rate limit if performing well
            if success_rate > 0.95 and avg_response_time < 2.0:
                current_limit = provider.rate_limiter.current_limit
                new_limit = min(current_limit * 1.1, current_limit * 2)
                provider.rate_limiter.current_limit new_limit = min(current_limit * 1.1, current_limit * 2)
                provider.rate_limiter.current_limit = new_limit
                self.logger.info(f"Increased rate limit for {name} to {new_limit}")
            
            # Decrease rate limit if performing poorly
            elif success_rate < 0.8 or avg_response_time > 5.0:
                current_limit = provider.rate_limiter.current_limit
                new_limit = max(current_limit * 0.9, 10)  # Minimum of 10 requests
                provider.rate_limiter.current_limit = new_limit
                self.logger.warning(f"Decreased rate limit for {name} to {new_limit}")
        
        # Adjust global rate limit based on overall system performance
        system_cpu = metrics['system']['cpu_percent']
        system_memory = metrics['system']['memory_percent']
        
        if system_cpu > 80 or system_memory > 85:
            # Reduce global rate limit under high system load
            current_global = self.global_rate_limiter.current_limit
            new_global = max(current_global * 0.8, 50)
            self.global_rate_limiter.current_limit = new_global
            self.logger.warning(f"Reduced global rate limit to {new_global} due to high system load")
        
        elif system_cpu < 50 and system_memory < 70:
            # Increase global rate limit when system is underutilized
            current_global = self.global_rate_limiter.current_limit
            new_global = min(current_global * 1.2, 1000)
            self.global_rate_limiter.current_limit = new_global
            self.logger.info(f"Increased global rate limit to {new_global}")
    
    async def create_session_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """Create a session context for persistent conversations"""
        try:
            self.session_contexts[session_id] = {
                'created_at': time.time(),
                'context': context,
                'message_history': [],
                'preferences': context.get('preferences', {}),
                'user_id': context.get('user_id'),
                'metadata': context.get('metadata', {})
            }
            self.logger.info(f"Created session context: {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create session context {session_id}: {e}")
            return False
    
    async def update_session_context(self, session_id: str, 
                                   message: Dict[str, str], 
                                   response: str) -> bool:
        """Update session context with new message and response"""
        if session_id not in self.session_contexts:
            return False
        
        try:
            session = self.session_contexts[session_id]
            session['message_history'].append({
                'timestamp': time.time(),
                'message': message,
                'response': response
            })
            
            # Keep only last 50 messages to prevent memory bloat
            if len(session['message_history']) > 50:
                session['message_history'] = session['message_history'][-50:]
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to update session context {session_id}: {e}")
            return False
    
    async def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session context"""
        return self.session_contexts.get(session_id)
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old session contexts"""
        current_time = time.time()
        sessions_to_remove = []
        
        for session_id, session_data in self.session_contexts.items():
            age_hours = (current_time - session_data['created_at']) / 3600
            if age_hours > max_age_hours:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.session_contexts[session_id]
            self.logger.info(f"Cleaned up old session: {session_id}")
        
        return len(sessions_to_remove)
    
    async def export_metrics(self, format: str = 'json') -> str:
        """Export system metrics in various formats"""
        metrics = self.get_system_metrics()
        
        if format.lower() == 'json':
            return json.dumps(metrics, indent=2, default=str)
        
        elif format.lower() == 'csv':
            # Flatten metrics for CSV export
            flattened = self._flatten_metrics(metrics)
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=flattened.keys())
            writer.writeheader()
            writer.writerow(flattened)
            return output.getvalue()
        
        elif format.lower() == 'prometheus':
            # Export in Prometheus format
            lines = []
            lines.append(f"# HELP ymera_total_requests Total number of requests")
            lines.append(f"# TYPE ymera_total_requests counter")
            lines.append(f"ymera_total_requests {metrics.get('total_requests', 0)}")
            
            lines.append(f"# HELP ymera_cache_hits Total cache hits")
            lines.append(f"# TYPE ymera_cache_hits counter")
            lines.append(f"ymera_cache_hits {metrics.get('cache_hits', 0)}")
            
            for provider, data in metrics.get('providers', {}).items():
                lines.append(f"ymera_provider_success_rate{{provider=\"{provider}\"}} {data.get('success_rate', 0)}")
                lines.append(f"ymera_provider_response_time{{provider=\"{provider}\"}} {data.get('avg_response_time', 0)}")
            
            return '\n'.join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _flatten_metrics(self, metrics: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export"""
        flattened = {}
        
        for key, value in metrics.items():
            new_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, dict):
                flattened.update(self._flatten_metrics(value, new_key))
            else:
                flattened[new_key] = value
        
        return flattened
    
    async def run_diagnostic(self) -> Dict[str, Any]:
        """Run comprehensive system diagnostic"""
        diagnostic_results = {
            'timestamp': time.time(),
            'status': 'healthy',
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test all providers
            provider_results = {}
            for name, provider in self.providers.items():
                health_status = await provider.health_check()
                provider_results[name] = {
                    'healthy': health_status,
                    'last_error': provider.last_error,
                    'performance': provider.get_performance_metrics()
                }
                
                if not health_status:
                    diagnostic_results['issues'].append(f"Provider {name} is unhealthy: {provider.last_error}")
                    diagnostic_results['status'] = 'degraded'
            
            diagnostic_results['providers'] = provider_results
            
            # Check system resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            if cpu_percent > 90:
                diagnostic_results['issues'].append(f"High CPU usage: {cpu_percent}%")
                diagnostic_results['recommendations'].append("Consider reducing concurrent requests or scaling infrastructure")
            
            if memory.percent > 90:
                diagnostic_results['issues'].append(f"High memory usage: {memory.percent}%")
                diagnostic_results['recommendations'].append("Consider increasing memory or implementing aggressive caching cleanup")
            
            # Check cache performance
            cache_hit_rate = self.cache_hits._value.get() / max(1, self.total_requests._value.get())
            if cache_hit_rate < 0.1:
                diagnostic_results['recommendations'].append("Low cache hit rate - consider adjusting cache TTL or size")
            
            # Check provider distribution
            router_history = list(self.router.routing_history)
            if len(router_history) > 10:
                recent_selections = [h['provider'] for h in router_history[-100:]]
                provider_distribution = {p: recent_selections.count(p) for p in set(recent_selections)}
                
                # Check if one provider is getting >80% of requests
                for provider, count in provider_distribution.items():
                    if count / len(recent_selections) > 0.8:
                        diagnostic_results['recommendations'].append(
                            f"Provider {provider} handling {count/len(recent_selections)*100:.1f}% of requests - "
                            "consider load balancing"
                        )
            
            if diagnostic_results['issues']:
                diagnostic_results['status'] = 'issues_found'
            
        except Exception as e:
            diagnostic_results['status'] = 'error'
            diagnostic_results['issues'].append(f"Diagnostic failed: {str(e)}")
        
        return diagnostic_results
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down YMERA LLM Manager...")
        
        # Signal background tasks to stop
        self._shutdown_event.set()
        
        # Wait for background tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Cleanup all providers
        for provider in self.providers.values():
            await provider.cleanup()
        
        # Clear session contexts
        self.session_contexts.clear()
        
        self.logger.info("YMERA LLM Manager shutdown complete")
    
    def __repr__(self) -> str:
        return f"YmeraLLMManager(providers={len(self.providers)}, sessions={len(self.session_contexts)})"


# Factory function for easy initialization
async def create_ymera_manager(config: Optional[Dict[str, Any]] = None) -> YmeraLLMManager:
    """Factory function to create and initialize YMERA LLM Manager"""
    
    # Default configuration if none provided
    if config is None:
        config = {
            'providers': {
                'openai': {
                    'api_key': os.getenv('OPENAI_API_KEY'),
                    'rate_limit': 60
                },
                'anthropic': {
                    'api_key': os.getenv('ANTHROPIC_API_KEY'),
                    'rate_limit': 50
                },
                'groq': {
                    'api_key': os.getenv('GROQ_API_KEY'),
                    'rate_limit': 100
                }
            }
        }
    
    # Write config to temporary file
    config_path = 'ymera_config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    try:
        manager = YmeraLLMManager(config_path)
        await manager.initialize()
        return manager
    finally:
        # Clean up temporary config file
        if os.path.exists(config_path):
            os.remove(config_path)


# Usage example and testing utilities
if __name__ == "__main__":
    async def main():
        # Example usage
        manager = await create_ymera_manager()
        
        try:
            # Test request
            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello, how are you?"}],
                max_tokens=100,
                request_type=RequestType.CHAT
            )
            
            response = await manager.generate(request)
            print(f"Response: {response.content}")
            print(f"Provider: {response.provider}")
            print(f"Tokens: {response.usage.total_tokens}")
            print(f"Cost: ${response.usage.cost:.4f}")
            
            # System status
            status = manager.get_provider_status()
            print(f"\nProvider Status: {json.dumps(status, indent=2)}")
            
            # Run diagnostic
            diagnostic = await manager.run_diagnostic()
            print(f"\nDiagnostic: {json.dumps(diagnostic, indent=2)}")
            
        finally:
            await manager.shutdown()
    
    # Run the example
    asyncio.run(main())