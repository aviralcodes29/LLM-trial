-- DocChat AI — Supabase PostgreSQL Schema
-- Run once against your Supabase project via the SQL Editor or psql.
-- Tables: users, usage_records, user_documents

-- ─────────────────────────────────────────────────────────────────
-- 1. users
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    username         VARCHAR(100)  NOT NULL UNIQUE,
    email            VARCHAR(100) UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users (email);


-- ─────────────────────────────────────────────────────────────────
-- 2. usage_records
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_records (
    id                 SERIAL PRIMARY KEY,
    user_id            INTEGER REFERENCES users(id) ON DELETE SET NULL,
    endpoint           VARCHAR(100) NOT NULL,
    model              VARCHAR(100) NOT NULL,
    prompt_tokens      INTEGER      NOT NULL DEFAULT 0,
    completion_tokens  INTEGER      NOT NULL DEFAULT 0,
    total_tokens       INTEGER      NOT NULL DEFAULT 0,
    estimated_cost     NUMERIC(12, 6) NOT NULL DEFAULT 0.0,
    timestamp          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_user_id   ON usage_records (user_id);
CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_records (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_usage_endpoint  ON usage_records (endpoint);


-- ─────────────────────────────────────────────────────────────────
-- 3. user_documents
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_documents (
    id           SERIAL PRIMARY KEY,
    doc_id       VARCHAR(64)  NOT NULL UNIQUE,
    user_id      INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename     VARCHAR(255) NOT NULL,
    chunks_count INTEGER      NOT NULL DEFAULT 0,
    file_type    VARCHAR(20),
    upload_time  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_docs_doc_id  ON user_documents (doc_id);
CREATE INDEX IF NOT EXISTS idx_user_docs_user_id ON user_documents (user_id);
