import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { SURFACE_LABELS } from './vocab';
import styles from './DossierSurface.module.css';

export default function SpacesSurface() {
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadSpaces = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [projects, areas] = await Promise.all([
        v4API.entities.list({ type: 'project' }),
        v4API.entities.list({ type: 'area' }),
      ]);
      const nextSpaces = [...(projects?.data || []), ...(areas?.data || [])].sort((left, right) =>
        left.title.localeCompare(right.title),
      );
      setSpaces(nextSpaces);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load spaces.'));
      setSpaces([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSpaces();
  }, [loadSpaces]);

  return (
    <section className={styles.surface} aria-label={SURFACE_LABELS.spaces}>
      <header className={styles.header}>
        <h1 className={styles.title}>{SURFACE_LABELS.spaces}</h1>
        <p className={styles.panelMeta}>
          Initiatives and contexts — each opens as a dossier for cold-start steering.
        </p>
      </header>

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {loading ? <p className={styles.empty}>Loading spaces…</p> : null}
      {!loading && spaces.length === 0 ? (
        <p className={styles.empty}>No spaces yet. Capture work and link it to a project or area.</p>
      ) : null}

      {!loading && spaces.length > 0 ? (
        <ul className={styles.list}>
          {spaces.map((space) => (
            <li key={space.id} className={styles.listItem}>
              <Link to={`/spaces/${space.id}`} className={styles.itemTitle}>
                {space.title}
              </Link>
              <p className={styles.itemMeta}>
                {space.type === 'project' ? 'Space with finish line' : 'Ongoing space'} · {space.status || 'active'}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
