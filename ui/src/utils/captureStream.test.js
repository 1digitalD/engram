import { describe, expect, it } from 'vitest';
import { formatCaptureStreamLabel } from './captureStream';

describe('formatCaptureStreamLabel', () => {
  it('maps known capture stream events to readable labels', () => {
    expect(formatCaptureStreamLabel({ type: 'extracting' })).toBe('extracting…');
    expect(formatCaptureStreamLabel({ type: 'linking', data: { links_created: 2 } }))
      .toBe('linking (2 links)…');
    expect(formatCaptureStreamLabel({ type: 'done' })).toBe('done');
    expect(formatCaptureStreamLabel({ type: 'error', data: { message: 'pipeline broke' } }))
      .toBe('pipeline broke');
  });
});
