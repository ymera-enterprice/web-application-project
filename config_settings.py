"""
YMERA Enterprise - Settings Configuration
Production-Ready Environment-Based Settings - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import os
import secrets
from functools import lru_cache
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Third-party imports (alphabetical)
from pydantic import BaseSettings, Field, validator, root_validator
import structlog

# ===============================================================================
# LOGGING CONFIGURATION
# ===============================================================================

logger = structlog.get_logger("ymera.settings")

# ===============================================================================
# CONSTANTS & CONFIGURATION
# ===============================================================================

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
PROJECT_ROOT = Path(__file__).parent.parent

# Default values
DEFAULT_SECRET_KEY = secrets.token_urlsafe(32)
DEFAULT_DATABASE_URL = "postgresql://ymera:password@localhost:5432/ymera"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"

# ===============================================================================
# CORE SETTINGS CLASS
# ===============================================================================

class Settings(BaseSettings):
    """
    Comprehensive application settings with environment-based configuration.
    
    This class manages all application settings including database connections,
    security configurations, API settings, and environment-specific options.
    """
    
    # ===== APPLICATION CONFIGURATION =====
    APP_NAME: str = Field(default="YMERA Enterprise Platform", description="Application name")
    VERSION: str = Field(default="4.0.0", description="Application version")
    DESCRIPTION: str = Field(
        default="Enterprise-grade Multi-Agent Learning Platform",
        description="Application description"
    )
    
    # ===== ENVIRONMENT CONFIGURATION =====
    ENVIRONMENT: str = Field(default="development", description="Deployment environment")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    TESTING: bool = Field(default=False, description="Enable testing mode")
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting"""
        allowed_environments = ["development", "staging", "production", "testing"]
        if v.lower() not in allowed_environments:
            raise ValueError(f"Environment must be one of: {allowed_environments}")
        return v.lower()
    
    # ===== SECURITY CONFIGURATION =====
    SECRET_KEY: str = Field(default_factory=lambda: DEFAULT_SECRET_KEY, description="Application secret key")
    JWT_SECRET_KEY: str = Field(default_factory=lambda: DEFAULT_SECRET_KEY, description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=10080, description="Access token expiration")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30, description="Refresh token expiration")
    
    @validator("SECRET_KEY", "JWT_SECRET_KEY")
    def validate_secret_keys(cls, v):
        """Validate secret keys have minimum length"""
        if len(v) < 32:
            logger.warning("Secret key length is less than recommended 32 characters")
        return v
    
    # ===== DATABASE CONFIGURATION =====
    DATABASE_URL: str = Field(default=DEFAULT_DATABASE_URL, description="Primary database URL")
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1, le=100, description="Database connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=40, ge=0, le=100, description="Database max overflow connections")
    DATABASE_POOL_TIMEOUT: int = Field(default=30, ge=1, le=300, description="Database pool timeout seconds")
    DATABASE_POOL_RECYCLE: int = Field(default=3600, ge=300, le=86400, description="Database pool recycle seconds")
    
    # ===== REDIS CONFIGURATION =====
    REDIS_URL: str = Field(default=DEFAULT_REDIS_URL, description="Redis connection URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=20, ge=1, le=100, description="Redis max connections")
    REDIS_SOCKET_TIMEOUT: int = Field(default=30, ge=1, le=300, description="Redis socket timeout")
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(default=30, ge=1, le=300, description="Redis connect timeout")
    
    # ===== API CONFIGURATION =====
    API_V1_PREFIX: str = Field(default="/api/v1", description="API version 1 prefix")
    API_HOST: str = Field(default="0.0.0.0", description="API host address")
    API_PORT: int = Field(default=8000, ge=1, le=65535, description="API port number")
    API_WORKERS: int = Field(default=4, ge=1, le=16, description="API worker processes")
    API_TIMEOUT: int = Field(default=30, ge=1, le=300, description="API request timeout")
    
    # ===== CORS CONFIGURATION =====
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins"
    )
    CORS_CREDENTIALS: bool = Field(default=True, description="Allow CORS credentials")
    CORS_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        description="Allowed CORS methods"
    )
    CORS_HEADERS: List[str] = Field(
        default=["*"],
        description="Allowed CORS headers"
    )
    
    # ===== LOGGING CONFIGURATION =====
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format (json/console)")
    LOG_FILE_PATH: Optional[str] = Field(default=None, description="Log file path")
    LOG_ROTATION_SIZE: str = Field(default="100MB", description="Log rotation size")
    LOG_RETENTION_DAYS: int = Field(default=30, ge=1, le=365, description="Log retention days")
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate logging level"""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.upper()
    
    # ===== PERFORMANCE CONFIGURATION =====
    MAX_REQUEST_SIZE: int = Field(default=16777216, ge=1048576, description="Max request size in bytes (16MB)")
    REQUEST_TIMEOUT: int = Field(default=30, ge=1, le=300, description="Request timeout seconds")
    RATE_LIMIT_REQUESTS: int = Field(default=1000, ge=1, description="Rate limit requests per minute")
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=1, le=3600, description="Rate limit window seconds")
    
    # ===== AGENT CONFIGURATION =====
    MAX_AGENTS: int = Field(default=100, ge=1, le=1000, description="Maximum number of agents")
    AGENT_HEARTBEAT_INTERVAL: int = Field(default=30, ge=5, le=300, description="Agent heartbeat interval")
    AGENT_TIMEOUT: int = Field(default=300, ge=30, le=3600, description="Agent timeout seconds")
    AGENT_MAX_MEMORY: int = Field(default=1073741824, ge=104857600, description="Agent max memory bytes (1GB)")
    
    # ===== LEARNING SYSTEM CONFIGURATION =====
    LEARNING_ENABLED: bool = Field(default=True, description="Enable learning system")
    LEARNING_CYCLE_INTERVAL: int = Field(default=60, ge=10, le=3600, description="Learning cycle interval")
    KNOWLEDGE_SYNC_INTERVAL: int = Field(default=300, ge=60, le=3600, description="Knowledge sync interval")
    PATTERN_ANALYSIS_INTERVAL: int = Field(default=900, ge=300, le=7200, description="Pattern analysis interval")
    MEMORY_CONSOLIDATION_INTERVAL: int = Field(default=3600, ge=900, le=86400, description="Memory consolidation interval")
    
    # ===== FILE STORAGE CONFIGURATION =====
    UPLOAD_DIR: str = Field(default="uploads", description="Upload directory path")
    MAX_FILE_SIZE: int = Field(default=104857600, ge=1048576, description="Max file size bytes (100MB)")
    ALLOWED_FILE_TYPES: List[str] = Field(
        default=[".txt", ".json", ".csv", ".pdf", ".docx", ".xlsx"],
        description="Allowed file extensions"
    )
    
    # ===== MONITORING CONFIGURATION =====
    METRICS_ENABLED: bool = Field(default=True, description="Enable metrics collection")
    METRICS_PORT: int = Field(default=9090, ge=1, le=65535, description="Metrics server port")
    HEALTH_CHECK_INTERVAL: int = Field(default=30, ge=5, le=300, description="Health check interval")
    PERFORMANCE_TRACKING: bool = Field(default=True, description="Enable performance tracking")
    
    # ===== EXTERNAL INTEGRATIONS =====
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None, description="Slack webhook URL")
    EMAIL_SMTP_HOST: Optional[str] = Field(default=None, description="SMTP host for emails")
    EMAIL_SMTP_PORT: int = Field(default=587, ge=1, le=65535, description="SMTP port")
    
    @root_validator
    def validate_environment_specific_settings(cls, values):
        """Validate settings based on environment"""
        environment = values.get("ENVIRONMENT", "development")
        
        if environment == "production":
            # Production-specific validations
            if values.get("DEBUG", False):
                logger.warning("Debug mode is enabled in production environment")
            
            if values.get("SECRET_KEY") == DEFAULT_SECRET_KEY:
                raise ValueError("Default secret key cannot be used in production")
        
        elif environment == "development":
            # Development-specific settings
            values["DEBUG"] = values.get("DEBUG", True)
            values["LOG_LEVEL"] = values.get("LOG_LEVEL", "DEBUG")
        
        elif environment == "testing":
            # Testing-specific settings
            values["TESTING"] = True
            values["DATABASE_URL"] = values.get("TEST_DATABASE_URL", values.get("DATABASE_URL"))
            values["REDIS_URL"] = values.get("TEST_REDIS_URL", values.get("REDIS_URL"))
        
        return values
    
    # ===== COMPUTED PROPERTIES =====
    @property
    def database_settings(self) -> Dict[str, Any]:
        """Get database connection settings"""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "pool_timeout": self.DATABASE_POOL_TIMEOUT,
            "pool_recycle": self.DATABASE_POOL_RECYCLE
        }
    
    @property
    def redis_settings(self) -> Dict[str, Any]:
        """Get Redis connection settings"""
        return {
            "url": self.REDIS_URL,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT,
            "socket_connect_timeout": self.REDIS_SOCKET_CONNECT_TIMEOUT
        }
    
    @property
    def security_settings(self) -> Dict[str, Any]:
        """Get security configuration settings"""
        return {
            "secret_key": self.SECRET_KEY,
            "jwt_secret_key": self.JWT_SECRET_KEY,
            "jwt_algorithm": self.JWT_ALGORITHM,
            "access_token_expire_minutes": self.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expire_days": self.REFRESH_TOKEN_EXPIRE_DAYS
        }
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment"""
        return self.ENVIRONMENT == "testing" or self.TESTING
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        validate_assignment = True
        extra = "forbid"  # Forbid extra fields

