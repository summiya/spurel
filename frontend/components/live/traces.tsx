"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { Icon } from "@/components/icons";
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel } from "@/components/ui";
import { useDemoToast } from "@/components/workbench-shell";
import { liveError, workspaceFetch } from "@/lib/live-client";
import type { LiveKnowledgeBase } from "@/lib/live-types";
import { describeRetrievalFilters, retrievalFiltersKey } from "@/lib/retrieval-filter-types";
import { otherScore, type RetrievalTraceDetail } from "@/lib/retrieval-types";
import {
  formatTraceScore,
  rankMovement,
  traceScoreLabel,
  type RetrievalTraceSummary,
  type TraceComparison,
  type TraceComparisonResult,
} from "@/lib/trace-history-types";
import { useWorkspacePages } from "@/lib/use-workspace-pages";

interface Props {
  initialKnowledgeBaseId?: string;
  initialTraceId?: string;
}

type LoadedSnapshot = { kb: string; id: string; data: RetrievalTraceDetail };
type LoadedComparison = { kb: string; first: string; second: string; data: TraceComparison };

function when(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown date" : date.toLocaleString();
}

function elapsed(value: number): string {
  return value.toFixed(1) + " ms";
}

function ScoreCell({
  item,
  mode,
}: {
  item: TraceComparisonResult;
  mode: "vector" | "keyword" | "hybrid";
}) {
  const first =
    mode === "vector"
      ? formatTraceScore(item.first_cosine_similarity, 4)
      : mode === "keyword"
        ? formatTraceScore(item.first_keyword_score, 5)
        : formatTraceScore(item.first_rrf_score, 6);
  const second =
    mode === "vector"
      ? formatTraceScore(item.second_cosine_similarity, 4)
      : mode === "keyword"
        ? formatTraceScore(item.second_keyword_score, 5)
        : formatTraceScore(item.second_rrf_score, 6);
  return (
    <span className="trace-score-pair">
      {traceScoreLabel(mode)} · A: {first} / B: {second}
    </span>
  );
}

