import React from 'react';
import { FileText, FolderOpen, Map, User, Library, CheckSquare } from 'lucide-react';

const TYPE_CONFIG = {
  note:     { label: 'Notes',     icon: FileText,   route: (id) => `/notes/${id}` },
  task:     { label: 'Tasks',     icon: CheckSquare, route: (id) => `/tasks/${id}` },
  project:  { label: 'Projects',  icon: FolderOpen, route: (id) => `/projects/${id}` },
  area:     { label: 'Areas',     icon: Map,        route: (id) => `/areas/${id}` },
  person:   { label: 'People',    icon: User,       route: (id) => `/people/${id}` },
  resource: { label: 'Resources', icon: Library,    route: (id) => `/resources/${id}` },
};

const STORE_COLLECTIONS = [
  ['note', 'notes'],
  ['task', 'tasks'],
  ['project', 'projects'],
  ['area', 'areas'],
  ['person', 'people'],
  ['resource', 'resources'],
];

export function resolveEntity(id, store) {
  if (!id || !store) return null;
  for (const [type, key] of STORE_COLLECTIONS) {
    const entity = store[key]?.find((item) => item.id === id);
    if (entity) {
      return { ...entity, type };
    }
  }
  return null;
}

export function getEntityTitle(entity) {
  if (!entity) return 'Untitled';
  if (entity.type === 'note') {
    return (entity.raw_text || '')
      .split('\n')[0]
      .replace(/^#\s*/, '')
      .trim() || entity.title || 'Untitled';
  }
  return entity.title || 'Untitled';
}

export function getEntityRoute(entity) {
  const cfg = TYPE_CONFIG[entity?.type];
  if (!cfg) return null;
  return cfg.route(entity.id);
}

export function EntityTypeIcon({ type, size = 12 }) {
  const cfg = TYPE_CONFIG[type];
  const Icon = cfg?.icon || FileText;
  return <Icon size={size} />;
}
