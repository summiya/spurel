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
> **Pre-alpha, not production ready.** The backend has working ingestion, retrieval, RAG and evaluation APIs. The Next.js frontend now has an **interactive design-preview shell** in SP-09 (this PR), using clearly labeled sample data; actual API-backed screens are planned for SP-10–SP-15. Images below are product **concept designs**, not screenshots of a functioning workbench.

[Quick start](#quick-start) · [Implemented today](#implemented-today) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md) · [Development guide](docs/development.md) · [Benchmark CI](docs/quality-gate-ci.md)

## What Spurel does

Spurel helps RAG developers understand **which document chunks were retrieved, how they ranked, whether the answer was grounded, and whether a change improved retrieval quality**.

The current backend supports a measurable path from document upload to retrieval traces and persisted benchmark runs. The approved design is implemented as an interactive, navigable frontend preview, but its metrics, documents and retrieval results are **illustrative**, not backend data.

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
| Next.js interactive preview | http://127.0.0.1:3000 | Navigable demo using sample data, not live backend data |
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

## Frontend preview (SP-09)

The approved midnight-blue, cyan and violet design is implemented in Next.js as a responsive
application shell with keyboard command search (**⌘K / Ctrl+K**), theme switching, and eight
interactive demo views: Overview, Knowledge Bases, Retrieval Lab, Chunk Inspector, Evaluations,
Trace History, RAG Answers, and Settings. You can change retrieval mode and Top K, inspect
different sample documents and chunk versions, compare sample runs, and explore cited example
answers. **Every sample result, metric and document is fabricated for this design preview.**

Frontend protected API calls are deliberately **not** enabled: a shared backend bearer token
cannot safely be offered to anonymous browser users. The only planned server-only connector
in SP-09 is a public health-check helper. SP-10–SP-15 will implement live workflows after
an appropriate frontend authentication/session boundary is introduced.

## Implemented today

| Capability | Implementation | Where |
| --- | --- | --- |
| Knowledge bases and documents | FastAPI CRUD subset: create/list knowledge bases; upload/list documents; text, Markdown and text-extractable PDF parsing | [Documents](backend/src/spurel/documents/) |
| Chunk inspection | Fixed-size **character** windows with overlap, persisted offsets and UUIDs; read-only version history | [Chunking](backend/src/spurel/infrastructure/chunking/fixed.py) |
| Embeddings | OpenAI embedding adapter; persisted pgvector embeddings keyed by provider/model/dimensions | [Embeddings](backend/src/spurel/embeddings/) |
| Retrieval | Exact pgvector cosine search; PostgreSQL full-text keyword scoring (`ts_rank_cd`, **not BM25**); hybrid Reciprocal Rank Fusion | [Retrieval](backend/src/spurel/retrieval/) |
| Inspectable retrieval | Saved retrieval traces, trace comparisons and graded retrieval metrics | [Retrieval API](backend/src/spurel/retrieval/api.py) |
| Evaluation | Labeled datasets, precision/recall@k, MRR, nDCG, coverage, persisted runs, comparisons, promoted baselines and regression gates | [Evaluation](backend/src/spurel/evaluation_datasets/) |
| Label consistency | Reject new judgments for inactive or foreign chunks; detect stale historical labels before live evaluations; judgment audit endpoint | [Judgment audit](backend/src/spurel/evaluation_datasets/judgment_integrity.py) |
| RAG answers | Hybrid retrieval plus OpenAI text generation, bounded source excerpts and model-requested source labels | [RAG](backend/src/spurel/rag/) |
| Reprocessing | Immutable chunk-set versions, stable UUIDs for unchanged chunks, staged embeddings, fenced retries and atomic activation | [Processing](backend/src/spurel/documents/processing.py) |
| Local developer tools | Full-stack Docker Compose, Alembic, pytest/PostgreSQL integration checks, Ruff, frontend lint/types/tests/build | [Development](docs/development.md) |

**Security boundary:** The frontend does not expose a protected API proxy or pass the backend token to the browser. Until a real user/session boundary is implemented, every interactive frontend screen uses local demo fixtures. Spurel currently authenticates the backend with **one shared bearer token**. Knowledge-base scoped queries are not user-specific tenant authorization. Do **not** expose it as a public multi-user service.

## Not implemented yet

The following are roadmap items, **not current capabilities**: API-connected frontend workflows, token-aware/structured chunking, OCR or scanned-PDF support, BM25, HNSW/ANN indexing, metadata retrieval filters, cross-encoder reranking, citation verification, additional hosted/local model adapters, multi-source connectors, experiment export, durable background ingestion and production-grade multi-user authorization.

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
Next.js interactive demo (backend wiring planned)
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

These images illustrate the planned interface. The repository now serves a responsive React implementation of this design with **sample-only data**. These images remain illustrative mockups; they are not screenshots of live Spurel backend results.

<p align="center">
  <img src="./docs/assets/retrieval-playground.svg" alt="Concept only: retrieval playground with candidate scores" width="100%" />
</p>

<p align="center">
  <img src="./docs/assets/experiment-comparison.svg" alt="Concept only: side-by-side retrieval experiment comparison" width="100%" />
</p>

The future workbench will make source candidates, scoring, chunk boundaries, evaluation runs and experiments visually explorable. The backend primitives exist for several of these features, but their UI has not been implemented.

## Roadmap and contributing

The [roadmap](docs/roadmap.md) tracks **SP-01–SP-28** by phase, distinguishes merged foundations from upcoming work, and lists priorities and acceptance criteria. SP-09 introduces the interactive frontend shell and demo screens. SP-10–SP-15 will connect those screens to real backend workflows through an authenticated server-only boundary.

Spurel is being built in public. For substantial changes, open an issue first and follow the existing architecture and tests. Good contribution areas include retrieval strategies, parsers, evaluation methods, reliable ingestion, UI, and documentation.

Project principles: **retrieval first**, **inspectable by default**, **measure before tuning**, **provider boundaries**, **reproducible experiments**, and **simple before clever**.

---

<p align="center"><strong>Spurel</strong> — See what your RAG pipeline is really doing.</p>
