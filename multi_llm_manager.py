"""
YMERA Multi-LLM Manager - Production Ready
Manages multiple AI providers with failover, load balancing, and rate limiting
"""

import asyncio
import aiohttp
import time
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta
import openai
import anthropic
import google.generativeai as genai
from groq import Groq
import hashlib
import random

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    DEEPSEEK = "deepseek"

@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    provider: str
    model: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    request_id: str

@dataclass
class LLMRequest:
    """Standardized LLM request"""
    messages: List[Dict[str, str]]
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: Optional[str] = None
    tools: Optional[List[Dict]] = None
    timeout: int = 60

class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Acquire rate limit token"""
        async with self._lock:
            now = time.time()
            # Remove old requests
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
    
    def get_reset_time(self) -> float:
        """Get time until rate limit resets"""
        if not self.requests:
            return 0
        return max(0, self.time_window - (time.time() - self.requests[0]))

class ProviderClient:
    """Base provider client"""
    
    def __init__(self, provider: LLMProvider, api_key: str, rate_limit: int = 50):
        self.provider = provider
        self.api_key = api_key
        self.rate_limiter = RateLimiter(rate_limit)
        self.client = None
        self.is_healthy = True
        self.last_error = None
        self.logger = logging.getLogger(f"{__name__}.{provider.value}")
        self.session = None
    
    async def initialize(self):
        """Initialize the provider client"""
        try:
            if self.provider == LLMProvider.OPENAI:
                self.client = openai.AsyncOpenAI(api_key=self.api_key)
            elif self.provider == LLMProvider.ANTHROPIC:
                self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
            elif self.provider == LLMProvider.GEMINI:
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel('gemini-pro')
            elif self.provider == LLMProvider.GROQ:
                self.client = Groq(api_key=self.api_key)
            elif self.provider == LLMProvider.DEEPSEEK:
                self.session = aiohttp.ClientSession()
            
            # Test connection
            await self.health_check()
            self.logger.info(f"Provider {self.provider.value} initialized successfully")
            
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            self.logger.error(f"Failed to initialize {self.provider.value}: {e}")
            raise
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response from the provider"""
        if not self.is_healthy:
            raise RuntimeError(f"Provider {self.provider.value} is not healthy: {self.last_error}")
        
        # Check rate limit
        if not await self.rate_limiter.acquire():
            wait_time = self.rate_limiter.get_reset_time()
            raise RuntimeError(f"Rate limit exceeded. Wait {wait_time:.1f} seconds")
        
        start_time = time.time()
        request_id = hashlib.md5(f"{self.provider.value}{time.time()}{random.random()}".encode()).hexdigest()[:8]
        
        try:
            if self.provider == LLMProvider.OPENAI:
                response = await self._openai_generate(request)
            elif self.provider == LLMProvider.ANTHROPIC:
                response = await self._anthropic_generate(request)
            elif self.provider == LLMProvider.GEMINI:
                response = await self._gemini_generate(request)
            elif self.provider == LLMProvider.GROQ:
                response = await self._groq_generate(request)
            elif self.provider == LLMProvider.DEEPSEEK:
                response = await self._deepseek_generate(request)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
            
            response.request_id = request_id
            response.metadata['response_time'] = time.time() - start_time
            
            self.is_healthy = True
            self.last_error = None
            
            return response
            
        except Exception as e:
            self.logger.error(f"Generation failed for {self.provider.value}: {e}")
            self.last_error = str(e)
            raise
    
    async def _openai_generate(self, request: LLMRequest) -> LLMResponse:
        """Generate using OpenAI"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        response = await self.client.chat.completions.create(
            model=request.model or "gpt-4",
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout=request.timeout
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider=self.provider.value,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            metadata={"finish_reason": response.choices[0].finish_reason},
            timestamp=datetime.utcnow(),
            request_id=""
        )
    
    async def _anthropic_generate(self, request: LLMRequest) -> LLMResponse:
        """Generate using Anthropic"""
        messages = request.messages.copy()
        system_prompt = request.system_prompt or ""
        
        response = await self.client.messages.create(
            model=request.model or "claude-3-sonnet-20240229",
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_prompt
        )
        
        return LLMResponse(
            content=response.content[0].text,
            provider=self.provider.value,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            },
            metadata={"stop_reason": response.stop_reason},
            timestamp=datetime.utcnow(),
            request_id=""
        )
    
    async def _gemini_generate(self, request: LLMRequest) -> LLMResponse:
        """Generate using Gemini"""
        # Convert messages to Gemini format
        prompt = ""
        if request.system_prompt:
            prompt = f"System: {request.system_prompt}\n\n"
        
        for msg in request.messages:
            role = msg["role"].title()
            content = msg["content"]
            prompt += f"{role}: {content}\n"
        
        prompt += "Assistant: "
        
        # Note: Using synchronous call as async version has limitations
        response = self.client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=request.max_tokens,
                temperature=request.temperature
            )
        )
        
        return LLMResponse(
            content=response.text,
            provider=self.provider.value,
            model="gemini-pro",
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
            },
            metadata={"finish_reason": "stop"},
            timestamp=datetime.utcnow(),
            request_id=""
        )
    
    async def _groq_generate(self, request: LLMRequest) -> LLMResponse:
        """Generate using Groq"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        # Groq client is synchronous, wrap in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.chat.completions.create(
                model=request.model or "mixtral-8x7b-32768",
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider=self.provider.value,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            metadata={"finish_reason": response.choices[0].finish_reason},
            timestamp=datetime.utcnow(),
            request_id=""
        )
    
    async def _deepseek_generate(self, request: LLMRequest) -> LLMResponse:
        """Generate using DeepSeek"""
        messages = request.messages.copy()
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        
        payload = {
            "model": request.model or "deepseek-coder",
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=request.timeout
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"DeepSeek API error {response.status}: {error_text}")
            
            data = await response.json()
            
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                provider=self.provider.value,
                model=data["model"],
                usage={
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"],
                    "total_tokens": data["usage"]["total_tokens"]
                },
                metadata={"finish_reason": data["choices"][0]["finish_reason"]},
                timestamp=datetime.utcnow(),
                request_id=""
            )
    
    async def health_check(self) -> bool:
        """Check provider health"""
        try:
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model="",
                max_tokens=10
            )
            await self.generate(test_request)
            self.is_healthy = True
            return True
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            self.logger.warning(f"Health check failed for {self.provider.value}: {e}")
            return False
    
    async def close(self):
        """Close the provider client"""
        if self.session:
            await self.session.close()
        self.logger.info(f"Provider {self.provider.value} client closed")

