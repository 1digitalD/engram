/**
 * Engram Zustand Store
 * Single source of truth for all app state
 */

import { create } from 'zustand';
import { notesAPI, projectsAPI, areasAPI, peopleAPI, tasksAPI, ingestAPI, tagsAPI, resourcesAPI, deletePreviewAPI } from '../api/engram';

const AI_STATUS_POLL_INTERVAL = 2000;
const AI_STATUS_POLL_MAX = 30;

function normalizeEntity(entity) {
  if (!entity || typeof entity !== 'object') return entity;
  const { name, ai_meta, ...rest } = entity;
  return {
    ...rest,
    title: name || rest.title,
    ...(ai_meta !== undefined && { _ai_meta: ai_meta }),
  };
}

/** Normalize an array of entities. */
function normalizeList(list) {
  return Array.isArray(list) ? list.map(normalizeEntity) : [];
}

const useStore = create((set, get) => ({
  // ── Data ──────────────────────────────────
  notes:    [],
  projects: [],
  areas:    [],
  people:   [],
  tasks:    [],
  tags:     [],
  resources: [],

  // ── UI State ───────────────────────────────
  loading:     false,
  toasts:      [],
  searchQuery: '',
  sidebarOpen: true,
  captureOpen: false,

  // ── Selected / Active ─────────────────────
  activeNote:    null,
  activeProject: null,
  activeArea:    null,
  activePerson:  null,

  // ── Actions ────────────────────────────────

  // Toast
  addToast: (toast) => {
    const id = Date.now().toString(36);
    set(s => ({ toasts: [...s.toasts, { id, ...toast }] }));
    setTimeout(() => get().removeToast(id), toast.type === 'error' ? 5000 : 3000);
  },
  removeToast: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),

  // Sidebar
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
  openCapture: () => set({ captureOpen: true }),
  closeCapture: () => set({ captureOpen: false }),

  // ── Data Loaders ───────────────────────────

  loadAll: async () => {
    set({ loading: true });
    try {
      const [notes, projects, areas, people, tasks, tags, resources] = await Promise.all([
        notesAPI.list(),
        projectsAPI.list(),
        areasAPI.list(),
        peopleAPI.list(),
        tasksAPI.list(),
        tagsAPI.list(),
        resourcesAPI.list(),
      ]);
      set({
        notes:    normalizeList(notes.data),
        projects: normalizeList(projects.data),
        areas:    normalizeList(areas.data),
        people:   normalizeList(people.data),
        tasks:    normalizeList(tasks.data),
        tags:     tags.data || [],
        resources: normalizeList(resources.data),
        loading:  false,
      });
    } catch (e) {
      set({ loading: false });
      get().addToast({ type: 'error', message: `Failed to load: ${e.message}` });
    }
  },

  // ── Notes ─────────────────────────────────

  createNote: async (data) => {
    try {
      const { raw_text, bucket, project_id, project_ids, area_id, person_id } = data;

      const noteProjectIdsEqual = (a, b) => {
        const sa = new Set(a || []);
        const sb = new Set(b || []);
        if (sa.size !== sb.size) return false;
        for (const id of sa) if (!sb.has(id)) return false;
        return true;
      };

      // Run through the full AI ingestion pipeline (classification, task
      // extraction, entity resolution, embeddings) — not a plain DB insert.
      // Note: ingest returns { note, tasks, project, area, people, ... }
      // while the REST notes API returns { data: note }.
      const res = await ingestAPI.capture({ content: raw_text, source: 'ui' });
      let note = res.note || res.data;

      const existingProjectIds = note.project_ids?.length
        ? note.project_ids
        : (note.project_id ? [note.project_id] : []);

      // Apply any user-explicit overrides set in the editor. The AI may have
      // chosen different values — user intent wins.
      const overrides = {};
      if (bucket && bucket !== note.bucket)           overrides.bucket     = bucket;
      if (project_ids !== undefined) {
        if (!noteProjectIdsEqual(existingProjectIds, project_ids)) {
          overrides.project_ids = project_ids;
        }
      } else if (project_id && project_id !== note.project_id) {
        overrides.project_id = project_id;
      }
      if (area_id    && area_id    !== note.area_id)    overrides.area_id    = area_id;
      if (person_id  && person_id  !== note.person_id)  overrides.person_id  = person_id;

      if (Object.keys(overrides).length > 0) {
        const patched = await notesAPI.update(note.id, overrides);
        note = normalizeEntity(patched.data);
        res.note = note;
      } else {
        note = normalizeEntity(note);
      }

      // Add note to state
      set(s => ({ notes: [note, ...s.notes] }));

      // Merge any auto-created tasks
      if (res.tasks?.length) {
        set(s => ({ tasks: [...normalizeList(res.tasks), ...s.tasks] }));
      }

      // Merge auto-created/matched project if new
      if (res.project) {
        const normalizedProject = normalizeEntity(res.project);
        set(s => ({
          projects: s.projects.find(p => p.id === normalizedProject.id)
            ? s.projects
            : [normalizedProject, ...s.projects],
        }));
      }

      // Merge auto-created/matched area if new
      if (res.area) {
        const normalizedArea = normalizeEntity(res.area);
        set(s => ({
          areas: s.areas.find(a => a.id === normalizedArea.id)
            ? s.areas
            : [normalizedArea, ...s.areas],
        }));
      }

      // Merge auto-resolved people
      if (res.people?.length) {
        set(s => {
          const existingIds = new Set(s.people.map(p => p.id));
          const newPeople = normalizeList(res.people).filter(p => !existingIds.has(p.id));
          return newPeople.length ? { people: [...newPeople, ...s.people] } : {};
        });
      }

      // Build a descriptive toast
      const parts = ['Note captured'];
      if (res.extraction?.bucket && res.extraction.bucket !== 'INBOX') {
        parts.push(`→ ${res.extraction.bucket}`);
      }
      if (res.tasks?.length) parts.push(`${res.tasks.length} task${res.tasks.length > 1 ? 's' : ''} created`);
      if (res.project) parts.push(`project: ${res.project.title}`);
      if (!res.confident && res.extraction?.confidence) parts.push('⚠ low confidence, check inbox');

      get().addToast({ type: 'success', message: parts.join(' · ') });
      return res;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateNote: async (id, data, opts = {}) => {
    const { silent } = opts;
    try {
      const res = await notesAPI.update(id, data);
      const updated = normalizeEntity(res.data);
      set(s => ({
        notes: s.notes.map(n => n.id === id ? updated : n),
        activeNote: s.activeNote?.id === id ? updated : s.activeNote,
      }));
      if (!silent) get().addToast({ type: 'success', message: 'Note updated' });
      return updated;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteNote: async (id, cascadeIds) => {
    try {
      const cascade = cascadeIds && cascadeIds.length > 0;
      await notesAPI.delete(id, cascade);
      const idsToDelete = new Set([id, ...(cascadeIds || [])]);
      set(s => ({
        notes: s.notes.filter(n => !idsToDelete.has(n.id)),
        activeNote: s.activeNote?.id === id ? null : s.activeNote,
      }));
      get().addToast({ type: 'success', message: 'Note deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  getDeletePreview: async (id) => {
    try {
      const res = await deletePreviewAPI.get(id);
      return res;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  setActiveNote: (note) => set({ activeNote: note }),

  /** Merge a single note from the server (e.g. daily note fetch) into `notes`. */
  upsertNote: (note) => {
    if (!note?.id) return;
    const normalized = normalizeEntity(note);
    set(s => {
      const idx = s.notes.findIndex(n => n.id === normalized.id);
      if (idx === -1) return { notes: [normalized, ...s.notes] };
      const next = [...s.notes];
      next[idx] = normalized;
      return { notes: next };
    });
  },

  // ── AI Status Polling ─────────────────────

  _aiPollTimers: {},

  startAiStatusPoll: (entityId, entityType) => {
    const { _aiPollTimers } = get();
    if (_aiPollTimers[entityId]) return;

    let attempts = 0;
    const timer = setInterval(async () => {
      attempts += 1;
      if (attempts > AI_STATUS_POLL_MAX) {
        clearInterval(timer);
        set(s => {
          const next = { ...s._aiPollTimers };
          delete next[entityId];
          return { _aiPollTimers: next };
        });
        return;
      }

      try {
        let res;
        if (entityType === 'note') res = await notesAPI.get(entityId);
        else if (entityType === 'project') res = await projectsAPI.get(entityId);
        else if (entityType === 'area') res = await areasAPI.get(entityId);
        else if (entityType === 'person') res = await peopleAPI.get(entityId);
        else if (entityType === 'task') res = await tasksAPI.get(entityId);
        else if (entityType === 'resource') res = await resourcesAPI.get(entityId);
        else return;

        const updated = normalizeEntity(res.data);
        if (updated.ai_status !== 'processing') {
          clearInterval(timer);
          set(s => {
            const next = { ...s._aiPollTimers };
            delete next[entityId];
            return { _aiPollTimers: next };
          });
          if (entityType === 'note') {
            set(s => ({
              notes: s.notes.map(n => n.id === entityId ? updated : n),
              activeNote: s.activeNote?.id === entityId ? updated : s.activeNote,
            }));
          } else if (entityType === 'project') {
            set(s => ({
              projects: s.projects.map(p => p.id === entityId ? updated : p),
              activeProject: s.activeProject?.id === entityId ? updated : s.activeProject,
            }));
          } else if (entityType === 'area') {
            set(s => ({
              areas: s.areas.map(a => a.id === entityId ? updated : a),
              activeArea: s.activeArea?.id === entityId ? updated : s.activeArea,
            }));
          } else if (entityType === 'person') {
            set(s => ({
              people: s.people.map(p => p.id === entityId ? updated : p),
              activePerson: s.activePerson?.id === entityId ? updated : s.activePerson,
            }));
          } else if (entityType === 'task') {
            set(s => ({
              tasks: s.tasks.map(t => t.id === entityId ? updated : t),
            }));
          } else if (entityType === 'resource') {
            set(s => ({
              resources: s.resources.map(r => r.id === entityId ? updated : r),
            }));
          }
        } else {
          set(s => {
            if (entityType === 'note') {
              return { notes: s.notes.map(n => n.id === entityId ? { ...n, ai_status: 'processing' } : n) };
            } else if (entityType === 'project') {
              return { projects: s.projects.map(p => p.id === entityId ? { ...p, ai_status: 'processing' } : p) };
            } else if (entityType === 'area') {
              return { areas: s.areas.map(a => a.id === entityId ? { ...a, ai_status: 'processing' } : a) };
            } else if (entityType === 'person') {
              return { people: s.people.map(p => p.id === entityId ? { ...p, ai_status: 'processing' } : p) };
            } else if (entityType === 'task') {
              return { tasks: s.tasks.map(t => t.id === entityId ? { ...t, ai_status: 'processing' } : t) };
            } else if (entityType === 'resource') {
              return { resources: s.resources.map(r => r.id === entityId ? { ...r, ai_status: 'processing' } : r) };
            }
            return {};
          });
        }
      } catch {
        if (attempts > AI_STATUS_POLL_MAX) {
          clearInterval(timer);
          set(s => {
            const next = { ...s._aiPollTimers };
            delete next[entityId];
            return { _aiPollTimers: next };
          });
        }
      }
    }, AI_STATUS_POLL_INTERVAL);

    set(s => ({ _aiPollTimers: { ...s._aiPollTimers, [entityId]: timer } }));
  },

  stopAiStatusPoll: (entityId) => {
    const { _aiPollTimers } = get();
    if (_aiPollTimers[entityId]) {
      clearInterval(_aiPollTimers[entityId]);
      set(s => {
        const next = { ...s._aiPollTimers };
        delete next[entityId];
        return { _aiPollTimers: next };
      });
    }
  },

  // ── Projects ───────────────────────────────

  createProject: async (data) => {
    try {
      const res = await projectsAPI.create(data);
      const project = normalizeEntity(res.data);
      set(s => ({ projects: [project, ...s.projects] }));
      get().addToast({ type: 'success', message: `Project "${project.title}" created` });
      return project;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateProject: async (id, data) => {
    try {
      const res = await projectsAPI.update(id, data);
      const updated = normalizeEntity(res.data);
      set(s => ({
        projects: s.projects.map(p => p.id === id ? updated : p),
        activeProject: s.activeProject?.id === id ? updated : s.activeProject,
      }));
      return { project: updated, rollup: res.rollup };
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteProject: async (id, cascadeIds) => {
    try {
      const cascade = cascadeIds && cascadeIds.length > 0;
      await projectsAPI.delete(id, cascade);
      const idsToDelete = new Set([id, ...(cascadeIds || [])]);
      set(s => ({
        projects: s.projects.filter(p => !idsToDelete.has(p.id)),
      }));
      get().addToast({ type: 'success', message: 'Project deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  setActiveProject: (project) => set({ activeProject: project }),

  // ── Areas ──────────────────────────────────

  createArea: async (data) => {
    try {
      const res = await areasAPI.create(data);
      const area = normalizeEntity(res.data);
      set(s => ({ areas: [area, ...s.areas] }));
      get().addToast({ type: 'success', message: `Area "${area.title}" created` });
      return area;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateArea: async (id, data) => {
    try {
      const res = await areasAPI.update(id, data);
      const updated = normalizeEntity(res.data);
      set(s => ({
        areas: s.areas.map(a => a.id === id ? updated : a),
        activeArea: s.activeArea?.id === id ? updated : s.activeArea,
      }));
      // Return detached_projects count if archiving
      return { ...updated, detached_projects: res.detached_projects };
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteArea: async (id, cascadeIds) => {
    try {
      const cascade = cascadeIds && cascadeIds.length > 0;
      await areasAPI.delete(id, cascade);
      const idsToDelete = new Set([id, ...(cascadeIds || [])]);
      set(s => ({
        areas: s.areas.filter(a => !idsToDelete.has(a.id)),
        activeArea: s.activeArea?.id === id ? null : s.activeArea,
      }));
      get().addToast({ type: 'success', message: 'Area deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  setActiveArea: (area) => set({ activeArea: area }),

  // ── Resources ──────────────────────────────

  updateResource: async (id, data) => {
    try {
      const res = await resourcesAPI.update(id, data);
      const updated = normalizeEntity(res.data);
      set(s => ({
        resources: s.resources.map(r => r.id === id ? updated : r),
      }));
      get().addToast({ type: 'success', message: 'Resource saved' });
      return updated;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteResource: async (id, cascadeIds) => {
    try {
      const cascade = cascadeIds && cascadeIds.length > 0;
      await resourcesAPI.delete(id, cascade);
      const idsToDelete = new Set([id, ...(cascadeIds || [])]);
      set(s => ({ resources: s.resources.filter(r => !idsToDelete.has(r.id)) }));
      get().addToast({ type: 'success', message: 'Resource deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  /** Replace or merge a resource row (e.g. after GET detail). */
  upsertResource: (resource) => {
    if (!resource?.id) return;
    const normalized = normalizeEntity(resource);
    set(s => {
      const idx = s.resources.findIndex(r => r.id === normalized.id);
      if (idx === -1) return { resources: [normalized, ...s.resources] };
      const next = [...s.resources];
      next[idx] = normalized;
      return { resources: next };
    });
  },

  // ── People ─────────────────────────────────

  createPerson: async (data) => {
    try {
      const res = await peopleAPI.create(data);
      const person = normalizeEntity(res.data);
      set(s => ({ people: [person, ...s.people] }));
      get().addToast({ type: 'success', message: `${person.title} added` });
      return person;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updatePerson: async (id, data) => {
    try {
      const res = await peopleAPI.update(id, data);
      const updated = normalizeEntity(res.data);
      set(s => ({
        people: s.people.map(p => p.id === id ? updated : p),
        activePerson: s.activePerson?.id === id ? updated : s.activePerson,
      }));
      return updated;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deletePerson: async (id, cascadeIds) => {
    try {
      const cascade = cascadeIds && cascadeIds.length > 0;
      await peopleAPI.delete(id, cascade);
      const idsToDelete = new Set([id, ...(cascadeIds || [])]);
      set(s => ({
        people: s.people.filter(p => !idsToDelete.has(p.id)),
        activePerson: s.activePerson?.id === id ? null : s.activePerson,
      }));
      get().addToast({ type: 'success', message: 'Person deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  setActivePerson: (person) => set({ activePerson: person }),

  // ── Tasks ──────────────────────────────────

  createTask: async (data) => {
    try {
      const payload = {
        ...data,
        due_date: data.due_date ?? null,
        area_id: data.area_id ?? null,
        note_id: data.note_id ?? null,
      };
      const res = await tasksAPI.create(payload);
      const task = normalizeEntity(res.data);
      set(s => ({ tasks: [task, ...s.tasks] }));
      get().addToast({ type: 'success', message: 'Task added' });
      return task;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateTask: async (id, data) => {
    try {
      const payload = {
        ...data,
        ...(Object.prototype.hasOwnProperty.call(data, 'due_date') ? { due_date: data.due_date ?? null } : {}),
        ...(Object.prototype.hasOwnProperty.call(data, 'area_id') ? { area_id: data.area_id ?? null } : {}),
        ...(Object.prototype.hasOwnProperty.call(data, 'note_id') ? { note_id: data.note_id ?? null } : {}),
      };
      const res = await tasksAPI.update(id, payload);
      const updated = normalizeEntity(res.data);
      set(s => ({ tasks: s.tasks.map(t => t.id === id ? updated : t) }));
      return updated;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteTask: async (id, cascadeIds) => {
    try {
      const cascade = cascadeIds && cascadeIds.length > 0;
      await tasksAPI.delete(id, cascade);
      const idsToDelete = new Set([id, ...(cascadeIds || [])]);
      set(s => ({ tasks: s.tasks.filter(t => !idsToDelete.has(t.id)) }));
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  // ── Search ─────────────────────────────────

  setSearchQuery: (q) => set({ searchQuery: q }),

  searchNotes: async (q) => {
    if (!q.trim()) return [];
    try {
      const res = await notesAPI.search(q);
      return res.data || [];
    } catch {
      return [];
    }
  },
}));

export default useStore;
