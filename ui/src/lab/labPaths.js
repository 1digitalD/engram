export function labDetailPath(entityOrType, id) {
  const type = typeof entityOrType === 'string' ? entityOrType : entityOrType?.type;
  const entityId = id ?? entityOrType?.id;
  if (!type || !entityId) return null;
  if (type === 'person') return `/lab/people/${entityId}`;
  return `/lab/${type}s/${entityId}`;
}
