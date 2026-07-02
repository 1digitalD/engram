import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { friendlyApiError, v4API } from '../api/v4Client';
import XGlyph from '../components/XGlyph';
import CitationsList from '../components/CitationsList';
import CitationEntitySheet from '../components/CitationEntitySheet';
import MarkdownEditor from '../components/MarkdownEditor';
import { useCapture } from '../context/CaptureContext';
import { useReview } from '../context/ReviewContext';
import { useSummary } from '../context/SummaryContext';
import { entityTitleLabel } from '../utils/entityDisplay';
import styles from '../styles/v5.module.css';
import {
  activityUpdatesMeta,
  buildActivityUpdates,
  buildNextActions,
  buildPeople,
  buildReferences,
  buildRelatedThreads,
  buildSignalCards,
  formatTimelineDate,
  narrativeSummary,
  pathForEntity,
  statusLabel,
  timelineGlyph,
} from './v5ThreadDetailUtils';

const ACTIVITY_UPDATE_ENTITY_TYPES = new Set(['project', 'task', 'area']);
const ACTIVITY_LOAD_MORE_PAGE_SIZE = 10;

const UPDATE_PLACEHOLDERS = {
  project: 'What changed on this project?',
  task: 'Progress on this task…',
  area: 'What is new in this area?',
};

const STATUS_OPTIONS = {
  note: ['active', 'processed', 'archived'],
  task: ['open', 'in_progress', 'waiting', 'blocked', 'done', 'cancelled'],
  project: ['active', 'on_hold', 'completed', 'cancelled'],
  area: ['active', 'archived'],
  person: ['active', 'archived'],
  resource: ['active', 'archived'],
};

const PRIORITY_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

