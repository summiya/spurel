# Local development and CI

[← README](../README.md) · [Architecture](architecture.md) · [Roadmap](roadmap.md) · [Benchmark gates](quality-gate-ci.md)

This guide covers Spurel's **working pre-alpha backend** and Next.js frontend, including live source, chunk, retrieval, trace-comparison, evaluation and RAG answer views. The Overview frontend follow-up adds read-only summaries using those existing endpoints. The Docker Compose configuration is for **localhost development, not production**.

## Requirements and startup

Install Docker Desktop / Docker Engine with **Compose v2**, Python 3 (for local environment bootstrapping), and Make. On Windows, WSL2 is the recommended shell environment for the Make targets.

Run these commands at the repository root:

```bash
make up       # Create .env if needed; build images, migrate, start and await healthy services
make status   # Smoke-check DB-backed API, bearer authentication and Next.js
make ps       # Show container state
make logs     # Stream all service logs
make down     # Stop containers and preserve DB/document volumes
```

| Component | Default address | Startup prerequisite |
| --- | --- | --- |
| PostgreSQL 17 + pgvector | 127.0.0.1:5432 | Docker |
| Alembic migrator | One-shot service; no port | PostgreSQL healthy |
| FastAPI backend | http://127.0.0.1:8000 | Migrations completed |
| Next.js source/chunk/retrieval workbench | http://127.0.0.1:3000 | Backend healthy |

The `Makefile` passes your local UID/GID to the frontend container so the Next.js process can safely write bind-mounted source files on Linux. Its `node_modules` and `.next` directories use named volumes.

The following commands may also be useful:

```bash
make init      # Generate/validate .env without starting Docker or exposing the token
make migrate   # Apply pending Alembic upgrades
make backend   # Follow backend logs
make frontend  # Follow frontend logs
```

**Service names:** `postgres`, `migrate`, `backend`, `frontend`. The backend communicates with the DB using `postgres:5432` inside the Compose network, not `localhost`.

## Live knowledge bases, documents and chunk inspection (SP-10–SP-11)

After pulling SP-10, run `make up` from the repository root, **including on an
existing installation**. The bootstrap adds two new strong random secrets to
your ignored `.env` if they are missing, without replacing your existing
PostgreSQL settings, API token or provider key:

```bash
make up
grep '^SPUREL_FRONTEND_OPERATOR_PASSWORD=' .env
```

Treat that printed value as a private local password. Open
`http://127.0.0.1:<your SPUREL_FRONTEND_PORT>/knowledge-bases`, enter the
password and use the live collection/document page. You can create/list
knowledge bases, upload/list text, Markdown or unencrypted text-extractable PDF
documents (max **25 MB**) and trigger processing. Indexing requires a valid
`OPENAI_API_KEY`; without one, document uploads still work but indexing fails
with a service-unavailable message.

For **SP-11**, open `/chunks` after signing in, or click **Inspect chunks**
next to an uploaded document. The page lists actual database-backed
knowledge bases, documents and saved chunk-set versions, including the active
index, historical snapshots, stored text, source character offsets, chunk UUIDs,
embedding counts and `processing/ready/failed` status. These reads never
alter the active version. Loading more and searching the currently loaded
chunks are explicitly distinguished from full-index searching. Documents
without a successfully published index show no active chunks.

The frontend keeps a **signed, 8-hour, HTTP-only, SameSite=Strict** local
operator cookie. The Next.js server alone knows the backend `SPUREL_API_TOKEN`
and calls `http://backend:8000` within Compose. Browser write requests require
a same-origin `Origin` header; unknown paths and identifiers are not forwarded
via a generic proxy. Signing out clears the cookie. This simple single-operator
access is **not a production login or multi-tenant authorization system**.

The SP-15 branch connects the RAG answer page to real FastAPI generation.
The Overview frontend follow-up uses real, loaded source/retrieval/evaluation records. It does not claim global totals, unmeasured pipeline health or uncomputed trends.

