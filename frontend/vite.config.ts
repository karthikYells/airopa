import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to the FastAPI backend so the frontend calls same-origin.
export default defineConfig({
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
