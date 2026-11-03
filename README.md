<p align="center">
  <img src="./docs/assets/spurel-hero.svg" alt="Spurel — open-source RAG observability, debugging and evaluation" width="100%" />
</p>

<p align="center">
  <strong>Open-source observability, debugging, experimentation, and evaluation for RAG systems.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-Frontend-000000?style=for-the-badge&logo=nextdotjs&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
</p>

<p align="center">
  <a href="#-why-spurel">Why Spurel</a> ·
  <a href="#-planned-features">Features</a> ·
  <a href="#-concept-ui">Concept UI</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-roadmap">Roadmap</a> ·
  <a href="#-contributing">Contributing</a>
</p>

> [!IMPORTANT]
> **Spurel is currently in early-stage design / pre-alpha.**  
> The screenshots below are product concept mockups, not screenshots of a finished implementation. The repository is being built in public.

## 🔐 API authentication

All Spurel business endpoints require a **shared bearer token**. The liveness endpoint `GET /health` remains unauthenticated. This first security boundary is suitable for a single trusted service/operator; it is **not** user login, organization isolation, or permission-aware multi-tenancy.

1. Generate a long, random token:

   ```bash
   python -c 'import secrets; print(secrets.token_urlsafe(32))'
   ```

2. Set `SPUREL_API_TOKEN` in your local `.env` file (do not commit it). The token must contain at least 32 printable, non-whitespace ASCII characters.

3. Include it when calling protected endpoints:

   ```bash
   curl -H "Authorization: Bearer $SPUREL_API_TOKEN" http://localhost:8000/knowledge-bases
   ```

A missing or invalid server-side token configuration returns **503** for all protected API routes (fail closed). Missing, malformed, or incorrect bearer credentials return **401** with `WWW-Authenticate: Bearer`. The same `SPUREL_API_TOKEN` environment variable is already understood by Spurel's benchmark/quality-gate CLI.

**API documentation:** Swagger UI (`/docs`), ReDoc, and OpenAPI JSON (`/openapi.json`) are disabled by default. For trusted local development only, set `SPUREL_ENABLE_DOCS=1` before starting the API. This exposes Swagger UI and its OpenAPI schema without authentication, but business endpoints still require the bearer token (use **Authorize** in Swagger). Do not enable public docs unless this metadata exposure is intentional.

**Security boundaries:** Use HTTPS when accessing the API remotely. Do not embed `SPUREL_API_TOKEN` in a browser application or ship it to end users. A future frontend should use a server-side gateway/session model, and publicly hosted multi-user deployments additionally require user authentication, tenant authorization, and role-based access control.

## ⚙️ Local environment

Copy the committed example file and add your own local secrets:

```bash
cp .env.example .env
```

Spurel currently reads configuration from the process environment, so for local shell development load the file before starting the backend:

```bash
set -a
source .env
set +a
```

The example includes the configuration currently used by Spurel:

- `DATABASE_URL`
- `SPUREL_LOCAL_STORAGE_ROOT`
- `OPENAI_API_KEY`
- `SPUREL_API_TOKEN`
- `SPUREL_ENABLE_DOCS`
- `SPUREL_EMBEDDING_MODEL`
- `SPUREL_EMBEDDING_DIMENSIONS`

> [!WARNING]
> Never commit your real `.env` file or API keys. Only `.env.example` belongs in Git.


## ✅ Continuous integration

The [CI workflow](.github/workflows/ci.yml) runs automatically on every pull request and push to `main`. All three jobs must pass:

- **Backend checks:** Python 3.13, repository-wide `ruff check .`, `ruff format --check` for Python files changed by the PR/push, and `pytest`.
- **PostgreSQL migrations:** start `pgvector/pgvector:pg17`, apply Alembic migrations, verify required tables/pgvector and that a repeated upgrade is safe.
- **PostgreSQL integration:** exercise real persistence, retrieval, and evaluations in a separate disposable test database.
- **Frontend checks:** Node.js 22, ESLint, Prettier, TypeScript, Vitest, and a Next.js production build.

These checks use no OpenAI keys and keep the existing manual [RAG quality-gate workflows](docs/quality-gate-ci.md) separate.

Run the corresponding commands locally:

