import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to the FastAPI backend so the frontend calls same-origin.
// VITE_BASE is the folder the page is served from on accessindia.nl,
// e.g. /engines/india-snapshot/ (see DEPLOY.md).
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: {
    port: 5190,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8077",
        changeOrigin: true,
      },
    },
  },
});
