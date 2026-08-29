import type { ChatApiResponse } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function apiUrl(path: string): string {
  if (!API_BASE) {
    // Production: same-origin /api via Vercel rewrite (see scripts/prepare_vercel_build.mjs).
    return path;
  }
  return `${API_BASE}${path}`;
}

export async function postChat(message: string): Promise<{
  status: number;
  data: ChatApiResponse | { detail?: string };
}> {
  const res = await fetch(apiUrl("/api/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const data = (await res.json()) as ChatApiResponse | { detail?: string };
  return { status: res.status, data };
}

export function stripStructuredFooter(text: string): string {
  return text
    .replace(/\n*Source:\s*https?:\/\/\S+/i, "")
    .replace(/\n*Last updated from sources:\s*\S+/i, "")
    .trim();
}
