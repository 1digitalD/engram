/**
 * Engram API Client
 * All HTTP calls to the Engram Flask backend.
 * BASE is empty so all calls are relative — works on any host/port.
 */

const PREFIX = '/api/v1';

async function apiRequest(method, path, body = null, params = {}) {
  const url = new URL(path, window.location.origin);
  url.pathname = PREFIX + path;
  if (Object.keys(params).length) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url.toString(), opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Notes ────────────────────────────────────
export const notesAPI = {
  list:    (params = {})  => apiRequest('GET',    '/notes', null, params),
  get:     (id)           => apiRequest('GET',    `/notes/${id}`),
  create:  (data)         => apiRequest('POST',   '/notes', data),
  update:  (id, data)     => apiRequest('PATCH',  `/notes/${id}`, data),
  delete:  (id)           => apiRequest('DELETE', `/notes/${id}`),
  search:  (q, mode)      => apiRequest('GET',    '/notes/search', null, { q, mode }),
};

// ── Ingest (smart multi-modal capture) ───────
export const ingestAPI = {
  capture: (data) => apiRequest('POST', '/ingest', data),
};

// ── Projects ─────────────────────────────────
export const projectsAPI = {
  list:   (params = {}) => apiRequest('GET',    '/projects', null, params),
  get:    (id)          => apiRequest('GET',    `/projects/${id}`),
  create: (d)           => apiRequest('POST',   '/projects', d),
  update: (id, d)       => apiRequest('PATCH',  `/projects/${id}`, d),
  delete: (id)          => apiRequest('DELETE', `/projects/${id}`),
};

// ── Resources ────────────────────────────────
export const resourcesAPI = {
  list:   (params = {}) => apiRequest('GET',    '/resources', null, params),
  get:    (id)          => apiRequest('GET',    `/resources/${id}`),
  create: (d)           => apiRequest('POST',   '/resources', d),
  update: (id, d)       => apiRequest('PATCH',  `/resources/${id}`, d),
  delete: (id)          => apiRequest('DELETE', `/resources/${id}`),
};

// ── Areas ────────────────────────────────────
export const areasAPI = {
  list:   (params = {}) => apiRequest('GET',    '/areas', null, params),
  get:    (id)          => apiRequest('GET',    `/areas/${id}`),
  create: (d)           => apiRequest('POST',   '/areas', d),
  update: (id, d)       => apiRequest('PATCH',  `/areas/${id}`, d),
  delete: (id)          => apiRequest('DELETE', `/areas/${id}`),
};

// ── People ───────────────────────────────────
export const peopleAPI = {
  list:   ()     => apiRequest('GET',    '/people'),
  get:    (id)   => apiRequest('GET',    `/people/${id}`),
  create: (d)    => apiRequest('POST',   '/people', d),
  update: (id, d)=> apiRequest('PATCH',  `/people/${id}`, d),
  delete: (id)   => apiRequest('DELETE', `/people/${id}`),
};

// ── Tasks ────────────────────────────────────
export const tasksAPI = {
  list:   (params = {}) => apiRequest('GET',    '/tasks', null, params),
  get:    (id)          => apiRequest('GET',    `/tasks/${id}`),
  create: (d)           => apiRequest('POST',   '/tasks', d),
  update: (id, d)       => apiRequest('PATCH',  `/tasks/${id}`, d),
  delete: (id)          => apiRequest('DELETE', `/tasks/${id}`),
};

// ── Tags ─────────────────────────────────────
export const tagsAPI = {
  list:   ()     => apiRequest('GET',    '/tags'),
  get:    (id)   => apiRequest('GET',    `/tags/${id}`),
  create: (d)    => apiRequest('POST',   '/tags', d),
  update: (id,d) => apiRequest('PATCH',  `/tags/${id}`, d),
  delete: (id)   => apiRequest('DELETE', `/tags/${id}`),
};

// ── Daily notes ──────────────────────────────
export const dailyAPI = {
  get: (date) => apiRequest('GET', '/daily', null, { date }),
  append: (body) => apiRequest('POST', '/daily/append', body),
};

// ── Links (knowledge graph) ──────────────────
export const linksAPI = {
  forNote:   (id)  => apiRequest('GET',    `/notes/${id}/links`),
  create:    (d)   => apiRequest('POST',   '/links', d),
  delete:    (id)  => apiRequest('DELETE', `/links/${id}`),
  related:   (id, limit) => apiRequest('GET', `/notes/${id}/related`, null, { limit }),
};

// ── Link proposals (AI-suggested, review → link) ──
export const proposalsAPI = {
  list:    (params = {}) => apiRequest('GET', '/proposals', null, params),
  generate: (data = {})  => apiRequest('POST', '/proposals/generate', data),
  accept:   (id)        => apiRequest('POST', `/proposals/${id}/accept`),
  dismiss:  (id)        => apiRequest('POST', `/proposals/${id}/dismiss`),
};

// ── Review aggregates ───────────────────────
export const reviewAPI = {
  weeklyDigest: (params = {}) => apiRequest('GET', '/review/weekly-digest', null, params),
};

// ── Knowledge health metrics ─────────────────
export const metricsAPI = {
  health: () => apiRequest('GET', '/metrics/health'),
  healthHistory: (params = {}) => apiRequest('GET', '/metrics/health/history', null, params),
};

// ── Summaries (progressive rollup + review) ─
export const summariesAPI = {
  list: (params = {}) => apiRequest('GET', '/summaries', null, params),
  get:  (id) => apiRequest('GET', `/summaries/${id}`),
};

// ── Batch ────────────────────────────────────
export const batchAPI = {
  execute: (operations, atomic = true) =>
    apiRequest('POST', '/batch', { operations, atomic }),
};

// ── Health ───────────────────────────────────
export const healthAPI = {
  check: () => apiRequest('GET', '/health'.replace('/api/v1', '')),
};
