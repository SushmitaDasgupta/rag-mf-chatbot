# Mutual Fund FAQ Assistant (Facts-Only RAG)

Facts-only Kotak mutual-fund FAQ chatbot. Answers come from a curated corpus built **only** from scheme Reference URLs in [`docs/problemStatement.md`](docs/problemStatement.md). No investment advice.

> **Facts-only. No investment advice.**

## Status

Phase 2 complete: RAG core (resolve → retrieve → Groq → validate → API). Phase 0 bootstrap and Phase 1 ingest/index pipeline included.

## Stack (MVP)

| Layer | Choice |
| --- | --- |
| API | FastAPI |
| UI (P4) | Streamlit |
| Vector store | Chroma (local) |
| Embeddings | `BAAI/bge-small-en-v1.5` (local, BGE prefixes) |
| LLM | Groq API (`GROQ_API_KEY`) |

## Selected schemes

| Scheme | Category |
| --- | --- |
| Kotak Large Cap Fund – Direct Growth | Large-cap |
| Kotak Midcap Fund – Direct Growth | Mid-cap |
| Kotak Arbitrage Fund – Direct Growth | Arbitrage |
| Kotak Savings Fund – Direct Growth | Debt / savings |
| Kotak Gold Fund – Growth Direct | Commodity / gold |
| Kotak Flexicap Fund – Direct Growth | Flexi-cap |
| Kotak Liquid Fund – Growth Direct | Liquid |

Source URLs are locked in [`data/manifest.yaml`](data/manifest.yaml) (verbatim copies from the problem statement).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set GROQ_API_KEY in .env (needed from generation phase onward)
```

## Smoke checks

```bash
pytest tests/ -q
uvicorn src.api.main:app --reload
# GET http://127.0.0.1:8000/api/health
```

## Ingest (Phase 1.1)

Fetch allowlisted scheme HTML into `data/raw/` (fail closed on non–problem-statement URLs):

```bash
python -m src.ingest.fetch
# or verify existing files without network:
python -m src.ingest.fetch --verify-only
```

Artifacts: `data/raw/<scheme_id>.html` and `data/raw/fetch_log.yaml` (hashes, HTTP status, timestamps).

## Parse (Phase 1.2)

Strip chrome and extract text/tables into `data/processed/parsed/`:

```bash
python -m src.ingest.parse
```

Outputs per scheme: `.json` + `.txt`, plus `SPOT_CHECK.md`, `parse_log.yaml`, and updated `data/processed/structured_facts.yaml` candidates.

## Chunk (Phase 1.3)

Section-aware chunks from parsed JSON into `data/processed/chunks/`:

```bash
python -m src.ingest.chunk
```

Outputs per scheme: `.json` + `.jsonl`, plus `CHUNK_QC.md` and `chunk_log.yaml`.

## Index (Phase 1.4)

Embed chunks into Chroma and run retrieval smoke probes:

```bash
python -m src.ingest.index
# after changing EMBEDDING_MODEL, recreate the collection:
python -m src.ingest.index --recreate-collection

# Inspect embeddings + sample retrieval
python scripts/inspect_embeddings.py
```

Full pipeline (fetch → parse → chunk → index):

```bash
python -m src.ingest.run --skip-fetch --verify-only
```

Artifacts: `data/vectorstore/` (Chroma), `data/vectorstore/index_log.yaml`, `data/processed/chunks/retrieval_probe_log.yaml`, and `data/processed/structured_facts_report.yaml`.

### Corpus freshness (Phase 6)

The corpus is **refreshed daily at 10:00 AM IST** via GitHub Actions ([`.github/workflows/daily-ingest.yml`](.github/workflows/daily-ingest.yml)). Successful runs commit updated `data/` artifacts to `main`. See [`docs/runbook.md`](docs/runbook.md) for manual refresh and failure handling.

## RAG core (Phase 2)

Chat pipeline: scheme resolver → tiered retriever → Groq generator → output validator → API.

```bash
# Retrieval probes (35 core facet checks; no Groq needed)
python scripts/retrieval_probe.py

# Golden smoke set (miss/refusal paths work without Groq; answers need GROQ_API_KEY)
python scripts/golden_cli.py

# Single-query demo (retrieval + LLM draft + final answer)
python scripts/ask.py --query "What is the current NAV of Kotak Arbitrage Fund?"

# API
uvicorn src.api.main:app --reload
# GET  http://127.0.0.1:8000/api/health
# GET  http://127.0.0.1:8000/api/limits
# POST http://127.0.0.1:8000/api/chat  {"message":"What is the expense ratio?","scheme_id":"kotak_large_cap_direct_growth"}
```

## UI (Phase 4)

React web app matching the Stitch design (`stitch_kotak_mutual_fund_faq_assistant/`) with chat history sidebar and rate-limit aware UX:

```bash
# Terminal 1 — API
uvicorn src.api.main:app --reload

# Terminal 2 — UI
cd ui && npm install && npm run dev
```

Open http://localhost:5173

The UI handles API rate limits (429 cooldown) client-side; Groq quota is enforced on the backend only.

Phase 2 modules: `src/rag/{scheme_resolver,intent,retrieve,generate,validate,chat}.py`

## Deployment

Phase-wise production deploy (backend first, then frontend): [`docs/deployment.md`](docs/deployment.md)

| Phase | Platform | Quick start |
| --- | --- | --- |
| **Phase 1** — Backend API | Railway | Connect repo → set `GROQ_API_KEY` + `CORS_ORIGINS` from [`railway.env.example`](railway.env.example) → deploy |
| **Phase 2** — Frontend UI | Vercel | Set `VITE_API_BASE_URL` to Railway URL → deploy `ui/` |

Verify Phase 1 after deploy:

```bash
bash scripts/verify_phase1_backend.sh https://YOUR-RAILWAY-URL.up.railway.app
```

## Repo layout

```text
docs/   data/{raw,processed}   src/{ingest,rag,guardrails,api}   ui/   tests/
```

Full build order: [`docs/implementation.md`](docs/implementation.md).
