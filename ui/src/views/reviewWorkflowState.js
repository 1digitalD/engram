import { useCallback, useEffect, useState } from 'react';

export const REVIEW_WORKFLOW_STORAGE_KEY = 'engram.reviewWorkflow.v1';

export const REVIEW_WORKFLOW_STEPS = [
  { id: 'inbox', title: 'Clear Inbox', short: 'Inbox' },
  { id: 'projects', title: 'Review Projects', short: 'Projects' },
  { id: 'areas', title: 'Review Areas', short: 'Areas' },
  { id: 'orphans', title: 'Orphan Notes', short: 'Orphans' },
  { id: 'proposals', title: 'Link Proposals', short: 'Links' },
  { id: 'insights', title: 'Insights', short: 'Insights' },
  { id: 'plan', title: 'Plan next week', short: 'Plan' },
];

export function defaultReviewWorkflowState() {
  const expanded = {};
  const completed = {};
  REVIEW_WORKFLOW_STEPS.forEach((s, i) => {
    expanded[s.id] = i === 0;
    completed[s.id] = false;
  });
  return {
    expanded,
    completed,
    lastActiveStepId: REVIEW_WORKFLOW_STEPS[0].id,
    updatedAt: null,
  };
}

/** Merge persisted JSON safely into canonical step shape */
export function mergeReviewWorkflowPersisted(parsed) {
  const base = defaultReviewWorkflowState();
  if (!parsed || typeof parsed !== 'object') return base;

  const expanded = { ...base.expanded };
  const completed = { ...base.completed };
  REVIEW_WORKFLOW_STEPS.forEach((s) => {
    if (typeof parsed.expanded?.[s.id] === 'boolean') expanded[s.id] = parsed.expanded[s.id];
    if (typeof parsed.completed?.[s.id] === 'boolean') completed[s.id] = parsed.completed[s.id];
  });
  const lastActiveStepId = REVIEW_WORKFLOW_STEPS.some((s) => s.id === parsed.lastActiveStepId)
    ? parsed.lastActiveStepId
    : base.lastActiveStepId;

  return { expanded, completed, lastActiveStepId, updatedAt: null };
}

/** Persist expand/collapse, completion checkboxes, active step across sessions (weekly review continuity). */
export function usePersistedReviewWorkflow(storageKey = REVIEW_WORKFLOW_STORAGE_KEY) {
  const [hydrated, setHydrated] = useState(false);
  const [state, setState] = useState(() => defaultReviewWorkflowState());
  const [hadPersistedDraft, setHadPersistedDraft] = useState(false);

  useEffect(() => {
    try {
      if (typeof localStorage === 'undefined') return;
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const merged = mergeReviewWorkflowPersisted(JSON.parse(raw));
        setState(merged);
        setHadPersistedDraft(true);
      }
    } catch {
      // ignore parse errors
    }
    setHydrated(true);
  }, [storageKey]);

  useEffect(() => {
    if (!hydrated || typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          expanded: state.expanded,
          completed: state.completed,
          lastActiveStepId: state.lastActiveStepId,
          updatedAt: new Date().toISOString(),
        })
      );
    } catch {
      // ignore quota errors
    }
  }, [state, hydrated, storageKey]);

  const resetWorkflow = useCallback(() => {
    setState(defaultReviewWorkflowState());
    setHadPersistedDraft(false);
    try {
      if (typeof localStorage !== 'undefined') localStorage.removeItem(storageKey);
    } catch {}
  }, [storageKey]);

  return { state, setState, hydrated, hadPersistedDraft, resetWorkflow };
}
