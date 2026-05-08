import React, { useEffect, useRef, useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import useStore from '../../stores/useStore';
import styles from './QuickCapture.module.css';

export default function QuickCapture({ onRequestFullEditor }) {
  const { createNote, closeCapture } = useStore();
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const taRef = useRef(null);

  useEffect(() => {
    taRef.current?.focus();
  }, []);

  const handleBackdrop = (e) => {
    if (e.target === e.currentTarget) closeCapture();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const raw = text.trim();
    if (!raw || saving) return;
    setSaving(true);
    try {
      await createNote({ raw_text: raw, bucket: 'INBOX' });
      setText('');
      closeCapture();
    } finally {
      setSaving(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeCapture();
    }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className={styles.backdrop} role="presentation" onMouseDown={handleBackdrop}>
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="quick-capture-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div>
            <h2 id="quick-capture-title" className={styles.title}>
              Quick capture
            </h2>
            <p className={styles.hint}>
              Saves to inbox · AI classifies on save ·{' '}
              <kbd>Cmd/Ctrl+Enter</kbd> to submit · <kbd>Esc</kbd> to close
            </p>
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            aria-label="Close"
            onClick={() => closeCapture()}
          >
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <textarea
            ref={taRef}
            className={styles.textarea}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Drop a thought, link, or task…"
            rows={5}
          />
          <div className={styles.actions}>
            <button
              type="button"
              className={styles.linkBtn}
              onClick={() => {
                closeCapture();
                onRequestFullEditor?.();
              }}
            >
              Open full editor…
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => closeCapture()}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || !text.trim()}>
              {saving ? <Loader2 size={14} className="spin" /> : null}
              Capture
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
