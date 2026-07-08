import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { GroupCommitmentComposer, TaskAffordances } from './TypedAffordances';
import { SURFACE_LABELS } from './vocab';
import styles from './WorkboardSurface.module.css';

const FILTERS = [
  { key: 'mine', label: 'Mine' },
  { key: 'waiting_on', label: 'Waiting on' },
  { key: 'overdue', label: 'Overdue' },
  { key: 'stale', label: 'Stale' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'at_risk', label: 'At risk' },
];

const GROUP_OPTIONS = [
  { key: 'space', label: 'Space' },
  { key: 'person', label: 'Person' },
];

const EMPTY_BOARD = { data: { groups: [] }, meta: { counts: {}, total: 0 } };

function formatDueDate(value) {
  if (!value) return 'No due date';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'No due date';
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(parsed);
}

function buildParams(group, filters) {
  const params = { group };
  if (filters.length > 0) params.state = filters;
  return params;
}

function itemMeta(item, group) {
  const parts = [item.status || 'open'];
  if (group === 'space' && item.owner?.title) parts.push(item.owner.title);
  if (group === 'person' && item.space?.title) parts.push(item.space.title);
  parts.push(`Due ${formatDueDate(item.due_at)}`);
  return parts.join(' · ');
}

function stateSummary(item) {
  return FILTERS.filter(({ key }) => item.states?.[key]).map(({ label }) => label);
}

function dueDateToIso(dateValue) {
  if (!dateValue) return null;
  return `${dateValue}T12:00:00Z`;
}

