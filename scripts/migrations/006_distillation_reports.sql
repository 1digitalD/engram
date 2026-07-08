-- Slice v6-10: distillation reports + ai_suggestions.report_id
-- Additive only: one new table + one nullable FK column + indexes/trigger.
-- Idempotent.

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

ALTER TABLE ai_suggestions
    ADD COLUMN IF NOT EXISTS report_id TEXT REFERENCES distillation_reports (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ai_suggestions_report_idx ON ai_suggestions (report_id);

CREATE OR REPLACE TRIGGER distillation_reports_updated_at
    BEFORE UPDATE ON distillation_reports
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
