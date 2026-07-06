import { Link } from 'react-router-dom';
import XGlyph from './XGlyph';
import { pathForEntityType } from '../utils/entityContext';
import styles from './EntityContextChips.module.css';

function ContextChip({ item, onRemove }) {
  const path = pathForEntityType(item.type, item.id);
  if (!path) return null;

  const typeClass = styles[`chip${item.type.charAt(0).toUpperCase()}${item.type.slice(1)}`];

  const handleRemove = (event) => {
    event.preventDefault();
    event.stopPropagation();
    onRemove?.(item);
  };

  return (
    <span className={`${styles.chip} ${typeClass || ''}`}>
      <Link
        to={path}
        className={styles.chipLink}
        onClick={(event) => event.stopPropagation()}
      >
        <XGlyph type={item.type} />
        <span className={styles.chipLabel}>{item.title || 'Untitled'}</span>
      </Link>
      {onRemove ? (
        <button
          type="button"
          className={styles.chipRemove}
          onClick={handleRemove}
          aria-label={`Remove ${item.type}`}
        >
          ×
        </button>
      ) : null}
    </span>
  );
}

export default function EntityContextChips({
  projects = [],
  areas = [],
  people = [],
  className = '',
  onRemove,
}) {
  const items = [
    ...(projects || []).map((item) => ({ ...item, type: 'project' })),
    ...(areas || []).map((item) => ({ ...item, type: 'area' })),
    ...(people || []).map((item) => ({ ...item, type: 'person' })),
  ];

  if (!items.length) return null;

  return (
    <div className={`${styles.chips} ${className}`.trim()}>
      {items.map((item) => (
        <ContextChip key={`${item.type}-${item.id}`} item={item} onRemove={onRemove} />
      ))}
    </div>
  );
}
