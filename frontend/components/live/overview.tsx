"use client";

import Link from "next/link";
import { useState } from "react";

import { Icon } from "@/components/icons";
import { RetrievalQualityChart } from "@/components/live/retrieval-quality-chart";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  PageHeading,
  Panel,
} from "@/components/ui";
import { percent, type EvaluationDataset, type EvaluationRunSummary } from "@/lib/evaluation-types";
import type { LiveDocument, LiveKnowledgeBase } from "@/lib/live-types";
import type { RetrievalTraceSummary } from "@/lib/trace-history-types";
import { useWorkspacePages } from "@/lib/use-workspace-pages";

function dateLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown date" : date.toLocaleString();
}

function milliseconds(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) + " ms" : "N/A";
}

/** Scope summary values to the currently loaded backend pages; never claim global totals. */
export function LiveOverviewPage() {
  const bases = useWorkspacePages<LiveKnowledgeBase>("/api/workspace/knowledge-bases");
  const [preferredBaseId, setPreferredBaseId] = useState("");
  const base = bases.items.find((item) => item.id === preferredBaseId) ?? bases.items[0] ?? null;
  const root = base ? `/api/workspace/knowledge-bases/${base.id}` : null;

  const documents = useWorkspacePages<LiveDocument>(root ? root + "/documents" : null);
  const traces = useWorkspacePages<RetrievalTraceSummary>(root ? root + "/retrieval/traces" : null);
  const datasets = useWorkspacePages<EvaluationDataset>(
    root ? root + "/evaluation-datasets" : null,
  );

  const [preferredDatasetId, setPreferredDatasetId] = useState("");
  const dataset =
    datasets.items.find((item) => item.id === preferredDatasetId) ?? datasets.items[0] ?? null;
  const runs = useWorkspacePages<EvaluationRunSummary>(
    root && dataset ? root + "/evaluation-datasets/" + dataset.id + "/runs" : null,
  );

  const indexedDocuments = documents.items.filter((item) => item.active_chunk_version > 0);
  const latestRun = runs.items[0] ?? null;
  const baseQuery = base ? "?kb=" + base.id : "";

  const liveCounts: Array<{
    label: string;
    value: string;
    description: string;
    icon: "database" | "file" | "layers" | "clock";
  }> = [
    {
      label: "Knowledge bases",
      value: bases.loading ? "…" : bases.error ? "N/A" : String(bases.items.length),
      description: bases.hasMore ? "Loaded collections · more available" : "Loaded collections",
      icon: "database",
    },
    {
      label: "Documents",
      value: documents.loading ? "…" : documents.error ? "N/A" : String(documents.items.length),
      description: documents.hasMore
        ? "Loaded in selected knowledge base · more available"
        : "Loaded in selected knowledge base",
      icon: "file",
    },
    {
      label: "Indexed documents",
      value: documents.loading ? "…" : documents.error ? "N/A" : String(indexedDocuments.length),
      description: "Active chunk version · loaded documents only",
      icon: "layers",
    },
    {
      label: "Saved retrieval traces",
      value: traces.loading ? "…" : traces.error ? "N/A" : String(traces.items.length),
      description: traces.hasMore
        ? "Loaded history · more available"
        : "Loaded history for selected knowledge base",
      icon: "clock",
    },
  ];

  return (
    <div className="screen">
      <PageHeading
        eyebrow="LIVE RETRIEVAL INTELLIGENCE"
        title="Every retrieval decision. Visible."
        description="Inspect real indexed sources, retrieval executions and benchmark quality for your selected knowledge base."
        badge="Live FastAPI / PostgreSQL"
        action={
          <>
            <Link href={"/evaluations"} className="button ghost">
              <Icon name="chart" size={15} /> Evaluations
            </Link>
            <Link href={"/retrieval" + baseQuery} className="button primary">
              <Icon name="zap" size={16} /> New retrieval
            </Link>
          </>
        }
      />

      <section className="hero-banner">
        <div className="hero-content">
          <p className="eyebrow">RETRIEVAL, DECODED</p>
          <h2>Stop guessing why RAG works.</h2>
          <p>
            Go from real sources to ranked retrieval evidence, saved traces and measured quality.
          </p>
          <Link href={"/retrieval" + baseQuery} className="button ghost compact">
            Explore retrieval lab <Icon name="arrow-right" size={15} />
          </Link>
        </div>
        <div className="hero-orbit" aria-hidden="true">
          <span className="orbit-ring" />
          <span className="orbit-node first" />
          <span className="orbit-node second" />
          <span className="orbit-node third" />
          <span className="orbit-core" />
        </div>
      </section>

      <Panel
        title="Knowledge-base workspace"
        hint="All metrics below use real records and explicitly loaded pages"
      >
        {bases.loading ? (
          <LoadingState label="Loading live knowledge bases" />
        ) : bases.error ? (
          <>
            <ErrorState description={bases.error} onRetry={bases.refresh} />
            <Link className="button ghost compact" href="/operator/login">
              <Icon name="shield" size={15} /> Sign in as local operator
            </Link>
          </>
        ) : !base ? (
          <EmptyState
            icon="database"
            title="No knowledge bases yet"
            description="Create a collection and index documents to populate your live dashboard."
            action={
              <Link className="button primary" href="/knowledge-bases">
                Create a knowledge base
              </Link>
            }
          />
        ) : (
          <div className="overview-selector">
            <div>
              <label className="field-label" htmlFor="overview-kb">
                Knowledge base
              </label>
              <select
                id="overview-kb"
                className="select-control"
                value={base.id}
                onChange={(event) => {
                  setPreferredBaseId(event.target.value);
                  setPreferredDatasetId("");
                }}
              >
                {bases.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="button ghost compact"
              type="button"
              onClick={() => {
                bases.refresh();
                documents.refresh();
                traces.refresh();
                datasets.refresh();
                runs.refresh();
              }}
            >
              <Icon name="refresh" size={15} /> Refresh live data
            </button>
            <Link className="button ghost compact" href={"/knowledge-bases"}>
              <Icon name="database" size={15} /> Manage sources
            </Link>
          </div>
        )}
        {bases.hasMore ? (
          <button
            type="button"
            className="button ghost compact"
            disabled={bases.loadingMore}
            onClick={() => void bases.loadMore()}
          >
            {bases.loadingMore ? "Loading…" : "Load more knowledge bases"}
          </button>
        ) : null}
        <p className="text-hint">
          No provider calls are made by this dashboard. Counts represent loaded pages, not totals
          across all knowledge bases, documents or retrieval history.
        </p>
      </Panel>

      {base ? (
        <>
          <div className="metrics-grid">
            {liveCounts.map((item) => (
              <MetricCard
                key={item.label}
                label={item.label}
                value={item.value}
                description={item.description}
                icon={item.icon}
                direction="neutral"
              />
            ))}
          </div>
          <div className="dashboard-grid">
            <RetrievalQualityChart
              datasetName={dataset?.name ?? null}
              runs={runs.items}
              loading={runs.loading}
              error={runs.error}
              hasMore={runs.hasMore}
              loadingMore={runs.loadingMore}
              refresh={runs.refresh}
              loadMore={() => void runs.loadMore()}
            />
            <Panel
              title="Document index readiness"
              hint="Active indexing state of loaded documents; not a synthetic pipeline-health score"
              action={
                <Link className="button ghost compact" href={"/chunks" + baseQuery}>
                  Inspect chunks <Icon name="arrow-right" size={14} />
                </Link>
              }
            >
              {documents.loading ? <LoadingState label="Loading documents" /> : null}
              {documents.error ? (
                <ErrorState description={documents.error} onRetry={documents.refresh} />
              ) : null}
              {!documents.loading && !documents.error && !documents.items.length ? (
                <EmptyState
                  icon="file"
                  title="No documents uploaded"
                  description="Upload and index a document to make it searchable."
                  action={
                    <Link className="button ghost compact" href="/knowledge-bases">
                      Upload document
                    </Link>
                  }
                />
              ) : null}
              <div className="overview-doc-list">
                {documents.items.slice(0, 6).map((document) => (
                  <Link
                    key={document.id}
                    href={`/chunks?kb=${base.id}&doc=${document.id}`}
                    className="overview-doc-entry"
                  >
                    <span className="recent-icon">
                      <Icon name="file" size={17} />
                    </span>
                    <span className="recent-body">
                      <strong>{document.filename}</strong>
                      <small>{dateLabel(document.created_at)}</small>
                    </span>
                    <span
                      className={
                        "status-badge " + (document.active_chunk_version > 0 ? "success" : "")
                      }
                    >
                      {document.active_chunk_version > 0
                        ? "Indexed · v" + document.active_chunk_version
                        : "Not indexed"}
                    </span>
                  </Link>
                ))}
              </div>
              {documents.hasMore ? (
                <button
                  type="button"
                  className="button ghost compact"
                  onClick={() => void documents.loadMore()}
                  disabled={documents.loadingMore}
                >
                  {documents.loadingMore ? "Loading…" : "Load more documents"}
                </button>
              ) : null}
              {documents.items.length > 6 ? (
                <p className="text-hint">
                  Showing the first six loaded documents here; manage the full list in Knowledge
                  Bases.
                </p>
              ) : null}
            </Panel>
          </div>

          <div className="dashboard-grid">
            <Panel
              title="Latest benchmark quality"
              hint="Measured against persisted relevance labels, for one selected dataset"
              action={
                <Link className="button ghost compact" href="/evaluations">
                  Open evaluations <Icon name="arrow-right" size={14} />
                </Link>
              }
            >
              {datasets.loading ? <LoadingState label="Loading evaluation datasets" /> : null}
              {datasets.error ? (
                <ErrorState description={datasets.error} onRetry={datasets.refresh} />
              ) : null}
              {datasets.items.length ? (
                <>
                  <label className="field-label" htmlFor="overview-dataset">
                    Evaluation dataset
                  </label>
                  <select
                    id="overview-dataset"
                    className="select-control overview-dataset"
                    value={dataset?.id ?? ""}
                    onChange={(event) => setPreferredDatasetId(event.target.value)}
                  >
                    {datasets.items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} · {item.case_count} cases
                      </option>
                    ))}
                  </select>
                </>
              ) : !datasets.loading && !datasets.error ? (
                <EmptyState
                  icon="chart"
                  title="No evaluation datasets"
                  description="Create graded retrieval labels and run a benchmark to measure quality."
                  action={
                    <Link className="button ghost compact" href="/evaluations">
                      Start evaluation
                    </Link>
                  }
                />
              ) : null}
              {runs.loading ? <LoadingState label="Loading benchmark history" /> : null}
              {runs.error ? <ErrorState description={runs.error} onRetry={runs.refresh} /> : null}
              {latestRun ? (
                <div className="overview-quality">
                  <div className="overview-quality-meta">
                    <span className="status-badge">
                      {latestRun.mode} · K={latestRun.top_k}
                    </span>
                    <span className="text-hint">{dateLabel(latestRun.created_at)}</span>
                  </div>
                  {[
                    ["Recall @ K", percent(latestRun.mean_recall_at_k)],
                    ["Precision @ K", percent(latestRun.mean_precision_at_k)],
                    ["MRR @ K", latestRun.mrr_at_k.toFixed(3)],
                    ["NDCG @ K", percent(latestRun.mean_ndcg_at_k)],
                    ["Judgment coverage", percent(latestRun.mean_judgment_coverage_at_k)],
                    ["Mean duration", milliseconds(latestRun.mean_duration_ms)],
                  ].map(([name, value]) => (
                    <div className="pipeline-detail" key={name}>
                      <span>{name}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                  <p className="text-hint">
                    Latest loaded run only. No invented baseline, trends or p95 latency.
                  </p>
                </div>
              ) : dataset && !runs.loading && !runs.error ? (
                <EmptyState
                  icon="chart"
                  title="No benchmark runs"
                  description="Run a Keyword, Vector or Hybrid evaluation to produce measured quality."
                  action={
                    <Link href="/evaluations" className="button ghost compact">
                      Run benchmark
                    </Link>
                  }
                />
              ) : null}
              {datasets.hasMore ? (
                <button
                  className="button ghost compact"
                  type="button"
                  disabled={datasets.loadingMore}
                  onClick={() => void datasets.loadMore()}
                >
                  {datasets.loadingMore ? "Loading…" : "Load more datasets"}
                </button>
              ) : null}
            </Panel>
            <Panel
              title="Recent saved retrievals"
              hint="Newest first, scoped to selected knowledge base"
              action={
                <Link href={"/traces" + baseQuery} className="button ghost compact">
                  Trace history <Icon name="arrow-right" size={14} />
                </Link>
              }
            >
              {traces.loading ? <LoadingState label="Loading saved traces" /> : null}
              {traces.error ? (
                <ErrorState description={traces.error} onRetry={traces.refresh} />
              ) : null}
              {!traces.loading && !traces.error && !traces.items.length ? (
                <EmptyState
                  icon="search"
                  title="No retrieval traces"
                  description="Run a Keyword retrieval in the Retrieval Lab to save your first trace."
                  action={
                    <Link href={"/retrieval" + baseQuery} className="button ghost compact">
                      Run retrieval
                    </Link>
                  }
                />
              ) : null}
              <div className="recent-list">
                {traces.items.slice(0, 5).map((trace) => (
                  <Link
                    key={trace.id}
                    href={`/traces?kb=${base.id}&trace=${trace.id}`}
                    className="recent-item"
                  >
                    <span className="recent-icon">
                      <Icon name="search" size={17} />
                    </span>
                    <span className="recent-body">
                      <strong>{trace.query}</strong>
                      <small>
                        {trace.mode} · {trace.result_count} saved results ·{" "}
                        {dateLabel(trace.created_at)}
                      </small>
                    </span>
                    <strong className="recent-score">{milliseconds(trace.duration_ms)}</strong>
                  </Link>
                ))}
              </div>
              {traces.hasMore ? (
                <button
                  type="button"
                  className="button ghost compact"
                  disabled={traces.loadingMore}
                  onClick={() => void traces.loadMore()}
                >
                  {traces.loadingMore ? "Loading…" : "Load more saved traces"}
                </button>
              ) : null}
            </Panel>
          </div>

          <div className="dashboard-grid overview-quick-grid">
            <Panel
              title="Jump into your workflow"
              hint="Direct links into the live backend-backed tools"
            >
              <div className="quick-list">
                {(
                  [
                    ["/knowledge-bases", "database", "Manage knowledge bases"],
                    ["/chunks" + baseQuery, "layers", "Inspect active chunks"],
                    ["/retrieval" + baseQuery, "search", "Run retrieval"],
                    ["/traces" + baseQuery, "clock", "Compare traces"],
                    ["/evaluations", "chart", "Evaluate retrieval quality"],
                    ["/rag" + baseQuery, "sparkles", "Generate a RAG answer"],
                  ] as const
                ).map(([href, icon, label]) => (
                  <Link href={href} key={href} className="quick-item">
                    <Icon name={icon} size={17} />
                    <span>{label}</span>
                    <Icon name="arrow-up-right" size={14} />
                  </Link>
                ))}
              </div>
            </Panel>
          </div>
        </>
      ) : null}
    </div>
  );
}