## Live Retrieval Lab (SP-12)

After signing in, open `/retrieval` or choose **Search this knowledge base**
from the Knowledge Bases screen. The Retrieval Lab submits a query to the
real backend **only when you click Run live retrieval**. Choose one of:

- **Keyword** (default): PostgreSQL `websearch_to_tsquery` and `ts_rank_cd`;
  no query-time embedding API call. This is not BM25.
- **Vector**: exact pgvector cosine ranking with the configured query embedding
  provider. This can require `OPENAI_API_KEY` and incur model usage charges.
- **Hybrid**: parallel vector and keyword ranking fused by reciprocal rank
  fusion, configurable `top_k`, `candidate_k` and `rrf_k`. It can also
  incur query embedding API charges.

The UI displays **raw** backend score units, ranked chunk IDs and source
offsets, actual duration and the persisted trace ID. **Inspect saved trace**
reads provider/model metadata and the stored trace snapshot. The
history/comparison UI is implemented in SP-13. Changing the query/settings
without running again leaves previous results clearly marked as old.

**First index documents** from Knowledge Bases. An uploaded but unprocessed
document has no active searchable chunks, so retrieval returns no matches.
The session cookie and server-only `SPUREL_API_TOKEN` secure these two new
allowlisted endpoints; no secrets are sent to browser JavaScript.

## Live saved-trace history and comparison (SP-13)

Open `/traces` after signing in, or click **Browse trace history** after
running Retrieval Lab. The page lists saved retrieval queries newest first,
with mode, timestamp, duration, result count and the recorded configuration.
Click **View saved evidence** to read the persisted snapshot. Select
**Trace A** and a distinct **Trace B**, then click **Compare saved traces**.
The backend returns per-chunk alignment, first and second ranks, signed
rank deltas, first-only and second-only counts, Jaccard overlap, raw score
snapshots and timing difference. The frontend does not generate synthetic
scores. An overlap ratio of null for two empty result sets is shown as N/A.

For trustworthy interpretation, compare runs with the same query and
prefer the same scoring mode. The UI warns when queries or modes differ.
**Rank movement is descriptive, not ground-truth retrieval-quality
evaluation**; the latter is a separate SP-14 feature. These operations
read already-persisted snapshots and do not call model providers, modify
documents or rerun retrieval.

Two exact server-side Next.js endpoints implement the feature: operator
authenticated `GET /.../retrieval/traces` with bounded pagination and
authenticated, same-origin `POST /.../retrieval/trace-comparisons` with
two validated distinct UUIDs. Existing secrets and DB migrations suffice.

## SP-14: live evaluation workbench (merged)

The `/evaluations` page requires the existing local operator session and reads actual
FastAPI/PostgreSQL evaluation datasets and saved benchmark runs. Select a knowledge base,
create a dataset, choose active chunks from an indexed document, assign relevance grades
0–3 (at least one relevant judgment), and save a labeled query. Run the judgment audit
before benchmarking. Stale labels block evaluation until corrected.

Keyword is the default benchmark and avoids query-time embedding calls. Vector and Hybrid
run only when explicitly requested and confirmed, and may use paid embedding APIs. The
backend runs datasets synchronously and accepts at most 100 cases per benchmark.
Only persisted metrics are displayed: mean Precision@K, Recall@K, MRR@K, NDCG@K,
judgment coverage and latency. Loading and comparing saved runs are read-only;
comparisons flag differing case/query sets and retrieval configurations.
Quality gates use explicit Recall drop thresholds; promoting a baseline is an
intentional, separately confirmed write.

The new Next.js routes under `/api/workspace/knowledge-bases/{id}/evaluation-datasets`
authenticate the operator session and enforce exact path, HTTP method and JSON
payload allowlists before forwarding the server-only bearer token. No new migrations
or secrets are required. Local frontend smoke: create an indexed document, create
a labeled case, audit, run Keyword twice, inspect both persisted runs, compare, and
check a quality gate. Do not claim successful live verification until this flow
has been tested in a running Spurel stack.

