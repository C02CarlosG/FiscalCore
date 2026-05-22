import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  root: "src",
  plugins: [react(), tailwindcss()],
  server: {
    port: 3001,
    proxy: { "/api": "http://localhost:8000" },
  },
  build: { outDir: "../dist", emptyOutDir: true },
});
