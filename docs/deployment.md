# Deployment guide

Deploy the **Mutual Fund FAQ Assistant** as a split stack:

| Layer | Platform | Code path | Purpose |
| --- | --- | --- | --- |
| **Backend (API)** | [Railway](https://railway.app) | Repo root (`src/`, `data/`) | FastAPI + Chroma + local embeddings + Groq generation |
| **Frontend (UI)** | [Vercel](https://vercel.com) | `ui/` | React + Vite chat UI |

**Repository:** [github.com/SushmitaDasgupta/rag-mf-chatbot](https://github.com/SushmitaDasgupta/rag-mf-chatbot)

Related docs: [`runbook.md`](./runbook.md) (corpus refresh), [`implementation.md`](./implementation.md) (architecture).

---

## Architecture (production)

```text
User browser
    │
    ▼
Vercel (static React UI)
    │  VITE_API_BASE_URL
    ▼
Railway (FastAPI)
    ├─ Chroma vector store  (data/vectorstore — baked into deploy)
    ├─ sentence-transformers (BAAI/bge-small-en-v1.5 — downloaded at runtime)
    └─ Groq API               (GROQ_API_KEY — secret on Railway)

GitHub Actions (daily 10:00 AM IST)
    └─ refreshes data/ on main → trigger Railway redeploy (optional webhook)
```

The UI calls the API directly from the browser. Vite’s dev proxy (`/api` → `localhost:8000`) is **not** used in production; set `VITE_API_BASE_URL` to your Railway URL instead.

---

## Prerequisites

- GitHub repo connected to both Railway and Vercel
- [Groq API key](https://console.groq.com/) for factual answer generation
- Railway account (Hobby or Pro — embedding model needs **≥ 2 GB RAM** recommended)
- Vercel account

**Deploy order:** Railway (backend) first → note the public API URL → Vercel (frontend) with that URL.

---

## 1. Backend — Railway

### 1.1 Create the service

1. Open [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `SushmitaDasgupta/rag-mf-chatbot`
3. **Root directory:** `/` (repo root — not `ui/`)
4. Railway auto-detects Python via `requirements.txt`

### 1.2 Start command

Railway injects a `PORT` variable. Use it in the start command:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

Set this under **Settings → Deploy → Start Command** (or add a `Procfile` at repo root — see [Optional config files](#optional-config-files)).

### 1.3 Environment variables (Railway)

Add these in **Variables** (never commit secrets):

| Variable | Required | Example / notes |
| --- | --- | --- |
| `GROQ_API_KEY` | **Yes** (for answers) | `gsk_...` |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` (default) |
| `CORS_ORIGINS` | **Yes** | `https://your-app.vercel.app` — add preview URLs if needed (comma-separated) |
| `EMBEDDING_MODEL` | No | `BAAI/bge-small-en-v1.5` |
| `VECTOR_STORE_PATH` | No | `data/vectorstore` |
| `CHROMA_COLLECTION` | No | `mutual_fund_chunks` |
| `MANIFEST_PATH` | No | `data/manifest.yaml` |
| `API_HOST` | No | `0.0.0.0` (uvicorn flag overrides) |

**CORS:** After Vercel deploys, set `CORS_ORIGINS` to your production Vercel URL. For preview deployments, either list each preview origin or use a single production origin only.

Example:

```env
GROQ_API_KEY=gsk_your_key_here
CORS_ORIGINS=https://rag-mf-chatbot.vercel.app,https://rag-mf-chatbot-git-main-sushmitadasgupta.vercel.app
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
VECTOR_STORE_PATH=data/vectorstore
```

### 1.4 Resources & build

| Setting | Recommendation |
| --- | --- |
| **Memory** | ≥ 2 GB (sentence-transformers + Chroma) |
| **Build** | `pip install -r requirements.txt` (default Nixpacks) |
| **Health check** | `GET /api/health` |

**Cold start:** First request after deploy may be slow while the embedding model downloads (~130 MB). Subsequent requests are faster.

**Corpus data:** `data/vectorstore/` and processed corpus files are committed to the repo and ship with each Railway deploy. Daily updates from [GitHub Actions](../.github/workflows/daily-ingest.yml) land on `main`; redeploy Railway (or enable deploy-on-push) to pick up fresh data.

### 1.5 Public URL

1. **Settings → Networking → Generate Domain**
2. Note the URL, e.g. `https://rag-mf-api-production.up.railway.app`
3. Verify:

```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/api/health
```

Expected: JSON with `"status": "ok"`, `"vector_count" > 0`, `"groq_configured": true`.

---

## 2. Frontend — Vercel

### 2.1 Create the project

1. Open [Vercel](https://vercel.com) → **Add New → Project**
2. Import `SushmitaDasgupta/rag-mf-chatbot`
3. Configure:

| Setting | Value |
| --- | --- |
| **Framework Preset** | Vite |
| **Root Directory** | `ui` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |
| **Install Command** | `npm install` |

### 2.2 Environment variables (Vercel)

| Variable | Required | Value |
| --- | --- | --- |
| `VITE_API_BASE_URL` | **Yes** | Railway public URL **without** trailing slash, e.g. `https://rag-mf-api-production.up.railway.app` |

Set for **Production** (and Preview if you want preview deployments to hit the same API).

> Vite embeds `VITE_*` variables at **build time**. Changing the API URL requires a **redeploy**.

### 2.3 SPA routing (optional `vercel.json`)

If client-side routes are added later, place this in `ui/vercel.json`:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

The current single-page app works without this for `/` only.

### 2.4 Deploy & verify

1. Deploy the project
2. Open the Vercel URL
3. Ask an example question (e.g. expense ratio for a Kotak scheme)
4. Confirm a factual answer with citation, or a polite refusal for advisory prompts

**Browser devtools:** Network tab should show `POST` to `https://YOUR-RAILWAY-URL/api/chat` (not `localhost`).

---

## 3. Wire backend ↔ frontend

After both are live:

1. Copy Vercel production URL → Railway `CORS_ORIGINS`
2. Redeploy Railway (or restart) so CORS picks up the new origin
3. If chat returns CORS errors in the browser, double-check `CORS_ORIGINS` matches the **exact** origin (scheme + host, no path)

```text
Vercel UI  ──POST /api/chat──▶  Railway API
              ▲
              └── CORS_ORIGINS must include Vercel origin
```

---

## 4. Post-deploy checklist

| Check | Command / action |
| --- | --- |
| API health | `curl https://<railway>/api/health` |
| Groq configured | `"groq_configured": true` in health response |
| Vectors loaded | `"vector_count" > 0` |
| CORS | Chat from Vercel UI succeeds (no browser CORS error) |
| Refusal path | Ask “Should I invest in Kotak Large Cap?” → refusal + edu link |
| Rate limit UX | UI shows cooldown on 429 (client-side) |

---

## 5. Corpus freshness in production

| Mechanism | What it does |
| --- | --- |
| **GitHub Actions** | Daily ingest at 10:00 AM IST commits updated `data/` to `main` |
| **Railway** | Serves corpus baked into the last deploy |

To serve updated corpus on Railway after a daily ingest commit:

- **Option A:** Enable **Deploy on push** to `main` in Railway (simplest)
- **Option B:** Manual redeploy from Railway dashboard after ingest commits
- **Option C:** Railway deploy webhook triggered by GitHub Actions (advanced)

See [`runbook.md`](./runbook.md) for ingest failure handling.

---

## 6. Secrets & security

- **Never** commit `GROQ_API_KEY` — Railway Variables only
- **Never** expose `GROQ_API_KEY` in Vercel (frontend only needs `VITE_API_BASE_URL`)
- Vercel env vars prefixed with `VITE_` are visible in the built JS bundle — only put non-secret URLs there
- No PII is collected by the app; do not add auth forms that capture PAN, phone, etc.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `503 GROQ_API_KEY is not configured` | Missing secret on Railway | Set `GROQ_API_KEY` and redeploy |
| CORS error in browser | `CORS_ORIGINS` mismatch | Add exact Vercel URL to Railway `CORS_ORIGINS` |
| `vector_count: 0` / degraded health | Chroma path wrong or empty deploy | Confirm `VECTOR_STORE_PATH=data/vectorstore` and `data/vectorstore/` exists in repo |
| Chat hits `localhost` | `VITE_API_BASE_URL` unset at build | Set on Vercel, redeploy UI |
| OOM / crash on Railway | Insufficient memory | Increase service memory to ≥ 2 GB |
| Slow first answer | Embedding model cold download | Normal; consider keeping service warm or accepting cold start |
| 429 from API | Groq rate limit | Wait for `Retry-After`; UI enforces client cooldown |

---

## 8. Optional config files

Add these to the repo for repeatable deploys (not required if set in platform UI).

### `Procfile` (repo root — Railway)

```text
web: uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### `ui/vercel.json` (Vercel SPA fallback)

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

### `railway.toml` (optional — Railway)

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
```

---

## 9. Local parity

Match production locally:

```bash
# Terminal 1 — API (same as Railway)
export GROQ_API_KEY=gsk_...
export CORS_ORIGINS=http://localhost:5173
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — UI (same as Vercel build env)
cd ui
export VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

---

## 10. Cost notes (indicative)

| Service | Typical MVP cost |
| --- | --- |
| Vercel (Hobby) | Free for personal static sites |
| Railway | Usage-based; embedding RAM may need paid tier |
| Groq | Free tier with RPM/RPD limits (see `.env.example`) |
| GitHub Actions | Free for public repos; daily ingest within free minutes |

---

## Document control

| Item | Value |
| --- | --- |
| Backend | Railway — FastAPI + Chroma + Groq |
| Frontend | Vercel — React/Vite in `ui/` |
| Related | [`runbook.md`](./runbook.md), [`README.md`](../README.md) |