# ===============================================================================
# ENVIRONMENT-SPECIFIC CONFIGURATIONS
# ===============================================================================

class DevelopmentSettings(Settings):
    """Development environment specific settings"""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    CORS_ORIGINS: List[str] = ["*"]

class ProductionSettings(Settings):
    """Production environment specific settings"""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    TESTING: bool = False
    
    class Config(Settings.Config):
        # In production, require all sensitive settings from environment
        fields = {
            "SECRET_KEY": {"env": "SECRET_KEY"},
            "JWT_SECRET_KEY": {"env": "JWT_SECRET_KEY"},
            "DATABASE_URL": {"env": "DATABASE_URL"},
            "REDIS_URL": {"env": "REDIS_URL"}
        }

class TestingSettings(Settings):
    """Testing environment specific settings"""
    TESTING: bool = True
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    DATABASE_URL: str = "sqlite:///test.db"
    REDIS_URL: str = "redis://localhost:6379/1"

# ===============================================================================
# SETTINGS FACTORY
# ===============================================================================

def get_settings_class():
    """Get the appropriate settings class based on environment"""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    settings_map = {
        "development": DevelopmentSettings,
        "staging": ProductionSettings,  # Use production settings for staging
        "production": ProductionSettings,
        "testing": TestingSettings
    }
    
    return settings_map.get(environment, DevelopmentSettings)

