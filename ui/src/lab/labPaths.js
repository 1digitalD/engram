import { legacyPath } from '../legacy/legacyPaths';

export function labDetailPath(entityOrType, id) {
  const type = typeof entityOrType === 'string' ? entityOrType : entityOrType?.type;
  const entityId = id ?? entityOrType?.id;
  if (!type || !entityId) return null;
  if (type === 'person') return legacyPath(`/lab/people/${entityId}`);
  return legacyPath(`/lab/${type}s/${entityId}`);
}
