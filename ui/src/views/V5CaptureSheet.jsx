/* eslint-disable react-refresh/only-export-components */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus } from 'lucide-react';
import Sheet from '../components/Sheet';
import { useCapture } from '../context/CaptureContext';
import { v4API, friendlyApiError } from '../api/v4Client';
import { captureStream, formatCaptureStreamLabel } from '../utils/captureStream';
import styles from './V5CaptureSheet.module.css';

export const CAPTURE_PLACEHOLDER = "Type anything. I'll suggest what I think it means; you can revert any of it after saving.";

const ATTACHMENT_NONE = { id: '', label: 'None', type: '' };

function entityPath(type, id) {
  if (!id) return '/notes';
  if (type === 'person') return `/people/${id}`;
  if (type === 'project') return `/projects/${id}`;
  if (type === 'task') return `/tasks/${id}`;
  if (type === 'area') return `/areas/${id}`;
  if (type === 'resource') return `/resources/${id}`;
  if (type === 'note') return `/notes/${id}`;
  return `/entities/${id}`;
}

function noteViewPath(note) {
  if (!note?.id) return '/inbox';
  return `/notes/${note.id}`;
}

async function resolveAttachmentMeta(attachment) {
  if (!attachment?.id) return null;
  try {
    const entity = await v4API.entities.get(attachment.id);
    return {
      id: entity.id,
      type: entity.type || attachment.type,
      label: entity.title || 'Untitled thread',
    };
  } catch {
    return {
      id: attachment.id,
      type: attachment.type,
      label: attachment.label || 'Current thread',
    };
  }
}

async function loadAttachmentOptions(defaultAttachment) {
  const options = [ATTACHMENT_NONE];
  if (defaultAttachment?.id) {
    const resolved = await resolveAttachmentMeta(defaultAttachment);
    if (resolved) options.push(resolved);
  }
  try {
    const [projects, people] = await Promise.all([
      v4API.entities.list({ type: 'project', limit: 12, sort: 'updated_at', order: 'desc' }),
      v4API.entities.list({ type: 'person', limit: 12, sort: 'updated_at', order: 'desc' }),
    ]);
    for (const entity of [...(projects.data || []), ...(people.data || [])]) {
      if (options.some((opt) => opt.id === entity.id)) continue;
      options.push({
        id: entity.id,
        type: entity.type,
        label: entity.title || 'Untitled',
      });
    }
  } catch {
    /* attachment list is best-effort */
  }
  return options;
}

export function CaptureToast({ toast }) {
  if (!toast) return null;
  const applied = toast.applied ?? 0;
  const suggested = toast.suggested ?? 0;
  return (
    <div className={styles.toast} role="status" aria-live="polite">
      <span>
        Saved · AI processing ({applied} applied, {suggested} suggested).
      </span>
      <Link className={styles.toastLink} to={toast.viewPath || '/inbox'}>
        View
      </Link>
    </div>
  );
}

export function CaptureFab() {
  const { openCapture } = useCapture();
  return (
    <>
      <button
        type="button"
        className={styles.fab}
        aria-label="Open capture"
        title="Capture"
        onClick={openCapture}
      >
        <Plus size={24} strokeWidth={2.2} aria-hidden="true" />
      </button>
      <div className={styles.mobileBar}>
        <button
          type="button"
          className={styles.mobileInput}
          aria-label="Open capture"
          onClick={openCapture}
        >
          {CAPTURE_PLACEHOLDER}
        </button>
      </div>
    </>
  );
}

