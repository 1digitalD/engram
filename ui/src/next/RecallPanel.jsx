import { groupRecallResults } from './recallUtils';
import { StatusBadge } from './statusTheme';
import styles from './RecallPanel.module.css';

export default function RecallPanel({
  query,
  results,
  loading,
  error,
  selectedIndex,
  onSelect,
  onHover,
}) {
  const trimmed = query.trim();
  if (!trimmed) return null;

  const grouped = groupRecallResults(results);

  return (
    <div className={styles.panel} id="recall-results" role="listbox" aria-label="Recall results">
      {error ? (
        <p className={styles.message} role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p className={styles.message}>Searching…</p> : null}
      {!loading && !error && results.length === 0 ? (
        <p className={styles.message}>No results for “{trimmed}”.</p>
      ) : null}
      {grouped.map((group) => (
        <section key={group.type} className={styles.group}>
          <h3 className={styles.groupLabel}>{group.label}</h3>
          <ul className={styles.list}>
            {group.items.map((entity) => {
              const globalIndex = results.indexOf(entity);
              const selected = globalIndex === selectedIndex;
              return (
                <li key={entity.id} role="option" aria-selected={selected}>
                  <button
                    type="button"
                    className={`${styles.resultButton} ${selected ? styles.resultSelected : ''}`}
                    onMouseEnter={() => onHover?.(globalIndex)}
                    onClick={() => onSelect?.(entity)}
                  >
                    <span className={styles.resultMain}>
                      <span className={styles.resultTitle}>{entity.title || '(no title)'}</span>
                      {entity.searchSnippet ? (
                        <span className={styles.resultSnippet}>{entity.searchSnippet}</span>
                      ) : null}
                    </span>
                    {entity.status ? <StatusBadge status={entity.status} /> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
