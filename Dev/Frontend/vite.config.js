import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  cacheDir: process.env.CS160_VITE_CACHE_DIR || "node_modules/.vite",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/notifications": "http://127.0.0.1:5000",
    },
  },
});
