import {
  useCallback, useEffect, useRef, useState,
} from 'react';
import styles from './InlineTitleEditor.module.css';

export default function InlineTitleEditor({
  title = '',
  onSave,
  className = '',
  emptyLabel = '(no title)',
  saving = false,
  disabled = false,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const inputRef = useRef(null);
  const committingRef = useRef(false);

  useEffect(() => {
    if (!editing) {
      setDraft(title);
    }
  }, [title, editing]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const startEditing = useCallback(() => {
    if (disabled || saving) return;
    setDraft(title);
    setEditing(true);
  }, [disabled, saving, title]);

  const cancel = useCallback(() => {
    setDraft(title);
    setEditing(false);
  }, [title]);

  const commit = useCallback(async () => {
    if (committingRef.current) return;
    committingRef.current = true;
    setEditing(false);

    const trimmed = draft.trim();
    const baseline = (title || '').trim();
    if (trimmed === baseline) {
      committingRef.current = false;
      return;
    }

    try {
      await onSave(trimmed);
    } catch {
      setDraft(title);
    } finally {
      committingRef.current = false;
    }
  }, [draft, onSave, title]);

  const displayText = title?.trim() || emptyLabel;
  const isEmpty = !title?.trim();

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={`${styles.input} ${className}`}
        type="text"
        value={draft}
        aria-label="Title"
        disabled={saving}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => { commit(); }}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            commit();
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            cancel();
          }
        }}
      />
    );
  }

  return (
    <h1 className={className}>
      <button
        type="button"
        className={`${styles.button} ${isEmpty ? styles.empty : ''}`}
        onClick={startEditing}
        disabled={disabled || saving}
        aria-label={`Title: ${displayText}. Click to edit.`}
      >
        {displayText}
      </button>
    </h1>
  );
}
