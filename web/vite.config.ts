import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { host: "0.0.0.0", port: 5173 },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("@tanstack")) return "vendor-query";
          if (id.includes("lightweight-charts")) return "vendor-lightweight-charts";
          if (id.includes("recharts") || id.includes("d3-")) return "vendor-recharts";
          if (id.includes("framer-motion")) return "vendor-motion";
          if (id.includes("react") || id.includes("scheduler")) return "vendor-react";
        },
      },
    },
  },
});
