import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { friendlyApiError, v4API } from '../api/v4Client';
import { ENTITY_TYPE_GLYPHS, SURFACE_LABELS, entityTypeLabel } from './vocab';
import styles from './TodaySurface.module.css';

function itemEntityType(item) {
  return item?.entity?.type || item?.entity_type || item?.marker?.entity?.type || 'task';
}

function itemPath(item) {
  const entity = item?.entity;
  const entityId = entity?.id || (item?.entity_type === 'project' ? item.id : null);
  const entityType = entity?.type || item?.entity_type;
  if (!entityId || !entityType) return null;
  if (entityType === 'person') return `/spaces/${entityId}`;
  if (entityType === 'project' || entityType === 'area') return `/spaces/${entityId}`;
  if (entityType === 'note') return null;
  return `/spaces/${entity?.projects?.[0]?.id || entity?.areas?.[0]?.id || ''}`;
}

function buildSubtitle(payload) {
  const needsCount = payload?.counts?.needs_you ?? payload?.needs_you?.length ?? 0;
  const motionCount = payload?.counts?.in_motion ?? payload?.in_motion?.length ?? 0;
  const newCount = payload?.new_since_yesterday_count ?? 0;
  const newlyAtRisk = payload?.counts?.newly_at_risk ?? payload?.newly_at_risk?.length ?? 0;

  const parts = [];
  if (needsCount > 0) {
    parts.push(`${needsCount} item${needsCount === 1 ? '' : 's'} need you`);
  }
  if (motionCount > 0) {
    parts.push(`${motionCount} in motion`);
  }
  if (newlyAtRisk > 0) {
    parts.push(`${newlyAtRisk} newly at risk`);
  }
  if (newCount > 0) {
    parts.push(`${newCount} new since yesterday`);
  }
  return parts.length > 0 ? `${parts.join(' · ')}.` : 'Nothing urgent right now.';
}

function TodayRow({ item }) {
  const entityType = itemEntityType(item);
  const glyph = ENTITY_TYPE_GLYPHS[entityType] || '•';
  const path = itemPath(item);
  const title = item?.title || 'Untitled';
  const summary = item?.summary || '';
  const receipts = item?.receipts || [];

  return (
    <li className={styles.row} data-kind={item.kind}>
      <div className={styles.rowHead}>
        <span className={styles.glyph} aria-hidden="true">{glyph}</span>
        <div className={styles.rowCopy}>
          {path ? (
            <Link to={path} className={styles.rowTitle}>{title}</Link>
          ) : (
            <p className={styles.rowTitle}>{title}</p>
          )}
          <p className={styles.rowMeta}>
            <span>{entityTypeLabel(entityType)}</span>
            {summary ? <span> · {summary}</span> : null}
          </p>
          {receipts.length > 0 ? (
            <ul className={styles.receipts}>
              {receipts.slice(0, 2).map((receipt) => (
                <li key={`${receipt.field}-${receipt.entity_id}`}>
                  {receipt.field}: {receipt.value}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function TodayColumn({ title, count, items, emptyHint }) {
  return (
    <section className={styles.column} aria-label={title}>
      <header className={styles.columnHeader}>
        <h2 className={styles.columnTitle}>{title}</h2>
        <span className={styles.columnCount} aria-label={`${count} items`}>{count}</span>
      </header>
      {items.length > 0 ? (
        <ul className={styles.list}>
          {items.map((item) => (
            <TodayRow key={`${item.kind}-${item.id}`} item={item} />
          ))}
        </ul>
      ) : (
        <p className={styles.empty}>{emptyHint}</p>
      )}
    </section>
  );
}

export default function TodaySurface() {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadToday = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await v4API.today();
      setPayload(data || null);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load Today.'));
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadToday();
  }, [loadToday]);

  const needsYou = payload?.needs_you || [];
  const inMotion = payload?.in_motion || [];
  const counts = payload?.counts || {
    needs_you: needsYou.length,
    in_motion: inMotion.length,
  };
  const subtitle = useMemo(() => buildSubtitle(payload), [payload]);
  const hasItems = needsYou.length > 0 || inMotion.length > 0;

  if (loading) {
    return (
      <div className={styles.surface} aria-busy="true">
        <p className={styles.status}>Loading Today…</p>
      </div>
    );
  }

  if (error && !payload) {
    return (
      <div className={styles.surface}>
        <p className={styles.error} role="alert">{error}</p>
      </div>
    );
  }

  return (
    <div className={styles.surface}>
      <header className={styles.header}>
        <h1 className={styles.title}>{SURFACE_LABELS.today}</h1>
        <p className={styles.subtitle}>{subtitle}</p>
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </header>

      <div className={styles.columns}>
        <TodayColumn
          title="Needs you"
          count={counts.needs_you ?? needsYou.length}
          items={needsYou}
          emptyHint="Nothing needs you right now."
        />
        <TodayColumn
          title="In motion"
          count={counts.in_motion ?? inMotion.length}
          items={inMotion}
          emptyHint="No background motion to watch."
        />
      </div>

      {!hasItems ? (
        <p className={styles.emptyPage}>Today is clear — capture something or check the Workboard.</p>
      ) : null}
    </div>
  );
}
