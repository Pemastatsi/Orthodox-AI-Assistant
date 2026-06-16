// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... } }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Proxy /api to the FastAPI backend so the browser makes same-origin requests in dev
// (no backend CORS needed). The backend runs on :8000 via `make dev`.
export default defineConfig({
  vite: {
    server: {
      // Bind IPv4 loopback. The lovable wrapper otherwise defaults to host "::" (IPv6),
      // which fails on IPv4-only environments. In a real Lovable sandbox this is overridden
      // back to "::" automatically, so this only affects local runs.
      host: "127.0.0.1",
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  },
});
