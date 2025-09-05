# config.py
import os
from typing import Dict, Optional

class Config:
    """Configuration class for YMERA Enterprise Platform."""

    def __init__(self):
        # Security settings
        self.security: Dict[str, str] = {
            'secret_key': os.getenv("SECRET_KEY", "your-secret-key-here"),
            'algorithm': os.getenv("JWT_ALGORITHM", "HS256"),
        }

        # System settings
        self.system: Dict[str, str] = {
            'host': os.getenv("HOST", "0.0.0.0"),
            'port': int(os.getenv("PORT", "8000")),
            'db_url': os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ymera_db"),
        }

        # API keys and endpoints
        self.api_keys: Dict[str, Optional[str]] = {
            'openai_api_key': os.getenv("OPENAI_API_KEY"),
            'xai_api_key': os.getenv("XAI_API_KEY"),
            'pinecone_api_key': os.getenv("PINECONE_API_KEY"),
            'anthropic_api_key': os.getenv("ANTHROPIC_API_KEY"),
            'gemini_api_key': os.getenv("GEMINI_API_KEY"),
            'groq_api_key': os.getenv("GROQ_API_KEY"),
            'deepseek_api_key': os.getenv("DEEPSEEK_API_KEY"),
            'together_ai_api_key': os.getenv("TOGETHER_AI_API_KEY"),
            'mistral_api_key': os.getenv("MISTRAL_API_KEY"),
            'maystro_api_key': os.getenv("MAYSTRO_API_KEY"),
            'github_api_key': os.getenv("GITHUB_API_KEY"),
            'discord_api_key': os.getenv("DISCORD_API_KEY"),
            'gemini_studio_api_key': os.getenv("GEMENI_STUDIO_API_KEY"),
        }

        # API endpoints and settings
        self.api_endpoints: Dict[str, str] = {
            'openai_base_url': "https://api.openai.com/v1",
            'xai_base_url': "https://api.x.ai/v1",
            'pinecone_env': os.getenv("PINECONE_ENV", "us-east-1"),
            'pinecone_index': os.getenv("PINECONE_INDEX", "ymera-learning"),
        }

        # Learning engine settings
        self.learning: Dict[str, str] = {
            'default_model': os.getenv("DEFAULT_MODEL", "openai"),
            'embedding_model': os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        }

    def get_api_key(self, service: str) -> Optional[str]:
        """Retrieve API key for a specific service."""
        return self.api_keys.get(service)

    def get_endpoint(self, service: str) -> str:
        """Retrieve endpoint URL for a specific service."""
        return self.api_endpoints.get(service, "")

# Instantiate config
config = Config()