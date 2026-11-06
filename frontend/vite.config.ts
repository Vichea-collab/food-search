import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev`: live reload on http://localhost:5173, API calls go to the Python server (python backend/web.py).
// `npm run build`: writes dist/, which the Python server serves on http://127.0.0.1:8080.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8080" },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
