import styles from './CitationsList.module.css';

const MAX_SNIPPET_LENGTH = 140;

export function truncateSnippet(snippet, maxLength = MAX_SNIPPET_LENGTH) {
  if (!snippet) return '';
  if (snippet.length <= maxLength) return snippet;
  const trimmed = snippet.slice(0, maxLength).trimEnd();
  return `${trimmed}…`;
}

export function formatCitationDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function CitationsList({ citations, onOpen, emptyText }) {
  if (!citations?.length) {
    if (!emptyText) return null;
    return <p className={styles.empty}>{emptyText}</p>;
  }

  return (
    <ul className={styles.list} aria-label="Citations">
      {citations.map((citation, index) => {
        const snippet = truncateSnippet(citation.snippet);
        const date = formatCitationDate(citation.date || citation.created_at || citation.updated_at);
        const meta = citation.meta || '';
        return (
          <li key={`${citation.entity_id}-${index}`} className={styles.card}>
            <span className={styles.glyph} aria-hidden="true">📝</span>
            <div className={styles.body}>
              <p className={styles.snippet}>{snippet}</p>
              <div className={styles.footer}>
                {date ? <span className={styles.date}>{date}</span> : null}
                {meta ? <span className={styles.meta}>{meta}</span> : null}
              </div>
            </div>
            {onOpen ? (
              <button
                type="button"
                className={styles.openButton}
                onClick={() => onOpen(citation)}
                aria-label={`Open citation ${index + 1}`}
              >
                open
              </button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
