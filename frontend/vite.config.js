import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api, /health e /files para o backend FastAPI em :8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5200,
    proxy: {
      "/health": "http://localhost:8000",
      "/cnpj": "http://localhost:8000",
      "/credenciais": "http://localhost:8000",
      "/portal": "http://localhost:8000",
      "/history": "http://localhost:8000",
      "/jobs": "http://localhost:8000",
      "/files": "http://localhost:8000",
    },
  },
});
