import { describe, expect, it } from "vitest";

import type { EvaluationRunSummary } from "./evaluation-types";
import {
  CHART_BOUNDS,
  qualityChartPoints,
  qualityConfigurationKey,
  qualityConfigurations,
  qualityPath,
} from "./quality-trend";

const now = Date.parse("2026-11-04T00:00:00Z");
const sample: EvaluationRunSummary = {
  run_id: "00000000-0000-4000-8000-000000000001",
  dataset_id: "00000000-0000-4000-8000-000000000002",
  mode: "keyword",
  top_k: 10,
  candidate_k: null,
  rrf_k: null,
  embedding_provider: null,
  embedding_model: null,
  embedding_dimensions: null,
  case_count: 3,
  mean_duration_ms: 14,
  total_duration_ms: 42,
  judgment_coverage_case_count: 3,
  mean_judgment_coverage_at_k: 1,
  mean_precision_at_k: 0.6,
  mean_recall_at_k: 0.8,
  mrr_at_k: 0.8,
  mean_ndcg_at_k: 0.85,
  created_at: "2026-11-03T00:00:00Z",
};
function run(overrides: Partial<EvaluationRunSummary>): EvaluationRunSummary {
  return { ...sample, ...overrides };
}

describe("saved quality-trend measurements", () => {
  it("separates retrieval modes, model settings, top K, hybrid settings and case counts", () => {
    const same = run({ run_id: "different" });
    expect(qualityConfigurationKey(same)).toBe(qualityConfigurationKey(sample));
    const otherModes = [
      run({ mode: "vector" }),
      run({ top_k: 5 }),
      run({ case_count: 4 }),
      run({ embedding_model: "text-embedding-version-2" }),
      run({ mode: "hybrid", candidate_k: 50, rrf_k: 60 }),
      run({ mode: "hybrid", candidate_k: 60, rrf_k: 60 }),
    ];
    for (const other of otherModes) {
      expect(qualityConfigurationKey(other)).not.toBe(qualityConfigurationKey(sample));
    }
    expect(qualityConfigurations([sample, same, ...otherModes])).toHaveLength(7);
  });

  it("includes only real runs inside the selected 7/30 day window", () => {
    const newest = sample;
    const older = run({
      run_id: "older",
      created_at: "2026-10-20T00:00:00Z",
      mean_recall_at_k: 0.9,
    });
    const wrongMode = run({ run_id: "mode", mode: "vector" });
    const future = run({ run_id: "future", created_at: "2026-11-05T00:00:00Z" });
    const invalid = run({ run_id: "invalid", mean_recall_at_k: Number.NaN });
    const all = [future, newest, older, newest, invalid, wrongMode];
    const key = qualityConfigurationKey(sample);
    expect(qualityChartPoints(all, key, 7, now).map((p) => p.run.run_id)).toEqual([newest.run_id]);
    expect(qualityChartPoints(all, key, 30, now).map((p) => p.run.run_id)).toEqual([
      "older",
      newest.run_id,
    ]);
  });

  it("uses actual timestamps and recorded percentages, not a smoothed sample curve", () => {
    const early = run({
      run_id: "early",
      created_at: "2026-10-29T00:00:00Z",
      mean_recall_at_k: 0.25,
      mean_precision_at_k: 0.5,
    });
    const points = qualityChartPoints([sample, early], qualityConfigurationKey(sample), 7, now);
    expect(points).toHaveLength(2);
    expect(points[0].x).toBeLessThan(points[1].x);
    const height = CHART_BOUNDS.height - CHART_BOUNDS.top - CHART_BOUNDS.bottom;
    expect(points[0].recallY).toBeCloseTo(CHART_BOUNDS.top + 0.75 * height);
    expect(points[0].precisionY).toBeCloseTo(CHART_BOUNDS.top + 0.5 * height);
    expect(points[1].recallY).toBeCloseTo(CHART_BOUNDS.top + 0.2 * height);
    expect(qualityPath(points, "recallY")).toContain("M");
    expect(qualityPath(points, "recallY")).toContain("L");
    expect(qualityPath([points[0]], "precisionY")).toBe("");
  });

  it("shows no fake points for empty or stale histories", () => {
    const key = qualityConfigurationKey(sample);
    expect(qualityChartPoints([], key, 7, now)).toEqual([]);
    expect(qualityChartPoints([run({ created_at: "not-a-date" })], key, 30, now)).toEqual([]);
    expect(qualityChartPoints([run({ created_at: "2026-09-01T00:00:00Z" })], key, 30, now)).toEqual(
      [],
    );
  });
});
