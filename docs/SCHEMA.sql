-- Engram v4 clean-cutover PostgreSQL schema
-- Fresh database only. No backward compatibility. No migration.
-- Requires: PostgreSQL 16+, pgvector extension
-- Run: psql $DATABASE_URL -f docs/SCHEMA.sql

-- WARNING: truncate_all_tables() contains a safety guard that refuses to run on the 'engram' database.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE IF NOT EXISTS entities (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    type          TEXT NOT NULL CHECK (type IN (
                    'note', 'task', 'project', 'area', 'resource', 'person'
                  )),
    title         TEXT,
    content       TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    lifecycle     TEXT NOT NULL DEFAULT 'active'
                  CHECK (lifecycle IN ('active', 'archived', 'deleted')),
    due_at        TIMESTAMPTZ,
    follow_up_at  TIMESTAMPTZ,
    source        TEXT,
    reference_url TEXT,
    properties    JSONB NOT NULL DEFAULT '{}',
    ai_meta          JSONB NOT NULL DEFAULT '{}',
    ai_status        TEXT NOT NULL DEFAULT 'pending'
                     CHECK (ai_status IN ('pending', 'processing', 'done', 'failed', 'skipped')),
    ai_summary       TEXT,
    ai_summarized_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS entities_type_idx       ON entities (type);
CREATE INDEX IF NOT EXISTS entities_status_idx     ON entities (type, status);
CREATE INDEX IF NOT EXISTS entities_lifecycle_idx  ON entities (lifecycle);
CREATE INDEX IF NOT EXISTS entities_due_idx        ON entities (due_at)
    WHERE due_at IS NOT NULL AND lifecycle = 'active';
CREATE INDEX IF NOT EXISTS entities_follow_up_idx  ON entities (follow_up_at)
    WHERE follow_up_at IS NOT NULL AND lifecycle = 'active';
CREATE INDEX IF NOT EXISTS entities_updated_idx    ON entities (updated_at DESC);
CREATE INDEX IF NOT EXISTS entities_ai_status_idx     ON entities (ai_status)
    WHERE ai_status IN ('pending', 'failed');
CREATE INDEX IF NOT EXISTS entities_summarized_at_idx ON entities (ai_summarized_at DESC)
    WHERE ai_summarized_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS entity_links (
    id                 TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    source_entity_id   TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    target_entity_id   TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    relationship_type  TEXT NOT NULL DEFAULT 'related'
CHECK (relationship_type IN (
                            'parent', 'related', 'derived_from', 'mentions',
                            'assigned_to', 'references', 'blocks', 'activity_update'
                        )),
    source             TEXT NOT NULL DEFAULT 'manual',
    confidence         FLOAT,
    evidence           TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_entity_links_no_self_link CHECK (source_entity_id <> target_entity_id),
    CONSTRAINT uq_entity_links_source_target_type
        UNIQUE (source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS entity_links_source_idx ON entity_links (source_entity_id);
CREATE INDEX IF NOT EXISTS entity_links_target_idx ON entity_links (target_entity_id);
CREATE INDEX IF NOT EXISTS entity_links_type_idx   ON entity_links (relationship_type);
CREATE INDEX IF NOT EXISTS entity_links_ai_idx     ON entity_links (source, confidence)
    WHERE source IN ('ai', 'embedding');

CREATE TABLE IF NOT EXISTS tags (
    id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name       TEXT NOT NULL UNIQUE,
    color      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_tags (
    entity_id  TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    tag_id     TEXT NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, tag_id)
);

CREATE INDEX IF NOT EXISTS entity_tags_tag_idx ON entity_tags (tag_id);

CREATE TABLE IF NOT EXISTS entity_chunks (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    entity_id       TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL DEFAULT 0,
    chunk_text      TEXT NOT NULL,
    embedding       VECTOR(1536),
    embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS entity_chunks_entity_idx ON entity_chunks (entity_id);
CREATE INDEX IF NOT EXISTS entity_chunks_hnsw_idx
    ON entity_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS entity_events (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    entity_id   TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL CHECK (event_type IN (
                    'created', 'updated', 'status_changed', 'archived', 'deleted',
                    'relationship_added', 'relationship_updated', 'relationship_removed',
                    'tag_added', 'tag_removed', 'ai_processed', 'ai_updated', 'ai_summarized',
                    'suggestion_accepted', 'suggestion_dismissed', 'suggestion_expired',
                    'review_marked_resolved', 'activity_update_added', 'reverted',
                    'merged', 'merged_into', 'type_converted', 'decision_recorded'
                  )),
    actor       TEXT NOT NULL,
    old_value   JSONB,
    new_value   JSONB,
    confidence  FLOAT,
    reason      TEXT,
    source_note_id TEXT REFERENCES entities (id) ON DELETE SET NULL,
    reverted_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS entity_events_entity_idx
    ON entity_events (entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS entity_events_occurred_at_idx
    ON entity_events (created_at DESC);
CREATE INDEX IF NOT EXISTS entity_events_type_idx
    ON entity_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS entity_events_actor_idx
    ON entity_events (actor)
    WHERE actor LIKE 'agent:%';
CREATE INDEX IF NOT EXISTS entity_events_source_note_idx
    ON entity_events (source_note_id, created_at ASC)
    WHERE source_note_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS distillation_reports (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    source_note_id TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'reviewed', 'partial', 'superseded')),
    narrative      JSONB NOT NULL DEFAULT '{}',
    stats          JSONB NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS distillation_reports_source_idx ON distillation_reports (source_note_id);
CREATE INDEX IF NOT EXISTS distillation_reports_status_idx ON distillation_reports (status);

CREATE TABLE IF NOT EXISTS ai_suggestions (
    id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    source_entity_id  TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    report_id         TEXT REFERENCES distillation_reports (id) ON DELETE SET NULL,
    suggestion_type   TEXT NOT NULL,
    operation_type    TEXT NOT NULL,
    payload           JSONB NOT NULL DEFAULT '{}',
    confidence        FLOAT,
    reason            TEXT,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'accepted', 'dismissed', 'edited', 'expired')),
    resolved_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_suggestions_status_idx ON ai_suggestions (status);
CREATE INDEX IF NOT EXISTS ai_suggestions_source_idx ON ai_suggestions (source_entity_id);
CREATE INDEX IF NOT EXISTS ai_suggestions_report_idx ON ai_suggestions (report_id);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    job_type     TEXT NOT NULL,
    entity_id    TEXT REFERENCES entities (id) ON DELETE CASCADE,
    payload      JSONB NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'running', 'done', 'failed')),
    attempts     INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    error        TEXT,
    run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS jobs_pending_idx
    ON jobs (run_after, job_type)
    WHERE status IN ('pending', 'failed') AND attempts < max_attempts;
CREATE INDEX IF NOT EXISTS jobs_entity_idx ON jobs (entity_id);

CREATE TABLE IF NOT EXISTS change_batches (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    source_note_id TEXT REFERENCES entities (id) ON DELETE SET NULL,
    actor          TEXT NOT NULL,
    source         TEXT NOT NULL DEFAULT 'ai',
    summary        TEXT,
    applied_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    undone_at      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS change_batches_source_note_idx ON change_batches (source_note_id);
CREATE INDEX IF NOT EXISTS change_batches_applied_at_idx  ON change_batches (applied_at DESC);

ALTER TABLE entity_events
    ADD COLUMN IF NOT EXISTS change_batch_id TEXT REFERENCES change_batches (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS entity_events_change_batch_idx
    ON entity_events (change_batch_id)
    WHERE change_batch_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisions (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    thread_id      TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    statement      TEXT NOT NULL,
    context        TEXT,
    decided_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by     TEXT NOT NULL,
    source_note_id TEXT REFERENCES entities (id) ON DELETE SET NULL,
    superseded_by  TEXT REFERENCES decisions (id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS decisions_thread_idx      ON decisions (thread_id, decided_at DESC);
CREATE INDEX IF NOT EXISTS decisions_source_note_idx ON decisions (source_note_id);
CREATE INDEX IF NOT EXISTS decisions_superseded_idx  ON decisions (superseded_by);

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

CREATE OR REPLACE TRIGGER entity_links_updated_at
    BEFORE UPDATE ON entity_links
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER tags_updated_at
    BEFORE UPDATE ON tags
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER ai_suggestions_updated_at
    BEFORE UPDATE ON ai_suggestions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER distillation_reports_updated_at
    BEFORE UPDATE ON distillation_reports
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER decisions_updated_at
    BEFORE UPDATE ON decisions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION truncate_all_tables()
RETURNS VOID AS $$
BEGIN
    -- Safety guard: truncate_all_tables() is a test-isolation tool.
    -- It MUST NOT run against the production 'engram' database.
    -- This check is a last-resort failsafe; the real protection is
    -- TEST_DATABASE_URL pointing to an isolated test instance.
    IF current_database() = 'engram' THEN
        RAISE EXCEPTION 'FATAL: truncate_all_tables() refused on production database "engram". This function is for test isolation only.';
    END IF;

    -- Bounded lock wait so a leaked connection or concurrent worker cannot
    -- cause the test runner to hang indefinitely. The caller retries on timeout.
    SET LOCAL statement_timeout = '5s';

TRUNCATE TABLE
    ai_suggestions,
    app_settings,
    change_batches,
    decisions,
    distillation_reports,
    entity_events,
    entity_chunks,
    entity_links,
        entity_tags,
        jobs,
        tags,
        entities
    RESTART IDENTITY CASCADE;
END;
$$ LANGUAGE plpgsql;