@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings with caching.
    
    This function creates and caches a Settings instance based on the current
    environment. The cache ensures that settings are loaded only once during
    application lifetime.
    
    Returns:
        Settings: Configured settings instance for the current environment
    """
    settings_class = get_settings_class()
    settings = settings_class()
    
    logger.info(
        "Settings initialized",
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
        version=settings.VERSION
    )
    
    return settings

# ===============================================================================
# CONFIGURATION VALIDATION
# ===============================================================================

def validate_settings(settings: Settings) -> Dict[str, Any]:
    """
    Validate settings configuration and return validation report.
    
    Args:
        settings: Settings instance to validate
        
    Returns:
        Dict containing validation results and recommendations
    """
    validation_report = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "recommendations": []
    }
    
    # Validate security settings
    if settings.is_production:
        if settings.SECRET_KEY == DEFAULT_SECRET_KEY:
            validation_report["errors"].append("Default secret key used in production")
            validation_report["valid"] = False
        
        if settings.DEBUG:
            validation_report["warnings"].append("Debug mode enabled in production")
    
    # Validate database settings
    if not settings.DATABASE_URL.startswith(("postgresql://", "sqlite://", "mysql://")):
        validation_report["warnings"].append("Unusual database URL format detected")
    
    # Validate performance settings
    if settings.DATABASE_POOL_SIZE < 10:
        validation_report["recommendations"].append("Consider increasing database pool size for better performance")
    
    if settings.API_WORKERS > 8:
        validation_report["recommendations"].append("High number of API workers may impact performance")
    
    # Log validation results
    if validation_report["errors"]:
        logger.error("Settings validation failed", errors=validation_report["errors"])
    elif validation_report["warnings"]:
        logger.warning("Settings validation warnings", warnings=validation_report["warnings"])
    else:
        logger.info("Settings validation passed successfully")
    
    return validation_report

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "Settings",
    "DevelopmentSettings",
    "ProductionSettings", 
    "TestingSettings",
    "get_settings",
    "get_settings_class",
    "validate_settings"
]