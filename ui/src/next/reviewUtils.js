import { itemEvidence, itemTitle, proposalLabel } from './vocab';
import { recallEntityPath } from './recallUtils';

export const DISMISS_REASONS = [
  'not a task',
  'not mine',
  'duplicate',
  'wrong target',
  'other',
];

export const CREATE_ENTITY_TYPES = [
  { value: 'task', label: 'Commitment' },
  { value: 'project', label: 'Space (project)' },
  { value: 'area', label: 'Space (area)' },
];

export const UPDATE_STATUS_OPTIONS = ['open', 'in_progress', 'waiting', 'done', 'blocked'];

/** Narrative items that map to pending AiSuggestions (resolveable). */
export function isResolvableItem(item) {
  if (!item?.id) return false;
  if (item.kind === 'routing_summary') return false;
  if (item.event_id) return false;
  return true;
}

export function isAppliedItem(item) {
  return Boolean(item?.event_id);
}

export function pendingSuggestionIds(suggestions = []) {
  return suggestions.filter((row) => row.status === 'pending').map((row) => row.id);
}

export function suggestionById(suggestions, id) {
  return (suggestions || []).find((row) => row.id === id) || null;
}

export function displayItemMeta(item, suggestions) {
  const linked = suggestionById(suggestions, item?.id);
  return {
    title: itemTitle(item),
    evidence: itemEvidence(item),
    typeLabel: linked ? proposalLabel(linked) : (item?.kind || 'Applied'),
    resolvable: isResolvableItem(item) && linked?.status === 'pending',
    suggestion: linked,
  };
}

export function countPendingInReport(suggestions = []) {
  return suggestions.filter((row) => row.status === 'pending').length;
}

export function reportQueueTitle(row) {
  if (row?.source_note_title) return row.source_note_title;
  return `Report ${String(row?.id || '').slice(0, 8)}`;
}

export function reportStatusLabel(row) {
  const pending = row?.pending_suggestion_count ?? 0;
  const status = row?.status || 'pending';
  if (pending > 0) {
    return pending === 1 ? '1 proposal' : `${pending} proposals`;
  }
  if (status === 'partial') return 'In progress';
  if (status === 'pending') return 'Applied only';
  return status;
}

export function initialProposalEditState(item, suggestion) {
  const payload = suggestion?.payload || item?.payload || {};
  const fields = payload.fields || {};
  return {
    title: payload.title || itemTitle(item) || '',
    type: payload.type || 'task',
    status: fields.status || payload.status || '',
    due_at: toDateInputValue(payload.due_at || fields.due_at),
    follow_up_at: toDateInputValue(payload.follow_up_at || fields.follow_up_at),
    assigned_to: payload.assigned_to || '',
    priority: fields.priority || payload.priority || '',
    content: payload.content || '',
    statement: payload.statement || '',
    context: payload.context || '',
  };
}

export function buildProposalEdits(suggestion, state) {
  const op = suggestion?.operation_type;
  if (op === 'update_entity') {
    const edits = {};
    if (state.status) edits.status = state.status;
    if (state.due_at) edits.due_at = dateInputToIso(state.due_at);
    if (state.follow_up_at) edits.follow_up_at = dateInputToIso(state.follow_up_at);
    if (state.priority) edits.priority = state.priority;
    return edits;
  }
  if (op === 'create_decision') {
    const edits = {};
    if (state.statement?.trim()) edits.statement = state.statement.trim();
    if (state.context?.trim()) edits.context = state.context.trim();
    return edits;
  }
  const edits = {};
  if (state.title?.trim()) edits.title = state.title.trim();
  if (state.type) edits.type = state.type;
  if (state.status) edits.status = state.status;
  if (state.due_at) edits.due_at = dateInputToIso(state.due_at);
  if (state.follow_up_at) edits.follow_up_at = dateInputToIso(state.follow_up_at);
  if (state.assigned_to?.trim()) edits.assigned_to = state.assigned_to.trim();
  if (state.content?.trim()) edits.content = state.content.trim();
  return edits;
}

export function citationEntityPath(citation) {
  if (!citation?.entity_id) return null;
  let type = citation.entity_type;
  if (!type && typeof citation.meta === 'string') {
    if (citation.meta.startsWith('Person')) type = 'person';
    if (citation.meta.startsWith('Space')) type = 'project';
  }
  return recallEntityPath({ id: citation.entity_id, type: type || 'task' });
}

function toDateInputValue(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString().slice(0, 10);
}

function dateInputToIso(value) {
  if (!value) return null;
  return `${value}T12:00:00.000Z`;
}

export const REVIEW_QUEUE_STATUSES = new Set(['pending', 'partial']);
export const REVIEW_QUEUE_LIMIT = 200;

export function mergeReviewReports(...lists) {
  const byId = new Map();
  for (const rows of lists) {
    for (const row of rows || []) {
      const status = row.status || 'pending';
      if (REVIEW_QUEUE_STATUSES.has(status)) {
        byId.set(row.id, { ...row, status });
      }
    }
  }
  return [...byId.values()].sort(
    (left, right) => new Date(right.created_at || 0) - new Date(left.created_at || 0),
  );
}

export async function fetchReviewQueueReports(reportsApi) {
  const [pendingResult, partialResult] = await Promise.allSettled([
    reportsApi.list({ status: 'pending', limit: REVIEW_QUEUE_LIMIT }),
    reportsApi.list({ status: 'partial', limit: REVIEW_QUEUE_LIMIT }),
  ]);
  const pendingPayload = pendingResult.status === 'fulfilled' ? pendingResult.value : null;
  const partialPayload = partialResult.status === 'fulfilled' ? partialResult.value : null;

  if (!pendingPayload && !partialPayload) {
    const reason =
      pendingResult.status === 'rejected'
        ? pendingResult.reason
        : partialResult.reason;
    throw reason instanceof Error ? reason : new Error('Could not load review queue.');
  }

  const rows = mergeReviewReports(pendingPayload?.data, partialPayload?.data);
  const total =
    (pendingPayload?.meta?.total ?? pendingPayload?.data?.length ?? 0) +
    (partialPayload?.meta?.total ?? partialPayload?.data?.length ?? 0);

  return { rows, total };
}
