import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The build is copied into the image and served at / next to /v1 (docker/Dockerfile).
// For local work, `npm run dev` proxies the API to a service on :8000 (docker run, or a
// kubectl port-forward).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "dist", emptyOutDir: true },
  server: { proxy: { "/v1": "http://127.0.0.1:8000" } },
});
