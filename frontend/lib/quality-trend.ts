import type { EvaluationRunSummary } from "@/lib/evaluation-types";

export type QualityWindowDays = 7 | 30;

export interface QualityConfiguration {
  key: string;
  label: string;
}

export interface QualityPoint {
  run: EvaluationRunSummary;
  timestamp: number;
  x: number;
  recallY: number;
  precisionY: number;
}

export const CHART_BOUNDS = {
  width: 600,
  height: 190,
  left: 42,
  right: 12,
  top: 16,
  bottom: 30,
} as const;
const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * A dataset can contain benchmarks from different retrieval modes, model versions
 * and case counts. Never connect their measurements as a single trend.
 * This still cannot prove that individual query/judgment sets are unchanged.
 */
export function qualityConfigurationKey(run: EvaluationRunSummary): string {
  return JSON.stringify([
    run.mode,
    run.top_k,
    run.candidate_k,
    run.rrf_k,
    run.embedding_provider,
    run.embedding_model,
    run.embedding_dimensions,
    run.case_count,
  ]);
}

export function qualityConfigurations(runs: EvaluationRunSummary[]): QualityConfiguration[] {
  const options: QualityConfiguration[] = [];
  const seen = new Set<string>();

  for (const run of runs) {
    const key = qualityConfigurationKey(run);
    if (seen.has(key)) continue;
    seen.add(key);
    const parts = [
      run.mode === "hybrid" ? "Hybrid" : run.mode === "vector" ? "Vector" : "Keyword",
      "Top " + run.top_k,
    ];
    if (run.mode === "hybrid") {
      parts.push("Candidates " + run.candidate_k, "RRF " + run.rrf_k);
    }
    if (run.embedding_model) parts.push(run.embedding_model);
    parts.push(run.case_count + (run.case_count === 1 ? " case" : " cases"));
    options.push({ key, label: parts.join(" · ") });
  }
  return options;
}

/** Only dated, valid, distinct persisted measurements from this one configuration. */
export function qualityRunsInWindow(
  runs: EvaluationRunSummary[],
  configurationKey: string,
  days: QualityWindowDays,
  nowMs: number,
): Array<{ run: EvaluationRunSummary; timestamp: number }> {
  const start = nowMs - days * DAY_MS;
  const unique = new Set<string>();
  return runs
    .filter((run) => {
      if (qualityConfigurationKey(run) !== configurationKey || unique.has(run.run_id)) return false;
      const timestamp = Date.parse(run.created_at);
      if (!Number.isFinite(timestamp) || timestamp < start || timestamp > nowMs) return false;
      if (
        !Number.isFinite(run.mean_recall_at_k) ||
        !Number.isFinite(run.mean_precision_at_k) ||
        run.mean_recall_at_k < 0 ||
        run.mean_recall_at_k > 1 ||
        run.mean_precision_at_k < 0 ||
        run.mean_precision_at_k > 1
      )
        return false;
      unique.add(run.run_id);
      return true;
    })
    .map((run) => ({ run, timestamp: Date.parse(run.created_at) }))
    .sort((a, b) => a.timestamp - b.timestamp || a.run.run_id.localeCompare(b.run.run_id));
}

export function qualityChartPoints(
  runs: EvaluationRunSummary[],
  configurationKey: string,
  days: QualityWindowDays,
  nowMs: number,
): QualityPoint[] {
  const plot = qualityRunsInWindow(runs, configurationKey, days, nowMs);
  const fromMs = nowMs - days * DAY_MS;
  const plotWidth = CHART_BOUNDS.width - CHART_BOUNDS.left - CHART_BOUNDS.right;
  const plotHeight = CHART_BOUNDS.height - CHART_BOUNDS.top - CHART_BOUNDS.bottom;

  return plot.map(({ run, timestamp }) => ({
    run,
    timestamp,
    x: CHART_BOUNDS.left + ((timestamp - fromMs) / (nowMs - fromMs)) * plotWidth,
    recallY: CHART_BOUNDS.top + (1 - run.mean_recall_at_k) * plotHeight,
    precisionY: CHART_BOUNDS.top + (1 - run.mean_precision_at_k) * plotHeight,
  }));
}

export function qualityPath(points: QualityPoint[], metric: "recallY" | "precisionY"): string {
  if (points.length < 2) return "";
  return points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${point[metric].toFixed(2)}`,
    )
    .join(" ");
}
