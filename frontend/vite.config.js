import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      [
        "/api/v1/cart",
        "/api/v1/orders",
        "/api/v1/payments",
        "/products/api/v1",
        "/api/v1/owner",
        "/api/v1/auth",
        "/media",
      ].map((path) => [
        path,
        {
          target: backend,
          changeOrigin: false,
        },
      ]),
    ),
  },
});
