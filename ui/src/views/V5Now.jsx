import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import { useSummary } from '../context/SummaryContext';
import { MOCKED_NOW_DATA } from './V5Now.fixtures';
import styles from './V5Now.module.css';

const USE_MOCKED_DATA = false;

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
  return item.title || 'Untitled';
}

function NowRow({ item, onAction, actionsDisabled = false }) {
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
              disabled={actionsDisabled}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function Section({ title, items, onAction, actionsDisabled = false }) {
  if (!items || items.length === 0) return null;

  return (
    <section className={styles.section} aria-label={title}>
      <h2 className={styles.sectionLabel}>
        {title}
        <span className={styles.sectionCount}>{items.length}</span>
      </h2>

      <div className={styles.rowList}>
        {items.map((item) => (
          <NowRow
            key={item.id}
            item={item}
            onAction={onAction}
            actionsDisabled={actionsDisabled}
          />
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
    ...(today.overdue || []).map((entity) => ({ ...entity, reason: 'overdue' })),
    ...(today.due_today || []).map((entity) => ({ ...entity, reason: 'due today' })),
    ...(today.delegations_quiet || []).map((entity) => ({ ...entity, reason: 'needs a nudge' })),
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
      subject: `${entity.title || 'Untitled project'} had no activity in ${entity.stale_days} days.`,
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
  const [pendingAction, setPendingAction] = useState(null);
  const navigate = useNavigate();
  const { refreshSummary } = useSummary();

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
        setError(friendlyApiError(err, 'Failed to load Now'));
        setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [previewData]);

  async function handleAction(item, action) {
    if (!item?.id || !action?.key) return;

    switch (action.key) {
      case 'open':
      case 'view':
        navigate(`/entities/${item.id}`);
        return;
      case 'snooze': {
        const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
        setPendingAction(action.key);
        try {
          await v4API.entities.update(item.id, { follow_up_at: tomorrow });
          const today = await v4API.today();
          setData(transformTodayResponse(today));
          refreshSummary();
        } catch (err) {
          setError(friendlyApiError(err, 'Snooze failed'));
        } finally {
          setPendingAction(null);
        }
        return;
      }
      case 'done': {
        setPendingAction(action.key);
        try {
          await v4API.entities.update(item.id, { status: 'done' });
          const today = await v4API.today();
          setData(transformTodayResponse(today));
          refreshSummary();
        } catch (err) {
          setError(friendlyApiError(err, 'Mark done failed'));
        } finally {
          setPendingAction(null);
        }
        return;
      }
      default:
        return;
    }
  }

  const hasItems = useMemo(
    () => Boolean((data?.needs_you_now || []).length || (data?.waiting_on_you || []).length || (data?.ambient || []).length),
    [data],
  );

  if (loading) {
    return (
      <main className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading Now…</p>
      </main>
    );
  }

  if (error && !data) {
    return (
      <main className={styles.page}>
        <p className={styles.error} role="alert">{error}</p>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Now</h1>
        <p className={styles.subtitle}>
          {hasItems
            ? `${(data?.needs_you_now?.length || 0) + (data?.waiting_on_you?.length || 0)} items need your attention.`
            : 'Nothing urgent. Use this time to plan ahead or capture notes.'}
        </p>
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </header>

      <Section
        title="Needs you now"
        items={data?.needs_you_now || []}
        onAction={handleAction}
        actionsDisabled={Boolean(pendingAction)}
      />
      <Section
        title="Waiting on you"
        items={data?.waiting_on_you || []}
        onAction={handleAction}
        actionsDisabled={Boolean(pendingAction)}
      />
      <Section
        title="Ambient"
        items={data?.ambient || []}
        onAction={handleAction}
        actionsDisabled={Boolean(pendingAction)}
      />

      {!hasItems && (
        <p className={styles.emptyHint}>No items in your Now view yet.</p>
      )}
    </main>
  );
}
