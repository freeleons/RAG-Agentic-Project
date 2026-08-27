/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // 127.0.0.1, not localhost: macOS AirPlay Receiver also listens on
    // port 5000 and answers localhost with 403 before Flask can.
    proxy: { "/api": "http://127.0.0.1:5004" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
