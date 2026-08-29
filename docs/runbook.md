# Operations runbook — Mutual Fund FAQ Assistant

Operational procedures for corpus refresh, the daily scheduler, and incident response.

Related: [`implementation.md`](./implementation.md) (Phase 6), [`problemStatement.md`](./problemStatement.md) (source URL allowlist).

---

## Corpus refresh (manual)

Re-fetch allowlisted scheme pages and rebuild the full index locally:

```bash
source .venv/bin/activate
python -m src.ingest.run
```

Verify retrieval probes pass:

```bash
python scripts/retrieval_probe.py
```

**Source rule:** Only URLs from `docs/problemStatement.md` may be ingested. Do not add AMC / AMFI / SEBI or other aggregator links. To add a scheme, its Reference URL must already exist in the problem statement.

### Refresh a single scheme

```bash
python -m src.ingest.run --scheme-id kotak_large_cap_direct_growth
```

### When to use `--recreate-collection`

Use only when the **embedding model** changes (e.g. `EMBEDDING_MODEL` in `.env`):

```bash
python -m src.ingest.index --recreate-collection
# or full pipeline:
python -m src.ingest.run --recreate-collection
```

Do **not** use `--recreate-collection` for routine daily refreshes.

---

## Daily scheduler (GitHub Actions)

The corpus is refreshed automatically **every day at 10:00 AM IST** (04:30 UTC) via [`.github/workflows/daily-ingest.yml`](../.github/workflows/daily-ingest.yml).

### What the workflow does

1. Checkout `main`
2. Install Python dependencies and cache the HuggingFace embedding model
3. Run ingest phases as **separate GitHub Actions steps** (each with its own log section):
   - **P1.1** `scripts/ingest/run_fetch.sh` — download scheme HTML → `data/raw/`
   - **P1.2** `scripts/ingest/run_parse.sh` — extract text/tables → `data/processed/parsed/`
   - **P1.3** `scripts/ingest/run_chunk.sh` — section-aware chunks → `data/processed/chunks/`
   - **P1.4** `scripts/ingest/run_index.sh` — embed + Chroma upsert → `data/vectorstore/`
   - **P1.5** `scripts/ingest/run_probes.sh` — retrieval smoke gate
4. Commit and push changed files under `data/raw`, `data/processed`, and `data/vectorstore` (only if there is a diff)

For local full-pipeline runs, `python -m src.ingest.run --fetch-fallback-cached` still orchestrates all phases in one command.

**No `GROQ_API_KEY` is required** — the scheduler is ingest-only.

### Manual trigger

1. Open the repo on GitHub → **Actions**
2. Select **Daily corpus ingest**
3. Click **Run workflow** (not "Re-run jobs" on an old run — that reuses the old workflow file)
4. Optionally enter a `scheme_id` to refresh one scheme only
5. Click **Run workflow**

In the job log you should see `commit_corpus_refresh.sh v3` at the start of the commit step.

### Failure handling

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Workflow fails at fetch | 403, timeout, or empty body from source | Check `data/raw/fetch_log.yaml` in the run logs; scheduler uses `--fetch-fallback-cached` to reuse committed raw HTML when indmoney blocks GitHub runner IPs |
| Workflow fails at probes | Index/chunk regression | Inspect `retrieval_probe_log.yaml` artifact in workspace; fix ingest locally, then re-run |
| Workflow succeeds, no commit | Source pages unchanged (idempotent) | Expected — corpus hashes are stable |
| Push rejected at end of run | New commit landed on `main` during ingest, or rebase conflict on `data/` | Workflow syncs to `origin/main`, rebuilds corpus commit, retries up to 10×; exits 0 if no diff after sync |
| Schedule not running | Forked repo | Scheduled workflows are disabled on forks; use the upstream repo |

Failed runs **do not push** partial or corrupt data — the job exits before the commit step.

### Notifications

GitHub sends email to watchers when a scheduled workflow fails. Configure repo **Watch → Actions** for alerts.

### Rate limits / politeness

- Fetches use `FETCH_TIMEOUT_SECONDS` (default 30s) from `.env.example`
- Schemes are fetched sequentially from `data/manifest.yaml`
- Do not increase parallelism without reviewing source-site terms

### Log readability

The ingest pipeline emits structured logs aligned with `docs/implementation.md` Phase 1 checkpoints:

```text
CORPUS MANIFEST | schemes_in_scope=7
  [1/7] Kotak Large Cap Fund – Direct Growth
         scheme_id=kotak_large_cap_direct_growth | category=Large-cap
         source_url=https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth
========================================================================
STAGE START: P1.1 FETCH — Download allowlisted scheme HTML → data/raw/
CHECKPOINT | P1.1 | fetch_url | Download scheme page for Kotak Large Cap Fund – Direct Growth | scheme_id=...
CHECKPOINT | P1.2 | parse_html | Extract text/tables for Kotak Large Cap Fund – Direct Growth | scheme_id=...
CHECKPOINT | P1.3 | chunk_sections | Build section-aware chunks for Kotak Large Cap Fund – Direct Growth | scheme_id=...
CHECKPOINT | P1.4 | load_embedding_model | Loading sentence-transformers model for vector embeddings | model=BAAI/bge-small-en-v1.5
CHECKPOINT | P1.4 | embed_and_upsert | Embed chunk.text and upsert vectors into Chroma | doc_id=... | vectors=21
CHECKPOINT | P1.4 | smoke_probes_done | Retrieval smoke probes complete | passed=35/35
STAGE DONE: P1.4 INDEX (45.2s)
```

| Phase | What the logs show |
| --- | --- |
| **P1.1 FETCH** | Which schemes are downloaded; network vs cached fallback; content hash |
| **P1.2 PARSE** | Text/table extraction; `structured_facts.yaml` update |
| **P1.3 CHUNK** | Section-aware chunk counts, facets, JSON/JSONL export |
| **P1.4 INDEX** | Embedding model load → Chroma open → per-scheme embed/upsert → 35 smoke probes |

- Set `LOG_LEVEL=DEBUG` for more detail; `WARNING` for quieter CI output
- GitHub Actions sets `HF_HUB_DISABLE_PROGRESS_BARS=1` to hide embedding model progress spam

### Corpus freshness

After a successful scheduled run, check the latest commit message:

```text
chore(ingest): daily corpus refresh YYYY-MM-DD
```

Or inspect `data/raw/fetch_log.yaml` and `data/vectorstore/index_log.yaml` for timestamps.

---

## Local clone after refresh

A fresh clone should work without re-ingesting if `data/vectorstore/` is present in `main`:

```bash
git clone <repo-url>
cd RAG-MutualFund\ Chatbot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set GROQ_API_KEY for chat only
uvicorn src.api.main:app --reload
```

If `data/vectorstore/` is missing, run `python -m src.ingest.run` once locally.
