import { commitmentDetailPath } from './commitmentUtils';

const TYPE_LABEL = {
  note: 'Notes',
  task: 'Tasks',
  space: 'Spaces',
  project: 'Spaces',
  area: 'Spaces',
  person: 'People',
  resource: 'Resources',
};

export function recallEntityPath(entity) {
  if (!entity?.id) return null;
  if (entity.type === 'person') return `/people/${entity.id}`;
  if (entity.type === 'project') return `/spaces/${entity.id}`;
  if (entity.type === 'area') return `/spaces/${entity.id}`;
  if (entity.type === 'task') {
    return commitmentDetailPath(entity.id);
  }
  if (entity.type === 'note') return `/notes/${entity.id}`;
  if (entity.type === 'resource') return `/resources/${entity.id}`;
  return null;
}

export function groupRecallResults(results) {
  const groups = new Map();
  for (const entity of results) {
    const type = entity.type === 'project' || entity.type === 'area' ? 'space' : entity.type || 'unknown';
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type).push(entity);
  }
  return [...groups.entries()].map(([type, items]) => ({
    type,
    label: TYPE_LABEL[type] || `${type}s`,
    items,
  }));
}
