import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Loader2, X } from 'lucide-react';

export const AI_ACTIONS = [
  { id: 'classify', label: 'Classify', description: 'Classify the selected text' },
  { id: 'extract_task', label: 'Extract Task', description: 'Extract actionable tasks' },
  { id: 'create_link', label: 'Find Links', description: 'Find related entities and links' },
  { id: 'improve_writing', label: 'Improve', description: 'Improve clarity and tone' },
];

export async function callAiAction(action, selectedText, apiCall) {
  if (apiCall) {
    return apiCall(action, selectedText);
  }
  // Call the real backend endpoint
  const res = await fetch('/api/v2/ai/propose-from-selection', {
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

  if (!visible || !selectedText) return null;

  const popoverStyle = {
    position: 'absolute',
    zIndex: 100,
    left: position.x,
    top: position.y,
    transform: 'translate(-50%, calc(-100% - 8px))',
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

  return (
    <div
      ref={popoverRef}
      style={popoverStyle}
      data-testid="ai-selection-popover"
      role="menu"
    >
      {result && (
        <div style={resultStyle} data-testid="ai-selection-result">
          {result}
        </div>
      )}
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

  const handleSelectionChange = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setSelection(s => s.visible ? { ...s, visible: false } : s);
      return;
    }

    const text = sel.toString().trim();
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    if (containerRef?.current && !containerRef.current.contains(range.commonAncestorContainer)) {
      setSelection(s => s.visible ? { ...s, visible: false } : s);
      return;
    }

    setSelection({
      text,
      position: {
        x: rect.left + rect.width / 2 + window.scrollX,
        y: rect.top + window.scrollY,
      },
      visible: true,
    });
  }, [containerRef]);

  useEffect(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [handleSelectionChange]);

  const hide = useCallback(() => {
    setSelection(s => ({ ...s, visible: false }));
  }, []);

  return { ...selection, hide };
}
