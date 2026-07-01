import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Link } from 'react-router-dom';
import { Loader2, RefreshCw, Search } from 'lucide-react';
import { v4API } from '../api/v4Client';
import { pathForEntity } from './v5ThreadDetailUtils';
import styles from './V5Memory.module.css';

const ENTITY_TYPES = [
  { value: '', label: 'All' },
  { value: 'note', label: 'Notes' },
  { value: 'task', label: 'Tasks' },
  { value: 'project', label: 'Projects' },
  { value: 'person', label: 'People' },
  { value: 'area', label: 'Areas' },
  { value: 'resource', label: 'Resources' },
];

const ACTOR_FILTERS = [
  { value: '', label: 'All' },
  { value: 'user', label: 'You' },
  { value: 'agent:', label: 'Agent' },
];

function entityPath(event) {
  const type = event.entity_type;
  const id = event.entity_id;
  if (!type || !id) return '#';
  return pathForEntity({ id, type });
}

function eventGlyph(event) {
  if (event.actor?.startsWith('agent:')) return '✦';
  if (event.event_type === 'activity_update_added') return '📝';
  if (event.event_type?.includes('decision')) return '⚖';
  if (event.event_type === 'created') return '▣';
  return '·';
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function dateHeaderLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown date';

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 7);

  const ts = date.getTime();
  if (ts >= startOfToday.getTime()) return 'Today';
  if (ts >= startOfYesterday.getTime()) return 'Yesterday';
  if (ts >= startOfWeek.getTime()) return 'Last week';

  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function groupEventsByDate(events) {
  const groups = new Map();
  for (const event of events) {
    const header = dateHeaderLabel(event.occurred_at);
    if (!groups.has(header)) {
      groups.set(header, []);
    }
    groups.get(header).push(event);
  }
  return [...groups.entries()];
}