function toLocalInput(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toIsoOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function buildDraft(entity) {
  return {
    title: entity?.title || '',
    content: entity?.content || '',
    status: entity?.status || '',
    due_at: toLocalInput(entity?.due_at),
    follow_up_at: toLocalInput(entity?.follow_up_at),
    priority: entity?.properties?.priority || '',
  };
}

function buildUpdatePayload(entity, draft) {
  const baseline = buildDraft(entity);
  const payload = {};

  if (draft.title !== baseline.title) {
    payload.title = draft.title.trim() || entity?.title || '';
  }
  if (draft.content !== baseline.content) {
    payload.content = draft.content;
  }
  if (draft.status !== baseline.status) {
    payload.status = draft.status || entity?.status;
  }
  if (draft.due_at !== baseline.due_at) {
    payload.due_at = toIsoOrNull(draft.due_at);
  }
  if (draft.follow_up_at !== baseline.follow_up_at) {
    payload.follow_up_at = toIsoOrNull(draft.follow_up_at);
  }
  if (draft.priority !== baseline.priority) {
    const properties = { ...(entity?.properties || {}) };
    if (draft.priority) {
      properties.priority = draft.priority;
    } else {
      delete properties.priority;
    }
    payload.properties = properties;
  }

  return payload;
}

function isDraftDirty(entity, draft) {
  const baseline = buildDraft(entity);
  return Object.keys(baseline).some((key) => baseline[key] !== draft[key]);
}

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

function EntityAttributeEditor({
  entity,
  open,
  draft,
  dirty,
  saving,
  error,
  onToggle,
  onChange,
  onSave,
  onCancel,
}) {
  const statuses = STATUS_OPTIONS[entity?.type] || ['active'];

  return (
    <section className={styles.section} aria-labelledby="thread-details-label">
      <div className={styles.sectionHeader}>
        <h2 id="thread-details-label" className={styles.sectionLabel}>Details</h2>
        <button
          type="button"
          className={styles.inlineButton}
          onClick={onToggle}
          aria-expanded={open}
        >
          {open ? 'Hide editor' : 'Edit details'}
        </button>
      </div>

      {!open ? (
        <div className={styles.detailChips}>
          <span className={styles.countChip}>status {statusLabel(entity?.status)}</span>
          <span className={styles.countChip}>due {entity?.due_at ? formatTimelineDate(entity.due_at) : 'none'}</span>
          <span className={styles.countChip}>follow up {entity?.follow_up_at ? formatTimelineDate(entity.follow_up_at) : 'none'}</span>
          <span className={styles.countChip}>priority {(entity?.properties || {}).priority || 'none'}</span>
        </div>
      ) : (
        <form
          className={styles.editorForm}
          onSubmit={(event) => {
            event.preventDefault();
            onSave();
          }}
        >
          <div className={styles.editorGrid}>
            <label className={styles.fieldStack}>
              <span className={styles.fieldLabel}>Title</span>
              <input
                className={styles.textInput}
                type="text"
                value={draft.title}
                onChange={(event) => onChange('title', event.target.value)}
              />
            </label>

            <label className={styles.fieldStack}>
              <span className={styles.fieldLabel}>Status</span>
              <select
                className={styles.selectInput}
                value={draft.status}
                onChange={(event) => onChange('status', event.target.value)}
              >
                {statuses.map((status) => (
                  <option key={status} value={status}>
                    {status.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.fieldStack}>
              <span className={styles.fieldLabel}>Due at</span>
              <input
                className={styles.textInput}
                type="datetime-local"
                value={draft.due_at}
                onChange={(event) => onChange('due_at', event.target.value)}
              />
            </label>

            <label className={styles.fieldStack}>
              <span className={styles.fieldLabel}>Follow up at</span>
              <input
                className={styles.textInput}
                type="datetime-local"
                value={draft.follow_up_at}
                onChange={(event) => onChange('follow_up_at', event.target.value)}
              />
            </label>

            <label className={styles.fieldStack}>
              <span className={styles.fieldLabel}>Priority</span>
              <select
                className={styles.selectInput}
                value={draft.priority}
                onChange={(event) => onChange('priority', event.target.value)}
              >
                {PRIORITY_OPTIONS.map((option) => (
                  <option key={option.value || 'none'} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className={styles.fieldStack}>
            <span className={styles.fieldLabel}>Content</span>
            <MarkdownEditor
              value={draft.content}
              onChange={(value) => onChange('content', value)}
              ariaLabel="Thread content"
              minRows={6}
              className={styles.editorMarkdown}
            />
          </label>

          {error ? <p className={styles.error} role="alert">{error}</p> : null}

          <div className={styles.editorActions}>
            <button
              type="button"
              className={styles.inlineButton}
              onClick={onCancel}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.inlineButtonPrimary}
              disabled={!dirty || saving}
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function AddUpdateComposer({
  entity,
  open,
  draft,
  saving,
  error,
  onToggle,
  onChange,
  onSubmit,
}) {
  const placeholder = UPDATE_PLACEHOLDERS[entity?.type] || 'What changed?';

  return (
    <section className={styles.section} aria-labelledby="thread-add-update-label">
      <div className={styles.sectionHeader}>
        <h2 id="thread-add-update-label" className={styles.sectionLabel}>Add update</h2>
        <button
          type="button"
          className={styles.inlineButton}
          onClick={onToggle}
          aria-expanded={open}
        >
          {open ? 'Hide' : 'Write update'}
        </button>
      </div>

      {!open ? (
        <p className={styles.emptyHint}>
          Record progress on{' '}
          <span className={styles.updateContext}>
            {entityTitleLabel(entity, { includeType: false })}
          </span>
          .
        </p>
      ) : (
        <form
          className={styles.updateComposer}
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <p className={styles.updateContext}>
            Updating:
            {' '}
            <strong>{entityTitleLabel(entity, { includeType: false })}</strong>
          </p>
          <label className={styles.fieldStack}>
            <span className={styles.fieldLabel}>Update text</span>
            <textarea
              className={styles.updateTextarea}
              aria-label="Update text"
              placeholder={placeholder}
              value={draft}
              onChange={(event) => onChange(event.target.value)}
              rows={4}
            />
          </label>
          {error ? <p className={styles.error} role="alert">{error}</p> : null}
          <div className={styles.editorActions}>
            <button
              type="button"
              className={styles.inlineButton}
              onClick={onToggle}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.inlineButtonPrimary}
              disabled={!draft.trim() || saving}
            >
              {saving ? 'Saving…' : 'Save update'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function UpdateOutcomePanel({ outcome, onDismiss }) {
  const { openReview } = useReview();
  if (!outcome) return null;
  const { applied = [], suggestions = [] } = outcome;
  const hasApplied = applied.length > 0;
  const hasSuggestions = suggestions.length > 0;
  if (!hasApplied && !hasSuggestions) return null;

  return (
    <div className={styles.outcomePanel} role="status" aria-live="polite">
      <div className={styles.outcomeHeader}>
        <strong>Update processed</strong>
        <button
          type="button"
          className={styles.inlineButton}
          onClick={onDismiss}
          aria-label="Dismiss update outcome"
        >
          Dismiss
        </button>
      </div>
      {hasApplied ? (
        <ul className={styles.outcomeList}>
          {applied.map((change, index) => (
            <li key={index}>{change.message}</li>
          ))}
        </ul>
      ) : null}
      {hasSuggestions ? (
        <div className={styles.outcomeSuggestions}>
          <p className={styles.outcomeCount}>
            {suggestions.length} suggested task{suggestions.length === 1 ? '' : 's'}
          </p>
          <ul className={styles.outcomeList}>
            {suggestions.map((suggestion, index) => (
              <li key={suggestion.id || index}>
                {suggestion.payload?.title || suggestion.title || 'Untitled suggestion'}
              </li>
            ))}
          </ul>
          <button
            type="button"
            className={styles.outcomeLink}
            onClick={openReview}
          >
            Review suggestions
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ThreadDetailContent({
  detail,
  events,
  canonicalText,
  onAction,
  onCapture,
  onOpenReference,
  editorOpen,
  editorDraft,
  editorDirty,
  editorSaving,
  editorError,
  onToggleEditor,
  onEditorChange,
  onEditorSave,
  onEditorCancel,
  showCaptureFab = true,
  showNextActions = true,
  updateOpen = false,
  updateDraft = '',
  updateSaving = false,
  updateError = '',
  onToggleUpdate,
  onUpdateChange,
  onUpdateSubmit,
  updateOutcome = null,
  onDismissUpdateOutcome,
  activityUpdates = [],
  activityHasMore = false,
  activityLoadingMore = false,
  onLoadMoreActivity = null,
}) {
  const entity = detail.entity;
  const entityType = entity.type;
  const summary = narrativeSummary(entity, canonicalText);
  const nextActions = buildNextActions(detail);
  const signalCards = buildSignalCards(detail, entityType);
  const people = buildPeople(detail);
  const relatedThreads = buildRelatedThreads(detail, entity);
  const references = buildReferences(detail, entity);
  const showAddUpdate = ACTIVITY_UPDATE_ENTITY_TYPES.has(entityType);
  const [longPressTarget, setLongPressTarget] = useState(null);

  const longPress = useLongPress((target) => {
    if (!target?.buttons?.length) return;
    setLongPressTarget(target);
  });

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
          {detail?.decisions_count ? (
            <>
              <span aria-hidden="true">·</span>
              <span
                className={styles.countChip}
                title={`${detail.decisions_count} decision${detail.decisions_count === 1 ? '' : 's'}`}
              >
                {detail.decisions_count} decision{detail.decisions_count === 1 ? '' : 's'}
              </span>
            </>
          ) : null}
        </div>
        <h1 className={styles.title}>{entityTitleLabel(entity, { includeType: false })}</h1>
      </header>

      <EntityAttributeEditor
        entity={entity}
        open={editorOpen}
        draft={editorDraft}
        dirty={editorDirty}
        saving={editorSaving}
        error={editorError}
        onToggle={onToggleEditor}
        onChange={onEditorChange}
        onSave={onEditorSave}
        onCancel={onEditorCancel}
      />

      <section className={styles.section} aria-labelledby="thread-narrative-label">
        <h2 id="thread-narrative-label" className={styles.sectionLabel}>Summary</h2>
        <p className={styles.narrative}>{summary}</p>
      </section>

      {showAddUpdate ? (
        <>
          <AddUpdateComposer
            entity={entity}
            open={updateOpen}
            draft={updateDraft}
            saving={updateSaving}
            error={updateError}
            onToggle={onToggleUpdate}
            onChange={onUpdateChange}
            onSubmit={onUpdateSubmit}
          />
          <UpdateOutcomePanel
            outcome={updateOutcome}
            onDismiss={onDismissUpdateOutcome}
          />
        </>
      ) : null}

      {activityUpdates.length > 0 ? (
        <section className={styles.section} aria-labelledby="thread-activity-label">
          <h2 id="thread-activity-label" className={styles.sectionLabel}>Activity</h2>
          {activityUpdates.map((update) => (
            <article key={update.id} className={styles.activityRow}>
              <time className={styles.activityMeta} dateTime={update.updated_at}>
                {formatTimelineDate(update.updated_at)}
              </time>
              <p className={styles.activityText}>{update.content}</p>
              <Link to={pathForEntity({ id: update.id, type: 'note' })} className={styles.inlineButton}>
                Open update
              </Link>
            </article>
          ))}
          {activityHasMore ? (
            <button
              type="button"
              className={styles.inlineButton}
              onClick={onLoadMoreActivity}
              disabled={activityLoadingMore || !onLoadMoreActivity}
            >
              {activityLoadingMore ? 'Loading…' : 'Load more'}
            </button>
          ) : null}
        </section>
      ) : null}

      {showNextActions ? (
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
          {nextActions.length > 0 ? (
            nextActions.map((action) => (
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
            ))
          ) : (
            <p className={styles.emptyHint}>No obvious next actions right now.</p>
          )}
        </section>
      ) : null}

      <section className={styles.section} aria-labelledby="thread-timeline-label">
        <h2 id="thread-timeline-label" className={styles.sectionLabel}>Timeline</h2>
        {timelineEvents.length > 0 ? (
          timelineEvents.map((event) => (
            <div
              key={event.id}
              className={styles.timelineRow}
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
          ))
        ) : (
          <p className={styles.emptyHint}>Nothing in the timeline yet.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="thread-people-label">
        <h2 id="thread-people-label" className={styles.sectionLabel}>People</h2>
        {people.length > 0 ? (
          people.map((person) => (
            <div key={person.id} className={styles.personRow}>
              <XGlyph type="person" />
              <Link to={pathForEntity(person.entity)} className={styles.personLink}>
                <span className={styles.personName}>
                  {entityTitleLabel(person.entity, { includeType: false })}
                </span>
                <span className={styles.personMeta}>
                  {person.relationship}
                  {person.subtitle ? ` · ${person.subtitle}` : ''}
                </span>
              </Link>
            </div>
          ))
        ) : (
          <p className={styles.emptyHint}>No people linked yet.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="thread-related-label">
        <h2 id="thread-related-label" className={styles.sectionLabel}>Related threads</h2>
        {relatedThreads.length > 0 ? (
          relatedThreads.map((thread) => (
            <div key={thread.id} className={styles.relatedRow}>
              <XGlyph type={thread.entity.type} />
              <Link to={pathForEntity(thread.entity)} className={styles.relatedLink}>
                <span className={styles.relatedTitle}>
                  {entityTitleLabel(thread.entity, { includeType: false })}
                </span>
                <span className={styles.relatedMeta}>{thread.subtitle}</span>
              </Link>
            </div>
          ))
        ) : (
          <p className={styles.emptyHint}>No related threads yet.</p>
        )}
      </section>

      <section className={styles.section} aria-labelledby="thread-references-label">
        <h2 id="thread-references-label" className={styles.sectionLabel}>References</h2>
        {references.length > 0 ? (
          <CitationsList citations={references} onOpen={onOpenReference} />
        ) : (
          <p className={styles.emptyHint}>No references yet.</p>
        )}
      </section>

      {showCaptureFab ? (
        <button
          type="button"
          className={styles.fab}
          aria-label="Capture"
          onClick={onCapture}
        >
          <Plus size={24} strokeWidth={2.2} aria-hidden="true" />
        </button>
      ) : null}

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
            <button
              type="button"
              className={styles.inlineButton}
              onClick={() => setLongPressTarget(null)}
            >
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
  const { openCapture } = useCapture();
  const { refreshSummary } = useSummary();
  const [detail, setDetail] = useState(previewDetail);
  const [events, setEvents] = useState(previewEvents);
  const [canonicalText, setCanonicalText] = useState(previewCanonical);
  const [loading, setLoading] = useState(!previewDetail);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorDraft, setEditorDraft] = useState(buildDraft(previewDetail?.entity));
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorError, setEditorError] = useState('');
  const [updateOpen, setUpdateOpen] = useState(false);
  const [updateDraft, setUpdateDraft] = useState('');
  const [updateSaving, setUpdateSaving] = useState(false);
  const [updateError, setUpdateError] = useState('');
  const [updateOutcome, setUpdateOutcome] = useState(null);
  const [extraActivityUpdates, setExtraActivityUpdates] = useState([]);
  const [activityLoadingMore, setActivityLoadingMore] = useState(false);
  const [citationEntityId, setCitationEntityId] = useState(null);
  const activeIdRef = useRef(id);

  useEffect(() => {
    activeIdRef.current = id;
  }, [id]);

  const reloadThread = useCallback(async () => {
    const requestId = id;
    const [detailResponse, eventsResponse, canonicalResponse] = await Promise.all([
      v4API.entities.detail(id),
      v4API.entities.events(id),
      v4API.entities.canonical(id).catch(() => ({ canonical: '' })),
    ]);

    if (activeIdRef.current !== requestId) return null;

    if (routeType && detailResponse?.entity?.type && detailResponse.entity.type !== routeType) {
      navigate(pathForEntity(detailResponse.entity), { replace: true, state: location.state });
      return null;
    }

    setDetail(detailResponse);
    setEvents(eventsResponse?.data || []);
    setCanonicalText(canonicalResponse?.canonical || '');
    return detailResponse;
  }, [id, routeType, navigate, location.state]);

  useEffect(() => {
    if (previewDetail) {
      setDetail(previewDetail);
      setEvents(previewEvents || []);
      setCanonicalText(previewCanonical || '');
      setEditorDraft(buildDraft(previewDetail.entity));
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError('');

    reloadThread()
      .then((loadedDetail) => {
        if (cancelled || !loadedDetail) return;
        setEditorDraft(buildDraft(loadedDetail.entity));
      })
      .catch((fetchError) => {
        if (!cancelled) setError(friendlyApiError(fetchError, 'Failed to load thread'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [previewDetail, previewEvents, previewCanonical, reloadThread]);

  useEffect(() => {
    setExtraActivityUpdates([]);
  }, [detail?.entity?.id, detail?.sections]);

  const baseActivityUpdates = useMemo(
    () => buildActivityUpdates(detail),
    [detail],
  );
  const activityTotal = activityUpdatesMeta(detail)?.total ?? baseActivityUpdates.length;
  const activityUpdates = useMemo(() => {
    const seen = new Set();
    const merged = [];
    [...baseActivityUpdates, ...extraActivityUpdates].forEach((update) => {
      if (!update?.id || seen.has(update.id)) return;
      seen.add(update.id);
      merged.push(update);
    });
    return merged;
  }, [baseActivityUpdates, extraActivityUpdates]);
  const activityHasMore = activityUpdates.length < activityTotal;

  const handleLoadMoreActivity = useCallback(async () => {
    if (!detail?.entity?.id || activityLoadingMore || !activityHasMore) return;
    setActivityLoadingMore(true);
    try {
      const response = await v4API.activityUpdates.list(detail.entity.id, {
        limit: ACTIVITY_LOAD_MORE_PAGE_SIZE,
        offset: activityUpdates.length,
      });
      setExtraActivityUpdates((current) => [...current, ...(response?.data || [])]);
    } catch (err) {
      setActionError(friendlyApiError(err, 'Failed to load more activity'));
    } finally {
      setActivityLoadingMore(false);
    }
  }, [detail, activityLoadingMore, activityHasMore, activityUpdates.length]);

  useEffect(() => {
    if (!detail?.entity || editorOpen) return;
    setEditorDraft(buildDraft(detail.entity));
  }, [detail, editorOpen]);

  const handleAction = useCallback(async (button) => {
    setActionError('');
    try {
      if (button.action === 'done' && button.entityId) {
        await v4API.entities.update(button.entityId, { status: 'done' });
        await reloadThread();
        refreshSummary();
        return;
      }

      if (button.action === 'remind' && button.entityId) {
        const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
        await v4API.entities.update(button.entityId, { follow_up_at: tomorrow });
        await reloadThread();
        refreshSummary();
        return;
      }
    } catch (err) {
      setActionError(friendlyApiError(err, 'Action failed'));
    }
  }, [reloadThread, refreshSummary]);

  const handleEditorChange = useCallback((field, value) => {
    setEditorError('');
    setEditorDraft((current) => ({ ...current, [field]: value }));
  }, []);

  const handleEditorCancel = useCallback(() => {
    setEditorDraft(buildDraft(detail?.entity));
    setEditorError('');
    setEditorOpen(false);
  }, [detail]);

  const handleEditorSave = useCallback(async () => {
    if (!detail?.entity) return;
    setEditorSaving(true);
    setEditorError('');

    try {
      await v4API.entities.update(detail.entity.id, buildUpdatePayload(detail.entity, editorDraft));
      const refreshed = await reloadThread();
      if (refreshed?.entity) {
        setEditorDraft(buildDraft(refreshed.entity));
      }
      setEditorOpen(false);
      refreshSummary();
    } catch (err) {
      setEditorError(friendlyApiError(err, 'Failed to save details'));
    } finally {
      setEditorSaving(false);
    }
  }, [detail, editorDraft, reloadThread, refreshSummary]);

  const handleCapture = useCallback(() => {
    openCapture();
  }, [openCapture]);

  const handleToggleUpdate = useCallback(() => {
    setUpdateError('');
    setUpdateOpen((current) => !current);
  }, []);

  const handleUpdateChange = useCallback((value) => {
    setUpdateError('');
    setUpdateDraft(value);
  }, []);

  const handleDismissUpdateOutcome = useCallback(() => {
    setUpdateOutcome(null);
  }, []);

  const handleUpdateSubmit = useCallback(async () => {
    if (!detail?.entity || !updateDraft.trim()) return;
    setUpdateSaving(true);
    setUpdateError('');

    try {
      const previousEntity = detail.entity;
      const result = await v4API.activityUpdates.create(detail.entity.id, updateDraft.trim());
      if (result?.skipped) {
        const message = result.reason === 'near_duplicate'
          ? 'A very similar update was saved recently. Edit your text or open the existing update.'
          : 'That exact update was already saved recently.';
        setUpdateError(message);
        return;
      }
      setUpdateDraft('');
      setUpdateOpen(false);

      const target = result?.target || previousEntity;
      const applied = [];
      if (target.status && target.status !== previousEntity.status) {
        applied.push({ message: `Status updated to ${statusLabel(target.status)}` });
      }
      if (target.follow_up_at !== previousEntity.follow_up_at) {
        applied.push({ message: `Follow-up set to ${formatTimelineDate(target.follow_up_at)}` });
      }
      setUpdateOutcome({
        applied,
        suggestions: result?.suggestions || [],
      });

      await reloadThread();
      refreshSummary();
    } catch (err) {
      setUpdateError(friendlyApiError(err, 'Failed to save update'));
    } finally {
      setUpdateSaving(false);
    }
  }, [detail, updateDraft, reloadThread, refreshSummary]);

  const editorDirty = useMemo(
    () => isDraftDirty(detail?.entity, editorDraft),
    [detail, editorDraft],
  );

  if (loading) {
    return (
      <main className={styles.page} aria-busy="true">
        <p className={styles.loading}>Loading thread…</p>
      </main>
    );
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
      {actionError ? <p className={styles.error} role="alert">{actionError}</p> : null}
      <ThreadDetailContent
        detail={detail}
        events={events}
        canonicalText={canonicalText}
        onAction={handleAction}
        onCapture={handleCapture}
        onOpenReference={(citation) => setCitationEntityId(citation.entity_id)}
        editorOpen={editorOpen}
        editorDraft={editorDraft}
        editorDirty={editorDirty}
        editorSaving={editorSaving}
        editorError={editorError}
        onToggleEditor={() => {
          setEditorError('');
          setEditorOpen((current) => {
            if (!current && detail?.entity) {
              setEditorDraft(buildDraft(detail.entity));
            }
            return !current;
          });
        }}
        onEditorChange={handleEditorChange}
        onEditorSave={handleEditorSave}
        onEditorCancel={handleEditorCancel}
        updateOpen={updateOpen}
        updateDraft={updateDraft}
        updateSaving={updateSaving}
        updateError={updateError}
        onToggleUpdate={handleToggleUpdate}
        onUpdateChange={handleUpdateChange}
        onUpdateSubmit={handleUpdateSubmit}
        updateOutcome={updateOutcome}
        onDismissUpdateOutcome={handleDismissUpdateOutcome}
        activityUpdates={activityUpdates}
        activityHasMore={activityHasMore}
        activityLoadingMore={activityLoadingMore}
        onLoadMoreActivity={handleLoadMoreActivity}
        showCaptureFab={false}
      />
      <CitationEntitySheet
        entityId={citationEntityId}
        open={!!citationEntityId}
        onClose={() => setCitationEntityId(null)}
      />
    </main>
  );
}

export { ThreadDetailContent };
