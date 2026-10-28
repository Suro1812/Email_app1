import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Standalone dev server on its own port (5173 by default). The proxy below
// is what lets this talk to the real FastAPI backend with zero backend
// changes: from the browser's point of view every /gmail, /auth and
// /notifications request looks same-origin (it goes to this Vite server),
// which avoids needing CORS headers added to app/webhook.py. Requires
// `./scripts/start-local-web.sh` already running on :8000 for real data —
// without it, the app still loads, requests just fail and the UI shows its
// error state (see useMessages.ts).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/gmail": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/notifications": "http://127.0.0.1:8000",
    },
  },
});
