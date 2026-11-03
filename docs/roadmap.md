# Spurel implementation roadmap

[← README](../README.md) · [Development](development.md) · [Architecture](architecture.md)

**Stage:** pre-alpha. The backend API and development infrastructure are functional; the frontend includes real source/chunk inspection with several advanced debugging views still in demo mode. This roadmap tracks the original **SP-01–SP-28** implementation plan, not a claim of a released product.

**Status convention:** ✅ Merged = implemented in `main`; ◐ In review = open PR, not yet available on `main`; ☐ Planned = not implemented.

## Phase 1 — Critical foundations

These tasks were prioritized first because the rest of the workbench depends on a secure, testable, reliable indexing and evaluation core.

| Task | Status | Deliverable | Reference |
| --- | --- | --- | --- |
| SP-01 | ✅ Merged | Bearer authentication on business API routes; public `/health` | [PR #61](https://github.com/summiya/spurel/pull/61) |
| SP-02 | ✅ Merged | Automatic backend/frontend CI and PostgreSQL migration smoke | [PR #62](https://github.com/summiya/spurel/pull/62) |
| SP-03 | ✅ Merged | Real PostgreSQL + pgvector integration tests | [PR #63](https://github.com/summiya/spurel/pull/63) |
| SP-04 | ✅ Merged | Versioned chunk sets; stable IDs for identical reprocessing; historic versions | [PR #64](https://github.com/summiya/spurel/pull/64) |
| SP-05 | ✅ Merged | Staged embeddings, failure recovery, leases and atomic index activation | [PR #65](https://github.com/summiya/spurel/pull/65) |
| SP-06 | ✅ Merged | Validate and audit evaluation judgments against active chunk versions | [PR #66](https://github.com/summiya/spurel/pull/66) |
| SP-07 | ✅ Merged | One-command local Compose environment, token bootstrap and full-stack smoke | [PR #67](https://github.com/summiya/spurel/pull/67) |
| SP-08 | ✅ Merged | Align README, architecture, dev guide and roadmap with actual code | [PR #68](https://github.com/summiya/spurel/pull/68) |

**Result:** A working backend foundation with secure local development, PostgreSQL-backed document processing/retrieval, version history, and benchmark metrics. **Not** production-ready and **not** a finished graphical workbench.

## Phase 2 — Functional frontend

SP-09 adds the interactive shell; SP-10 connects real knowledge bases and
documents; SP-11 adds the live Chunk Inspector. Retrieval, evaluation, trace
comparison and RAG screens remain planned for SP-12–SP-15.

| Task | Priority | Status | Scope / acceptance target |
| --- | --- | --- | --- |
| SP-09 | Critical | ✅ Merged | Responsive workbench, keyboard command palette, theme and demo-only initial screens. [PR #69](https://github.com/summiya/spurel/pull/69) |
| SP-10 | High | ✅ Merged | Local operator session and server-only FastAPI calls; live KB/document create/list/upload/index and pagination. [PR #70](https://github.com/summiya/spurel/pull/70) |
| SP-11 | High | ◐ In review | Operator-protected live Chunk Inspector: source selection, active/historical versions, real persisted text and offsets, embedding status, pagination, empty/error states and tests |
| SP-12 | High | ☐ Planned | Retrieval Playground: issue vector/keyword/hybrid queries and display ranks, scores, traces and configuration |
| SP-13 | High | ☐ Planned | Trace Comparison UI: compare saved retrieval traces and explain candidate/ranking differences |
| SP-14 | High | ☐ Planned | Evaluation Dashboard: label datasets, inspect judgment audits, run benchmarks, compare runs and quality gates |
| SP-15 | Medium | ☐ Planned | RAG Answer UI: queries, answer, source excerpts/labels, trace link and missing-context handling |

**Frontend security requirement:** Do not place `SPUREL_API_TOKEN` in `NEXT_PUBLIC_*`, browser storage, or client JavaScript. The shared bearer token is not a replacement for user authentication or tenant authorization.

**Proposed milestone:** *Spurel v0.2 — Retrieval Workbench*, after the core frontend flows (SP-09–SP-15) are implemented and tested. This is a **target milestone, not an existing release or tag**.

## Phase 3 — Advanced retrieval and ingestion

| Task | Priority | Status | Scope / acceptance target |
| --- | --- | --- | --- |
| SP-16 | High | ☐ Planned | Model-token-aware chunking and accurate token counts/overlap |
| SP-17 | High | ☐ Planned | Recursive, heading/Markdown-aware and sentence-aware chunking strategies |
| SP-18 | High | ☐ Planned | PDF page references, structured extraction and an explicitly configured OCR fallback |
| SP-19 | High | ☐ Planned | Consistent knowledge-base metadata filters across retrieval modes, with tests |
| SP-20 | High | ☐ Planned | pgvector HNSW indexing, recall/latency benchmarks, indexing trade-offs |
| SP-21 | High | ☐ Planned | Pluggable cross-encoder reranking with candidate/rerank/final ranks |
| SP-22 | Medium | ☐ Planned | Per-stage timing and retrieval observability in API traces and workbench |

**Current baseline:** fixed-size **character** chunks, unencrypted text-extractable PDFs, exact pgvector cosine ranking, PostgreSQL **full-text `ts_rank_cd`** keyword ranking, and RRF. There is **no BM25 implementation** even though PostgreSQL keyword search already exists.

## Phase 4 — Quality, extensibility and release

| Task | Priority | Status | Scope / acceptance target |
| --- | --- | --- | --- |
| SP-23 | High | ☐ Planned | Check whether generated source labels actually support answer claims |
| SP-24 | Medium | ☐ Planned | Additional evaluation methods/metrics and calibrated quality reporting |
| SP-25 | High | ☐ Planned | Additional hosted and local embedding/generation adapters, tested at provider boundaries |
| SP-26 | Medium | ☐ Planned | Export experiment configurations, traces, runs and metrics in machine-readable formats |
| SP-27 | High | ☐ Planned | Operational logging, monitoring and trace/error correlation in production-like environments |
| SP-28 | Medium | ☐ Planned | Open-source release checklist, contributor docs, examples and tagged releases |

Provider names, rerankers, semantic chunking, Redis-backed jobs and external data connectors are **not** commitments of current support; they require implementation, security review, integration tests and documentation.

## Known limitations and hardening backlog

These are cross-cutting technical debts, **not completed roadmap tasks**:

1. **Authentication:** One shared API bearer token, no per-user sessions, RBAC or actual tenant authorization. Local work is bound to loopback, not exposed as a public service.
2. **Evaluation race:** Stale judgment checks occur before and after retrieval but run persistence is a separate transaction; a narrow activation window remains. Version pinning or atomic snapshot/persist is future hardening.
3. **Ingestion execution:** Processing still runs in an HTTP request. Lease renewal occurs between embedding batches, so a single provider call longer than the lease can be reclaimed; stale workers are fenced at promotion.
4. **Parsing:** No OCR/scanned PDFs; encrypted PDFs are unsupported; fixed-size chunking counts characters, not model tokens.
5. **Retrieval:** Exact pgvector search only; Postgres keyword scoring is not BM25; no HNSW, filters or reranking.
6. **Frontend:** Live source and chunk inspection use the single-operator local session, but retrieval/evaluation/trace/RAG views still use fixtures. The session is not production identity, RBAC or multi-tenant authorization.
7. **Dependency reproducibility:** Frontend does not yet commit a `package-lock.json`; `npm install` is used, and Docker image tags are not digest-pinned.
8. **Deployment:** Compose is intended for localhost development, with example database credentials and hot reload. The project has no hardened production deployment profile.

## Definition of done

A task is ready for review when it preserves the existing code structure, has focused tests, passes applicable GitHub Actions jobs, explains migrations or breaking changes, and documents user-visible behavior and limitations. The work is considered **merged** only when its PR is actually merged; a green CI run is not proof of production readiness.

Please choose the next task in sequence from this roadmap, rather than conflating the unbuilt UI or future providers with the backend that is already implemented.
