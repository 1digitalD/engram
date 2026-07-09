export const LEGACY_PREFIX = '/legacy';

export function legacyPath(path) {
  if (!path || path === '#') return path;
  if (path.startsWith(LEGACY_PREFIX)) return path;
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${LEGACY_PREFIX}${normalized}`;
}
