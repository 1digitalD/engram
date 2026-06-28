-- Tier 2 followup: archive obvious-noise tasks (status remarks, vague meeting outcomes)
--
-- Targets 12 tasks that are clearly one-off status remarks, NOT real commitments:
--   - 9 from the 'status_remark' bucket (titles start with check/share/discuss/ask)
--   - 2 ai_suggestion tasks with empty content or vague ephemeral content
--   - "Identify next task for Priya" - meta-task about planning, no content
--
-- Conservative: only deletes tasks with NO incoming entity_links (verified beforehand
-- with the diagnostic query). Safe to soft-delete.

BEGIN;

-- List all tasks to archive
WITH doomed AS (
  SELECT id FROM entities
  WHERE type = 'task' AND lifecycle = 'active' AND status IN ('open', 'in_progress')
    AND (
      title = 'Ask reviewers for written feedback'
      OR title = 'Check due date'
      OR title = 'Check HITL delivery status'
      OR title = 'Check Jira visibility'
      OR title = 'Check responsive-design delivery status'
      OR title = 'Discuss design alternatives with Lexi and Priya'
      OR title = 'Discuss promotion path'
      OR title = 'Discuss promotion path with Sarosh'
      OR title = 'Discuss stop stream design learnings'
      OR title = 'Identify next task for Priya'
      OR title = 'Share recipe-skill examples'
      OR title = 'Share slipped bug update'
    )
)
-- First delete outgoing entity_links (these tasks point AT other entities)
DELETE FROM entity_links
WHERE source_entity_id IN (SELECT id FROM doomed);

-- Then soft-delete the task entities
UPDATE entities
SET lifecycle = 'deleted',
    updated_at = NOW()
WHERE id IN (
  SELECT id FROM entities
  WHERE type = 'task' AND lifecycle = 'active' AND status IN ('open', 'in_progress')
    AND (
      title = 'Ask reviewers for written feedback'
      OR title = 'Check due date'
      OR title = 'Check HITL delivery status'
      OR title = 'Check Jira visibility'
      OR title = 'Check responsive-design delivery status'
      OR title = 'Discuss design alternatives with Lexi and Priya'
      OR title = 'Discuss promotion path'
      OR title = 'Discuss promotion path with Sarosh'
      OR title = 'Discuss stop stream design learnings'
      OR title = 'Identify next task for Priya'
      OR title = 'Share recipe-skill examples'
      OR title = 'Share slipped bug update'
    )
);

-- Write audit events
INSERT INTO entity_events (entity_id, event_type, actor, reason, created_at)
SELECT id, 'archived', 'human:cleanup', 'tier-2 followup: status-remark task, no incoming links, no real commitment', NOW()
FROM entities
WHERE type = 'task' AND lifecycle = 'deleted'
  AND updated_at > NOW() - INTERVAL '5 seconds'
  AND title IN (
    'Ask reviewers for written feedback',
    'Check due date',
    'Check HITL delivery status',
    'Check Jira visibility',
    'Check responsive-design delivery status',
    'Discuss design alternatives with Lexi and Priya',
    'Discuss promotion path',
    'Discuss promotion path with Sarosh',
    'Discuss stop stream design learnings',
    'Identify next task for Priya',
    'Share recipe-skill examples',
    'Share slipped bug update'
  );

-- Verify
SELECT 'after-cleanup' AS step,
       COUNT(*) FILTER (WHERE type = 'task' AND lifecycle = 'active') AS active_tasks,
       COUNT(*) FILTER (WHERE type = 'task' AND lifecycle = 'active' AND status IN ('open', 'in_progress')) AS open_or_in_progress,
       COUNT(*) FILTER (WHERE type = 'task' AND lifecycle = 'deleted' AND updated_at > NOW() - INTERVAL '1 hour') AS recently_archived
FROM entities WHERE type = 'task';

COMMIT;