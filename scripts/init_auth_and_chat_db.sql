-- ============================================================================
-- Script: init_auth_and_chat_db.sql
-- Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
-- Description: DDL Migration script for User Management, Authentication,
--              Chat Sessions, Chat Messages with RAG sources, User Feedbacks,
--              and Security Audit Logs with full Foreign Key constraints and Indexes.
-- ============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- 2. Users Table (Authentication & RBAC)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for high-speed authentication lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ----------------------------------------------------------------------------
-- 3. Chat Sessions Table (Session History & Isolation)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'Yeni Sohbet',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Foreign Key & sorting indexes for chat sessions
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. Chat Messages Table (Messages, Roles & RAG Metadata)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Foreign Key, chronological ordering and GIN index for sources
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_sources_gin ON chat_messages USING gin (sources_metadata);

-- ----------------------------------------------------------------------------
-- 5. Feedbacks Table (Message Evaluation & Ratings)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    rating INT NOT NULL CHECK (rating >= 0 AND rating <= 5), -- 1-5 stars or 0/1 thumbs
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Foreign Key index for feedback analytics
CREATE INDEX IF NOT EXISTS idx_feedbacks_message_id ON feedbacks(message_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_rating ON feedbacks(rating);

-- ----------------------------------------------------------------------------
-- 6. Audit Logs Table (Security, Compliance & Activity Monitoring)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL, -- 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'QUERY_EXECUTED', 'PASSWORD_RESET', etc.
    ip_address VARCHAR(45),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Audit query indexes for security analysis and reporting
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);

-- ----------------------------------------------------------------------------
-- Verification Comments
-- ----------------------------------------------------------------------------
COMMENT ON TABLE users IS 'Stores registered users, salted password hashes, and RBAC roles.';
COMMENT ON TABLE chat_sessions IS 'Stores user-isolated chat sessions for conversation history.';
COMMENT ON TABLE chat_messages IS 'Stores multi-turn chat messages with RAG sources metadata JSONB.';
COMMENT ON TABLE feedbacks IS 'Stores user ratings (1-5 or thumbs up/down) and qualitative feedback on assistant responses.';
COMMENT ON TABLE audit_logs IS 'Immutable security audit trail for user authentication and system actions.';
