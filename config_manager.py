"""
YMERA Core Configuration Manager - Production Ready
Handles environment-based configuration with validation and secrets management
"""

import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = field(default_factory=lambda: os.getenv(
        'DATABASE_URL', 
        'sqlite:///ymera.db'
    ))
    pool_size: int = field(default_factory=lambda: int(os.getenv('DB_POOL_SIZE', '10')))
    max_overflow: int = field(default_factory=lambda: int(os.getenv('DB_MAX_OVERFLOW', '20')))
    echo: bool = field(default_factory=lambda: os.getenv('DB_ECHO', 'false').lower() == 'true')

@dataclass
class RedisConfig:
    """Redis configuration"""
    url: str = field(default_factory=lambda: os.getenv(
        'REDIS_URL', 
        'redis://localhost:6379/0'
    ))
    default_ttl: int = field(default_factory=lambda: int(os.getenv('REDIS_DEFAULT_TTL', '3600')))
    max_connections: int = field(default_factory=lambda: int(os.getenv('REDIS_MAX_CONNECTIONS', '10')))

@dataclass
class SecurityConfig:
    """Security configuration"""
    secret_key: str = field(default_factory=lambda: os.getenv(
        'SECRET_KEY', 
        'your-super-secret-key-change-in-production'
    ))
    jwt_algorithm: str = field(default_factory=lambda: os.getenv('JWT_ALGORITHM', 'HS256'))
    access_token_expire_minutes: int = field(default_factory=lambda: int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30')))
    refresh_token_expire_days: int = field(default_factory=lambda: int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '7')))

@dataclass
class AIConfig:
    """AI services configuration"""
    openai_api_key: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv('ANTHROPIC_API_KEY', ''))
    gemini_api_key: str = field(default_factory=lambda: os.getenv('GEMINI_API_KEY', ''))
    groq_api_key: str = field(default_factory=lambda: os.getenv('GROQ_API_KEY', ''))
    deepseek_api_key: str = field(default_factory=lambda: os.getenv('DEEPSEEK_API_KEY', ''))
    
    default_llm_provider: str = field(default_factory=lambda: os.getenv('DEFAULT_LLM_PROVIDER', 'openai'))
    fallback_llm_providers: List[str] = field(default_factory=lambda: os.getenv(
        'FALLBACK_LLM_PROVIDERS', 
        'anthropic,groq'
    ).split(','))
    
    embedding_model: str = field(default_factory=lambda: os.getenv('EMBEDDING_MODEL', 'text-embedding-ada-002'))
    max_tokens: int = field(default_factory=lambda: int(os.getenv('MAX_TOKENS', '4096')))
    temperature: float = field(default_factory=lambda: float(os.getenv('TEMPERATURE', '0.7')))

@dataclass
class VectorDBConfig:
    """Vector database configuration"""
    pinecone_api_key: str = field(default_factory=lambda: os.getenv('PINECONE_API_KEY', ''))
    pinecone_environment: str = field(default_factory=lambda: os.getenv('PINECONE_ENVIRONMENT', 'us-west1-gcp'))
    pinecone_index_name: str = field(default_factory=lambda: os.getenv('PINECONE_INDEX_NAME', 'ymera-knowledge'))
    dimension: int = field(default_factory=lambda: int(os.getenv('VECTOR_DIMENSION', '1536')))

@dataclass
class GitHubConfig:
    """GitHub integration configuration"""
    token: str = field(default_factory=lambda: os.getenv('GITHUB_TOKEN', ''))
    webhook_secret: str = field(default_factory=lambda: os.getenv('GITHUB_WEBHOOK_SECRET', ''))
    rate_limit_per_hour: int = field(default_factory=lambda: int(os.getenv('GITHUB_RATE_LIMIT', '5000')))

