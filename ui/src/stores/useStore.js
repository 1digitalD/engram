/**
 * Engram Zustand Store
 * Single source of truth for all app state
 */

import { create } from 'zustand';
import { notesAPI, projectsAPI, areasAPI, peopleAPI, tasksAPI, ingestAPI, tagsAPI, resourcesAPI } from '../api/engram';

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
        notes:    notes.data || [],
        projects: projects.data || [],
        areas:    areas.data || [],
        people:   people.data || [],
        tasks:    tasks.data || [],
        tags:     tags.data || [],
        resources: resources.data || [],
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
        note = patched.data;
        res.note = note; // keep ref consistent
      }

      // Add note to state
      set(s => ({ notes: [note, ...s.notes] }));

      // Merge any auto-created tasks
      if (res.tasks?.length) {
        set(s => ({ tasks: [...res.tasks, ...s.tasks] }));
      }

      // Merge auto-created/matched project if new
      if (res.project) {
        set(s => ({
          projects: s.projects.find(p => p.id === res.project.id)
            ? s.projects
            : [res.project, ...s.projects],
        }));
      }

      // Merge auto-created/matched area if new
      if (res.area) {
        set(s => ({
          areas: s.areas.find(a => a.id === res.area.id)
            ? s.areas
            : [res.area, ...s.areas],
        }));
      }

      // Merge auto-resolved people
      if (res.people?.length) {
        set(s => {
          const existingIds = new Set(s.people.map(p => p.id));
          const newPeople = res.people.filter(p => !existingIds.has(p.id));
          return newPeople.length ? { people: [...newPeople, ...s.people] } : {};
        });
      }

      // Build a descriptive toast
      const parts = ['Note captured'];
      if (res.extraction?.bucket && res.extraction.bucket !== 'INBOX') {
        parts.push(`→ ${res.extraction.bucket}`);
      }
      if (res.tasks?.length) parts.push(`${res.tasks.length} task${res.tasks.length > 1 ? 's' : ''} created`);
      if (res.project) parts.push(`project: ${res.project.name}`);
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
      const updated = res.data;
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

  deleteNote: async (id) => {
    try {
      await notesAPI.delete(id);
      set(s => ({
        notes: s.notes.filter(n => n.id !== id),
        activeNote: s.activeNote?.id === id ? null : s.activeNote,
      }));
      get().addToast({ type: 'success', message: 'Note deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  setActiveNote: (note) => set({ activeNote: note }),

  /** Merge a single note from the server (e.g. daily note fetch) into `notes`. */
  upsertNote: (note) => {
    if (!note?.id) return;
    set(s => {
      const idx = s.notes.findIndex(n => n.id === note.id);
      if (idx === -1) return { notes: [note, ...s.notes] };
      const next = [...s.notes];
      next[idx] = note;
      return { notes: next };
    });
  },

  // ── Projects ───────────────────────────────

  createProject: async (data) => {
    try {
      const res = await projectsAPI.create(data);
      const project = res.data;
      set(s => ({ projects: [project, ...s.projects] }));
      get().addToast({ type: 'success', message: `Project "${project.name}" created` });
      return project;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateProject: async (id, data) => {
    try {
      const res = await projectsAPI.update(id, data);
      const updated = res.data;
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

  deleteProject: async (id) => {
    try {
      await projectsAPI.delete(id);
      set(s => ({ projects: s.projects.filter(p => p.id !== id) }));
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
      const area = res.data;
      set(s => ({ areas: [area, ...s.areas] }));
      get().addToast({ type: 'success', message: `Area "${area.name}" created` });
      return area;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateArea: async (id, data) => {
    try {
      const res = await areasAPI.update(id, data);
      const updated = res.data;
      set(s => ({
        areas: s.areas.map(a => a.id === id ? updated : a),
        activeArea: s.activeArea?.id === id ? updated : s.activeArea,
      }));
      return updated;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteArea: async (id) => {
    try {
      await areasAPI.delete(id);
      set(s => ({
        areas: s.areas.filter(a => a.id !== id),
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
      const updated = res.data;
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

  deleteResource: async (id) => {
    try {
      await resourcesAPI.delete(id);
      set(s => ({ resources: s.resources.filter(r => r.id !== id) }));
      get().addToast({ type: 'success', message: 'Resource deleted' });
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  /** Replace or merge a resource row (e.g. after GET detail). */
  upsertResource: (resource) => {
    if (!resource?.id) return;
    set(s => {
      const idx = s.resources.findIndex(r => r.id === resource.id);
      if (idx === -1) return { resources: [resource, ...s.resources] };
      const next = [...s.resources];
      next[idx] = resource;
      return { resources: next };
    });
  },

  // ── People ─────────────────────────────────

  createPerson: async (data) => {
    try {
      const res = await peopleAPI.create(data);
      const person = res.data;
      set(s => ({ people: [person, ...s.people] }));
      get().addToast({ type: 'success', message: `${person.name} added` });
      return person;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updatePerson: async (id, data) => {
    try {
      const res = await peopleAPI.update(id, data);
      const updated = res.data;
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

  deletePerson: async (id) => {
    try {
      await peopleAPI.delete(id);
      set(s => ({
        people: s.people.filter(p => p.id !== id),
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
      const task = res.data;
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
      const updated = res.data;
      set(s => ({ tasks: s.tasks.map(t => t.id === id ? updated : t) }));
      return updated;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  deleteTask: async (id) => {
    try {
      await tasksAPI.delete(id);
      set(s => ({ tasks: s.tasks.filter(t => t.id !== id) }));
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
