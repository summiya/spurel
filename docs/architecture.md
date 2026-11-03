# Architecture: implemented backend and future workbench

[← README](../README.md) · [Roadmap](roadmap.md) · [Local development](development.md)

Spurel has working backend APIs and an interactive Next.js frontend. SP-10–SP-14 connect
Knowledge Bases, Documents, live chunk history, retrieval, saved-trace comparison and
evaluation workflows. SP-15 adds operator-authenticated RAG answers using the existing FastAPI service. A frontend follow-up now displays scoped read-only records on the Overview.

## System boundary

```text
                             Next.js live sources / chunks / retrieval / traces
                             + evaluations / SP-15 RAG answers
                                      |
                                      v
                          FastAPI business endpoints
                            shared bearer token
                                      |
                 +--------------------+--------------------+
                 |                    |                    |
              Documents           Retrieval             Evaluation
              and versions        / RAG                  and quality
                 |                    |                    |
          parse → chunk            pgvector cosine        labeled cases
          → stage → embed          PostgreSQL FTS         metrics and runs
          → verify → publish       hybrid RRF             comparison / gates
                 |                    |                    |
                 +--------------------+--------------------+
                                      |
                            PostgreSQL + pgvector
                          + local document blob files
```

FastAPI runs on Python 3.13 and uses Pydantic schemas, application services, interface contracts (ports), async SQLAlchemy repositories and Alembic. The API is protected with a **single shared token**, not personal logins or per-tenant authorization.

| Code location | Responsibility |
| --- | --- |
| [`backend/src/spurel/main.py`](../backend/src/spurel/main.py) | API assembly, protected routers and health |
| [`knowledge_bases/`](../backend/src/spurel/knowledge_bases/) | KB metadata and scoped repository |
| [`documents/`](../backend/src/spurel/documents/) | Upload, parsing, chunking pipeline, immutable chunk-set versions, status and history |
| [`embeddings/`](../backend/src/spurel/embeddings/) | Embedding pipeline and persisted vectors |
| [`retrieval/`](../backend/src/spurel/retrieval/) | Vector/keyword/hybrid retrieval, traces, comparisons, trace evaluation |
| [`rag/`](../backend/src/spurel/rag/) | Hybrid retrieval, bounded prompt context, generated answer and source metadata |
| [`evaluation_datasets/`](../backend/src/spurel/evaluation_datasets/) | Labeled data, benchmarks, baseline history, quality gates and CLI |
| [`infrastructure/`](../backend/src/spurel/infrastructure/) | PDF/text parsers, fixed character chunker, local storage, OpenAI adapters |
| [`backend/migrations/`](../backend/migrations/) | PostgreSQL schema migrations |
| [`frontend/app/`](../frontend/app/) | Operator-protected source management, chunks, retrieval, traces and evaluations; RAG answers connected by SP-15 branch |

## Ingestion and versioned indexing

1. Upload a text, Markdown or **unencrypted, text-extractable PDF** to a knowledge base. File metadata is stored in PostgreSQL and source bytes in local blob storage.
2. Parse the bytes. The current chunker uses fixed-size **character windows** with an optional overlap and exact text offsets. This is not token-aware chunking.
3. Create a new immutable chunk-set version in `processing` state. The previous `active_chunk_version` remains queryable while embedding proceeds.
4. Generate embeddings in batches with the current OpenAI adapter. Persist them using chunk UUID, provider, model and dimensions.
5. Verify complete embedding coverage and promote the staged version in one database transaction. A failed embedding call leaves the older version active.
6. Identical reprocessing reuses existing active chunk UUIDs; a failed/expired attempt can be reclaimed and retried with its original staged chunk IDs.

The indexer uses a per-document processing lease and fenced attempt ID to prevent a stale worker from activating a reclaimed version. **It runs in the HTTP request**, not in a durable job queue. A provider call longer than the lease is a known recovery edge case; see the [roadmap](roadmap.md).

Historical versions, IDs and embeddings remain inspectable, even after activation of a newer version. Old relevance labels are deliberately not cascaded away.

The **SP-11 Chunk Inspector** reads the existing FastAPI document, version and
chunk-inspection endpoints through explicit operator-authenticated Next.js GET
handlers. Active chunks use the normal `/chunks` read endpoint; selecting a
historical version fetches `/versions/{version}/chunks` without promoting it.
The UI exposes persisted text, zero-based chunk index, source offsets and the
number of embedding records, **not** invented similarity/quality scores.
Each list is paginated, and unindexed uploads return empty active chunk lists.
The frontend sends no embedding or generation requests during inspection.

## Retrieval and RAG

**Current retrieval choices:**

- **Vector:** exact cosine-distance ranking over the active chunk version using PostgreSQL + pgvector; no ANN/HNSW index yet.
- **Keyword:** PostgreSQL `websearch_to_tsquery` and `ts_rank_cd` on persisted search vectors; **this is not BM25**.
- **Hybrid:** concurrent keyword/vector retrieval with **Reciprocal Rank Fusion (RRF)**. Source ranks and scores are retained.
- **Traces:** persisted retrieval queries, results and configuration snapshots with trace viewing/comparison APIs.

RAG generation builds a bounded context from traced hybrid matches and calls an OpenAI text-generation adapter. Responses expose the exact source excerpts and labels requested by the system prompt. **Source-label display is not citation/claim verification**; the latter remains planned.

