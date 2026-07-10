import "@testing-library/jest-dom/vitest";

// Polyfill localStorage for tests
if (!globalThis.localStorage) {
  const store: Record<string, string> = {};
  globalThis.localStorage = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      for (const key in store) {
        delete store[key];
      }
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
    length: Object.keys(store).length,
  } as Storage;
}