## SP-15: live RAG answers (merged)

The operator-authenticated `/rag` page uses a dedicated, allowlisted
same-origin Next.js POST endpoint that forwards validated requests only to
`/knowledge-bases/{knowledge_base_id}/rag/answer` using the existing
**server-only** FastAPI token. It rejects cross-origin requests, invalid KB
UUIDs, unsupported settings, malformed/oversized bodies and anonymous calls.
No new backend provider, migration, secret or data store is introduced.

Open `http://localhost:3000/rag` after sign-in, select a knowledge base with
processed documents and provide a query. Top K is 1–20, Candidate K ranges
from Top K to 100, and RRF K is 1–1,000. The UI makes **no model calls**
until the operator explicitly confirms each generation attempt; hybrid query
embeddings and OpenAI text generation may incur provider charges. The
backend needs `OPENAI_API_KEY` and generation-model configuration.

An answer displays its actual response text, model/provider names, saved
retrieval trace ID, bounded context source labels, excerpt text, chunk UUIDs
and source character offsets. Source labels are clickable but are **not**
automatic claim verification (SP-23). Source and trace deep links lead into
the existing live Chunk Inspector and Trace History. No-result retrievals show
the backend's no-context response, with no invented citations and no
text-generation call. The frontend does not persist conversation history.

CI uses invalid requests, cross-origin rejection and unauthenticated calls to
test the Next.js API route **without submitting a valid paid RAG request**.
The frontend has mocked integration tests for successful answers, no context,
validation, provider errors and explicit consent. Live provider verification
requires an explicitly authorized local manual test.

## Live Overview dashboard (frontend follow-up)

The landing route `/` no longer displays fictional counts or invented trends. It reads
the existing operator-protected knowledge-base, document, retrieval-trace,
evaluation-dataset and benchmark-run **GET** endpoints. Unauthenticated
visitors receive a sign-in prompt and no protected data. Select a knowledge
base to see loaded document/index readiness, newest saved traces and measured
benchmark quality from one selected evaluation dataset. The restored quality
chart plots recorded Recall@K and Precision@K over 7 or 30 days, using the
selected dataset and one exact retrieval configuration plus case count.
The chart only connects stored runs, never invents daily values, and indicates
when the selected period has insufficient data. Load older run-history pages
explicitly when needed; only loaded history is charted. Model calls are not
initiated and no global totals, p95 or other unmeasured statistics are invented.
The overview is intentionally separate from SP-16's unbuilt backend token-aware
chunking.

## SP-16: opt-in token-aware processing (in review)

The Knowledge Bases document panel keeps its existing **Process / Reprocess**
buttons. New adjacent chunk settings permit switching from the unchanged
character default (1,000 characters / 200 overlap) to **model tokens**
(default 512 / 64). Both strategies validate chunk size and overlap. Custom
settings require explicit user confirmation because reprocessing may incur
embedding API charges. An unchanged no-body POST preserves the legacy
processing code path.

When enabled, the backend runs a `tiktoken` encoding for the configured
`SPUREL_EMBEDDING_MODEL`. Token windows fit the requested token count and
also the existing 20,000-character DB safety cap; overlap is bounded in
model tokens. Exact Unicode/source character offsets and old chunk versions
remain untouched. A new version is staged only if chunk boundaries/content
differ; it becomes active only after embedding coverage is validated. Failed
reprocessing does not replace the current active index.

The Chunk Inspector adds read-only `token_count` and `tokenizer_encoding`
to both active and historical chunk views. These counts are calculated when
reading for the **currently configured embedding model**, not persisted at
indexing time, so the displayed count for a historic version can change
when the model encoding changes. Unknown tokenizer models show an unavailable
count; the system does not estimate tokens from word/character heuristics.
The `tiktoken` encoding cache may need internet access on first use.
No provider API request is made solely for token counting.

