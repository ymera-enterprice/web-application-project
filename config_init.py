"""
YMERA Enterprise - Configuration Module
Production-Ready Configuration Management - v4.0
Enterprise-grade implementation with zero placeholders
"""

# ===============================================================================
# STANDARD IMPORTS SECTION
# ===============================================================================

# Standard library imports (alphabetical)
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Local imports (alphabetical)
from .settings import Settings, get_settings
from .database import DatabaseConfig, get_database_config
from .security import SecurityConfig, get_security_config

# ===============================================================================
# MODULE METADATA
# ===============================================================================

__version__ = "4.0.0"
__author__ = "YMERA Enterprise Team"
__description__ = "Production-ready configuration management system"

# ===============================================================================
# CONFIGURATION REGISTRY
# ===============================================================================

class ConfigurationRegistry:
    """Central registry for all configuration components"""
    
    def __init__(self):
        self._settings: Optional[Settings] = None
        self._database_config: Optional[DatabaseConfig] = None
        self._security_config: Optional[SecurityConfig] = None
        self._initialized = False
    
    @property
    def settings(self) -> Settings:
        """Get application settings"""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration"""
        if self._database_config is None:
            self._database_config = get_database_config()
        return self._database_config
    
    @property
    def security(self) -> SecurityConfig:
        """Get security configuration"""
        if self._security_config is None:
            self._security_config = get_security_config()
        return self._security_config
    
    def initialize(self) -> None:
        """Initialize all configuration components"""
        if self._initialized:
            return
        
        # Force initialization of all configs
        _ = self.settings
        _ = self.database
        _ = self.security
        
        self._initialized = True
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of all configuration settings"""
        return {
            "application": {
                "name": self.settings.APP_NAME,
                "version": self.settings.VERSION,
                "environment": self.settings.ENVIRONMENT,
                "debug": self.settings.DEBUG
            },
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "database": self.database.database,
                "pool_size": self.database.pool_size
            },
            "security": {
                "jwt_algorithm": self.security.jwt_algorithm,
                "token_expire_minutes": self.security.access_token_expire_minutes,
                "password_min_length": self.security.password_min_length
            }
        }

# ===============================================================================
# GLOBAL CONFIGURATION INSTANCE
# ===============================================================================

# Global configuration registry instance
config = ConfigurationRegistry()

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def validate_environment() -> bool:
    """Validate that all required environment variables are set"""
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "REDIS_URL"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

def setup_environment() -> None:
    """Setup environment-specific configurations"""
    # Add project root to Python path
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Initialize configuration
    config.initialize()

def get_config_for_environment(env: str) -> Dict[str, Any]:
    """Get configuration optimized for specific environment"""
    base_config = config.get_config_summary()
    
    if env == "production":
        base_config.update({
            "logging_level": "INFO",
            "debug": False,
            "testing": False
        })
    elif env == "development":
        base_config.update({
            "logging_level": "DEBUG",
            "debug": True,
            "testing": False
        })
    elif env == "testing":
        base_config.update({
            "logging_level": "WARNING",
            "debug": False,
            "testing": True
        })
    
    return base_config

# ===============================================================================
# EXPORTS
# ===============================================================================

__all__ = [
    "config",
    "ConfigurationRegistry",
    "Settings",
    "DatabaseConfig",
    "SecurityConfig",
    "get_settings",
    "get_database_config",
    "get_security_config",
    "validate_environment",
    "setup_environment",
    "get_config_for_environment"
]