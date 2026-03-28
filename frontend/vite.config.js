import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    allowedHosts: ["isinigetir.com", ".isinigetir.com", "localhost", "127.0.0.1"],
    watch: {
      usePolling: true
    },
    hmr: {
      clientPort: 3001
    }
  }
});
