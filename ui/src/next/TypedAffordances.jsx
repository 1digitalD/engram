import { useState } from 'react';

import { friendlyApiError, v4API } from '../api/v4Client';
import styles from './TypedAffordances.module.css';

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'waiting', label: 'Waiting' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
  { value: 'cancelled', label: 'Cancelled' },
];

function formatDateInput(value) {
  if (!value) return '';
  return String(value).slice(0, 10);
}

export function NudgeDraftAffordance({ item, onCopied }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState('');
  const [meta, setMeta] = useState(null);
  const [copyNote, setCopyNote] = useState('');

  async function loadDraft() {
    setLoading(true);
    setError('');
    setCopyNote('');
    try {
      const response = await v4API.commitments.nudgeDraft(item.id);
      const payload = response?.data || {};
      setDraft(payload.draft || '');
      setMeta(payload);
      setOpen(true);
    } catch (err) {
      setError(friendlyApiError(err, 'Could not draft nudge.'));
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    if (!draft.trim()) return;
    try {
      await navigator.clipboard.writeText(draft);
      setCopyNote('Copied to clipboard.');
      onCopied?.();
    } catch (_err) {
      setCopyNote('Copy failed — select the text and copy manually.');
    }
  }

  return (
    <div className={styles.stack}>
      <div className={styles.row}>
        <button
          type="button"
          className={styles.button}
          disabled={loading}
          onClick={() => (open && draft ? setOpen(false) : loadDraft())}
        >
          {loading ? 'Drafting…' : open ? 'Hide nudge draft' : 'Draft nudge'}
        </button>
        {open && draft ? (
          <button type="button" className={styles.buttonPrimary} onClick={handleCopy}>
            Copy nudge
          </button>
        ) : null}
      </div>
      {error ? (
        <p className={styles.nudgeMeta} role="alert">
          {error}
        </p>
      ) : null}
      {copyNote ? (
        <p className={styles.nudgeMeta} aria-live="polite">
          {copyNote}
        </p>
      ) : null}
      {open && draft ? (
        <div className={styles.nudgePanel}>
          {meta?.original_ask ? (
            <p className={styles.nudgeMeta}>
              Original ask: {meta.original_ask}
              {meta.committed_at ? ` · ${meta.committed_at}` : ''}
            </p>
          ) : null}
          <textarea
            aria-label={`${item.title} nudge draft`}
            className={styles.nudgeDraft}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </div>
      ) : null}
    </div>
  );
}

export function TaskAffordances({
  item,
  people,
  spaces,
  onStatusChange,
  onDueChange,
  onMoveSpace,
  onHandOwner,
  onLogUpdate,
  onMarkDone,
  showNudge = false,
}) {
  const [status, setStatus] = useState(item.status || 'open');
  const [dueDate, setDueDate] = useState(formatDateInput(item.due_at));
  const [spaceId, setSpaceId] = useState(item.space?.id || '');
  const [ownerId, setOwnerId] = useState(item.owner?.id || '');
  const [updateText, setUpdateText] = useState('');

  return (
    <div className={styles.stack}>
      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>Status</span>
          <select
            aria-label={`${item.title} status`}
            className={styles.select}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className={styles.button}
          onClick={() => onStatusChange(item.id, status)}
        >
          Set status
        </button>
      </div>

      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>Due</span>
          <input
            aria-label={`${item.title} due date`}
            className={styles.input}
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
          />
        </label>
        <button
          type="button"
          className={styles.button}
          onClick={() => onDueChange(item.id, dueDate)}
        >
          Set due date
        </button>
      </div>

      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>Space</span>
          <select
            aria-label={`${item.title} move to space`}
            className={styles.select}
            value={spaceId}
            onChange={(event) => setSpaceId(event.target.value)}
          >
            <option value="">Choose space</option>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.title}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className={styles.button}
          disabled={!spaceId}
          onClick={() => onMoveSpace(item.id, spaceId)}
        >
          Move to space
        </button>
      </div>

      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>Owner</span>
          <select
            aria-label={`${item.title} hand to owner`}
            className={styles.select}
            value={ownerId}
            onChange={(event) => setOwnerId(event.target.value)}
          >
            <option value="">Choose owner</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.title}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className={styles.button}
          disabled={!ownerId}
          onClick={() => onHandOwner(item.id, ownerId)}
        >
          Hand to owner
        </button>
      </div>

      <div className={styles.row}>
        <label className={styles.fieldWide}>
          <span className={styles.label}>Update</span>
          <input
            aria-label={`${item.title} log update`}
            className={styles.input}
            type="text"
            value={updateText}
            onChange={(event) => setUpdateText(event.target.value)}
          />
        </label>
        <button
          type="button"
          className={styles.button}
          disabled={!updateText.trim()}
          onClick={() => {
            onLogUpdate(item.id, updateText.trim());
            setUpdateText('');
          }}
        >
          Log update
        </button>
        <button type="button" className={styles.buttonPrimary} onClick={() => onMarkDone(item.id)}>
          Mark done
        </button>
      </div>
      {showNudge ? <NudgeDraftAffordance item={item} /> : null}
    </div>
  );
}

export function GroupCommitmentComposer({ label, onSubmit }) {
  const [title, setTitle] = useState('');

  return (
    <div className={styles.row}>
      <label className={styles.fieldWide}>
        <span className={styles.label}>Add commitment</span>
        <input
          aria-label={`Add commitment for ${label}`}
          className={styles.input}
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <button
        type="button"
        className={styles.buttonPrimary}
        disabled={!title.trim()}
        onClick={() => {
          onSubmit(title.trim());
          setTitle('');
        }}
      >
        Add commitment
      </button>
    </div>
  );
}

export function EntryAttachAffordance({ entryTitle, targets, onAttach }) {
  const [targetId, setTargetId] = useState('');

  return (
    <div className={styles.row}>
      <label className={styles.fieldWide}>
        <span className={styles.label}>Attach</span>
        <select
          aria-label={`Attach ${entryTitle}`}
          className={styles.select}
          value={targetId}
          onChange={(event) => setTargetId(event.target.value)}
        >
          <option value="">Choose destination</option>
          {targets.map((target) => (
            <option key={target.id} value={target.id}>
              {target.title}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className={styles.button}
        disabled={!targetId}
        onClick={() => onAttach(targetId)}
      >
        Attach entry
      </button>
    </div>
  );
}
