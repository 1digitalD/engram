/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import styles from './V4Today.module.css';

const TASK_STATUSES = ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'];

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function shortDate(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function EntityRow({ entity, onQuickStatus }) {
  const due = shortDate(entity.due_at);
  const follow = shortDate(entity.follow_up_at);
  const isTask = entity.type === 'task';
  return (
    <li className={styles.row}>
      <Link to={entityPath(entity)} className={styles.rowLink}>
        <strong>{entity.title || 'Untitled'}</strong>
        {entity.content && (
          <MarkdownContent content={entity.content} compact />
        )}
      </Link>
      <div className={styles.metaRow}>
        <span className={styles.typePill}>{entity.type}</span>
        {isTask ? (
          <select
            className={styles.statusPillSelect}
            value={entity.status}
            onChange={(event) => onQuickStatus(entity.id, event.target.value)}
            aria-label={`Status of ${entity.title || 'task'}`}
          >
            {TASK_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        ) : (
          <span className={styles.statusPill}>{entity.status}</span>
        )}
        {entity.properties?.priority && (
          <span className={styles.priorityPill}>!{entity.properties.priority}</span>
        )}
        {due && <span className={styles.mutedMeta}>Due {due}</span>}
        {follow && <span className={styles.mutedMeta}>Follow-up {follow}</span>}
      </div>
    </li>
  );
}

function EntitySection({ title, items, onQuickStatus, accent }) {
  if (items.length === 0) return null;
  return (
    <section className={`${styles.panel} ${accent ? styles[`panel_${accent}`] : ''}`}>
      <header className={styles.panelHeader}>
        <h2>{title}</h2>
        <span className={styles.count}>{items.length}</span>
      </header>
      <ul className={styles.list}>
        {items.map((entity) => (
          <EntityRow key={entity.id} entity={entity} onQuickStatus={onQuickStatus} />
        ))}
      </ul>
    </section>
  );
}

export default function V4Today() {
  const [today, setToday] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    try {
      const data = await v4API.today();
      setToday(data);
    } catch (err) {
      setError(err.message || 'Failed to load today');
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function handleQuickStatus(entityId, status) {
    try {
      await v4API.entities.update(entityId, { status });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update status');
    }
  }

  if (error) {
    return <main className={styles.today}><section className={styles.panel}><p>{error}</p></section></main>;
  }
  if (!today) {
    return <main className={styles.today}><section className={styles.panel}><p>Loading today...</p></section></main>;
  }

  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const overdue = today.overdue || [];
  const dueToday = today.due_today || [];
  const followUps = today.follow_ups || [];
  const blocked = today.blocked_tasks || [];
  const waiting = today.waiting_tasks || [];
  const idleProjects = today.projects_without_open_tasks || [];
  const suggestions = today.pending_suggestions || [];

  const totalActionable = overdue.length + dueToday.length + followUps.length + blocked.length + waiting.length;

  return (
    <main className={styles.today}>
      <header className={styles.dateHeader}>
        <h1>{dateLabel}</h1>
        <p className={styles.dateSub}>
          {totalActionable === 0
            ? 'Nothing urgent. Use this time to plan ahead or capture notes.'
            : `${totalActionable} item${totalActionable === 1 ? '' : 's'} need your attention today.`}
        </p>
      </header>

      <EntitySection
        title="Overdue"
        items={overdue}
        onQuickStatus={handleQuickStatus}
        accent="overdue"
      />
      <EntitySection
        title="Due today"
        items={dueToday}
        onQuickStatus={handleQuickStatus}
        accent="due"
      />
      <EntitySection
        title="Follow up today"
        items={followUps}
        onQuickStatus={handleQuickStatus}
      />
      <EntitySection
        title="Blocked"
        items={blocked}
        onQuickStatus={handleQuickStatus}
      />
      <EntitySection
        title="Waiting"
        items={waiting}
        onQuickStatus={handleQuickStatus}
      />

      {suggestions.length > 0 && (
        <section className={styles.panel}>
          <header className={styles.panelHeader}>
            <h2>AI suggestions to review</h2>
            <span className={styles.count}>{suggestions.length}</span>
          </header>
          <ul className={styles.list}>
            {suggestions.map((s) => (
              <li key={s.id} className={styles.row}>
                <Link to="/suggestions" className={styles.rowLink}>
                  <strong>{s.payload?.title || s.suggestion_type}</strong>
                  <span className={styles.metaRow}>
                    <span className={styles.typePill}>{s.suggestion_type}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {idleProjects.length > 0 && (
        <details className={styles.collapsible}>
          <summary className={styles.collapsibleSummary}>
            Backlog hygiene · {idleProjects.length} project{idleProjects.length === 1 ? '' : 's'} without an open task
          </summary>
          <section className={styles.panel}>
            <ul className={styles.list}>
              {idleProjects.map((p) => (
                <li key={p.id} className={styles.row}>
                  <Link to={entityPath(p)} className={styles.rowLink}>
                    <strong>{p.title || 'Untitled project'}</strong>
                    <span className={styles.metaRow}>
                      <span className={styles.statusPill}>{p.status}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </details>
      )}
    </main>
  );
}
