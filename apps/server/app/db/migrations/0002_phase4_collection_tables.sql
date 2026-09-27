-- Migration 0002: Phase 4 Source Collection Engine Tables
-- Creates tables for sources, collection_jobs, and documents with required indexes.

CREATE TABLE IF NOT EXISTS sources (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    base_url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    capabilities JSON NOT NULL DEFAULT '[]'::json,
    access_method VARCHAR(50) NOT NULL DEFAULT 'api',
    rate_limit JSON NOT NULL DEFAULT '{"requests": 60, "period_seconds": 60}'::json,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources (domain);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources (status);

CREATE TABLE IF NOT EXISTS collection_jobs (
    id VARCHAR(100) PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL,
    workflow_id VARCHAR(100) NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMP WITH TIME ZONE NULL,
    completed_at TIMESTAMP WITH TIME ZONE NULL,
    metadata JSON NOT NULL DEFAULT '{}'::json,
    error TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_collection_jobs_request_id ON collection_jobs (request_id);
CREATE INDEX IF NOT EXISTS idx_collection_jobs_workflow_id ON collection_jobs (workflow_id);
CREATE INDEX IF NOT EXISTS idx_collection_jobs_status ON collection_jobs (status);

CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(100) PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    content_type VARCHAR(100) NOT NULL DEFAULT 'text/html',
    content TEXT NOT NULL,
    content_hash VARCHAR(128) NOT NULL,
    status_code INTEGER NOT NULL DEFAULT 200,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    metadata JSON NOT NULL DEFAULT '{}'::json,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_job_id ON documents (job_id);
CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents (source_id);
CREATE INDEX IF NOT EXISTS idx_documents_canonical_url ON documents (canonical_url);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents (content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_collected_at ON documents (collected_at);
