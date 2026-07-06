import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import EntityGlyphCircle from '../components/EntityGlyphCircle';
import { entityTitleLabel } from '../utils/entityDisplay';
import { labDetailPath } from './labPaths';
import styles from './LabPeople.module.css';

function deriveSummary(detail) {
  const pulse = detail?.pulse;
  const summary = pulse?.summary || {};
  const openTasks = summary.open_tasks ?? 0;
  const quiet = (summary.quiet_tasks ?? 0) > 0;

  const currentLoad = detail?.current_load || [];
  const lastHeard = currentLoad
    .map((item) => item.last_heard_at)
    .filter(Boolean)
    .sort((a, b) => new Date(b) - new Date(a))[0] || null;

  return { openTasks, quiet, lastHeard };
}

function formatLastHeard(iso) {
  if (!iso) return 'No updates yet';
  const date = new Date(iso);
  const now = new Date();
  const days = Math.floor((now - date) / (1000 * 60 * 60 * 24));
  if (days < 1) return 'Last heard today';
  if (days === 1) return 'Last heard yesterday';
  return `Last heard ${days} days ago`;
}

function openTaskLabel(count) {
  if (count === 0) return 'No open tasks';
  return `${count} open task${count === 1 ? '' : 's'}`;
}

export default function LabPeople() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    async function load() {
      try {
        const listResponse = await v4API.entities.list({
          type: 'person',
          lifecycle: 'active',
          limit: 200,
          sort: 'updated_at',
          order: 'desc',
        });
        const people = listResponse?.data || [];
        if (!active) return;

        if (people.length === 0) {
          setItems([]);
          setLoading(false);
          return;
        }

        const details = await Promise.all(
          people.map(async (person) => {
            try {
              const detail = await v4API.entities.detail(person.id);
              return { person, detail };
            } catch (detailError) {
              return { person, error: detailError };
            }
          }),
        );

        if (!active) return;
        setItems(details);
      } catch (err) {
        if (!active) return;
        setError(friendlyApiError(err, 'Failed to load people'));
        setItems([]);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => { active = false; };
  }, []);

  if (loading) {
    return (
      <div className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading people…</p>
      </div>
    );
  }

  if (error && items.length === 0) {
    return (
      <div className={styles.page}>
        <p className={styles.errorMessage} role="alert">{error}</p>
      </div>
    );
  }

  return (
    <div className={styles.page} aria-label="People list">
      <header className={styles.header}>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>People</h1>
          <p className={styles.subtitle}>
            {items.length}
            {' '}
            {items.length === 1 ? 'person' : 'people'}
          </p>
        </div>
      </header>

      {error ? <p className={styles.errorMessage} role="alert">{error}</p> : null}

      {items.length > 0 ? (
        <ul className={styles.list}>
          {items.map(({ person, detail, error: detailError }) => {
            const summary = detail ? deriveSummary(detail) : null;
            return (
              <li key={person.id}>
                <Link
                  to={labDetailPath(person)}
                  className={styles.row}
                  data-entity-type="person"
                >
                  <EntityGlyphCircle type="person" />
                  <div className={styles.rowMain}>
                    <span className={styles.rowTitle}>
                      {entityTitleLabel(person, { includeType: false })}
                    </span>
                    {detailError ? (
                      <span className={styles.rowMeta}>Could not load summary</span>
                    ) : summary ? (
                      <span className={styles.rowMeta}>
                        {openTaskLabel(summary.openTasks)}
                        <span className={styles.metaDot}>·</span>
                        {formatLastHeard(summary.lastHeard)}
                        {summary.quiet ? (
                          <>
                            <span className={styles.metaDot}>·</span>
                            <span className={styles.quietFlag}>Gone quiet</span>
                          </>
                        ) : null}
                      </span>
                    ) : null}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={styles.emptyHint}>
          No people yet. Mention someone in a capture to add them.
        </p>
      )}
    </div>
  );
}
