import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@common": path.resolve(__dirname, "../common/src"),
      "@heroicons/react": path.resolve(__dirname, "./node_modules/@heroicons/react"),
      "axios": path.resolve(__dirname, "./node_modules/axios"),
      "clsx": path.resolve(__dirname, "./node_modules/clsx"),
      "react": path.resolve(__dirname, "./node_modules/react"),
      "react/jsx-runtime": path.resolve(__dirname, "./node_modules/react/jsx-runtime"),
      "react-router-dom": path.resolve(__dirname, "./node_modules/react-router-dom"),
      "tailwind-merge": path.resolve(__dirname, "./node_modules/tailwind-merge"),
    },
  },
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (url) => url.replace(/^\/api/, ""),
      },
      "/uploads": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
