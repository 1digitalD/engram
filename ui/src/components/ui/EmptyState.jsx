import React from 'react';
import styles from './EmptyState.module.css';

const ILLUSTRATIONS = {
  notes: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <rect x="12" y="8" width="40" height="48" rx="6" stroke="var(--border)" strokeWidth="1.5"/>
      <line x1="20" y1="22" x2="44" y2="22" stroke="var(--border)" strokeWidth="1.5" strokeLinecap="round"/>
      <line x1="20" y1="30" x2="44" y2="30" stroke="var(--border)" strokeWidth="1.5" strokeLinecap="round"/>
      <line x1="20" y1="38" x2="36" y2="38" stroke="var(--border)" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  projects: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <rect x="8" y="12" width="22" height="40" rx="4" stroke="var(--border)" strokeWidth="1.5"/>
      <rect x="34" y="12" width="22" height="28" rx="4" stroke="var(--border)" strokeWidth="1.5"/>
      <rect x="34" y="44" width="22" height="8" rx="2" stroke="var(--border)" strokeWidth="1.5"/>
    </svg>
  ),
  tasks: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <rect x="10" y="10" width="44" height="44" rx="6" stroke="var(--border)" strokeWidth="1.5"/>
      <polyline points="20,24 28,32 44,16" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  search: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <circle cx="28" cy="28" r="14" stroke="var(--border)" strokeWidth="1.5"/>
      <line x1="38" y1="38" x2="52" y2="52" stroke="var(--border)" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  graph: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
      <circle cx="32" cy="32" r="6" fill="var(--accent)" opacity="0.3"/>
      <circle cx="14" cy="18" r="4" fill="var(--border)"/>
      <circle cx="50" cy="18" r="4" fill="var(--border)"/>
      <circle cx="14" cy="46" r="4" fill="var(--border)"/>
      <circle cx="50" cy="46" r="4" fill="var(--border)"/>
      <line x1="32" y1="32" x2="14" y2="18" stroke="var(--border)" strokeWidth="1"/>
      <line x1="32" y1="32" x2="50" y2="18" stroke="var(--border)" strokeWidth="1"/>
      <line x1="32" y1="32" x2="14" y2="46" stroke="var(--border)" strokeWidth="1"/>
      <line x1="32" y1="32" x2="50" y2="46" stroke="var(--border)" strokeWidth="1"/>
    </svg>
  ),
};

export default function EmptyState({ type = 'notes', title, message, action }) {
  return (
    <div className={styles.container}>
      <div className={styles.icon}>
        {ILLUSTRATIONS[type] || ILLUSTRATIONS.notes}
      </div>
      <h3 className={styles.title}>{title}</h3>
      {message && <p className={styles.message}>{message}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
