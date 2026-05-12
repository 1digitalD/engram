-- Engram v2 — PostgreSQL Schema
-- Requires: PostgreSQL 16+, pgvector extension
-- Run: psql $DATABASE_URL -f docs/SCHEMA.sql

-- ─── Extensions ──────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector

-- ─── Tags ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tags (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name       TEXT NOT NULL,
    color      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name)
);

-- ─── Entities (single-table inheritance) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS entities (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,

    -- Discriminator
    type          TEXT NOT NULL CHECK (type IN (
                    'note', 'task', 'project', 'area', 'resource', 'person'
                  )),

    -- Universal base fields
    title         TEXT,
    content       TEXT,

    -- Lifecycle: cross-cutting operational/existence state
    status        TEXT NOT NULL DEFAULT 'active',
    lifecycle     TEXT NOT NULL DEFAULT 'active'
                  CHECK (lifecycle IN ('active', 'paused', 'done', 'archived', 'deleted')),

    follow_up_at  TIMESTAMPTZ,
    source        TEXT,          -- 'manual' | 'ai' | 'web' | 'file' | 'mcp' | 'api'
    reference_url TEXT,

    -- Type-specific fields (queryable via generated columns below)
    properties    JSONB NOT NULL DEFAULT '{}',

    -- AI metadata and processing state
    ai_meta       JSONB NOT NULL DEFAULT '{}',
    ai_status     TEXT NOT NULL DEFAULT 'pending'
                  CHECK (ai_status IN ('pending', 'processing', 'done', 'failed', 'skipped')),

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Generated columns for common type-specific fields (indexed separately below)
ALTER TABLE entities
    ADD COLUMN IF NOT EXISTS priority  TEXT
        GENERATED ALWAYS AS (properties->>'priority') STORED,
    ADD COLUMN IF NOT EXISTS due_date  TEXT
        GENERATED ALWAYS AS (properties->>'due_date') STORED,
    ADD COLUMN IF NOT EXISTS bucket    TEXT
        GENERATED ALWAYS AS (properties->>'bucket') STORED;

-- Full-text search (covers title + content, title weighted higher)
ALTER TABLE entities
    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(content, '')), 'B')
        ) STORED;

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS entities_type_idx       ON entities (type);
CREATE INDEX IF NOT EXISTS entities_lifecycle_idx  ON entities (lifecycle);
CREATE INDEX IF NOT EXISTS entities_status_idx     ON entities (type, status);
CREATE INDEX IF NOT EXISTS entities_updated_idx    ON entities (updated_at DESC);
CREATE INDEX IF NOT EXISTS entities_fts_idx        ON entities USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS entities_ai_status_idx  ON entities (ai_status)
    WHERE ai_status IN ('pending', 'failed');

-- Type-specific indexes
CREATE INDEX IF NOT EXISTS entities_priority_idx   ON entities (priority)
    WHERE type = 'task' AND lifecycle = 'active';
CREATE INDEX IF NOT EXISTS entities_due_date_idx   ON entities (due_date)
    WHERE type = 'task' AND due_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS entities_bucket_idx     ON entities (bucket)
    WHERE type = 'note';
CREATE INDEX IF NOT EXISTS entities_follow_up_idx  ON entities (follow_up_at)
    WHERE follow_up_at IS NOT NULL AND lifecycle = 'active';

-- ─── Entity Tags (universal — replaces note_tags + resource_tags) ─────────────

CREATE TABLE IF NOT EXISTS entity_tags (
    entity_id  TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    tag_id     TEXT NOT NULL REFERENCES tags (id)     ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, tag_id)
);

CREATE INDEX IF NOT EXISTS entity_tags_tag_idx ON entity_tags (tag_id);

-- ─── Entity Links (universal relationship graph) ──────────────────────────────

CREATE TABLE IF NOT EXISTS entity_links (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    src_id      TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    dst_id      TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,

    -- Semantic relationship type
    -- 'related' | 'parent' | 'references' | 'blocks' | 'mentions'
    -- 'derived_from' | 'assigned_to'
    link_type   TEXT NOT NULL DEFAULT 'related',

    weight      FLOAT NOT NULL DEFAULT 1.0,
    source      TEXT  NOT NULL DEFAULT 'manual',
    -- 'manual' | 'ai' | 'system' | 'embedding'

    confidence  FLOAT,   -- populated for ai/embedding sources
    evidence    TEXT,    -- AI reasoning or human note

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (src_id, dst_id, link_type),
    CHECK  (src_id <> dst_id)
);