export function LiveTraceHistoryPage({ initialKnowledgeBaseId, initialTraceId }: Props) {
  const notify = useDemoToast();
  const bases = useWorkspacePages<LiveKnowledgeBase>("/api/workspace/knowledge-bases");
  const [baseId, setBaseId] = useState(initialKnowledgeBaseId ?? "");
  const base = bases.items.find((item) => item.id === baseId) ?? bases.items[0] ?? null;
  const traceRoot = base ? `/api/workspace/knowledge-bases/${base.id}/retrieval` : null;
  const history = useWorkspacePages<RetrievalTraceSummary>(
    traceRoot ? `${traceRoot}/traces` : null,
  );
  const [firstId, setFirstId] = useState(initialTraceId ?? "");
  const [secondId, setSecondId] = useState("");
  const [filter, setFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("all");
  const [snapshot, setSnapshot] = useState<LoadedSnapshot | null>(null);
  const [snapshotError, setSnapshotError] = useState("");
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [comparison, setComparison] = useState<LoadedComparison | null>(null);
  const [comparisonError, setComparisonError] = useState("");
  const [comparisonBusy, setComparisonBusy] = useState(false);
  const serial = useRef(0);

  const first = history.items.find((item) => item.id === firstId) ?? history.items[0] ?? null;
  const second =
    history.items.find((item) => item.id === secondId && item.id !== first?.id) ?? null;
  const detail =
    snapshot && base && first && snapshot.kb === base.id && snapshot.id === first.id
      ? snapshot.data
      : null;
  const compared =
    comparison &&
    base &&
    first &&
    second &&
    comparison.kb === base.id &&
    comparison.first === first.id &&
    comparison.second === second.id
      ? comparison.data
      : null;

  const filtered = useMemo(() => {
    const search = filter.trim().toLowerCase();
    return history.items.filter(
      (item) =>
        (modeFilter === "all" || modeFilter === item.mode) &&
        (item.query.toLowerCase().includes(search) ||
          item.id.toLowerCase().includes(search) ||
          item.mode.toLowerCase().includes(search)),
    );
  }, [history.items, filter, modeFilter]);

  function invalidate() {
    serial.current += 1;
    setSnapshot(null);
    setSnapshotError("");
    setSnapshotBusy(false);
    setComparison(null);
    setComparisonError("");
    setComparisonBusy(false);
  }

  function selectBase(value: string) {
    invalidate();
    setBaseId(value);
    setFirstId("");
    setSecondId("");
    setFilter("");
    setModeFilter("all");
  }

  function selectFirst(value: string) {
    invalidate();
    setFirstId(value);
    if (secondId === value) setSecondId("");
  }

  function selectSecond(value: string) {
    invalidate();
    setSecondId(value);
  }

  async function inspect() {
    if (!base || !first || snapshotBusy) return;
    const stamp = ++serial.current;
    setSnapshotBusy(true);
    setSnapshotError("");
    try {
      const data = await workspaceFetch<RetrievalTraceDetail>(
        `/api/workspace/knowledge-bases/${base.id}/retrieval/traces/${first.id}`,
      );
      if (serial.current !== stamp) return;
      if (data.id !== first.id || data.knowledge_base_id !== base.id) {
        throw new Error("Saved trace did not match the selected knowledge base.");
      }
      setSnapshot({ kb: base.id, id: first.id, data });
    } catch (cause) {
      if (serial.current === stamp) setSnapshotError(liveError(cause));
    } finally {
      if (serial.current === stamp) setSnapshotBusy(false);
    }
  }

  async function compare() {
    if (!base || !first || !second || comparisonBusy) return;
    const stamp = ++serial.current;
    setComparisonBusy(true);
    setComparisonError("");
    try {
      const data = await workspaceFetch<TraceComparison>(
        `/api/workspace/knowledge-bases/${base.id}/retrieval/trace-comparisons`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            first_trace_id: first.id,
            second_trace_id: second.id,
          }),
        },
      );
      if (serial.current !== stamp) return;
      if (data.first.trace_id !== first.id || data.second.trace_id !== second.id) {
        throw new Error("Comparison response did not match the selected trace pair.");
      }
      setComparison({ kb: base.id, first: first.id, second: second.id, data });
      notify("Saved trace comparison loaded. No retrieval rerun or model call was made.");
    } catch (cause) {
      if (serial.current === stamp) setComparisonError(liveError(cause));
    } finally {
      if (serial.current === stamp) setComparisonBusy(false);
    }
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="LIVE RETRIEVAL OBSERVABILITY"
        title="Trace history"
        description="Investigate persisted retrievals, inspect ranked evidence and compare two saved executions."
        badge="Live PostgreSQL traces"
        action={
          <Link href="/retrieval" className="button ghost compact">
            <Icon name="play" size={15} /> Run a query
          </Link>
        }
      />
      <div className="inline-notice">
        <Icon name="shield" size={16} />
        All comparisons use immutable saved trace snapshots from the backend. They do not rerun
        searches or call an embedding model. Rank and overlap changes alone do not measure answer
        quality.
      </div>
      <Panel
        title="Trace workspace"
        hint="Choose the knowledge base that contains your saved retrievals"
      >
        {bases.loading ? (
          <LoadingState label="Loading knowledge bases" />
        ) : bases.error ? (
          <ErrorState description={bases.error} onRetry={bases.refresh} />
        ) : bases.items.length === 0 ? (
          <EmptyState
            icon="database"
            title="No knowledge bases"
            description="Create a knowledge base and run a query before viewing saved traces."
            action={
              <Link href="/knowledge-bases" className="button ghost compact">
                Manage sources
              </Link>
            }
          />
        ) : (
          <>
            <div className="trace-source-chooser">
              <div>
                <label className="field-label" htmlFor="trace-kb">
                  Knowledge base
                </label>
                <select
                  className="select-control"
                  id="trace-kb"
                  value={base?.id ?? ""}
                  onChange={(event) => selectBase(event.target.value)}
                >
                  {bases.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
              <button type="button" className="button ghost compact" onClick={bases.refresh}>
                <Icon name="refresh" size={14} /> Refresh collections
              </button>
            </div>
            {bases.hasMore ? (
              <button
                type="button"
                className="button ghost compact live-load-more"
                disabled={bases.loadingMore}
                onClick={() => void bases.loadMore()}
              >
                {bases.loadingMore ? "Loading…" : "Load more knowledge bases"}
              </button>
            ) : null}
          </>
        )}
      </Panel>

      {base ? (
        <div className="trace-grid">
          <Panel
            title="Saved retrievals"
            hint="Newest first · filter currently loaded records"
            action={
              <button
                type="button"
                className="button ghost compact"
                onClick={() => {
                  invalidate();
                  history.refresh();
                }}
                disabled={history.loading || history.loadingMore}
              >
                <Icon name="refresh" size={14} /> Refresh
              </button>
            }
          >
            <div className="trace-filters">
              <label className="sr-only" htmlFor="trace-search">
                Filter loaded traces
              </label>
              <input
                id="trace-search"
                type="search"
                className="input-control"
                placeholder="Query, mode or trace ID..."
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
              <label className="sr-only" htmlFor="trace-mode-filter">
                Filter retrieval mode
              </label>
              <select
                id="trace-mode-filter"
                className="select-control"
                value={modeFilter}
                onChange={(event) => setModeFilter(event.target.value)}
              >
                <option value="all">All modes</option>
                <option value="keyword">Keyword</option>
                <option value="vector">Vector</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
            {history.loading ? (
              <LoadingState label="Loading saved retrieval history" />
            ) : history.error ? (
              <ErrorState description={history.error} onRetry={history.refresh} />
            ) : history.items.length === 0 ? (
              <EmptyState
                icon="search"
                title="No saved retrievals"
                description="Run one or more queries in Retrieval Lab. Even a zero-result query saves a trace."
                action={
                  <Link href={`/retrieval?kb=${base.id}`} className="button ghost compact">
                    Run a query
                  </Link>
                }
              />
            ) : filtered.length === 0 ? (
              <EmptyState
                title="No loaded traces match"
                description="Clear your filter or load another page to find older runs."
              />
            ) : (
              <div className="trace-list">
                {filtered.map((item) => (
                  <div className="live-trace-list-entry" key={item.id}>
                    <button
                      type="button"
                      className={"trace-row " + (item.id === first?.id ? "active" : "")}
                      aria-pressed={item.id === first?.id}
                      onClick={() => selectFirst(item.id)}
                    >
                      <span className="trace-icon">
                        <Icon name="search" size={17} />
                      </span>
                      <span className="trace-content">
                        <strong>{item.query}</strong>
                        <small>
                          {item.mode} · {when(item.created_at)} · {item.result_count} result(s)
                        </small>
                        <small>
                          ID {item.id.slice(0, 8)} · Top K {item.top_k}
                        </small>
                        {item.filters ? (
                          <small>Filtered · {describeRetrievalFilters(item.filters)}</small>
                        ) : null}
                        {item.reranker_model ? (
                          <small>Cross-encoder · {item.reranker_model}</small>
                        ) : null}
                      </span>
                      <span className="trace-duration">{elapsed(item.duration_ms)}</span>
                    </button>
                    <button
                      type="button"
                      className="button ghost compact trace-compare-target"
                      disabled={item.id === first?.id}
                      aria-label={`Compare ${item.query} as B`}
                      onClick={() => selectSecond(item.id)}
                    >
                      {second?.id === item.id ? "Selected B" : "Use as B"}
                    </button>
                  </div>
                ))}
              </div>
            )}
            {history.hasMore ? (
              <button
                type="button"
                className="button ghost live-load-more"
                disabled={history.loadingMore}
                onClick={() => void history.loadMore()}
              >
                {history.loadingMore ? "Loading…" : "Load older traces"}
              </button>
            ) : null}
            <p className="text-hint">History and filters operate on loaded pages (50 at a time).</p>
          </Panel>
          <Panel
            title="Trace details · A"
            hint="Select a saved run to inspect its exact persisted result snapshot"
            action={first ? <span className="status-badge success">{first.mode}</span> : null}
          >
            {first ? (
              <>
                <h3 className="trace-query-title">{first.query}</h3>
                <div className="trace-stat-grid">
                  <span>
                    <strong>{first.result_count}</strong>
                    <small>Saved results</small>
                  </span>
                  <span>
                    <strong>{elapsed(first.duration_ms)}</strong>
                    <small>Duration</small>
                  </span>
                  <span>
                    <strong>Top {first.top_k}</strong>
                    <small>Requested K</small>
                  </span>
                </div>
                <div className="trace-detail-facts">
                  <span>
                    Trace ID <strong>{first.id}</strong>
                  </span>
                  <span>
                    Created <strong>{when(first.created_at)}</strong>
                  </span>
                  {first.mode === "hybrid" ? (
                    <span>
                      Hybrid pool{" "}
                      <strong>
                        Candidate K {first.candidate_k} · RRF K {first.rrf_k}
                      </strong>
                    </span>
                  ) : null}
                  {first.reranker_model ? (
                    <span>Reranker <strong>{first.reranker_model}</strong></span>
                  ) : null}
                  <span>
                    Embedding{" "}
                    <strong>
                      {first.embedding_model ?? "Not applicable (keyword)"}
                      {first.embedding_dimensions
                        ? ` · ${first.embedding_dimensions} dimensions`
                        : ""}
                    </strong>
                  </span>
                </div>
                <div className="retrieval-inspector-actions">
                  <button
                    type="button"
                    className="button primary compact"
                    disabled={snapshotBusy}
                    onClick={() => void inspect()}
                  >
                    <Icon name="layers" size={14} />
                    {snapshotBusy
                      ? "Reading…"
                      : detail
                        ? "Reload saved evidence"
                        : "View saved evidence"}
                  </button>
                  <Link href={`/retrieval?kb=${base.id}`} className="button ghost compact">
                    <Icon name="play" size={14} /> Run another query
                  </Link>
                </div>
                {snapshotError ? (
                  <div className="inline-notice live-error" role="alert">
                    {snapshotError}
                  </div>
                ) : null}
                {detail ? (
                  <>
                    <p className="text-hint">
                      Saved retrieval scope: {describeRetrievalFilters(detail.filters)}
                      {detail.reranker_model ? ` · Cross-encoder: ${detail.reranker_model}` : ""}
                    </p>
                    <div className="trace-evidence">
                      {detail.results.length ? (
                        detail.results.map((item) => (
                          <div
                            className="trace-evidence-row live-trace-evidence"
                            key={item.chunk_id}
                          >
                            <span className="result-rank">
                              {String(item.rank).padStart(2, "0")}
                            </span>
                            <div>
                              <strong>
                                Chunk {item.chunk_index + 1} · {item.chunk_id.slice(0, 8)}
                              </strong>
                              <p>{item.text}</p>
                              <small>
                                Source offsets {item.start_offset}–{item.end_offset}
                              </small>
                              <small>
                                Raw {traceScoreLabel(detail.mode)}:{" "}
                                {otherScore(
                                  detail.mode === "vector"
                                    ? item.cosine_similarity
                                    : detail.mode === "keyword"
                                      ? item.keyword_score
                                      : item.rrf_score,
                                  detail.mode === "hybrid" ? 6 : detail.mode === "keyword" ? 5 : 4,
                                )}
                              </small>
                              {item.candidate_rank != null ? (
                                <small>
                                  RRF candidate #{item.candidate_rank} → reranked #{item.rerank_rank} · cross-encoder score {otherScore(item.rerank_score, 5)}
                                </small>
                              ) : null}
                              <Link
                                href={`/chunks?kb=${base.id}&doc=${item.document_id}`}
                                className="text-hint"
                              >
                                Inspect original document
                              </Link>
                            </div>
                          </div>
                        ))
                      ) : (
                        <EmptyState
                          title="Zero-result saved trace"
                          description="This completed run returned no indexed chunks; its query and timing are still persisted."
                        />
                      )}
                    </div>
                  </>
                ) : null}
              </>
            ) : (
              <EmptyState
                title="Select a trace"
                description="Choose a saved retrieval on the left to inspect its source data."
              />
            )}
          </Panel>
        </div>
      ) : null}

      {base && history.items.length > 0 ? (
        <Panel
          title="Compare two saved retrievals"
          hint="Read-only comparison · A is the selected trace, B is a second run from this knowledge base"
        >
          <div className="trace-comparison-controls">
            <div>
              <label htmlFor="trace-first" className="field-label">
                Trace A · baseline
              </label>
              <select
                id="trace-first"
                className="select-control"
                value={first?.id ?? ""}
                onChange={(event) => selectFirst(event.target.value)}
              >
                {history.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.mode} · {item.query.slice(0, 70)} · {item.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="trace-second" className="field-label">
                Trace B · comparison
              </label>
              <select
                id="trace-second"
                className="select-control"
                value={second?.id ?? ""}
                onChange={(event) => selectSecond(event.target.value)}
              >
                <option value="">Choose a different saved trace</option>
                {history.items
                  .filter((item) => item.id !== first?.id)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.mode} · {item.query.slice(0, 70)} · {item.id.slice(0, 8)}
                    </option>
                  ))}
              </select>
            </div>
            <button
              type="button"
              className="button primary"
              disabled={!first || !second || comparisonBusy}
              onClick={() => void compare()}
            >
              <Icon name="activity" size={16} />
              {comparisonBusy ? "Comparing…" : "Compare saved traces"}
            </button>
          </div>
          {comparisonError ? (
            <div className="inline-notice live-error" role="alert">
              {comparisonError}
            </div>
          ) : null}
          {compared ? (
            <>
              {!compared.same_query ? (
                <div className="inline-notice">
                  <Icon name="info" size={16} />
                  Different queries: overlap, rank and timing changes reflect both query and
                  retrieval differences. Do not interpret them as a controlled A/B improvement.
                </div>
              ) : null}
              {retrievalFiltersKey(compared.first.filters) !==
              retrievalFiltersKey(compared.second.filters) ? (
                <div className="inline-notice">
                  <Icon name="info" size={16} />
                  Different document filters: these traces searched different document subsets. Rank
                  changes cannot be attributed to ranking quality alone.
                </div>
              ) : null}
              {compared.first.mode !== compared.second.mode ? (
                <div className="inline-notice">
                  <Icon name="info" size={16} />
                  Different retrieval modes: raw cosine, PostgreSQL FTS and RRF scores use different
                  scales and must not be compared numerically across modes.
                </div>
              ) : null}
              <div className="trace-compare-stats">
                <span>
                  <small>Shared chunks</small>
                  <strong>{compared.overlap_count}</strong>
                </span>
                <span>
                  <small>Union of chunks</small>
                  <strong>{compared.union_count}</strong>
                </span>
                <span>
                  <small>Jaccard overlap</small>
                  <strong>
                    {compared.overlap_ratio === null
                      ? "N/A · no chunks"
                      : `${(compared.overlap_ratio * 100).toFixed(1)}%`}
                  </strong>
                </span>
                <span>
                  <small>Only in A / B</small>
                  <strong>
                    {compared.first_only_count} / {compared.second_only_count}
                  </strong>
                </span>
                <span>
                  <small>B duration − A duration</small>
                  <strong>
                    {compared.duration_delta_ms >= 0 ? "+" : ""}
                    {elapsed(compared.duration_delta_ms)}
                  </strong>
                </span>
              </div>
              <div className="trace-run-side-by-side">
                {([compared.first, compared.second] as const).map((side, index) => (
                  <div className="trace-run-side" key={side.trace_id}>
                    <strong>
                      Trace {index === 0 ? "A" : "B"} · {side.mode}
                    </strong>
                    <small>{side.query}</small>
                    <small>
                      Top {side.top_k} · {side.result_count} result(s) · {elapsed(side.duration_ms)}
                    </small>
                    {side.reranker_model ? (
                      <small>Cross-encoder · {side.reranker_model}</small>
                    ) : null}
                    {side.mode === "hybrid" ? (
                      <small>
                        Candidate K {side.candidate_k} · RRF K {side.rrf_k}
                      </small>
                    ) : null}
                    <small>
                      {side.embedding_model ?? "No query embeddings"}
                      {side.embedding_dimensions
                        ? ` · ${side.embedding_dimensions} dimensions`
                        : ""}
                    </small>
                  </div>
                ))}
              </div>
              <h3 className="subsection-title">Aligned ranked evidence</h3>
              {compared.results.length === 0 ? (
                <EmptyState
                  title="Both traces returned no matches"
                  description="There are no chunks to align. The comparison still preserves the queries, timing and configuration."
                />
              ) : (
                <div className="trace-aligned-results">
                  {compared.results.map((item) => (
                    <div className="trace-aligned-row" key={item.chunk_id}>
                      <div className="trace-aligned-heading">
                        <strong>
                          Chunk {item.chunk_index + 1} · {item.chunk_id.slice(0, 8)}
                        </strong>
                        <span
                          className={
                            "status-badge " +
                            (item.rank_delta !== null && item.rank_delta < 0 ? "success" : "")
                          }
                        >
                          {rankMovement(item.rank_delta, item.first_rank, item.second_rank)}
                        </span>
                      </div>
                      <p>{item.text}</p>
                      <div className="trace-aligned-details">
                        <span>Rank A: {item.first_rank ?? "—"}</span>
                        <span>Rank B: {item.second_rank ?? "—"}</span>
                        <span>
                          Source {item.start_offset}–{item.end_offset}
                        </span>
                      </div>
                      {compared.first.mode === compared.second.mode ? (
                        <ScoreCell item={item} mode={compared.first.mode} />
                      ) : (
                        <div className="trace-score-pair">
                          A {traceScoreLabel(compared.first.mode)}:{" "}
                          {formatTraceScore(
                            compared.first.mode === "vector"
                              ? item.first_cosine_similarity
                              : compared.first.mode === "keyword"
                                ? item.first_keyword_score
                                : item.first_rrf_score,
                            compared.first.mode === "hybrid"
                              ? 6
                              : compared.first.mode === "keyword"
                                ? 5
                                : 4,
                          )}{" "}
                          · B {traceScoreLabel(compared.second.mode)}:{" "}
                          {formatTraceScore(
                            compared.second.mode === "vector"
                              ? item.second_cosine_similarity
                              : compared.second.mode === "keyword"
                                ? item.second_keyword_score
                                : item.second_rrf_score,
                            compared.second.mode === "hybrid"
                              ? 6
                              : compared.second.mode === "keyword"
                                ? 5
                                : 4,
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <p className="text-hint">
                Rank movement = B rank − A rank: negative moves toward rank 1, positive moves away.
                This is a descriptive comparison of stored outputs, not relevance evaluation or a
                causal quality assessment.
              </p>
            </>
          ) : (
            <p className="muted-panel-note">
              Select two different stored traces from this knowledge base, then compare. No search
              is rerun and no model API request is made.
            </p>
          )}
        </Panel>
      ) : null}
    </div>
  );
}
