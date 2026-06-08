import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { v4API } from '../api/v4Client';
import styles from './V4AgentActivity.module.css';

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function formatCategory(value) {
  return String(value || '').replace(/_/g, ' ');
}

function formatConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '';
  return `${Math.round(value * 100)}%`;
}

function formatTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString();
}

export default function V4AgentActivity() {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ counts: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadActivity() {
    setLoading(true);
    setError('');
    try {
      const response = await v4API.agentActivity({ limit: 80 });
      setItems(response.data || []);
      setMeta(response.meta || { counts: {} });
    } catch (err) {
      setError(err.message || 'Failed to load agent activity');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadActivity();
  }, []);

  return (
    <main className={styles.activity}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Agent audit</p>
          <h1>Recent automation</h1>
        </div>
        <button type="button" className={styles.refreshButton} onClick={loadActivity} disabled={loading}>
          <RefreshCw size={14} strokeWidth={2.2} aria-hidden="true" />
          Refresh
        </button>
      </header>

      <section className={styles.summary}>
        {['auto_applied', 'suggested', 'review_action', 'failed'].map((key) => (
          <div key={key} className={styles.stat}>
            <strong>{meta.counts?.[key] || 0}</strong>
            <span>{formatCategory(key)}</span>
          </div>
        ))}
      </section>

      {error ? <p className={styles.error}>{error}</p> : null}
      {loading ? (
        <p className={styles.empty}>Loading agent activity...</p>
      ) : items.length === 0 ? (
        <p className={styles.empty}>No agent activity yet.</p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={`${item.kind}:${item.id}`} className={styles.row}>
              <div className={styles.rowMain}>
                <span className={`${styles.category} ${styles[`category_${item.category}`] || ''}`}>
                  {formatCategory(item.category)}
                </span>
                <strong>{formatCategory(item.event_type)}</strong>
                {item.entity ? (
                  <Link to={entityPath(item.entity)} className={styles.entityLink}>
                    {item.entity.title || 'Untitled'} · {item.entity.type}
                  </Link>
                ) : (
                  <span className={styles.muted}>No source entity</span>
                )}
                {item.reason ? <p>{item.reason}</p> : null}
              </div>
              <div className={styles.rowMeta}>
                {formatConfidence(item.confidence) ? <span>{formatConfidence(item.confidence)}</span> : null}
                <span>{item.actor}</span>
                <time dateTime={item.created_at || undefined}>{formatTime(item.created_at)}</time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