CREATE INDEX IF NOT EXISTS entity_links_src_idx  ON entity_links (src_id);
CREATE INDEX IF NOT EXISTS entity_links_dst_idx  ON entity_links (dst_id);
CREATE INDEX IF NOT EXISTS entity_links_type_idx ON entity_links (link_type);
CREATE INDEX IF NOT EXISTS entity_links_ai_idx   ON entity_links (source, confidence)
    WHERE source IN ('ai', 'embedding');

-- ─── Entity Chunks (embeddings for any entity) ────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_chunks (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    entity_id       TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    chunk_index     INT  NOT NULL DEFAULT 0,
    chunk_text      TEXT NOT NULL,
    embedding       VECTOR(1536),
    embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (entity_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS entity_chunks_entity_idx ON entity_chunks (entity_id);

-- HNSW index for fast approximate nearest-neighbor search
-- m=16, ef_construction=64 are good defaults for 1536-dim embeddings
CREATE INDEX IF NOT EXISTS entity_chunks_hnsw_idx
    ON entity_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ─── Entity Events (audit log + lifecycle history) ────────────────────────────

CREATE TABLE IF NOT EXISTS entity_events (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    entity_id   TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,

    -- Event type
    -- 'created' | 'status_changed' | 'field_updated' | 'lifecycle_changed'
    -- 'link_added' | 'link_removed'
    -- 'ai_classified' | 'ai_extracted' | 'ai_correction'
    -- 'archived' | 'deleted'
    event_type  TEXT NOT NULL,

    -- Who or what caused this event
    -- 'user' | 'agent:ingest' | 'agent:classify' | 'agent:autolink' | 'system'
    actor       TEXT NOT NULL,

    old_value   JSONB,   -- previous state (for diffs)
    new_value   JSONB,   -- new state

    confidence  FLOAT,   -- populated for AI-originated events
    reason      TEXT,    -- AI reasoning or human annotation

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS entity_events_entity_idx
    ON entity_events (entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS entity_events_type_idx
    ON entity_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS entity_events_actor_idx
    ON entity_events (actor)
    WHERE actor LIKE 'agent:%';

-- ─── Background Jobs ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,

    -- Job type: 'classify' | 'embed' | 'autolink' | 'extract'
    job_type     TEXT NOT NULL,

    entity_id    TEXT REFERENCES entities (id) ON DELETE CASCADE,
    payload      JSONB NOT NULL DEFAULT '{}',

    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'running', 'done', 'failed')),

    attempts     INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    error        TEXT,

    -- Worker will not pick up job before this time (enables backoff)
    run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Primary worker polling index
CREATE INDEX IF NOT EXISTS jobs_pending_idx
    ON jobs (run_after, job_type)
    WHERE status IN ('pending', 'failed') AND attempts < max_attempts;

CREATE INDEX IF NOT EXISTS jobs_entity_idx ON jobs (entity_id);

-- ─── Link Proposals (AI-suggested links for human review) ─────────────────────

CREATE TABLE IF NOT EXISTS link_proposals (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    src_id      TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    dst_id      TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    link_type   TEXT NOT NULL DEFAULT 'related',
    confidence  FLOAT,
    evidence    TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS link_proposals_status_idx ON link_proposals (status);
CREATE INDEX IF NOT EXISTS link_proposals_src_idx    ON link_proposals (src_id);
CREATE INDEX IF NOT EXISTS link_proposals_dst_idx    ON link_proposals (dst_id);

-- ─── Summaries (layered entity summaries) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS summaries (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    entity_id   TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    granularity TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS summaries_entity_idx ON summaries (entity_id);

-- ─── Updated_at triggers ──────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER tags_updated_at
    BEFORE UPDATE ON tags
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER summaries_updated_at
    BEFORE UPDATE ON summaries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── Test database reset helper ───────────────────────────────────────────────
-- Used by test suite to reset state between test runs.
-- Call: SELECT truncate_all_tables();

CREATE OR REPLACE FUNCTION truncate_all_tables()
RETURNS VOID AS $$
BEGIN
    TRUNCATE TABLE
        summaries,
        link_proposals,
        entity_events,
        entity_chunks,
        entity_links,
        entity_tags,
        jobs,
        entities,
        tags
    RESTART IDENTITY CASCADE;
END;
$$ LANGUAGE plpgsql;
