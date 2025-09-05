# ===============================================================================
# YMERA Enterprise Platform - Environment Configuration Template
# Production-Ready Environment Variables - v4.0
# Copy this file to .env and configure for your environment
# ===============================================================================

# ===============================================================================
# APPLICATION CONFIGURATION
# ===============================================================================
ENVIRONMENT=development
DEBUG=true
APP_NAME="YMERA Enterprise Platform"
APP_VERSION="4.0.0"
SECRET_KEY=your-super-secret-key-change-this-in-production-minimum-32-characters
API_V1_PREFIX="/api/v1"

# ===============================================================================
# SERVER CONFIGURATION
# ===============================================================================
HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=false

# SSL Configuration (optional)
SSL_CERT_FILE=
SSL_KEY_FILE=

# Allowed hosts for security (comma-separated)
ALLOWED_HOSTS=localhost,127.0.0.1,*.yourdomain.com

# ===============================================================================
# DATABASE CONFIGURATION
# ===============================================================================
# Primary Database
DATABASE_URL=postgresql+asyncpg://ymera_user:ymera_password@localhost:5432/ymera_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# Test Database (for running tests)
TEST_DATABASE_URL=postgresql+asyncpg://ymera_test:ymera_test@localhost:5432/ymera_test_db

# Database Migration Settings
ALEMBIC_CONFIG_FILE=alembic.ini
AUTO_MIGRATE=false

# ===============================================================================
# REDIS CONFIGURATION
# ===============================================================================
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=100
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_HEALTH_CHECK_INTERVAL=30

# Redis Clusters (if using Redis Cluster)
REDIS_CLUSTER_NODES=localhost:7000,localhost:7001,localhost:7002

# ===============================================================================
# AUTHENTICATION & SECURITY
# ===============================================================================
# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-should-be-different-from-app-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Password Hashing
PASSWORD_HASH_ROUNDS=12

# API Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,https://yourdomain.com
CORS_ALLOW_CREDENTIALS=true

# ===============================================================================
# LEARNING ENGINE CONFIGURATION
# ===============================================================================
# Core Learning Settings
LEARNING_ENGINE_ENABLED=true
LEARNING_CYCLE_INTERVAL=60
KNOWLEDGE_SYNC_INTERVAL=300
PATTERN_DISCOVERY_INTERVAL=900
MEMORY_CONSOLIDATION_INTERVAL=3600

# Learning Performance Settings
MAX_LEARNING_BATCH_SIZE=1000
LEARNING_THREAD_POOL_SIZE=4
KNOWLEDGE_RETENTION_DAYS=90
PATTERN_SIGNIFICANCE_THRESHOLD=0.75

# Inter-Agent Learning
INTER_AGENT_SYNC_ENABLED=true
KNOWLEDGE_TRANSFER_TIMEOUT=30
COLLABORATION_SCORE_THRESHOLD=0.6

# External Learning Integration
EXTERNAL_LEARNING_ENABLED=true
EXTERNAL_KNOWLEDGE_VALIDATION=true
KNOWLEDGE_CONFIDENCE_THRESHOLD=0.8

# ===============================================================================
# AGENT CONFIGURATION
# ===============================================================================
# Agent Registry Settings
MAX_AGENTS_PER_USER=10
AGENT_IDLE_TIMEOUT=3600
AGENT_CLEANUP_INTERVAL=1800

# Agent Performance
AGENT_MAX_CONCURRENT_TASKS=5
AGENT_TASK_TIMEOUT=300
AGENT_MEMORY_LIMIT=512

# Agent Communication
AGENT_MESSAGE_QUEUE_SIZE=1000
AGENT_HEARTBEAT_INTERVAL=30
AGENT_DISCOVERY_ENABLED=true

# ===============================================================================
# MACHINE LEARNING & AI CONFIGURATION
# ===============================================================================
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_ORG_ID=your-openai-org-id
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=4000
OPENAI_TEMPERATURE=0.7

