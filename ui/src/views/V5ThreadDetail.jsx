import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { v4API } from '../api/v4Client';
import XGlyph from '../components/XGlyph';
import { entityTitleLabel } from '../utils/entityDisplay';
import styles from '../styles/v5.module.css';
import {
  buildNextActions,
  buildPeople,
  buildRelatedThreads,
  buildSignalCards,
  formatTimelineDate,
  narrativeSummary,
  pathForEntity,
  statusLabel,
  timelineGlyph,
} from './v5ThreadDetailUtils';

function useLongPress(onLongPress, { delay = 500 } = {}) {
  const timerRef = useRef(null);

  const clear = useCallback(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const start = useCallback((event, payload) => {
    clear();
    timerRef.current = window.setTimeout(() => {
      onLongPress(payload, event);
    }, delay);
  }, [clear, delay, onLongPress]);

  useEffect(() => clear, [clear]);

  return {
    onTouchStart: (event, payload) => start(event, payload),
    onTouchEnd: clear,
    onTouchMove: clear,
    onMouseDown: (event, payload) => start(event, payload),
    onMouseUp: clear,
    onMouseLeave: clear,
  };
}

function ActionButton({ button, onAction }) {
  if (button.href) {
    return (
      <Link
        to={button.href}
        className={button.action === 'open' ? styles.inlineButtonPrimary : styles.inlineButton}
        aria-label={button.label}
      >
        {button.label}
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={button.action === 'done' ? styles.inlineButtonPrimary : styles.inlineButton}
      aria-label={button.label}
      onClick={() => onAction(button)}
    >
      {button.label}
    </button>
  );
}

function ThreadDetailContent({
  detail,
  events,
  canonicalText,
  onAction,
  onCapture,
}) {
  const entity = detail.entity;
  const entityType = entity.type;
  const summary = narrativeSummary(entity, canonicalText);
  const nextActions = buildNextActions(detail, entityType);
  const signalCards = buildSignalCards(detail, entityType);
  const people = buildPeople(detail);
  const relatedThreads = buildRelatedThreads(detail, entity);
  const [longPressTarget, setLongPressTarget] = useState(null);

  const longPress = useLongPress((target) => setLongPressTarget(target));

  const timelineEvents = useMemo(
    () => (events || []).filter((event) => event?.narration),
    [events],
  );

  return (
    <>
      <header className={styles.header}>
        <div className={styles.typeMeta}>
          <XGlyph type={entityType} />
          <span>{entityType}</span>
          <span aria-hidden="true">·</span>
          <span className={styles.statusPill}>{statusLabel(entity.status)}</span>
        </div>
        <h1 className={styles.title}>{entityTitleLabel(entity, { includeType: false })}</h1>
      </header>

      <section className={styles.section} aria-labelledby="thread-narrative-label">
        <h2 id="thread-narrative-label" className={styles.sectionLabel}>Summary</h2>
        <p className={styles.narrative}>{summary}</p>
      </section>

      <section className={styles.section} aria-labelledby="thread-next-actions-label">
        <h2 id="thread-next-actions-label" className={styles.sectionLabel}>Next actions</h2>
        {signalCards.map((card) => (
          <article key={card.key} className={styles.signalCard} aria-label={card.title}>
            <h3 className={styles.signalTitle}>{card.title}</h3>
            <p className={styles.signalBody}>{card.body}</p>
            {card.meta ? (
              <p className={styles.signalMeta}>
                {Object.entries(card.meta)
                  .filter(([, value]) => typeof value === 'number' && value > 0)
                  .map(([key, value]) => `${value} ${key.replace(/_/g, ' ')}`)
                  .join(' · ')}
              </p>
            ) : null}
          </article>
        ))}
        {nextActions.length > 0 ? nextActions.map((action) => (
          <div
            key={action.id}
            className={styles.actionRow}
            onTouchStart={(event) => longPress.onTouchStart(event, action)}
            onTouchEnd={longPress.onTouchEnd}
            onTouchMove={longPress.onTouchMove}
            onMouseDown={(event) => longPress.onMouseDown(event, action)}
            onMouseUp={longPress.onMouseUp}
            onMouseLeave={longPress.onMouseLeave}
            data-testid={`action-row-${action.id}`}
          >
            <div className={styles.actionLabel}>{action.label}</div>
            <div className={styles.actionButtons}>
              {action.buttons.map((button) => (
                <ActionButton key={button.key} button={button} onAction={onAction} />
              ))}
            </div>
          </div>
        )) : (
          <p className={styles.emptyHint}>No obvious next actions right now.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="thread-timeline-label">
        <h2 id="thread-timeline-label" className={styles.sectionLabel}>Timeline</h2>
        {timelineEvents.length > 0 ? timelineEvents.map((event) => (
          <div
            key={event.id}
            className={styles.timelineRow}
            onTouchStart={(touchEvent) => longPress.onTouchStart(touchEvent, {
              label: event.narration,
              buttons: [{ key: 'open', label: 'Copy narration', action: 'decide' }],
            })}
            onTouchEnd={longPress.onTouchEnd}
            onTouchMove={longPress.onTouchMove}
            data-testid={`timeline-row-${event.id}`}
          >
            <time className={styles.timelineDate} dateTime={event.created_at}>
              {formatTimelineDate(event.created_at)}
            </time>
            <span className={styles.timelineGlyph} aria-hidden="true">
              {timelineGlyph(event)}
            </span>
            <p className={styles.timelineText}>{event.narration}</p>
          </div>
        )) : (
          <p className={styles.emptyHint}>Nothing in the timeline yet.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="thread-people-label">
        <h2 id="thread-people-label" className={styles.sectionLabel}>People</h2>
        {people.length > 0 ? people.map((person) => (
          <div key={person.id} className={styles.personRow}>
            <XGlyph type="person" />
            <Link to={pathForEntity(person.entity)} className={styles.personLink}>
              <span className={styles.personName}>{entityTitleLabel(person.entity, { includeType: false })}</span>
              <span className={styles.personMeta}>{person.relationship}{person.subtitle ? ` · ${person.subtitle}` : ''}</span>
            </Link>
          </div>
        )) : (
          <p className={styles.emptyHint}>No people linked yet.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="thread-related-label">
        <h2 id="thread-related-label" className={styles.sectionLabel}>Related threads</h2>
        {relatedThreads.length > 0 ? relatedThreads.map((thread) => (
          <div key={thread.id} className={styles.relatedRow}>
            <XGlyph type={thread.entity.type} />
            <Link to={pathForEntity(thread.entity)} className={styles.relatedLink}>
              <span className={styles.relatedTitle}>{entityTitleLabel(thread.entity, { includeType: false })}</span>
              <span className={styles.relatedMeta}>{thread.subtitle}</span>
            </Link>
          </div>
        )) : (
          <p className={styles.emptyHint}>No related threads yet.</p>
        )}
      </section>

      <button
        type="button"
        className={styles.fab}
        aria-label="Capture"
        onClick={onCapture}
      >
        <Plus size={24} strokeWidth={2.2} aria-hidden="true" />
      </button>

      {longPressTarget ? (
        <div className={styles.longPressMenu} role="dialog" aria-label="Quick actions">
          <div className={styles.longPressSheet}>
            <p className={styles.longPressTitle}>{longPressTarget.label || 'Quick actions'}</p>
            {(longPressTarget.buttons || []).map((button) => (
              <ActionButton
                key={button.key}
                button={button}
                onAction={(selected) => {
                  onAction(selected);
                  setLongPressTarget(null);
                }}
              />
            ))}
            <button type="button" className={styles.inlineButton} onClick={() => setLongPressTarget(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}

export default function V5ThreadDetail({
  type: routeType,
  previewDetail = null,
  previewEvents = null,
  previewCanonical = '',
}) {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(previewDetail);
  const [events, setEvents] = useState(previewEvents);
  const [canonicalText, setCanonicalText] = useState(previewCanonical);
  const [loading, setLoading] = useState(!previewDetail);
  const [error, setError] = useState('');

  useEffect(() => {
    if (previewDetail) {
      setDetail(previewDetail);
      setEvents(previewEvents || []);
      setCanonicalText(previewCanonical || '');
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError('');

    Promise.all([
      v4API.entities.detail(id),
      v4API.entities.events(id),
      v4API.entities.canonical(id).catch(() => ({ canonical: '' })),
    ])
      .then(([detailResponse, eventsResponse, canonicalResponse]) => {
        if (cancelled) return;
        const loadedDetail = detailResponse;
        if (routeType && loadedDetail?.entity?.type && loadedDetail.entity.type !== routeType) {
          navigate(pathForEntity(loadedDetail.entity), { replace: true, state: location.state });
          return;
        }
        setDetail(loadedDetail);
        setEvents(eventsResponse?.data || []);
        setCanonicalText(canonicalResponse?.canonical || '');
      })
      .catch((fetchError) => {
        if (!cancelled) setError(fetchError.message || 'Failed to load thread');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, routeType, previewDetail, previewEvents, previewCanonical, navigate, location.state]);

  const handleAction = useCallback(async (button) => {
    if (button.action === 'done' && button.entityId) {
      await v4API.entities.update(button.entityId, { status: 'done' });
      const refreshed = await v4API.entities.detail(id);
      setDetail(refreshed);
      return;
    }
    if (button.action === 'remind' && button.entityId) {
      const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
      await v4API.entities.update(button.entityId, { follow_up_at: tomorrow });
      const refreshed = await v4API.entities.detail(id);
      setDetail(refreshed);
    }
  }, [id]);

  const handleCapture = useCallback(() => {
    navigate('/', { state: { capture: true, threadId: detail?.entity?.id } });
  }, [navigate, detail?.entity?.id]);

  if (loading) {
    return <main className={styles.page} aria-busy="true"><p className={styles.loading}>Loading thread…</p></main>;
  }

  if (error || !detail?.entity) {
    return (
      <main className={styles.page}>
        <p className={styles.error} role="alert">{error || 'Thread not found'}</p>
        <Link to={location.state?.from || '/'} className={styles.backLink}>← Back</Link>
      </main>
    );
  }

  return (
    <main className={styles.page} aria-label={`${detail.entity.type} thread detail`}>
      <Link
        to={location.state?.from || (detail.entity.type === 'person' ? '/people' : `/${detail.entity.type}s`)}
        className={styles.backLink}
      >
        ← Back
      </Link>
      <ThreadDetailContent
        detail={detail}
        events={events}
        canonicalText={canonicalText}
        onAction={handleAction}
        onCapture={handleCapture}
      />
    </main>
  );
}

export { ThreadDetailContent };
