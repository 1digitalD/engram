export const DEFAULT_OPEN_STATUSES = ['open', 'in_progress', 'waiting', 'blocked'];

export const STATUS_FILTER_OPTIONS = [
  { key: 'open', label: 'Open' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'waiting', label: 'Waiting' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'done', label: 'Done' },
  { key: 'cancelled', label: 'Cancelled' },
];

export const DATE_PRESET_OPTIONS = [
  { key: 'any', label: 'Any' },
  { key: 'overdue', label: 'Overdue' },
  { key: 'this_week', label: 'This week' },
  { key: 'next_30', label: 'Next 30 days' },
];

export const SORT_OPTIONS = [
  { key: 'created_at', label: 'Created' },
  { key: 'follow_up_at', label: 'Follow-up' },
];

export const ORDER_OPTIONS = [
  { key: 'desc', label: 'Newest first' },
  { key: 'asc', label: 'Oldest first' },
];

export function localDateString(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function isoDate(date) {
  return localDateString(date);
}

function startOfToday() {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  return date;
}

function endOfWeek(from) {
  const date = new Date(from);
  const day = date.getDay();
  const daysUntilSunday = day === 0 ? 0 : 7 - day;
  date.setDate(date.getDate() + daysUntilSunday);
  return date;
}

export function datePresetParams(preset, fieldPrefix) {
  if (!preset || preset === 'any') return {};

  const today = startOfToday();
  const beforeKey = `${fieldPrefix}_before`;
  const afterKey = `${fieldPrefix}_after`;

  if (preset === 'overdue') {
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    return { [beforeKey]: isoDate(yesterday) };
  }

  if (preset === 'this_week') {
    return {
      [afterKey]: isoDate(today),
      [beforeKey]: isoDate(endOfWeek(today)),
    };
  }

  if (preset === 'next_30') {
    const horizon = new Date(today);
    horizon.setDate(horizon.getDate() + 30);
    return {
      [afterKey]: isoDate(today),
      [beforeKey]: isoDate(horizon),
    };
  }

  return {};
}

export function buildTaskBoardParams({
  statuses,
  assignee,
  duePreset,
  followUpPreset,
  sort,
  order,
}) {
  const params = {
    sort,
    order,
  };

  if (statuses?.length) {
    params.status = statuses.join(',');
  }
  if (assignee) {
    params.assignee = assignee;
  }

  return {
    ...params,
    ...datePresetParams(duePreset, 'due'),
    ...datePresetParams(followUpPreset, 'follow_up'),
  };
}

export function defaultOrderForSort(sort) {
  return sort === 'follow_up_at' ? 'asc' : 'desc';
}