# Anthropic Configuration
ANTHROPIC_API_KEY=your-anthropic-api-key-here
ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Local LLM Configuration (if using local models)
LOCAL_LLM_ENABLED=false
LOCAL_LLM_MODEL_PATH=/models/llama-2-7b-chat
LOCAL_LLM_DEVICE=cpu
LOCAL_LLM_MAX_LENGTH=2048

# Embeddings Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_BATCH_SIZE=32

# ===============================================================================
# VECTOR DATABASE CONFIGURATION
# ===============================================================================
# ChromaDB Configuration
CHROMA_ENABLED=true
CHROMA_PERSIST_DIRECTORY=./data/chroma
CHROMA_COLLECTION_NAME=ymera_knowledge

# Pinecone Configuration (if using Pinecone)
PINECONE_ENABLED=false
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-west1-gcp
PINECONE_INDEX_NAME=ymera-index

# Qdrant Configuration (if using Qdrant)
QDRANT_ENABLED=false
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=ymera_vectors

# ===============================================================================
# KNOWLEDGE GRAPH CONFIGURATION
# ===============================================================================
# Neo4j Configuration
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
NEO4J_DATABASE=ymera

# Graph Processing
GRAPH_MAX_NODES=100000
GRAPH_MAX_RELATIONSHIPS=1000000
GRAPH_QUERY_TIMEOUT=30

# ===============================================================================
# FILE STORAGE CONFIGURATION
# ===============================================================================
# Local File Storage
FILE_STORAGE_TYPE=local
FILE_STORAGE_PATH=./data/files
FILE_MAX_SIZE_MB=100
ALLOWED_FILE_TYPES=pdf,docx,txt,csv,json,xlsx

# AWS S3 Configuration (if using S3)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-west-2
AWS_S3_BUCKET=ymera-files

# Azure Blob Storage Configuration (if using Azure)
AZURE_STORAGE_CONNECTION_STRING=your-azure-connection-string
AZURE_CONTAINER_NAME=ymera-files

# Google Cloud Storage Configuration (if using GCS)
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GCS_BUCKET_NAME=ymera-files

# ===============================================================================
# LOGGING & MONITORING CONFIGURATION
# ===============================================================================
# Logging Settings
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=./logs/ymera.log
LOG_MAX_FILE_SIZE=100MB
LOG_BACKUP_COUNT=5

# Structured Logging
STRUCTLOG_ENABLED=true
LOG_CORRELATION_ID=true

# Monitoring & Metrics
METRICS_ENABLED=true
PROMETHEUS_METRICS_PORT=9090
HEALTH_CHECK_INTERVAL=30

# OpenTelemetry Configuration
OTEL_ENABLED=false
OTEL_SERVICE_NAME=ymera-enterprise
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Sentry Configuration (Error Tracking)
SENTRY_ENABLED=false
SENTRY_DSN=your-sentry-dsn-here
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1

# ===============================================================================
# MESSAGE QUEUE CONFIGURATION
# ===============================================================================
# Celery Configuration
CELERY_ENABLED=true
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_TIMEZONE=UTC
CELERY_WORKER_CONCURRENCY=4

# Apache Kafka Configuration (if using Kafka)
KAFKA_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_PREFIX=ymera
KAFKA_CONSUMER_GROUP=ymera-group

# RabbitMQ Configuration (if using RabbitMQ)
RABBITMQ_ENABLED=false
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# ===============================================================================
# SEARCH ENGINE CONFIGURATION
# ===============================================================================
# Elasticsearch Configuration
ELASTICSEARCH_ENABLED=false
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_INDEX_PREFIX=ymera
ELASTICSEARCH_USERNAME=
ELASTICSEARCH_PASSWORD=

# OpenSearch Configuration (if using OpenSearch)
OPENSEARCH_ENABLED=false
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=
OPENSEARCH_PASSWORD=

# ===============================================================================
# ENTERPRISE INTEGRATIONS
# ===============================================================================
# LDAP Configuration
LDAP_ENABLED=false
LDAP_SERVER=ldap://your-ldap-server:389
LDAP_BASE_DN=dc=company,dc=com
LDAP_BIND_DN=cn=admin,dc=company,dc=com
LDAP_BIND_PASSWORD=your-ldap-password
LDAP_USER_SEARCH_BASE=ou=users,dc=company,dc=com

