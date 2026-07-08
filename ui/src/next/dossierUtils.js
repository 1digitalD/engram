import { narrativeSummary, sectionItems } from '../views/v5ThreadDetailUtils';

export function openCommitmentsFromDetail(detail) {
  return sectionItems(detail, 'open_tasks').map((item) => item.entity).filter(Boolean);
}

export function formatDossierDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date);
}

export function formatRelativeAge(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const diffMs = Date.now() - date.getTime();
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (days <= 0) return 'today';
  if (days === 1) return '1d';
  return `${days}d`;
}

export function briefStalenessLabel(generatedAt) {
  if (!generatedAt) return 'No brief yet';
  const date = new Date(generatedAt);
  if (Number.isNaN(date.getTime())) return 'Brief age unknown';
  const hours = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60));
  if (hours < 1) return 'as of just now';
  if (hours < 24) return `as of ${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `as of ${days}d ago`;
}

export function buildSpaceBrief(briefPayload, detail) {
  const spaceId = detail?.entity?.id;
  const brief = briefPayload?.brief;
  const taskIds = new Set(openCommitmentsFromDetail(detail).map((task) => task.id));

  const scopedItems = (brief?.items || []).filter(
    (item) => item.entity_id === spaceId || taskIds.has(item.entity_id),
  );

  let narrative = '';
  if (scopedItems.length > 0) {
    narrative = scopedItems.map((item) => `${item.title}: ${item.why_now}`).join(' ');
  } else {
    narrative = narrativeSummary(detail?.entity, '');
  }

  return {
    narrative,
    generatedAt: brief?.generated_at || null,
    model: brief?.model || null,
    items: scopedItems,
    fromCache: briefPayload?.from_cache ?? false,
  };
}

export function partitionCommitments(tasks, operatorPersonId) {
  const mine = [];
  const waitingOn = [];

  tasks.forEach((task) => {
    const ownerId = task.owner?.id || task.assigned_to?.id;
    if (ownerId && operatorPersonId && ownerId !== operatorPersonId) {
      waitingOn.push(task);
    } else if (task.status === 'waiting' || task.status === 'blocked') {
      waitingOn.push(task);
    } else {
      mine.push(task);
    }
  });

  return { mine, waitingOn };
}

export function openQuestionsFromSuggestions(suggestions, spaceId, taskIds) {
  return (suggestions || []).filter((suggestion) => {
    const payload = suggestion?.payload || {};
    const threadId = payload.thread_id;
    const targetId = payload.entity_id || payload.target_entity_id;
    const isSpaceScoped = threadId === spaceId || taskIds.has(targetId);
    if (!isSpaceScoped) return false;

    const kind = payload.kind || suggestion?.suggestion_type || '';
    const reason = (suggestion?.reason || '').toLowerCase();
    return (
      kind === 'attribution'
      || kind === 'question'
      || Boolean(payload.question)
      || reason.includes('who committed')
      || reason.includes('open question')
    );
  });
}

export function eventAmendDetail(event) {
  if (!event?.old_value || !event?.new_value) return null;
  if (event.reason !== 'amended' && event.event_type !== 'updated') return null;

  const keys = Object.keys(event.new_value);
  if (keys.length === 0) return null;

  return keys.map((key) => ({
    field: key,
    from: event.old_value[key],
    to: event.new_value[key],
  }));
}

export function formatTimelineStamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
