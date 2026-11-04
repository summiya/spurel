<p align="center">
  <img src="./docs/assets/spurel-hero.svg" alt="Spurel — RAG retrieval observability, debugging and evaluation" width="100%" />
</p>

<p align="center">
  <strong>An open-source workbench for inspecting, testing and improving RAG retrieval.</strong>
</p>

<p align="center">
  <img alt="Python 3.13" src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-frontend-000000?style=flat-square&logo=nextdotjs&logoColor=white">
  <img alt="PostgreSQL and pgvector" src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white">
</p>

> [!IMPORTANT]
> **Pre-alpha, not production ready.** Knowledge Bases, Documents, Chunk Inspector, Retrieval Lab, Trace History/Comparison, Evaluations and RAG Answers use authenticated FastAPI-backed workflows. This frontend follow-up replaces the Overview's sample metrics with honest read-only counts and saved activity scoped to an actual knowledge base. The images below remain concepts, not verified backend screenshots.

[Quick start](#quick-start) · [Implemented today](#implemented-today) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md) · [Development guide](docs/development.md) · [Benchmark CI](docs/quality-gate-ci.md)

## What Spurel does

Spurel helps RAG developers understand **which document chunks were retrieved, how they ranked, whether the answer was grounded, and whether a change improved retrieval quality**.

The backend supports ingestion, chunk versions, traces, benchmarks and grounded RAG answers. The frontend exposes live source, chunk, retrieval, trace comparison, evaluations and RAG answers. The Overview now summarizes loaded records from those existing workflows, without claiming global totals.

## Quick start

**Requirements:** Docker with Compose v2, Python 3 and Make. You do not need to install Node or the Python backend packages on your host.

From the repository root:

```bash
make up       # Create .env safely, build, migrate, start and wait for healthy services
make status   # Check PostgreSQL-backed API, bearer authentication and frontend
make logs     # Follow container logs
make down     # Stop without deleting the local database or uploaded files
```

| Local service | URL or port | Status |
| --- | --- | --- |
| Next.js frontend | http://127.0.0.1:3000 | Live read-only Overview plus operator-protected sources, chunks, retrieval, traces, evaluation and RAG |
| FastAPI health | http://127.0.0.1:8000/health | Public |
| FastAPI business API | http://127.0.0.1:8000/knowledge-bases | Shared bearer token required |
| PostgreSQL + pgvector | 127.0.0.1:5432 | Local development only |

The initializer writes a strong random `SPUREL_API_TOKEN` to the ignored `.env` without displaying it. **Never commit that file or put the token into frontend/client-side code.** To try an authenticated endpoint from a trusted local shell:

```bash
set -a
source .env
set +a
curl -H "Authorization: Bearer $SPUREL_API_TOKEN" \
  http://127.0.0.1:8000/knowledge-bases
```

No OpenAI key is required to **start** the stack or manage knowledge bases. Document embedding and generated answers require provider credentials and configuration. See the [development guide](docs/development.md) for environment variables, tests, migrations, alternate ports and data safety.

## Interactive frontend (SP-09–SP-15; Overview follow-up in review)

The approved midnight-blue, cyan and violet design is implemented in Next.js as a responsive
application shell with keyboard command search (**⌘K / Ctrl+K**), theme switching, and eight
routes: Overview, Knowledge Bases, Retrieval Lab, Chunk Inspector, Evaluations,
Trace History, RAG Answers, and Settings. Real retrieval and evaluation records,
source excerpts and trace comparisons are backed by FastAPI/PostgreSQL; the
SP-15 adds on-demand provider-backed RAG answers. The Overview now summarizes
real loaded documents, indexed status, saved traces and benchmark measurements.

**SP-10 through SP-14 connect Knowledge Bases, Documents, Chunk Inspector,
Retrieval Lab, Trace History/Comparison and Evaluations. SP-15 connects RAG
Answers**, all through the same signed, HTTP-only local operator session.
Create collections, upload and process documents, then inspect the active chunks
and historic processing versions, including exact offsets, UUIDs and embedding
availability. The backend bearer token stays **only on the Next.js server**.
RAG generation is explicitly invoked after a cost warning; it never runs automatically on page load or typing.

After `make up`, find your locally generated operator password in the ignored
`.env` by running `grep '^SPUREL_FRONTEND_OPERATOR_PASSWORD=' .env` from the repo root.
Open `http://localhost:3000/knowledge-bases` (or your configured frontend host port)
and sign in. Never share the password or session signing secret. Use `make up` after
pulling SP-10 to add the missing settings to **existing** `.env` files.

## Generate a live RAG answer (SP-15, merged)

In this feature branch, sign in and open **[RAG Answers](http://localhost:3000/rag)**.
Choose an indexed knowledge base, enter a question and configure Top K (1–20),
Candidate K (at least Top K, at most 100) and RRF K (1–1,000). An explicit
confirmation precedes every request because hybrid retrieval and text generation
may call OpenAI and incur charges. No paid calls run while typing, navigating
or opening the page. Without valid provider credentials or indexed content,
generation can fail or return a no-context response.

The frontend shows the backend's exact answer, provider/model metadata, saved
retrieval trace ID, and context excerpts with persisted source UUIDs, original
offsets and links into Chunk Inspector. Returned source labels can be selected
inline; **a model-emitted label is not independent citation/claim verification**.
An empty retrieval returns a clear no-context state without fabricating evidence.
Full answer transcripts are not persisted by this UI; retrieval trace snapshots
are persisted by the backend.

## Live Overview dashboard (frontend follow-up)

Open [Overview](http://localhost:3000/) and sign in as the local operator to load
real knowledge bases, active indexing status, newest persisted retrieval traces
and benchmark metrics. Choose a specific knowledge base and, optionally, an evaluation
dataset. All counts are **loaded-page counts**, never fabricated global totals.
The restored **Retrieval quality over time** chart uses real saved benchmark Recall@K
and Precision@K over the last 7 or 30 days, separated by retrieval configuration
and case count. Until you create labeled cases and execute benchmarks, the chart
shows an empty state rather than invented points. The latest-run metrics remain
visible separately; no synthetic p95 or ingestion-health score is invented.

Overview uses only authenticated existing GET endpoints, so navigating here
does not call OpenAI or incur embedding/generation usage charges. The chart shows
only loaded benchmark pages (50 runs per page) and does not imply identical
query/judgment sets merely because settings match. Additional pages can be
loaded where supported; link through to Evaluations for run comparisons.
No database migrations, new provider adapters or backend changes are required.
This Overview work is separate from the merged SP-16/SP-17 chunking strategies and the SP-18 PDF-processing review branch.

## SP-16: opt-in token-aware chunking (merged)

Spurel's existing character chunking remains the default: **1,000 characters**
with **200-character overlap**, with the same processing button and version
history. SP-16 adds a `Model tokens` option alongside those
controls in the Knowledge Bases document panel. Token size defaults to
**512**, overlap to **64**, both adjustable within validated bounds.

The token mode uses `tiktoken` to count the **configured OpenAI embedding
model's tokens** locally (no provider call just to count), and retains exact
original-source character offsets, Unicode text, immutable version history
and the safe staged-embedding/promotion lifecycle. Reprocessing may incur
embedding API charges, and custom settings always require confirmation.
The Chunk Inspector shows exact token counts with their **current embedding
model encoding**; historical display counts are recomputed for that encoding,
not claimed as immutable historical tokenizer provenance.

The backend processing endpoint accepts optional JSON
`{"strategy":"tokens","chunk_size":512,"overlap":64}`; bodyless
POSTs keep the original character defaults. This integration adds no database
migration and does not delete old versions or automatically reindex documents.


## SP-17: structure-aware chunking (merged)

The Knowledge Bases screen gains **three additional**, opt-in chunking methods:
**Recursive** (prefers paragraphs, then sentences, lines and spaces),
**Markdown headings** (respects section headings and ignores heading-like
text inside fenced code blocks), and **Sentences** (prefers natural punctuation
boundaries and avoids common abbreviations). Existing **Characters** and
**Model tokens** remain untouched and retain their original defaults.

These new strategies use bounded *character* sizes and overlaps, not model
tokens. They keep exact original source excerpts and character offsets;
oversized units fall back to smaller separators and, only when necessary,
fixed character windows. Overlap may be **less than requested** or omitted
to avoid cutting through a sentence or crossing a Markdown heading.
Source passages are never rewritten, and no language model is called to
decide the boundaries. The methods improve splitting but do not guarantee
semantic understanding or perfect sentence detection in all languages.

Existing Processing and Reprocessing buttons, chunk inspector, historical
versions, dashboard and quality graph stay intact. Only an explicit action
(with confirmation for non-default settings) triggers re-indexing and may
incur embedding API charges. No database schema change or automatic
reprocessing is introduced.


## SP-18: PDF pages and optional scanned-PDF OCR (in review)

PDF ingestion in this branch continues using the existing pypdf text extraction
by default. Each processed PDF chunk additionally receives immutable **1-based
PDF page numbers** and an **includes OCR text** marker where applicable.
Chunk Inspector, Retrieval Lab and RAG source evidence display those references,
while keeping existing source text, UUIDs, scores and citation labels.
Previously indexed PDF chunk versions are not modified or falsely backfilled:
new page metadata appears only after an explicit successful reprocessing run.

For a text-heavy PDF with unusual columns or spacing, opt into layout-preserving
extraction using `SPUREL_PDF_EXTRACTION_MODE=layout` in your server's
local `.env`. Default is `plain`, preserving previous extraction semantics.

Scanned PDFs need OCR. Local **Tesseract + Poppler** are included in the
development backend image but **OCR is disabled by default**. To opt in,
add these settings to the local `.env` and restart the backend:

```dotenv
SPUREL_PDF_OCR_ENABLED=true
SPUREL_PDF_OCR_LANGUAGE=eng
SPUREL_PDF_OCR_MAX_PAGES=5
```

Only pages with no extractable text are OCR candidates, with a maximum of
20 per processing request, limited PDF size, raster dimensions and per-page
timeouts. OCR runs **only during explicit Process/Reprocess**, not on upload,
open, search or inspection; it makes no remote OCR API call. Recognition can
be inaccurate, so check page citations against the original PDF. Encrypted
PDFs remain unsupported. Processing still needs the configured embedding
provider and may incur charges; failed attempts never activate partial indexes.
The new nullable page columns are added through a **non-destructive Alembic
migration**, preserving existing document/chunk versions. Never reset volumes.

## SP-19: source metadata filters (in review)

SP-19 adds an **optional Document metadata filters** panel to the existing
[Retrieval Lab](http://localhost:3000/retrieval), without removing search modes,
results, traces or the dashboard graph. Filter by the **actual persisted**
document UUID, PDF/Markdown/plain-text type, a literal case-insensitive
filename substring, and an inclusive UTC upload date range. The conditions
are combined with AND; several document IDs or file types in an API request
are OR within their own field. Existing empty/unfiltered queries work as before.

Filters are validated on the client and backend, then applied **inside SQL
before ranking**, including both vector and keyword candidate pools used by
hybrid RRF. A result filtered only after ranking could miss relevant matches
within the requested source scope; this implementation avoids that. Saved
retrieval traces record the exact normalized filter configuration and Trace
History flags comparisons with different scopes.

The filter panel lists **loaded** documents from the selected knowledge base;
the backend always enforces the requested knowledge-base scope regardless
of document ID, so IDs from another collection never reveal its content.
No document metadata is edited, and filters do not perform access control
or establish per-user permissions. Existing RAG answers and evaluation flows
remain unfiltered by default; SP-19 adds filters to the three Retrieval Lab
search modes only. No search/embedding call occurs just by editing filters.

SP-19 uses an additive nullable JSONB trace-filter snapshot column in
Alembic migration **0014**. The PR is **based on SP-18 PR #80**, which adds
migration 0013; merge SP-18 first, then merge SP-19. Existing trace snapshots
remain untouched with `filters: null`.

## SP-20: explicitly built HNSW index and real recall/latency benchmark (in review)

The existing **exact** vector/hybrid retrieval and live dashboard remain unchanged.
SP-20 adds a separate operator-only index/benchmark utility for exploring
pgvector HNSW safely without changing the default answer/ranking path or
incurring OpenAI charges.

Spurel's \`chunk_embeddings.embedding\` column stores **mixed vector dimensions**,
so one global index is not suitable. The tool creates a **dimension-specific,
partial cosine HNSW index**. It builds **concurrently** and only after you
explicitly confirm. No Alembic migration, automatic index creation, data deletion,
document reprocessing, or RAG/retrieval behavior change occurs on deployment.

From the local repository with the Compose stack running:

\`\`\`bash
# Check whether the 1536-dimensional HNSW index is present:
docker compose exec backend spurel-hnsw status --dimensions 1536

# Explicitly build (may take time, memory and disk space):
docker compose exec backend spurel-hnsw build --dimensions 1536 --confirm-build

# Compare the actual HNSW index to exact search using existing stored vectors,
# scoped to one real KB and embedding provider/model/dimension combination:
docker compose exec backend spurel-hnsw --json benchmark \
  --dimensions 1536 \
  --knowledge-base-id YOUR_KNOWLEDGE_BASE_UUID \
  --provider openai --model text-embedding-3-small \
  --top-k 10 --samples 20 --ef-search 100 --min-recall 0.9
\`\`\`

The benchmark reports measured **Recall@K**, min recall, median/p95 query
times, number of real sampled queries, index size and whether PostgreSQL's
EXPLAIN plan used the intended HNSW index. It fails closed if it cannot
prove an indexed plan or no persisted active embeddings match. The query
vectors are sampled from persisted embeddings (self-query bias); use
representative datasets before interpreting these numbers as production
quality. Benchmarks do **not** call embedding/generation APIs.

Index builds affect insert cost, memory/disk, and migration/operations time;
higher \`ef_search\` can improve recall but may increase latency. Filtering
to a knowledge base can also reduce approximate recall. The basic pgvector
\`vector\` HNSW operator class supports **up to 2,000 dimensions**. This tool
refuses larger dimensions rather than silently truncate or re-embed.
Indexes are never dropped by the tool. A production-like rollout should
first confirm sufficient representative recall/latency before any future
opt-in change to live search.

## Inspect real chunks (SP-11)

Once signed in, open [Chunk Inspector](http://localhost:3000/chunks) or select
**Inspect chunks** beside a document in Knowledge Bases. Select its active
index or a saved older version to view the actual stored excerpts, chunk UUIDs,
source character offsets, processing status and embedding-record counts.
Historical versions are **read-only and not used by normal retrieval**.
Pagination and text filtering operate on explicitly loaded pages, not the
entire database. An uploaded but unprocessed document correctly shows **no
active chunks**; indexing requires a configured embedding provider.

## Run real retrieval (SP-12)

After operator sign-in, open **[Retrieval Lab](http://localhost:3000/retrieval)**,
select a knowledge base, enter a query, choose **Keyword**, **Vector** or
**Hybrid**, and click **Run live retrieval**. The response contains real
ranked chunks, source offsets, raw scores, execution duration and the
persisted retrieval trace ID. **Inspect saved trace** reads the stored
snapshot and provider/model metadata; SP-13 adds full trace history
and comparison.

- **Keyword** uses PostgreSQL full-text search (`ts_rank_cd`, **not BM25**).
  It makes no query-time embedding-model call.
- **Vector** performs exact pgvector cosine retrieval and calls the configured
  embedding provider for the query.
- **Hybrid** runs both retrieval modes and fuses rankings with RRF. It supports
  `top_k`, `candidate_k` and `rrf_k`. Scores have **different scales**;
  the frontend displays the raw values, not invented percentages.

Both Vector and Hybrid may incur provider costs and require a configured
`OPENAI_API_KEY` plus compatible indexed embeddings. **No mode can return
evidence from a document until it has been successfully processed**.
Queries run only after you explicitly submit them, not as you type.

## Compare persisted retrieval traces (SP-13)

Sign in and open **[Trace History](http://localhost:3000/traces)**, or click
**Browse trace history** after a Retrieval Lab run. Choose a knowledge base,
inspect saved runs and optionally select two different traces as A and B.

SP-13 calls the existing read-only backend comparison service to show
the *actual* shared/unique chunk IDs, overlap ratio (Jaccard over the two
saved result sets), rank changes, raw scores and duration delta.
Negative rank delta means an improved numerical rank in B; it is
**not** proof of improved retrieval relevance or generated-answer quality.
Comparisons between **different queries** or **different retrieval modes**
are explicitly flagged. Undefined overlap when both runs have no results
is shown as **N/A**, not as a fabricated zero.

The UI loads history in bounded pages, filters **loaded** traces and
does not rerun queries, process documents or call embedding providers.
It requires the existing local operator login; the backend bearer token
remains server-side.

## Implemented today

| Capability | Implementation | Where |
| --- | --- | --- |
| Knowledge bases and documents | FastAPI CRUD subset: create/list knowledge bases; upload/list documents; text, Markdown and text-extractable PDF parsing | [Documents](backend/src/spurel/documents/) |
| Chunk inspection | Character and model-token chunking (SP-16); SP-17 adds opt-in structural boundaries; persisted offsets/UUIDs and read-only version history retained | [Chunking](backend/src/spurel/infrastructure/chunking/fixed.py) |
| Embeddings | OpenAI embedding adapter; persisted pgvector embeddings keyed by provider/model/dimensions | [Embeddings](backend/src/spurel/embeddings/) |
| Retrieval | Exact pgvector cosine search; PostgreSQL full-text keyword scoring (`ts_rank_cd`, **not BM25**); hybrid Reciprocal Rank Fusion | [Retrieval](backend/src/spurel/retrieval/) |
| Inspectable retrieval | Saved retrieval traces, trace comparisons and graded retrieval metrics | [Retrieval API](backend/src/spurel/retrieval/api.py) |
| Evaluation | Labeled datasets, precision/recall@k, MRR, nDCG, coverage, persisted runs, comparisons, promoted baselines and regression gates | [Evaluation](backend/src/spurel/evaluation_datasets/) |
| Label consistency | Reject new judgments for inactive or foreign chunks; detect stale historical labels before live evaluations; judgment audit endpoint | [Judgment audit](backend/src/spurel/evaluation_datasets/judgment_integrity.py) |
| RAG answers | Hybrid retrieval plus OpenAI text generation, bounded source excerpts and model-requested source labels | [RAG](backend/src/spurel/rag/) |
| Reprocessing | Immutable chunk-set versions, stable UUIDs for unchanged chunks, staged embeddings, fenced retries and atomic activation | [Processing](backend/src/spurel/documents/processing.py) |
| Live frontend source management | Local operator login, live knowledge-base creation/list, document upload/list and indexing, server-only backend proxy | [Knowledge bases](frontend/components/live/knowledge-bases.tsx) |
| Live Chunk Inspector | Read-only active chunks, historical versions, persisted text, offsets, embedding counts, filtering and pagination | [Chunk Inspector](frontend/components/live/chunk-inspector.tsx) |
| Live Retrieval Lab | Keyword, vector and hybrid queries; actual raw ranked scores, source offsets, parameters, persisted trace inspection | [Retrieval Lab](frontend/components/live/retrieval-lab.tsx) |
| Live Trace History and Comparison | Newest-first saved retrievals, scoped snapshot inspection, overlap, rank movement, raw score and timing comparisons | [Traces](frontend/components/live/traces.tsx) |
| Live Evaluations | Persisted label datasets, judgment audits, Keyword/Vector/Hybrid benchmarks, saved runs, comparisons, baselines and quality gates | [Evaluations](frontend/components/live/evaluations.tsx) |
| Live RAG Answers | Explicit answer generation, bounded hybrid settings, real source excerpts/labels, saved trace and chunk links | [RAG answer UI](frontend/components/live/rag-answers.tsx) |
| Local developer tools | Full-stack Docker Compose, Alembic, pytest/PostgreSQL integration checks, Ruff, frontend lint/types/tests/build | [Development](docs/development.md) |

**Security boundary:** A local operator password gates the Next.js source-management API. A
signed, HTTP-only session allows the Next.js server to call FastAPI with its separate
shared bearer token; no backend token is included in client code. This is **single-user
local access**, not per-user authorization, RBAC, or permission-aware multi-tenancy. Knowledge-base scoped queries are not user-specific tenant authorization. Do **not** expose it as a public multi-user service.

## Not implemented yet

The following are roadmap items, **not current capabilities on main**: scanned-PDF OCR (SP-18 under review), BM25, HNSW/ANN indexing, metadata retrieval filters, cross-encoder reranking, citation/claim verification, additional hosted/local model adapters, multi-source connectors, experiment export, durable background ingestion and production-grade multi-user authorization.

For task scope and order, see the [maintained roadmap](docs/roadmap.md).

## API overview

All routes below except `GET /health` require `Authorization: Bearer <token>`.

| Workflow | Example endpoint |
| --- | --- |
| Create/list knowledge bases | `/knowledge-bases` |
| Upload/list/process documents | `/knowledge-bases/{knowledge_base_id}/documents` |
| Inspect active or historical chunks | `/knowledge-bases/{knowledge_base_id}/documents/{document_id}/chunks` and `.../versions` |
| Query vector, keyword or hybrid search | `/knowledge-bases/{knowledge_base_id}/retrieval/{mode}` (`vector`, `keyword` or `hybrid`) |
| Browse retrieval traces | `/knowledge-bases/{knowledge_base_id}/retrieval/traces` |
| Manage evaluation datasets and runs | `/knowledge-bases/{knowledge_base_id}/evaluation-datasets` |
| Audit stale evaluation labels | `/knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/judgment-audit` |
| Generate a retrieved-context answer | `/knowledge-bases/{knowledge_base_id}/rag/answer` |

Set `SPUREL_ENABLE_DOCS=1` **only in a trusted local environment** to expose Swagger at `/docs`. Protected routes still require the bearer token; the docs and schema themselves are publicly readable on the bound server when enabled.

## Architecture at a glance

```text
Next.js live source, chunk, retrieval, evaluation, trace and RAG inspection
          |
          v
 FastAPI + shared bearer authentication
          |
          +-- Documents -> parse -> chunk-set versions -> staged embeddings -> activate
          +-- Retrieval -> exact vector / Postgres FTS -> RRF -> saved traces
          +-- RAG -> traced retrieval -> provider-backed answer + source excerpts
          +-- Evaluation -> labeled cases -> runs -> comparisons / baselines / gates
          |
          v
 PostgreSQL 17 + pgvector, local document blob storage
```

Backend code is organized into domain/application services, interfaces (ports), and SQLAlchemy/provider adapters. Ingestion currently runs synchronously in an HTTP request; it is **not** a durable job pipeline. See [architecture and design limitations](docs/architecture.md).

## UI vision (concepts only)

These images illustrate the interface concept. The frontend includes **live source, chunk, retrieval, trace, evaluation and RAG answer views**; this Overview follow-up adds real read-only summaries. The images remain mockups, not screenshots of live backend results.

<p align="center">
  <img src="./docs/assets/retrieval-playground.svg" alt="Concept only: retrieval playground with candidate scores" width="100%" />
</p>

<p align="center">
  <img src="./docs/assets/experiment-comparison.svg" alt="Concept only: side-by-side retrieval experiment comparison" width="100%" />
</p>

The workbench already makes source candidates, chunk boundaries, saved retrieval decisions and evaluation runs inspectable. More advanced retrieval controls, provider adapters and production authorization remain future work.

## Roadmap and contributing

The [roadmap](docs/roadmap.md) tracks **SP-01–SP-28** by phase. SP-09–SP-15 are merged, including live evaluations (PR #74) and RAG answers (PR #75). The Overview follow-up and SP-16 token-aware chunking are merged. SP-17 is merged. SP-18 adds opt-in PDF layout/OCR and saved PDF page references in its review branch.

Spurel is being built in public. For substantial changes, open an issue first and follow the existing architecture and tests. Good contribution areas include retrieval strategies, parsers, evaluation methods, reliable ingestion, UI, and documentation.

Project principles: **retrieval first**, **inspectable by default**, **measure before tuning**, **provider boundaries**, **reproducible experiments**, and **simple before clever**.

---

<p align="center"><strong>Spurel</strong> — See what your RAG pipeline is really doing.</p>
