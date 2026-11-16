import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` proxies /api to the Python backend (scripts/bpm_api.py, port 8790).
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8790" } },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
  build: { chunkSizeWarningLimit: 1600 },
});
