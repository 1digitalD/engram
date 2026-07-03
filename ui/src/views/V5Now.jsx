import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import EntityContextChips from '../components/EntityContextChips';
import { useReview } from '../context/ReviewContext';
import { useSummary } from '../context/SummaryContext';
import { FOLLOW_UP_24H_TITLE, FOLLOW_UP_TOMORROW_LABEL } from '../utils/followUpActions';
import { hasTaskContext } from '../utils/entityContext';
import { getTodayActionItems } from '../utils/today';
import { MOCKED_NOW_DATA } from './V5Now.fixtures';
import styles from './V5Now.module.css';

const USE_MOCKED_DATA = false;

function routeForEntity(type, id) {
  if (!type || !id) return '/now';
  if (type === 'person') return `/people/${id}`;
  return `/${type}s/${id}`;
}

function itemPath(item) {
  if (item.nonNavigable) return null;
  return routeForEntity(item.type, item.id);
}

function threadPath(item) {
  if (item.thread?.type && item.thread?.id) {
    return routeForEntity(item.thread.type, item.thread.id);
  }
  return itemPath(item);
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
  const detailPath = itemPath(item);
  const parentThreadPath = threadPath(item);
  const band = bandForScore(item.attention_score ?? 0);
  const actions = item.actions || [];
  const showTaskContext = item.type === 'task' && hasTaskContext(item);

  return (
    <article className={`${styles.row} ${band}`}>
      {detailPath ? (
        <Link to={detailPath} className={styles.sentence}>
          {sentenceFor(item)}
        </Link>
      ) : (
        <p className={styles.sentence}>{sentenceFor(item)}</p>
      )}

      <div className={styles.meta}>
        {item.when ? <span>{item.when}</span> : null}
        {item.when && item.why_now ? <span className={styles.metaDot}>·</span> : null}
        {item.why_now ? <span>{item.why_now}</span> : null}
        {!showTaskContext && item.thread ? (
          <>
            <span className={styles.metaDot}>·</span>
            <Link to={parentThreadPath} className={styles.threadChip}>
              {item.thread.label}
            </Link>
          </>
        ) : null}
      </div>

      {showTaskContext ? (
        <EntityContextChips
          projects={item.projects}
          areas={item.areas}
          className={styles.contextChips}
        />
      ) : null}

      {actions.length > 0 && (
        <div className={styles.actions}>
          {actions.slice(0, 3).map((action) => (
            <button
              key={action.key}
              type="button"
              className={`${styles.actionButton} ${action.primary ? styles.actionButtonPrimary : ''}`}
              onClick={() => onAction(item, action)}
              disabled={actionsDisabled}
              title={action.title}
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

const ACTION_REASON_LABELS = {
  overdue_follow_up: 'overdue follow-up',
  follow_up_today: 'follow-up today',
  blocked: 'blocked',
  waiting: 'waiting',
  needs_attention: 'needs attention',
};

function entityKey(entity) {
  return entity?.id || null;
}

function mapEntityToNowItem(entity, reason) {
  const score = entity.attention?.score ?? entity.attention_score ?? 50;
  const projects = entity.projects || [];
  const areas = entity.areas || [];
  const project = projects[0];
  const subject = entity.title
    ? `${entity.title}${entity.content ? ` — ${entity.content.slice(0, 120)}` : ''}`
    : 'Untitled item';

  return {
    id: entity.id,
    type: entity.type || 'task',
    subject,
    projects,
    areas,
    when: entity.due_at
      ? new Date(entity.due_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
      : (entity.follow_up_at
        ? new Date(entity.follow_up_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : 'No date'),
    why_now: reason || entity.attention?.reasons?.[0]?.label || 'Needs attention',
    thread: project
      ? { id: project.id, label: project.title, type: 'project' }
      : { id: entity.id, label: entity.title || 'Untitled', type: entity.type || 'task' },
    actions: [
      { key: 'open', label: 'Open', primary: true },
      { key: 'snooze', label: FOLLOW_UP_TOMORROW_LABEL, title: FOLLOW_UP_24H_TITLE },
      { key: 'done', label: 'Done' },
    ],
    attention_score: score,
  };
}

function bandNowItem(item, needs, waiting, ambient) {
  const score = item.attention_score ?? 0;
  if (score >= 75) {
    needs.push(item);
  } else if (score >= 25) {
    waiting.push(item);
  } else {
    ambient.push(item);
  }
}

export function transformTodayResponse(today) {
  const needs = [];
  const waiting = [];
  const ambient = [];
  const seen = new Set();

  function addEntity(entity, reason) {
    const key = entityKey(entity);
    if (!entity || !key || seen.has(key)) return;
    seen.add(key);
    bandNowItem(mapEntityToNowItem(entity, reason), needs, waiting, ambient);
  }

  for (const entity of today.overdue || []) addEntity(entity, 'overdue');
  for (const entity of today.due_today || []) addEntity(entity, 'due today');
  for (const entity of today.delegations_quiet || []) addEntity(entity, 'needs a nudge');
  for (const item of today.dependency_interventions || []) {
    addEntity(item.entity, item.label);
  }
  for (const { entity, reason } of getTodayActionItems(today)) {
    addEntity(entity, ACTION_REASON_LABELS[reason] || reason);
  }

  for (const note of today.recent_notes || []) {
    const key = entityKey(note);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    ambient.push({
      id: note.id,
      type: 'note',
      subject: note.title || (note.content ? note.content.slice(0, 120) : 'Recent note'),
      when: 'Recent',
      why_now: note.ai?.intent ? `${note.ai.intent.replace(/_/g, ' ')} note` : 'Recent capture',
      thread: { id: note.id, label: note.title || 'Note', type: 'note' },
      actions: [{ key: 'open', label: 'Open', primary: true }],
      attention_score: 15,
    });
  }

  const stale = [...(today.stale_projects || []), ...(today.suggested_archival || [])];
  for (const entity of stale) {
    const key = entityKey(entity);
    if (!key || seen.has(key)) continue;
    seen.add(key);
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

  const suggestions = today.pending_suggestions || [];
  if (suggestions.length > 0) {
    waiting.push({
      id: 'pending-suggestions',
      type: 'suggestions',
      subject: `${suggestions.length} suggestion${suggestions.length === 1 ? '' : 's'} ready to review`,
      when: 'Review',
      why_now: 'From recent captures',
      actions: [{ key: 'review', label: 'Review suggestions', primary: true }],
      attention_score: 55,
      nonNavigable: true,
    });
  }

  return {
    needs_you_now: needs,
    waiting_on_you: waiting,
    ambient,
    new_since_yesterday_count: today.new_since_yesterday_count ?? 0,
  };
}

function buildSubtitle(data) {
  const attentionCount = (data?.needs_you_now?.length || 0) + (data?.waiting_on_you?.length || 0);
  const newCount = data?.new_since_yesterday_count ?? 0;

  if (attentionCount > 0) {
    const base = `${attentionCount} item${attentionCount === 1 ? '' : 's'} need your attention.`;
    return newCount > 0 ? `${base} ${newCount} new since yesterday.` : base;
  }
  if (newCount > 0) {
    return `${newCount} new since yesterday. Nothing urgent right now.`;
  }
  return 'Nothing urgent. Use this time to plan ahead or capture notes.';
}

export default function V5Now({ previewData }) {
  const [data, setData] = useState(previewData || null);
  const [loading, setLoading] = useState(!previewData);
  const [error, setError] = useState('');
  const [pendingAction, setPendingAction] = useState(null);
  const navigate = useNavigate();
  const { refreshSummary } = useSummary();
  const { openReview } = useReview();

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
        navigate(itemPath(item));
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
          setError(friendlyApiError(err, 'Follow-up update failed'));
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
      case 'review':
        openReview();
        return;
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
        <p className={styles.subtitle}>{buildSubtitle(data)}</p>
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
