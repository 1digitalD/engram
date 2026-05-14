import React from 'react';
import { FileText, FolderOpen, Map, User, Library, CheckSquare, Link2, ArrowUp, ArrowDown } from 'lucide-react';

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

export const ENTITY_TYPES = ['note', 'task', 'project', 'area', 'person', 'resource'];

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
    return (entity.content || entity.raw_text || '')
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

export function getEntityTypeLabel(type) {
  const cfg = TYPE_CONFIG[type];
  return cfg?.label || 'Unknown';
}

/**
 * Map raw link_type + entity types to a human-readable UI label.
 * Returns an object with `label` (forward direction) and `inverseLabel` (reverse).
 */
export function getRelationshipDisplayLabel(srcType, dstType, linkType, direction = 'outgoing') {
  const pairs = {
    'parent': {
      task_project:        { label: 'Belongs to project', inverseLabel: 'Has task' },
      project_area:        { label: 'Part of area',       inverseLabel: 'Contains project' },
      task_area:           { label: 'Part of area',       inverseLabel: 'Has task' },
      resource_area:       { label: 'Filed under area',    inverseLabel: 'Contains resource' },
    },
    'derived_from': {
      task_note:           { label: 'Created from note',  inverseLabel: 'Generated task' },
      project_note:        { label: 'Created from note',  inverseLabel: 'Generated project' },
      resource_note:       { label: 'Created from note',  inverseLabel: 'Generated resource' },
      area_note:           { label: 'Created from note',  inverseLabel: 'Generated area' },
      person_note:         { label: 'Created from note',  inverseLabel: 'Generated person' },
    },
    'mentions': {
      note_person:         { label: 'Mentions',           inverseLabel: 'Mentioned in' },
      note_project:        { label: 'Mentions',           inverseLabel: 'Mentioned in' },
      note_area:           { label: 'Mentions',           inverseLabel: 'Mentioned in' },
    },
    'references': {
      note_resource:       { label: 'References',         inverseLabel: 'Referenced by' },
      task_resource:       { label: 'Uses resource',      inverseLabel: 'Used by' },
      project_resource:    { label: 'Uses resource',      inverseLabel: 'Used by' },
    },
    'assigned_to': {
      task_person:         { label: 'Assigned to',        inverseLabel: 'Assigned' },
      project_person:      { label: 'Owned by',            inverseLabel: 'Owns' },
    },
    'blocks': {
      task_task:           { label: 'Blocks',             inverseLabel: 'Blocked by' },
      project_project:     { label: 'Blocks',             inverseLabel: 'Blocked by' },
    },
    'related': {},
  };

  const src = srcType || '';
  const dst = dstType || '';
  const key = `${src}_${dst}`;

  const typeMap = pairs[linkType];
  if (typeMap?.[key]) {
    return direction === 'incoming' ? typeMap[key].inverseLabel || typeMap[key].label : typeMap[key].label;
  }

  const fallbacks = {
    parent:             'Parent',
    derived_from:       'Derived from',
    mentions:           'Mentions',
    references:         'References',
    assigned_to:        'Assigned to',
    blocks:             'Blocks',
    related:            'Related',
  };

  return fallbacks[linkType] || linkType;
}

/**
 * Resolve multiple link IDs at once, returning { resolved, unresolved }.
 */
export function resolveLinks(ids, store) {
  const resolved = [];
  const unresolved = [];
  for (const id of (ids || [])) {
    const entity = resolveEntity(id, store);
    if (entity) resolved.push(entity);
    else unresolved.push(id);
  }
  return { resolved, unresolved };
}
