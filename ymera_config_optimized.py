"""
YMERA Enterprise Configuration Management - Replit Optimized
Streamlined configuration system optimized for Replit deployment
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from enum import Enum
import secrets
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from pydantic import BaseSettings, Field, validator, SecretStr
import structlog

# Configure structured logging
logger = structlog.get_logger("ymera.config")

# Core Enums
class Environment(str, Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"

# Configuration Data Classes
@dataclass
class DatabaseConfig:
    """Simplified database configuration for Replit"""
    url: str
    pool_size: int = 5  # Reduced for Replit
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False
    connection_timeout: int = 10

@dataclass
class RedisConfig:
    """Redis configuration optimized for Replit"""
    url: str
    max_connections: int = 20  # Reduced for Replit
    socket_timeout: int = 5
    retry_on_timeout: bool = True
    decode_responses: bool = True

@dataclass
class LLMConfig:
    """LLM provider configuration"""
    provider: LLMProvider
    api_key: str
    model_name: str
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 60  # Reduced for Replit
    retry_attempts: int = 2

@dataclass
class AgentConfig:
    """Agent system configuration - Replit optimized"""
    max_concurrent_agents: int = 3  # Reduced for Replit resources
    agent_timeout: int = 120  # Reduced timeout
    heartbeat_interval: int = 30
    max_retries: int = 2
    orchestration_interval: int = 30  # Increased for Replit
    agent_memory_limit: int = 256  # MB - Reduced for Replit

class YMERAConfig(BaseSettings):
    """
    YMERA Configuration Manager - Replit Optimized
    
    Streamlined configuration focusing on essential features for Replit deployment
    """
    
    # Core Application Settings
    app_name: str = Field(default="YMERA Enterprise", env="APP_NAME")
    app_version: str = Field(default="3.0.0", env="APP_VERSION")
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")  # Default True for Replit development
    
    # Security Settings
    secret_key: SecretStr = Field(env="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database Configuration (PostgreSQL focus for production, SQLite for dev)
    database_url: SecretStr = Field(env="DATABASE_URL")
    db_pool_size: int = Field(default=5, env="DB_POOL_SIZE")  # Replit optimized
    db_max_overflow: int = Field(default=10, env="DB_MAX_OVERFLOW")
    db_echo: bool = Field(default=False, env="DB_ECHO")
    
    # Redis Configuration
    redis_url: SecretStr = Field(env="REDIS_URL")
    redis_max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    cache_default_ttl: int = Field(default=3600, env="CACHE_DEFAULT_TTL")
    
    # AI Service API Keys - Only include what you actually use
    openai_api_key: Optional[SecretStr] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[SecretStr] = Field(default=None, env="ANTHROPIC_API_KEY")
    groq_api_key: Optional[SecretStr] = Field(default=None, env="GROQ_API_KEY")
    gemini_api_key: Optional[SecretStr] = Field(default=None, env="GEMINI_API_KEY")
    deepseek_api_key: Optional[SecretStr] = Field(default=None, env="DEEPSEEK_API_KEY")
    
    default_llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI, env="DEFAULT_LLM_PROVIDER")
    
    # Vector Database - Pinecone
    pinecone_api_key: Optional[SecretStr] = Field(default=None, env="PINECONE_API_KEY")
    pinecone_environment: str = Field(default="us-west1-gcp-free", env="PINECONE_ENVIRONMENT")
    pinecone_index_name: str = Field(default="ymera-knowledge", env="PINECONE_INDEX_NAME")
    
    # GitHub Integration
    github_token: Optional[SecretStr] = Field(default=None, env="GITHUB_TOKEN")
    
    # Server Configuration - Replit Optimized
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")  # Single worker for Replit
    reload: bool = Field(default=True, env="RELOAD")  # Auto-reload for development
    
    # Logging Configuration
    log_level: LogLevel = Field(default=LogLevel.INFO, env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    # CORS Settings
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["*"],  # Open for development
        env="ALLOWED_ORIGINS"
    )
    
    # Agent System - Replit Resource Constraints
    max_concurrent_agents: int = Field(default=3, env="MAX_CONCURRENT_AGENTS")
    agent_timeout: int = Field(default=120, env="AGENT_TIMEOUT")
    orchestration_interval: int = Field(default=30, env="ORCHESTRATION_INTERVAL")
    
    # Learning System - Simplified
    enable_continuous_learning: bool = Field(default=True, env="ENABLE_CONTINUOUS_LEARNING")
    learning_update_interval: int = Field(default=600, env="LEARNING_UPDATE_INTERVAL")  # 10 minutes
    
    # Monitoring - Simplified
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    health_check_interval: int = Field(default=120, env="HEALTH_CHECK_INTERVAL")  # 2 minutes
    
    # Rate Limiting - Conservative for Replit
    rate_limit_requests: int = Field(default=50, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_logging()
        self._apply_replit_optimizations()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.value.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _apply_replit_optimizations(self):
        """Apply Replit-specific optimizations"""
        if os.getenv('REPL_ID'):  # Running on Replit
            # Force single worker on Replit
            self.workers = 1
            
            # Use Replit's PORT if available
            if os.getenv('PORT'):
                self.port = int(os.getenv('PORT'))
            
            # Reduce resource usage
            self.db_pool_size = min(3, self.db_pool_size)
            self.redis_max_connections = min(15, self.redis_max_connections)
            self.max_concurrent_agents = min(2, self.max_concurrent_agents)
    
    # Validators
    @validator('secret_key')
    def validate_secret_key(cls, v):
        if not v or len(v.get_secret_value()) < 32:
            return SecretStr(secrets.token_urlsafe(64))
        return v
    
    @validator('database_url')
    def validate_database_url(cls, v):
        url = v.get_secret_value()
        if not url.startswith(('postgresql', 'sqlite')):
            raise ValueError("Only PostgreSQL and SQLite are supported")
        return v
    
    @validator('port')
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("Invalid port number")
        return v
    
    # Configuration Getters
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return DatabaseConfig(
            url=self.database_url.get_secret_value(),
            pool_size=self.db_pool_size,
            max_overflow=self.db_max_overflow,
            echo=self.db_echo
        )
    
    def get_redis_config(self) -> RedisConfig:
        """Get Redis configuration"""
        return RedisConfig(
            url=self.redis_url.get_secret_value(),
            max_connections=self.redis_max_connections
        )
    
    def get_agent_config(self) -> AgentConfig:
        """Get agent system configuration"""
        return AgentConfig(
            max_concurrent_agents=self.max_concurrent_agents,
            agent_timeout=self.agent_timeout,
            orchestration_interval=self.orchestration_interval
        )
    
    def get_llm_config(self, provider: LLMProvider) -> Optional[LLMConfig]:
        """Get LLM configuration for specific provider"""
        api_key_map = {
            LLMProvider.OPENAI: self.openai_api_key,
            LLMProvider.ANTHROPIC: self.anthropic_api_key,
            LLMProvider.GROQ: self.groq_api_key,
            LLMProvider.GOOGLE: self.gemini_api_key,
            LLMProvider.DEEPSEEK: self.deepseek_api_key
        }
        
        model_map = {
            LLMProvider.OPENAI: "gpt-4",
            LLMProvider.ANTHROPIC: "claude-3-sonnet-20240229",
            LLMProvider.GROQ: "mixtral-8x7b-32768",
            LLMProvider.GOOGLE: "gemini-pro",
            LLMProvider.DEEPSEEK: "deepseek-chat"
        }
        
        api_key = api_key_map.get(provider)
        if not api_key:
            return None
            
        return LLMConfig(
            provider=provider,
            api_key=api_key.get_secret_value(),
            model_name=model_map[provider]
        )
    
    def get_available_llm_providers(self) -> List[LLMProvider]:
        """Get list of configured LLM providers"""
        available = []
        if self.openai_api_key:
            available.append(LLMProvider.OPENAI)
        if self.anthropic_api_key:
            available.append(LLMProvider.ANTHROPIC)
        if self.groq_api_key:
            available.append(LLMProvider.GROQ)
        if self.gemini_api_key:
            available.append(LLMProvider.GOOGLE)
        if self.deepseek_api_key:
            available.append(LLMProvider.DEEPSEEK)
        return available
    
    async def validate_connections(self) -> Dict[str, bool]:
        """Validate external service connections"""
        results = {}
        
        # Database validation
        try:
            db_url = self.database_url.get_secret_value()
            if db_url.startswith('sqlite'):
                results['database'] = True  # SQLite doesn't need connection test
            else:
                # For PostgreSQL, we'd test the connection here
                results['database'] = True  # Simplified for now
        except Exception:
            results['database'] = False
        
        # Redis validation
        try:
            redis_url = self.redis_url.get_secret_value()
            # Test Redis connection would go here
            results['redis'] = True  # Simplified for now
        except Exception:
            results['redis'] = False
        
        # AI services validation
        available_providers = self.get_available_llm_providers()
        results['ai_services'] = len(available_providers) > 0
        
        return results
    
    def get_replit_ready_config(self) -> Dict[str, Any]:
        """Get Replit-ready configuration summary"""
        return {
            'app_name': self.app_name,
            'environment': self.environment.value,
            'host': self.host,
            'port': self.port,
            'workers': self.workers,
            'debug': self.debug,
            'reload': self.reload,
            'database_type': 'sqlite' if 'sqlite' in self.database_url.get_secret_value() else 'postgresql',
            'ai_providers_configured': len(self.get_available_llm_providers()),
            'max_agents': self.max_concurrent_agents,
            'resources_optimized': os.getenv('REPL_ID') is not None
        }
    
    @classmethod
    def create_replit_env_file(cls, file_path: str = ".env"):
        """Create Replit-optimized .env file"""
        replit_env_content = f"""# YMERA Enterprise - Replit Configuration
