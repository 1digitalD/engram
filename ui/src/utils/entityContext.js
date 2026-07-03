export function pathForEntityType(type, id) {
  if (!type || !id) return null;
  if (type === 'person') return `/people/${id}`;
  return `/${type}s/${id}`;
}

export function taskContextItems(entity) {
  const projects = (entity?.projects || []).map((item) => ({ ...item, type: 'project' }));
  const areas = (entity?.areas || []).map((item) => ({ ...item, type: 'area' }));
  const people = (entity?.people || []).map((item) => ({ ...item, type: 'person' }));
  return [...projects, ...areas, ...people];
}

export function hasTaskContext(entity) {
  return taskContextItems(entity).length > 0;
}
