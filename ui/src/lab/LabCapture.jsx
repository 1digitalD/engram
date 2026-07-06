import { useEffect, useMemo, useState } from 'react';
import Sheet from '../components/Sheet';
import { v4API, friendlyApiError } from '../api/v4Client';
import { formatSuggestionType, suggestionTitle } from '../views/V5ReviewSheet';
import styles from './LabCapture.module.css';

export function formatAppliedChangeLabel(change) {
  if (!change) return 'Change';
  switch (change.type) {
    case 'entity_created':
      return `Created ${change.entity_type || 'entity'}: ${change.title || 'Untitled'}`;
    case 'entity_updated':
      return `Updated ${change.entity_type || 'entity'}: ${change.title || 'Untitled'}`;
    case 'relationship_added':
      return `Linked ${change.relationship_type || 'related'}${change.matched_entity?.title ? ` → ${change.matched_entity.title}` : ''}`;
    case 'activity_update_added':
      return `Added update${change.matched_entity?.title ? ` on ${change.matched_entity.title}` : ''}`;
    case 'title_updated':
      return `Set title: ${change.title || 'Untitled'}`;
    case 'summary_updated':
      return 'Updated note summary';
    case 'tag_added':
      return `Tagged: ${change.tag || 'tag'}`;
    default:
      return change.type?.replace(/_/g, ' ') || 'Change';
  }
}

export function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return `${Math.round(Number(value) * 100)}%`;
}

export function captureEventLabel(event) {
  if (!event) return 'Change';
  const value = event.new_value || {};
  switch (event.event_type) {
    case 'created':
      return `Created ${value.type || 'entity'}: ${value.title || 'Untitled'}`;
    case 'ai_updated':
      return `Updated ${Object.keys(value).join(', ') || 'fields'}`;
    case 'relationship_added':
      return `Linked ${value.relationship_type || 'related'}`;
    case 'activity_update_added':
      return 'Added activity update';
    default:
      return event.event_type?.replace(/_/g, ' ') || 'Change';
  }
}

function AppliedChangeCard({ change }) {
  const confidence = formatConfidence(change.match_confidence ?? change.confidence);
  const reason = change.reason || change.matched_entity?.title;
  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        <h3 className={styles.itemTitle}>{formatAppliedChangeLabel(change)}</h3>
        <span className={styles.itemType}>{change.type?.replace(/_/g, ' ')}</span>
      </div>
      {reason ? <p className={styles.itemReason}>{reason}</p> : null}
      {confidence ? <p className={styles.itemMeta}>Confidence: {confidence}</p> : null}
    </li>
  );
}

function SuggestionCard({
  suggestion,
  busy,
  onAccept,
  onDismiss,
  onResolve,
}) {
  const confidence = formatConfidence(suggestion.match_confidence ?? suggestion.confidence);
  const reason = suggestion.reason || suggestion.payload?.evidence;
  const nearMatch = suggestion.matched_entity || suggestion.payload?.near_match;
  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        <h3 className={styles.itemTitle}>{suggestionTitle(suggestion)}</h3>
        <span className={styles.itemType}>{formatSuggestionType(suggestion.suggestion_type)}</span>
      </div>
      {reason ? <p className={styles.itemReason}>{reason}</p> : null}
      {nearMatch?.title ? (
        <p className={styles.itemMeta}>
          Near match:
          {' '}
          {nearMatch.title}
          {nearMatch.score || suggestion.match_confidence
            ? ` (${formatConfidence(nearMatch.score ?? suggestion.match_confidence)})`
            : ''}
        </p>
      ) : null}
      {confidence ? <p className={styles.itemMeta}>Confidence: {confidence}</p> : null}
      <div className={styles.itemActions}>
        <button
          type="button"
          className={styles.buttonSecondary}
          disabled={busy}
          onClick={() => onDismiss(suggestion.id)}
        >
          Dismiss
        </button>
        {nearMatch?.id || nearMatch?.entity_id ? (
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => onResolve(suggestion.id, nearMatch.id || nearMatch.entity_id)}
          >
            Use match
          </button>
        ) : null}
        <button
          type="button"
          className={styles.buttonPrimary}
          disabled={busy}
          onClick={() => onAccept(suggestion.id)}
        >
          Accept
        </button>
      </div>
    </li>
  );
}

