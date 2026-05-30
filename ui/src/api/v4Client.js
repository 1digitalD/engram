const API_PREFIX = '/api/v4';

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
    events: (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}/events`),
    canonical: (id) => v4Request('GET', `/entities/${encodeURIComponent(id)}/canonical`),
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
    dismiss: (id) => v4Request('POST', `/suggestions/${encodeURIComponent(id)}/dismiss`),
  },
  reprocess: (entityId) => v4Request('POST', `/entities/${encodeURIComponent(entityId)}/reprocess`),
  search: (params = {}) => v4Request('GET', '/search', null, params),
  today: () => v4Request('GET', '/today'),
  recent: (params = {}) => v4Request('GET', '/recent', null, params),
  inbox: (params = {}) => v4Request('GET', '/inbox', null, params),
  activityUpdates: {
    list: (entityId) => v4Request('GET', `/entities/${encodeURIComponent(entityId)}/activity_updates`),
    create: (entityId, content) => v4Request('POST', `/entities/${encodeURIComponent(entityId)}/activity_updates`, { content }),
  },
};
