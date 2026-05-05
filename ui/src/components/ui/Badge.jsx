import React from 'react';
import styles from './Badge.module.css';

const BUCKET_LABELS = {
  INBOX:    'Inbox',
  PROJECTS: 'Projects',
  AREAS:    'Areas',
  RESOURCES:'Resources',
  ARCHIVES: 'Archives',
};

export function BucketBadge({ bucket }) {
  if (!bucket) return null;
  return (
    <span className={`${styles.badge} ${styles[`bucket${bucket.charAt(0) + bucket.slice(1).toLowerCase()}`] || styles.default}`}>
      {BUCKET_LABELS[bucket] || bucket}
    </span>
  );
}

export function TagBadge({ tag, onRemove }) {
  return (
    <span className={styles.tag}>
      #{typeof tag === 'string' ? tag : tag.name}
      {onRemove && (
        <button onClick={() => onRemove(tag)} className={styles.tagRemove}>
          ×
        </button>
      )}
    </span>
  );
}

export function StatusBadge({ status }) {
  const map = {
    open:        { label: 'Open',   cls: styles.open },
    'in-progress':{ label: 'In Progress', cls: styles.inProgress },
    done:        { label: 'Done',   cls: styles.done },
    archived:   { label: 'Archived', cls: styles.archived },
  };
  const s = map[status] || { label: status, cls: styles.default };
  return <span className={`${styles.statusBadge} ${s.cls}`}>{s.label}</span>;
}

export function PriorityBadge({ priority }) {
  const cls = priority === 'HIGH' ? styles.priorityHigh
    : priority === 'LOW' ? styles.priorityLow
    : styles.priorityMed;
  return <span className={`${styles.priorityBadge} ${cls}`}>{priority || 'MEDIUM'}</span>;
}
