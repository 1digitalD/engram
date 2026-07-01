import { describe, expect, it } from 'vitest';
import { friendlyApiError } from './v4Client';

describe('friendlyApiError (B-018)', () => {
  it('returns quota-specific message for 429 + insufficient_quota', () => {
    const err = Object.assign(new Error('You exceeded your current quota'), {
      status: 429,
      body: { error: 'You exceeded your current quota, please check your plan.' },
    });
    const msg = friendlyApiError(err);
    expect(msg).toMatch(/usage limit/i);
    expect(msg).not.toMatch(/quota/); // Don't leak the raw OpenAI billing message
  });

  it('returns rate-limit message for 429 without quota/billing keyword', () => {
    const err = Object.assign(new Error('Too many requests'), {
      status: 429,
      body: { error: 'Too many requests' },
    });
    const msg = friendlyApiError(err);
    expect(msg).toMatch(/rate-limited/i);
  });

  it('returns network message for fetch TypeError', () => {
    const err = new TypeError('Failed to fetch');
    const msg = friendlyApiError(err);
    expect(msg).toMatch(/connection/i);
    expect(msg).not.toMatch(/Failed to fetch/);
  });

  it('returns generic 5xx message', () => {
    const err = Object.assign(new Error('Internal Server Error'), {
      status: 500,
      body: { error: 'Internal Server Error' },
    });
    const msg = friendlyApiError(err);
    expect(msg).toMatch(/unexpected/i);
  });

  it('truncates very long messages', () => {
    const longMsg = 'x'.repeat(500);
    const err = Object.assign(new Error(longMsg), { status: 400, body: {} });
    const msg = friendlyApiError(err);
    expect(msg.length).toBeLessThanOrEqual(200);
    expect(msg).toMatch(/…$/);
  });

  it('uses fallback when no message and no status', () => {
    const err = new Error('');
    const msg = friendlyApiError(err, 'Custom fallback');
    expect(msg).toBe('Custom fallback');
  });

  it('uses fallback when err is undefined', () => {
    const msg = friendlyApiError(undefined, 'Nothing happened');
    expect(msg).toBe('Nothing happened');
  });

  it('returns default message when err is undefined and no fallback', () => {
    const msg = friendlyApiError(undefined);
    expect(msg).toBe('Something went wrong.');
  });

  it('passes through short 4xx error messages unchanged', () => {
    const err = Object.assign(new Error('Invalid input: missing required field'), {
      status: 422,
      body: { error: 'Invalid input: missing required field' },
    });
    const msg = friendlyApiError(err);
    expect(msg).toBe('Invalid input: missing required field');
  });
});