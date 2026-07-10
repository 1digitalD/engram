import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { createActionQueue } from './actionQueue';
import {
  assignTaskToSpace,
  listSpacesForAssign,
  normalizeTaskOwner,
  taskSpaceRef,
} from './commitmentUtils';
import { formatDossierDate } from './dossierUtils';
import SpaceAssignPrompt from './SpaceAssignPrompt';
import { StatusBadge } from './statusTheme';
import { WorkboardItemAffordances } from './TypedAffordances';
import { SURFACE_LABELS } from './vocab';
import { sectionItems } from '../views/v5ThreadDetailUtils';
import styles from './CommitmentDetailSurface.module.css';

function dueDateToIso(dateValue) {
  if (!dateValue) return null;
  return `${dateValue}T12:00:00Z`;
}

export default function CommitmentDetailSurface() {
  const { taskId } = useParams();
  const [detail, setDetail] = useState(null);
  const [people, setPeople] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionNote, setActionNote] = useState('');
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignBusy, setAssignBusy] = useState(false);
  const [assignError, setAssignError] = useState('');
  const enqueueAction = useMemo(() => createActionQueue(), []);

  const loadReferences = useCallback(async () => {
    const [projects, areas, peoplePayload] = await Promise.all([
      v4API.entities.list({ type: 'project' }),
      v4API.entities.list({ type: 'area' }),
      v4API.entities.list({ type: 'person' }),
    ]);
    const nextSpaces = listSpacesForAssign(projects, areas);
    setSpaces(nextSpaces);
    setPeople((peoplePayload?.data || []).slice().sort((left, right) => left.title.localeCompare(right.title)));
  }, []);

  const loadDetail = useCallback(async ({ silent = false } = {}) => {
    if (!taskId) return;
    if (!silent) setLoading(true);
    setError('');
    try {
      const payload = await v4API.entities.detail(taskId);
      setDetail(payload || null);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load commitment.'));
      if (!silent) setDetail(null);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    loadReferences();
  }, [loadReferences]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const task = useMemo(() => normalizeTaskOwner(detail?.entity), [detail]);
  const space = useMemo(() => taskSpaceRef(task), [task]);
  const sourceNotes = useMemo(() => sectionItems(detail, 'source_notes'), [detail]);

  async function runAction(message, action) {
    return enqueueAction(async () => {
      setError('');
      try {
        await action();
        setActionNote(message);
        await loadDetail({ silent: true });
        return true;
      } catch (err) {
        setError(friendlyApiError(err, 'Could not save change.'));
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
    return runAction('Moved to new space.', () => assignTaskToSpace(v4API.entities, itemId, targetId));
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

  async function handleAssignSpace(spaceId) {
    if (!task?.id || !spaceId) return;
    setAssignBusy(true);
    setAssignError('');
    try {
      await assignTaskToSpace(v4API.entities, task.id, spaceId);
      setAssignOpen(false);
      setActionNote('Assigned to space.');
      await loadDetail({ silent: true });
    } catch (err) {
      setAssignError(friendlyApiError(err, 'Could not assign to space.'));
    } finally {
      setAssignBusy(false);
    }
  }

  if (loading) {
    return (
      <section className={styles.surface} aria-busy="true">
        <p className={styles.status}>Loading commitment…</p>
      </section>
    );
  }

  if (!task) {
    return (
      <section className={styles.surface}>
        <p className={styles.error} role="alert">{error || 'Commitment not found.'}</p>
        <Link to="/today">← {SURFACE_LABELS.today}</Link>
      </section>
    );
  }

  const workboardItem = {
    ...task,
    space: space ? { id: space.id, title: space.title } : null,
  };

  return (
    <section className={styles.surface} aria-label="Commitment detail">
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <div>
            <p className={styles.eyebrow}>Commitment</p>
            <h1 className={styles.title}>{task.title}</h1>
            <div className={styles.metaRow}>
              <StatusBadge status={task.status || 'open'} />
              {space ? (
                <Link to={`/spaces/${space.id}`} className={styles.chip}>
                  Space: {space.title}
                </Link>
              ) : (
                <button type="button" className={styles.chipButton} onClick={() => setAssignOpen(true)}>
                  Stand-alone · assign to space
                </button>
              )}
              {task.due_at ? <span className={styles.chip}>Due {formatDossierDate(task.due_at)}</span> : null}
              {task.follow_up_at ? (
                <span className={styles.chip}>Follow-up {formatDossierDate(task.follow_up_at)}</span>
              ) : null}
            </div>
          </div>
          <Link to="/today" className={styles.backLink}>
            ← {SURFACE_LABELS.today}
          </Link>
        </div>
        {actionNote ? <p className={styles.note}>{actionNote}</p> : null}
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </header>

      {task.content ? <p className={styles.body}>{task.content}</p> : null}

      <section className={styles.controls} aria-label="Commitment controls">
        <WorkboardItemAffordances
          item={workboardItem}
          people={people}
          spaces={spaces}
          group="space"
          onStatusChange={handleStatusChange}
          onDueChange={handleDueChange}
          onFollowUpChange={handleFollowUpChange}
          onMoveSpace={handleMoveSpace}
          onHandOwner={handleHandOwner}
          onLogUpdate={handleLogUpdate}
        />
      </section>

      {sourceNotes.length > 0 ? (
        <section className={styles.section} aria-label="Source notes">
          <h2 className={styles.sectionTitle}>Source notes</h2>
          <ul className={styles.sourceList}>
            {sourceNotes.map((item) => (
              <li key={item.entity?.id || item.id}>
                {item.entity?.title || item.title || 'Source note'}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <SpaceAssignPrompt
        taskTitle={task.title}
        spaces={spaces}
        open={assignOpen}
        busy={assignBusy}
        error={assignError}
        onClose={() => {
          setAssignOpen(false);
          setAssignError('');
        }}
        onAssign={handleAssignSpace}
      />
    </section>
  );
}
