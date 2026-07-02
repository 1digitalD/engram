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
    return <p className={pageStyles.statusMessage}>Loading threads…</p>;
  }

  if (error) {
    return <p className={pageStyles.errorMessage}>{error}</p>;
  }

  const showingPartial = totalCount > threads.length;

  return (
    <div className={pageStyles.page}>
      <div className={pageStyles.headerRow}>
        <span className={pageStyles.title}>Threads · {totalCount} active</span>
        <span className={pageStyles.subtitle}>
          ranked by attention
          {showingPartial ? ` · showing ${threads.length}` : ' ↓'}
        </span>
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
          <div className={pageStyles.list}>
            {grouped.ambient.map((thread) => (
              <V5EntityRow key={thread.id} thread={thread} variant="ambient" />
            ))}
          </div>
        </>
      ) : null}

      {threads.length === 0 ? (
        <p className={pageStyles.statusMessage}>No active threads yet.</p>
      ) : null}
    </div>
  );
}
