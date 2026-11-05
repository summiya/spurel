"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";

import { Icon } from "@/components/icons";
import { ProviderStatusPanel } from "@/components/live/provider-status";
import { StageTimingBreakdown } from "@/components/live/stage-timings";
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel } from "@/components/ui";
import { useDemoToast } from "@/components/workbench-shell";
import { liveError, workspaceFetch } from "@/lib/live-client";
import type { LiveDocument, LiveKnowledgeBase } from "@/lib/live-types";
import {
  describeRetrievalFilters,
  parseRetrievalMetadataFilters,
  retrievalFiltersKey,
  type DocumentMediaType,
  type RetrievalMetadataFilters,
} from "@/lib/retrieval-filter-types";
import {
  isRetrievalResult,
  mainScore,
  otherScore,
  type RetrievalMatch,
  type RetrievalMode,
  type RetrievalResult,
  type RetrievalTraceDetail,
} from "@/lib/retrieval-types";
import { useWorkspacePages } from "@/lib/use-workspace-pages";

interface Props {
  initialKnowledgeBaseId?: string;
}

interface CompletedRun {
  knowledgeBaseId: string;
  knowledgeBaseName: string;
  result: RetrievalResult;
  filters: RetrievalMetadataFilters | null;
}

function duration(value: number): string {
  return value.toFixed(1) + " ms";
}

function formatDate(raw: string): string {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
}

function modeTitle(mode: RetrievalMode): string {
  return mode === "hybrid"
    ? "Hybrid · RRF"
    : mode === "keyword"
      ? "Keyword · PostgreSQL FTS"
      : "Vector · cosine";
}

function EvidenceItem({
  item,
  mode,
  selected,
  onSelect,
}: {
  item: RetrievalMatch;
  mode: RetrievalMode;
  selected: boolean;
  onSelect: () => void;
}) {
  const score = mainScore(item, mode);
  return (
    <button
      type="button"
      className={"evidence-result " + (selected ? "selected" : "")}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <div className="result-heading">
        <span className="result-rank">{String(item.rank).padStart(2, "0")}</span>
        <strong>
          Document {item.document_id.slice(0, 8)} · Chunk {item.chunk_index + 1}
        </strong>
        <span className="retrieval-score">
          {score.label}: {score.value}
        </span>
      </div>
      <p>{item.text}</p>
      <div className="tag-row">
        <span className="tag">
          Source {item.start_offset}–{item.end_offset}
        </span>
        {item.page_start != null ? (
          <span className="tag">
            PDF page {item.page_start}
            {item.page_end !== item.page_start ? `–${item.page_end}` : ""}
            {item.ocr_used ? " · OCR" : ""}
          </span>
        ) : null}
        {mode === "hybrid" ? (
          <>
            <span className="tag">
              {item.vector_rank === null || item.vector_rank === undefined
                ? "Not in vector pool"
                : `Vector rank #${item.vector_rank}`}
            </span>
            <span className="tag">
              {item.keyword_rank === null || item.keyword_rank === undefined
                ? "Not in keyword pool"
                : `Keyword rank #${item.keyword_rank}`}
            </span>
            {item.candidate_rank != null ? (
              <span className="tag">
                RRF candidate #{item.candidate_rank} → reranked #{item.rerank_rank}
              </span>
            ) : null}
          </>
        ) : null}
      </div>
    </button>
  );
}

