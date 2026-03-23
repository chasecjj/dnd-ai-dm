import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8642",
      "/ws": {
        target: "ws://localhost:8642",
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/three/")) return "three";
          if (id.includes("@react-three/fiber") || id.includes("@react-three/drei")) return "r3f";
          if (id.includes("@react-three/rapier")) return "r3f-physics";
          if (id.includes("@react-three/postprocessing")) return "r3f-postprocessing";
        },
      },
    },
  },
});
