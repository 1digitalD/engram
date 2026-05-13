import React, { useState } from 'react';
import { AlertTriangle, Check, X, Loader2 } from 'lucide-react';
import Modal from '../ui/Modal';
import { EntityTypeIcon } from '../ConnectionsPanel/ConnectionsPanel';
import styles from './DeleteConfirmModal.module.css';

const ENTITY_TYPE_LABELS = {
  note: 'Note',
  task: 'Task',
  project: 'Project',
  area: 'Area',
  resource: 'Resource',
  person: 'Person',
};

export default function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  entityTitle,
  entityType,
  preview,
}) {
  const [cascadeIds, setCascadeIds] = useState(new Set());
  const [busy, setBusy] = useState(false);

  const safeToCascade = preview?.safe_to_cascade || [];
  const blocked = preview?.blocked || [];
  const warning = preview?.warning;

  const handleToggle = (id) => {
    setCascadeIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (cascadeIds.size === safeToCascade.length) {
      setCascadeIds(new Set());
    } else {
      setCascadeIds(new Set(safeToCascade.map((e) => e.id)));
    }
  };

  const handleConfirm = async () => {
    setBusy(true);
    try {
      await onConfirm(Array.from(cascadeIds));
    } finally {
      setBusy(false);
    }
  };

  const hasCascadeItems = safeToCascade.length > 0;
  const hasBlockedItems = blocked.length > 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={busy ? () => {} : onClose}
      title="Delete entity"
      size="md"
      footer={
        <>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={handleConfirm}
            disabled={busy}
          >
            {busy ? (
              <>
                <Loader2 size={14} className="spin" /> Deleting…
              </>
            ) : (
              <>
                <X size={14} /> Delete
              </>
            )}
          </button>
        </>
      }
    >
      <div className={styles.warning}>
        <AlertTriangle size={16} />
        <span>
          Are you sure you want to delete <strong>{entityTitle}</strong>? This
          action cannot be undone.
        </span>
      </div>

      {hasCascadeItems && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>
              {safeToCascade.length} linked entity
              {safeToCascade.length > 1 ? 'ies' : 'y'} will become orphaned
            </span>
            <button
              type="button"
              className={styles.selectAll}
              onClick={handleSelectAll}
            >
              {cascadeIds.size === safeToCascade.length
                ? 'Deselect all'
                : 'Select all'}
            </button>
          </div>
          <ul className={styles.entityList}>
            {safeToCascade.map((entity) => (
              <li key={entity.id} className={styles.entityRow}>
                <label className={styles.entityLabel}>
                  <input
                    type="checkbox"
                    checked={cascadeIds.has(entity.id)}
                    onChange={() => handleToggle(entity.id)}
                  />
                  <span className={styles.entityIcon}>
                    <EntityTypeIcon type={entity.type} size={14} />
                  </span>
                  <span className={styles.entityName}>{entity.title}</span>
                  <span className={styles.entityType}>
                    {ENTITY_TYPE_LABELS[entity.type] || entity.type}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {cascadeIds.size > 0 && (
            <p className={styles.cascadeNote}>
              <Check size={12} /> {cascadeIds.length} orphaned entity
              {cascadeIds.size > 1 ? 'ies' : 'y'} will also be deleted
            </p>
          )}
        </div>
      )}

      {hasBlockedItems && (
        <div className={styles.section}>
          <span className={styles.sectionTitle}>
            {blocked.length} linked entity{blocked.length > 1 ? 'ies' : 'y'}{' '}
            have other connections and will not be affected
          </span>
          <ul className={styles.entityList}>
            {blocked.map((entity) => (
              <li key={entity.id} className={`${styles.entityRow} ${styles.blocked}`}>
                <span className={styles.entityIcon}>
                  <EntityTypeIcon type={entity.type} size={14} />
                </span>
                <span className={styles.entityName}>{entity.title}</span>
                <span className={styles.entityType}>
                  {ENTITY_TYPE_LABELS[entity.type] || entity.type}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {warning && !hasCascadeItems && !hasBlockedItems && (
        <p className={styles.warningText}>{warning}</p>
      )}

      {!hasCascadeItems && !hasBlockedItems && !warning && (
        <p className={styles.safeText}>
          No linked entities will be affected.
        </p>
      )}
    </Modal>
  );
}
