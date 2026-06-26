/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BookOpen, Compass, FileText, FolderKanban, SquareCheck, User } from 'lucide-react';
import { v4API } from '../api/v4Client';
import { entityTitleLabel } from '../utils/entityDisplay';
import CardActions from '../components/CardActions';
import MarkdownContent from '../components/MarkdownContent';
import {
  getTodayActionItems,
  getTodayAttentionCount,
  getTodayDeadlinesAhead,
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
  if (reason === 'captured_blocker') return 'captured blocker';
  if (reason === 'captured_follow_up') return 'captured follow-up';
  if (reason === 'captured_delegation') return 'captured delegation';
  if (reason === 'needs_attention') return 'needs attention';
  return reason;
}

function formatAttention(entity) {
  const attention = entity?.attention;
  if (!attention?.score) return '';
  const topReason = attention.reasons?.[0]?.label;
  return topReason ? `${attention.level} · ${topReason}` : attention.level;
}

const TYPE_GLYPHS = {
  task: SquareCheck,
  project: FolderKanban,
  note: FileText,
  person: User,
  area: Compass,
  resource: BookOpen,
};

function TypeGlyph({ type }) {
  const Icon = TYPE_GLYPHS[type] || FileText;
  return (
    <span className={styles.typeGlyph} role="img" aria-label={type} title={type}>
      <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
    </span>
  );
}

function EntityRow({ entity, onQuickStatus, onUpdateField, onChanged, fromState, reason }) {
  const isTask = entity.type === 'task';
  const attentionLabel = formatAttention(entity);
  const priorityPill = entity.properties?.priority
    ? <span className={styles.priorityPill}>!{entity.properties.priority}</span>
    : entity.inherited_priority
      ? <span className={styles.priorityPill} title="Inherited from project">~{entity.inherited_priority}</span>
      : null;
  const hasFocusRow = (entity.projects || []).length > 0 || reason || priorityPill || attentionLabel;
  return (
    <li className={`${styles.row} cardActionsParent`}>
      <CardActions entity={entity} onChanged={onChanged} />
      <Link to={entityPath(entity)} state={fromState} className={styles.rowLink}>
        <span className={styles.titleRow}>
          <TypeGlyph type={entity.type} />
          <strong>{entityTitleLabel(entity)}</strong>
        </span>
        {entity.content && (
          <MarkdownContent content={entity.content} compact />
        )}
      </Link>
      <div className={styles.metaRow}>
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
      {hasFocusRow && (
        <div className={styles.metaRow}>
          {(entity.projects || []).map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className={styles.projectChip}
              title={`Project: ${project.title}`}
            >
              ▣ {project.title}
            </Link>
          ))}
          {reason ? <span className={styles.reasonPill}>{reasonLabel(reason)}</span> : null}
          {priorityPill}
          {attentionLabel && (
            <span className={styles.attentionPill}>{attentionLabel}</span>
          )}
        </div>
      )}
    </li>
  );
}

function DelegationQuietRow({ entity, fromState }) {
  return (
    <li className={styles.row}>
      <Link to={entityPath(entity)} state={fromState} className={styles.rowLink}>
        <span className={styles.titleRow}>
          <TypeGlyph type={entity.type} />
          <strong>{entityTitleLabel(entity)}</strong>
        </span>
        {entity.last_update && (
          <MarkdownContent content={entity.last_update} compact />
        )}
      </Link>
      <div className={styles.metaRow}>
        <span className={styles.reasonPill}>
          {entity.days_silent} day{entity.days_silent === 1 ? '' : 's'} silent
        </span>
        {!entity.last_update && (
          <span className={styles.mutedMeta}>no activity update yet</span>
        )}
      </div>
    </li>
  );
}

function DependencyInterventionRow({ item, fromState }) {
  const entity = item.entity;
  if (!entity) return null;

  return (
    <li className={styles.row}>
      <Link to={entityPath(entity)} state={fromState} className={styles.rowLink}>
        <span className={styles.titleRow}>
          <TypeGlyph type={entity.type} />
          <strong>{entityTitleLabel(entity)}</strong>
        </span>
      </Link>
      <div className={styles.metaRow}>
        <span className={styles.statusPill}>{entity.status}</span>
        <span className={styles.reasonPill}>{item.label}</span>
      </div>
      {item.blocker ? (
        <div className={styles.metaRow}>
          <Link to={entityPath(item.blocker)} state={fromState} className={styles.projectChip}>
            ▣ {item.blocker.title}
          </Link>
        </div>
      ) : item.blocked_preview ? (
        <p className={styles.mutedMeta}>First impacted: {item.blocked_preview}</p>
      ) : null}
      {item.last_heard_preview ? (
        <p className={styles.mutedMeta}>{item.last_heard_preview}</p>
      ) : null}
    </li>
  );
}

function StaleProjectRow({ entity, fromState, archival }) {
  return (
    <li className={styles.row}>
      <Link to={entityPath(entity)} state={fromState} className={styles.rowLink}>
        <strong>{entity.title || 'Untitled project'}</strong>
      </Link>
      <div className={styles.metaRow}>
        <span className={styles.statusPill}>{entity.status}</span>
        <span className={styles.reasonPill}>
          no activity in {entity.stale_days} day{entity.stale_days === 1 ? '' : 's'}
        </span>
        {archival && <span className={styles.reasonPill}>consider archiving</span>}
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

function CollapsibleSection({ title, count, accent, initialOpen = false, children }) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <section className={`${styles.panel} ${accent ? styles[`panel_${accent}`] : ''}`}>
      <button
        type="button"
        className={styles.panelHeaderToggle}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <h2>{title}</h2>
        <span className={styles.count}>{count}</span>
        <span className={styles.toggleHint}>{open ? 'hide' : 'show'}</span>
      </button>
      {open && (
        <div className={styles.collapsibleBody}>
          {children}
        </div>
      )}
    </section>
  );
}

