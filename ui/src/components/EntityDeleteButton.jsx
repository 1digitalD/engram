import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { v4API, friendlyApiError } from '../api/v4Client';
import styles from './EntityDeleteButton.module.css';

export default function EntityDeleteButton({
  entity,
  onDeleted,
  onError,
  disabled = false,
  className = '',
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!entity?.id || deleting) return;
    setDeleting(true);
    try {
      await v4API.entities.delete(entity.id);
      onDeleted?.();
    } catch (err) {
      onError?.(friendlyApiError(err, 'Failed to delete'));
    } finally {
      setDeleting(false);
    }
  }

  const label = entity?.title || entity?.type || 'item';

  return (
    <button
      type="button"
      className={`${styles.button} ${className}`.trim()}
      onClick={handleDelete}
      disabled={disabled || deleting}
      aria-label={`Delete ${label}`}
      title="Delete"
    >
      <Trash2 size={14} strokeWidth={2.2} aria-hidden="true" />
      <span>{deleting ? 'Deleting…' : 'Delete'}</span>
    </button>
  );
}
