import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import { MOCKED_NOW_DATA } from './V5Now.fixtures';
import styles from './V5Now.module.css';

const USE_MOCKED_DATA = true;

function entityPath(item) {
  if (item.thread?.type === 'person') return `/people/${item.thread.id}`;
  if (item.thread?.type) return `/${item.thread.type}s/${item.thread.id}`;
  return `/entities/${item.id}`;
}

function bandForScore(score) {
  if (score >= 75) return styles.rowHot;
  if (score >= 25) return styles.rowWarm;
  return styles.rowAmbient;
}

function sentenceFor(item) {
  if (item.subject) return item.subject;
  return `${item.title || 'Untitled'}`;
}

function NowRow({ item, onAction }) {
  const path = entityPath(item);
  const band = bandForScore(item.attention_score ?? 0);
  const actions = item.actions || [];

  return (
    <article className={`${styles.row} ${band}`}>
      <Link to={path} className={styles.sentence}>
        {sentenceFor(item)}
      </Link>

      <div className={styles.meta}>
        {item.when ? <span>{item.when}</span> : null}
        {item.when && item.why_now ? <span className={styles.metaDot}>·</span> : null}
        {item.why_now ? <span>{item.why_now}</span> : null}
        {item.thread ? (
          <>
            <span className={styles.metaDot}>·</span>
            <Link to={path} className={styles.threadChip}>
              {item.thread.label}
            </Link>
          </>
        ) : null}
      </div>

      {actions.length > 0 && (
        <div className={styles.actions}>
          {actions.slice(0, 3).map((action) => (
            <button
              key={action.key}
              type="button"
              className={`${styles.actionButton} ${action.primary ? styles.actionButtonPrimary : ''}`}
              onClick={() => onAction(item, action)}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function Section({ title, items, onAction }) {
  if (!items || items.length === 0) return null;
  return (
    <section className={styles.section} aria-label={title}>
      <h2 className={styles.sectionLabel}>
        {title}
        <span className={styles.sectionCount}>{items.length}</span>
      </h2>
      <div className={styles.rowList}>
        {items.map((item) => (
          <NowRow key={item.id} item={item} onAction={onAction} />
        ))}
      </div>
    </section>
  );
}

function transformTodayResponse(today) {
  const needs = [];
  const waiting = [];
  const ambient = [];

  const allEntities = [
    ...(today.overdue || []).map((e) => ({ ...e, reason: 'overdue' })),
    ...(today.due_today || []).map((e) => ({ ...e, reason: 'due today' })),
    ...(today.delegations_quiet || []).map((e) => ({ ...e, reason: 'needs a nudge' })),
    ...(today.dependency_interventions || []).map((item) => ({ ...item.entity, reason: item.label })),
  ];

  for (const entity of allEntities) {
    if (!entity) continue;
    const score = entity.attention?.score ?? entity.attention_score ?? 50;
    const project = (entity.projects || [])[0];
    const subject = entity.title
      ? `${entity.title}${entity.content ? ` — ${entity.content.slice(0, 120)}` : ''}`
      : 'Untitled item';
    const item = {
      id: entity.id,
      type: entity.type || 'task',
      subject,
      when: entity.due_at
        ? new Date(entity.due_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : (entity.follow_up_at
            ? new Date(entity.follow_up_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
            : 'No date'),
      why_now: entity.reason || entity.attention?.reasons?.[0]?.label || 'Needs attention',
      thread: project
        ? { id: project.id, label: project.title, type: 'project' }
        : { id: entity.id, label: entity.title || 'Untitled', type: entity.type || 'task' },
      actions: [
        { key: 'open', label: 'Open', primary: true },
        { key: 'snooze', label: 'Snooze' },
        { key: 'done', label: 'Done' },
      ],
      attention_score: score,
    };

    if (score >= 75) {
      needs.push(item);
    } else if (score >= 25) {
      waiting.push(item);
    } else {
      ambient.push(item);
    }
  }

  const stale = [...(today.stale_projects || []), ...(today.suggested_archival || [])];
  for (const entity of stale) {
    ambient.push({
      id: entity.id,
      type: 'project',
      subject: `${entity.title || 'Untitled project'} has had no activity in ${entity.stale_days} days.`,
      when: 'Ambient',
      why_now: 'Stalled project context',
      thread: { id: entity.id, label: entity.title || 'Untitled', type: 'project' },
      actions: [{ key: 'view', label: 'View' }],
      attention_score: 10,
    });
  }

  return { needs_you_now: needs, waiting_on_you: waiting, ambient };
}

export default function V5Now({ previewData }) {
  const [data, setData] = useState(previewData || null);
  const [loading, setLoading] = useState(!previewData);
  const [error, setError] = useState('');

  useEffect(() => {
    if (previewData) {
      setData(previewData);
      setLoading(false);
      return;
    }

    if (USE_MOCKED_DATA) {
      setData(MOCKED_NOW_DATA);
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError('');
    v4API.today()
      .then((today) => {
        if (!active) return;
        setData(transformTodayResponse(today));
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || 'Failed to load Now');
        setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [previewData]);

  function handleAction() {
    // Placeholder for action handlers; deep links handled by row link.
  }

  const dateLabel = useMemo(() => new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }), []);

  if (loading) {
    return <p className={styles.loading}>Loading now…</p>;
  }

  if (error) {
    return <p className={styles.error}>{error}</p>;
  }

  const hasItems = data
    && (data.needs_you_now?.length || data.waiting_on_you?.length || data.ambient?.length);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{dateLabel}</h1>
        <p className={styles.subtitle}>
          {hasItems
            ? `${(data.needs_you_now?.length || 0) + (data.waiting_on_you?.length || 0)} items need your attention.`
            : 'Nothing urgent. Use this time to plan ahead or capture notes.'}
        </p>
      </header>

      <Section
        title="Needs you now"
        items={data?.needs_you_now || []}
        onAction={handleAction}
        accent="hot"
      />

      <Section
        title="Waiting on you"
        items={data?.waiting_on_you || []}
        onAction={handleAction}
        accent="warm"
      />

      <Section
        title="Ambient"
        items={data?.ambient || []}
        onAction={handleAction}
        accent="ambient"
      />

      {!hasItems && (
        <p className={styles.emptyHint}>No items in your Now view yet.</p>
      )}
    </main>
  );
}
