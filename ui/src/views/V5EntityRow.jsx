import { Link } from 'react-router-dom';
import EntityGlyphCircle from '../components/EntityGlyphCircle';
import styles from './V5EntityRow.module.css';

function formatAttention(score) {
  if (score >= 75) return { label: 'urgent', className: styles.badgeUrgent };
  if (score >= 50) return { label: 'high', className: styles.badgeHigh };
  if (score >= 25) return { label: 'warm', className: styles.badgeWarm };
  return { label: 'quiet', className: styles.badgeQuiet };
}

function entityPath(thread) {
  if (thread.type === 'person') return `/people/${thread.id}`;
  if (thread.type === 'project') return `/projects/${thread.id}`;
  if (thread.type === 'area') return `/areas/${thread.id}`;
  if (thread.type === 'topic' && thread.key_items?.[0]?.id) {
    return `/notes/${thread.key_items[0].id}`;
  }
  return `/entities/${thread.id}`;
}

function buildMeta(thread) {
  const parts = [];
  const keyCount = thread.key_items?.length || 0;
  if (keyCount) {
    parts.push(`${keyCount} key item${keyCount === 1 ? '' : 's'}`);
  }
  const topReason = thread.attention_reasons?.[0]?.label;
  if (topReason) parts.push(topReason);
  return parts.join(' · ');
}

export default function V5EntityRow({ thread, variant = 'row' }) {
  const attention = formatAttention(thread.attention_score ?? 0);
  const meta = buildMeta(thread);
  const detailPath = entityPath(thread);

  if (variant === 'ambient') {
    return (
      <Link to={detailPath} className={styles.ambientCard} data-entity-type={thread.type}>
        <div className={styles.ambientHead}>
          <EntityGlyphCircle type={thread.type} />
          <span>{thread.name}</span>
        </div>
        <div className={styles.ambientBody}>
          score {thread.attention_score}
          {meta ? ` · ${meta}` : ''}
        </div>
      </Link>
    );
  }

  const bandClass = thread.attention_score >= 75
    ? styles.rowHot
    : thread.attention_score >= 25
      ? styles.rowWarm
      : styles.rowDefault;

  return (
    <Link to={detailPath} className={`${styles.row} ${bandClass}`} data-entity-type={thread.type}>
      <div className={styles.rowMain}>
        <div className={styles.sentence}>
          <EntityGlyphCircle type={thread.type} />
          <span>{thread.name}</span>
        </div>
        {meta ? <div className={styles.meta}>{meta}</div> : null}
        {thread.last_context ? (
          <div className={styles.lastContext}>{thread.last_context}</div>
        ) : null}
      </div>
      <div className={styles.actions}>
        <span className={attention.className}>{thread.attention_score}</span>
      </div>
    </Link>
  );
}
