/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import mdStyles from '../components/MarkdownContent.module.css';
import styles from './V4Today.module.css';

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function EntitySection({ title, items }) {
  return (
    <section className={styles.panel}>
      <h2>
        {title}
        {items.length > 0 && <span className={styles.count}>{items.length}</span>}
      </h2>
      {items.length === 0 ? (
        <p className={styles.empty}>Nothing here.</p>
      ) : (
        <ul className={styles.list}>
          {items.map((entity) => (
            <li key={entity.id}>
              <Link to={entityPath(entity)}>
                <strong>{entity.title || 'Untitled'}</strong>
                {entity.content && (
                  <div className={`${mdStyles.md} ${mdStyles.mdCompact}`}>
                    <MarkdownContent content={entity.content} />
                  </div>
                )}
                <span>{entity.type} · {entity.status}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function V4Today() {
  const [today, setToday] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    v4API.today()
      .then(setToday)
      .catch((err) => setError(err.message || 'Failed to load today'));
  }, []);

  if (error) {
    return (
      <main className={styles.today}>
        <section className={styles.panel}><p>{error}</p></section>
      </main>
    );
  }

  if (!today) {
    return (
      <main className={styles.today}>
        <section className={styles.panel}><p>Loading today...</p></section>
      </main>
    );
  }

  const dateLabel = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  return (
    <main className={styles.today}>
      <header className={styles.dateHeader}>
        <h1>{dateLabel}</h1>
      </header>

      <EntitySection title="Overdue and Today" items={today.follow_ups || []} />
      <EntitySection title="Blocked or Waiting" items={today.blocked_or_waiting_tasks || []} />
      <EntitySection title="Projects Without Open Tasks" items={today.projects_without_open_tasks || []} />
      <EntitySection title="Recent Notes" items={today.recent_notes || []} />

      <section className={styles.panel}>
        <h2>
          Suggestions
          {today.pending_suggestions?.length > 0 && (
            <span className={styles.count}>{today.pending_suggestions.length}</span>
          )}
        </h2>
        {today.pending_suggestions?.length ? (
          <ul className={styles.list}>
            {today.pending_suggestions.map((suggestion) => (
              <li key={suggestion.id}>
                <Link to="/suggestions">
                  <strong>{suggestion.payload?.title || suggestion.suggestion_type}</strong>
                  <span>{suggestion.suggestion_type}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.empty}>No pending suggestions.</p>
        )}
      </section>
    </main>
  );
}
