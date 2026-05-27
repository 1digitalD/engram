import React from 'react';
import { Archive, Trash2 } from 'lucide-react';
import { v4API } from '../api/v4Client';
import styles from './CardActions.module.css';

/**
 * Inline card actions: archive + delete icons.
 * Hover-revealed on the parent card via `.cardActionsParent:hover .cardActions { opacity: 1 }`.
 * Click handlers stop propagation so the parent <Link> doesn't navigate.
 */
export default function CardActions({ entity, onChanged }) {
  async function archive(event) {
    event.preventDefault();
    event.stopPropagation();
    try {
      await v4API.entities.update(entity.id, { lifecycle: 'archived' });
      onChanged?.({ kind: 'archived', id: entity.id });
    } catch (err) {
      // Best-effort — surfacing errors here is too noisy on a quick action.
      // The detail page error banner is the right place for retries.
    }
  }

  async function remove(event) {
    event.preventDefault();
    event.stopPropagation();
    try {
      await v4API.entities.delete(entity.id);
      onChanged?.({ kind: 'deleted', id: entity.id });
    } catch (err) {
      // ditto
    }
  }

  return (
    <span className={styles.cardActions}>
      <button
        type="button"
        className={styles.actionButton}
        onClick={archive}
        aria-label={`Archive ${entity.title || 'item'}`}
        title="Archive"
      >
        <Archive size={13} strokeWidth={2.2} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={`${styles.actionButton} ${styles.danger}`}
        onClick={remove}
        aria-label={`Delete ${entity.title || 'item'}`}
        title="Delete"
      >
        <Trash2 size={13} strokeWidth={2.2} aria-hidden="true" />
      </button>
    </span>
  );
}
