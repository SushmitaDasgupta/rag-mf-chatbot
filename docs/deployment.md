# Deployment guide

Deploy the **Mutual Fund FAQ Assistant** in two phases: **backend first**, then **frontend**. Complete each phase in order before moving to the next.

| Layer | Platform | Code path | Purpose |
| --- | --- | --- | --- |
| **Backend (API)** | [Railway](https://railway.app) | Repo root (`src/`, `data/`) | FastAPI + Chroma + local embeddings + Groq generation |
| **Frontend (UI)** | [Vercel](https://vercel.com) | `ui/` | React + Vite chat UI |

**Repository:** [github.com/SushmitaDasgupta/rag-mf-chatbot](https://github.com/SushmitaDasgupta/rag-mf-chatbot)

Related docs: [`runbook.md`](./runbook.md) (corpus refresh), [`implementation.md`](./implementation.md) (architecture).

---

## Deployment phases overview

| Phase | Name | Platform | Primary outcome | Depends on |
| --- | --- | --- | --- | --- |
| **Phase 1** | Backend API | Railway | `GET /api/health` returns `ok` with vectors loaded | GitHub repo, Groq API key |
| **Phase 2** | Frontend UI | Vercel | Chat UI loads and calls Railway API | Phase 1 public URL |

**Rule:** Do not start Phase 2 until Phase 1 is verified. The frontend needs the Railway URL at build time (`VITE_API_BASE_URL`).

---

## Architecture (production)

```text
User browser
    │
    ▼
Vercel (static React UI)          ← Phase 2
    │  VITE_API_BASE_URL
    ▼
Railway (FastAPI)                 ← Phase 1
    ├─ Chroma vector store  (data/vectorstore — baked into deploy)
    ├─ sentence-transformers (BAAI/bge-small-en-v1.5 — downloaded at runtime)
    └─ Groq API               (GROQ_API_KEY — secret on Railway)

GitHub Actions (daily 10:00 AM IST)
    └─ refreshes data/ on main → trigger Railway redeploy (optional webhook)
```

The UI calls the API directly from the browser. Vite’s dev proxy (`/api` → `localhost:8000`) is **not** used in production; set `VITE_API_BASE_URL` to your Railway URL instead.

---

## Prerequisites (before Phase 1)

- GitHub repo connected to Railway and Vercel
- [Groq API key](https://console.groq.com/) for factual answer generation
- Railway account (Hobby or Pro — embedding model needs **≥ 2 GB RAM** recommended)
- Vercel account

---

## Phase 1 — Backend (Railway)

**Goal:** A publicly reachable FastAPI service with Chroma loaded, Groq configured, and a passing health check.

### Phase 1.1 — Create the service

1. Open [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `SushmitaDasgupta/rag-mf-chatbot`
3. **Root directory:** `/` (repo root — not `ui/`)
4. Railway auto-detects Python via `requirements.txt`

**Exit criteria:** Service builds without error (dependencies install).

### Phase 1.2 — Start command

Railway injects a `PORT` variable. The repo includes a production start script and config:

| File | Purpose |
| --- | --- |
| `scripts/start_api.sh` | Starts uvicorn on `$PORT` (default 8000 locally) |
| `Procfile` | `web: bash scripts/start_api.sh` |
| `railway.toml` | Start command, health check, Python 3.11, default env |

You do **not** need to set the start command manually in Railway if `railway.toml` / `Procfile` are detected.

```bash
bash scripts/start_api.sh
# equivalent to: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
```

**Exit criteria:** Deploy logs show `=== API START | host=0.0.0.0 port=...`.

### Phase 1.3 — Environment variables

Add these in **Variables** (never commit secrets). Copy from [`railway.env.example`](../railway.env.example) as a template:

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

> **CORS note:** If you have not deployed Vercel yet, set a placeholder origin (e.g. `http://localhost:5173`) for now. Update `CORS_ORIGINS` with your real Vercel URL after Phase 2.

Example:

```env
GROQ_API_KEY=gsk_your_key_here
CORS_ORIGINS=https://rag-mf-chatbot.vercel.app,https://rag-mf-chatbot-git-main-sushmitadasgupta.vercel.app
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
VECTOR_STORE_PATH=data/vectorstore
```

**Exit criteria:** All required variables set in Railway dashboard.

### Phase 1.4 — Resources & health check

| Setting | Recommendation |
| --- | --- |
| **Memory** | ≥ 2 GB (sentence-transformers + Chroma) |
| **Build** | `pip install -r requirements.txt` (default Nixpacks) |
| **Health check** | `GET /api/health` |

**Cold start:** First request after deploy may be slow while the embedding model downloads (~130 MB). Subsequent requests are faster.

**Corpus data:** `data/vectorstore/` and processed corpus files are committed to the repo and ship with each Railway deploy. Daily updates from [GitHub Actions](../.github/workflows/daily-ingest.yml) land on `main`; redeploy Railway (or enable deploy-on-push) to pick up fresh data.

**Exit criteria:** Health check path configured; memory ≥ 2 GB.

### Phase 1.5 — Public URL & verification

1. **Settings → Networking → Generate Domain**
2. Note the URL, e.g. `https://rag-mf-api-production.up.railway.app`
3. Verify with the included script (or `curl`):

```bash
bash scripts/verify_phase1_backend.sh https://YOUR-RAILWAY-URL.up.railway.app
```

Or manually:

```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/api/health
```

Expected: JSON with `"status": "ok"`, `"vector_count" > 0`, `"groq_configured": true`.

**Phase 1 complete when:** Health endpoint returns success with vectors loaded and Groq configured. Save the Railway URL — you need it for Phase 2.

---

## Phase 2 — Frontend (Vercel)

**Goal:** A production chat UI that calls the Phase 1 Railway API (not `localhost`).

**Depends on:** Phase 1 public URL.

### Phase 2.1 — Create the project

1. Open [Vercel](https://vercel.com) → **Add New → Project**
2. Import `SushmitaDasgupta/rag-mf-chatbot`
3. Configure:

| Setting | Value |
| --- | --- |
| **Root Directory** | `/` (repo root) **or** `ui` — both work |
| **Framework Preset** | Other / Vite (see `vercel.json` below) |

**Repo root (`/`):** uses root [`vercel.json`](../vercel.json) — builds `ui/` and avoids FastAPI auto-detection on `src/api/main.py`.

**`ui/` root:** uses [`ui/vercel.json`](../ui/vercel.json) — standard Vite preset with `dist` output.

Do **not** leave Vercel on default FastAPI detection — the backend runs on Railway, not Vercel.

### Phase 2.2 — Environment variables

Copy from [`vercel.env.example`](../vercel.env.example) into **Vercel → Settings → Environment Variables**:

| Variable | Required | Value |
| --- | --- | --- |
| `VITE_API_BASE_URL` | **Yes** | Railway public URL from Phase 1.5 **without** trailing slash, e.g. `https://rag-mf-api-production.up.railway.app` |

Set for **Production** (and Preview if you want preview deployments to hit the same API).

> Vite embeds `VITE_*` variables at **build time**. Changing the API URL requires a **redeploy**.

Local production build test (optional):

```bash
VITE_API_BASE_URL=https://YOUR-RAILWAY-URL.up.railway.app bash scripts/build_ui_production.sh
```

**Exit criteria:** `VITE_API_BASE_URL` set to your Railway URL before first build.

### Phase 2.3 — SPA routing (`ui/vercel.json`)

Committed in the repo for client-side routing and Vercel build defaults:

```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

**Exit criteria:** `ui/vercel.json` present (no manual Vercel dashboard overrides needed).

### Phase 2.4 — Deploy & verify

1. Deploy the project
2. Verify with the included script (or open the URL manually):

```bash
bash scripts/verify_phase2_frontend.sh https://YOUR-APP.vercel.app https://YOUR-RAILWAY-URL.up.railway.app
```

3. Ask an example question (e.g. expense ratio for a Kotak scheme)
4. Confirm a factual answer with citation, or a polite refusal for advisory prompts

**Browser devtools:** Network tab should show `POST` to `https://YOUR-RAILWAY-URL/api/chat` (not `localhost`).

**Phase 2 complete when:** UI loads and chat requests reach Railway successfully.

---

## After deployment — Wire backend ↔ frontend

Run this once both phases are live:

1. Copy Vercel production URL → Railway `CORS_ORIGINS`
2. Redeploy Railway (or restart) so CORS picks up the new origin
3. If chat returns CORS errors in the browser, double-check `CORS_ORIGINS` matches the **exact** origin (scheme + host, no path)

```text
Vercel UI  ──POST /api/chat──▶  Railway API
              ▲
              └── CORS_ORIGINS must include Vercel origin
```

For preview deployments, either list each preview origin in `CORS_ORIGINS` or use production origin only.

---

## Post-deploy checklist

| Check | Command / action |
| --- | --- |
| Phase 1 — API health | `curl https://<railway>/api/health` |
| Phase 1 — Groq configured | `"groq_configured": true` in health response |
| Phase 1 — Vectors loaded | `"vector_count" > 0` |
| Phase 2 — API URL in UI | Network tab shows Railway host, not `localhost` |
| End-to-end — CORS | Chat from Vercel UI succeeds (no browser CORS error) |
| End-to-end — Refusal path | Ask “Should I invest in Kotak Large Cap?” → refusal + edu link |
| End-to-end — Rate limit UX | UI shows cooldown on 429 (client-side) |

---

## Corpus freshness in production

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

## Secrets & security

- **Never** commit `GROQ_API_KEY` — Railway Variables only
- **Never** expose `GROQ_API_KEY` in Vercel (frontend only needs `VITE_API_BASE_URL`)
- Vercel env vars prefixed with `VITE_` are visible in the built JS bundle — only put non-secret URLs there
- No PII is collected by the app; do not add auth forms that capture PAN, phone, etc.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `No FastAPI entrypoint found` on Vercel | Vercel auto-detected Python backend at repo root | Use root [`vercel.json`](../vercel.json) (`framework: null`, builds `ui/`) or set Root Directory to `ui/` |
| `503 GROQ_API_KEY is not configured` | Missing secret on Railway | Set `GROQ_API_KEY` and redeploy (Phase 1.3) |
| CORS error in browser | `CORS_ORIGINS` mismatch | Add exact Vercel URL to Railway `CORS_ORIGINS` |
| `vector_count: 0` / degraded health | Chroma path wrong or empty deploy | Confirm `VECTOR_STORE_PATH=data/vectorstore` and `data/vectorstore/` exists in repo |
| Chat hits `localhost` | `VITE_API_BASE_URL` unset at build | Set on Vercel (Phase 2.2), redeploy UI |
| OOM / crash on Railway | Insufficient memory | Increase service memory to ≥ 2 GB (Phase 1.4) |
| Slow first answer | Embedding model cold download | Normal; consider keeping service warm or accepting cold start |
| 429 from API | Groq rate limit | Wait for `Retry-After`; UI enforces client cooldown |

---

## Repo config files

Phase 1 backend files (committed to the repo):

| File | Platform | Purpose |
| --- | --- | --- |
| `Procfile` | Railway | Process type `web` → `scripts/start_api.sh` |
| `railway.toml` | Railway | Start command, health check, Python 3.11, default env |
| `scripts/start_api.sh` | Railway | Production uvicorn entrypoint (`$PORT`) |
| `scripts/verify_phase1_backend.sh` | Local / CI | Phase 1.5 health gate |
| `railway.env.example` | Railway | Variable template for dashboard |
| `.python-version` | Railway / local | Python 3.11 |

Phase 2 (Vercel) files:

| File | Platform | Purpose |
| --- | --- | --- |
| `vercel.json` | Vercel | Root deploy — builds `ui/`, disables FastAPI auto-detect |
| `ui/vercel.json` | Vercel | Use when Root Directory is set to `ui/` |
| `ui/.env.example` | Local / Vercel | `VITE_API_BASE_URL` template for `ui/` |
| `vercel.env.example` | Vercel | Variable template for dashboard |
| `scripts/build_ui_production.sh` | Local / CI | Production build with API URL guard |
| `scripts/verify_phase2_frontend.sh` | Local / CI | Phase 2.4 reachability gate |

---

## Local parity

Match production locally:

```bash
# Terminal 1 — API (same as Railway / Phase 1)
export GROQ_API_KEY=gsk_...
export CORS_ORIGINS=http://localhost:5173
bash scripts/start_api.sh

# Terminal 2 — UI (same as Vercel / Phase 2)
cd ui
export VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev

# Or test a production build locally:
# VITE_API_BASE_URL=http://127.0.0.1:8000 bash scripts/build_ui_production.sh
# cd ui && npm run preview
```

---

## Cost notes (indicative)

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
| Phase 1 | Railway — FastAPI + Chroma + Groq |
| Phase 2 | Vercel — React/Vite in `ui/` |
| Related | [`runbook.md`](./runbook.md), [`README.md`](../README.md) |
