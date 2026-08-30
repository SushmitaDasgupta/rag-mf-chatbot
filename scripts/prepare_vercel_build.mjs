#!/usr/bin/env node
/**
 * Vercel prebuild: validate Railway API URL is configured for /api proxy.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiUrl = (process.env.RAILWAY_API_URL || process.env.VITE_API_BASE_URL || "")
  .trim()
  .replace(/\/$/, "");

if (!apiUrl) {
  console.error(
    "ERROR: Set RAILWAY_API_URL (recommended) or VITE_API_BASE_URL in Vercel Environment Variables.",
  );
  console.error("Use your Railway public URL from Phase 1.5, without a trailing slash.");
  process.exit(1);
}

if (!/^https?:\/\//i.test(apiUrl)) {
  console.error(`ERROR: API URL must start with http:// or https:// (got: ${apiUrl})`);
  process.exit(1);
}

// Relative /api paths in the UI bundle (proxied by api/[...path].ts on Vercel).
const prodEnvPath = path.join(repoRoot, "ui", ".env.production.local");
fs.writeFileSync(prodEnvPath, "VITE_API_BASE_URL=\n");

console.log(`Vercel API proxy target validated -> ${apiUrl}`);
