import { itemEvidence, itemTitle, proposalLabel } from './vocab';

export const DISMISS_REASONS = [
  'not a task',
  'not mine',
  'duplicate',
  'wrong target',
  'other',
];

/** Narrative items that map to pending AiSuggestions (resolveable). */
export function isResolvableItem(item) {
  if (!item?.id) return false;
  if (item.kind === 'routing_summary') return false;
  if (item.event_id) return false;
  return true;
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
  };
}

export function countPendingInReport(suggestions = []) {
  return suggestions.filter((row) => row.status === 'pending').length;
}
