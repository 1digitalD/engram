export function taskOwnerRef(item) {
  if (item?.owner?.id) return item.owner;
  const person = item?.people?.[0];
  if (person?.id) return person;
  if (item?.assigned_to?.id) return item.assigned_to;
  return null;
}

export function taskOwnerId(item) {
  return taskOwnerRef(item)?.id || '';
}

export function normalizeTaskOwner(task) {
  if (!task) return task;
  const owner = taskOwnerRef(task);
  return owner ? { ...task, owner } : task;
}

export function taskSpaceRef(entity) {
  const project = entity?.projects?.[0];
  if (project?.id) return { id: project.id, title: project.title, kind: 'project' };
  const area = entity?.areas?.[0];
  if (area?.id) return { id: area.id, title: area.title, kind: 'area' };
  return null;
}

export function taskSpaceId(entity) {
  return taskSpaceRef(entity)?.id || '';
}

export function isOrphanTaskEntity(entity) {
  return entity?.type === 'task' && !taskSpaceId(entity);
}

export function commitmentDetailPath(taskId) {
  return taskId ? `/commitments/${taskId}` : null;
}

export async function assignTaskToSpace(entitiesApi, taskId, spaceId) {
  if (!taskId || !spaceId) {
    throw new Error('Task and space are required.');
  }
  return entitiesApi.createLink(taskId, {
    target_id: spaceId,
    relationship_type: 'parent',
    replace_existing: true,
    batch_summary: 'assign commitment to space',
  });
}

export function listSpacesForAssign(...payloads) {
  const byId = new Map();
  for (const payload of payloads) {
    for (const row of payload?.data || []) {
      if (row?.id) byId.set(row.id, row);
    }
  }
  return [...byId.values()].sort((left, right) =>
    (left.title || '').localeCompare(right.title || '', undefined, { sensitivity: 'base' }),
  );
}
