import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import Sheet from './Sheet';
import { v4API } from '../api/v4Client';
import { ThreadDetailContent } from '../views/V5ThreadDetail';
import styles from './CitationEntitySheet.module.css';

export default function CitationEntitySheet({ entityId, open, onClose }) {
  const [detail, setDetail] = useState(null);
  const [events, setEvents] = useState([]);
  const [canonicalText, setCanonicalText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // B-016: track the element that opened the sheet so we can restore focus
  // when it closes. Without this, focus jumps to <body> after closing.
  const previouslyFocusedRef = useRef(null);

  useEffect(() => {
    if (!open || !entityId) {
      setDetail(null);
      setEvents([]);
      setCanonicalText('');
      setError('');
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError('');

    Promise.all([
      v4API.entities.detail(entityId),
      v4API.entities.events(entityId),
      v4API.entities.canonical(entityId).catch(() => ({ canonical: '' })),
    ])
      .then(([detailResponse, eventsResponse, canonicalResponse]) => {
        if (cancelled) return;
        setDetail(detailResponse);
        setEvents(eventsResponse?.data || []);
        setCanonicalText(canonicalResponse?.canonical || '');
      })
      .catch((fetchError) => {
        if (!cancelled) setError(fetchError.message || 'Failed to load citation');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, entityId]);

  const handleClose = useCallback(() => {
    onClose?.();
  }, [onClose]);

  // B-016: capture the focused element when opening; restore on close.
  // We capture just before `open` flips true (in the previous render's
  // cleanup) and restore on the close transition. Storing the element
  // (not just its selector) handles dynamically-rendered citation
  // links correctly.
  useEffect(() => {
    if (open) {
      const previouslyFocused = document.activeElement;
      previouslyFocusedRef.current =
        previouslyFocused && previouslyFocused instanceof HTMLElement
          ? previouslyFocused
          : null;
      return () => {
        // Restore on unmount or when `open` flips back to false.
        const target = previouslyFocusedRef.current;
        if (target && document.contains(target) && typeof target.focus === 'function') {
          target.focus();
        }
        previouslyFocusedRef.current = null;
      };
    }
    return undefined;
  }, [open]);

  return (
    <Sheet open={open} onClose={handleClose} ariaLabel="Citation" mobileBottomSheet={false}>
      <div className={styles.sheet}>
        <header className={styles.header}>
          <button
            type="button"
            className={styles.backButton}
            onClick={handleClose}
            aria-label="Back"
          >
            <ArrowLeft size={16} strokeWidth={2.2} aria-hidden="true" />
            Back
          </button>
        </header>
        <div className={styles.body}>
          {loading && (
            <p className={styles.status}>Loading citation…</p>
          )}
          {error && (
            <p className={styles.statusError} role="alert">{error}</p>
          )}
          {!loading && !error && detail?.entity && (
            <ThreadDetailContent
              detail={detail}
              events={events}
              canonicalText={canonicalText}
              onAction={() => {}}
              onCapture={() => {}}
              showCaptureFab={false}
              showNextActions={false}
              titleEditable={false}
            />
          )}
        </div>
      </div>
    </Sheet>
  );
}
