import { useCallback, useEffect, useState } from 'react';
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
            />
          )}
        </div>
      </div>
    </Sheet>
  );
}
