import { useState, useEffect } from 'react';
import { X, Loader2, FileText, CheckSquare, Library, Users } from 'lucide-react';
import styles from './CaptureModal.module.css';

const CAPTURE_TYPES = [
  { value: 'note', label: 'Note', icon: FileText },
  { value: 'task', label: 'Task', icon: CheckSquare },
  { value: 'resource', label: 'Resource', icon: Library },
  { value: 'person', label: 'Person', icon: Users },
];

export default function CaptureModal({ onClose, onCreated }) {
  const [content, setContent] = useState('');
  const [entityType, setEntityType] = useState('note');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const handleSubmit = async (event) => {
    event.preventDefault();
    const body = content.trim();
    if (!body || submitting) return;

    setSubmitting(true);
    setError('');

    try {
      const response = await fetch('/api/v2/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: body,
          entity_type: entityType,
          source: 'ui',
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
      }

      const entity = payload.data || payload.entity || payload.note;
      if (!entity?.id) {
        throw new Error('Capture response did not include a created entity');
      }

      onCreated({
        entity,
        aiStatus: payload.ai_status || entity.ai_status || 'processing',
        selectedType: entityType,
      });
    } catch (err) {
      setError(err.message || 'Capture failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape' && !submitting) {
      event.preventDefault();
      onClose();
    }
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSubmit(event);
    }
  };

  function isTypingElement(el) {
    if (!el || !(el instanceof HTMLElement)) return false;
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (el.closest('[contenteditable="true"]')) return true;
    return false;
  }

  useEffect(() => {
    const handleGlobalKey = (e) => {
      if (e.key === 'Escape' && !submitting && !isTypingElement(/** @type {HTMLElement} */(e.target))) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleGlobalKey);
    return () => document.removeEventListener('keydown', handleGlobalKey);
  }, [onClose, submitting]);

  return (
    <div
      role="presentation"
      className={styles.backdrop}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="capture-modal-title"
        className={styles.panel}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className={styles.header}>
          <div>
            <h2 id="capture-modal-title" className={styles.title}>
              Quick capture
            </h2>
            <p className={styles.subtitle}>
              Create from anywhere. AI classifies and links after save.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close capture"
            className={styles.closeBtn}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.typeSelector}>
            {CAPTURE_TYPES.map(({ value, label, icon: Icon }) => {
              const active = value === entityType;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setEntityType(value)}
                  disabled={submitting}
                  className={`${styles.typeBtn} ${active ? styles.active : ''}`}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              );
            })}
          </div>

          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Capture a thought, task, person, or reference..."
            rows={5}
            disabled={submitting}
            className={styles.textarea}
            autoFocus
          />

          <div className={styles.footer}>
            <div
              className={`${styles.status} ${
                error ? styles.error : submitting ? styles.processing : ''
              }`}
            >
              {error ? error : submitting ? 'Classifying...' : 'Cmd/Ctrl+Enter to create'}
            </div>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={styles.createBtn}
                disabled={submitting || !content.trim()}
              >
                {submitting ? <Loader2 size={14} className={styles.spinner} /> : null}
                {submitting ? 'Processing' : 'Create'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