The only implemented external provider adapters are OpenAI-based embeddings and text generation. The architecture has interfaces for more providers, but does **not** currently integrate Ollama, Cohere, Voyage, Anthropic, Gemini or OpenRouter.

### SP-12: live retrieval and trace inspection

The authenticated `/retrieval` page calls one of three **exact, allowlisted**
Next.js POST handlers, each validating a nonempty query (up to 8,000
characters), `top_k` (1–100), plus hybrid `candidate_k >= top_k` (max 100)
and `rrf_k` (1–1,000). The handlers reject cross-origin writes and forward
the backend bearer token only server-side. Retrieval is **not** triggered on
keystrokes. Keyword queries do not call the embedding provider; vector and
hybrid require a configured query embedding model and may incur usage costs.

The UI renders raw cosine similarity, PostgreSQL full-text `ts_rank_cd` and
RRF scores **without mixing their numeric scales**. Every completed search
returns a persisted trace UUID and actual execution duration. A separate,
authenticated GET handler fetches the **saved trace detail** with provider,
model, dimensions and historical ranked results. SP-13 adds live history browsing and comparisons of stored traces.

### SP-13: persisted trace history and read-only comparison

The operator-protected `/traces` frontend lists bounded newest-first trace
pages via exact GET endpoints, and retrieves an immutable ranked-result
snapshot with the existing detail GET. An explicitly invoked comparison
POST validates two **different UUIDs**, uses same-origin CSRF protection,
and calls the existing FastAPI trace-comparison service. The backend
returns shared/unique chunks, aligned ranks and raw score fields,
Jaccard overlap and B−A duration and rank deltas. No provider call or
retrieval reexecution occurs during inspection or comparison.

A negative rank delta indicates a move toward the first rank, not
necessarily better relevance. Cross-query and cross-mode results are
explicitly labeled non-comparable as controlled experiments. The
comparison is descriptive and does **not** calculate graded relevance
metrics or answer quality. Saved traces remain read-only.

## Evaluation and regression protection

- Evaluation datasets hold named cases with graded relevance judgments keyed to persisted **chunk UUIDs**.
- Dataset runs compute precision/recall@k, MRR, nDCG, judgment coverage and duration; run and case metrics are persisted for history.
- Runs can be compared; baselines can be explicitly promoted, resolved and reviewed via promotion history. Quality gates evaluate defined regression thresholds.
- New judgments must point at active chunks in the correct knowledge base. Existing stale or missing references are detectable through the read-only **judgment audit** and block live benchmark runs.
- The evaluator checks labels before and after retrieval to detect active-version changes during a run. Historical benchmark snapshots are preserved, not rewritten.

**Remaining race:** final judgment validation and saving a run occur in separate transactions; a narrow activation window remains. Fully atomic version pinning/persistence is future hardening.

The [benchmark and quality-gate CLIs](quality-gate-ci.md) call the API and can be invoked through manual/reusable GitHub Actions workflows. These workflows are **separate** from automatic pull-request CI.

## API and security

The API has routers for health, knowledge bases, documents, retrieval, evaluation datasets and RAG. Representative routes:

```text
GET  /health
POST /knowledge-bases
POST /knowledge-bases/{knowledge_base_id}/documents
POST /knowledge-bases/{knowledge_base_id}/documents/{document_id}/process
GET  /knowledge-bases/{knowledge_base_id}/documents/{document_id}/versions
POST /knowledge-bases/{knowledge_base_id}/retrieval/hybrid
GET  /knowledge-bases/{knowledge_base_id}/retrieval/traces
POST /knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/evaluate/keyword
GET  /knowledge-bases/{knowledge_base_id}/evaluation-datasets/{dataset_id}/judgment-audit
POST /knowledge-bases/{knowledge_base_id}/rag/answer
```

Except for `GET /health`, the business endpoints require a shared `SPUREL_API_TOKEN`. Swagger/OpenAPI are disabled by default and can be enabled for **trusted local** use with `SPUREL_ENABLE_DOCS=1`.

**SP-10 frontend operator boundary:** The Knowledge Bases and Documents UI can now
use live FastAPI data. It requires a strong locally generated operator password,
verified by the Next.js server, which sets a signed, HTTP-only, SameSite=Strict
cookie (8-hour TTL). The server sends the existing FastAPI bearer token only
to explicit allowlisted source-management endpoints. Browser mutations are
rejected on mismatched `Origin`. This provides a practical **single-operator
development workflow**, not scalable user identity or tenant authorization.

**Important:** Filtering repository operations by knowledge-base ID is not permission-aware tenant isolation. The current bearer token permits access to all knowledge-base routes. Do not deploy this as a public multi-tenant product without real user/session authentication and authorization.

## What is planned, not implemented

The frontend has live source, chunk, retrieval, trace-comparison, evaluation and provider-backed RAG answer inspection. A frontend follow-up summarizes real Overview data without new backend APIs. The following are **not built**: recursive/semantic/token-aware chunking, scanned-PDF OCR, BM25, pgvector ANN/HNSW, metadata filters, rerankers, independent citation/claim verification, non-OpenAI providers, data-source connectors, Redis-backed background jobs, experiment export and production auth/monitoring.

For the exact implementation order and deliverables, use [SP-01–SP-28 roadmap](roadmap.md).
