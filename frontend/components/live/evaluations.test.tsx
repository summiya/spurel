import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveEvaluationsPage } from "./evaluations";

const toast = vi.hoisted(() => ({ notify: vi.fn() }));
vi.mock("@/components/workbench-shell", () => ({ useDemoToast: () => toast.notify }));

const kb = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const datasetId = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const docId = "3f7358dd-47f8-4dda-8284-3797e9045b8a";
const chunkId = "f10f0b5e-5765-41da-9287-b34992d38396";
const run1 = "c89b74bb-ad22-44c5-a4bc-3d1493635a70";
const run2 = "b71a0d37-637d-4f55-9749-40d6d1c2b953";
const root = "/api/workspace/knowledge-bases/" + kb;
const datasets = root + "/evaluation-datasets";
const evalRoot = datasets + "/" + datasetId;

const caseRecord = {
  id: "f30ecec9-f12f-480c-9002-7f83822544c1",
  dataset_id: datasetId,
  query: "Example policy query",
  judgment_count: 1,
  relevant_judgment_count: 1,
  created_at: "2026-11-03T18:00:00Z",
};
function run(id: string, recall: number) {
  return {
    run_id: id,
    knowledge_base_id: kb,
    dataset_id: datasetId,
    mode: "keyword",
    top_k: 10,
    candidate_k: null,
    rrf_k: null,
    embedding_provider: null,
    embedding_model: null,
    embedding_dimensions: null,
    case_count: 1,
    total_duration_ms: 12,
    mean_duration_ms: 12,
    judgment_coverage_case_count: 1,
    mean_judgment_coverage_at_k: 1,
    mean_precision_at_k: 0.1,
    mean_recall_at_k: recall,
    mrr_at_k: 1,
    mean_ndcg_at_k: 1,
    created_at: "2026-11-03T19:00:00Z",
    cases: [
      {
        position: 1,
        case_id: caseRecord.id,
        query: caseRecord.query,
        duration_ms: 12,
        judged_count: 1,
        relevant_count: 1,
        retrieved_count_at_k: 1,
        judged_retrieved_at_k: 1,
        relevant_retrieved_at_k: 1,
        judgment_coverage_at_k: 1,
        precision_at_k: 0.1,
        recall_at_k: recall,
        reciprocal_rank_at_k: 1,
        ndcg_at_k: 1,
      },
    ],
  };
}
const page = (items: unknown[]) => ({ items, limit: 50, offset: 0 });
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
let casesPresent = false;
let priorRuns = false;

function fakeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  const method = init?.method ?? "GET";
  if (url === "/api/workspace/knowledge-bases?offset=0") {
    return Promise.resolve(json(page([{ id: kb, name: "Engineering handbook" }])));
  }
  if (url === datasets + "?offset=0") {
    return Promise.resolve(
      json(
        page([
          {
            id: datasetId,
            knowledge_base_id: kb,
            name: "Quality QA",
            case_count: casesPresent ? 1 : 0,
            created_at: "2026-11-03T12:00:00Z",
          },
        ]),
      ),
    );
  }
  if (url === root + "/documents?offset=0") {
    return Promise.resolve(
      json(
        page([
          { id: docId, active_chunk_version: 1, filename: "handbook.txt", knowledge_base_id: kb },
        ]),
      ),
    );
  }
  if (url === root + "/documents/" + docId + "/chunks?offset=0") {
    return Promise.resolve(
      json(
        page([
          {
            id: chunkId,
            document_id: docId,
            index: 0,
            text: "Annual leave policy allows days off",
            start_offset: 0,
            end_offset: 35,
            has_embeddings: true,
            embedding_count: 1,
          },
        ]),
      ),
    );
  }
  if (url === evalRoot + "/cases?offset=0" && method === "GET")
    return Promise.resolve(json(page(casesPresent ? [caseRecord] : [])));
  if (url === evalRoot + "/runs?offset=0")
    return Promise.resolve(json(page(priorRuns ? [run(run1, 1), run(run2, 0.8)] : [])));
  if (url === evalRoot + "/baselines?offset=0") return Promise.resolve(json(page([])));
  if (url === evalRoot + "/cases" && method === "POST") {
    casesPresent = true;
    return Promise.resolve(
      json({ ...caseRecord, judgments: [{ chunk_id: chunkId, relevance: 3 }] }, 201),
    );
  }
  if (url === evalRoot + "/judgment-audit")
    return Promise.resolve(
      json({
        dataset_id: datasetId,
        case_count: 1,
        judgment_count: 1,
        is_usable: true,
        invalid_count: 0,
        inactive_version_count: 0,
        missing_or_out_of_scope_count: 0,
        issues_truncated: false,
        issues: [],
      }),
    );
  if (url === evalRoot + "/evaluate/keyword" && method === "POST") {
    priorRuns = true;
    return Promise.resolve(json(run(run1, 1)));
  }
  if (url === evalRoot + "/run-comparisons" && method === "POST")
    return Promise.resolve(
      json({
        dataset_id: datasetId,
        first: run(run1, 1),
        second: run(run2, 0.8),
        same_retrieval_configuration: true,
        same_case_set: true,
        aggregate_comparable: true,
        shared_case_count: 1,
        first_only_case_count: 0,
        second_only_case_count: 0,
        comparable_case_count: 1,
        query_changed_case_count: 0,
        mean_recall_delta: -0.2,
        mean_precision_delta: 0,
        mrr_delta: 0,
        mean_ndcg_delta: 0,
        mean_duration_delta_ms: 0,
        cases: [],
      }),
    );
  if (url === evalRoot + "/quality-gates/evaluate" && method === "POST")
    return Promise.resolve(
      json({
        status: "fail",
        aggregate_comparable: true,
        same_retrieval_configuration: true,
        unavailable_metrics: [],
        checks: [
          {
            metric: "mean_recall_at_k",
            first_value: 1,
            second_value: 0.8,
            delta: -0.2,
            allowed_regression: 0.05,
            regression_amount: 0.2,
            passed: false,
          },
        ],
      }),
    );
  if (url === evalRoot + "/baselines" && method === "PUT")
    return Promise.resolve(
      json({
        baseline_id: run1,
        run_id: run1,
        dataset_id: datasetId,
        mode: "keyword",
        top_k: 10,
        promoted_at: "2026-11-03T20:00:00Z",
        configuration_fingerprint: "a".repeat(64),
      }),
    );
  if (url === evalRoot + "/runs/" + run1 && method === "GET")
    return Promise.resolve(json(run(run1, 1)));
  return Promise.resolve(json({ error: "Unexpected test path " + url }, 500));
}

