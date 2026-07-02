import { useCallback, useEffect, useState } from 'react';
import Sheet from '../components/Sheet';
import { v4API, friendlyApiError } from '../api/v4Client';
import { useSummary } from '../context/SummaryContext';
import styles from './V5ReviewSheet.module.css';

export function formatSuggestionType(suggestionType) {
  if (!suggestionType) return 'Suggestion';
  if (suggestionType.startsWith('create_')) {
    return `New ${suggestionType.slice(7).replace(/_/g, ' ')}`;
  }
  return suggestionType.replace(/_/g, ' ');
}

export function suggestionTitle(row) {
  return row?.payload?.title || row?.title || 'Untitled suggestion';
}

export default function V5ReviewSheet({ open, onClose }) {
  const { refreshSummary } = useSummary();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  const loadSuggestions = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await v4API.suggestions.list({ status: 'pending' });
      setRows(payload?.data || []);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load suggestions.'));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) {
      setRows([]);
      setError('');
      setBusyId(null);
      return;
    }
    loadSuggestions();
  }, [open, loadSuggestions]);

  async function handleAccept(id) {
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.accept(id);
      setRows((prev) => prev.filter((row) => row.id !== id));
      refreshSummary();
    } catch (err) {
      setError(friendlyApiError(err, 'Could not accept suggestion.'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDismiss(id) {
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.dismiss(id);
      setRows((prev) => prev.filter((row) => row.id !== id));
      refreshSummary();
    } catch (err) {
      setError(friendlyApiError(err, 'Could not dismiss suggestion.'));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Sheet open={open} onClose={onClose} ariaLabel="Review suggestions" mobileBottomSheet>
      <div className={styles.reviewSheet}>
        <header className={styles.header}>
          <div>
            <h2 className={styles.title}>Review suggestions</h2>
            <p className={styles.subtitle}>Accept to create, dismiss to skip.</p>
          </div>
        </header>

        <div className={styles.body}>
          {error ? <div className={styles.error} role="alert">{error}</div> : null}
          {loading ? (
            <p className={styles.empty}>Loading suggestions…</p>
          ) : rows.length === 0 ? (
            <p className={styles.empty}>No pending suggestions.</p>
          ) : (
            <ul className={styles.list} aria-label="Pending suggestions">
              {rows.map((row) => {
                const evidence = row.reason || row.payload?.evidence;
                const sourceTitle = row.source_note_title;
                const disabled = busyId === row.id;
                return (
                  <li key={row.id} className={styles.card}>
                    <div className={styles.cardHeader}>
                      <h3 className={styles.cardTitle}>{suggestionTitle(row)}</h3>
                      <span className={styles.cardType}>{formatSuggestionType(row.suggestion_type)}</span>
                    </div>
                    {sourceTitle ? (
                      <p className={styles.cardMeta}>From: {sourceTitle}</p>
                    ) : null}
                    {evidence ? (
                      <p className={styles.cardEvidence}>{evidence}</p>
                    ) : null}
                    <div className={styles.actions}>
                      <button
                        type="button"
                        className={styles.buttonSecondary}
                        disabled={disabled}
                        onClick={() => handleDismiss(row.id)}
                      >
                        Dismiss
                      </button>
                      <button
                        type="button"
                        className={styles.buttonPrimary}
                        disabled={disabled}
                        onClick={() => handleAccept(row.id)}
                      >
                        Accept
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </Sheet>
  );
}
