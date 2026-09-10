import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// public/ holds revision-state.json and the copied data/ tree, so both are served
// from the site root in dev and copied into dist/ on build.
export default defineConfig({
  plugins: [react()],
  server: { port: 5183, strictPort: false },
});
