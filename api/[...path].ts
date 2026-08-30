/**
 * Vercel serverless proxy: /api/* on Vercel -> Railway backend.
 * Uses RAILWAY_API_URL (or VITE_API_BASE_URL) at runtime — no CORS from the browser.
 */
export const config = {
  runtime: "edge",
};

function backendBase(): string | null {
  const raw = process.env.RAILWAY_API_URL || process.env.VITE_API_BASE_URL || "";
  const base = raw.trim().replace(/\/$/, "");
  return base || null;
}

export default async function handler(request: Request): Promise<Response> {
  const base = backendBase();
  if (!base) {
    return new Response(
      JSON.stringify({ detail: "RAILWAY_API_URL is not configured on Vercel." }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const incoming = new URL(request.url);
  const target = new URL(`${base}${incoming.pathname}${incoming.search}`);

  const headers = new Headers(request.headers);
  headers.delete("host");

  const init: RequestInit = {
    method: request.method,
    headers,
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }

  return fetch(target.toString(), init);
}
