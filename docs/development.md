# Local development and CI

[← README](../README.md) · [Architecture](architecture.md) · [Roadmap](roadmap.md) · [Benchmark gates](quality-gate-ci.md)

This guide covers Spurel's **working pre-alpha backend** and **placeholder Next.js frontend**. The Docker Compose configuration is for **localhost development, not production**.

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
| Next.js placeholder | http://127.0.0.1:3000 | Backend healthy |

The `Makefile` passes your local UID/GID to the frontend container so the Next.js process can safely write bind-mounted source files on Linux. Its `node_modules` and `.next` directories use named volumes.

The following commands may also be useful:

```bash
make init      # Generate/validate .env without starting Docker or exposing the token
make migrate   # Apply pending Alembic upgrades
make backend   # Follow backend logs
make frontend  # Follow frontend logs
```

**Service names:** `postgres`, `migrate`, `backend`, `frontend`. The backend communicates with the DB using `postgres:5432` inside the Compose network, not `localhost`.

## Environment and secrets

`make init` copies `.env.example` to the ignored `.env` on first use, generates a strong random `SPUREL_API_TOKEN`, and restricts its permissions to the file owner on POSIX systems. It **does not replace** an existing valid token or provider key. Do not print, commit, or share your `.env`.

| Variable | Purpose | Notes |
| --- | --- | --- |
| `SPUREL_API_TOKEN` | Shared bearer token for business API routes | Required; minimum 32 printable ASCII characters |
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

**Never place this token in `NEXT_PUBLIC_*` environment variables or send it from browser JavaScript.** Spurel currently has **no** user/session authentication, RBAC or true tenant authorization. The current frontend is only a placeholder and does not expose an authenticated client flow.

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

The host `DATABASE_URL` uses `localhost`. Do not run another API container on the same host port. The frontend can also run separately with Node 22 and `npm install` / `npm run dev` from `frontend/`.

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
| Local Compose smoke | Full-stack Docker build/up, migrations, backend auth and health, frontend HTTP, cleanup |

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
