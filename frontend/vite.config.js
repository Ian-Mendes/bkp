import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 3000,
    proxy: {
      // mesma origem em dev: o navegador chama /api e o Vite encaminha ao backend (sem CORS)
      "/api": {
        target: "http://api:8000",   // nome do serviço no docker-compose
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
