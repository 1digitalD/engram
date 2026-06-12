/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Pencil, RefreshCw, RotateCcw, X } from 'lucide-react';
import { v4API } from '../api/v4Client';
import CardActions from '../components/CardActions';
import MarkdownContent from '../components/MarkdownContent';
import MarkdownEditor from '../components/MarkdownEditor';
import styles from './V4Suggestions.module.css';

const ENTITY_TYPES = ['task', 'project', 'area', 'resource', 'person'];

function formatDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString();
}

function formatConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value) || value <= 0) return '';
  return `${Math.round(value * 100)}% confidence`;
}

function suggestionTitle(suggestion) {
  const payload = suggestion?.payload || {};
  return payload.title || suggestion?.suggestion_type || 'Suggestion';
}

function suggestionDetail(suggestion) {
  const payload = suggestion?.payload || {};
  if (suggestion.operation_type === 'link_existing') {
    return `Link to ${payload.target_type || 'entity'} · ${payload.relationship_type || 'related'}`;
  }
  return `${payload.type || suggestion.operation_type} · ${payload.status || 'review required'}`;
}

function sourceNotePath(entityId) {
  return `/notes/${entityId}`;
}

function formatAiStatus(value) {
  if (!value) return '';
  return String(value).replace(/_/g, ' ');
}

function NoteReviewCard({ note, loadedSuggestionCount, onReprocess, onResolve, onChanged, busy }) {
  const aiStatus = note.ai?.status || '';
  const expectedSuggestionCount = note.pending_suggestion_count || 0;
  const hasMissingSuggestionDetails = expectedSuggestionCount > loadedSuggestionCount;

  return (
    <li className={`${styles.reviewCard} cardActionsParent`}>
      <CardActions entity={note} onChanged={onChanged} />
      <div className={styles.cardBody}>
        <strong>{note.title || 'Untitled note'}</strong>
        <span className={styles.sourceNote}>
          source note · <Link to={sourceNotePath(note.id)}>open note</Link>
        </span>
        <div className={styles.cardMeta}>
          {aiStatus ? <span className={styles.metaPill}>AI · {formatAiStatus(aiStatus)}</span> : null}
          {expectedSuggestionCount > 0 ? (
            <span className={styles.metaPill}>
              {expectedSuggestionCount} suggestion{expectedSuggestionCount === 1 ? '' : 's'}
            </span>
          ) : null}
          {formatConfidence(note.ai?.confidence) ? (
            <span className={styles.metaPill}>{formatConfidence(note.ai.confidence)}</span>
          ) : null}
          {note.updated_at ? (
            <span className={styles.metaPill}>updated · {formatDateTime(note.updated_at)}</span>
          ) : null}
        </div>
        {note.ai?.summary || note.ai?.entity_summary ? (
          <p className={styles.sourceSummary}>{note.ai.entity_summary || note.ai.summary}</p>
        ) : null}
        {note.content ? (
          <div className={styles.sourceExcerpt}>
            <MarkdownContent content={note.content} compact />
          </div>
        ) : null}
        {aiStatus === 'failed' ? (
          <p className={styles.reviewHint}>AI extraction failed. Re-run extraction to move this note forward.</p>
        ) : null}
        {aiStatus === 'pending' ? (
          <p className={styles.reviewHint}>AI is still marked pending. Re-run extraction if this note appears stuck.</p>
        ) : null}
        {hasMissingSuggestionDetails ? (
          <p className={styles.reviewHint}>
            {expectedSuggestionCount - loadedSuggestionCount} linked suggestion
            {expectedSuggestionCount - loadedSuggestionCount === 1 ? '' : 's'} still need review but are not expanded below yet.
          </p>
        ) : null}
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.resolveButton}
          onClick={() => onResolve(note.id)}
          disabled={busy}
        >
          Mark reviewed
        </button>
        <button
          type="button"
          className={`${styles.iconButton} ${styles.reprocessButton}`}
          onClick={() => onReprocess(note.id)}
          disabled={busy}
          aria-label={`Re-run AI for ${note.title || 'note'}`}
          title="Re-run AI extraction"
        >
          <RotateCcw size={14} strokeWidth={2.2} aria-hidden="true" />
        </button>
      </div>
    </li>
  );
}

