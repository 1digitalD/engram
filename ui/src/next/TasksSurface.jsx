import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { createActionQueue } from './actionQueue';
import CommitmentItemRow from './CommitmentItemRow';
import { commitmentDetailPath } from './commitmentUtils';
import {
  DATE_PRESET_OPTIONS,
  DEFAULT_OPEN_STATUSES,
  ORDER_OPTIONS,
  SORT_OPTIONS,
  STATUS_FILTER_OPTIONS,
  buildTaskBoardParams,
  defaultOrderForSort,
} from './tasksBoardUtils';
import { SURFACE_LABELS } from './vocab';
import styles from './TasksSurface.module.css';

const EMPTY_BOARD = { data: { groups: [] }, meta: { counts: { by_status: {} }, total: 0 } };

function dueDateToIso(dateValue) {
  if (!dateValue) return null;
  return `${dateValue}T12:00:00Z`;
}

export default function TasksSurface() {
  const [activeStatuses, setActiveStatuses] = useState(DEFAULT_OPEN_STATUSES);
  const [assignee, setAssignee] = useState('');
  const [duePreset, setDuePreset] = useState('any');
  const [followUpPreset, setFollowUpPreset] = useState('any');
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState('desc');
  const [board, setBoard] = useState(EMPTY_BOARD);
  const [people, setPeople] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionNote, setActionNote] = useState('');
  const [statusBeforeDone, setStatusBeforeDone] = useState({});
  const enqueueAction = useMemo(() => createActionQueue(), []);

  const boardParams = useMemo(
    () =>
      buildTaskBoardParams({
        statuses: activeStatuses,
        assignee: assignee || undefined,
        duePreset,
        followUpPreset,
        sort,
        order,
      }),
    [activeStatuses, assignee, duePreset, followUpPreset, sort, order],
  );

  const loadBoard = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const payload = await v4API.taskBoard(boardParams);
      setBoard(payload || EMPTY_BOARD);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load tasks.'));
      if (!silent) setBoard(EMPTY_BOARD);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [boardParams]);

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

  function toggleStatus(statusKey) {
    setActiveStatuses((current) => {
      if (current.includes(statusKey)) {
        const next = current.filter((value) => value !== statusKey);
        return next.length > 0 ? next : current;
      }
      return [...current, statusKey];
    });
  }

  function handleSortChange(nextSort) {
    setSort(nextSort);
    setOrder(defaultOrderForSort(nextSort));
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
        setError(friendlyApiError(err, 'Could not save task change.'));
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
    return runAction('Moved to new project.', () =>
      v4API.entities.createLink(itemId, {
        target_id: targetId,
        relationship_type: 'parent',
        replace_existing: true,
        batch_summary: 'move commitment to new space',
      }),
    );
  }

  async function handleHandOwner(itemId, targetId) {
    return runAction('Assignee updated.', () =>
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
    await runAction('Task marked done.', () => v4API.entities.update(itemId, { status: 'done' }));
  }

  async function handleToggleDone(itemId, checked, currentStatus) {
    if (checked && currentStatus !== 'done') {
      setStatusBeforeDone((current) => ({ ...current, [itemId]: currentStatus }));
    }
    const restoreStatus = statusBeforeDone[itemId] || 'open';
    const nextStatus = checked ? 'done' : restoreStatus;
    await runAction(checked ? 'Task marked done.' : 'Task reopened.', () =>
      v4API.entities.update(itemId, { status: nextStatus }),
    );
  }

  const statusCounts = board?.meta?.counts?.by_status || {};
  const groups = board?.data?.groups || [];
  const commitmentHandlers = {
    onStatusChange: handleStatusChange,
    onDueChange: handleDueChange,
    onFollowUpChange: handleFollowUpChange,
    onMoveSpace: handleMoveSpace,
    onHandOwner: handleHandOwner,
    onLogUpdate: handleLogUpdate,
    onMarkDone: handleMarkDone,
    onToggleDone: handleToggleDone,
  };

  return (
    <section className={styles.surface} aria-label={SURFACE_LABELS.tasks}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{SURFACE_LABELS.tasks}</h1>
          <p className={styles.subtitle}>All commitments grouped by project, with filters for status, assignee, and dates.</p>
        </div>
      </header>

      <div className={styles.filterRow} role="group" aria-label="Filter tasks by status">
        {STATUS_FILTER_OPTIONS.map((filter) => {
          const count = statusCounts[filter.key] || 0;
          const active = activeStatuses.includes(filter.key);
          return (
            <button
              key={filter.key}
              type="button"
              className={active ? styles.filterChipActive : styles.filterChip}
              aria-pressed={active}
              onClick={() => toggleStatus(filter.key)}
            >
              <span>{filter.label}</span>
              <span className={styles.filterCount}>{count}</span>
            </button>
          );
        })}
      </div>

      <div className={styles.controlRow}>
        <label className={styles.controlField}>
          <span className={styles.controlLabel}>Assignee</span>
          <select
            className={styles.controlSelect}
            aria-label="Filter tasks by assignee"
            value={assignee}
            onChange={(event) => setAssignee(event.target.value)}
          >
            <option value="">All</option>
            <option value="unassigned">Unassigned</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.title}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.controlField}>
          <span className={styles.controlLabel}>Due</span>
          <select
            className={styles.controlSelect}
            aria-label="Filter tasks by due date"
            value={duePreset}
            onChange={(event) => setDuePreset(event.target.value)}
          >
            {DATE_PRESET_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.controlField}>
          <span className={styles.controlLabel}>Follow-up</span>
          <select
            className={styles.controlSelect}
            aria-label="Filter tasks by follow-up date"
            value={followUpPreset}
            onChange={(event) => setFollowUpPreset(event.target.value)}
          >
            {DATE_PRESET_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.controlField}>
          <span className={styles.controlLabel}>Sort</span>
          <select
            className={styles.controlSelect}
            aria-label="Sort tasks"
            value={sort}
            onChange={(event) => handleSortChange(event.target.value)}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.controlField}>
          <span className={styles.controlLabel}>Order</span>
          <select
            className={styles.controlSelect}
            aria-label="Sort order"
            value={order}
            onChange={(event) => setOrder(event.target.value)}
          >
            {ORDER_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
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
        {loading ? <p className={styles.empty}>Loading tasks…</p> : null}
        {!loading && groups.length === 0 ? <p className={styles.empty}>No tasks match these filters.</p> : null}

        {!loading ? (
          <div className={styles.groupList}>
            {groups.map((bucket) => (
              <section key={bucket.key} className={styles.groupCard}>
                <div className={styles.groupHeader}>
                  <div>
                    <h2 className={styles.groupTitle}>
                      {bucket.entity_id ? (
                        <Link to={`/spaces/${bucket.entity_id}`}>{bucket.label}</Link>
                      ) : (
                        bucket.label
                      )}
                    </h2>
                    <p className={styles.groupMeta}>{bucket.counts?.total || 0} tasks</p>
                  </div>
                </div>

                <ul className={styles.itemList}>
                  {bucket.items.map((item) => (
                    <CommitmentItemRow
                      key={item.id}
                      item={item}
                      people={people}
                      spaces={spaces}
                      group="space"
                      titleHref={commitmentDetailPath(item.id)}
                      showCheckbox
                      showCreatedAge
                      expandableUpdate
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
