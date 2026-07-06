import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { v4API, friendlyApiError } from '../api/v4Client';
import EntityGlyphCircle from '../components/EntityGlyphCircle';
import { transformTodayResponse } from '../views/V5Now';
import { labDetailPath } from './labPaths';
import styles from './LabToday.module.css';

function itemPath(item) {
  if (item.nonNavigable) return null;
  if (item.thread?.type && item.thread?.id) {
    return labDetailPath(item.thread.type, item.thread.id);
  }
  return labDetailPath(item.type, item.id);
}

function TodayRow({ item }) {
  const path = itemPath(item);
  return (
    <article
      className={styles.row}
      data-entity-type={item.type}
    >
      <div className={styles.rowHead}>
        <EntityGlyphCircle type={item.type} />
        {path ? (
          <Link to={path} className={styles.sentence}>
            {item.subject || item.title || 'Untitled'}
          </Link>
        ) : (
          <p className={styles.sentence}>{item.subject || item.title || 'Untitled'}</p>
        )}
      </div>
      {item.why_now ? (
        <div className={styles.meta}>
          <span>{item.why_now}</span>
        </div>
      ) : null}
    </article>
  );
}

function Section({ title, items }) {
  if (!items || items.length === 0) return null;

  return (
    <section className={styles.section} aria-label={title}>
      <h2 className={styles.sectionLabel}>
        {title}
        <span className={styles.sectionCount}>{items.length}</span>
      </h2>
      <div className={styles.rowList}>
        {items.map((item) => (
          <TodayRow key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}

function buildSubtitle(data) {
  const attentionCount = (data?.needs_you_now?.length || 0) + (data?.waiting_on_you?.length || 0);
  const newCount = data?.new_since_yesterday_count ?? 0;

  if (attentionCount > 0) {
    const base = `${attentionCount} item${attentionCount === 1 ? '' : 's'} need your attention.`;
    return newCount > 0 ? `${base} ${newCount} new since yesterday.` : base;
  }
  if (newCount > 0) {
    return `${newCount} new since yesterday. Nothing urgent right now.`;
  }
  return 'Nothing urgent. Use this time to plan ahead or capture notes.';
}

export default function LabToday() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    v4API.today()
      .then((today) => {
        if (!active) return;
        setData(transformTodayResponse(today));
      })
      .catch((err) => {
        if (!active) return;
        setError(friendlyApiError(err, 'Failed to load Today'));
        setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const hasItems = useMemo(
    () => Boolean((data?.needs_you_now || []).length
      || (data?.waiting_on_you || []).length
      || (data?.ambient || []).length),
    [data],
  );

  if (loading) {
    return (
      <div className={styles.page} aria-busy="true">
        <p className={styles.statusMessage}>Loading Today…</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className={styles.page}>
        <p className={styles.errorMessage} role="alert">{error}</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header>
        <p className={styles.meta}>{buildSubtitle(data)}</p>
        {error ? <p className={styles.errorMessage} role="alert">{error}</p> : null}
      </header>

      <Section title="Needs you now" items={data?.needs_you_now || []} />
      <Section title="Waiting on you" items={data?.waiting_on_you || []} />
      <Section title="Ambient" items={data?.ambient || []} />

      {!hasItems && (
        <p className={styles.emptyHint}>No items in your Today view yet.</p>
      )}
    </div>
  );
}
