/**
 * Engram API Client
 * All HTTP calls to the Engram Flask backend
 */

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5001';
const PREFIX = `${BASE}/api/v1`;

async function request(method, path, body = null, params = {}) {
  const url = new URL(`${PREFIX}${path}`);
  if (Object.keys(params).length) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
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
  list:    (params = {})  => request('GET',  '/notes', null, params),
  get:     (id)           => request('GET',  `/notes/${id}`),
  create:  (data)         => request('POST', '/notes', data),
  update:  (id, data)     => request('PUT',  `/notes/${id}`, data),
  delete:  (id)           => request('DELETE', `/notes/${id}`),
  search:  (q)            => request('GET',  '/notes/search', null, { q }),
};

// ── Projects ─────────────────────────────────
export const projectsAPI = {
  list:   ()  => request('GET',    '/projects'),
  get:    (id) => request('GET',    `/projects/${id}`),
  create: (d)  => request('POST',   '/projects', d),
  update: (id, d) => request('PUT', `/projects/${id}`, d),
  delete: (id) => request('DELETE', `/projects/${id}`),
};

// ── Areas ────────────────────────────────────
export const areasAPI = {
  list:   ()  => request('GET',    '/areas'),
  get:    (id) => request('GET',    `/areas/${id}`),
  create: (d)  => request('POST',   '/areas', d),
  update: (id, d) => request('PUT', `/areas/${id}`, d),
  delete: (id) => request('DELETE', `/areas/${id}`),
};

// ── People ───────────────────────────────────
export const peopleAPI = {
  list:   ()  => request('GET',    '/people'),
  get:    (id) => request('GET',    `/people/${id}`),
  create: (d)  => request('POST',   '/people', d),
  update: (id, d) => request('PUT', `/people/${id}`, d),
  delete: (id) => request('DELETE', `/people/${id}`),
};

// ── Tasks ────────────────────────────────────
export const tasksAPI = {
  list:   ()  => request('GET',    '/tasks'),
  get:    (id) => request('GET',    `/tasks/${id}`),
  create: (d)  => request('POST',   '/tasks', d),
  update: (id, d) => request('PUT', `/tasks/${id}`, d),
  delete: (id) => request('DELETE', `/tasks/${id}`),
};

// ── Tags ─────────────────────────────────────
export const tagsAPI = {
  list: () => request('GET', '/tags'),
};