```bash
cd backend
python -m pip install -e ".[dev]"
ruff check .
# Check formatting of the Python files you changed (example):
ruff format --check src/spurel/retrieval/traced.py
python -m pytest -q

cd ../frontend
npm install --no-audit --no-fund
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

**Current limitation:** existing Python files have significant pre-existing Ruff formatting drift, so CI enforces formatting on **changed backend Python files**, not the entire historical tree. Clean up remaining legacy formatting separately. Also, `frontend/package-lock.json` is not committed, so CI currently uses `npm install`, not a reproducible `npm ci`. Add the lockfile in a follow-up. Migration checks are smoke tests of the database schema, not end-to-end PostgreSQL integration tests; those are tracked separately. Configure the three CI job names as required status checks in GitHub branch protection if you want to prevent merging red PRs.

## 🧪 Real PostgreSQL integration tests

The automatic CI includes a dedicated **PostgreSQL integration** job using a fresh
`pgvector/pgvector:pg17` test database. It runs Alembic migrations before executing
the `postgres`-marked tests.

The integration suite uses the real async SQLAlchemy repositories and local filesystem
storage, with a deterministic 3-dimensional embedding fixture. It tests:

- Authenticated HTTP upload, document processing and chunk inspection
- Exact vector retrieval, PostgreSQL full-text search, hybrid RRF, and persisted traces
- Knowledge-base scoped access to document chunks and retrieval results
- Persisted evaluation datasets, benchmarks, run comparisons, baselines, and audit history
- Atomic chunk replacement rollback and embedding upsert against actual DB constraints

No OpenAI API key or external inference request is needed.

To run locally, use a **disposable database whose name ends in `_test`**:

```bash
# From the repo root; ensure the isolated test database already exists:
export DATABASE_URL=postgresql+asyncpg://spurel:spurel@localhost:5432/spurel_test
export SPUREL_TEST_DATABASE_URL="$DATABASE_URL"
cd backend
python -m pip install -e ".[dev]"
alembic upgrade head
python -m pytest -q -m postgres
```

The tests refuse non-`_test` PostgreSQL database names and clean up only the
knowledge bases they create. Without `SPUREL_TEST_DATABASE_URL`, they skip;
the CI job sets it explicitly so missing configuration cannot produce a false pass.
Regular unit tests run with `python -m pytest -q -m "not postgres"`.

## 📖 Document chunk-set versioning

Spurel retains **immutable indexing snapshots** when a document is reprocessed.
This is versioning of the *derived chunks*, not replacement of the uploaded source
file; existing document uploads remain immutable.

- Uploading a document begins with `active_chunk_version = 0` (not indexed yet).
- First processing **stages** version `1`, generates all its embeddings, then
  atomically publishes it. Until then, `active_chunk_version = 0`.
- Reprocessing with **identical chunk texts, indexes and offsets** reuses the
  active version and existing UUIDs, preserving related embeddings and judgments.
- Changed chunks get a new `processing` version without altering the old active
  index. Only after all expected embeddings are stored is the new version published.
- Failed embedding/indexing leaves the old active version searchable. Failed
  versions retain partial embeddings and chunk IDs, and retrying the same chunk
  set reclaims the failed version rather than creating duplicate versions.
- Old version rows, embeddings, UUIDs and relevance labels remain available.
- Vector/keyword/hybrid retrieval and the standard Chunk Inspector see **only
  the active version**, preventing duplicate or stale results.

Authenticated read-only history endpoints:

```text
GET /knowledge-bases/{knowledge_base_id}/documents/{document_id}/versions
GET /knowledge-bases/{knowledge_base_id}/documents/{document_id}/versions/{version}/chunks
```

The document list response exposes `active_chunk_version`. The processing
response returns `chunk_version` and `reused_active_version`. Version history
reports `status` (`processing`, `failed`, `ready`) and `attempt_count`, and
the historical inspector retains chunk IDs and embedding availability.
Knowledge-base scoping applies to both history endpoints.

**Upgrade:** The PostgreSQL migration CI job seeds a legacy document and embedding, then verifies they survive the schema change unchanged. Migration `0011_version_document_chunks` backfills existing
documents with indexed chunks as version `1`, preserving **their original UUIDs,
embeddings, and evaluation judgment references**. Existing uploaded-but-
unprocessed documents remain at version `0`. Rollback from a database with
multiple versions **discards inactive historical chunk rows and their embeddings**;
back up the database first.

### Safe staged processing (SP-05)

Processing uses **stage → embed → verify coverage → publish**. A staged version
is never returned by normal retrieval; it is visible only through explicit
read-only history inspection. Promotion checks that the persisted chunk count
matches the version and that every chunk has an embedding in the requested
provider/model/dimension space. The version pointer is updated in the same
transaction as marking the new version `ready`.

Only one processing attempt per document may own a non-expired **30-minute lease**.
Active embedding workers renew it before each batch. Competing attempts receive
HTTP **409 Conflict**. If a process terminates unexpectedly, its lease expires;
a later request can reclaim the staged version (if its chunks match) or create
the next version. An attempt UUID fences stale workers from publishing or
overwriting the state of a reclaimed attempt. New `0012_stage_chunk_processing`
migration marks existing versions `ready` without changing their chunk IDs.

A failed provider call returns the existing generic 503 response. The previous
active index is still searchable. Retried partial embeddings are upserted
idempotently; old historical snapshots and evaluation judgments are retained.
The long-running process is still synchronous per HTTP request; persistent
background work and stronger multi-tenant authorization are separate tasks.

**SP-06 remains:** Evaluation relevance judgments for *older* chunks survive,
but live evaluation must detect or explicitly handle stale evidence when a
new version becomes active.

## ✨ What is Spurel?

**Spurel** is an open-source RAG engineering workbench for developers who want to understand **why** a retrieval pipeline succeeds or fails.

Most RAG demos stop here:

```text
Question → Retrieve chunks → LLM → Answer
```

Spurel focuses on everything that happens in the middle:

```text
What was retrieved?
Why did it rank?
Which chunking strategy worked better?
Did hybrid search improve recall?
Did reranking help?
Which queries consistently fail?
What changed between experiment A and B?
```

> **Make RAG retrieval visible, measurable, reproducible, and easier to improve.**

## 🎯 Why Spurel?

| Problem | What Spurel helps you inspect |
|---|---|
| 🧩 Bad chunking | Boundaries, token counts, overlap, lost context |
| 🔎 Weak retrieval | Retrieved candidates, similarity scores, missed evidence |
| ⚖️ Poor ranking | Vector vs. keyword vs. reranker scores |
| 🧠 Wrong context | What was actually passed to the LLM |
| 🧪 No measurement | Recall@K, MRR, hit rate, context precision |
| 🔁 Hard-to-reproduce tuning | Saved experiments and configuration snapshots |
| 🕵️ Silent regressions | Evaluation runs across versions |

## 🚀 Planned features

### 🔍 Retrieval Playground
- Vector search
- BM25 / keyword retrieval
- Hybrid retrieval
- Reciprocal Rank Fusion
- Metadata filters
- Configurable `top_k`
- Reranking
- Per-stage scores
- Candidate → final-rank trace

### 🧩 Chunk Inspector
- Fixed-size chunking
- Recursive chunking
- Markdown / heading-aware chunking
- Sentence-aware chunking
- Semantic chunking
- Token counts
- Overlap visualization
- Metadata preview

### 🧪 Experiment Comparison

```text
Experiment A                       Experiment B
────────────────────────          ────────────────────────
500-token chunks                  1,000-token chunks
Hybrid retrieval                  Vector-only retrieval
RRF                               No fusion
Cross-encoder reranker            No reranker
top_k = 10                        top_k = 10
```

### 📊 Evaluation
- Recall@K
- Precision@K
- Hit Rate
- Mean Reciprocal Rank (MRR)
- NDCG
- Context precision
- Context recall
- Retrieval latency

### 📚 Knowledge Bases
- Documents
- Chunks
- Embeddings
- Metadata
- Ingestion runs
- Retrieval configurations
- Evaluation datasets

### 🔌 Provider-independent design

**Embeddings:** `OpenAI` · `Cohere` · `Voyage` · `SentenceTransformers` · `Ollama`

**LLMs:** `OpenAI` · `Anthropic` · `Gemini` · `Ollama` · `OpenRouter`

Spurel starts with **PostgreSQL + pgvector** for vector storage.

## 🖥️ Concept UI

### Retrieval Playground

<p align="center">
  <img src="./docs/assets/retrieval-playground.svg" alt="Spurel retrieval playground concept" width="100%" />
</p>

Inspect why chunks were retrieved, how they scored, what reranking changed, and what evidence reached generation.

### Experiment Comparison

<p align="center">
  <img src="./docs/assets/experiment-comparison.svg" alt="Spurel experiment comparison concept" width="100%" />
</p>

> Mockup values are illustrative only. Real experiment metrics will come from evaluation runs.

## 🏗️ Architecture

<p align="center">
  <img src="./docs/assets/rag-pipeline.svg" alt="Spurel RAG pipeline" width="100%" />
</p>

```text
                    ┌──────────────────────┐
                    │       Next.js        │
                    │    Debugging UI      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       FastAPI        │
                    │      REST API        │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
 ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
 │   Ingestion    │   │   Retrieval    │   │   Evaluation   │
 │ parse          │   │ vector         │   │ datasets       │
 │ normalize      │   │ BM25           │   │ metrics        │
 │ chunk          │   │ hybrid         │   │ experiments    │
 │ embed          │   │ rerank         │   │ comparisons    │
 └───────┬────────┘   └───────┬────────┘   └───────┬────────┘
         └────────────────────┼────────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │ PostgreSQL + pgvector│
                    └──────────────────────┘