function SuggestionCard({ suggestion, onAccept, onDismiss, onUpdate, onReprocess, onResolveToExisting, busy }) {
  const isCreate = suggestion.operation_type === 'create_entity';
  const nearMatch = isCreate ? suggestion.payload?.near_match : null;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    title: suggestion.payload?.title || '',
    content: suggestion.payload?.content || '',
    type: suggestion.payload?.type || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSave() {
    setSaving(true);
    setError('');
    try {
      await onUpdate(suggestion.id, draft);
      setEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setDraft({
      title: suggestion.payload?.title || '',
      content: suggestion.payload?.content || '',
      type: suggestion.payload?.type || '',
    });
    setEditing(false);
    setError('');
  }

  return (
    <li className={`${styles.card} ${editing ? styles.cardEditing : ''}`}>
      {editing ? (
        <div className={styles.editForm}>
          <div className={styles.editRow}>
            <input
              className={styles.editInput}
              value={draft.title}
              onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
              placeholder="Title"
              aria-label="Title"
              autoFocus
            />
            <select
              className={styles.editSelect}
              value={draft.type}
              onChange={(e) => setDraft((d) => ({ ...d, type: e.target.value }))}
              aria-label="Entity type"
            >
              {ENTITY_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <MarkdownEditor
            value={draft.content || ''}
            onChange={(val) => setDraft((d) => ({ ...d, content: val }))}
            placeholder="Description"
            minRows={3}
          />
          {error && <p className={styles.editError}>{error}</p>}
          <div className={styles.editActions}>
            <button
              type="button"
              className={styles.saveButton}
              onClick={handleSave}
              disabled={saving || !draft.title.trim()}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className={styles.cardBody}>
            <strong>{suggestionTitle(suggestion)}</strong>
            <span>{suggestionDetail(suggestion)}</span>
            <div className={styles.cardMeta}>
              {formatConfidence(suggestion.confidence) ? (
                <span className={styles.metaPill}>{formatConfidence(suggestion.confidence)}</span>
              ) : null}
              {suggestion.created_at ? (
                <span className={styles.metaPill}>suggested · {formatDateTime(suggestion.created_at)}</span>
              ) : null}
            </div>
            {suggestion.source_note_title && (
              <span className={styles.sourceNote}>from · {suggestion.source_note_title}</span>
            )}
            {suggestion.reason && <p>{suggestion.reason}</p>}
            {nearMatch?.entity_id && (
              <div className={styles.nearMatchRow}>
                <span className={styles.nearMatchLabel}>
                  Looks like existing: <strong>{nearMatch.title || 'Untitled'}</strong>
                  {typeof nearMatch.score === 'number' ? ` (${Math.round(nearMatch.score * 100)}% similar)` : ''}
                </span>
                <button
                  type="button"
                  className={styles.nearMatchButton}
                  onClick={() => onResolveToExisting(suggestion.id)}
                  disabled={busy}
                  title={`Don't create — link the note to "${nearMatch.title}" instead`}
                >
                  Use existing
                </button>
              </div>
            )}
          </div>
          <div className={styles.actions}>
            {isCreate && (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.editButton}`}
                onClick={() => setEditing(true)}
                disabled={busy}
                aria-label="Edit"
                title="Edit"
              >
                <Pencil size={14} strokeWidth={2.2} aria-hidden="true" />
              </button>
            )}
            {suggestion.source_entity_id && (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.reprocessButton}`}
                onClick={() => onReprocess(suggestion.source_entity_id)}
                disabled={busy}
                aria-label="Re-run AI"
                title="Re-run AI extraction"
              >
                <RotateCcw size={14} strokeWidth={2.2} aria-hidden="true" />
              </button>
            )}
            <button
              type="button"
              className={`${styles.iconButton} ${styles.acceptButton}`}
              onClick={() => onAccept(suggestion.id)}
              disabled={busy}
              aria-label="Accept"
              title="Accept"
            >
              <Check size={16} strokeWidth={2.4} aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`${styles.iconButton} ${styles.dismissButton}`}
              onClick={() => onDismiss(suggestion.id)}
              disabled={busy}
              aria-label="Dismiss"
              title="Dismiss"
            >
              <X size={16} strokeWidth={2.4} aria-hidden="true" />
            </button>
          </div>
        </>
      )}
    </li>
  );
}

