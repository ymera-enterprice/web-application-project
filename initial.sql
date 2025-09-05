-- YMERA Core Database Schema
-- Version: 1.0.0
-- Description: Initial database schema for YMERA enterprise platform

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types
CREATE TYPE user_status AS ENUM (
    'active',
    'inactive', 
    'suspended',
    'pending_verification',
    'locked',
    'deleted'
);

CREATE TYPE activity_type AS ENUM (
    'login',
    'logout',
    'password_change',
    'profile_update',
    'agent_create',
    'agent_update',
    'agent_delete',
    'learning_data_add',
    'system_access'
);

CREATE TYPE agent_status AS ENUM (
    'active',
    'inactive',
    'error',
    'maintenance'
);

-- ============================================================================
-- USERS TABLE
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt VARCHAR(32) NOT NULL,
    
    -- Profile information
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    display_name VARCHAR(200),
    avatar_url TEXT,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    
    -- Security fields
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    email_verification_token VARCHAR(255),
    email_verification_expires TIMESTAMPTZ,
    is_mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret VARCHAR(32),
    backup_codes JSONB NOT NULL DEFAULT '[]',
    
    -- Account security
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    last_login_ip VARCHAR(45), -- IPv6 compatible
    password_changed_at TIMESTAMPTZ,
    
    -- Status
    user_status user_status NOT NULL DEFAULT 'pending_verification',
    
    -- Metadata and timestamps
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for users table
CREATE UNIQUE INDEX users_email_idx ON users(email);
CREATE UNIQUE INDEX users_username_idx ON users(username);
CREATE INDEX users_status_email_idx ON users(user_status, email);
CREATE INDEX users_last_login_idx ON users(last_login_at);
CREATE INDEX users_created_at_idx ON users(created_at);

-- Create trigram indexes for search
CREATE INDEX users_username_trgm_idx ON users USING GIN (username gin_trgm_ops);
CREATE INDEX users_email_trgm_idx ON users USING GIN (email gin_trgm_ops);
CREATE INDEX users_name_trgm_idx ON users USING GIN ((first_name || ' ' || last_name) gin_trgm_ops);

-- ============================================================================
-- USER SESSIONS TABLE
-- ============================================================================

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    
    -- Session details
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_info JSONB NOT NULL DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for user_sessions table
CREATE UNIQUE INDEX sessions_token_idx ON user_sessions(session_token);
CREATE UNIQUE INDEX sessions_refresh_token_idx ON user_sessions(refresh_token);
CREATE INDEX sessions_user_id_idx ON user_sessions(user_id);
CREATE INDEX sessions_active_idx ON user_sessions(is_active, expires_at);
CREATE INDEX sessions_expires_at_idx ON user_sessions(expires_at);

-- ============================================================================
-- USER ACTIVITIES TABLE
-- ============================================================================

CREATE TABLE user_activities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL,
    
    -- Activity details
    activity_type activity_type NOT NULL,
    activity_details JSONB NOT NULL DEFAULT '{}',
    
    -- Context information
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Resource information
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    
    -- Result information
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    duration_ms INTEGER,
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for user_activities table
CREATE INDEX activities_user_type_time_idx ON user_activities(user_id, activity_type, created_at);
CREATE INDEX activities_resource_idx ON user_activities(resource_type, resource_id);
CREATE INDEX activities_created_at_idx ON user_activities(created_at);
CREATE INDEX activities_success_idx ON user_activities(success);

-- ============================================================================
-- ROLES TABLE
-- ============================================================================

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '[]',
    is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for roles table
CREATE UNIQUE INDEX roles_code_idx ON roles(code);

-- ============================================================================
-- USER ROLES JUNCTION TABLE
-- ============================================================================

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by UUID REFERENCES users(id),
    
    PRIMARY KEY (user_id, role_id)
);

-- Create indexes for user_roles table
CREATE INDEX user_roles_user_role_idx ON user_roles(user_id, role_id);
CREATE INDEX user_roles_assigned_at_idx ON user_roles(assigned_at);

-- ============================================================================
-- AGENTS TABLE
-- ============================================================================

CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) UNIQUE NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Configuration
    capabilities JSONB NOT NULL DEFAULT '[]',
    configuration JSONB NOT NULL DEFAULT '{}',
    max_concurrent_tasks INTEGER NOT NULL DEFAULT 10,
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    memory_limit_mb INTEGER NOT NULL DEFAULT 512,
    
    -- Status
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    status agent_status NOT NULL DEFAULT 'inactive',
    last_heartbeat TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB NOT NULL DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for agents table
