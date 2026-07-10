export const LEGACY_PREFIX = '/legacy';

let appPathPrefix = '';

export function setAppPathPrefix(prefix = '') {
  appPathPrefix = prefix || '';
}

export function getAppPathPrefix() {
  return appPathPrefix;
}

export function appPath(path) {
  if (!path || path === '#') return path;
  if (/^https?:\/\//.test(path)) return path;
  if (path.startsWith(LEGACY_PREFIX) || path.startsWith('/next')) return path;
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${appPathPrefix}${normalized}`;
}

/** Historical name — resolves to v6 root paths by default, /legacy/* inside LegacyApp. */
export function legacyPath(path) {
  return appPath(path);
}
