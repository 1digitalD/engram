const DATE_RECEIPT_FIELDS = new Set([
  'due_at',
  'follow_up_at',
  'updated_at',
  'created_at',
  'last_update',
  'decided_at',
  'occurred_at',
]);

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}(?:[T\s]|$)/;

export function formatLocalDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

export function isIsoDateValue(value) {
  return typeof value === 'string' && ISO_DATE_PATTERN.test(value);
}

export function formatReceiptField(field) {
  if (field === 'due_at') return 'due';
  if (field === 'follow_up_at') return 'follow-up';
  if (field === 'updated_at') return 'updated';
  if (field === 'created_at') return 'created';
  if (field === 'last_update') return 'last update';
  return String(field || 'receipt').replace(/_/g, ' ');
}

export function formatReceiptValue(field, value) {
  if (value == null || value === '') return '';
  if (DATE_RECEIPT_FIELDS.has(field) || isIsoDateValue(value)) {
    return formatLocalDate(value);
  }
  return String(value);
}