function FilterChips({ options, value, onChange, ariaLabel }) {
  return (
    <div className={styles.chipGroup} role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`${styles.chip} ${value === option.value ? styles.chipActive : ''}`}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function EventCard({ event }) {
  const path = entityPath(event);
  return (
    <article className={styles.eventCard} data-testid={`memory-event-${event.id}`}>
      <div className={styles.eventMeta}>
        <time className={styles.eventTime} dateTime={event.occurred_at}>
          {formatTime(event.occurred_at)}
        </time>
        <span className={styles.eventGlyph} aria-hidden="true">{eventGlyph(event)}</span>
        <Link to={path} className={styles.eventEntityType}>
          {event.entity_type}
        </Link>
        <span className={styles.eventActor}>{event.actor}</span>
      </div>
      <p className={styles.eventNarration}>{event.narration}</p>
    </article>
  );
}

export default function V5Memory({ previewData }) {
  const [events, setEvents] = useState(previewData?.events || []);
  const [nextOffset, setNextOffset] = useState(previewData?.next_offset || null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const [search, setSearch] = useState('');
  const [entityType, setEntityType] = useState('');
  const [actorFilter, setActorFilter] = useState('');
  const [threadId, setThreadId] = useState('');

  const touchStartY = useRef(null);
  const observerTarget = useRef(null);

  const filters = useMemo(() => ({
    entity_type: entityType,
    actor: actorFilter,
    thread_id: threadId,
  }), [entityType, actorFilter, threadId]);

  const hasActiveFilters = entityType || actorFilter || threadId || search;

  const loadEvents = useCallback(async (offset = 0, append = false) => {
    if (offset === 0) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError('');
    try {
      const params = {
        limit: 50,
        offset,
        ...(entityType ? { entity_type: entityType } : {}),
        ...(actorFilter ? { actor: actorFilter } : {}),
        ...(threadId ? { thread_id: threadId } : {}),
      };
      const data = await v4API.timeline(params);
      if (append) {
        setEvents((prev) => [...prev, ...data.events]);
      } else {
        setEvents(data.events);
      }
      setNextOffset(data.next_offset);
    } catch (err) {
      setError(err.message || 'Failed to load timeline');
      if (!append) setEvents([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
      setRefreshing(false);
    }
  }, [entityType, actorFilter, threadId]);

  useEffect(() => {
    if (previewData) {
      setEvents(previewData.events || []);
      setNextOffset(previewData.next_offset || null);
      return;
    }
    loadEvents(0, false);
  }, [previewData, loadEvents]);

  useEffect(() => {
    if (previewData) return;
    loadEvents(0, false);
  }, [entityType, actorFilter, threadId]);

  useEffect(() => {
    if (previewData) return;
    if (!observerTarget.current || !nextOffset) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && nextOffset && !loadingMore && !loading) {
          loadEvents(nextOffset, true);
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(observerTarget.current);
    return () => observer.disconnect();
  }, [nextOffset, loadingMore, loading, loadEvents, previewData]);

  function handleRefresh() {
    if (refreshing || loading || previewData) return;
    setRefreshing(true);
    loadEvents(0, false);
  }

  function handleTouchStart(event) {
    if (previewData) return;
    touchStartY.current = event.touches[0].clientY;
  }

  function handleTouchEnd(event) {
    if (previewData || touchStartY.current == null) return;
    const endY = event.changedTouches[0].clientY;
    const diff = endY - touchStartY.current;
    touchStartY.current = null;
    if (diff > 80 && window.scrollY < 10) {
      handleRefresh();
    }
  }

  const filteredEvents = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return events;
    return events.filter((event) => (
      (event.narration || '').toLowerCase().includes(q)
      || (event.entity_type || '').toLowerCase().includes(q)
      || (event.actor || '').toLowerCase().includes(q)
    ));
  }, [events, search]);

  const grouped = useMemo(() => groupEventsByDate(filteredEvents), [filteredEvents]);

  return (
    <main
      className={styles.page}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      <header className={styles.header}>
        <h1 className={styles.title}>Memory</h1>
        <p className={styles.subtitle}>Everything that happened, in order.</p>
      </header>

      <div className={styles.controls}>
        <div className={styles.searchBox}>
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            placeholder="Search events…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className={styles.searchInput}
            aria-label="Search events"
          />
        </div>

        <div className={styles.filterStack}>
          <FilterChips
            options={ENTITY_TYPES}
            value={entityType}
            onChange={setEntityType}
            ariaLabel="Filter by entity type"
          />
          <FilterChips
            options={ACTOR_FILTERS}
            value={actorFilter}
            onChange={setActorFilter}
            ariaLabel="Filter by actor"
          />
          <div className={styles.threadFilter}>
            <input
              type="text"
              placeholder="Thread ID filter"
              value={threadId}
              onChange={(event) => setThreadId(event.target.value.trim())}
              className={styles.threadInput}
              aria-label="Filter by thread ID"
            />
          </div>
        </div>
      </div>

      {refreshing && (
        <div className={styles.refreshIndicator}>
          <RefreshCw size={16} className={styles.spin} aria-hidden="true" />
          <span>Refreshing…</span>
        </div>
      )}

      {loading && !refreshing ? (
        <div className={styles.loading}>
          <Loader2 size={20} className={styles.spin} aria-hidden="true" />
          <span>Loading memory…</span>
        </div>
      ) : null}

      {error ? <p className={styles.error}>{error}</p> : null}

      {!loading && !error && grouped.length === 0 ? (
        <p className={styles.emptyHint}>
          {hasActiveFilters
            ? 'No events match your filters.'
            : 'Nothing in your memory yet. Capture something first.'}
        </p>
      ) : null}

      <div className={styles.timeline}>
        {grouped.map(([header, headerEvents]) => (
          <section key={header} className={styles.dateGroup} aria-label={header}>
            <h2 className={styles.dateHeader}>{header}</h2>
            <div className={styles.eventList}>
              {headerEvents.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {loadingMore ? (
        <div className={styles.loadingMore}>
          <Loader2 size={18} className={styles.spin} aria-hidden="true" />
          <span>Loading more…</span>
        </div>
      ) : null}

      {!previewData && nextOffset ? (
        <div ref={observerTarget} className={styles.loadTrigger} aria-hidden="true" />
      ) : null}
    </main>
  );
}
