function entityKey(entity) {
  if (!entity) return null;
  return entity.id || `${entity.type || 'entity'}:${entity.title || ''}`;
}

const HIGH_SIGNAL_NOTE_INTENTS = ['blocker', 'follow_up', 'delegation'];

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

export function getTodayUnscheduledAttentionEntities(today) {
  return dedupeEntities(today?.unscheduled_attention_tasks || []);
}

export function getTodayAttentionNotes(today) {
  return dedupeEntities(
    (today?.recent_notes || []).filter((entity) => HIGH_SIGNAL_NOTE_INTENTS.includes(entity?.ai?.intent)),
  );
}

export function getTodayActionItems(today) {
  const seen = new Set();
  const result = [];
  const buckets = [
    ['overdue_follow_up', today?.overdue_follow_ups || []],
    ['follow_up_today', today?.follow_ups || []],
    ['blocked', today?.blocked_tasks || []],
    ['waiting', today?.waiting_tasks || []],
    ['needs_attention', getTodayUnscheduledAttentionEntities(today)],
  ];

  for (const [reason, items] of buckets) {
    for (const entity of items) {
      const key = entityKey(entity);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      result.push({ entity, reason });
    }
  }

  return result;
}

export function getTodayDeadlinesAhead(today) {
  return dedupeEntities([
    ...(today?.upcoming_follow_ups || []),
    ...(today?.upcoming_due_tasks || []),
  ]);
}

export function getTodayAttentionCount(today) {
  return dedupeEntities([
    ...getTodayActionableEntities(today),
    ...getTodayStuckEntities(today),
    ...getTodayAttentionNotes(today),
    ...getTodayUnscheduledAttentionEntities(today),
  ]).length;
}

export function getTodayFocusItems(today, limit = 6) {
  const seen = new Set();
  const result = [];
  let order = 0;
  const buckets = [
    ['overdue', today?.overdue || []],
    ['due_today', today?.due_today || []],
    ['overdue_follow_up', today?.overdue_follow_ups || []],
    ['follow_up_today', today?.follow_ups || []],
    ['captured_blocker', getTodayAttentionNotes(today).filter((entity) => entity?.ai?.intent === 'blocker')],
    ['captured_follow_up', getTodayAttentionNotes(today).filter((entity) => entity?.ai?.intent === 'follow_up')],
    ['captured_delegation', getTodayAttentionNotes(today).filter((entity) => entity?.ai?.intent === 'delegation')],
  ];

  for (const [reason, items] of buckets) {
    for (const entity of items) {
      const key = entityKey(entity);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      result.push({ entity, reason, order });
      order += 1;
    }
  }

  return result
    .sort((a, b) => {
      const scoreDelta = (b.entity?.attention?.score || 0) - (a.entity?.attention?.score || 0);
      if (scoreDelta !== 0) return scoreDelta;
      return a.order - b.order;
    })
    .slice(0, limit)
    .map(({ entity, reason }) => ({ entity, reason }));
}
