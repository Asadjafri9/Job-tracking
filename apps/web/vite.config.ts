import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    proxy: {
      "/auth": "http://127.0.0.1:18000",
      "/api/v1": "http://127.0.0.1:18000",
    },
  },
});
