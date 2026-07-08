import { useCallback, useEffect, useState } from 'react';
import { friendlyApiError, v4API } from '../api/v4Client';
import { ENTITY_TYPE_GLYPHS, SURFACE_LABELS, entityTypeLabel } from './vocab';
import styles from './StreamSurface.module.css';

function entryDate(entry) {
  return entry?.created_at || entry?.updated_at || null;
}

function formatDayLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown day';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

function formatTimeLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function groupEntriesByDay(entries) {
  const groups = [];
  const byDay = new Map();

  entries.forEach((entry) => {
    const stamp = entryDate(entry);
    const key = stamp ? formatDayLabel(stamp) : 'Unknown day';
    if (!byDay.has(key)) {
      const group = { key, label: key, items: [] };
      byDay.set(key, group);
      groups.push(group);
    }
    byDay.get(key).items.push(entry);
  });

  return groups;
}

function streamEntryTitle(entry) {
  return entry?.title || entry?.content || 'Untitled capture';
}

export default function StreamSurface() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadStream = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const payload = await v4API.entities.list({
        type: 'note',
        limit: 100,
        sort: 'created_at',
        order: 'desc',
        lifecycle: 'active',
      });
      setEntries(payload?.data || []);
    } catch (err) {
      setEntries([]);
      setError(friendlyApiError(err, 'Could not load stream.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStream();
  }, [loadStream]);

  const groups = groupEntriesByDay(entries);

  return (
    <section className={styles.surface} aria-label={SURFACE_LABELS.stream}>
      <header className={styles.header}>
        <h1 className={styles.title}>{SURFACE_LABELS.stream}</h1>
        <p className={styles.subtitle}>
          Recent captures, grouped by day so the stream reads like a chronological work log.
        </p>
      </header>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      {loading ? <p className={styles.empty}>Loading stream…</p> : null}
      {!loading && groups.length === 0 ? <p className={styles.empty}>No captures in stream yet.</p> : null}

      {!loading && groups.length > 0 ? (
        <div className={styles.groupList}>
          {groups.map((group) => (
            <section key={group.key} className={styles.group}>
              <div className={styles.groupHeader}>
                <h2 className={styles.groupTitle}>{group.label}</h2>
                <span className={styles.groupCount}>{group.items.length}</span>
              </div>

              <ul className={styles.entryList}>
                {group.items.map((entry) => {
                  const type = entry?.type || 'note';
                  const stamp = entryDate(entry);
                  return (
                    <li key={entry.id} className={styles.entry}>
                      <div className={styles.entryGlyph} aria-hidden="true">
                        {ENTITY_TYPE_GLYPHS[type] || '?'}
                      </div>
                      <div className={styles.entryBody}>
                        <div className={styles.entryHeader}>
                          <span className={styles.entryType}>{entityTypeLabel(type)}</span>
                          {stamp ? (
                            <time className={styles.entryTime} dateTime={stamp}>
                              {formatTimeLabel(stamp)}
                            </time>
                          ) : null}
                        </div>
                        <p className={styles.entryTitle}>{streamEntryTitle(entry)}</p>
                        {entry?.content && entry.content !== entry.title ? (
                          <p className={styles.entryContent}>{entry.content}</p>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      ) : null}
    </section>
  );
}
