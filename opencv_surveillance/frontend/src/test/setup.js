// Test setup file for Vitest
import '@testing-library/jest-dom';

// Mock window.matchMedia (not available in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {}, // deprecated
    removeListener: () => {}, // deprecated
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
};

// Node's own experimental localStorage shadows jsdom's.
//
// Node 22 exposes a global `localStorage` that is unusable unless the process
// was started with --localstorage-file. It takes precedence over the one jsdom
// installs, so any module reading bare `localStorage` at import time saw
// undefined and failed to load. authService.js does exactly that — its
// singleton is constructed at module scope — so the whole file collected zero
// tests with "Cannot read properties of undefined (reading 'getItem')".
//
// A Map-backed implementation is installed unconditionally rather than
// forwarding to jsdom's, because whether jsdom's own copy survives the shadowing
// varies by Node and jsdom version. This is small, exact, and does not depend on
// which of them wins.
class MemoryStorage {
  constructor() {
    this.store = new Map();
  }
  get length() {
    return this.store.size;
  }
  key(index) {
    return Array.from(this.store.keys())[index] ?? null;
  }
  getItem(key) {
    return this.store.has(String(key)) ? this.store.get(String(key)) : null;
  }
  setItem(key, value) {
    this.store.set(String(key), String(value));
  }
  removeItem(key) {
    this.store.delete(String(key));
  }
  clear() {
    this.store.clear();
  }
}

for (const name of ['localStorage', 'sessionStorage']) {
  const storage = new MemoryStorage();
  Object.defineProperty(globalThis, name, {
    configurable: true,
    writable: true,
    value: storage,
  });
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, name, {
      configurable: true,
      writable: true,
      value: storage,
    });
  }
}
