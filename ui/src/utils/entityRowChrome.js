export function entityTypeAccent(type) {
  if (!type) return '';
  return `entity-${type}`;
}

export function statusPillVariant(status) {
  if (!status) return 'neutral';
  if (status === 'blocked') return 'blocked';
  if (status === 'waiting') return 'waiting';
  if (status === 'done' || status === 'cancelled' || status === 'archived') return 'done';
  if (status === 'in_progress') return 'active';
  return 'neutral';
}

export function dueUrgencyClass(entity) {
  if (entity?.type !== 'task') return '';
  const dueAt = entity.due_at ? new Date(entity.due_at) : null;
  if (!dueAt || Number.isNaN(dueAt.getTime())) return '';

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dueDay = new Date(dueAt);
  dueDay.setHours(0, 0, 0, 0);

  if (dueDay < today) return 'dueOverdue';
  if (dueDay.getTime() === today.getTime()) return 'dueToday';
  return '';
}