CREATE UNIQUE INDEX agents_agent_id_idx ON agents(agent_id);
CREATE INDEX agents_type_idx ON agents(agent_type);
CREATE INDEX agents_status_idx ON agents(status);
CREATE INDEX agents_enabled_idx ON agents(enabled);
CREATE INDEX agents_created_by_idx ON agents(created_by);
CREATE INDEX agents_last_heartbeat_idx ON agents(last_heartbeat);

-- Create trigram indexes for search
CREATE INDEX agents_name_trgm_idx ON agents USING GIN (name gin_trgm_ops);
CREATE INDEX agents_description_trgm_idx ON agents USING GIN (description gin_trgm_ops);

-- ============================================================================
-- AGENT LEARNING DATA TABLE
-- ============================================================================

CREATE TABLE agent_learning_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_agent_id VARCHAR(100) NOT NULL,
    knowledge_type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    confidence_score INTEGER NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
    tags JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for agent_learning_data table
CREATE INDEX learning_data_source_agent_idx ON agent_learning_data(source_agent_id);
CREATE INDEX learning_data_knowledge_type_idx ON agent_learning_data(knowledge_type);
CREATE INDEX learning_data_confidence_idx ON agent_learning_data(confidence_score);
CREATE INDEX learning_data_created_at_idx ON agent_learning_data(created_at);

-- Create GIN index for tags search
CREATE INDEX learning_data_tags_idx ON agent_learning_data USING GIN (tags);

-- ============================================================================
-- SYSTEM HEALTH TABLE
-- ============================================================================

CREATE TABLE system_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    response_time_ms INTEGER,
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for system_health table
CREATE INDEX health_component_idx ON system_health(component);
CREATE INDEX health_status_idx ON system_health(status);
CREATE INDEX health_time_idx ON system_health(created_at);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_roles_updated_at BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to cleanup expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions 
    WHERE expires_at < NOW() OR is_active = FALSE;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup old activities (keep last 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_activities()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_activities 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup old health records (keep last 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_health_records()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM system_health 
    WHERE created_at < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DEFAULT DATA
-- ============================================================================

-- Insert default roles
INSERT INTO roles (code, name, description, permissions, is_system_role) VALUES
('admin', 'Administrator', 'Full system access', '["*"]', TRUE),
('user', 'User', 'Standard user access', '["read", "create_agent", "manage_own_data"]', TRUE),
('agent_manager', 'Agent Manager', 'Manage agents and learning data', '["read", "create_agent", "update_agent", "delete_agent", "manage_learning_data"]', TRUE),
('viewer', 'Viewer', 'Read-only access', '["read"]', TRUE);

-- ============================================================================
-- PERFORMANCE OPTIMIZATIONS
-- ============================================================================

-- Analyze tables for better query planning
ANALYZE users;
ANALYZE user_sessions;
ANALYZE user_activities;
ANALYZE roles;
ANALYZE user_roles;
ANALYZE agents;
ANALYZE agent_learning_data;
ANALYZE system_health;

-- Set autovacuum parameters for high-activity tables
ALTER TABLE user_activities SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE user_sessions SET (
    autovacuum_vacuum_scale_factor = 0.2,
    autovacuum_analyze_scale_factor = 0.1
);

ALTER TABLE system_health SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE users IS 'Core user accounts and authentication data';
COMMENT ON TABLE user_sessions IS 'Active user sessions with JWT token management';
COMMENT ON TABLE user_activities IS 'Audit trail of all user actions';
COMMENT ON TABLE roles IS 'Role-based access control definitions';
COMMENT ON TABLE user_roles IS 'User-role assignments';
COMMENT ON TABLE agents IS 'AI agents configuration and status';
COMMENT ON TABLE agent_learning_data IS 'Knowledge data generated by agents';
COMMENT ON TABLE system_health IS 'System health monitoring records';

COMMENT ON COLUMN users.password_hash IS 'PBKDF2 hashed password with salt';
COMMENT ON COLUMN users.salt IS 'Random salt for password hashing';
COMMENT ON COLUMN users.metadata IS 'Flexible JSON metadata storage';
COMMENT ON COLUMN user_sessions.device_info IS 'Client device information';
COMMENT ON COLUMN agents.capabilities IS 'Array of agent capability strings';
COMMENT ON COLUMN agents.configuration IS 'Agent-specific configuration JSON';
COMMENT ON COLUMN agent_learning_data.confidence_score IS 'Confidence score 0-100';

-- Migration complete
SELECT 'YMERA Core database schema initialized successfully' as status;
