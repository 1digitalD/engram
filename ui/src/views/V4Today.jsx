/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import CardActions from '../components/CardActions';
import MarkdownContent from '../components/MarkdownContent';
import {
  getTodayAttentionCount,
  getTodayDueNowEntities,
  getTodayFocusItems,
  getTodayOverdueEntities,
  getTodayStuckEntities,
} from '../utils/today';
import styles from './V4Today.module.css';

const TASK_STATUSES = ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'];

function toLocalInput(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function InlineDateChip({ value, label, ariaLabel, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(toLocalInput(value));
  const ref = useRef(null);

  useEffect(() => { setDraft(toLocalInput(value)); }, [value]);
  useEffect(() => {
    if (editing && ref.current) ref.current.focus();
  }, [editing]);

  async function commit() {
    setEditing(false);
    const next = draft || null;
    const currentInput = toLocalInput(value);
    if ((next || '') === currentInput) return;
    await onSave(next);
  }

  if (editing) {
    return (
      <input
        ref={ref}
        type="datetime-local"
        className={styles.inlineDateInput}
        value={draft}
        aria-label={ariaLabel}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); commit(); }
          else if (e.key === 'Escape') { e.preventDefault(); setDraft(toLocalInput(value)); setEditing(false); }
        }}
      />
    );
  }

  const display = value ? shortDate(value) : '—';
  return (
    <button
      type="button"
      className={`${styles.inlineDateChip} ${!value ? styles.inlineDateChipEmpty : ''}`}
      onClick={() => setEditing(true)}
      title={`Click to edit ${label.toLowerCase()}`}
      aria-label={ariaLabel}
    >
      <span className={styles.inlineDateLabel}>{label}</span>
      <span className={styles.inlineDateValue}>{display}</span>
    </button>
  );
}

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function shortDate(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  const sameYear = d.getFullYear() === new Date().getFullYear();
  return d.toLocaleDateString(undefined, sameYear
    ? { month: 'short', day: 'numeric' }
    : { month: 'short', day: 'numeric', year: 'numeric' });
}

function reasonLabel(reason) {
  if (reason === 'overdue') return 'overdue';
  if (reason === 'due_today') return 'due today';
  if (reason === 'overdue_follow_up') return 'follow-up overdue';
  if (reason === 'follow_up_today') return 'follow-up today';
  if (reason === 'blocked') return 'blocked';
  if (reason === 'waiting') return 'waiting';
  return reason;
}

function EntityRow({ entity, onQuickStatus, onUpdateField, onChanged, fromState, reason }) {
  const isTask = entity.type === 'task';
  return (
    <li className={`${styles.row} cardActionsParent`}>
      <CardActions entity={entity} onChanged={onChanged} />
      <Link to={entityPath(entity)} state={fromState} className={styles.rowLink}>
        <strong>{entity.title || 'Untitled'}</strong>
        {entity.content && (
          <MarkdownContent content={entity.content} compact />
        )}
      </Link>
      <div className={styles.metaRow}>
        <span className={styles.typePill}>{entity.type}</span>
        {reason ? <span className={styles.reasonPill}>{reasonLabel(reason)}</span> : null}
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
        <InlineDateChip
          value={entity.due_at}
          label="Due"
          ariaLabel={`Due date for ${entity.title || 'item'}`}
          onSave={(val) => onUpdateField(entity.id, { due_at: val })}
        />
        <InlineDateChip
          value={entity.follow_up_at}
          label="Follow-up"
          ariaLabel={`Follow-up date for ${entity.title || 'item'}`}
          onSave={(val) => onUpdateField(entity.id, { follow_up_at: val })}
        />
      </div>
    </li>
  );
}

