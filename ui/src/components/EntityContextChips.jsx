import { Link } from 'react-router-dom';
import XGlyph from './XGlyph';
import { pathForEntityType } from '../utils/entityContext';
import styles from './EntityContextChips.module.css';

function ContextChip({ item }) {
  const path = pathForEntityType(item.type, item.id);
  if (!path) return null;

  return (
    <Link
      to={path}
      className={`${styles.chip} ${styles[`chip${item.type.charAt(0).toUpperCase()}${item.type.slice(1)}`]}`}
      onClick={(event) => event.stopPropagation()}
    >
      <XGlyph type={item.type} />
      <span className={styles.chipLabel}>{item.title || 'Untitled'}</span>
    </Link>
  );
}

export default function EntityContextChips({
  projects = [],
  areas = [],
  className = '',
}) {
  const items = [
    ...(projects || []).map((item) => ({ ...item, type: 'project' })),
    ...(areas || []).map((item) => ({ ...item, type: 'area' })),
  ];

  if (!items.length) return null;

  return (
    <div className={`${styles.chips} ${className}`.trim()}>
      {items.map((item) => (
        <ContextChip key={`${item.type}-${item.id}`} item={item} />
      ))}
    </div>
  );
}
