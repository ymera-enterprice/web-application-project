# YMERA Enterprise Multi-Agent System - Environment Configuration Template
# Copy this file to .env and fill in your actual values

# ====== Application Configuration ======
APP_NAME=YMERA Enterprise Multi-Agent System
APP_VERSION=2.0.0
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=8000
WORKERS=2
MAX_WORKERS=4
LOG_LEVEL=INFO
SECRET_KEY=your-super-secure-secret-key-here-change-this-in-production

# ====== Database Configuration ======
DATABASE_URL=postgresql://ymera_user:ymera_secure_2024@localhost:5432/ymera_enterprise
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_ECHO=false

# ====== Redis Configuration ======
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_DB=1
REDIS_SESSION_DB=2
REDIS_QUEUE_DB=3
CACHE_DEFAULT_TTL=3600

# ====== JWT Configuration ======
JWT_SECRET_KEY=your-jwt-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ====== AI Service API Keys ======
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GEMINI_API_KEY=your-google-gemini-api-key-here
GROQ_API_KEY=your-groq-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# AI Provider Configuration
DEFAULT_LLM_PROVIDER=openai
FALLBACK_LLM_PROVIDERS=anthropic,gemini,groq
EMBEDDING_MODEL=text-embedding-3-large
MAX_TOKENS=4096
TEMPERATURE=0.1

# ====== Vector Database Configuration ======
# Pinecone
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_ENVIRONMENT=us-west1-gcp-free
PINECONE_INDEX_NAME=ymera-knowledge-base
VECTOR_DIMENSION=3072

# Alternative Vector DBs (uncomment if using)
# WEAVIATE_URL=http://localhost:8080
# QDRANT_URL=http://localhost:6333
# CHROMA_PERSIST_DIRECTORY=./chroma_db

# ====== GitHub Integration ======
GITHUB_TOKEN=your-github-personal-access-token
GITHUB_WEBHOOK_SECRET=your-github-webhook-secret
GITHUB_APP_ID=your-github-app-id
GITHUB_PRIVATE_KEY_PATH=./github-private-key.pem

# ====== External Service Configuration ======
# Sentry (Error Monitoring)
SENTRY_DSN=your-sentry-dsn-here
SENTRY_ENVIRONMENT=production

# Prometheus Monitoring
PROMETHEUS_PORT=9090
METRICS_ENABLED=true

# Email Configuration (for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_TLS=true

# ====== Security Configuration ======
ALLOWED_ORIGINS=https://your-domain.com,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# SSL/TLS Configuration
SSL_ENABLED=false
SSL_CERT_PATH=./certs/cert.pem
SSL_KEY_PATH=./certs/key.pem

# ====== Storage Configuration ======
# Local Storage
UPLOAD_PATH=./uploads
MAX_UPLOAD_SIZE=100MB
ALLOWED_EXTENSIONS=.py,.js,.ts,.json,.yaml,.yml,.md,.txt,.pdf,.docx

# Cloud Storage (Optional)
# AWS_ACCESS_KEY_ID=your-aws-access-key
# AWS_SECRET_ACCESS_KEY=your-aws-secret-key
# AWS_BUCKET_NAME=ymera-enterprise-storage
# AWS_REGION=us-east-1

# ====== Deployment Configuration ======
DEPLOYMENT_ENVIRONMENT=replit
CONTAINER_REGISTRY=ghcr.io
DOCKER_IMAGE_TAG=latest

# Kubernetes Configuration (if using)
# KUBERNETES_NAMESPACE=ymera-enterprise
# KUBERNETES_CONFIG_PATH=~/.kube/config

# ====== Monitoring & Observability ======
HEALTH_CHECK_INTERVAL=30
METRICS_COLLECTION_INTERVAL=60
LOG_RETENTION_DAYS=30
STRUCTURED_LOGGING=true

# OpenTelemetry Configuration
OTEL_ENABLED=true
OTEL_SERVICE_NAME=ymera-enterprise
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# ====== Agent System Configuration ======
AGENT_MAX_CONCURRENT_TASKS=10
AGENT_TASK_TIMEOUT=300
AGENT_HEARTBEAT_INTERVAL=30
AGENT_RETRY_ATTEMPTS=3
AGENT_RETRY_DELAY=5

# Learning Engine Configuration
LEARNING_ENABLED=true
LEARNING_BATCH_SIZE=100
LEARNING_EVALUATION_INTERVAL=3600
KNOWLEDGE_UPDATE_THRESHOLD=0.8

# ====== Performance Configuration ======
# Async Configuration
ASYNCIO_TASK_TIMEOUT=300
MAX_CONCURRENT_REQUESTS=1000
REQUEST_TIMEOUT=30