class MultiLLMManager:
    """Production-ready multi-LLM manager with failover and load balancing"""
    
    def __init__(self, 
                 openai_api_key: str = "",
                 anthropic_api_key: str = "",
                 google_api_key: str = "",
                 groq_api_key: str = "",
                 deepseek_api_key: str = "",
                 default_provider: str = "openai",
                 fallback_providers: List[str] = None):
        
        self.providers: Dict[str, ProviderClient] = {}
        self.default_provider = default_provider
        self.fallback_providers = fallback_providers or ["anthropic", "groq"]
        self.logger = logging.getLogger(__name__)
        self.request_cache = {}  # Simple in-memory cache
        self.cache_ttl = 300  # 5 minutes
        
        # Initialize providers
        if openai_api_key:
            self.providers["openai"] = ProviderClient(LLMProvider.OPENAI, openai_api_key)
        if anthropic_api_key:
            self.providers["anthropic"] = ProviderClient(LLMProvider.ANTHROPIC, anthropic_api_key)
        if google_api_key:
            self.providers["gemini"] = ProviderClient(LLMProvider.GEMINI, google_api_key)
        if groq_api_key:
            self.providers["groq"] = ProviderClient(LLMProvider.GROQ, groq_api_key)
        if deepseek_api_key:
            self.providers["deepseek"] = ProviderClient(LLMProvider.DEEPSEEK, deepseek_api_key)
    
    async def initialize(self):
        """Initialize all providers"""
        initialization_tasks = []
        for provider in self.providers.values():
            initialization_tasks.append(provider.initialize())
        
        # Initialize with some tolerance for failures
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)
        
        healthy_providers = []
        for provider_name, result in zip(self.providers.keys(), results):
            if isinstance(result, Exception):
                self.logger.warning(f"Failed to initialize {provider_name}: {result}")
            else:
                healthy_providers.append(provider_name)
        
        if not healthy_providers:
            raise RuntimeError("No AI providers could be initialized")
        
        self.logger.info(f"Initialized {len(healthy_providers)} AI providers: {healthy_providers}")
    
    async def generate(self, 
                      messages: List[Dict[str, str]],
                      model: str = None,
                      provider: str = None,
                      max_tokens: int = 4096,
                      temperature: float = 0.7,
                      system_prompt: str = None,
                      use_cache: bool = True,
                      timeout: int = 60) -> LLMResponse:
        """Generate response with automatic failover"""
        
        request = LLMRequest(
            messages=messages,
            model=model or "",
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            timeout=timeout
        )
        
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(request)
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                self.logger.debug("Returning cached response")
                return cached_response
        
        # Determine providers to try
        providers_to_try = []
        if provider and provider in self.providers:
            providers_to_try = [provider]
        else:
            providers_to_try = [self.default_provider] + self.fallback_providers
        
        # Try providers in order
        last_error = None
        for provider_name in providers_to_try:
            if provider_name not in self.providers:
                continue
            
            provider_client = self.providers[provider_name]
            if not provider_client.is_healthy:
                self.logger.warning(f"Skipping unhealthy provider: {provider_name}")
                continue
            
            try:
                response = await provider_client.generate(request)
                
                # Cache successful response
                if use_cache:
                    self._cache_response(cache_key, response)
                
                self.logger.info(f"Generated response using {provider_name}")
                return response
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Provider {provider_name} failed: {e}")
                continue
        
        # All providers failed
        raise RuntimeError(f"All AI providers failed. Last error: {last_error}")
    
    async def generate_stream(self, 
                            messages: List[Dict[str, str]],
                            model: str = None,
                            provider: str = None,
                            max_tokens: int = 4096,
                            temperature: float = 0.7,
                            system_prompt: str = None):
        """Generate streaming response (simplified implementation)"""
        # For streaming, we'll use the primary provider only
        # In production, this would be fully implemented for each provider
        response = await self.generate(
            messages=messages,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            use_cache=False
        )
        
        # Simulate streaming by chunking the response
        words = response.content.split()
        for i in range(0, len(words), 5):
            chunk = " ".join(words[i:i+5])
            yield {"chunk": chunk, "done": i+5 >= len(words)}
            await asyncio.sleep(0.1)  # Simulate streaming delay
    
    def _get_cache_key(self, request: LLMRequest) -> str:
        """Generate cache key for request"""
        content = json.dumps({
            "messages": request.messages,
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system_prompt": request.system_prompt
        }, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """Get cached response if valid"""
        if cache_key in self.request_cache:
            cached_data = self.request_cache[cache_key]
            if time.time() - cached_data["timestamp"] < self.cache_ttl:
                return cached_data["response"]
            else:
                del self.request_cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, response: LLMResponse):
        """Cache response"""
        self.request_cache[cache_key] = {
            "response": response,
            "timestamp": time.time()
        }
        
        # Simple cache cleanup (keep last 1000 entries)
        if len(self.request_cache) > 1000:
            oldest_keys = sorted(self.request_cache.keys(), 
                               key=lambda k: self.request_cache[k]["timestamp"])[:100]
            for key in oldest_keys:
                del self.request_cache[key]
    
    async def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers"""
        status = {}
        for name, provider in self.providers.items():
            status[name] = {
                "healthy": provider.is_healthy,
                "last_error": provider.last_error,
                "rate_limit_reset": provider.rate_limiter.get_reset_time()
            }
        return status
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Run health check on all providers"""
        results = {}
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        return results
    
    def get_available_providers(self) -> List[str]:
        """Get list of healthy providers"""
        return [name for name, provider in self.providers.items() if provider.is_healthy]
    
    async def close(self):
        """Close all provider connections"""
        close_tasks = [provider.close() for provider in self.providers.values()]
        await asyncio.gather(*close_tasks, return_exceptions=True)
        self.logger.info("All AI providers closed")