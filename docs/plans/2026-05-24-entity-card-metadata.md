# Entity Card Metadata Enhancement — Implementation Plan

> **For Hermes:** Use software-delivery skill to implement this plan.

**Goal:** Add dates (created_at, due_at, follow_up_at), tags, and relationship counts to entity card views in the Engram UI.

**Architecture:** React frontend only. The API already returns all needed fields in the entity DTO — no backend changes required.

**Tech Stack:** React 19, CSS Modules, Vitest

---

## Current State

**Entity list cards** (V4EntityList.jsx:128-146):
- Shows: title, content excerpt, status pill, optional priority pill
- Missing: created_at, due_at, follow_up_at, tags, relationship counts

**Linked entity rows** (V4EntityDetail.jsx → LinkedEntityRow):
- Shows: title, status, type (optional), relationship type, due_at, priority
- Missing: created_at, updated_at, follow_up_at, tags

**API response** (Entity.to_dict at models.py:320-343):
- Returns: id, type, title, content, status, lifecycle, due_at, follow_up_at, source, reference_url, properties, tags, ai, relationship_counts, created_at, updated_at
- All data is already available — just not displayed in card views

---

## Tasks

### T1: Add created_at and due_at to entity list cards

**Objective:** Show human-readable dates on entity list cards

**Files:**
- Modify: `ui/src/views/V4EntityList.jsx` (card rendering around lines 130-146)
- Modify: `ui/src/views/V4EntityScreens.module.css` (date display styles)

**Changes in V4EntityList.jsx:**

Add date formatting at the top of the component:

```javascript
function formatRelativeDate(iso) {
  if (!iso) return null;
  const now = new Date();
  const date = new Date(iso);
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function formatDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString();
}
```

Update card rendering to show dates:

```jsx
<li key={entity.id}>
  <Link to={detailPath(entity)}>
    <strong>{entity.title || 'Untitled'}</strong>
    <div className={styles.metaRow}>
      <span className={styles.mutedMeta}>{formatRelativeDate(entity.created_at)}</span>
      <span className={styles.statusPill}>{entity.status}</span>
      {entity.properties?.priority && (
        <span className={styles.priorityPill}>P{entity.properties.priority}</span>
      )}
      {entity.due_at && (
        <span className={styles.dueMeta}>Due {formatDate(entity.due_at)}</span>
      )}
    </div>
  </Link>
</li>
```

**CSS additions:**
```css
.mutedMeta {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.dueMeta {
  color: color-mix(in oklch, var(--yellow) 55%, var(--text-secondary));
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
}
```

**Verification:** Open any entity list — cards show creation date, due date when present.

---

### T2: Add tags to entity list cards

**Objective:** Show tags on entity list cards

**Files:**
- Modify: `ui/src/views/V4EntityList.jsx`
- Modify: `ui/src/views/V4EntityScreens.module.css`

**Changes in V4EntityList.jsx:**

Add tags after the metaRow:

```jsx
{entity.tags && entity.tags.length > 0 && (
  <div className={styles.tagStrip}>
    {entity.tags.slice(0, 3).map((tag) => (
      <span key={tag.id || tag.name} className={styles.tagPill}>{tag.name}</span>
    ))}
    {entity.tags.length > 3 && (
      <span className={styles.tagPillOverflow}>+{entity.tags.length - 3}</span>
    )}
  </div>
)}
```

**CSS additions:**
```css
.tagStrip {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.tagPill {
  background: color-mix(in oklch, var(--accent) 8%, var(--surface));
  border: 1px solid color-mix(in oklch, var(--accent) 18%, var(--border));
  border-radius: var(--radius-full);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
  padding: 2px 6px;
  white-space: nowrap;
}

.tagPillOverflow {
  background: color-mix(in oklch, var(--text-muted) 8%, var(--surface));
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
  padding: 2px 6px;
}
```

**Verification:** Cards with tags show up to 3 tag pills with "+N" overflow.

---

### T3: Add relationship count to entity list cards

**Objective:** Show relationship link count on cards

**Files:**
- Modify: `ui/src/views/V4EntityList.jsx`

**Changes:**

Add relationship count next to tags:

```jsx
{entity.relationship_counts && (
  <span className={styles.relCount}>
    {entity.relationship_counts.outgoing + entity.relationship_counts.incoming > 0 && (
      <>{entity.relationship_counts.outgoing + entity.relationship_counts.incoming} links</>
    )}
  </span>
)}
```

**CSS:**
```css
.relCount {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}
```

---

### T4: Update linked entity rows with metadata

**Objective:** Show created_at and tags on linked entity rows in detail view

**Files:**
- Modify: `ui/src/views/V4EntityDetail.jsx` (LinkedEntityRow component, lines 522-560)

**Changes in LinkedEntityRow:**

```jsx
function LinkedEntityRow({ item, onRemove, onQuickStatus, showType = false }) {
  return (
    <li>
      <Link to={pathForEntity(item.entity)}>
        <strong>{item.entity.title || 'Untitled'}</strong>
        <span className={styles.metaRow}>
          {showType && <span className={styles.typePill}>{item.entity.type}</span>}
          {item.entity.created_at && <span className={styles.mutedMeta}>{formatRelativeDate(item.entity.created_at)}</span>}
          <span className={styles.statusPill}>{item.entity.status}</span>
          <span className={styles.relationshipPill}>{item.relationship.relationship_type}</span>
        </span>
        {item.entity.due_at && <span className={styles.dueMeta}>Due {formatDate(item.entity.due_at)}</span>}
        {item.entity.properties?.priority && <span className={styles.priorityPill}>P{item.entity.properties.priority}</span>}
        {item.entity.tags && item.entity.tags.length > 0 && (
          <span className={styles.tagStrip}>
            {item.entity.tags.slice(0, 2).map((tag) => (
              <span key={tag.id || tag.name} className={styles.tagPill}>{tag.name}</span>
            ))}
            {item.entity.tags.length > 2 && <span className={styles.tagPillOverflow}>+{item.entity.tags.length - 2}</span>}
          </span>
        )}
      </Link>
      <div className={styles.cardActions}>
        {/* existing action buttons unchanged */}
      </div>
    </li>
  );
}
```

---

### T5: Update tests for new metadata display

**Objective:** Verify card metadata renders correctly

**Files:**
- Modify: `ui/src/views/V4EntityScreens.test.jsx`

**Changes:**

Add test cases:
1. Entity list card shows created_at, due_at, tags
2. Entity list card hides metadata when fields are null
3. Linked entity row shows created_at and tags (in existing detail test)

---

### T6: Run tests and fix regressions

**Objective:** All existing tests pass, new tests pass

**Run:** `cd ui && npm test`

---

## Task Graph

```
T1 → T2 → T3 (all V4EntityList.jsx, same file — serialize)
T4 (linked rows in V4EntityDetail.jsx — independent file, parallel with T1-T3)
T5 (test updates — after T1-T4)
T6 (test run — final)
```

**Note:** T1, T2, T3 all touch V4EntityList.jsx — must be serialized in order within one card. T4 touches a different file (V4EntityDetail.jsx) and can run in parallel.

Actually, since all changes to V4EntityList.jsx are small and interleaved, let me bundle T1+T2+T3 into one task and T4 into a parallel task.