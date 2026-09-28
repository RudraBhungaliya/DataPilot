-- Migration 0003: Add human action and checkpoint columns to collection_jobs table

ALTER TABLE collection_jobs ADD COLUMN IF NOT EXISTS source JSON;
ALTER TABLE collection_jobs ADD COLUMN IF NOT EXISTS current_step VARCHAR(64);
ALTER TABLE collection_jobs ADD COLUMN IF NOT EXISTS progress DOUBLE PRECISION DEFAULT 0.0 NOT NULL;
ALTER TABLE collection_jobs ADD COLUMN IF NOT EXISTS human_action_required BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE collection_jobs ADD COLUMN IF NOT EXISTS human_action_reason VARCHAR(128);
ALTER TABLE collection_jobs ADD COLUMN IF NOT EXISTS checkpoint JSON;
