# YMERA Platform - Stage 1: Core Foundation
# Environment Configuration - Production Ready
# ================================================

# Application Configuration
APP_NAME="YMERA Platform"
APP_VERSION="3.0"
STAGE="Stage 1 - Core Foundation"
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8000

# Stage 1 Specific Settings
YMERA_STAGE=1
CORE_AGENTS_ENABLED=true
BASIC_SERVICES_ENABLED=true

# Security Configuration
SECRET_KEY=your-secret-key-here-generate-a-strong-one
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
ENCRYPTION_KEY=your-fernet-encryption-key-here

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ymera
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=100

# GitHub API Keys (3 keys, 1 admin)
GITHUB_TOKEN_1=ghp_your_github_token_1
GITHUB_TOKEN_2=ghp_your_github_token_2
GITHUB_TOKEN_ADMIN=ghp_your_admin_github_token

# Claude API Keys (7 keys)
CLAUDE_API_KEY_1=sk-ant-your_claude_key_1
CLAUDE_API_KEY_2=sk-ant-your_claude_key_2
CLAUDE_API_KEY_3=sk-ant-your_claude_key_3
CLAUDE_API_KEY_4=sk-ant-your_claude_key_4
CLAUDE_API_KEY_5=sk-ant-your_claude_key_5
CLAUDE_API_KEY_6=sk-ant-your_claude_key_6
CLAUDE_API_KEY_7=sk-ant-your_claude_key_7

# Gemini API Keys (5 keys)
GEMINI_API_KEY_1=your_gemini_key_1
GEMINI_API_KEY_2=your_gemini_key_2
GEMINI_API_KEY_3=your_gemini_key_3
GEMINI_API_KEY_4=your_gemini_key_4
GEMINI_API_KEY_5=your_gemini_key_5

# DeepSeek API Keys (5 keys)
DEEPSEEK_API_KEY_1=your_deepseek_key_1
DEEPSEEK_API_KEY_2=your_deepseek_key_2
DEEPSEEK_API_KEY_3=your_deepseek_key_3
DEEPSEEK_API_KEY_4=your_deepseek_key_4
DEEPSEEK_API_KEY_5=your_deepseek_key_5

# Groq API Keys (5 keys)
GROQ_API_KEY_1=your_groq_key_1
GROQ_API_KEY_2=your_groq_key_2
GROQ_API_KEY_3=your_groq_key_3
GROQ_API_KEY_4=your_groq_key_4
GROQ_API_KEY_5=your_groq_key_5

# Pinecone Configuration (1 key)
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=ymera-vectors

# OpenAI API Keys (8 keys, 3 service accounts)
OPENAI_API_KEY_1=sk-your_openai_key_1
OPENAI_API_KEY_2=sk-your_openai_key_2
OPENAI_API_KEY_3=sk-your_openai_key_3
OPENAI_API_KEY_4=sk-your_openai_key_4
OPENAI_API_KEY_5=sk-your_openai_key_5
OPENAI_SERVICE_ACCOUNT_1=sk-your_service_account_1
OPENAI_SERVICE_ACCOUNT_2=sk-your_service_account_2
OPENAI_SERVICE_ACCOUNT_3=sk-your_service_account_3

# AI Configuration
DEFAULT_MODEL=gpt-4
DEFAULT_TEMPERATURE=0.7
MAX_TOKENS=4000
CONTEXT_WINDOW_SIZE=8000

# Vector Database Configuration
VECTOR_DIMENSION=1536
SIMILARITY_THRESHOLD=0.8

# Enterprise Features
ENABLE_MONITORING=true
ENABLE_METRICS=true
ENABLE_LOGGING=true
LOG_LEVEL=INFO
SENTRY_DSN=your_sentry_dsn_if_using

# Performance Settings
WORKER_PROCESSES=4
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT=300
KEEP_ALIVE_TIMEOUT=65

# File Storage
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=100MB
ALLOWED_FILE_TYPES=py,txt,md,json,yaml,yml

# Code Analysis
ENABLE_SECURITY_SCAN=true
ENABLE_CODE_QUALITY_CHECK=true
PYLINT_THRESHOLD=8.0

# System Monitoring
HEALTH_CHECK_INTERVAL=60
METRICS_PORT=9090

# Development Settings (Remove in production)
RELOAD=true
ACCESS_LOG=true