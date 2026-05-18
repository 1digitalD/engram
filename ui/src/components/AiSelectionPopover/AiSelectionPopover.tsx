import React, { useState, useCallback, useEffect, useLayoutEffect, useRef } from 'react';
import { Loader2, X } from 'lucide-react';

export const AI_ACTIONS = [
  { id: 'classify', label: 'Classify', description: 'Classify the selected text' },
  { id: 'extract_task', label: 'Extract Task', description: 'Extract actionable tasks' },
  { id: 'create_link', label: 'Find Links', description: 'Find related entities and links' },
  { id: 'find_and_update', label: 'Find & Update', description: 'Find an existing entity to update' },
  { id: 'improve_writing', label: 'Improve', description: 'Improve clarity and tone' },
];

export async function callAiAction(action, selectedText, apiCall) {
  if (apiCall) {
    return apiCall(action, selectedText);
  }
  // Call the real backend endpoint
  const res = await fetch('/api/v4/ai/propose-from-selection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, selected_text: selectedText }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || `AI action failed: ${res.status}`);
  }
  return res.json();
}

export default function AiSelectionPopover({
  visible = false,
  position = { x: 0, y: 0 },
  selectedText = '',
  onAction,
  onClose,
  busy = false,
  result = null,
}) {
  const popoverRef = useRef(null);
  const [hoveredAction, setHoveredAction] = useState(null);
  const [closeHovered, setCloseHovered] = useState(false);
  const [dismissedCandidateIds, setDismissedCandidateIds] = useState([]);
  const [applyingCandidateIds, setApplyingCandidateIds] = useState([]);
  const [clampedX, setClampedX] = useState(position.x);
  const [resolvedTop, setResolvedTop] = useState(position.y);

  useEffect(() => {
    setDismissedCandidateIds([]);
    setApplyingCandidateIds([]);
  }, [result]);

  useEffect(() => {
    if (!visible) return;
    const handler = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        onClose?.();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [visible, onClose]);

  useLayoutEffect(() => {
    if (!visible) return;
    const width = popoverRef.current?.offsetWidth || 0;
    const height = popoverRef.current?.offsetHeight || 0;
    const viewportWidth = window.innerWidth || 0;
    const viewportHeight = window.innerHeight || 0;
    if (width <= 0 || viewportWidth <= 0 || viewportHeight <= 0) {
      setClampedX(position.x);
      setResolvedTop(position.y);
      return;
    }
    const gutter = 12;
    const anchorGap = 10;
    const minCenter = gutter + width / 2;
    const maxCenter = Math.max(minCenter, viewportWidth - gutter - width / 2);
    const next = Math.min(Math.max(position.x, minCenter), maxCenter);
    setClampedX(next);

    const aboveTop = position.y - height - anchorGap;
    const belowTop = position.y + anchorGap;
    const fitsAbove = aboveTop >= gutter;
    const fitsBelow = belowTop + height <= viewportHeight - gutter;

    if (fitsAbove) {
      setResolvedTop(aboveTop);
    } else if (fitsBelow) {
      setResolvedTop(belowTop);
    } else {
      setResolvedTop(Math.max(gutter, Math.min(belowTop, viewportHeight - height - gutter)));
    }
  }, [visible, position.x, position.y, result, selectedText]);

  useEffect(() => {
    if (!visible) return;
    const handler = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [visible, onClose]);

  const popoverStyle = {
    position: 'fixed',
    zIndex: 100,
    left: clampedX,
    top: resolvedTop,
    transform: 'translateX(-50%)',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    width: 'max-content',
    maxWidth: 'min(420px, calc(100vw - 24px))',
  };

  const toolbarStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '2px',
    padding: '3px',
    background: 'var(--bg-surface-3, var(--bg-surface3, var(--bg-elevated)))',
    border: '1px solid var(--border)',
    borderRadius: '7px',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.55)',
  };

  const actionStyle = (isHovered) => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '24px',
    padding: '4px 9px',
    border: 'none',
    borderRadius: '5px',
    background: isHovered ? 'rgba(255, 255, 255, 0.06)' : 'transparent',
    color: 'var(--text-secondary)',
    cursor: busy ? 'not-allowed' : 'pointer',
    fontSize: '11.5px',
    fontWeight: 500,
    lineHeight: 1,
    transition: 'background-color 120ms ease, color 120ms ease, opacity 120ms ease',
    opacity: busy ? 0.6 : 1,
    whiteSpace: 'nowrap',
  });

  const closeStyle = {
    ...actionStyle(closeHovered),
    color: 'var(--text-secondary)',
    marginLeft: '2px',
    padding: '4px',
  };

  const resultStyle = {
    alignSelf: 'center',
    maxWidth: 'min(360px, calc(100vw - 24px))',
    padding: '6px 10px',
    background: 'var(--bg-surface)',
    border: '1px solid var(--accent-dim)',
    borderRadius: '5px',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)',
    color: 'var(--accent)',
    fontSize: '11.5px',
    fontFamily: 'var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace)',
    lineHeight: 1.45,
    whiteSpace: 'pre-wrap',
  };

  const disambiguationStyle = {
    alignSelf: 'center',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    width: 'min(420px, calc(100vw - 24px))',
    padding: '10px',
    background: 'var(--bg-surface)',
    border: '1px solid var(--accent-dim)',
    borderRadius: '7px',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)',
  };

  const candidateCardStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '8px',
    borderRadius: '6px',
    background: 'var(--bg-surface-2, var(--bg-surface2, rgba(255,255,255,0.03)))',
    border: '1px solid var(--border)',
  };

  const candidateActionsStyle = {
    display: 'flex',
    gap: '6px',
  };

  const candidateButtonStyle = (primary) => ({
    minHeight: '24px',
    padding: '4px 9px',
    borderRadius: '5px',
    border: primary ? '1px solid var(--accent-dim)' : '1px solid var(--border)',
    background: primary ? 'rgba(111, 179, 255, 0.12)' : 'transparent',
    color: primary ? 'var(--accent)' : 'var(--text-secondary)',
    cursor: 'pointer',
    fontSize: '11.5px',
    fontWeight: 500,
  });

  const findAndUpdateCandidates = Array.isArray(result?.candidates)
    ? result.candidates.filter((candidate) => (
      candidate?.entity?.id && !dismissedCandidateIds.includes(candidate.entity.id)
    ))
    : [];

  const handleApplyCandidate = useCallback(async (candidate) => {
    const candidateId = candidate?.entity?.id;
    if (!candidateId || !candidate?.proposed_change) return;

    setApplyingCandidateIds((current) => current.concat(candidateId));
    try {
      const res = await fetch(`/api/v4/entities/${candidateId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(candidate.proposed_change),
      });
      if (!res.ok) {
        let errorMessage = `Failed to update entity ${candidateId}`;
        try {
          const err = await res.json();
          errorMessage = err.error || errorMessage;
        } catch {
          // Ignore malformed error JSON and use the fallback message.
        }
        throw new Error(errorMessage);
      }
      setDismissedCandidateIds((current) => current.concat(candidateId));
    } finally {
      setApplyingCandidateIds((current) => current.filter((id) => id !== candidateId));
    }
  }, []);

  const handleDismissCandidate = useCallback((candidateId) => {
    setDismissedCandidateIds((current) => current.concat(candidateId));
  }, []);

  if (!visible || !selectedText) return null;

  const renderResult = () => {
    if (!result) return null;

    if (Array.isArray(result?.candidates)) {
      if (findAndUpdateCandidates.length === 0) {
        return (
          <div style={resultStyle} data-testid="ai-selection-result">
            No remaining update candidates.
          </div>
        );
      }

      return (
        <div style={disambiguationStyle} data-testid="ai-selection-disambiguation">
          {findAndUpdateCandidates.map((candidate) => {
            const candidateId = candidate.entity.id;
            const isApplying = applyingCandidateIds.includes(candidateId);
            return (
              <div key={candidateId} style={candidateCardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
                  <strong style={{ color: 'var(--text-primary)', fontSize: '12px' }}>
                    {candidate.entity.title || 'Untitled entity'}
                  </strong>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '11px', textTransform: 'capitalize' }}>
                    {candidate.entity.type}
                  </span>
                </div>
                <div style={resultStyle}>
                  {(candidate.proposed_change_summary || candidate.proposed_change?.content || '').trim()}
                </div>
                <div style={candidateActionsStyle}>
                  <button
                    type="button"
                    style={candidateButtonStyle(true)}
                    onClick={() => handleApplyCandidate(candidate)}
                    disabled={isApplying}
                    aria-label={`Apply ${candidate.entity.title || candidateId}`}
                  >
                    {isApplying ? 'Applying...' : 'Apply'}
                  </button>
                  <button
                    type="button"
                    style={candidateButtonStyle(false)}
                    onClick={() => handleDismissCandidate(candidateId)}
                    aria-label={`Dismiss ${candidate.entity.title || candidateId}`}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    return (
      <div style={resultStyle} data-testid="ai-selection-result">
        {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
      </div>
    );
  };

  return (
    <div
      ref={popoverRef}
      style={popoverStyle}
      data-testid="ai-selection-popover"
      role="menu"
    >
      {renderResult()}
      <div style={toolbarStyle}>
        {AI_ACTIONS.map(action => (
          <button
            key={action.id}
            type="button"
            style={actionStyle(hoveredAction === action.id)}
            onClick={() => onAction(action.id)}
            onMouseEnter={() => setHoveredAction(action.id)}
            onMouseLeave={() => setHoveredAction(null)}
            disabled={busy}
            data-testid={`ai-action-${action.id}`}
            role="menuitem"
            title={action.description}
          >
            {busy ? <Loader2 size={12} className="spin" /> : action.label}
          </button>
        ))}
        <button
          type="button"
          style={closeStyle}
          onClick={onClose}
          onMouseEnter={() => setCloseHovered(true)}
          onMouseLeave={() => setCloseHovered(false)}
          aria-label="Close AI actions"
          data-testid="ai-popover-close"
        >
          <X size={12} />
        </button>
      </div>
    </div>
  );
}

// ─── Hook: useTextSelection ─────────────────────────────────────────────

export function useTextSelection(containerRef) {
  const [selection, setSelection] = useState({ text: '', position: { x: 0, y: 0 }, visible: false });

  useEffect(() => {
    let pending = null;

    const handler = () => {
      const sel = window.getSelection();
      const isCollapsed = !sel || sel.isCollapsed || !sel.toString().trim();
      const text = isCollapsed ? '' : sel.toString().trim();
      const range = isCollapsed || !sel.rangeCount ? null : sel.getRangeAt(0);
      const rect = range ? range.getBoundingClientRect() : null;
      const inContainer = containerRef?.current && range
        ? containerRef.current.contains(range.commonAncestorContainer)
        : false;

      const next = isCollapsed || (containerRef?.current && !inContainer)
        ? null
        : {
            text,
            position: {
              x: rect.left + rect.width / 2,
              y: rect.top,
            },
            visible: true,
          };

      if (pending) clearTimeout(pending);
      pending = setTimeout(() => {
        pending = null;
        if (next) {
          setSelection(next);
        } else {
          setSelection(s => s.visible ? { ...s, visible: false } : s);
        }
      }, 0);
    };

    document.addEventListener('selectionchange', handler);
    return () => {
      document.removeEventListener('selectionchange', handler);
      if (pending) clearTimeout(pending);
    };
  }, [containerRef]);

  const hide = useCallback(() => {
    setSelection(s => ({ ...s, visible: false }));
  }, []);

  return { ...selection, hide };
}
