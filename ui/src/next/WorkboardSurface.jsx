import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { createActionQueue } from './actionQueue';
import CommitmentItemRow from './CommitmentItemRow';
import { GroupCommitmentComposer } from './TypedAffordances';
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

function buildParams(group, filters) {
  const params = { group };
  if (filters.length > 0) params.state = filters;
  return params;
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
  const enqueueAction = useMemo(() => createActionQueue(), []);

  const loadBoard = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const payload = await v4API.workboard(buildParams(group, activeFilters));
      setBoard(payload || EMPTY_BOARD);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load workboard.'));
      if (!silent) setBoard(EMPTY_BOARD);
    } finally {
      if (!silent) setLoading(false);
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
    return enqueueAction(async () => {
      setError('');
      try {
        await action();
        setActionNote(message);
        await loadBoard({ silent: true });
        return true;
      } catch (err) {
        setError(friendlyApiError(err, 'Could not save affordance change.'));
        return false;
      }
    });
  }

  async function handleStatusChange(itemId, status) {
    return runAction('Status updated.', () => v4API.entities.update(itemId, { status }));
  }

  async function handleDueChange(itemId, dueDate) {
    return runAction('Due date updated.', () => v4API.entities.update(itemId, { due_at: dueDateToIso(dueDate) }));
  }

  async function handleFollowUpChange(itemId, followUpDate) {
    return runAction('Follow-up date updated.', () =>
      v4API.entities.update(itemId, { follow_up_at: dueDateToIso(followUpDate) }),
    );
  }

  async function handleMoveSpace(itemId, targetId) {
    return runAction('Moved to new space.', () =>
      v4API.entities.createLink(itemId, {
        target_id: targetId,
        relationship_type: 'parent',
        replace_existing: true,
        batch_summary: 'move commitment to new space',
      }),
    );
  }

  async function handleHandOwner(itemId, targetId) {
    return runAction('Handed to new owner.', () =>
      v4API.entities.createLink(itemId, {
        target_id: targetId,
        relationship_type: 'assigned_to',
        replace_existing: true,
        batch_summary: 'hand commitment to new owner',
      }),
    );
  }

  async function handleLogUpdate(itemId, content) {
    return runAction('Update logged.', () => v4API.activityUpdates.create(itemId, content));
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
  const commitmentHandlers = {
    onStatusChange: handleStatusChange,
    onDueChange: handleDueChange,
    onFollowUpChange: handleFollowUpChange,
    onMoveSpace: handleMoveSpace,
    onHandOwner: handleHandOwner,
    onLogUpdate: handleLogUpdate,
    onMarkDone: handleMarkDone,
  };

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
                        <Link to={`/spaces/${bucket.entity_id}`}>{bucket.label}</Link>
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
                  {bucket.items.map((item) => (
                    <CommitmentItemRow
                      key={item.id}
                      item={item}
                      people={people}
                      spaces={spaces}
                      group={group}
                      states={stateSummary(item)}
                      showNudge={Boolean(item.states?.waiting_on)}
                      {...commitmentHandlers}
                    />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
