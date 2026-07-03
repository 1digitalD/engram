import { useCallback, useEffect, useMemo, useState } from 'react';
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

function groupKey(row) {
  return row?.payload?.group_id || null;
}

export default function V5ReviewSheet({ open, onClose }) {
  const { refreshSummary } = useSummary();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [busyGroup, setBusyGroup] = useState(null);

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
      setBusyGroup(null);
      return;
    }
    loadSuggestions();
  }, [open, loadSuggestions]);

  const { grouped, ungrouped } = useMemo(() => {
    const groupedMap = new Map();
    const ungroupedRows = [];
    for (const row of rows) {
      const key = groupKey(row);
      if (key) {
        if (!groupedMap.has(key)) {
          groupedMap.set(key, []);
        }
        groupedMap.get(key).push(row);
      } else {
        ungroupedRows.push(row);
      }
    }
    return { grouped: groupedMap, ungrouped: ungroupedRows };
  }, [rows]);

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

  async function handleAcceptGroup(groupRows) {
    const key = groupKey(groupRows[0]);
    setBusyGroup(key);
    setError('');
    const ids = groupRows.map((row) => row.id);
    try {
      await Promise.all(ids.map((id) => v4API.suggestions.accept(id)));
      setRows((prev) => prev.filter((row) => !ids.includes(row.id)));
      refreshSummary();
    } catch (err) {
      setError(friendlyApiError(err, 'Could not accept all suggestions.'));
    } finally {
      setBusyGroup(null);
    }
  }

  function renderCard(row, options = {}) {
    const evidence = row.reason || row.payload?.evidence;
    const sourceTitle = row.source_note_title;
    const disabled = busyId === row.id || options.disabled;
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
              {Array.from(grouped.entries()).map(([key, groupRows]) => {
                const count = groupRows.length;
                const disabled = busyGroup === key;
                return (
                  <li key={key} className={styles.group}>
                    <div className={styles.groupHeader}>
                      <span className={styles.groupTitle}>
                        {count} action {count === 1 ? 'item' : 'items'} from this note
                      </span>
                      <button
                        type="button"
                        className={styles.buttonPrimary}
                        disabled={disabled}
                        onClick={() => handleAcceptGroup(groupRows)}
                      >
                        Accept all
                      </button>
                    </div>
                    <ul className={styles.groupList}>
                      {groupRows.map((row) => renderCard(row, { disabled }))}
                    </ul>
                  </li>
                );
              })}
              {ungrouped.map((row) => renderCard(row))}
            </ul>
          )}
        </div>
      </div>
    </Sheet>
  );
}
