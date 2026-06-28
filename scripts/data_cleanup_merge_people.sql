-- Tier 2 followup: merge duplicate people entities
--
-- Three duplicate pairs identified by:
--   docker exec engram-postgres-1 psql ... (see session notes 2026-06-27)
--
-- For each pair, we:
--   1. Migrate unique links from drop_id to keep_id (preserving relationship_type)
--   2. Delete duplicate links that already exist on keep_id
--   3. Soft-delete the drop entity (lifecycle='deleted', write entity_event)
--   4. Add a 'merged_into' link from drop to keep for audit trail

BEGIN;

-- 1. Migrate unique links: Akash (7583bf17) → Akash Mandole (e4897721)
--    Drop has 2 unique links: assigned_to from 879336ca and activity_update from 1fd3f6d8
INSERT INTO entity_links (source_entity_id, target_entity_id, relationship_type, source, confidence, created_at, updated_at)
SELECT
  source_entity_id,
  'e4897721-447d-4d6d-be65-9812f08740f8',
  relationship_type,
  source,
  confidence,
  NOW(),
  NOW()
FROM entity_links
WHERE target_entity_id = '7583bf17-be4d-4a24-8feb-b4e3e6ba682e'
  AND relationship_type IN ('assigned_to', 'activity_update')
ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING;

-- 2. Migrate unique link: Priya (a86846a6) → Priya Luthra (2823f457)
INSERT INTO entity_links (source_entity_id, target_entity_id, relationship_type, source, confidence, created_at, updated_at)
SELECT
  source_entity_id,
  '2823f457-c1a1-4d5c-b70b-e6d86176badc',
  relationship_type,
  source,
  confidence,
  NOW(),
  NOW()
FROM entity_links
WHERE target_entity_id = 'a86846a6-7f32-4f03-8c48-e1ba170da85a'
ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING;

-- 3. Migrate unique link: Rohit Behbav (e8275d18) → Rohit (4f3652c4)
INSERT INTO entity_links (source_entity_id, target_entity_id, relationship_type, source, confidence, created_at, updated_at)
SELECT
  source_entity_id,
  '4f3652c4-5fbd-463f-844a-828a98aafdc1',
  relationship_type,
  source,
  confidence,
  NOW(),
  NOW()
FROM entity_links
WHERE target_entity_id = 'e8275d18-dccf-4775-acc0-cbb09fa088d7'
ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING;

-- 4. Delete all links from the drop entities (their content has been migrated above)
DELETE FROM entity_links WHERE target_entity_id IN (
  '7583bf17-be4d-4a24-8feb-b4e3e6ba682e',
  'a86846a6-7f32-4f03-8c48-e1ba170da85a',
  'e8275d18-dccf-4775-acc0-cbb09fa088d7'
);

-- 5. Soft-delete the drop entities
UPDATE entities
SET lifecycle = 'deleted',
    updated_at = NOW()
WHERE id IN (
  '7583bf17-be4d-4a24-8feb-b4e3e6ba682e',
  'a86846a6-7f32-4f03-8c48-e1ba170da85a',
  'e8275d18-dccf-4775-acc0-cbb09fa088d7'
);

-- 6. Write entity_event records for audit trail
INSERT INTO entity_events (entity_id, event_type, actor, reason, new_value, created_at)
VALUES
  ('7583bf17-be4d-4a24-8feb-b4e3e6ba682e', 'merged_into', 'human:cleanup', 'tier-2 cleanup: duplicate of Akash Mandole', '{"merged_into_id": "e4897721-447d-4d6d-be65-9812f08740f8"}'::jsonb, NOW()),
  ('a86846a6-7f32-4f03-8c48-e1ba170da85a', 'merged_into', 'human:cleanup', 'tier-2 cleanup: duplicate of Priya Luthra', '{"merged_into_id": "2823f457-c1a1-4d5c-b70b-e6d86176badc"}'::jsonb, NOW()),
  ('e8275d18-dccf-4775-acc0-cbb09fa088d7', 'merged_into', 'human:cleanup', 'tier-2 cleanup: duplicate of Rohit', '{"merged_into_id": "4f3652c4-5fbd-463f-844a-828a98aafdc1"}'::jsonb, NOW());

-- Verify
SELECT 'after-merge' AS step, COUNT(*) AS people_active
FROM entities WHERE type = 'person' AND lifecycle = 'active';

COMMIT;