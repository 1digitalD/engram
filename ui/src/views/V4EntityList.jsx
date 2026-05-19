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
    if (!title.trim()) return;
    setLoading(true);
    setError('');
    try {
      const response = await v4API.entities.create({
        type,
        title: title.trim(),
        content: content.trim() || null,
      });
      setEntities((current) => [response.data, ...current]);
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
      <section className={styles.panel}>
        <p className={styles.eyebrow}>Engram v4</p>
        <h1>{pluralTitle[type]}</h1>
        <form onSubmit={handleCreate} className={styles.form} aria-label={`Create ${type}`}>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={`New ${type} title`}
            aria-label="Title"
          />
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Optional content"
            aria-label="Content"
            rows={3}
          />
          <button type="submit" disabled={loading || !title.trim()}>
            Create {type}
          </button>
        </form>
        {error && <div className={styles.error}>{error}</div>}
      </section>

      <section className={styles.panel}>
        <h2>{pluralTitle[type]} list</h2>
        {entities.length === 0 ? (
          <p>No {pluralTitle[type].toLowerCase()} yet.</p>
        ) : (
          <ul className={styles.cards}>
            {entities.map((entity) => (
              <li key={entity.id}>
                <Link to={detailPath(entity)}>
                  <strong>{entity.title || 'Untitled'}</strong>
                  <span>{entity.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
