import { describe, expect, it } from 'vitest';
import { formatLocalDate, formatReceiptField, formatReceiptValue } from './dateFormat';

describe('dateFormat', () => {
  it('formats ISO timestamps as local calendar dates', () => {
    const formatted = formatLocalDate('2026-07-08T12:00:00Z');
    expect(formatted).toMatch(/Jul/);
    expect(formatted).toMatch(/8/);
    expect(formatted).toMatch(/2026/);
    expect(formatted).not.toContain('T');
    expect(formatted).not.toContain('Z');
  });

  it('formats receipt values for date fields', () => {
    expect(formatReceiptField('due_at')).toBe('due');
    expect(formatReceiptValue('due_at', '2026-07-08T09:00:00Z')).toMatch(/Jul/);
    expect(formatReceiptValue('note', 'from standup')).toBe('from standup');
  });
});
