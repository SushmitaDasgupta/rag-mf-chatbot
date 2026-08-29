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
3. Run `python -m src.ingest.run` (fetch → parse → chunk → embed → Chroma upsert)
4. Run `python scripts/retrieval_probe.py` (post-refresh smoke gate)
5. Commit and push changed files under `data/raw`, `data/processed`, and `data/vectorstore` (only if there is a diff)

**No `GROQ_API_KEY` is required** — the scheduler is ingest-only.

### Manual trigger

1. Open the repo on GitHub → **Actions**
2. Select **Daily corpus ingest**
3. Click **Run workflow**
4. Optionally enter a `scheme_id` to refresh one scheme only
5. Click **Run workflow**

### Failure handling

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Workflow fails at fetch | 403, timeout, or empty body from source | Check `data/raw/fetch_log.yaml` in the run logs; scheduler uses `--fetch-fallback-cached` to reuse committed raw HTML when indmoney blocks GitHub runner IPs |
| Workflow fails at probes | Index/chunk regression | Inspect `retrieval_probe_log.yaml` artifact in workspace; fix ingest locally, then re-run |
| Workflow succeeds, no commit | Source pages unchanged (idempotent) | Expected — corpus hashes are stable |
| Schedule not running | Forked repo | Scheduled workflows are disabled on forks; use the upstream repo |

Failed runs **do not push** partial or corrupt data — the job exits before the commit step.

### Notifications

GitHub sends email to watchers when a scheduled workflow fails. Configure repo **Watch → Actions** for alerts.

### Rate limits / politeness

- Fetches use `FETCH_TIMEOUT_SECONDS` (default 30s) from `.env.example`
- Schemes are fetched sequentially from `data/manifest.yaml`
- Do not increase parallelism without reviewing source-site terms

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