```

## 🧰 Planned stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript |
| Backend | Python 3.13 + FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2 |
| Migrations | Alembic |
| Database | PostgreSQL |
| Vector search | pgvector |
| Cache / jobs | Redis |
| Containers | Docker / Docker Compose |
| Testing | Pytest |
| CI | GitHub Actions |

## 🧠 Core domain

```text
Workspace
  ├── Knowledge Base
  │     ├── Documents
  │     ├── Chunks
  │     ├── Embeddings
  │     └── Ingestion Runs
  ├── Retrieval Configuration
  │     ├── Retriever
  │     ├── Fusion
  │     ├── Reranker
  │     └── Filters
  ├── Evaluation Dataset
  │     ├── Questions
  │     └── Expected Evidence
  └── Experiment
        ├── Configuration Snapshot
        ├── Retrieval Traces
        └── Metrics
```

## 🛣️ Roadmap

### Phase 0 — Foundation
- [ ] Repository structure
- [ ] Backend + frontend applications
- [ ] PostgreSQL + pgvector
- [ ] Docker Compose
- [x] CI
- [ ] Configuration and environment management

### Phase 1 — Ingestion
- [ ] Knowledge bases
- [ ] PDF / Markdown / text ingestion
- [ ] Chunking pipeline
- [ ] Embeddings
- [ ] Chunk Inspector
- [ ] Metadata

### Phase 2 — Retrieval
- [ ] Vector search
- [ ] Keyword / BM25 retrieval
- [ ] Hybrid retrieval
- [ ] Metadata filtering
- [ ] Retrieval Playground
- [ ] Retrieval traces

### Phase 3 — Reranking
- [ ] Reranker interface
- [ ] Cross-encoder reranking
- [ ] Ranking comparison
- [ ] Per-stage score visualization

### Phase 4 — Evaluation
- [ ] Evaluation datasets
- [ ] Recall@K
- [ ] Precision@K
- [ ] Hit rate
- [ ] MRR
- [ ] NDCG
- [ ] Experiment runs
- [ ] Side-by-side comparison

### Phase 5 — Open-source extensibility
- [ ] Embedding provider adapters
- [ ] LLM provider adapters
- [ ] Pluggable retrieval strategies
- [ ] Exportable experiment results
- [ ] Public extension documentation

## 🧭 What Spurel is not

Spurel is intentionally **not**:
- a general-purpose AI agent platform
- an MCP client
- a workflow automation engine
- a generic ChatGPT clone
- another basic “chat with your PDF” demo

Spurel is about **retrieval engineering**.

## 🤝 Contributing

Spurel is being built in public. Contributions will be welcome as the foundation lands.

Good contribution areas:
- chunking strategies
- retriever adapters
- rerankers
- evaluation metrics
- parsers
- visualization improvements
- documentation
- reproducible RAG benchmarks

Before a large change, please open an issue describing the proposal so the design can stay coherent.

## 🌱 Project philosophy

1. **Retrieval first** — optimize evidence before generation.
2. **Inspectable by default** — important decisions should be visible.
3. **Measure before tuning** — improvements need evaluation.
4. **Provider-independent boundaries** — infrastructure should be replaceable.
5. **Reproducible experiments** — configurations and results should be traceable.
6. **Simple before clever** — add complexity only when it solves a demonstrated problem.
7. **Open by design** — useful primitives should be reusable outside the UI.

<p align="center">
  <strong>Spurel</strong><br/>
  <sub>See what your RAG pipeline is really doing.</sub>
</p>

<p align="center">
  ⭐ Star the repository if you want to follow the build.
</p>