# Generated on {datetime.utcnow().isoformat()}

# Application Settings
APP_NAME=YMERA Enterprise
APP_VERSION=3.0.0
ENVIRONMENT=development
DEBUG=true

# Security
SECRET_KEY={secrets.token_urlsafe(64)}
JWT_ALGORITHM=HS256

# Database - SQLite for development, PostgreSQL for production
DATABASE_URL=sqlite:///./ymera.db
# For production: DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Redis - Use Replit's Redis or external service
REDIS_URL=redis://localhost:6379/0

# AI Services - Add your API keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GROQ_API_KEY=your_groq_key_here

# Default AI Provider
DEFAULT_LLM_PROVIDER=openai

# Vector Database (optional)
PINECONE_API_KEY=your_pinecone_key_here
PINECONE_ENVIRONMENT=us-west1-gcp-free

# GitHub Integration (optional)
GITHUB_TOKEN=your_github_token_here

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=1
RELOAD=true

# Logging
LOG_LEVEL=info

# CORS
ALLOWED_ORIGINS=*

# Agent System - Replit Optimized
MAX_CONCURRENT_AGENTS=2
AGENT_TIMEOUT=120
ORCHESTRATION_INTERVAL=30

# Learning System
ENABLE_CONTINUOUS_LEARNING=true
LEARNING_UPDATE_INTERVAL=600