# Memory Management
MEMORY_LIMIT_MB=2048
GARBAGE_COLLECTION_THRESHOLD=1000

# Connection Pooling
HTTP_POOL_CONNECTIONS=100
HTTP_POOL_MAXSIZE=100
HTTP_MAX_RETRIES=3

# ====== Development & Testing ======
TESTING=false
TEST_DATABASE_URL=postgresql://test_user:test_pass@localhost:5432/test_ymera
MOCK_EXTERNAL_SERVICES=false

# Code Analysis Configuration
CODE_QUALITY_THRESHOLD=8.0
SECURITY_SCAN_ENABLED=true
VULNERABILITY_THRESHOLD=medium

# ====== Backup Configuration ======
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_DAYS=30
BACKUP_STORAGE_PATH=./backups

# Database Backup
DB_BACKUP_ENABLED=true
DB_BACKUP_COMPRESSION=true

# ====== Feature Flags ======
FEATURE_ADVANCED_ANALYTICS=true
FEATURE_REAL_TIME_COLLABORATION=true
FEATURE_AUTO_DEPLOYMENT=true
FEATURE_SEMANTIC_SEARCH=true
FEATURE_CODE_GENERATION=true
FEATURE_VULNERABILITY_SCANNING=true

# ====== Experimental Features ======
EXPERIMENTAL_MULTI_MODAL_AI=false
EXPERIMENTAL_QUANTUM_ALGORITHMS=false
EXPERIMENTAL_BLOCKCHAIN_INTEGRATION=false

# ====== Third-Party Integrations ======
# Slack Integration
SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
SLACK_CHANNEL=#ymera-notifications

# Discord Integration
DISCORD_BOT_TOKEN=your-discord-bot-token
DISCORD_GUILD_ID=your-discord-guild-id

# Webhook Configuration
WEBHOOK_SECRET=your-webhook-secret-key
WEBHOOK_TIMEOUT=30

# ====== Advanced Configuration ======
# Multi-tenancy
MULTI_TENANT_ENABLED=false
DEFAULT_TENANT_ID=default

# Internationalization
DEFAULT_LANGUAGE=en
SUPPORTED_LANGUAGES=en,es,fr,de,zh,ja

# Time Zone Configuration
DEFAULT_TIMEZONE=UTC
LOCALIZE_TIMESTAMPS=true

# ====== Replit Specific Configuration ======
REPL_OWNER=your-replit-username
REPL_SLUG=ymera-enterprise
REPL_ID=your-repl-id

# Replit Database (if using)
REPLIT_DB_URL=your-replit-database-url

# ====== Production Optimizations ======
UVLOOP_ENABLED=true
HTTPTOOLS_ENABLED=true
ORJSON_ENABLED=true
CYTHON_ENABLED=true

# Caching Strategy
CACHE_STRATEGY=redis
CACHE_COMPRESSION=true
CACHE_SERIALIZATION=msgpack

# ====== Security Hardening ======
SECURITY_HEADERS_ENABLED=true
CSP_ENABLED=true
HSTS_ENABLED=true
SECURE_COOKIES=true

# Authentication & Authorization
OAUTH2_ENABLED=false
LDAP_ENABLED=false
SAML_ENABLED=false

# ====== Scaling Configuration ======
AUTO_SCALING_ENABLED=false
MIN_REPLICAS=1
MAX_REPLICAS=10
TARGET_CPU_UTILIZATION=70

# Load Balancing
LOAD_BALANCER_ENABLED=false
SESSION_AFFINITY=false

# ====== Compliance & Auditing ======
AUDIT_LOGGING_ENABLED=true
GDPR_COMPLIANCE=true
HIPAA_COMPLIANCE=false
SOX_COMPLIANCE=false

# Data Retention
DATA_RETENTION_POLICY=365
LOG_RETENTION_POLICY=90
BACKUP_RETENTION_POLICY=30

# ====== Custom Extensions ======
CUSTOM_PLUGINS_ENABLED=false
PLUGIN_DIRECTORY=./plugins
PLUGIN_CONFIG_PATH=./plugins/config

# Webhook Endpoints for Custom Integrations
CUSTOM_WEBHOOK_ENDPOINTS=
EXTERNAL_API_ENDPOINTS=

# ====== End of Configuration ======
# Remember to:
# 1. Never commit this file with real secrets to version control
# 2. Use Replit Secrets for sensitive values in production
# 3. Regularly rotate API keys and secrets
# 4. Monitor usage and costs for external services
# 5. Test configuration changes in a staging environment first