export function LiveRetrievalLabPage({ initialKnowledgeBaseId }: Props) {
  const notify = useDemoToast();
  const bases = useWorkspacePages<LiveKnowledgeBase>("/api/workspace/knowledge-bases");
  const [preferredBaseId, setPreferredBaseId] = useState(initialKnowledgeBaseId ?? "");
  const knowledgeBase =
    bases.items.find((base) => base.id === preferredBaseId) ?? bases.items[0] ?? null;
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<RetrievalMode>("keyword");
  const [topK, setTopK] = useState(10);
  const [candidateK, setCandidateK] = useState(50);
  const [rrfK, setRrfK] = useState(60);
  const [rerank, setRerank] = useState(false);
  const [documentFilterId, setDocumentFilterId] = useState("");
  const [mediaType, setMediaType] = useState<DocumentMediaType | "">("");
  const [filenameContains, setFilenameContains] = useState("");
  const [dateAfter, setDateAfter] = useState("");
  const [dateBefore, setDateBefore] = useState("");
  const documents = useWorkspacePages<LiveDocument>(
    knowledgeBase ? `/api/workspace/knowledge-bases/${knowledgeBase.id}/documents` : null,
  );
  const rawMetadata = {
    ...(documentFilterId ? { document_ids: [documentFilterId] } : {}),
    ...(mediaType ? { media_types: [mediaType] } : {}),
    ...(filenameContains.trim() ? { filename_contains: filenameContains.trim() } : {}),
    ...(dateAfter ? { created_after: new Date(dateAfter + "T00:00:00.000Z").toISOString() } : {}),
    ...(dateBefore
      ? { created_before: new Date(dateBefore + "T23:59:59.999Z").toISOString() }
      : {}),
  };
  const hasMetadata = Object.keys(rawMetadata).length > 0;
  const activeFilters = hasMetadata ? parseRetrievalMetadataFilters(rawMetadata) : null;
  const invalidFilter = hasMetadata && !activeFilters;
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [run, setRun] = useState<CompletedRun | null>(null);
  const [preferredChunk, setPreferredChunk] = useState("");
  const [trace, setTrace] = useState<RetrievalTraceDetail | null>(null);
  const [traceError, setTraceError] = useState("");
  const [traceLoading, setTraceLoading] = useState(false);
  const sequence = useRef(0);

  const currentRun = run?.knowledgeBaseId === knowledgeBase?.id ? run : null;
  const result = currentRun?.result;
  const chosen =
    result?.matches.find((item) => item.chunk_id === preferredChunk) ?? result?.matches[0];
  const editedSinceRun = Boolean(
    result &&
    (query.trim() !== result.query ||
      mode !== result.mode ||
      topK !== result.top_k ||
      (result.mode === "hybrid" &&
        (candidateK !== result.candidate_k ||
          rrfK !== result.rrf_k ||
          rerank !== Boolean(result.rerank))) ||
      retrievalFiltersKey(activeFilters) !== retrievalFiltersKey(currentRun?.filters)),
  );

  function changeBase(id: string) {
    sequence.current += 1;
    setPreferredBaseId(id);
    setDocumentFilterId("");
    setMediaType("");
    setFilenameContains("");
    setDateAfter("");
    setDateBefore("");
    setRun(null);
    setError("");
    setRunning(false);
    setTrace(null);
    setTraceError("");
    setTraceLoading(false);
    setPreferredChunk("");
  }

  function updateTopK(value: number) {
    const next = Math.max(1, Math.min(100, value));
    setTopK(next);
    setCandidateK((current) => Math.max(current, next));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (!knowledgeBase || !normalized || normalized.length > 8000 || running || invalidFilter)
      return;
    if (
      mode === "hybrid" &&
      rerank &&
      !window.confirm(
        "Run explicit cross-encoder reranking? This sends selected document excerpts to your configured reranker service, which may incur charges.",
      )
    )
      return;
    const id = ++sequence.current;
    const target = knowledgeBase.id;
    const submittedMode = mode;
    const payload = {
      query: normalized,
      top_k: topK,
      ...(mode === "hybrid"
        ? { candidate_k: candidateK, rrf_k: rrfK, ...(rerank ? { rerank: true } : {}) }
        : {}),
      ...(activeFilters ? { filters: activeFilters } : {}),
    };
    setRunning(true);
    setError("");
    setRun(null);
    setTrace(null);
    setTraceError("");
    setPreferredChunk("");
    try {
      const raw = await workspaceFetch<unknown>(
        `/api/workspace/knowledge-bases/${target}/retrieval/${submittedMode}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (
        !isRetrievalResult(raw) ||
        raw.mode !== submittedMode ||
        Boolean(raw.rerank) !== (submittedMode === "hybrid" && rerank)
      ) {
        throw new Error("The retrieval API returned an unexpected response.");
      }
      if (id !== sequence.current) return;
      if (
        activeFilters &&
        retrievalFiltersKey(raw.filters) !== retrievalFiltersKey(activeFilters)
      ) {
        throw new Error("The backend did not confirm the requested document metadata filters.");
      }
      setRun({
        knowledgeBaseId: target,
        knowledgeBaseName: knowledgeBase.name,
        result: raw,
        filters: activeFilters,
      });
      notify(
        `Saved retrieval trace ${raw.trace_id.slice(0, 8)} · ${raw.matches.length} result(s).`,
      );
    } catch (cause) {
      if (id === sequence.current) {
        setError(
          liveError(cause) +
            (submittedMode === "keyword"
              ? ""
              : " For vector and hybrid modes, also check your embedding provider credentials and indexed embedding space."),
        );
      }
    } finally {
      if (id === sequence.current) setRunning(false);
    }
  }

  async function loadPersistedTrace() {
    if (!currentRun || traceLoading) return;
    const id = ++sequence.current;
    setTraceLoading(true);
    setTraceError("");
    try {
      const saved = await workspaceFetch<RetrievalTraceDetail>(
        `/api/workspace/knowledge-bases/${currentRun.knowledgeBaseId}/retrieval/traces/${currentRun.result.trace_id}`,
      );
      if (id !== sequence.current) return;
      if (saved.id !== currentRun.result.trace_id || saved.mode !== currentRun.result.mode) {
        throw new Error("Persisted retrieval trace does not match the completed run.");
      }
      setTrace(saved);
    } catch (cause) {
      if (id === sequence.current) setTraceError(liveError(cause));
    } finally {
      if (id === sequence.current) setTraceLoading(false);
    }
  }

  async function copyExcerpt(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      notify("Exact retrieved excerpt copied.");
    } catch {
      notify("Clipboard unavailable in this browser.");
    }
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="LIVE RETRIEVAL ENGINEERING"
        title="Retrieval lab"
        description="Query your actual active index, inspect the original rankings and examine persisted retrieval traces."
        badge="Live FastAPI results"
        action={
          <Link href="/knowledge-bases" className="button ghost compact">
            <Icon name="database" size={15} /> Manage sources
          </Link>
        }
      />
      <ProviderStatusPanel purpose="embedding" />
      <div className="inline-notice">
        <Icon name="shield" size={17} />
        All results, scores and timings are returned by your own Spurel backend. Keyword mode uses
        PostgreSQL full-text search (not BM25). Vector and Hybrid can call the configured embedding
        provider.
      </div>
      <Panel title="Query composer" hint="Explicit queries only — no automatic model requests">
        {bases.loading ? (
          <LoadingState label="Loading your knowledge bases" />
        ) : bases.error ? (
          <ErrorState description={bases.error} onRetry={bases.refresh} />
        ) : bases.items.length === 0 ? (
          <EmptyState
            icon="database"
            title="No knowledge bases available"
            description="Create a collection and process some documents before searching."
            action={
              <Link href="/knowledge-bases" className="button primary">
                Open Knowledge Bases
              </Link>
            }
          />
        ) : (
          <form onSubmit={submit}>
            <div className="retrieval-base-row">
              <div>
                <label className="field-label" htmlFor="retrieval-knowledge-base">
                  Knowledge base
                </label>
                <select
                  id="retrieval-knowledge-base"
                  className="select-control"
                  value={knowledgeBase?.id ?? ""}
                  disabled={running}
                  onChange={(event) => changeBase(event.target.value)}
                >
                  {bases.items.map((base) => (
                    <option value={base.id} key={base.id}>
                      {base.name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                className="button ghost compact"
                disabled={bases.loadingMore || running}
                onClick={bases.refresh}
              >
                <Icon name="refresh" size={14} /> Refresh collections
              </button>
            </div>
            {bases.hasMore ? (
              <button
                type="button"
                className="button ghost compact live-load-more"
                disabled={bases.loadingMore || running}
                onClick={() => void bases.loadMore()}
              >
                {bases.loadingMore ? "Loading…" : "Load more knowledge bases"}
              </button>
            ) : null}
            <label htmlFor="retrieval-query" className="field-label">
              Search query
            </label>
            <textarea
              id="retrieval-query"
              className="textarea-control retrieval-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              required
              maxLength={8000}
              disabled={running}
              placeholder="Enter a question or search phrase from your indexed documents..."
            />
            <div className="retrieval-filter-panel">
              <strong>Document metadata filters (optional)</strong>
              <p className="text-hint">
                Restrict which indexed documents can be ranked. All selected criteria must match;
                filename search treats % and _ as literal characters. Editing filters does not run a
                query.
              </p>
              <div className="retrieval-config-grid">
                <div>
                  <label htmlFor="filter-document" className="field-label">
                    Document
                  </label>
                  <select
                    id="filter-document"
                    className="select-control"
                    disabled={running || documents.loading}
                    value={documentFilterId}
                    onChange={(event) => setDocumentFilterId(event.target.value)}
                  >
                    <option value="">All documents</option>
                    {documents.items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.filename}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="filter-type" className="field-label">
                    File type
                  </label>
                  <select
                    id="filter-type"
                    className="select-control"
                    disabled={running}
                    value={mediaType}
                    onChange={(event) => setMediaType(event.target.value as DocumentMediaType | "")}
                  >
                    <option value="">All file types</option>
                    <option value="application/pdf">PDF</option>
                    <option value="text/markdown">Markdown</option>
                    <option value="text/plain">Text</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="filter-filename" className="field-label">
                    Filename contains
                  </label>
                  <input
                    id="filter-filename"
                    className="input-control"
                    type="text"
                    maxLength={100}
                    value={filenameContains}
                    disabled={running}
                    onChange={(event) => setFilenameContains(event.target.value)}
                    placeholder="e.g. handbook"
                  />
                </div>
                <div>
                  <label htmlFor="filter-after" className="field-label">
                    Uploaded on or after (UTC)
                  </label>
                  <input
                    id="filter-after"
                    className="input-control"
                    type="date"
                    value={dateAfter}
                    disabled={running}
                    onChange={(event) => setDateAfter(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="filter-before" className="field-label">
                    Uploaded on or before (UTC)
                  </label>
                  <input
                    id="filter-before"
                    className="input-control"
                    type="date"
                    value={dateBefore}
                    disabled={running}
                    onChange={(event) => setDateBefore(event.target.value)}
                  />
                </div>
              </div>
              {documents.error ? (
                <p role="alert" className="text-hint">
                  {documents.error}
                </p>
              ) : null}
              {documents.hasMore ? (
                <button
                  type="button"
                  className="button ghost compact"
                  onClick={() => void documents.loadMore()}
                  disabled={documents.loadingMore || running}
                >
                  {documents.loadingMore ? "Loading…" : "Load more documents for selection"}
                </button>
              ) : null}
              {invalidFilter ? (
                <p role="alert" className="text-hint">
                  Invalid metadata filter: check the filename and date range.
                </p>
              ) : null}
              <p className="text-hint">
                Scope: {describeRetrievalFilters(activeFilters)}. Only the selected knowledge base
                is searched.
              </p>
            </div>
            <div className="retrieval-config-grid">
              <div>
                <span className="field-label">Retrieval strategy</span>
                <div className="segmented-control" role="group" aria-label="Retrieval strategy">
                  {(["keyword", "vector", "hybrid"] as const).map((candidate) => (
                    <button
                      key={candidate}
                      type="button"
                      className={"segment-button " + (mode === candidate ? "selected" : "")}
                      aria-pressed={mode === candidate}
                      disabled={running}
                      onClick={() => setMode(candidate)}
                    >
                      {candidate === "keyword"
                        ? "Keyword"
                        : candidate === "vector"
                          ? "Vector"
                          : "Hybrid"}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label htmlFor="retrieval-topk" className="field-label">
                  Top K (1–100)
                </label>
                <input
                  id="retrieval-topk"
                  className="input-control"
                  type="number"
                  min={1}
                  max={100}
                  required
                  value={topK}
                  disabled={running}
                  onChange={(event) => updateTopK(Number(event.target.value))}
                />
              </div>
              {mode === "hybrid" ? (
                <>
                  <div>
                    <label htmlFor="retrieval-candidatek" className="field-label">
                      Candidate K ({topK}–100)
                    </label>
                    <input
                      id="retrieval-candidatek"
                      className="input-control"
                      type="number"
                      min={topK}
                      max={100}
                      required
                      value={candidateK}
                      disabled={running}
                      onChange={(event) =>
                        setCandidateK(Math.max(topK, Math.min(100, Number(event.target.value))))
                      }
                    />
                  </div>
                  <div>
                    <label htmlFor="retrieval-rrfk" className="field-label">
                      RRF K (1–1,000)
                    </label>
                    <input
                      id="retrieval-rrfk"
                      className="input-control"
                      type="number"
                      min={1}
                      max={1000}
                      required
                      value={rrfK}
                      disabled={running}
                      onChange={(event) =>
                        setRrfK(Math.max(1, Math.min(1000, Number(event.target.value))))
                      }
                    />
                  </div>
                </>
              ) : null}
            </div>
            {mode === "hybrid" ? (
              <div className="retrieval-filter-panel">
                <label className="field-label" htmlFor="retrieval-rerank">
                  <input
                    id="retrieval-rerank"
                    type="checkbox"
                    checked={rerank}
                    disabled={running}
                    onChange={(event) => setRerank(event.target.checked)}
                  />{" "}
                  Cross-encoder reranking (opt-in)
                </label>
                <p className="text-hint">
                  Re-score the fused candidate pool before selecting Top K. A configured server-side
                  reranker is required. Only clicking Run will send excerpt text to that service; it
                  may incur charges. Default retrieval remains exact RRF.
                </p>
              </div>
            ) : null}
            <div className="retrieval-submit-row">
              <div className="text-hint">
                {mode === "keyword"
                  ? "PostgreSQL FTS · no query-time embedding provider call"
                  : "Vector embeddings may incur API usage; configure the selected provider server-side"}
              </div>
              <button
                type="submit"
                className="button primary"
                disabled={running || !knowledgeBase || !query.trim() || invalidFilter}
              >
                <Icon name={running ? "refresh" : "play"} size={15} />
                {running ? "Running…" : "Run live retrieval"}
              </button>
            </div>
          </form>
        )}
        {error ? (
          <div className="inline-notice live-error" role="alert">
            {error}
          </div>
        ) : null}
      </Panel>

      {running ? <LoadingState label="Retrieving and persisting the result trace" /> : null}

      {result ? (
        <>
          {editedSinceRun ? (
            <div className="inline-notice">
              <Icon name="info" size={15} />
              Your query or configuration has changed. The results below belong to the last
              completed run; click Run live retrieval to update them.
            </div>
          ) : null}
          <Panel
            title="Completed retrieval"
            hint="These values come from the persisted retrieval execution"
          >
            <div className="live-retrieval-metrics">
              <span>
                <small>Mode</small>
                <strong>
                  {modeTitle(result.mode)}
                  {result.rerank ? " · Cross-encoder" : ""}
                </strong>
              </span>
              <span>
                <small>Matches returned</small>
                <strong>
                  {result.matches.length} / {result.top_k}
                </strong>
              </span>
              <span>
                <small>Duration</small>
                <strong>{duration(result.duration_ms)}</strong>
              </span>
              <span>
                <small>Knowledge base</small>
                <strong>{currentRun?.knowledgeBaseName}</strong>
              </span>
            </div>
            <p className="text-hint" aria-label="Applied document metadata filters">
              Applied document scope: {describeRetrievalFilters(currentRun?.filters)}
            </p>
            <div className="retrieval-trace-bar">
              <span className="retrieval-trace-id" title={result.trace_id}>
                Trace ID · {result.trace_id}
              </span>
              <Link
                href={`/traces?kb=${currentRun?.knowledgeBaseId}&trace=${result.trace_id}`}
                className="button ghost compact"
              >
                <Icon name="activity" size={14} /> Browse trace history
              </Link>
              <button
                type="button"
                className="button ghost compact"
                disabled={traceLoading}
                onClick={() => void loadPersistedTrace()}
              >
                <Icon name="clock" size={15} />
                {traceLoading
                  ? "Reading saved trace…"
                  : trace
                    ? "Reload saved trace"
                    : "Inspect saved trace"}
              </button>
            </div>
            <p className="text-hint">
              Executed: “{result.query}”
              {result.mode === "hybrid"
                ? ` · Top K ${result.top_k} · Candidate K ${result.candidate_k} · RRF K ${result.rrf_k}${result.rerank ? ` · Reranked with ${result.reranker_model}` : ""}`
                : ` · Top K ${result.top_k}`}
            </p>
            {traceError ? (
              <div className="inline-notice live-error" role="alert">
                {traceError}
              </div>
            ) : null}
            {trace ? (
              <div className="saved-trace-details" aria-label="Persisted trace details">
                <strong>Verified persisted trace · {formatDate(trace.created_at)}</strong>
                <span>
                  Mode: {trace.mode} · {trace.results.length} saved result(s)
                </span>
                <span>
                  Embedding:{" "}
                  {trace.embedding_provider && trace.embedding_model
                    ? `${trace.embedding_provider} / ${trace.embedding_model} · ${trace.embedding_dimensions} dimensions`
                    : "Not applicable (keyword only)"}
                </span>
                <span>Original duration: {duration(trace.duration_ms)}</span>
                <span>Saved filters: {describeRetrievalFilters(trace.filters)}</span>
                <span>Cross-encoder: {trace.reranker_model ?? "Not used"}</span>
              </div>
            ) : null}
            <StageTimingBreakdown timings={result.stage_timings_ms} />
          </Panel>
          <div className="results-grid">
            <Panel
              title="Ranked evidence"
              hint={`${result.matches.length} real ${result.mode} result(s) from the active chunk index`}
              action={<span className="status-badge success">Real database results</span>}
            >
              {result.matches.length ? (
                <div className="evidence-list">
                  {result.matches.map((item) => (
                    <EvidenceItem
                      key={item.chunk_id}
                      item={item}
                      mode={result.mode}
                      selected={item.chunk_id === chosen?.chunk_id}
                      onSelect={() => setPreferredChunk(item.chunk_id)}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon="search"
                  title="No matching indexed chunks"
                  description="No evidence matched this query in the selected knowledge base. Verify that documents have been successfully processed, or try different terms."
                  action={
                    <Link href="/knowledge-bases" className="button ghost compact">
                      Check indexed documents
                    </Link>
                  }
                />
              )}
            </Panel>
            <Panel title="Evidence inspector" hint="Exact stored chunk and source scores">
              {chosen && currentRun ? (
                <>
                  <div className="inspector-head">
                    <strong>
                      Chunk {chosen.chunk_index + 1} · Rank #{chosen.rank}
                    </strong>
                    <small>Persisted chunk UUID · {chosen.chunk_id}</small>
                  </div>
                  <pre className="live-chunk-preview">{chosen.text}</pre>
                  <div className="retrieval-score-facts">
                    <div>
                      <small>{mainScore(chosen, result.mode).label}</small>
                      <strong>{mainScore(chosen, result.mode).value}</strong>
                    </div>
                    {result.mode === "hybrid" ? (
                      <>
                        {chosen.candidate_rank != null ? (
                          <>
                            <div>
                              <small>Original RRF candidate rank</small>
                              <strong>{chosen.candidate_rank}</strong>
                            </div>
                            <div>
                              <small>Reranked final rank</small>
                              <strong>{chosen.rerank_rank}</strong>
                            </div>
                            <div>
                              <small>Cross-encoder score (raw)</small>
                              <strong>{otherScore(chosen.rerank_score, 5)}</strong>
                            </div>
                            <div>
                              <small>Original RRF score</small>
                              <strong>{otherScore(chosen.rrf_score, 6)}</strong>
                            </div>
                          </>
                        ) : null}
                        <div>
                          <small>Vector pool rank</small>
                          <strong>{chosen.vector_rank ?? "Not present"}</strong>
                        </div>
                        <div>
                          <small>Keyword pool rank</small>
                          <strong>{chosen.keyword_rank ?? "Not present"}</strong>
                        </div>
                        <div>
                          <small>Cosine similarity</small>
                          <strong>{otherScore(chosen.cosine_similarity, 4)}</strong>
                        </div>
                        <div>
                          <small>PostgreSQL FTS</small>
                          <strong>{otherScore(chosen.keyword_score, 5)}</strong>
                        </div>
                      </>
                    ) : null}
                    <div>
                      <small>Source offsets</small>
                      <strong>
                        {chosen.start_offset}–{chosen.end_offset}
                      </strong>
                    </div>
                    {chosen.page_start != null ? (
                      <div>
                        <small>PDF source page</small>
                        <strong>
                          {chosen.page_start}
                          {chosen.page_end !== chosen.page_start ? `–${chosen.page_end}` : ""}
                          {chosen.ocr_used ? " · OCR" : ""}
                        </strong>
                      </div>
                    ) : null}
                    <div>
                      <small>Document ID</small>
                      <strong>{chosen.document_id}</strong>
                    </div>
                    <div>
                      <small>Chunk ID</small>
                      <strong>{chosen.chunk_id}</strong>
                    </div>
                  </div>
                  <div className="retrieval-inspector-actions">
                    <Link
                      href={`/chunks?kb=${currentRun.knowledgeBaseId}&doc=${chosen.document_id}`}
                      className="button ghost compact"
                    >
                      <Icon name="layers" size={14} /> Inspect document
                    </Link>
                    <button
                      type="button"
                      className="button ghost compact"
                      onClick={() => void copyExcerpt(chosen.text)}
                    >
                      <Icon name="copy" size={14} /> Copy excerpt
                    </button>
                  </div>
                  <p className="text-hint">
                    Scores are raw backend values, not percentages. Cosine, PostgreSQL full-text
                    relevance and RRF are different scales and cannot be directly compared.
                  </p>
                </>
              ) : (
                <EmptyState
                  title="No evidence selected"
                  description="Run a query that matches indexed chunks, then choose a result to inspect."
                />
              )}
            </Panel>
          </div>
        </>
      ) : !running && !error ? (
        <EmptyState
          icon="search"
          title="Run a query to inspect real evidence"
          description="Choose a knowledge base with indexed documents, enter a query and select Keyword, Vector or Hybrid. No sample results are shown on this page."
        />
      ) : null}
    </div>
  );
}
