/**
 * Engram Zustand Store
 * Single source of truth for all app state
 */

import { create } from 'zustand';
import { notesAPI, projectsAPI, areasAPI, peopleAPI, tasksAPI } from '../api/engram';

const useStore = create((set, get) => ({
  // ── Data ──────────────────────────────────
  notes:    [],
  projects: [],
  areas:    [],
  people:   [],
  tasks:    [],
  tags:     [],

  // ── UI State ───────────────────────────────
  loading:     false,
  toasts:      [],
  searchQuery: '',
  sidebarOpen: true,

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

  // ── Data Loaders ───────────────────────────

  loadAll: async () => {
    set({ loading: true });
    try {
      const [notes, projects, areas, people, tasks] = await Promise.all([
        notesAPI.list(),
        projectsAPI.list(),
        areasAPI.list(),
        peopleAPI.list(),
        tasksAPI.list(),
      ]);
      set({
        notes:    notes.data || [],
        projects: projects.data || [],
        areas:    areas.data || [],
        people:   people.data || [],
        tasks:    tasks.data || [],
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
      const res = await notesAPI.create(data);
      const note = res.data;
      set(s => ({ notes: [note, ...s.notes] }));
      get().addToast({ type: 'success', message: 'Note captured' });
      return note;
    } catch (e) {
      get().addToast({ type: 'error', message: e.message });
      throw e;
    }
  },

  updateNote: async (id, data) => {
    try {
      const res = await notesAPI.update(id, data);
      const updated = res.data;
      set(s => ({
        notes: s.notes.map(n => n.id === id ? updated : n),
        activeNote: s.activeNote?.id === id ? updated : s.activeNote,
      }));
      get().addToast({ type: 'success', message: 'Note updated' });
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
      return updated;
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

  setActiveArea: (area) => set({ activeArea: area }),

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

  setActivePerson: (person) => set({ activePerson: person }),

  // ── Tasks ──────────────────────────────────

  createTask: async (data) => {
    try {
      const res = await tasksAPI.create(data);
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
      const res = await tasksAPI.update(id, data);
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