export default function V5CaptureSheet({
  open: openProp,
  onClose: onCloseProp,
  defaultAttachment: defaultAttachmentProp,
  onSaved,
  attachmentOptions: attachmentOptionsProp,
  captureFn = captureStream,
}) {
  const captureCtx = useCapture();
  const open = openProp ?? captureCtx.open;
  const onClose = onCloseProp ?? captureCtx.closeCapture;
  const defaultAttachment = defaultAttachmentProp ?? captureCtx.defaultAttachment;
  const initialContent = captureCtx.initialContent ?? '';
  const showToast = captureCtx.showToast;

  const [content, setContent] = useState('');
  const [attachment, setAttachment] = useState(ATTACHMENT_NONE);
  const [attachmentOptions, setAttachmentOptions] = useState([ATTACHMENT_NONE]);
  const [streaming, setStreaming] = useState(false);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState('');
  const lastPayloadRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setContent('');
      setAttachment(ATTACHMENT_NONE);
      setStreaming(false);
      setEvents([]);
      setError('');
      lastPayloadRef.current = null;
      return;
    }
    setContent(initialContent);

    let active = true;
    (async () => {
      const options = attachmentOptionsProp
        || await loadAttachmentOptions(defaultAttachment);
      if (!active) return;
      setAttachmentOptions(options);
      if (defaultAttachment?.id) {
        const match = options.find((opt) => opt.id === defaultAttachment.id);
        setAttachment(match || options[1] || ATTACHMENT_NONE);
      } else {
        setAttachment(ATTACHMENT_NONE);
      }
    })();

    return () => { active = false; };
  }, [open, defaultAttachment, attachmentOptionsProp, initialContent]);

  const activeLabel = useMemo(
    () => events.filter((event) => event.type !== 'done').at(-1),
    [events],
  );

  async function linkToThread(noteId, thread) {
    if (!thread?.id || !noteId) return;
    try {
      await v4API.relationships.create(thread.id, {
        target_entity_id: noteId,
        relationship_type: 'related',
        source: 'capture',
      });
    } catch {
      /* linking is best-effort; capture still succeeded */
    }
  }

  async function runCapture(trimmed, threadAttachment) {
    setStreaming(true);
    setError('');
    setEvents([]);
    lastPayloadRef.current = { content: trimmed, attachment: threadAttachment };

    const body = {
      content: trimmed,
      source: 'ui',
      mode: 'auto',
    };
    if (threadAttachment?.id) body.thread_id = threadAttachment.id;

    try {
      const result = await captureFn(body, {
        onEvent: (event) => {
          setEvents((prev) => [...prev, event]);
        },
      });
      if (threadAttachment?.id && result?.source_note?.id) {
        await linkToThread(result.source_note.id, threadAttachment);
      }
      const applied = (result?.applied_changes || []).length;
      const suggested = (result?.suggestions || []).length;
      onSaved?.(result);
      onClose();
      if (showToast) {
        showToast({
          applied,
          suggested,
          viewPath: noteViewPath(result?.source_note),
        });
      }
    } catch (err) {
      setError(friendlyApiError(err, 'Capture failed'));
    } finally {
      setStreaming(false);
    }
  }

  function handleSave() {
    const trimmed = content.trim();
    if (!trimmed || streaming) return;
    runCapture(trimmed, attachment);
  }

  function handleRetry() {
    const last = lastPayloadRef.current;
    if (!last?.content || streaming) return;
    setError('');
    runCapture(last.content, last.attachment || attachment);
  }

  return (
    <Sheet open={open} onClose={onClose} ariaLabel="Capture">
      <div className={styles.captureSheet}>
        <header className={styles.header}>
          <h2 className={styles.title}>Quick capture</h2>
          <div className={styles.attachmentWrap}>
            <span>attached:</span>
            <select
              className={styles.attachmentSelect}
              aria-label="Capture attachment"
              value={attachment.id}
              disabled={streaming}
              onChange={(event) => {
                const next = attachmentOptions.find((opt) => opt.id === event.target.value);
                setAttachment(next || ATTACHMENT_NONE);
              }}
            >
              {attachmentOptions.map((opt) => (
                <option key={opt.id || 'none'} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </header>

        <div className={styles.body}>
          <textarea
            className={styles.textarea}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder={CAPTURE_PLACEHOLDER}
            aria-label="Capture text"
            disabled={streaming}
            rows={6}
            autoFocus
          />
          <p className={styles.hint}>
            After saving you can review applied changes and revert anything you disagree with.
          </p>

          {streaming && (
            <div className={styles.progress} aria-live="polite">
              <strong>{formatCaptureStreamLabel(activeLabel) || 'Working…'}</strong>
              <ul className={styles.progressList}>
                {events.map((event, index) => (
                  <li
                    key={`${event.type}-${index}`}
                    className={`${styles.progressItem} ${
                      index === events.length - 1 ? styles.progressItemActive : ''
                    }`}
                  >
                    {formatCaptureStreamLabel(event)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div className={styles.error} role="alert">
              {error}
              <div className={styles.errorActions}>
                <button
                  type="button"
                  className={styles.buttonSecondary}
                  onClick={handleRetry}
                >
                  Retry
                </button>
              </div>
            </div>
          )}
        </div>

        <footer className={styles.footer}>
          <span className={styles.footerHint}>Long-press + for voice (coming soon)</span>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={onClose}
            disabled={streaming}
          >
            Cancel
          </button>
          <button
            type="button"
            className={styles.buttonPrimary}
            onClick={handleSave}
            disabled={!content.trim() || streaming}
          >
            {streaming ? 'Saving…' : 'Save'}
          </button>
        </footer>
      </div>
    </Sheet>
  );
}

export { entityPath, loadAttachmentOptions, ATTACHMENT_NONE };
