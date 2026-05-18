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

const listEntities = (type, params = {}) => v4Request('GET', '/entities', null, { ...params, type });
const createEntity = (type, data) => v4Request('POST', '/entities', { ...data, type });
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
    accept: (id) => v4Request('POST', `/suggestions/${encodeURIComponent(id)}/accept`),
    dismiss: (id) => v4Request('POST', `/suggestions/${encodeURIComponent(id)}/dismiss`),
  },
  search: (params = {}) => v4Request('GET', '/search', null, params),
  today: () => v4Request('GET', '/today'),
  recent: (params = {}) => v4Request('GET', '/recent', null, params),
};

export const notesAPI = {
  list: (params = {}) => listEntities('note', params),
  get: getEntity,
  detail: getEntityDetail,
  create: (data) => createEntity('note', data),
  update: updateEntity,
  delete: deleteEntity,
  search: (q, mode = 'hybrid') => v4API.search({ q, mode, type: 'note' }),
};

export const tasksAPI = {
  list: (params = {}) => listEntities('task', params),
  get: getEntity,
  detail: getEntityDetail,
  create: (data) => createEntity('task', data),
  update: updateEntity,
  delete: deleteEntity,
};

export const projectsAPI = {
  list: (params = {}) => listEntities('project', params),
  get: getEntity,
  detail: getEntityDetail,
  create: (data) => createEntity('project', data),
  update: updateEntity,
  delete: deleteEntity,
};

export const areasAPI = {
  list: (params = {}) => listEntities('area', params),
  get: getEntity,
  detail: getEntityDetail,
  create: (data) => createEntity('area', data),
  update: updateEntity,
  delete: deleteEntity,
};

export const peopleAPI = {
  list: (params = {}) => listEntities('person', params),
  get: getEntity,
  detail: getEntityDetail,
  create: (data) => createEntity('person', data),
  update: updateEntity,
  delete: deleteEntity,
};

export const resourcesAPI = {
  list: (params = {}) => listEntities('resource', params),
  get: getEntity,
  detail: getEntityDetail,
  create: (data) => createEntity('resource', data),
  update: updateEntity,
  delete: deleteEntity,
};

export const captureAPI = {
  capture: v4API.capture,
};

export const suggestionsAPI = v4API.suggestions;
export const relationshipsAPI = v4API.relationships;
export const entitiesAPI = v4API.entities;
export const healthAPI = { check: v4API.health };

export const tagsAPI = {
  list: async () => ({ data: [] }),
  create: async () => ({ data: null }),
  update: async () => ({ data: null }),
  delete: async () => ({ data: null }),
};

export const ingestAPI = { capture: v4API.capture };
export const connectionsAPI = { forEntity: v4API.relationships.list };
export const linkTypesAPI = { forPair: async () => ({ data: [] }) };
export const deletePreviewAPI = { get: async (id) => ({ id, cascade: [] }) };
export const proposalsAPI = { list: async () => ({ data: [] }) };
export const reviewAPI = { weeklyDigest: async () => ({ data: null }) };
export const metricsAPI = { health: async () => ({ data: null }) };
export const summariesAPI = { list: async () => ({ data: [] }) };
export const batchAPI = { execute: async () => ({ data: [] }) };
export const changeBatchesAPI = { list: async () => ({ data: [] }) };