export default function WorkboardSurface() {
  const [group, setGroup] = useState('space');
  const [activeFilters, setActiveFilters] = useState([]);
  const [board, setBoard] = useState(EMPTY_BOARD);
  const [people, setPeople] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionNote, setActionNote] = useState('');

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await v4API.workboard(buildParams(group, activeFilters));
      setBoard(payload || EMPTY_BOARD);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load workboard.'));
      setBoard(EMPTY_BOARD);
    } finally {
      setLoading(false);
    }
  }, [activeFilters, group]);

  const loadReferences = useCallback(async () => {
    try {
      const [projects, areas, peoplePayload] = await Promise.all([
        v4API.entities.list({ type: 'project' }),
        v4API.entities.list({ type: 'area' }),
        v4API.entities.list({ type: 'person' }),
      ]);
      const nextSpaces = [...(projects?.data || []), ...(areas?.data || [])].sort((left, right) =>
        left.title.localeCompare(right.title),
      );
      setSpaces(nextSpaces);
      setPeople((peoplePayload?.data || []).slice().sort((left, right) => left.title.localeCompare(right.title)));
    } catch (err) {
      setError((current) => current || friendlyApiError(err, 'Could not load affordance targets.'));
    }
  }, []);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  useEffect(() => {
    loadReferences();
  }, [loadReferences]);

  function toggleFilter(filterKey) {
    setActiveFilters((current) =>
      current.includes(filterKey) ? current.filter((value) => value !== filterKey) : [...current, filterKey],
    );
  }

  async function runAction(message, action) {
    setError('');
    try {
      await action();
      setActionNote(message);
      await loadBoard();
    } catch (err) {
      setError(friendlyApiError(err, 'Could not save affordance change.'));
    }
  }

  async function handleStatusChange(itemId, status) {
    await runAction('Status updated.', () => v4API.entities.update(itemId, { status }));
  }

  async function handleDueChange(itemId, dueDate) {
    await runAction('Due date updated.', () => v4API.entities.update(itemId, { due_at: dueDateToIso(dueDate) }));
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

  async function handleAddCommitment(bucket, title) {
    await runAction('Commitment added.', async () => {
      const created = await v4API.entities.create({ type: 'task', title, status: 'open' });
      const taskId = created?.data?.id;
      if (!taskId || !bucket.entity_id) return;
      if (bucket.kind === 'space') {
        await v4API.entities.createLink(taskId, {
          target_id: bucket.entity_id,
          relationship_type: 'parent',
        });
      } else if (bucket.kind === 'person') {
        await v4API.entities.createLink(taskId, {
          target_id: bucket.entity_id,
          relationship_type: 'assigned_to',
        });
      }
    });
  }

  const counts = board?.meta?.counts || {};
  const groups = board?.data?.groups || [];

  return (
    <section className={styles.surface} aria-label={SURFACE_LABELS.workboard}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{SURFACE_LABELS.workboard}</h1>
          <p className={styles.subtitle}>
            One board for every open commitment. Inline affordances write the same Ledger history as any other human
            edit.
          </p>
        </div>

        <div className={styles.groupToggle} aria-label="Group commitments">
          {GROUP_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className={group === option.key ? styles.toggleActive : styles.toggle}
              aria-pressed={group === option.key}
              onClick={() => setGroup(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className={styles.filterRow} role="group" aria-label="Filter commitments by state">
        {FILTERS.map((filter) => {
          const count = counts[filter.key] || 0;
          const active = activeFilters.includes(filter.key);
          return (
            <button
              key={filter.key}
              type="button"
              className={active ? styles.filterChipActive : styles.filterChip}
              aria-pressed={active}
              onClick={() => toggleFilter(filter.key)}
            >
              <span>{filter.label}</span>
              <span className={styles.filterCount}>{count}</span>
            </button>
          );
        })}
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

      <div className={styles.layout}>
        <div className={styles.boardColumn}>
          {loading ? <p className={styles.empty}>Loading workboard…</p> : null}
          {!loading && groups.length === 0 ? <p className={styles.empty}>No open commitments match this board slice.</p> : null}

          {!loading ? (
            <div className={styles.groupList}>
              {groups.map((bucket) => (
                <section key={bucket.key} className={styles.groupCard}>
                  <div className={styles.groupHeader}>
                    <div>
                      <h2 className={styles.groupTitle}>
                        {bucket.kind === 'space' && bucket.entity_id ? (
                          <Link to={`/next/spaces/${bucket.entity_id}`}>{bucket.label}</Link>
                        ) : (
                          bucket.label
                        )}
                      </h2>
                      <p className={styles.groupMeta}>{bucket.counts?.total || 0} commitments</p>
                    </div>
                    {bucket.at_risk?.flag ? <span className={styles.groupRiskFlag}>At risk</span> : null}
                  </div>

                  {bucket.at_risk?.reason ? <p className={styles.groupRiskReason}>{bucket.at_risk.reason}</p> : null}

                  <GroupCommitmentComposer label={bucket.label} onSubmit={(title) => handleAddCommitment(bucket, title)} />

                  <ul className={styles.itemList}>
                    {bucket.items.map((item) => {
                      const states = stateSummary(item);
                      return (
                        <li key={item.id} className={styles.item}>
                          <div className={styles.itemHeader}>
                            <div>
                              <h3 className={styles.itemTitle}>{item.title}</h3>
                              <p className={styles.itemMeta}>{itemMeta(item, group)}</p>
                            </div>
                            {item.at_risk?.flag ? <span className={styles.itemRiskFlag}>At risk</span> : null}
                          </div>

                          {states.length > 0 ? (
                            <div className={styles.stateList} aria-label={`${item.title} states`}>
                              {states.map((state) => (
                                <span key={state} className={styles.statePill}>
                                  {state}
                                </span>
                              ))}
                            </div>
                          ) : null}

                          {item.at_risk?.reason ? <p className={styles.reason}>{item.at_risk.reason}</p> : null}
                          {item.blocked_by?.length ? (
                            <p className={styles.blockedBy}>
                              Blocked by {item.blocked_by.map((blocker) => blocker.title).join(', ')}.
                            </p>
                          ) : null}

                          <TaskAffordances
                            item={item}
                            people={people}
                            spaces={spaces}
                            onStatusChange={handleStatusChange}
                            onDueChange={handleDueChange}
                            onMoveSpace={handleMoveSpace}
                            onHandOwner={handleHandOwner}
                            onLogUpdate={handleLogUpdate}
                            onMarkDone={handleMarkDone}
                            showNudge={Boolean(item.states?.waiting_on)}
                          />
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          ) : null}
        </div>

        <aside className={styles.rail}>
          <h2 className={styles.railTitle}>Themes</h2>
          <p className={styles.railCopy}>
            Theme signals will stack here once Phase 5 lands. For now, keep the rail in place so the board layout does
            not shift later.
          </p>
          <div className={styles.railPlaceholder}>No theme signals in this slice.</div>
        </aside>
      </div>
    </section>
  );
}
