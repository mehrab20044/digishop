import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],

  server: {
    host: "localhost",

    proxy: {
      "/api/v1/owner": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/api/v1/auth": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/media": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});