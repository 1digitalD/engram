import styles from './statusTheme.module.css';

export const TASK_STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'waiting', label: 'Waiting' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
  { value: 'cancelled', label: 'Cancelled' },
];

export const PROJECT_STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'on_hold', label: 'On hold' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];

export const AREA_STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
];

const STATUS_LABELS = {
  open: 'Open',
  in_progress: 'In progress',
  waiting: 'Waiting',
  blocked: 'Blocked',
  done: 'Done',
  cancelled: 'Cancelled',
  active: 'Active',
  on_hold: 'On hold',
  completed: 'Completed',
  archived: 'Archived',
};

const TONE_BY_STATUS = {
  open: styles.toneOpen,
  in_progress: styles.toneInProgress,
  waiting: styles.toneWaiting,
  blocked: styles.toneBlocked,
  done: styles.toneDone,
  cancelled: styles.toneCancelled,
  active: styles.toneActive,
  on_hold: styles.toneOnHold,
  completed: styles.toneCompleted,
  archived: styles.toneArchived,
};

export function normalizeStatus(status) {
  return String(status || 'open')
    .toLowerCase()
    .replace(/-/g, '_');
}

export function statusLabel(status) {
  const key = normalizeStatus(status);
  return STATUS_LABELS[key] || key.replace(/_/g, ' ');
}

export function statusToneClass(status) {
  return TONE_BY_STATUS[normalizeStatus(status)] || styles.toneDefault;
}

function joinClasses(...values) {
  return values.filter(Boolean).join(' ');
}

export function StatusBadge({ status, className }) {
  return (
    <span className={joinClasses(styles.badge, statusToneClass(status), className)}>
      {statusLabel(status)}
    </span>
  );
}

export function StatusSelect({
  value,
  onChange,
  options,
  className,
  variant = 'pill',
  ...rest
}) {
  const variantClass = variant === 'chip' ? styles.selectChip : styles.selectPill;
  return (
    <select
      className={joinClasses(styles.select, variantClass, statusToneClass(value), className)}
      value={value}
      onChange={onChange}
      {...rest}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
