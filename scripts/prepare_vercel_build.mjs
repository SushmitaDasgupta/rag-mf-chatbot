#!/usr/bin/env node
/**
 * Vercel prebuild: require Railway API URL and inject /api proxy rewrites.
 * Browser calls same-origin /api/* on Vercel; Vercel forwards to Railway.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiUrl = (process.env.VITE_API_BASE_URL || process.env.RAILWAY_API_URL || "")
  .trim()
  .replace(/\/$/, "");

if (!apiUrl) {
  console.error(
    "ERROR: Set VITE_API_BASE_URL (or RAILWAY_API_URL) in Vercel Environment Variables.",
  );
  console.error("Use your Railway public URL from Phase 1.5, without a trailing slash.");
  console.error("Example: https://rag-mf-api-production.up.railway.app");
  process.exit(1);
}

if (!/^https?:\/\//i.test(apiUrl)) {
  console.error(`ERROR: API URL must start with http:// or https:// (got: ${apiUrl})`);
  process.exit(1);
}

const vercelPath = path.join(repoRoot, "vercel.json");
const vercel = JSON.parse(fs.readFileSync(vercelPath, "utf8"));
vercel.rewrites = [
  { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
  { source: "/(.*)", destination: "/index.html" },
];
fs.writeFileSync(vercelPath, `${JSON.stringify(vercel, null, 2)}\n`);

// Relative /api paths in the UI bundle (same-origin proxy on Vercel).
const prodEnvPath = path.join(repoRoot, "ui", ".env.production.local");
fs.writeFileSync(prodEnvPath, "VITE_API_BASE_URL=\n");

console.log(`Vercel API proxy configured -> ${apiUrl}`);
