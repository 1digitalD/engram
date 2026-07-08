import { useCallback, useEffect, useState } from 'react';
import { friendlyApiError, v4API } from '../api/v4Client';
import { SURFACE_LABELS } from './vocab';
import styles from './WorkboardSurface.module.css';

const FILTERS = [
  { key: 'mine', label: 'Mine' },
  { key: 'waiting_on', label: 'Waiting on' },
  { key: 'overdue', label: 'Overdue' },
  { key: 'stale', label: 'Stale' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'at_risk', label: 'At risk' },
];

const GROUP_OPTIONS = [
  { key: 'space', label: 'Space' },
  { key: 'person', label: 'Person' },
];

function formatDueDate(value) {
  if (!value) return 'No due date';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'No due date';
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(parsed);
}

function buildParams(group, filters) {
  const params = { group };
  if (filters.length > 0) params.state = filters;
  return params;
}

function itemMeta(item, group) {
  const parts = [item.status || 'open'];
  if (group === 'space' && item.owner?.title) parts.push(item.owner.title);
  if (group === 'person' && item.space?.title) parts.push(item.space.title);
  parts.push(`Due ${formatDueDate(item.due_at)}`);
  return parts.join(' · ');
}

function stateSummary(item) {
  return FILTERS.filter(({ key }) => item.states?.[key]).map(({ label }) => label);
}

export default function WorkboardSurface() {
  const [group, setGroup] = useState('space');
  const [activeFilters, setActiveFilters] = useState([]);
  const [board, setBoard] = useState({ data: { groups: [] }, meta: { counts: {}, total: 0 } });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionNote, setActionNote] = useState('');

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await v4API.workboard(buildParams(group, activeFilters));
      setBoard(payload || { data: { groups: [] }, meta: { counts: {}, total: 0 } });
    } catch (err) {
      setError(friendlyApiError(err, 'Could not load workboard.'));
      setBoard({ data: { groups: [] }, meta: { counts: {}, total: 0 } });
    } finally {
      setLoading(false);
    }
  }, [activeFilters, group]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  function toggleFilter(filterKey) {
    setActiveFilters((current) =>
      current.includes(filterKey)
        ? current.filter((value) => value !== filterKey)
        : [...current, filterKey],
    );
  }

  function announceAction(label, detail) {
    setActionNote(`${label}: ${detail}`);
  }

  const counts = board?.meta?.counts || {};
  const groups = board?.data?.groups || [];

  return (
    <section className={styles.surface} aria-label={SURFACE_LABELS.workboard}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{SURFACE_LABELS.workboard}</h1>
          <p className={styles.subtitle}>
            Scan every open commitment across spaces, then pivot by owner when you need a carry load view.
          </p>
        </div>

        <div className={styles.groupToggle} role="group" aria-label="Group commitments by">
          {GROUP_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className={group === option.key ? styles.toggleActive : styles.toggle}
              aria-pressed={group === option.key}
              onClick={() => setGroup(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className={styles.filterRow} role="group" aria-label="Filter commitments by state">
        {FILTERS.map((filter) => {
          const count = counts[filter.key] || 0;
          const active = activeFilters.includes(filter.key);
          return (
            <button
              key={filter.key}
              type="button"
              className={active ? styles.filterChipActive : styles.filterChip}
              aria-pressed={active}
              onClick={() => toggleFilter(filter.key)}
            >
              <span>{filter.label}</span>
              <span className={styles.filterCount}>{count}</span>
            </button>
          );
        })}
      </div>

      {actionNote ? (
        <p className={styles.actionNote} aria-live="polite">
          {actionNote}
        </p>
      ) : null}

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <div className={styles.layout}>
        <div className={styles.boardColumn}>
          {loading ? <p className={styles.empty}>Loading workboard…</p> : null}

          {!loading && groups.length === 0 ? (
            <p className={styles.empty}>No open commitments match this slice of the board.</p>
          ) : null}

          {!loading ? (
            <div className={styles.groupList}>
              {groups.map((bucket) => (
                <section key={bucket.key} className={styles.groupCard}>
                  <div className={styles.groupHeader}>
                    <div>
                      <h2 className={styles.groupTitle}>{bucket.label}</h2>
                      <p className={styles.groupMeta}>
                        {bucket.counts?.total || 0} commitments
                      </p>
                    </div>
                    {bucket.at_risk?.flag ? (
                      <span className={styles.groupRiskFlag}>At risk</span>
                    ) : null}
                  </div>

                  {bucket.at_risk?.reason ? (
                    <p className={styles.groupRiskReason}>{bucket.at_risk.reason}</p>
                  ) : null}

                  <ul className={styles.itemList}>
                    {bucket.items.map((item) => {
                      const states = stateSummary(item);
                      return (
                        <li key={item.id} className={styles.item}>
                          <div className={styles.itemHeader}>
                            <div>
                              <h3 className={styles.itemTitle}>{item.title}</h3>
                              <p className={styles.itemMeta}>{itemMeta(item, group)}</p>
                            </div>
                            {item.at_risk?.flag ? (
                              <span className={styles.itemRiskFlag}>At risk</span>
                            ) : null}
                          </div>

                          {states.length > 0 ? (
                            <div className={styles.stateList} aria-label={`${item.title} states`}>
                              {states.map((state) => (
                                <span key={state} className={styles.statePill}>
                                  {state}
                                </span>
                              ))}
                            </div>
                          ) : null}

                          {item.at_risk?.reason ? (
                            <p className={styles.reason}>{item.at_risk.reason}</p>
                          ) : null}

                          {item.blocked_by?.length ? (
                            <p className={styles.blockedBy}>
                              Blocked by {item.blocked_by.map((blocker) => blocker.title).join(', ')}.
                            </p>
                          ) : null}

                          <div className={styles.actions}>
                            <button
                              type="button"
                              className={styles.actionPrimary}
                              onClick={() => announceAction('Done', 'Direct completion lands in the next manipulation slice.')}
                            >
                              Done
                            </button>
                            <button
                              type="button"
                              className={styles.actionSecondary}
                              onClick={() => announceAction('Draft nudge', 'Nudge drafting ships in Phase 4.')}
                            >
                              Draft nudge
                            </button>
                            <button
                              type="button"
                              className={styles.actionSecondary}
                              onClick={() => announceAction('Add marker', 'Markers land in the Today slice.')}
                            >
                              Add marker
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          ) : null}
        </div>

        <aside className={styles.rail}>
          <h2 className={styles.railTitle}>Themes</h2>
          <p className={styles.railCopy}>
            Theme signals will stack here once Phase 5 lands. For now, keep the rail in place so the board layout
            does not shift later.
          </p>
          <div className={styles.railPlaceholder}>No theme signals in this slice.</div>
        </aside>
      </div>
    </section>
  );
}
