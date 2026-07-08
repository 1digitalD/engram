import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { timelineGlyphType } from '../utils/timelineGlyphs';
import {
  briefStalenessLabel,
  buildSpaceBrief,
  eventAmendDetail,
  formatDossierDate,
  formatRelativeAge,
  formatTimelineStamp,
  openCommitmentsFromDetail,
  openQuestionsFromSuggestions,
  partitionCommitments,
} from './dossierUtils';
import { GroupCommitmentComposer, NudgeDraftAffordance, TaskAffordances } from './TypedAffordances';
import { SURFACE_LABELS } from './vocab';
import styles from './DossierSurface.module.css';

const PINNABLE_HEADER_FIELDS = [
  { key: 'status', label: 'status' },
  { key: 'due_at', label: 'finish line' },
  { key: 'title', label: 'title' },
];

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'ledger', label: 'Ledger' },
];

function actorLabel(actor) {
  if (!actor) return 'system';
  if (actor === 'user') return 'you';
  if (actor.startsWith('agent:')) return `✦ ${actor.slice('agent:'.length)}`;
  return actor;
}

function PinFieldChip({ field, label, value, pinned, onToggle }) {
  if (!value) return null;
  return (
    <span className={pinned ? styles.chipPinned : styles.chip}>
      {label}: {value}
      <button
        type="button"
        className={styles.pinButton}
        aria-label={pinned ? `Unpin ${label}` : `Pin ${label}`}
        aria-pressed={pinned}
        onClick={() => onToggle(field, pinned)}
      >
        {pinned ? '📌' : '○'}
      </button>
    </span>
  );
}

