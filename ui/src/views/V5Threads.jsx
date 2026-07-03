import { useEffect, useMemo, useState } from 'react';
import { v4API, friendlyApiError } from '../api/v4Client';
import V5EntityRow from './V5EntityRow';
import styles from './V5Threads.module.css';

function bandForScore(score) {
  if (score >= 75) return 'hot';
  if (score >= 25) return 'warm';
  return 'ambient';
}

function groupThreads(threads) {
  const groups = { hot: [], warm: [], ambient: [] };
  for (const thread of threads) {
    groups[bandForScore(thread.attention_score ?? 0)].push(thread);
  }
  return groups;
}

export default function V5Threads() {
  const [threads, setThreads] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    v4API.threads({ rank: 'attention', limit: 200 })
      .then((data) => {
        if (!active) return;
        setThreads(data?.threads || []);
        setTotalCount(data?.total_count ?? (data?.threads || []).length);
      })
      .catch((err) => {
        if (!active) return;
        setError(friendlyApiError(err, 'Failed to load threads'));
        setThreads([]);
        setTotalCount(0);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const grouped = useMemo(() => groupThreads(threads), [threads]);

  if (loading) {
    return (
      <main className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading threads…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className={styles.page}>
        <p className={styles.errorMessage} role="alert">{error}</p>
      </main>
    );
  }

  const showingPartial = totalCount > threads.length;

  return (
    <main className={styles.page} aria-label="Threads">
      <header className={styles.headerRow}>
        <h1 className={styles.title}>Threads · {totalCount} active</h1>
        <p className={styles.subtitle}>
          ranked by attention
          {showingPartial ? ` · showing ${threads.length}` : ''}
        </p>
      </header>

      {grouped.hot.length ? (
        <section aria-label="Hot threads">
          <h2 className={styles.sectionLabel}>hot</h2>
          <div className={styles.list}>
            {grouped.hot.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} />
            ))}
          </div>
        </section>
      ) : null}

      {grouped.warm.length ? (
        <section aria-label="Warm threads">
          <h2 className={styles.sectionLabel}>warm</h2>
          <div className={styles.list}>
            {grouped.warm.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} />
            ))}
          </div>
        </section>
      ) : null}

      {grouped.ambient.length ? (
        <section aria-label="Ambient threads">
          <h2 className={styles.sectionLabel}>ambient</h2>
          <div className={styles.list}>
            {grouped.ambient.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} variant="ambient" />
            ))}
          </div>
        </section>
      ) : null}

      {threads.length === 0 ? (
        <p className={styles.statusMessage}>No active threads yet.</p>
      ) : null}
    </main>
  );
}