# SAML Configuration
SAML_ENABLED=false
SAML_ENTITY_ID=ymera-enterprise
SAML_SSO_URL=https://your-idp.com/sso
SAML_X509_CERT_PATH=./certs/saml.crt
SAML_PRIVATE_KEY_PATH=./certs/saml.key

# Microsoft Graph API
MS_GRAPH_ENABLED=false
MS_GRAPH_CLIENT_ID=your-ms-graph-client-id
MS_GRAPH_CLIENT_SECRET=your-ms-graph-client-secret
MS_GRAPH_TENANT_ID=your-tenant-id

# Google API Configuration
GOOGLE_API_ENABLED=false
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_PROJECT_ID=your-google-project-id

# ===============================================================================
# PERFORMANCE & SCALING CONFIGURATION
# ===============================================================================
# Connection Pooling
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
REDIS_CONNECTION_POOL_SIZE=100

# Caching Configuration
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
CACHE_COMPRESSION=true

# Background Task Configuration
BACKGROUND_TASK_WORKERS=4
BACKGROUND_TASK_QUEUE_SIZE=1000
BACKGROUND_TASK_TIMEOUT=300

# ===============================================================================
# DEVELOPMENT & TESTING CONFIGURATION
# ===============================================================================
# Development Settings
DEV_RELOAD=true
DEV_DEBUG_TOOLBAR=true
DEV_PROFILER_ENABLED=false

# Testing Configuration
TEST_DATABASE_RESET=true
TEST_PARALLEL=true
TEST_COVERAGE_THRESHOLD=90
TEST_FIXTURES_PATH=./tests/fixtures

# Mock Services (for testing)
MOCK_OPENAI=false
MOCK_EXTERNAL_APIS=false
MOCK_FILE_STORAGE=false

# ===============================================================================
# BACKUP & DISASTER RECOVERY
# ===============================================================================
# Database Backup
DB_BACKUP_ENABLED=false
DB_BACKUP_SCHEDULE="0 2 * * *"  # Daily at 2 AM
DB_BACKUP_RETENTION_DAYS=30
DB_BACKUP_STORAGE_PATH=./backups/db

# File Backup
FILE_BACKUP_ENABLED=false
FILE_BACKUP_SCHEDULE="0 3 * * *"  # Daily at 3 AM
FILE_BACKUP_RETENTION_DAYS=30

# ===============================================================================
# SECURITY CONFIGURATION
# ===============================================================================
# Security Headers
SECURITY_HEADERS_ENABLED=true
HSTS_MAX_AGE=31536000
CSP_ENABLED=true
CSP_POLICY="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

# API Security
API_KEY_ENABLED=false
API_KEY_HEADER_NAME=X-API-Key
REQUIRE_HTTPS=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STRATEGY=sliding_window
RATE_LIMIT_REDIS_URL=redis://localhost:6379/3

# ===============================================================================
# FEATURE FLAGS
# ===============================================================================
# Core Features
FEATURE_USER_REGISTRATION=true
FEATURE_AGENT_CREATION=true
FEATURE_FILE_UPLOAD=true
FEATURE_REAL_TIME_CHAT=true

# Advanced Features
FEATURE_MULTI_AGENT_COLLABORATION=true
FEATURE_KNOWLEDGE_GRAPH=true
FEATURE_PATTERN_RECOGNITION=true
FEATURE_EXTERNAL_INTEGRATIONS=true

# Experimental Features
FEATURE_AUTO_SCALING=false
FEATURE_PREDICTIVE_ANALYTICS=false
FEATURE_ADVANCED_NLP=false

# ===============================================================================
# CUSTOM CONFIGURATION
# ===============================================================================
# Add your custom environment variables here
# CUSTOM_INTEGRATION_API_KEY=your-custom-api-key
# CUSTOM_SERVICE_URL=https://api.custom-service.com
# CUSTOM_FEATURE_ENABLED=true