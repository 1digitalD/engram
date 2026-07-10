import { useEffect, useRef, useState } from 'react';
import { FolderInput, UserRound } from 'lucide-react';

import { friendlyApiError, v4API } from '../api/v4Client';
import { taskOwnerId } from './commitmentUtils';
import { StatusSelect, TASK_STATUS_OPTIONS } from './statusTheme';
import styles from './TypedAffordances.module.css';

function formatDateInput(value) {
  if (!value) return '';
  return String(value).slice(0, 10);
}

export function ExpandableUpdateField({ item, onLogUpdate }) {
  const [expanded, setExpanded] = useState(false);
  const [updateText, setUpdateText] = useState('');
  const fieldRef = useRef(null);

  useEffect(() => {
    if (expanded) {
      fieldRef.current?.focus();
    }
  }, [expanded]);

  async function submitUpdate() {
    const text = updateText.trim();
    if (!text) return;
    const ok = await onLogUpdate(item.id, text);
    if (ok !== false) {
      setUpdateText('');
      setExpanded(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submitUpdate();
    }
  }

  const sharedProps = {
    'aria-label': `${item.title} log update`,
    className: expanded ? styles.updateTextarea : styles.updateInput,
    value: updateText,
    onChange: (event) => setUpdateText(event.target.value),
    onFocus: () => setExpanded(true),
    onKeyDown: handleKeyDown,
    placeholder: 'Log update…',
    rows: expanded ? 3 : 1,
  };

  return (
    <div className={styles.expandableUpdate}>
      <label className={styles.updateField}>
        <span className={styles.srOnly}>Log update for {item.title}</span>
        <textarea ref={fieldRef} {...sharedProps} />
      </label>
      <button
        type="button"
        className={styles.button}
        aria-label={`Log update for ${item.title}`}
        disabled={!updateText.trim()}
        onClick={submitUpdate}
      >
        Log
      </button>
    </div>
  );
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

export function InlineTaskStatusDue({ item, onStatusChange, onDueChange, onFollowUpChange }) {
  return (
    <div className={styles.scheduleRow}>
      <StatusSelect
        aria-label={`${item.title} status`}
        className={styles.inlineSelect}
        value={item.status || 'open'}
        options={TASK_STATUS_OPTIONS}
        onChange={(event) => onStatusChange(item.id, event.target.value)}
      />
      <input
        aria-label={`${item.title} due date`}
        className={styles.inlineInput}
        type="date"
        title="Due date"
        value={formatDateInput(item.due_at)}
        onChange={(event) => onDueChange(item.id, event.target.value)}
      />
      {onFollowUpChange ? (
        <input
          aria-label={`${item.title} follow-up date`}
          className={styles.inlineInput}
          type="date"
          title="Follow-up date"
          value={formatDateInput(item.follow_up_at)}
          onChange={(event) => onFollowUpChange(item.id, event.target.value)}
        />
      ) : null}
    </div>
  );
}

export function WorkboardItemAffordances({
  item,
  people,
  spaces,
  group,
  onStatusChange,
  onDueChange,
  onFollowUpChange,
  onMoveSpace,
  onHandOwner,
  onLogUpdate,
  showNudge = false,
  expandableUpdate = false,
}) {
  const [ownerId, setOwnerId] = useState(() => taskOwnerId(item));
  const [moveOpen, setMoveOpen] = useState(false);
  const [spaceId, setSpaceId] = useState(item.space?.id || '');
  const [updateText, setUpdateText] = useState('');
  const [status, setStatus] = useState(item.status || 'open');
  const [dueDate, setDueDate] = useState(() => formatDateInput(item.due_at));
  const [followUpDate, setFollowUpDate] = useState(() => formatDateInput(item.follow_up_at));
  const itemRef = useRef(item);

  useEffect(() => {
    itemRef.current = item;
  }, [item]);

  useEffect(() => {
    setOwnerId(taskOwnerId(item));
  }, [item.id, item.owner?.id, item.people?.[0]?.id, item.assigned_to?.id]);

  useEffect(() => {
    setStatus(item.status || 'open');
    setDueDate(formatDateInput(item.due_at));
    setFollowUpDate(formatDateInput(item.follow_up_at));
  }, [item.id, item.status, item.due_at, item.follow_up_at]);

  function closeMovePanel() {
    setMoveOpen(false);
    setSpaceId(item.space?.id || '');
  }

  async function confirmMove() {
    if (!spaceId || spaceId === item.space?.id) {
      closeMovePanel();
      return;
    }
    const ok = await onMoveSpace(item.id, spaceId);
    if (ok !== false) closeMovePanel();
  }

  return (
    <div className={styles.workboardItem}>
      <div className={styles.controlRows}>
        <div className={styles.assigneeRow}>
          <StatusSelect
            aria-label={`${item.title} status`}
            className={styles.inlineSelect}
            value={status}
            options={TASK_STATUS_OPTIONS}
            onChange={async (event) => {
              const next = event.target.value;
              setStatus(next);
              const ok = await onStatusChange(item.id, next);
              if (ok === false) setStatus(itemRef.current.status || 'open');
            }}
          />
          <select
            aria-label={`${item.title} owner`}
            className={styles.inlineSelectWide}
            value={ownerId}
            onChange={(event) => setOwnerId(event.target.value)}
          >
            <option value="">Unassigned</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.glyphButton}
            aria-label={`Hand ${item.title} to owner`}
            disabled={!ownerId || ownerId === taskOwnerId(item)}
            onClick={async () => {
              const ok = await onHandOwner(item.id, ownerId);
              if (ok === false) setOwnerId(taskOwnerId(itemRef.current));
            }}
          >
            <UserRound size={16} strokeWidth={2.25} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.scheduleRow}>
          <input
            aria-label={`${item.title} due date`}
            className={styles.inlineInput}
            type="date"
            title="Due date"
            value={dueDate}
            onChange={async (event) => {
              const next = event.target.value;
              setDueDate(next);
              const ok = await onDueChange(item.id, next);
              if (ok === false) setDueDate(formatDateInput(itemRef.current.due_at));
            }}
          />
          <input
            aria-label={`${item.title} follow-up date`}
            className={styles.inlineInput}
            type="date"
            title="Follow-up date"
            value={followUpDate}
            onChange={async (event) => {
              const next = event.target.value;
              setFollowUpDate(next);
              const ok = await onFollowUpChange(item.id, next);
              if (ok === false) setFollowUpDate(formatDateInput(itemRef.current.follow_up_at));
            }}
          />
          <button
            type="button"
            className={moveOpen ? styles.glyphButtonActive : styles.glyphButton}
            aria-label={`Move ${item.title} to another space`}
            aria-expanded={moveOpen}
            onClick={() => setMoveOpen((open) => !open)}
          >
            <FolderInput size={16} strokeWidth={2.25} aria-hidden="true" />
          </button>
          {expandableUpdate ? (
            <ExpandableUpdateField item={item} onLogUpdate={onLogUpdate} />
          ) : (
            <>
              <label className={styles.updateField}>
                <span className={styles.srOnly}>Log update for {item.title}</span>
                <input
                  aria-label={`${item.title} log update`}
                  className={styles.updateInput}
                  type="text"
                  placeholder="Log update…"
                  value={updateText}
                  onChange={(event) => setUpdateText(event.target.value)}
                />
              </label>
              <button
                type="button"
                className={styles.button}
                aria-label={`Log update for ${item.title}`}
                disabled={!updateText.trim()}
                onClick={async () => {
                  const text = updateText.trim();
                  if (!text) return;
                  const ok = await onLogUpdate(item.id, text);
                  if (ok !== false) setUpdateText('');
                }}
              >
                Log
              </button>
            </>
          )}
        </div>
      </div>

      {moveOpen ? (
        <div className={styles.movePanel}>
          {!item.space?.id ? (
            <ul className={styles.spacePickList} aria-label={`${item.title} move to space`}>
              {spaces.map((space) => (
                <li key={space.id}>
                  <button
                    type="button"
                    className={styles.spacePickButton}
                    onClick={async () => {
                      const ok = await onMoveSpace(item.id, space.id);
                      if (ok !== false) closeMovePanel();
                    }}
                  >
                    {space.title || 'Untitled space'}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <>
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
              <div className={styles.moveActions}>
                <button type="button" className={styles.buttonPrimary} disabled={!spaceId} onClick={confirmMove}>
                  Move
                </button>
                <button type="button" className={styles.button} onClick={closeMovePanel}>
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {showNudge ? <NudgeDraftAffordance item={item} /> : null}
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
  hideStatusDue = false,
}) {
  const [status, setStatus] = useState(item.status || 'open');
  const [dueDate, setDueDate] = useState(formatDateInput(item.due_at));
  const [spaceId, setSpaceId] = useState(item.space?.id || '');
  const [ownerId, setOwnerId] = useState(item.owner?.id || '');
  const [updateText, setUpdateText] = useState('');

  return (
    <div className={styles.stack}>
      {!hideStatusDue ? (
        <>
          <div className={styles.row}>
            <label className={styles.field}>
              <span className={styles.label}>Status</span>
              <StatusSelect
                aria-label={`${item.title} status`}
                className={styles.select}
                value={status}
                options={TASK_STATUS_OPTIONS}
                onChange={(event) => setStatus(event.target.value)}
              />
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
        </>
      ) : null}

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
