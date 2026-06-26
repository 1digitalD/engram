import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { v4API } from '../api/v4Client';
import { entityTitleLabel } from '../utils/entityDisplay';
import styles from './V4AgentActivity.module.css';

const CATEGORY_LABELS = {
  auto_applied: 'auto applied',
  suggested: 'pending suggestion',
  review_action: 'review action',
  failed: 'ai failed',
};

function entityPath(entity) {
  if (!entity) return '#';
  const base = entity.type === 'person' ? 'people' : `${entity.type}s`;
  return `/${base}/${entity.id}`;
}

function formatCategory(value) {
  return CATEGORY_LABELS[value] || String(value || '').replace(/_/g, ' ');
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

function formatEventType(value) {
  const key = String(value || '').toLowerCase();
  if (key === 'create_task') return 'task suggestion created';
  if (key === 'create_project') return 'project suggestion created';
  if (key === 'create_person') return 'person suggestion created';
  if (key === 'create_area') return 'area suggestion created';
  if (key === 'create_resource') return 'resource suggestion created';
  if (key === 'link_existing') return 'link suggestion created';
  if (key === 'suggestion_accepted') return 'suggestion accepted';
  if (key === 'suggestion_dismissed') return 'suggestion dismissed';
  if (key === 'ai_updated') return 'capture applied';
  if (key === 'ai_failed') return 'capture failed';
  return String(value || '').replace(/_/g, ' ');
}

function itemSummary(item) {
  if (item.kind === 'suggestion') {
    return 'Pending risky change awaiting review.';
  }
  if (item.kind === 'failed_note') {
    return 'Latest extraction attempt failed for this note.';
  }
  if (item.category === 'review_action') {
    return 'A pending suggestion was resolved by review.';
  }
  return 'Automation already applied this change.';
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
        <div className={styles.headerCopy}>
          <p className={styles.eyebrow}>Agent audit</p>
          <h1>Agent log</h1>
          <p className={styles.headerText}>
            Raw automation history: applied changes, pending suggestions, review actions, and failures.
          </p>
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

      <section className={styles.explainer}>
        <strong>What this log is showing</strong>
        <div className={styles.legendGrid}>
          <p><span className={`${styles.category} ${styles.category_auto_applied}`}>auto applied</span> Safe automation the system already wrote.</p>
          <p><span className={`${styles.category} ${styles.category_suggested}`}>pending suggestion</span> A risky change queued for review.</p>
          <p><span className={`${styles.category} ${styles.category_review_action}`}>review action</span> A suggestion was accepted or dismissed.</p>
          <p><span className={`${styles.category} ${styles.category_failed}`}>ai failed</span> Extraction failed on a note and needs another run.</p>
        </div>
        <p>
          Use <Link to="/suggestions">Review</Link> to clear pending review work and <Link to="/inbox">Inbox</Link> to inspect captured notes.
        </p>
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
                <strong>{formatEventType(item.event_type)}</strong>
                {item.entity ? (
                  <Link to={entityPath(item.entity)} className={styles.entityLink}>
                    {entityTitleLabel(item.entity, { includeType: false })} · {item.entity.type}
                  </Link>
                ) : (
                  <span className={styles.muted}>No source entity</span>
                )}
                {item.reason ? <p>{item.reason}</p> : null}
                <p className={styles.hint}>{itemSummary(item)}</p>
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
