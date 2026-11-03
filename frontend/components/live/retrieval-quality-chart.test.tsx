import type { ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EvaluationRunSummary } from "@/lib/evaluation-types";
import { RetrievalQualityChart } from "./retrieval-quality-chart";

const now = Date.parse("2026-11-04T00:00:00Z");
const baseRun: EvaluationRunSummary = {
  run_id: "00000000-0000-4000-8000-000000000001",
  dataset_id: "00000000-0000-4000-8000-000000000002",
  mode: "keyword",
  top_k: 10,
  candidate_k: null,
  rrf_k: null,
  embedding_provider: null,
  embedding_model: null,
  embedding_dimensions: null,
  case_count: 2,
  mean_duration_ms: 9.5,
  total_duration_ms: 19,
  judgment_coverage_case_count: 2,
  mean_judgment_coverage_at_k: 1,
  mean_precision_at_k: 0.6,
  mean_recall_at_k: 0.8,
  mrr_at_k: 0.8,
  mean_ndcg_at_k: 0.8,
  created_at: "2026-11-03T00:00:00Z",
};
function sample(overrides: Partial<EvaluationRunSummary> = {}): EvaluationRunSummary {
  return { ...baseRun, ...overrides };
}
const refresh = vi.fn();
const loadMore = vi.fn();
function graph(
  runs: EvaluationRunSummary[],
  extras: Partial<ComponentProps<typeof RetrievalQualityChart>> = {},
) {
  return render(
    <RetrievalQualityChart
      datasetName="Real QA"
      runs={runs}
      loading={false}
      error=""
      hasMore={false}
      loadingMore={false}
      refresh={refresh}
      loadMore={loadMore}
      nowMs={now}
      {...extras}
    />,
  );
}

describe("Overview measured quality chart", () => {
  it("restores the chart from saved benchmark measurements rather than fixtures", () => {
    graph([
      sample(),
      sample({
        run_id: "00000000-0000-4000-8000-000000000003",
        created_at: "2026-10-30T00:00:00Z",
        mean_recall_at_k: 0.65,
        mean_precision_at_k: 0.4,
      }),
    ]);
    expect(screen.getByRole("heading", { name: "Retrieval quality over time" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Measured recall and precision over the last 7 days from 2 saved benchmark/i })).toBeInTheDocument();
    expect(document.querySelectorAll(".quality-real-recall")).toHaveLength(1);
    expect(document.querySelectorAll(".quality-real-precision")).toHaveLength(1);
    expect(screen.getByText(/2 saved run\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/Lines connect measurements, not daily estimates/i)).toBeInTheDocument();
    expect(screen.queryByText("Sample · 7 days")).not.toBeInTheDocument();
  });

  it("filters 7/30 days and connects points only when there are at least two runs", () => {
    graph([
      sample(),
      sample({
        run_id: "00000000-0000-4000-8000-000000000004",
        created_at: "2026-10-18T00:00:00Z",
        mean_recall_at_k: 0.25,
      }),
    ]);
    expect(screen.getByText(/Only one saved run matches/i)).toBeInTheDocument();
    expect(document.querySelectorAll(".quality-real-recall")).toHaveLength(0);

    fireEvent.change(screen.getByRole("combobox", { name: "Chart time window" }), {
      target: { value: "30" },
    });
    expect(screen.getByRole("img", { name: /over the last 30 days from 2 saved benchmark/i })).toBeInTheDocument();
    expect(document.querySelectorAll(".quality-real-recall")).toHaveLength(1);
  });

  it("does not merge different retrieval settings into one fabricated trend", () => {
    graph([
      sample(),
      sample({
        run_id: "00000000-0000-4000-8000-000000000005",
        mode: "vector",
      }),
    ]);
    expect(screen.getByRole("combobox", { name: "Retrieval configuration" })).toBeInTheDocument();
    expect(document.querySelectorAll(".quality-real-recall")).toHaveLength(0);
    const choice = screen.getByRole("combobox", { name: "Retrieval configuration" });
    const vectorOption = screen.getByRole("option", { name: /Vector · Top 10/ });
    fireEvent.change(choice, { target: { value: (vectorOption as HTMLOptionElement).value } });
    expect(screen.getByText(/Only one saved run matches/i)).toBeInTheDocument();
    expect(document.querySelectorAll(".quality-real-recall")).toHaveLength(0);
  });

  it("keeps the panel visible without inventing points before labeled evaluations", () => {
    graph([]);
    expect(screen.getByRole("heading", { name: "Retrieval quality over time" })).toBeInTheDocument();
    expect(screen.getByText("No benchmark history yet")).toBeInTheDocument();
    expect(screen.getByText(/Uploading documents alone does not measure retrieval quality/i)).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Measured recall/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run evaluation" })).toHaveAttribute("href", "/evaluations");
  });

  it("supports reading older saved pages without generating new evaluations", () => {
    refresh.mockClear();
    loadMore.mockClear();
    graph([sample()], { hasMore: true });
    fireEvent.click(screen.getByRole("button", { name: "Load older runs" }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
    expect(refresh).toHaveBeenCalledOnce();
    expect(loadMore).toHaveBeenCalledOnce();
  });

  it("shows a scoped empty or error state when history is unavailable", () => {
    const first = graph([], { datasetName: null });
    expect(screen.getByText("No evaluation dataset")).toBeInTheDocument();
    first.unmount();
    graph([], { error: "Backend temporarily unavailable" });
    expect(screen.getByRole("alert")).toHaveTextContent("Backend temporarily unavailable");
  });
});