export default function DossierSurface() {
  const { spaceId } = useParams();
  const [activeTab, setActiveTab] = useState('overview');
  const [detail, setDetail] = useState(null);
  const [briefPayload, setBriefPayload] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [ledgerEvents, setLedgerEvents] = useState([]);
  const [people, setPeople] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [operatorPersonId, setOperatorPersonId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionNote, setActionNote] = useState('');

  const loadDossier = useCallback(async () => {
    if (!spaceId) return;
    setLoading(true);
    setError('');
    try {
      const [
        detailResponse,
        briefResponse,
        timelineResponse,
        decisionsResponse,
        suggestionsResponse,
        eventsResponse,
        projects,
        areas,
        peoplePayload,
      ] = await Promise.all([
        v4API.entities.detail(spaceId),
        v4API.brief(),
        v4API.timeline({ thread_id: spaceId, limit: 40 }),
        v4API.decisions.list({ thread_id: spaceId }),
        v4API.suggestions.list({ status: 'pending' }),
        v4API.entities.events(spaceId),
        v4API.entities.list({ type: 'project' }),
        v4API.entities.list({ type: 'area' }),
        v4API.entities.list({ type: 'person' }),
      ]);

      setDetail(detailResponse);
      setBriefPayload(briefResponse);
      setTimeline(timelineResponse?.events || []);
      setDecisions(decisionsResponse?.data || []);
      setLedgerEvents(eventsResponse?.data || []);

      const tasks = openCommitmentsFromDetail(detailResponse);
      const taskIds = new Set(tasks.map((task) => task.id));
      setQuestions(openQuestionsFromSuggestions(suggestionsResponse?.data, spaceId, taskIds));

      const nextSpaces = [...(projects?.data || []), ...(areas?.data || [])].sort((left, right) =>
        left.title.localeCompare(right.title),
      );
      setSpaces(nextSpaces);
      setPeople((peoplePayload?.data || []).slice().sort((left, right) => left.title.localeCompare(right.title)));

      const operator = (peoplePayload?.data || []).find((person) => person.is_owner || person.properties?.is_owner);
      setOperatorPersonId(operator?.id || null);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load dossier.'));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [spaceId]);

  useEffect(() => {
    loadDossier();
  }, [loadDossier]);

  const entity = detail?.entity;
  const pinnedFields = useMemo(() => new Set(entity?.pinned_fields || []), [entity?.pinned_fields]);
  const spaceBrief = useMemo(() => buildSpaceBrief(briefPayload, detail), [briefPayload, detail]);
  const commitments = useMemo(() => openCommitmentsFromDetail(detail), [detail]);
  const { mine, waitingOn } = useMemo(
    () => partitionCommitments(commitments, operatorPersonId),
    [commitments, operatorPersonId],
  );

  async function runAction(message, action) {
    setError('');
    try {
      await action();
      setActionNote(message);
      await loadDossier();
    } catch (err) {
      setError(friendlyApiError(err, 'Could not save change.'));
    }
  }

  async function handlePinToggle(field, pinned) {
    await runAction(pinned ? 'Field unpinned.' : 'Field pinned.', () =>
      pinned ? v4API.entities.unpin(entity.id, field) : v4API.entities.pin(entity.id, field),
    );
  }

  async function handleStatusChange(itemId, status) {
    await runAction('Status updated.', () => v4API.entities.update(itemId, { status }));
  }

  async function handleDueChange(itemId, dueDate) {
    const dueAt = dueDate ? `${dueDate}T12:00:00Z` : null;
    await runAction('Due date updated.', () => v4API.entities.update(itemId, { due_at: dueAt }));
  }

  async function handleMoveSpace(itemId, targetId) {
    await runAction('Moved to new space.', () =>
      v4API.entities.createLink(itemId, {
        target_id: targetId,
        relationship_type: 'parent',
        replace_existing: true,
        batch_summary: 'move commitment to new space',
      }),
    );
  }

  async function handleHandOwner(itemId, targetId) {
    await runAction('Handed to new owner.', () =>
      v4API.entities.createLink(itemId, {
        target_id: targetId,
        relationship_type: 'assigned_to',
        replace_existing: true,
        batch_summary: 'hand commitment to new owner',
      }),
    );
  }

  async function handleLogUpdate(itemId, content) {
    await runAction('Update logged.', () => v4API.activityUpdates.create(itemId, content));
  }

  async function handleMarkDone(itemId) {
    await runAction('Commitment marked done.', () => v4API.entities.update(itemId, { status: 'done' }));
  }

  async function handleAddCommitment(title) {
    await runAction('Commitment added.', async () => {
      const created = await v4API.entities.create({ type: 'task', title, status: 'open' });
      const taskId = created?.data?.id;
      if (!taskId) return;
      await v4API.entities.createLink(taskId, {
        target_id: spaceId,
        relationship_type: 'parent',
      });
    });
  }

  if (loading) {
    return (
      <section className={styles.surface} aria-label="Space dossier">
        <p className={styles.empty}>Loading dossier…</p>
      </section>
    );
  }

  if (!entity) {
    return (
      <section className={styles.surface} aria-label="Space dossier">
        <p className={styles.error} role="alert">
          {error || 'Space not found.'}
        </p>
        <Link to="/next/spaces">Back to Spaces</Link>
      </section>
    );
  }

  return (
    <section className={styles.surface} aria-label="Space dossier">
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <div>
            <h1 className={styles.title}>{entity.title}</h1>
            <div className={styles.metaRow}>
              {PINNABLE_HEADER_FIELDS.map(({ key, label }) => {
                const rawValue = key === 'due_at' ? entity.due_at : entity[key];
                const displayValue =
                  key === 'due_at'
                    ? rawValue
                      ? formatDossierDate(rawValue)
                      : null
                    : rawValue;
                return (
                  <PinFieldChip
                    key={key}
                    field={key}
                    label={label}
                    value={displayValue}
                    pinned={pinnedFields.has(key)}
                    onToggle={handlePinToggle}
                  />
                );
              })}
              <span className={styles.chipAi}>
                ✦ Brief {briefStalenessLabel(spaceBrief.generatedAt)}
              </span>
            </div>
          </div>
          <Link to="/next/spaces" className={styles.chip}>
            ← {SURFACE_LABELS.spaces}
          </Link>
        </div>
      </header>

      <div className={styles.tabRow} role="tablist" aria-label="Dossier views">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={activeTab === tab.key ? styles.tabActive : styles.tab}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {actionNote ? (
        <p className={styles.actionNote} aria-live="polite">
          {actionNote}
        </p>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {activeTab === 'overview' ? (
        <div className={styles.layout}>
          <div className={styles.column}>
            <section aria-labelledby="dossier-brief-label">
              <h2 id="dossier-brief-label" className={styles.sectionTitle}>
                The brief
              </h2>
              <div className={styles.panelAi}>
                <p className={styles.panelCopy}>{spaceBrief.narrative}</p>
                <p className={styles.panelMeta}>
                  {spaceBrief.model ? `Model: ${spaceBrief.model}` : 'Heuristic brief'}
                  {spaceBrief.fromCache ? ' · cached' : ''}
                </p>
              </div>
            </section>

            <section aria-labelledby="dossier-decisions-label">
              <h2 id="dossier-decisions-label" className={styles.sectionTitle}>
                Decisions
              </h2>
              <div className={styles.panel}>
                {decisions.length === 0 ? (
                  <p className={styles.empty}>No decisions recorded for this Space yet.</p>
                ) : (
                  <ul className={styles.list}>
                    {decisions.map((decision) => (
                      <li key={decision.id} className={styles.listItem}>
                        <p className={styles.itemTitle}>
                          {decision.superseded_by ? <s>{decision.statement}</s> : decision.statement}
                        </p>
                        <p className={styles.itemMeta}>
                          {actorLabel(decision.decided_by)} · {formatDossierDate(decision.decided_at)}
                          {decision.context ? ` · ${decision.context}` : ''}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>

            <section aria-labelledby="dossier-commitments-label">
              <h2 id="dossier-commitments-label" className={styles.sectionTitle}>
                Open commitments
              </h2>
              <div className={styles.panel}>
                <GroupCommitmentComposer label={entity.title} onSubmit={handleAddCommitment} />
                {mine.length === 0 && waitingOn.length === 0 ? (
                  <p className={styles.empty}>No open commitments in this Space.</p>
                ) : (
                  <>
                    {mine.length > 0 ? (
                      <>
                        <h3 className={styles.sectionTitle}>Yours</h3>
                        <ul className={styles.list}>
                          {mine.map((task) => (
                            <li key={task.id} className={styles.listItem}>
                              <p className={styles.itemTitle}>{task.title}</p>
                              <p className={styles.itemMeta}>
                                {task.status} · due {formatDossierDate(task.due_at) || 'unset'}
                              </p>
                              <TaskAffordances
                                item={{ ...task, space: { id: spaceId, title: entity.title } }}
                                people={people}
                                spaces={spaces}
                                onStatusChange={handleStatusChange}
                                onDueChange={handleDueChange}
                                onMoveSpace={handleMoveSpace}
                                onHandOwner={handleHandOwner}
                                onLogUpdate={handleLogUpdate}
                                onMarkDone={handleMarkDone}
                              />
                            </li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                    {waitingOn.length > 0 ? (
                      <>
                        <h3 className={styles.sectionTitle}>Waiting on others</h3>
                        <ul className={styles.list}>
                          {waitingOn.map((task) => (
                            <li key={task.id} className={styles.listItem}>
                              <p className={styles.itemTitle}>
                                {task.owner?.title ? `${task.owner.title} — ` : ''}
                                {task.title}
                              </p>
                              <p className={styles.itemMeta}>
                                {task.status} · {formatRelativeAge(task.updated_at || task.created_at)} quiet
                              </p>
                              <NudgeDraftAffordance item={{ ...task, space: { id: spaceId, title: entity.title } }} />
                            </li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                  </>
                )}
              </div>
            </section>

            <section aria-labelledby="dossier-questions-label">
              <h2 id="dossier-questions-label" className={styles.sectionTitle}>
                Open questions
              </h2>
              <div className={styles.panel}>
                {questions.length === 0 ? (
                  <p className={styles.empty}>No open questions for this Space.</p>
                ) : (
                  <ul className={styles.list}>
                    {questions.map((item) => (
                      <li key={item.id} className={styles.listItem}>
                        <p className={styles.itemTitle}>
                          {item.payload?.question || item.reason || item.payload?.statement || 'Open question'}
                        </p>
                        {item.source_note_title ? (
                          <p className={styles.itemMeta}>From {item.source_note_title}</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          </div>

          <div className={styles.column}>
            <section aria-labelledby="dossier-spine-label">
              <h2 id="dossier-spine-label" className={styles.sectionTitle}>
                Spine
              </h2>
              {timeline.length === 0 ? (
                <p className={styles.empty}>Nothing on the Spine yet.</p>
              ) : (
                <div className={styles.spine}>
                  {timeline.map((event) => {
                    const isAi = event.actor?.startsWith('agent:');
                    return (
                      <article
                        key={event.id}
                        className={`${styles.spineEvent} ${isAi ? styles.spineEventAi : ''}`}
                      >
                        <div className={styles.panel}>
                          <div className={styles.eventRow}>
                            <span className={isAi ? styles.actorAi : styles.actor}>{actorLabel(event.actor)}</span>
                            <span className={styles.itemMeta}>{formatTimelineStamp(event.occurred_at)}</span>
                            <span className={styles.itemMeta} aria-hidden="true">
                              {timelineGlyphType(event, { defaultEntityType: event.entity_type })}
                            </span>
                          </div>
                          <p className={styles.panelCopy}>{event.narration}</p>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </div>
      ) : (
        <section aria-labelledby="dossier-ledger-label">
          <h2 id="dossier-ledger-label" className={styles.sectionTitle}>
            Ledger — {entity.title}
          </h2>
          {ledgerEvents.length === 0 ? (
            <p className={styles.empty}>No Ledger events for this Space yet.</p>
          ) : (
            <div className={styles.ledgerList}>
              {ledgerEvents.map((event) => {
                const amend = eventAmendDetail(event);
                const isAi = event.actor?.startsWith('agent:');
                return (
                  <article key={event.id} className={styles.ledgerItem}>
                    <div className={styles.eventRow}>
                      <span className={isAi ? styles.actorAi : styles.actor}>{actorLabel(event.actor)}</span>
                      <span className={styles.itemMeta}>{formatTimelineStamp(event.created_at)}</span>
                      <span className={styles.itemMeta}>{event.event_type}</span>
                    </div>
                    <p className={styles.panelCopy}>{event.narration}</p>
                    {event.reason ? <p className={styles.itemMeta}>Reason: {event.reason}</p> : null}
                    {amend ? (
                      <ul className={styles.list}>
                        {amend.map((change) => (
                          <li key={change.field} className={styles.amendDetail}>
                            {change.field}: {String(change.from ?? '—')} → {String(change.to ?? '—')}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}
    </section>
  );
}
