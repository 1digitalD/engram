import { useCallback, useEffect, useState } from 'react';

import { friendlyApiError, v4API } from '../api/v4Client';
import { EntryAttachAffordance } from './TypedAffordances';
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
  const [targets, setTargets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionNote, setActionNote] = useState('');

  const loadStream = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await v4API.entities.list({
        type: 'note',
        lifecycle: 'active',
        limit: 100,
      });
      setEntries(payload?.data || []);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load stream.'));
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTargets = useCallback(async () => {
    try {
      const [tasks, projects, areas, people] = await Promise.all([
        v4API.entities.list({ type: 'task', limit: 50 }),
        v4API.entities.list({ type: 'project', limit: 50 }),
        v4API.entities.list({ type: 'area', limit: 50 }),
        v4API.entities.list({ type: 'person', limit: 50 }),
      ]);
      setTargets([...(tasks?.data || []), ...(projects?.data || []), ...(areas?.data || []), ...(people?.data || [])]);
    } catch (err) {
      setError((current) => current || friendlyApiError(err, 'Could not load attach targets.'));
    }
  }, []);

  useEffect(() => {
    loadStream();
  }, [loadStream]);

  useEffect(() => {
    loadTargets();
  }, [loadTargets]);

  async function handleAttach(entryId, targetId) {
    setError('');
    try {
      await v4API.entities.createLink(entryId, {
        target_id: targetId,
        relationship_type: 'related',
      });
      setActionNote('Stream entry attached.');
    } catch (err) {
      setError(friendlyApiError(err, 'Could not attach stream entry.'));
    }
  }

  const groups = groupEntriesByDay(entries);

  return (
    <section className={styles.surface} aria-label={SURFACE_LABELS.stream}>
      <header className={styles.header}>
        <h1 className={styles.title}>{SURFACE_LABELS.stream}</h1>
        <p className={styles.subtitle}>
          Chronological capture log for notes and updates that landed in the workspace. Attach a receipt inline when it
          belongs with a person, space, or commitment.
        </p>
      </header>

      {actionNote ? <p className={styles.subtitle}>{actionNote}</p> : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
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
                  const title = streamEntryTitle(entry);
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
                        <p className={styles.entryTitle}>{title}</p>
                        {entry?.content && entry.content !== entry.title ? (
                          <p className={styles.entryContent}>{entry.content}</p>
                        ) : null}
                        {type === 'note' ? (
                          <EntryAttachAffordance
                            entryTitle={title}
                            targets={targets}
                            onAttach={(targetId) => handleAttach(entry.id, targetId)}
                          />
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