function EntitySection({ title, items, onQuickStatus, onUpdateField, onChanged, fromState, accent, reason }) {
  if (items.length === 0) return null;
  return (
    <section className={`${styles.panel} ${accent ? styles[`panel_${accent}`] : ''}`}>
      <header className={styles.panelHeader}>
        <h2>{title}</h2>
        <span className={styles.count}>{items.length}</span>
      </header>
      <ul className={styles.list}>
        {items.map((entity) => (
          <EntityRow
            key={entity.id}
            entity={entity}
            onQuickStatus={onQuickStatus}
            onUpdateField={onUpdateField}
            onChanged={onChanged}
            fromState={fromState}
            reason={reason}
          />
        ))}
      </ul>
    </section>
  );
}

export default function V4Today() {
  const location = useLocation();
  const fromState = { from: location.pathname + location.search };
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

  async function handleUpdateField(entityId, partial) {
    try {
      await v4API.entities.update(entityId, partial);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update');
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
  const overdueFollowUps = today.overdue_follow_ups || [];
  const followUps = today.follow_ups || [];
  const upcomingFollowUps = today.upcoming_follow_ups || [];
  const blocked = today.blocked_tasks || [];
  const waiting = today.waiting_tasks || [];
  const idleProjects = today.projects_without_open_tasks || [];
  const recentNotes = today.recent_notes || [];
  const suggestions = today.pending_suggestions || [];

  const totalActionable = getTodayAttentionCount(today);
  const focusNow = getTodayFocusItems(today, 6);
  const overdueSummaryCount = getTodayOverdueEntities(today).length;
  const dueNowSummaryCount = getTodayDueNowEntities(today).length;
  const stuckSummaryCount = getTodayStuckEntities(today).length;

  return (
    <main className={styles.today}>
      <header className={styles.dateHeader}>
        <h1>{dateLabel}</h1>
        <p className={styles.dateSub}>
          {totalActionable === 0
            ? 'Nothing urgent. Use this time to plan ahead or capture notes.'
            : `${totalActionable} item${totalActionable === 1 ? '' : 's'} need your attention today.`}
        </p>
        <div className={styles.summaryStrip}>
          <span className={styles.summaryPill}>{overdueSummaryCount} overdue</span>
          <span className={styles.summaryPill}>{dueNowSummaryCount} due or follow-up today</span>
          <span className={styles.summaryPill}>{stuckSummaryCount} stuck</span>
        </div>
      </header>

      {focusNow.length > 0 && (
        <section className={`${styles.panel} ${styles.panel_focus}`}>
          <header className={styles.panelHeader}>
            <h2>Focus now</h2>
            <span className={styles.count}>{focusNow.length}</span>
          </header>
          <ul className={styles.list}>
            {focusNow.map(({ entity, reason }) => (
              <EntityRow
                key={`focus-${entity.id}-${reason}`}
                entity={entity}
                onQuickStatus={handleQuickStatus}
                onUpdateField={handleUpdateField}
                onChanged={load}
                fromState={fromState}
                reason={reason}
              />
            ))}
          </ul>
        </section>
      )}

      <EntitySection
        title="Overdue"
        items={overdue}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
        accent="overdue"
        reason="overdue"
      />
      <EntitySection
        title="Due today"
        items={dueToday}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
        accent="due"
        reason="due_today"
      />
      <EntitySection
        title="Overdue follow-ups"
        items={overdueFollowUps}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
        accent="overdue"
        reason="overdue_follow_up"
      />
      <EntitySection
        title="Follow up today"
        items={followUps}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
        reason="follow_up_today"
      />
      <EntitySection
        title="Upcoming follow-ups (next 7 days)"
        items={upcomingFollowUps}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
      />
      <EntitySection
        title="Blocked"
        items={blocked}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
        reason="blocked"
      />
      <EntitySection
        title="Waiting"
        items={waiting}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
        reason="waiting"
      />
      <EntitySection
        title="Recent notes"
        items={recentNotes}
        onQuickStatus={handleQuickStatus}
        onUpdateField={handleUpdateField}
        onChanged={load}
        fromState={fromState}
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