export default function V4Today() {
  const location = useLocation();
  const fromState = { from: location.pathname + location.search };
  const [today, setToday] = useState(null);
  const [error, setError] = useState('');
  const [idleShowAll, setIdleShowAll] = useState(false);

  async function load() {
    try {
      const data = await v4API.today();
      setToday(data);
    } catch (err) {
      setError(err.message || 'Failed to load today');
    }
  }

  useEffect(() => { load(); }, []);

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

  async function handleMarkDayReviewed() {
    try {
      await v4API.today.review();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to mark day reviewed');
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
  const idleProjects = today.projects_without_open_tasks || [];
  const staleProjects = today.stale_projects || [];
  const suggestedArchival = today.suggested_archival || [];
  const recentNotes = today.recent_notes || [];
  const delegationsQuiet = today.delegations_quiet || [];
  const dependencyInterventions = today.dependency_interventions || [];

  const totalActionable = getTodayAttentionCount(today);
  const focusNow = getTodayFocusItems(today, 6);
  const overdueSummaryCount = getTodayOverdueEntities(today).length;
  const dueNowSummaryCount = getTodayDueNowEntities(today).length;
  const stuckSummaryCount = getTodayStuckEntities(today).length;
  const actionItems = getTodayActionItems(today);
  const deadlinesAhead = getTodayDeadlinesAhead(today);
  const reviewedToday = !!today.reviewed_today;
  const newSinceYesterday = today.new_since_yesterday_count || 0;

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
          {newSinceYesterday > 0 && (
            <span className={styles.summaryPill}>
              {newSinceYesterday} new since yesterday
            </span>
          )}
        </div>
        <button
          type="button"
          className={styles.reviewButton}
          onClick={handleMarkDayReviewed}
          disabled={reviewedToday}
        >
          {reviewedToday ? 'Day reviewed' : 'Mark day reviewed'}
        </button>
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
      {actionItems.length > 0 && (
        <section className={styles.panel}>
          <header className={styles.panelHeader}>
            <h2>Your actions</h2>
            <span className={styles.count}>{actionItems.length}</span>
          </header>
          <ul className={styles.list}>
            {actionItems.map(({ entity, reason }) => (
              <EntityRow
                key={`action-${entity.id}-${reason}`}
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
      {delegationsQuiet.length > 0 && (
        <section className={`${styles.panel} ${styles.panel_overdue}`}>
          <header className={styles.panelHeader}>
            <h2>Delegations needing a nudge</h2>
            <span className={styles.count}>{delegationsQuiet.length}</span>
          </header>
          <ul className={styles.list}>
            {delegationsQuiet.map((entity) => (
              <DelegationQuietRow key={entity.id} entity={entity} fromState={fromState} />
            ))}
          </ul>
        </section>
      )}
      {dependencyInterventions.length > 0 && (
        <section className={`${styles.panel} ${styles.panel_focus}`}>
          <header className={styles.panelHeader}>
            <h2>Dependency interventions</h2>
            <span className={styles.count}>{dependencyInterventions.length}</span>
          </header>
          <ul className={styles.list}>
            {dependencyInterventions.map((item) => (
              <DependencyInterventionRow
                key={`${item.kind}-${item.entity?.id || 'unknown'}-${item.blocker?.id || item.blocked_count || '0'}`}
                item={item}
                fromState={fromState}
              />
            ))}
          </ul>
        </section>
      )}

      {deadlinesAhead.length > 0 && (
        <details className={styles.collapsible}>
          <summary className={styles.collapsibleSummary}>
            Deadlines ahead · {deadlinesAhead.length} item{deadlinesAhead.length === 1 ? '' : 's'} this week
          </summary>
          <section className={styles.panel}>
            <ul className={styles.list}>
              {deadlinesAhead.map((entity) => (
                <EntityRow
                  key={`deadline-${entity.id}`}
                  entity={entity}
                  onQuickStatus={handleQuickStatus}
                  onUpdateField={handleUpdateField}
                  onChanged={load}
                  fromState={fromState}
                />
              ))}
            </ul>
          </section>
        </details>
      )}

      {recentNotes.length > 0 && (
        <CollapsibleSection title="Recent notes" count={recentNotes.length}>
          <ul className={styles.list}>
            {recentNotes.map((entity) => (
              <EntityRow
                key={entity.id}
                entity={entity}
                onQuickStatus={handleQuickStatus}
                onUpdateField={handleUpdateField}
                onChanged={load}
                fromState={fromState}
              />
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {suggestedArchival.length > 0 && (
        <CollapsibleSection title="Suggested archival" count={suggestedArchival.length}>
          <ul className={styles.list}>
            {suggestedArchival.map((p) => (
              <StaleProjectRow key={p.id} entity={p} fromState={fromState} archival />
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {staleProjects.length > 0 && (
        <CollapsibleSection title="Stale projects" count={staleProjects.length}>
          <ul className={styles.list}>
            {staleProjects.map((p) => (
              <StaleProjectRow key={p.id} entity={p} fromState={fromState} />
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {idleProjects.length > 0 && (
        <CollapsibleSection title="Projects without open tasks" count={idleProjects.length}>
          <ul className={styles.list}>
            {idleProjects.slice(0, idleShowAll ? undefined : 5).map((p) => (
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
          {!idleShowAll && idleProjects.length > 5 && (
            <button
              type="button"
              className={styles.viewAllLink}
              onClick={() => setIdleShowAll(true)}
            >
              View all {idleProjects.length}
            </button>
          )}
        </CollapsibleSection>
      )}
    </main>
  );
}
