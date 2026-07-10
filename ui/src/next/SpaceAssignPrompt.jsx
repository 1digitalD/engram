import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import styles from './SpaceAssignPrompt.module.css';

export default function SpaceAssignPrompt({
  taskTitle,
  spaces = [],
  open,
  busy = false,
  error = '',
  onClose,
  onAssign,
}) {
  const [pendingSpaceId, setPendingSpaceId] = useState('');

  useEffect(() => {
    if (!open) setPendingSpaceId('');
  }, [open]);

  if (!open || typeof document === 'undefined') return null;

  async function handlePick(spaceId) {
    if (!spaceId || busy || pendingSpaceId) return;
    setPendingSpaceId(spaceId);
    try {
      await onAssign(spaceId);
    } finally {
      setPendingSpaceId('');
    }
  }

  const disabled = busy || Boolean(pendingSpaceId);

  return createPortal(
    <div className={styles.backdrop} role="presentation">
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="space-assign-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className={styles.header}>
          <h2 id="space-assign-title" className={styles.title}>
            Assign to a space
          </h2>
          <p className={styles.subtitle}>
            {taskTitle ? `Choose where “${taskTitle}” belongs.` : 'Choose a space for this commitment.'}
          </p>
        </header>

        {spaces.length === 0 ? (
          <p className={styles.empty}>No spaces yet — create one from Review or Spaces first.</p>
        ) : (
          <ul className={styles.spaceList} aria-label="Choose space">
            {spaces.map((space) => (
              <li key={space.id}>
                <button
                  type="button"
                  className={styles.spaceOption}
                  disabled={disabled}
                  aria-busy={pendingSpaceId === space.id}
                  onClick={() => handlePick(space.id)}
                >
                  {space.title || 'Untitled space'}
                </button>
              </li>
            ))}
          </ul>
        )}

        {busy || pendingSpaceId ? (
          <p className={styles.status} aria-live="polite">Assigning…</p>
        ) : null}
        {error ? <p className={styles.error} role="alert">{error}</p> : null}

        <div className={styles.actions}>
          <button type="button" className={styles.buttonSecondary} disabled={disabled} onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
