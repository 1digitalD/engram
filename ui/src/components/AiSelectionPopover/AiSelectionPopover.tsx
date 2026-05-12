import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Sparkles, Tag, CheckSquare, Link2, PenLine, Loader2, X } from 'lucide-react';
import styles from './AiSelectionPopover.module.css';

export const AI_ACTIONS = [
  { id: 'classify', label: 'Classify', icon: Tag, description: 'Classify the selected text' },
  { id: 'extract_task', label: 'Extract Task', icon: CheckSquare, description: 'Extract actionable tasks' },
  { id: 'create_link', label: 'Create Link', icon: Link2, description: 'Create knowledge graph link' },
  { id: 'improve_writing', label: 'Improve Writing', icon: PenLine, description: 'Improve clarity and tone' },
];

export async function callAiAction(action, selectedText, apiCall) {
  if (apiCall) {
    return apiCall(action, selectedText);
  }
  // Call the real backend endpoint
  const res = await fetch('/api/v1/ai/propose-from-selection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, text: selectedText }),
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

  return (
    <div
      ref={popoverRef}
      className={styles.popover}
      style={{ left: position.x, top: position.y }}
      data-testid="ai-selection-popover"
      role="menu"
    >
      <div className={styles.popoverHeader}>
        <Sparkles size={14} className={styles.popoverIcon} />
        <span className={styles.popoverTitle}>AI Actions</span>
        <button
          className={styles.popoverClose}
          onClick={onClose}
          aria-label="Close AI actions"
          data-testid="ai-popover-close"
        >
          <X size={12} />
        </button>
      </div>
      <div className={styles.popoverSelected}>
        &ldquo;{selectedText.length > 80 ? `${selectedText.slice(0, 80)}...` : selectedText}&rdquo;
      </div>
      <div className={styles.popoverActions}>
        {AI_ACTIONS.map(action => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              className={styles.actionBtn}
              onClick={() => onAction(action.id)}
              disabled={busy}
              data-testid={`ai-action-${action.id}`}
              role="menuitem"
              title={action.description}
            >
              {busy ? <Loader2 size={14} className="spin" /> : <Icon size={14} />}
              <span className={styles.actionLabel}>{action.label}</span>
            </button>
          );
        })}
      </div>
      {result && (
        <div className={styles.popoverResult} data-testid="ai-selection-result">
          <span className={styles.resultLabel}>Result:</span>
          <p>{result}</p>
        </div>
      )}
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
        x: rect.left + rect.width / 2 - 120,
        y: rect.top - 10 + window.scrollY,
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
