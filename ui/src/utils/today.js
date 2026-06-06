function entityKey(entity) {
  if (!entity) return null;
  return entity.id || `${entity.type || 'entity'}:${entity.title || ''}`;
}

function dedupeEntities(items) {
  const seen = new Set();
  const result = [];
  for (const entity of items || []) {
    const key = entityKey(entity);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push(entity);
  }
  return result;
}

export function getTodayActionableEntities(today) {
  return dedupeEntities([
    ...(today?.overdue || []),
    ...(today?.due_today || []),
    ...(today?.overdue_follow_ups || []),
    ...(today?.follow_ups || []),
  ]);
}

export function getTodayOverdueEntities(today) {
  return dedupeEntities([
    ...(today?.overdue || []),
    ...(today?.overdue_follow_ups || []),
  ]);
}

export function getTodayDueNowEntities(today) {
  return dedupeEntities([
    ...(today?.due_today || []),
    ...(today?.follow_ups || []),
  ]);
}

export function getTodayStuckEntities(today) {
  return dedupeEntities([
    ...(today?.blocked_tasks || []),
    ...(today?.waiting_tasks || []),
  ]);
}

export function getTodayAttentionCount(today) {
  return dedupeEntities([
    ...getTodayActionableEntities(today),
    ...getTodayStuckEntities(today),
  ]).length;
}

export function getTodayFocusItems(today, limit = 6) {
  const seen = new Set();
  const result = [];
  const buckets = [
    ['overdue', today?.overdue || []],
    ['due_today', today?.due_today || []],
    ['overdue_follow_up', today?.overdue_follow_ups || []],
    ['follow_up_today', today?.follow_ups || []],
  ];

  for (const [reason, items] of buckets) {
    for (const entity of items) {
      const key = entityKey(entity);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      result.push({ entity, reason });
      if (result.length >= limit) return result;
    }
  }

  return result;
}
