/**
 * Display label for an entity title. When title is missing, returns
 * "(no title)" plus id and type so list rows remain actionable.
 */
export function entityTitleLabel(entityOrItem, { includeType = true } = {}) {
  const title = entityOrItem?.title;
  if (title) return title;

  const id = entityOrItem?.id ?? entityOrItem?.entity_id;
  const type = entityOrItem?.type ?? entityOrItem?.entity_type;
  const parts = ['(no title)'];
  if (id) parts.push(String(id));
  if (includeType && type) parts.push(`[${type}]`);
  return parts.join(' ');
}
