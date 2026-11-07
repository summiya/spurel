"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Icon } from "@/components/icons";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  PageHeading,
  Panel,
} from "@/components/ui";
import { useDemoToast } from "@/components/workbench-shell";
import type { PersistedChunk } from "@/lib/chunk-inspection-types";
import {
  deltaPercent,
  percent,
  type EvaluationBaseline,
  type EvaluationCase,
  type EvaluationCaseSummary,
  type EvaluationComparison,
  type EvaluationDataset,
  type EvaluationJudgment,
  type EvaluationMode,
  type EvaluationRun,
  type EvaluationRunSummary,
  type JudgmentAudit,
  type QualityGate,
} from "@/lib/evaluation-types";
import { liveError, workspaceFetch } from "@/lib/live-client";
import type { LiveDocument, LiveKnowledgeBase } from "@/lib/live-types";
import { useWorkspacePages } from "@/lib/use-workspace-pages";

const modes: EvaluationMode[] = ["keyword", "vector", "hybrid"];
type Snapshot<T> = { knowledgeBaseId: string; datasetId: string; data: T };
type RunSnapshot = Snapshot<EvaluationRun>;
type CaseSnapshot = Snapshot<EvaluationCase>;

function formattedDate(input: string): string {
  const value = new Date(input);
  return Number.isNaN(value.getTime()) ? "Unknown" : value.toLocaleString();
}
function ms(value: number | null | undefined): string {
  return value === null || value === undefined ? "N/A" : value.toFixed(1) + " ms";
}
function loadScope<T>(
  snapshot: Snapshot<T> | null,
  base: string | null,
  dataset: string | null,
): T | null {
  return snapshot?.knowledgeBaseId === base && snapshot?.datasetId === dataset
    ? snapshot.data
    : null;
}
function metricRow(label: string, a: string, b: string, delta: string) {
  return { label, a, b, delta };
}
async function send<T>(path: string, method: "POST" | "PUT", body: unknown): Promise<T> {
  return workspaceFetch<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
function ErrorMessage({ message }: { message: string }) {
  return message ? (
    <p className="live-error" role="alert">
      {message}
    </p>
  ) : null;
}

export function LiveEvaluationsPage() {
  const notify = useDemoToast();
  const bases = useWorkspacePages<LiveKnowledgeBase>("/api/workspace/knowledge-bases");
  const [preferredBaseId, setPreferredBaseId] = useState("");
  const base = bases.items.find((item) => item.id === preferredBaseId) ?? bases.items[0] ?? null;
  const baseId = base?.id ?? null;
  const root = baseId ? "/api/workspace/knowledge-bases/" + baseId : null;
  const datasets = useWorkspacePages<EvaluationDataset>(
    root ? root + "/evaluation-datasets" : null,
  );
  const [preferredDatasetId, setPreferredDatasetId] = useState("");
  const dataset =
    datasets.items.find((item) => item.id === preferredDatasetId) ?? datasets.items[0] ?? null;
  const datasetId = dataset?.id ?? null;
  const path = root && datasetId ? root + "/evaluation-datasets/" + datasetId : null;
  const cases = useWorkspacePages<EvaluationCaseSummary>(path ? path + "/cases" : null);
  const runs = useWorkspacePages<EvaluationRunSummary>(path ? path + "/runs" : null);
  const baselines = useWorkspacePages<EvaluationBaseline>(path ? path + "/baselines" : null);
  const documents = useWorkspacePages<LiveDocument>(root ? root + "/documents" : null);
  const [preferredDocumentId, setPreferredDocumentId] = useState("");
  const document =
    documents.items.find(
      (item) => item.id === preferredDocumentId && item.active_chunk_version > 0,
    ) ??
    documents.items.find((item) => item.active_chunk_version > 0) ??
    null;
  const chunkPath = root && document ? root + "/documents/" + document.id + "/chunks" : null;
  const chunks = useWorkspacePages<PersistedChunk>(chunkPath);

  const [newDatasetName, setNewDatasetName] = useState("");
  const [query, setQuery] = useState("");
  const [labels, setLabels] = useState<EvaluationJudgment[]>([]);
  const [mode, setMode] = useState<EvaluationMode>("keyword");
  const [topK, setTopK] = useState(10);
  const [candidateK, setCandidateK] = useState(50);
  const [rrfK, setRrfK] = useState(60);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [auditSnapshot, setAuditSnapshot] = useState<Snapshot<JudgmentAudit> | null>(null);
  const [runSnapshot, setRunSnapshot] = useState<RunSnapshot | null>(null);
  const [caseSnapshot, setCaseSnapshot] = useState<CaseSnapshot | null>(null);
  const [firstId, setFirstId] = useState("");
  const [secondId, setSecondId] = useState("");
  const [comparisonSnapshot, setComparisonSnapshot] =
    useState<Snapshot<EvaluationComparison> | null>(null);
  const [gateSnapshot, setGateSnapshot] = useState<Snapshot<QualityGate> | null>(null);
  const [maxRecallDrop, setMaxRecallDrop] = useState(0.05);

  const audit = loadScope(auditSnapshot, baseId, datasetId);
  const selectedRun = runs.items.find((item) => item.run_id === firstId) ?? runs.items[0] ?? null;
  const otherRun =
    runs.items.find((item) => item.run_id === secondId && item.run_id !== selectedRun?.run_id) ??
    null;
  const persistedDetail = loadScope(runSnapshot, baseId, datasetId);
  const runDetail = persistedDetail?.run_id === selectedRun?.run_id ? persistedDetail : null;
  const currentRun = selectedRun ?? null;
  const comparison = loadScope(comparisonSnapshot, baseId, datasetId);
  const compared =
    comparison?.first.run_id === selectedRun?.run_id &&
    comparison?.second.run_id === otherRun?.run_id
      ? comparison
      : null;
  const gate = loadScope(gateSnapshot, baseId, datasetId);
  const caseDetail = loadScope(caseSnapshot, baseId, datasetId);

  function changedScope() {
    setError("");
    setLabels([]);
    setAuditSnapshot(null);
    setRunSnapshot(null);
    setCaseSnapshot(null);
    setComparisonSnapshot(null);
    setGateSnapshot(null);
    setFirstId("");
    setSecondId("");
  }
  async function action(name: string, callback: () => Promise<void>) {
    if (busy) return;
    setError("");
    setBusy(name);
    try {
      await callback();
    } catch (cause) {
      setError(liveError(cause));
    } finally {
      setBusy("");
    }
  }
  function addLabel(chunkId: string) {
    setLabels((current) =>
      current.some((item) => item.chunk_id === chunkId)
        ? current
        : [...current, { chunk_id: chunkId, relevance: 3 }],
    );
  }
  async function createDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!root || !newDatasetName.trim()) return;
    await action("dataset", async () => {
      const created = await send<EvaluationDataset>(root + "/evaluation-datasets", "POST", {
        name: newDatasetName.trim(),
      });
      setNewDatasetName("");
      changedScope();
      setPreferredDatasetId(created.id);
      datasets.refresh();
      notify("Evaluation dataset saved in PostgreSQL.");
    });
  }
  async function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!path || !query.trim()) return;
    if (!labels.length || !labels.some((item) => item.relevance > 0)) {
      setError("Label at least one active chunk as relevant (grade 1–3).");
      return;
    }
    await action("case", async () => {
      await send<EvaluationCase>(path + "/cases", "POST", {
        query: query.trim(),
        judgments: labels,
      });
      setQuery("");
      setLabels([]);
      cases.refresh();
      datasets.refresh();
      setAuditSnapshot(null);
      notify("Labeled case persisted. Run a judgment audit before benchmarking.");
    });
  }
  async function inspectCase(id: string) {
    if (!path || !baseId || !datasetId) return;
    await action("inspect-case", async () => {
      const data = await workspaceFetch<EvaluationCase>(path + "/cases/" + id);
      setCaseSnapshot({ knowledgeBaseId: baseId, datasetId, data });
    });
  }
  async function auditJudgments() {
    if (!path || !baseId || !datasetId) return;
    await action("audit", async () => {
      const data = await workspaceFetch<JudgmentAudit>(path + "/judgment-audit");
      setAuditSnapshot({ knowledgeBaseId: baseId, datasetId, data });
      notify(
        data.is_usable ? "Judgment audit passed." : "Judgment audit found stale or invalid labels.",
      );
    });
  }
  async function benchmark(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!path || !baseId || !datasetId || !cases.items.length) return;
    if (!audit || !audit.is_usable) {
      setError("Run a passing judgment audit before executing a benchmark.");
      return;
    }
    if (
      mode !== "keyword" &&
      !window.confirm(
        "This " +
          mode +
          " benchmark may call your embedding provider for every query and incur API charges. Run now?",
      )
    )
      return;
    await action("benchmark", async () => {
      const request =
        mode === "hybrid"
          ? { top_k: topK, candidate_k: Math.max(candidateK, topK), rrf_k: rrfK }
          : { top_k: topK };
      const data = await send<EvaluationRun>(path + "/evaluate/" + mode, "POST", request);
      setRunSnapshot({ knowledgeBaseId: baseId, datasetId, data });
      setFirstId(data.run_id);
      setSecondId("");
      setComparisonSnapshot(null);
      setGateSnapshot(null);
      runs.refresh();
      notify("Real " + mode + " benchmark completed and saved.");
    });
  }
  async function inspectRun(id: string) {
    if (!path || !baseId || !datasetId) return;
    setFirstId(id);
    setComparisonSnapshot(null);
    setGateSnapshot(null);
    await action("inspect-run", async () => {
      const data = await workspaceFetch<EvaluationRun>(path + "/runs/" + id);
      setRunSnapshot({ knowledgeBaseId: baseId, datasetId, data });
    });
  }
  async function compareRuns() {
    if (!path || !baseId || !datasetId || !selectedRun || !otherRun) return;
    await action("compare", async () => {
      const data = await send<EvaluationComparison>(path + "/run-comparisons", "POST", {
        first_run_id: selectedRun.run_id,
        second_run_id: otherRun.run_id,
      });
      setComparisonSnapshot({ knowledgeBaseId: baseId, datasetId, data });
      setGateSnapshot(null);
    });
  }
  async function checkGate() {
    if (!path || !baseId || !datasetId || !selectedRun || !otherRun) return;
    await action("gate", async () => {
      const data = await send<QualityGate>(path + "/quality-gates/evaluate", "POST", {
        first_run_id: selectedRun.run_id,
        second_run_id: otherRun.run_id,
        thresholds: { max_mean_recall_drop: maxRecallDrop },
      });
      setGateSnapshot({ knowledgeBaseId: baseId, datasetId, data });
    });
  }
  async function promoteBaseline() {
    if (
      !path ||
      !selectedRun ||
      !window.confirm(
        "Promote this saved run as the explicit baseline for its exact retrieval configuration?",
      )
    )
      return;
    await action("promote", async () => {
      await send<EvaluationBaseline>(path + "/baselines", "PUT", { run_id: selectedRun.run_id });
      baselines.refresh();
      notify("Saved baseline promoted for this configuration.");
    });
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="LIVE RETRIEVAL QUALITY"
        title="Evaluations"
        description="Label real chunks, benchmark retrieval strategies and inspect persisted quality evidence."
        badge="Live PostgreSQL metrics"
        action={
          <Link href="/traces" className="button ghost compact">
            <Icon name="clock" size={15} /> Trace history
          </Link>
        }
      />
      <div className="inline-notice">
        <Icon name="shield" size={16} /> Quality metrics require human judgments; no metrics are
        invented. Keyword benchmarks avoid query-time OpenAI calls. Vector and Hybrid can incur
        provider charges and run only on explicit confirmation.
      </div>

      <Panel
        title="Evaluation workspace"
        hint="Choose the real knowledge base and evaluation dataset"
      >
        {bases.loading ? (
          <LoadingState label="Loading knowledge bases" />
        ) : bases.error ? (
          <ErrorState description={bases.error} onRetry={bases.refresh} />
        ) : !base ? (
          <EmptyState
            title="No knowledge bases yet"
            description="Create and index a knowledge base first."
            icon="database"
            action={
              <Link href="/knowledge-bases" className="button ghost compact">
                Manage knowledge bases
              </Link>
            }
          />
        ) : (
          <div className="eval-controls">
            <div>
              <label className="field-label" htmlFor="eval-base">
                Knowledge base
              </label>
              <select
                id="eval-base"
                className="select-control"
                value={baseId ?? ""}
                onChange={(event) => {
                  changedScope();
                  setPreferredBaseId(event.target.value);
                  setPreferredDatasetId("");
                  setPreferredDocumentId("");
                }}
              >
                {bases.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="eval-dataset">
                Evaluation dataset
              </label>
              <select
                id="eval-dataset"
                className="select-control"
                value={datasetId ?? ""}
                disabled={!datasets.items.length}
                onChange={(event) => {
                  changedScope();
                  setPreferredDatasetId(event.target.value);
                }}
              >
                {!datasets.items.length ? <option value="">No datasets yet</option> : null}
                {datasets.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.case_count} cases
                  </option>
                ))}
              </select>
            </div>
            <button
              className="button ghost compact"
              type="button"
              onClick={() => {
                datasets.refresh();
                bases.refresh();
              }}
            >
              Refresh collections
            </button>
          </div>
        )}
        {bases.hasMore ? (
          <button
            type="button"
            className="button ghost compact"
            onClick={() => void bases.loadMore()}
          >
            Load more knowledge bases
          </button>
        ) : null}
        {datasets.loading ? <LoadingState label="Loading evaluation datasets" /> : null}
        {datasets.error ? (
          <ErrorState description={datasets.error} onRetry={datasets.refresh} />
        ) : null}
        {datasets.hasMore ? (
          <button
            type="button"
            className="button ghost compact"
            onClick={() => void datasets.loadMore()}
          >
            Load more datasets
          </button>
        ) : null}
        {base ? (
          <form className="eval-form-row" onSubmit={(event) => void createDataset(event)}>
            <div>
              <label htmlFor="new-eval-dataset" className="field-label">
                New dataset name
              </label>
              <input
                id="new-eval-dataset"
                className="input-control"
                maxLength={120}
                value={newDatasetName}
                onChange={(event) => setNewDatasetName(event.target.value)}
                placeholder="e.g. Employee handbook QA"
                required
              />
            </div>
            <button
              type="submit"
              className="button primary"
              disabled={Boolean(busy) || !newDatasetName.trim()}
            >
              <Icon name="plus" size={15} /> {busy === "dataset" ? "Creating…" : "Create dataset"}
            </button>
          </form>
        ) : null}
      </Panel>
      <ErrorMessage message={error} />

      {path && dataset ? (
        <>
          <Panel
            title="Label ground-truth cases"
            hint="Use active, persisted chunk UUIDs. Labels are grades 0–3; at least one must be relevant."
          >
            <div className="eval-controls">
              <div>
                <label className="field-label" htmlFor="eval-doc">
                  Indexed document
                </label>
                <select
                  id="eval-doc"
                  className="select-control"
                  value={document?.id ?? ""}
                  disabled={!document}
                  onChange={(event) => setPreferredDocumentId(event.target.value)}
                >
                  {!document ? <option value="">No indexed documents</option> : null}
                  {documents.items
                    .filter((item) => item.active_chunk_version > 0)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.filename}
                      </option>
                    ))}
                </select>
              </div>
              <div className="eval-control-hint">
                <Link
                  href={"/chunks?kb=" + baseId + (document ? "&doc=" + document.id : "")}
                  className="button ghost compact"
                >
                  <Icon name="layers" size={14} /> Inspect active chunks
                </Link>
              </div>
            </div>
            {documents.loading || chunks.loading ? (
              <LoadingState label="Loading indexed evidence" />
            ) : null}
            {documents.error ? (
              <ErrorState description={documents.error} onRetry={documents.refresh} />
            ) : null}
            {chunks.error ? (
              <ErrorState description={chunks.error} onRetry={chunks.refresh} />
            ) : null}
            {!document && !documents.loading ? (
              <p className="muted-panel-note">
                Index a document before creating labels. Uploaded-only documents have no active
                chunks.
              </p>
            ) : null}
            {document && !chunks.loading && chunks.items.length === 0 ? (
              <p className="muted-panel-note">No active chunks in the current document.</p>
            ) : null}
            <div className="eval-chunk-list">
              {chunks.items.map((chunk) => (
                <div className="eval-chunk-row" key={chunk.id}>
                  <div>
                    <strong>Chunk {chunk.index + 1}</strong>
                    <small>{chunk.id}</small>
                    <p>{chunk.text.slice(0, 220)}</p>
                  </div>
                  <button
                    type="button"
                    className="button ghost compact"
                    disabled={Boolean(busy) || labels.some((item) => item.chunk_id === chunk.id)}
                    onClick={() => addLabel(chunk.id)}
                  >
                    <Icon name="plus" size={14} />{" "}
                    {labels.some((item) => item.chunk_id === chunk.id) ? "Selected" : "Add label"}
                  </button>
                </div>
              ))}
            </div>
            {chunks.hasMore ? (
              <button
                type="button"
                className="button ghost compact"
                onClick={() => void chunks.loadMore()}
                disabled={chunks.loadingMore}
              >
                {chunks.loadingMore ? "Loading…" : "Load more active chunks"}
              </button>
            ) : null}
            <form onSubmit={(event) => void createCase(event)} className="eval-case-form">
              <div>
                <label className="field-label" htmlFor="eval-case-query">
                  Evaluation query
                </label>
                <textarea
                  id="eval-case-query"
                  className="input-control"
                  rows={2}
                  maxLength={8000}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="A real question your retrieval system should answer"
                  required
                />
              </div>
              {labels.length ? (
                <div className="eval-label-list">
                  {labels.map((item) => (
                    <div className="eval-label-item" key={item.chunk_id}>
                      <code title={item.chunk_id}>{item.chunk_id.slice(0, 13)}…</code>
                      <label>
                        <span className="field-label">Relevance</span>
                        <select
                          className="select-control"
                          value={item.relevance}
                          onChange={(event) =>
                            setLabels((current) =>
                              current.map((existing) =>
                                existing.chunk_id === item.chunk_id
                                  ? { ...existing, relevance: Number(event.target.value) }
                                  : existing,
                              ),
                            )
                          }
                        >
                          {[0, 1, 2, 3].map((grade) => (
                            <option value={grade} key={grade}>
                              {grade}{" "}
                              {grade === 0 ? "Irrelevant" : grade === 3 ? "Highly relevant" : ""}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        className="button ghost compact"
                        onClick={() =>
                          setLabels((current) =>
                            current.filter((existing) => existing.chunk_id !== item.chunk_id),
                          )
                        }
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted-panel-note">
                  Select one or more active chunks above to attach graded judgments.
                </p>
              )}
              <button
                type="submit"
                className="button primary"
                disabled={
                  Boolean(busy) || !query.trim() || !labels.some((item) => item.relevance > 0)
                }
              >
                <Icon name="plus" size={15} /> {busy === "case" ? "Saving…" : "Save labeled case"}
              </button>
            </form>
            <div className="eval-section-divider" />
            <div className="eval-action-heading">
              <strong>Saved labeled cases</strong>
              <button className="button ghost compact" type="button" onClick={cases.refresh}>
                <Icon name="refresh" size={14} /> Refresh
              </button>
            </div>
            {cases.loading ? <LoadingState label="Loading cases" /> : null}
            {cases.error ? <ErrorState description={cases.error} onRetry={cases.refresh} /> : null}
            {!cases.loading && !cases.items.length && !cases.error ? (
              <EmptyState
                title="No labeled cases"
                description="Add a query and label active chunks to begin."
                icon="book"
              />
            ) : null}
            {cases.items.length ? (
              <div className="responsive-table">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Query</th>
                      <th>Labels</th>
                      <th>Relevant</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.query}</td>
                        <td>{item.judgment_count}</td>
                        <td>{item.relevant_judgment_count}</td>
                        <td>
                          <button
                            className="table-link"
                            type="button"
                            onClick={() => void inspectCase(item.id)}
                          >
                            Inspect judgments
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {cases.hasMore ? (
              <button
                type="button"
                className="button ghost compact"
                onClick={() => void cases.loadMore()}
              >
                Load more cases
              </button>
            ) : null}
            {caseDetail ? (
              <div className="eval-diagnostics">
                <strong>Saved case: {caseDetail.query}</strong>
                {caseDetail.judgments.map((item) => (
                  <p key={item.chunk_id}>
                    <code>{item.chunk_id}</code> · grade {item.relevance}
                  </p>
                ))}
              </div>
            ) : null}
          </Panel>

          <Panel
            title="Judgment integrity"
            hint="Checks existing labels against the active document versions before a benchmark."
          >
            <button
              type="button"
              className="button ghost"
              onClick={() => void auditJudgments()}
              disabled={Boolean(busy) || cases.loading || !cases.items.length}
            >
              <Icon name="shield" size={15} />{" "}
              {busy === "audit" ? "Auditing…" : "Run judgment audit"}
            </button>
            {!audit ? (
              <p className="muted-panel-note">
                No audit loaded. A successful audit is required to enable Run benchmark.
              </p>
            ) : (
              <div className="eval-diagnostics">
                <strong>
                  {audit.is_usable ? "Judgments valid for active index" : "Judgments need review"}
                </strong>
                <div className="eval-mini-stats">
                  <span>Cases: {audit.case_count}</span>
                  <span>Judgments: {audit.judgment_count}</span>
                  <span>Invalid: {audit.invalid_count}</span>
                  <span>Inactive version: {audit.inactive_version_count}</span>
                  <span>Missing/out of scope: {audit.missing_or_out_of_scope_count}</span>
                </div>
                {audit.issues.map((item, index) => (
                  <p key={item.case_id + item.chunk_id + index}>
                    {item.reason} · chunk <code>{item.chunk_id}</code> · active version{" "}
                    {item.active_chunk_version ?? "N/A"}
                  </p>
                ))}
                {audit.issues_truncated ? <p>Issues list is truncated.</p> : null}
              </div>
            )}
          </Panel>

          <Panel
            title="Run benchmark"
            hint="Explicit execution against saved labels; full results are persisted."
          >
            <form className="eval-benchmark-controls" onSubmit={(event) => void benchmark(event)}>
              <div>
                <label className="field-label" htmlFor="eval-mode">
                  Retrieval strategy
                </label>
                <select
                  id="eval-mode"
                  className="select-control"
                  value={mode}
                  onChange={(event) => setMode(event.target.value as EvaluationMode)}
                >
                  {modes.map((item) => (
                    <option key={item} value={item}>
                      {item[0].toUpperCase() + item.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="field-label" htmlFor="eval-top-k">
                  Top K
                </label>
                <input
                  id="eval-top-k"
                  className="input-control"
                  type="number"
                  min={1}
                  max={100}
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value))}
                />
              </div>
              {mode === "hybrid" ? (
                <>
                  <div>
                    <label className="field-label" htmlFor="eval-candidate-k">
                      Candidate K
                    </label>
                    <input
                      id="eval-candidate-k"
                      className="input-control"
                      type="number"
                      min={topK}
                      max={100}
                      value={candidateK}
                      onChange={(event) => setCandidateK(Number(event.target.value))}
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="eval-rrf-k">
                      RRF K
                    </label>
                    <input
                      id="eval-rrf-k"
                      className="input-control"
                      type="number"
                      min={1}
                      max={1000}
                      value={rrfK}
                      onChange={(event) => setRrfK(Number(event.target.value))}
                    />
                  </div>
                </>
              ) : null}
              <button
                type="submit"
                className="button primary"
                disabled={
                  Boolean(busy) ||
                  !audit?.is_usable ||
                  !cases.items.length ||
                  !Number.isInteger(topK) ||
                  topK < 1 ||
                  topK > 100
                }
              >
                <Icon name="play" size={15} />{" "}
                {busy === "benchmark" ? "Running…" : "Run live benchmark"}
              </button>
            </form>
            {mode !== "keyword" ? (
              <p className="muted-panel-note">
                This mode can call your embedding provider once per evaluated query. Charges may
                apply. A confirmation will appear before execution.
              </p>
            ) : null}
          </Panel>

          <div className="metrics-grid">
            <MetricCard
              label="Mean Recall @ K"
              value={percent(currentRun?.mean_recall_at_k)}
              description={
                currentRun
                  ? currentRun.mode + " · " + currentRun.case_count + " labeled cases"
                  : "No persisted runs"
              }
              icon="search"
              direction="neutral"
            />
            <MetricCard
              label="Mean Precision @ K"
              value={percent(currentRun?.mean_precision_at_k)}
              description={currentRun ? "Top K " + currentRun.top_k : "No persisted runs"}
              icon="filter"
              direction="neutral"
            />
            <MetricCard
              label="MRR @ K"
              value={currentRun ? currentRun.mrr_at_k.toFixed(3) : "N/A"}
              description="Mean reciprocal rank"
              icon="layers"
              direction="neutral"
            />
            <MetricCard
              label="Mean NDCG @ K"
              value={percent(currentRun?.mean_ndcg_at_k)}
              description={
                currentRun
                  ? "Mean duration " + ms(currentRun.mean_duration_ms)
                  : "No persisted runs"
              }
              icon="chart"
              direction="neutral"
            />
          </div>

          <Panel
            title="Persisted benchmark history"
            hint="Actual PostgreSQL runs; select any run to inspect per-query metrics."
          >
            {currentRun && path ? (
              <>
                <div className="rag-live-answer-actions">
                  <a
                    className="button ghost compact"
                    href={`${path}/runs/${currentRun.run_id}/export?format=json`}
                    download={`spurel-evaluation-run-${currentRun.run_id}.json`}
                  >
                    <Icon name="download" size={15} /> Export run JSON
                  </a>
                  <a
                    className="button ghost compact"
                    href={`${path}/runs/${currentRun.run_id}/export?format=csv`}
                    download={`spurel-evaluation-run-${currentRun.run_id}.csv`}
                  >
                    <Icon name="download" size={15} /> Export run CSV
                  </a>
                </div>
                <p className="text-hint">
                  Exports include saved benchmark configuration, original case queries, aggregate
                  scores and per-case metrics. Handle exported data securely. No evaluation is rerun
                  by downloading.
                </p>
              </>
            ) : null}
            {runs.loading ? <LoadingState label="Loading benchmark history" /> : null}
            {runs.error ? <ErrorState description={runs.error} onRetry={runs.refresh} /> : null}
            {!runs.loading && !runs.items.length && !runs.error ? (
              <EmptyState
                title="No benchmark runs"
                description="Pass the judgment audit and execute Keyword first."
                icon="chart"
              />
            ) : null}
            {runs.items.length ? (
              <div className="responsive-table">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Mode</th>
                      <th>Recall</th>
                      <th>Precision</th>
                      <th>MRR</th>
                      <th>NDCG</th>
                      <th>Mean latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.items.map((item) => (
                      <tr
                        key={item.run_id}
                        className={item.run_id === currentRun?.run_id ? "selected" : ""}
                      >
                        <td>
                          <button
                            type="button"
                            className="table-link"
                            onClick={() => void inspectRun(item.run_id)}
                          >
                            {formattedDate(item.created_at)}
                          </button>
                          <small className="table-subline">{item.run_id.slice(0, 13)}…</small>
                        </td>
                        <td>
                          {item.mode} · K={item.top_k}
                        </td>
                        <td>{percent(item.mean_recall_at_k)}</td>
                        <td>{percent(item.mean_precision_at_k)}</td>
                        <td>{item.mrr_at_k.toFixed(3)}</td>
                        <td>{percent(item.mean_ndcg_at_k)}</td>
                        <td>{ms(item.mean_duration_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {runs.hasMore ? (
              <button
                className="button ghost compact"
                type="button"
                onClick={() => void runs.loadMore()}
              >
                Load more runs
              </button>
            ) : null}
            {runDetail ? (
              <>
                <div className="eval-diagnostics">
                  <strong>Saved run · {runDetail.run_id}</strong>
                  <p>
                    {runDetail.mode} · Top K {runDetail.top_k} · {runDetail.case_count} cases · mean
                    judgment coverage {percent(runDetail.mean_judgment_coverage_at_k)}
                  </p>
                  <p>
                    Embedding: {runDetail.embedding_provider ?? "Not used"} ·{" "}
                    {runDetail.embedding_model ?? "N/A"}
                  </p>
                </div>
                <div className="responsive-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Case / Query</th>
                        <th>Recall</th>
                        <th>Precision</th>
                        <th>RR</th>
                        <th>NDCG</th>
                        <th>Coverage</th>
                        <th>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runDetail.cases.map((item) => (
                        <tr key={item.case_id}>
                          <td>{item.query}</td>
                          <td>{percent(item.recall_at_k)}</td>
                          <td>{percent(item.precision_at_k)}</td>
                          <td>{item.reciprocal_rank_at_k.toFixed(3)}</td>
                          <td>{percent(item.ndcg_at_k)}</td>
                          <td>{percent(item.judgment_coverage_at_k)}</td>
                          <td>{ms(item.duration_ms)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : currentRun ? (
              <button
                type="button"
                className="button ghost compact"
                onClick={() => void inspectRun(currentRun.run_id)}
              >
                Inspect selected run
              </button>
            ) : null}
          </Panel>

          <Panel
            title="Compare two benchmark runs"
            hint="Read-only persisted comparisons. Delta = B − A; meaningful aggregates require matching case sets."
          >
            {runs.items.length < 2 ? (
              <p className="muted-panel-note">
                Run at least two evaluations on this dataset to compare them.
              </p>
            ) : (
              <>
                <div className="eval-compare-controls">
                  <div>
                    <label className="field-label" htmlFor="eval-run-a">
                      Run A · baseline candidate
                    </label>
                    <select
                      className="select-control"
                      id="eval-run-a"
                      value={selectedRun?.run_id ?? ""}
                      onChange={(event) => {
                        setFirstId(event.target.value);
                        setRunSnapshot(null);
                        setComparisonSnapshot(null);
                        setGateSnapshot(null);
                      }}
                    >
                      {runs.items.map((item) => (
                        <option value={item.run_id} key={item.run_id}>
                          {item.mode} · {formattedDate(item.created_at)} · {item.run_id.slice(0, 8)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="field-label" htmlFor="eval-run-b">
                      Run B · candidate
                    </label>
                    <select
                      className="select-control"
                      id="eval-run-b"
                      value={otherRun?.run_id ?? ""}
                      onChange={(event) => {
                        setSecondId(event.target.value);
                        setComparisonSnapshot(null);
                        setGateSnapshot(null);
                      }}
                    >
                      <option value="">Select distinct run B</option>
                      {runs.items
                        .filter((item) => item.run_id !== selectedRun?.run_id)
                        .map((item) => (
                          <option value={item.run_id} key={item.run_id}>
                            {item.mode} · {formattedDate(item.created_at)} ·{" "}
                            {item.run_id.slice(0, 8)}
                          </option>
                        ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    className="button primary"
                    disabled={!otherRun || Boolean(busy)}
                    onClick={() => void compareRuns()}
                  >
                    Compare saved runs
                  </button>
                </div>
                {compared ? (
                  <>
                    {!compared.aggregate_comparable ? (
                      <div className="inline-notice">
                        <Icon name="alert" size={16} /> Different query/case sets: aggregate deltas
                        are not comparable. Shared cases: {compared.shared_case_count}; changed
                        queries: {compared.query_changed_case_count}.
                      </div>
                    ) : null}
                    {!compared.same_retrieval_configuration ? (
                      <p className="muted-panel-note">
                        Retrieval configurations differ; interpret quality and latency deltas with
                        care.
                      </p>
                    ) : null}
                    <div className="responsive-table">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Metric</th>
                            <th>Run A</th>
                            <th>Run B</th>
                            <th>Delta B − A</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[
                            metricRow(
                              "Recall @ K",
                              percent(compared.first.mean_recall_at_k),
                              percent(compared.second.mean_recall_at_k),
                              deltaPercent(compared.mean_recall_delta),
                            ),
                            metricRow(
                              "Precision @ K",
                              percent(compared.first.mean_precision_at_k),
                              percent(compared.second.mean_precision_at_k),
                              deltaPercent(compared.mean_precision_delta),
                            ),
                            metricRow(
                              "MRR @ K",
                              compared.first.mrr_at_k.toFixed(3),
                              compared.second.mrr_at_k.toFixed(3),
                              compared.mrr_delta === null ? "N/A" : compared.mrr_delta.toFixed(3),
                            ),
                            metricRow(
                              "NDCG @ K",
                              percent(compared.first.mean_ndcg_at_k),
                              percent(compared.second.mean_ndcg_at_k),
                              deltaPercent(compared.mean_ndcg_delta),
                            ),
                            metricRow(
                              "Mean latency",
                              ms(compared.first.mean_duration_ms),
                              ms(compared.second.mean_duration_ms),
                              ms(compared.mean_duration_delta_ms),
                            ),
                          ].map((item) => (
                            <tr key={item.label}>
                              <td>{item.label}</td>
                              <td>{item.a}</td>
                              <td>{item.b}</td>
                              <td>{item.delta}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}
                <div className="eval-section-divider" />
                <div className="eval-gate-controls">
                  <div>
                    <label className="field-label" htmlFor="eval-max-recall-drop">
                      Maximum allowed Recall decrease (fraction)
                    </label>
                    <input
                      className="input-control"
                      id="eval-max-recall-drop"
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={maxRecallDrop}
                      onChange={(event) => setMaxRecallDrop(Number(event.target.value))}
                    />
                  </div>
                  <button
                    type="button"
                    className="button ghost"
                    disabled={!otherRun || Boolean(busy) || maxRecallDrop < 0 || maxRecallDrop > 1}
                    onClick={() => void checkGate()}
                  >
                    <Icon name="shield" size={15} /> Check quality gate
                  </button>
                  <button
                    type="button"
                    className="button ghost"
                    disabled={!selectedRun || Boolean(busy)}
                    onClick={() => void promoteBaseline()}
                  >
                    Promote run A as baseline
                  </button>
                </div>
                {gate && compared ? (
                  <div className="eval-diagnostics">
                    <strong>Quality gate: {gate.status.toUpperCase().replace("_", " ")}</strong>
                    {!gate.aggregate_comparable ? (
                      <p>Not evaluable because case/query sets differ.</p>
                    ) : null}
                    {gate.checks.map((check) => (
                      <p key={check.metric}>
                        {check.metric}: {check.passed ? "PASS" : "FAIL"} · regression{" "}
                        {check.regression_amount.toFixed(4)} · allowed{" "}
                        {check.allowed_regression.toFixed(4)}
                      </p>
                    ))}
                  </div>
                ) : null}
              </>
            )}
            {baselines.error ? (
              <ErrorState description={baselines.error} onRetry={baselines.refresh} />
            ) : null}
            <div className="eval-section-divider" />
            <strong>Promoted baselines</strong>
            {!baselines.loading && !baselines.items.length ? (
              <p className="muted-panel-note">No explicit baseline has been promoted yet.</p>
            ) : null}
            {baselines.items.map((item) => (
              <p className="muted-panel-note" key={item.baseline_id}>
                {item.mode} · K={item.top_k} · {item.run_id.slice(0, 13)}… · promoted{" "}
                {formattedDate(item.promoted_at)}
              </p>
            ))}
            {baselines.hasMore ? (
              <button
                type="button"
                className="button ghost compact"
                onClick={() => void baselines.loadMore()}
              >
                Load more baselines
              </button>
            ) : null}
          </Panel>
        </>
      ) : base && !datasets.loading && !datasets.error ? (
        <EmptyState
          icon="chart"
          title="Create an evaluation dataset"
          description="Choose a name above, then label actual active chunks to measure retrieval quality."
        />
      ) : null}
    </div>
  );
}
