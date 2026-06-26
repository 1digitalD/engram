import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { v4API } from '../api/v4Client';
import { entityTitleLabel } from '../utils/entityDisplay';
import styles from './V4Home.module.css';

function entityPath(item) {
  const base = item.entity_type === 'person' ? 'people' : `${item.entity_type}s`;
  return `/${base}/${item.entity_id}`;
}

function urgencyClass(urgency) {
  if (urgency >= 5) return styles.urgencyHigh;
  if (urgency >= 3) return styles.urgencyMedium;
  return styles.urgencyLow;
}

function BriefPanel({ brief, refreshing, onRefresh }) {
  return (
    <section className={styles.briefPanel} aria-label="Daily brief">
      <header className={styles.briefHeader}>
        <div>
          <p className={styles.eyebrow}>Daily brief</p>
          {brief?.narrative ? <h1>{brief.narrative}</h1> : <h1>What needs you today</h1>}
        </div>
        <button
          type="button"
          className={styles.refreshButton}
          onClick={onRefresh}
          disabled={refreshing}
          aria-label="Refresh brief"
          title="Regenerate the brief"
        >
          <RefreshCw size={15} strokeWidth={2} className={refreshing ? 'spin' : undefined} aria-hidden="true" />
        </button>
      </header>
      {!brief && (
        <p className={styles.briefEmpty}>
          No brief yet — it generates from your projects, tasks and recent updates.
          Hit refresh to create one.
        </p>
      )}
      {brief && brief.items.length === 0 && (
        <p className={styles.briefEmpty}>Nothing urgent surfaced. Clear runway.</p>
      )}
      {brief && brief.items.length > 0 && (
        <ol className={styles.briefList}>
          {brief.items.map((item) => (
            <li key={item.entity_id} className={styles.briefItem}>
              <span className={`${styles.urgencyDot} ${urgencyClass(item.urgency)}`} aria-hidden="true" />
              <div className={styles.briefItemBody}>
                <Link to={entityPath(item)} className={styles.briefItemTitle}>
                  {entityTitleLabel(item)}
                </Link>
                <span className={styles.briefWhy}>{item.why_now}</span>
              </div>
              <span className={styles.briefType}>{item.entity_type}</span>
            </li>
          ))}
        </ol>
      )}
      {brief?.generated_at && (
        <p className={styles.briefMeta}>
          generated {new Date(brief.generated_at).toLocaleString()}
        </p>
      )}
    </section>
  );
}

function TrustStrip({ trust }) {
  if (!trust) return null;
  const acceptance = trust.suggestions?.acceptance_rate;
  const correction = trust.correction_rate;
  return (
    <section className={styles.trustStrip} aria-label="Agent trust metrics">
      <Link to="/suggestions" className={styles.trustCard}>
        <strong>{trust.suggestions?.pending ?? '—'}</strong>
        <span>pending review</span>
      </Link>
      <div className={styles.trustCard}>
        <strong>{acceptance === null || acceptance === undefined ? '—' : `${Math.round(acceptance * 100)}%`}</strong>
        <span>suggestions accepted ({trust.window_days}d)</span>
      </div>
      <div className={styles.trustCard}>
        <strong>{correction === null || correction === undefined ? '—' : `${Math.round(correction * 100)}%`}</strong>
        <span>agent actions corrected</span>
      </div>
      <div className={styles.trustCard}>
        <strong>{trust.agent_actions?.total ?? 0}</strong>
        <span>agent actions ({trust.window_days}d)</span>
      </div>
    </section>
  );
}

function CoordinationRadar({ radar }) {
  const people = radar?.people || [];
  const projects = radar?.projects || [];
  if (people.length === 0 && projects.length === 0) return null;

  return (
    <section className={styles.radarPanel} aria-label="Coordination radar">
      <div>
        <p className={styles.eyebrow}>Active focus</p>
        <h2 className={styles.radarTitle}>Coordination radar</h2>
      </div>
      <div className={styles.radarGrid}>
        {people.map((item) => (
          <article key={`${item.entity_type}:${item.entity_id}`} className={styles.radarCard}>
            <span className={styles.radarLabel}>1:1</span>
            <Link to={entityPath(item)} className={styles.radarLink}>
              {entityTitleLabel(item)}
            </Link>
            <p className={styles.radarHeadline}>{item.headline}</p>
          </article>
        ))}
        {projects.map((item) => (
          <article key={`${item.entity_type}:${item.entity_id}`} className={styles.radarCard}>
            <span className={styles.radarLabel}>Project</span>
            <Link to={entityPath(item)} className={styles.radarLink}>
              {entityTitleLabel(item)}
            </Link>
            <p className={styles.radarHeadline}>{item.headline}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function V4Home() {
  const [brief, setBrief] = useState(null);
  const [trust, setTrust] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  async function load({ force = false } = {}) {
    setError('');
    if (force) setRefreshing(true);
    try {
      const [briefRes, trustRes, summaryRes] = await Promise.allSettled([
        v4API.brief(force ? { force: 1 } : {}),
        v4API.metrics.trust(),
        v4API.summary(),
      ]);
      if (briefRes.status === 'fulfilled') setBrief(briefRes.value.brief);
      if (trustRes.status === 'fulfilled') setTrust(trustRes.value);
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value);
      if (briefRes.status === 'rejected' && trustRes.status === 'rejected') {
        setError(briefRes.reason?.message || 'Failed to load home');
      }
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className={styles.home}>
      {error && <p className={styles.error}>{error}</p>}
      <BriefPanel brief={brief} refreshing={refreshing} onRefresh={() => load({ force: true })} />
      <TrustStrip trust={trust} />
      <CoordinationRadar radar={summary?.coordination_radar} />
      {summary && (
        <div className={styles.shortcutGrid}>
          <Link to="/inbox" className={styles.shortcutCard}>
            <strong>Capture</strong>
            <span>Capture a note or jump into the inbox queue.</span>
          </Link>
          <Link to="/suggestions" className={styles.shortcutCard}>
            <strong>Clear review</strong>
            <span>{summary.inbox_count} note{summary.inbox_count === 1 ? '' : 's'} in review</span>
          </Link>
          <Link to="/today" className={styles.shortcutCard}>
            <strong>Run today</strong>
            <span>{summary.today_count} item{summary.today_count === 1 ? '' : 's'} need attention</span>
          </Link>
        </div>
      )}
    </main>
  );
}