function ReceiptEventCard({ event, busy, onUndo }) {
  const reverted = Boolean(event.reverted_at);
  return (
    <li className={styles.item}>
      <div className={styles.itemHead}>
        <h3 className={styles.itemTitle}>{captureEventLabel(event)}</h3>
        <span className={styles.itemType}>{event.event_type?.replace(/_/g, ' ')}</span>
      </div>
      {event.reason ? <p className={styles.itemReason}>{event.reason}</p> : null}
      {formatConfidence(event.confidence) ? (
        <p className={styles.itemMeta}>Confidence: {formatConfidence(event.confidence)}</p>
      ) : null}
      <div className={styles.itemActions}>
        {reverted ? (
          <span className={styles.itemMeta}>Undone</span>
        ) : (
          <button
            type="button"
            className={styles.buttonGhost}
            disabled={busy}
            onClick={() => onUndo(event.id)}
          >
            Undo
          </button>
        )}
      </div>
    </li>
  );
}

export default function LabCapture({
  open,
  onClose,
  captureFn = v4API.capture,
}) {
  const [phase, setPhase] = useState('compose');
  const [content, setContent] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [receiptEvents, setReceiptEvents] = useState([]);

  useEffect(() => {
    if (!open) {
      setPhase('compose');
      setContent('');
      setBusy(false);
      setError('');
      setResult(null);
      setSuggestions([]);
      setReceiptEvents([]);
    }
  }, [open]);

  const appliedChanges = useMemo(
    () => result?.applied_changes || [],
    [result],
  );

  async function runCapture() {
    const trimmed = content.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError('');
    try {
      const payload = await captureFn({
        content: trimmed,
        source: 'lab',
        mode: 'auto',
      });
      setResult(payload);
      setSuggestions(payload?.suggestions || []);
      setPhase('review');
    } catch (err) {
      setError(friendlyApiError(err, 'Capture failed'));
    } finally {
      setBusy(false);
    }
  }

  async function loadReceipt(noteId) {
    const payload = await v4API.entities.captureChanges(noteId);
    setReceiptEvents(payload?.data || []);
  }

  async function goToReceipt() {
    if (!result?.source_note?.id || busy) return;
    setBusy(true);
    setError('');
    try {
      await loadReceipt(result.source_note.id);
      setPhase('receipt');
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load receipt'));
    } finally {
      setBusy(false);
    }
  }

  async function handleAccept(id) {
    setBusy(true);
    setError('');
    try {
      await v4API.suggestions.accept(id);
      setSuggestions((prev) => prev.filter((row) => row.id !== id));
    } catch (err) {
      setError(friendlyApiError(err, 'Could not accept suggestion'));
    } finally {
      setBusy(false);
    }
  }

  async function handleDismiss(id) {
    setBusy(true);
    setError('');
    try {
      await v4API.suggestions.dismiss(id);
      setSuggestions((prev) => prev.filter((row) => row.id !== id));
    } catch (err) {
      setError(friendlyApiError(err, 'Could not dismiss suggestion'));
    } finally {
      setBusy(false);
    }
  }

  async function handleResolve(id, targetId) {
    setBusy(true);
    setError('');
    try {
      await v4API.suggestions.resolveToExisting(id, targetId);
      setSuggestions((prev) => prev.filter((row) => row.id !== id));
    } catch (err) {
      setError(friendlyApiError(err, 'Could not resolve suggestion'));
    } finally {
      setBusy(false);
    }
  }

  async function handleUndo(eventId) {
    if (!result?.source_note?.id || busy) return;
    setBusy(true);
    setError('');
    try {
      await v4API.events.revert(eventId);
      await loadReceipt(result.source_note.id);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not undo change'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onClose={onClose} ariaLabel="Lab capture">
      <div className={styles.sheet}>
        <header className={styles.header}>
          <h2 className={styles.title}>
            {phase === 'compose' && 'Capture'}
            {phase === 'review' && 'Review capture'}
            {phase === 'receipt' && 'Capture receipt'}
          </h2>
          <p className={styles.subtitle}>
            {phase === 'compose' && 'Type anything — you will see what was applied and why before closing.'}
            {phase === 'review' && 'Auto-applied items show match reasoning. Resolve ambiguous items inline.'}
            {phase === 'receipt' && 'Undo any auto-applied change from this capture.'}
          </p>
        </header>

        <div className={styles.body}>
          {phase === 'compose' ? (
            <textarea
              className={styles.textarea}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Type a note, task, or update…"
              aria-label="Capture text"
              disabled={busy}
            />
          ) : null}

          {phase === 'review' ? (
            <>
              {appliedChanges.length > 0 ? (
                <section className={styles.section} aria-label="Auto-applied changes">
                  <h3 className={styles.sectionLabel}>Auto-applied</h3>
                  <ul className={styles.itemList}>
                    {appliedChanges.map((change, index) => (
                      <AppliedChangeCard key={`${change.type}-${index}`} change={change} />
                    ))}
                  </ul>
                </section>
              ) : (
                <p className={styles.emptyState}>Nothing was auto-applied for this capture.</p>
              )}

              {suggestions.length > 0 ? (
                <section className={styles.section} aria-label="Suggestions to resolve">
                  <h3 className={styles.sectionLabel}>Needs your call</h3>
                  <ul className={styles.itemList}>
                    {suggestions.map((suggestion) => (
                      <SuggestionCard
                        key={suggestion.id}
                        suggestion={suggestion}
                        busy={busy}
                        onAccept={handleAccept}
                        onDismiss={handleDismiss}
                        onResolve={handleResolve}
                      />
                    ))}
                  </ul>
                </section>
              ) : null}
            </>
          ) : null}

          {phase === 'receipt' ? (
            <>
              <p className={styles.receiptSummary}>
                Saved note
                {result?.source_note?.title ? `: ${result.source_note.title}` : ''}
                .
                {' '}
                {receiptEvents.filter((event) => !event.reverted_at).length}
                {' '}
                change
                {receiptEvents.filter((event) => !event.reverted_at).length === 1 ? '' : 's'}
                {' '}
                can still be undone.
              </p>
              {receiptEvents.length > 0 ? (
                <ul className={styles.itemList} aria-label="Capture changes">
                  {receiptEvents.map((event) => (
                    <ReceiptEventCard
                      key={event.id}
                      event={event}
                      busy={busy}
                      onUndo={handleUndo}
                    />
                  ))}
                </ul>
              ) : (
                <p className={styles.emptyState}>No undoable changes were recorded for this note.</p>
              )}
            </>
          ) : null}

          {error ? <p className={styles.error} role="alert">{error}</p> : null}
        </div>

        <footer className={styles.footer}>
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={onClose}
            disabled={busy}
          >
            Close
          </button>
          {phase === 'compose' ? (
            <button
              type="button"
              className={styles.buttonPrimary}
              onClick={runCapture}
              disabled={!content.trim() || busy}
            >
              {busy ? 'Capturing…' : 'Capture'}
            </button>
          ) : null}
          {phase === 'review' ? (
            <button
              type="button"
              className={styles.buttonPrimary}
              onClick={goToReceipt}
              disabled={busy || suggestions.length > 0}
              title={suggestions.length > 0 ? 'Resolve or dismiss suggestions first' : undefined}
            >
              {busy ? 'Loading…' : 'View receipt'}
            </button>
          ) : null}
        </footer>
      </div>
    </Sheet>
  );
}
