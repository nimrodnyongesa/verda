import type { NextConfig } from "next";
import path from "node:path";

// API routing:
//   - Server Components → lib/api.ts → ${WAKILI_INTERNAL_API_BASE} (default 127.0.0.1:8765)
//   - Client Components → /api/be/[...path]/route.ts (proxy with Bearer injection)
//   - Auth flow         → /api/auth/{login,callback,logout,me,providers}/route.ts
// No rewrites needed; route handlers match first.

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