The new backend processing request body is optional:
```json
{"strategy":"tokens","chunk_size":512,"overlap":64}
```
The frontend allows only these keys and values, and rejects invalid or
cross-origin requests before contacting FastAPI. Processing requires normal
embedding credentials; only explicit Process / Reprocess triggers embedding.

## Environment and secrets

`make init` copies `.env.example` to the ignored `.env` on first use, generates a strong random `SPUREL_API_TOKEN`, and restricts its permissions to the file owner on POSIX systems. It **does not replace** an existing valid token or provider key. Do not print, commit, or share your `.env`.

| Variable | Purpose | Notes |
| --- | --- | --- |
| `SPUREL_API_TOKEN` | Shared bearer token for FastAPI + Next.js server-to-server calls | Required; minimum 32 printable ASCII characters |
| `SPUREL_FRONTEND_OPERATOR_PASSWORD` | Local password used for frontend sign-in | Generated by `make init` |
| `SPUREL_FRONTEND_SESSION_SECRET` | Signing key for HTTP-only session cookies | Generated separately; server-only |
| `SPUREL_BACKEND_URL` | Next.js internal server-to-server FastAPI URL | Compose sets `http://backend:8000` |
| `SPUREL_ENABLE_DOCS` | Set to `1` to expose Swagger/OpenAPI | Off by default; trusted local use only |
| `DATABASE_URL` | Host-process SQLAlchemy/Alembic URL | Compose overrides it for containers |
| `SPUREL_POSTGRES_PASSWORD` | Development PostgreSQL password | Default example is local-only |
| `SPUREL_POSTGRES_PORT` | PostgreSQL host port | Defaults to `5432` |
| `SPUREL_API_PORT` | FastAPI host port | Defaults to `8000` |
| `SPUREL_FRONTEND_PORT` | Next.js host port | Defaults to `3000` |
| `SPUREL_LOCAL_STORAGE_ROOT` | Host-mode document file storage | Compose mounts a persistent named volume |
| `OPENAI_API_KEY` | OpenAI embeddings and generation | Optional for startup, needed for model-backed calls |
| `SPUREL_EMBEDDING_MODEL` / `SPUREL_EMBEDDING_DIMENSIONS` | Embedding provider configuration | Defaults in `.env.example` |
| `SPUREL_GENERATION_MODEL` / `SPUREL_GENERATION_MAX_OUTPUT_TOKENS` | Model-backed RAG answer generation | Set appropriate provider configuration before use |

After `make up`, this command checks the public API liveness:

```bash
curl http://127.0.0.1:8000/health
```

For a protected route, load your local environment into a **trusted shell**:

```bash
set -a
source .env
set +a
curl -H "Authorization: Bearer $SPUREL_API_TOKEN" \
  http://127.0.0.1:8000/knowledge-bases
```

Anonymous protected requests return `401`; a missing or weak *server-side* token configuration disables the protected routes with `503`. `SPUREL_ENABLE_DOCS=1` enables `/docs` and `/openapi.json` without protecting the schema itself, so use it only on a trusted interface.

**Never place this token in `NEXT_PUBLIC_*` environment variables or send it from browser JavaScript.** Spurel has a signed local operator session, but **no** per-user authentication, RBAC or true tenant authorization. SP-10 through SP-15 use this session for protected source,
chunk, retrieval, trace, evaluation and generated-answer workflows. The API proxy
requires a valid operator session and an exact allowlisted route; multi-user login remains unimplemented.

## Run the backend on the host (optional)

For developers who prefer their own Python tooling:

```bash
make init
docker compose --env-file .env up -d postgres
set -a
source .env
set +a

cd backend
python3.13 -m pip install -e ".[dev]"
alembic upgrade head
uvicorn spurel.main:app --reload --host 127.0.0.1 --port 8000
```

