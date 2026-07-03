const LINK_PARTS = [
  { key: 'tasks', one: 'task', other: 'tasks' },
  { key: 'projects', one: 'project', other: 'projects' },
  { key: 'notes', one: 'note', other: 'notes' },
];

function countLabel(count, one, other) {
  if (!count) return null;
  return `${count} ${count === 1 ? one : other}`;
}

export function formatProjectOpenBadge(taskCounts) {
  const open = taskCounts?.open ?? 0;
  if (open <= 0) return null;
  return `${open} open`;
}

export function formatLinkedCountsSummary(linkedCounts) {
  if (!linkedCounts) return null;
  const parts = LINK_PARTS
    .map(({ key, one, other }) => countLabel(linkedCounts[key] ?? 0, one, other))
    .filter(Boolean);
  return parts.length ? parts.join(' · ') : null;
}

export function listRowSecondaryMeta(entity, type) {
  if (type === 'project') {
    return formatProjectOpenBadge(entity.task_counts);
  }
  if (type === 'area' || type === 'person') {
    return formatLinkedCountsSummary(entity.linked_counts);
  }
  return null;
}
