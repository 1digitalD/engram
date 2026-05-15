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
  const contentType = (res.headers.get('content-type') || '').toLowerCase();
  const isJson = contentType.includes('application/json');

  if (!res.ok) {
    const errBody = isJson
      ? await res.json().catch(() => ({ error: res.statusText }))
      : { error: `${res.status} ${res.statusText}` };
    const msg = errBody.error || errBody.message || `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.body = errBody;
    throw err;
  }
  if (res.status === 204) return {};
  if (!isJson) {
    const sample = await res.text().catch(() => '');
    throw new Error(
      `Unexpected non-JSON response from ${method} ${url.pathname}: ${sample.slice(0, 80)}`
    );
  }
  return res.json();
}

// ── Notes ────────────────────────────────────
export const notesAPI = {
  list:    (params = {})  => apiRequest('GET',    '/notes', null, params),
  get:     (id)           => apiRequest('GET',    `/notes/${id}`),
  create:  (data)         => apiRequest('POST',   '/notes', data),
  update:  (id, data)     => apiRequest('PATCH',  `/notes/${id}`, data),
  delete:  (id, cascade)  => apiRequest('DELETE', `/notes/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
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
  delete: (id, cascade) => apiRequest('DELETE', `/projects/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
};

// ── Resources ────────────────────────────────
export const resourcesAPI = {
  list:   (params = {}) => apiRequest('GET',    '/resources', null, params),
  get:    (id)          => apiRequest('GET',    `/resources/${id}`),
  create: (d)           => apiRequest('POST',   '/resources', d),
  update: (id, d)       => apiRequest('PATCH',  `/resources/${id}`, d),
  delete: (id, cascade) => apiRequest('DELETE', `/resources/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
};

// ── Areas ────────────────────────────────────
export const areasAPI = {
  list:   (params = {}) => apiRequest('GET',    '/areas', null, params),
  get:    (id)          => apiRequest('GET',    `/areas/${id}`),
  create: (d)           => apiRequest('POST',   '/areas', d),
  update: (id, d)       => apiRequest('PATCH',  `/areas/${id}`, d),
  delete: (id, cascade) => apiRequest('DELETE', `/areas/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
};

// ── People ───────────────────────────────────
export const peopleAPI = {
  list:   ()          => apiRequest('GET',    '/people'),
  get:    (id)        => apiRequest('GET',    `/people/${id}`),
  create: (d)         => apiRequest('POST',   '/people', d),
  update: (id, d)     => apiRequest('PATCH',  `/people/${id}`, d),
  delete: (id, cascade) => apiRequest('DELETE', `/people/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
};

// ── Tasks ────────────────────────────────────
export const tasksAPI = {
  list:   (params = {}) => apiRequest('GET',    '/tasks', null, params),
  get:    (id)          => apiRequest('GET',    `/tasks/${id}`),
  create: (d)           => apiRequest('POST',   '/tasks', d),
  update: (id, d)       => apiRequest('PATCH',  `/tasks/${id}`, d),
  delete: (id, cascade) => apiRequest('DELETE', `/tasks/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
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
  list:     (params = {}) => apiRequest('GET',    '/links', null, params),
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

// ── Universal entity API ────────────────────
export const entitiesAPI = {
  get:     (id)       => apiRequest('GET',    `/entities/${id}`),
  update:  (id, data) => apiRequest('PATCH',  `/entities/${id}`, data),
  delete:  (id, cascade) => apiRequest('DELETE', `/entities/${id}`, null, { cascade: cascade ? 'true' : 'false' }),
  search:  (q)        => apiRequest('GET',    '/search', null, { q }),
  links:   (id)       => apiRequest('GET',    `/entities/${id}/links`),
  events:  (id)       => apiRequest('GET',    `/entities/${id}/events`),
};

// ── Capture API ────────────────────────────
export const captureAPI = {
  capture: async (data) => {
    // Prefer canonical v1 endpoint, fallback to current v2 route in mixed deployments.
    try {
      return await apiRequest('POST', '/capture', data);
    } catch (e) {
      const res = await fetch('/api/v2/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || err.message || `HTTP ${res.status}`);
      }
      return res.json();
    }
  },
};

// ── Suggestions API ────────────────────────
export const suggestionsAPI = {
  list:    async (params = {}) => {
    const qs = new URLSearchParams();
    if (params.entityId) qs.set('entity_id', params.entityId);
    if (params.status) qs.set('status', params.status);
    if (params.limit) qs.set('limit', params.limit);
    const q = qs.toString();
    const res = await fetch(`/api/v2/suggestions${q ? '?' + q : ''}`);
    if (!res.ok) throw new Error(`Failed to load suggestions: ${res.status}`);
    return res.json();
  },
  accept: async (id) => {
    const res = await fetch(`/api/v2/suggestions/${id}/accept`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to accept suggestion: ${res.status}`);
    return res.json();
  },
  dismiss: async (id) => {
    const res = await fetch(`/api/v2/suggestions/${id}/dismiss`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to dismiss suggestion: ${res.status}`);
    return res.json();
  },
  edit: async (id, payload) => {
    const res = await fetch(`/api/v2/suggestions/${id}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || err.message || `Failed to edit suggestion: ${res.status}`);
    }
    return res.json();
  },
};

export const changeBatchesAPI = {
  list: async (params = {}) => {
    const qs = new URLSearchParams();
    if (params.limit) qs.set('limit', params.limit);
    if (params.sourceNoteId) qs.set('source_note_id', params.sourceNoteId);
    const q = qs.toString();
    const res = await fetch(`/api/v2/change-batches${q ? '?' + q : ''}`);
    if (!res.ok) throw new Error(`Failed to load change batches: ${res.status}`);
    return res.json();
  },
  undo: async (id) => {
    const res = await fetch(`/api/v2/change-batches/${id}/undo`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || err.message || `Failed to undo batch: ${res.status}`);
    }
    return res.json();
  },
};

// ── Relationships API ─────────────────────
export const relationshipsAPI = {
  list:        (entityId)     => fetch(`/api/v2/links/${encodeURIComponent(entityId)}`).then(r => r.json()),
  create:      (data)         => apiRequest('POST',   '/links', data),
  delete:      (linkId)       => apiRequest('DELETE', `/links/${linkId}`),
  linkTypes:   (srcType, dstType) => linkTypesAPI.forPair(srcType, dstType),
  deletePreview: (entityId)   => apiRequest('GET',    `/entities/${entityId}/delete-preview`),
};

// ── Connections (universal entity links) ──────
export const connectionsAPI = {
  forEntity: (id) => apiRequest('GET', `/entities/${id}/links`),
};

// ── V2 Links API ───────────────────────────
export const linkTypesAPI = {
  forPair: async (srcType, dstType) => {
    const res = await fetch(`/api/v2/link-types/${srcType}/${dstType}`);
    if (!res.ok) throw new Error(`Failed to fetch link types: ${res.status}`);
    return res.json();
  },
};


// ── Health ───────────────────────────────────
export const healthAPI = {
  check: () => apiRequest('GET', '/health'.replace('/api/v1', '')),
};

// ── Delete Preview ───────────────────────────
export const deletePreviewAPI = {
  get: async (id) => {
    const res = await fetch(`/api/v2/entities/${encodeURIComponent(id)}/delete-preview`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(err.error || err.message || `HTTP ${res.status}`);
    }
    return res.json();
  },
};