export default function V4Suggestions() {
  const [suggestions, setSuggestions] = useState([]);
  const [reviewNotes, setReviewNotes] = useState([]);
  const [sourceNotes, setSourceNotes] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');
  const [reconcileMessage, setReconcileMessage] = useState('');

  async function loadSuggestions(options = {}) {
    const { clearReconcileMessage = true } = options;
    if (clearReconcileMessage) {
      setReconcileMessage('');
    }
    setError('');
    setLoading(true);
    try {
      const [inbox, response] = await Promise.all([
        v4API.inbox({ limit: 100 }),
        v4API.suggestions.list({ status: 'pending' }),
      ]);
      const nextSuggestions = response.data || [];
      const nextReviewNotes = inbox.needs_review || [];
      setSuggestions(nextSuggestions);
      setReviewNotes(nextReviewNotes);

      const notesById = Object.fromEntries(nextReviewNotes.map((note) => [note.id, note]));
      const sourceIds = [...new Set(nextSuggestions.map((s) => s.source_entity_id).filter(Boolean))]
        .filter((sourceId) => !notesById[sourceId]);
      if (sourceIds.length > 0) {
        const noteResults = await Promise.allSettled(sourceIds.map((sourceId) => v4API.entities.get(sourceId)));
        const fetchedNotes = {};
        sourceIds.forEach((sourceId, index) => {
          const result = noteResults[index];
          if (result.status === 'fulfilled' && result.value?.data) {
            fetchedNotes[sourceId] = result.value.data;
          }
        });
        setSourceNotes({ ...notesById, ...fetchedNotes });
      } else {
        setSourceNotes(notesById);
      }
    } catch (err) {
      setError(err.message || 'Failed to load suggestions');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSuggestions();
  }, []);

  async function handleAccept(id) {
    if (busyId) return;
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.accept(id);
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || 'Failed to accept suggestion');
    } finally {
      setBusyId('');
    }
  }

  async function handleResolveToExisting(id) {
    if (busyId) return;
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.resolveToExisting(id);
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || 'Failed to resolve to existing entity');
    } finally {
      setBusyId('');
    }
  }

  async function handleDismiss(id) {
    if (busyId) return;
    setBusyId(id);
    setError('');
    try {
      await v4API.suggestions.dismiss(id);
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || 'Failed to dismiss suggestion');
    } finally {
      setBusyId('');
    }
  }

  async function handleUpdate(id, data) {
    const response = await v4API.suggestions.update(id, data);
    setSuggestions((current) =>
      current.map((s) => (s.id === id ? { ...s, payload: response.data.payload } : s))
    );
  }

  async function handleReprocess(entityId) {
    if (busyId) return;
    setBusyId(`reprocess-${entityId}`);
    setError('');
    try {
      await v4API.reprocess(entityId);
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || 'Failed to reprocess note');
      setLoading(false);
    } finally {
      setBusyId('');
    }
  }

  async function handleResolveReview(entityId) {
    if (busyId) return;
    setBusyId(`resolve-${entityId}`);
    setError('');
    try {
      await v4API.review.resolve(entityId);
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || 'Failed to resolve review');
    } finally {
      setBusyId('');
    }
  }

  async function handleBatch(groupKey, action) {
    if (busyId) return;
    setBusyId(`group-${groupKey}-${action}`);
    setError('');
    const groupSuggestions = groupedSuggestions.find((group) => group.key === groupKey)?.suggestions || [];
    try {
      for (const suggestion of groupSuggestions) {
        if (action === 'accept') {
          await v4API.suggestions.accept(suggestion.id);
        } else {
          await v4API.suggestions.dismiss(suggestion.id);
        }
      }
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || `Failed to ${action} suggestions`);
    } finally {
      setBusyId('');
    }
  }

  async function handleReconcile() {
    if (busyId || loading) return;
    setBusyId('reconcile');
    setError('');
    setReconcileMessage('');
    try {
      const response = await v4API.suggestions.reconcile({ limit: 200 });
      const expired = response.meta?.expired ?? response.data?.length ?? 0;
      setReconcileMessage(
        expired > 0
          ? `Expired ${expired} stale suggestion${expired === 1 ? '' : 's'}.`
          : 'No stale suggestions found.'
      );
      await loadSuggestions({ clearReconcileMessage: false });
    } catch (err) {
      setError(err.message || 'Failed to reconcile suggestions');
    } finally {
      setBusyId('');
    }
  }

  const groupedSuggestions = (() => {
    const grouped = new Map();
    suggestions.forEach((suggestion) => {
      const key = suggestion.source_entity_id || `ungrouped-${suggestion.id}`;
      const existing = grouped.get(key) || {
        key,
        sourceEntityId: suggestion.source_entity_id || null,
        sourceNote: suggestion.source_entity_id ? sourceNotes[suggestion.source_entity_id] : null,
        sourceTitle: suggestion.source_note_title || sourceNotes[suggestion.source_entity_id]?.title || 'Review queue',
        suggestions: [],
      };
      existing.sourceNote = existing.sourceEntityId ? (sourceNotes[existing.sourceEntityId] || existing.sourceNote) : null;
      existing.suggestions.push(suggestion);
      grouped.set(key, existing);
    });
    return [...grouped.values()];
  })();
  const suggestionCountsByNote = groupedSuggestions.reduce((counts, group) => {
    if (group.sourceEntityId) {
      counts[group.sourceEntityId] = group.suggestions.length;
    }
    return counts;
  }, {});
  const aiReviewNotes = reviewNotes.filter((note) => {
    const aiStatus = note.ai?.status;
    const expectedSuggestionCount = note.pending_suggestion_count || 0;
    const loadedSuggestionCount = suggestionCountsByNote[note.id] || 0;
    return aiStatus === 'pending' || aiStatus === 'failed' || expectedSuggestionCount > loadedSuggestionCount;
  });
  const totalReviewItems = reviewNotes.length;
  const aiPendingCount = reviewNotes.filter((note) => note.ai?.status === 'pending').length;
  const aiFailedCount = reviewNotes.filter((note) => note.ai?.status === 'failed').length;

  return (
    <main className={styles.suggestions}>
      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <h2>Review queue</h2>
            <p className={styles.panelIntro}>
              One place for stuck AI notes, failed extraction, and pending suggestions.
            </p>
          </div>
          <div className={styles.panelActions}>
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={handleReconcile}
              disabled={loading || !!busyId}
              aria-label="Reconcile stale suggestions"
              title="Reconcile stale suggestions"
            >
              Reconcile stale
            </button>
            <button
              type="button"
              className={styles.refreshButton}
              onClick={loadSuggestions}
              disabled={loading || !!busyId}
              aria-label="Refresh suggestions"
              title="Refresh"
            >
              <RefreshCw size={12} strokeWidth={2.2} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </div>
        <section className={styles.summaryGrid} aria-label="Review queue summary">
          <div className={styles.summaryCard}>
            <strong>{totalReviewItems}</strong>
            <span>notes needing review</span>
          </div>
          <div className={styles.summaryCard}>
            <strong>{suggestions.length}</strong>
            <span>pending suggestions</span>
          </div>
          <div className={styles.summaryCard}>
            <strong>{aiPendingCount}</strong>
            <span>AI pending</span>
          </div>
          <div className={styles.summaryCard}>
            <strong>{aiFailedCount}</strong>
            <span>AI failed</span>
          </div>
        </section>
        {error && <div className={styles.error}>{error}</div>}
        {reconcileMessage && <div className={styles.notice}>{reconcileMessage}</div>}
        {loading ? (
          <p>Loading review queue...</p>
        ) : (
          <div className={styles.reviewStack}>
            <section className={styles.subpanel}>
              <header className={styles.subpanelHeader}>
                <h3>AI attention</h3>
                <span className={styles.countPill}>{aiReviewNotes.length}</span>
              </header>
              {aiReviewNotes.length === 0 ? (
                <p className={styles.emptyState}>No stuck AI notes right now.</p>
              ) : (
                <ul className={styles.groupStack}>
                  {aiReviewNotes.map((note) => (
                    <NoteReviewCard
                      key={note.id}
                      note={note}
                      loadedSuggestionCount={suggestionCountsByNote[note.id] || 0}
                      onReprocess={handleReprocess}
                      onResolve={handleResolveReview}
                      onChanged={() => loadSuggestions({ clearReconcileMessage: false })}
                      busy={!!busyId}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className={styles.subpanel}>
              <header className={styles.subpanelHeader}>
                <h3>Pending suggestions</h3>
                <span className={styles.countPill}>{suggestions.length}</span>
              </header>
              {suggestions.length === 0 ? (
                <p className={styles.emptyState}>No pending suggestions.</p>
              ) : (
                <div className={styles.groupStack}>
                  {groupedSuggestions.map((group) => (
                    <section key={group.key} className={styles.groupCard}>
                      <header className={styles.groupHeader}>
                        <div className={styles.groupHeaderBody}>
                          <strong>{group.sourceNote?.title || group.sourceTitle}</strong>
                          {group.sourceEntityId ? (
                            <span className={styles.sourceNote}>
                              from note · <Link to={sourceNotePath(group.sourceEntityId)}>open source</Link>
                            </span>
                          ) : (
                            <span className={styles.sourceNote}>ungrouped review</span>
                          )}
                          <div className={styles.groupMeta}>
                            {group.sourceNote?.ai?.status ? (
                              <span className={styles.metaPill}>AI · {String(group.sourceNote.ai.status).replace(/_/g, ' ')}</span>
                            ) : null}
                            {formatConfidence(group.sourceNote?.ai?.confidence) ? (
                              <span className={styles.metaPill}>{formatConfidence(group.sourceNote.ai.confidence)}</span>
                            ) : null}
                            {group.sourceNote?.updated_at ? (
                              <span className={styles.metaPill}>updated · {formatDateTime(group.sourceNote.updated_at)}</span>
                            ) : null}
                          </div>
                          {group.sourceNote?.ai?.summary || group.sourceNote?.ai?.entity_summary ? (
                            <p className={styles.sourceSummary}>
                              {group.sourceNote.ai.entity_summary || group.sourceNote.ai.summary}
                            </p>
                          ) : null}
                          {group.sourceNote?.content ? (
                            <div className={styles.sourceExcerpt}>
                              <MarkdownContent content={group.sourceNote.content} compact />
                            </div>
                          ) : null}
                        </div>
                        <div className={styles.groupActions}>
                          <button
                            type="button"
                            className={styles.groupActionButton}
                            onClick={() => handleBatch(group.key, 'accept')}
                            disabled={!!busyId}
                          >
                            Accept all
                          </button>
                          <button
                            type="button"
                            className={`${styles.groupActionButton} ${styles.groupActionButtonDanger}`}
                            onClick={() => handleBatch(group.key, 'dismiss')}
                            disabled={!!busyId}
                          >
                            Dismiss all
                          </button>
                        </div>
                      </header>
                      <ul className={styles.list}>
                        {group.suggestions.map((suggestion) => (
                          <SuggestionCard
                            key={suggestion.id}
                            suggestion={suggestion}
                            onAccept={handleAccept}
                            onDismiss={handleDismiss}
                            onUpdate={handleUpdate}
                            onReprocess={handleReprocess}
                            onResolveToExisting={handleResolveToExisting}
                            busy={!!busyId}
                          />
                        ))}
                      </ul>
                    </section>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </section>
    </main>
  );
}