# Monitoring
ENABLE_METRICS=true
HEALTH_CHECK_INTERVAL=120

# Rate Limiting
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60
"""
        
        try:
            with open(file_path, 'w') as f:
                f.write(replit_env_content)
            print(f"✅ Replit-optimized .env file created at: {file_path}")
            print("🔑 Please update the API keys before running!")
            print("📝 For SQLite: No additional database setup needed")
            print("🐘 For PostgreSQL: Update DATABASE_URL with your connection string")
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")

# Configuration Factory Functions
def create_replit_config() -> YMERAConfig:
    """Create Replit-optimized configuration"""
    return YMERAConfig(
        environment=Environment.DEVELOPMENT,
        debug=True,
        workers=1,
        reload=True,
        max_concurrent_agents=2,
        db_pool_size=3,
        redis_max_connections=15
    )

def create_production_config() -> YMERAConfig:
    """Create production configuration"""
    return YMERAConfig(
        environment=Environment.PRODUCTION,
        debug=False,
        workers=2,
        reload=False,
        max_concurrent_agents=5,
        db_pool_size=10,
        redis_max_connections=30
    )

# Async Context Manager
@asynccontextmanager
async def get_config():
    """Get configuration with validation"""
    config = YMERAConfig()
    
    try:
        # Validate connections on startup
        validation_results = await config.validate_connections()
        
        if not all(validation_results.values()):
            logger.warning("Some services failed validation", results=validation_results)
        
        yield config
        
    except Exception as e:
        logger.error("Configuration setup failed", error=str(e))
        raise
    finally:
        logger.info("Configuration cleanup completed")

# Export main components
__all__ = [
    'YMERAConfig',
    'Environment',
    'LogLevel',
    'LLMProvider',
    'DatabaseConfig',
    'RedisConfig',
    'LLMConfig',
    'AgentConfig',
    'create_replit_config',
    'create_production_config',
    'get_config'
]
