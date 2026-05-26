/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import MarkdownContent from '../components/MarkdownContent';
import styles from './V4Today.module.css';

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function EntitySection({ title, items }) {
  if (items.length === 0) return null;
  return (
    <section className={styles.panel}>
      <h2>
        {title}
        <span className={styles.count}>{items.length}</span>
      </h2>
      <ul className={styles.list}>
        {items.map((entity) => (
          <li key={entity.id}>
            <Link to={entityPath(entity)}>
              <strong>{entity.title || 'Untitled'}</strong>
              {entity.content && (
                <MarkdownContent content={entity.content} compact />
              )}
              <span>{entity.type} · {entity.status}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EmptyStub({ label }) {
  return <span className={styles.emptyStub}>{label}</span>;
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

  const sectionData = [
    { key: 'follow_ups', title: 'Overdue and Today', items: today.follow_ups || [], stub: 'Nothing overdue' },
    { key: 'blocked', title: 'Blocked or Waiting', items: today.blocked_or_waiting_tasks || [], stub: 'Nothing blocked' },
    { key: 'idle', title: 'Projects Without Open Tasks', items: today.projects_without_open_tasks || [], stub: 'All projects active' },
    { key: 'notes', title: 'Recent Notes', items: today.recent_notes || [], stub: 'No recent notes' },
  ];

  const pendingSuggestions = today.pending_suggestions || [];
  const emptyStubs = sectionData.filter((s) => s.items.length === 0).map((s) => s.stub);
  if (pendingSuggestions.length === 0) emptyStubs.push('No pending suggestions');

  return (
    <main className={styles.today}>
      <header className={styles.dateHeader}>
        <h1>{dateLabel}</h1>
      </header>

      {sectionData.map((section) => (
        <EntitySection key={section.key} title={section.title} items={section.items} />
      ))}

      {pendingSuggestions.length > 0 && (
        <section className={styles.panel}>
          <h2>
            Suggestions
            <span className={styles.count}>{pendingSuggestions.length}</span>
          </h2>
          <ul className={styles.list}>
            {pendingSuggestions.map((suggestion) => (
              <li key={suggestion.id}>
                <Link to="/suggestions">
                  <strong>{suggestion.payload?.title || suggestion.suggestion_type}</strong>
                  <span>{suggestion.suggestion_type}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {emptyStubs.length > 0 && (
        <footer className={styles.emptyRow} aria-label="All clear sections">
          {emptyStubs.map((label) => (
            <EmptyStub key={label} label={label} />
          ))}
        </footer>
      )}
    </main>
  );
}
