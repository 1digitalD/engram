import { useState } from 'react';
import {
  DISMISS_REASONS,
  CREATE_ENTITY_TYPES,
  UPDATE_STATUS_OPTIONS,
  buildProposalEdits,
  displayItemMeta,
  initialProposalEditState,
  isAppliedItem,
} from './reviewUtils';
import { ACTION_LABELS } from './vocab';
import styles from './ReviewSurface.module.css';

function ProposalEditForm({ suggestion, item, busy, onCancel, onSubmit }) {
  const [state, setState] = useState(() => initialProposalEditState(item, suggestion));
  const op = suggestion?.operation_type;

  function updateField(field, value) {
    setState((current) => ({ ...current, [field]: value }));
  }

  return (
    <div className={styles.editForm}>
      {op === 'create_decision' ? (
        <>
          <label htmlFor={`edit-statement-${item.id}`}>Decision statement</label>
          <textarea
            id={`edit-statement-${item.id}`}
            className={styles.editTextarea}
            value={state.statement}
            onChange={(event) => updateField('statement', event.target.value)}
            disabled={busy}
            rows={3}
          />
          <label htmlFor={`edit-context-${item.id}`}>Context (optional)</label>
          <input
            id={`edit-context-${item.id}`}
            className={styles.editInput}
            value={state.context}
            onChange={(event) => updateField('context', event.target.value)}
            disabled={busy}
          />
        </>
      ) : op === 'update_entity' ? (
        <>
          <label htmlFor={`edit-status-${item.id}`}>Status</label>
          <select
            id={`edit-status-${item.id}`}
            className={styles.editInput}
            value={state.status}
            onChange={(event) => updateField('status', event.target.value)}
            disabled={busy}
          >
            <option value="">Keep as proposed</option>
            {UPDATE_STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{status.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <label htmlFor={`edit-due-${item.id}`}>Due date</label>
          <input
            id={`edit-due-${item.id}`}
            type="date"
            className={styles.editInput}
            value={state.due_at}
            onChange={(event) => updateField('due_at', event.target.value)}
            disabled={busy}
          />
          <label htmlFor={`edit-follow-${item.id}`}>Follow-up date</label>
          <input
            id={`edit-follow-${item.id}`}
            type="date"
            className={styles.editInput}
            value={state.follow_up_at}
            onChange={(event) => updateField('follow_up_at', event.target.value)}
            disabled={busy}
          />
          <label htmlFor={`edit-priority-${item.id}`}>Priority</label>
          <select
            id={`edit-priority-${item.id}`}
            className={styles.editInput}
            value={state.priority}
            onChange={(event) => updateField('priority', event.target.value)}
            disabled={busy}
          >
            <option value="">Keep as proposed</option>
            {['low', 'medium', 'high', 'critical'].map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </>
      ) : (
        <>
          <label htmlFor={`edit-title-${item.id}`}>Title</label>
          <input
            id={`edit-title-${item.id}`}
            className={styles.editInput}
            value={state.title}
            onChange={(event) => updateField('title', event.target.value)}
            disabled={busy}
          />
          <label htmlFor={`edit-type-${item.id}`}>Type</label>
          <select
            id={`edit-type-${item.id}`}
            className={styles.editInput}
            value={state.type}
            onChange={(event) => updateField('type', event.target.value)}
            disabled={busy}
          >
            {CREATE_ENTITY_TYPES.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <label htmlFor={`edit-due-create-${item.id}`}>Due date</label>
          <input
            id={`edit-due-create-${item.id}`}
            type="date"
            className={styles.editInput}
            value={state.due_at}
            onChange={(event) => updateField('due_at', event.target.value)}
            disabled={busy}
          />
          <label htmlFor={`edit-owner-${item.id}`}>Owner</label>
          <input
            id={`edit-owner-${item.id}`}
            className={styles.editInput}
            value={state.assigned_to}
            onChange={(event) => updateField('assigned_to', event.target.value)}
            disabled={busy}
            placeholder="Person name"
          />
          <label htmlFor={`edit-content-${item.id}`}>Notes (optional)</label>
          <textarea
            id={`edit-content-${item.id}`}
            className={styles.editTextarea}
            value={state.content}
            onChange={(event) => updateField('content', event.target.value)}
            disabled={busy}
            rows={2}
          />
        </>
      )}
      <div className={styles.actions}>
        <button type="button" className={styles.buttonSecondary} disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className={styles.buttonPrimary}
          disabled={busy}
          onClick={() => onSubmit(buildProposalEdits(suggestion, state))}
        >
          {ACTION_LABELS.verifyWithEdits}
        </button>
      </div>
    </div>
  );
}

export default function ReviewItem({
  item,
  suggestions,
  busy,
  onVerify,
  onEdit,
  onDismiss,
  onLater,
  onUndoApplied,
}) {
  const [dismissOpen, setDismissOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const meta = displayItemMeta(item, suggestions);

  if (isAppliedItem(item)) {
    return (
      <li className={styles.item}>
        <div className={styles.itemHeader}>
          <h3 className={styles.itemTitle}>{meta.title}</h3>
          <span className={styles.itemType}>{meta.typeLabel}</span>
        </div>
        {meta.evidence ? <p className={styles.itemEvidence}>{meta.evidence}</p> : null}
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => onUndoApplied(item.event_id)}
          >
            {ACTION_LABELS.undo}
          </button>
        </div>
      </li>
    );
  }

  if (!meta.resolvable) {
    return (
      <li className={styles.item}>
        <div className={styles.itemHeader}>
          <h3 className={styles.itemTitle}>{meta.title}</h3>
          <span className={styles.itemType}>{meta.typeLabel}</span>
        </div>
        {meta.evidence ? <p className={styles.itemEvidence}>{meta.evidence}</p> : null}
      </li>
    );
  }

  return (
    <li className={styles.item}>
      <div className={styles.itemHeader}>
        <h3 className={styles.itemTitle}>{meta.title}</h3>
        <span className={styles.itemType}>{meta.typeLabel}</span>
      </div>
      {meta.evidence ? <p className={styles.itemEvidence}>{meta.evidence}</p> : null}

      {editOpen ? (
        <ProposalEditForm
          suggestion={meta.suggestion}
          item={item}
          busy={busy}
          onCancel={() => setEditOpen(false)}
          onSubmit={(edits) => {
            onEdit(item.id, edits);
            setEditOpen(false);
          }}
        />
      ) : dismissOpen ? (
        <div className={styles.dismissReasons}>
          <span>Dismiss reason:</span>
          <div className={styles.dismissReasonList} role="group" aria-label="Dismiss reason">
            {DISMISS_REASONS.map((reason) => (
              <button
                key={reason}
                type="button"
                className={styles.buttonSecondary}
                disabled={busy}
                onClick={() => {
                  onDismiss(item.id, reason);
                  setDismissOpen(false);
                }}
              >
                {reason}
              </button>
            ))}
            <button
              type="button"
              className={styles.buttonSecondary}
              disabled={busy}
              onClick={() => {
                onDismiss(item.id);
                setDismissOpen(false);
              }}
            >
              no reason
            </button>
          </div>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => setDismissOpen(false)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => onLater(item.id)}
          >
            {ACTION_LABELS.later}
          </button>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => setDismissOpen(true)}
          >
            {ACTION_LABELS.dismiss}
          </button>
          <button
            type="button"
            className={styles.buttonSecondary}
            disabled={busy}
            onClick={() => setEditOpen(true)}
          >
            {ACTION_LABELS.edit}
          </button>
          <button
            type="button"
            className={styles.buttonPrimary}
            disabled={busy}
            onClick={() => onVerify(item.id)}
          >
            {ACTION_LABELS.verify}
          </button>
        </div>
      )}
    </li>
  );
}
