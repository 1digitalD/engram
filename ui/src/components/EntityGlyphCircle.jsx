import XGlyph from './XGlyph';
import styles from './EntityGlyphCircle.module.css';

export default function EntityGlyphCircle({ type, className = '' }) {
  const typeClass = styles[type] || '';
  return (
    <span className={`${styles.circle} ${typeClass} ${className}`.trim()} aria-hidden="true">
      <XGlyph type={type} />
    </span>
  );
}
