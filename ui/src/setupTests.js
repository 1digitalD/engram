import '@testing-library/jest-dom/vitest';
import * as React from 'react';
if (typeof globalThis.React === 'undefined') globalThis.React = React;

/** jsdom doesn't implement Range rect APIs, which ProseMirror's coordsAtPos relies on. */
if (typeof Range !== 'undefined') {
  if (!Range.prototype.getClientRects) {
    Range.prototype.getClientRects = () => [
      { bottom: 0, height: 0, left: 0, right: 0, top: 0, width: 0, x: 0, y: 0 },
    ];
  }
  if (!Range.prototype.getBoundingClientRect) {
    Range.prototype.getBoundingClientRect = () => ({
      bottom: 0, height: 0, left: 0, right: 0, top: 0, width: 0, x: 0, y: 0,
    });
  }
}

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