The host `DATABASE_URL` uses `localhost`. Do not run another API container on the same host port. The frontend can also run separately with Node 22 and `npm install` / `npm run dev` from `frontend/`. The source and chunk inspector require the server-only operator credentials and a running FastAPI backend. Other screens still use fixtures.

## Tests and quality checks

From `backend/` after installing `.[dev]`:

```bash
ruff check .
ruff format --check src/spurel/documents/processing.py   # Check only changed files
python -m pytest -q -m "not postgres"
```

The legacy Python tree has pre-existing formatting differences. CI enforces Ruff formatting on **changed backend Python files**, while lint runs across the full backend.

**Real PostgreSQL tests must run against a separate DB whose name ends in `_test`.** Start the local PostgreSQL service and create a disposable test DB, once:

```bash
# At repository root, with PostgreSQL running:
docker compose --env-file .env exec -T postgres \
  psql -U spurel -d postgres -c "CREATE DATABASE spurel_test"
```

Then, from `backend/`:

```bash
export DATABASE_URL="postgresql+asyncpg://spurel:spurel@localhost:5432/spurel_test"
export SPUREL_TEST_DATABASE_URL="$DATABASE_URL"
alembic upgrade head
python -m pytest -q -m postgres
```

These sample credentials match the default **development** configuration. If you changed the PostgreSQL password or host port, update the test URL. Do not run these tests against the non-test `spurel` DB. Tests deliberately refuse database names not ending in `_test`.

From `frontend/`:

```bash
npm install --no-audit --no-fund
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

There is **no committed `frontend/package-lock.json` yet**: CI uses `npm install`, not frozen `npm ci`. Dependency locking is a follow-up.

## GitHub Actions

Every pull request and push to `main` triggers five independent checks in [CI](../.github/workflows/ci.yml):

| Job | What it verifies |
| --- | --- |
| Backend checks | Ruff lint, changed-file formatting, non-PostgreSQL pytest |
| PostgreSQL migrations | Legacy-to-current migrations, preserved chunk IDs/embeddings and pgvector |
| PostgreSQL integration | Real database document/retrieval/evaluation scenarios with deterministic embeddings |
| Frontend checks | ESLint, Prettier, TypeScript, Vitest and Next.js production build |
| Local Compose smoke | Full-stack Docker build/up, operator session, KB/upload/chunk reads, real keyword retrieval and two-trace history/comparison, invalid input and CSRF rejection, logout denial; no OpenAI calls |

Real OpenAI keys are **not required** for CI. Two separate workflows — [RAG quality gate](../.github/workflows/rag-quality-gate.yml) and [RAG benchmark gate](../.github/workflows/rag-benchmark-gate.yml) — are **manual/reusable**, not automatic on every PR. See [benchmark-gate CLI setup](quality-gate-ci.md).

The five automatic CI job names should be set as required checks in repository branch-protection settings if you want failed PRs blocked from merging.

## Troubleshooting and data safety

- **Port occupied:** change `SPUREL_POSTGRES_PORT`, `SPUREL_API_PORT` or `SPUREL_FRONTEND_PORT` in `.env`, then rerun `make up`. Update direct-host URLs accordingly.
- **API 401/503:** check that your server and curl session use the same `SPUREL_API_TOKEN`. `make init` refuses weak or ambiguous token values.
- **PostgreSQL not ready:** inspect `make ps` and `make logs`; Alembic runs only after the database health check.
- **Next.js permission problems:** start with `make up` so the frontend gets your UID/GID for source bind mounts.
- **Model-backed endpoints unavailable:** configure the provider key and model names; the stack itself can be healthy without them.

`make down` preserves PostgreSQL and uploaded-document named volumes. **`docker compose down --volumes` deletes local data.** Do not use it as a troubleshooting default.

This setup is not suitable for an internet-exposed service: it has hot reload, shared bearer authentication, developer DB credentials and no production hardening.