describe("SP-14 live evaluation workbench", () => {
  beforeEach(() => {
    casesPresent = false;
    priorRuns = false;
    toast.notify.mockClear();
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows real dataset and active chunks with N/A metrics and no implicit model calls", async () => {
    render(<LiveEvaluationsPage />);
    await screen.findByRole("option", { name: /Engineering handbook/i });
    await screen.findByText(/Annual leave policy allows days off/);
    expect(screen.getByText("Evaluations")).toBeInTheDocument();
    expect(screen.getByText("Live PostgreSQL metrics")).toBeInTheDocument();
    expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
    expect(
      vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === "GET"),
    ).toBe(true);
  });

  it("saves graded active-chunk labels, audits and only then executes an explicit Keyword benchmark", async () => {
    render(<LiveEvaluationsPage />);
    await screen.findByText(/Annual leave policy allows days off/);
    fireEvent.click(screen.getByRole("button", { name: /Add label/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Evaluation query" }), {
      target: { value: "Example policy query" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save labeled case/i }));
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([url, init]) => String(url) === evalRoot + "/cases" && init?.method === "POST",
          ),
      ).toBe(true),
    );
    await screen.findByText("Example policy query");
    fireEvent.click(screen.getByRole("button", { name: /Run judgment audit/i }));
    await screen.findByText("Judgments valid for active index");
    fireEvent.click(screen.getByRole("button", { name: "Run live benchmark" }));
    await screen.findByText(/Saved run ·/);
    expect(
      vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes("/evaluate/")),
    ).toHaveLength(1);
    const benchmarkCall = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => String(url).includes("/evaluate/"));
    expect(benchmarkCall?.[1]).toMatchObject({
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    expect(JSON.parse(String(benchmarkCall?.[1]?.body))).toEqual({ top_k: 10 });
  });

  it("exports a selected saved evaluation run without triggering any benchmark", async () => {
    priorRuns = true;
    render(<LiveEvaluationsPage />);
    const json = await screen.findByRole("link", { name: "Export run JSON" });
    const csv = screen.getByRole("link", { name: "Export run CSV" });
    expect(json).toHaveAttribute("href", `${evalRoot}/runs/${run1}/export?format=json`);
    expect(json).toHaveAttribute("download", `spurel-evaluation-run-${run1}.json`);
    expect(csv).toHaveAttribute("href", `${evalRoot}/runs/${run1}/export?format=csv`);
    expect(screen.getByText(/No evaluation is rerun by downloading/)).toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.every(([, opts]) => !opts?.method || opts.method === "GET"),
    ).toBe(true);
  });

  it("compares persisted runs, checks gates explicitly and never invokes an embedding model", async () => {
    casesPresent = true;
    priorRuns = true;
    render(<LiveEvaluationsPage />);
    await screen.findByRole("combobox", { name: "Run B · candidate" });
    const candidate = screen.getByRole("combobox", { name: "Run B · candidate" });
    fireEvent.change(candidate, { target: { value: run2 } });
    fireEvent.click(screen.getByRole("button", { name: "Compare saved runs" }));
    await screen.findByText("-20.0 pp");
    fireEvent.click(screen.getByRole("button", { name: /Check quality gate/i }));
    await screen.findByText("Quality gate: FAIL");
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes("/evaluate/"))).toBe(
      false,
    );
    const gateRequest = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => String(url).endsWith("/quality-gates/evaluate"));
    expect(JSON.parse(String(gateRequest?.[1]?.body)).thresholds).toEqual({
      max_mean_recall_drop: 0.05,
    });
  });
});
