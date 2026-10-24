import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api is proxied to FastAPI. Inside docker compose the target is
// the `api` service; locally it's localhost.
const apiTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
});
