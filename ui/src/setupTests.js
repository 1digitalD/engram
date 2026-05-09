import '@testing-library/jest-dom/vitest';

/** Node / partial jsdom environments may expose a broken `localStorage`; tests need a real Map-backed one. */
function makeMemoryStorage() {
  const map = new Map();
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      map.set(String(key), String(value));
    },
    removeItem(key) {
      map.delete(String(key));
    },
    clear() {
      map.clear();
    },
    get length() {
      return map.size;
    },
    key(i) {
      return Array.from(map.keys())[i] ?? null;
    },
  };
}

const _ls = globalThis.localStorage;
if (
  !_ls ||
  typeof _ls.getItem !== 'function' ||
  typeof _ls.setItem !== 'function' ||
  typeof _ls.removeItem !== 'function' ||
  typeof _ls.clear !== 'function'
) {
  Object.defineProperty(globalThis, 'localStorage', {
    value: makeMemoryStorage(),
    configurable: true,
    writable: true,
  });
}
