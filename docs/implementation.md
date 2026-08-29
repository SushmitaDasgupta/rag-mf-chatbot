# Implementation Plan: Mutual Fund FAQ Assistant (Facts-Only RAG)

Phase-wise build plan derived from [`problemStatement.md`](./problemStatement.md) and [`architecture.md`](./architecture.md).

**Product goal:** A trustworthy Kotak mutual-fund FAQ assistant that answers from a curated corpus built **only** from the scheme Reference URLs in [`problemStatement.md`](./problemStatement.md), never gives investment advice, and always returns short, cited answers.

**Stack anchors (MVP):** Python API, section-aware chunking + local vector store, **Groq API** for generation (`GROQ_API_KEY`, default model **`openai/gpt-oss-120b`** — see [P2.3 generation model](#generation-model)), embeddings via **`BAAI/bge-small-en-v1.5`** (see [P1.4 embedding model selection](#embedding-model-selection-corpus-informed)), minimal chat UI.

**Source rule (normative):** Mutual-fund ingest URLs and answer citations must be exact copies of Reference links from `problemStatement.md`. Do not add AMC / AMFI / SEBI / other aggregator URLs as scheme sources.

---

## How to use this document

| Item | Guidance |
| --- | --- |
| Phase order | Complete phases in sequence; within P1–P6, complete **sub-phases** (e.g. 1.1 → 1.2 → …) in order |
| Exit criteria | A sub-phase is done only when its checklist is fully green; a parent phase is done when all its sub-phases are done |
| Definition of Done (global) | Meets [Success Criteria](#global-definition-of-done) below |
| Docs of record | Problem statement (requirements) · Architecture (design) · This file (build order) · [`eval.md`](./eval.md) · [`edge-case.md`](./edge-case.md) |

---

## Global Definition of Done

Mapped from the problem statement success criteria:

- [ ] Accurate retrieval of factual mutual fund information (golden Q&A pass rate meets target)
- [ ] Strict facts-only responses (advisory suite all refuse correctly)
- [ ] Every answer has exactly one citation equal to that scheme’s `problemStatement.md` Reference URL + `Last updated from sources: <date>`
- [ ] Advisory / comparison / return-calculation queries refused with educational link (or scheme problem-statement URL for performance)
- [ ] Minimal UI: welcome, 3 example questions, always-visible **“Facts-only. No investment advice.”**
- [ ] No collection/storage of PAN, Aadhaar, account numbers, OTPs, email, or phone
- [ ] README with setup, selected schemes, RAG overview, known limitations

---

## Phase overview

| Phase | Name | Primary outcome | Depends on |
| --- | --- | --- | --- |
| **P0** | Project bootstrap & corpus | Repo layout, 3–5 Kotak schemes, manifest URLs from problem statement only | — |
| **P1.1** | Ingestion (fetch) | Allowlisted HTML fetched + hashed under `data/raw/` | P0 |
| **P1.2** | Parsing | Clean text/tables per scheme page under `data/processed/` | P1.1 |
| **P1.3** | Chunking | Section-aware chunks + metadata (+ optional parent links) | P1.2 |
| **P1.4** | Embed, index & structured facts | Vector store + side-car facts + smoke probes | P1.3 |
| **P2.1** | Scheme resolver | Query → `scheme_id` (or clarify / unsupported) | P1.4 |
| **P2.2** | Retriever | Top-k chunks / structured short-circuit; empty-safe | P2.1 |
| **P2.3** | Groq generator | Grounded draft answers from context only | P2.2 |
| **P2.4** | Output validator | ≤3 sentences, one allowlisted citation, footer | P2.3 |
| **P2.5** | API & CLI harness | `POST /api/chat`, health, golden CLI | P2.4 |
| **P3.1** | PII gate | Block PAN/Aadhaar/account/OTP/email/phone before RAG/LLM | P2.5 |
| **P3.2** | Intent classifier | Factual / process / performance / advisory / unclear | P3.1 |
| **P3.3** | Refusal & performance paths | Templates, edu links, scheme URL for performance | P3.2 |
| **P3.4** | Guardrail integration & refusal tests | Orchestrator wiring + `refusal_cases.json` automation | P3.3 |
| **P4.1** | UI shell | Welcome, disclaimer, layout (no PII fields) | P3.4 |
| **P4.2** | Chat + examples | Chips + transcript wired to API | P4.1 |
| **P4.3** | UI E2E polish | Errors, mobile, demo paths (fact + refusal) | P4.2 |
| **P5.1** | Golden eval suite | `golden_questions.json` + runner; ≥80% format+citation | P4.3 |
| **P5.2** | Refusal eval & pytest | Full refusal/PII **100%**; unit tests wired | P5.1 |
| **P5.3** | README & refresh runbook | Setup, schemes, limitations, re-ingest steps | P5.2 |
| **P5.4** | DoD sign-off & demo script | Global DoD + 3 fact / 2 refusal demo | P5.3 |
| **P6.1** | GitHub Actions workflow scaffold | Scheduled + manual-dispatch workflow in `.github/workflows/` | P1.4, P5.3 |
| **P6.2** | Daily ingest pipeline job | Fetch → parse → chunk → embed → Chroma upsert via `src.ingest.run` | P6.1 |
| **P6.3** | Corpus artifact persistence | Commit refreshed `data/` + vectorstore; idempotent upsert verified | P6.2 |
| **P6.4** | Scheduler ops & smoke gate | Failure alerts, post-refresh probes, runbook for on-call | P6.3 |

```text
P0 Bootstrap + corpus
 └─▶ P1.1 Ingestion (fetch)
      └─▶ P1.2 Parsing
           └─▶ P1.3 Chunking
                └─▶ P1.4 Embed / index / structured facts
                     └─▶ P2.1 Scheme resolver
                          └─▶ P2.2 Retriever
                               └─▶ P2.3 Groq generator
                                    └─▶ P2.4 Output validator
                                         └─▶ P2.5 API + CLI
                                              └─▶ P3.1 PII gate
                                                   └─▶ P3.2 Intent classifier
                                                        └─▶ P3.3 Refusal / performance paths
                                                             └─▶ P3.4 Integration + refusal tests
                                                                  └─▶ P4.1 UI shell
                                                                       └─▶ P4.2 Chat + examples
                                                                            └─▶ P4.3 UI E2E polish
                                                                                 └─▶ P5.1 Golden eval
                                                                                      └─▶ P5.2 Refusal eval
                                                                                           └─▶ P5.3 README / runbook
                                                                                                └─▶ P5.4 DoD + demo
                                                                                                     └─▶ P6.1 GH Actions scaffold
                                                                                                          └─▶ P6.2 Daily ingest job
                                                                                                               └─▶ P6.3 Artifact persistence
                                                                                                                    └─▶ P6.4 Scheduler ops
```

---

## Phase 0 — Project bootstrap & corpus definition

**Goal:** Establish the repo, secrets, and a locked scheme/source manifest whose URLs are **only** those listed in [`problemStatement.md`](./problemStatement.md).

### Objectives

- Scaffold the repository per architecture layout
- Select **3–5 Kotak** schemes from the problem-statement candidate table (category diversity)
- Copy each selected scheme’s Reference URL **verbatim** into the manifest (no URL substitution)
- Decide initial stack choices that unblock coding (API + UI + vector store)

### Allowed scheme sources (from problem statement only)

Select 3–5 rows; lock them in `data/manifest.yaml` with these exact `source_url` values:

| Scheme | Category | `source_url` (copy exactly) |
| --- | --- | --- |
| Kotak Large Cap Fund – Direct Growth | Large-cap | https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth |
| Kotak Midcap Fund – Direct Growth | Mid-cap | https://www.indmoney.com/mutual-funds/kotak-midcap-fund-direct-growth |
| Kotak Arbitrage Fund – Direct Growth | Arbitrage | https://www.indmoney.com/mutual-funds/kotak-arbitrage-fund-direct-growth |
| Kotak Savings Fund – Direct Growth | Debt / savings | https://www.indmoney.com/mutual-funds/kotak-savings-fund-direct-growth |
| Kotak Gold Fund – Growth Direct | Commodity / gold | https://www.indmoney.com/mutual-funds/kotak-gold-fund-growth-direct |
| Kotak Flexicap Fund – Direct Growth | Flexi-cap | https://www.indmoney.com/mutual-funds/kotak-flexicap-fund-direct-growth |
| Kotak Liquid Fund – Growth Direct | Liquid | https://www.indmoney.com/mutual-funds/kotak-liquid-fund-growth-direct |

> **Do not** replace these with AMC / AMFI / SEBI / other aggregator links. If a URL is not in `problemStatement.md`, it must not enter the corpus or citations.

### Tasks

1. Create repo structure:

   ```text
   docs/  data/{raw,processed}  src/{ingest,rag,guardrails,api}  ui/  tests/
   ```

2. Add `.env.example` with `GROQ_API_KEY`, optional `GROQ_MODEL` (default `openai/gpt-oss-120b`), embedding/vector settings
3. Add `requirements.txt` / `pyproject.toml` (FastAPI, vector DB client, HTML parse, Groq SDK or OpenAI-compatible client)
4. Author `data/manifest.yaml`:

   - `scheme_id`, display name, category
   - `source_url` = exact Reference URL from `problemStatement.md`
   - `doc_type: scheme_reference_page`, refresh cadence
5. Optionally place an initial copy of HTML under `data/raw/` (formal fetch pipeline is **P1.1**)
6. Draft `data/processed/structured_facts.yaml` stubs for: expense ratio, exit load, min SIP, riskometer, benchmark (fill in **P1.2 / P1.4**)
7. Build citation allowlist in code as the set of problem-statement Reference URLs (full URL match, not open host)

### Deliverables

- [ ] Runnable empty project (deps install cleanly)
- [ ] Locked scheme list (3–5) documented in manifest + later README
- [ ] Manifest URLs only from problem statement
- [ ] `.env.example` documenting `GROQ_API_KEY`

### Exit criteria

- [ ] Every manifest `source_url` appears verbatim in `problemStatement.md`
- [ ] No AMC / AMFI / SEBI / other non–problem-statement scheme URLs in the manifest
- [ ] Team agrees on UI approach for P4 (Streamlit/Gradio **or** Next.js)

### Risks / notes

- Page layouts on IndMoney may change; record content hashes after fetch (P1.1) and re-run smoke tests on refresh

---

## Phase 1 — Corpus pipeline (ingestion → parse → chunk → index)

**Parent goal:** Turn **problem-statement scheme pages** into retrieval-ready chunks per [architecture §5.4 Chunking strategy](./architecture.md#54-chunking-strategy).

### Phase 1.1 — Ingestion (fetch)

**Goal:** Reliably fetch only allowlisted scheme pages into `data/raw/` with integrity metadata.

#### Tasks

1. Implement fetch module: read `data/manifest.yaml`
2. **Reject** any URL not in the problem-statement allowlist (fail closed)
3. Download HTML (or verify existing raw files) into `data/raw/`
4. Store content hash, fetch timestamp, HTTP status per `scheme_id` / `doc_id`
5. Surface clear errors on 403 / timeout / empty body (do not silent-skip)

#### Deliverables

- [ ] `src/ingest/fetch.py` (or equivalent) runnable via CLI
- [ ] Raw HTML on disk for every selected scheme
- [ ] Fetch manifest/log with hashes

#### Exit criteria

- [ ] Every fetched URL equals a problem-statement Reference URL
- [ ] Failed fetches are visible and block “success” status for that scheme
- [ ] Re-fetch updates hash when content changes

---

### Phase 1.2 — Parsing

**Goal:** Extract usable text and tables from fetched HTML; strip chrome.

#### Tasks

1. Parse HTML → main content text
2. Detect and extract tables (expense ratio, exit load, SIP, etc.)
3. Serialize tables to stable text rows (no mid-cell splits later)
4. Strip nav, ads, cookie banners, unrelated fund widgets
5. Write per-scheme parse artifacts under `data/processed/parsed/`
6. Draft/update structured fact candidates from obvious labeled fields (finalize in P1.4)

#### Deliverables

- [ ] `src/ingest/parse.py` (or equivalent)
- [ ] Parsed text + table serializations per scheme
- [ ] Spot-check notes for fee/load tables

#### Exit criteria

- [ ] Each selected scheme has a non-empty parse artifact
- [ ] Fee/load tables readable as stable text (or explicitly flagged for manual override)
- [ ] No dependence on non-allowlisted URLs during parse

---

### Phase 1.3 — Chunking

**Goal:** Emit section-aware chunks with full metadata (not yet embedded), tuned to the **actual** Phase 1.2 artifacts under `data/processed/`.

#### What the processed corpus looks like (evidence)

Observed across all 7 schemes after parse (`data/processed/parsed/*.json` + `structured_facts.yaml`):

| Signal | Observation | Implication for chunking |
| --- | --- | --- |
| Parse source | Almost entirely `__NEXT_DATA__` (`parse_source: next_data`) | Chunk from structured `sections[]` / `tables[]`, not raw HTML |
| Doc size | ~700–1000 words of `main_text` per scheme | Whole documents are tiny; sliding windows add noise, not value |
| Section length | ~112 sections total; median ~24 words; max ~300 words | Default “400–700 token” targets rarely apply; most units are already sub-target |
| Structure | Stable pattern: Overview → Riskometer → About/Key Parameters → Taxation/Objective/Min investment → FAQs → Holdings tables | Hierarchy is **facet/label**, not SID/KIM chapter trees |
| Fee/load table | `fund_overview_info` is a **9-row** `Field \| Value` KV table on every scheme | Keep table atomic **and** emit per-row facet chunks (headers repeated) |
| Facet hints | Strong coverage: expense, exit load, SIP/investment, lock-in, riskometer, benchmark; some FAQs for process | Prefer one primary `facet` per chunk; use parse `facet_hints` as seeds |
| Side-car | `structured_facts.yaml` already holds expense / exit / SIP / risk / benchmark candidates | Chunking complements exact lookup; does not replace the side-car |

**Do not** treat this corpus like a multi-page SID/factsheet PDF. Chunking must optimize for **precise single-facet retrieval** on short IndMoney scheme pages.

#### Corpus-informed chunking strategy

```text
data/processed/parsed/<scheme_id>.json
        │
        ├─ tables[kind=overview_kv]     ──▶  (A) whole-table parent chunk
        │                                   ──▶  (B) one child chunk per fee/load/SIP/benchmark/lock-in row
        │
        ├─ tables[kind=holdings]        ──▶  (C) one chunk per holdings table (≤15 rows already)
        │
        ├─ sections[] (non-FAQ)         ──▶  (D) one chunk per section if ≥ min size;
        │                                   else merge with next sibling under same parent theme
        │
        └─ sections[] heading startswith FAQ:
                                        ──▶  (E) one chunk per FAQ (Q + A kept together)

Every emitted chunk also inherits:
  scheme_id, scheme_name, doc_type=scheme_reference_page,
  source_url (exact problem-statement URL), effective_date (as_of_date / last_updated),
  ingested_at, section, facet, parent_id, chunk_id
```

##### A / B — Overview KV table (highest leverage)

Rationale: FAQ queries (“What is the expense ratio?”, “What is the exit load?”) map 1:1 to a single overview row. A single multi-facet overview chunk still helps the LLM, but **row-level children** improve dense retrieval so “exit load” does not compete with “benchmark” inside one embedding.

Rules:

1. Serialize already stable from parse (`Field | Value` lines) — **never** re-split mid-cell.
2. Emit **parent** chunk = full overview table + header prefix (usually ≪ hard max).
3. Emit **child** chunks = one row each for labels matching core facets, repeating headers:

   ```text
   Field | Value
   Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
   ```

4. Map labels → `facet`: Expense ratio → `expense_ratio`; Exit Load → `exit_load`; Min Lumpsum/SIP → `min_sip` (+ `min_investment`); Benchmark → `benchmark`; Lock In → `lock_in`; Riskometer table → `riskometer`.
5. Non-core rows (AUM, Inception, TurnOver) may stay **parent-only** unless eval shows need.

##### C — Holdings tables

Rationale: Holdings support “top holdings” FAQs but are not core compliance facets. Keep each holdings table as **one chunk** (already capped at ~15 rows in parse). Do not row-split unless a table exceeds hard max (unexpected for MVP).

##### D — Prose sections (About, Key Parameters, Taxation, Objective, Min investment)

Rationale: Median section is ~24 words — below a useful embedding floor if emitted alone without scheme context. Always prepend scheme/doc/section prefixes. Merge only when a section is near-empty **and** adjacent sibling shares the same theme; **never** merge across different facet-bearing sections (e.g. do not merge Taxation into Minimum Investment).

##### E — FAQ sections

Rationale: Parse already emits `FAQ: <question>` headings with short answers (often the same facts as the overview). Keep **one chunk per FAQ** (question + answer). Tag `facet` from `facet_hints` when present (expense / exit load FAQs are especially valuable as retrieval paraphrases).

#### Size / overlap defaults (revised for this corpus)

| Parameter | Prior generic default | **Revised for `data/processed/`** | Rationale |
| --- | --- | --- | --- |
| Target size | 400–700 tokens | **80–250 tokens** for facet/FAQ/row chunks; parent overview may be larger but still small | Matches observed section lengths; oversized targets forced pointless merges |
| Hard max | 1024 tokens | **512 tokens** | Entire scheme `main_text` is ~1k words; no chunk should approach a full page |
| Hard min | 80 tokens | **40 tokens** of body **or** any chunk with a core `facet` tag | Riskometer / single-row facts are legitimately short; prefixes add recall |
| Overlap | 50–80 within long sections | **0 by default**; 20–40 only if a prose section exceeds hard max | Almost no section needs splitting today |
| Separators | Heading → para → sentence | **Table row → section heading → paragraph → sentence** | Tables are the primary fact carriers |
| Prefix | `[Scheme]`, `[Doc]`, `[Section]` | Required on every chunk | Short bodies omit the scheme name; user queries usually include it |

**Header prefix example:**

```text
[Scheme: Kotak Large Cap Fund – Direct Growth]
[Doc: scheme_reference_page | Section: Fund Overview | Facet: exit_load]
Field | Value
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
```

#### Relationship to `structured_facts.yaml`

Chunking and the side-car are **complementary**:

- **Side-car** (`data/processed/structured_facts.yaml`): exact lookup / short-circuit for expense ratio, exit load, min SIP, riskometer, benchmark (same `source_url`).
- **Chunks**: semantic retrieval for paraphrases, FAQs, taxation/process wording, and holdings.

Do not drop facet chunks just because the side-car is filled — retrieval eval and “explain in one sentence” answers still need grounded text.

#### What not to chunk

- Peer-comparison / ranking widgets (already excluded or down-ranked at parse)
- Cookie/nav/app-promo chrome (stripped at parse)
- Any text whose `source_url` is not an exact `problemStatement.md` Reference URL
- Duplicate near-identical bodies: if FAQ answer equals overview row text, keep **both** only when wording differs enough to help paraphrase recall; otherwise keep overview row + one FAQ, drop exact dupes by hash

#### Tasks

1. Implement section-aware hierarchical chunker over **parsed JSON** (not naive sliding window on `main_text`)
2. Apply the **revised** size/overlap table above
3. Implement overview parent + per-row facet children; holdings whole-table; FAQ one-shot; prose section rules
4. Attach metadata: `scheme_id`, `scheme_name`, `doc_type=scheme_reference_page`, `source_url` (problem-statement URL), `effective_date`, `ingested_at`, `section`, `facet`, `parent_id`, `chunk_id`
5. Tag facets: `expense_ratio`, `exit_load`, `min_sip`, `min_investment`, `lock_in`, `riskometer`, `benchmark`, `process_statements` (seed from parse `facet_hints` + label map)
6. Export inspectable chunks to `data/processed/chunks/` (JSON/JSONL per scheme) + brief chunk QC notes

#### Deliverables

- [ ] `src/ingest/chunk.py` (or equivalent)
- [ ] Chunk JSON/JSONL export per scheme under `data/processed/chunks/`
- [ ] Quality gate: drop empty chunks; fail if `source_url` missing / not allowlisted
- [ ] Spot-check: overview fee/load rows intact (no mid-cell splits); each scheme has facet coverage or explicit absence

#### Exit criteria

- [ ] Every chunk `source_url` is an exact problem-statement Reference URL
- [ ] Core facets tagged where present in parse/side-car (or marked absent for smoke later)
- [ ] Manual spot-check: expense ratio / exit load table rows not split mid-cell
- [ ] No embedding/index required yet to pass this sub-phase
- [ ] Chunk sizes reflect revised defaults (most chunks ≪ 512 tokens)

---

### Phase 1.4 — Embed, index & structured facts

**Goal:** Make chunks retrievable; lock high-precision side-car facts. Index design must match the **retrieval strategy** in [P2.2](#phase-22--retriever) (tiered hybrid, not naive top-k dense search).

#### Corpus snapshot (post–P1.3, `data/processed/`)

| Artifact | Count / shape | Retrieval role |
| --- | --- | --- |
| `chunks/*.json(l)` | **148** chunks, 7 schemes (~19–23 / scheme) | Semantic + metadata-filtered search |
| `structured_facts.yaml` | **5/5** core facets filled per scheme | Tier-0 exact short-circuit |
| `parsed/*.json` | 7 scheme pages (~700–1000 words each) | Source of truth for re-chunk; not queried directly |
| Avg chunk size | **~54 tokens** (p50 48, max 315) | Tiny index — precision > recall breadth |
| Chunk kinds | `overview_row` (35), `faq` (55), `prose` (35), `overview_parent` (7), `riskometer` (7), `holdings` (9) | Kind-based ranking is primary signal |

#### Indexing rules (aligned with retrieval)

1. **Embed field:** use full `chunk.text` (includes `[Scheme]` / `[Doc]` / `[Section]` prefix), not `body` alone — prefixes carry scheme name for user queries.
2. **Store metadata on every vector:** `chunk_id`, `doc_id`, `scheme_id`, `source_url`, `effective_date`, `section`, `facet`, `facets[]`, `kind`, `parent_id`, `content_hash`.
3. **Idempotent upsert:** delete all vectors for `doc_id` before re-insert on refresh.
4. **Do not embed duplicates:** if `content_hash` collides within a scheme, keep highest-priority `kind` (`overview_row` > `riskometer` > `faq` > `prose` > `overview_parent` > `holdings`).
5. **Optional index slimming:** `overview_parent` may be indexed with `index_for_search: false` and retrieved only via `parent_id` expansion (see P2.2) — reduces redundant hits against row children.
6. **Structured facts:** treat `structured_facts.yaml` as a **parallel lookup table** (not embedded). Values already match `overview_row` bodies; used for Tier-0 answers.

#### Embedding model selection (corpus-informed)

Profiled on indexed `data/processed/chunks/` (141 searchable vectors after excluding `overview_parent`; 148 total chunks).

##### Corpus traits that drive model choice

| Trait | Observed | Implication for embeddings |
| --- | --- | --- |
| Corpus size | **148 chunks**, ~8k tokens total | Any small English model works; no need for large/API embeddings |
| Chunk length | p50 **48 words**, avg **54**, max **315** | Short-text retrievers outperform long-document models |
| Language | **English** + `₹` / `INR` (274 non-ASCII chars) | English models suffice; multilingual models add cost without benefit |
| Text shape | Mix of `Field \| Value` table rows, FAQ Q&A, prose | NL queries (“What is the expense ratio?”) are **semantically distant** from `overview_row` table rows |
| Lexical overlap | FAQ ↔ query **~0.48**; `overview_row` ↔ query **~0.16** | Dense search helps FAQ paraphrases; metadata routing must lead for table rows |
| Prefixes | **148/148** chunks include `[Scheme: …]` / `[Doc: …]` headers | Embed full `chunk.text` — prefixes carry scheme name for user queries |
| Retrieval role | Dense is **Tier 3 tie-breaker** only (after structured facts + kind/facet routing) | Model quality matters less than routing; upgrade is optional |

##### Model comparison (probe set: 35 queries, scheme-filtered pure dense)

Benchmark on the P1.4 probe queries (7 schemes × 5 core facets), **without** Tier-2 routing — measures raw semantic matching only:

| Model | Dims | Index size (141 vecs) | Pure-dense top-1 | Pure-dense top-3 | Tiered hybrid top-1 (P1.4 probes) |
| --- | --- | --- | --- | --- | --- |
| `BAAI/bge-small-en-v1.5` **(current)** | 384 | ~0.2 MB | **46%** (16/35) | 100% | **100%** (35/35) |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~0.2 MB | **34%** (12/35) | 100% | 100% (prior index) |
| `sentence-transformers/all-mpnet-base-v2` | 768 | ~0.4 MB | **69%** (24/35) | 100% | not benchmarked |

> **Key insight:** Pure dense search still mis-ranks most queries — **tiered routing recovers 100%**. `bge-small-en-v1.5` improves raw semantic matching (+12pp top-1 vs MiniLM) for Tier-3 tie-breaks; it does **not** replace metadata routing.

##### Recommendation

| Priority | Model | When to use |
| --- | --- | --- |
| **Default (MVP)** | `BAAI/bge-small-en-v1.5` | **Active** — indexed in `data/vectorstore/`; retrieval-tuned; 384-dim; 35/35 tiered probes pass |
| **Prior baseline** | `sentence-transformers/all-MiniLM-L6-v2` | Superseded; faster but weaker pure-dense matching |
| **Upgrade candidate** | `sentence-transformers/all-mpnet-base-v2` | Only if P2.2 eval shows Tier-3 failures after BGE (+23pp pure-dense vs BGE, but 2× index size) |
| **Not recommended** | `bge-large`, `e5-large`, OpenAI/Cohere API embeddings | Overkill for 148 chunks; adds latency/cost with no gain when Tier-0/2 routing leads |

**Normative default:** **`BAAI/bge-small-en-v1.5`** with BGE instruction prefixes (implemented in `src/rag/embeddings.py`). Switching models requires full re-index: `python -m src.ingest.index --recreate-collection`.

**Embedding settings (BGE):**

- Model: `BAAI/bge-small-en-v1.5` (`EMBEDDING_MODEL` in `.env`)
- Embed field: full `chunk.text` (includes scheme/doc/section prefix)
- **Query prefix:** `Represent this sentence for searching relevant passages: …`
- **Document prefix:** `Represent this document for retrieval: …`
- Similarity: cosine (`normalize_embeddings=True`)
- Implementation: `src/rag/embeddings.py` → `SentenceTransformerEmbedding` (used by index + P2.2 retriever)
- `overview_parent` chunks: stored but `index_for_search=false` — excluded from dense search

#### Tasks

1. Embed chunks; upsert into Chroma or FAISS (MVP local) with metadata above
2. Idempotent re-ingest: replace all chunks for a `doc_id` on refresh (no duplicates)
3. Finalize `data/processed/structured_facts.yaml` (already populated from P1.2; allow manual overrides)
4. Allow manual overrides when parse is wrong (still same citation URL)
5. **Smoke probes** (feeds P2.2): for each scheme × core facet, assert Tier-0 fact exists **and** Tier-2 retrieval returns `overview_row` or `riskometer` in top-3
6. Wire `python -m src.ingest.run` end-to-end (fetch → parse → chunk → index)

#### Deliverables

- [x] Populated vector store under a known path / collection name (`data/vectorstore/`, collection `mutual_fund_chunks`)
- [x] Filled structured facts for core facets where present
- [x] Full ingest CLI pipeline (`python -m src.ingest.run`)
- [x] `data/processed/chunks/retrieval_probe_log.yaml` from smoke probes
- [x] `data/processed/structured_facts_report.yaml` from index validation (Tier-0 facet audit)

#### Manual overrides (`structured_facts.yaml`)

When parse output is wrong, set a field value **and** its override flag (same `source_url` required):

```yaml
schemes:
  kotak_large_cap_direct_growth:
    source_url: https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth
    expense_ratio: 0.70%
    manual_override_expense_ratio: true
```

Re-running `python -m src.ingest.parse` preserves `manual_override_*` fields; non-overridden fields are refreshed from parse.

#### Exit criteria

- [x] Re-running ingest for one doc does not duplicate chunks (verified: 148 vectors after single-scheme re-index)
- [x] Core facets present for each selected scheme **or** explicitly marked “not in corpus” (7/7 schemes; Liquid `min_sip` = `--`)
- [x] Smoke probe log saved (feeds later eval L0/L1)
- [x] Probe: `scheme_id` filter prevents cross-scheme leakage on all test queries (35/35 pass)

#### Risks / notes (Phase 1)

- Poor HTML/table extraction → manual override rows in structured facts (expected for MVP); overrides must still cite the problem-statement URL
- **Facet tag noise on `prose` chunks** (e.g. `expense_ratio` on Taxation/Holdings sections) — index metadata as-is but retrieval must **down-rank prose** for core facet queries (P2.2)

---

## Phase 2 — RAG core (retrieve → Groq → validate → API)

**Parent goal:** Produce compliant factual answers from retrieved context using **Groq**, with deterministic output validation.

### Phase 2.1 — Scheme resolver

**Goal:** Map user text to a supported `scheme_id` or ask to clarify.

#### Tasks

1. Alias table for selected scheme display names / short forms
2. Resolve unique matches to `scheme_id`
3. On ambiguity → return `clarify` with candidate list
4. On unknown / other AMC → mark unsupported (full refusal copy comes in P3)

#### Deliverables

- [ ] `src/rag/scheme_resolver.py` (or equivalent)
- [ ] Unit tests for aliases, typos (best-effort), multi-match

#### Exit criteria

- [ ] Each manifest scheme resolves from its canonical name
- [ ] Ambiguous queries do not silently pick the wrong scheme

---

### Phase 2.2 — Retriever

**Goal:** Return grounded context chunks (and structured facts) without hallucination on misses. Strategy is **evidence-based** on the indexed `data/processed/` corpus — not generic “dense top-k RAG”.

> **Design record:** Corpus was profiled after P1.4 indexing (148 chunks, 7 schemes, 35 smoke probes). Findings below are normative for `src/rag/retrieve.py`.

#### Empirical analysis of `data/processed/` (post P1.4)

| Signal | Observed value | Retrieval implication |
| --- | --- | --- |
| Total index size | **148 chunks**, ~8k tokens corpus-wide | Metadata routing must lead; dense search is a tie-breaker only |
| Chunk kinds | `faq` 55 · `overview_row` 35 · `prose` 35 · `holdings` 9 · `overview_parent` 7 · `riskometer` 7 | `kind` is the primary rank signal |
| Token size | p50 **48**, avg **54**, max **315** | Return 1–3 chunks max; parent expand stays under ~200 tokens |
| Null `facet` | **60/148** chunks (FAQs without facet, holdings, parents) | Never rely on `facet` alone — combine with `kind` + section |
| Core facet coverage | **7/7** schemes have all 5 core facets in chunks + `structured_facts.yaml` | Tier-0 short-circuit is always available for fee/load/SIP/risk/benchmark |
| `overview_row` oracle | Expense, exit, min SIP, benchmark, lock-in: **7/7** schemes each have `kind=overview_row` | Deterministic hit for numeric facet queries |
| `riskometer` kind | **7/7** dedicated `kind=riskometer` chunks (avg ~30 tokens) | Route risk queries to `kind=riskometer`, not `kind=prose` |
| Prose facet noise | **31** `kind=prose` chunks tagged with core facets (Taxation, Holdings, Key Parameters) | **Exclude `kind=prose`** for core numeric facets when any `overview_row` exists |
| FAQ paraphrases | 13 expense + 6 exit-load FAQs; values sometimes **rounded** vs overview (e.g. Arbitrage TER 2.3734% row vs 2.37% FAQ) | Prefer `structured_facts` + `overview_row` over FAQ for numeric answers |
| FAQ off-topic | 7× “return on fund”, 7× NAV, 7× AUM, 7× fund manager per scheme | Route returns → P3 performance refusal; do not retrieve for factual fee queries |
| Holdings tables | **9** chunks across **5/7** schemes (no holdings chunk for Liquid, Savings) | Holdings intent: FAQ “top holdings” first; `kind=holdings` when present |
| `process_statements` | Tagged only on Taxation `prose` (6 schemes) — no real download copy | Expect `not_in_corpus` for statement-download queries |
| Content-hash collisions | **0** within scheme | Dedup at index time is defensive; routing is the real precision lever |
| Smoke probes (P1.4) | **35/35 pass** (7 schemes × 5 facets); top-1 kind: **28 `overview_row`**, **7 `riskometer`** | Validates Tier-2 routing; implement retriever to match probe logic |

#### Recommended strategy: tiered hybrid (not pure dense RAG)

**Best approach for this corpus:** a **6-tier pipeline** where dense embedding is the *third* signal, not the first.

| Tier | What | Why for this corpus |
| --- | --- | --- |
| **0** | `structured_facts.yaml` lookup | Exact values for 5 core facets; beats FAQ rounding; no LLM needed for the number |
| **1** | Hard `scheme_id` filter | Mandatory — 148 chunks across 7 schemes; prevents cross-scheme leak (proven in probes) |
| **2** | `kind` + `facet` routing | `overview_row` / `riskometer` are oracle chunks; prose has 31 false-positive facet tags |
| **3** | Dense re-rank (within Tier-2 candidates) | Corpus is tiny; re-rank only when multiple candidates survive Tier 2; model: `BAAI/bge-small-en-v1.5` |
| **4** | BM25 tie-break on FAQ `section` heading | Helps natural-language phrasing (“what is the exit load”) reach FAQ when row missed |
| **5** | Parent expand (`overview_parent` via `parent_id`) | Child row ≈30 tokens; parent table ≈99 tokens — add parent for LLM context only |

**Skip dense search when:** Tier 2 yields exactly one `overview_row` (or `riskometer`) matching the intent facet — return it directly (+ Tier-0 fact). This covers the common case (28/35 probes hit `overview_row` at rank 1 without needing semantic tie-break).

**Do not use:** global top-k dense search across all 148 chunks; BM25-only; or trusting `facet` metadata on `kind=prose`.

#### Why not pure dense retrieval?

Analysis of `data/processed/chunks/` (148 chunks, 7 schemes):

| Finding | Implication |
| --- | --- |
| Corpus is **tiny** (~54 tokens/chunk avg; whole index ≈ 8k tokens) | Semantic search alone is fragile; metadata routing must lead |
| **5/5 core facets** populated in `structured_facts.yaml` for every scheme | Tier-0 exact lookup beats embedding for expense / exit / SIP / risk / benchmark |
| **`overview_row` is the oracle chunk** for expense, exit, min SIP, benchmark, lock-in (7/7 schemes each) | Facet + `kind` filter should win before vector score |
| **`riskometer` kind** beats duplicate prose section for risk queries | Prefer `kind=riskometer` over `kind=prose` when facet is `riskometer` |
| **55 FAQ chunks** — 13 expense + 6 exit-load tagged; rest are NAV/AUM/returns/manager | FAQs are paraphrase fallback only; **7 “returns” FAQs must route to refusal** |
| **FAQ value drift** — rounded TER (2.37% vs 2.3734%), exit load (0.25% vs 0.2%) | Canonical source: `structured_facts` → `overview_row` → FAQ (never FAQ alone for numbers) |
| **Facet noise on prose** — 31 chunks: `expense_ratio` on Taxation, Holdings, Key Parameters | Never trust `facet` alone on `kind=prose`; exclude for core facet intents |
| **Holdings** — 9 table chunks on 5/7 schemes; FAQ “top holdings” on all 7 | Route holdings intent to FAQ + `kind=holdings`; Savings/Liquid have FAQ only |
| **`process_statements`** — Taxation prose only; no download instructions | Expect `not_in_corpus`; do not invent AMFI/AMC links |
| **Liquid `min_sip: "--"`** in structured facts | Tier-0 present but value absent — fall back to `overview_row` Min Lumpsum/SIP or `min_lumpsum: ₹1,000` |
| Parent expand: `overview_row` ≈ 28–42 tokens → parent `overview_parent` ≈ 99 tokens | Retrieve child, **expand parent** for LLM context only |
| P1.4 probes: **35/35 pass**, 0 cross-scheme leaks | Retriever must mirror probe logic in `src/ingest/index.py` |

**Conclusion:** Use a **tiered hybrid retriever** — structured short-circuit → metadata facet/kind routing → dense re-rank → parent expand. Pure vector top-k across all 148 chunks will mis-rank on facet noise and cross-kind redundancy.

#### Canonical answer source priority (normative)

When multiple chunks contain the same fact, use this precedence for the **answer value** (all still cite the same `source_url`):

```text
1. structured_facts.yaml[scheme_id][facet]     ← Tier-0 (exact; handles overview table wording)
2. kind=overview_row + matching facet          ← Tier-2 oracle chunk
3. kind=riskometer (for riskometer facet only)
4. kind=faq with matching facet / heading      ← paraphrase; may be rounded
5. kind=prose (Minimum Investment, Taxation) ← narrative only; never for numeric TER/exit
6. miss → not_in_corpus
```

#### Recommended retrieval pipeline

```text
User query
    │
    ▼
[P2.1] scheme_id resolved? ──no──▶ clarify / unsupported
    │ yes
    ▼
[P3.2] intent + facet label (expense_ratio | exit_load | min_sip | …)
    │
    ▼
┌─ Tier 0: Structured fact short-circuit ─────────────────────────────┐
│ If facet ∈ {expense_ratio, exit_load, min_sip, riskometer, benchmark} │
│ AND structured_facts[scheme_id][facet] is non-null/non-sentinel:       │
│   → attach fact value + source_url + last_updated                      │
│   → still fetch 1 grounding chunk (overview_row or riskometer) below   │
│   → if value is "--" (Liquid min_sip): treat as absent; use row/prose  │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 1: Hard filter ───────────────────────────────────────────────┐
│   scheme_id = resolved scheme (mandatory — prevents cross-scheme leak) │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 2: Facet + kind routing (primary ranker) ─────────────────────┐
│   If facet known, prefer chunks in this order:                       │
│     expense_ratio | exit_load | min_sip | benchmark | lock_in        │
│       → kind=overview_row AND facet matches                          │
│     riskometer → kind=riskometer (then overview_row if missing)      │
│     holdings   → kind=faq (heading ∋ "holdings") then kind=holdings  │
│     taxation / general process → kind=prose, section ∋ Taxation      │
│     paraphrase / unclear facet → kind=faq then overview_row          │
│   Exclude for core facets: kind=prose unless no candidate remains      │
│   Skip Tier 3 dense if exactly 1 overview_row/riskometer candidate   │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 3: Dense semantic re-rank (within filtered set) ──────────────┐
│   Embed query; score candidates from Tier 2 (or all scheme chunks    │
│   if facet unknown). Model: `BAAI/bge-small-en-v1.5` (see P1.4 / `src/rag/embeddings.py`). │
│   top_k = 3 (max 4) — corpus is small; more adds noise               │
│   Use normalize_embeddings=True (cosine). Re-index if model changes. │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 4: Optional BM25 tie-break ────────────────────────────────────┐
│   Lightweight keyword boost for FAQ questions (exact phrase match    │
│   on section heading). Helps "what is the exit load" → FAQ chunk.    │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 5: Parent expand (generation context only) ───────────────────┐
│   If top hit is overview_row with parent_id → also pass parent       │
│   overview_parent text to generator (not a second citation).         │
└──────────────────────────────────────────────────────────────────────┘
    │
    ▼
Empty after Tier 2+3? → signal not_in_corpus (no fabricated fees)
```

#### Facet → chunk kind routing table (normative for MVP)

| User intent / `facet` | Primary chunk `kind` | Fallback | Structured fact? |
| --- | --- | --- | --- |
| `expense_ratio` | `overview_row` | `faq` (expense FAQ) | **Yes** — Tier 0 |
| `exit_load` | `overview_row` | `faq` (exit load FAQ) | **Yes** |
| `min_sip` / `min_investment` | `overview_row` (Min Lumpsum/SIP row) | prose “Minimum Investment…” | **Yes** (min_sip; Liquid `--` → row/prose) |
| `benchmark` | `overview_row` | — | **Yes** |
| `riskometer` | `riskometer` | `overview_row` if ever missing | **Yes** |
| `lock_in` | `overview_row` | prose “Minimum Investment…” | Side-car `lock_in` (optional) |
| holdings / top holdings | `faq` (heading ∋ "holdings") | `kind=holdings` then prose “Holdings” | No |
| taxation | `prose` (Taxation section) | — | No |
| `process_statements` | — (weak corpus) | Taxation prose only | **No** — likely `not_in_corpus` |

#### Scoring weights (starting point for implementation)

When multiple candidates survive Tier 2 filter, combine:

| Signal | Weight | Notes |
| --- | --- | --- |
| `kind` matches routing table primary | +3.0 | Dominant signal |
| `facet` metadata equals intent facet | +2.0 | Ignore on `kind=prose` for core facets unless no other hit |
| Dense cosine similarity | +1.0 × score | Re-rank only within scheme |
| FAQ heading contains query noun | +0.5 | e.g. “exit load” in section |
| `kind=overview_parent` | −1.0 | Prefer row children unless user asks broadly (“fund details”) |
| `kind=prose` + core facet intent | −2.0 | Mitigates Taxation/Holdings false facet tags |

#### Context bundle passed to generator

Return a single structured payload, e.g.:

```json
{
  "scheme_id": "kotak_large_cap_direct_growth",
  "source_url": "https://www.indmoney.com/mutual-funds/kotak-large-cap-fund-direct-growth",
  "effective_date": "26 Aug 2026",
  "structured_fact": { "facet": "exit_load", "value": "1.0% — Exit Load of 1% if redeemed in 0-1 Years" },
  "chunks": [
    { "chunk_id": "…", "kind": "overview_row", "text": "…" },
    { "chunk_id": "…", "kind": "overview_parent", "text": "…", "expanded_from_parent": true }
  ],
  "retrieval_status": "hit"
}
```

For `not_in_corpus`: `chunks: []`, `structured_fact: null`, `retrieval_status: "miss"` — generator must not run (or returns fixed template in P2.3).

#### Known corpus gaps (set expectations in eval)

| Query type | Expected retrieval behaviour |
| --- | --- |
| “How do I download account statement / capital gains?” | **Miss** — Taxation prose mentions tax rules, not download steps |
| “How do I invest?” (FAQ exists) | FAQ hit but answer is generic IndMoney CTA — facts-only, no advice depth |
| “What was the 3Y return?” / “return on fund” FAQ | **Refusal path** (P3) — 7 per-scheme “return on fund” FAQs exist but must not be used for performance answers |
| Kotak Liquid minimum SIP | `structured_facts.min_sip = "--"`; use `overview_row` Min Lumpsum/SIP (`₹1,000/--`) or `min_lumpsum` |
| Top holdings (Liquid, Savings) | No `kind=holdings` chunk — FAQ “top holdings” only |
| Cross-scheme compare | **Refusal** — never retrieve multiple `scheme_id`s |

#### P1.4 probe baseline (implementation reference)

Smoke probes in `data/processed/chunks/retrieval_probe_log.yaml` validate the Tier-2 strategy before P2.2 is coded:

| Metric | Result |
| --- | --- |
| Probes run | 35 (7 schemes × 5 core facets) |
| Pass rate | **100%** (35/35) |
| Top-1 kind | `overview_row` 28 · `riskometer` 7 |
| Cross-scheme leak | **0** |
| Implementation | Mirror `probe_retrieve()` in `src/ingest/index.py` |

P2.2 retriever should produce ≥ **95%** top-1 `overview_row` / `riskometer` on the same probe set.

#### Tasks

1. Implement tiered pipeline in `src/rag/retrieve.py` (Tiers 0–5 above)
2. **Mandatory** `scheme_id` metadata filter after resolver
3. Load `structured_facts.yaml` for Tier 0; load chunk metadata from vector store + `data/processed/chunks/` side index
4. Dense re-rank with `top_k = 3` (cap 4); optional BM25 on FAQ headings
5. Parent expand for `overview_row` hits
6. Empty / miss path: `retrieval_status: miss` — no invented fees
7. Probe script: golden facet queries per scheme; log kind + chunk_id of top hit

#### Deliverables

- [ ] `src/rag/retrieve.py` (or equivalent) — implement tiers 0–5 above; reuse probe logic from `src/ingest/index.py`
- [ ] `scripts/retrieval_probe.py` (or extend P1.4 probe runner for eval)
- [ ] Probe log showing `overview_row` / `riskometer` in top-3 for all core facets × 7 schemes (baseline: **35/35** in `retrieval_probe_log.yaml`)

#### Exit criteria

- [ ] Scheme filter prevents cross-scheme chunk leakage on probe set
- [ ] Core facet probes: ≥ **95%** top-1 is `overview_row` or `riskometer` (as appropriate)
- [ ] Tier 0 structured fact returns correct value for all 7 schemes × 5 core facets
- [ ] Empty retrieval returns explicit `miss` (no fabricated fees)
- [ ] `process_statements` probes return `miss` or flagged weak hit (documented, not silent wrong answer)

---

### Phase 2.3 — Groq generator

**Goal:** Draft facts-only answers strictly from provided context.

#### Generation model

Groq-hosted instruct model for grounded answer drafting. **`llama-3.3-70b-versatile` is decommissioned** — do not use.

| Priority | Model | When to use |
| --- | --- | --- |
| **Default (MVP)** | `openai/gpt-oss-120b` | **Active** — facts-only generation via Groq; low temperature (`0–0.2`) |
| **Prior default** | `llama-3.3-70b-versatile` | Decommissioned on Groq |

**Normative default:** **`openai/gpt-oss-120b`** (`GROQ_MODEL` in `.env`, fallback in `src/config.py`). Implementation: `src/rag/generate.py`.

**Generation settings:**

- Model: `openai/gpt-oss-120b` (`GROQ_MODEL` in `.env`)
- Client: Groq OpenAI-compatible chat completions (`GROQ_API_KEY`)
- Temperature: `0–0.2` (facts-only; minimize hallucination)
- `max_tokens`: 256 (≤3 sentences enforced downstream by validator)

#### Tasks

1. Groq client (OpenAI-compatible): `GROQ_API_KEY`, `GROQ_MODEL` (`openai/gpt-oss-120b`), temperature `0–0.2`
2. System prompt: answer **only** from context; ≤3 sentences; no advice; do not invent URLs
3. Orchestrator injects `citation_url` + `last_updated` from metadata (problem-statement URL only)
4. Skip generation when retrieval miss is already decided (optional: short fixed template instead)

#### Deliverables

- [ ] `src/rag/generate.py` (or equivalent)
- [ ] Local smoke call with `.env` key (never commit secrets)

#### Exit criteria

- [ ] Live Groq call succeeds for a sample grounded prompt
- [ ] Prompt/context path does not require user PII

---

### Phase 2.4 — Output validator

**Goal:** Enforce the normative response contract before returning to callers.

#### Response contract

**Answer:** ≤3 sentences + exactly one problem-statement citation + last-updated footer  
**Disclaimer string:** `Facts-only. No investment advice.`

#### Tasks

1. Sentence count ≤ 3 (ignore/strip footer when counting)
2. Exactly one citation; must match allowlist (overwrite with metadata URL if model drifts)
3. Ensure footer: `Last updated from sources: YYYY-MM-DD`
4. Ban advisory phrases → regenerate once or refuse
5. Unit tests for missing citation, extra URLs, missing footer, ban phrases

#### Deliverables

- [ ] `src/rag/validate.py` (or equivalent)
- [ ] `tests/test_validator.py`

#### Exit criteria

- [ ] Validator repairs or rejects non-compliant drafts in unit tests
- [ ] Non-allowlisted URLs never leave the validator as final citations

---

### Phase 2.5 — API & CLI harness

**Goal:** Expose chat over HTTP and support golden runs without UI.

#### Tasks

1. `POST /api/chat` → `{ type, text, citation_url, last_updated_from_sources, disclaimer }`
2. `GET /api/health`
3. Wire resolver → retrieve → generate → validate
4. CLI harness for an initial `tests/golden_questions.json` smoke set

#### Deliverables

- [ ] `src/api/` chat + health
- [ ] Initial golden JSON + CLI runner
- [ ] Sample factual questions succeed end-to-end for each scheme

#### Exit criteria

- [ ] Citations on sample answers equal problem-statement Reference URLs
- [ ] Empty-corpus style queries do not hallucinate fees or loads
- [ ] Health endpoint reports dependency readiness (e.g. index loaded)

#### Risks / notes (Phase 2)

- Keep prompts and retrieved context free of any user PII (hard block in P3.1)

---

## Phase 3 — Guardrails & refusal handling

**Parent goal:** Compliance by construction — block sensitive inputs and refuse non-factual intents per problem statement.

### Phase 3.1 — PII gate

**Goal:** Detect and block sensitive identifiers before retrieval or Groq.

#### Tasks

1. Detect PAN, Aadhaar, account/folio numbers, OTPs, email, phone
2. On hit: `refusal`; do not log raw message; do not call Groq or vector store
3. Unit tests with **synthetic** PII-shaped strings only

#### Deliverables

- [ ] `src/guardrails/pii.py`
- [ ] `tests/test_pii.py`

#### Exit criteria

- [ ] PII fixtures never reach Groq / vector store
- [ ] Raw PII not written to logs

---

### Phase 3.2 — Intent classifier

**Goal:** Route each message to the correct pipeline branch.

#### Tasks

1. Rules-first classifier; optional small Groq classify call only if rules uncertain **and** PII already cleared

   | Intent | Action |
   | --- | --- |
   | `factual_scheme_fact` | RAG pipeline |
   | `process_howto` | RAG (if on source page) |
   | `performance_request` | Performance refusal path |
   | `advisory_or_compare` | Advisory refusal path |
   | `unclear` | Clarify or refuse if unsafe |

2. Tune to avoid over-refusal on factual fee questions containing “better”

#### Deliverables

- [ ] `src/guardrails/intent.py`
- [ ] Intent unit fixtures (advisory vs factual)

#### Exit criteria

- [ ] Core advisory / compare / performance examples classify correctly
- [ ] Core expense ratio / exit load / SIP examples stay `factual_scheme_fact`

---

### Phase 3.3 — Refusal & performance paths

**Goal:** Polite, on-policy refusal copy and performance handling.

#### Tasks

1. Advisory/compare refusal: facts-only limitation + educational link (AMFI/SEBI examples from problem statement — not scheme corpus)
2. Performance refusal: no return math; cite scheme’s **problem-statement Reference URL**
3. Out-of-corpus AMC/scheme: refuse or list supported Kotak schemes from manifest
4. Keep output-side banlist active even after RAG

#### Deliverables

- [ ] `src/guardrails/refusals.py` (templates)
- [ ] Documented edu link URL(s) used in refusals

#### Exit criteria

- [ ] Advisory refusals include edu link and no advice language
- [ ] Performance refusals cite problem-statement scheme URL only

---

### Phase 3.4 — Guardrail integration & refusal tests

**Goal:** Wire gates into the orchestrator and automate the refusal suite.

#### Tasks

1. Order: PII → intent → (refusal | RAG)
2. Build `tests/refusal_cases.json` covering:

   - “Should I invest…?”
   - “Which fund is better?”
   - Return comparison / forecast prompts
   - PII-bearing prompts
   - Performance “what was 3Y return?” → problem-statement scheme URL only
3. Automate runner; ensure factual goldens still pass (no over-refusal)

#### Deliverables

- [ ] Guardrails integrated in chat orchestrator
- [ ] Automated refusal suite

#### Exit criteria

- [ ] All advisory fixtures refuse with educational link
- [ ] Performance fixtures never compute/compare returns
- [ ] PII fixtures never reach Groq / vector store
- [ ] Factual fixtures still pass for expense ratio / exit load / SIP

#### Risks / notes (Phase 3)

- Over-broad advisory rules can block legitimate fact questions — tune with golden + refusal suites together

---

## Phase 4 — Minimal user interface

**Parent goal:** Ship the problem-statement UI: welcome, three examples, visible disclaimer, chat.

### Phase 4.1 — UI shell

**Goal:** Static shell with branding of the FAQ experience and compliance chrome.

#### Tasks

1. Scaffold chosen UI stack (**React + Vite + Tailwind** in `ui/`; Stitch design in `stitch_kotak_mutual_fund_faq_assistant/`)
2. Welcome message (facts-only Kotak FAQ framing)
3. Persistent disclaimer: **Facts-only. No investment advice.**
4. Ensure **no** login, KYC upload, or PII fields

#### Deliverables

- [x] `ui/` React app runs locally (`npm run dev`)
- [ ] Disclaimer visible on first viewport (or sticky)

#### Exit criteria

- [ ] No PII input fields in the UI
- [ ] Welcome + disclaimer present

---

### Phase 4.2 — Chat + example questions

**Goal:** Wire interactive Q&A to `POST /api/chat`.

#### Tasks

1. Three example question chips (clickable), e.g.:

   - What is the expense ratio of Kotak Large Cap Fund – Direct Growth?
   - What is the exit load for Kotak Flexicap Fund – Direct Growth?
   - What is the minimum SIP amount for Kotak Liquid Fund?
2. Chat transcript: answer text, citation link (problem-statement URL), last-updated footer
3. Optional: list supported scheme names on empty state

#### Deliverables

- [ ] Chips prefill/send questions
- [ ] Live chat against local API

#### Exit criteria

- [ ] Example chip produces a cited factual answer for an in-corpus scheme
- [ ] Citation renders as a single clickable link

---

### Phase 4.3 — UI E2E polish

**Goal:** Demo-ready UX for success and failure paths.

#### Groq rate limits (`openai/gpt-oss-120b`)

Normative free-tier caps (local guard + UI surfacing in P4):

| Limit | Value | Where enforced |
| --- | --- | --- |
| Requests / minute | **30** | `src/guardrails/groq_limits.py` before Groq call |
| Requests / day | **1,000** | same |
| Tokens / minute | **8,000** | pre-flight estimate + reconcile from Groq `usage` |
| Tokens / day | **200,000** | same |

**UI / API behaviour (P4):**

- `GET /api/limits` — remaining minute/day request + token budgets
- `POST /api/chat` returns **HTTP 429** + `Retry-After` when local guard trips
- Streamlit UI (`ui/app.py`, legacy): sidebar quota meters — **primary UI is React** (`ui/src/`)
- Refusal / PII / retrieval-miss paths **do not** call Groq (no quota burn)

Override via `.env`: `GROQ_RPM_LIMIT`, `GROQ_RPD_LIMIT`, `GROQ_TPM_LIMIT`, `GROQ_TPD_LIMIT`, `UI_MIN_SECONDS_BETWEEN_REQUESTS`.

#### Tasks

1. Friendly API error state (no stack traces)
2. Mobile-usable single-column layout
3. Verify advisory question path shows polite refusal + edu link
4. Confirm disclaimer remains visible during chat scroll (sticky if needed)
5. Surface Groq quota in sidebar; block rapid-fire example-chip clicks

#### Deliverables

- [x] `ui/` React shell + chat (`ui/src/App.tsx`)
- [ ] `GET /api/limits` for Groq quota display
- [ ] UI checklist from [`eval.md`](./eval.md) L6 signed off
- [ ] Fact + refusal demo paths recorded

#### Exit criteria

- [ ] End-to-end: example question → factual answer citing problem-statement URL
- [ ] End-to-end: advisory question → polite refusal + edu link
- [ ] Error path is user-safe

---

## Phase 5 — Harden, evaluation, README & runbook

**Parent goal:** Meet deliverables and success criteria; make the system demable and maintainable. See [`eval.md`](./eval.md).

### Phase 5.1 — Golden eval suite

**Goal:** Automate factual quality measurement.

#### Tasks

1. Expand `tests/golden_questions.json` — per scheme × facet (expense ratio, exit load, min SIP, riskometer, benchmark, process if in corpus)
2. Metrics: retrieval hit (correct section), groundedness (as available), citation equals problem-statement URL, format compliance
3. Runner + `reports/golden_report.json`

#### Deliverables

- [ ] Golden fixtures + runner
- [ ] Report artifact

#### Exit criteria

- [ ] Golden **format + citation** pass rate **≥ 80%** (MVP gate)

---

### Phase 5.2 — Refusal eval & pytest wiring

**Goal:** Lock compliance bar and unit regressions.

#### Tasks

1. Complete refusal suite (advisory, compare, performance, PII) per [`edge-case.md`](./edge-case.md) / [`eval.md`](./eval.md)
2. Wire `pytest` for validator, PII, and suite runners (CI-local)
3. Logging policy: request id, latency, intent, hit/miss, validator pass — **no raw PII**
4. Optional: `GET /api/meta` for schemes covered + corpus refresh date

#### Deliverables

- [ ] `tests/refusal_cases.json` + runner
- [ ] pytest entrypoints green locally

#### Exit criteria

- [ ] Refusal / PII cases **100%** pass
- [ ] Over-refusal guard does not fail core factual goldens

---

### Phase 5.3 — README & refresh runbook

**Goal:** A new developer can run the demo from docs alone.

#### Tasks

1. Root `README.md`:

   - Setup (`GROQ_API_KEY`, ingest, API, UI)
   - Selected AMC (**Kotak**) and schemes with **problem-statement source URLs**
   - Architecture overview (link `docs/architecture.md`)
   - Known limitations (including source-URL constraint)
   - Disclaimer snippet
2. Refresh runbook (`docs/runbook.md` or README section):

   - Re-fetch the **same** problem-statement URLs → re-ingest → bump `effective_date` → smoke + eval
   - Add a scheme only if its Reference URL already exists in `problemStatement.md`
   - Point to **Phase 6** for automated daily refresh via GitHub Actions

#### Deliverables

- [ ] `README.md` complete
- [ ] Refresh steps documented

#### Exit criteria

- [ ] README alone sufficient to run ingest + API + UI
- [ ] Refresh steps explicitly forbid non–problem-statement URLs

---

### Phase 5.4 — DoD sign-off & demo script

**Goal:** Close Global Definition of Done and stakeholder demo readiness.

#### Tasks

1. Final pass against Global Definition of Done
2. Demo script: 3 factual + 2 refusal prompts
3. Archive eval `reports/summary.md` with date / git sha
4. Corpus refresh regression once (L7) if time allows

#### Deliverables

- [ ] Signed DoD checklist
- [ ] Demo script
- [ ] Eval summary report

#### Exit criteria

- [ ] All Global Definition of Done boxes checked
- [ ] Agreed pass thresholds met (≥80% golden format+citation; **100%** refusal/PII)

---

## Phase 6 — Daily corpus refresh scheduler (GitHub Actions)

**Parent goal:** Keep the RAG corpus current without manual intervention. A GitHub Actions workflow runs **once per day**, re-executing the full Phase 1 pipeline — scrape (fetch), normalize (parse), chunk, embed, and upsert ChromaDB — so answers always reflect the latest allowlisted scheme pages.

**Depends on:** P1.1–P1.4 (ingest modules + `python -m src.ingest.run`), P5.3 (refresh runbook). Does **not** require `GROQ_API_KEY` (embeddings are local).

### Why GitHub Actions

| Requirement | GitHub Actions fit |
| --- | --- |
| Daily cadence | Native `schedule` cron trigger |
| No extra infra | Runs in repo; no separate cron VM |
| Audit trail | Workflow run logs + commit history for each refresh |
| Manual override | `workflow_dispatch` for on-demand refresh before demos |
| Secrets | None required for ingest-only job (Groq key stays out of scheduler) |

### End-to-end flow

```text
cron (daily) or workflow_dispatch
        │
        ▼
.github/workflows/daily-ingest.yml
        │
        ├─ checkout main
        ├─ setup Python + cache pip / HuggingFace model
        ├─ pip install -r requirements.txt
        ├─ python -m src.ingest.run          # fetch → parse → chunk → index
        ├─ python scripts/retrieval_probe.py # post-refresh smoke (no Groq)
        ├─ git commit refreshed data/ artifacts
        └─ git push (GITHUB_TOKEN)           # only if diff non-empty
```

**Pipeline command (authoritative):**

```bash
python -m src.ingest.run
```

This invokes, in order: `src.ingest.fetch` → `src.ingest.parse` → `src.ingest.chunk` → `src.ingest.index` (Chroma upsert with idempotent `doc_id` delete-before-insert per P1.4).

### Phase 6.1 — GitHub Actions workflow scaffold

**Goal:** Add a version-controlled workflow file with schedule, permissions, and manual trigger.

#### Tasks

1. Create `.github/workflows/daily-ingest.yml`
2. Triggers:
   - `schedule`: `cron: '30 4 * * *'` (10:00 AM IST daily)
   - `workflow_dispatch`: optional `scheme_id` input for single-scheme refresh
3. Job permissions: `contents: write` (to push refreshed corpus commits)
4. Concurrency: `group: daily-ingest` + `cancel-in-progress: false` (avoid overlapping full refreshes)
5. Timeout: ≥ 30 minutes (first run downloads embedding model)

#### Deliverables

- [ ] `.github/workflows/daily-ingest.yml` committed
- [ ] Workflow visible under **Actions** tab; manual dispatch succeeds (dry run or full)

#### Exit criteria

- [ ] Scheduled trigger configured (or documented if disabled on forks)
- [ ] `workflow_dispatch` runs without syntax errors

---

### Phase 6.2 — Daily ingest pipeline job

**Goal:** Run the full ingestion stack in CI with the same entrypoint as local dev.

#### Tasks

1. Workflow steps (minimal):

   ```yaml
   - uses: actions/checkout@v4
   - uses: actions/setup-python@v5
     with:
       python-version: "3.11"
       cache: pip
   - run: pip install -r requirements.txt
   - run: python -m src.ingest.run
     env:
       EMBEDDING_MODEL: BAAI/bge-small-en-v1.5
       VECTOR_STORE_PATH: data/vectorstore
       CHROMA_COLLECTION: mutual_fund_chunks
   ```

2. Cache HuggingFace / sentence-transformers model between runs (`~/.cache/huggingface`) to keep daily runs fast
3. **Do not** pass `GROQ_API_KEY` — scheduler is ingest-only
4. Fail the job if `src.ingest.run` exits non-zero (fetch/parse/chunk/index errors block push)
5. Optional: `--scheme-id` branch when `workflow_dispatch` input is set

#### Deliverables

- [ ] Green workflow run that completes fetch → parse → chunk → index
- [ ] `data/raw/fetch_log.yaml`, `data/processed/*`, `data/vectorstore/index_log.yaml` updated in workspace

#### Exit criteria

- [ ] All manifest schemes processed (or explicit per-scheme failure with job failure)
- [ ] Chroma collection vector count matches post-chunk expectations (see `index_log.yaml`)
- [ ] No non–problem-statement URLs ingested (existing allowlist guard in fetch)

---

### Phase 6.3 — Corpus artifact persistence

**Goal:** Persist refreshed raw HTML, processed JSON/chunks, structured facts, and ChromaDB so deploys and local clones use the latest index.

#### Persistence strategy (MVP)

| Artifact | Path | CI action |
| --- | --- | --- |
| Raw HTML | `data/raw/*.html`, `fetch_log.yaml` | Commit if changed |
| Parsed | `data/processed/parsed/`, `parse_log.yaml` | Commit if changed |
| Chunks | `data/processed/chunks/`, `chunk_log.yaml` | Commit if changed |
| Structured facts | `data/processed/structured_facts.yaml` | Commit if changed |
| Vector store | `data/vectorstore/` (Chroma) | Commit if changed |
| Probe log | `data/processed/chunks/retrieval_probe_log.yaml` | Commit if changed |

**Git note:** `.gitignore` currently excludes `data/vectorstore/`. For the scheduler to persist Chroma across runs, either:

- **Option A (recommended for small corpus):** Stop ignoring `data/vectorstore/` and commit the directory from CI (7 schemes ≪ Git LFS threshold), **or**
- **Option B:** Publish `data/vectorstore/` as a versioned GitHub Actions artifact and document download in deploy runbook (no auto-push).

Pick one option in P6.3 and document in README / runbook.

#### Tasks

1. After successful ingest, run retrieval smoke: `python scripts/retrieval_probe.py` (or rely on probes inside `run_index`)
2. Configure git identity in workflow (`github-actions[bot]`)
3. Commit only when `git diff --quiet` is false:

   ```bash
   git add data/raw data/processed data/vectorstore
   git commit -m "chore(ingest): daily corpus refresh $(date -u +%Y-%m-%d)"
   git push
   ```

4. Commit message includes UTC date; `effective_date` / `ingested_at` in chunks already bumped by ingest
5. Protect `main`: allow bot push for `data/**` paths or use a dedicated `corpus-refresh` branch + PR (team choice)

#### Deliverables

- [ ] Automated commit (or PR) with refreshed corpus after green ingest
- [ ] `GET /api/meta` (if implemented in P5.2) reflects latest `effective_date`

#### Exit criteria

- [ ] Second consecutive daily run is idempotent when source pages unchanged (no empty commits or hash churn)
- [ ] When a scheme page changes, fetch log hash updates and vectors upsert correctly
- [ ] Clone from `main` after refresh works without re-running ingest locally

---

### Phase 6.4 — Scheduler ops & smoke gate

**Goal:** Operable daily refresh with clear failure modes and operator runbook.

#### Tasks

1. **Failure notifications:** GitHub Actions email on workflow failure; optional Slack/webhook step
2. **Runbook** (`docs/runbook.md` § Daily scheduler):

   - How to re-run manually (`workflow_dispatch`)
   - How to refresh one scheme (`--scheme-id`)
   - What to do when fetch fails (403, timeout) — do not bypass allowlist
   - When to use `--recreate-collection` (embedding model change only, not daily)
3. **Post-refresh gate:** retrieval probes must pass before commit/push; optional: run golden format+citation subset (no Groq) if available
4. Document rate limits / politeness: single manifest, sequential fetch, existing `FETCH_TIMEOUT_SECONDS`
5. README: add **Corpus freshness** line — “Refreshed daily via GitHub Actions; see last commit under `data/`”

#### Deliverables

- [ ] Runbook section for scheduler
- [ ] Failed ingest does **not** push partial/corrupt index
- [ ] README mentions daily automation

#### Exit criteria

- [ ] Simulated fetch failure fails workflow and leaves `main` unchanged
- [ ] Manual dispatch documented and verified once
- [ ] Team agrees on cron time (UTC) and notification channel

#### Risks / notes

- **Forks:** `schedule` is disabled on forks by default; document that production uses the upstream repo
- **Model download:** first run is slow; cache HuggingFace artifacts
- **Chroma binary size:** monitor repo size if committing vectorstore; switch to LFS or artifact store if it grows
- **No Groq in scheduler:** generation eval stays separate; scheduler only maintains retrieval corpus

---

## Cross-cutting work (all phases)

| Concern | Practice |
| --- | --- |
| Secrets | `GROQ_API_KEY` only in `.env`; never commit; document in `.env.example` with `GROQ_MODEL=openai/gpt-oss-120b` |
| Scheduler | Daily ingest workflow uses **no** Groq secret; only `GITHUB_TOKEN` for corpus commits |
| Sources | Ingest + citation allowlist = exact Reference URLs from `problemStatement.md` only |
| Privacy | No PAN/Aadhaar/account/OTP/email/phone collection anywhere |
| Response format | Validator is source of truth for ≤3 sentences, one link, footer |
| Scope control | No advice, rankings, or return calculations in-product |

---

## Suggested milestone timeline (indicative)

Adjust to team size; assumes 1–2 builders familiar with Python RAG.

| Phase | Indicative effort |
| --- | --- |
| P0 Bootstrap & corpus | 0.5–1 day |
| P1.1 Ingestion | 0.25–0.5 day |
| P1.2 Parsing | 0.5–1 day |
| P1.3 Chunking | 0.5–1 day |
| P1.4 Embed / index / facts | 0.5–1 day |
| P2.1 Scheme resolver | 0.25–0.5 day |
| P2.2 Retriever | 0.5–0.75 day |
| P2.3 Groq generator | 0.25–0.5 day |
| P2.4 Output validator | 0.25–0.5 day |
| P2.5 API & CLI | 0.25–0.5 day |
| P3.1 PII gate | 0.25 day |
| P3.2 Intent classifier | 0.25–0.5 day |
| P3.3 Refusal / performance paths | 0.25–0.5 day |
| P3.4 Integration + refusal tests | 0.25–0.5 day |
| P4.1 UI shell | 0.25 day |
| P4.2 Chat + examples | 0.25–0.5 day |
| P4.3 UI E2E polish | 0.25–0.5 day |
| P5.1 Golden eval | 0.5 day |
| P5.2 Refusal eval & pytest | 0.25–0.5 day |
| P5.3 README & runbook | 0.25–0.5 day |
| P5.4 DoD & demo | 0.25 day |
| P6.1 GH Actions scaffold | 0.25 day |
| P6.2 Daily ingest job | 0.25–0.5 day |
| P6.3 Artifact persistence | 0.25 day |
| P6.4 Scheduler ops | 0.25 day |

**MVP target:** roughly **1–2 weeks** calendar time including source gathering and eval tuning. **+0.5–1 day** for Phase 6 scheduler after P5.

---

## Phase exit tracker

| Phase | Owner | Status | Exit signed off |
| --- | --- | --- | --- |
| P0 Bootstrap & corpus | | Not started | |
| P1.1 Ingestion | | Not started | |
| P1.2 Parsing | | Not started | |
| P1.3 Chunking | | Not started | |
| P1.4 Embed / index / facts | | Complete | |
| P2.1 Scheme resolver | | Not started | |
| P2.2 Retriever | | Not started | |
| P2.3 Groq generator | | Not started | |
| P2.4 Output validator | | Not started | |
| P2.5 API & CLI | | Not started | |
| P3.1 PII gate | | Not started | |
| P3.2 Intent classifier | | Not started | |
| P3.3 Refusal / performance | | Not started | |
| P3.4 Integration + refusal tests | | Not started | |
| P4.1 UI shell | | Not started | |
| P4.2 Chat + examples | | Not started | |
| P4.3 UI E2E polish | | Not started | |
| P5.1 Golden eval | | Not started | |
| P5.2 Refusal eval & pytest | | Not started | |
| P5.3 README & runbook | | Not started | |
| P5.4 DoD & demo | | Not started | |
| P6.1 GH Actions scaffold | | Not started | |
| P6.2 Daily ingest job | | Not started | |
| P6.3 Artifact persistence | | Not started | |
| P6.4 Scheduler ops | | Not started | |

---

## Traceability

| Requirement (problem statement) | Implemented in |
| --- | --- |
| Kotak AMC, 3–5 diverse schemes; scheme links from problem-statement table only | P0, P1.1–P1.4 |
| Facts: expense ratio, exit load, min SIP, lock-in, riskometer, benchmark, statements process | P1.2–P1.4 facets; P2.2–P2.5 answers |
| ≤3 sentences, one citation, last-updated footer | P2.4 validator; P2.5 API |
| Refuse advice / comparisons; edu link | P3.2–P3.4 |
| Performance → scheme problem-statement URL only (no return calc) | P3.3–P3.4 |
| No PII collection | P3.1; P4.1 UI constraints |
| Minimal UI + disclaimer | P4.1–P4.3 |
| README + limitations | P5.3–P5.4 |
| Eval gates (≥80% / 100%) | P5.1–P5.2 |
| Daily corpus refresh (latest scheme data) | P6.1–P6.4 |

---

## Document control

| Item | Value |
| --- | --- |
| Related | [`problemStatement.md`](./problemStatement.md), [`architecture.md`](./architecture.md), [`eval.md`](./eval.md), [`edge-case.md`](./edge-case.md) |
| Status | Implementation plan for MVP (sub-phased) |
| Audience | Engineering, PM |
