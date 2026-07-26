import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite serves on :5173 and proxies API + WebSocket to the core backend on
// :8000, so there's no CORS to worry about. Prod: `vite build` -> dist/, which
// the backend serves directly (single origin at peekabot.local).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist" },
});