@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration"""
    log_level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))
    log_format: str = field(default_factory=lambda: os.getenv('LOG_FORMAT', 'json'))
    enable_metrics: bool = field(default_factory=lambda: os.getenv('ENABLE_METRICS', 'true').lower() == 'true')
    metrics_port: int = field(default_factory=lambda: int(os.getenv('METRICS_PORT', '9090')))
    health_check_interval: int = field(default_factory=lambda: int(os.getenv('HEALTH_CHECK_INTERVAL', '30')))

@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = field(default_factory=lambda: os.getenv('HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('PORT', '8000')))
    workers: int = field(default_factory=lambda: int(os.getenv('WORKERS', '1')))
    reload: bool = field(default_factory=lambda: os.getenv('RELOAD', 'false').lower() == 'true')
    debug: bool = field(default_factory=lambda: os.getenv('DEBUG', 'false').lower() == 'true')

@dataclass
class AgentConfig:
    """Agent system configuration"""
    max_concurrent_tasks: int = field(default_factory=lambda: int(os.getenv('MAX_CONCURRENT_TASKS', '10')))
    task_timeout: int = field(default_factory=lambda: int(os.getenv('TASK_TIMEOUT', '300')))  # 5 minutes
    learning_enabled: bool = field(default_factory=lambda: os.getenv('LEARNING_ENABLED', 'true').lower() == 'true')
    learning_interval: int = field(default_factory=lambda: int(os.getenv('LEARNING_INTERVAL', '3600')))  # 1 hour
    feedback_threshold: float = field(default_factory=lambda: float(os.getenv('FEEDBACK_THRESHOLD', '0.8')))

@dataclass
class YMERAConfig:
    """Main YMERA configuration container"""
    environment: str = field(default_factory=lambda: os.getenv('ENVIRONMENT', 'development'))
    version: str = field(default_factory=lambda: os.getenv('VERSION', '2.0.0'))
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    
    # Computed properties for backward compatibility
    @property
    def database_url(self) -> str:
        return self.database.url
    
    @property
    def db_pool_size(self) -> int:
        return self.database.pool_size
    
    @property
    def db_max_overflow(self) -> int:
        return self.database.max_overflow
    
    @property
    def redis_url(self) -> str:
        return self.redis.url
    
    @property
    def cache_default_ttl(self) -> int:
        return self.redis.default_ttl
    
    @property
    def secret_key(self) -> str:
        return self.security.secret_key
    
    @property
    def jwt_algorithm(self) -> str:
        return self.security.jwt_algorithm
    
    @property
    def jwt_access_token_expire_minutes(self) -> int:
        return self.security.access_token_expire_minutes
    
    @property
    def openai_api_key(self) -> str:
        return self.ai.openai_api_key
    
    @property
    def anthropic_api_key(self) -> str:
        return self.ai.anthropic_api_key
    
    @property
    def gemini_api_key(self) -> str:
        return self.ai.gemini_api_key
    
    @property
    def groq_api_key(self) -> str:
        return self.ai.groq_api_key
    
    @property
    def deepseek_api_key(self) -> str:
        return self.ai.deepseek_api_key
    
    @property
    def default_llm_provider(self) -> str:
        return self.ai.default_llm_provider
    
    @property
    def fallback_llm_providers(self) -> List[str]:
        return self.ai.fallback_llm_providers
    
    @property
    def embedding_model(self) -> str:
        return self.ai.embedding_model
    
    @property
    def pinecone_api_key(self) -> str:
        return self.vector_db.pinecone_api_key
    
    @property
    def pinecone_environment(self) -> str:
        return self.vector_db.pinecone_environment
    
    @property
    def pinecone_index_name(self) -> str:
        return self.vector_db.pinecone_index_name
    
    @property
    def github_token(self) -> str:
        return self.github.token
    
    @property
    def log_level(self) -> str:
        return self.monitoring.log_level

class ConfigManager:
    """Production-ready configuration manager"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.config: Optional[YMERAConfig] = None
        self.logger = logging.getLogger(__name__)
    
    async def load_config(self) -> YMERAConfig:
        """Load configuration from environment and files"""
        try:
            # Load base configuration
            self.config = YMERAConfig()
            
            # Load from config file if provided
            if self.config_file and Path(self.config_file).exists():
                await self._load_config_file(self.config_file)
            
            # Validate configuration
            self._validate_config()
            
            self.logger.info(f"Configuration loaded successfully for environment: {self.config.environment}")
            return self.config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            raise
    
    async def _load_config_file(self, config_file: str):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
            
            # Update configuration with file values
            self._update_config_from_dict(file_config)
            
        except Exception as e:
            self.logger.warning(f"Failed to load config file {config_file}: {str(e)}")
    
    def _update_config_from_dict(self, config_dict: Dict[str, Any]):
        """Update configuration from dictionary"""
        for key, value in config_dict.items():
            if hasattr(self.config, key):
                if isinstance(value, dict) and hasattr(getattr(self.config, key), '__dict__'):
                    # Update nested configuration
                    nested_config = getattr(self.config, key)
                    for nested_key, nested_value in value.items():
                        if hasattr(nested_config, nested_key):
                            setattr(nested_config, nested_key, nested_value)
                else:
                    setattr(self.config, key, value)
    
    def _validate_config(self):
        """Validate critical configuration values"""
        if not self.config:
            raise ValueError("Configuration not loaded")
        
        # Validate required API keys based on providers
        ai_providers = [self.config.ai.default_llm_provider] + self.config.ai.fallback_llm_providers
        
        for provider in ai_providers:
            if provider == 'openai' and not self.config.ai.openai_api_key:
                self.logger.warning("OpenAI API key not configured")
            elif provider == 'anthropic' and not self.config.ai.anthropic_api_key:
                self.logger.warning("Anthropic API key not configured")
            elif provider == 'gemini' and not self.config.ai.gemini_api_key:
                self.logger.warning("Gemini API key not configured")
            elif provider == 'groq' and not self.config.ai.groq_api_key:
                self.logger.warning("Groq API key not configured")
            elif provider == 'deepseek' and not self.config.ai.deepseek_api_key:
                self.logger.warning("DeepSeek API key not configured")
        
        # Validate security settings
        if self.config.environment == 'production':
            if self.config.security.secret_key == 'your-super-secret-key-change-in-production':
                raise ValueError("Must set SECRET_KEY environment variable for production")
        
        # Validate database URL format
        if not self.config.database.url:
            raise ValueError("Database URL is required")
        
        self.logger.info("Configuration validation completed")
    
    def get_config(self) -> YMERAConfig:
        """Get current configuration"""
        if not self.config:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self.config
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.config and self.config.environment == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.config and self.config.environment == 'development'
    
    def get_ai_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for specific AI provider"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        provider_configs = {
            'openai': {
                'api_key': self.config.ai.openai_api_key,
                'model': 'gpt-4',
                'max_tokens': self.config.ai.max_tokens,
                'temperature': self.config.ai.temperature
            },
            'anthropic': {
                'api_key': self.config.ai.anthropic_api_key,
                'model': 'claude-3-sonnet-20240229',
                'max_tokens': self.config.ai.max_tokens,
                'temperature': self.config.ai.temperature
            },
            'gemini': {
                'api_key': self.config.ai.gemini_api_key,
                'model': 'gemini-pro',
                'max_tokens': self.config.ai.max_tokens,
                'temperature': self.config.ai.temperature
            },
            'groq': {
                'api_key': self.config.ai.groq_api_key,
                'model': 'mixtral-8x7b-32768',
                'max_tokens': self.config.ai.max_tokens,
                'temperature': self.config.ai.temperature
            },
            'deepseek': {
                'api_key': self.config.ai.deepseek_api_key,
                'model': 'deepseek-coder',
                'max_tokens': self.config.ai.max_tokens,
                'temperature': self.config.ai.temperature
            }
        }
        
        return provider_configs.get(provider, {})
    
    def export_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        if not self.config:
            raise RuntimeError("Configuration not loaded")
        
        config_dict = {}
        
        for field_name, field_value in self.config.__dict__.items():
            if hasattr(field_value, '__dict__'):
                # Nested configuration
                nested_dict = {}
                for nested_name, nested_value in field_value.__dict__.items():
                    if include_secrets or not self._is_secret_field(nested_name):
                        nested_dict[nested_name] = nested_value
                config_dict[field_name] = nested_dict
            elif include_secrets or not self._is_secret_field(field_name):
                config_dict[field_name] = field_value
        
        return config_dict
    
    def _is_secret_field(self, field_name: str) -> bool:
        """Check if field contains sensitive information"""
        secret_patterns = ['key', 'secret', 'password', 'token']
        return any(pattern in field_name.lower() for pattern in secret_patterns)
