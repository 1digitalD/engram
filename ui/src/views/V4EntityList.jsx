/* eslint-disable no-unused-vars */
import React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API } from '../api/v4Client';
import styles from './V4EntityScreens.module.css';

const pluralTitle = {
  note: 'Notes',
  task: 'Tasks',
  project: 'Projects',
  area: 'Areas',
  person: 'People',
  resource: 'Resources',
};

function detailPath(entity) {
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

export default function V4EntityList({ type }) {
  const [entities, setEntities] = useState([]);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    v4API.entities.list({ type, limit: 100 })
      .then((response) => {
        if (active) setEntities(response.data || []);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [type]);

  async function handleCreate(event) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    const trimmedContent = content.trim();
    if (type === 'note' ? !trimmedTitle && !trimmedContent : !trimmedTitle) return;
    setLoading(true);
    setError('');
    try {
      if (type === 'note') {
        const response = await v4API.capture({
          title: trimmedTitle || undefined,
          content: trimmedContent || trimmedTitle,
          source: 'ui',
          mode: 'auto',
        });
        setEntities((current) => [response.source_note, ...current]);
      } else {
        const response = await v4API.entities.create({
          type,
          title: trimmedTitle,
          content: trimmedContent || null,
        });
        setEntities((current) => [response.data, ...current]);
      }
      setTitle('');
      setContent('');
    } catch (err) {
      setError(err.message || `Failed to create ${type}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.screen}>
      <section className={styles.listHeaderPanel}>
        <div className={styles.listHeading}>
          <h1>{pluralTitle[type]}</h1>
        </div>
        <form onSubmit={handleCreate} className={styles.quickCreateForm} aria-label={`Create ${type}`}>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={type === 'note' ? 'Optional note title' : `New ${type} title`}
            aria-label="Title"
          />
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder={type === 'note' ? 'Write the note. AI can safely extract metadata and links.' : 'Optional content'}
            aria-label="Content"
            rows={type === 'note' ? 2 : 1}
          />
          <button className={styles.primaryButton} type="submit" disabled={loading || (type === 'note' ? !title.trim() && !content.trim() : !title.trim())}>
            {loading ? 'Creating...' : `Create ${type}`}
          </button>
        </form>
        {error && <div className={styles.error}>{error}</div>}
      </section>

      <section className={styles.listPanel}>
        <header className={styles.segmentHeader}>
          <div className={styles.segmentHeaderRight}>
            <span className={styles.countPill}>{entities.length}</span>
          </div>
        </header>
        {entities.length === 0 ? (
          <p className={styles.emptyText}>No {pluralTitle[type].toLowerCase()} yet.</p>
        ) : (
          <ul className={styles.cards}>
            {entities.map((entity) => (
              <li key={entity.id}>
                <Link to={detailPath(entity)}>
                  <strong>{entity.title || 'Untitled'}</strong>
                  <span className={styles.metaRow}>
                    <span className={styles.statusPill}>{entity.status}</span>
                    {entity.properties?.priority && (
                      <span className={styles.priorityPill}>Priority {entity.properties.priority}</span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
