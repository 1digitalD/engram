import { normalizeSearchResults } from '../utils/searchResults';

const API_PREFIX = '/api/v4';

/**
 * Translate known API errors to user-friendly messages. B-018: raw OpenAI
 * error strings are confusing and can leak billing/quota internals. Use
 * `friendlyApiError(err)` in catch blocks instead of `err.message`.
 */
export function friendlyApiError(err, fallback) {
  const status = err?.status;
  const body = err?.body || {};
  // 429 quota / rate limit
  if (status === 429) {
    if (
      typeof body.error === 'string' &&
      /quota|billing|insufficient/i.test(body.error)
    ) {
      return 'Service is temporarily unavailable — usage limit reached. Try again later or check your plan.';
    }
    return 'Service is rate-limited right now. Wait a minute and try again.';
  }
  // Network / CORS / DNS — fetch throws before status is set
  if (err instanceof TypeError && /fetch|network/i.test(err.message)) {
    return 'Could not reach the workspace. Check your connection and try again.';
  }
  if (status >= 500) {
    return 'The workspace hit an unexpected error. Try again in a moment.';
  }
  // Default: trim and clean the raw message
  const raw = err?.message || '';
  if (raw.length > 200) return `${raw.slice(0, 197)}…`;
  return raw || fallback || 'Something went wrong.';
}

export async function v4Request(method, path, body = null, params = {}) {
  const url = new URL(`${API_PREFIX}${path}`, window.location.origin);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value);
    }
  });

  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== null && body !== undefined) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url.toString(), options);
  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  const isJson = contentType.includes('application/json');

  if (!response.ok) {
    const errorBody = isJson
      ? await response.json().catch(() => ({ error: response.statusText }))
      : { error: `${response.status} ${response.statusText}` };
    const error = new Error(errorBody.error || errorBody.message || `HTTP ${response.status}`);
    error.status = response.status;
    error.body = errorBody;
    throw error;
  }

  if (response.status === 204) return {};
  return isJson ? response.json() : {};
}

const getEntity = (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}`);
const getEntityDetail = (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}/detail`);
const updateEntity = (id, data) => v4Request('PATCH', `/entities/${encodeURIComponent(id)}`, data);
const deleteEntity = (id) => v4Request('DELETE', `/entities/${encodeURIComponent(id)}`);

export { captureStream } from '../utils/captureStream';

export const v4API = {
  health: () => v4Request('GET', '/health'),
  capture: (data) => v4Request('POST', '/capture', data),
  entities: {
    list: (params = {}) => v4Request('GET', '/entities', null, params),
    create: (data) => v4Request('POST', '/entities', data),
    get: getEntity,
    detail: getEntityDetail,
    update: updateEntity,
    delete: deleteEntity,
    setOwner: (id) => v4Request('POST', `/entities/${encodeURIComponent(id)}/owner`),
    clearOwner: (id) => v4Request('DELETE', `/entities/${encodeURIComponent(id)}/owner`),
    merge: (id, targetId) => v4Request('POST', `/entities/${encodeURIComponent(id)}/merge`, { target_id: targetId }),
    convert: (id, type) => v4Request('POST', `/entities/${encodeURIComponent(id)}/convert`, { type }),
    createLink: (id, data) => v4Request('POST', `/entities/${encodeURIComponent(id)}/links`, data),
    pin: (id, field) => v4Request('POST', `/entities/${encodeURIComponent(id)}/pin`, { field }),
    unpin: (id, field) => v4Request('POST', `/entities/${encodeURIComponent(id)}/unpin`, { field }),
    events: (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}/events`),
    canonical: (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}/canonical`),
    captureChanges: (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}/capture-changes`),
  },
  events: {
    revert: (id) => v4Request('POST', `/events/${encodeURIComponent(id)}/revert`),
  },
  relationships: {
    list: (entityId) => v4Request('GET', `/entities/${encodeURIComponent(entityId)}/relationships`),
    create: (entityId, data) => v4Request('POST', `/entities/${encodeURIComponent(entityId)}/relationships`, data),
    update: (relationshipId, data) => v4Request('PATCH', `/relationships/${encodeURIComponent(relationshipId)}`, data),
    delete: (relationshipId) => v4Request('DELETE', `/relationships/${encodeURIComponent(relationshipId)}`),
  },
  suggestions: {
    list: (params = {}) => v4Request('GET', '/suggestions', null, params),
    update: (id, data) => v4Request('PATCH', `/suggestions/${encodeURIComponent(id)}`, data),
    accept: (id) => v4Request('POST', `/suggestions/${encodeURIComponent(id)}/accept`),
    dismiss: (id, data) => v4Request('POST', `/suggestions/${encodeURIComponent(id)}/dismiss`, data),
    resolveToExisting: (id, targetId) => v4Request('POST', `/suggestions/${encodeURIComponent(id)}/resolve-to-existing`, targetId ? { target_id: targetId } : {}),
    reconcile: (params = {}) => v4Request('POST', '/suggestions/reconcile', null, params),
  },
  review: {
    resolve: (entityId) => v4Request('POST', `/entities/${encodeURIComponent(entityId)}/review/resolve`),
  },
  reprocess: (entityId) => v4Request('POST', `/entities/${encodeURIComponent(entityId)}/reprocess`),
  search: async (params = {}) => {
    const response = await v4Request('GET', '/search', null, params);
    return { ...response, data: normalizeSearchResults(response) };
  },
  mentions: (params = {}) => v4Request('GET', '/entities/mentions', null, params),
  today: Object.assign(() => v4Request('GET', '/today'), {
    review: () => v4Request('POST', '/today/review'),
  }),
  summary: () => v4Request('GET', '/summary'),
  threads: (params = {}) => v4Request('GET', '/threads', null, params),
  brief: (params = {}) => v4Request('GET', '/brief', null, params),
  metrics: {
    trust: (params = {}) => v4Request('GET', '/metrics/trust', null, params),
    recordReview: (data) => v4Request('POST', '/metrics/trust/review', data),
  },
  recent: (params = {}) => v4Request('GET', '/recent', null, params),
  inbox: (params = {}) => v4Request('GET', '/inbox', null, params),
  ask: (data) => v4Request('POST', '/ask', data),
  agentActivity: (params = {}) => v4Request('GET', '/agent-activity', null, params),
  decisions: {
    list: (params = {}) => v4Request('GET', '/decisions', null, params),
    create: (data) => v4Request('POST', '/decisions', data),
  },
  timeline: (params = {}) => v4Request('GET', '/timeline', null, params),
  activityUpdates: {
    list: (entityId, params = {}) => v4Request(
      'GET',
      `/entities/${encodeURIComponent(entityId)}/activity_updates`,
      null,
      params,
    ),
    create: (entityId, content) => v4Request('POST', `/entities/${encodeURIComponent(entityId)}/activity_updates`, { content }),
  },
  workboard: (params = {}) => v4Request('GET', '/workboard', null, params),
  commitments: {
    nudgeDraft: (id) => v4Request('POST', `/commitments/${encodeURIComponent(id)}/nudge-draft`),
  },
  reports: {
    list: (params = {}) => v4Request('GET', '/reports', null, params),
    get: (id) => v4Request('GET', `/reports/${encodeURIComponent(id)}`),
    resolve: (id, data) => v4Request('POST', `/reports/${encodeURIComponent(id)}/resolve`, data),
  },
};
