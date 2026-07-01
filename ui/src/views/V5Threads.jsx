import { useEffect, useMemo, useState } from 'react';
import { v4API, friendlyApiError } from '../api/v4Client';
import V5EntityRow from './V5EntityRow';
import pageStyles from '../styles/v5.module.css';

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    v4API.threads({ rank: 'attention', limit: 20 })
      .then((data) => {
        if (!active) return;
        setThreads(data?.threads || []);
      })
      .catch((err) => {
        if (!active) return;
        setError(friendlyApiError(err, 'Failed to load threads'));
        setThreads([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const grouped = useMemo(() => groupThreads(threads), [threads]);

  if (loading) {
    return <p className={pageStyles.statusMessage}>Loading threads…</p>;
  }

  if (error) {
    return <p className={pageStyles.errorMessage}>{error}</p>;
  }

  return (
    <div className={pageStyles.page}>
      <div className={pageStyles.headerRow}>
        <span className={pageStyles.title}>Threads · {threads.length} active</span>
        <span className={pageStyles.subtitle}>ranked by attention ↓</span>
      </div>

      {grouped.hot.length ? (
        <>
          <div className={pageStyles.sectionLabel}>hot</div>
          <div className={pageStyles.list}>
            {grouped.hot.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} />
            ))}
          </div>
        </>
      ) : null}

      {grouped.warm.length ? (
        <>
          <div className={pageStyles.sectionLabel}>warm</div>
          <div className={pageStyles.list}>
            {grouped.warm.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} />
            ))}
          </div>
        </>
      ) : null}

      {grouped.ambient.length ? (
        <>
          <div className={pageStyles.sectionLabel}>ambient</div>
          <div className={pageStyles.ambientGrid}>
            {grouped.ambient.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} variant="ambient" />
            ))}
          </div>
        </>
      ) : null}

      {!threads.length ? (
        <p className={pageStyles.statusMessage}>No active threads yet.</p>
      ) : null}
    </div>
  );
}
