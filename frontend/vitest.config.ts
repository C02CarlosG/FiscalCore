import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    passWithNoTests: true,
    // Node 22+ ships an experimental global `localStorage`/`sessionStorage`
    // accessor that returns undefined unless --localstorage-file is passed.
    // Vitest's global setup does not overwrite already-present global keys,
    // so Node's broken accessor shadows jsdom's real, working localStorage.
    // Disabling the experimental flag in the worker process lets jsdom's
    // implementation win. See https://github.com/vitest-dev/vitest/issues/8757
    // (Vitest 4 removed `poolOptions.<pool>.execArgv` in favor of a
    // top-level `execArgv` option — see the pool-rework migration guide.)
    execArgv: ["--no-experimental-webstorage"],
  },
});
