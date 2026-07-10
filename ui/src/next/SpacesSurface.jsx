import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { formatLocalDate } from './dateFormat';
import { StatusBadge } from './statusTheme';
import { SURFACE_LABELS } from './vocab';
import styles from './SpacesSurface.module.css';

function spaceTypeLabel(space) {
  return space.type === 'project' ? 'Finish line' : 'Ongoing';
}

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
        <p className={styles.subtitle}>
          Initiatives and contexts — open any space for its dossier, brief, decisions, and commitments.
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
        <ul className={styles.spaceGrid}>
          {spaces.map((space) => (
            <li key={space.id} className={styles.spaceCard}>
              <Link to={`/spaces/${space.id}`} className={styles.spaceTitle}>
                {space.title}
              </Link>
              <div className={styles.spaceMeta}>
                <span className={styles.spaceChip}>{spaceTypeLabel(space)}</span>
                <StatusBadge status={space.status || 'active'} />
                {space.due_at ? (
                  <span className={`${styles.spaceChip} ${styles.spaceChipAccent}`}>
                    Finish {formatLocalDate(space.due_at)}
                  </span>
                ) : null}
                {space.follow_up_at ? (
                  <span className={styles.spaceChip}>
                    Follow-up {formatLocalDate(space.follow_up_at)}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
